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
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from src.arena.order import OrderSide, PositionSide


logger = logging.getLogger(__name__)


class ViewModelPublisher:
    """
    Constructs JSON-safe UI view models and computes incremental state deltas
    by tracking candle signatures and fill sequence watermarks across ticks.
    """

    def __init__(self) -> None:
        self.last_candle_sig: Optional[str] = None
        self.last_fill_seq: int = -1
        self.last_history_sig: Optional[Tuple[int, float]] = None

    def reset(self) -> None:
        self.last_candle_sig = None
        self.last_fill_seq = -1
        self.last_history_sig = None

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
        first_t = candles[0].get("t", 0)
        raw = f"{len(candles)}:{first_t}:{last.get('t')}:{last.get('o')}:{last.get('h')}:{last.get('l')}:{last.get('c')}"
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    def compute_delta_payload(
        self, full_state: Dict[str, Any], force_full: bool = False
    ) -> Dict[str, Any]:
        """
        Produces an incremental state-delta dictionary from a full UI state snapshot.
        - If no candle has changed since the previous poll, omits the full `candles` array
          and sets `candles_unchanged=True`.
        - If no new fill has arrived, omits `fills` and sets `fills_unchanged=True`.
        """
        delta = dict(full_state)
        candles = full_state.get("candles") or []
        fills = full_state.get("fills") or []

        candle_sig = self.compute_candle_signature(candles)
        top_fill_seq = int(fills[0]["seq"]) if fills and "seq" in fills[0] else 0

        if force_full or self.last_candle_sig is None:
            self.last_candle_sig = candle_sig
            self.last_fill_seq = top_fill_seq
            delta["is_delta"] = False
            delta["candles_unchanged"] = False
            delta["fills_unchanged"] = False
            return delta

        candles_same = candle_sig == self.last_candle_sig
        fills_same = top_fill_seq == self.last_fill_seq

        self.last_candle_sig = candle_sig
        self.last_fill_seq = top_fill_seq

        delta["is_delta"] = bool(candles_same or fills_same)
        delta["candles_unchanged"] = candles_same
        delta["fills_unchanged"] = fills_same

        if candles_same:
            delta.pop("candles", None)
        if fills_same:
            delta.pop("fills", None)

        return delta

    def compute_delta_from_snapshot(
        self, snapshot: Dict[str, Any], force_full: bool = False
    ) -> Dict[str, Any]:
        """
        Audit §5.2: same output as compute_delta_payload, but the heavy
        arrays are dropped BEFORE the deepcopy instead of after it.

        The old path deepcopied the whole snapshot (150 candles + 60
        fills + price histories) on every 1 Hz poll and only then popped
        the unchanged arrays. This method peeks at the candle/fill
        signatures first: when both are unchanged it deepcopies
        everything EXCEPT candles/fills, so the copy cost is the small
        remainder. When either changed (or on the first poll / force
        full) it deepcopies the whole snapshot, exactly like before.
        The snapshot itself is never mutated.
        """
        candles = snapshot.get("candles") or []
        fills = snapshot.get("fills") or []
        candle_sig = self.compute_candle_signature(candles)
        top_fill_seq = int(fills[0]["seq"]) if fills and "seq" in fills[0] else 0

        if force_full or self.last_candle_sig is None:
            self.last_candle_sig = candle_sig
            self.last_fill_seq = top_fill_seq
            delta = copy.deepcopy(snapshot)
            delta["is_delta"] = False
            delta["candles_unchanged"] = False
            delta["fills_unchanged"] = False
            return delta

        candles_same = candle_sig == self.last_candle_sig
        fills_same = top_fill_seq == self.last_fill_seq
        self.last_candle_sig = candle_sig
        self.last_fill_seq = top_fill_seq

        if candles_same and fills_same:
            delta = copy.deepcopy(
                {k: v for k, v in snapshot.items() if k not in ("candles", "fills")}
            )
            delta["is_delta"] = True
            delta["candles_unchanged"] = True
            delta["fills_unchanged"] = True
            return delta

        delta = copy.deepcopy(snapshot)
        delta["is_delta"] = bool(candles_same or fills_same)
        delta["candles_unchanged"] = candles_same
        delta["fills_unchanged"] = fills_same
        if candles_same:
            delta.pop("candles", None)
        if fills_same:
            delta.pop("fills", None)
        return delta


def _build_engine_view_model_impl(engine: Any, rankings: List[Any], gen: int) -> Dict[str, Any]:
    """
    Extracts the complete JSON-serializable view model dictionary from LiveArenaEngine.
    """
    fz = ViewModelPublisher.finite
    q = engine.latest_quote
    spot = q.price if q else engine.broker.current_price

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
        in_pos = p.position_qty > Decimal("0")
        is_short = p.position_side == PositionSide.SHORT
        upnl_pct = Decimal("0")
        if in_pos and p.avg_entry_price > Decimal("0") and spot > Decimal("0"):
            if is_short:
                upnl_pct = (p.avg_entry_price - spot) / p.avg_entry_price * Decimal("100")
            else:
                upnl_pct = (spot - p.avg_entry_price) / p.avg_entry_price * Decimal("100")
        tp_txt = f"{float(g.take_profit_pct) * 100:.1f}%" if g.take_profit_pct else "—"
        stop_ord = engine.broker.active_stops.get(pid)
        tp_ord = engine.broker.active_targets.get(pid)
        sl_p = fz(stop_ord.price) if (in_pos and stop_ord and stop_ord.price) else None
        tp_p = fz(tp_ord.price) if (in_pos and tp_ord and tp_ord.price) else None


        strategies.append(
            {
                "id": pid,
                "rank": r.rank,
                "name": engine.STRATEGY_DISPLAY.get(pid, c.base_name),
                "color": engine.STRATEGY_COLORS.get(pid, "#ECF2F8"),
                "generation": g.generation,
                "leverage": fz(g.leverage),
                "leverage_enabled": bool(g.leverage_enabled),
                "leverage_label": f"{float(g.leverage):.1f}x Lev" if g.leverage_enabled else "Spot 1x",
                "genome": (
                    f"{'Lev ' + str(round(float(g.leverage), 1)) + 'x' if g.leverage_enabled else 'Spot 1x'} | "
                    f"Size {float(g.position_ratio) * 100:.0f}% | "
                    f"SL {float(g.stop_loss_pct) * 100:.2f}% | TP {tp_txt}"
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
                "qty": fz(p.position_qty),
                "entry_price": fz(p.avg_entry_price) if in_pos else None,
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
                "expected_r": mc_st.get("expected_r"),
                "target_prob": mc_st.get("target_prob"),
                "stop_prob": mc_st.get("stop_prob"),
                "r_multiple": mc_st.get("r_multiple"),
                # A2: True when the 1.8R above is the uncapped-runner
                # model assumption rather than a real TP.
                "r_multiple_is_assumption": mc_st.get("r_multiple_is_assumption"),
                "ev_passed": mc_st.get("passed"),
            }
        )

    fills_view: List[Dict[str, Any]] = []
    live_start = float(engine.live_start_ts or 0.0)

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
    live_counter = 0
    for f in engine.fill_records:
        if _is_fill_live(f):
            live_counter += 1
            if getattr(f, "order_id", None):
                live_seq_by_order_id[f.order_id] = live_counter
            live_seq_by_id[id(f)] = live_counter

    for f in reversed(engine.fill_records[-60:]):
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
                "time": time.strftime("%H:%M:%S", time.localtime(f.timestamp)),
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

    now = time.time()
    if engine.paused and getattr(engine, "_pause_start_ts", None) is not None:
        now = engine._pause_start_ts
    elif not engine.auto_evolve_enabled and getattr(engine, "_auto_evolve_disabled_ts", None) is not None:
        now = engine._auto_evolve_disabled_ts
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
    # pure time countdown: the latest ("\u6700\u665a") the next
    # evolution can happen. The trade counts come from the engine's
    # own counter (_closed_trades_since_evolve), not a new one.
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
        f"\u6700\u665a {int(next_evolve_sec_latest)}s"
        f"\uff08{int(engine.auto_evolve_interval_sec)}s \u4e0a\u9650\uff09\uff1b"
        f"\u9084\u5dee {trades_remaining} \u7b46\u5e73\u5009\u5373\u89f8\u767c"
    )
    # Display label for the Genetic Engine card. Frontend assets must stay
    # CJK-free (see test_zero_cjk_in_frontend_assets), so the Chinese label
    # is rendered here in Python and the frontend only displays it opaquely.
    next_evolve_trades_label = (
        f"\u9084\u5dee {trades_remaining} \u7b46" if trades_remaining > 0 else "\u5373\u5c07\u89f8\u767c"
    )

    if rankings and (engine.tv_champion.get("generation") == 1 or not engine.tv_champion.get("strategy_id")):
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
        active_tv_champ = engine.tv_champion

    champ_id = active_tv_champ.get("strategy_id", "comp_agg")
    tv_payloads = []
    for f in reversed(engine.fill_records[-60:]):
        if f.portfolio_id == champ_id:
            tv_payloads.append(
                {
                    "time": time.strftime("%H:%M:%S", time.localtime(f.timestamp)),
                    "ticker": "ETHUSD",
                    "action": f.side.value,
                    "qty": fz(f.qty),
                    "price": fz(f.price),
                    "pnl": fz(f.realized_pnl) if f.is_closing_fill else None,
                    "status": "SIM_EXECUTED",
                }
            )

    return {
        "paused": engine.paused,
        "auto_evolve_enabled": engine.auto_evolve_enabled,
        "auto_evolve_interval_sec": engine.auto_evolve_interval_sec,
        "next_evolve_sec": int(next_evolve_sec),
        # P2-A: "latest" bound + trade-count progress (see above).
        "next_evolve_sec_latest": int(next_evolve_sec_latest),
        "closed_trades_since_evolve": int(closed_since_evolve),
        "closed_trades_to_next_evolve": int(trades_remaining),
        "next_evolve_sec_note": next_evolve_note,
        "next_evolve_trades_label": next_evolve_trades_label,
        "evolution_events": engine.evolution_events,
        "macro_commander": engine.macro_commander.current_state.to_dict(),
        "intel_hub": engine.macro_commander.get_intel_hub_telemetry(),
        "mtf": {
            "htf_bias": getattr(engine, "htf_bias", "NEUTRAL"),
            "htf_ema_50": fz(getattr(engine, "htf_ema_50", 0.0)),
            "htf_ema_200": fz(getattr(engine, "htf_ema_200", 0.0)),
            "candles_1h_count": len(getattr(engine, "candles_1h", [])),
        },
        "candles": [
            {
                "t": c["t"],
                "o": fz(c["o"]),
                "h": fz(c["h"]),
                "l": fz(c["l"]),
                "c": fz(c["c"]),
            }
            for c in (engine.published_candles if engine.published_candles else engine.candles)[-150:]
        ],
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
        "price_history": [fz(v) for v in engine.eth_price_series],
        "ema_fast_history": [fz(v) for v in engine.ema_fast_series],
        "ema_slow_history": [fz(v) for v in engine.ema_slow_series],
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
        "auto_evolve_enabled": False,
        "auto_evolve_interval_sec": 21600,
        "next_evolve_sec": 0,
        "next_evolve_sec_latest": 0,
        "closed_trades_since_evolve": 0,
        "closed_trades_to_next_evolve": 30,
        "next_evolve_sec_note": "\u6700\u665a 0s\uff0821600s \u4e0a\u9650\uff09\uff1b\u9084\u5dee 30 \u7b46\u5e73\u5009\u5373\u89f8\u767c",
        "next_evolve_trades_label": "\u9084\u5dee 30 \u7b46",
        "evolution_events": [],
        "macro_commander": {},
        "intel_hub": {},
        "mtf": {
            "htf_bias": "NEUTRAL",
            "htf_ema_50": 0.0,
            "htf_ema_200": 0.0,
            "candles_1h_count": 0,
        },
        "candles": [],
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

