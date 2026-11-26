"""
src/gui/view_model.py - State Extraction & Diff-Based JSON ViewModel Publisher
Implements Phase 6 (P3): Engine Modularization & State Delta Streaming over IPC.
"""
from __future__ import annotations

import copy
import hashlib
import json
import logging
import math
import threading
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from src.arena.order import OrderSide, PositionSide
from src.data.timemachine import CHOP_GATE_ER_THRESHOLD
from src.intelligence.config_manager import DEFAULT_GEMINI_MODEL


logger = logging.getLogger(__name__)

_SHALLOW_DELTA_DICT_LIST_KEYS = ("candles", "candles_5m", "candles_15m", "fills")
_SHALLOW_DELTA_SCALAR_LIST_KEYS = ("price_history", "ema_fast_history", "ema_slow_history")
_FAST_CLONE_DELTA_KEYS = (
    "strategies",
    "evolution_events",
    "risk_telemetry",
    "tv_hub",
    "ui_prefs",
    "mtf",
    "quant_meta",
    "omni_meta",
    "macro_commander",
)
_SHALLOW_DELTA_KEYS = frozenset(
    _SHALLOW_DELTA_DICT_LIST_KEYS + _SHALLOW_DELTA_SCALAR_LIST_KEYS + _FAST_CLONE_DELTA_KEYS
)

_HEATMAP_STRATEGIES = ("comp_agg", "comp_cons", "comp_trail", "comp_orb", "comp_vwap")
_HEATMAP_LABELS = ("AGG", "CONS", "TRAIL", "ORB", "MEAN")


def _clone_json_tree(obj: Any) -> Any:
    """Fast recursive clone for JSON-primitive dict/list snapshots without copy.deepcopy memo overhead."""
    if isinstance(obj, dict):
        return {k: _clone_json_tree(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clone_json_tree(item) for item in obj]
    if isinstance(obj, tuple):
        return [_clone_json_tree(item) for item in obj]
    return obj


def _safe_fmt_hms(ts: Any) -> str:
    """Format an epoch timestamp as HH:MM:SS without raising on Windows invalid/negative dates."""
    try:
        val = float(ts)
        if not math.isfinite(val) or val < 0.0:
            return ""
        return time.strftime("%H:%M:%S", time.localtime(val))
    except (OSError, OverflowError, ValueError, TypeError):
        return ""


class ViewModelPublisher:
    """
    Constructs JSON-safe UI view models and computes incremental state deltas
    by tracking candle signatures and fill sequence watermarks across ticks.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.last_candle_sig: Optional[str] = None
        self.last_candle_5m_sig: Optional[str] = None
        self.last_candle_15m_sig: Optional[str] = None
        self.last_fill_seq: int = -1
        self.last_fill_sig: Optional[Tuple[int, int, bool, str]] = None
        self.last_history_sig: Optional[Tuple[Any, ...]] = None
        self.last_intel_events_sig: Optional[Tuple[Any, ...]] = None

    def reset(self) -> None:
        with self._lock:
            self.last_candle_sig = None
            self.last_candle_5m_sig = None
            self.last_candle_15m_sig = None
            self.last_fill_seq = -1
            self.last_fill_sig = None
            self.last_history_sig = None
            self.last_intel_events_sig = None

    @staticmethod
    def finite(val: Any, default: float = 0.0) -> float:
        """JSON-safe float (WebView JSON.parse rejects NaN / Infinity)."""
        try:
            f = float(val)
        except (TypeError, ValueError):
            return default
        return f if math.isfinite(f) else default

    @staticmethod
    def compute_candle_signature(candles: List[Dict[str, Any]]) -> str:
        if not candles:
            return "empty"
        last = candles[-1]
        prev = candles[-2] if len(candles) >= 2 else None
        prev_sig = f"{prev.get('t')}:{prev.get('c')}" if isinstance(prev, dict) else ""
        first_t = candles[0].get("t", 0)
        return f"{len(candles)}:{first_t}:{prev_sig}:{last.get('t')}:{last.get('o')}:{last.get('h')}:{last.get('l')}:{last.get('c')}"

    @staticmethod
    def compute_fill_signature(fills: List[Dict[str, Any]]) -> Tuple[int, int, bool, str]:
        if not fills:
            return (0, 0, False, "")
        top = fills[0]
        return (
            len(fills),
            int(top.get("seq", 0) or 0),
            bool(top.get("is_live", False)),
            str(top.get("time", "")),
        )

    @staticmethod
    def compute_history_signature(state: Dict[str, Any]) -> Tuple[Any, ...]:
        ph = state.get("price_history") or []
        ef = state.get("ema_fast_history") or []
        es = state.get("ema_slow_history") or []
        return (
            len(ph), ph[0] if ph else None, ph[-1] if ph else None,
            len(ef), ef[-1] if ef else None,
            len(es), es[-1] if es else None,
        )

    @staticmethod
    def compute_intel_events_signature(state: Dict[str, Any]) -> Tuple[Any, ...]:
        intel = state.get("intel_hub")
        if not isinstance(intel, dict):
            return ()
        events = intel.get("events")
        if not isinstance(events, list):
            return ()
        sig = []
        for e in events:
            if not isinstance(e, dict):
                continue
            acts = e.get("strategy_actions")
            act_sig = (
                tuple(
                    (a.get("strat_id"), a.get("action"), a.get("time"))
                    if isinstance(a, dict)
                    else str(a)
                    for a in acts
                )
                if isinstance(acts, list)
                else ()
            )
            sig.append(
                (
                    e.get("id"),
                    e.get("event_ts") if "event_ts" in e else e.get("timestamp"),
                    e.get("headline") if "headline" in e else e.get("raw_title"),
                    e.get("summary"),
                    e.get("article_state"),
                    e.get("article_progress"),
                    e.get("article_stage"),
                    e.get("urgency") if "urgency" in e else e.get("urgency_score"),
                    e.get("sentiment"),
                    act_sig,
                )
            )
        return tuple(sig)

    def compute_delta_payload(
        self, full_state: Dict[str, Any], force_full: bool = False
    ) -> Dict[str, Any]:
        """
        Produces an incremental state-delta dictionary from a full UI state snapshot.
        - Omits unchanged heavy arrays (`candles`, `fills`, price/EMA history, `intel_hub.events`)
          and sets the corresponding `*_unchanged` flags.
        """
        delta = dict(full_state)
        candles = full_state.get("candles") or []
        fills = full_state.get("fills") or []

        candle_sig = self.compute_candle_signature(candles)
        c5_sig: Optional[str] = (
            self.compute_candle_signature(full_state["candles_5m"] or [])
            if "candles_5m" in full_state
            else None
        )
        c15_sig: Optional[str] = (
            self.compute_candle_signature(full_state["candles_15m"] or [])
            if "candles_15m" in full_state
            else None
        )
        fill_sig = self.compute_fill_signature(fills)
        history_sig = self.compute_history_signature(full_state)
        intel_sig = self.compute_intel_events_signature(full_state)
        top_fill_seq = fill_sig[1]

        with self._lock:
            if force_full or self.last_candle_sig is None:
                self.last_candle_sig = candle_sig
                self.last_candle_5m_sig = c5_sig
                self.last_candle_15m_sig = c15_sig
                self.last_fill_seq = top_fill_seq
                self.last_fill_sig = fill_sig
                self.last_history_sig = history_sig
                self.last_intel_events_sig = intel_sig
                delta["is_delta"] = False
                delta["candles_unchanged"] = False
                delta["candles_5m_unchanged"] = False
                delta["candles_15m_unchanged"] = False
                delta["fills_unchanged"] = False
                delta["history_unchanged"] = False
                delta["intel_events_unchanged"] = False
                return delta

            candles_same = candle_sig == self.last_candle_sig
            c5_same = (
                c5_sig is not None
                and self.last_candle_5m_sig is not None
                and c5_sig == self.last_candle_5m_sig
            )
            c15_same = (
                c15_sig is not None
                and self.last_candle_15m_sig is not None
                and c15_sig == self.last_candle_15m_sig
            )
            fills_same = fill_sig == self.last_fill_sig
            history_same = history_sig == self.last_history_sig
            intel_same = (
                isinstance(full_state.get("intel_hub"), dict)
                and "events" in full_state["intel_hub"]
                and intel_sig == self.last_intel_events_sig
            )

            self.last_candle_sig = candle_sig
            self.last_candle_5m_sig = c5_sig
            self.last_candle_15m_sig = c15_sig
            self.last_fill_seq = top_fill_seq
            self.last_fill_sig = fill_sig
            self.last_history_sig = history_sig
            self.last_intel_events_sig = intel_sig

        delta["is_delta"] = bool(candles_same or c5_same or c15_same or fills_same or history_same or intel_same)
        delta["candles_unchanged"] = candles_same
        delta["candles_5m_unchanged"] = c5_same
        delta["candles_15m_unchanged"] = c15_same
        delta["fills_unchanged"] = fills_same
        delta["history_unchanged"] = history_same
        delta["intel_events_unchanged"] = intel_same

        if candles_same:
            delta.pop("candles", None)
        if c5_same:
            delta.pop("candles_5m", None)
        if c15_same:
            delta.pop("candles_15m", None)
        if fills_same:
            delta.pop("fills", None)
        if history_same:
            delta.pop("price_history", None)
            delta.pop("ema_fast_history", None)
            delta.pop("ema_slow_history", None)
        if intel_same and isinstance(delta.get("intel_hub"), dict):
            intel_copy = dict(delta["intel_hub"])
            intel_copy.pop("events", None)
            delta["intel_hub"] = intel_copy

        return delta

    def compute_delta_from_snapshot(
        self, snapshot: Dict[str, Any], force_full: bool = False
    ) -> Dict[str, Any]:
        """
        Audit §5.2: same output as compute_delta_payload, but any unchanged
        heavy arrays (`candles`, `candles_5m`, `candles_15m`, `fills`, price/EMA history, `intel_hub.events`)
        are excluded BEFORE cloning instead of popped after it. The snapshot
        itself is never mutated.
        """
        candles = snapshot.get("candles") or []
        fills = snapshot.get("fills") or []
        candle_sig = self.compute_candle_signature(candles)
        c5_sig: Optional[str] = (
            self.compute_candle_signature(snapshot["candles_5m"] or [])
            if "candles_5m" in snapshot
            else None
        )
        c15_sig: Optional[str] = (
            self.compute_candle_signature(snapshot["candles_15m"] or [])
            if "candles_15m" in snapshot
            else None
        )
        fill_sig = self.compute_fill_signature(fills)
        history_sig = self.compute_history_signature(snapshot)
        intel_sig = self.compute_intel_events_signature(snapshot)
        top_fill_seq = fill_sig[1]

        with self._lock:
            if force_full or self.last_candle_sig is None:
                self.last_candle_sig = candle_sig
                self.last_candle_5m_sig = c5_sig
                self.last_candle_15m_sig = c15_sig
                self.last_fill_seq = top_fill_seq
                self.last_fill_sig = fill_sig
                self.last_history_sig = history_sig
                self.last_intel_events_sig = intel_sig
                is_first = True
                candles_same = False
                c5_same = False
                c15_same = False
                fills_same = False
                history_same = False
                intel_same = False
            else:
                is_first = False
                candles_same = candle_sig == self.last_candle_sig
                c5_same = (
                    c5_sig is not None
                    and self.last_candle_5m_sig is not None
                    and c5_sig == self.last_candle_5m_sig
                )
                c15_same = (
                    c15_sig is not None
                    and self.last_candle_15m_sig is not None
                    and c15_sig == self.last_candle_15m_sig
                )
                fills_same = fill_sig == self.last_fill_sig
                history_same = history_sig == self.last_history_sig
                intel_same = (
                    isinstance(snapshot.get("intel_hub"), dict)
                    and "events" in snapshot["intel_hub"]
                    and intel_sig == self.last_intel_events_sig
                )
                self.last_candle_sig = candle_sig
                self.last_candle_5m_sig = c5_sig
                self.last_candle_15m_sig = c15_sig
                self.last_fill_seq = top_fill_seq
                self.last_fill_sig = fill_sig
                self.last_history_sig = history_sig
                self.last_intel_events_sig = intel_sig

        if is_first:
            delta = copy.deepcopy(snapshot)
            delta["is_delta"] = False
            delta["candles_unchanged"] = False
            delta["candles_5m_unchanged"] = False
            delta["candles_15m_unchanged"] = False
            delta["fills_unchanged"] = False
            delta["history_unchanged"] = False
            delta["intel_events_unchanged"] = False
            return delta

        omit = set(_SHALLOW_DELTA_KEYS)
        if intel_same:
            omit.add("intel_hub")

        delta = copy.deepcopy({k: v for k, v in snapshot.items() if k not in omit})
        for fk in _FAST_CLONE_DELTA_KEYS:
            if fk in snapshot:
                delta[fk] = _clone_json_tree(snapshot[fk])

        if not candles_same and "candles" in snapshot:
            delta["candles"] = _clone_json_tree(snapshot["candles"])
        for tf_key, same_flag in (("candles_5m", c5_same), ("candles_15m", c15_same)):
            if not same_flag and tf_key in snapshot:
                delta[tf_key] = _clone_json_tree(snapshot[tf_key])
        if not fills_same and "fills" in snapshot:
            delta["fills"] = _clone_json_tree(snapshot["fills"])
        if not history_same:
            for hk in _SHALLOW_DELTA_SCALAR_LIST_KEYS:
                if hk in snapshot:
                    hv = snapshot[hk]
                    delta[hk] = list(hv) if isinstance(hv, list) else _clone_json_tree(hv)

        if intel_same and isinstance(snapshot.get("intel_hub"), dict):
            delta["intel_hub"] = {
                k: _clone_json_tree(v) for k, v in snapshot["intel_hub"].items() if k != "events"
            }

        delta["is_delta"] = bool(candles_same or c5_same or c15_same or fills_same or history_same or intel_same)
        delta["candles_unchanged"] = candles_same
        delta["candles_5m_unchanged"] = c5_same
        delta["candles_15m_unchanged"] = c15_same
        delta["fills_unchanged"] = fills_same
        delta["history_unchanged"] = history_same
        delta["intel_events_unchanged"] = intel_same
        return delta


def _sanitize_candles_tail(src_candles: Any, limit: int = 150) -> List[Dict[str, float]]:
    fz = ViewModelPublisher.finite
    out: List[Dict[str, float]] = []
    if not isinstance(src_candles, list):
        return out
    for c in src_candles[-limit:]:
        if not isinstance(c, dict):
            continue
        out.append({
            "t": fz(c.get("t")),
            "o": fz(c.get("o")),
            "h": fz(c.get("h")),
            "l": fz(c.get("l")),
            "c": fz(c.get("c")),
        })
    return out


def _sanitize_candles_tail_cached(
    src_candles: Any,
    vm_cache: Optional[Dict[str, Any]],
    cache_prefix: str,
    limit: int = 150,
) -> List[Dict[str, float]]:
    """Prefix-cached candle tail sanitization shared across 1m, 5m, and 15m series."""
    if not isinstance(src_candles, list) or not src_candles:
        return []
    if vm_cache is None or len(src_candles) < 2:
        return _sanitize_candles_tail(src_candles, limit=limit)
    fz = ViewModelPublisher.finite
    tail = src_candles[-limit:]
    n_sc = len(tail)
    first_c = tail[0] if isinstance(tail[0], dict) else {}
    prev_c = tail[-2] if isinstance(tail[-2], dict) else {}
    prefix_key = (
        id(src_candles),
        n_sc,
        first_c.get("t"),
        prev_c.get("t"),
        prev_c.get("c"),
    )
    key_slot = f"{cache_prefix}_prefix_key"
    val_slot = f"{cache_prefix}_prefix"
    if vm_cache.get(key_slot) == prefix_key:
        out = [dict(c) for c in vm_cache[val_slot]]
    else:
        out = _sanitize_candles_tail(tail[:-1], limit=limit)
        vm_cache[key_slot] = prefix_key
        vm_cache[val_slot] = [dict(c) for c in out]
    last_c = tail[-1]
    if isinstance(last_c, dict):
        out.append({
            "t": fz(last_c.get("t")),
            "o": fz(last_c.get("o")),
            "h": fz(last_c.get("h")),
            "l": fz(last_c.get("l")),
            "c": fz(last_c.get("c")),
        })
    return out


def _safe_int_val(val: Any, default: int = 0) -> int:
    if isinstance(val, bool):
        return default
    try:
        f = float(val)
        return int(f) if math.isfinite(f) else default
    except (TypeError, ValueError, OverflowError):
        return default


def _safe_opt_pct(raw: Any) -> Optional[float]:
    if raw is None or isinstance(raw, bool):
        return None
    try:
        f = float(raw)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(f):
        return None
    return round(f * 100.0, 2)


def _downsample_equity_history(
    equity_history: Any,
    max_points: int = 60,
    vm_cache: Optional[Dict[str, Any]] = None,
    cache_key: Optional[str] = None,
) -> List[Dict[str, float]]:
    fz = ViewModelPublisher.finite
    if not equity_history or max_points <= 0:
        return []

    tail_item = None
    try:
        n = len(equity_history)
        if n == 0:
            return []
        tail_item = equity_history[-1]
    except Exception:
        pts = list(equity_history)
        n = len(pts)
        if n == 0:
            return []
        tail_item = pts[-1]
    else:
        pts = None

    hist_key = (
        id(equity_history),
        getattr(equity_history, "_mut_gen", None),
        n,
        max_points,
        tail_item,
    )
    if vm_cache is not None and cache_key:
        cached_entry = vm_cache.get(cache_key)
        if isinstance(cached_entry, tuple) and len(cached_entry) == 2 and cached_entry[0] == hist_key:
            return [dict(pt) for pt in cached_entry[1]]

    if pts is None:
        pts = list(equity_history)
        n = len(pts)
        if n == 0:
            return []

    if max_points == 1:
        indices: Any = [n - 1]
    elif n <= max_points:
        indices = range(n)
    else:
        step = (n - 1) / float(max_points - 1)
        indices = [round(i * step) for i in range(max_points)]
        indices[-1] = n - 1
    out: List[Dict[str, float]] = []
    seen_idx = -1
    for idx in indices:
        if idx == seen_idx or idx >= n or idx < 0:
            continue
        seen_idx = idx
        item = pts[idx]
        if isinstance(item, (tuple, list)) and len(item) >= 2:
            out.append({"t": fz(item[0]), "v": fz(item[1])})
    if vm_cache is not None and cache_key:
        vm_cache[cache_key] = (hist_key, [dict(pt) for pt in out])
    return out


def _safe_genome_params(g: Any) -> Dict[str, Any]:
    fz = ViewModelPublisher.finite
    if g is None:
        return {}
    return {
        "generation": max(1, _safe_int_val(getattr(g, "generation", 1), 1)),
        "leverage": round(fz(getattr(g, "leverage", 1.0), 1.0), 2),
        "leverage_enabled": bool(getattr(g, "leverage_enabled", False)),
        "position_ratio_pct": round(fz(getattr(g, "position_ratio", 0.0)) * 100.0, 2),
        "stop_loss_pct": round(fz(getattr(g, "stop_loss_pct", 0.0)) * 100.0, 2),
        "take_profit_pct": _safe_opt_pct(getattr(g, "take_profit_pct", None)),
        "risk_per_trade_pct": round(fz(getattr(g, "risk_per_trade_pct", 0.0)) * 100.0, 2),
        "news_sensitivity": round(fz(getattr(g, "news_sensitivity", 1.0), 1.0), 2),
        "cooldown_bars": max(0, _safe_int_val(getattr(g, "cooldown_bars", 0), 0)),
        "trailing_activation_pct": _safe_opt_pct(getattr(g, "trailing_activation_pct", None)),
        "trailing_distance_pct": _safe_opt_pct(getattr(g, "trailing_distance_pct", None)),
    }


def _build_activity_heatmap(
    fill_records: Any,
    now_ts: Optional[float] = None,
    vm_cache: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    bucket_sec = 300
    bucket_count = 12
    raw_now = float(now_ts if now_ts is not None else time.time())
    now_val = raw_now if (math.isfinite(raw_now) and raw_now >= 0.0) else time.time()
    end_bucket = int(now_val // bucket_sec) * bucket_sec
    start_bucket = end_bucket - (bucket_count - 1) * bucket_sec

    n_fills = len(fill_records) if fill_records else 0
    tail_rec = fill_records[-1] if n_fills else None
    hm_key = (
        id(fill_records) if fill_records is not None else None,
        end_bucket,
        n_fills,
        getattr(tail_rec, "fill_seq", None) if tail_rec is not None else None,
        getattr(tail_rec, "timestamp", None) if tail_rec is not None else None,
    )
    if vm_cache is not None:
        cached_hm = vm_cache.get("activity_heatmap")
        if isinstance(cached_hm, tuple) and len(cached_hm) == 2 and cached_hm[0] == hm_key:
            c_val = cached_hm[1]
            return {
                "strategies": list(c_val["strategies"]),
                "labels": list(c_val["labels"]),
                "bucket_minutes": c_val["bucket_minutes"],
                "bucket_count": c_val["bucket_count"],
                "bucket_labels": list(c_val["bucket_labels"]),
                "matrix": [list(row) for row in c_val["matrix"]],
                "max_count": c_val["max_count"],
            }

    strat_idx = {pid: idx for idx, pid in enumerate(_HEATMAP_STRATEGIES)}
    matrix = [[0] * bucket_count for _ in _HEATMAP_STRATEGIES]

    if fill_records:
        for rec in reversed(fill_records):
            pid = getattr(rec, "portfolio_id", None)
            if pid not in strat_idx:
                continue
            try:
                rts = float(getattr(rec, "timestamp", 0.0))
            except (TypeError, ValueError):
                continue
            if not math.isfinite(rts) or rts < start_bucket:
                continue
            b_idx = int((rts - start_bucket) // bucket_sec)
            if 0 <= b_idx < bucket_count:
                matrix[strat_idx[pid]][b_idx] += 1

    bucket_labels: List[str] = []
    for i in range(bucket_count):
        bt = start_bucket + i * bucket_sec
        try:
            bucket_labels.append(time.strftime("%H:%M", time.localtime(bt)))
        except (OSError, OverflowError, ValueError):
            bucket_labels.append("")

    max_count = max((cnt for row in matrix for cnt in row), default=0)
    res = {
        "strategies": list(_HEATMAP_STRATEGIES),
        "labels": list(_HEATMAP_LABELS),
        "bucket_minutes": 5,
        "bucket_count": bucket_count,
        "bucket_labels": bucket_labels,
        "matrix": matrix,
        "max_count": int(max_count),
    }
    if vm_cache is not None:
        vm_cache["activity_heatmap"] = (
            hm_key,
            {
                **res,
                "strategies": list(res["strategies"]),
                "labels": list(res["labels"]),
                "bucket_labels": list(res["bucket_labels"]),
                "matrix": [list(row) for row in matrix],
            },
        )
    return res


def _build_risk_telemetry(
    engine: Any,
    spot: Any,
    strategies: List[Dict[str, Any]],
    macro_state: Dict[str, Any],
    vm_cache: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    fz = ViewModelPublisher.finite
    chop_er: Optional[float] = None
    get_er = getattr(engine, "get_chop_er_20", None)
    if callable(get_er):
        try:
            raw_er = get_er()
            if isinstance(raw_er, (int, float, Decimal)) and not isinstance(raw_er, bool):
                er_f = float(raw_er)
                if math.isfinite(er_f):
                    chop_er = round(er_f, 4)
        except Exception:
            chop_er = None

    spot_f = fz(spot)
    gross_exposure = 0.0
    for c in (getattr(engine, "competitors", None) or []):
        p = getattr(c, "portfolio", None)
        if p is None:
            continue
        qty_f = abs(fz(getattr(p, "position_qty", 0.0)))
        if qty_f <= 0.0:
            continue
        mark_f = spot_f if spot_f > 0.0 else abs(fz(getattr(p, "avg_entry_price", 0.0)))
        gross_exposure = fz(gross_exposure + qty_f * mark_f, gross_exposure)

    total_equity = fz(sum(fz(s.get("equity")) for s in strategies)) if strategies else 0.0
    if total_equity <= 0.0:
        for c in (getattr(engine, "competitors", None) or []):
            p = getattr(c, "portfolio", None)
            if p is not None:
                total_equity = fz(total_equity + fz(getattr(p, "total_equity", 0.0)), total_equity)

    gross_lev = fz(gross_exposure / total_equity) if total_equity > 0.0 else 0.0
    macro_mult = fz((macro_state or {}).get("risk_multiplier", 1.0), 1.0)
    chop_thresh = float(CHOP_GATE_ER_THRESHOLD)
    blocked_cnt = _safe_int_val(getattr(engine, "live_chop_gate_blocked", 0), 0)

    return {
        "chop_er_20": chop_er,
        "chop_threshold": chop_thresh,
        "chop_blocked": bool(chop_er is not None and chop_er < chop_thresh),
        "chop_blocked_count": max(0, blocked_cnt),
        "gross_exposure_usd": round(fz(gross_exposure), 2),
        "total_equity_usd": round(fz(total_equity), 2),
        "gross_leverage": round(fz(gross_lev), 3),
        "macro_risk_mult": round(fz(macro_mult, 1.0), 3),
        "activity_heatmap": _build_activity_heatmap(getattr(engine, "fill_records", None), vm_cache=vm_cache),
    }


def _build_engine_view_model_impl(engine: Any, rankings: List[Any], gen: int) -> Dict[str, Any]:
    """
    Extracts the complete JSON-serializable view model dictionary from LiveArenaEngine.
    """
    fz = ViewModelPublisher.finite
    q = engine.latest_quote
    spot = q.price if q else engine.broker.current_price

    vm_cache = getattr(engine, "_vm_cache", None)
    if not isinstance(vm_cache, dict):
        vm_cache = {}
        try:
            engine._vm_cache = vm_cache
        except Exception:
            pass

    strategies: List[Dict[str, Any]] = []
    for r in rankings:
        c = next((comp for comp in engine.competitors if comp.portfolio_id == r.portfolio_id), None)
        if c is None:
            # Stale ranking entry (competitor removed): skip it instead of
            # raising StopIteration and taking down the whole view model.
            continue
        p = c.portfolio
        g = c.genome
        pid = r.portfolio_id
        tel = engine.strategy_telemetry.get(pid, {})
        mc_st = tel.get("mc_stats", {})
        pos_qty_d = p.position_qty if isinstance(p.position_qty, Decimal) and p.position_qty.is_finite() else Decimal("0")
        avg_ep_d = p.avg_entry_price if isinstance(p.avg_entry_price, Decimal) and p.avg_entry_price.is_finite() else Decimal("0")
        spot_d = spot if isinstance(spot, Decimal) and spot.is_finite() else Decimal("0")
        in_pos = pos_qty_d > Decimal("0")
        is_short = p.position_side == PositionSide.SHORT
        upnl_pct = Decimal("0")
        if in_pos and avg_ep_d > Decimal("0") and spot_d > Decimal("0"):
            if is_short:
                upnl_pct = (avg_ep_d - spot_d) / avg_ep_d * Decimal("100")
            else:
                upnl_pct = (spot_d - avg_ep_d) / avg_ep_d * Decimal("100")
        tp_pct_val = _safe_opt_pct(getattr(g, "take_profit_pct", None))
        tp_txt = f"{tp_pct_val:.1f}%" if tp_pct_val is not None else "—"
        stop_ord = engine.broker.active_stops.get(pid)
        tp_ord = engine.broker.active_targets.get(pid)
        sl_p = fz(stop_ord.price) if (in_pos and stop_ord and stop_ord.price) else None
        tp_p = fz(tp_ord.price) if (in_pos and tp_ord and tp_ord.price) else None

        lev_f = fz(g.leverage, 1.0)
        pos_ratio_f = fz(g.position_ratio, 0.0)
        sl_pct_f = fz(g.stop_loss_pct, 0.0)
        strategies.append(
            {
                "id": pid,
                "rank": r.rank,
                "name": engine.STRATEGY_DISPLAY.get(pid, c.base_name),
                "color": engine.STRATEGY_COLORS.get(pid, "#ECF2F8"),
                "generation": g.generation,
                "leverage": lev_f,
                "leverage_enabled": bool(g.leverage_enabled),
                "leverage_label": f"{lev_f:.1f}x Lev" if g.leverage_enabled else "Spot 1x",
                "genome": (
                    f"{'Lev ' + str(round(lev_f, 1)) + 'x' if g.leverage_enabled else 'Spot 1x'} | "
                    f"Size {pos_ratio_f * 100:.0f}% | "
                    f"SL {sl_pct_f * 100:.2f}% | TP {tp_txt}"
                ),
                "genome_params": _safe_genome_params(g),
                "equity_history": _downsample_equity_history(
                    getattr(p, "equity_history", None),
                    vm_cache=vm_cache,
                    cache_key=f"eq_{pid}",
                ),
                "equity": fz(r.equity),
                "cash": fz(p.cash),
                "margin_locked": fz(p.margin_locked),
                "roi_pct": fz(r.roi_pct),
                "unrealized_pnl": fz(p.unrealized_pnl),
                "unrealized_pct": fz(upnl_pct),
                "realized_pnl": fz(p.realized_pnl),
                "in_position": in_pos,
                "position_side": p.position_side.value,
                "qty": fz(pos_qty_d),
                "entry_price": fz(avg_ep_d) if in_pos else None,
                "stop_loss": sl_p,
                "take_profit": tp_p,
                "win_rate_pct": fz(r.win_rate_pct),
                "closed_trades": int(r.closed_trades),
                "max_dd_pct": fz(r.max_drawdown_pct),
                "sharpe": fz(r.sharpe_ratio),
                "fitness": fz(r.fitness_score),
                "intent": tel.get("intent", ""),
                # No Monte Carlo evaluation has run yet for this strategy
                # (mc_stats is empty until the first bracket is evaluated):
                # report unknown (None), never fabricated defaults. The old
                # defaults (EV 0.0, win 50%, R 1.8, passed True, verdict
                # "EV Gate Active") were invented numbers (item 7).
                "mc_verdict": mc_st.get("verdict"),
                "expected_r": fz(mc_st.get("expected_r")) if mc_st.get("expected_r") is not None else None,
                "target_prob": fz(mc_st.get("target_prob")) if mc_st.get("target_prob") is not None else None,
                "stop_prob": fz(mc_st.get("stop_prob")) if mc_st.get("stop_prob") is not None else None,
                "r_multiple": fz(mc_st.get("r_multiple")) if mc_st.get("r_multiple") is not None else None,
                # A2: True when the 1.8R above is the uncapped-runner
                # model assumption rather than a real TP.
                "r_multiple_is_assumption": mc_st.get("r_multiple_is_assumption"),
                "ev_passed": mc_st.get("passed"),
            }
        )

    live_start = float(engine.live_start_ts or 0.0)
    fill_recs = engine.fill_records
    n_fills = len(fill_recs)
    tail_f = fill_recs[-1] if n_fills else None
    fills_cache_key = (
        n_fills,
        getattr(tail_f, "fill_seq", None),
        getattr(tail_f, "timestamp", None),
        getattr(tail_f, "order_id", None),
        live_start,
        bool(engine.live_orders_enabled),
        int(getattr(engine, "_live_fill_seq_offset", 0) or 0),
    )

    if vm_cache.get("fills_key") == fills_cache_key:
        fills_view = [dict(item) for item in vm_cache["fills_view"]]
    else:
        fills_view = []

        # Number live fills starting from 1 chronologically, completely ignoring historical warmup orders
        def _is_fill_live(f_item: Any) -> bool:
            if getattr(f_item, "is_live", False):
                return True
            if live_start > 0.0 and getattr(f_item, "timestamp", 0.0) >= (live_start - 5.0):
                return True
            if engine.live_orders_enabled and live_start == 0.0:
                return True
            return False

        live_seq_by_order_id: Dict[str, int] = {}
        live_seq_by_id: Dict[int, int] = {}
        live_counter = int(getattr(engine, "_live_fill_seq_offset", 0) or 0)
        for f in fill_recs:
            if _is_fill_live(f):
                live_counter += 1
                if getattr(f, "order_id", None):
                    live_seq_by_order_id[f.order_id] = live_counter
                live_seq_by_id[id(f)] = live_counter

        for f in reversed(fill_recs[-60:]):
            pid = f.portfolio_id
            is_live = _is_fill_live(f)
            is_short_pos = getattr(f, "position_side", PositionSide.LONG) == PositionSide.SHORT
            if is_short_pos:
                is_entry = f.side == OrderSide.SELL
                action_label = "OPEN SHORT" if is_entry else "COVER SHORT"
            else:
                is_entry = f.side == OrderSide.BUY
                action_label = "OPEN LONG" if is_entry else "CLOSE LONG"
            base_reason = engine.REASON_DISPLAY.get(f.reason.value, f.reason.value)
            entry_p_dec = getattr(f, "entry_price", None)
            assigned_seq = (
                live_seq_by_order_id.get(getattr(f, "order_id", ""))
                or live_seq_by_id.get(id(f))
                or (live_counter if is_live else f.fill_seq)
            )

            fills_view.append(
                {
                    "seq": assigned_seq,
                    "time": _safe_fmt_hms(f.timestamp),
                    "strategy": engine.STRATEGY_DISPLAY.get(pid, pid).split(" ")[0],
                    "side": f.side.value,
                    "action_label": action_label,
                    "is_entry": is_entry,
                    "qty": fz(f.qty),
                    "price": fz(f.price),
                    "entry_price": fz(entry_p_dec) if entry_p_dec else None,
                    "pnl": fz(f.realized_pnl) if not is_entry else None,
                    "reason": base_reason,
                    "is_live": is_live,
                }
            )
        vm_cache["fills_key"] = fills_cache_key
        vm_cache["fills_view"] = [dict(item) for item in fills_view]

    leader = strategies[0] if strategies else None
    quant_meta = {
        "source": "Local Pure-Math Quant Core",
        "is_online": engine.market_online,
        "endpoint": "In-Memory Native Engine",
        "active_model": "Genetic Evolution + Monte Carlo EV",
        "quota_pct": None,  # Unknown: the local engine reports no quota (was a fabricated 100.0, item 7).
        "tokens_used": 0,
        "tokens_saved": 0,
    }
    omni_summary = (
        f"Leader: {leader['name']} ROI {leader['roi_pct']:+.2f}% | "
        f"RSI {fz(engine.live_rsi):.1f} | ATR ${fz(engine.live_atr):.2f} | "
        f"EMA {fz(engine.live_ema_fast):,.2f}/{fz(engine.live_ema_slow):,.2f}"
    ) if leader else "Synchronizing live orderflow..."

    freeze_candidates = []
    if engine.paused and getattr(engine, "_pause_start_ts", None) is not None:
        freeze_candidates.append(engine._pause_start_ts)
    if not engine.auto_evolve_enabled and getattr(engine, "_auto_evolve_disabled_ts", None) is not None:
        freeze_candidates.append(engine._auto_evolve_disabled_ts)
    now = min(freeze_candidates) if freeze_candidates else time.time()
    elapsed_since_evolve = max(0.0, now - engine.last_evolve_ts)
    # P2-A: honest countdown. Evolution fires on the EARLIER of the
    # time cap and N closed trades (live_engine._auto_evolve_reason),
    # so a pure hours countdown overstates the wait once trades
    # accumulate. next_evolve_sec blends both triggers: the time
    # countdown scaled by the fraction of closing trades still
    # needed -- 0 when either trigger is met, the full countdown
    # when no trade has closed yet. It is a display countdown, not
    # the trigger predicate itself (the 30-minute debounce still
    # applies in _auto_evolve_reason). next_evolve_sec_latest is the
    # pure time countdown: the latest the next evolution can happen.
    # The trade counts come from the engine's own counter
    # (_closed_trades_since_evolve), not a new one.
    time_remaining = max(0.0, float(engine.auto_evolve_interval_sec) - elapsed_since_evolve)
    evolve_trade_threshold = int(getattr(engine, "auto_evolve_closed_trades", 30) or 30)
    closed_since_evolve = int(getattr(engine, "_closed_trades_since_evolve", 0) or 0)
    trades_remaining = max(0, evolve_trade_threshold - closed_since_evolve)
    if evolve_trade_threshold > 0:
        next_evolve_sec = time_remaining * (trades_remaining / evolve_trade_threshold)
    else:
        next_evolve_sec = time_remaining
    next_evolve_sec_latest = time_remaining
    next_evolve_note = (
        f"Latest in {int(next_evolve_sec_latest)}s "
        f"({int(engine.auto_evolve_interval_sec)}s cap); "
        f"{trades_remaining} closed trade{'s' if trades_remaining != 1 else ''} remaining to trigger"
    )
    # Display label for the Genetic Engine card. Frontend assets must stay
    # CJK-free (see test_zero_cjk_in_frontend_assets).
    next_evolve_trades_label = (
        f"{trades_remaining} trade{'s' if trades_remaining != 1 else ''} left"
        if trades_remaining > 0
        else "Triggering soon"
    )

    if rankings and (gen == 1 or not engine.tv_champion.get("strategy_id")):
        top = rankings[0]
        active_tv_champ = {
            "strategy_id": top.portfolio_id,
            "name": engine.STRATEGY_DISPLAY.get(top.portfolio_id, top.name),
            "generation": gen,
            "roi_pct": fz(top.roi_pct),
            "fitness": fz(top.fitness_score),
            "win_rate_pct": fz(top.win_rate_pct),
            "closed_trades": int(top.closed_trades),
            "status": "Hourly Leader (Active Dispatch)",
        }
    else:
        raw_champ = dict(engine.tv_champion)
        for num_k in ("roi_pct", "fitness", "win_rate_pct"):
            if num_k in raw_champ and raw_champ[num_k] is not None:
                raw_champ[num_k] = fz(raw_champ[num_k])
        active_tv_champ = raw_champ

    champ_id = active_tv_champ.get("strategy_id", "comp_agg")
    tv_cache_key = (fills_cache_key, champ_id)
    if vm_cache.get("tv_key") == tv_cache_key:
        tv_payloads = [dict(item) for item in vm_cache["tv_payloads"]]
    else:
        tv_payloads = []
        for f in reversed(fill_recs[-60:]):
            if f.portfolio_id == champ_id:
                tv_payloads.append(
                    {
                        "time": _safe_fmt_hms(f.timestamp),
                        "ticker": "ETHUSD",
                        "action": f.side.value,
                        "qty": fz(f.qty),
                        "price": fz(f.price),
                        "pnl": fz(f.realized_pnl) if f.is_closing_fill else None,
                        "status": "SIM_EXECUTED",
                    }
                )
                if len(tv_payloads) >= 6:
                    break
        vm_cache["tv_key"] = tv_cache_key
        vm_cache["tv_payloads"] = [dict(item) for item in tv_payloads]

    src_candles = engine.published_candles if engine.published_candles else engine.candles
    sanitized_candles = _sanitize_candles_tail_cached(src_candles, vm_cache, "candles")

    intel_hub = engine.macro_commander.get_intel_hub_telemetry()
    macro_state_safe = (
        dict(intel_hub["macro_state"])
        if isinstance(intel_hub, dict) and isinstance(intel_hub.get("macro_state"), dict)
        else engine.macro_commander.current_state.to_dict()
    )
    risk_telemetry = _build_risk_telemetry(engine, spot, strategies, macro_state_safe, vm_cache=vm_cache)
    candles_5m_view = _sanitize_candles_tail_cached(getattr(engine, "candles_5m", None), vm_cache, "candles_5m")
    candles_15m_view = _sanitize_candles_tail_cached(getattr(engine, "candles_15m", None), vm_cache, "candles_15m")
    llm_cli = getattr(engine, "llm_client", None)
    raw_model = getattr(llm_cli, "model_commander", None) or getattr(llm_cli, "model_ingest", None)
    active_model = raw_model if (isinstance(raw_model, str) and raw_model.strip()) else DEFAULT_GEMINI_MODEL

    return {
        "paused": engine.paused,
        "session_restored": bool(getattr(engine, "_has_restored_session", False)),
        "auto_evolve_enabled": engine.auto_evolve_enabled,
        "auto_evolve_interval_sec": engine.auto_evolve_interval_sec,
        "next_evolve_sec": int(next_evolve_sec),
        # P2-A: "latest" bound + trade-count progress (see above).
        "next_evolve_sec_latest": int(next_evolve_sec_latest),
        "closed_trades_since_evolve": int(closed_since_evolve),
        "closed_trades_to_next_evolve": int(trades_remaining),
        "next_evolve_sec_note": next_evolve_note,
        "next_evolve_trades_label": next_evolve_trades_label,
        "evolution_events": [
            {
                **dict(e),
                **({"ts": fz(e["ts"])} if "ts" in e and e["ts"] is not None else {}),
                **({"leader_roi_pct": fz(e["leader_roi_pct"])} if "leader_roi_pct" in e and e["leader_roi_pct"] is not None else {}),
            }
            for e in engine.evolution_events
        ],
        "macro_commander": macro_state_safe,
        "intel_hub": intel_hub,
        "risk_telemetry": risk_telemetry,
        "ui_prefs": {
            "gemini_model": active_model,
            "preload_intel_articles": bool(getattr(engine, "preload_intel_articles", True)),
        },
        "mtf": {
            "htf_bias": getattr(engine, "htf_bias", "NEUTRAL"),
            "htf_ema_50": fz(getattr(engine, "htf_ema_50", 0.0)),
            "htf_ema_200": fz(getattr(engine, "htf_ema_200", 0.0)),
            "candles_1h_count": len(getattr(engine, "candles_1h", [])),
        },
        "candles": sanitized_candles,
        "candles_5m": candles_5m_view,
        "candles_15m": candles_15m_view,
        "cadence_sec": engine.cadence_sec,
        "tv_hub": {
            "champion": active_tv_champ,
            "next_rotation_sec": int(next_evolve_sec),
            "payloads": tv_payloads[:6],
            "webhook_endpoint": "Internal Signal Bus",
            "is_connected": False,
        },
        "quant_meta": quant_meta,
        "omni_meta": quant_meta,
        "omni_summary": omni_summary,
        "strategies": strategies,
        "fills": fills_view,
        "price_history": [v if (type(v) is float and math.isfinite(v)) else fz(v) for v in engine.eth_price_series],
        "ema_fast_history": [v if (type(v) is float and math.isfinite(v)) else fz(v) for v in engine.ema_fast_series],
        "ema_slow_history": [v if (type(v) is float and math.isfinite(v)) else fz(v) for v in engine.ema_slow_series],
    }


def _empty_view_model(error: str) -> Dict[str, Any]:
    """Safe fallback view model used when the engine is missing or broken.

    Carries every top-level key the frontend reads so a broken engine
    degrades to an empty dashboard instead of crashing the bridge (item 7).
    """
    quant_meta = {
        "source": "Local Pure-Math Quant Core",
        "is_online": False,
        "endpoint": "In-Memory Native Engine",
        "active_model": "Genetic Evolution + Monte Carlo EV",
        "quota_pct": None,
        "tokens_used": 0,
        "tokens_saved": 0,
    }
    return {
        "error": error,
        "engine_available": False,
        "paused": False,
        "session_restored": False,
        "auto_evolve_enabled": False,
        "auto_evolve_interval_sec": 21600,
        "next_evolve_sec": 0,
        "next_evolve_sec_latest": 0,
        "closed_trades_since_evolve": 0,
        "closed_trades_to_next_evolve": 30,
        "next_evolve_sec_note": "Latest in 0s (21600s cap); 30 closed trades remaining to trigger",
        "next_evolve_trades_label": "30 trades left",
        "evolution_events": [],
        "macro_commander": {},
        "intel_hub": {},
        "risk_telemetry": {
            "chop_er_20": None,
            "chop_threshold": float(CHOP_GATE_ER_THRESHOLD),
            "chop_blocked": False,
            "chop_blocked_count": 0,
            "gross_exposure_usd": 0.0,
            "total_equity_usd": 0.0,
            "gross_leverage": 0.0,
            "macro_risk_mult": 1.0,
            "activity_heatmap": {
                "strategies": list(_HEATMAP_STRATEGIES),
                "labels": list(_HEATMAP_LABELS),
                "bucket_minutes": 5,
                "bucket_count": 12,
                "bucket_labels": [""] * 12,
                "matrix": [[0] * 12 for _ in _HEATMAP_STRATEGIES],
                "max_count": 0,
            },
        },
        "ui_prefs": {
            "gemini_model": "gemini-3.1-flash-lite",
            "preload_intel_articles": True,
        },
        "mtf": {
            "htf_bias": "NEUTRAL",
            "htf_ema_50": 0.0,
            "htf_ema_200": 0.0,
            "candles_1h_count": 0,
        },
        "candles": [],
        "candles_5m": [],
        "candles_15m": [],
        "cadence_sec": 1.0,
        "tv_hub": {
            "champion": {},
            "next_rotation_sec": 0,
            "payloads": [],
            "webhook_endpoint": "Internal Signal Bus",
            "is_connected": False,
        },
        "quant_meta": quant_meta,
        "omni_meta": quant_meta,
        "omni_summary": "",
        "strategies": [],
        "fills": [],
        "price_history": [],
        "ema_fast_history": [],
        "ema_slow_history": [],
    }


def build_engine_view_model(engine: Any, rankings: List[Any], gen: int) -> Dict[str, Any]:
    """Fault-tolerant entry point (item 7).

    The old version raised on any abnormal engine state (engine None, a
    missing attribute, a stale ranking entry) and took down the whole view
    model / bridge poll. Now it returns the safe empty model instead.
    """
    if engine is None:
        return _empty_view_model("engine_not_initialized")
    try:
        return _build_engine_view_model_impl(engine, rankings or [], gen)
    except Exception as e:
        logger.exception("build_engine_view_model failed, returning empty model: %s", e)
        return _empty_view_model(str(e))

