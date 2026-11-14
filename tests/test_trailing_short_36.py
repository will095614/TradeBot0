"""Audit 3.6: TrailingGuard trails shorts in the backtest.

Before the fix evaluate_signal ran the LONG ratchet for both sides
(position_qty > 0 holds for shorts too): it armed "trailing" when the
price ROSE 2% -- a 2% loss for a short -- and wrote a SELL stop whose
price chased the rally upward instead of ratcheting down, so a backtest
short never trailed. After the fix the short branch mirrors the live
short ratchet (lowest tracking, 2.0% trigger, stop = lowest x (1 + 0.6%),
BUY side, ratchet-down only) plus the breakeven step the method already
applies to longs.
"""
import time
from decimal import Decimal

from src.arena.broker_sim import BrokerSim
from src.arena.order import ExecutionReason, OrderSide
from src.competitors.trailing_guard import TrailingGuardCompetitor
from src.data.eth_feed import CandleBar
from src.data.timemachine import TimeMachineArena


def _open_short(comp, broker, price, ts):
    """Open a short through the real entry path; return the entry price."""
    ticket = comp.evaluate_signal(
        signal="BUY", side=OrderSide.SELL, market_price=price,
        indicators={}, broker=broker, timestamp=ts)
    assert ticket is not None
    assert ticket.side == OrderSide.SELL
    fill = broker.submit_order(ticket)
    assert fill is not None
    assert comp.portfolio.position_side.value == "SHORT"
    return comp.portfolio.avg_entry_price


def test_short_trailing_stop_ratchets_down_then_exits_at_trailed_level():
    """Direct: short at 3500 (slippage 0, so entry is exactly 3500.00).
    Falls to a 3430 trough, then retraces -- the stop must ratchet down
    3552.50 -> 3498.25 (breakeven at +1%) -> 3450.58 (trailing at +2%),
    never move back up, and the short must exit at the trailed level."""
    broker = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0.0"))
    comp = TrailingGuardCompetitor(initial_cash=Decimal("100000.00"))
    broker.register_portfolio(comp.portfolio, max_position_ratio=comp.max_position_ratio)
    # Prime the venue clock: a market fill needs a current price.
    broker.on_tick(Decimal("3500.00"), timestamp=999.0)

    entry = _open_short(comp, broker, Decimal("3500.00"), 1000.0)
    assert entry == Decimal("3500.00")
    stop = broker.active_stops["comp_trail"]
    assert stop.side == OrderSide.BUY
    assert stop.price == Decimal("3552.50")  # entry x 1.015 (genome SL 1.5%)

    # +1.43% gain: breakeven step, stop moves down to entry x 0.9995.
    comp.evaluate_signal(signal="HOLD", market_price=Decimal("3450.00"),
                         indicators={}, broker=broker, timestamp=1001.0)
    assert comp.trailing_active is False
    assert broker.active_stops["comp_trail"].price == Decimal("3498.25")
    assert broker.active_stops["comp_trail"].side == OrderSide.BUY

    # +2.00% gain: trailing arms, stop = trough x (1 + 0.6%) = 3450.58.
    comp.evaluate_signal(signal="HOLD", market_price=Decimal("3430.00"),
                         indicators={}, broker=broker, timestamp=1002.0)
    assert comp.trailing_active is True
    assert comp.lowest_price_since_entry == Decimal("3430.00")
    assert broker.active_stops["comp_trail"].price == Decimal("3450.58")

    # Small bounce: the trough (and the stop) must NOT move back up.
    comp.evaluate_signal(signal="HOLD", market_price=Decimal("3440.00"),
                         indicators={}, broker=broker, timestamp=1003.0)
    assert comp.lowest_price_since_entry == Decimal("3430.00")
    assert broker.active_stops["comp_trail"].price == Decimal("3450.58")

    # Retrace through the trailed stop: the short covers at the trailed
    # level, not at the original 3552.50 stop (never reached) or untrailed.
    fills = broker.on_tick(price=Decimal("3460.00"), high=Decimal("3460.00"),
                           low=Decimal("3460.00"), timestamp=1004.0,
                           open_price=Decimal("3460.00"))
    assert comp.portfolio.position_qty == Decimal("0")
    assert len(fills) == 1
    assert fills[0].reason == ExecutionReason.TRAILING_STOP
    assert fills[0].realized_pnl > Decimal("0")


def _tape():
    """23 bars: 15 flat warmup bars (trend up), a SELL bar that opens the
    short, HOLD bars while the price falls to a 3420 trough, then HOLD bars
    retracing through the trailed stop. Signals come from the synthetic
    generate_signal path (macd_hist None): SELL only on the EMA flip-down
    bar, HOLD while the trend stays down and RSI stays 50."""
    now = time.time()
    closes = [3500.0] * 15 + [3500.0, 3480.0, 3460.0, 3440.0, 3420.0,
                              3425.0, 3435.0, 3445.0]
    bars = []
    for i, close in enumerate(closes):
        if i < 15:
            ema_fast, ema_slow = Decimal("3510.00"), Decimal("3490.00")
        else:
            ema_fast, ema_slow = Decimal("3490.00"), Decimal("3510.00")
        bars.append(CandleBar(
            timestamp=now - (len(closes) - i) * 60.0,
            open_=Decimal(f"{close:.2f}"),
            high=Decimal(f"{close + 5.0:.2f}"),
            low=Decimal(f"{close - 5.0:.2f}"),
            close=Decimal(f"{close:.2f}"),
            volume=Decimal("15.00"),
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            rsi=Decimal("50.00"),
            atr=Decimal("12.00"),
        ))
    return bars


def test_backtest_short_trailing_stop_ratchets_down():
    """Backtest, tape cut off at the trough: the short is still open, the
    stop has ratcheted down to trough x (1 + 0.6%) = 3440.52 as a BUY stop."""
    bars = _tape()[:21]  # bars 0..20, ends at 3425 after the 3420 trough
    arena = TimeMachineArena(initial_cash=Decimal("100000.00"))
    arena.run_simulation(bars)

    comp = arena.comp_d
    assert comp.portfolio.position_qty > Decimal("0")
    assert comp.portfolio.position_side.value == "SHORT"
    assert comp.trailing_active is True
    assert comp.lowest_price_since_entry == Decimal("3420.00")
    stop = arena.broker.active_stops["comp_trail"]
    assert stop.side == OrderSide.BUY
    assert stop.price == Decimal("3440.52")
    assert stop.price < (comp.portfolio.avg_entry_price * Decimal("0.9995")).quantize(Decimal("0.01"))


def test_backtest_short_exits_at_trailed_level_not_original_stop():
    """Backtest, full tape: the retrace crosses the trailed stop, so the
    short covers with a TRAILING_STOP fill in profit -- the original
    3552.50 stop was never reached."""
    arena = TimeMachineArena(initial_cash=Decimal("100000.00"))
    arena.run_simulation(_tape())

    comp = arena.comp_d
    assert comp.portfolio.position_qty == Decimal("0")
    closing = [f for f in arena.broker.execution_audit
               if f.portfolio_id == "comp_trail" and f.is_closing_fill]
    assert closing, "trailing short never closed"
    last = closing[-1]
    assert last.reason == ExecutionReason.TRAILING_STOP
    assert last.realized_pnl > Decimal("0")
