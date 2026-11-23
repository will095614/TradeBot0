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
import re
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import weakref
import zipfile
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from src.intelligence.config_manager import PROVIDER_ENV_MAP, parse_omni_env_line

logger = logging.getLogger("tradebot0.gateway_supervisor")
_ANSI_CSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

PROVIDER_ENDPOINTS = {
    "deepseek": "https://api.deepseek.com/models",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/models",
    "groq": "https://api.groq.com/openai/v1/models",
    "nvidia": "https://integrate.api.nvidia.com/v1/models",
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
# Documented approximate on-disk size of the npm-installed omniroute
# package (~2.6 GB / ~164k files on Windows; see TradeBot0.iss). Used
# during `npm install` to compute an estimated 0-99% progress value from
# real bytes written into <runtime>/omniroute; 100% is reserved for real
# success (`done`).
RUNTIME_OMNIROUTE_EXPECTED_BYTES = int(2.6 * 1024 * 1024 * 1024)
RUNTIME_OMNIROUTE_PROGRESS_INTERVAL_SEC = 1.0
RUNTIME_OMNIROUTE_ETA_MIN_ELAPSED_SEC = 10.0
RUNTIME_OMNIROUTE_ETA_MAX_SEC = 3600.0
RUNTIME_OMNIROUTE_BASE_MESSAGE = "Installing OmniRoute (about 3-5 min, ~2.6 GB)..."

# Gateway auto-restart watchdog (gateway diagnosis workstream): the
# frontend polls state once a second; the watchdog probes the gateway
# over HTTP with a 1 s timeout, so a 5 s cadence keeps detection fast
# without hammering a recovering gateway. After 5 consecutive failed
# restarts it stops trying and reports connection_problem persistently
# instead of spinning forever. Backoff before the next attempt after N
# consecutive failures: 10s, 20s, 40s, 80s, 160s, capped at 300s.
WATCHDOG_POLL_SEC = 5.0
WATCHDOG_MAX_CONSECUTIVE_FAILURES = 5
WATCHDOG_RETRY_BASE_SEC = 10.0
WATCHDOG_RETRY_MAX_SEC = 300.0


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
                sup.cancel_runtime_install()
            except Exception as e:
                logger.debug("Gateway runtime install cancel at exit failed: %s", e)
        for sup in list(cls._live_supervisors):
            try:
                sup.stop_watchdog()
            except Exception as e:
                logger.debug("Gateway watchdog stop at exit failed: %s", e)
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
        omni_data_dir: Optional[Path] = None,
        on_gateway_recovered: Optional[Callable[[], None]] = None,
    ) -> None:
        self.host = host
        self.port = port
        self._on_gateway_recovered = on_gateway_recovered
        self.omni_data_dir: Path = (
            Path(omni_data_dir) if omni_data_dir is not None else (Path.home() / ".omniroute")
        )
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
        self._install_resp = None
        self._install_progress: Optional[int] = None  # 0-100 when real, else None
        self._install_phase: str = ""
        # Double-spawn guard for start_daemon (F5): two concurrent callers
        # (wizard save + runtime-install finish) used to both pass the
        # port check and spawn two daemons; the second overwrote
        # child_process and orphaned the first.
        self._daemon_lock = threading.Lock()
        self._password_sync_lock = threading.Lock()
        self._daemon_starting: bool = False
        self._daemon_starting_thread: Optional[int] = None
        self._abort_spawn_event = threading.Event()
        self._watchdog_spawn_abort: Optional[Tuple[int, threading.Event]] = None
        self.install_status: str = "idle"  # idle | downloading-node | installing-omniroute | done | failed | cancelled
        self.install_message: str = ""
        # Auto-restart watchdog state (gateway diagnosis workstream),
        # guarded by _watchdog_lock: the thread only ever restarts a
        # gateway the app has seen healthy (or the caller just verified
        # healthy via start_watchdog(armed=True)). _watchdog_armed is
        # sticky once any probe finds the gateway healthy.
        self._watchdog_lock = threading.Lock()
        self._watchdog_thread: Optional[threading.Thread] = None
        self._watchdog_stop = threading.Event()
        self._watchdog_state: str = "idle"  # idle | ok | restarting | stopped
        self._watchdog_healthy: Optional[bool] = None
        self._watchdog_armed: bool = False
        self._watchdog_failures: int = 0
        self._watchdog_next_retry_ts: float = 0.0
        self._watchdog_last_restart_ts: Optional[float] = None

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
    def _get_cli_base_command(cls) -> Optional[List[str]]:
        """Resolves a locally installed OmniRoute CLI base invocation without npx.

        Prefers `node.exe <omniroute.mjs>` directly so Windows never allocates a
        console via cmd.exe / omniroute.cmd. Returns None when OmniRoute is not
        installed locally (never falls back to npx, which would trigger a 2.6 GB
        network download).
        """
        node_bin = cls._resolve_node_bin()
        if node_bin:
            # 0. App-local runtime install first (item 10 B3)
            local_mjs = cls._runtime_base() / "omniroute" / "node_modules" / "omniroute" / "bin" / "omniroute.mjs"
            if local_mjs.is_file():
                return [node_bin, str(local_mjs)]

            # 1. Global npm location in APPDATA
            appdata = os.environ.get("APPDATA", "")
            if appdata:
                global_mjs = os.path.join(appdata, "npm", "node_modules", "omniroute", "bin", "omniroute.mjs")
                if os.path.exists(global_mjs):
                    return [node_bin, global_mjs]

            # 2. Relative to omniroute command if present in PATH
            omni_path = (
                (shutil.which("omniroute.cmd") or shutil.which("omniroute"))
                if sys.platform == "win32"
                else (shutil.which("omniroute") or shutil.which("omniroute.cmd"))
            )
            if omni_path:
                rel_mjs = os.path.join(os.path.dirname(omni_path), "node_modules", "omniroute", "bin", "omniroute.mjs")
                if os.path.exists(rel_mjs):
                    return [node_bin, rel_mjs]

        omni_bin = (
            (shutil.which("omniroute.cmd") or shutil.which("omniroute"))
            if sys.platform == "win32"
            else (shutil.which("omniroute") or shutil.which("omniroute.cmd"))
        )
        if omni_bin:
            return [omni_bin]
        return None

    @classmethod
    def _get_daemon_command(cls, port: int) -> Optional[List[str]]:
        """
        Builds the command line arguments to spawn OmniRoute in 100% headless background mode.
        On Windows, directly uses `node.exe <path_to_omniroute.mjs> serve --no-open --port <port>`
        to bypass `cmd.exe` and `omniroute.cmd` batch scripts which trigger Windows Terminal popups.
        Never falls back to `npx` (which would silently trigger a 2.6 GB download).
        """
        base_cmd = cls._get_cli_base_command()
        if base_cmd:
            return base_cmd + ["serve", "--no-open", "--port", str(port)]
        return None

    @staticmethod
    def _read_initial_password_from_env_file(env_path: Path) -> str:
        """Reads INITIAL_PASSWORD from an OmniRoute .env file without logging it."""
        if not env_path.is_file():
            return ""
        try:
            for raw_line in env_path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
                parsed = parse_omni_env_line(raw_line)
                if parsed is not None and parsed[0] == "INITIAL_PASSWORD":
                    return parsed[1].strip()
        except Exception as e:
            logger.debug("Could not read INITIAL_PASSWORD from %s: %s", env_path, e)
        return ""

    def sync_admin_password(
        self,
        password: str,
        data_dir: Optional[Path] = None,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """Persists the admin password directly into OmniRoute's storage.sqlite.

        OmniRoute only consults INITIAL_PASSWORD from .env when storage.sqlite
        has no bcrypt hash yet; once a hash exists (from any prior run or
        install), editing .env alone has no effect. This helper invokes
        OmniRoute's own CLI:
        - `reset-password --password-stdin` (password sent via stdin, never argv)
          when `<data_dir>/storage.sqlite` already exists;
        - `setup --non-interactive` (password sent via INITIAL_PASSWORD in the
          child env, never argv) when `<data_dir>/storage.sqlite` does not yet
          exist, creating the DB with requireLogin=true and setupComplete=true.
        The password value is never logged or placed on the command line.
        """
        if not isinstance(password, str) or len(password.strip()) < 8:
            return {"ok": False, "error": "Admin password must be at least 8 characters."}
        pw = password.strip()
        if re.search(r"[\r\n\t\x00-\x1f]", pw):
            return {"ok": False, "error": "Admin password contains invalid characters."}

        cli_base = self._get_cli_base_command()
        if not cli_base:
            return {
                "ok": True,
                "skipped": True,
                "reason": "cli_not_installed",
            }

        target_dir = Path(data_dir) if data_dir is not None else self.omni_data_dir
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return {"ok": False, "error": f"Failed to prepare OmniRoute data directory: {e}"}

        with self._password_sync_lock:
            child_env = os.environ.copy()
            for key in list(child_env):
                if (
                    key in ("_MEIPASS", "_MEIPASS2", "PYTHONPATH", "PYTHONHOME", "INITIAL_PASSWORD", "LLM_API_KEY")
                    or key.endswith("_API_KEY")
                ):
                    child_env.pop(key, None)
            child_env["DATA_DIR"] = str(target_dir)
            child_env["OMNIROUTE_CLI_SKIP_DEFAULT_DATA_ENV"] = "1"
            child_env["OMNIROUTE_CLI_SKIP_REPO_ENV"] = "1"
            child_env["OMNIROUTE_NO_UPDATE_NOTIFIER"] = "1"
            if cli_base and Path(cli_base[0]).is_file():
                node_dir_str = str(Path(cli_base[0]).parent)
                existing_path = child_env.get("PATH", "")
                child_env["PATH"] = f"{node_dir_str}{os.pathsep}{existing_path}" if existing_path else node_dir_str

            db_path = target_dir / "storage.sqlite"
            if db_path.is_file():
                mode = "reset-password"
                cmd = cli_base + ["reset-password", "--password-stdin"]
                child_env.pop("INITIAL_PASSWORD", None)
                stdin_payload: Optional[str] = pw
            else:
                mode = "setup"
                cmd = cli_base + ["setup", "--non-interactive"]
                child_env["INITIAL_PASSWORD"] = pw
                stdin_payload = None

            startupinfo = None
            creation_flags = 0
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0
                creation_flags = 0x08000000

            try:
                run_kwargs: Dict[str, Any] = {
                    "cwd": os.path.expanduser("~"),
                    "env": child_env,
                    "stdout": subprocess.PIPE,
                    "stderr": subprocess.PIPE,
                    "text": True,
                    "encoding": "utf-8",
                    "errors": "replace",
                    "timeout": timeout,
                    "startupinfo": startupinfo,
                    "creationflags": creation_flags,
                    "close_fds": True,
                }
                if stdin_payload is not None:
                    run_kwargs["input"] = stdin_payload
                else:
                    run_kwargs["stdin"] = subprocess.DEVNULL
                proc = subprocess.run(cmd, **run_kwargs)
            except subprocess.TimeoutExpired:
                logger.error("OmniRoute %s timed out after %.1fs", mode, timeout)
                return {"ok": False, "error": f"Applying OmniRoute password timed out ({mode})."}
            except Exception as e:
                logger.error("OmniRoute %s failed to execute: %s", mode, type(e).__name__)
                return {"ok": False, "error": f"Failed to apply OmniRoute password: {type(e).__name__}"}

            if proc.returncode != 0:
                stderr_lines = [
                    _ANSI_CSI_RE.sub("", ln).strip()
                    for ln in (proc.stderr or "").splitlines()
                    if _ANSI_CSI_RE.sub("", ln).strip()
                ]
                stdout_lines = [
                    _ANSI_CSI_RE.sub("", ln).strip()
                    for ln in (proc.stdout or "").splitlines()
                    if _ANSI_CSI_RE.sub("", ln).strip()
                ]
                summary = (
                    stderr_lines[-1]
                    if stderr_lines
                    else (stdout_lines[-1] if stdout_lines else f"exit code {proc.returncode}")
                )
                logger.error("OmniRoute %s exited with code %d: %s", mode, proc.returncode, summary)
                return {"ok": False, "error": f"Failed to apply OmniRoute password ({mode}): {summary}"}

            logger.info("Synchronized OmniRoute admin password into storage.sqlite via %s", mode)
            return {"ok": True, "skipped": False, "mode": mode}

    @classmethod
    def is_cli_available(cls) -> bool:
        """Checks if a local omniroute CLI or direct node runner is installed (excludes npx)."""
        if cls._get_daemon_command(20128) is not None:
            return True
        return bool(shutil.which("omniroute.cmd") or shutil.which("omniroute"))

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
            names = ("npm.cmd", "npm") if sys.platform == "win32" else ("npm", "npm.cmd")
            for name in names:
                cand = node_dir / name
                if cand.is_file():
                    return str(cand)
        if sys.platform == "win32":
            return shutil.which("npm.cmd") or shutil.which("npm")
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

        progress is 0-100 during the Node.js zip download (real
        Content-Length bytes received / total, or None when the server
        sends no Content-Length) and an estimated 0-99 during the
        OmniRoute npm install (real bytes written into
        <runtime>/omniroute divided by the documented ~2.6 GB expected
        total, clamped at 99). 100 appears only when the install
        succeeds ("done").
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

    def _set_install_progress(
        self, progress: Optional[int], message: Optional[str] = None
    ) -> None:
        """Updates the install percent (and optionally message) without log spam."""
        with self._install_lock:
            self._install_progress = progress
            if message is not None:
                self.install_message = message

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
            self._install_progress = 0 if self.install_status == "installing-omniroute" else None
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
            self._install_proc = None
            resp = self._install_resp
            self._install_resp = None
        if resp is not None:
            try:
                resp.close()
            except Exception as e:
                logger.debug("Failed to close active Node download response during cancel: %s", e)
        if proc is not None and proc.poll() is None:
            self._terminate_install_proc(proc)
        return {"ok": True, "message": "Cancelling installation..."}

    @staticmethod
    def _terminate_install_proc(proc: subprocess.Popen) -> None:
        """Kills an npm child and, on Windows, its whole tree: npm.cmd
        runs under cmd.exe, so killing cmd.exe alone would orphan the
        node.exe actually doing the install."""
        if sys.platform == "win32":
            # Kill the whole process tree BEFORE killing the parent cmd.exe,
            # otherwise child node.exe processes detach and escape taskkill /T.
            try:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=15, creationflags=0x08000000,
                )
            except Exception as e:
                logger.debug("taskkill for install process failed: %s", e)
        try:
            if proc.poll() is None:
                proc.kill()
        except Exception as e:
            logger.debug("Failed to kill install process: %s", e)
        try:
            proc.wait(timeout=10)
        except Exception as e:
            logger.debug("Cancelled install process wait timed out: %s", e)

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
        npm_started = False
        npm_succeeded = False
        try:
            base = self._runtime_base()
            base.mkdir(parents=True, exist_ok=True)
            if self._install_cancel_event.is_set():
                raise _InstallCancelledError("Installation cancelled.")
            node_bin = self._resolve_node_bin()
            downloaded_node = False
            if node_bin is None:
                self._set_install_status("downloading-node", "Downloading Node.js (about 37 MB)...", phase="Downloading Node.js")
                node_bin = self._download_node(base)
                downloaded_node = True
            if not (downloaded_node and self.omniroute_installed()):
                npm_bin = self._resolve_npm_bin(node_bin)
                if npm_bin is None:
                    raise RuntimeError("npm was not found next to Node.js.")
                self._set_install_status(
                    "installing-omniroute",
                    RUNTIME_OMNIROUTE_BASE_MESSAGE,
                    progress=0,
                    phase="Installing OmniRoute",
                )
                npm_started = True
                self._npm_install_omniroute(npm_bin, base)
                if self._install_cancel_event.is_set():
                    raise _InstallCancelledError("Installation cancelled.")
                if not self.omniroute_installed():
                    raise RuntimeError("OmniRoute install finished but the package was not found.")
                npm_succeeded = True
            if self._install_cancel_event.is_set():
                raise _InstallCancelledError("Installation cancelled.")
            # If the user already configured INITIAL_PASSWORD in ~/.omniroute/.env,
            # apply it directly to storage.sqlite before spawning so an older DB
            # hash cannot shadow the configured password. Never auto-start an
            # unprotected default-password gateway before the user sets one.
            saved_pw = self._read_initial_password_from_env_file(self.omni_data_dir / ".env")
            if not saved_pw:
                self._set_install_status(
                    "done",
                    "OmniRoute installed. Enter your API key and admin password, then click Save & Launch.",
                    progress=100,
                    phase="Installed",
                )
                return
            self._set_install_status(
                "installing-omniroute",
                "OmniRoute installed. Starting the gateway...",
                progress=99,
                phase="Starting gateway",
            )
            pw_sync = self.sync_admin_password(saved_pw, data_dir=self.omni_data_dir)
            if not pw_sync.get("ok"):
                logger.warning("Post-install OmniRoute password sync failed: %s", pw_sync.get("error"))
            if self._install_cancel_event.is_set():
                raise _InstallCancelledError("Installation cancelled.")
            ok, msg = self.start_daemon(max_wait_sec=30.0)
            if self._install_cancel_event.is_set():
                if ok:
                    self.shutdown()
                raise _InstallCancelledError("Installation cancelled.")
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
            if (npm_started and not npm_succeeded) or not self.omniroute_installed():
                self._cleanup_cancelled_install(self._runtime_base())
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
            with self._install_lock:
                self._install_resp = resp
            try:
                total = None
                try:
                    raw_total = resp.headers.get("Content-Length")
                    parsed_total = int(raw_total) if raw_total else 0
                    total = parsed_total if parsed_total > 0 else None
                except Exception:
                    total = None
                downloaded = 0
                while True:
                    if self._install_cancel_event.is_set():
                        raise _InstallCancelledError("Installation cancelled.")
                    try:
                        chunk = resp.read(1024 * 1024)
                    except Exception:
                        if self._install_cancel_event.is_set():
                            raise _InstallCancelledError("Installation cancelled.")
                        raise
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        self._set_install_progress(min(100, int(downloaded * 100 / total)))
            finally:
                with self._install_lock:
                    if self._install_resp is resp:
                        self._install_resp = None
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

    @staticmethod
    def _measure_dir_bytes(
        path: Path, cancel_event: Optional[threading.Event] = None
    ) -> int:
        """Measures total bytes of regular files under `path` via os.scandir.

        Skips symlinks so npm .bin junctions cannot loop, tolerates
        concurrent file/dir churn (OSError) while npm extracts, and checks
        cancel_event periodically so cancellation is never delayed.
        """
        total = 0
        stack = [os.fspath(path)]
        dirs_visited = 0
        while stack:
            if cancel_event is not None and dirs_visited % 256 == 0 and cancel_event.is_set():
                break
            current = stack.pop()
            dirs_visited += 1
            try:
                with os.scandir(current) as it:
                    for entry in it:
                        try:
                            if entry.is_symlink() or (hasattr(entry, "is_junction") and entry.is_junction()):
                                continue
                            if entry.is_dir(follow_symlinks=False):
                                stack.append(entry.path)
                            elif entry.is_file(follow_symlinks=False):
                                total += entry.stat(follow_symlinks=False).st_size
                        except OSError:
                            continue
            except OSError:
                continue
        return total

    @staticmethod
    def _format_omniroute_progress_message(
        pct: int,
        written_bytes: int,
        total_bytes: int,
        elapsed_sec: float,
        expected_bytes: int,
    ) -> str:
        """Formats the OmniRoute install status banner message with an ETA
        once enough elapsed time and real byte throughput exist."""
        if elapsed_sec < RUNTIME_OMNIROUTE_ETA_MIN_ELAPSED_SEC or pct < 1:
            return RUNTIME_OMNIROUTE_BASE_MESSAGE
        remaining_bytes = expected_bytes - total_bytes
        if written_bytes <= 0 or remaining_bytes <= 0:
            return f"Installing OmniRoute — {pct}%"
        throughput = written_bytes / elapsed_sec
        if throughput <= 0:
            return f"Installing OmniRoute — {pct}%"
        remaining_sec = remaining_bytes / throughput
        if remaining_sec <= 0 or remaining_sec > RUNTIME_OMNIROUTE_ETA_MAX_SEC:
            return f"Installing OmniRoute — {pct}%"
        rounded_sec = max(1, int(round(remaining_sec)))
        if rounded_sec < 60:
            eta = f"~{rounded_sec} s left"
        else:
            eta = f"~{max(1, int(round(remaining_sec / 60.0)))} min left"
        return f"Installing OmniRoute — {pct}% ({eta})"

    def _npm_install_omniroute(self, npm_bin: str, base: Path) -> None:
        """Runs `npm install --prefix <runtime>/omniroute omniroute`.
        npm 11+ blocks postinstall scripts by default, so the documented
        --allow-scripts list is passed first (native bindings need it);
        if npm rejects the flag (older npm), retry once without it."""
        prefix = base / "omniroute"
        prefix.mkdir(parents=True, exist_ok=True)
        expected_bytes = max(1, int(RUNTIME_OMNIROUTE_EXPECTED_BYTES))
        phase_start = time.monotonic()
        initial_bytes = self._measure_dir_bytes(
            prefix, cancel_event=self._install_cancel_event
        )
        best_pct = min(99, int(initial_bytes * 100 / expected_bytes))
        self._set_install_progress(best_pct)
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
                if self._install_cancel_event.is_set():
                    raise _InstallCancelledError("Installation cancelled.")
                log_file.write(f"--- attempt {i + 1}: {' '.join(cmd)} ---\n")
                log_file.flush()
                attempt_start_offset = log_file.tell()
                # Popen (not run) so a cancel can kill the child: the
                # poll loop checks the cancel event every 0.25 s and the
                # 30-minute deadline, mirroring the old run(timeout=1800).
                try:
                    child_env = os.environ.copy()
                    for key in list(child_env):
                        if (
                            key in ("_MEIPASS", "_MEIPASS2", "PYTHONPATH", "PYTHONHOME", "INITIAL_PASSWORD", "LLM_API_KEY")
                            or key.endswith("_API_KEY")
                        ):
                            child_env.pop(key, None)
                    npm_dir = str(Path(npm_bin).parent)
                    if npm_dir and os.path.isdir(npm_dir):
                        existing_path = child_env.get("PATH", "")
                        child_env["PATH"] = f"{npm_dir}{os.pathsep}{existing_path}" if existing_path else npm_dir
                    startupinfo = None
                    creation_flags = 0
                    if sys.platform == "win32":
                        startupinfo = subprocess.STARTUPINFO()
                        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                        startupinfo.wShowWindow = 0
                        creation_flags = 0x08000000
                    proc = subprocess.Popen(
                        cmd,
                        cwd=str(prefix),
                        stdin=subprocess.DEVNULL,
                        stdout=log_file,
                        stderr=subprocess.STDOUT,
                        env=child_env,
                        startupinfo=startupinfo,
                        creationflags=creation_flags,
                        close_fds=True,
                    )
                    with self._install_lock:
                        if self._install_cancel_event.is_set():
                            self._install_proc = None
                            _cancel_now = True
                        else:
                            self._install_proc = proc
                            _cancel_now = False
                    if _cancel_now:
                        self._terminate_install_proc(proc)
                        raise _InstallCancelledError("Installation cancelled.")
                    try:
                        deadline = time.monotonic() + 1800
                        next_measure = 0.0
                        while True:
                            if self._install_cancel_event.is_set():
                                self._terminate_install_proc(proc)
                                raise _InstallCancelledError("Installation cancelled.")
                            rc = proc.poll()
                            if rc is not None:
                                break
                            now = time.monotonic()
                            if now > deadline:
                                self._terminate_install_proc(proc)
                                raise RuntimeError("npm install timed out after 30 minutes.")
                            if now >= next_measure:
                                scan_start = time.monotonic()
                                size = self._measure_dir_bytes(
                                    prefix, cancel_event=self._install_cancel_event
                                )
                                if self._install_cancel_event.is_set():
                                    self._terminate_install_proc(proc)
                                    raise _InstallCancelledError("Installation cancelled.")
                                scan_done = time.monotonic()
                                raw_pct = min(99, int(size * 100 / expected_bytes))
                                best_pct = max(best_pct, raw_pct)
                                msg = self._format_omniroute_progress_message(
                                    best_pct,
                                    max(0, size - initial_bytes),
                                    size,
                                    scan_done - phase_start,
                                    expected_bytes,
                                )
                                self._set_install_progress(best_pct, message=msg)
                                interval = max(0.0, float(RUNTIME_OMNIROUTE_PROGRESS_INTERVAL_SEC))
                                scan_dur = max(0.0, scan_done - scan_start)
                                next_measure = scan_done + max(interval, scan_dur * 2.0)
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
                tail = self._tail_install_log(2000, min_offset=attempt_start_offset)
                if i == 0 and ("allow-scripts" in tail or "unknown option" in tail.lower()):
                    continue
                break
        raise RuntimeError(last_error or "npm install failed.")

    def _tail_install_log(self, n_chars: int, min_offset: int = 0) -> str:
        """Last n_chars of the install log (at or after min_offset), for failure diagnosis."""
        try:
            with open(self.install_log_path, "rb") as f:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                start = max(int(min_offset), size - max(1, int(n_chars)) * 4)
                if start >= size:
                    return ""
                f.seek(start)
                data = f.read()
            return data.decode("utf-8", errors="replace")[-n_chars:]
        except Exception:
            return ""

    # --- Auto-restart watchdog (gateway diagnosis workstream) ---------
    def start_watchdog(self, armed: bool = False) -> bool:
        """Starts the auto-restart watchdog thread (idempotent).

        Pass armed=True when the caller just verified the gateway is
        healthy (run() after a successful auto-launch, or
        save_and_launch_gateway after a healthy connect/spawn), so a
        gateway that dies before the first probe still gets restarted.
        A watchdog that has never seen the gateway healthy never
        restarts it: a gateway that never started belongs to the setup
        flow, not the watchdog. Returns False when already running.
        """
        with self._watchdog_lock:
            old = self._watchdog_thread
            if old is not None and old.is_alive():
                if armed:
                    self._watchdog_armed = True
                    self._watchdog_failures = 0
                    self._watchdog_next_retry_ts = 0.0
                    if self._watchdog_state == "stopped":
                        self._watchdog_state = "ok"
                return False
            stop_evt = threading.Event()
            self._watchdog_stop = stop_evt
            self._watchdog_armed = bool(armed)
            t = threading.Thread(
                target=self._watchdog_loop,
                args=(stop_evt,),
                name="omniroute-gateway-watchdog",
                daemon=True,
            )
            self._watchdog_thread = t
            t.start()
            return True

    def stop_watchdog(self) -> None:
        """Stops the watchdog thread (best-effort join, never blocks long).

        If the thread is mid-restart when asked to stop, the join times
        out and the reference is kept so a later start_watchdog() does
        not spawn a duplicate; the old thread is a daemon and exits on
        its own once its current attempt finishes.
        """
        with self._watchdog_lock:
            self._watchdog_stop.set()
            t = self._watchdog_thread
        if t is not None and t.is_alive():
            t.join(timeout=2.0)
        with self._watchdog_lock:
            if t is self._watchdog_thread and (t is None or not t.is_alive()):
                self._watchdog_thread = None

    def watchdog_status(self) -> Dict[str, Any]:
        """Current watchdog state for the dashboard diagnosis line.

        state: idle (never started) | ok | restarting (a restart is in
        flight) | stopped (gave up after repeated failures). healthy is
        None until the first probe. Never raises.
        """
        try:
            with self._watchdog_lock:
                return {
                    "state": self._watchdog_state,
                    "healthy": self._watchdog_healthy,
                    "armed": self._watchdog_armed,
                    "consecutive_failures": self._watchdog_failures,
                    "last_restart_ts": self._watchdog_last_restart_ts,
                }
        except Exception:
            return {"state": "idle", "healthy": None, "armed": False, "consecutive_failures": 0, "last_restart_ts": None}

    @staticmethod
    def _watchdog_backoff_sec(failures: int) -> float:
        """Backoff before the next restart attempt after `failures`
        consecutive failures: 10s, 20s, 40s, 80s, 160s, capped at 300s."""
        if failures <= 0:
            return WATCHDOG_RETRY_BASE_SEC
        return min(WATCHDOG_RETRY_MAX_SEC, WATCHDOG_RETRY_BASE_SEC * (2 ** (failures - 1)))

    def _watchdog_loop(self, stop_evt: Optional[threading.Event] = None) -> None:
        """Background loop: probe health every WATCHDOG_POLL_SEC and restart a
        dead gateway. Runs until stop_evt is set. Never raises.

        Wait-then-tick: the first probe happens one interval after start, not
        immediately, so the probe cadence is uniform from the start. This also
        guarantees a caller that stops the watchdog right after starting it
        (e.g. a test tearing down its mocks) never sees a tick run after its
        own mocks are gone — a tick-then-wait loop could fire a real
        start_daemon once the mocks had exited.
        """
        evt = stop_evt if stop_evt is not None else self._watchdog_stop
        while not evt.is_set():
            evt.wait(WATCHDOG_POLL_SEC)
            if evt.is_set():
                break
            try:
                self._watchdog_tick(evt)
            except Exception as e:
                logger.debug("Gateway watchdog tick failed: %s", e)

    def _probe_gateway_healthy(self) -> bool:
        """Cheap liveness check: port open AND /api/health answers 200."""
        try:
            if not self.is_port_open(timeout=0.35):
                return False
            healthy, _ = self.probe_health(timeout=1.0)
            return bool(healthy)
        except Exception as e:
            logger.debug("Gateway watchdog health probe failed: %s", e)
            return False

    def _watchdog_tick(self, stop_evt: Optional[threading.Event] = None) -> None:
        """One watchdog iteration: probe health, restart once if dead.

        Never restarts while a runtime install is running (the install
        finishes by starting the gateway itself), never restarts a
        gateway it has never seen healthy, and never restarts after
        giving up (state "stopped") until the gateway recovers on its
        own -- the dashboard then reports connection_problem persistently
        instead of spinning forever. A restart already in flight when
        stop_watchdog() is called still finishes (bounded by
        start_daemon's 30 s wait); the double-spawn guard serializes
        it against any concurrent start_daemon caller.
        """
        evt = stop_evt if stop_evt is not None else self._watchdog_stop
        # Install in progress: the installer owns the gateway lifecycle.
        try:
            with self._install_lock:
                installing = self.install_status in ("downloading-node", "installing-omniroute")
        except Exception:
            installing = False
        if installing:
            return
        if evt.is_set():
            return
        healthy = self._probe_gateway_healthy()
        with self._watchdog_lock:
            if evt.is_set():
                return
            self._watchdog_healthy = healthy
            if healthy:
                self._watchdog_armed = True
                self._watchdog_failures = 0
                self._watchdog_next_retry_ts = 0.0
                # A manual recovery (user started the gateway by hand)
                # after give-up brings the watchdog back to ok.
                self._watchdog_state = "ok"
                return
            if self._watchdog_state == "stopped":
                # Gave up: keep reporting unhealthy, never restart again
                # until the gateway comes back on its own.
                return
            if not self._watchdog_armed:
                # Never saw this gateway healthy: it never started, so
                # restarting is the setup flow's job, not the watchdog's.
                return
            now = time.monotonic()
            if now < self._watchdog_next_retry_ts:
                return
            self._watchdog_state = "restarting"
        # Restart outside the lock: start_daemon can block up to 30 s.
        with self._daemon_lock:
            self._watchdog_spawn_abort = (threading.get_ident(), evt)
        try:
            ok, msg = self.start_daemon(max_wait_sec=30.0)
        finally:
            with self._daemon_lock:
                if self._watchdog_spawn_abort is not None and self._watchdog_spawn_abort[0] == threading.get_ident():
                    self._watchdog_spawn_abort = None
        recovered = False
        with self._watchdog_lock:
            if evt.is_set():
                if self._watchdog_state == "restarting":
                    self._watchdog_state = "ok"
                return
            if ok:
                self._watchdog_state = "ok"
                self._watchdog_failures = 0
                self._watchdog_next_retry_ts = 0.0
                self._watchdog_last_restart_ts = time.time()
                self._watchdog_healthy = True
                recovered = True
                logger.info("Gateway watchdog restarted the OmniRoute gateway.")
            else:
                self._watchdog_failures += 1
                failures = self._watchdog_failures
                logger.warning(
                    "Gateway watchdog restart attempt %d failed: %s", failures, msg
                )
                if failures >= WATCHDOG_MAX_CONSECUTIVE_FAILURES:
                    self._watchdog_state = "stopped"
                    logger.warning(
                        "Gateway watchdog gave up after %d consecutive failed restarts; "
                        "reporting connection problem until the gateway recovers.",
                        failures,
                    )
                else:
                    self._watchdog_state = "ok"
                    self._watchdog_next_retry_ts = time.monotonic() + self._watchdog_backoff_sec(failures)
        if recovered and callable(self._on_gateway_recovered):
            try:
                self._on_gateway_recovered()
            except Exception as rec_cb_err:
                logger.debug("Gateway recovered callback failed: %s", rec_cb_err)

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
                    if isinstance(data, dict) and bool(data.get("ok", True)):
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
        cleaned = "".join(ch for ch in (raw_key or "").strip() if ord(ch) >= 0x20 and ord(ch) != 0x7F)
        if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in ("'", '"'):
            cleaned = cleaned[1:-1].strip()
        key = cleaned

        if not key:
            return {"ok": False, "message": "Key cannot be empty", "latency_ms": 0}
        if not key.isascii():
            return {"ok": False, "message": "API key contains invalid non-ASCII characters", "latency_ms": 0}
        if len(key) < 8:
            return {"ok": False, "message": "Key length is suspiciously short", "latency_ms": 0}

        endpoint = PROVIDER_ENDPOINTS.get(norm_prov)
        if not endpoint:
            # Unknown provider, check basic length
            return {"ok": True, "message": "Custom key format accepted", "latency_ms": 0}

        t0 = time.perf_counter()
        try:
            if norm_prov == "gemini":
                # Pass Gemini API key via x-goog-api-key header rather than URL query string.
                req = urllib.request.Request(
                    endpoint,
                    headers={
                        "x-goog-api-key": key,
                        "User-Agent": "TradeBot0-Validator/2.0",
                        "Accept": "application/json",
                    },
                )
            else:
                # DeepSeek, Groq, NVIDIA NIM, OpenRouter take Bearer token header
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
            err_body = ""
            try:
                err_body = (he.read(2048) or b"").decode("utf-8", errors="replace")
            except Exception:
                err_body = ""
            finally:
                try:
                    he.close()
                except Exception:
                    pass
            if he.code in (401, 403):
                return {"ok": False, "message": f"Invalid Key / Unauthorized (HTTP {he.code})", "latency_ms": elapsed_ms}
            if norm_prov == "gemini" and he.code == 400 and (
                "API_KEY_INVALID" in err_body or "api key not valid" in err_body.lower()
            ):
                return {"ok": False, "message": "Invalid Key / Unauthorized (HTTP 400)", "latency_ms": elapsed_ms}
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

    def _is_spawn_aborted(self, abort_event: Optional[threading.Event] = None) -> bool:
        if self._abort_spawn_event.is_set():
            return True
        if abort_event is not None and abort_event.is_set():
            return True
        wd = self._watchdog_spawn_abort
        if wd is not None and wd[0] == threading.get_ident() and wd[1].is_set():
            return True
        return False

    def _warn_if_missing_storage_encryption_key(self) -> None:
        db_path = self.omni_data_dir / "storage.sqlite"
        if not db_path.is_file():
            return
        if os.environ.get("STORAGE_ENCRYPTION_KEY", "").strip():
            return
        env_path = self.omni_data_dir / ".env"
        has_key = False
        if env_path.is_file():
            try:
                for raw_line in env_path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
                    parsed = parse_omni_env_line(raw_line)
                    if parsed is not None and parsed[0] == "STORAGE_ENCRYPTION_KEY" and parsed[1].strip():
                        has_key = True
                        break
            except Exception:
                pass
        if not has_key:
            logger.warning(
                "OmniRoute storage.sqlite exists in %s without STORAGE_ENCRYPTION_KEY set in .env; "
                "provider secrets will use OmniRoute's built-in fallback key.",
                self.omni_data_dir,
            )

    def start_daemon(
        self,
        max_wait_sec: float = 30.0,
        abort_event: Optional[threading.Event] = None,
    ) -> Tuple[bool, str]:
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
                self._abort_spawn_event.clear()
                _already_starting = False
        if _already_starting:
            deadline = time.monotonic() + max_wait_sec
            while time.monotonic() < deadline:
                if self._is_spawn_aborted(abort_event):
                    return False, "OmniRoute daemon startup cancelled."
                time.sleep(0.25)
                if self.is_port_open(timeout=0.2):
                    healthy, _ = self.probe_health(timeout=2.0)
                    if healthy:
                        return True, f"Connected to OmniRoute gateway at {self.host}:{self.port} (started by a concurrent request)"
                with self._daemon_lock:
                    still_starting = self._daemon_starting
                if not still_starting:
                    if self.is_port_open(timeout=0.2):
                        healthy, _ = self.probe_health(timeout=2.0)
                        if healthy:
                            return True, f"Connected to OmniRoute gateway at {self.host}:{self.port} (started by a concurrent request)"
                    return False, "Concurrent OmniRoute daemon startup failed."
            return False, f"OmniRoute daemon did not respond within {max_wait_sec}s timeout."
        try:
            return self._start_daemon_once(max_wait_sec, abort_event=abort_event)
        finally:
            with self._daemon_lock:
                self._daemon_starting = False
                self._daemon_starting_thread = None

    def _start_daemon_once(
        self,
        max_wait_sec: float = 30.0,
        abort_event: Optional[threading.Event] = None,
    ) -> Tuple[bool, str]:
        # Single spawn attempt (see start_daemon for the concurrency guard).
        # Step 1: Check if already running and healthy
        if self.is_port_open():
            healthy, _ = self.probe_health(timeout=2.0)
            if healthy:
                return True, f"Connected to existing OmniRoute gateway at {self.host}:{self.port}"
            # If our own previously spawned child is wedged on the port, clean it up and respawn.
            with self._daemon_lock:
                own_hung = bool(self.is_self_spawned and self.child_process is not None)
            if own_hung:
                logger.warning("Self-spawned OmniRoute daemon on port %d failed health probe; recycling it.", self.port)
                self.shutdown()
                self._abort_spawn_event.clear()
                release_deadline = time.monotonic() + 1.5
                while time.monotonic() < release_deadline and self.is_port_open(timeout=0.15):
                    time.sleep(0.1)
                if self.is_port_open(timeout=0.15):
                    return False, f"Port {self.port} is occupied by another application."
            else:
                # Port open but not responding to health check: foreign application conflict
                return False, f"Port {self.port} is occupied by another application."

        # Step 2: Resolve command for 100% headless daemon execution
        cmd = self._get_daemon_command(self.port)
        if not cmd:
            return False, "OmniRoute CLI is not installed or not found in system PATH."

        if self._is_spawn_aborted(abort_event):
            return False, "OmniRoute daemon startup cancelled."

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
            for key in ("_MEIPASS", "_MEIPASS2", "PYTHONPATH", "PYTHONHOME", "INITIAL_PASSWORD"):
                child_env.pop(key, None)
            if cmd and Path(cmd[0]).is_file():
                node_dir = str(Path(cmd[0]).parent)
                cur_path = child_env.get("PATH", "")
                if node_dir and node_dir not in cur_path.split(os.pathsep):
                    child_env["PATH"] = f"{node_dir}{os.pathsep}{cur_path}" if cur_path else node_dir
            # Pin DATA_DIR to the same directory ConfigManager writes .env into
            # (~/.omniroute by default), preventing Windows split-brain with %APPDATA%\omniroute.
            try:
                self.omni_data_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.debug("Could not pre-create omni_data_dir %s: %s", self.omni_data_dir, e)
            child_env["DATA_DIR"] = str(self.omni_data_dir)
            child_env["OMNIROUTE_SERVER_HOST"] = self.host or "127.0.0.1"
            child_env["OMNIROUTE_CLI_SKIP_DEFAULT_DATA_ENV"] = "1"
            child_env["OMNIROUTE_CLI_SKIP_REPO_ENV"] = "1"
            child_env["OMNIROUTE_NO_UPDATE_NOTIFIER"] = "1"
            if (self.omni_data_dir / ".env").is_file():
                # Strip inherited secrets so <DATA_DIR>/.env is the canonical source of truth.
                for env_var in (*PROVIDER_ENV_MAP.values(), "INITIAL_PASSWORD", "STORAGE_ENCRYPTION_KEY"):
                    child_env.pop(env_var, None)
            self._warn_if_missing_storage_encryption_key()
            # Ensure web dashboard is accessible when user clicks Launch Console
            child_env["OMNIROUTE_HEADLESS"] = "0"

            # Close a stale log handle first (respawn after a previous daemon
            # died), then open the daemon log: output goes to a file, not
            # DEVNULL, so a failed startup leaves something to read (item 8).
            with self._daemon_lock:
                old_log = self._daemon_log_file
                self._daemon_log_file = None
            if old_log is not None:
                try:
                    old_log.close()
                except Exception as e:
                    logger.debug("Failed to close stale daemon log handle: %s", e)
            log_file = self._open_daemon_log()
            popen_kwargs: Dict[str, Any] = {
                "cwd": safe_cwd,
                "env": child_env,
                "close_fds": True,
                "startupinfo": startupinfo,
                "creationflags": creation_flags,
                "stdin": subprocess.DEVNULL,
                "stdout": log_file,
                "stderr": log_file,
            }
            if sys.platform != "win32":
                popen_kwargs["start_new_session"] = True
            try:
                proc = subprocess.Popen(cmd, **popen_kwargs)
            except Exception:
                log_file.close()
                raise
            with self._daemon_lock:
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

        # Step 4: Poll health with strict circuit breaker (and fail fast if child exits or aborted)
        deadline = time.monotonic() + max_wait_sec
        exited_early_rc: Optional[int] = None
        aborted = False
        while time.monotonic() < deadline:
            if self._is_spawn_aborted(abort_event):
                aborted = True
                break
            time.sleep(0.25)
            if self._is_spawn_aborted(abort_event):
                aborted = True
                break
            rc = proc.poll()
            if isinstance(rc, int):
                exited_early_rc = rc
                break
            if self.is_port_open(timeout=0.2):
                healthy, _ = self.probe_health(timeout=2.0)
                if healthy:
                    return True, f"OmniRoute daemon started and verified on port {self.port}"

        # Step 5: Timed out, aborted, or crashed early - tear down child process to prevent orphan leak
        self.shutdown()
        if aborted:
            return False, "OmniRoute daemon startup cancelled."
        if exited_early_rc is not None:
            return False, f"OmniRoute daemon exited early (code {exited_early_rc}). Check {self.daemon_log_path}."
        return False, f"OmniRoute daemon did not respond within {max_wait_sec}s timeout."

    def _read_server_pid_file(self) -> Optional[int]:
        pid_path = self.omni_data_dir / "server" / ".pid"
        if not pid_path.is_file():
            return None
        try:
            raw = pid_path.read_text(encoding="utf-8", errors="replace").strip()
            if raw.isdigit():
                val = int(raw)
                return val if val > 0 else None
        except Exception:
            pass
        return None

    def shutdown(self) -> None:
        """Terminates the spawned child process cleanly if created by this supervisor.

        Only ever touches processes this supervisor itself spawned. A gateway
        (or any other program) the user started by hand on the same port is
        left alone: killing it would destroy someone else's process (item 6).
        """
        # Signal any in-flight start_daemon wait loop to abort promptly instead
        # of blocking shutdown for the full 30s health-poll timeout.
        self._abort_spawn_event.set()

        # If another thread is mid-spawn, wait for it to finish
        # assigning child_process (bounded): snapshotting None now would
        # orphan the daemon it is about to spawn. The spawning thread
        # itself never waits (it owns the flag).
        _spawn_deadline = time.monotonic() + 35.0
        while True:
            with self._daemon_lock:
                _starting = self._daemon_starting
                _starter = self._daemon_starting_thread
            if not _starting or _starter == threading.get_ident():
                break
            if time.monotonic() > _spawn_deadline:
                logger.warning("Gateway shutdown timed out waiting for a concurrent spawn")
                break
            time.sleep(0.1)

        with self._daemon_lock:
            was_self_spawned = self.is_self_spawned
            proc = self.child_process if was_self_spawned else None
            self.child_process = None
            self.is_self_spawned = False
            log_file = self._daemon_log_file
            self._daemon_log_file = None

        owned_pid: Optional[int] = None
        owned_pids: Set[int] = set()
        if proc is not None:
            owned_pid = proc.pid
            if isinstance(owned_pid, int) and owned_pid > 0:
                owned_pids.add(owned_pid)
            if was_self_spawned:
                srv_pid = self._read_server_pid_file()
                if srv_pid is not None:
                    owned_pids.add(srv_pid)
            pid = owned_pid
            try:
                logger.info("Terminating self-spawned OmniRoute daemon (PID %d)", pid)
                if sys.platform == "win32":
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(pid)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=15,
                        creationflags=0x08000000,
                        close_fds=True,
                        check=False,
                    )
                    try:
                        proc.wait(timeout=1.5)
                    except Exception as e:
                        logger.debug("Daemon did not exit within wait timeout during shutdown: %s", e)
                    if proc.poll() is None:
                        try:
                            proc.kill()
                            proc.wait(timeout=1.5)
                        except Exception as e:
                            logger.debug("Fallback proc.kill() during shutdown failed: %s", e)
                else:
                    try:
                        os.killpg(os.getpgid(pid), signal.SIGTERM)
                    except Exception:
                        proc.terminate()
                    try:
                        proc.wait(timeout=1.5)
                    except Exception:
                        try:
                            os.killpg(os.getpgid(pid), signal.SIGKILL)
                        except Exception:
                            proc.kill()
                        try:
                            proc.wait(timeout=1.0)
                        except Exception:
                            pass
            except Exception:
                try:
                    proc.kill()
                except Exception as e:
                    logger.debug("Failed to kill daemon process during shutdown: %s", e)

        # Fail-safe cleanup: only if OUR OWN child (or its server/.pid worker)
        # is somehow still holding the port after termination. A foreign listener is never killed.
        if owned_pid is not None and self.is_port_open(timeout=0.1):
            self._kill_port_owner(self.port, owned_pid=owned_pid, owned_pids=owned_pids)

        # Close the daemon log handle opened by start_daemon (if any). This
        # also runs on the timeout path, which calls shutdown() after the
        # daemon failed to become healthy.
        if log_file is not None:
            try:
                log_file.close()
            except Exception as e:
                logger.debug("Failed to close daemon log handle during shutdown: %s", e)

    def _kill_port_owner(
        self,
        port: int,
        owned_pid: Optional[int] = None,
        owned_pids: Optional[Set[int]] = None,
    ) -> None:
        """Terminates a lingering listener on the port ONLY if it is our own
        spawned child (PID match). With owned_pid=None and no owned_pids it
        does nothing: a foreign process on the port is never killed (item 6).
        """
        allowed_pids: Set[int] = set(owned_pids) if owned_pids else set()
        if owned_pid is not None:
            allowed_pids.add(int(owned_pid))
        if not allowed_pids:
            return
        if sys.platform == "win32":
            try:
                output = subprocess.check_output(
                    ["netstat", "-ano"],
                    shell=False,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=15,
                    stderr=subprocess.DEVNULL,
                    creationflags=0x08000000,
                    close_fds=True,
                )
                port_suffix = f":{int(port)}"
                for line in output.splitlines():
                    parts = line.strip().split()
                    if (
                        len(parts) >= 5
                        and parts[1].endswith(port_suffix)
                        and "LISTENING" in parts[3].upper()
                    ):
                        target_pid = parts[4]
                        if target_pid.isdigit() and int(target_pid) in allowed_pids:
                            logger.info("Terminating lingering own daemon on port %d (PID %s)", port, target_pid)
                            subprocess.run(
                                ["taskkill", "/F", "/T", "/PID", target_pid],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                timeout=15,
                                creationflags=0x08000000,
                                close_fds=True,
                                check=False,
                            )
            except Exception as e:
                logger.debug("Failed to terminate lingering daemon on port %s: %s", port, e)

