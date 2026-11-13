#!/usr/bin/env python3
"""Fix item 8: OmniRoute gateway startup (TradeBot0 maintenance list).

Applies exact-once-verified replacements to the PC project tree (run with
cwd = project root) and, identically, to the local audit copy.
Every replacement is verified to occur exactly once before anything is
written; on any mismatch the script aborts without touching a file.
Newline style is preserved (files are LF; open with newline="").

Four fixes (all foreground waits stay foreground -- user design):
  1. start_daemon wait 14s/15s -> 30s (two dashboard call sites + default).
  2. gateway_auto_spawn default unified to True (code default was already
     True; the source data/system_config.json said False while the frozen
     %APPDATA% one said True). The script flips the file in place with
     stdlib json (no project imports: the jupyter env running it has no
     project deps), preserving the other keys.
  3. Daemon stdout/stderr go to logs/omniroute_daemon.log (rotated at 5 MB)
     instead of DEVNULL, so a failed startup leaves something to read.
  4. probe_health timeout in start_daemon 0.5s/0.6s -> 2.0s.
"""
import os
import sys

if not os.path.isdir("src/gui"):
    print("FAIL: run this script from the project root (src/gui not found)")
    sys.exit(1)

REPLACEMENTS = []
NEW_FILES = {}

# ------------------------------------------------- gateway_supervisor.py: imports
REPLACEMENTS.append(("src/intelligence/gateway_supervisor.py", r'''import atexit
import json
import logging
import os
import shutil
''', r'''import atexit
import json
import logging
import os
from pathlib import Path
import shutil
'''))

# --------------------------------------- gateway_supervisor.py: log constants
REPLACEMENTS.append(("src/intelligence/gateway_supervisor.py", r'''PROVIDER_ENDPOINTS = {
    "deepseek": "https://api.deepseek.com/models",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/models",
    "groq": "https://api.groq.com/openai/v1/models",
    "openrouter": "https://openrouter.ai/api/v1/models",
}
''', r'''PROVIDER_ENDPOINTS = {
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
'''))

# -------------------------------------------- gateway_supervisor.py: __init__
REPLACEMENTS.append(("src/intelligence/gateway_supervisor.py", r'''    def __init__(self, host: str = "127.0.0.1", port: int = 20128) -> None:
        self.host = host
        self.port = port
        self.child_process: Optional[subprocess.Popen] = None
        self.is_self_spawned: bool = False
''', r'''    def __init__(
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
'''))

# ------------------------- gateway_supervisor.py: log opener + 30 s default
REPLACEMENTS.append(("src/intelligence/gateway_supervisor.py", r'''    def start_daemon(self, max_wait_sec: float = 15.0) -> Tuple[bool, str]:
''', r'''    def _open_daemon_log(self):
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
                except Exception:
                    pass
        return open(log_path, "a", encoding="utf-8", errors="replace", buffering=1)

    def start_daemon(self, max_wait_sec: float = 30.0) -> Tuple[bool, str]:
'''))

# --------------------------- gateway_supervisor.py: existing-daemon probe 2 s
REPLACEMENTS.append(("src/intelligence/gateway_supervisor.py", r'''        if self.is_port_open():
            healthy, _ = self.probe_health(timeout=0.6)
''', r'''        if self.is_port_open():
            healthy, _ = self.probe_health(timeout=2.0)
'''))

# ------------------------------ gateway_supervisor.py: spawn to log file
REPLACEMENTS.append(("src/intelligence/gateway_supervisor.py", r'''            proc = subprocess.Popen(
                cmd,
                cwd=safe_cwd,
                env=child_env,
                close_fds=True,
                startupinfo=startupinfo,
                creationflags=creation_flags,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.child_process = proc
            self.is_self_spawned = True
            logger.info("Spawned headless background OmniRoute daemon (PID %d)", proc.pid)
''', r'''            # Close a stale log handle first (respawn after a previous daemon
            # died), then open the daemon log: output goes to a file, not
            # DEVNULL, so a failed startup leaves something to read (item 8).
            if self._daemon_log_file is not None:
                try:
                    self._daemon_log_file.close()
                except Exception:
                    pass
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
            except Exception:
                pass
            logger.info("Spawned headless background OmniRoute daemon (PID %d)", proc.pid)
'''))

# ------------------------------ gateway_supervisor.py: polling probe 2 s
REPLACEMENTS.append(("src/intelligence/gateway_supervisor.py", r'''                healthy, _ = self.probe_health(timeout=0.5)
''', r'''                healthy, _ = self.probe_health(timeout=2.0)
'''))

# ---------------------------- gateway_supervisor.py: close log on shutdown
REPLACEMENTS.append(("src/intelligence/gateway_supervisor.py", r'''        # Fail-safe cleanup: only if OUR OWN child is somehow still holding
        # the port after termination. A foreign listener is never killed.
        if owned_pid is not None:
            self._kill_port_owner(self.port, owned_pid=owned_pid)
''', r'''        # Fail-safe cleanup: only if OUR OWN child is somehow still holding
        # the port after termination. A foreign listener is never killed.
        if owned_pid is not None:
            self._kill_port_owner(self.port, owned_pid=owned_pid)

        # Close the daemon log handle opened by start_daemon (if any). This
        # also runs on the timeout path, which calls shutdown() after the
        # daemon failed to become healthy.
        if self._daemon_log_file is not None:
            try:
                self._daemon_log_file.close()
            except Exception:
                pass
            self._daemon_log_file = None
'''))

# --------------------------------------- dashboard.py: 14 s -> 30 s (2 sites)
REPLACEMENTS.append(("src/gui/dashboard.py", r'''                spawn_ok, spawn_msg = self._dashboard.gateway_supervisor.start_daemon(max_wait_sec=14.0)
''', r'''                spawn_ok, spawn_msg = self._dashboard.gateway_supervisor.start_daemon(max_wait_sec=30.0)
'''))

REPLACEMENTS.append(("src/gui/dashboard.py", r'''                    self.gateway_supervisor.start_daemon(max_wait_sec=14.0)
''', r'''                    self.gateway_supervisor.start_daemon(max_wait_sec=30.0)
'''))

NEW_FILES["tests/test_gateway_item8.py"] = r'''"""Item 8 tests: OmniRoute gateway startup wait, auto-spawn default,
daemon log file, and health-probe timeout."""
import inspect
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import src.gui.dashboard as dashboard_mod
from src.gui.dashboard import ArenaDashboard, _ArenaBridgeApi
from src.intelligence.config_manager import ConfigManager, DEFAULT_SYSTEM_CONFIG
from src.intelligence.gateway_supervisor import (
    DAEMON_LOG_MAX_BYTES,
    GatewaySupervisor,
    _default_daemon_log_path,
)


# ------------------------------------------------------------ wait: 30 seconds
def test_start_daemon_default_wait_is_30_seconds():
    sig = inspect.signature(GatewaySupervisor.start_daemon)
    assert sig.parameters["max_wait_sec"].default == 30.0


def test_save_and_launch_gateway_waits_30_seconds(tmp_path):
    """Onboarding launch path passes the widened 30 s wait to the supervisor."""
    dash = ArenaDashboard()
    dash.config_manager = ConfigManager(
        data_dir=tmp_path / "data",
        omni_env_path=tmp_path / ".omniroute" / ".env",
    )
    dash.gateway_supervisor = GatewaySupervisor(
        daemon_log_path=tmp_path / "logs" / "omniroute_daemon.log"
    )
    bridge = _ArenaBridgeApi(dash)
    try:
        with patch.object(dash.gateway_supervisor, "is_port_open", return_value=False), \
             patch.object(dash.gateway_supervisor, "start_daemon", return_value=(True, "ok")) as mock_start:
            res = bridge.save_and_launch_gateway({"deepseek": "<redacted>"}, auto_spawn=True)
        assert res["status"] == "ok"
        assert res["gateway_online"] is True
        mock_start.assert_called_once_with(max_wait_sec=30.0)
    finally:
        dash.engine.stop()


class _FakeEvent:
    def __iadd__(self, handler):
        return self


class _FakeWindow:
    def __init__(self):
        self.events = SimpleNamespace(
            shown=_FakeEvent(), closing=_FakeEvent(), closed=_FakeEvent()
        )
        self.on_top = False

    def maximize(self):
        pass

    def destroy(self):
        pass

    def toggle_fullscreen(self):
        pass


class _FakeWebview:
    def __init__(self):
        self.window = _FakeWindow()
        self.started = False

    def create_window(self, *args, **kwargs):
        return self.window

    def start(self, debug=False):
        self.started = True


def test_run_auto_spawn_waits_30_seconds(tmp_path, monkeypatch):
    """run()'s auto-spawn path passes the widened 30 s wait (fake webview)."""
    dash = ArenaDashboard()
    dash.config_manager = ConfigManager(
        data_dir=tmp_path / "data",
        omni_env_path=tmp_path / ".omniroute" / ".env",
    )
    dash.config_manager.save_config({
        "has_completed_onboarding": True,
        "skip_ai_mode": False,
        "gateway_auto_spawn": True,
    })
    fake_supervisor = MagicMock()
    fake_supervisor.is_port_open.return_value = False
    fake_supervisor.start_daemon.return_value = (True, "ok")
    dash.gateway_supervisor = fake_supervisor
    fake_webview = _FakeWebview()
    monkeypatch.setitem(sys.modules, "webview", fake_webview)
    try:
        dash.run()
    finally:
        dash.engine.stop()
    assert fake_webview.started is True
    fake_supervisor.start_daemon.assert_called_once_with(max_wait_sec=30.0)


def test_no_14_second_gateway_wait_remains():
    src = Path(dashboard_mod.__file__).read_text(encoding="utf-8")
    assert "max_wait_sec=14.0" not in src
    assert src.count("max_wait_sec=30.0") == 2


# ------------------------------------------------------- auto-spawn default
def test_gateway_auto_spawn_default_is_true(tmp_path):
    assert DEFAULT_SYSTEM_CONFIG["gateway_auto_spawn"] is True
    cm = ConfigManager(data_dir=tmp_path / "data")
    # No file at all: the merged default spawns the gateway.
    assert cm.load_config()["gateway_auto_spawn"] is True
    # A file that never mentions the key still gets the default.
    (tmp_path / "data" / "system_config.json").write_text(
        '{"has_completed_onboarding": true}', encoding="utf-8"
    )
    assert cm.load_config()["gateway_auto_spawn"] is True


# ------------------------------------------------------------ probe timeout
def test_existing_daemon_check_uses_2s_probe(tmp_path):
    gs = GatewaySupervisor(daemon_log_path=tmp_path / "logs" / "omniroute_daemon.log")
    with patch.object(gs, "is_port_open", return_value=True), \
         patch.object(gs, "probe_health", return_value=(True, {"status": "ok"})) as mock_probe:
        ok, msg = gs.start_daemon()
    assert ok is True
    assert "existing" in msg
    mock_probe.assert_called_once_with(timeout=2.0)


def test_start_daemon_polls_health_with_2s_timeout_and_logs_to_file(tmp_path):
    """Polling loop uses a 2 s probe timeout; daemon output goes to the log
    file (not DEVNULL); shutdown closes the log handle."""
    log_path = tmp_path / "logs" / "omniroute_daemon.log"
    gs = GatewaySupervisor(daemon_log_path=log_path)
    fake_proc = MagicMock()
    fake_proc.pid = 12345
    probe_calls = []

    def fake_probe(timeout):
        probe_calls.append(timeout)
        return (True, {"status": "ok"}) if len(probe_calls) >= 2 else (False, {})

    try:
        with patch.object(GatewaySupervisor, "_get_daemon_command", return_value=["fake-cmd"]), \
             patch("subprocess.Popen", return_value=fake_proc) as mock_popen, \
             patch.object(gs, "is_port_open", side_effect=[False, True, True]), \
             patch.object(gs, "probe_health", side_effect=fake_probe):
            ok, msg = gs.start_daemon()
        assert ok is True
        assert probe_calls == [2.0, 2.0]
        kwargs = mock_popen.call_args.kwargs
        assert kwargs["stdout"] is not subprocess.DEVNULL
        assert kwargs["stderr"] is kwargs["stdout"]
        assert kwargs["stdout"].name.endswith("omniroute_daemon.log")
        assert gs._daemon_log_file is not None
    finally:
        gs.shutdown()
    assert gs._daemon_log_file is None
    assert "12345" in log_path.read_text(encoding="utf-8")


# -------------------------------------------------------------- daemon log
def test_daemon_log_default_path_is_project_logs():
    path = _default_daemon_log_path()
    assert path.name == "omniroute_daemon.log"
    assert path.parent.name == "logs"


def test_daemon_log_rotates_over_5mb(tmp_path):
    log_path = tmp_path / "logs" / "omniroute_daemon.log"
    log_path.parent.mkdir(parents=True)
    log_path.write_bytes(b"x" * (DAEMON_LOG_MAX_BYTES + 1))
    gs = GatewaySupervisor(daemon_log_path=log_path)
    f = gs._open_daemon_log()
    try:
        f.write("fresh\n")
    finally:
        f.close()
    backup = tmp_path / "logs" / "omniroute_daemon.log.1"
    assert backup.is_file()
    assert backup.stat().st_size == DAEMON_LOG_MAX_BYTES + 1
    assert log_path.stat().st_size < 1024
'''


def main():
    for rel, old, new in REPLACEMENTS:
        with open(rel, "r", encoding="utf-8", newline="") as f:
            content = f.read()
        count = content.count(old)
        if count != 1:
            print(f"FAIL {rel}: expected exactly 1 occurrence, found {count}")
            sys.exit(1)
        content = content.replace(old, new)
        with open(rel, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        print(f"OK {rel}")
    for rel, text in NEW_FILES.items():
        if os.path.exists(rel):
            print(f"FAIL {rel}: already exists")
            sys.exit(1)
        with open(rel, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        print(f"CREATED {rel}")

    # Unify the gateway_auto_spawn default on this machine (item 8.2):
    # the code default and the frozen %APPDATA% config are already True;
    # only the source data/system_config.json still said False. Flip it in
    # place (other keys preserved) so source runs match exe behaviour.
    # Stdlib-only on purpose: the jupyter env running this script has no
    # project deps, so ConfigManager cannot be imported here.
    import json
    cfg_path = os.path.join("data", "system_config.json")
    if os.path.isfile(cfg_path):
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        before = cfg.get("gateway_auto_spawn")
        if before is not True:
            cfg["gateway_auto_spawn"] = True
            tmp_path = cfg_path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(json.dumps(cfg, indent=2, ensure_ascii=False))
            os.replace(tmp_path, cfg_path)
            print(f"CONFIG gateway_auto_spawn: {before!r} -> True")
        else:
            print("CONFIG gateway_auto_spawn: already True")
    else:
        print("CONFIG gateway_auto_spawn: no system_config.json (code default is True)")
    print("ALL PATCHES APPLIED")


if __name__ == "__main__":
    main()
