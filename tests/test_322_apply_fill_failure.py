"""Audit 3.22: a ValueError from Portfolio.apply_fill must not escape
on_tick and kill the cadence. _execute_fill catches it, logs a warning,
records it in rejection_audit like any other rejection, and returns
None; the rest of the tick still processes and later ticks still work.
"""
import logging
from decimal import Decimal

from src.arena.broker_sim import BrokerSim
from src.arena.order import ExecutionReason, OrderSide, OrderType, OrderTicket, PositionSide
from src.arena.portfolio import Portfolio


def _open_long(broker, stop_loss=None):
    p = Portfolio(
        "p_322", "ApplyFillFail",
        initial_cash=Decimal("100000.00"),
        leverage=Decimal("3.0"), leverage_enabled=True,
    )
    broker.register_portfolio(p, max_position_ratio=Decimal("0.70"))
    broker.on_tick(price=Decimal("3500.00"), timestamp=100.0)
    ticket = OrderTicket(
        "p_322", "ETH/USD", OrderSide.BUY, OrderType.MARKET,
        qty=Decimal("20"), stop_loss=stop_loss, timestamp=100.0,
    )
    fill = broker.submit_order(ticket)
    assert fill is not None
    assert p.position_qty == Decimal("20.0000")
    return p


def test_apply_fill_value_error_does_not_kill_cadence(monkeypatch, caplog):
    broker = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0.0"))
    p = _open_long(broker, stop_loss=Decimal("3400.00"))
    assert broker.active_stops.get("p_322") is not None

    def _boom(fill):
        raise ValueError("Insufficient cash in p_322: need 99999, have 1")

    monkeypatch.setattr(p, "apply_fill", _boom)

    # Stop-hit tick: the stop fill raises inside apply_fill.
    with caplog.at_level(logging.WARNING):
        fills = broker.on_tick(price=Decimal("3350.00"), timestamp=101.0)
    assert fills == []  # no fill, but no raise either
    assert p.position_qty == Decimal("20.0000")  # position untouched
    assert any("apply_fill failed" in r.message for r in caplog.records)
    assert any(
        pid == "p_322" and "apply_fill failed" in reason
        for pid, reason in broker.rejection_audit
    )

    # The cadence continues: with apply_fill restored, the same stop
    # price now fills and closes the position.
    monkeypatch.undo()
    fills = broker.on_tick(price=Decimal("3350.00"), timestamp=102.0)
    assert len(fills) == 1
    assert fills[0].reason == ExecutionReason.STOP_LOSS
    assert p.position_qty == Decimal("0")


def test_submit_order_returns_none_when_apply_fill_fails(monkeypatch):
    broker = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0.0"))
    p = Portfolio("p_322b", "ApplyFillFail2", initial_cash=Decimal("100000.00"))
    broker.register_portfolio(p)
    broker.on_tick(price=Decimal("3500.00"), timestamp=100.0)

    def _boom(fill):
        raise ValueError("boom")

    monkeypatch.setattr(p, "apply_fill", _boom)
    ticket = OrderTicket(
        "p_322b", "ETH/USD", OrderSide.BUY, OrderType.MARKET,
        qty=Decimal("1"), timestamp=100.0,
    )
    assert broker.submit_order(ticket) is None
    assert p.position_qty == Decimal("0")
