"""Chop gate (Phase 8): Kaufman efficiency-ratio gate on new entries.

Measured on real tapes (one pass, gen-1 defaults; experiment
~/workspace/tradebot_audit/chop_gate_exp.py, results in %TEMP%/chop_gate_exp):
  gate           FLAT mean ROI / Fit      TREND mean ROI / Fit
  none           -5.52% / -49.76           +0.86% / -5.96
  ER(20) < 0.25  -3.44% / -19.05           +2.83% / +7.75   <- implemented
  ER(20) < 0.15  -5.00% / -32.16           +0.89% / -4.90
  range/ATR < 3  -3.45% / -25.83           +0.91% / -5.48
  ADX(14) < 20   -4.59% / -30.92           -1.34% / -17.54  (hurts trend: rejected)
  ADX(14) < 25   -3.54% / -22.27           +0.84% / -0.41
ER(20) < 0.25 recovers 2.08pp (38%) of the flat-month loss and improves
the trend month, so it ships in the backtest. Scope note: the gate is
validated on 15m bars (20 bars = 5h window). The live engine replays
1m candles with a 150-bar buffer, so the same 5h statistic cannot run
there as-is -- the live port is deferred to the full debug & optimize
pass (needs 1m-timescale calibration), and live entries stay ungated.
"""
from __future__ import annotations

from decimal import Decimal

from src.data.eth_feed import CandleBar
from src.data.timemachine import TimeMachineArena, efficiency_ratio


def _bar(ts, close, ema_fast, ema_slow, rsi=Decimal("55.00"), high=None, low=None):
    c = Decimal(str(close))
    return CandleBar(
        timestamp=float(ts),
        open_=c,
        high=c + Decimal("15.00") if high is None else Decimal(str(high)),
        low=c - Decimal("15.00") if low is None else Decimal(str(low)),
        close=c,
        volume=Decimal("100.0"),
        ema_fast=Decimal(str(ema_fast)),
        ema_slow=Decimal(str(ema_slow)),
        rsi=Decimal(str(rsi)),
        atr=Decimal("25.00"),
    )


def _choppy_bars(n=60):
    """Oscillating closes (+/-$10) with alternating EMA crossovers, so
    BUY/SELL signals fire almost every bar. ER over any 21 closes is
    ~0.05 -- deep chop once the window fills."""
    bars = []
    for i in range(n):
        close = 3500 + (10 if i % 2 else 0)
        if i % 2 == 0:
            ema_fast, ema_slow = close + 5, close - 5  # uptrend -> BUY
        else:
            ema_fast, ema_slow = close - 5, close + 5  # downtrend -> SELL
        bars.append(_bar(1000.0 + i * 900, close, ema_fast, ema_slow))
    return bars


def _trend_bars(n=60):
    """Monotonic +$5/bar rise, fast EMA above slow throughout. ER ~ 1."""
    bars = []
    for i in range(n):
        close = 3500 + 5 * i
        bars.append(_bar(1000.0 + i * 900, close, close - 5, close - 20,
                         rsi=Decimal("50.00") + Decimal(min(i, 10))))
    return bars


def _total_closed(arena):
    return sum(c.portfolio.closed_trades_count for c in arena.competitors)


def test_efficiency_ratio_unit():
    assert efficiency_ratio([100.0, 101.0, 102.0, 103.0, 104.0]) == 1.0
    assert efficiency_ratio([100.0, 101.0, 100.0, 101.0, 100.0, 101.0,
                             100.0, 101.0, 100.0, 101.0, 100.0]) < 0.1
    assert efficiency_ratio([100.0, 100.0, 100.0]) == 1.0  # no path -> not chop
    assert efficiency_ratio([100.0]) == 1.0


def test_gate_blocks_entries_on_choppy_tape():
    bars = _choppy_bars()
    ungated = TimeMachineArena(symbol="ETH/USD", initial_cash=Decimal("100000.00"))
    ungated.run_simulation(bars, chop_gate=False)
    gated = TimeMachineArena(symbol="ETH/USD", initial_cash=Decimal("100000.00"))
    gated.run_simulation(bars, chop_gate=True)
    assert gated.chop_gate_blocked > 0
    assert _total_closed(gated) < _total_closed(ungated)
    ungated_fills = sum(len(c.portfolio.trade_history) for c in ungated.competitors)
    gated_fills = sum(len(c.portfolio.trade_history) for c in gated.competitors)
    assert gated_fills < ungated_fills


def test_gate_inactive_on_trend_tape():
    bars = _trend_bars()
    ungated = TimeMachineArena(symbol="ETH/USD", initial_cash=Decimal("100000.00"))
    r_off = ungated.run_simulation(bars, chop_gate=False)
    gated = TimeMachineArena(symbol="ETH/USD", initial_cash=Decimal("100000.00"))
    r_on = gated.run_simulation(bars, chop_gate=True)
    assert gated.chop_gate_blocked == 0
    assert [float(r.roi_pct) for r in r_on] == [float(r.roi_pct) for r in r_off]
    assert [r.closed_trades for r in r_on] == [r.closed_trades for r in r_off]


def test_gate_never_blocks_closes():
    """A long opened in the trend leg must still close on the SELL
    signal even though the gate is active by then (chop leg), and
    later flat entries in chop must be blocked."""
    bars = []
    for i in range(20):  # trend leg: BUY opens the long (price above fast EMA)
        close = 3500 + 5 * i
        bars.append(_bar(1000.0 + i * 900, close, close - 5, close - 20))
    for i in range(20, 60):  # chop leg, still "uptrend" EMAs (no SELL yet)
        close = 3595 + (10 if i % 2 else 0)
        bars.append(_bar(1000.0 + i * 900, close, close - 5, close - 20))
    for i in range(60, 65):  # EMA crosses down -> SELL while gate is active
        close = 3595 + (10 if i % 2 else 0)
        bars.append(_bar(1000.0 + i * 900, close, close - 20, close - 5))
    arena = TimeMachineArena(symbol="ETH/USD", initial_cash=Decimal("100000.00"))
    arena.run_simulation(bars, chop_gate=True)
    assert arena.chop_gate_blocked > 0
    agg = arena.comp_a.portfolio
    assert agg.position_qty == Decimal("0"), "the long must have closed on the SELL"
    assert len(agg.trade_history) >= 2, "open + close fills expected"
