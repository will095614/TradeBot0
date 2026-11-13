"""Item 7 tests: GUI password handling, fabricated view-model values,
view-model fault tolerance, reset state preservation, async evolve,
UI-thread shutdown, single config load."""
import inspect
import json
import pytest
import threading
import time
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import src.gui.dashboard as dashboard_mod
from src.arena.order import FillEvent, OrderSide, PositionSide
from src.data.live_engine import LiveArenaEngine
from src.gui.dashboard import ArenaDashboard, _ArenaBridgeApi
from src.gui.view_model import build_engine_view_model
from src.intelligence.config_manager import ConfigManager
from src.intelligence.gateway_supervisor import GatewaySupervisor


def _rankings(engine):
    return [
        SimpleNamespace(
            portfolio_id=c.portfolio_id, rank=i + 1, equity=100000.0,
            roi_pct=0.0, win_rate_pct=0.0, closed_trades=0,
            max_drawdown_pct=0.0, sharpe_ratio=0.0, fitness_score=0.0,
            name=c.base_name,
        )
        for i, c in enumerate(engine.competitors)
    ]


# ------------------------------------------------------------------ password
def test_setup_status_never_returns_password(tmp_path):
    dash = ArenaDashboard()
    dash.config_manager = ConfigManager(
        data_dir=tmp_path / "data",
        omni_env_path=tmp_path / ".omniroute" / ".env",
    )
    dash.gateway_supervisor = GatewaySupervisor()
    bridge = _ArenaBridgeApi(dash)

    st = bridge.get_setup_status()
    assert st["status"] == "ok"
    assert "omniroute_password" not in st
    assert st["omniroute_password_configured"] is False
    assert "OmniAdmin2026!ChangeMe" not in json.dumps(st)

    # A configured custom password is still never returned, only flagged.
    env_dir = tmp_path / ".omniroute"
    env_dir.mkdir(parents=True, exist_ok=True)
    (env_dir / ".env").write_text("INITIAL_PASSWORD=MySecret123\n", encoding="utf-8")
    st2 = bridge.get_setup_status()
    assert st2["omniroute_password_configured"] is True
    assert "omniroute_password" not in st2
    assert "MySecret123" not in json.dumps(st2)


def test_frontend_assets_contain_no_default_password():
    assets = Path(__file__).resolve().parent.parent / "src" / "gui" / "assets"
    for name in ("index.html", "app.js"):
        text = (assets / name).read_text(encoding="utf-8")
        assert "OmniAdmin2026!ChangeMe" not in text, f"default password still in {name}"


# ------------------------------------------------------- fabricated view model
def test_view_model_does_not_fabricate_take_profit():
    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    try:
        engine.broker.current_price = Decimal("2500")
        comp = engine.comp_a
        comp.portfolio.position_qty = Decimal("10")
        comp.portfolio.position_side = PositionSide.LONG
        comp.portfolio.avg_entry_price = Decimal("2400")
        engine.broker.active_stops[comp.portfolio_id] = SimpleNamespace(price=Decimal("2300"))
        vm = build_engine_view_model(engine, _rankings(engine), 1)
        strat = next(s for s in vm["strategies"] if s["id"] == comp.portfolio_id)
        assert strat["stop_loss"] == 2300.0
        # No target order: unknown (None), not a price synthesized from SL.
        assert strat["take_profit"] is None
    finally:
        engine.stop()


def test_view_model_reports_unknown_mc_and_quota():
    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    try:
        vm = build_engine_view_model(engine, _rankings(engine), 1)
        for strat in vm["strategies"]:
            assert strat["expected_r"] is None
            assert strat["target_prob"] is None
            assert strat["stop_prob"] is None
            assert strat["r_multiple"] is None
            assert strat["ev_passed"] is None
            assert strat["mc_verdict"] is None
        assert vm["quant_meta"]["quota_pct"] is None
        assert vm["omni_meta"]["quota_pct"] is None
    finally:
        engine.stop()


# ------------------------------------------------------------ fault tolerance
def test_view_model_survives_missing_or_broken_engine():
    vm = build_engine_view_model(None, [], 1)
    assert vm["engine_available"] is False
    assert vm["strategies"] == []
    assert "error" in vm

    vm2 = build_engine_view_model(SimpleNamespace(), [], 1)
    assert vm2["engine_available"] is False
    assert vm2["strategies"] == []


def test_view_model_skips_stale_ranking_entry():
    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    try:
        rankings = _rankings(engine) + [
            SimpleNamespace(
                portfolio_id="comp_ghost", rank=99, equity=0.0, roi_pct=0.0,
                win_rate_pct=0.0, closed_trades=0, max_drawdown_pct=0.0,
                sharpe_ratio=0.0, fitness_score=0.0, name="Ghost",
            )
        ]
        vm = build_engine_view_model(engine, rankings, 1)
        assert "error" not in vm
        assert len(vm["strategies"]) == 6
    finally:
        engine.stop()


# ---------------------------------------------------------------- reset_engine
def test_reset_engine_preserves_pause_generation_and_fills():
    dash = ArenaDashboard(initial_cash=Decimal("100000.00"))
    try:
        dash.engine.paused = True
        for c in dash.engine.competitors:
            c.genome = replace(c.genome, generation=5)
        fill = FillEvent(
            order_id="test-1", portfolio_id="comp_agg", symbol="ETH/USD",
            side=OrderSide.BUY, qty=Decimal("1"), price=Decimal("2500"),
            fee=Decimal("1"), timestamp=time.time(),
        )
        dash.engine.fill_records.append(fill)
        dash.engine.evolution_events.append({"generation": 5, "note": "test"})

        dash.reset_engine()

        assert dash.engine.paused is True
        assert max(c.genome.generation for c in dash.engine.competitors) == 5
        assert fill in dash.engine.fill_records
        assert dash.engine.evolution_events[-1].get("note") == "test"
        # Loop thread is alive but paused: no trading resumes by itself.
        assert dash.engine.running is True
        assert all(c.portfolio.position_qty == 0 for c in dash.engine.competitors)
    finally:
        dash.engine.stop()


# ------------------------------------------------------------------ async evolve
def test_manual_evolve_does_not_block_bridge():
    dash = ArenaDashboard(initial_cash=Decimal("100000.00"))
    bridge = _ArenaBridgeApi(dash)
    started = threading.Event()
    release = threading.Event()
    calls = []

    def slow_evolve(trigger="manual"):
        calls.append(trigger)
        started.set()
        release.wait(timeout=10)

    dash.engine.evolve_now = slow_evolve
    try:
        t0 = time.monotonic()
        state = bridge.evolve_now()
        elapsed = time.monotonic() - t0
        assert elapsed < 5.0  # returned without waiting for evolution
        assert started.wait(timeout=5)  # evolution actually started in background
        assert state.get("evolution_running") is True
        bridge.evolve_now()  # second click while running: no second run
        assert len(calls) == 1
    finally:
        release.set()
        deadline = time.monotonic() + 5
        while dash._evolution_running and time.monotonic() < deadline:
            time.sleep(0.05)
        assert dash._evolution_running is False
        dash.engine.stop()


# --------------------------------------------------------------------- shutdown
def test_shutdown_closes_window_on_calling_thread():
    dash = ArenaDashboard(initial_cash=Decimal("100000.00"))
    bridge = _ArenaBridgeApi(dash)
    caller = threading.get_ident()
    seen = []
    mock_win = MagicMock()
    mock_win.destroy.side_effect = lambda: seen.append(threading.get_ident())
    dash.window = mock_win
    try:
        res = bridge.shutdown(save_progress=False)
        assert res["status"] == "shutting_down"
        assert mock_win.destroy.call_count == 1
        assert seen == [caller]  # destroyed on the calling thread, not a background thread
    finally:
        dash.engine.stop()


# ------------------------------------------------------- run() / window handle
def test_run_loads_config_once_and_uses_window_title_constant():
    src = inspect.getsource(dashboard_mod.ArenaDashboard.run)
    assert src.count("load_config()") == 1
    assert "title=WINDOW_TITLE" in src
    assert dashboard_mod.WINDOW_TITLE.startswith("TradeBot0")
    assert callable(dashboard_mod._get_native_hwnd)
    assert dashboard_mod._get_native_hwnd(SimpleNamespace()) is None
    fake = SimpleNamespace(native=SimpleNamespace(Handle=SimpleNamespace(ToInt64=lambda: 12345)))
    assert dashboard_mod._get_native_hwnd(fake) == 12345


# ------------------------------------------------------- short view model
def test_view_model_short_unrealized_pnl_pct():
    """空頭持倉的未實現損益 %（view_model.py:122）等於手算值。

    Short: (entry - spot) / entry * 100。entry 2400、現價 2300 時
    +4.1667%；現價漲到 2500 時 -4.1667%（與多頭版符號相反）。"""
    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    try:
        engine.latest_quote = None  # spot 取 broker.current_price
        engine.broker.current_price = Decimal("2300")
        comp = engine.comp_a
        comp.portfolio.position_qty = Decimal("10")
        comp.portfolio.position_side = PositionSide.SHORT
        comp.portfolio.avg_entry_price = Decimal("2400")
        vm = build_engine_view_model(engine, _rankings(engine), 1)
        strat = next(s for s in vm["strategies"] if s["id"] == comp.portfolio_id)
        assert strat["position_side"] == "SHORT"
        assert strat["in_position"] is True
        assert strat["unrealized_pct"] == pytest.approx((2400 - 2300) / 2400 * 100)

        # 價格漲破進場價：空頭虧損，符號為負。
        engine.broker.current_price = Decimal("2500")
        vm2 = build_engine_view_model(engine, _rankings(engine), 1)
        strat2 = next(s for s in vm2["strategies"] if s["id"] == comp.portfolio_id)
        assert strat2["unrealized_pct"] == pytest.approx((2400 - 2500) / 2400 * 100)
    finally:
        engine.stop()
