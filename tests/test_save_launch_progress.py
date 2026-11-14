"""Save & Launch stage reporting and honest splash progress.

Problem 1: the wizard showed no progress while save_and_launch_gateway ran
(a single synchronous bridge call). The backend now records the current
stage; these tests prove the stage advances, stays below 100% mid-call,
and reaches 100% only when the call actually returns -- and that a failed
run never reports 100%.

Problem 2: the splash bar could display 100% while the exit gate (first
chart frame + first tables + min duration) was still closed. The static
tests below prove the structural rules: the target is capped at 90 until
the gate opens, the render flags only ever become true from real renders
(or the 3.5 s safety timer), and Save & Launch no longer jump-starts the
splash at 75%.
"""
import re
from pathlib import Path
from unittest.mock import patch

from src.gui.dashboard import ArenaDashboard, _ArenaBridgeApi
from src.intelligence.config_manager import ConfigManager
from src.intelligence.gateway_supervisor import GatewaySupervisor

_ASSETS = Path(__file__).resolve().parents[1] / "src" / "gui" / "assets"


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


def _read_app_js():
    return (_ASSETS / "app.js").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Problem 1: stage reporting
# ---------------------------------------------------------------------------


def test_save_launch_stage_advances_and_done_only_on_return(tmp_path):
    """Mid-call the stage is 'starting-gateway' at 70; 100 only on return."""
    dash, bridge = _make_bridge(tmp_path)
    seen = {}

    def fake_start_daemon(max_wait_sec=30.0):
        # Capture the stage exactly while the gateway is still starting.
        seen.update(bridge.get_save_launch_status())
        return (True, "ok")

    try:
        # start_watchdog is mocked: a real watchdog thread must never start
        # in tests — a delayed first tick could outlive these mocks and spawn
        # a real gateway on the machine.
        with patch.object(dash.gateway_supervisor, "is_port_open", return_value=False), \
             patch.object(dash.gateway_supervisor, "start_daemon", side_effect=fake_start_daemon), \
             patch.object(dash.gateway_supervisor, "start_watchdog", return_value=True):
            res = bridge.save_and_launch_gateway(
                {"deepseek": "sk-test-key"}, admin_password="test-password-1"
            )
        assert res["status"] == "ok"
        assert seen["status"] == "starting-gateway"
        assert seen["progress"] == 70
        assert seen["progress"] < 100
        final = bridge.get_save_launch_status()
        assert final["status"] == "done"
        assert final["progress"] == 100
    finally:
        dash.gateway_supervisor.stop_watchdog()
        dash.engine.stop()


def test_save_launch_failed_stage_never_reports_100(tmp_path):
    """A run that fails validation reports 'failed', never 100%."""
    dash, bridge = _make_bridge(tmp_path)
    try:
        # No password configured and none supplied: the call fails fast.
        res = bridge.save_and_launch_gateway({"deepseek": "sk-test-key"})
        assert res["ok"] is False
        stage = bridge.get_save_launch_status()
        assert stage["status"] == "failed"
        assert stage["progress"] != 100
    finally:
        dash.engine.stop()


def test_save_launch_stage_resets_between_runs(tmp_path):
    """A second, failing run must not show the first run's stale 'done'."""
    dash, bridge = _make_bridge(tmp_path)
    try:
        # start_watchdog is mocked: a real watchdog thread must never start
        # in tests — a delayed first tick could outlive these mocks and spawn
        # a real gateway on the machine.
        with patch.object(dash.gateway_supervisor, "is_port_open", return_value=True), \
             patch.object(dash.gateway_supervisor, "probe_health", return_value=(True, "ok")), \
             patch.object(dash.gateway_supervisor, "start_watchdog", return_value=True):
            res = bridge.save_and_launch_gateway(
                {"deepseek": "sk-test-key"}, admin_password="test-password-1"
            )
        assert res["ok"] is True
        assert bridge.get_save_launch_status()["status"] == "done"
        res2 = bridge.save_and_launch_gateway(
            {"deepseek": "sk-test-key"}, admin_password="short"
        )
        assert res2["ok"] is False
        assert bridge.get_save_launch_status()["status"] == "failed"
    finally:
        dash.gateway_supervisor.stop_watchdog()
        dash.engine.stop()


def test_get_save_launch_status_returns_copy(tmp_path):
    """Mutating the returned dict must not corrupt the stored stage."""
    dash, bridge = _make_bridge(tmp_path)
    try:
        first = bridge.get_save_launch_status()
        first["status"] = "tampered"
        first["progress"] = 100
        second = bridge.get_save_launch_status()
        assert second["status"] == "idle"
        assert second["progress"] is None
    finally:
        dash.engine.stop()


def test_save_launch_status_polled_from_js():
    """The wizard poll loop must call the new bridge method (the UI
    contract test also fails on an uncalled bridge method)."""
    js = _read_app_js()
    assert "pywebview.api.get_save_launch_status" in js
    assert "setupSaveProgress" in js


# ---------------------------------------------------------------------------
# Problem 2: honest splash 100%
# ---------------------------------------------------------------------------


def test_splash_target_capped_at_90_while_gate_closed():
    """setSplashTarget must consult the exit gate and cap the target at 90
    while it is closed, so the bar can never display 100% early."""
    js = _read_app_js()
    m = re.search(r"function setSplashTarget\(percent\) \{(.*?)\n\}", js, re.S)
    assert m, "setSplashTarget not found in app.js"
    body = m.group(1)
    assert "isSplashGateOpen" in body, "setSplashTarget must consult the exit gate"
    assert "90" in body, "setSplashTarget must cap the target at 90 while the gate is closed"


def test_splash_no_unconditional_flag_set_on_timer():
    """The render flags may only become true from a real render (chart draw
    / table render) or the 3.5 s safety timer -- never from a timed jump."""
    js = _read_app_js()
    assert js.count("hasFirstChartDrawn = true") == 2, (
        "hasFirstChartDrawn may only be set by drawPriceChart and the "
        "safety timer"
    )
    assert js.count("hasFirstTableRendered = true") == 2, (
        "hasFirstTableRendered may only be set by renderAll and the "
        "safety timer"
    )


def test_save_and_launch_does_not_jump_splash_to_75():
    """The two remaining setSplashTarget(75) calls are the honest ones:
    the 1300 ms bootstrapped milestone and the poll-driven quote step.
    Save & Launch must not jump-start the splash."""
    js = _read_app_js()
    assert js.count("setSplashTarget(75)") == 2
