"""Audit 3.4: the ORB opening range is anchored to the session's first 15 bars.

Before the fix the live range was recomputed from ``cs[:15]`` -- the oldest
15 bars of the rolling 200-bar buffer -- so it slid forward as the buffer
rolled (~3h of drift), and the backtest used a rolling 14-bar window, so
backtest ORB was a rolling-channel breakout, a different strategy from live
ORB. After the fix both paths anchor to the first 15 bars of the session
tape and freeze the range once 15 bars exist.
"""
from decimal import Decimal

import pytest

from src.data.eth_feed import CandleBar
from src.data.live_engine import LiveArenaEngine
from src.data.timemachine import TimeMachineArena


def _warmup_bars():
    """120 deterministic bars: first 15 flat with a 3520/3480 box, then rising.

    Fixture data, never production data.
    """
    # Fixed UTC day (02:00Z): a wall-clock "now" near midnight would
    # straddle two trading days and make the first-15 anchor depend on
    # the time the suite happens to run. V2.8.0 made the range
    # day-scoped, so the fixture pins one day.
    now = 1_767_225_600.0 + 2 * 3600  # 2026-01-01T02:00:00Z
    bars = []
    for i in range(120):
        if i < 15:
            close, high, low = 3500.0, 3520.0, 3480.0
        else:
            close = 3500.0 + (i - 14)
            high, low = close + 5.0, close - 5.0
        bars.append(CandleBar(
            timestamp=now - (120 - i) * 60.0,
            open_=Decimal(f"{close:.2f}"),
            high=Decimal(f"{high:.2f}"),
            low=Decimal(f"{low:.2f}"),
            close=Decimal(f"{close:.2f}"),
            volume=Decimal("15.00"),
            ema_fast=Decimal(f"{close:.2f}"),
            ema_slow=Decimal(f"{close:.2f}"),
            rsi=Decimal("50.00"),
            atr=Decimal("12.00"),
        ))
    return bars


def test_bootstrap_anchors_orb_range_to_first_15_warmup_bars(monkeypatch):
    """Live bootstrap: the range comes from the first 15 warmup bars and freezes."""
    monkeypatch.setattr(
        "src.data.live_engine.ETHFeed.fetch_historical_bars",
        staticmethod(lambda *a, **k: _warmup_bars()),
    )
    engine = LiveArenaEngine(initial_cash=Decimal("500000.00"), symbol="ETH/USD")
    engine.bootstrap_intraday_session()
    assert engine.live_orb_high == Decimal("3520.00")
    assert engine.live_orb_low == Decimal("3480.00")
    assert engine._orb_range_frozen is True


def test_live_orb_range_does_not_drift_with_rolling_buffer():
    """After 15 session bars exist the range never moves, however far the buffer rolls."""
    engine = LiveArenaEngine(initial_cash=Decimal("500000.00"), symbol="ETH/USD")
    # 250 session candles: first 15 box 3600/3400, the rest a wider 3700/3300 box.
    engine.candles = [
        {"t": float(i * 60), "o": 3500.0,
         "h": 3600.0 if i < 15 else 3700.0,
         "l": 3400.0 if i < 15 else 3300.0,
         "c": 3500.0}
        for i in range(250)
    ]
    engine._recompute_candle_indicators()
    assert engine.live_orb_high == Decimal("3600.00")
    assert engine.live_orb_low == Decimal("3400.00")
    assert engine._orb_range_frozen is True

    # Roll the buffer 50 bars forward (the old code would now read bars 50-64
    # as the "opening" range) and recompute: the range must not move.
    engine.candles = engine.candles[50:] + [
        {"t": float((250 + i) * 60), "o": 3500.0, "h": 3800.0, "l": 3200.0, "c": 3500.0}
        for i in range(50)
    ]
    engine._recompute_candle_indicators()
    assert engine.live_orb_high == Decimal("3600.00")
    assert engine.live_orb_low == Decimal("3400.00")


def _tape_bar(ts, close, high=None, low=None):
    return CandleBar(
        timestamp=ts,
        open_=Decimal(f"{close - 2:.2f}"),
        high=Decimal(f"{high if high is not None else close + 5:.2f}"),
        low=Decimal(f"{low if low is not None else close - 5:.2f}"),
        close=Decimal(f"{close:.2f}"),
        volume=Decimal("100.0"),
        ema_fast=Decimal(f"{close - 1:.2f}"),
        ema_slow=Decimal(f"{close - 5:.2f}"),
        rsi=Decimal("55.00"),
        atr=Decimal("25.00"),
    )


def test_backtest_orb_range_anchored_to_first_15_tape_bars():
    """Backtest ORB uses the first 15 tape bars, not a rolling 14-bar window.

    First 15 bars box 3600/3400; the tape then rallies to 3780. The rolling
    window's high climbs with the rally, so under the old code the recorded
    orb_high would climb too; anchored it stays 3600/3400 for every bar.
    """
    arena = TimeMachineArena(symbol="ETH/USD", initial_cash=Decimal("500000.00"))
    bars = [_tape_bar(1000.0 + i * 900, 3500, high=3600, low=3400) for i in range(15)]
    closes = [3550, 3600, 3650, 3700, 3750, 3780, 3780, 3780, 3780, 3780, 3780]
    bars += [_tape_bar(1000.0 + (15 + i) * 900, c) for i, c in enumerate(closes)]

    seen = []
    orig_evaluate = arena.comp_e.evaluate_signal

    def _spy(signal, market_price, indicators, broker, timestamp, **kwargs):
        seen.append((indicators["orb_high"], indicators["orb_low"]))
        return orig_evaluate(signal, market_price, indicators, broker, timestamp, **kwargs)

    arena.comp_e.evaluate_signal = _spy
    rankings = arena.run_simulation(bars)
    assert len(rankings) == 5
    assert seen, "ORB competitor was never evaluated"
    assert all(h == Decimal("3600") and lo == Decimal("3400") for h, lo in seen), seen
    # The breakout above the anchored 3600 ceiling opens the ORB long, and the
    # midpoint-anchored stop (3500) keeps it alive through the 3780 peak:
    # TP 3950 is never reached, SL 3500 is never touched. (The active stop
    # ticket carries the stop level in `price`.)
    assert arena.comp_e.portfolio.position_qty > Decimal("0")
    stop = arena.broker.active_stops.get("comp_orb")
    assert stop is not None and stop.price == Decimal("3500.00")
