"""P0-B / F1: Sortino is never invented.

When a portfolio has no downside returns at all, the downside deviation
does not exist -- the old code returned abs(sharpe) * 1.5, a multiplier
with no source. The metric now returns None (undefined); fitness counts
an undefined Sortino as 0.
"""
import math
from decimal import Decimal

from src.arena.leaderboard import Leaderboard
from src.arena.portfolio import Portfolio


def _portfolio_with_history(points):
    p = Portfolio("p_sort", "Sortino Tester", initial_cash=Decimal("100000.00"))
    p.equity_history = [(float(t), Decimal(str(v))) for t, v in points]
    return p


def test_sortino_no_downside_returns_is_not_invented():
    """F1: an all-winning history has no downside deviation, so Sortino
    is undefined (None) -- never abs(sharpe) * 1.5."""
    p = _portfolio_with_history(
        [(0, 100000), (1, 101000), (2, 102500), (3, 104000), (4, 105500)]
    )
    sharpe, sortino = Leaderboard.calculate_sharpe_and_sortino(p)
    assert sharpe > 0
    assert sortino is None
    assert sortino != round(abs(sharpe) * 1.5, 2)
    # Fitness treats the undefined Sortino exactly like a 0 contribution.
    assert Leaderboard.calculate_fitness(5.0, 1.0, sharpe, sortino, False) == (
        Leaderboard.calculate_fitness(5.0, 1.0, sharpe, 0.0, False)
    )


def test_sortino_with_losses_is_real_downside_deviation():
    """F1 guard: with real losses, Sortino is still the genuine
    downside-deviation value -- the fix must not touch that branch."""
    points = [(0, 100000), (1, 101000), (2, 99000), (3, 102000), (4, 98000), (5, 103000)]
    p = _portfolio_with_history(points)
    sharpe, sortino = Leaderboard.calculate_sharpe_and_sortino(p)
    assert sortino is not None

    returns = [
        (float(points[i][1]) - float(points[i - 1][1])) / float(points[i - 1][1])
        for i in range(1, len(points))
    ]
    mean_ret = sum(returns) / len(returns)
    downside_dev = math.sqrt(sum(r ** 2 for r in returns if r < 0.0) / len(returns))
    # Timestamps are 1s apart (< 60s), so periods_per_year is the 35040
    # 15-minute-bar annualization, same as the implementation uses.
    expected = max(-25.0, min(25.0, round((mean_ret / downside_dev) * math.sqrt(35040.0), 2)))
    assert sortino == expected
    assert sharpe > 0  # sanity: the shared Sharpe path is untouched too


def test_rankings_handles_undefined_sortino():
    """F1: get_rankings survives an all-winning portfolio -- fitness gets
    the None (0 contribution) and the table shows the 0.0 fallback."""
    p = _portfolio_with_history(
        [(0, 100000), (1, 101000), (2, 102500), (3, 104000), (4, 105500)]
    )
    rankings = Leaderboard.get_rankings({"p_sort": p})
    assert len(rankings) == 1
    assert rankings[0].sortino_ratio == 0.0
    sharpe, _ = Leaderboard.calculate_sharpe_and_sortino(p)
    assert rankings[0].fitness_score == Leaderboard.calculate_fitness(
        float(p.roi_pct), float(p.max_drawdown_pct), sharpe, 0.0,
        p.is_circuit_breaker_tripped,
        closed_trades=0,
    )

# =========================================================== P2-A
# A3: the 35040 annualization is a named constant with a documented
# 365-day x 96 15-minute-bar convention (number unchanged).
# ===========================================================


def test_annualization_period_is_named_constant_with_documented_convention():
    """A3: the annualization period is the named constant
    PERIODS_PER_YEAR_15MIN_BARS == 35040 (365 days x 96 15-minute bars),
    the sub-60s branch returns exactly that constant, and the convention
    is documented where the constant lives. The number is unchanged --
    this test pins the labelling, not a new value."""
    import inspect

    import src.arena.leaderboard as lb_mod
    from src.arena.leaderboard import Leaderboard, PERIODS_PER_YEAR_15MIN_BARS

    assert PERIODS_PER_YEAR_15MIN_BARS == 35040.0
    # Too few points: the default is the named constant.
    assert Leaderboard._estimate_periods_per_year([]) == PERIODS_PER_YEAR_15MIN_BARS
    assert Leaderboard._estimate_periods_per_year(
        [(0.0, Decimal("100000"))]
    ) == PERIODS_PER_YEAR_15MIN_BARS
    # Sub-60s sampling (live ticks): still the 15-minute-bar convention.
    p = _portfolio_with_history(
        [(0, 100000), (1, 101000), (2, 99000), (3, 102000), (4, 103000)]
    )
    assert Leaderboard._estimate_periods_per_year(p.equity_history) == PERIODS_PER_YEAR_15MIN_BARS
    # The estimator really uses the named constant, not a bare literal.
    fn_src = inspect.getsource(Leaderboard._estimate_periods_per_year)
    assert "PERIODS_PER_YEAR_15MIN_BARS" in fn_src
    assert "35040" not in fn_src
    # The convention is documented at the constant: 365 days x 96
    # 15-minute bars per day.
    mod_src = inspect.getsource(lb_mod)
    assert "365" in mod_src and "96" in mod_src and "15-minute" in mod_src
