"""Audit 3.7: snapshot truncates trade_history but keeps cumulative counters.

Before the fix the snapshot kept only the last 50 fills but the full
win/loss counters, while the leaderboard derived win rate and closed
trades by COUNTING the truncated history -- so after a restore with >50
closed trades the win rate was a small-sample value, closed_trades was
capped at 50, and the fitness churn penalty was understated.

Fix (option (b)): the counters are the lifetime truth and round-trip
unchanged; the snapshot marks the history as a truncated sample
(trade_history_total / trade_history_truncated / total_fills); win rate,
closed_trades and total_trades are derived from the lifetime counters.
Recomputing the counters from the kept 50 was rejected: it would discard
lifetime performance on every restore and break the
realized_pnl = gross_profit - gross_loss identity.

All storage here is a tmp_path ArenaStorage -- never the real database.
"""
import time
from decimal import Decimal

from src.arena.leaderboard import Leaderboard
from src.arena.order import ExecutionReason, OrderSide, OrderTicket, OrderType
from src.data.eth_feed import CandleBar
from src.data.live_engine import LiveArenaEngine
from src.data.persistence import ArenaStorage


def _bars():
    """120 deterministic 1m bars (same shape as the 3.4/3.5 fixtures)."""
    now = time.time()
    return [
        CandleBar(
            timestamp=now - (120 - i) * 60.0,
            open_=Decimal("3500.00"),
            high=Decimal("3520.00"),
            low=Decimal("3480.00"),
            close=Decimal("3500.00"),
            volume=Decimal("15.00"),
            ema_fast=Decimal("3500.00"),
            ema_slow=Decimal("3500.00"),
            rsi=Decimal("50.00"),
            atr=Decimal("12.00"),
        )
        for i in range(120)
    ]


def _round_trips(eng, n=60):
    """Drive n round trips on comp_a through the real broker: buy 0.1 ETH
    at 3500, sell at 3520 (win) or 3480 (loss). Pattern 2 wins / 1 loss
    gives 40 wins / 20 losses. Price moves (+/-$20) dominate fees and
    slippage, so the win/loss split is deterministic."""
    broker = eng.broker
    broker.on_tick(price=Decimal("3500.00"), timestamp=1000.0)
    ts = 2000.0
    for i in range(n):
        sell_price = Decimal("3480.00") if i % 3 == 2 else Decimal("3520.00")
        buy = broker.submit_order(OrderTicket(
            portfolio_id="comp_agg", symbol="ETH/USD", side=OrderSide.BUY,
            order_type=OrderType.MARKET, qty=Decimal("0.1"),
            price=Decimal("3500.00"), reason=ExecutionReason.SIGNAL_ENTRY,
            timestamp=ts))
        assert buy is not None
        ts += 1.0
        sell = broker.submit_order(OrderTicket(
            portfolio_id="comp_agg", symbol="ETH/USD", side=OrderSide.SELL,
            order_type=OrderType.MARKET, qty=Decimal("0.1"),
            price=sell_price, reason=ExecutionReason.SIGNAL,
            timestamp=ts))
        assert sell is not None
        ts += 1.0
    return eng.comp_a.portfolio


def _stats_for(eng, pid="comp_agg"):
    rankings = Leaderboard.get_rankings(eng.broker.portfolios)
    return next(r for r in rankings if r.portfolio_id == pid)


def test_snapshot_counters_survive_restore_with_truncated_history(tmp_path, monkeypatch):
    """60 closed trades (>50): after save + restore, win rate /
    closed_trades / total_trades / profit_factor equal the pre-save
    lifetime values -- not the truncated-history values -- and the
    snapshot says explicitly that its history is a sample."""
    storage = ArenaStorage(db_path=str(tmp_path / "arena_history.db"))
    eng = LiveArenaEngine(storage=storage,
                          initial_cash=Decimal("500000.00"), symbol="ETH/USD")
    monkeypatch.setattr(
        "src.data.live_engine.ETHFeed.fetch_historical_bars",
        staticmethod(lambda *a, **k: _bars()),
    )
    try:
        eng.bootstrap_intraday_session()
        p = _round_trips(eng, n=60)

        # Pre-save lifetime truth: 40 wins / 20 losses, 120 fills.
        assert p.win_count == 40
        assert p.loss_count == 20
        assert p.closed_trades_count == 60
        assert p.total_fills == 120
        assert len(p.trade_history) == 120
        pre = _stats_for(eng)
        assert pre.win_rate_pct == Decimal("66.67")
        assert pre.closed_trades == 60
        assert pre.total_trades == 120
        assert pre.profit_factor == p.profit_factor

        assert eng.save_session_state() is True
        snap = eng.storage.load_session_snapshot()
        comp_a = next(c for c in snap["competitors"] if c["portfolio_id"] == "comp_agg")
        assert comp_a["trade_history_total"] == 120
        assert comp_a["trade_history_truncated"] is True
        assert len(comp_a["trade_history"]) == 50
        assert comp_a["win_count"] == 40
        assert comp_a["loss_count"] == 20
        assert comp_a["total_fills"] == 120
    finally:
        eng.stop()

    # Restore into a fresh engine on the same file -- no graceful
    # shutdown, no extra save -- and the lifetime metrics must come
    # back intact, not capped at the 50 retained fills.
    eng2 = LiveArenaEngine(
        storage=ArenaStorage(db_path=str(tmp_path / "arena_history.db")),
        initial_cash=Decimal("500000.00"), symbol="ETH/USD")
    try:
        assert eng2.restore_session_state() is True
        p2 = eng2.comp_a.portfolio
        assert p2.win_count == 40
        assert p2.loss_count == 20
        assert p2.closed_trades_count == 60
        assert p2.total_fills == 120
        assert len(p2.trade_history) == 50
        # The money identity option (a) would have broken still holds:
        # gross_profit - gross_loss == realized_pnl (full history).
        assert (p2.gross_profit - p2.gross_loss) == p2.realized_pnl

        post = _stats_for(eng2)
        assert post.win_rate_pct == Decimal("66.67")
        assert post.win_rate_pct == pre.win_rate_pct
        assert post.closed_trades == 60
        assert post.closed_trades == pre.closed_trades
        assert post.total_trades == 120
        assert post.total_trades == pre.total_trades
        assert post.profit_factor == pre.profit_factor
    finally:
        eng2.stop()


def test_short_history_is_not_marked_truncated(tmp_path, monkeypatch):
    """Fewer than 50 fills: the marker says not truncated and the totals
    agree with the retained history (the honest case)."""
    storage = ArenaStorage(db_path=str(tmp_path / "arena_history.db"))
    eng = LiveArenaEngine(storage=storage,
                          initial_cash=Decimal("500000.00"), symbol="ETH/USD")
    monkeypatch.setattr(
        "src.data.live_engine.ETHFeed.fetch_historical_bars",
        staticmethod(lambda *a, **k: _bars()),
    )
    try:
        eng.bootstrap_intraday_session()
        p = _round_trips(eng, n=3)  # 3 wins/losses mix, 6 fills
        assert eng.save_session_state() is True
        snap = eng.storage.load_session_snapshot()
        comp_a = next(c for c in snap["competitors"] if c["portfolio_id"] == "comp_agg")
        assert comp_a["trade_history_total"] == 6
        assert comp_a["trade_history_truncated"] is False
        assert len(comp_a["trade_history"]) == 6
        assert comp_a["total_fills"] == 6
        assert p.win_count + p.loss_count == 3
    finally:
        eng.stop()
