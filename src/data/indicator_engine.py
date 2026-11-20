"""
src/data/indicator_engine.py - Live Technical Indicators, MTF Resampling, ORB & Chop Gate.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import logging
import math
import time
from typing import Any, Dict, List, Optional

from src.arena.order import OrderSide
from src.data.mtf_engine import MultiTimeframeEngine
from src.data.quote_feeds import parse_symbol_pairs
from src.data.timemachine import CHOP_GATE_ER_THRESHOLD, CHOP_GATE_WINDOW_BARS, efficiency_ratio

logger = logging.getLogger(__name__)

MTF_SEED_STALE_SEC = 3 * 3600


class IndicatorEngineMixin:
    """Computes live RSI/ATR/TypicalMean/ORB indicators and 15m/1h MTF gates."""

    @staticmethod
    def _calc_ema(closes: List[float], period: int) -> float:
        return MultiTimeframeEngine.calc_ema(closes, period)

    def _update_mtf_regimes(self, new_1m_bar: Dict[str, Any]) -> None:
        self.mtf_engine.candles_5m = self.candles_5m
        self.mtf_engine.candles_15m = self.candles_15m
        self.mtf_engine.candles_1h = self.candles_1h
        self.mtf_engine.update_from_1m_bar(new_1m_bar)
        self.candles_5m = self.mtf_engine.candles_5m
        self.candles_15m = self.mtf_engine.candles_15m
        self.candles_1h = self.mtf_engine.candles_1h
        self.htf_ema_50 = self.mtf_engine.htf_ema_50
        self.htf_ema_200 = self.mtf_engine.htf_ema_200
        self.htf_bias = self.mtf_engine.htf_bias

    def is_entry_permitted_by_mtf(self, side: OrderSide) -> bool:
        if self.htf_bias == "BEARISH" and side == OrderSide.BUY:
            return False
        if self.htf_bias == "BULLISH" and side == OrderSide.SELL:
            return False
        return True

    def _chop_gate_blocks(self) -> bool:
        closed = self.candles_15m[:-1]
        if len(closed) <= CHOP_GATE_WINDOW_BARS:
            return False
        closes = [float(b["c"]) for b in closed[-CHOP_GATE_WINDOW_BARS - 1:]]
        return efficiency_ratio(closes) < CHOP_GATE_ER_THRESHOLD

    def _seed_chop_gate_buckets(self, seed_bars: List[Dict[str, Any]], warmup_start_ts: float) -> int:
        if not seed_bars or not warmup_start_ts:
            return 0
        chain: List[Dict[str, Any]] = []
        expect = float(warmup_start_ts) - 60.0
        for b in reversed(seed_bars):
            try:
                t = float(b["t"])
            except (KeyError, TypeError, ValueError):
                break
            if abs(t - expect) < 1.0:
                chain.append(b)
                expect -= 60.0
            else:
                break
        chain.reverse()
        if not chain:
            return 0
        fed = 0
        for b in chain:
            try:
                bar = {
                    "t": float(b["t"]),
                    "o": float(b["o"]),
                    "h": float(b["h"]),
                    "l": float(b["l"]),
                    "c": float(b["c"]),
                    "v": float(b.get("v", 0.0)),
                }
            except (KeyError, TypeError, ValueError):
                continue
            self.mtf_engine.update_from_1m_bar(bar)
            fed += 1
        if fed == 0:
            return 0
        self.candles_5m = self.mtf_engine.candles_5m
        self.candles_15m = self.mtf_engine.candles_15m
        self.candles_1h = self.mtf_engine.candles_1h
        self.htf_ema_50 = self.mtf_engine.htf_ema_50
        self.htf_ema_200 = self.mtf_engine.htf_ema_200
        self.htf_bias = self.mtf_engine.htf_bias
        return fed

    def _seed_mtf_1h_history(self) -> None:
        if self._stop_event.is_set() or not self._is_current_generation():
            return
        ticker = parse_symbol_pairs(getattr(self, "symbol", "ETH/USD"))["yahoo"]
        try:
            bars = self._fetch_historical_bars(ticker=ticker, period="14d", interval="1h")
        except Exception as e:
            logger.debug("MTF 1h history seed skipped (fetch failed): %s", e)
            return
        if self._stop_event.is_set() or not self._is_current_generation():
            return
        if not bars:
            logger.debug("MTF 1h history seed skipped (no bars returned).")
            return
        buckets = [
            {
                "t": float(b.timestamp),
                "o": float(b.open),
                "h": float(b.high),
                "l": float(b.low),
                "c": float(b.close),
                "v": float(b.volume),
            }
            for b in bars
        ]
        buckets.sort(key=lambda b: b["t"])
        if time.time() - buckets[-1]["t"] > MTF_SEED_STALE_SEC:
            logger.debug("MTF 1h history seed skipped (last bar too old).")
            return
        if len(buckets) < MultiTimeframeEngine.MIN_HTF_BARS:
            logger.debug("MTF 1h history seed skipped (%d bars < %d).", len(buckets), MultiTimeframeEngine.MIN_HTF_BARS)
            return
        with self.lock:
            if self._stop_event.is_set() or not self._is_current_generation():
                return
            bias = self.mtf_engine.seed_1h_buckets(buckets)
            self.candles_1h = self.mtf_engine.candles_1h
            self.htf_ema_50 = self.mtf_engine.htf_ema_50
            self.htf_ema_200 = self.mtf_engine.htf_ema_200
            self.htf_bias = bias
            logger.info("MTF 1h history seeded: %d buckets, bias %s.", len(self.candles_1h), bias)

    def _update_candle(
        self,
        ts: float,
        close: Decimal,
        high: Optional[Decimal] = None,
        low: Optional[Decimal] = None,
        open_: Optional[Decimal] = None,
    ) -> None:
        """Aggregates a bar or tick into its 1m candle, updates MTF regimes, and queues/persists closed bars."""
        c = float(close)
        h = float(high) if high is not None else c
        lo = float(low) if low is not None else c
        if not (math.isfinite(ts) and math.isfinite(c) and math.isfinite(h) and math.isfinite(lo)):
            return
        if c <= 0.0 or h <= 0.0 or lo <= 0.0:
            return
        minute = float(int(ts // 60) * 60)
        if self.candles and minute < self.candles[-1]["t"]:
            return
        if self.candles and self.candles[-1]["t"] == minute:
            cur = self.candles[-1]
            cur["h"] = max(cur["h"], h)
            cur["l"] = min(cur["l"], lo)
            cur["c"] = c
        elif not self.candles or minute > self.candles[-1]["t"]:
            o = float(open_) if (open_ is not None and math.isfinite(float(open_)) and float(open_) > 0.0) else (self.candles[-1]["c"] if self.candles else c)
            self.candles.append({"t": minute, "o": o, "h": max(h, o), "l": min(lo, o), "c": c})
            if len(self.candles) > self.max_candles:
                del self.candles[:-self.max_candles]

        if self.candles:
            self._update_mtf_regimes(self.candles[-1])
            if self.is_bootstrapped and self._is_current_generation() and len(self.candles) >= 2:
                closed = self.candles[-2]
                if closed["t"] != self._last_saved_candle_t:
                    self._last_saved_candle_t = closed["t"]
                    if getattr(self, "_defer_sql_flush", False):
                        self._pending_sql_candles.append(dict(closed))
                    else:
                        try:
                            self.storage.save_candle(closed)
                        except Exception as e:
                            logger.debug("SQLite candle save skipped: %s", e)

    def _recompute_orb_range(self, cs: List[Dict[str, float]]) -> None:
        if not cs:
            return
        day = datetime.fromtimestamp(float(cs[-1]["t"]), timezone.utc).date()
        if self._orb_session_day != day:
            self._orb_session_day = day
            self._orb_range_frozen = False
        if self._orb_range_frozen:
            return
        day_bars = [
            b for b in cs
            if datetime.fromtimestamp(float(b["t"]), timezone.utc).date() == day
        ]
        if not day_bars:
            return
        first_15 = day_bars[:15]
        self.live_orb_high = Decimal(str(round(max(x["h"] for x in first_15), 2)))
        self.live_orb_low = Decimal(str(round(min(x["l"] for x in first_15), 2)))
        if len(day_bars) >= 15:
            self._orb_range_frozen = True

    def _recompute_candle_indicators(self, period: int = 14) -> None:
        """Wilder RSI(14), ATR(14), ORB range, and session typical-price mean."""
        cs = self.candles
        if not cs:
            return
        self._recompute_orb_range(cs)
        cum_p = sum((x["h"] + x["l"] + x["c"]) / 3.0 for x in cs)
        mean_val = cum_p / len(cs)
        if math.isfinite(mean_val) and mean_val > 0.0:
            self.live_typical_mean = Decimal(str(round(mean_val, 2)))

        if len(cs) < period + 1:
            return

        trs = [
            max(cs[i]["h"] - cs[i]["l"], abs(cs[i]["h"] - cs[i - 1]["c"]), abs(cs[i]["l"] - cs[i - 1]["c"]))
            for i in range(1, len(cs))
        ]

        closes = [x["c"] for x in cs]
        avg_g = sum(max(0.0, closes[i] - closes[i - 1]) for i in range(1, period + 1)) / period
        avg_l = sum(max(0.0, closes[i - 1] - closes[i]) for i in range(1, period + 1)) / period
        for i in range(period + 1, len(closes)):
            d = closes[i] - closes[i - 1]
            avg_g = (avg_g * (period - 1) + max(0.0, d)) / period
            avg_l = (avg_l * (period - 1) + max(0.0, -d)) / period
        if avg_l == 0 and avg_g == 0:
            rsi = 50.0
        elif avg_l == 0:
            rsi = 100.0
        elif avg_g == 0:
            rsi = 0.0
        else:
            rs = avg_g / avg_l
            rsi = 100.0 - (100.0 / (1.0 + rs))

        atr = sum(trs[:period]) / period
        for tr in trs[period:]:
            atr = (atr * (period - 1) + tr) / period

        if math.isfinite(rsi):
            self.live_rsi = Decimal(str(round(rsi, 2)))
        if math.isfinite(atr):
            self.live_atr = max(Decimal("1.50"), Decimal(str(round(atr, 2))))
            self.broker.current_atr = self.live_atr
