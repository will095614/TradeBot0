"""Audit 3.17: the SIGNAL_EXIT fast path in _try_enter_bracket is NOT dead.

The audit claimed no caller can reach it with SIGNAL_EXIT. That is true
of the 24 production call sites in live_engine.py (all pass only side=,
so signal defaults to "BUY" and evaluate_signal("BUY") never returns a
close ticket). But the path is live and load-bearing:

* test_close_ticket_bypasses_veto_and_gates_under_hold_cash
  (tests/test_intel_veto.py) routes a close ticket through
  _enter_via_strategy(signal="SELL") and asserts it closes under
  HOLD_CASH.
* The fast path is the ONLY guard that makes close tickets safe through
  _try_enter_bracket: without it a close ticket would hit the macro veto
  (called with is_close=False -- the comment there says "Only opening
  orders reach this point") and the MC EV gate (which would crash on
  stop_loss=None, as the fast-path comment warns).
* It guards a deliberate design property (item 6): a position must
  always be exitable, even under HOLD_CASH. And _enter_via_strategy
  accepts signal= as API surface, so any future signal="SELL" caller
  needs the guard.

Deleting the fast path would break that test and remove the guard with
no surviving path for a close ticket through _try_enter_bracket (the
cadence's direct broker.submit_order is a different route). So the
deletion is NOT made. This test pins the fast path directly, so any
future attempt to delete it fails loudly here first.
"""
from decimal import Decimal

from src.arena.order import ExecutionReason
from src.arena.order import PositionSide
from src.data.live_engine import LiveArenaEngine


def test_signal_exit_fast_path_closes_under_hold_cash():
    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    engine.bootstrap_intraday_session()
    engine.macro_commander.current_state.directional_bias = "HOLD_CASH"
    engine.broker.current_price = Decimal("2600.00")
    comp = engine.comp_a
    comp.portfolio.position_qty = Decimal("5")
    comp.portfolio.position_side = PositionSide.LONG
    comp.portfolio.avg_entry_price = Decimal("2500.00")

    ticket = comp._close_ticket(engine.broker, 2000.0)
    assert ticket is not None
    assert ticket.reason == ExecutionReason.SIGNAL_EXIT
    assert ticket.stop_loss is None  # the MC EV gate would crash on this

    closed = engine._try_enter_bracket(
        comp, Decimal("2600.00"), ticket.stop_loss, ticket.take_profit,
        2000.0, "TEST_CLOSE", ticket=ticket,
    )
    assert closed is True
    assert comp.portfolio.position_qty == Decimal("0")
    engine.stop()
