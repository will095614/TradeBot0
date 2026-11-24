"""Save & Launch stage reporting and honest splash progress.

Problem 1: the wizard showed no progress while save_and_launch ran
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

_ASSETS = Path(__file__).resolve().parents[1] / "src" / "gui" / "assets"


def _make_bridge(tmp_path):
    dash = ArenaDashboard()
    dash.config_manager = ConfigManager(data_dir=tmp_path / "data")
    return dash, _ArenaBridgeApi(dash)


def _read_app_js():
    return (_ASSETS / "app.js").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Problem 1: stage reporting
# ---------------------------------------------------------------------------


def test_save_launch_stage_advances_and_done_only_on_return(tmp_path):
    """Mid-call the stage is 'verifying-ai' at 75; 100 only on return."""
    dash, bridge = _make_bridge(tmp_path)
    seen = {}

    def fake_probe(raw_key, timeout=3.0):
        seen.update(bridge.get_save_launch_status())
        return {"ok": True, "message": "Verified (42ms)", "latency_ms": 42}

    try:
        with patch("src.gui.dashboard.probe_gemini_api_key", side_effect=fake_probe):
            res = bridge.save_and_launch({"gemini": "AIzaSy-test-key-12345"})
        assert res["status"] == "ok"
        assert res["ok"] is True
        assert seen["status"] == "verifying-ai"
        assert seen["progress"] == 75
        assert seen["progress"] < 100
        final = bridge.get_save_launch_status()
        assert final["status"] == "done"
        assert final["progress"] == 100
    finally:
        dash.engine.stop()


def test_save_launch_failed_stage_never_reports_100(tmp_path):
    """A run that fails config persistence reports 'failed', never 100%."""
    dash, bridge = _make_bridge(tmp_path)
    try:
        with patch.object(dash.config_manager, "set_gemini_api_key", return_value={"ok": False, "error": "disk error"}):
            res = bridge.save_and_launch({"gemini": "AIzaSy-test-key-12345"})
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
        with patch("src.gui.dashboard.probe_gemini_api_key", return_value={"ok": True, "message": "Verified", "latency_ms": 15}):
            res = bridge.save_and_launch({"gemini": "AIzaSy-test-key-12345"})
        assert res["ok"] is True
        assert bridge.get_save_launch_status()["status"] == "done"
        with patch.object(dash.config_manager, "save_config", return_value=False):
            res2 = bridge.save_and_launch({"gemini": "AIzaSy-test-key-12345"})
        assert res2["ok"] is False
        assert bridge.get_save_launch_status()["status"] == "failed"
    finally:
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
