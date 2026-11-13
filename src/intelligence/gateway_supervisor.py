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
import time
import urllib.error
import urllib.request
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


def _default_daemon_log_path() -> Path:
    """Default daemon log path, mirroring ConfigManager's data-dir layout:
    frozen exe -> %APPDATA%/TradeBot0/logs, source run -> <project root>/logs."""
    if getattr(sys, "frozen", False):
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) / "TradeBot0" if appdata else Path.home() / ".tradebot0"
    else:
        base = Path(__file__).resolve().parent.parent.parent
    return base / "logs" / DAEMON_LOG_FILENAME


class GatewaySupervisor:
    """
    Manages OmniRoute gateway lifecycle and performs fail-safe key verification.
    Guarantees that no error causes an unhandled exception or freezes the UI loop.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 20128,
        daemon_log_path: Optional[Path] = None,
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

        # Register exit hook to clean up child process on application termination
        atexit.register(self.shutdown)

    @classmethod
    def _get_daemon_command(cls, port: int) -> Optional[List[str]]:
        """
        Builds the command line arguments to spawn OmniRoute in 100% headless background mode.
        On Windows, directly uses `node.exe <path_to_omniroute.mjs> serve --no-open --port <port>`
        to bypass `cmd.exe` and `omniroute.cmd` batch scripts which trigger Windows Terminal popups.
        """
        node_bin = shutil.which("node") or shutil.which("node.exe")
        if node_bin:
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
                return {"ok": True, "message": "Key valid (Rate limit 429 active)", "latency_ms": elapsed_ms}
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
        """
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

