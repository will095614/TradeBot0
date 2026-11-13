"""Phase 2G graphics regression tests (2026-11-13).

Contract tests for the graphics optimizations in src/gui/assets/app.js.
These assert the optimization hooks exist in the shipped code; the measured
before/after numbers live in debug_phase2g_report.md (live-app measurement,
not reproducible headless).
"""
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "src" / "gui" / "assets"


def _js():
    return (ASSETS / "app.js").read_text(encoding="utf-8")


def test_p2g_chart_loop_capped_at_60fps():
    """G1 (user decision 2026-11-13): chart rAF loop capped at 60fps.

    The 16.7ms interval constant, the too-early defer via one-shot timer, and
    the -1 sentinel (keeps startChartAnimLoop from double-starting while the
    timer is pending) must all be present; the paused single-render path must
    still exist above the throttle.
    """
    js = _js()
    assert "CHART_FRAME_MIN_INTERVAL_MS = 16.7" in js
    assert "chartAnimLastRenderMs" in js
    assert "chartAnimRaf = -1;" in js
    assert "setTimeout(() => {\n      chartAnimRaf = null;\n      stepChartAnimLoop();\n    }, delayMs);" in js
    # Paused path still renders once and returns before the throttle.
    paused = js.index("if (latestState.paused) {")
    throttle = js.index("CHART_FRAME_MIN_INTERVAL_MS", paused)
    assert paused != -1 and throttle > paused


def test_p2g_hidden_view_stops_chart_loop():
    """G2 (Phase 2G): no chart animation loop while Intel Hub is shown.

    drawPriceChart must check #intelHubMainView and return (after snapping
    the animated values to their targets) instead of starting the loop, so
    the display:none canvas stops consuming frames.
    """
    js = _js()
    assert "G2 (Phase 2G)" in js
    assert "document.getElementById('intelHubMainView')" in js
    assert "animSpot = targetSpot;" in js
    assert "candleSlideOffset = 0;" in js


def test_p2g_no_temporary_probe_left_in_shipped_assets():
    """The temporary P2G measurement probe must never ship."""
    js = _js()
    assert "__P2G_PROBE__" not in js
    assert "127.0.0.1:18777" not in js
