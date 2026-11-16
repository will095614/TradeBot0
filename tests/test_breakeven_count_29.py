"""Audit 2.9: a breakeven close is a closed trade, but neither a win
nor a loss.

closed_trades_count must count it (so it agrees with total_fills about
completed trades), while the win rate stays wins / decided trades.
"""
from __future__ import annotations

from decimal import Decimal

from src.arena.leaderboard import Leaderboard
from src.arena.order import FillEvent, OrderSide
from src.arena.portfolio import Portfolio


def _breakeven_portfolio():
    # 0% fee scenario so the round trip PnL is exactly 0.00.
    p = Portfolio(
        portfolio_id="test_p",
        name="Test Portfolio",
        initial_cash=Decimal("1000.00"),
        maker_taker_fee_rate=Decimal("0.0"),
    )
    buy = FillEvent(
        "b1", "test_p", "ETH/USD", OrderSide.BUY,
        Decimal("1.0"), Decimal("500.00"), Decimal("0.0"), 100.0,
    )
    p.apply_fill(buy)
    sell = FillEvent(
        "s1", "test_p", "ETH/USD", OrderSide.SELL,
        Decimal("1.0"), Decimal("500.00"), Decimal("0.0"), 101.0,
    )
    p.apply_fill(sell)
    return p


def test_breakeven_close_counts_as_closed_trade():
    p = _breakeven_portfolio()
    assert p.win_count == 0
    assert p.loss_count == 0
    assert p.breakeven_count == 1
    assert p.closed_trades_count == 1
    assert p.total_fills == 2
    assert Leaderboard.calculate_win_rate(p) == Decimal("0.00")


def test_breakeven_close_keeps_win_rate_decided_only():
    p = _breakeven_portfolio()
    # One real win on top: the win rate is 1/1, not 1/2.
    buy2 = FillEvent(
        "b2", "test_p", "ETH/USD", OrderSide.BUY,
        Decimal("1.0"), Decimal("500.00"), Decimal("0.0"), 102.0,
    )
    p.apply_fill(buy2)
    sell2 = FillEvent(
        "s2", "test_p", "ETH/USD", OrderSide.SELL,
        Decimal("1.0"), Decimal("510.00"), Decimal("0.0"), 103.0,
    )
    p.apply_fill(sell2)
    assert p.win_count == 1
    assert p.breakeven_count == 1
    assert p.closed_trades_count == 2
    assert p.total_fills == 4
    assert Leaderboard.calculate_win_rate(p) == Decimal("100.00")


def test_breakeven_count_resets():
    p = _breakeven_portfolio()
    assert p.breakeven_count == 1
    p.reset()
    assert p.breakeven_count == 0
    assert p.closed_trades_count == 0
    assert p.total_fills == 0
