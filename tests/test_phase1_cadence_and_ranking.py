import time
from decimal import Decimal
from src.arena.portfolio import Portfolio
from src.arena.leaderboard import Leaderboard
from src.data.live_engine import LiveArenaEngine


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


def test_candle_cadence_dispatcher_timing_and_dispatch():
    """
    Verify that LiveArenaEngine's CandleCadenceDispatcher maintains stable
    candle slice publication at the configured cadence_sec.
    """
    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    engine.bootstrap_intraday_session()

    # Initial state has published candles populated
    assert len(engine.published_candles) > 0
    assert engine.cadence_sec == 5.0

    state = engine.get_ui_state()
    assert "candles" in state
    assert len(state["candles"]) > 0
    assert state.get("cadence_sec") == 5.0

    # Test dynamic cadence reconfiguration
    new_cadence = engine.set_cadence_interval(3.0)
    assert new_cadence == 3.0
    assert engine.cadence_sec == 3.0

    # Bounds clamping (1.0 to 10.0)
    assert engine.set_cadence_interval(0.2) == 1.0
    assert engine.set_cadence_interval(30.0) == 10.0
