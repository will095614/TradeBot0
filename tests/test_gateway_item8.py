"""Item 8 tests: OmniRoute gateway startup wait, auto-spawn default,
daemon log file, and health-probe timeout."""
import inspect
import re
import subprocess
import sys
import urllib.error
import urllib.request
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
            res = bridge.save_and_launch_gateway({"deepseek": "sk-test-item8-000000000000000000000000"}, auto_spawn=True, admin_password="TestAdmin123")
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
    # Item 10 A1: auto-spawn now requires a configured admin password.
    dash.config_manager.set_admin_password("TestAdmin123")
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


def test_run_skips_auto_spawn_without_admin_password(tmp_path, monkeypatch):
    """run() never auto-spawns a gateway whose console is still on OmniRoute's
    built-in default password (item 10 A1); the wizard forces one first."""
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
    fake_supervisor.start_daemon.assert_not_called()


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


# ------------------------------------------------- P1: probe_health 本體
class _FakeHTTPResponse:
    """Minimal urlopen stand-in: status + read() + context manager."""

    def __init__(self, status, body=b""):
        self.status = status
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_probe_health_success_failure_timeout(tmp_path):
    """probe_health 本體（非 mock probe）：200＋正確 JSON→True；
    非 200／超時／連線拒絕／壞 JSON→False。"""
    gs = GatewaySupervisor(daemon_log_path=tmp_path / "logs" / "omniroute_daemon.log")
    with patch(
        "urllib.request.urlopen",
        return_value=_FakeHTTPResponse(200, b'{"status": "ok", "version": "3.8.53"}'),
    ) as mock_urlopen:
        ok, data = gs.probe_health(timeout=2.0)
    assert ok is True
    assert data == {"status": "ok", "version": "3.8.53"}
    req = mock_urlopen.call_args[0][0]
    assert req.full_url == "http://127.0.0.1:20128/api/health"
    assert mock_urlopen.call_args[1]["timeout"] == 2.0

    with patch("urllib.request.urlopen", return_value=_FakeHTTPResponse(503, b"")):
        assert gs.probe_health() == (False, {})

    with patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")):
        assert gs.probe_health() == (False, {})

    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
        assert gs.probe_health() == (False, {})

    with patch("urllib.request.urlopen", return_value=_FakeHTTPResponse(200, b"not json")):
        assert gs.probe_health() == (False, {})


def test_start_daemon_spawns_and_waits_with_fake_proc(tmp_path):
    """Spawn 路徑：daemon 指令正確、stdout/stderr 進 log 檔、log 寫 PID／時間標頭。"""
    log_path = tmp_path / "logs" / "omniroute_daemon.log"
    gs = GatewaySupervisor(daemon_log_path=log_path)
    fake_proc = MagicMock()
    fake_proc.pid = 4242
    cmd = ["node", "omniroute.mjs", "serve", "--no-open", "--port", "20128"]
    probe_calls = []

    def fake_probe(timeout):
        probe_calls.append(timeout)
        return (True, {"status": "ok"}) if len(probe_calls) >= 2 else (False, {})

    try:
        with patch.object(GatewaySupervisor, "_get_daemon_command", return_value=cmd) as mock_cmd, \
             patch("subprocess.Popen", return_value=fake_proc) as mock_popen, \
             patch.object(gs, "is_port_open", side_effect=[False, True, True]), \
             patch.object(gs, "probe_health", side_effect=fake_probe):
            ok, msg = gs.start_daemon()
        assert ok is True
        assert "verified" in msg
        assert probe_calls == [2.0, 2.0]
        mock_cmd.assert_called_once_with(20128)
        mock_popen.assert_called_once()
        assert mock_popen.call_args[0][0] == cmd
        kwargs = mock_popen.call_args.kwargs
        assert kwargs["stdin"] is subprocess.DEVNULL
        assert kwargs["stdout"] is not subprocess.DEVNULL
        assert kwargs["stderr"] is kwargs["stdout"]
        assert kwargs["stdout"].name.endswith("omniroute_daemon.log")
        assert gs.child_process is fake_proc
        assert gs.is_self_spawned is True
    finally:
        gs.shutdown()
    assert re.search(
        r"--- OmniRoute daemon spawned \(PID 4242\) at \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} ---",
        log_path.read_text(encoding="utf-8"),
    )


def test_start_daemon_times_out_when_health_never_ok(tmp_path):
    """超時路徑：port 已開但 health 永遠 False→回 False，並拆掉自己 spawn 的子行程。"""
    log_path = tmp_path / "logs" / "omniroute_daemon.log"
    gs = GatewaySupervisor(daemon_log_path=log_path)
    fake_proc = MagicMock()
    fake_proc.pid = 4243
    port_checks = {"n": 0}

    def fake_is_port_open(timeout=0.35):
        port_checks["n"] += 1
        return port_checks["n"] > 1

    try:
        with patch.object(GatewaySupervisor, "_get_daemon_command", return_value=["fake-cmd"]), \
             patch("subprocess.Popen", return_value=fake_proc), \
             patch.object(gs, "is_port_open", side_effect=fake_is_port_open), \
             patch.object(gs, "probe_health", return_value=(False, {})) as mock_probe:
            ok, msg = gs.start_daemon(max_wait_sec=0.75)
        assert ok is False
        assert "did not respond" in msg
        assert mock_probe.call_count >= 1
        assert gs.child_process is None
        assert gs._daemon_log_file is None
    finally:
        gs.shutdown()
    assert "4243" in log_path.read_text(encoding="utf-8")
