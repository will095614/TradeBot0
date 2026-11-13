from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from src.arena.order import OrderSide
from src.intelligence.omniroute_client import OmniRouteClient
from src.intelligence.ingestion import IntelligenceHarvester, StructuredEvent

logger = logging.getLogger(__name__)


def _safe_float(value: Any, default: float) -> float:
    """Parses an untrusted numeric value (LLM output / feed data).

    Returns `default` when the value is missing or not a number, instead of
    raising. A failed parse must never take down the veto pipeline (item 6).
    """
    try:
        return float(value)
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
            "veto_count_today": self.veto_count_today,
            "total_evaluations": self.total_evaluations,
            "status": self.status,
            "latest_event": self.latest_event,
        }


class MacroCommander:
    """
    Stage 2 Macro Commander: Synthesizes cross-market intelligence from OmniRoute
    and enforces Strict Veto (Option A) across all 6 arena competitors.
    """

    STRAT_LABELS: Dict[str, str] = {
        "comp_agg": "Strategy 1 (AGG)",
        "comp_cons": "Strategy 2 (CONS)",
        "comp_atr": "Strategy 3 (ATR)",
        "comp_trail": "Strategy 4 (TRAIL)",
        "comp_orb": "Strategy 5 (ORB)",
        "comp_vwap": "Strategy 6 (Mean)",
    }

    def __init__(self, client: OmniRouteClient, harvester: Optional[IntelligenceHarvester] = None) -> None:
        self.client = client
        self.harvester = harvester or IntelligenceHarvester(client=client)
        self.current_state = MacroRegimeState()
        self.synthesis_lock = asyncio.Lock()
        self.last_synthesis_time: float = 0.0
        self.curated_events: List[Dict[str, Any]] = []
        self._seed_default_events()

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
        self.current_state.latest_event = None

    def ensure_traditional_chinese_seed_events(self) -> None:
        """
        Guarantees that all events currently in curated_events have Traditional Chinese
        headlines and summaries. Used during bootstrap and reset before UI reveal.
        """
        for evt in self.curated_events:
            head = evt.get("headline", "")
            sum_txt = evt.get("summary", "")
            if not IntelligenceHarvester._contains_cjk(head) or not IntelligenceHarvester._contains_cjk(sum_txt):
                dummy_event = StructuredEvent(
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
        if not self.curated_events:
            # No real event yet: nothing honest to annotate. Never re-seed
            # fabricated events just to have something to attach to (item 6).
            return

        active_evt = self.curated_events[0] if self.curated_events else None
        if not active_evt:
            return

        acts = active_evt.setdefault("strategy_actions", [])
        # Retain only the latest action per strategy to prevent spamming
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

    async def refresh_digest_async(self) -> MacroRegimeState:
        """
        Triggers an AI-driven refresh of macro intelligence, fetching genuine live RSS feeds
        over HTTP and synthesizing through OmniRoute or local deterministic NLP.
        """
        try:
            await self.client.check_health()
            try:
                raw_events = await asyncio.to_thread(self.harvester.fetch_live_feeds, 5, 3.5)
                if raw_events:
                    structured = await self.harvester.process_batch(raw_events)
                    if structured:
                        return await self.synthesize_regime(structured)
            except Exception as ex:
                if "cannot schedule new futures after shutdown" in str(ex):
                    logger.debug("Live feed harvest skipped during shutdown: %s", ex)
                else:
                    logger.warning("Error harvesting live feeds in refresh_digest_async: %s", ex)

            recent = self.harvester.get_latest_events(10)
            if recent:
                return await self.synthesize_regime(recent)
            return self.current_state
        finally:
            if getattr(self.client, "_owns_session", False):
                await self.client.close()

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
                logger.debug("Failed to read quota from client, falling back to estimate: %s", e)
        elif tokens_used > 0:
            quota_pct = max(0.0, round((1.0 - (tokens_used / 100000.0)) * 100.0, 1))

        tot_tokens = tokens_used + tokens_saved
        dedup_pct = round((tokens_saved / tot_tokens) * 100.0, 1) if tot_tokens > 0 else 0.0

        return {
            "omniroute": {
                "status": status_text,
                "endpoint": str(getattr(self.client, "base_url", "http://localhost:20128/v1")),
                "model_ingest": str(getattr(self.client, "model_ingest", "auto")),
                "model_commander": str(getattr(self.client, "model_commander", "auto")),
                "quota_pct": quota_pct,
                "tokens_used": tokens_used,
                "tokens_saved": tokens_saved,
                "dedup_pct": dedup_pct,
                "total_requests": int(getattr(self.client, "total_requests", 0)),
                "successful_requests": int(getattr(self.client, "successful_requests", 0)),
                "retried_requests": int(getattr(self.client, "retried_requests", 0)),
                "failed_requests": int(getattr(self.client, "failed_requests", 0)),
                "concurrency_limit": int(getattr(self.client, "max_concurrent", 25)),
            },
            "macro_state": self.current_state.to_dict(),
            "events": self.curated_events[:25],
        }

    def check_trade_veto(self, side: OrderSide, competitor_name: str, is_close: bool = False) -> Tuple[bool, str]:
        """
        Enforces Strict Veto (Option A) against incoming orders from any of the 6 competitors.
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

        bias = self.current_state.directional_bias

        if bias == "LONG_ONLY" and side == OrderSide.SELL:
            self.current_state.veto_count_today += 1
            reason = f"VETO_MACRO_LONG_ONLY: Short trade blocked by Macro Commander ({self.current_state.active_headline})"
            return False, reason

        if bias == "SHORT_ONLY" and side == OrderSide.BUY:
            self.current_state.veto_count_today += 1
            reason = f"VETO_MACRO_SHORT_ONLY: Long trade blocked by Macro Commander ({self.current_state.active_headline})"
            return False, reason

        if bias == "HOLD_CASH":
            self.current_state.veto_count_today += 1
            reason = f"VETO_MACRO_HOLD_CASH: All opening orders blocked during severe risk-off regime ({self.current_state.active_headline})"
            return False, reason

        return True, "PASSED"

    async def synthesize_regime(self, recent_events: List[StructuredEvent]) -> MacroRegimeState:
        """
        Performs Stage 2 cross-market synthesis by prompting LLM_MODEL_COMMANDER
        with the latest structured event stream.
        """
        async with self.synthesis_lock:
            now = time.time()
            if not recent_events:
                self.current_state.last_synthesis_ts = now
                self.current_state.status = "ONLINE" if self.client.is_gateway_online else "STANDBY"
                return self.current_state

            # Ingest structured events into curated timeline (newest first), ensuring Traditional Chinese headline & summary
            for e in recent_events:
                zh_head, zh_sum = IntelligenceHarvester.ensure_traditional_chinese(e)
                dedup_key = e.raw_title or zh_head
                evt_id = f"evt_{int(now)}_{abs(hash(dedup_key)) % 10000}"
                already_exists = any(
                    (e.raw_title and x.get("raw_title") == e.raw_title) or x.get("headline") == zh_head
                    for x in self.curated_events
                )
                if not already_exists:
                    self.curated_events.insert(0, {
                        "id": evt_id,
                        "time": time.strftime("%H:%M:%S"),
                        "source": e.source,
                        "domain": e.domain,
                        "urgency": e.urgency_score,
                        "sentiment": round(e.sentiment_score, 2),
                        "headline": zh_head,
                        "summary": zh_sum,
                        "raw_title": e.raw_title,
                        "strategy_actions": [],
                    })
            if len(self.curated_events) > 60:
                self.curated_events = self.curated_events[:60]

            # Format top items for commander
            lines = []
            for e in recent_events[-15:]:
                sent_tag = f"+{e.sentiment_score:.2f}" if e.sentiment_score >= 0 else f"{e.sentiment_score:.2f}"
                lines.append(f"- [{e.source} | Urg {e.urgency_score}/10 | Sent {sent_tag}] {e.summary}")
            intel_digest = "\n".join(lines)

            system_prompt = (
                "You are the Supreme Macro Commander governing a 6-strategy crypto trading arena.\n"
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

            user_prompt = f"Analyze this live intelligence digest and declare the macro regime:\n\n{intel_digest}"

            parsed = None
            if self.client.is_gateway_online:
                parsed = await self.client.chat_json(
                    model=self.client.model_commander,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=0.0,
                    max_tokens=600,
                )

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
                headline = str(parsed.get("active_headline", "Macro regime updated from live stream"))

                self.current_state.regime = regime
                self.current_state.directional_bias = bias
                self.current_state.risk_multiplier = risk_mult
                self.current_state.confidence = conf
                self.current_state.active_headline = headline
                self.current_state.status = "ONLINE"
                logger.info("Macro Commander Regime Updated: %s | Bias: %s | Headline: %s", regime, bias, headline)
            else:
                # Fallback: if LLM unreachable or unparseable, compute deterministic sentiment aggregate.
                # Conservative bar on purpose: without the LLM this is keyword
                # soup, so a single bearish word (sentiment -0.45) plus a
                # common urgency-7 word ("rate"/"sec"/"fed") must NOT flip the
                # whole arena into a directional veto. |avg_sent| >= 0.60
                # needs at least two net directional words and urgency >= 8
                # needs a genuinely severe keyword (item 6).
                avg_sent = sum(e.sentiment_score for e in recent_events) / len(recent_events)
                max_urg = max(e.urgency_score for e in recent_events)

                if avg_sent > 0.60 and max_urg >= 8:
                    self.current_state.regime = "BULLISH_SURGE"
                    self.current_state.directional_bias = "LONG_ONLY"
                    self.current_state.risk_multiplier = 1.25
                    self.current_state.active_headline = recent_events[-1].summary[:80]
                elif avg_sent < -0.60 and max_urg >= 8:
                    self.current_state.regime = "BEARISH_PANIC"
                    self.current_state.directional_bias = "SHORT_ONLY"
                    self.current_state.risk_multiplier = 0.75
                    self.current_state.active_headline = recent_events[-1].summary[:80]
                else:
                    self.current_state.regime = "NORMAL"
                    self.current_state.directional_bias = "BIDIRECTIONAL"
                    self.current_state.risk_multiplier = 1.0
                    self.current_state.active_headline = "全球訂單流維持宏觀均衡。實時智能情報監控運行中。"

                self.current_state.status = "STANDBY" if not self.client.is_gateway_online else "ONLINE"

            if self.curated_events:
                self.current_state.latest_event = self.curated_events[0]

            return self.current_state

