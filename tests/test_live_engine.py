import json
import time
from decimal import Decimal

from src.data.live_engine import LiveArenaEngine, LiveQuote


def _quote(price: str) -> LiveQuote:
    p = Decimal(price)
    return LiveQuote(
        price=p, bid=p - Decimal("0.05"), ask=p + Decimal("0.05"),
        high_24h=p + Decimal("40"), low_24h=p - Decimal("40"),
        volume_24h=Decimal("1000"), change_24h_pct=Decimal("1.25"),
        source="UnitTest", timestamp=time.time(),
    )


def _drive(engine: LiveArenaEngine, prices: list[str]) -> None:
    """Feeds synthetic ticks through the same path as the live loop (no network)."""
    prev = None
    for px in prices:
        q = _quote(px)
        engine.latest_quote = q
        engine.tick_count += 1
        engine.live_ema_fast = q.price
        engine.live_ema_slow = q.price - Decimal("1")
        engine.broker.on_tick(q.price, high=q.ask, low=q.bid, timestamp=q.timestamp, open_price=prev or q.price)
        if prev is None:
            engine._ensure_active_live_positions(q.price, q.timestamp)
        engine._evaluate_live_strategies(q.price, prev or q.price, q.timestamp)
        engine._record_series_point(q.price, q.timestamp)
        prev = q.price


def test_live_engine_ui_state_is_json_safe_and_complete():
    engine = LiveArenaEngine(initial_cash=Decimal("500000.00"), symbol="ETH/USD")
    _drive(engine, ["3500.00", "3502.50", "3498.00", "3505.00"])

    state = engine.get_ui_state()
    json.dumps(state, allow_nan=False)  # WebView bridge must never receive NaN/Infinity

    assert state["paused"] is False
    assert len(state["strategies"]) == 6
    assert {s["id"] for s in state["strategies"]} == {"comp_agg", "comp_cons", "comp_atr", "comp_trail", "comp_orb", "comp_vwap"}
    assert any(s["in_position"] for s in state["strategies"])
    assert len(state["price_history"]) == 4
    # Dead payloads eliminated to preserve 97% network/serialization bandwidth
    assert "equity_curves" not in state
    assert "series" not in state
    assert "competitors" not in state
    assert len(json.dumps(state)) < 25000
    assert any(f["side"] == "BUY" for f in state["fills"])

    assert "tv_hub" in state
    assert "champion" in state["tv_hub"]
    assert "payloads" in state["tv_hub"]
    assert "omni_meta" in state
    assert state["omni_meta"]["quota_pct"] == 100.0


def test_live_engine_evolve_preserves_fill_tape_and_portfolio_positions():
    engine = LiveArenaEngine(initial_cash=Decimal("500000.00"))
    _drive(engine, ["3500.00", "3480.00", "3510.00"])
    fills_before = len(engine.fill_records)
    assert fills_before > 0

    engine.evolve_now()
    state = engine.get_ui_state()
    json.dumps(state, allow_nan=False)

    assert state["generation"] >= 2
    assert len(engine.fill_records) >= fills_before
    # Scheme 1: Open positions and equity are preserved across evolution (not wiped)
    assert any(s["in_position"] for s in state["strategies"])
    for s in state["strategies"]:
        assert abs(s["equity"] - 500000.0) < 5000.0


def test_pause_flag_round_trips():
    engine = LiveArenaEngine()
    engine.paused = True
    assert engine.get_ui_state()["paused"] is True


def test_auto_evolve_timer_and_toggle():
    engine = LiveArenaEngine(initial_cash=Decimal("3000.00"))
    _drive(engine, ["3500.00"])
    assert engine.auto_evolve_enabled is True
    # Default interval must be 6 hours (21600s)
    assert engine.auto_evolve_interval_sec == 21600
    now = time.time()
    assert engine._auto_evolve_due(now=now) is False
    assert engine._auto_evolve_due(now=now + 3601) is False  # 1hr is not due yet
    assert engine._auto_evolve_due(now=now + 21601) is True  # 6hr is due

    # Test dynamic switching to 1h
    engine.set_auto_evolve_interval(3600)
    assert engine.auto_evolve_interval_sec == 3600
    assert engine._auto_evolve_due(now=now + 3601) is True

    toggled = engine.toggle_auto_evolve()
    assert toggled is False
    assert engine._auto_evolve_due(now=now + 3601) is False
    state = engine.get_ui_state()
    assert "next_evolve_sec" in state
    assert state["auto_evolve_interval_sec"] == 3600
    assert "candles" in state


def test_fill_event_has_monotonic_seq_and_action_label():
    engine = LiveArenaEngine(initial_cash=Decimal("3000.00"))
    _drive(engine, ["3500.00", "3515.00", "3490.00", "3520.00"])
    state = engine.get_ui_state()
    fills = state["fills"]
    assert len(fills) > 0
    # Every fill should have a positive integer sequence number
    for f in fills:
        assert isinstance(f["seq"], int)
        assert f["seq"] > 0
        assert f["action_label"] in ("OPEN BUY", "CLOSE SELL")


def test_anti_churn_cooldown_prevents_same_timestamp_reentry():
    engine = LiveArenaEngine(initial_cash=Decimal("3000.00"))
    engine.broker.current_price = Decimal("3500.00")
    ts = 1700000000.0
    # Simulate an exit fill setting cooldown
    engine.strategy_cooldown["comp_cons"] = ts + 60.0
    # At the exact same timestamp, evaluation should NOT enter
    engine.comp_b.portfolio.position_qty = Decimal("0.0000")
    engine.live_rsi = Decimal("50.00")
    engine._evaluate_live_strategies(Decimal("3500.00"), Decimal("3501.00"), ts)
    assert engine.comp_b.portfolio.position_qty == Decimal("0.0000")  # Blocked by cooldown!

    # Once timestamp exceeds cooldown, it can enter on tick up
    engine._evaluate_live_strategies(Decimal("3501.00"), Decimal("3500.00"), ts + 61.0)
    assert engine.comp_b.portfolio.position_qty > Decimal("0.0000")  # Entered!


def test_resilient_quote_cache_fallback():
    engine = LiveArenaEngine(initial_cash=Decimal("3000.00"))
    # Seed latest_quote
    cached_q = _quote("3550.00")
    engine.latest_quote = cached_q
    # Test fetch_realtime_eth_quote fallback by simulating connection error
    import unittest.mock as mock
    with mock.patch.object(engine.session, "get", side_effect=Exception("Network Timeout")):
        q = engine.fetch_realtime_eth_quote()
        assert q.price == Decimal("3550.00")
        assert "Cache" in q.source


def test_strategy_palette_and_bracket_state_complete():
    engine = LiveArenaEngine(initial_cash=Decimal("500000.00"))
    # 1. Colors must be distinct and high-contrast
    colors = engine.STRATEGY_COLORS
    assert len(colors) == 6
    assert len(set(colors.values())) == 6
    assert colors["comp_agg"] == "#FF334B"
    assert colors["comp_cons"] == "#38BDF8"
    assert colors["comp_atr"] == "#FFB800"
    assert colors["comp_trail"] == "#00E676"
    assert colors["comp_orb"] == "#A855F7"
    assert colors["comp_vwap"] == "#14F195"

    # 2. Drive with ticks to prime all positions
    _drive(engine, ["3500.00", "3502.00"])
    state = engine.get_ui_state()
    strategies = state["strategies"]
    assert len(strategies) == 6
    for s in strategies:
        assert s["color"] in colors.values()
        assert "in_position" in s
        assert "stop_loss" in s
        assert "take_profit" in s
        if s["in_position"]:
            assert s["entry_price"] is not None and s["entry_price"] > 0
            assert s["stop_loss"] is not None and s["stop_loss"] > 0


def test_ui_template_integrity_and_cleanliness():
    from src.gui.dashboard import HTML_TEMPLATE
    import re
    # 1. Zero Chinese characters in GUI template
    chinese_match = re.findall(r"[\u4e00-\u9fff]", HTML_TEMPLATE)
    assert len(chinese_match) == 0, f"Found Chinese characters in UI: {chinese_match}"

    # 2. Key CSS classes & Micro-Animations present
    assert "live-dot" in HTML_TEMPLATE
    assert "radarRipple" in HTML_TEMPLATE
    assert "tickUpGlow" in HTML_TEMPLATE
    assert "tickDownGlow" in HTML_TEMPLATE
    assert "markerPulse" in HTML_TEMPLATE
    assert "newFillFlash" in HTML_TEMPLATE
    assert "idleBlink" in HTML_TEMPLATE
    assert "toggleFullscreen" in HTML_TEMPLATE
    assert "badge-buy" in HTML_TEMPLATE
    assert "badge-sell" in HTML_TEMPLATE
    assert "evolveIntervalSelect" in HTML_TEMPLATE
    assert "changeEvolveInterval" in HTML_TEMPLATE

    # 3. Fills reason does not duplicate Cost string
    engine = LiveArenaEngine(initial_cash=Decimal("3000.00"))
    _drive(engine, ["3500.00", "3510.00", "3490.00"])
    state = engine.get_ui_state()
    for f in state["fills"]:
        assert "(Cost $" not in f["reason"]


def test_startup_ev_gate_enforcement():
    from unittest.mock import patch
    from src.data.timemachine import MonteCarloBracketOdds

    engine = LiveArenaEngine(initial_cash=Decimal("500000.00"), symbol="ETH/USD")
    failing_odds = MonteCarloBracketOdds(
        passed=False,
        target_prob=0.10,
        stop_prob=0.80,
        neither_prob=0.10,
        decided_win_rate=0.11,
        expected_r=-0.75,
        r_multiple=2.0,
        breakeven_prob=0.33,
        verdict="Blocked by EV Gate (EV -0.75R | Win 11%)"
    )
    with patch.object(engine.mc_evaluator, "evaluate_bracket", return_value=failing_odds):
        engine._ensure_active_live_positions(Decimal("3500.00"), time.time())

    for c in engine.competitors:
        assert c.portfolio.position_qty == Decimal("0.0000")
        assert "EV Gate Blocked" in engine.strategy_telemetry[c.portfolio_id]["intent"]






