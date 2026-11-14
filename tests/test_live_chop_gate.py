"""Debug pass, Part C: live chop gate (live_engine._chop_gate_blocks).

The backtest gate (test_508_chop_gate.py) blocks new entries while
Kaufman ER over the last 21 15m closes is < 0.25. The live gate reuses
that exact statistic, window and threshold, reading the 15m closes
from the MTF engine's live aggregation of the 1m feed. The live drive
(probe dbg_v270_livegate.py, production engine on real Binance 1m
bars) showed it recovers a material share of the flat-month loss
without hurting the trend month, so it ships in the live entry funnel
(_try_enter_bracket, after the SIGNAL_EXIT fast path).

These tests pin: the warmup boundary (21 closed bars), the chop/trend
split, the forming-bucket exclusion, the entry block through the real
funnel, and -- most importantly -- that a SIGNAL_EXIT close is never
blocked by the gate.
"""
from decimal import Decimal

from src.arena.order import ExecutionReason, OrderSide, PositionSide
from src.data.live_engine import LiveArenaEngine


def _bars(closes):
    """15m bucket dicts (forming bucket = last element)."""
    return [
        {"t": float(i * 900), "o": float(c), "h": float(c),
         "l": float(c), "c": float(c), "v": 1.0}
        for i, c in enumerate(closes)
    ]


def _choppy_closes(n=21):
    """Alternating 3500/3520: net ~20 over a ~400 path, ER ~0.05."""
    return [3500.0 + (20.0 if i % 2 else 0.0) for i in range(n)]


def _trend_closes(n=21):
    """Monotonic +10/bar: ER = 1.0."""
    return [3500.0 + 10.0 * i for i in range(n)]


def _engine_with_15m(closes):
    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    engine.bootstrap_intraday_session()
    engine.htf_bias = "NEUTRAL"
    engine.candles_15m = _bars(closes)
    return engine


def test_chop_gate_open_with_fewer_than_21_closed_bars():
    engine = _engine_with_15m([])
    assert engine._chop_gate_blocks() is False
    # 20 closed choppy bars + forming bucket: still open (needs 21).
    engine.candles_15m = _bars(_choppy_closes(20) + [3500.0])
    assert engine._chop_gate_blocks() is False
    engine.stop()


def test_chop_gate_blocks_on_choppy_15m():
    engine = _engine_with_15m(_choppy_closes(21) + [3500.0])
    assert engine._chop_gate_blocks() is True
    engine.stop()


def test_chop_gate_excludes_the_forming_bucket():
    """A forming bucket whose close would make ER look trending must
    not unblock the gate: only closed bars count."""
    engine = _engine_with_15m(_choppy_closes(21) + [4000.0])
    assert engine._chop_gate_blocks() is True
    engine.stop()


def test_chop_gate_open_on_trending_15m():
    engine = _engine_with_15m(_trend_closes(21) + [3700.0])
    assert engine._chop_gate_blocks() is False
    engine.stop()


def test_chop_gate_open_when_path_is_zero():
    """Flat closes (path 0): efficiency_ratio returns 1.0, not chop,
    and the gate never crashes on a zero path."""
    engine = _engine_with_15m([3500.0] * 21 + [3500.0])
    assert engine._chop_gate_blocks() is False
    engine.stop()


def test_chop_gate_blocks_entry_through_try_enter_bracket():
    engine = _engine_with_15m(_choppy_closes(21) + [3500.0])
    comp = engine.comp_a
    assert comp.portfolio.position_qty == Decimal("0")
    entered = engine._try_enter_bracket(
        comp, Decimal("3510.00"), Decimal("3400.00"), Decimal("3620.00"),
        2000.0, "TEST_CHOP", side=OrderSide.BUY,
    )
    assert entered is False
    assert comp.portfolio.position_qty == Decimal("0")
    assert engine.live_chop_gate_blocked == 1
    assert engine.strategy_cooldown["comp_agg"] == 2000.0 + 20.0
    assert "Chop Gate" in engine.strategy_telemetry["comp_agg"]["intent"]
    engine.stop()


def test_chop_gate_never_blocks_signal_exit_close():
    """A position must always be exitable, even while the gate blocks
    entries -- the SIGNAL_EXIT fast path runs before the gate."""
    engine = _engine_with_15m(_choppy_closes(21) + [3500.0])
    assert engine._chop_gate_blocks() is True
    engine.broker.current_price = Decimal("2600.00")
    comp = engine.comp_a
    comp.portfolio.position_qty = Decimal("5")
    comp.portfolio.position_side = PositionSide.LONG
    comp.portfolio.avg_entry_price = Decimal("2500.00")

    ticket = comp._close_ticket(engine.broker, 2000.0)
    assert ticket is not None
    assert ticket.reason == ExecutionReason.SIGNAL_EXIT

    closed = engine._try_enter_bracket(
        comp, Decimal("2600.00"), ticket.stop_loss, ticket.take_profit,
        2000.0, "TEST_CLOSE", ticket=ticket,
    )
    assert closed is True
    assert comp.portfolio.position_qty == Decimal("0")
    assert engine.live_chop_gate_blocked == 0
    engine.stop()
