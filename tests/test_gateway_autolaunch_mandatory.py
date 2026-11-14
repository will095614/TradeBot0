"""Auto-launch is mandatory: the gateway_auto_spawn option was removed.

Offline mode was removed, so OmniRoute is required to use the app at all.
The setup wizard has no auto-launch checkbox, the gateway always spawns on
Save & Launch and on app start (once onboarding is complete), and a stored
False from an older install is ignored.
"""
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.gui.dashboard import ArenaDashboard, _ArenaBridgeApi
from src.intelligence.config_manager import ConfigManager
from src.intelligence.gateway_supervisor import GatewaySupervisor


def _assets_root() -> Path:
    return Path(__file__).resolve().parent.parent / "src" / "gui" / "assets"


def _make_bridge(tmp_path):
    dash = ArenaDashboard()
    dash.config_manager = ConfigManager(
        data_dir=tmp_path / "data",
        omni_env_path=tmp_path / ".omniroute" / ".env",
    )
    dash.gateway_supervisor = GatewaySupervisor(
        daemon_log_path=tmp_path / "logs" / "omniroute_daemon.log"
    )
    return dash, _ArenaBridgeApi(dash)


def test_wizard_has_no_autolaunch_checkbox():
    """The wizard HTML/CSS/JS contain no auto-launch checkbox at all."""
    html = (_assets_root() / "index.html").read_text(encoding="utf-8")
    css = (_assets_root() / "app.css").read_text(encoding="utf-8")
    js = (_assets_root() / "app.js").read_text(encoding="utf-8")
    assert "chkAutoSpawnGateway" not in html
    assert "chkAutoSpawnGateway" not in js
    assert "Auto-launch background" not in html
    assert "setup-checkbox-row" not in html
    assert "setup-checkbox-row" not in css
    assert "setup-checkbox-label" not in css
    assert "gateway_auto_spawn" not in js
    # The gateway panel keeps its remaining content.
    assert "setup-gateway-options" in html
    assert "Credentials synchronize directly" in html
    assert "Models are auto-routed by OmniRoute" in html
    assert "btnInstallGatewayRuntime" in html


def test_setup_status_has_no_autolaunch_option(tmp_path):
    dash, bridge = _make_bridge(tmp_path)
    try:
        assert "gateway_auto_spawn" not in bridge.get_setup_status()
    finally:
        dash.engine.stop()


def test_save_and_launch_spawns_despite_stored_false(tmp_path):
    """A stored gateway_auto_spawn=False (older install) is ignored: the
    gateway is still started."""
    dash, bridge = _make_bridge(tmp_path)
    try:
        dash.config_manager.save_config({
            "has_completed_onboarding": True,
            "skip_ai_mode": False,
            "gateway_auto_spawn": False,
        })
        dash.config_manager.set_admin_password("TestAdmin123")
        with patch.object(dash.gateway_supervisor, "is_port_open", return_value=False), \
             patch.object(dash.gateway_supervisor, "start_daemon", return_value=(True, "ok")) as mock_start:
            res = bridge.save_and_launch_gateway(
                {"deepseek": "sk-test-mandatory-000000000000000000000000"},
                admin_password="TestAdmin123",
            )
        assert res["ok"] is True
        assert res["gateway_online"] is True
        mock_start.assert_called_once_with(max_wait_sec=30.0)
        assert "gateway_auto_spawn" not in bridge.get_setup_status()
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


def test_run_spawns_despite_stored_false(tmp_path, monkeypatch):
    """run() ignores a stored gateway_auto_spawn=False from an older install."""
    dash = ArenaDashboard()
    dash.config_manager = ConfigManager(
        data_dir=tmp_path / "data",
        omni_env_path=tmp_path / ".omniroute" / ".env",
    )
    dash.config_manager.save_config({
        "has_completed_onboarding": True,
        "skip_ai_mode": False,
        "gateway_auto_spawn": False,
    })
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
