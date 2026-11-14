"""
src/data/mtf_engine.py - Multi-Timeframe (MTF) Trend Confluence Engine
Implements Phase 4 (P2) & Phase 6 (P3): 1m / 5m / 15m / 1h bar aggregation and 1h EMA trend gatekeeper.
"""
from __future__ import annotations

from typing import Any, Dict, List
from src.arena.order import OrderSide


class MultiTimeframeEngine:
    """
    Synthesizes 5-minute, 15-minute, and 1-hour higher-timeframe OHLCV bars from 1-minute candles
    and evaluates 1h 50/200 EMA structural trend bias.
    """

    # Minimum 1h buckets for a regime (recompute_regime stays NEUTRAL below).
    MIN_HTF_BARS = 50
    # Minimum median inter-bar gap for a seed to be trusted as 1h history.
    # Real 1h bars are 3600 s apart; 1m bars (the warmup / test fixtures)
    # are 60 s apart and must never be mistaken for 1h history.
    MIN_SEED_MEDIAN_GAP_SEC = 1800.0

    def __init__(self, max_htf_bars: int = 240) -> None:
        self.max_htf_bars = max_htf_bars
        self.candles_5m: List[Dict[str, float]] = []
        self.candles_15m: List[Dict[str, float]] = []
        self.candles_1h: List[Dict[str, float]] = []
        self.htf_ema_50: float = 0.0
        self.htf_ema_200: float = 0.0
        self.htf_bias: str = "NEUTRAL"

    @staticmethod
    def calc_ema(closes: List[float], period: int) -> float:
        if not closes:
            return 0.0
        alpha = 2.0 / (period + 1.0)
        ema = float(closes[0])
        for c in closes[1:]:
            ema = (float(c) * alpha) + (ema * (1.0 - alpha))
        return round(ema, 2)

    @staticmethod
    def _upsert_bucket(
        bucket_list: List[Dict[str, float]],
        bucket_seconds: int,
        bar_1m: Dict[str, Any],
        max_len: int,
    ) -> None:
        ts = float(bar_1m["t"])
        slot = float(int(ts // bucket_seconds) * bucket_seconds)
        o = float(bar_1m["o"])
        h = float(bar_1m["h"])
        lo = float(bar_1m["l"])
        c = float(bar_1m["c"])
        v = float(bar_1m.get("v", 0.0))

        if bucket_list and bucket_list[-1]["t"] == slot:
            cur = bucket_list[-1]
            cur["h"] = max(cur["h"], h)
            cur["l"] = min(cur["l"], lo)
            cur["c"] = c
            cur["v"] = cur.get("v", 0.0) + v
        elif not bucket_list or slot > bucket_list[-1]["t"]:
            bucket_list.append({"t": slot, "o": o, "h": h, "l": lo, "c": c, "v": v})
            if len(bucket_list) > max_len:
                del bucket_list[:-max_len]

    def update_from_1m_bar(self, new_1m_bar: Dict[str, Any]) -> str:
        """
        Aggregates a 1m bar into 5m, 15m, and 1h buckets and updates the 1h EMA trend regime.
        """
        self._upsert_bucket(self.candles_5m, 300, new_1m_bar, self.max_htf_bars)
        self._upsert_bucket(self.candles_15m, 900, new_1m_bar, self.max_htf_bars)
        self._upsert_bucket(self.candles_1h, 3600, new_1m_bar, self.max_htf_bars)
        return self.recompute_regime()

    def recompute_regime(self) -> str:
        if len(self.candles_1h) >= self.MIN_HTF_BARS:
            closes = [float(c["c"]) for c in self.candles_1h]
            self.htf_ema_50 = self.calc_ema(closes, 50)
            self.htf_ema_200 = self.calc_ema(closes, 200) if len(closes) >= 200 else self.htf_ema_50
            last_close = closes[-1]
            if last_close > self.htf_ema_50 and self.htf_ema_50 >= self.htf_ema_200:
                self.htf_bias = "BULLISH"
            elif last_close < self.htf_ema_50 and self.htf_ema_50 <= self.htf_ema_200:
                self.htf_bias = "BEARISH"
            else:
                self.htf_bias = "BULLISH" if last_close > self.htf_ema_50 else "BEARISH"
        else:
            self.htf_bias = "NEUTRAL"
        return self.htf_bias

    def seed_1h_buckets(self, buckets: List[Dict[str, float]]) -> str:
        """
        Seed the 1h bucket history from real fetched 1h bars (audit 2.3).

        The 1m-derived buckets can never reach the regime threshold (200
        1m bars span ~3.3 h), so without a seed htf_bias is NEUTRAL forever
        and the entry veto is dead code. Buckets are dicts with t/o/h/l/c/v
        keys, normally converted from ETHFeed 1h CandleBars.

        Validation -- any failure leaves the current buckets and bias
        untouched and returns the current bias:
        - malformed rows (missing / non-positive o/h/l/c, bad timestamp)
          are dropped;
        - the median inter-bar gap must be >= MIN_SEED_MEDIAN_GAP_SEC,
          so 1m-spaced bars can never pose as 1h history;
        - fewer than MIN_HTF_BARS buckets stays NEUTRAL, exactly like
          recompute_regime.

        The list is replaced in place (clear + extend) so aliases held by
        the engine stay valid, and only the most recent max_htf_bars are
        kept.
        """
        clean: List[Dict[str, float]] = []
        for b in buckets or []:
            try:
                t = float(b["t"])
                o = float(b["o"])
                h = float(b["h"])
                lo = float(b["l"])
                c = float(b["c"])
                v = float(b.get("v", 0.0))
            except (KeyError, TypeError, ValueError):
                continue
            if t <= 0.0 or o <= 0.0 or h <= 0.0 or lo <= 0.0 or c <= 0.0:
                continue
            clean.append({"t": t, "o": o, "h": h, "l": lo, "c": c, "v": v})
        clean.sort(key=lambda b: b["t"])
        dedup: List[Dict[str, float]] = []
        for b in clean:
            if dedup and dedup[-1]["t"] == b["t"]:
                dedup[-1] = b
            else:
                dedup.append(b)
        if len(dedup) < self.MIN_HTF_BARS:
            return self.htf_bias
        if len(dedup) >= 2:
            gaps = sorted(dedup[i + 1]["t"] - dedup[i]["t"] for i in range(len(dedup) - 1))
            median_gap = gaps[len(gaps) // 2]
            if median_gap < self.MIN_SEED_MEDIAN_GAP_SEC:
                return self.htf_bias
        self.candles_1h.clear()
        self.candles_1h.extend(dedup[-self.max_htf_bars:])
        return self.recompute_regime()

    def is_entry_permitted(self, side: OrderSide) -> bool:
        """
        Vetoes 1m breakout entries that trade directly into higher-timeframe opposition.
        """
        if self.htf_bias == "BEARISH" and side == OrderSide.BUY:
            return False
        if self.htf_bias == "BULLISH" and side == OrderSide.SELL:
            return False
        return True

