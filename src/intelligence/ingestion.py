from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
import hashlib
import json
import logging
import time
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set
import xml.etree.ElementTree as ET
import aiohttp

from src.intelligence.omniroute_client import OmniRouteClient

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 TradeBot0-Intelligence/1.0"


@dataclass
class RawEvent:
    source: str
    domain: str  # "crypto", "macro", "geopolitics", "tech", "prediction"
    title: str
    url: str
    timestamp: float
    raw_content: str = ""
    entities: List[str] = field(default_factory=list)


@dataclass
class StructuredEvent:
    timestamp: str  # ISO8601
    source: str
    domain: str
    entities_tickers: List[str]
    urgency_score: int  # 1 to 10
    sentiment_score: float  # -1.0 to +1.0
    summary: str
    raw_title: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "source": self.source,
            "domain": self.domain,
            "entities_tickers": self.entities_tickers,
            "urgency_score": self.urgency_score,
            "sentiment_score": round(self.sentiment_score, 2),
            "summary": self.summary,
            "raw_title": self.raw_title,
        }


class DeduplicationBuffer:
    """
    High-performance in-memory ring buffer with SHA-256 Title+URL hashing.
    Prevents redundant token consumption by filtering duplicate articles.
    """

    def __init__(self, capacity: int = 5000) -> None:
        self.capacity = capacity
        self.seen_hashes: Set[str] = set()
        self.ring: deque[str] = deque(maxlen=capacity)

    def is_new(self, title: str, url: str) -> bool:
        if not title:
            return False
        norm = f"{title.strip().lower()}|{url.strip().lower()}"
        h = hashlib.sha256(norm.encode("utf-8")).hexdigest()
        if h in self.seen_hashes:
            return False
        if len(self.ring) >= self.capacity:
            oldest = self.ring.popleft()
            self.seen_hashes.discard(oldest)
        self.seen_hashes.add(h)
        self.ring.append(h)
        return True

    def __len__(self) -> int:
        return len(self.seen_hashes)


def parse_rss_atom(xml_text: str, source_name: str, domain: str) -> List[RawEvent]:
    """
    Parses RSS 2.0 and Atom feeds into a standardized list of RawEvent items.
    """
    events: List[RawEvent] = []
    if not xml_text or not isinstance(xml_text, str):
        return events

    try:
        root = ET.fromstring(xml_text)
    except Exception as e:
        logger.debug("Failed to parse XML for %s: %s", source_name, e)
        return events

    now = time.time()

    # RSS 2.0 (<rss><channel><item>...</item></channel></rss>)
    for item in root.findall(".//item"):
        title_el = item.find("title")
        link_el = item.find("link")
        desc_el = item.find("description")

        title = title_el.text.strip() if (title_el is not None and title_el.text) else ""
        link = link_el.text.strip() if (link_el is not None and link_el.text) else ""
        desc = desc_el.text.strip() if (desc_el is not None and desc_el.text) else ""

        if title:
            events.append(RawEvent(
                source=source_name,
                domain=domain,
                title=title,
                url=link or source_name,
                timestamp=now,
                raw_content=desc[:300]
            ))

    # Atom (<feed><entry>...</entry></feed>)
    # Handle namespace if present
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    entries = root.findall(".//atom:entry", ns) or root.findall(".//entry")
    for entry in entries:
        title_el = entry.find("atom:title", ns) if "atom" in ns else None
        if title_el is None:
            title_el = entry.find("title")
        link_el = entry.find("atom:link", ns) if "atom" in ns else None
        if link_el is None:
            link_el = entry.find("link")

        title = title_el.text.strip() if (title_el is not None and title_el.text) else ""
        link = ""
        if link_el is not None:
            link = link_el.get("href") or link_el.text or ""

        if title:
            events.append(RawEvent(
                source=source_name,
                domain=domain,
                title=title,
                url=link or source_name,
                timestamp=now,
            ))

    return events


def parse_polymarket_events(data: Any) -> List[RawEvent]:
    """
    Parses Polymarket Gamma API events, tracking active geopolitical/political/crypto prediction odds.
    """
    events: List[RawEvent] = []
    if not isinstance(data, list):
        return events

    now = time.time()
    for item in data[:30]:
        if not isinstance(item, dict):
            continue
        title = item.get("title") or item.get("question") or ""
        vol = float(item.get("volume24hr") or 0.0)
        slug = item.get("slug") or ""
        url = f"https://polymarket.com/event/{slug}" if slug else "https://polymarket.com"

        markets = item.get("markets", [])
        odds_str = ""
        if isinstance(markets, list) and markets:
            outcomes = markets[0].get("outcomes", [])
            outcome_prices = markets[0].get("outcomePrices", [])
            if outcomes and outcome_prices:
                try:
                    pairs = [f"{o}: {float(p)*100:.0f}%" for o, p in zip(outcomes, outcome_prices)]
                    odds_str = " | Odds: " + ", ".join(pairs)
                except Exception:
                    pass

        if title:
            full_title = f"[Polymarket 24h Vol ${vol:,.0f}] {title}{odds_str}"
            events.append(RawEvent(
                source="Polymarket",
                domain="prediction",
                title=full_title,
                url=url,
                timestamp=now,
                raw_content=odds_str
            ))
    return events


def parse_reddit_posts(data: Any, subreddit: str, domain: str) -> List[RawEvent]:
    """
    Parses Reddit JSON listing (r/{subreddit}/hot.json or new.json).
    """
    events: List[RawEvent] = []
    if not isinstance(data, dict):
        return events

    children = data.get("data", {}).get("children", [])
    now = time.time()
    for child in children:
        d = child.get("data", {})
        title = d.get("title", "").strip()
        score = int(d.get("score", 0))
        permalink = d.get("permalink", "")
        url = f"https://reddit.com{permalink}" if permalink else f"https://reddit.com/r/{subreddit}"

        # Focus on posts with positive engagement
        if title and score >= 5:
            full_title = f"[r/{subreddit} \u2191{score}] {title}"
            events.append(RawEvent(
                source=f"Reddit r/{subreddit}",
                domain=domain,
                title=full_title,
                url=url,
                timestamp=now,
            ))
    return events


class IntelligenceHarvester:
    """
    Stage 1 Harvester: Ingests raw news streams, deduplicates, and uses
    LLM_MODEL_INGEST to parse, tag entities, score urgency and sentiment.
    Dispatches out-of-band interrupts on urgency >= 8.
    """

    def __init__(
        self,
        client: OmniRouteClient,
        dedup_buffer: Optional[DeduplicationBuffer] = None,
        on_urgent_interrupt: Optional[Callable[[StructuredEvent], Coroutine[Any, Any, None]]] = None,
    ) -> None:
        self.client = client
        self.dedup = dedup_buffer or DeduplicationBuffer(capacity=5000)
        self.on_urgent_interrupt = on_urgent_interrupt

        # Rolling storage of recent structured events
        self.recent_structured_events: deque[StructuredEvent] = deque(maxlen=200)
        self.is_running: bool = False
        self._harvest_task: Optional[asyncio.Task] = None

    def push_raw_events(self, raw_events: List[RawEvent]) -> List[RawEvent]:
        """Filters incoming raw events through the deduplication buffer."""
        fresh = []
        for e in raw_events:
            if self.dedup.is_new(e.title, e.url):
                fresh.append(e)
        return fresh

    async def process_batch(self, events: List[RawEvent]) -> List[StructuredEvent]:
        """
        Processes a micro-batch of raw events with LLM_MODEL_INGEST to produce structured JSON events.
        """
        if not events:
            return []

        # Build concise extraction prompt
        lines = []
        for idx, e in enumerate(events[:12], start=1):
            lines.append(f"{idx}. [{e.source} | {e.domain}] {e.title}")
        news_block = "\n".join(lines)

        system_prompt = (
            "You are an elite quantitative intelligence extractor. Analyze the financial/crypto/geopolitical news items.\n"
            "Output a JSON object with key 'events' containing an array of objects with the following schema:\n"
            "[\n"
            "  {\n"
            '    "index": 1,\n'
            '    "entities_tickers": ["BTC", "FED"],\n'
            '    "urgency_score": 1_to_10,\n'
            '    "sentiment_score": -1.0_to_1.0,\n'
            '    "summary": "Brief 15-word impact summary"\n'
            "  }\n"
            "]\n"
            "Urgency rubric: 1-4=Routine noise, 5-7=Notable market mover, 8-10=Black Swan, Fed rate shock, election result, major war, or SEC enforcement."
        )

        user_prompt = f"Extract structured intelligence for these events:\n\n{news_block}"

        parsed_json = await self.client.chat_json(
            model=self.client.model_ingest,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.0,
            max_tokens=1500,
        )

        structured_results: List[StructuredEvent] = []
        iso_now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        if parsed_json and "events" in parsed_json and isinstance(parsed_json["events"], list):
            for item in parsed_json["events"]:
                try:
                    idx = int(item.get("index", 1)) - 1
                    raw = events[idx] if (0 <= idx < len(events)) else events[0]
                    urgency = max(1, min(10, int(item.get("urgency_score", 5))))
                    sentiment = max(-1.0, min(1.0, float(item.get("sentiment_score", 0.0))))
                    tickers = [str(t).upper() for t in item.get("entities_tickers", [])]
                    summary = str(item.get("summary", raw.title))

                    se = StructuredEvent(
                        timestamp=iso_now,
                        source=raw.source,
                        domain=raw.domain,
                        entities_tickers=tickers,
                        urgency_score=urgency,
                        sentiment_score=sentiment,
                        summary=summary,
                        raw_title=raw.title,
                    )
                    structured_results.append(se)
                    self.recent_structured_events.append(se)

                    # Trigger out-of-band interrupt if event is critical
                    if urgency >= 8 and self.on_urgent_interrupt:
                        logger.warning(
                            "CRITICAL INTELLIGENCE SHOCK (Urgency %d): %s [%s]",
                            urgency, summary, raw.title[:80]
                        )
                        asyncio.create_task(self.on_urgent_interrupt(se))

                except Exception as ex:
                    logger.debug("Failed parsing individual event extraction: %s", ex)
        else:
            # Fallback heuristic extraction if LLM is offline or returned unparseable response
            for raw in events[:12]:
                title_lower = raw.title.lower()
                urgency = 5
                sentiment = 0.0
                if any(w in title_lower for w in ["soars", "surges", "breakout", "all-time high", "rate cut", "wins election", "bullish"]):
                    sentiment = 0.65
                elif any(w in title_lower for w in ["crashes", "plunges", "war", "ban", "lawsuit", "hacked", "bearish", "indicted"]):
                    sentiment = -0.65

                if any(w in title_lower for w in ["election result", "fed interest rate", "black swan", "halted", "emergency"]):
                    urgency = 8

                se = StructuredEvent(
                    timestamp=iso_now,
                    source=raw.source,
                    domain=raw.domain,
                    entities_tickers=["BTC"],
                    urgency_score=urgency,
                    sentiment_score=sentiment,
                    summary=raw.title[:100],
                    raw_title=raw.title,
                )
                structured_results.append(se)
                self.recent_structured_events.append(se)
                if urgency >= 8 and self.on_urgent_interrupt:
                    asyncio.create_task(self.on_urgent_interrupt(se))

        return structured_results

    def get_latest_events(self, count: int = 30) -> List[StructuredEvent]:
        """Returns the most recent structured events."""
        return list(self.recent_structured_events)[-count:]

