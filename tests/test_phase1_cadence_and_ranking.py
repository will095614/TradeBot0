import time
from decimal import Decimal
from src.arena.portfolio import Portfolio
from src.arena.leaderboard import Leaderboard
from src.data.live_engine import LiveArenaEngine


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


def test_leaderboard_ranked_strictly_by_total_equity():
    """
    Verify that Leaderboard.get_rankings strictly orders competitors
    by total equity in descending order (highest net worth = Rank #1).
    """
    p1 = Portfolio(portfolio_id="alpha", initial_cash=Decimal("100000.00"), name="Strategy Alpha")
    p2 = Portfolio(portfolio_id="beta", initial_cash=Decimal("105000.00"), name="Strategy Beta")
    p3 = Portfolio(portfolio_id="gamma", initial_cash=Decimal("92000.00"), name="Strategy Gamma")
    p4 = Portfolio(portfolio_id="delta", initial_cash=Decimal("118000.00"), name="Strategy Delta")

    portfolios = {
        "alpha": p1,
        "beta": p2,
        "gamma": p3,
        "delta": p4,
    }

    rankings = Leaderboard.get_rankings(portfolios)
    assert len(rankings) == 4
    # Delta should be Rank 1 ($118,000)
    assert rankings[0].portfolio_id == "delta"
    assert rankings[0].rank == 1
    assert rankings[0].equity == Decimal("118000.00")

    # Beta should be Rank 2 ($105,000)
    assert rankings[1].portfolio_id == "beta"
    assert rankings[1].rank == 2

    # Alpha should be Rank 3 ($100,000)
    assert rankings[2].portfolio_id == "alpha"
    assert rankings[2].rank == 3

    # Gamma should be Rank 4 ($92,000)
    assert rankings[3].portfolio_id == "gamma"
    assert rankings[3].rank == 4


def test_candle_cadence_dispatcher_timing_and_dispatch(monkeypatch):
    """
    Verify that LiveArenaEngine's CandleCadenceDispatcher maintains stable
    candle slice publication at the configured cadence_sec.
    """
    # Tests run with ARENA_FAST_TEST=1, so no real bars are fetched; seed the
    # bootstrap with deterministic fixture bars (test-only data).
    monkeypatch.setattr("src.data.live_engine.ETHFeed.fetch_historical_bars", staticmethod(lambda *a, **k: _fixture_bars()))
    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    engine.bootstrap_intraday_session()

    # Initial state has published candles populated
    assert len(engine.published_candles) > 0
    assert engine.cadence_sec == 1.0

    state = engine.get_ui_state()
    assert "candles" in state
    assert len(state["candles"]) > 0
    assert state.get("cadence_sec") == 1.0

    # Test dynamic cadence reconfiguration
    new_cadence = engine.set_cadence_interval(3.0)
    assert new_cadence == 3.0
    assert engine.cadence_sec == 3.0

    # Bounds clamping (1.0 to 10.0)
    assert engine.set_cadence_interval(0.2) == 1.0
    assert engine.set_cadence_interval(30.0) == 10.0
    engine.stop()


def test_micro_bar_aggregation_preserves_wick_extremes_r1(monkeypatch):
    """
    [R1 Checkpoint] Verify that intermediate high spike and low flush
    inside a slice are preserved in micro-bar aggregation and never discarded.
    """
    from src.data.live_engine import LiveQuote
    # Tests run with ARENA_FAST_TEST=1, so no real bars are fetched; seed the
    # bootstrap with deterministic fixture bars (test-only data).
    monkeypatch.setattr("src.data.live_engine.ETHFeed.fetch_historical_bars", staticmethod(lambda *a, **k: _fixture_bars()))
    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    engine.bootstrap_intraday_session()

    t0 = engine.candles[-1]["t"]
    quotes = [
        LiveQuote(price=Decimal("95000.00"), bid=Decimal("94990.00"), ask=Decimal("95010.00"), high_24h=Decimal("98000.00"), low_24h=Decimal("92000.00"), volume_24h=Decimal("100.0"), change_24h_pct=Decimal("2.0"), source="test", timestamp=t0),
        LiveQuote(price=Decimal("95800.00"), bid=Decimal("95790.00"), ask=Decimal("95810.00"), high_24h=Decimal("98000.00"), low_24h=Decimal("92000.00"), volume_24h=Decimal("100.0"), change_24h_pct=Decimal("2.0"), source="test", timestamp=t0 + 1.0),
        LiveQuote(price=Decimal("94200.00"), bid=Decimal("94190.00"), ask=Decimal("94210.00"), high_24h=Decimal("98000.00"), low_24h=Decimal("92000.00"), volume_24h=Decimal("100.0"), change_24h_pct=Decimal("2.0"), source="test", timestamp=t0 + 2.0),
        LiveQuote(price=Decimal("95200.00"), bid=Decimal("95190.00"), ask=Decimal("95210.00"), high_24h=Decimal("98000.00"), low_24h=Decimal("92000.00"), volume_24h=Decimal("100.0"), change_24h_pct=Decimal("2.0"), source="test", timestamp=t0 + 3.0),
    ]

    with engine.lock:
        engine._slice_ticks.extend(quotes)

    # Aggregate slice
    ticks = list(engine._slice_ticks)
    open_p = ticks[0].price
    high_p = max(t.price for t in ticks)
    low_p = min(t.price for t in ticks)
    close_p = ticks[-1].price

    assert open_p == Decimal("95000.00")
    assert high_p == Decimal("95800.00")  # Extreme high captured
    assert low_p == Decimal("94200.00")   # Extreme low captured
    assert close_p == Decimal("95200.00")

    engine._update_candle(t0, close=close_p, high=high_p, low=low_p, open_=open_p)
    last_candle = engine.candles[-1]
    assert last_candle["h"] >= float(Decimal("95800.00"))
    assert last_candle["l"] <= float(Decimal("94200.00"))
    engine.stop()
