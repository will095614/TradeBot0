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
    assert len(state["strategies"]) == 5
    assert {s["id"] for s in state["strategies"]} == {"comp_agg", "comp_cons", "comp_trail", "comp_orb", "comp_vwap"}
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
    assert "market_online" in state
    assert "quant_meta" in state
    assert state["quant_meta"]["active_model"] == "Genetic Evolution + Monte Carlo EV"


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
        assert f["action_label"] in ("OPEN LONG", "CLOSE LONG", "OPEN SHORT", "COVER SHORT")


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


def test_no_cached_price_when_feed_down():
    # Offline mode removed (item 3): when every live source fails, the fetch
    # must report offline instead of returning the last price as if live.
    engine = LiveArenaEngine(initial_cash=Decimal("3000.00"))
    # Seed latest_quote with a perfectly good price
    cached_q = _quote("3550.00")
    engine.latest_quote = cached_q
    import unittest.mock as mock
    with mock.patch.object(engine.session, "get", side_effect=Exception("Network Timeout")):
        q = engine.fetch_realtime_eth_quote()
        assert q.is_offline is True
        assert q.price == Decimal("0.00")
        assert q.source == "Market Offline (No Feed)"


def test_strategy_palette_and_bracket_state_complete():
    engine = LiveArenaEngine(initial_cash=Decimal("500000.00"))
    # 1. Colors must be distinct and high-contrast
    colors = engine.STRATEGY_COLORS
    assert len(colors) == 5
    assert len(set(colors.values())) == 5
    assert colors["comp_agg"] == "#FF334B"
    assert colors["comp_cons"] == "#38BDF8"
    assert colors["comp_trail"] == "#00E676"
    assert colors["comp_orb"] == "#A855F7"
    assert colors["comp_vwap"] == "#FFD60A"

    # 2. Drive with ticks to prime all positions
    _drive(engine, ["3500.00", "3502.00"])
    state = engine.get_ui_state()
    strategies = state["strategies"]
    assert len(strategies) == 5
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

    # 3. High-Tech Splash Screen elements present
    assert "splashOverlay" in HTML_TEMPLATE
    assert "splashProgressBar" in HTML_TEMPLATE
    assert "splashStepLabel" in HTML_TEMPLATE
    assert "splashPercentLabel" in HTML_TEMPLATE

    # 4. Fills reason does not duplicate Cost string
    engine = LiveArenaEngine(initial_cash=Decimal("3000.00"))
    _drive(engine, ["3500.00", "3510.00", "3490.00"])
    state = engine.get_ui_state()
    for f in state["fills"]:
        assert "(Cost $" not in f["reason"]


def test_startup_ev_gate_enforcement():
    from unittest.mock import patch
    from src.data.timemachine import MonteCarloBracketOdds

    engine = LiveArenaEngine(initial_cash=Decimal("500000.00"), symbol="ETH/USD")
    # Audit 3.3: startup entries route through evaluate_signal, so the
    # EV gate only sees strategies whose own entry condition holds. Seed
    # a genuine uptrend + ORB range + session mean so all five attempt an
    # entry and reach the (mocked failing) gate; with default live state
    # ORB has no range to break out of and never reaches the gate.
    engine.live_ema_fast = Decimal("3500.00")
    engine.live_ema_slow = Decimal("3490.00")
    engine.live_rsi = Decimal("50.00")
    engine.live_atr = Decimal("20.00")
    engine.live_orb_high = Decimal("3490.00")
    engine.live_orb_low = Decimal("3390.00")
    engine.live_typical_mean = Decimal("3495.00")
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


def test_offline_feed_safety_blocks_mock_fills():
    import unittest.mock as mock

    engine = LiveArenaEngine(initial_cash=Decimal("500000.00"), symbol="ETH/USD")
    engine.latest_quote = None  # No cache

    with mock.patch.object(engine.session, "get", side_effect=Exception("Total network disconnect")):
        q = engine.fetch_realtime_eth_quote()
        assert q.is_offline is True
        assert q.price == Decimal("0.00")
        assert "Offline" in q.source

    # Ensure state exposes market_online=False and no simulated orders are filled
    state = engine.get_ui_state()
    assert state["market_online"] is False
    assert state["quote"]["price"] == 0.0
    assert state["quote"]["is_offline"] is True


def _fixture_bars(n=120):
    """Deterministic test-only candles so bootstrap has a warm chart.

    Tests run with ARENA_FAST_TEST=1, so the live feed returns no bars and
    the test SQLite cache is empty; previously the (now deleted) synthetic
    fallback supplied these. Fixture data, never production data.
    """
    import time
    from decimal import Decimal
    from src.data.eth_feed import CandleBar

    now = time.time()
    bars = []
    price = 3500.0
    for i in range(n):
        bars.append(CandleBar(
            timestamp=now - (n - i) * 60.0,
            open_=Decimal(f"{price:.2f}"),
            high=Decimal(f"{price + 5:.2f}"),
            low=Decimal(f"{price - 5:.2f}"),
            close=Decimal(f"{price:.2f}"),
            volume=Decimal("15.00"),
            ema_fast=Decimal(f"{price:.2f}"),
            ema_slow=Decimal(f"{price:.2f}"),
            rsi=Decimal("50.00"),
            atr=Decimal("12.00"),
        ))
        price += 1.0
    return bars


def test_lifecycle_sequence_warmup_before_live_orders(monkeypatch):
    # Tests run with ARENA_FAST_TEST=1, so no real bars are fetched; seed the
    # bootstrap with deterministic fixture bars (test-only data).
    monkeypatch.setattr("src.data.live_engine.ETHFeed.fetch_historical_bars", staticmethod(lambda *a, **k: _fixture_bars()))
    engine = LiveArenaEngine(initial_cash=Decimal("500000.00"), symbol="ETH/USD")
    assert engine.is_bootstrapped is False
    assert engine.live_orders_enabled is False

    # Simulate historical warmup
    engine.bootstrap_intraday_session()
    assert engine.is_bootstrapped is True
    assert len(engine.candles) >= 30
    # During warmup, live order placement is suppressed
    assert engine.live_orders_enabled is False

    state = engine.get_ui_state()
    assert state["is_bootstrapped"] is True
    assert state["live_orders_enabled"] is False
    assert state["candle_count"] >= 30

    # Frontend verifies render -> triggers start_live_trading
    engine.start_live_trading()
    assert engine.live_orders_enabled is True
    assert engine.get_ui_state()["live_orders_enabled"] is True


def test_live_engine_eth_and_leverage_configuration():
    engine = LiveArenaEngine()
    assert engine.symbol == "ETH/USD"
    assert engine.initial_cash == Decimal("100000.00")
    for c in engine.competitors:
        assert c.portfolio.cash == Decimal("100000.00")
        assert c.portfolio.total_equity == Decimal("100000.00")

    # Verify per-competitor leverage policies
    assert engine.comp_a.genome.leverage_enabled is True
    assert engine.comp_a.genome.leverage == Decimal("3.0")

    assert engine.comp_b.genome.leverage_enabled is False
    assert engine.comp_b.genome.leverage == Decimal("1.0")

    assert engine.comp_d.genome.leverage_enabled is True
    assert engine.comp_d.genome.leverage == Decimal("2.0")

    assert engine.comp_e.genome.leverage_enabled is True
    assert engine.comp_e.genome.leverage == Decimal("2.5")

    assert engine.comp_f.genome.leverage_enabled is False
    assert engine.comp_f.genome.leverage == Decimal("1.0")

    # Verify view model exposes leverage attributes
    state = engine.get_ui_state()
    for strat in state["strategies"]:
        assert "leverage" in strat
        assert "leverage_enabled" in strat
        assert "leverage_label" in strat
        assert "margin_locked" in strat
        if strat["id"] == "comp_agg":
            assert strat["leverage_enabled"] is True
            assert strat["leverage"] == 3.0
            assert "3.0x Lev" in strat["leverage_label"]
        elif strat["id"] == "comp_cons":
            assert strat["leverage_enabled"] is False
            assert "Spot 1x" in strat["leverage_label"]


def test_live_engine_bidirectional_long_and_short_execution():
    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    ts = 1700000000.0
    engine.live_start_ts = ts
    engine.is_bootstrapped = True
    engine.live_orders_enabled = True

    # 1. Drive a downtrend tick sequence: price falling, EMA fast < slow
    engine.live_ema_fast = Decimal("3400.00")
    engine.live_ema_slow = Decimal("3500.00")
    engine.live_rsi = Decimal("30.00")
    engine.live_atr = Decimal("20.00")

    # comp_a breakdown short entry
    engine.comp_a.portfolio.position_qty = Decimal("0.0000")
    engine.strategy_cooldown["comp_agg"] = 0.0
    engine._evaluate_live_strategies(Decimal("3400.00"), Decimal("3420.00"), ts + 1.0)

    # If TimeMachine passed, verify Comp A entered SHORT
    if engine.comp_a.portfolio.position_qty > Decimal("0.0000"):
        assert engine.comp_a.portfolio.position_side.value == "SHORT"
        assert engine.broker.active_stops["comp_agg"].price > Decimal("3400.00")  # Short SL is ABOVE entry!

    # 2. Drive an oversold/uptrend tick sequence: price rising, RSI bounce
    engine.live_ema_fast = Decimal("3550.00")
    engine.live_ema_slow = Decimal("3500.00")
    engine.live_rsi = Decimal("45.00")
    engine.comp_b.portfolio.position_qty = Decimal("0.0000")
    engine.strategy_cooldown["comp_cons"] = 0.0
    engine._evaluate_live_strategies(Decimal("3520.00"), Decimal("3510.00"), ts + 2.0)

    # Verify UI state exposes position_side
    state = engine.get_ui_state()
    for strat in state["strategies"]:
        assert "position_side" in strat
        assert strat["position_side"] in ("FLAT", "LONG", "SHORT")







def test_auto_evolve_fires_on_closed_trades():
    """Evolution optimization (item 4b): auto-evolution fires after 30 closed
    trades (not opens), earliest 30 minutes after the previous evolution;
    the 6-hour cap still fires on time alone."""
    from src.arena.order import OrderSide, OrderTicket, OrderType

    engine = LiveArenaEngine(initial_cash=Decimal("3000.00"))
    engine.latest_quote = _quote("3500.00")
    now = time.time()
    engine.last_evolve_ts = now

    # 6-hour cap still works with zero trades.
    assert engine._auto_evolve_reason(now=now + 21601) == "time"

    def _round_trips(n):
        broker = engine.broker
        broker.on_tick(price=Decimal("3500.00"), timestamp=now)
        for _ in range(n):
            buy = OrderTicket("comp_cons", "ETH/USD", OrderSide.BUY, OrderType.MARKET, qty=Decimal("0.1"), timestamp=now)
            assert broker.submit_order(buy) is not None
            sell = OrderTicket("comp_cons", "ETH/USD", OrderSide.SELL, OrderType.MARKET, qty=Decimal("0.1"), timestamp=now)
            assert broker.submit_order(sell) is not None
        engine._harvest_fills()

    _round_trips(29)
    assert engine._closed_trades_since_evolve == 29
    assert engine._auto_evolve_due(now=now + 100) is False
    assert engine._auto_evolve_due(now=now + 2000) is False  # debounce ok, still < 30

    _round_trips(1)
    assert engine._closed_trades_since_evolve == 30
    assert engine._auto_evolve_due(now=now + 100) is False  # debounce blocks
    assert engine._auto_evolve_reason(now=now + 1801) == "trades"
    assert engine._auto_evolve_due(now=now + 1801) is True

    # Evolving resets the counter.
    engine.evolve_now(trigger="manual")
    assert engine._closed_trades_since_evolve == 0
    assert engine._auto_evolve_due(now=now + 1801) is False

# =========================================================== P0-A
# Short-side live evaluation, indicator math, restore path, and
# quote-provider parsing/fallback. All mock, zero network.
# ===========================================================


def _open_short(engine, pid, qty="0.5", ts=1700001000.0):
    """Open a short directly through the broker (fill ~3499.47 @ 3500).

    Returns the fill. The entry ticket carries a stop above / target
    below entry, so broker.active_stops/targets are armed like a real
    live entry.
    """
    from src.arena.order import OrderSide, OrderType, OrderTicket

    engine.broker.current_price = Decimal("3500.00")
    ticket = OrderTicket(
        pid, "ETH/USD", OrderSide.SELL, OrderType.MARKET, qty=Decimal(qty),
        stop_loss=Decimal("3552.50"), take_profit=Decimal("3430.00"),
        timestamp=ts,
    )
    fill = engine.broker.submit_order(ticket)
    assert fill is not None
    return fill


def _open_long(engine, pid, qty="0.5", ts=1700001000.0):
    """Open a long directly through the broker (fill just above 3500).

    Mirror of _open_short: the entry ticket carries a stop below /
    target above entry, so broker.active_stops/targets are armed like a
    real live entry.
    """
    from src.arena.order import OrderSide, OrderType, OrderTicket

    engine.broker.current_price = Decimal("3500.00")
    ticket = OrderTicket(
        pid, "ETH/USD", OrderSide.BUY, OrderType.MARKET, qty=Decimal(qty),
        stop_loss=Decimal("3447.50"), take_profit=Decimal("3570.00"),
        timestamp=ts,
    )
    fill = engine.broker.submit_order(ticket)
    assert fill is not None
    return fill


def _kraken_payload():
    return {"result": {"ETHUSD": {
        "c": ["3500.55", "0.1"],
        "o": "3400.00",
        "b": ["3500.00", "1", "1.0"],
        "a": ["3501.00", "1", "1.0"],
        "h": ["3600.00", "3610.00"],
        "l": ["3390.00", "3380.00"],
        "v": ["100.0", "1234.567"],
    }}}


def _coinbase_ticker_payload():
    return {"price": "3501.25", "bid": "3501.00", "ask": "3501.50", "volume": "987.654"}


def _coinbase_stats_payload():
    return {"open": "3400.00", "high": "3605.00", "low": "3395.00"}


def _mock_resp(status=200, payload=None):
    import unittest.mock as mock

    resp = mock.Mock()
    resp.status_code = status
    resp.json.return_value = payload
    return resp


def test_evaluate_live_strategies_short_exits_are_signal_only():
    """Audit 2.1: the hardcoded +0.25%/+0.15%/+0.35%/+0.30% profit caps
    (and ATR's max($8, 1.4xATR) cap) are gone -- a favourable move no
    longer closes a position by itself. Only a genuine signal reversal
    closes (Conservative: price back to EMA-fast; Session Mean: price
    past mean - 1.5xATR), and the Trailing Guard still ratchets.

    Same setup as the old short-take-profits test (2.5% favourable
    move, all five short): Aggressive / ORB stay SHORT with their
    brackets intact -- the 2.5% move is far past every removed cap, yet
    nothing closes them. The bracket TP (3430.00) is already passed by
    the 3412 price, so in the real cadence broker.on_tick would have
    filled it before _evaluate_live_strategies runs; this test drives
    _evaluate_live_strategies directly, so it stays armed here.
    """
    from src.arena.order import ExecutionReason, OrderSide, PositionSide

    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    ts = 1700001000.0
    for pid in ("comp_agg", "comp_cons", "comp_trail", "comp_orb", "comp_vwap"):
        _open_short(engine, pid, ts=ts)
    entries = {c.portfolio_id: c.portfolio.avg_entry_price for c in engine.competitors}
    for entry in entries.values():
        assert Decimal("3400.00") < entry < Decimal("3600.00")

    engine.live_atr = Decimal("20.00")
    engine.live_rsi = Decimal("50.00")
    engine.live_ema_fast = Decimal("3500.00")
    engine.live_ema_slow = Decimal("3490.00")
    entry = entries["comp_agg"]
    price = (entry * Decimal("0.975")).quantize(Decimal("0.01"))
    engine.broker.current_price = price
    engine._evaluate_live_strategies(price, entry, ts)

    # No profit cap: Aggressive / ATR / ORB stay short, brackets intact.
    for pid in ("comp_agg", "comp_orb"):
        comp = next(c for c in engine.competitors if c.portfolio_id == pid)
        assert comp.portfolio.position_qty == Decimal("0.5"), pid
        assert comp.portfolio.position_side == PositionSide.SHORT, pid
        assert pid not in engine.strategy_cooldown, pid
        assert pid in engine.broker.active_targets, pid  # bracket still armed

    # Signal reversals still close: Conservative (price back under
    # EMA-fast) and Session Mean (price past mean - 1.5xATR).
    for pid in ("comp_cons", "comp_vwap"):
        comp = next(c for c in engine.competitors if c.portfolio_id == pid)
        assert comp.portfolio.position_qty == Decimal("0"), pid
        assert comp.portfolio.position_side == PositionSide.FLAT, pid
        assert engine.strategy_cooldown[pid] == ts + 60.0, pid
        assert pid not in engine.broker.active_stops, pid
        assert pid not in engine.broker.active_targets, pid
    tp_fills = [f for f in engine.broker.execution_audit if f.reason == ExecutionReason.TAKE_PROFIT]
    assert {f.portfolio_id for f in tp_fills} == {"comp_cons", "comp_vwap"}
    for f in tp_fills:
        assert f.side == OrderSide.BUY  # covering a short
        assert f.qty == Decimal("0.5")

    # Trailing Guard has no TAKE_PROFIT market exit: its short exit is
    # the ratchet lowering the stop as the trough extends.
    trail = engine.comp_d
    assert trail.portfolio.position_qty == Decimal("0.5")
    assert trail.portfolio.position_side == PositionSide.SHORT
    assert trail.trailing_active is True
    assert trail.lowest_price_since_entry == price
    new_stop = engine.broker.active_stops["comp_trail"]
    assert new_stop.side == OrderSide.BUY
    assert new_stop.reason == ExecutionReason.TRAILING_STOP
    assert new_stop.price == (price * (Decimal("1") + trail.genome.trailing_distance_pct)).quantize(Decimal("0.01"))
    assert new_stop.price < Decimal("3552.50")
    assert "comp_trail" not in engine.strategy_cooldown


def test_evaluate_live_strategies_small_gain_does_not_close_longs():
    """Audit 2.1 (longs): a +1.00% gain -- past every removed profit cap
    (agg 0.25%, cons 0.15%, orb 0.35%, vwap
    0.30%) -- must NOT close any long. Indicators are set so no signal
    reversal fires either (EMA-fast above price, ORB mid below price,
    mean + 1.5xATR above price), so the only exit left is the genome
    bracket, which sits at 3570.00, above the test price."""
    from src.arena.order import ExecutionReason, PositionSide

    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    ts = 1700001000.0
    opened = ("comp_agg", "comp_cons", "comp_orb", "comp_vwap")
    for pid in opened:
        _open_long(engine, pid, ts=ts)
    entries = {
        pid: next(c for c in engine.competitors if c.portfolio_id == pid).portfolio.avg_entry_price
        for pid in opened
    }
    for entry in entries.values():
        assert Decimal("3400.00") < entry < Decimal("3600.00")

    engine.live_atr = Decimal("20.00")
    engine.live_rsi = Decimal("50.00")
    engine.live_ema_fast = Decimal("3540.00")
    engine.live_ema_slow = Decimal("3530.00")
    engine.live_orb_high = Decimal("3535.00")
    engine.live_orb_low = Decimal("3515.00")
    engine.live_typical_mean = Decimal("3520.00")
    entry = entries["comp_agg"]
    price = (entry * Decimal("1.01")).quantize(Decimal("0.01"))
    engine.broker.current_price = price
    engine._evaluate_live_strategies(price, entry, ts)

    for pid in ("comp_agg", "comp_cons", "comp_orb", "comp_vwap"):
        comp = next(c for c in engine.competitors if c.portfolio_id == pid)
        assert comp.portfolio.position_qty == Decimal("0.5"), pid
        assert comp.portfolio.position_side == PositionSide.LONG, pid
        assert pid not in engine.strategy_cooldown, pid
        assert pid in engine.broker.active_targets, pid  # bracket intact
    assert not [f for f in engine.broker.execution_audit
                if f.reason == ExecutionReason.TAKE_PROFIT]


def test_evaluate_live_strategies_small_gain_does_not_close_shorts():
    """Audit 2.1 (shorts): a -1.00% favourable move -- past every removed
    profit cap -- must NOT close any short. Indicators are set so no
    signal reversal fires either (EMA-fast below price, ORB mid above
    price, mean - 1.5xATR below price). The Trailing Guard stays open
    too: its 2.0% trigger is not reached at a 1.0% gain."""
    from src.arena.order import ExecutionReason, PositionSide

    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    ts = 1700001000.0
    for pid in ("comp_agg", "comp_cons", "comp_trail", "comp_orb", "comp_vwap"):
        _open_short(engine, pid, ts=ts)
    entries = {c.portfolio_id: c.portfolio.avg_entry_price for c in engine.competitors}
    for entry in entries.values():
        assert Decimal("3400.00") < entry < Decimal("3600.00")

    engine.live_atr = Decimal("20.00")
    engine.live_rsi = Decimal("50.00")
    engine.live_ema_fast = Decimal("3460.00")
    engine.live_ema_slow = Decimal("3470.00")
    engine.live_orb_high = Decimal("3490.00")
    engine.live_orb_low = Decimal("3470.00")
    engine.live_typical_mean = Decimal("3480.00")
    entry = entries["comp_agg"]
    price = (entry * Decimal("0.99")).quantize(Decimal("0.01"))
    engine.broker.current_price = price
    engine._evaluate_live_strategies(price, entry, ts)

    for pid in ("comp_agg", "comp_cons", "comp_trail", "comp_orb", "comp_vwap"):
        comp = next(c for c in engine.competitors if c.portfolio_id == pid)
        assert comp.portfolio.position_qty == Decimal("0.5"), pid
        assert comp.portfolio.position_side == PositionSide.SHORT, pid
        assert pid not in engine.strategy_cooldown, pid
        assert pid in engine.broker.active_targets, pid  # bracket intact
    assert not [f for f in engine.broker.execution_audit
                if f.reason == ExecutionReason.TAKE_PROFIT]


def test_bracket_take_profit_closes_via_on_tick():
    """Audit 2.1: with the hardcoded profit caps gone, the genome
    bracket is what closes a position at its target. A long whose
    bracket TP sits at 3570.00 closes when broker.on_tick sees the
    high touch 3570.00 -- with a TAKE_PROFIT fill, the position flat,
    and the bracket cleared."""
    from src.arena.order import ExecutionReason, OrderSide, PositionSide

    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    ts = 1700001000.0
    _open_long(engine, "comp_agg", ts=ts)
    comp = engine.comp_a
    assert comp.portfolio.position_side == PositionSide.LONG
    assert engine.broker.active_targets["comp_agg"].price == Decimal("3570.00")

    fills = engine.broker.on_tick(
        price=Decimal("3570.00"), high=Decimal("3570.00"),
        low=Decimal("3570.00"), timestamp=ts, open_price=Decimal("3570.00"),
    )
    assert len(fills) == 1
    assert fills[0].reason == ExecutionReason.TAKE_PROFIT
    assert fills[0].side == OrderSide.SELL
    assert fills[0].qty == Decimal("0.5")
    assert comp.portfolio.position_qty == Decimal("0")
    assert comp.portfolio.position_side == PositionSide.FLAT
    assert "comp_agg" not in engine.broker.active_targets
    assert "comp_agg" not in engine.broker.active_stops


def test_evaluate_live_strategies_short_entries():
    import unittest.mock as mock
    from src.arena.order import OrderSide, PositionSide

    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    engine.broker.current_price = Decimal("3500.00")
    # Downtrend, falling price, RSI high: satisfies the live short-entry
    # conditions of CONS (RSI>=58, vel<=0) and ORB (price<=ORB low,
    # vel<=0) at once.
    engine.live_rsi = Decimal("60.00")
    engine.live_atr = Decimal("20.00")
    engine.live_ema_fast = Decimal("3500.00")
    engine.live_ema_slow = Decimal("3510.00")
    engine.live_orb_high = Decimal("3510.00")
    engine.live_orb_low = Decimal("3495.00")
    engine.live_typical_mean = Decimal("3500.00")
    ts = 1700001000.0

    with mock.patch.object(engine, "_enter_via_strategy", wraps=engine._enter_via_strategy) as spy:
        engine._evaluate_live_strategies(Decimal("3490.00"), Decimal("3500.00"), ts)

    entered = {}
    for call in spy.call_args_list:
        args, kwargs = call[0], call[1]
        if kwargs.get("side") == OrderSide.SELL:
            entered[args[0].portfolio_id] = args[3]
    assert entered["comp_cons"] == "SCALP_SHORT"
    assert entered["comp_orb"] == "ORB_SHORT"

    for pid in ("comp_cons", "comp_orb"):
        comp = next(c for c in engine.competitors if c.portfolio_id == pid)
        assert comp.portfolio.position_side == PositionSide.SHORT
        assert comp.portfolio.position_qty > Decimal("0")
        stop = engine.broker.active_stops[pid]
        assert stop.side == OrderSide.BUY  # short stop buys to cover
        assert stop.price > comp.portfolio.avg_entry_price
    # Brackets are the strategies' own (genome) brackets, not hand-made:
    # CONS stop = entry x 1.01 (1.0% SL),
    # ORB stop = entry + max($10, ORB-mid - entry) = ORB midpoint 3502.50.
    assert engine.broker.active_stops["comp_cons"].price == Decimal("3524.90")
    assert engine.broker.active_stops["comp_orb"].price == Decimal("3502.50")


def test_recompute_candle_indicators_rsi_atr_orb_mean():
    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))

    def _candles(closes):
        return [{"t": float(i), "o": float(c), "h": float(c + 5), "l": float(c - 5), "c": float(c)}
                for i, c in enumerate(closes)]

    # 20 known candles, closes alternating +10 / -5 / +15.
    # Hand-computed Wilder RSI(14)/ATR(14):
    #   first-14 gains 100, losses 35 -> avg_g 100/14, avg_l 35/14;
    #   Wilder-smoothed over the last 5 diffs (+15,-5,+15,-5,+15)
    #   -> avg_g 7.722987..., avg_l 2.343485..., RSI 76.72.
    #   TR is 15 (+10/+15 diffs) or 10 (-5 diffs); first-14 mean 12.5,
    #   Wilder-smoothed over the last 5 TRs -> ATR 15.07.
    #   ORB = first 15 bars: high 3570+5=3575, low 3500-5=3495.
    #   Typical mean = mean of (h+l+c)/3 = mean of closes = 3547.75.
    closes = [3500, 3510, 3505, 3520, 3515, 3530, 3525, 3540, 3535, 3550,
              3545, 3560, 3555, 3570, 3565, 3580, 3575, 3590, 3585, 3600]
    engine.candles = _candles(closes)
    engine._recompute_candle_indicators()
    assert engine.live_rsi == Decimal("76.72")
    assert engine.live_atr == Decimal("15.07")
    assert engine.broker.current_atr == Decimal("15.07")
    assert engine.live_orb_high == Decimal("3575.00")
    assert engine.live_orb_low == Decimal("3495.00")
    assert engine.live_typical_mean == Decimal("3547.75")

    # EMA helper: alpha=2/(3+1)=0.5 over [100..104] -> 103.06.
    assert LiveArenaEngine._calc_ema([100.0, 101.0, 102.0, 103.0, 104.0], 3) == 103.06
    assert LiveArenaEngine._calc_ema([], 3) == 0.0

    # Boundaries, each hand-computed the same way.
    cases = [
        # (closes, rsi, atr, orb_high, orb_low, typical_mean)
        ([3500] * 20, "50.00", "10.00", "3505.00", "3495.00", "3500.00"),  # all flat
        ([3500 + 10 * i for i in range(20)], "100.00", "15.00", "3645.00", "3495.00", "3595.00"),  # all up
        ([3500 - 10 * i for i in range(20)], "0.00", "15.00", "3505.00", "3355.00", "3405.00"),  # all down
    ]
    # Audit 3.4: the ORB range is frozen once a session's first 15 bars
    # are in, so each boundary case needs its own fresh engine (a new
    # session) instead of reusing one engine's frozen range. The asserted
    # RSI/ATR/ORB/mean values are unchanged.
    for closes_b, rsi_b, atr_b, orb_h_b, orb_l_b, mean_b in cases:
        case_engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
        case_engine.candles = _candles(closes_b)
        case_engine._recompute_candle_indicators()
        assert case_engine.live_rsi == Decimal(rsi_b)
        assert case_engine.live_atr == Decimal(atr_b)
        assert case_engine.live_orb_high == Decimal(orb_h_b)
        assert case_engine.live_orb_low == Decimal(orb_l_b)
        assert case_engine.live_typical_mean == Decimal(mean_b)

    # Fewer than 15 candles: indicators are left untouched.
    fresh = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    fresh.candles = _candles(closes[:10])
    fresh._recompute_candle_indicators()
    assert fresh.live_rsi == Decimal("50.00")
    assert fresh.live_atr == Decimal("85.00")


def test_deserialize_ticket_round_trips_and_rejects_garbage():
    from src.arena.order import OrderSide, OrderTicket, OrderType

    D = LiveArenaEngine._deserialize_ticket

    # None / unhandled types never raise.
    assert D(None) is None
    assert D(["not", "a", "ticket"]) is None

    # OrderTicket passes through untouched.
    t0 = OrderTicket("comp_cons", "ETH/USD", OrderSide.SELL, OrderType.STOP_MARKET,
                     qty=Decimal("0.5"), price=Decimal("3550.00"))
    assert D(t0) is t0

    # Normal dict round-trips every field.
    t = D({"portfolio_id": "comp_cons", "symbol": "ETH/USD", "side": "BUY",
           "order_type": "LIMIT", "qty": "0.25", "price": "3500.00",
           "stop_loss": "3400.00", "take_profit": "3600.00"})
    assert t is not None
    assert (t.portfolio_id, t.symbol, t.side, t.order_type, t.qty, t.price,
            t.stop_loss, t.take_profit) == (
        "comp_cons", "ETH/USD", OrderSide.BUY, OrderType.LIMIT,
        Decimal("0.25"), Decimal("3500.00"), Decimal("3400.00"), Decimal("3600.00"))

    # A bare number carries no quantity: dropped, not a qty=0 stop.
    assert D(3550.00) is None
    assert D("3550.00") is None
    # Missing / zero / negative qty: dropped, not a qty=0 stop.
    assert D({"portfolio_id": "comp_cons", "price": "3550.00"}) is None
    assert D({"portfolio_id": "comp_cons", "qty": "0", "price": "3550.00"}) is None
    assert D({"portfolio_id": "comp_cons", "qty": "-1", "price": "3550.00"}) is None
    # Missing price does not crash (price None, qty kept).
    t_noprice = D({"portfolio_id": "comp_cons", "qty": "0.5"})
    assert t_noprice is not None and t_noprice.price is None
    # Missing / invalid side/type fall back to SELL / STOP_MARKET.
    t_def = D({"portfolio_id": "comp_cons", "qty": "0.5", "price": "3550.00"})
    assert t_def.side == OrderSide.SELL
    assert t_def.order_type == OrderType.STOP_MARKET
    t_bad = D({"portfolio_id": "comp_cons", "side": "HOLD", "order_type": "ICEBERG",
               "qty": "0.5", "price": "3550.00"})
    assert t_bad.side == OrderSide.SELL
    assert t_bad.order_type == OrderType.STOP_MARKET

    # Restore level: a qty=0 ticket must not be mounted as a live stop.
    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    zero_stop = {"portfolio_id": "comp_cons", "symbol": "ETH/USD", "side": "SELL",
                 "order_type": "STOP_MARKET", "qty": "0", "price": "3550.00",
                 "stop_loss": None, "take_profit": None}
    assert engine.restore_session_state(
        {"competitors": [], "active_stops": {"comp_cons": zero_stop}, "active_targets": {}}) is True
    assert "comp_cons" not in engine.broker.active_stops
    # ... while a real stop still mounts.
    zero_stop["qty"] = "0.5"
    assert engine.restore_session_state(
        {"competitors": [], "active_stops": {"comp_cons": zero_stop}, "active_targets": {}}) is True
    assert engine.broker.active_stops["comp_cons"].qty == Decimal("0.5")
    assert engine.broker.active_stops["comp_cons"].price == Decimal("3550.00")


def test_restore_open_position_recomputes_margin_and_stops():
    from src.arena.order import OrderSide, OrderTicket, OrderType, PositionSide

    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    stop = OrderTicket("comp_cons", "ETH/USD", OrderSide.BUY, OrderType.STOP_MARKET,
                       qty=Decimal("0.5"), price=Decimal("3550.00"))
    target = OrderTicket("comp_cons", "ETH/USD", OrderSide.BUY, OrderType.LIMIT,
                         qty=Decimal("0.5"), price=Decimal("3400.00"))
    # No "margin_locked" key on purpose: restore must recompute it as
    # cost / leverage -- cons is spot 1x (1750.00), agg is 3x (583.33).
    snapshot = {
        "schema_version": 2, "generation": 1,
        "competitors": [
            {"portfolio_id": "comp_cons", "cash": "98250.00", "position_qty": "0.5",
             "position_side": "SHORT", "avg_entry_price": "3500.00",
             "current_market_price": "3490.00", "realized_pnl": "0",
             "total_fees_paid": "0", "gross_profit": "0", "gross_loss": "0",
             "win_count": 0, "loss_count": 0, "peak_equity": "100000.00",
             "max_drawdown_pct": "0.00", "is_circuit_breaker_tripped": False},
            {"portfolio_id": "comp_agg", "cash": "100000.00", "position_qty": "0.5",
             "position_side": "SHORT", "avg_entry_price": "3500.00",
             "current_market_price": "3490.00", "realized_pnl": "0",
             "total_fees_paid": "0", "gross_profit": "0", "gross_loss": "0",
             "win_count": 0, "loss_count": 0, "peak_equity": "100000.00",
             "max_drawdown_pct": "0.00", "is_circuit_breaker_tripped": False},
        ],
        "active_stops": {"comp_cons": LiveArenaEngine._serialize_ticket(stop)},
        "active_targets": {"comp_cons": LiveArenaEngine._serialize_ticket(target)},
        "position_entry_ts": {"comp_cons": 1700000000.0},
    }
    assert engine.restore_session_state(snapshot) is True

    cons = engine.comp_b.portfolio
    assert cons.position_qty == Decimal("0.5")
    assert cons.position_side == PositionSide.SHORT
    assert cons.avg_entry_price == Decimal("3500.00")
    assert cons.cash == Decimal("98250.00")
    assert cons.margin_locked == Decimal("1750.00")  # 0.5 x 3500 / 1x
    agg = engine.comp_a.portfolio
    assert agg.margin_locked == Decimal("583.33")  # 0.5 x 3500 / 3x

    restored_stop = engine.broker.active_stops["comp_cons"]
    assert restored_stop.side == OrderSide.BUY
    assert restored_stop.price == Decimal("3550.00")
    assert restored_stop.qty == Decimal("0.5")
    restored_target = engine.broker.active_targets["comp_cons"]
    assert restored_target.order_type == OrderType.LIMIT
    assert restored_target.price == Decimal("3400.00")
    assert engine.position_entry_ts["comp_cons"] == 1700000000.0

    # Invalid stored genome: the default genome is kept and RESTORE_WARN
    # is logged (stop_loss_pct 0.50 is outside [0.006, 0.035]).
    engine2 = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    default_sl = engine2.comp_b.genome.stop_loss_pct
    bad = {"portfolio_id": "comp_cons", "cash": "100000.00", "position_qty": "0",
           "position_side": "FLAT", "avg_entry_price": "0",
           "genome": {"position_ratio": "0.25", "risk_per_trade_pct": "0.010",
                      "stop_loss_pct": "0.50", "take_profit_pct": "0.018",
                      "atr_risk_pct": "0.015", "atr_stop_mult": "1.5",
                      "atr_target_mult": "2.5", "trailing_trigger_pct": "2.0",
                      "trailing_distance_pct": "0.006", "cooldown_bars": 0,
                      "generation": 1, "leverage_enabled": False,
                      "leverage": "1.0", "news_sensitivity": 0.3}}
    assert engine2.restore_session_state({"competitors": [bad]}) is True
    assert engine2.comp_b.genome.stop_loss_pct == default_sl
    assert any(e.get("tag") == "RESTORE_WARN" for e in engine2.live_logs)



def test_restore_applies_genome_leverage_to_portfolio():
    # Audit 3.2: the restored genome's leverage must reach the portfolio
    # ledger. Before the fix the ledger kept the constructor default, so
    # a genome evolved to 4.5x resumed with 3x margin math (RiskGuard
    # sizing, margin affordability, total_equity all diverge).
    from decimal import ROUND_HALF_UP

    from src.arena.order import OrderSide, OrderTicket, OrderType

    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))

    def _genome(**overrides):
        base = {
            "position_ratio": "0.40", "risk_per_trade_pct": "0.015",
            "stop_loss_pct": "0.015", "take_profit_pct": "0.025",
            "atr_risk_pct": "0.015", "atr_stop_mult": "1.5",
            "atr_target_mult": "2.5", "trailing_trigger_pct": "2.0",
            "trailing_distance_pct": "0.006", "cooldown_bars": 0,
            "generation": 5, "leverage_enabled": False,
            "leverage": "1.0", "news_sensitivity": 0.5,
        }
        base.update(overrides)
        return base

    def _flat_comp(pid, genome):
        return {"portfolio_id": pid, "cash": "100000.00",
                "position_qty": "0", "position_side": "FLAT",
                "avg_entry_price": "0", "current_market_price": "3500.00",
                "realized_pnl": "0", "total_fees_paid": "0",
                "gross_profit": "0", "gross_loss": "0",
                "win_count": 0, "loss_count": 0,
                "peak_equity": "100000.00", "max_drawdown_pct": "0.00",
                "is_circuit_breaker_tripped": False, "genome": genome}

    snapshot = {"competitors": [
        # Aggressive default is 3x: an evolved 4.5x genome must win.
        _flat_comp("comp_agg", _genome(position_ratio="0.70",
                                       risk_per_trade_pct="0.025",
                                       stop_loss_pct="0.035",
                                       take_profit_pct=None,
                                       leverage_enabled=True,
                                       leverage="4.5",
                                       news_sensitivity=0.8)),
        # Trailing Guard default is 2x enabled: a stored genome with
        # leverage switched off must land at 1.0x, not keep 2.0x.
        _flat_comp("comp_trail", _genome(leverage_enabled=False,
                                         leverage="2.0",
                                         news_sensitivity=0.5)),
    ]}
    assert engine.restore_session_state(snapshot) is True

    agg = engine.comp_a
    assert agg.genome.leverage == Decimal("4.5")
    assert agg.genome.leverage_enabled is True
    assert agg.portfolio.leverage == Decimal("4.5")
    assert agg.portfolio.leverage_enabled is True

    trail = engine.comp_d
    assert trail.genome.leverage_enabled is False
    assert trail.portfolio.leverage == Decimal("1.0")
    assert trail.portfolio.leverage_enabled is False

    # Derived quantity: the next fill's margin must be struck at the
    # restored 4.5x, not the 3x constructor default.
    engine.broker.on_tick(Decimal("3500"), high=Decimal("3500.05"),
                          low=Decimal("3499.95"), timestamp=time.time(),
                          open_price=Decimal("3500"))
    fill = engine.broker.submit_order(OrderTicket(
        portfolio_id="comp_agg", symbol="ETH/USD", side=OrderSide.BUY,
        order_type=OrderType.MARKET, qty=Decimal("1"),
        timestamp=time.time()))
    assert fill is not None
    expected_margin = ((fill.qty * fill.price) / Decimal("4.5")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP)
    assert agg.portfolio.margin_locked == expected_margin
    stale_margin = ((fill.qty * fill.price) / Decimal("3.0")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP)
    assert agg.portfolio.margin_locked != stale_margin



def _startup_engine_long():
    # Shared setup: uptrend, RSI 50, ATR 20, ORB range 3390-3490 with
    # price above the high, mean 3495 just under the price -- every
    # strategy's deploy direction is LONG and its evaluate_signal entry
    # condition is met.
    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    price = Decimal("3500")
    engine.live_ema_fast = Decimal("3500")
    engine.live_ema_slow = Decimal("3490")
    engine.live_rsi = Decimal("50")
    engine.live_atr = Decimal("20")
    engine.live_orb_high = Decimal("3490")
    engine.live_orb_low = Decimal("3390")
    engine.live_typical_mean = Decimal("3495")
    engine.broker.on_tick(price, high=price + Decimal("0.05"),
                          low=price - Decimal("0.05"),
                          timestamp=time.time(), open_price=price)
    engine._ensure_active_live_positions(price, time.time())
    return engine


def test_startup_brackets_match_genome_brackets_long():
    # Audit 3.3: the first trade of a session must carry the genome
    # brackets (via each strategy's own evaluate_signal), not the old
    # hardcoded startup brackets (cons 0.6%/0.9%, trail 0.9%, ORB 0.8%,
    # mean 0.7%).
    engine = _startup_engine_long()
    stops = engine.broker.active_stops
    targets = engine.broker.active_targets
    # Aggressive LONG (uptrend): genome 3.5% SL, uncapped TP.
    assert stops["comp_agg"].price == Decimal("3377.50")
    assert "comp_agg" not in targets
    # Conservative LONG (RSI 50): genome 1.0% SL / 1.8% TP.
    assert stops["comp_cons"].price == Decimal("3465.00")
    assert targets["comp_cons"].price == Decimal("3563.00")
    # Trailing LONG: genome 1.5% SL, no TP.
    assert stops["comp_trail"].price == Decimal("3447.50")
    assert "comp_trail" not in targets
    # ORB LONG (price above range high): midpoint SL, 2.0R target.
    # orb_mid = (3490 + 3390) / 2 = 3440; stop_dist = 60.
    assert stops["comp_orb"].price == Decimal("3440.00")
    assert targets["comp_orb"].price == Decimal("3620.00")
    # Session Mean LONG (price near the mean): mean-anchored SL, 2.2R.
    assert stops["comp_vwap"].price == Decimal("3485.00")
    assert targets["comp_vwap"].price == Decimal("3533.00")
    # All five actually deployed.
    assert all(c.portfolio.position_qty > Decimal("0")
               for c in engine.competitors)


def test_startup_brackets_match_genome_brackets_short():
    # Audit 3.3, short side: downtrend, RSI 60, ATR 20, ORB range
    # 3510-3610 with price below the low, mean 3505 just above the
    # price -- every strategy's deploy direction is SHORT and its
    # evaluate_signal entry condition is met.
    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    price = Decimal("3500")
    engine.live_ema_fast = Decimal("3490")
    engine.live_ema_slow = Decimal("3500")
    engine.live_rsi = Decimal("60")
    engine.live_atr = Decimal("20")
    engine.live_orb_high = Decimal("3610")
    engine.live_orb_low = Decimal("3510")
    engine.live_typical_mean = Decimal("3505")
    engine.broker.on_tick(price, high=price + Decimal("0.05"),
                          low=price - Decimal("0.05"),
                          timestamp=time.time(), open_price=price)
    engine._ensure_active_live_positions(price, time.time())
    stops = engine.broker.active_stops
    targets = engine.broker.active_targets
    # Aggressive SHORT: genome 3.5% SL, uncapped TP.
    assert stops["comp_agg"].price == Decimal("3622.50")
    assert "comp_agg" not in targets
    # Conservative SHORT: genome 1.0% SL / 1.8% TP.
    assert stops["comp_cons"].price == Decimal("3535.00")
    assert targets["comp_cons"].price == Decimal("3437.00")
    # Trailing SHORT: genome 1.5% SL, no TP.
    assert stops["comp_trail"].price == Decimal("3552.50")
    assert "comp_trail" not in targets
    # ORB SHORT (price below range low): midpoint SL, 2.0R target.
    assert stops["comp_orb"].price == Decimal("3560.00")
    assert targets["comp_orb"].price == Decimal("3380.00")
    # Session Mean SHORT: mean-anchored SL, 2.2R target.
    assert stops["comp_vwap"].price == Decimal("3515.00")
    assert targets["comp_vwap"].price == Decimal("3467.00")
    assert all(c.portfolio.position_qty > Decimal("0")
               for c in engine.competitors)


def test_binance_quote_success_parses_all_fields():
    import unittest.mock as mock

    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    payload = {"lastPrice": "3512.34", "bidPrice": "3512.10", "askPrice": "3512.50",
               "highPrice": "3600.00", "lowPrice": "3400.00", "volume": "12345.678",
               "priceChangePercent": "2.50"}
    with mock.patch.object(engine.session, "get",
                           return_value=_mock_resp(200, payload)) as mocked_get:
        q = engine._fetch_binance_quote()
    assert mocked_get.call_args[0][0] == "https://api.binance.com/api/v3/ticker/24hr?symbol=ETHUSDT"
    assert q is not None
    assert q.price == Decimal("3512.34")
    assert q.bid == Decimal("3512.10")
    assert q.ask == Decimal("3512.50")
    assert q.high_24h == Decimal("3600.00")
    assert q.low_24h == Decimal("3400.00")
    assert q.volume_24h == Decimal("12345.68")
    assert q.change_24h_pct == Decimal("2.50")
    assert q.source == "Binance Live"
    assert q.is_offline is False


def test_kraken_quote_success_parses():
    import unittest.mock as mock

    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    with mock.patch.object(engine.session, "get",
                           return_value=_mock_resp(200, _kraken_payload())) as mocked_get:
        q = engine._fetch_kraken_quote()
    assert mocked_get.call_args[0][0] == "https://api.kraken.com/0/public/Ticker?pair=ETHUSD"
    assert q is not None
    # price = last trade c[0]; change = (3500.55-3400)/3400*100 = 2.96;
    # high/low/volume are the 24h entries h[1]/l[1]/v[1].
    assert q.price == Decimal("3500.55")
    assert q.bid == Decimal("3500.00")
    assert q.ask == Decimal("3501.00")
    assert q.high_24h == Decimal("3610.00")
    assert q.low_24h == Decimal("3380.00")
    assert q.volume_24h == Decimal("1234.57")
    assert q.change_24h_pct == Decimal("2.96")
    assert q.source == "Kraken Live"
    assert q.is_offline is False

    # Kraken down: the fetcher itself returns None...
    with mock.patch.object(engine.session, "get", side_effect=Exception("Kraken down")):
        assert engine._fetch_kraken_quote() is None
    # ... and the full fetch falls through to Coinbase.
    engine2 = LiveArenaEngine(initial_cash=Decimal("100000.00"))

    def dispatch(url, timeout=None, **kwargs):
        if "binance" in url or "kraken" in url:
            raise Exception("provider down")
        if "ticker" in url:
            return _mock_resp(200, _coinbase_ticker_payload())
        return _mock_resp(200, _coinbase_stats_payload())

    with mock.patch.object(engine2.session, "get", side_effect=dispatch):
        q2 = engine2.fetch_realtime_eth_quote()
    assert q2 is not None
    assert q2.source == "Coinbase Live"
    assert q2.price == Decimal("3501.25")


def test_coinbase_quote_success_parses():
    import unittest.mock as mock

    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    ticker = _mock_resp(200, _coinbase_ticker_payload())
    stats = _mock_resp(200, _coinbase_stats_payload())
    with mock.patch.object(engine.session, "get", side_effect=[ticker, stats]):
        q = engine._fetch_coinbase_quote()
    assert q is not None
    # change = (3501.25-3400)/3400*100 = 2.98; volume 987.654 -> 987.65.
    assert q.price == Decimal("3501.25")
    assert q.bid == Decimal("3501.00")
    assert q.ask == Decimal("3501.50")
    assert q.high_24h == Decimal("3605.00")
    assert q.low_24h == Decimal("3395.00")
    assert q.volume_24h == Decimal("987.65")
    assert q.change_24h_pct == Decimal("2.98")
    assert q.source == "Coinbase Live"
    assert q.is_offline is False

    # Stats down: the quote is still returned, with price-based 24h
    # high/low and 0.00 change (only the ticker gates the quote).
    with mock.patch.object(engine.session, "get",
                           side_effect=[_mock_resp(200, _coinbase_ticker_payload()),
                                        _mock_resp(500, {})]):
        q2 = engine._fetch_coinbase_quote()
    assert q2 is not None
    assert q2.price == Decimal("3501.25")
    assert q2.high_24h == Decimal("3501.25")
    assert q2.low_24h == Decimal("3501.25")
    assert q2.change_24h_pct == Decimal("0.00")

    # Ticker down: no quote at all.
    with mock.patch.object(engine.session, "get", side_effect=Exception("Coinbase down")):
        assert engine._fetch_coinbase_quote() is None
    with mock.patch.object(engine.session, "get",
                           side_effect=[_mock_resp(500, {}), _mock_resp(200, {})]):
        assert engine._fetch_coinbase_quote() is None


def test_quote_provider_fallback_order_and_cooldown():
    import unittest.mock as mock

    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    calls = []

    def dispatch(url, timeout=None, **kwargs):
        calls.append(url)
        if "binance" in url:
            raise Exception("Binance down")
        if "kraken" in url:
            return _mock_resp(200, _kraken_payload())
        raise AssertionError("coinbase must not be reached: " + url)

    # Binance fails -> Kraken wins and becomes the preferred provider.
    with mock.patch.object(engine.session, "get", side_effect=dispatch):
        q = engine.fetch_realtime_eth_quote()
    assert q is not None
    assert q.source == "Kraken Live"
    assert engine.preferred_quote_provider == "kraken"
    assert calls[0].startswith("https://api.binance.com/")
    assert "kraken" in calls[1]
    assert len(calls) == 2

    # Next fetch tries the preferred provider (kraken) first; binance is
    # still in its 15s cooldown and is not retried.
    calls.clear()
    with mock.patch.object(engine.session, "get", side_effect=dispatch):
        q2 = engine.fetch_realtime_eth_quote()
    assert q2.source == "Kraken Live"
    assert "kraken" in calls[0]
    assert len(calls) == 1

    # All three down -> offline sentinel, and no new request is made
    # while every provider is inside its 15s cooldown.
    engine2 = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    with mock.patch.object(engine2.session, "get", side_effect=Exception("all down")) as mocked:
        first = engine2.fetch_realtime_eth_quote()
        assert first.is_offline is True
        assert first.price == Decimal("0.00")
        assert first.source == "Market Offline (No Feed)"
        assert mocked.call_count == 3  # binance, kraken, coinbase: once each
        second = engine2.fetch_realtime_eth_quote()
        assert second.is_offline is True
        assert mocked.call_count == 3

# =========================================================== P1-A
# Live logic: forced short brackets, stagnation exit, short trailing
# ratchet, bootstrap SQLite freshness (needs the code fix), start_live
# success path, and the MTF counter-trend gate.
# ===========================================================


def test_ensure_active_live_positions_short_brackets():
    """P1 §2.3: with every condition pointing down, _ensure_active_live_
    positions opens a SHORT bracket for all five strategies: SL above the
    entry, TP below it, R multiple equal to the long version's. Aggressive
    and Trailing Guard are uncapped runners (TP None on both sides), so
    their stop distance from the call price is asserted instead."""
    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    engine.broker.on_tick(price=Decimal("3500.00"), timestamp=1700000000.0)
    # Downtrend for Agg/Trail, RSI > 52 for Cons short, price below
    # the ORB midpoint (3550) and below the session mean (3510).
    engine.live_ema_fast = Decimal("3490.00")
    engine.live_ema_slow = Decimal("3500.00")
    engine.live_rsi = Decimal("60.00")
    engine.live_atr = Decimal("20.00")
    engine.live_orb_high = Decimal("3600.00")
    engine.live_orb_low = Decimal("3500.00")
    # Audit 3.3: the mean must sit inside Session Mean's pullback zone
    # (|price-mean| <= 0.85xATR = 17) or it refuses entry; 3510 is 10
    # away, still above the price, so the SHORT deploys as intended.
    engine.live_typical_mean = Decimal("3510.00")
    engine.htf_bias = "NEUTRAL"  # MTF must not veto the SELL side here
    price = Decimal("3500.00")
    engine._ensure_active_live_positions(price, 1700000000.0)

    # (pid, expected R from the 3500.00 call price, or None if uncapped)
    # Audit 3.3: startup brackets are the genome brackets now, so the
    # R multiples are the genome's -- not the old hardcoded caps'.
    expected_r = {
        "comp_cons": Decimal("1.8"),   # (3500-3437)/(3535-3500) = 63/35
        "comp_orb": Decimal("2.0"),    # (3500-3400)/(3550-3500) = 100/50
        "comp_vwap": Decimal("2.2"),   # (3500-3456)/(3520-3500) = 44/20
    }
    for c in engine.competitors:
        pid = c.portfolio_id
        p = c.portfolio
        assert p.position_side.value == "SHORT", pid
        assert p.position_qty > Decimal("0"), pid
        stop = engine.broker.active_stops[pid]
        assert stop.side.value == "BUY", pid  # a short stop buys to cover
        assert stop.price > p.avg_entry_price, pid
        target = engine.broker.active_targets.get(pid)
        if pid in expected_r:
            assert target is not None, pid
            assert target.price < p.avg_entry_price, pid
            r = (price - target.price) / (stop.price - price)
            assert r == expected_r[pid], f"{pid}: R {r} != {expected_r[pid]}"
        else:
            # Uncapped runners: no target on either side; the stop
            # distance from the call price equals the long version's.
            assert target is None, pid
            assert stop.price - price == (
                Decimal("122.50") if pid == "comp_agg"  # 3.5% of 3500
                else Decimal("52.50")                    # 1.5% of 3500 (genome)
            ), pid


def test_stagnation_exit_closes_after_40m():
    """P1 §2.2 (:1010-1019): a short held 40 minutes with no TP trigger
    and < 0.10% gain is force-closed with STAGNATION_EXIT and a 60s
    cooldown (the same timestamp cannot re-enter, the cooldown blocks it)."""
    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    ts = 1700001000.0
    _open_short(engine, "comp_cons", ts=ts)
    entry = engine.comp_b.portfolio.avg_entry_price
    assert entry == Decimal("3499.47")
    engine.position_entry_ts["comp_cons"] = ts - 2400.0  # held 40 minutes
    engine.live_atr = Decimal("20.00")
    engine.live_rsi = Decimal("50.00")
    engine.live_ema_fast = Decimal("3500.00")
    engine.live_ema_slow = Decimal("3490.00")
    engine.broker.current_price = entry
    # Price == entry (0% gain) and prev == price (vel 0): the only exit
    # that can fire for comp_cons here is the stagnation timeout.
    engine._evaluate_live_strategies(entry, entry, ts)

    assert engine.comp_b.portfolio.position_qty == Decimal("0.0000")
    assert engine.comp_b.portfolio.position_side.value == "FLAT"
    assert engine.strategy_cooldown["comp_cons"] == ts + 60.0
    assert "comp_cons" not in engine.position_entry_ts
    assert any(e.get("tag") == "STAGNATION_EXIT" for e in engine.live_logs)


def test_trailing_guard_short_ratchet_moves_stop_down():
    """P1 §2.2 (:1168,1171-1180): a short whose price makes a new low
    past the 2.0% trailing trigger updates the trough, arms trailing,
    and lowers the stop to trough x (1 + trailing_distance_pct)."""
    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    ts = 1700001000.0
    _open_short(engine, "comp_trail", ts=ts)
    entry = engine.comp_d.portfolio.avg_entry_price
    assert entry == Decimal("3499.47")
    price = (entry * Decimal("0.975")).quantize(Decimal("0.01"))  # -2.5%
    assert price == Decimal("3411.98")
    engine.live_atr = Decimal("20.00")
    engine.live_rsi = Decimal("50.00")
    engine.live_ema_fast = Decimal("3500.00")
    engine.live_ema_slow = Decimal("3490.00")
    engine.broker.current_price = price
    engine._evaluate_live_strategies(price, entry, ts)

    trail = engine.comp_d
    assert trail.portfolio.position_side.value == "SHORT"
    assert trail.portfolio.position_qty == Decimal("0.5000")
    assert trail.lowest_price_since_entry == price
    assert trail.trailing_active is True
    stop = engine.broker.active_stops["comp_trail"]
    assert stop.side.value == "BUY"
    assert stop.price == (price * (Decimal("1") + trail.genome.trailing_distance_pct)).quantize(Decimal("0.01"))
    assert stop.price == Decimal("3432.45")
    assert stop.price < Decimal("3552.50")  # the entry stop moved down
    assert any(e.get("tag") == "TRAIL_RATCHET" for e in engine.live_logs)


def _cache_rows(now, last_age_sec, n=120, omit_volume_every=0):
    """SQLite candle rows ascending in time, last bar `last_age_sec` old.

    Prices rise 3500+i, high/low +/-5, volume 15.0 except every
    `omit_volume_every`-th row, which omits the volume key entirely.
    """
    rows = []
    last_t = now - last_age_sec
    for i in range(n):
        price = 3500.0 + i
        row = {"t": last_t - (n - 1 - i) * 60.0, "o": price,
               "h": price + 5.0, "l": price - 5.0, "c": price}
        if not (omit_volume_every and i % omit_volume_every == 0):
            row["v"] = 15.0
        rows.append(row)
    return rows


def test_bootstrap_rejects_stale_sqlite_candles(monkeypatch):
    """P1 §2.6: a SQLite cache whose newest bar is 3600s old must not
    become the opening bars -- not even through the fallback branch that
    used to hydrate the cache unconditionally when the live feed failed.
    The engine starts with an empty chart and waits for live quotes."""
    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    monkeypatch.setattr(engine.storage, "load_latest_candles",
                        lambda limit=120: _cache_rows(time.time(), 3600))
    monkeypatch.setattr("src.data.live_engine.ETHFeed.fetch_historical_bars",
                        staticmethod(lambda *a, **k: []))
    engine.bootstrap_intraday_session()

    assert engine.is_bootstrapped is True
    assert engine.candles == []
    assert engine.live_orb_high == Decimal("0.00")
    assert engine.live_typical_mean == Decimal("0.00")


def test_bootstrap_hydrates_fresh_sqlite_candles(monkeypatch):
    """P1 §2.6: a fresh SQLite cache (newest bar 60s old) hydrates the
    chart, and the missing-field fill rules are pinned: a bar without a
    volume key is built with volume 15.0, rsi 50.00, atr 12.00 (the
    CandleBar construction is spied on, since volume is not stored on
    the engine's own candle dicts)."""
    from src.data.eth_feed import CandleBar as _RealBar

    seen = []

    class _SpyBar:
        def __init__(self, **kwargs):
            seen.append(kwargs)
            self._real = _RealBar(**kwargs)

        def __getattr__(self, name):
            return getattr(self._real, name)

    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    monkeypatch.setattr("src.data.live_engine.CandleBar", _SpyBar)
    monkeypatch.setattr(engine.storage, "load_latest_candles",
                        lambda limit=120: _cache_rows(time.time(), 60, omit_volume_every=10))
    # The 1m warmup feed must not be re-fetched on a fresh cache hit (its
    # exception would be swallowed by bootstrap's try/except, so a flag
    # -- not a raise -- is what proves it stayed untouched). Audit 2.3
    # adds one legitimate fetch: real 1h history to seed the MTF gate,
    # which the 1m-only cache cannot supply -- so the only fetch call is
    # the 1h seed.
    fetch_calls = []

    def _no_fetch(*a, **k):
        fetch_calls.append(k.get("interval"))
        return []

    monkeypatch.setattr("src.data.live_engine.ETHFeed.fetch_historical_bars",
                        staticmethod(_no_fetch))
    engine.bootstrap_intraday_session()

    assert fetch_calls == ["1h"]
    assert engine.is_bootstrapped is True
    assert len(engine.candles) == 120
    assert len(seen) == 120
    # Every 10th bar omitted its volume key; all 120 were still built
    # with the documented fills.
    for i, kwargs in enumerate(seen):
        assert kwargs["volume"] == Decimal("15.0"), i
        assert kwargs["rsi"] == Decimal("50.00"), i
        assert kwargs["atr"] == Decimal("12.00"), i
    # Indicators come from the last bar's fills; ORB / mean from the bars.
    assert engine.live_rsi == Decimal("50.00")
    assert engine.live_atr == Decimal("12.00")
    assert engine.live_orb_high == Decimal("3519.00")  # max high, first 15 bars
    assert engine.live_orb_low == Decimal("3495.00")   # min low, first 15 bars
    assert engine.live_typical_mean == Decimal("3559.50")  # mean of 3500..3619


def test_start_live_trading_success_path(monkeypatch):
    """P1 §2.8: after a successful bootstrap, start_live_trading()
    accepts, enables live orders, and records ARENA_REVEALED."""
    monkeypatch.setattr("src.data.live_engine.ETHFeed.fetch_historical_bars",
                        staticmethod(lambda *a, **k: _fixture_bars()))
    engine = LiveArenaEngine(initial_cash=Decimal("500000.00"), symbol="ETH/USD")
    assert engine.is_bootstrapped is False
    assert engine.live_orders_enabled is False

    engine.bootstrap_intraday_session()
    assert engine.is_bootstrapped is True
    assert engine.live_orders_enabled is False

    engine.latest_quote = _quote("3500.00")
    result = engine.start_live_trading()
    assert result == {"accepted": True, "reason": "Live trading active", "restored": False}
    assert engine.live_orders_enabled is True
    assert engine.live_trading_active is True
    assert any(e.get("tag") == "ARENA_REVEALED" for e in engine.live_logs)


def test_mtf_gate_blocks_counter_trend_entries():
    """P1 §2.8 (mtf_engine.py:91-95): the 1h bias vetoes entries that
    trade directly into higher-timeframe opposition, and lets everything
    through while the bias is undetermined (NEUTRAL / unknown)."""
    from src.arena.order import OrderSide
    from src.data.mtf_engine import MultiTimeframeEngine

    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))

    engine.htf_bias = "BEARISH"
    assert engine.is_entry_permitted_by_mtf(OrderSide.BUY) is False
    assert engine.is_entry_permitted_by_mtf(OrderSide.SELL) is True

    engine.htf_bias = "BULLISH"
    assert engine.is_entry_permitted_by_mtf(OrderSide.BUY) is True
    assert engine.is_entry_permitted_by_mtf(OrderSide.SELL) is False

    for undetermined in ("NEUTRAL", "UNKNOWN", ""):
        engine.htf_bias = undetermined
        assert engine.is_entry_permitted_by_mtf(OrderSide.BUY) is True
        assert engine.is_entry_permitted_by_mtf(OrderSide.SELL) is True

    # The engine-level gate is the same rule as the MTF engine itself.
    mtf = MultiTimeframeEngine()
    mtf.htf_bias = "BEARISH"
    assert mtf.is_entry_permitted(OrderSide.BUY) is False
    assert mtf.is_entry_permitted(OrderSide.SELL) is True
    mtf.htf_bias = "BULLISH"
    assert mtf.is_entry_permitted(OrderSide.BUY) is True
    assert mtf.is_entry_permitted(OrderSide.SELL) is False
    mtf.htf_bias = "NEUTRAL"
    assert mtf.is_entry_permitted(OrderSide.BUY) is True
    assert mtf.is_entry_permitted(OrderSide.SELL) is True

# =========================================================== P2-A
# next_evolve_sec honesty + toggle compensation + 60-tick integration.
# ===========================================================


def _drive_fixed(engine, prices, t0):
    """Drive ticks with fixed +1s timestamps (deterministic): the same
    path as _drive (broker tick -> forced opens on tick 1 -> live
    evaluation -> series point), but with no wall-clock dependence, so
    cooldowns / entries / TP fills are reproducible run to run."""
    prev = None
    for i, px in enumerate(prices):
        ts = t0 + float(i)
        p = Decimal(px)
        q = LiveQuote(
            price=p, bid=p - Decimal("0.05"), ask=p + Decimal("0.05"),
            high_24h=p + Decimal("40"), low_24h=p - Decimal("40"),
            volume_24h=Decimal("1000"), change_24h_pct=Decimal("1.25"),
            source="UnitTest", timestamp=ts,
        )
        engine.latest_quote = q
        engine.tick_count += 1
        engine.live_ema_fast = q.price
        engine.live_ema_slow = q.price - Decimal("1")
        engine.broker.on_tick(q.price, high=q.ask, low=q.bid, timestamp=ts, open_price=prev or q.price)
        if prev is None:
            engine._ensure_active_live_positions(q.price, ts)
        engine._evaluate_live_strategies(q.price, prev or q.price, ts)
        engine._record_series_point(q.price, ts)
        prev = q.price


def test_next_evolve_sec_counts_trades_not_only_hours():
    """P2-A: the view-model countdown counts closed trades, not only
    hours. Evolution fires on the earlier of the 6h cap and 30 closed
    trades, so after 29 genuine closing fills the countdown must be
    ~1/30 of the 6h cap (~720s), not ~21600s -- while the "latest"
    bound still reports the pure 6h countdown, labelled as such."""
    from src.arena.order import OrderSide, OrderTicket, OrderType

    engine = LiveArenaEngine(initial_cash=Decimal("3000.00"))
    engine.latest_quote = _quote("3500.00")
    now = time.time()
    engine.last_evolve_ts = now

    # Zero trades: the blended countdown equals the 6h "latest" bound.
    state0 = engine.get_ui_state()
    assert state0["closed_trades_since_evolve"] == 0
    assert state0["closed_trades_to_next_evolve"] == 30
    assert state0["next_evolve_sec"] == state0["next_evolve_sec_latest"]
    assert state0["next_evolve_sec"] > 21000

    # 29 genuine closing fills through the broker (same round-trip
    # shape as test_auto_evolve_fires_on_closed_trades).
    broker = engine.broker
    broker.on_tick(price=Decimal("3500.00"), timestamp=now)
    for _ in range(29):
        buy = OrderTicket("comp_cons", "ETH/USD", OrderSide.BUY, OrderType.MARKET, qty=Decimal("0.1"), timestamp=now)
        assert broker.submit_order(buy) is not None
        sell = OrderTicket("comp_cons", "ETH/USD", OrderSide.SELL, OrderType.MARKET, qty=Decimal("0.1"), timestamp=now)
        assert broker.submit_order(sell) is not None
    state = engine.get_ui_state()  # harvests fills -> counter is 29
    assert engine._closed_trades_since_evolve == 29
    assert state["closed_trades_since_evolve"] == 29
    assert state["closed_trades_to_next_evolve"] == 1
    # ~1/30 of the 6h cap: near 0 next to 21600, not the hours countdown.
    assert 0 < state["next_evolve_sec"] <= 900
    assert state["next_evolve_sec"] < state["next_evolve_sec_latest"] / 10
    # The "latest" bound is still the pure 6h countdown, labelled as such.
    assert 21000 < state["next_evolve_sec_latest"] <= 21600
    assert "\u6700\u665a" in state["next_evolve_sec_note"]
    assert "1 \u7b46\u5e73\u5009" in state["next_evolve_sec_note"]


def test_toggle_auto_evolve_reenable_compensates_disabled_time(monkeypatch):
    """P2 §2.8 (live_engine.py:1813-1823): disabling auto-evolve for a
    long stretch and re-enabling must push last_evolve_ts forward by
    the disabled span -- the disabled hours must not count toward the
    6h cap, or evolution would mis-fire the instant it is re-enabled."""
    engine = LiveArenaEngine(initial_cash=Decimal("3000.00"))
    engine.latest_quote = _quote("3500.00")
    clock = {"now": 1700000000.0}
    monkeypatch.setattr(time, "time", lambda: clock["now"])
    engine.last_evolve_ts = clock["now"]
    assert engine.auto_evolve_enabled is True
    assert engine._auto_evolve_due(now=clock["now"]) is False

    # Disable at T0; 7 hours pass while disabled.
    assert engine.toggle_auto_evolve() is False
    assert engine._auto_evolve_disabled_ts == clock["now"]
    clock["now"] += 7 * 3600

    # Re-enable: last_evolve_ts jumps forward by exactly the disabled span.
    assert engine.toggle_auto_evolve() is True
    assert engine._auto_evolve_disabled_ts is None
    assert engine.last_evolve_ts == 1700000000.0 + 7 * 3600
    # No immediate mis-trigger: only seconds have elapsed since the
    # compensated stamp (without compensation, 7h >= 6h would fire now).
    assert engine._auto_evolve_due(now=clock["now"]) is False
    assert engine._auto_evolve_reason(now=clock["now"]) is None
    # The 6h cap still fires 6h after the compensated stamp.
    assert engine._auto_evolve_reason(now=clock["now"] + 21601) == "time"


def test_live_tick_integration_fixed_price_series():
    """P2 §2.10: 60 fixed-price ticks (no real time) replace the old
    'run the loop 1s and hope' coverage: rise 3500 -> 3703 (+7/tick),
    then fall -> 3403 (-10/tick). Every strategy enters on tick 1.

    Audit 2.1 changed what closes them: the hardcoded +0.15%..+0.35%
    profit caps are gone, so positions close only at their genome
    brackets (via broker.on_tick), at a stop, or on a kept signal
    exit -- and a bracket close sets no cooldown in this harness
    (_drive_fixed drives on_tick directly; the real live loop sets
    60s on closing fills), so strategies re-enter when their entry
    condition holds again. Audit 3.3 changed what opens them: the
    startup brackets are the genome brackets now (Cons 3465/3563,
    ATR 3372.50/3712.50, ORB 3440/3620, Mean 3456.50/3595.70), and
    ORB needs a real range to enter, so the harness seeds one
    (3490/3390) -- without it ORB never deploys. Net over 60 ticks:
    22 fills, 9 closes (6x TAKE_PROFIT + 1x TRAILING_STOP + 2x
    STOP_LOSS). Cons closes once, via the cadence SCALP_TP at tick 7
    (gain 0.5xATR reached before the genome TP 3563), which sets the
    60s cooldown, so it cannot re-enter within the 60-tick series;
    ORB closes twice (TP at tick 18, then the re-entered long stops
    out at 3440 on the falling leg). Aggressive (uncapped TP, no
    reversal in this series) and ATR (bracket SL 3372.50 / TP 3712.50
    untouched by the 3403..3703 range) ride the whole series; the
    trailing guard re-enters SHORT on the falling leg; the closed-trade
    counter matches the closing fills; no evolution fires (9 < 30
    trades, far under the 6h cap)."""
    from collections import Counter

    engine = LiveArenaEngine(initial_cash=Decimal("500000.00"), symbol="ETH/USD")
    # Audit 3.3: ORB needs a real opening range to enter (startup and
    # cadence both route through evaluate_signal now); seed one so all
    # five deploy on tick 1 as this test intends.
    engine.live_orb_high = Decimal("3490.00")
    engine.live_orb_low = Decimal("3390.00")
    t0 = 1700000000.0
    prices = [f"{3500 + 7 * i:.2f}" for i in range(30)] + [f"{3703 - 10 * (i + 1):.2f}" for i in range(30)]
    assert len(prices) == 60
    _drive_fixed(engine, prices, t0)
    assert engine.tick_count == 60

    state = engine.get_ui_state()
    # Entries: 5 forced opens on tick 1 + re-entries after bracket
    # closes (vwap 5, orb 1, trail 1).
    assert len(engine.fill_records) == 21
    # Closes are bracket TPs / stops / the trailing stop, plus the
    # cadence SCALP_TP (cons, tick 7) -- none via the removed caps.
    by_pid = Counter(f.portfolio_id for f in engine.fill_records if getattr(f, "is_closing_fill", False))
    assert by_pid == {"comp_vwap": 5, "comp_cons": 1, "comp_orb": 2, "comp_trail": 1}
    reasons = Counter(f.reason.value for f in engine.fill_records if getattr(f, "is_closing_fill", False))
    assert reasons == {"TAKE_PROFIT": 6, "TRAILING_STOP": 1, "STOP_LOSS": 2}
    expected_closed = {
        "comp_agg": 0, "comp_cons": 1,
        "comp_trail": 1, "comp_orb": 2, "comp_vwap": 5,
    }
    for s in state["strategies"]:
        assert s["closed_trades"] == expected_closed[s["id"]], s["id"]
    # The closed-trade counter (evolution trigger input) matches the tape.
    assert engine._closed_trades_since_evolve == 9
    # Cooldown: only the cadence SCALP_TP close (cons, tick 7) sets
    # 60s in this harness; bracket closes set none here (the real live
    # loop sets 60s on on_tick closing fills), so the trailing guard's
    # bracket close leaves it free to re-enter SHORT on the falling leg.
    assert engine.strategy_cooldown["comp_cons"] == t0 + 67.0
    assert "comp_trail" not in engine.strategy_cooldown
    trail = next(s for s in state["strategies"] if s["id"] == "comp_trail")
    assert trail["in_position"] is True
    assert trail["position_side"] == "SHORT"
    # Aggressive (uncapped) rides the series;
    # Session Mean rides its last short; Conservative and ORB end flat.
    for s in state["strategies"]:
        if s["id"] == "comp_agg":
            assert s["in_position"] is True, s["id"]
            assert s["position_side"] == "LONG", s["id"]
        elif s["id"] in ("comp_vwap", "comp_trail"):
            assert s["in_position"] is True, s["id"]
            assert s["position_side"] == "SHORT", s["id"]
        else:
            assert s["in_position"] is False, s["id"]
    # No evolution: 9 < 30 closed trades and minutes under the 6h cap.
    assert state["generation"] == 1
    assert engine.evolution_events == []
    assert engine._auto_evolve_due(now=t0 + 60.0) is False
    # The honest countdown already reflects the 9 closed trades.
    assert 0 < state["next_evolve_sec"] < state["next_evolve_sec_latest"]
    assert state["closed_trades_since_evolve"] == 9
    assert state["closed_trades_to_next_evolve"] == 21
