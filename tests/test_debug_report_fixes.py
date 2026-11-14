import os
from decimal import Decimal
import pytest

from src.arena.portfolio import Portfolio, PositionSide
from src.arena.broker_sim import BrokerSim
from src.data.live_engine import LiveArenaEngine, LiveQuote
from src.gui.dashboard import ArenaDashboard


def test_portfolio_reset_clears_all_metrics():
    """Verify Finding 3: Portfolio.reset() completely resets drawdowns, fees, history, and breaker."""
    p = Portfolio(portfolio_id="test", name="Test", initial_cash=Decimal("100000.00"))
    p.cash = Decimal("40000.00")
    p.position_qty = Decimal("15.0")
    p.position_side = PositionSide.LONG
    p.avg_entry_price = Decimal("2700.00")
    p.margin_locked = Decimal("60000.00")
    p.open_position_entry_fee = Decimal("25.00")
    p.realized_pnl = Decimal("1500.00")
    p.total_fees_paid = Decimal("120.00")
    p.win_count = 3
    p.loss_count = 2
    p.max_drawdown_pct = Decimal("12.50")
    p.is_circuit_breaker_tripped = True

    # Test reset
    p.reset(Decimal("100000.00"))

    assert p.cash == Decimal("100000.00")
    assert p.position_qty == Decimal("0.0000")
    assert p.position_side == PositionSide.FLAT
    assert p.margin_locked == Decimal("0.00")
    assert p.open_position_entry_fee == Decimal("0.00")
    assert p.realized_pnl == Decimal("0.00")
    assert p.total_fees_paid == Decimal("0.00")
    assert p.win_count == 0
    assert p.loss_count == 0
    assert p.max_drawdown_pct == Decimal("0.00")
    assert p.is_circuit_breaker_tripped is False

    # Also test the backward-compatible max_drawdown setter
    p.max_drawdown = Decimal("5.50")
    assert p.max_drawdown_pct == Decimal("5.50")
    assert p.max_drawdown == Decimal("5.50")


def test_session_save_and_restore_with_locked_margin(tmp_path):
    """Verify Finding 1 & 6: Session state saves and restores locked margin and position state."""
    os.environ["ARENA_FAST_TEST"] = "1"
    engine = LiveArenaEngine(symbol="ETH/USD", initial_cash=Decimal("100000.00"))
    comp = engine.competitors[0]

    # Simulate an open leveraged position
    comp.portfolio.cash = Decimal("30000.00")
    comp.portfolio.margin_locked = Decimal("70000.00")
    comp.portfolio.position_qty = Decimal("25.0")
    comp.portfolio.position_side = PositionSide.LONG
    comp.portfolio.avg_entry_price = Decimal("2800.00")
    comp.portfolio.open_position_entry_fee = Decimal("35.00")
    comp.portfolio.current_market_price = Decimal("2800.00")
    comp.portfolio.max_drawdown_pct = Decimal("3.25")
    comp.portfolio.is_circuit_breaker_tripped = False
    original_equity = comp.portfolio.total_equity

    assert original_equity == Decimal("100000.00")

    # Save
    save_ok = engine.save_session_state()
    assert save_ok is True

    # Create fresh engine and restore
    engine2 = LiveArenaEngine(symbol="ETH/USD", initial_cash=Decimal("100000.00"))
    restore_ok = engine2.restore_session_state()
    assert restore_ok is True

    comp2 = engine2.competitors[0]
    comp2.portfolio.current_market_price = Decimal("2800.00")

    assert comp2.portfolio.cash == Decimal("30000.00")
    assert comp2.portfolio.margin_locked == Decimal("70000.00")
    assert comp2.portfolio.position_qty == Decimal("25.0")
    assert comp2.portfolio.position_side == PositionSide.LONG
    assert comp2.portfolio.avg_entry_price == Decimal("2800.00")
    assert comp2.portfolio.open_position_entry_fee == Decimal("35.00")
    assert comp2.portfolio.max_drawdown_pct == Decimal("3.25")
    assert comp2.portfolio.total_equity == original_equity


def test_start_live_trading_does_not_wipe_restored_positions():
    """Verify Finding 1: start_live_trading does not flatten restored positions."""
    os.environ["ARENA_FAST_TEST"] = "1"
    engine = LiveArenaEngine(symbol="ETH/USD", initial_cash=Decimal("100000.00"))
    comp = engine.competitors[0]

    # Set up open position
    comp.portfolio.cash = Decimal("35000.00")
    comp.portfolio.margin_locked = Decimal("65000.00")
    comp.portfolio.position_qty = Decimal("20.0")
    comp.portfolio.position_side = PositionSide.LONG
    comp.portfolio.avg_entry_price = Decimal("2750.00")
    comp.portfolio.current_market_price = Decimal("2750.00")
    engine.is_bootstrapped = True

    # Call start_live_trading
    res = engine.start_live_trading()
    assert res.get("accepted") is True
    assert res.get("restored") is True

    # Positions should NOT be wiped
    assert comp.portfolio.position_qty == Decimal("20.0")
    assert comp.portfolio.margin_locked == Decimal("65000.00")
    assert comp.portfolio.cash == Decimal("35000.00")
    assert comp.portfolio.total_equity == Decimal("100000.00")


def test_start_live_trading_readiness_handshake():
    """Verify Finding 2: start_live_trading refuses to activate before bootstrap is complete."""
    os.environ["ARENA_FAST_TEST"] = "1"
    engine = LiveArenaEngine(symbol="ETH/USD", initial_cash=Decimal("100000.00"))
    engine.is_bootstrapped = False

    # Attempt to start live trading before bootstrap finishes
    res = engine.start_live_trading()
    assert res.get("accepted") is False
    assert "bootstrapping" in res.get("reason", "").lower()
    assert engine.live_orders_enabled is False


def test_get_ui_state_mutation_isolation():
    """Verify Finding 9: Callers cannot mutate live engine internal state via get_ui_state()."""
    os.environ["ARENA_FAST_TEST"] = "1"
    engine = LiveArenaEngine(symbol="ETH/USD", initial_cash=Decimal("100000.00"))
    engine.bootstrap_intraday_session()

    state = engine.get_ui_state()
    original_cash = state["strategies"][0]["cash"]

    # Mutate the returned dictionary
    state["strategies"][0]["cash"] = -999999.0
    state["generation"] = 9999

    # Re-fetch state
    fresh_state = engine.get_ui_state()
    assert fresh_state["strategies"][0]["cash"] == original_cash
    assert fresh_state["generation"] != 9999


def test_setup_status_has_no_gateway_auto_spawn_option():
    """Auto-launch is mandatory (offline mode removed): the
    gateway_auto_spawn option was deleted, so get_setup_status must not
    report it anymore."""
    dashboard = ArenaDashboard(initial_cash=Decimal("100000.00"))
    status = dashboard._bridge.get_setup_status()
    assert "gateway_auto_spawn" not in status


def _raise_no_network(*args, **kwargs):
    """Hermetic guard (P1): the live loop's background quote fetcher used
    to hit the real Binance REST endpoint. Fail fast instead, so the suite
    runs offline and deterministically; all three quote fetchers catch a
    broad Exception and fall back to the offline sentinel."""
    raise ConnectionError("hermetic test: no real network (mocked session.get)")


def test_cooperative_stop_event(monkeypatch):
    """Verify Finding 5: Engine cleanly stops worker loops via threading stop event."""
    os.environ["ARENA_FAST_TEST"] = "1"
    engine = LiveArenaEngine(symbol="ETH/USD", initial_cash=Decimal("100000.00"))
    # Hermetic (P1): the background quote fetcher must not hit real Binance.
    monkeypatch.setattr(engine.session, "get", _raise_no_network)
    assert not engine.running
    assert not engine._stop_event.is_set()

    engine.start_live_loop(interval_sec=1.0)
    assert engine.running
    assert not engine._stop_event.is_set()

    engine.stop_live_loop(timeout=2.0)
    assert not engine.running
    assert engine._stop_event.is_set()
    assert engine.worker_thread is None


def test_full_restore_bootstrap_start_integration():
    """Verify Verification §3.1: Restored positions survive bootstrap and activate cleanly."""
    os.environ["ARENA_FAST_TEST"] = "1"
    engine1 = LiveArenaEngine(symbol="ETH/USD", initial_cash=Decimal("100000.00"))
    comp1 = engine1.competitors[0]

    # Set up leveraged position
    comp1.portfolio.cash = Decimal("30000.00")
    comp1.portfolio.margin_locked = Decimal("70000.00")
    comp1.portfolio.position_qty = Decimal("25.0")
    comp1.portfolio.position_side = PositionSide.LONG
    comp1.portfolio.avg_entry_price = Decimal("2800.00")
    comp1.portfolio.open_position_entry_fee = Decimal("35.00")
    comp1.portfolio.current_market_price = Decimal("2800.00")
    comp1.portfolio.max_drawdown_pct = Decimal("2.50")
    engine1.live_orders_enabled = True

    ok = engine1.save_session_state()
    assert ok is True

    # Fresh engine: restore -> bootstrap -> start
    engine2 = LiveArenaEngine(symbol="ETH/USD", initial_cash=Decimal("100000.00"))
    restore_ok = engine2.restore_session_state()
    assert restore_ok is True
    assert engine2._has_restored_session is True

    # Real bootstrap should NOT purge restored portfolios
    engine2.bootstrap_intraday_session()
    assert engine2.is_bootstrapped is True

    comp2 = engine2.competitors[0]
    assert comp2.portfolio.position_qty == Decimal("25.0")
    assert comp2.portfolio.margin_locked == Decimal("70000.00")
    assert comp2.portfolio.cash == Decimal("30000.00")
    expected_unrealized = (comp2.portfolio.current_market_price - comp2.portfolio.avg_entry_price) * comp2.portfolio.position_qty
    assert comp2.portfolio.total_equity == (Decimal("30000.00") + Decimal("70000.00") + expected_unrealized).quantize(Decimal("0.01"))

    # Start live trading should recognise restored positions
    res = engine2.start_live_trading()
    assert res.get("accepted") is True
    assert res.get("restored") is True
    assert "restored positions" in res.get("reason", "").lower()
    assert comp2.portfolio.position_qty == Decimal("25.0")


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


def test_offline_start_does_not_execute_stale_candles(monkeypatch):
    """Verify Verification §3.2: start_live_trading with offline quote does not open orders from last candle."""
    os.environ["ARENA_FAST_TEST"] = "1"
    # Tests run with ARENA_FAST_TEST=1, so no real bars are fetched; seed the
    # bootstrap with deterministic fixture bars (test-only data).
    monkeypatch.setattr("src.data.live_engine.ETHFeed.fetch_historical_bars", staticmethod(lambda *a, **k: _fixture_bars()))
    engine = LiveArenaEngine(symbol="ETH/USD", initial_cash=Decimal("100000.00"))
    engine.bootstrap_intraday_session()
    assert engine.is_bootstrapped is True
    assert len(engine.candles) > 0

    # Offline quote
    engine.latest_quote = LiveQuote(
        price=Decimal("2650.00"),
        bid=Decimal("2649.50"),
        ask=Decimal("2650.50"),
        high_24h=Decimal("2700.00"),
        low_24h=Decimal("2600.00"),
        volume_24h=Decimal("1000.0"),
        change_24h_pct=Decimal("0.5"),
        source="mock",
        timestamp=1000.0,
        is_offline=True,
    )

    res = engine.start_live_trading()
    assert res.get("accepted") is True
    assert res.get("restored") is False
    assert "awaiting online quote" in res.get("reason", "").lower()

    # Zero fills opened from stale candle
    assert len(engine.fill_records) == 0
    assert all(c.portfolio.position_qty == Decimal("0.0000") for c in engine.competitors)


def test_trade_and_equity_history_persistence():
    """Verify Verification §3.4: Snapshot preserves trade history, equity history, fill records, and live_start_ts."""
    from src.arena.order import FillEvent, OrderSide, PositionSide, ExecutionReason
    os.environ["ARENA_FAST_TEST"] = "1"
    engine = LiveArenaEngine(symbol="ETH/USD", initial_cash=Decimal("100000.00"))
    comp = engine.competitors[0]

    test_fill = FillEvent(
        order_id="test_ord_1",
        portfolio_id=comp.portfolio_id,
        symbol="ETH/USD",
        side=OrderSide.BUY,
        qty=Decimal("5.0"),
        price=Decimal("2700.00"),
        fee=Decimal("6.75"),
        timestamp=1700000005.0,
        realized_pnl=Decimal("0.00"),
        reason=ExecutionReason.SIGNAL,
        fill_seq=1,
        entry_price=Decimal("2700.00"),
        position_side=PositionSide.LONG,
    )
    comp.portfolio.trade_history.append(test_fill)
    comp.portfolio.equity_history.append((1700000005.0, Decimal("100250.00")))
    engine.fill_records.append(test_fill)
    engine.live_start_ts = 1700000000.0

    save_ok = engine.save_session_state()
    assert save_ok is True

    engine2 = LiveArenaEngine(symbol="ETH/USD", initial_cash=Decimal("100000.00"))
    restore_ok = engine2.restore_session_state()
    assert restore_ok is True

    assert engine2.live_start_ts == 1700000000.0
    assert len(engine2.fill_records) == 1
    assert engine2.fill_records[0].order_id == "test_ord_1"
    assert engine2.fill_records[0].price == Decimal("2700.00")

    comp2 = engine2.competitors[0]
    assert len(comp2.portfolio.trade_history) == 1
    assert comp2.portfolio.trade_history[0].order_id == "test_ord_1"
    assert len(comp2.portfolio.equity_history) == 1
    assert comp2.portfolio.equity_history[0][1] == Decimal("100250.00")


def test_slow_bootstrap_stop_safety(monkeypatch):
    """Verify Verification §3.3: stop_live_loop and reset_engine handle worker lifecycle cleanly."""
    os.environ["ARENA_FAST_TEST"] = "1"
    engine = LiveArenaEngine(symbol="ETH/USD", initial_cash=Decimal("100000.00"))
    # Hermetic (P1): the background quote fetcher must not hit real Binance.
    monkeypatch.setattr(engine.session, "get", _raise_no_network)
    engine.start_live_loop(interval_sec=0.5)
    assert engine.running is True

    # Stop with short timeout
    engine.stop_live_loop(timeout=2.0)
    assert engine.running is False
    assert engine._stop_event.is_set()


def test_pause_feed_updates_ui_snapshot_immediately():
    """Verify that toggling pause immediately updates the lock-free UI state snapshot."""
    os.environ["ARENA_FAST_TEST"] = "1"
    engine = LiveArenaEngine(symbol="ETH/USD", initial_cash=Decimal("100000.00"))
    assert engine.paused is False
    assert engine.get_ui_state()["paused"] is False

    # Pause the feed
    engine.paused = True
    assert engine.paused is True
    # Verify snapshot immediately reflects paused without waiting for _live_loop cadence
    snap = engine.get_ui_state()
    assert snap["paused"] is True

    # Toggle pause via toggle_pause()
    res = engine.toggle_pause()
    assert res is False
    assert engine.paused is False
    assert engine.get_ui_state()["paused"] is False

    # Test auto evolve toggle snapshot publication
    orig_auto = engine.auto_evolve_enabled
    engine.toggle_auto_evolve()
    assert engine.auto_evolve_enabled != orig_auto
    assert engine.get_ui_state()["auto_evolve_enabled"] != orig_auto

    # Test set_auto_evolve_interval snapshot publication
    engine.set_auto_evolve_interval(14400)
    assert engine.get_ui_state()["auto_evolve_interval_sec"] == 14400


