"""Audit 2.8: Sharpe/Sortino cache must not freeze between fills forever.

The fill-driven cache key is right for performance, but without a TTL
the served metrics freeze at the last fill while the equity history
keeps moving. A 60s TTL bounds the staleness: after the TTL, the next
read recomputes (at most once per TTL per portfolio when read).
"""
from __future__ import annotations

from decimal import Decimal

from src.arena.leaderboard import Leaderboard
from src.arena.portfolio import Portfolio

_MIXED = [(0, 100000), (1, 101000), (2, 99000), (3, 102000), (4, 98000), (5, 103000)]


def _counting_periods(monkeypatch):
    calls = {"n": 0}
    orig = Leaderboard._estimate_periods_per_year

    def counting(history):
        calls["n"] += 1
        return orig(history)

    monkeypatch.setattr(Leaderboard, "_estimate_periods_per_year", counting)
    return calls


def test_metrics_recompute_after_ttl(monkeypatch):
    p = Portfolio("p_ttl", "TTL Tester", initial_cash=Decimal("100000.00"))
    p.equity_history = [(float(t), Decimal(str(v))) for t, v in _MIXED]
    calls = _counting_periods(monkeypatch)
    clock = {"t": 1000.0}
    monkeypatch.setattr(
        "src.arena.leaderboard.time.monotonic", lambda: clock["t"]
    )
    first = Leaderboard.calculate_sharpe_and_sortino(p)
    assert calls["n"] == 1
    # Ticks arrive, no fills: within the TTL the cached value is served.
    p.update_market_price(Decimal("103500.00"), timestamp=6.0)
    p.update_market_price(Decimal("103200.00"), timestamp=7.0)
    second = Leaderboard.calculate_sharpe_and_sortino(p)
    assert second == first
    assert calls["n"] == 1
    # Past the TTL the next read recomputes against the moved history.
    clock["t"] = 1000.0 + Leaderboard.METRICS_CACHE_TTL_SEC + 1.0
    third = Leaderboard.calculate_sharpe_and_sortino(p)
    assert calls["n"] == 2
    assert third != first
