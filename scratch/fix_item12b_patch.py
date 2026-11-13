#!/usr/bin/env python3
"""Fix item 12B: forum collection, phase 1 = StockTwits only (TradeBot0).

Applies exact-once-verified replacements to the PC project tree (run with
cwd = project root) and, identically, to the local audit copy.
Every replacement is verified to occur exactly once before anything is
written; on any mismatch the script aborts without touching a file.
Newline style is preserved (files are LF; open with newline="").

Design basis: ~/workspace/tradebot_audit/item12_design.md, section B,
as amended by the user 2026-11-13:
  - SCOPE CHANGE 1 (Reddit dropped): every user would need their own
    OAuth app, which conflicts with "anyone can use it". No Reddit OAuth
    client, no Reddit credential reading, no Reddit dependency. D3 void.
  - SCOPE CHANGE 2 (no-login sources only, applies to B and all future
    sources): only sources that need no login / registration / API key.
    StockTwits public v2 was verified from the PC 2026-11-13 (HTTP 200,
    no auth, just a User-Agent) for streams/symbol/ETH.json,
    ETH.X.json, BTC.X.json and trending/symbols.json. Tree News (needs a
    key), Reddit (OAuth), X (paid), Discord/Telegram (user channels) are
    NOT connected and no logic for them is written.
  - StockTwits "ETH" is the Grayscale ETF (NYSEArca), not crypto: the
    crypto streams are ETH.X and BTC.X (verified from the PC).

What this patch does:
  1. FEED_REGISTRY: removes Tree News (key) and the 2 Reddit entries
     (OAuth); adds Decrypt (rss) and StockTwits ETH.X / BTC.X (type
     stocktwits). The registry now holds no-login sources only.
  2. Registry-driven fetcher: IntelligenceHarvester.fetch_from_registry()
     dispatches by type (rss/atom -> parse_rss_atom, rest_json ->
     parse_polymarket_events); stocktwits entries are owned by
     ForumCollector (forum batch, own cadence) and are explicitly skipped
     here so the same stream is never scored twice per digest.
     fetch_live_feeds() now calls it; the 4 hardcoded RSS targets are
     gone (all four are registry entries; behaviour unchanged).
  3. ForumCollector (new file src/intelligence/forum_collector.py):
     StockTwits streams only, 15-minute collect cadence, 12 summaries /
     rolling hour cap, ARENA_FAST_TEST short-circuit (no network in
     tests). Symbols are read from the registry's stocktwits entries.
     Extension point for phase 2: a new source method returning RawEvents
     with domain="forum", called from collect_async() next to
     _collect_stocktwits(); the registry stays the single source list.
     No LLM Discovery call exists in phase 1: the streams are fixed, so
     there is nothing to discover; thread picking returns with Reddit.
  4. Events gain tier / thread_id / consensus (StructuredEvent; RawEvent
     gains tier / thread_id). parse_stocktwits_stream() builds one
     RawEvent per stream: title carries the latest message (dedup key),
     raw_content is the top-20 messages concatenated (<= 1200 chars).
     process_batch() carries the fields through and asks the LLM for a
     reply consensus on forum threads only; the keyword fallback derives
     one deterministically from the event score.
  5. refresh_digest_async(): news batch first, then a separate forum
     batch (forum chatter never crowds breaking news out of the 6-event
     cap), then synthesize on the combined structured events. Forum
     failures never break the news path.
"""
import os
import sys

if not os.path.isdir("src/gui"):
    print("FAIL: run this script from the project root (src/gui not found)")
    sys.exit(1)

REPLACEMENTS = []
NEW_FILES = {}


def rep(path, old, new):
    REPLACEMENTS.append((path, old, new))


# =========================================================== 1. registry: no-login only
rep("src/intelligence/ingestion.py", """    # Tier 0: Breaking Websocket / Sub-second tape
    {"id": "tree_news_ws", "name": "Tree News", "tier": 0, "domain": "crypto", "type": "websocket", "url": "wss://news.treeofalpha.com/ws"},
    # Tier 1: 30-60s Breaking Wires, Prediction & Geopolitics""",
"""    # User rule 2026-11-13: no-login sources ONLY. Tree News (needs an API
    # key), Reddit (per-user OAuth), X (paid), Discord/Telegram (user
    # channels) are NOT listed here and are never fetched.
    # Tier 1: 30-60s Breaking Wires, Prediction & Geopolitics""")

rep("src/intelligence/ingestion.py", """    {"id": "reddit_crypto", "name": "Reddit r/CryptoCurrency", "tier": 2, "domain": "crypto", "type": "reddit_json", "url": "https://www.reddit.com/r/CryptoCurrency/hot.json?limit=25"},
    {"id": "reddit_wsb", "name": "Reddit r/wallstreetbets", "tier": 2, "domain": "macro", "type": "reddit_json", "url": "https://www.reddit.com/r/wallstreetbets/hot.json?limit=25"},""",
"""    {"id": "decrypt_wire", "name": "Decrypt", "tier": 2, "domain": "crypto", "type": "rss", "url": "https://decrypt.co/feed"},
    {"id": "stocktwits_ethx", "name": "StockTwits ETH.X", "tier": 2, "domain": "forum", "type": "stocktwits", "url": "https://api.stocktwits.com/api/2/streams/symbol/ETH.X.json"},
    {"id": "stocktwits_btcx", "name": "StockTwits BTC.X", "tier": 2, "domain": "forum", "type": "stocktwits", "url": "https://api.stocktwits.com/api/2/streams/symbol/BTC.X.json"},""")

# datetime import (StockTwits created_at parsing)
rep("src/intelligence/ingestion.py", """import asyncio
from collections import deque
from dataclasses import dataclass, field""",
"""import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime""")

# =========================================================== 2. event fields
rep("src/intelligence/ingestion.py", """@dataclass
class RawEvent:
    source: str
    domain: str  # "crypto", "macro", "geopolitics", "tech", "prediction"
    title: str
    url: str
    timestamp: float
    raw_content: str = ""
    entities: List[str] = field(default_factory=list)""",
"""@dataclass
class RawEvent:
    source: str
    domain: str  # "crypto", "macro", "geopolitics", "tech", "prediction", "forum"
    title: str
    url: str
    timestamp: float
    raw_content: str = ""
    entities: List[str] = field(default_factory=list)
    tier: int = 2  # source tier from FEED_REGISTRY (0-3); 2 = general news/forum
    thread_id: Optional[str] = None  # forum thread key, e.g. "stocktwits:ETH.X\"""")

rep("src/intelligence/ingestion.py", """@dataclass
class StructuredEvent:
    timestamp: str  # ISO8601
    source: str
    domain: str
    entities_tickers: List[str]
    urgency_score: int  # 1 to 10
    sentiment_score: float  # -1.0 to +1.0
    summary: str
    raw_title: str = ""
    headline_zh: str = ""

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
            "headline_zh": self.headline_zh,
        }""",
"""@dataclass
class StructuredEvent:
    timestamp: str  # ISO8601
    source: str
    domain: str
    entities_tickers: List[str]
    urgency_score: int  # 1 to 10
    sentiment_score: float  # -1.0 to +1.0
    summary: str
    raw_title: str = ""
    headline_zh: str = ""
    tier: int = 2  # source tier (0-3); feeds the C1 weighted sentiment formula
    thread_id: Optional[str] = None  # forum thread key, e.g. "stocktwits:ETH.X"
    consensus: Optional[Dict[str, float]] = None  # forum reply split {bullish, bearish, neutral}

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
            "headline_zh": self.headline_zh,
            "tier": self.tier,
            "thread_id": self.thread_id,
            "consensus": self.consensus,
        }""")


# =========================================================== 3. parsers: tier + stocktwits
rep("src/intelligence/ingestion.py", """def parse_rss_atom(xml_text: str, source_name: str, domain: str) -> List[RawEvent]:""",
"""def parse_rss_atom(xml_text: str, source_name: str, domain: str, tier: int = 2) -> List[RawEvent]:""")

rep("src/intelligence/ingestion.py", """        if title:
            events.append(RawEvent(
                source=source_name,
                domain=domain,
                title=title,
                url=link or source_name,
                timestamp=now,
                raw_content=desc[:450]
            ))""",
"""        if title:
            events.append(RawEvent(
                source=source_name,
                domain=domain,
                title=title,
                url=link or source_name,
                timestamp=now,
                raw_content=desc[:450],
                tier=tier,
            ))""")

rep("src/intelligence/ingestion.py", """        if title:
            events.append(RawEvent(
                source=source_name,
                domain=domain,
                title=title,
                url=link or source_name,
                timestamp=now,
                raw_content=desc[:450],
            ))""",
"""        if title:
            events.append(RawEvent(
                source=source_name,
                domain=domain,
                title=title,
                url=link or source_name,
                timestamp=now,
                raw_content=desc[:450],
                tier=tier,
            ))""")

rep("src/intelligence/ingestion.py", """        if title:
            full_title = f"[Polymarket 24h Vol ${vol:,.0f}] {title}{odds_str}"
            events.append(RawEvent(
                source="Polymarket",
                domain="prediction",
                title=full_title,
                url=url,
                timestamp=now,
                raw_content=odds_str
            ))""",
"""        if title:
            full_title = f"[Polymarket 24h Vol ${vol:,.0f}] {title}{odds_str}"
            events.append(RawEvent(
                source="Polymarket",
                domain="prediction",
                title=full_title,
                url=url,
                timestamp=now,
                raw_content=odds_str,
                tier=1,
            ))""")


def _stocktwits_parser_code():
    return '''def _parse_iso_ts(value: Any) -> float:
    """Parses an ISO8601 timestamp to epoch seconds; now on failure."""
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except (ValueError, TypeError):
            pass
    return time.time()


def parse_stocktwits_stream(data: Any, symbol: str) -> List[RawEvent]:
    """
    Parses one StockTwits v2 symbol stream into a single forum RawEvent.

    The stream is newest-first (30 messages/page); the top 20 messages are
    concatenated into raw_content (<= 1200 chars) and the event is keyed on
    the latest message, so dedup only produces a new event when the stream
    actually moves. No login: the public v2 endpoint returns HTTP 200 with
    just a User-Agent (verified from the PC 2026-11-13). Note "ETH" on
    StockTwits is the Grayscale ETF; the crypto streams are ETH.X / BTC.X.
    """
    events: List[RawEvent] = []
    if not isinstance(data, dict):
        return events
    messages = data.get("messages", [])
    if not isinstance(messages, list) or not messages:
        return events

    top = [m for m in messages[:20] if isinstance(m, dict) and (m.get("body") or "").strip()]
    if not top:
        return events

    latest = top[0]
    latest_id = latest.get("id")
    latest_user = ""
    user = latest.get("user")
    if isinstance(user, dict):
        latest_user = str(user.get("username", ""))

    # Title carries the latest message: dedup (title+URL) then only fires
    # when the stream moves, instead of once per fetch.
    first_line = re.sub(r"\\s+", " ", (latest.get("body") or "").strip().split("\\n")[0])
    title = f"[StockTwits {symbol}] {first_line[:80]}"
    url = (
        f"https://stocktwits.com/{latest_user}/message/{latest_id}"
        if latest_user and latest_id is not None
        else f"https://api.stocktwits.com/api/2/streams/symbol/{symbol}.json"
    )

    lines = []
    for m in top:
        body = re.sub(r"\\s+", " ", (m.get("body") or "").strip())
        if not body:
            continue
        uname = ""
        mu = m.get("user")
        if isinstance(mu, dict):
            uname = str(mu.get("username", ""))
        sent = ""
        ent = m.get("entities")
        if isinstance(ent, dict):
            s = ent.get("sentiment")
            if isinstance(s, dict) and s.get("basic"):
                sent = f" [{s.get('basic')}]"
        lines.append(f"{uname}{sent}: {body[:200]}")
    raw_content = "\\n".join(lines)[:1200]

    events.append(RawEvent(
        source=f"StockTwits {symbol}",
        domain="forum",
        title=title,
        url=url,
        timestamp=_parse_iso_ts(latest.get("created_at")),
        raw_content=raw_content,
        tier=2,
        thread_id=f"stocktwits:{symbol}",
    ))
    return events


'''


# Insert the StockTwits parser before the InterruptDebouncer class.
rep("src/intelligence/ingestion.py", """class InterruptDebouncer:""",
_stocktwits_parser_code() + """class InterruptDebouncer:""")


# =========================================================== 4. registry-driven fetcher + fetch_live_feeds
rep("src/intelligence/ingestion.py", """    def fetch_live_feeds(self, max_per_source: int = 5, timeout_sec: float = 3.0) -> List[RawEvent]:""",
"""    def fetch_from_registry(self, max_per_source: int = 5, timeout_sec: float = 3.0) -> List[RawEvent]:
        \"\"\"
        Registry-driven fetch (item 12B): every entry in FEED_REGISTRY is a
        no-login source (user rule 2026-11-13), dispatched by its `type`:
        rss/atom -> parse_rss_atom, rest_json -> parse_polymarket_events.
        `stocktwits` entries are owned by ForumCollector (forum batch, own
        cadence) and are explicitly skipped here, so the same stream is
        never scored twice per digest. Unknown types are skipped, never
        fatal: one dead source must not take down the whole digest.
        \"\"\"
        import requests

        fresh_events: List[RawEvent] = []
        headers = {"User-Agent": USER_AGENT}

        for entry in FEED_REGISTRY:
            etype = str(entry.get("type", ""))
            if etype == "stocktwits":
                # ForumCollector owns StockTwits (separate forum batch).
                logger.debug("Registry entry %s is forum-owned, skipped by news fetch", entry.get("id"))
                continue
            try:
                resp = requests.get(entry["url"], headers=headers, timeout=timeout_sec)
                if resp.status_code != 200:
                    logger.debug("Registry feed %s returned HTTP %d", entry.get("id"), resp.status_code)
                    continue
                if etype in ("rss", "atom"):
                    parsed = parse_rss_atom(resp.text, entry["name"], entry["domain"], tier=int(entry.get("tier", 2)))
                elif etype == "rest_json":
                    parsed = parse_polymarket_events(resp.json())
                else:
                    logger.debug("Unknown registry feed type %r for %s, skipped", etype, entry.get("id"))
                    continue
                for e in parsed[:max_per_source]:
                    if self.dedup.is_new(e.title, e.url):
                        fresh_events.append(e)
                    elif hasattr(self.client, "record_dedup_hit"):
                        self.client.record_dedup_hit()
            except Exception as ex:
                logger.debug("Registry feed fetch error for %s: %s", entry.get("id"), ex)

        return fresh_events

    def fetch_live_feeds(self, max_per_source: int = 5, timeout_sec: float = 3.0) -> List[RawEvent]:""")

rep("src/intelligence/ingestion.py", """        feed_targets = [
            ("CoinDesk", "crypto", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
            ("CoinTelegraph", "crypto", "https://cointelegraph.com/rss"),
            ("Decrypt", "crypto", "https://decrypt.co/feed"),
            ("ForexLive", "macro", "https://www.forexlive.com/feed/news"),
        ]

        fresh_events: List[RawEvent] = []
        headers = {"User-Agent": USER_AGENT}

        for source_name, domain, url in feed_targets:
            try:
                import requests
                resp = requests.get(url, headers=headers, timeout=timeout_sec)
                if resp.status_code == 200 and resp.text:
                    parsed = parse_rss_atom(resp.text, source_name, domain)
                    for e in parsed[:max_per_source]:
                        if self.dedup.is_new(e.title, e.url):
                            fresh_events.append(e)
                        else:
                            # Dedup hit: count it, do not claim a token figure
                            # (item 12 / A4-3: the old 420 was a fixed estimate).
                            if hasattr(self.client, "record_dedup_hit"):
                                self.client.record_dedup_hit()
            except Exception as ex:
                logger.debug("Live feed fetch error for %s: %s", source_name, ex)

        return fresh_events""",
"""        # Registry-driven fetch (item 12B): the 4 previously hardcoded RSS
        # sources are registry entries now (Decrypt included); the single
        # source of truth is FEED_REGISTRY, which holds no-login sources
        # only (user rule 2026-11-13).
        return self.fetch_from_registry(max_per_source=max_per_source, timeout_sec=timeout_sec)""")


# =========================================================== 5. process_batch: tier/thread/consensus
rep("src/intelligence/ingestion.py", """            '      "sentiment_score": 0.35,\\n'
            '      "headline_zh": "繁體中文新聞標題（精準翻譯並提煉核心事件，約15至28字）",\\n'""",
"""            '      "sentiment_score": 0.35,\\n'
            '      "consensus": {"bullish": 0.6, "bearish": 0.25, "neutral": 0.15},\\n'
            '      "headline_zh": "繁體中文新聞標題（精準翻譯並提煉核心事件，約15至28字）",\\n'""")

rep("src/intelligence/ingestion.py", """            "CRITICAL REQUIREMENT: Both 'headline_zh' and 'summary' MUST be written strictly in Traditional Chinese (繁體中文). Never output English in headline_zh or summary.\\n"
            "Urgency rubric: 1-4=Routine noise, 5-7=Notable market mover, 8-10=Black Swan, Fed rate shock, election result, major war, or SEC enforcement."
        )""",
"""            "CRITICAL REQUIREMENT: Both 'headline_zh' and 'summary' MUST be written strictly in Traditional Chinese (繁體中文). Never output English in headline_zh or summary.\\n"
            "For forum threads only, also include 'consensus' with the share of replies that are bullish / bearish / neutral (three numbers summing to 1.0); omit it for news items.\\n"
            "Urgency rubric: 1-4=Routine noise, 5-7=Notable market mover, 8-10=Black Swan, Fed rate shock, election result, major war, or SEC enforcement."
        )""")

rep("src/intelligence/ingestion.py", """                    urgency = max(1, min(10, int(item.get("urgency_score", 5))))
                    sentiment = max(-1.0, min(1.0, float(item.get("sentiment_score", 0.0))))
                    tickers = [str(t).upper() for t in item.get("entities_tickers", [])]""",
"""                    urgency = max(1, min(10, int(item.get("urgency_score", 5))))
                    sentiment = max(-1.0, min(1.0, float(item.get("sentiment_score", 0.0))))
                    tickers = [str(t).upper() for t in item.get("entities_tickers", [])]
                    consensus = self._parse_consensus(item.get("consensus"))""")

rep("src/intelligence/ingestion.py", """                    se = StructuredEvent(
                        timestamp=iso_now,
                        source=raw.source,
                        domain=raw.domain,
                        entities_tickers=tickers,
                        urgency_score=urgency,
                        sentiment_score=sentiment,
                        summary=summary,
                        raw_title=raw.title,
                        headline_zh=headline_zh,
                    )""",
"""                    se = StructuredEvent(
                        timestamp=iso_now,
                        source=raw.source,
                        domain=raw.domain,
                        entities_tickers=tickers,
                        urgency_score=urgency,
                        sentiment_score=sentiment,
                        summary=summary,
                        raw_title=raw.title,
                        headline_zh=headline_zh,
                        tier=raw.tier,
                        thread_id=raw.thread_id,
                        consensus=consensus,
                    )""")

rep("src/intelligence/ingestion.py", """                se = StructuredEvent(
                    timestamp=iso_now,
                    source=raw.source,
                    domain=raw.domain,
                    entities_tickers=tickers,
                    urgency_score=urgency,
                    sentiment_score=round(sentiment, 2),
                    summary=summary_zh,
                    raw_title=raw.title,
                    headline_zh=headline_zh,
                )""",
"""                # Forum consensus without the LLM: a deterministic split of
                # the single event score (bullish/bearish/neutral shares),
                # not a measured reply distribution (item 12B).
                s2 = round(sentiment, 2)
                consensus = {
                    "bullish": round(max(0.0, s2), 2),
                    "bearish": round(max(0.0, -s2), 2),
                    "neutral": round(1.0 - abs(s2), 2),
                } if raw.thread_id else None

                se = StructuredEvent(
                    timestamp=iso_now,
                    source=raw.source,
                    domain=raw.domain,
                    entities_tickers=tickers,
                    urgency_score=urgency,
                    sentiment_score=s2,
                    summary=summary_zh,
                    raw_title=raw.title,
                    headline_zh=headline_zh,
                    tier=raw.tier,
                    thread_id=raw.thread_id,
                    consensus=consensus,
                )""")

rep("src/intelligence/ingestion.py", """    @staticmethod
    def _contains_cjk(text: str) -> bool:
        return bool(text and re.search(r"[\\u4e00-\\u9fff]", text))""",
"""    @staticmethod
    def _contains_cjk(text: str) -> bool:
        return bool(text and re.search(r"[\\u4e00-\\u9fff]", text))

    @staticmethod
    def _parse_consensus(value: Any) -> Optional[Dict[str, float]]:
        \"\"\"Validates an LLM-returned reply-sentiment distribution.

        Returns normalized bullish/bearish/neutral shares summing to 1.0,
        or None when the value is missing, malformed, or all zeros.
        \"\"\"
        if not isinstance(value, dict):
            return None
        try:
            b = max(0.0, float(value.get("bullish", 0.0)))
            be = max(0.0, float(value.get("bearish", 0.0)))
            n = max(0.0, float(value.get("neutral", 0.0)))
        except (TypeError, ValueError):
            return None
        total = b + be + n
        if total <= 0.0:
            return None
        return {
            "bullish": round(b / total, 2),
            "bearish": round(be / total, 2),
            "neutral": round(n / total, 2),
        }""")


# =========================================================== 6. macro_commander: forum wiring + curated fields
rep("src/intelligence/macro_commander.py", """from src.intelligence.omniroute_client import OmniRouteClient
from src.intelligence.ingestion import IntelligenceHarvester, StructuredEvent""",
"""from src.intelligence.omniroute_client import OmniRouteClient
from src.intelligence.forum_collector import ForumCollector
from src.intelligence.ingestion import IntelligenceHarvester, StructuredEvent""")

rep("src/intelligence/macro_commander.py", """    def __init__(self, client: OmniRouteClient, harvester: Optional[IntelligenceHarvester] = None) -> None:
        self.client = client
        self.harvester = harvester or IntelligenceHarvester(client=client)
        self.current_state = MacroRegimeState()""",
"""    def __init__(self, client: OmniRouteClient, harvester: Optional[IntelligenceHarvester] = None) -> None:
        self.client = client
        self.harvester = harvester or IntelligenceHarvester(client=client)
        self.forum_collector = ForumCollector(client=client)
        self.current_state = MacroRegimeState()""")

rep("src/intelligence/macro_commander.py", """            await self.client.check_health()
            try:
                raw_events = await asyncio.to_thread(self.harvester.fetch_live_feeds, 5, 3.5)
                if raw_events:
                    structured = await self.harvester.process_batch(raw_events)
                    if structured:
                        return await self.synthesize_regime(structured)
            except Exception as ex:""",
"""            await self.client.check_health()
            try:
                raw_events = await asyncio.to_thread(self.harvester.fetch_live_feeds, 5, 3.5)
                structured_all: List[StructuredEvent] = []
                if raw_events:
                    structured_all.extend(await self.harvester.process_batch(raw_events))
                # Forum batch (item 12B): StockTwits streams are collected on
                # their own cadence and scored in a separate batch, so forum
                # chatter never crowds breaking news out of the 6-event cap.
                try:
                    forum_events = await self.forum_collector.collect_async()
                    if forum_events:
                        structured_all.extend(await self.harvester.process_batch(forum_events))
                except Exception as ex:
                    logger.warning("Forum collection failed, continuing with news only: %s", ex)
                if structured_all:
                    return await self.synthesize_regime(structured_all)
            except Exception as ex:""")

rep("src/intelligence/macro_commander.py", """                        "headline": zh_head,
                        "summary": zh_sum,
                        "raw_title": e.raw_title,
                        "strategy_actions": [],
                    })""",
"""                        "headline": zh_head,
                        "summary": zh_sum,
                        "raw_title": e.raw_title,
                        "tier": e.tier,
                        "thread_id": e.thread_id,
                        "consensus": e.consensus,
                        "strategy_actions": [],
                    })""")


# =========================================================== 7. registry test: tree_news removed
rep("tests/test_phase3_ingestion.py", """    # Core Tape & Macro
    assert any("tree_news" in i for i in ids)
    assert any("polymarket" in i for i in ids)""",
"""    # Core Tape & Macro
    # Tree News was removed 2026-11-13 (item 12B): it needs an API key and
    # the user rule is no-login sources only.
    assert any("polymarket" in i for i in ids)""")


# =========================================================== new files
NEW_FILES["src/intelligence/forum_collector.py"] = '''"""src/intelligence/forum_collector.py - Forum thread collector (item 12B).

Phase 1 (user rule 2026-11-13: no-login sources only): StockTwits public
v2 streams only. Verified from the PC 2026-11-13: the streams return
HTTP 200 with no auth, just a User-Agent. No Reddit (per-user OAuth
conflicts with "anyone can use it"), no X (paid), no Discord/Telegram
(user channels) -- no code for them exists here.

Note "ETH" on StockTwits is the Grayscale ETF (NYSEArca); the crypto
streams are ETH.X and BTC.X (verified from the PC).

Extension point for phase 2 (e.g. Reddit): add a source method that
returns RawEvents with domain="forum" and call it from collect_async()
next to _collect_stocktwits(); FEED_REGISTRY stays the single list of
sources, and the harvester scores forum events in their own batch.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from typing import Any, List, Optional

from src.intelligence.ingestion import (
    FEED_REGISTRY,
    RawEvent,
    USER_AGENT,
    parse_stocktwits_stream,
)

logger = logging.getLogger(__name__)

# Phase-1 forum cadence: streams are re-fetched at most every 15 minutes,
# and at most 12 stream summaries per rolling hour (design B4 caps).
FORUM_COLLECT_INTERVAL_SEC = 900.0
FORUM_MAX_SUMMARIES_PER_HOUR = 12
_DEFAULT_SYMBOLS = ["ETH.X", "BTC.X"]


def _symbols_from_registry() -> List[str]:
    """Reads the StockTwits symbols from the registry's stocktwits entries."""
    syms: List[str] = []
    for entry in FEED_REGISTRY:
        if entry.get("type") != "stocktwits":
            continue
        url = str(entry.get("url", ""))
        m = re.search(r"/symbol/([^/.]+)\\.json", url)
        if m and m.group(1) not in syms:
            syms.append(m.group(1))
    return syms or list(_DEFAULT_SYMBOLS)


class ForumCollector:
    """Collects forum threads into RawEvents for the separate forum batch.

    Phase 1: StockTwits symbol streams only. There is no LLM Discovery
    call in phase 1: the streams are fixed (ETH.X / BTC.X), so there is
    nothing to discover; thread picking (Discovery) returns with a
    multi-thread source in phase 2.
    """

    def __init__(self, client: Any, symbols: Optional[List[str]] = None) -> None:
        self.client = client
        self.symbols = list(symbols) if symbols else _symbols_from_registry()
        self.collect_interval_sec = FORUM_COLLECT_INTERVAL_SEC
        self.max_summaries_per_hour = FORUM_MAX_SUMMARIES_PER_HOUR
        self._last_collect_ts: float = 0.0
        self._summary_window_start: float = 0.0
        self._summary_count: int = 0

    def fetch_stocktwits_stream(self, symbol: str, timeout_sec: float = 5.0) -> Optional[RawEvent]:
        """Fetches one public StockTwits stream (no login) -> one RawEvent."""
        import requests

        url = f"https://api.stocktwits.com/api/2/streams/symbol/{symbol}.json"
        try:
            resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout_sec)
            if resp.status_code != 200:
                logger.debug("StockTwits stream %s returned HTTP %d", symbol, resp.status_code)
                return None
            parsed = parse_stocktwits_stream(resp.json(), symbol)
            return parsed[0] if parsed else None
        except Exception as ex:
            logger.debug("StockTwits stream fetch failed for %s: %s", symbol, ex)
            return None

    def _hourly_cap_reached(self, now: float) -> bool:
        if now - self._summary_window_start >= 3600.0:
            self._summary_window_start = now
            self._summary_count = 0
        return self._summary_count >= self.max_summaries_per_hour

    def _collect_stocktwits(self) -> List[RawEvent]:
        events: List[RawEvent] = []
        now = time.time()
        for symbol in self.symbols:
            if self._hourly_cap_reached(now):
                break
            ev = self.fetch_stocktwits_stream(symbol)
            if ev is not None:
                events.append(ev)
                self._summary_count += 1
        return events

    async def collect_async(self) -> List[RawEvent]:
        """Returns fresh forum RawEvents (at most once per collect interval).

        ARENA_FAST_TEST short-circuits to [] so the test suite never touches
        the network. Phase 2 sources plug in here next to
        _collect_stocktwits().
        """
        if os.environ.get("ARENA_FAST_TEST") == "1":
            return []
        now = time.time()
        if now - self._last_collect_ts < self.collect_interval_sec:
            return []
        if self._hourly_cap_reached(now):
            logger.debug(
                "Forum hourly summary cap reached (%d), skipping", self.max_summaries_per_hour
            )
            return []
        self._last_collect_ts = now
        events: List[RawEvent] = []
        events.extend(await asyncio.to_thread(self._collect_stocktwits))
        return events
'''

NEW_FILES["tests/test_forum_collector.py"] = '''"""Item 12B tests: StockTwits-only forum collection (no-login sources only).

No Reddit code or tests exist in phase 1 (user rule 2026-11-13: Reddit
needs per-user OAuth, which conflicts with "anyone can use it").
Covers: the StockTwits parser, the registry-driven fetcher (no-login
sources only, forum streams owned by the collector), collector cadence
and hourly cap, and the offline forum flow (keyword fallback, no LLM)."""
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

from src.intelligence.forum_collector import ForumCollector
from src.intelligence.ingestion import (
    FEED_REGISTRY,
    IntelligenceHarvester,
    RawEvent,
    StructuredEvent,
    parse_stocktwits_stream,
)
from src.intelligence.macro_commander import MacroCommander
from src.intelligence.omniroute_client import OmniRouteClient


def _stream_json(symbol, latest_id, bodies):
    msgs = []
    for i, body in enumerate(bodies):
        msgs.append({
            "id": latest_id - i,
            "body": body,
            "created_at": "2026-11-13T07:00:00Z",
            "user": {"username": f"user{i}"},
            "entities": {"sentiment": {"basic": "Bullish"}} if i == 0 else {},
        })
    return {"messages": msgs, "symbol": {"symbol": symbol}}


def test_parse_stocktwits_stream_builds_one_forum_event():
    data = _stream_json("ETH.X", 100, [
        "ETH.X breakout above resistance, momentum building",
        "Second message with more detail here",
        "Third message, short",
    ])
    events = parse_stocktwits_stream(data, "ETH.X")
    assert len(events) == 1
    ev = events[0]
    assert ev.domain == "forum"
    assert ev.tier == 2
    assert ev.thread_id == "stocktwits:ETH.X"
    assert "StockTwits ETH.X" in ev.source
    assert "breakout above resistance" in ev.title
    assert "user0" in ev.raw_content
    assert "Second message" in ev.raw_content
    assert len(ev.raw_content) <= 1200
    assert ev.url == "https://stocktwits.com/user0/message/100"
    assert ev.timestamp > 0


def test_parse_stocktwits_stream_empty_and_malformed():
    assert parse_stocktwits_stream({"messages": []}, "ETH.X") == []
    assert parse_stocktwits_stream({"messages": [{"body": "  "}]}, "ETH.X") == []
    assert parse_stocktwits_stream(None, "ETH.X") == []
    assert parse_stocktwits_stream("not a dict", "ETH.X") == []


def test_parse_stocktwits_stream_truncates_long_content():
    bodies = ["x" * 500] * 20
    events = parse_stocktwits_stream(_stream_json("BTC.X", 7, bodies), "BTC.X")
    assert len(events) == 1
    assert len(events[0].raw_content) <= 1200


def test_registry_contains_only_no_login_sources():
    """User rule 2026-11-13: the registry holds no-login sources only."""
    types = {e.get("type") for e in FEED_REGISTRY}
    assert types <= {"rss", "atom", "rest_json", "stocktwits"}
    assert "websocket" not in types  # Tree News needs a key
    assert "reddit_json" not in types  # Reddit needs per-user OAuth
    ids = {e["id"] for e in FEED_REGISTRY}
    assert "tree_news_ws" not in ids
    assert "reddit_crypto" not in ids
    assert "reddit_wsb" not in ids
    assert "decrypt_wire" in ids
    assert "stocktwits_ethx" in ids
    assert "stocktwits_btcx" in ids
    # Crypto streams are ETH.X / BTC.X: plain "ETH" on StockTwits is the
    # Grayscale ETF, not crypto (verified from the PC).
    urls = {e["url"] for e in FEED_REGISTRY if e.get("type") == "stocktwits"}
    assert urls == {
        "https://api.stocktwits.com/api/2/streams/symbol/ETH.X.json",
        "https://api.stocktwits.com/api/2/streams/symbol/BTC.X.json",
    }


def _registry_mock_get(url, headers=None, timeout=None):
    """Per-URL mock: unique RSS titles (so dedup keeps one per source),
    Polymarket JSON, and a hard failure if a forum URL is ever fetched
    by the news fetcher (the collector owns those)."""
    mock_resp = MagicMock()
    if "stocktwits" in url:
        raise AssertionError(f"news fetcher must not fetch forum URL: {url}")
    if "polymarket" in url:
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {"title": "Poly event", "volume24hr": 100, "slug": "x", "markets": []}
        ]
        mock_resp.text = ""
        return mock_resp
    mock_resp.status_code = 200
    mock_resp.text = (
        "<rss><channel><item>"
        f"<title>Item from {url}</title><link>{url}/item1</link>"
        "<description>desc</description></item></channel></rss>"
    )
    mock_resp.json.side_effect = ValueError("not json")
    return mock_resp


def test_fetch_from_registry_dispatches_by_type_and_skips_forum():
    client = OmniRouteClient()
    harvester = IntelligenceHarvester(client=client)
    with patch("requests.get", side_effect=_registry_mock_get):
        events = harvester.fetch_from_registry()
    fetchable = [e for e in FEED_REGISTRY if e.get("type") in ("rss", "atom", "rest_json")]
    assert len(events) == len(fetchable) == 16
    assert all(e.domain != "forum" for e in events)
    assert all(e.source != "StockTwits" for e in events)
    # Tiers ride along from the registry.
    by_source = {e.source: e for e in events}
    assert by_source["ForexLive Breaking Wire"].tier == 1
    assert by_source["CoinDesk Live"].tier == 2
    assert by_source["FRED Economic Data Releases"].tier == 3
    assert by_source["Polymarket"].tier == 1


def test_fetch_live_feeds_still_returns_test_fixtures():
    """ARENA_FAST_TEST=1 (conftest) still returns the 2 marked fixtures."""
    client = OmniRouteClient()
    harvester = IntelligenceHarvester(client=client)
    events = harvester.fetch_live_feeds()
    assert len(events) == 2
    assert all("[TEST]" in e.title for e in events)


def test_forum_collector_stocktwits_flow_and_cadence(monkeypatch):
    """Collector fetches both streams, then stays quiet until the 15-minute
    cadence elapses; a moved stream then yields new events."""
    monkeypatch.setenv("ARENA_FAST_TEST", "0")
    calls = {"n": 0}

    def mock_get(url, headers=None, timeout=None):
        calls["n"] += 1
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        if "ETH.X" in url:
            mock_resp.json.return_value = _stream_json("ETH.X", 100 + calls["n"], ["ETH.X moon", "more"])
        else:
            mock_resp.json.return_value = _stream_json("BTC.X", 200, ["BTC.X steady", "more"])
        return mock_resp

    collector = ForumCollector(client=MagicMock())
    assert collector.symbols == ["ETH.X", "BTC.X"]
    with patch("requests.get", side_effect=mock_get):
        first = asyncio.run(collector.collect_async())
        assert len(first) == 2
        assert {e.thread_id for e in first} == {"stocktwits:ETH.X", "stocktwits:BTC.X"}
        # Immediate second call: cadence gate, no HTTP at all.
        before = calls["n"]
        assert asyncio.run(collector.collect_async()) == []
        assert calls["n"] == before
        # 16 minutes later: fetches again.
        collector._last_collect_ts = time.time() - 961.0
        second = asyncio.run(collector.collect_async())
        assert len(second) == 2


def test_forum_collector_hourly_cap(monkeypatch):
    monkeypatch.setenv("ARENA_FAST_TEST", "0")
    collector = ForumCollector(client=MagicMock())
    collector._summary_count = 12
    collector._summary_window_start = time.time()
    with patch("requests.get") as mock_get:
        assert asyncio.run(collector.collect_async()) == []
        mock_get.assert_not_called()


def test_forum_collector_fast_test_short_circuits():
    """Under ARENA_FAST_TEST the collector never touches the network."""
    collector = ForumCollector(client=MagicMock())
    with patch("requests.get") as mock_get:
        assert asyncio.run(collector.collect_async()) == []
        mock_get.assert_not_called()


def test_forum_batch_scored_without_llm_when_offline(monkeypatch):
    """Gateway down: forum events still flow through the keyword fallback
    (no LLM call), and the news path is unaffected."""
    monkeypatch.setenv("ARENA_FAST_TEST", "0")
    mock_client = MagicMock()
    mock_client.is_gateway_online = False
    mock_client._owns_session = False
    mock_client.check_health = AsyncMock(return_value=False)
    mock_client.chat_json = AsyncMock(return_value=None)

    def mock_get(url, headers=None, timeout=None):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        if "stocktwits" in url:
            sym = "ETH.X" if "ETH.X" in url else "BTC.X"
            mock_resp.json.return_value = _stream_json(sym, 500, [f"{sym} surge rally gains", "more"])
            return mock_resp
        mock_resp.text = (
            "<rss><channel><item>"
            f"<title>News {url}</title><link>{url}/n1</link>"
            "<description>desc</description></item></channel></rss>"
        )
        mock_resp.json.side_effect = ValueError("not json")
        return mock_resp

    commander = MacroCommander(mock_client)
    with patch("requests.get", side_effect=mock_get):
        state = asyncio.run(commander.refresh_digest_async())
    mock_client.chat_json.assert_not_called()
    sources = [e.source for e in commander.harvester.recent_structured_events]
    assert any(s.startswith("StockTwits") for s in sources)
    assert state is commander.current_state


def test_process_batch_carries_tier_thread_and_consensus():
    """LLM consensus is parsed and normalized; fields ride through."""
    async def _run():
        mock_client = MagicMock()
        mock_client.is_gateway_online = True
        mock_client.model_ingest = "auto"
        mock_client.chat_json = AsyncMock(return_value={
            "events": [{
                "index": 1,
                "entities_tickers": ["ETH"],
                "urgency_score": 6,
                "sentiment_score": 0.4,
                "headline_zh": "測試標題",
                "summary": "測試摘要內容",
                "consensus": {"bullish": 6, "bearish": 2, "neutral": 2},
            }]
        })
        harvester = IntelligenceHarvester(client=mock_client)
        raw = [RawEvent(
            source="StockTwits ETH.X", domain="forum", title="t", url="https://x/1",
            timestamp=2000.0, tier=2, thread_id="stocktwits:ETH.X",
        )]
        out = await harvester.process_batch(raw)
        assert len(out) == 1
        assert out[0].tier == 2
        assert out[0].thread_id == "stocktwits:ETH.X"
        assert out[0].consensus == {"bullish": 0.6, "bearish": 0.2, "neutral": 0.2}
    asyncio.run(_run())


def test_process_batch_fallback_consensus_from_score():
    """Keyword fallback derives a deterministic consensus split for forum
    threads only; news events get none."""
    async def _run():
        mock_client = MagicMock()
        mock_client.is_gateway_online = False
        mock_client.chat_json = AsyncMock(return_value=None)
        harvester = IntelligenceHarvester(client=mock_client)
        forum = RawEvent(
            source="StockTwits ETH.X", domain="forum",
            title="ETH.X surge rally gains", url="https://x/1",
            timestamp=2000.0, tier=2, thread_id="stocktwits:ETH.X",
        )
        news = RawEvent(
            source="CoinDesk", domain="crypto",
            title="Ethereum surge rally gains", url="https://x/2",
            timestamp=2000.0, tier=2,
        )
        out = await harvester.process_batch([forum, news])
        assert len(out) == 2
        f, n = out
        assert f.consensus == {"bullish": 0.7, "bearish": 0.0, "neutral": 0.3}
        assert n.consensus is None
    asyncio.run(_run())


def test_structured_event_new_fields_default():
    se = StructuredEvent(
        timestamp="2026-11-13T00:00:00Z", source="Test", domain="crypto",
        entities_tickers=["ETH"], urgency_score=5, sentiment_score=0.0,
        summary="s",
    )
    assert se.tier == 2
    assert se.thread_id is None
    assert se.consensus is None
    d = se.to_dict()
    assert d["tier"] == 2
    assert d["thread_id"] is None
    assert d["consensus"] is None
'''


# =========================================================== apply (verify ALL, then write)
def main():
    # Phase 1: verify every replacement matches exactly once, and no new
    # file already exists. Nothing is written until all checks pass, so a
    # bad anchor can never leave a half-applied patch behind.
    contents: dict = {}
    for path, old, new in REPLACEMENTS:
        if path not in contents:
            with open(path, "r", encoding="utf-8", newline="") as f:
                contents[path] = f.read()
        n = contents[path].count(old)
        if n != 1:
            print(f"FAIL {path}: expected 1 occurrence, found {n} for: {old[:80]!r}")
            sys.exit(1)
    for path in NEW_FILES:
        if os.path.exists(path):
            print(f"FAIL {path}: already exists, refusing to overwrite")
            sys.exit(1)
    # Phase 2: apply.
    for path, old, new in REPLACEMENTS:
        contents[path] = contents[path].replace(old, new)
        print(f"OK {path}")
    for path, content in contents.items():
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(content)
    for path, content in NEW_FILES.items():
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        print(f"NEW {path}")
    print(f"Applied {len(REPLACEMENTS)} replacements + {len(NEW_FILES)} new files.")


if __name__ == "__main__":
    main()
