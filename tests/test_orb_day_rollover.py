"""V2.8.0: the ORB range must roll with the UTC trading day.

Before the fix the live range was frozen at bootstrap (app start) for the
life of the process, and the backtest anchored to bars[:15] of the whole
dataset, so a run that crossed midnight kept trading the previous day's
opening range. Both paths now rebuild from the first 15 closed bars of the
new UTC day and freeze again.
"""
from decimal import Decimal

from src.data.eth_feed import CandleBar
from src.data.live_engine import LiveArenaEngine
from src.data.timemachine import TimeMachineArena

DAY1 = 1_767_225_600.0          # 2026-01-01T00:00:00Z
DAY2 = DAY1 + 86_400.0          # 2026-01-02T00:00:00Z


def _minute_candles(day_start, count, high, low):
    mid = (high + low) / 2.0
    return [
        {
            "t": day_start + i * 60.0,
            "o": mid,
            "h": high,
            "l": low,
            "c": mid,
        }
        for i in range(count)
    ]


def _tape_bar(timestamp, close, high, low):
    return CandleBar(
        timestamp=timestamp,
        open_=Decimal(f"{close - 2:.2f}"),
        high=Decimal(f"{high:.2f}"),
        low=Decimal(f"{low:.2f}"),
        close=Decimal(f"{close:.2f}"),
        volume=Decimal("100.0"),
        ema_fast=Decimal(f"{close - 1:.2f}"),
        ema_slow=Decimal(f"{close - 5:.2f}"),
        rsi=Decimal("55.00"),
        atr=Decimal("25.00"),
    )


def test_live_orb_range_rolls_at_utc_midnight():
    engine = LiveArenaEngine(initial_cash=Decimal("500000.00"), symbol="ETH/USD")
    engine.candles = _minute_candles(DAY1, 30, 3600.0, 3400.0)
    engine._recompute_candle_indicators()
    assert engine.live_orb_high == Decimal("3600.00")
    assert engine.live_orb_low == Decimal("3400.00")
    assert engine._orb_range_frozen is True

    # The rolling buffer still holds yesterday's bars when the new day
    # starts; only the new day's first 15 may define the range.
    engine.candles = engine.candles + _minute_candles(DAY2, 15, 3800.0, 3700.0)
    engine._recompute_candle_indicators()
    assert engine.live_orb_high == Decimal("3800.00")
    assert engine.live_orb_low == Decimal("3700.00")
    assert engine._orb_range_frozen is True


def test_live_orb_range_is_forming_on_a_partial_new_day():
    engine = LiveArenaEngine(initial_cash=Decimal("500000.00"), symbol="ETH/USD")
    engine.candles = _minute_candles(DAY1, 30, 3600.0, 3400.0)
    engine._recompute_candle_indicators()
    assert engine._orb_range_frozen is True

    engine.candles = engine.candles + _minute_candles(DAY2, 5, 3900.0, 3750.0)
    engine._recompute_candle_indicators()
    assert engine.live_orb_high == Decimal("3900.00")
    assert engine.live_orb_low == Decimal("3750.00")
    assert engine._orb_range_frozen is False, "the old frozen range must not survive the rollover"


def test_backtest_orb_range_rolls_at_utc_midnight():
    arena = TimeMachineArena(symbol="ETH/USD", initial_cash=Decimal("500000.00"))
    bars = (
        [_tape_bar(DAY1 + i * 900.0, 3500.0, 3600.0, 3400.0) for i in range(20)]
        + [_tape_bar(DAY2 + i * 900.0, 3750.0, 3800.0, 3700.0) for i in range(20)]
    )
    seen = []
    original = arena.comp_e.evaluate_signal

    def _spy(signal, market_price, indicators, broker, timestamp, **kwargs):
        seen.append((float(timestamp), indicators["orb_high"], indicators["orb_low"]))
        return original(signal, market_price, indicators, broker, timestamp, **kwargs)

    arena.comp_e.evaluate_signal = _spy
    arena.run_simulation(bars)

    day1 = [(h, lo) for ts, h, lo in seen if ts < DAY2]
    day2 = [(h, lo) for ts, h, lo in seen if ts >= DAY2]
    assert day1 and day2, seen
    assert all(h == Decimal("3600") and lo == Decimal("3400") for h, lo in day1)
    assert all(h == Decimal("3800") and lo == Decimal("3700") for h, lo in day2)
