"""Audit 3.8: restored tickets lose their reason.

Before the fix _serialize_ticket wrote no `reason` and no `timestamp`,
so after a restore every stop-loss defaulted to ExecutionReason.SIGNAL
and displayed as "Strategy Signal" (the broker's on_tick reuses
stop_order.reason for the fill). After the fix both fields round-trip;
older saves without them fall back to the current default display.
"""
from decimal import Decimal

from src.arena.broker_sim import BrokerSim
from src.arena.order import ExecutionReason, OrderSide, OrderTicket, OrderType
from src.arena.portfolio import Portfolio
from src.data.live_engine import LiveArenaEngine

S = LiveArenaEngine._serialize_ticket
D = LiveArenaEngine._deserialize_ticket


def test_stop_loss_and_take_profit_reasons_round_trip():
    """STOP_LOSS and TAKE_PROFIT tickets keep their reason, timestamp and
    every other field through serialize -> deserialize."""
    stop = OrderTicket(
        portfolio_id="comp_agg", symbol="ETH/USD", side=OrderSide.SELL,
        order_type=OrderType.STOP_MARKET, qty=Decimal("0.1"),
        price=Decimal("3400.00"), reason=ExecutionReason.STOP_LOSS,
        timestamp=1234.5)
    target = OrderTicket(
        portfolio_id="comp_agg", symbol="ETH/USD", side=OrderSide.SELL,
        order_type=OrderType.LIMIT, qty=Decimal("0.1"),
        price=Decimal("3600.00"), reason=ExecutionReason.TAKE_PROFIT,
        timestamp=1235.5)

    s_stop = S(stop)
    assert s_stop["reason"] == "STOP_LOSS"
    assert s_stop["timestamp"] == 1234.5
    t_stop = D(s_stop)
    assert t_stop.reason == ExecutionReason.STOP_LOSS
    assert t_stop.reason.value == "STOP_LOSS"
    assert t_stop.timestamp == 1234.5
    assert (t_stop.portfolio_id, t_stop.symbol, t_stop.side,
            t_stop.order_type, t_stop.qty, t_stop.price) == (
        "comp_agg", "ETH/USD", OrderSide.SELL, OrderType.STOP_MARKET,
        Decimal("0.1"), Decimal("3400.00"))

    s_target = S(target)
    assert s_target["reason"] == "TAKE_PROFIT"
    assert s_target["timestamp"] == 1235.5
    t_target = D(s_target)
    assert t_target.reason == ExecutionReason.TAKE_PROFIT
    assert t_target.reason.value == "TAKE_PROFIT"
    assert t_target.timestamp == 1235.5
    assert t_target.price == Decimal("3600.00")


def test_old_save_without_reason_falls_back_to_signal():
    """An old save (no reason / timestamp keys) and a garbage reason both
    deserialize to the current default display instead of raising."""
    old = {"portfolio_id": "comp_agg", "symbol": "ETH/USD", "side": "SELL",
           "order_type": "STOP_MARKET", "qty": "0.1", "price": "3400.00",
           "stop_loss": None, "take_profit": None}
    t_old = D(old)
    assert t_old is not None
    assert t_old.reason == ExecutionReason.SIGNAL
    assert t_old.reason.value == "SIGNAL"

    bogus = dict(old, reason="BOGUS", timestamp="not-a-number")
    t_bogus = D(bogus)
    assert t_bogus is not None
    assert t_bogus.reason == ExecutionReason.SIGNAL


def test_restored_stop_loss_fill_displays_stop_loss():
    """End to end through the broker: a restored STOP_LOSS stop triggers a
    fill whose reason is STOP_LOSS -- not SIGNAL ("Strategy Signal")."""
    broker = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0.0"))
    p = Portfolio(portfolio_id="comp_agg", name="Test",
                  initial_cash=Decimal("100000.00"))
    broker.register_portfolio(p, max_position_ratio=Decimal("0.70"))
    broker.on_tick(price=Decimal("3500.00"), timestamp=1000.0)

    # Open a long at 3500.
    fill = broker.submit_order(OrderTicket(
        portfolio_id="comp_agg", symbol="ETH/USD", side=OrderSide.BUY,
        order_type=OrderType.MARKET, qty=Decimal("0.1"),
        price=Decimal("3500.00"), reason=ExecutionReason.SIGNAL_ENTRY,
        timestamp=1001.0))
    assert fill is not None
    assert p.position_qty == Decimal("0.1")

    # Simulate save -> restore of the stop bracket, then mount it the way
    # restore_session_state does (replacing the broker's stops).
    stop = OrderTicket(
        portfolio_id="comp_agg", symbol="ETH/USD", side=OrderSide.SELL,
        order_type=OrderType.STOP_MARKET, qty=Decimal("0.1"),
        price=Decimal("3400.00"), reason=ExecutionReason.STOP_LOSS,
        timestamp=1002.0)
    broker.active_stops["comp_agg"] = D(S(stop))

    fills = broker.on_tick(price=Decimal("3390.00"), high=Decimal("3390.00"),
                           low=Decimal("3390.00"), timestamp=1003.0,
                           open_price=Decimal("3390.00"))
    assert p.position_qty == Decimal("0")
    assert len(fills) == 1
    assert fills[0].reason == ExecutionReason.STOP_LOSS
    assert fills[0].reason.value == "STOP_LOSS"
