from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime, timezone
import hashlib
import logging
import math
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Tuple
import weakref

from src.arena.order import OrderSide
from src.intelligence.omniroute_client import OmniRouteClient
from src.intelligence.forum_collector import ForumCollector
from src.intelligence.ingestion import IntelligenceHarvester, StructuredEvent

logger = logging.getLogger(__name__)

# Item 12 / A3 option 2: a keyword-fallback regime older than this (seconds)
# steps down to neutral instead of letting stale keyword scores veto trades.
FALLBACK_MAX_AGE_SEC = 1800.0

# Weighted sentiment (item 12C / C1): tier weights, 60-minute half-life,
# 60-minute evidence window, at most the 30 freshest events.
TIER_WEIGHTS = {0: 1.5, 1: 1.2, 2: 1.0, 3: 0.7}
WEIGHTED_WINDOW_MIN = 60.0
WEIGHTED_MAX_EVENTS = 30
WEIGHTED_HALF_LIFE_MIN = 60.0

# First-sync progress (workstream 3): milestone percent for each real
# pipeline stage of refresh_digest_async. The percent is the stage
# milestone, never measured time: 100 is reported only when the run
# actually produced events; a run that ends with an empty stream stays
# at or below 90, so the loading bar never claims completion while the
# stream is still loading.
SYNC_STAGE_PERCENT = {
    "idle": 0,
    "checking": 10,
    "fetching": 30,
    "processing": 55,
    "forum": 70,
    "synthesizing": 85,
    "waiting": 85,
    "done": 100,
}

# Intel Hub stream redesign, Phase A: per-event full article.
# The harvest pipeline stores only a 35-70 word summary plus a truncated
# raw snippet (RSS 450 chars / StockTwits 1200 chars), so there is no
# source full text to excerpt. Audit 2.10: the snippet rides the curated
# event ("raw_snippet") into the article prompt, so the ~1000-word target
# is grounded in the event's own words instead of only the summary. The
# article is generated lazily on first expand and cached on the curated
# event. The snippet is stripped from the 1 Hz telemetry
# (_TELEMETRY_ARTICLE_KEYS) -- it is prompt material only.
ARTICLE_TARGET_WORDS = 1000
# Below this length an LLM reply is not an article (and never the
# one-line summary passed off as one); it counts as a failed generation.
ARTICLE_MIN_CHARS = 200
# The six article paragraphs, in order.
ARTICLE_SECTION_HEADINGS = ("事件經過", "背景脈絡", "市場含義", "風險因素", "後續觀察", "總結")


def _dedup_tickers(tickers: Any) -> List[str]:
    """Uppercase, order-preserving dedup of entity tickers.

    Returns [] when the source list is empty or missing, never None, so
    the frontend can always iterate the field.
    """
    seen: List[str] = []
    for t in tickers or []:
        up = str(t).strip().upper()
        if up and up not in seen:
            seen.append(up)
    return seen


def build_event_article_prompts(evt: Dict[str, Any]) -> Tuple[str, str]:
    """Builds the (system_prompt, user_prompt) for one event's article.

    The model must return a single JSON object {"article": "..."} so the
    chat_json contract (parsed JSON dict) is honoured. The article is
    organized strictly from the event's own material -- headline,
    summary, raw title, source -- and must not invent figures, dates,
    quotes or sources that are not in that material.
    """
    system_prompt = (
        "你是一位繁體中文財經情報編輯。請根據提供的單則情報素材，整理成一篇繁體中文文章。\n"
        "輸出必須是單一 JSON 物件，格式如下：\n"
        '{"article": "文章全文"}\n'
        "規則：\n"
        "- 文章全文必須以繁體中文撰寫，約 1000 字，共 6 段。\n"
        "- 6 段依序為：事件經過、背景脈絡、市場含義、風險因素、後續觀察、總結。\n"
        "- 只能使用素材中已有的資訊（標題、摘要、原文標題、原文片段、來源）；不得編造素材中沒有的具體數字、日期、引言或來源。\n"
        "- 不得把摘要本身當作文章回傳；文章必須是展開整理的完整內容。\n"
        "- 若素材不足以支撐 1000 字，寧可寫得精簡誠實，也不要編造細節充數。\n"
        "- 只輸出 JSON 物件，不要輸出其他文字或說明。"
    )
    snippet = (evt.get("raw_snippet") or "").strip()
    snippet_line = f"原文片段：{snippet}\n" if snippet else ""
    user_prompt = (
        f"情報來源：{evt.get('source', '')}\n"
        f"原文標題：{evt.get('raw_title', '')}\n"
        f"標題：{evt.get('headline', '')}\n"
        f"摘要：{evt.get('summary', '')}\n"
        f"{snippet_line}"
        "請依上述素材整理一篇繁體中文文章，約 1000 字、共 6 段"
        "（事件經過、背景脈絡、市場含義、風險因素、後續觀察、總結）。"
    )
    return system_prompt, user_prompt


def _event_age_min(timestamp: str, now: float) -> float:
    """Minutes between an event's ISO8601 timestamp and `now`.

    Unparseable timestamps are treated as fresh (age 0): a malformed
    timestamp must not silently drop a real event from the weighted
    score. Future timestamps (clock skew) clamp to 0.
    """
    try:
        dt = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, (now - dt.timestamp()) / 60.0)
    except (TypeError, ValueError):
        return 0.0


def _safe_float(value: Any, default: float) -> float:
    """Parses an untrusted numeric value (LLM output / feed data).

    Returns `default` when the value is missing, non-finite (NaN/Inf), or not a
    number, instead of raising. A failed parse must never take down the veto
    pipeline (item 6).
    """
    try:
        parsed = float(value)
        return parsed if math.isfinite(parsed) else default
    except (TypeError, ValueError):
        return default


@dataclass
class MacroRegimeState:
    regime: str = "NORMAL"  # "BULLISH_SURGE", "BEARISH_PANIC", "HIGH_VOLATILITY_CHOP", "NORMAL"
    directional_bias: str = "BIDIRECTIONAL"  # "LONG_ONLY", "SHORT_ONLY", "BIDIRECTIONAL", "HOLD_CASH"
    risk_multiplier: float = 1.0  # 0.5 to 1.5
    active_headline: str = "全球訂單流維持宏觀均衡。實時智能情報監控運行中。"
    confidence: float = 0.50
    last_synthesis_ts: float = 0.0
    # Fallback provenance (item 12 / A3 option 2): True while the current
    # bias came from the local keyword fallback instead of the LLM, and the
    # timestamp the fallback first took over (for the 30-minute expiry).
    fallback: bool = False
    fallback_since_ts: float = 0.0
    # Weighted sentiment (item 12C): deterministic tier/urgency/time-decay
    # scores from the latest synthesis; 0.0/0.0/0.0 means no usable evidence.
    weighted_sentiment: float = 0.0  # S in [-1, 1]
    weighted_urgency: float = 0.0  # U in [0, 10]
    weighted_coverage: float = 0.0  # N, decay-weighted event count
    veto_count_today: int = 0
    total_evaluations: int = 0
    status: str = "ONLINE"  # "ONLINE", "STANDBY", "OFFLINE"
    latest_event: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "regime": self.regime,
            "directional_bias": self.directional_bias,
            "risk_multiplier": round(self.risk_multiplier, 2),
            "active_headline": self.active_headline,
            "confidence": round(self.confidence, 2),
            "last_synthesis_time": time.strftime("%H:%M:%S", time.localtime(self.last_synthesis_ts)) if self.last_synthesis_ts else "",
            "fallback": self.fallback,
            "fallback_since": time.strftime("%H:%M:%S", time.localtime(self.fallback_since_ts)) if self.fallback_since_ts else "",
            "weighted_sentiment": round(self.weighted_sentiment, 3),
            "weighted_urgency": round(self.weighted_urgency, 2),
            "weighted_coverage": round(self.weighted_coverage, 2),
            "veto_count_today": self.veto_count_today,
            "total_evaluations": self.total_evaluations,
            "status": self.status,
            "latest_event": self.latest_event,
        }


class MacroCommander:
    """
    Stage 2 Macro Commander: Synthesizes cross-market intelligence from OmniRoute
    and enforces Strict Veto (Option A) across all 5 arena competitors.
    """

    STRAT_LABELS: Dict[str, str] = {
        "comp_agg": "Strategy 1 (AGG)",
        "comp_cons": "Strategy 2 (CONS)",
        "comp_trail": "Strategy 3 (TRAIL)",
        "comp_orb": "Strategy 4 (ORB)",
        "comp_vwap": "Strategy 5 (Mean)",
    }

    def __init__(self, client: OmniRouteClient, harvester: Optional[IntelligenceHarvester] = None) -> None:
        self.client = client
        self.harvester = harvester or IntelligenceHarvester(client=client)
        self.forum_collector = ForumCollector(client=client)
        self.current_state = MacroRegimeState()
        self._events_lock = threading.RLock()
        self._synthesis_locks: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Lock]" = weakref.WeakKeyDictionary()
        self._synthesis_locks_guard = threading.Lock()
        self.synthesis_lock = asyncio.Lock()
        self.last_synthesis_time: float = 0.0
        self._last_synthesized_keys: Tuple[str, ...] = ()
        self._veto_day: date = date.today()
        self.curated_events: List[Dict[str, Any]] = []
        self._curated_version: int = 0
        self._telemetry_events_cache_key: Optional[Tuple[int, int]] = None
        self._telemetry_events_cache: List[Dict[str, Any]] = []
        self._seed_default_events()
        # First-sync progress (workstream 3): the current pipeline
        # stage + milestone percent, read by get_intel_hub_telemetry.
        self.sync_status: Dict[str, Any] = {
            "stage": "idle",
            "percent": 0,
            "detail": "",
            "updated_at": 0.0,
        }
        # Per-event article generation (Phase A): one lock + refcount per
        # event id so concurrent expand calls coalesce without a prune TOCTOU.
        self._article_locks: Dict[str, List[Any]] = {}
        self._article_locks_guard = threading.Lock()

    def _get_synthesis_lock(self) -> asyncio.Lock:
        try:
            loop = asyncio.get_running_loop()
            with self._synthesis_locks_guard:
                lock = self._synthesis_locks.get(loop)
                if lock is None:
                    lock = asyncio.Lock()
                    self._synthesis_locks[loop] = lock
                return lock
        except RuntimeError:
            return self.synthesis_lock

    def _seed_default_events(self) -> None:
        # No fabricated news: the intel timeline starts empty and is filled
        # only by real harvested events (synthesize_regime). The old version
        # seeded five invented headlines attributed to real outlets
        # (CoinDesk / SEC / Bloomberg) and presented them as genuine
        # intelligence in the Intel Hub (item 6).
        self.current_state.regime = "NORMAL"
        self.current_state.directional_bias = "BIDIRECTIONAL"
        self.current_state.risk_multiplier = 1.0
        self.current_state.active_headline = "全球訂單流維持宏觀均衡。實時智能情報監控運行中。"
        # No real data yet: neutral confidence, not the old 0.85.
        self.current_state.confidence = 0.50
        self.current_state.status = "ONLINE" if self.client.is_gateway_online else "STANDBY"

        self.curated_events = []
        self._curated_version += 1
        self.current_state.latest_event = None

    def ensure_traditional_chinese_seed_events(self) -> None:
        """
        Guarantees that all events currently in curated_events have Traditional Chinese
        headlines and summaries. Used during bootstrap and reset before UI reveal.
        """
        with self._events_lock:
            mutated = False
            for evt in self.curated_events:
                head = evt.get("headline", "")
                sum_txt = evt.get("summary", "")
                if not IntelligenceHarvester._contains_cjk(head) or not IntelligenceHarvester._contains_cjk(sum_txt):
                    dummy_event = StructuredEvent(
                        timestamp="",
                        entities_tickers=list(evt.get("tickers") or []),
                        raw_title=head or evt.get("raw_title", ""),
                        source=evt.get("source", ""),
                        domain=evt.get("domain", "crypto"),
                        urgency_score=evt.get("urgency", 5),
                        sentiment_score=evt.get("sentiment", 0.0),
                        headline_zh="",
                        summary=sum_txt,
                    )
                    zh_h, zh_s = IntelligenceHarvester.ensure_traditional_chinese(dummy_event)
                    evt["headline"] = zh_h
                    evt["summary"] = zh_s
                    mutated = True
            if mutated:
                self._curated_version += 1
            if not IntelligenceHarvester._contains_cjk(self.current_state.active_headline):
                self.current_state.active_headline = "全球訂單流維持宏觀均衡。實時智能情報監控運行中。"
            if self.curated_events:
                self.current_state.latest_event = self.curated_events[0]

    def record_strategy_action(self, strat_id: str, name: str, action: str, badge_cls: str = "buy", is_macro_action: bool = False) -> None:
        """
        Associates an executed trade, veto, or bracket shift for Strategy 1-6 with the current macro event.
        Retains the latest status per strategy (at most 6 items) to prevent spamming redundant actions.
        """
        display_name = self.STRAT_LABELS.get(strat_id, name)
        with self._events_lock:
            if not self.curated_events:
                return
            active_evt = self.curated_events[0]
            acts = active_evt.setdefault("strategy_actions", [])
            existing_idx = next((i for i, a in enumerate(acts) if a.get("strat_id") == strat_id), -1)
            if existing_idx >= 0:
                acts.pop(existing_idx)
            acts.insert(0, {
                "strat_id": strat_id,
                "name": display_name,
                "action": action,
                "badge_cls": badge_cls,
                "time": time.strftime("%H:%M:%S"),
            })
            if len(acts) > 6:
                acts.pop()
            self.current_state.latest_event = active_evt
            self._curated_version += 1

    def _set_sync_stage(self, stage: str, detail: str = "", percent: Optional[int] = None) -> None:
        """Records the current sync stage (atomic dict replacement, so
        the telemetry reader never sees a half-written status)."""
        if percent is None:
            percent = SYNC_STAGE_PERCENT.get(stage, 0)
        if stage == "failed":
            # A failed run keeps the last milestone reached -- the bar
            # never advances on a failure, and never claims 100.
            percent = self.sync_status.get("percent", 0)
        self.sync_status = {
            "stage": stage,
            "percent": percent,
            "detail": detail,
            "updated_at": time.time(),
        }

    async def refresh_digest_async(self, stop_event: Optional[threading.Event] = None) -> MacroRegimeState:
        """
        Triggers an AI-driven refresh of macro intelligence, fetching genuine live RSS feeds
        over HTTP and synthesizing through OmniRoute or local deterministic NLP.
        Records the real pipeline stage in self.sync_status so the Intel
        Hub stream loading bar can show honest milestone progress.
        """
        def _shutting_down() -> bool:
            if sys.is_finalizing() or (stop_event is not None and stop_event.is_set()):
                return True
            fn = getattr(self.client, "is_shutting_down", None)
            return callable(fn) and fn() is True

        if _shutting_down():
            return self.current_state
        fetch_error: Optional[str] = None
        # Audit 3.12: check_health catches every Exception and returns a
        # bool, so a dead gateway never raised here -- the "failed" stage
        # was unreachable and gateway death surfaced as waiting/done.
        # Record the boolean result and use it at the end of the refresh.
        gateway_healthy = True
        # NOTE (2026-11-15): no per-refresh session close here any
        # more. The old finally block closed the shared client
        # session after every refresh, while a concurrent lazy
        # article generation (get_event_article, bridge thread) was
        # still using it -- the in-flight chat_json died with
        # "Session is closed" (app log 16:52:53/54/59, 16:56:16).
        # The session now lives with the commander: get_session()
        # rebuilds it on demand when closed or when the calling
        # loop differs. No shutdown path closes the LLM client
        # (dashboard/engine stop don't touch it); __del__ still
        # runs close_sync() at GC time. Do NOT re-add a per-refresh
        # close to "prevent leaks" -- that was the race.
        self._set_sync_stage("checking", "Checking AI gateway")
        try:
            gateway_healthy = await self.client.check_health()
        except Exception as ex:
            self._set_sync_stage("failed", f"Gateway unreachable: {str(ex)[:60]}")
            raise
        if _shutting_down():
            return self.current_state
        try:
            self._set_sync_stage("fetching", "Fetching live news feeds")
            raw_events = await asyncio.to_thread(self.harvester.fetch_live_feeds, 5, 3.5)
            if _shutting_down():
                return self.current_state
            structured_all: List[StructuredEvent] = []
            if raw_events:
                self._set_sync_stage("processing", f"Reading {len(raw_events)} new stories")
                structured_all.extend(await self.harvester.process_batch(raw_events))
            if _shutting_down():
                return self.current_state
            # Forum batch (item 12B): StockTwits streams are collected on
            # their own cadence and scored in a separate batch, so forum
            # chatter never crowds breaking news out of the 6-event cap.
            try:
                self._set_sync_stage("forum", "Collecting community signals")
                forum_events = await self.forum_collector.collect_async()
                if forum_events and hasattr(self.harvester, "push_raw_events"):
                    forum_events = self.harvester.push_raw_events(forum_events)
                if forum_events:
                    structured_all.extend(await self.harvester.process_batch(forum_events))
            except Exception as ex:
                if (
                    "cannot schedule new futures after shutdown" in str(ex)
                    or sys.is_finalizing()
                    or (stop_event is not None and stop_event.is_set())
                ):
                    logger.debug("Forum collection skipped during shutdown: %s", ex)
                    return self.current_state
                logger.warning("Forum collection failed, continuing with news only: %s", ex)
            if structured_all:
                if _shutting_down():
                    return self.current_state
                self._set_sync_stage("synthesizing", "Synthesizing market direction")
                state = await self.synthesize_regime(structured_all)
                self._set_sync_stage("done", "Stream live" if self.curated_events else "No new events yet",
                                     percent=100 if self.curated_events else 90)
                return state
        except Exception as ex:
            if "cannot schedule new futures after shutdown" in str(ex) or _shutting_down():
                logger.debug("Live feed harvest skipped during shutdown: %s", ex)
                return self.current_state
            else:
                logger.warning("Error harvesting live feeds in refresh_digest_async: %s", ex)
            fetch_error = str(ex)[:80] or ex.__class__.__name__

        if fetch_error:
            with self._events_lock:
                self._expire_fallback_if_stale(time.time())
            self._set_sync_stage("failed", f"Sync failed: {fetch_error}")
            return self.current_state
        if not gateway_healthy:
            # Audit 3.12: the gateway is dead and the refresh produced
            # nothing to synthesize -- say so instead of "waiting".
            with self._events_lock:
                self._expire_fallback_if_stale(time.time())
            self._set_sync_stage("failed", "Gateway unreachable")
            return self.current_state

        recent = self.harvester.get_latest_events(10)
        if recent:
            recent_keys = tuple((e.raw_title or e.summary) for e in recent)
            if recent_keys == self._last_synthesized_keys and not self.current_state.fallback and self.curated_events:
                self._set_sync_stage("done", "Stream live", percent=100)
                return self.current_state
            if _shutting_down():
                return self.current_state
            self._set_sync_stage("synthesizing", "Synthesizing market direction")
            state = await self.synthesize_regime(recent)
            self._set_sync_stage("done", "Stream live" if self.curated_events else "No new events yet",
                                 percent=100 if self.curated_events else 90)
            return state
        with self._events_lock:
            self._expire_fallback_if_stale(time.time())
        self._set_sync_stage("waiting", "No new events yet")
        return self.current_state

    def run_digest_sync(self, stop_event: Optional[threading.Event] = None) -> "MacroRegimeState":
        """Run refresh_digest_async on a private loop, then clean up.

        The LLM client creates a session per event loop; this wrapper
        closes that loop's session before the loop ends, so a refresh
        never leaves an Unclosed client session behind. Callers that
        already have a running loop use refresh_digest_async directly.
        """
        def _shutting_down() -> bool:
            if sys.is_finalizing() or (stop_event is not None and stop_event.is_set()):
                return True
            fn = getattr(self.client, "is_shutting_down", None)
            return callable(fn) and fn() is True

        if _shutting_down():
            return self.current_state

        async def _wrapped() -> "MacroRegimeState":
            try:
                import inspect as _inspect
                fn = self.refresh_digest_async
                try:
                    params = _inspect.signature(fn).parameters
                    accepts_stop = "stop_event" in params or any(
                        p.kind == _inspect.Parameter.VAR_KEYWORD for p in params.values()
                    )
                except (TypeError, ValueError):
                    accepts_stop = False
                if accepts_stop:
                    return await fn(stop_event=stop_event)
                return await fn()
            finally:
                closer = getattr(self.client, "close_loop_session", None)
                if callable(closer):
                    try:
                        await closer()
                    except Exception as ex:
                        logger.debug("Digest loop-session cleanup failed: %s", ex)

        return asyncio.run(_wrapped())

    def get_intel_hub_telemetry(self) -> Dict[str, Any]:
        """
        Returns complete intelligence diagnostic telemetry for the Macro Intel Hub panel.
        Honest metrics: reports 0 tokens when total_requests is 0.
        """
        is_online = bool(getattr(self.client, "is_gateway_online", False))
        total_reqs = getattr(self.client, "total_requests", 0)
        total_reqs = int(total_reqs) if isinstance(total_reqs, (int, float)) else 0
        raw_used = getattr(self.client, "total_tokens_used", 0)
        tokens_used = int(raw_used) if isinstance(raw_used, (int, float)) else 0
        raw_saved = getattr(self.client, "total_tokens_saved", 0)
        tokens_saved = int(raw_saved) if isinstance(raw_saved, (int, float)) else 0
        raw_hits = getattr(self.client, "total_dedup_hits", 0)
        dedup_hits = int(raw_hits) if isinstance(raw_hits, (int, float)) else 0

        status_text = "ONLINE" if is_online else "STANDBY"

        # Unknown quota is reported as None, never as a fabricated 100.0%
        # (item 6). The frontend already treats a non-number as unknown.
        quota_pct: Optional[float] = None
        if hasattr(self.client, "get_quota_pct") and callable(self.client.get_quota_pct):
            try:
                q_val = self.client.get_quota_pct()
                if isinstance(q_val, (int, float)):
                    quota_pct = float(q_val)
            except Exception as e:
                logger.debug("Failed to read quota from client: %s", e)
        # P0-B / F4: no fallback estimate. The old `elif` divided by a
        # made-up 100000 denominator; with no user-set DAILY_TOKEN_QUOTA
        # the quota is unknown and stays None.

        tot_tokens = tokens_used + tokens_saved
        dedup_pct = round((tokens_saved / tot_tokens) * 100.0, 1) if tot_tokens > 0 else 0.0

        return {
            "omniroute": {
                "status": status_text,
                "endpoint": str(getattr(self.client, "base_url", "http://127.0.0.1:20128/v1")),
                "model_ingest": str(getattr(self.client, "model_ingest", "auto")),
                "model_commander": str(getattr(self.client, "model_commander", "auto")),
                "quota_pct": quota_pct,
                "tokens_used": tokens_used,
                "tokens_saved": tokens_saved,
                "dedup_pct": dedup_pct,
                "dedup_hits": dedup_hits,
                "quota_throttled": self.is_quota_throttled(),
                "digest_interval_sec": self.digest_interval_sec(),
                "total_requests": int(getattr(self.client, "total_requests", 0)),
                "successful_requests": int(getattr(self.client, "successful_requests", 0)),
                "retried_requests": int(getattr(self.client, "retried_requests", 0)),
                "failed_requests": int(getattr(self.client, "failed_requests", 0)),
                "concurrency_limit": int(getattr(self.client, "max_concurrent", 25)),
            },
            "macro_state": self._telemetry_macro_state(),
            "events": self._telemetry_events(25),
            # First-sync progress (workstream 3): the current pipeline
            # stage + milestone percent. A copy, so a reader can never
            # rewrite the live status dict.
            "sync": dict(self.sync_status),
        }

    # The generated article body is deliberately NOT part of the 1 Hz
    # telemetry payload: the UI caches it and fetches on demand via
    # get_event_article(). Measured before this fix: 25 expanded events
    # took the snapshot from 14,817 to 153,342 chars (+135 KiB) of text
    # the snapshot deep-copied and serialized every second.
    # Audit 2.10: "raw_snippet" rides here too -- up to 1200 chars
    # per event x 60 events must never ride the 1 Hz telemetry
    # (finding 2.1).
    _TELEMETRY_ARTICLE_KEYS = ("article", "article_error", "raw_snippet")
    # Locks are per-event and only needed while a call is in flight; a
    # long-lived process must not accumulate one forever per event id.
    _ARTICLE_LOCK_PRUNE_THRESHOLD = 128

    @classmethod
    def _telemetry_event(cls, evt: Dict[str, Any]) -> Dict[str, Any]:
        """A snapshot-safe copy of one curated event (no article body, no raw snippet)."""
        out: Dict[str, Any] = {}
        for k, v in evt.items():
            if k in cls._TELEMETRY_ARTICLE_KEYS:
                continue
            if k == "strategy_actions" and isinstance(v, list):
                out[k] = [dict(a) if isinstance(a, dict) else a for a in v]
            elif k == "tickers" and isinstance(v, list):
                out[k] = list(v)
            elif k == "consensus" and isinstance(v, dict):
                out[k] = dict(v)
            else:
                out[k] = v
        return out

    def _telemetry_events(self, limit: int) -> List[Dict[str, Any]]:
        with self._events_lock:
            cache_key = (self._curated_version, limit)
            if self._telemetry_events_cache_key != cache_key:
                self._telemetry_events_cache = [
                    self._telemetry_event(e) for e in self.curated_events[:limit]
                ]
                self._telemetry_events_cache_key = cache_key
            return [dict(e) for e in self._telemetry_events_cache]

    def _telemetry_macro_state(self) -> Dict[str, Any]:
        """Current regime state, with any latest_event article stripped."""
        with self._events_lock:
            self._expire_fallback_if_stale(time.time())
            state = self.current_state.to_dict()
            latest = state.get("latest_event")
            if isinstance(latest, dict):
                state["latest_event"] = self._telemetry_event(latest)
            return state

    def _prune_article_locks(self) -> None:
        """Drop unreferenced locks for events no longer in the curated list."""
        with self._events_lock:
            live_ids = {e.get("id") for e in self.curated_events}
        with self._article_locks_guard:
            if len(self._article_locks) <= self._ARTICLE_LOCK_PRUNE_THRESHOLD:
                return
            stale = [
                event_id
                for event_id, entry in self._article_locks.items()
                if event_id not in live_ids and entry[1] <= 0 and not entry[0].locked()
            ]
            for event_id in stale:
                self._article_locks.pop(event_id, None)

    def _acquire_article_lock_entry(self, event_id: str) -> List[Any]:
        """Increments refcount and returns [lock, refcount] for event_id."""
        with self._article_locks_guard:
            entry = self._article_locks.get(event_id)
            if entry is None:
                entry = [threading.Lock(), 0]
                self._article_locks[event_id] = entry
            entry[1] += 1
            return entry

    def _release_article_lock_entry(self, event_id: str, entry: List[Any]) -> None:
        with self._article_locks_guard:
            entry[1] = max(0, entry[1] - 1)
        if len(self._article_locks) > self._ARTICLE_LOCK_PRUNE_THRESHOLD:
            self._prune_article_locks()

    def _get_article_lock(self, event_id: str) -> threading.Lock:
        """Back-compat helper returning the per-event lock (pruning stale entries)."""
        self._prune_article_locks()
        with self._article_locks_guard:
            entry = self._article_locks.get(event_id)
            if entry is None:
                entry = [threading.Lock(), 0]
                self._article_locks[event_id] = entry
            return entry[0]

    def get_event_article(self, event_id: str) -> Dict[str, Any]:
        """Returns the cached ~1000-word article for one curated event.

        First call generates it via the ingest model (temperature 0)
        and caches it on the event; a second call returns the cache
        without any LLM call. A failed generation leaves the event in
        state "failed" with the reason in "article_error", and a later
        explicit call retries (the gateway may have recovered since).
        Gateway offline or LLM failure returns {"ok": False, ...}
        honestly -- never a fabricated article, and never the one-line
        summary passed off as the article. Never raises.
        """
        if sys.is_finalizing():
            return {"ok": False, "event_id": event_id, "state": "none", "reason": "shutting down"}
        shut_fn = getattr(self.client, "is_shutting_down", None)
        if callable(shut_fn) and shut_fn() is True:
            return {"ok": False, "event_id": event_id, "state": "none", "reason": "shutting down"}
        with self._events_lock:
            evt = next((x for x in self.curated_events if x.get("id") == event_id), None)
        if evt is None:
            return {"ok": False, "event_id": event_id, "state": "none", "reason": "event not found"}
        entry = self._acquire_article_lock_entry(event_id)
        try:
            with entry[0]:
                with self._events_lock:
                    state = str(evt.get("article_state") or "none")
                    article = evt.get("article")
                    if state == "ready" and isinstance(article, str) and article.strip():
                        return {"ok": True, "event_id": event_id, "state": "ready", "article": article}
                    evt["article_state"] = "loading"
                    evt["article"] = None
                    evt.pop("article_error", None)
                    self._curated_version += 1
                    evt_copy = dict(evt)
                try:
                    article_text, error = self._generate_article_sync(evt_copy)
                except Exception as ex:
                    article_text, error = None, f"article generation failed: {ex}"
                with self._events_lock:
                    if article_text is None:
                        evt["article_state"] = "failed"
                        evt["article_error"] = error or "article generation failed"
                        self._curated_version += 1
                        logger.warning("Event article generation failed for %s: %s", event_id, evt["article_error"])
                        return {"ok": False, "event_id": event_id, "state": "failed", "reason": evt["article_error"]}
                    evt["article"] = article_text
                    evt["article_state"] = "ready"
                    self._curated_version += 1
                    return {"ok": True, "event_id": event_id, "state": "ready", "article": article_text}
        finally:
            self._release_article_lock_entry(event_id, entry)

    async def _generate_article_async(self, evt: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
        """One LLM call for one article. Returns (article_text, error).

        The error half is a short human-readable reason (gateway
        offline / no usable JSON / no article text / too short); the
        caller stores it as "article_error" and reports ok False.
        """
        if getattr(self.client, "is_gateway_online", False) is not True:
            return None, "gateway offline"
        system_prompt, user_prompt = build_event_article_prompts(evt)
        try:
            # Article timeout 150s (2026-11-15 A/B probe: the routed
            # model takes 69-100s to generate a ~1000-word article, so
            # the 60s client default can never complete it).
            parsed = await self.client.chat_json(
                model=self.client.model_ingest,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.0,
                max_tokens=2500,
                timeout_sec=150.0,
            )
        except Exception as ex:
            return None, f"LLM call failed: {ex}"
        if not isinstance(parsed, dict):
            return None, "LLM returned no usable JSON"
        article = parsed.get("article")
        if not isinstance(article, str) or not article.strip():
            return None, "LLM returned no article text"
        article = article.strip()
        if len(article) < ARTICLE_MIN_CHARS:
            return None, "LLM returned an article too short to be an article"
        return article, None

    async def _run_article_with_cleanup(self, evt: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
        """Generate one article, then close THIS loop's LLM session.

        Every asyncio.run() creates a loop; a session created on it must
        be closed on it before the loop ends, or it is left unclosed.
        The cleanup touches only the current loop's session, so it can
        never close a session another thread is still using.
        """
        try:
            return await self._generate_article_async(evt)
        finally:
            closer = getattr(self.client, "close_loop_session", None)
            if callable(closer):
                try:
                    await closer()
                except Exception as ex:
                    logger.debug("Article loop-session cleanup failed: %s", ex)

    def _generate_article_sync(self, evt: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
        """Runs _generate_article_async from sync code (bridge thread).

        The bridge runs on a pywebview worker thread with no running
        event loop, so asyncio.run is the normal path. If a loop is
        already running in this thread (e.g. called from async test
        code), the coroutine runs on a helper thread with its own loop
        instead of raising "asyncio.run() cannot be called from a
        running event loop".
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is None:
            return asyncio.run(self._run_article_with_cleanup(evt))
        result: Dict[str, Any] = {}

        def _runner() -> None:
            try:
                result["value"] = asyncio.run(self._run_article_with_cleanup(evt))
            except BaseException as ex:
                result["error"] = ex

        thread = threading.Thread(target=_runner, daemon=True)
        thread.start()
        thread.join()
        if "error" in result:
            raise result["error"]
        return result["value"]

    def check_trade_veto(self, side: OrderSide, competitor_name: str, is_close: bool = False) -> Tuple[bool, str]:
        """
        Enforces Strict Veto (Option A) against incoming orders from any of the 5 competitors.
        The veto only ever blocks OPENING orders. Closing / reducing a
        position lowers risk, so a close is never vetoed: under HOLD_CASH a
        trader must still be able to sell a long (or cover a short) to stop
        the bleeding instead of being locked inside a deteriorating market.
        Returns:
            (True, "PASSED") if trade complies with macro regime.
            (False, reason) if trade is strictly vetoed.
        """
        # Closing a position is risk-reducing: never veto it (item 6).
        if is_close:
            return True, "PASSED"

        with self._events_lock:
            self._expire_fallback_if_stale(time.time())
            today = date.today()
            if today != self._veto_day:
                self._veto_day = today
                self.current_state.veto_count_today = 0

            bias = self.current_state.directional_bias
            headline = self.current_state.active_headline

            if bias == "LONG_ONLY" and side == OrderSide.SELL:
                self.current_state.veto_count_today += 1
                reason = f"VETO_MACRO_LONG_ONLY: Short trade blocked by Macro Commander ({headline})"
                return False, reason

            if bias == "SHORT_ONLY" and side == OrderSide.BUY:
                self.current_state.veto_count_today += 1
                reason = f"VETO_MACRO_SHORT_ONLY: Long trade blocked by Macro Commander ({headline})"
                return False, reason

            if bias == "HOLD_CASH":
                self.current_state.veto_count_today += 1
                reason = f"VETO_MACRO_HOLD_CASH: All opening orders blocked during severe risk-off regime ({headline})"
                return False, reason

            return True, "PASSED"

    def _expire_fallback_if_stale(self, now: float) -> None:
        """Steps an expired keyword fallback down to neutral (item 12 / A3).

        A fallback regime older than FALLBACK_MAX_AGE_SEC (30 minutes)
        stops vetoing: the keyword scores that produced it are stale, and a
        directional veto must come from a live LLM synthesis, not from
        half-hour-old keyword soup.
        """
        if not self.current_state.fallback:
            return
        if self.current_state.fallback_since_ts <= 0.0:
            return
        if now - self.current_state.fallback_since_ts <= FALLBACK_MAX_AGE_SEC:
            return
        was_non_neutral = (
            self.current_state.regime != "NORMAL"
            or self.current_state.directional_bias != "BIDIRECTIONAL"
            or self.current_state.risk_multiplier != 1.0
        )
        self.current_state.regime = "NORMAL"
        self.current_state.directional_bias = "BIDIRECTIONAL"
        self.current_state.risk_multiplier = 1.0
        self.current_state.confidence = 0.50
        self.current_state.active_headline = "全球訂單流維持宏觀均衡。實時智能情報監控運行中。"
        if was_non_neutral:
            logger.info("Keyword fallback regime expired after 30m without LLM; stepped down to BIDIRECTIONAL")

    def is_quota_throttled(self) -> bool:
        """True while measured token usage has reached the daily quota.

        The `is True` guard matters: mock clients answer any attribute with
        a truthy mock, which must never read as "over quota" (item 12 /
        A4-4). Only a real boolean True counts.
        """
        fn = getattr(self.client, "is_over_quota", None)
        if not callable(fn):
            return False
        try:
            return fn() is True
        except Exception as e:
            logger.debug("Quota check failed, assuming under quota: %s", e)
            return False

    def digest_interval_sec(self, base_sec: float = 300.0) -> float:
        """Effective digest cadence (item 12 / A4-4).

        Once the daily quota is reached -- a user-set DAILY_TOKEN_QUOTA
        budget, or a 429 observed within its cooldown (F4) -- the digest
        slows from the base cadence to at least 900s so the gateway is not
        hammered while over budget. Never shortens a longer
        user-configured interval.
        """
        if self.is_quota_throttled():
            return max(float(base_sec), 900.0)
        return float(base_sec)

    def compute_weighted_sentiment(
        self, events: List[StructuredEvent], now: Optional[float] = None
    ) -> Tuple[float, float, float]:
        """Deterministic tier/urgency/time-decay weighted sentiment (item 12C).

        Returns (S, U, N): weighted sentiment in [-1, 1], weighted urgency
        in [1, 10], decay-weighted event count. Only events from the last
        60 minutes count (at most the 30 freshest); with no usable evidence
        all three are 0.0. The LLM path uses these as a prompt reference;
        the keyword fallback uses them for direction (C1 thresholds).
        """
        now = time.time() if now is None else now
        scored = []
        for e in events:
            age_min = _event_age_min(e.timestamp, now)
            if age_min > WEIGHTED_WINDOW_MIN:
                continue
            try:
                tier_w = TIER_WEIGHTS.get(int(getattr(e, "tier", 2)), 1.0)
            except (TypeError, ValueError):
                tier_w = 1.0
            urg = max(1, min(10, int(_safe_float(getattr(e, "urgency_score", 5), 5.0))))
            sent = max(-1.0, min(1.0, _safe_float(getattr(e, "sentiment_score", 0.0), 0.0)))
            urg_w = 0.5 + urg / 10.0
            decay = 0.5 ** (age_min / WEIGHTED_HALF_LIFE_MIN)
            scored.append((tier_w * urg_w * decay, sent, float(urg), decay))
        if not scored:
            return 0.0, 0.0, 0.0
        # Freshest first (largest decay), keep at most 30.
        scored.sort(key=lambda item: -item[3])
        scored = scored[:WEIGHTED_MAX_EVENTS]
        total_w = sum(w for w, _, _, _ in scored)
        if not math.isfinite(total_w) or total_w <= 0.0:
            return 0.0, 0.0, 0.0
        s = sum(w * sent for w, sent, _, _ in scored) / total_w
        u = sum(w * urg for w, _, urg, _ in scored) / total_w
        n = sum(d for _, _, _, d in scored)
        s = max(-1.0, min(1.0, s)) if math.isfinite(s) else 0.0
        u = max(0.0, min(10.0, u)) if math.isfinite(u) else 0.0
        n = max(0.0, n) if math.isfinite(n) else 0.0
        return s, u, n

    def news_sizing_multiplier(self, news_sensitivity: float = 0.5) -> float:
        """Per-strategy news sizing factor (item 12C / C2).

        base = 1 + (risk_multiplier - 1) * ((confidence - 0.5) / 0.5):
        no confidence (0.5, e.g. keyword fallback) means news does not
        move size at all; full confidence means the full risk_multiplier.
        The per-strategy factor interpolates between 1.0 and base by the
        strategy's news_sensitivity (0.0 = news-blind, 1.0 = full effect).
        Callers pass competitor.genome.news_sensitivity. Result is clamped
        to [0.5, 1.5], the risk_multiplier range.
        """
        try:
            with self._events_lock:
                rm_raw = float(self.current_state.risk_multiplier)
                conf_raw = float(self.current_state.confidence)
            sens_raw = float(news_sensitivity)
            if not (math.isfinite(rm_raw) and math.isfinite(conf_raw) and math.isfinite(sens_raw)):
                return 1.0
            rm = max(0.5, min(1.5, rm_raw))
            conf = max(0.5, min(1.0, conf_raw))
            sens = max(0.0, min(1.0, sens_raw))
        except (TypeError, ValueError):
            return 1.0
        base = 1.0 + (rm - 1.0) * ((conf - 0.5) / 0.5)
        mult = 1.0 + (base - 1.0) * sens
        return max(0.5, min(1.5, mult))

    async def synthesize_regime(self, recent_events: List[StructuredEvent]) -> MacroRegimeState:
        """
        Performs Stage 2 cross-market synthesis by prompting LLM_MODEL_COMMANDER
        with the latest structured event stream.
        """
        async with self._get_synthesis_lock():
            now = time.time()
            if not recent_events:
                with self._events_lock:
                    self.current_state.last_synthesis_ts = now
                    self.current_state.status = "ONLINE" if self.client.is_gateway_online else "STANDBY"
                    self.current_state.weighted_sentiment = 0.0
                    self.current_state.weighted_urgency = 0.0
                    self.current_state.weighted_coverage = 0.0
                    # No fresh evidence: an expired fallback still steps down
                    # (item 12 / A3), even with nothing new to synthesize.
                    self._expire_fallback_if_stale(now)
                return self.current_state

            # Ingest structured events into curated timeline (newest first), ensuring Traditional Chinese headline & summary.
            # Iterate in reverse so recent_events[0] lands at curated_events[0].
            with self._events_lock:
                inserted = False
                for e in reversed(recent_events):
                    zh_head, zh_sum = IntelligenceHarvester.ensure_traditional_chinese(e)
                    dedup_key = e.raw_title or zh_head
                    digest_hex = hashlib.sha256(dedup_key.encode("utf-8")).hexdigest()[:8]
                    evt_id = f"evt_{int(now)}_{digest_hex}"
                    already_exists = any(
                        (
                            (e.raw_title == x.get("raw_title"))
                            if (e.raw_title and x.get("raw_title"))
                            else (x.get("headline") == zh_head)
                        )
                        for x in self.curated_events
                    )
                    if not already_exists:
                        local_tm = time.localtime(now)
                        self.curated_events.insert(0, {
                            "id": evt_id,
                            "event_ts": int(now),
                            "date_time": time.strftime("%Y-%m-%d %H:%M:%S", local_tm),
                            "time": time.strftime("%H:%M:%S", local_tm),
                            "source": e.source,
                            "domain": e.domain,
                            "urgency": e.urgency_score,
                            "sentiment": round(_safe_float(e.sentiment_score, 0.0), 2),
                            "headline": zh_head,
                            "summary": zh_sum,
                            "raw_title": e.raw_title,
                            "raw_snippet": getattr(e, "raw_content", "") or "",
                            "tier": e.tier,
                            "thread_id": e.thread_id,
                            "consensus": e.consensus,
                            "strategy_actions": [],
                            "tickers": _dedup_tickers(e.entities_tickers),
                            "article": None,
                            "article_state": "none",
                        })
                        inserted = True
                if len(self.curated_events) > 60:
                    self.curated_events = self.curated_events[:60]
                if inserted:
                    self._curated_version += 1

            # Format top items for commander
            lines = []
            for e in recent_events[-15:]:
                sent_tag = f"+{e.sentiment_score:.2f}" if e.sentiment_score >= 0 else f"{e.sentiment_score:.2f}"
                lines.append(f"- [{e.source} | Urg {e.urgency_score}/10 | Sent {sent_tag}] {e.summary}")
            intel_digest = "\n".join(lines)

            # Weighted reference (item 12C / C1): deterministic tier /
            # urgency / time-decay scores. The LLM still judges, but it
            # sees the same numbers the keyword fallback would use.
            w_s, w_u, w_n = self.compute_weighted_sentiment(recent_events, now)

            system_prompt = (
                "You are the Supreme Macro Commander governing a 5-strategy ETH/USD crypto trading arena.\n"
                "Your mission: synthesize real-time news/events and output an authoritative macro regime.\n"
                "You have STRICT VETO POWER. If conditions strongly favor one direction (e.g. US election pro-crypto surge),\n"
                "command LONG_ONLY so all counter-trend short trades are immediately vetoed.\n"
                "If black swan / regulatory crackdown occurs, command SHORT_ONLY or HOLD_CASH.\n"
                "Output MUST be a single JSON object with this exact schema:\n"
                "{\n"
                '  "regime": "BULLISH_SURGE" | "BEARISH_PANIC" | "HIGH_VOLATILITY_CHOP" | "NORMAL",\n'
                '  "directional_bias": "LONG_ONLY" | "SHORT_ONLY" | "BIDIRECTIONAL" | "HOLD_CASH",\n'
                '  "risk_multiplier": float between 0.5 and 1.5,\n'
                '  "active_headline": "Concise headline (under 15 words summarizing the macro narrative)",\n'
                '  "confidence": float between 0.5 and 1.0\n'
                "}\n"
                "CRITICAL REQUIREMENT: The 'active_headline' MUST be written in Traditional Chinese (繁體中文), under 25 words summarizing the current macro narrative."
            )

            user_prompt = (
                f"Analyze this live intelligence digest and declare the macro regime:\n\n{intel_digest}\n\n"
                f"Weighted reference (deterministic, tier/urgency/60-min half-life): "
                f"S={w_s:+.2f}, U={w_u:.1f}, N={w_n:.1f}. "
                f"Treat N<2 as insufficient evidence for a directional call; "
                f"HOLD_CASH needs S<-0.65, U>=9 and confidence>=0.8."
            )

            parsed = None
            if self.client.is_gateway_online:
                parsed = await self.client.chat_json(
                    model=self.client.model_commander,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=0.0,
                    max_tokens=600,
                )

            log_msg: Optional[Tuple[str, str, str]] = None
            with self._events_lock:
                self.current_state.weighted_sentiment = w_s
                self.current_state.weighted_urgency = w_u
                self.current_state.weighted_coverage = w_n
                self.current_state.total_evaluations += 1
                self.current_state.last_synthesis_ts = now

                if parsed and isinstance(parsed, dict) and "directional_bias" in parsed:
                    regime = str(parsed.get("regime", "NORMAL")).upper()
                    if regime not in {"BULLISH_SURGE", "BEARISH_PANIC", "HIGH_VOLATILITY_CHOP", "NORMAL"}:
                        regime = "NORMAL"

                    bias = str(parsed.get("directional_bias", "BIDIRECTIONAL")).upper()
                    if bias not in {"LONG_ONLY", "SHORT_ONLY", "BIDIRECTIONAL", "HOLD_CASH"}:
                        bias = "BIDIRECTIONAL"

                    # LLM numbers are untrusted text: a non-numeric value (e.g.
                    # "high") falls back to the safe default instead of raising
                    # out of the veto pipeline (item 6).
                    risk_mult = max(0.5, min(1.5, _safe_float(parsed.get("risk_multiplier"), 1.0)))
                    conf = max(0.0, min(1.0, _safe_float(parsed.get("confidence"), 0.70)))
                    raw_hl = parsed.get("active_headline")
                    headline = str(raw_hl).strip() if raw_hl is not None else ""
                    if not headline:
                        headline = "Macro regime updated from live stream"

                    self.current_state.regime = regime
                    self.current_state.directional_bias = bias
                    self.current_state.risk_multiplier = risk_mult
                    self.current_state.confidence = conf
                    self.current_state.active_headline = headline
                    self.current_state.status = "ONLINE"
                    # LLM is back in charge: the fallback provenance clears.
                    self.current_state.fallback = False
                    self.current_state.fallback_since_ts = 0.0
                    log_msg = (regime, bias, headline)
                else:
                    # Fallback (item 12C / C1): if the LLM is unreachable or
                    # unparseable, direction comes from the weighted scores
                    # (S/U/N) instead of the old unweighted average + max.
                    # The bar is deliberately conservative: one extreme event
                    # (N < 1.9) can never flip the arena, and HOLD_CASH is never
                    # set here -- it needs live LLM confidence >= 0.8, which a
                    # keyword fallback by definition does not have. Confidence
                    # resets to 0.50 ("no confidence"), so news sizing (C2) is
                    # neutral until the LLM is back.
                    top_ev = max(
                        recent_events,
                        key=lambda ev: (
                            _safe_float(getattr(ev, "urgency_score", 5), 5.0),
                            abs(_safe_float(getattr(ev, "sentiment_score", 0.0), 0.0)),
                        ),
                    )
                    if w_s > 0.45 and w_u >= 7 and w_n >= 1.9:
                        self.current_state.regime = "BULLISH_SURGE"
                        self.current_state.directional_bias = "LONG_ONLY"
                        self.current_state.risk_multiplier = 1.25
                        self.current_state.active_headline = (top_ev.summary or "")[:80]
                    elif w_s < -0.45 and w_u >= 7 and w_n >= 1.9:
                        self.current_state.regime = "BEARISH_PANIC"
                        self.current_state.directional_bias = "SHORT_ONLY"
                        self.current_state.risk_multiplier = 0.75
                        self.current_state.active_headline = (top_ev.summary or "")[:80]
                    else:
                        self.current_state.regime = "NORMAL"
                        self.current_state.directional_bias = "BIDIRECTIONAL"
                        self.current_state.risk_multiplier = 1.0
                        self.current_state.active_headline = "全球訂單流維持宏觀均衡。實時智能情報監控運行中。"
                    self.current_state.confidence = 0.50

                    # Emergency backup only (item 12 / A3 option 2): the keyword
                    # fallback is marked as such, and after 30 minutes without
                    # the LLM it steps down to neutral instead of letting stale
                    # keyword scores keep vetoing trades.
                    if not self.current_state.fallback:
                        self.current_state.fallback = True
                        self.current_state.fallback_since_ts = now
                    self._expire_fallback_if_stale(now)

                    self.current_state.status = "STANDBY" if not self.client.is_gateway_online else "ONLINE"

                self._last_synthesized_keys = tuple((e.raw_title or e.summary) for e in recent_events[-10:])
                if self.curated_events:
                    self.current_state.latest_event = self.curated_events[0]

            if log_msg is not None:
                logger.info("Macro Commander Regime Updated: %s | Bias: %s | Headline: %s", *log_msg)

            return self.current_state

