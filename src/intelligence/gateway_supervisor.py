"""
src/intelligence/gateway_supervisor.py - OmniRoute Gateway Supervisor & Key Validator
Handles headless daemon process lifecycle, TCP port probing, single-key validation,
and defensive fallback when Node/OmniRoute CLI is absent or ports conflict.
"""
from __future__ import annotations

import atexit
import json
import logging
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import weakref
import zipfile
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("tradebot0.gateway_supervisor")

PROVIDER_ENDPOINTS = {
    "deepseek": "https://api.deepseek.com/models",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/models",
    "groq": "https://api.groq.com/openai/v1/models",
    "openrouter": "https://openrouter.ai/api/v1/models",
}

DAEMON_LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB: rotate before the daemon log grows without bound
DAEMON_LOG_FILENAME = "omniroute_daemon.log"

# One-click runtime install (item 10 B3): the official Node.js zip for the
# app-local runtime, and the install log name. OmniRoute itself is installed
# with npm (no standalone binary exists); the 2.6 GB package is far too big
# to bundle in the installer, so it is downloaded once on first run.
RUNTIME_NODE_VERSION = "24.21.0"
RUNTIME_NODE_ZIP_URL = "https://nodejs.org/dist/v24.21.0/node-v24.21.0-win-x64.zip"
RUNTIME_INSTALL_LOG_FILENAME = "omniroute_install.log"


class _InstallCancelledError(Exception):
    """Raised inside the runtime-install worker when the user cancels.

    Caught by _run_runtime_install, which cleans up partial artifacts and
    reports the install as cancelled instead of failed.
    """


def _default_daemon_log_path() -> Path:
    """Default daemon log path, mirroring ConfigManager's data-dir layout:
    frozen exe -> %APPDATA%/TradeBot0/logs, source run -> <project root>/logs."""
    if getattr(sys, "frozen", False):
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) / "TradeBot0" if appdata else Path.home() / ".tradebot0"
    else:
        base = Path(__file__).resolve().parent.parent.parent
    return base / "logs" / DAEMON_LOG_FILENAME


def _default_install_log_path() -> Path:
    """Same base as the daemon log; the install log records the one-click
    Node.js / OmniRoute install (item 10 B3)."""
    return _default_daemon_log_path().with_name(RUNTIME_INSTALL_LOG_FILENAME)


class GatewaySupervisor:
    """
    Manages OmniRoute gateway lifecycle and performs fail-safe key verification.
    Guarantees that no error causes an unhandled exception or freezes the UI loop.
    """

    # Live supervisors only (weak refs): the atexit handler must not
    # keep dead instances alive.
    _live_supervisors: "weakref.WeakSet[GatewaySupervisor]" = weakref.WeakSet()
    _atexit_registered: bool = False

    @classmethod
    def _shutdown_all_at_exit(cls) -> None:
        for sup in list(cls._live_supervisors):
            try:
                sup.shutdown()
            except Exception as e:
                logger.debug("Gateway shutdown at exit failed: %s", e)

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 20128,
        daemon_log_path: Optional[Path] = None,
        install_log_path: Optional[Path] = None,
    ) -> None:
        self.host = host
        self.port = port
        self.child_process: Optional[subprocess.Popen] = None
        self.is_self_spawned: bool = False
        # Where a spawned daemon's stdout/stderr go (item 8): a real log
        # file, not DEVNULL, so a failed startup leaves something to read.
        # Tests inject a tmp path; production uses <root>/logs/omniroute_daemon.log.
        self.daemon_log_path: Path = (
            Path(daemon_log_path) if daemon_log_path is not None else _default_daemon_log_path()
        )
        self._daemon_log_file = None
        self.install_log_path: Path = (
            Path(install_log_path) if install_log_path is not None else _default_install_log_path()
        )
        # One-click runtime install state (item 10 B3); guarded by a lock
        # because the worker thread and the bridge read it concurrently.
        self._install_lock = threading.Lock()
        self._install_thread: Optional[threading.Thread] = None
        # Cancel support + progress (wizard progress bar / close warning):
        # the worker polls this event; the cancel path may also hold the
        # running npm child so it can be killed from another thread.
        self._install_cancel_event = threading.Event()
        self._install_proc: Optional[subprocess.Popen] = None
        self._install_progress: Optional[int] = None  # 0-100 when real, else None
        self._install_phase: str = ""
        # Double-spawn guard for start_daemon (F5): two concurrent callers
        # (wizard save + runtime-install finish) used to both pass the
        # port check and spawn two daemons; the second overwrote
        # child_process and orphaned the first.
        self._daemon_lock = threading.Lock()
        self._daemon_starting: bool = False
        self._daemon_starting_thread: Optional[int] = None
        self.install_status: str = "idle"  # idle | downloading-node | installing-omniroute | done | failed | cancelled
        self.install_message: str = ""

        # Exit hook: a single class-level handler shuts down whatever
        # supervisors are still alive (WeakSet, so dead instances drop out
        # on their own). The old code registered bound self.shutdown per
        # instance, which retained every supervisor ever built until
        # process exit.
        GatewaySupervisor._live_supervisors.add(self)
        if not GatewaySupervisor._atexit_registered:
            GatewaySupervisor._atexit_registered = True
            atexit.register(GatewaySupervisor._shutdown_all_at_exit)

    @classmethod
    def _get_daemon_command(cls, port: int) -> Optional[List[str]]:
        """
        Builds the command line arguments to spawn OmniRoute in 100% headless background mode.
        On Windows, directly uses `node.exe <path_to_omniroute.mjs> serve --no-open --port <port>`
        to bypass `cmd.exe` and `omniroute.cmd` batch scripts which trigger Windows Terminal popups.
        """
        node_bin = cls._resolve_node_bin()
        if node_bin:
            # 0. App-local runtime install first (item 10 B3): the app's own
            # Node.js + OmniRoute live under the per-user runtime folder,
            # never in the global npm tree.
            local_mjs = cls._runtime_base() / "omniroute" / "node_modules" / "omniroute" / "bin" / "omniroute.mjs"
            if local_mjs.is_file():
                return [node_bin, str(local_mjs), "serve", "--no-open", "--port", str(port)]

            # 1. Check global npm location in APPDATA
            appdata = os.environ.get("APPDATA", "")
            if appdata:
                global_mjs = os.path.join(appdata, "npm", "node_modules", "omniroute", "bin", "omniroute.mjs")
                if os.path.exists(global_mjs):
                    return [node_bin, global_mjs, "serve", "--no-open", "--port", str(port)]

            # 2. Check relative to omniroute command if present in PATH
            omni_path = shutil.which("omniroute.cmd") or shutil.which("omniroute")
            if omni_path:
                rel_mjs = os.path.join(os.path.dirname(omni_path), "node_modules", "omniroute", "bin", "omniroute.mjs")
                if os.path.exists(rel_mjs):
                    return [node_bin, rel_mjs, "serve", "--no-open", "--port", str(port)]

        omni_bin = (
            shutil.which("omniroute")
            or shutil.which("omniroute.cmd")
            or shutil.which("npx")
        )
        if omni_bin:
            if "npx" in os.path.basename(omni_bin).lower():
                return [omni_bin, "-y", "omniroute", "serve", "--no-open", "--port", str(port)]
            return [omni_bin, "serve", "--no-open", "--port", str(port)]

        return None

    @classmethod
    def is_cli_available(cls) -> bool:
        """Checks if omniroute CLI or direct node runner is found in system PATH."""
        if cls._get_daemon_command(20128) is not None:
            return True
        return bool(shutil.which("omniroute") or shutil.which("omniroute.cmd") or shutil.which("npx"))

    # --- App-local runtime (item 10 A4 / B3) --------------------------------
    @staticmethod
    def _runtime_base() -> Path:
        """Per-user runtime folder for the app's own Node.js + OmniRoute.
        %LOCALAPPDATA%\\TradeBot0\\runtime on Windows (LOCALAPPDATA, not
        APPDATA, so a 2.6 GB install never roams with the user profile),
        falling back to %APPDATA% then ~/.tradebot0. Program Files is not
        writable at runtime, so the runtime lives here -- never in the
        install folder and never in the global npm tree."""
        local = os.environ.get("LOCALAPPDATA")
        if local:
            return Path(local) / "TradeBot0" / "runtime"
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "TradeBot0" / "runtime"
        return Path.home() / ".tradebot0" / "runtime"

    @classmethod
    def _runtime_node_bin(cls) -> Optional[str]:
        node_exe = cls._runtime_base() / "node" / "node.exe"
        return str(node_exe) if node_exe.is_file() else None

    @classmethod
    def _resolve_node_bin(cls) -> Optional[str]:
        """Node executable: the app-local runtime first, then system Node."""
        return cls._runtime_node_bin() or shutil.which("node") or shutil.which("node.exe")

    @classmethod
    def _resolve_npm_bin(cls, node_bin: Optional[str]) -> Optional[str]:
        """npm next to the given node.exe (runtime install), else npm on PATH."""
        if node_bin:
            node_dir = Path(node_bin).parent
            for name in ("npm.cmd", "npm"):
                cand = node_dir / name
                if cand.is_file():
                    return str(cand)
        return shutil.which("npm") or shutil.which("npm.cmd")

    @classmethod
    def node_available(cls) -> bool:
        """True when any Node.js is usable (app-local runtime or system)."""
        return cls._resolve_node_bin() is not None

    @classmethod
    def omniroute_installed(cls) -> bool:
        """True when an omniroute package is actually present (app-local
        runtime or the global npm tree). npx alone does NOT count: npx would
        download ~2.6 GB on first start and the 30 s spawn wait would kill it."""
        local_mjs = cls._runtime_base() / "omniroute" / "node_modules" / "omniroute" / "bin" / "omniroute.mjs"
        if local_mjs.is_file():
            return True
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            global_mjs = os.path.join(appdata, "npm", "node_modules", "omniroute", "bin", "omniroute.mjs")
            if os.path.exists(global_mjs):
                return True
        omni_path = shutil.which("omniroute.cmd") or shutil.which("omniroute")
        if omni_path:
            rel_mjs = os.path.join(os.path.dirname(omni_path), "node_modules", "omniroute", "bin", "omniroute.mjs")
            if os.path.exists(rel_mjs):
                return True
        return False

    @classmethod
    def gateway_unavailable_reason(cls) -> Optional[str]:
        """English reason string for the setup wizard when the gateway cannot
        start, or None when it can."""
        if not cls.node_available():
            return "Node.js is not installed. The OmniRoute gateway needs Node.js 22 or later."
        if not cls.omniroute_installed():
            return "OmniRoute is not installed. Install it with one click below (about 3-5 min, ~2.6 GB)."
        if not cls.is_cli_available():
            return "OmniRoute CLI is not installed or not found in system PATH."
        return None

    def install_runtime_status(self) -> Dict[str, Any]:
        """Current one-click install state for the wizard poll loop.

        progress is a real 0-100 percent only while the Node.js zip is
        downloading (Content-Length bytes received / total); it is None in
        every other phase because npm reports no trustworthy percent, so
        the frontend shows an indeterminate bar there instead of a
        fabricated number.
        """
        with self._install_lock:
            return {
                "status": self.install_status,
                "message": self.install_message,
                "progress": self._install_progress,
                "phase": self._install_phase,
            }

    def _set_install_status(
        self, status: str, message: str,
        progress: Optional[int] = None, phase: str = "",
    ) -> None:
        with self._install_lock:
            self.install_status = status
            self.install_message = message
            self._install_progress = progress
            self._install_phase = phase
        logger.info("Runtime install status: %s - %s", status, message)
        try:
            self.install_log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.install_log_path, "a", encoding="utf-8", errors="replace") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {status}: {message}\n")
        except Exception as e:
            logger.debug("Failed to write install log: %s", e)

    def _set_install_progress(self, progress: Optional[int]) -> None:
        """Updates only the download percent (no log spam: the Node.js zip
        reports once per MB read)."""
        with self._install_lock:
            self._install_progress = progress

    def start_runtime_install(self) -> Dict[str, Any]:
        """Starts the one-click Node.js + OmniRoute install in a background
        thread (item 10 B3). Safe to call repeatedly: a running install is
        not started twice. The arena keeps running in Pure Math mode while
        the install runs; the gateway is started automatically when it ends."""
        with self._install_lock:
            if self.install_status in ("downloading-node", "installing-omniroute"):
                return {"ok": True, "message": "Installation already running."}
            if self.node_available() and self.omniroute_installed():
                self.install_status = "done"
                self.install_message = "OmniRoute is already installed."
                self._install_progress = 100
                self._install_phase = "Installed"
                return {"ok": True, "message": self.install_message}
            self._install_cancel_event.clear()
            self.install_status = "downloading-node" if not self.node_available() else "installing-omniroute"
            self.install_message = "Starting installation in the background..."
            self._install_progress = None
            self._install_phase = (
                "Downloading Node.js" if self.install_status == "downloading-node"
                else "Installing OmniRoute"
            )
            t = threading.Thread(target=self._run_runtime_install, name="omniroute-runtime-install", daemon=True)
            self._install_thread = t
            t.start()
            return {"ok": True, "message": "Installation started in the background."}

    def cancel_runtime_install(self) -> Dict[str, Any]:
        """Cancels a running one-click install (wizard close warning).

        Sets the cancel event and kills the running npm child (whole
        process tree on Windows, where npm runs under cmd.exe); the
        worker thread notices, cleans up partial artifacts, and reports
        status "cancelled". Safe to call when nothing is running.
        """
        with self._install_lock:
            if self.install_status not in ("downloading-node", "installing-omniroute"):
                return {"ok": False, "message": "No installation is running."}
            self._install_cancel_event.set()
            proc = self._install_proc
        if proc is not None and proc.poll() is None:
            self._terminate_install_proc(proc)
        return {"ok": True, "message": "Cancelling installation..."}

    @staticmethod
    def _terminate_install_proc(proc: subprocess.Popen) -> None:
        """Kills an npm child and, on Windows, its whole tree: npm.cmd
        runs under cmd.exe, so killing cmd.exe alone would orphan the
        node.exe actually doing the install."""
        try:
            proc.kill()
        except Exception as e:
            logger.debug("Failed to kill install process: %s", e)
        if sys.platform == "win32":
            try:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=15, creationflags=0x08000000,
                )
            except Exception as e:
                logger.debug("taskkill for install process failed: %s", e)
        try:
            proc.wait(timeout=10)
        except Exception:
            pass

    def _cleanup_cancelled_install(self, base: Path) -> None:
        """Removes partial install artifacts after a cancel so a later
        attempt starts clean and omniroute_installed() never misreports
        a half-installed package as good. A fully extracted Node.js is
        kept: it is valid, and the retry then skips the download."""
        for target in (base / "node.zip", base / "_node_tmp", base / "omniroute"):
            try:
                if target.is_dir():
                    shutil.rmtree(target, ignore_errors=True)
                elif target.exists():
                    target.unlink()
            except Exception as e:
                logger.debug("Cancel cleanup failed for %s: %s", target, e)

    def _run_runtime_install(self) -> None:
        """Background worker: Node.js zip (if needed) + npm install omniroute
        into the app-local runtime folder, then start the gateway."""
        try:
            base = self._runtime_base()
            base.mkdir(parents=True, exist_ok=True)
            if self._install_cancel_event.is_set():
                raise _InstallCancelledError("Installation cancelled.")
            node_bin = self._resolve_node_bin()
            if node_bin is None:
                self._set_install_status("downloading-node", "Downloading Node.js (about 37 MB)...", phase="Downloading Node.js")
                node_bin = self._download_node(base)
            npm_bin = self._resolve_npm_bin(node_bin)
            if npm_bin is None:
                raise RuntimeError("npm was not found next to Node.js.")
            self._set_install_status("installing-omniroute", "Installing OmniRoute (about 3-5 min, ~2.6 GB)...", phase="Installing OmniRoute")
            self._npm_install_omniroute(npm_bin, base)
            if self._install_cancel_event.is_set():
                raise _InstallCancelledError("Installation cancelled.")
            if not self.omniroute_installed():
                raise RuntimeError("OmniRoute install finished but the package was not found.")
            self._set_install_status("done", "OmniRoute installed. Starting the gateway...", progress=100, phase="Installed")
            ok, msg = self.start_daemon(max_wait_sec=30.0)
            if ok:
                self._set_install_status("done", "OmniRoute installed and the gateway is online.", progress=100, phase="Installed")
            else:
                self._set_install_status("done", f"OmniRoute installed, but the gateway did not start: {msg}", progress=100, phase="Installed")
        except _InstallCancelledError:
            logger.info("OmniRoute runtime install cancelled by user.")
            self._cleanup_cancelled_install(self._runtime_base())
            self._set_install_status("cancelled", "Installation cancelled.", phase="Cancelled")
        except Exception as e:
            logger.error("OmniRoute runtime install failed: %s", e)
            self._set_install_status("failed", f"Installation failed: {e}", phase="Failed")

    def _download_node(self, base: Path) -> str:
        """Downloads the official Node.js zip and extracts it to
        <runtime>/node. Returns the node.exe path.

        Reads in 1 MB chunks so the wizard can show a real percent
        (bytes received / Content-Length) and so a cancel is noticed
        promptly instead of only after the whole 37 MB arrives. When
        the server sends no Content-Length, progress stays None and
        the frontend shows an indeterminate bar.
        """
        node_dir = base / "node"
        zip_path = base / "node.zip"
        req = urllib.request.Request(
            RUNTIME_NODE_ZIP_URL, headers={"User-Agent": "TradeBot0-Installer/1.0"}
        )
        with urllib.request.urlopen(req, timeout=600) as resp, open(zip_path, "wb") as f:
            total = None
            try:
                raw_total = resp.headers.get("Content-Length")
                total = int(raw_total) if raw_total else None
            except Exception:
                total = None
            downloaded = 0
            while True:
                if self._install_cancel_event.is_set():
                    raise _InstallCancelledError("Installation cancelled.")
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    self._set_install_progress(min(100, int(downloaded * 100 / total)))
        tmp_dir = base / "_node_tmp"
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(tmp_dir)
        if self._install_cancel_event.is_set():
            raise _InstallCancelledError("Installation cancelled.")
        entries = [p for p in tmp_dir.iterdir()]
        src_dir = entries[0] if len(entries) == 1 and entries[0].is_dir() else tmp_dir
        if node_dir.exists():
            shutil.rmtree(node_dir)
        shutil.move(str(src_dir), str(node_dir))
        shutil.rmtree(tmp_dir, ignore_errors=True)
        try:
            zip_path.unlink()
        except Exception as e:
            logger.debug("Failed to delete Node.js zip after extract: %s", e)
        node_exe = node_dir / "node.exe"
        if not node_exe.is_file():
            raise RuntimeError("Downloaded Node.js package has no node.exe.")
        self._set_install_progress(100)
        return str(node_exe)

    def _npm_install_omniroute(self, npm_bin: str, base: Path) -> None:
        """Runs `npm install --prefix <runtime>/omniroute omniroute`.
        npm 11+ blocks postinstall scripts by default, so the documented
        --allow-scripts list is passed first (native bindings need it);
        if npm rejects the flag (older npm), retry once without it."""
        prefix = base / "omniroute"
        prefix.mkdir(parents=True, exist_ok=True)
        allow = "--allow-scripts=omniroute,better-sqlite3,keytar,tls-client-node,onnxruntime-node,sharp,core-js,esbuild,@parcel/watcher,@swc/core,protobufjs,koffi"
        attempts = [
            [npm_bin, "install", "--prefix", str(prefix), allow, "omniroute"],
            [npm_bin, "install", "--prefix", str(prefix), "omniroute"],
        ]
        last_error = ""
        with open(self.install_log_path, "a", encoding="utf-8", errors="replace", buffering=1) as log_file:
            log_file.write(
                f"--- npm install omniroute --prefix {prefix} "
                f"at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n"
            )
            for i, cmd in enumerate(attempts):
                log_file.write(f"--- attempt {i + 1}: {' '.join(cmd)} ---\n")
                log_file.flush()
                # Popen (not run) so a cancel can kill the child: the
                # poll loop checks the cancel event every 0.25 s and the
                # 30-minute deadline, mirroring the old run(timeout=1800).
                try:
                    child_env = os.environ.copy()
                    for key in ("_MEIPASS", "_MEIPASS2", "PYTHONPATH", "PYTHONHOME"):
                        child_env.pop(key, None)
                    creation_flags = 0x08000000 if sys.platform == "win32" else 0
                    proc = subprocess.Popen(
                        cmd, stdout=log_file, stderr=subprocess.STDOUT,
                        env=child_env, creationflags=creation_flags,
                    )
                    with self._install_lock:
                        self._install_proc = proc
                    try:
                        deadline = time.monotonic() + 1800
                        while True:
                            if self._install_cancel_event.is_set():
                                self._terminate_install_proc(proc)
                                raise _InstallCancelledError("Installation cancelled.")
                            rc = proc.poll()
                            if rc is not None:
                                break
                            if time.monotonic() > deadline:
                                self._terminate_install_proc(proc)
                                raise RuntimeError("npm install timed out after 30 minutes.")
                            time.sleep(0.25)
                    finally:
                        with self._install_lock:
                            if self._install_proc is proc:
                                self._install_proc = None
                except _InstallCancelledError:
                    raise
                if proc.returncode == 0:
                    return
                last_error = f"npm install exited with code {proc.returncode} (attempt {i + 1})"
                tail = self._tail_install_log(2000)
                if i == 0 and ("allow-scripts" in tail or "unknown option" in tail.lower()):
                    continue
                break
        raise RuntimeError(last_error or "npm install failed.")

    def _tail_install_log(self, n_chars: int) -> str:
        """Last n_chars of the install log, for failure diagnosis."""
        try:
            text = self.install_log_path.read_text(encoding="utf-8", errors="replace")
            return text[-n_chars:]
        except Exception:
            return ""

    def is_port_open(self, timeout: float = 0.35) -> bool:
        """Fast TCP socket probe to verify if port is actively listening."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(timeout)
                return s.connect_ex((self.host, self.port)) == 0
        except Exception as e:
            logger.debug("Port probe error for %s:%s: %s", self.host, self.port, e)
            return False

    def probe_health(self, timeout: float = 1.0) -> Tuple[bool, Dict[str, Any]]:
        """
        Sends an HTTP GET probe to /api/health to confirm the service is OmniRoute.
        Distinguishes between a healthy OmniRoute gateway and a conflicting foreign server.
        """
        url = f"http://{self.host}:{self.port}/api/health"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "TradeBot0-Supervisor/2.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    return True, data
        except Exception as e:
            logger.debug("Gateway health probe failed: %s", e)
        return False, {}

    def test_single_key(self, provider: str, raw_key: str, timeout: float = 3.5) -> Dict[str, Any]:
        """
        Non-blocking live probe of an individual provider API key with strict timeout.
        Returns a clean dictionary with ok status, latency, and descriptive message.
        """
        norm_prov = provider.lower().strip()
        key = (raw_key or "").strip()

        if not key:
            return {"ok": False, "message": "Key cannot be empty", "latency_ms": 0}
        if len(key) < 8:
            return {"ok": False, "message": "Key length is suspiciously short", "latency_ms": 0}

        endpoint = PROVIDER_ENDPOINTS.get(norm_prov)
        if not endpoint:
            # Unknown provider, check basic length
            return {"ok": True, "message": "Custom key format accepted", "latency_ms": 0}

        t0 = time.perf_counter()
        try:
            if norm_prov == "gemini":
                # Gemini takes key as URL query parameter
                req_url = f"{endpoint}?key={key}"
                req = urllib.request.Request(req_url, headers={"User-Agent": "TradeBot0-Validator/2.0"})
            else:
                # DeepSeek, Groq, OpenRouter take Bearer token header
                req = urllib.request.Request(
                    endpoint,
                    headers={
                        "Authorization": f"Bearer {key}",
                        "User-Agent": "TradeBot0-Validator/2.0",
                        "Accept": "application/json",
                    },
                )

            with urllib.request.urlopen(req, timeout=timeout) as resp:
                elapsed_ms = int((time.perf_counter() - t0) * 1000)
                if resp.status in (200, 201):
                    return {"ok": True, "message": f"Verified ({elapsed_ms}ms)", "latency_ms": elapsed_ms}
                return {"ok": False, "message": f"Unexpected status {resp.status}", "latency_ms": elapsed_ms}

        except urllib.error.HTTPError as he:
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            if he.code in (401, 403):
                return {"ok": False, "message": "Invalid Key / Unauthorized (HTTP 401)", "latency_ms": elapsed_ms}
            elif he.code == 429:
                # 429 only proves the key was accepted far enough to be rate
                # limited; it cannot prove the key is valid. Never report it
                # as verified (item 12 / A4-1): the wizard must show it as
                # unconfirmed and let the user retry later.
                return {"ok": False, "message": "Key status unconfirmed (rate limited, HTTP 429) — retry later", "latency_ms": elapsed_ms}
            return {"ok": False, "message": f"Provider error (HTTP {he.code})", "latency_ms": elapsed_ms}
        except (urllib.error.URLError, socket.timeout, TimeoutError) as te:
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            # Offline or DNS error: return defensive warning without blocking
            return {"ok": False, "message": f"Connection timed out or offline ({elapsed_ms}ms)", "latency_ms": elapsed_ms}
        except Exception as e:
            return {"ok": False, "message": f"Validation issue: {type(e).__name__}", "latency_ms": 0}

    def _open_daemon_log(self):
        """Opens the daemon log for append, rotating it once it exceeds the cap.

        Keeps one rotated backup (``omniroute_daemon.log.1``); if rotation
        itself fails, the file is truncated instead so the log still cannot
        grow without bound.
        """
        log_path = self.daemon_log_path
        log_path.parent.mkdir(parents=True, exist_ok=True)
        if log_path.is_file() and log_path.stat().st_size > DAEMON_LOG_MAX_BYTES:
            backup = log_path.with_suffix(".log.1")
            try:
                if backup.exists():
                    backup.unlink()
                log_path.rename(backup)
            except Exception as e:
                logger.warning("Failed to rotate daemon log %s: %s", log_path, e)
                try:
                    log_path.write_text("", encoding="utf-8")
                except Exception as e:
                    logger.debug("Failed to truncate daemon log after rotation failure: %s", e)
        return open(log_path, "a", encoding="utf-8", errors="replace", buffering=1)

    def start_daemon(self, max_wait_sec: float = 30.0) -> Tuple[bool, str]:
        """
        Ensures an OmniRoute daemon is active and listening on the designated port.
        If already active, reuses it immediately. If not active, launches it headless
        in the background without displaying console windows.

        Double-spawn guard (F5): while one thread is spawning, a second
        caller waits on the health probe instead of spawning its own
        daemon; the spawn itself runs in _start_daemon_once.
        """
        with self._daemon_lock:
            if self._daemon_starting:
                _already_starting = True
            else:
                self._daemon_starting = True
                self._daemon_starting_thread = threading.get_ident()
                _already_starting = False
        if _already_starting:
            deadline = time.time() + max_wait_sec
            while time.time() < deadline:
                time.sleep(0.25)
                if self.is_port_open(timeout=0.2):
                    healthy, _ = self.probe_health(timeout=2.0)
                    if healthy:
                        return True, f"Connected to OmniRoute gateway at {self.host}:{self.port} (started by a concurrent request)"
            return False, f"OmniRoute daemon did not respond within {max_wait_sec}s timeout."
        try:
            return self._start_daemon_once(max_wait_sec)
        finally:
            with self._daemon_lock:
                self._daemon_starting = False
                self._daemon_starting_thread = None

    def _start_daemon_once(self, max_wait_sec: float = 30.0) -> Tuple[bool, str]:
        # Single spawn attempt (see start_daemon for the concurrency guard).
        # Step 1: Check if already running and healthy
        if self.is_port_open():
            healthy, _ = self.probe_health(timeout=2.0)
            if healthy:
                return True, f"Connected to existing OmniRoute gateway at {self.host}:{self.port}"
            # Port open but not responding to health check: foreign application conflict
            return False, f"Port {self.port} is occupied by another application."

        # Step 2: Resolve command for 100% headless daemon execution
        cmd = self._get_daemon_command(self.port)
        if not cmd:
            return False, "OmniRoute CLI is not installed or not found in system PATH."

        # Step 3: Spawn background daemon cleanly without displaying console windows
        try:
            startupinfo = None
            creation_flags = 0
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0  # SW_HIDE: completely suppress window
                creation_flags = 0x08000000  # CREATE_NO_WINDOW: zero console window allocation

            # CRITICAL: Strip PyInstaller environment variables and set cwd to user home directory
            # so the child daemon never inherits or locks the PyInstaller _MEIPASS extraction directory.
            safe_cwd = os.path.expanduser("~")
            child_env = os.environ.copy()
            for key in ("_MEIPASS", "_MEIPASS2", "PYTHONPATH", "PYTHONHOME"):
                child_env.pop(key, None)
            # Ensure web dashboard is accessible when user clicks Launch Console
            child_env["OMNIROUTE_HEADLESS"] = "0"

            # Close a stale log handle first (respawn after a previous daemon
            # died), then open the daemon log: output goes to a file, not
            # DEVNULL, so a failed startup leaves something to read (item 8).
            if self._daemon_log_file is not None:
                try:
                    self._daemon_log_file.close()
                except Exception as e:
                    logger.debug("Failed to close stale daemon log handle: %s", e)
                self._daemon_log_file = None
            log_file = self._open_daemon_log()
            try:
                proc = subprocess.Popen(
                    cmd,
                    cwd=safe_cwd,
                    env=child_env,
                    close_fds=True,
                    startupinfo=startupinfo,
                    creationflags=creation_flags,
                    stdin=subprocess.DEVNULL,
                    stdout=log_file,
                    stderr=log_file,
                )
            except Exception:
                log_file.close()
                raise
            self.child_process = proc
            self.is_self_spawned = True
            self._daemon_log_file = log_file
            try:
                log_file.write(
                    f"--- OmniRoute daemon spawned (PID {proc.pid}) "
                    f"at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n"
                )
            except Exception as e:
                logger.debug("Failed to write daemon spawn header to log: %s", e)
            logger.info("Spawned headless background OmniRoute daemon (PID %d)", proc.pid)
        except Exception as e:
            logger.error("Failed to spawn OmniRoute daemon: %s", e)
            return False, f"Process execution failed: {e}"

        # Step 4: Poll health with strict circuit breaker
        deadline = time.time() + max_wait_sec
        while time.time() < deadline:
            time.sleep(0.25)
            if self.is_port_open(timeout=0.2):
                healthy, _ = self.probe_health(timeout=2.0)
                if healthy:
                    return True, f"OmniRoute daemon started and verified on port {self.port}"

        # Step 5: Timed out - tear down child process to prevent orphan leak
        self.shutdown()
        return False, f"OmniRoute daemon did not respond within {max_wait_sec}s timeout."

    def shutdown(self) -> None:
        """Terminates the spawned child process cleanly if created by this supervisor.

        Only ever touches processes this supervisor itself spawned. A gateway
        (or any other program) the user started by hand on the same port is
        left alone: killing it would destroy someone else's process (item 6).
        """
        # If another thread is mid-spawn, wait for it to finish
        # assigning child_process (bounded): snapshotting None now would
        # orphan the daemon it is about to spawn. The spawning thread
        # itself never waits (it owns the flag).
        _spawn_deadline = time.time() + 35.0
        while True:
            with self._daemon_lock:
                _starting = self._daemon_starting
                _starter = self._daemon_starting_thread
            if not _starting or _starter == threading.get_ident():
                break
            if time.time() > _spawn_deadline:
                logger.warning("Gateway shutdown timed out waiting for a concurrent spawn")
                break
            time.sleep(0.1)

        owned_pid: Optional[int] = None
        if self.child_process and self.is_self_spawned:
            owned_pid = self.child_process.pid
            pid = owned_pid
            try:
                logger.info("Terminating self-spawned OmniRoute daemon (PID %d)", pid)
                if sys.platform == "win32":
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(pid)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=0x08000000,
                        close_fds=True,
                        check=False,
                    )
                    try:
                        self.child_process.wait(timeout=1.5)
                    except Exception as e:
                        logger.debug("Daemon did not exit within wait timeout during shutdown: %s", e)
                else:
                    self.child_process.terminate()
                    self.child_process.wait(timeout=1.0)
            except Exception:
                try:
                    self.child_process.kill()
                except Exception as e:
                    logger.debug("Failed to kill daemon process during shutdown: %s", e)
            finally:
                self.child_process = None
                self.is_self_spawned = False

        # Fail-safe cleanup: only if OUR OWN child is somehow still holding
        # the port after termination. A foreign listener is never killed.
        if owned_pid is not None:
            self._kill_port_owner(self.port, owned_pid=owned_pid)

        # Close the daemon log handle opened by start_daemon (if any). This
        # also runs on the timeout path, which calls shutdown() after the
        # daemon failed to become healthy.
        if self._daemon_log_file is not None:
            try:
                self._daemon_log_file.close()
            except Exception as e:
                logger.debug("Failed to close daemon log handle during shutdown: %s", e)
            self._daemon_log_file = None

    def _kill_port_owner(self, port: int, owned_pid: Optional[int] = None) -> None:
        """Terminates a lingering listener on the port ONLY if it is our own
        spawned child (PID match). With owned_pid=None (no child of ours) it
        does nothing: a foreign process on the port is never killed (item 6).
        """
        if owned_pid is None:
            return
        if sys.platform == "win32":
            try:
                output = subprocess.check_output(
                    f"netstat -ano | findstr :{port}",
                    shell=True,
                    text=True,
                    stderr=subprocess.DEVNULL,
                    creationflags=0x08000000,
                )
                for line in output.splitlines():
                    parts = line.strip().split()
                    if len(parts) >= 5 and "LISTENING" in parts[3].upper():
                        target_pid = parts[4]
                        if target_pid.isdigit() and int(target_pid) == owned_pid:
                            logger.info("Terminating lingering own daemon on port %d (PID %s)", port, target_pid)
                            subprocess.run(
                                ["taskkill", "/F", "/T", "/PID", target_pid],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                creationflags=0x08000000,
                                close_fds=True,
                                check=False,
                            )
            except Exception as e:
                logger.debug("Failed to terminate lingering daemon on port %s: %s", port, e)

