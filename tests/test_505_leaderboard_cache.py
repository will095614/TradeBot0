"""Audit §5.5: leaderboard metrics must be cached across ticks.

calculate_sharpe_and_sortino keyed its cache on the latest equity
value, which moves on every tick, so the cache never hit and 6 x
up-to-2000-point loops ran every second. The key is now fill-driven
(total_fills, closed_trades_count, equity-history version): ticks
between fills hit the cache, and any fill, reset, or wholesale history
replacement (restore) invalidates it.
"""
from __future__ import annotations

from decimal import Decimal

from src.arena.leaderboard import Leaderboard
from src.arena.order import ExecutionReason, FillEvent, OrderSide
from src.arena.portfolio import Portfolio


def _portfolio_with_history(points):
    p = Portfolio("p_cache", "Cache Tester", initial_cash=Decimal("100000.00"))
    p.equity_history = [(float(t), Decimal(str(v))) for t, v in points]
    return p


def _counting_periods(monkeypatch):
    calls = {"n": 0}
    orig = Leaderboard._estimate_periods_per_year

    def counting(history):
        calls["n"] += 1
        return orig(history)

    monkeypatch.setattr(Leaderboard, "_estimate_periods_per_year", counting)
    return calls


_MIXED = [(0, 100000), (1, 101000), (2, 99000), (3, 102000), (4, 98000), (5, 103000)]
_UPTREND = [(0, 100000), (1, 101000), (2, 102500), (3, 104000), (4, 105500)]
_DOWNTREND = [(0, 100000), (1, 99000), (2, 98000), (3, 97000), (4, 96000)]


def test_metrics_cached_across_ticks_with_no_fills(monkeypatch):
    p = _portfolio_with_history(_MIXED)
    calls = _counting_periods(monkeypatch)
    first = Leaderboard.calculate_sharpe_and_sortino(p)
    assert calls["n"] == 1
    # More ticks arrive (history grows, no fills): the metrics must be
    # identical and no recompute may happen.
    p.update_market_price(Decimal("103500.00"), timestamp=6.0)
    p.update_market_price(Decimal("103200.00"), timestamp=7.0)
    second = Leaderboard.calculate_sharpe_and_sortino(p)
    assert second == first
    assert calls["n"] == 1


def test_fill_invalidates_cache(monkeypatch):
    p = _portfolio_with_history(_MIXED)
    calls = _counting_periods(monkeypatch)
    Leaderboard.calculate_sharpe_and_sortino(p)
    assert calls["n"] == 1
    # A real fill lands through apply_fill: the next call must recompute.
    fill = FillEvent(
        order_id="o1",
        portfolio_id="p_cache",
        symbol="ETH/USD",
        side=OrderSide.BUY,
        qty=Decimal("0.01"),
        price=Decimal("3500.00"),
        fee=Decimal("0.10"),
        timestamp=8.0,
        reason=ExecutionReason.SIGNAL,
    )
    p.apply_fill(fill)
    assert p.total_fills == 1
    Leaderboard.calculate_sharpe_and_sortino(p)
    assert calls["n"] == 2


def test_reset_invalidates_cache(monkeypatch):
    """The reset collision: after reset() the counters are 0 again, so
    without a history-version in the key the pre-reset metrics would be
    served for a completely different history."""
    p = _portfolio_with_history(_UPTREND)
    calls = _counting_periods(monkeypatch)
    first = Leaderboard.calculate_sharpe_and_sortino(p)
    assert first[0] > 0
    assert calls["n"] == 1
    p.reset()
    p.equity_history = [(float(t), Decimal(str(v))) for t, v in _DOWNTREND]
    second = Leaderboard.calculate_sharpe_and_sortino(p)
    assert calls["n"] == 2
    assert second[0] < 0
    assert second != first


def test_replace_equity_history_invalidates_cache(monkeypatch):
    """Wholesale history replacement (the restore path) must invalidate,
    even though no fill happened and the counters are unchanged."""
    p = _portfolio_with_history(_UPTREND)
    calls = _counting_periods(monkeypatch)
    first = Leaderboard.calculate_sharpe_and_sortino(p)
    assert first[0] > 0
    assert calls["n"] == 1
    p.replace_equity_history([(float(t), Decimal(str(v))) for t, v in _DOWNTREND])
    second = Leaderboard.calculate_sharpe_and_sortino(p)
    assert calls["n"] == 2
    assert second[0] < 0
    assert second != first


def test_risk_free_rate_change_invalidates_cache(monkeypatch):
    p = _portfolio_with_history(_MIXED)
    calls = _counting_periods(monkeypatch)
    Leaderboard.calculate_sharpe_and_sortino(p)
    Leaderboard.calculate_sharpe_and_sortino(p, risk_free_rate=0.05)
    assert calls["n"] == 2
    # Same rate again: cached.
    Leaderboard.calculate_sharpe_and_sortino(p, risk_free_rate=0.05)
    assert calls["n"] == 2
