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

    def get_chop_er_20(self) -> Optional[float]:
        """Returns Efficiency Ratio over the trailing closed 15m bars, or None while warming up."""
        closed = self.candles_15m[:-1]
        if len(closed) <= CHOP_GATE_WINDOW_BARS:
            return None
        closes = [float(b["c"]) for b in closed[-CHOP_GATE_WINDOW_BARS - 1:]]
        return float(efficiency_ratio(closes))

    def _chop_gate_blocks(self) -> bool:
        er = self.get_chop_er_20()
        return er is not None and er < CHOP_GATE_ER_THRESHOLD

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
                bt = float(b["t"])
                bo = float(b["o"])
                bh = float(b["h"])
                bl = float(b["l"])
                bc = float(b["c"])
                bv = float(b.get("v", 0.0))
            except (KeyError, TypeError, ValueError):
                continue
            if not (
                math.isfinite(bt) and math.isfinite(bo) and math.isfinite(bh)
                and math.isfinite(bl) and math.isfinite(bc) and math.isfinite(bv)
            ):
                continue
            if bo <= 0.0 or bh <= 0.0 or bl <= 0.0 or bc <= 0.0:
                continue
            bar = {"t": bt, "o": bo, "h": bh, "l": bl, "c": bc, "v": max(0.0, bv)}
            self.mtf_engine.update_from_1m_bar(bar, recompute=False)
            fed += 1
        if fed == 0:
            return 0
        self.mtf_engine.recompute_regime()
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
        buckets = []
        for b in bars:
            try:
                bt = float(b.timestamp)
                bo = float(b.open)
                bh = float(b.high)
                bl = float(b.low)
                bc = float(b.close)
                bv = float(b.volume)
            except (AttributeError, TypeError, ValueError):
                continue
            if not (
                math.isfinite(bt) and math.isfinite(bo) and math.isfinite(bh)
                and math.isfinite(bl) and math.isfinite(bc) and math.isfinite(bv)
            ):
                continue
            if bt <= 0.0 or bo <= 0.0 or bh <= 0.0 or bl <= 0.0 or bc <= 0.0 or bv < 0.0:
                continue
            buckets.append({"t": bt, "o": bo, "h": bh, "l": bl, "c": bc, "v": bv})
        if not buckets:
            logger.debug("MTF 1h history seed skipped (no valid bars).")
            return
        buckets.sort(key=lambda b: b["t"])
        last_t = buckets[-1]["t"]
        if not math.isfinite(last_t) or (time.time() - last_t) > MTF_SEED_STALE_SEC:
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
        volume: Optional[Decimal] = None,
    ) -> None:
        """Aggregates a bar or tick into its 1m candle, updates MTF regimes, and queues/persists closed bars."""
        c = float(close)
        h = float(high) if high is not None else c
        lo = float(low) if low is not None else c
        if not (math.isfinite(ts) and math.isfinite(c) and math.isfinite(h) and math.isfinite(lo)):
            return
        if c <= 0.0 or h <= 0.0 or lo <= 0.0:
            return
        vol_f: Optional[float] = None
        if volume is not None:
            try:
                vf = float(volume)
                if math.isfinite(vf) and vf >= 0.0:
                    vol_f = vf
            except (TypeError, ValueError):
                vol_f = None
        minute = float(int(ts // 60) * 60)
        bar_h = max(h, lo) if high is not None else max(h, lo, c)
        bar_l = min(h, lo) if low is not None else min(h, lo, c)
        if self.candles and minute < self.candles[-1]["t"]:
            return
        if self.candles and self.candles[-1]["t"] == minute:
            cur = self.candles[-1]
            cur["h"] = max(cur["h"], bar_h)
            cur["l"] = min(cur["l"], bar_l)
            cur["c"] = c
            if vol_f is not None:
                cur["v"] = vol_f
        elif not self.candles or minute > self.candles[-1]["t"]:
            o = float(open_) if (open_ is not None and math.isfinite(float(open_)) and float(open_) > 0.0) else (self.candles[-1]["c"] if self.candles else c)
            bar_dict: Dict[str, float] = {
                "t": minute,
                "o": o,
                "h": max(bar_h, o) if high is None else bar_h,
                "l": min(bar_l, o) if low is None else bar_l,
                "c": c,
            }
            if vol_f is not None:
                bar_dict["v"] = vol_f
            self.candles.append(bar_dict)
            if len(self.candles) > self.max_candles:
                del self.candles[:-self.max_candles]
            self._ind_prefix_cache = None

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

    def _recompute_orb_range(self, cs: List[Dict[str, float]], has_forming_bar: bool = False) -> None:
        if not cs:
            return
        last_ts = float(cs[-1]["t"])
        day_idx = int(last_ts // 86400)
        prev_day_idx = getattr(self, "_orb_session_day_idx", None)
        if prev_day_idx != day_idx:
            day = datetime.fromtimestamp(last_ts, timezone.utc).date()
            if self._orb_session_day != day:
                self._orb_session_day = day
                self._orb_range_frozen = False
            self._orb_session_day_idx = day_idx
        if self._orb_range_frozen:
            return
        day_bars = [b for b in cs if int(float(b["t"]) // 86400) == day_idx]
        if not day_bars:
            return
        first_15 = day_bars[:15]
        self.live_orb_high = Decimal(str(round(max(x["h"] for x in first_15), 2)))
        self.live_orb_low = Decimal(str(round(min(x["l"] for x in first_15), 2)))
        freeze_at = 16 if has_forming_bar else 15
        if len(day_bars) >= freeze_at:
            self._orb_range_frozen = True

    def _recompute_candle_indicators(self, period: int = 14, has_forming_bar: bool = False) -> None:
        """Wilder RSI(14), ATR(14), ORB range, and session typical-price mean (O(1) cached over closed bars)."""
        cs = self.candles
        if not cs:
            return
        self._recompute_orb_range(cs, has_forming_bar=has_forming_bar)

        n = len(cs)
        last_bar = cs[-1]
        last_typ = (last_bar["h"] + last_bar["l"] + last_bar["c"]) / 3.0

        if n < period + 1:
            cum_p = sum((x["h"] + x["l"] + x["c"]) / 3.0 for x in cs)
            mean_val = cum_p / n
            if math.isfinite(mean_val) and mean_val > 0.0:
                self.live_typical_mean = Decimal(str(round(mean_val, 2)))
            return

        prev_bar = cs[-2]
        prefix_key = (
            id(cs),
            n,
            period,
            cs[0]["t"],
            cs[0]["c"],
            prev_bar["t"],
            prev_bar["c"],
            prev_bar["h"],
            prev_bar["l"],
        )
        cache = getattr(self, "_ind_prefix_cache", None)

        if n == period + 1:
            cum_p = sum((x["h"] + x["l"] + x["c"]) / 3.0 for x in cs)
            mean_val = cum_p / n
            if math.isfinite(mean_val) and mean_val > 0.0:
                self.live_typical_mean = Decimal(str(round(mean_val, 2)))

            avg_g = sum(max(0.0, cs[i]["c"] - cs[i - 1]["c"]) for i in range(1, period + 1)) / period
            avg_l = sum(max(0.0, cs[i - 1]["c"] - cs[i]["c"]) for i in range(1, period + 1)) / period
            atr = sum(
                max(cs[i]["h"] - cs[i]["l"], abs(cs[i]["h"] - cs[i - 1]["c"]), abs(cs[i]["l"] - cs[i - 1]["c"]))
                for i in range(1, period + 1)
            ) / period
        else:
            if cache is not None and cache[0] == prefix_key:
                _, typ_sum_prev, avg_g_prev, avg_l_prev, atr_prev = cache
            else:
                typ_sum_prev = sum((cs[i]["h"] + cs[i]["l"] + cs[i]["c"]) / 3.0 for i in range(n - 1))
                avg_g_prev = sum(max(0.0, cs[i]["c"] - cs[i - 1]["c"]) for i in range(1, period + 1)) / period
                avg_l_prev = sum(max(0.0, cs[i - 1]["c"] - cs[i]["c"]) for i in range(1, period + 1)) / period
                for i in range(period + 1, n - 1):
                    d = cs[i]["c"] - cs[i - 1]["c"]
                    avg_g_prev = (avg_g_prev * (period - 1) + max(0.0, d)) / period
                    avg_l_prev = (avg_l_prev * (period - 1) + max(0.0, -d)) / period

                atr_prev = sum(
                    max(cs[i]["h"] - cs[i]["l"], abs(cs[i]["h"] - cs[i - 1]["c"]), abs(cs[i]["l"] - cs[i - 1]["c"]))
                    for i in range(1, period + 1)
                ) / period
                for i in range(period + 1, n - 1):
                    tr_i = max(
                        cs[i]["h"] - cs[i]["l"],
                        abs(cs[i]["h"] - cs[i - 1]["c"]),
                        abs(cs[i]["l"] - cs[i - 1]["c"]),
                    )
                    atr_prev = (atr_prev * (period - 1) + tr_i) / period

                self._ind_prefix_cache = (prefix_key, typ_sum_prev, avg_g_prev, avg_l_prev, atr_prev)

            mean_val = (typ_sum_prev + last_typ) / n
            if math.isfinite(mean_val) and mean_val > 0.0:
                self.live_typical_mean = Decimal(str(round(mean_val, 2)))

            d_last = last_bar["c"] - prev_bar["c"]
            avg_g = (avg_g_prev * (period - 1) + max(0.0, d_last)) / period
            avg_l = (avg_l_prev * (period - 1) + max(0.0, -d_last)) / period
            tr_last = max(
                last_bar["h"] - last_bar["l"],
                abs(last_bar["h"] - prev_bar["c"]),
                abs(last_bar["l"] - prev_bar["c"]),
            )
            atr = (atr_prev * (period - 1) + tr_last) / period

        if avg_l == 0 and avg_g == 0:
            rsi = 50.0
        elif avg_l == 0:
            rsi = 100.0
        elif avg_g == 0:
            rsi = 0.0
        else:
            rs = avg_g / avg_l
            rsi = 100.0 - (100.0 / (1.0 + rs))

        if math.isfinite(rsi):
            self.live_rsi = Decimal(str(round(rsi, 2)))
        if math.isfinite(atr):
            self.live_atr = max(Decimal("1.50"), Decimal(str(round(atr, 2))))
            self.broker.current_atr = self.live_atr
