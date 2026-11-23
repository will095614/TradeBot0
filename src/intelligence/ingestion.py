from __future__ import annotations

import asyncio
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import functools
import hashlib
import html
import inspect
import json
import logging
import math
import os
import re
import time
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Tuple, Union
import weakref
import xml.etree.ElementTree as ET
import aiohttp

from src.intelligence.omniroute_client import OmniRouteClient

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 TradeBot0-Intelligence/1.0"
SEC_EDGAR_USER_AGENT = "TradeBot0/2.5 (contact@tradebot0.local)"
DEFAULT_MAX_ARTICLE_AGE_HOURS: float = 48.0

# [R3] Comprehensive Multi-Domain Feed Registry
FEED_REGISTRY: List[Dict[str, Any]] = [
    # User rule 2026-11-13: no-login sources ONLY. Tree News (needs an API
    # key), Reddit (per-user OAuth), X (paid), Discord/Telegram (user
    # channels) are NOT listed here and are never fetched.
    # Tier 1: 30-60s Breaking Wires, Prediction & Geopolitics
    {"id": "polymarket_gamma", "name": "Polymarket Gamma", "tier": 1, "domain": "prediction", "type": "rest_json", "url": "https://gamma-api.polymarket.com/events?limit=25&active=true"},
    {"id": "sec_edgar_8k", "name": "SEC EDGAR 8-K", "tier": 1, "domain": "corporate", "type": "atom", "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&CIK=&type=8-K&company=&dateb=&owner=include&start=0&count=40&output=atom"},
    {"id": "aljazeera_world", "name": "Al Jazeera World Wire", "tier": 1, "domain": "geopolitics", "type": "rss", "url": "https://www.aljazeera.com/xml/rss/all.xml"},
    {"id": "breaking_defense", "name": "Breaking Defense", "tier": 1, "domain": "geopolitics", "type": "rss", "url": "https://breakingdefense.com/feed/"},
    {"id": "war_zone", "name": "The War Zone", "tier": 1, "domain": "geopolitics", "type": "rss", "url": "https://www.twz.com/feed"},
    {"id": "gcaptain", "name": "gCaptain Maritime Security", "tier": 1, "domain": "geopolitics", "type": "rss", "url": "https://gcaptain.com/feed/"},
    {"id": "forexlive", "name": "ForexLive Breaking Wire", "tier": 1, "domain": "macro", "type": "rss", "url": "https://www.forexlive.com/feed/news"},
    {"id": "fxstreet_wire", "name": "FXStreet Macro Wire", "tier": 1, "domain": "macro", "type": "rss", "url": "https://www.fxstreet.com/rss/news"},
    {"id": "theblock_wire", "name": "The Block", "tier": 1, "domain": "crypto", "type": "rss", "url": "https://www.theblock.co/rss.xml"},
    # Tier 2: 3-5m Semiconductor/AI Supply Chain, Crypto & Community
    {"id": "tomshardware_ai", "name": "Tom's Hardware AI & Silicon", "tier": 2, "domain": "tech", "type": "rss", "url": "https://www.tomshardware.com/feeds/all"},
    {"id": "trendforce", "name": "TrendForce Global Tech", "tier": 2, "domain": "tech", "type": "rss", "url": "https://www.trendforce.com/news/feed/"},
    {"id": "digitimes", "name": "DigiTimes Semiconductor Wire", "tier": 2, "domain": "tech", "type": "rss", "url": "https://www.digitimes.com/rss/daily.xml"},
    {"id": "technews_tw", "name": "TechNews Global Supply Chain", "tier": 2, "domain": "tech", "type": "rss", "url": "https://technews.tw/feed/"},
    {"id": "coindesk_wire", "name": "CoinDesk Live", "tier": 2, "domain": "crypto", "type": "rss", "url": "https://www.coindesk.com/arc/outboundfeeds/rss/"},
    {"id": "cointelegraph_wire", "name": "CoinTelegraph", "tier": 2, "domain": "crypto", "type": "rss", "url": "https://cointelegraph.com/rss"},
    {"id": "decrypt_wire", "name": "Decrypt", "tier": 2, "domain": "crypto", "type": "rss", "url": "https://decrypt.co/feed"},
    {"id": "ecb_press", "name": "ECB Press Releases", "tier": 2, "domain": "macro", "type": "rss", "url": "https://www.ecb.europa.eu/rss/press.html"},
    {"id": "stocktwits_ethx", "name": "StockTwits ETH.X", "tier": 2, "domain": "forum", "type": "stocktwits", "url": "https://api.stocktwits.com/api/2/streams/symbol/ETH.X.json"},
    {"id": "stocktwits_btcx", "name": "StockTwits BTC.X", "tier": 2, "domain": "forum", "type": "stocktwits", "url": "https://api.stocktwits.com/api/2/streams/symbol/BTC.X.json"},
    # Tier 3: 15-30m Macro Liquidity & Central Banks
    {"id": "fred_releases", "name": "FRED Economic Data Releases", "tier": 3, "domain": "macro", "type": "rss", "url": "https://news.research.stlouisfed.org/feed/"},
    {"id": "fed_press_releases", "name": "Federal Reserve Press Releases", "tier": 3, "domain": "macro", "type": "rss", "url": "https://www.federalreserve.gov/feeds/press_all.xml"},
]


@dataclass
class RawEvent:
    source: str
    domain: str  # "crypto", "macro", "geopolitics", "tech", "prediction", "forum"
    title: str
    url: str
    timestamp: float
    raw_content: str = ""
    entities: List[str] = field(default_factory=list)
    tier: int = 2  # source tier from FEED_REGISTRY (0-3); 2 = general news/forum
    thread_id: Optional[str] = None  # forum thread key, e.g. "stocktwits:ETH.X"
    published_at: Optional[float] = None  # parsed publish epoch; None if feed omitted date


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
    headline_zh: str = ""
    tier: int = 2  # source tier (0-3); feeds the C1 weighted sentiment formula
    thread_id: Optional[str] = None  # forum thread key, e.g. "stocktwits:ETH.X"
    consensus: Optional[Dict[str, float]] = None  # forum reply split {bullish, bearish, neutral}
    # Audit 2.10: the truncated raw snippet (RSS 450 chars /
    # StockTwits 1200 chars) rides through structuring so the
    # article prompt is grounded in the event's own words.
    # Not in to_dict: it is prompt material only, never telemetry.
    raw_content: str = ""

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
        }


_POLY_VOL_PREFIX_RE = re.compile(r"^\[Polymarket 24h Vol \$[^\]]+\]\s*")
_POLY_ODDS_SUFFIX_RE = re.compile(r"\s*\|\s*Odds:.*$")


def _dedup_normalize_title(title: str) -> str:
    """Normalizes volatile Polymarket volume/odds strings so the same market
    doesn't bypass deduplication on every volume tick."""
    s = title.strip()
    if s.startswith("[Polymarket 24h Vol $"):
        s = _POLY_VOL_PREFIX_RE.sub("", s)
        s = _POLY_ODDS_SUFFIX_RE.sub("", s)
    return s.strip().lower()


class DeduplicationBuffer:
    """
    High-performance in-memory FIFO buffer with SHA-256 Title+URL hashing.
    Backed by an insertion-ordered dict for O(1) lookup, O(1) ghost-free
    forget(), and O(1) oldest eviction.
    """

    def __init__(self, capacity: int = 5000) -> None:
        self.capacity = max(1, int(capacity))
        self._seen: Dict[str, None] = {}

    @property
    def seen_hashes(self):
        return self._seen.keys()

    @staticmethod
    def _hash_key(title: str, url: str) -> str:
        norm = f"{_dedup_normalize_title(title)}|{url.strip().lower()}"
        return hashlib.sha256(norm.encode("utf-8")).hexdigest()

    def is_new(self, title: str, url: str) -> bool:
        if not title:
            return False
        h = self._hash_key(title, url)
        if h in self._seen:
            return False
        if len(self._seen) >= self.capacity:
            del self._seen[next(iter(self._seen))]
        self._seen[h] = None
        return True

    def forget(self, title: str, url: str) -> None:
        """Removes a previously marked item so unprocessed overflow can retry later."""
        if not title:
            return
        h = self._hash_key(title, url)
        self._seen.pop(h, None)

    def __len__(self) -> int:
        return len(self._seen)


_SCRIPT_STYLE_RE = re.compile(r"<(?:script|style)\b[^>]*>.*?</(?:script|style)>", re.IGNORECASE | re.DOTALL)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _clean_html_text(raw_html: str) -> str:
    if not raw_html:
        return ""
    text = html.unescape(str(raw_html))
    text = _SCRIPT_STYLE_RE.sub(" ", text)
    text = _HTML_TAG_RE.sub(" ", text)
    text = html.unescape(text)
    return _WS_RE.sub(" ", text).strip()


def _compile_word_group(words: Tuple[str, ...]) -> re.Pattern:
    return re.compile(r"\b(?:" + "|".join(re.escape(w) for w in words) + r")\b")


_BULL_WORDS = (
    "surge", "soar", "gain", "rally", "rise", "jump", "record", "ath",
    "inflow", "boost", "bull", "approve", "expand", "profit", "deal",
    "launch", "breakout", "adoption",
)
_BEAR_WORDS = (
    "crash", "plunge", "drop", "fall", "dump", "hack", "exploit", "lawsuit",
    "sue", "ban", "freeze", "investigate", "fraud", "bear", "fine",
    "outflow", "liquidation", "slump",
)
_BULL_RE = _compile_word_group(_BULL_WORDS)
_BEAR_RE = _compile_word_group(_BEAR_WORDS)
_URG9_RE = _compile_word_group(("emergency", "black swan", "halt", "freeze", "war", "ban", "indict", "indicted", "billion"))
_URG7_RE = _compile_word_group(("lawsuit", "sues", "sued", "sec", "fed", "rate", "subpoena", "hack", "etf", "tariff", "tariffs", "sanction", "sanctions"))
_URG6_RE = _compile_word_group(("deal", "tax", "report", "policy", "million", "launch", "upgrade"))
_TICKER_RES: Tuple[Tuple[re.Pattern, str], ...] = (
    (_compile_word_group(("eth", "ethereum", "ether")), "ETH"),
    (_compile_word_group(("btc", "bitcoin")), "BTC"),
    (_compile_word_group(("sol", "solana")), "SOL"),
    (_compile_word_group(("xrp", "ripple")), "XRP"),
    (_compile_word_group(("fed", "fomc", "rate", "powell")), "FED"),
    (_compile_word_group(("sec", "cftc")), "SEC"),
    (_compile_word_group(("ai", "anthropic", "openai", "nvidia")), "AI"),
)
_ENTITY_RES: Tuple[Tuple[re.Pattern, str], ...] = (
    (_compile_word_group(("ethereum", "ether", "eth", "vitalik")), "以太坊 (ETH)"),
    (_compile_word_group(("bitcoin", "btc")), "比特幣 (BTC)"),
    (_compile_word_group(("solana", "sol")), "Solana (SOL)"),
    (_compile_word_group(("xrp", "ripple")), "瑞波幣 (XRP)"),
    (_compile_word_group(("dogecoin", "doge")), "狗狗幣 (DOGE)"),
    (_compile_word_group(("stablecoin", "usdt", "usdc", "tether", "circle")), "穩定幣市場"),
    (_compile_word_group(("etf", "blackrock", "fidelity", "grayscale")), "機構現貨 ETF"),
    (_compile_word_group(("fed", "federal reserve", "fomc", "powell", "interest rate", "rate cut", "inflation", "cpi")), "聯準會與宏觀利率"),
    (_compile_word_group(("sec", "cftc", "gensler", "regulation", "regulatory", "lawsuit", "sues", "court")), "美國金融監管機構"),
    (_compile_word_group(("trump", "white house", "treasury", "tariff", "tariffs", "congress", "senate")), "美國政府與總經政策"),
    (_compile_word_group(("binance", "coinbase", "kraken", "bybit", "robinhood", "exchange")), "主流加密交易所"),
    (_compile_word_group(("defi", "layer 2", "l2", "rollup", "staking", "restaking", "airdrop")), "鏈上 DeFi 與二層擴容協議"),
    (_compile_word_group(("ai", "artificial intelligence", "openai", "anthropic", "nvidia", "semiconductor", "chip")), "AI 算力與科技產業"),
    (_compile_word_group(("hack", "hacked", "exploit", "phishing", "stolen", "breach", "security")), "區塊鏈資安與防護"),
    (_compile_word_group(("whale", "institutional", "microstrategy", "strategy", "treasury reserve")), "機構與巨鯨部位"),
)
_THEME_RES: Tuple[Tuple[re.Pattern, str, str], ...] = (
    (
        _compile_word_group(("hack", "hacked", "exploit", "stolen", "breach", "phishing")),
        "爆出資安漏洞與異常資金流動警報",
        "鏈上監測顯示相關協議或平台出現安全事件，市場短線避險情緒升溫，建議留意資金外溢與波動風險",
    ),
    (
        _compile_word_group(("lawsuit", "sues", "sued", "indict", "indicted", "probe", "subpoena", "ban", "banned", "crackdown", "fine", "fined")),
        "面臨監管審查與法律合規挑戰",
        "監管機構針對相關業務展開合規調查或訴訟程序，政策不確定性可能引發相關板塊短線波動",
    ),
    (
        _compile_word_group(("etf", "inflow", "inflows", "institutional", "blackrock", "fidelity", "accumulate", "buy", "purchases")),
        "機構資金配置與場外流動性動態更新",
        "機構投資人與大型資金池持續調整數位資產部位，現貨市場籌碼結構與流動性深度出現顯著變化",
    ),
    (
        _compile_word_group(("fed", "fomc", "powell", "rate", "cpi", "inflation", "jobs", "payroll", "yield", "treasury", "dollar", "dxy")),
        "釋出最新總經政策與利率預期訊號",
        "總體經濟指標與央行官員談話牽動美元流動性預期，跨市場風險資產與加密貨幣定價同步反應",
    ),
    (
        _compile_word_group(("tariff", "tariffs", "trade war", "sanction", "sanctions", "geopolitical", "geopolitics", "war", "red sea", "middle east")),
        "國際貿易政策與地緣局勢最新進展",
        "跨國關稅政策與地緣局勢變動影響全球供應鏈與避險資金流向，市場密切評估通膨與風險溢價",
    ),
    (
        _compile_word_group(("surge", "surged", "soar", "rally", "rallied", "jump", "breakout", "record", "ath", "gain", "bull", "bullish")),
        "買盤動能強勁推動價格與活躍度攀升",
        "受市場利多催化與資金流入帶動，相關資產買盤動能明顯轉強，短線多頭結構維持優勢",
    ),
    (
        _compile_word_group(("crash", "crashed", "plunge", "plunged", "drop", "dropped", "fall", "dump", "slump", "liquidation", "liquidations", "outflow", "outflows", "bear", "bearish")),
        "遭遇獲利了結與短線回調修正壓力",
        "市場出現階段性賣壓與槓桿部位清算，短線價格回測支撐區間，量化策略維持嚴格風控止損",
    ),
    (
        _compile_word_group(("launch", "launched", "upgrade", "partner", "partnership", "expand", "integrate", "mainnet", "testnet", "adopt", "adopted", "adoption")),
        "宣布生態技術升級與重大策略合作",
        "底層網路效能升級與跨平台機構合作持續推進，有助於提升鏈上結算效率與長期基本面價值",
    ),
)
_METRICS_RE = re.compile(
    r"(?:\$\d+(?:\.\d+)?\s*(?:billion|million|trillion|b|m|k)?|\d+(?:\.\d+)?%|\d+\s*bps)",
    flags=re.IGNORECASE,
)


@functools.lru_cache(maxsize=256)
def _compiled_word_re(word_lower: str) -> re.Pattern:
    return re.compile(r"\b" + re.escape(word_lower) + r"\b")


def _contains_word(text: str, word: str) -> bool:
    """Word-boundary keyword match.

    Plain `word in text` substring matching misfires constantly on financial
    text: "bear" matches "bearing", "ai" matches "said", "ban" matches
    "bank", "sec" matches "second", "eth" matches "method". A keyword only
    counts when it appears as a whole word (item 6).
    """
    if not text or not word:
        return False
    w = word.strip().lower()
    if not w:
        return False
    return _compiled_word_re(w).search(text.lower()) is not None


def _first_child_text(parent: Any, tags: Tuple[str, ...]) -> str:
    """Return the first non-empty stripped child text without truth-testing Element nodes."""
    if parent is None:
        return ""
    for tag in tags:
        el = parent.find(tag)
        if el is not None:
            txt = (el.text or "").strip() or "".join(el.itertext()).strip()
            if txt:
                return txt
    return ""


def _parse_feed_ts(value: Any, now: Optional[float] = None) -> Optional[float]:
    """Parse RFC 2822 / ISO 8601 feed timestamps to epoch seconds, or None."""
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    ref_now = time.time() if now is None else float(now)
    dt: Optional[datetime] = None

    norm = f"{raw[:-1]}+00:00" if raw.endswith(("Z", "z")) else raw
    if re.match(r"^\d{4}-\d{2}-\d{2}", norm):
        try:
            dt = datetime.fromisoformat(norm)
        except (ValueError, TypeError):
            dt = None
    if dt is None:
        try:
            dt = parsedate_to_datetime(raw)
        except (ValueError, TypeError):
            dt = None
    if dt is None:
        try:
            dt = datetime.fromisoformat(norm)
        except (ValueError, TypeError):
            return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    try:
        ts = dt.timestamp()
    except (ValueError, OSError, OverflowError):
        return None
    if not math.isfinite(ts) or ts <= 0.0:
        return None
    if ts > ref_now + 300.0:
        return ref_now
    return ts


def parse_rss_atom(xml_text: Union[str, bytes], source_name: str, domain: str, tier: int = 2) -> List[RawEvent]:
    """
    Parses RSS 2.0 and Atom feeds into a standardized list of RawEvent items.
    """
    events: List[RawEvent] = []
    if not xml_text or not isinstance(xml_text, (str, bytes, bytearray)):
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

        title = _clean_html_text(title_el.text) if (title_el is not None and title_el.text) else ""
        link = link_el.text.strip() if (link_el is not None and link_el.text) else ""
        desc = _clean_html_text(desc_el.text) if (desc_el is not None and desc_el.text) else ""
        raw_date = _first_child_text(
            item,
            (
                "pubDate",
                "{http://purl.org/dc/elements/1.1/}date",
                "date",
                "{http://www.w3.org/2005/Atom}updated",
                "updated",
            ),
        )
        pub_ts = _parse_feed_ts(raw_date, now=now)

        if title:
            events.append(RawEvent(
                source=source_name,
                domain=domain,
                title=title,
                url=link or source_name,
                timestamp=pub_ts if pub_ts is not None else now,
                raw_content=desc[:450],
                tier=tier,
                published_at=pub_ts,
            ))

    # Atom (<feed><entry>...</entry></feed>)
    # Handle namespace if present
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    entries = root.findall(".//atom:entry", ns)
    if not entries:
        entries = root.findall(".//entry")
    for entry in entries:
        title_el = entry.find("atom:title", ns)
        if title_el is None:
            title_el = entry.find("title")
        link_els = entry.findall("atom:link", ns)
        if not link_els:
            link_els = entry.findall("link")
        link_el = None
        for cand in link_els:
            rel = (cand.get("rel") or "").strip().lower()
            if rel in ("", "alternate") and (cand.get("href") or (cand.text or "").strip()):
                link_el = cand
                break
        if link_el is None and link_els:
            link_el = link_els[0]
        sum_el = entry.find("atom:summary", ns)
        if sum_el is None:
            sum_el = entry.find("atom:content", ns)
        if sum_el is None:
            sum_el = entry.find("summary")
        if sum_el is None:
            sum_el = entry.find("content")

        title_raw = "".join(title_el.itertext()) if title_el is not None else ""
        desc_raw = "".join(sum_el.itertext()) if sum_el is not None else ""
        title = _clean_html_text(title_raw)
        desc = _clean_html_text(desc_raw)
        link = ""
        if link_el is not None:
            link = (link_el.get("href") or link_el.text or "").strip()
        raw_date = _first_child_text(
            entry,
            (
                "{http://www.w3.org/2005/Atom}published",
                "{http://www.w3.org/2005/Atom}updated",
                "published",
                "updated",
            ),
        )
        pub_ts = _parse_feed_ts(raw_date, now=now)

        if title:
            events.append(RawEvent(
                source=source_name,
                domain=domain,
                title=title,
                url=link or source_name,
                timestamp=pub_ts if pub_ts is not None else now,
                raw_content=desc[:450],
                tier=tier,
                published_at=pub_ts,
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
        try:
            vol = float(item.get("volume24hr") or 0.0)
            if not math.isfinite(vol) or vol < 0.0:
                vol = 0.0
        except (TypeError, ValueError):
            vol = 0.0
        slug = item.get("slug") or ""
        url = f"https://polymarket.com/event/{slug}" if slug else "https://polymarket.com"

        markets = item.get("markets", [])
        odds_str = ""
        if isinstance(markets, list) and markets and isinstance(markets[0], dict):
            outcomes = markets[0].get("outcomes", [])
            outcome_prices = markets[0].get("outcomePrices", [])
            if isinstance(outcomes, str):
                try:
                    outcomes = json.loads(outcomes)
                except Exception:
                    outcomes = []
            if isinstance(outcome_prices, str):
                try:
                    outcome_prices = json.loads(outcome_prices)
                except Exception:
                    outcome_prices = []
            if isinstance(outcomes, list) and isinstance(outcome_prices, list) and outcomes and outcome_prices:
                try:
                    pairs = []
                    for o, p in zip(outcomes, outcome_prices):
                        pf = float(p)
                        if math.isfinite(pf):
                            pairs.append(f"{o}: {pf*100:.0f}%")
                    if pairs:
                        odds_str = " | Odds: " + ", ".join(pairs)
                except Exception as e:
                    logger.debug("Failed to format Polymarket odds, omitting: %s", e)

        if title:
            full_title = f"[Polymarket 24h Vol ${vol:,.0f}] {title}{odds_str}"
            events.append(RawEvent(
                source="Polymarket",
                domain="prediction",
                title=full_title,
                url=url,
                timestamp=now,
                raw_content=odds_str,
                tier=1,
            ))
    return events


def parse_reddit_posts(data: Any, subreddit: str, domain: str) -> List[RawEvent]:
    """
    Parses Reddit JSON listing (r/{subreddit}/hot.json or new.json).
    """
    events: List[RawEvent] = []
    if not isinstance(data, dict):
        return events

    listing = data.get("data")
    if not isinstance(listing, dict):
        return events
    children = listing.get("children")
    if not isinstance(children, list):
        return events
    now = time.time()
    for child in children:
        if not isinstance(child, dict):
            continue
        d = child.get("data")
        if not isinstance(d, dict):
            continue
        title = str(d.get("title") or "").strip()
        try:
            score = int(d.get("score") or 0)
        except (TypeError, ValueError):
            score = 0
        permalink = str(d.get("permalink") or "")
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


def _parse_iso_ts(value: Any) -> float:
    """Compatibility wrapper returning epoch seconds; now on failure."""
    res = _parse_feed_ts(value)
    return res if res is not None else time.time()


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
    latest_body = html.unescape(str(latest.get("body") or "")).strip()
    first_line = _WS_RE.sub(" ", latest_body.split("\n")[0])
    title = f"[StockTwits {symbol}] {first_line[:80]}"
    url = (
        f"https://stocktwits.com/{latest_user}/message/{latest_id}"
        if latest_user and latest_id is not None
        else f"https://api.stocktwits.com/api/2/streams/symbol/{symbol}.json"
    )

    lines = []
    for m in top:
        body = _WS_RE.sub(" ", html.unescape(str(m.get("body") or "")).strip())
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
    raw_content = "\n".join(lines)[:1200]

    now_ts = time.time()
    pub_ts = _parse_feed_ts(latest.get("created_at"), now=now_ts)
    events.append(RawEvent(
        source=f"StockTwits {symbol}",
        domain="forum",
        title=title,
        url=url,
        timestamp=pub_ts if pub_ts is not None else now_ts,
        raw_content=raw_content,
        tier=2,
        thread_id=f"stocktwits:{symbol}",
        published_at=pub_ts,
    ))
    return events


def _rank_fresh_events(
    events: List[RawEvent],
    fetch_now: float,
    page_size: int = 6,
    max_per_source_per_page: int = 2,
) -> List[RawEvent]:
    """Order events newest-first while capping any single source per micro-batch page."""
    if not events:
        return []
    ordered = sorted(
        events,
        key=lambda e: -(e.published_at if e.published_at is not None else fetch_now),
    )
    if page_size <= 0 or max_per_source_per_page <= 0:
        return ordered

    result: List[RawEvent] = []
    remaining = ordered
    while remaining:
        page: List[RawEvent] = []
        deferred: List[RawEvent] = []
        counts: Dict[str, int] = {}
        for ev in remaining:
            src_cnt = counts.get(ev.source, 0)
            if len(page) < page_size and src_cnt < max_per_source_per_page:
                page.append(ev)
                counts[ev.source] = src_cnt + 1
            else:
                deferred.append(ev)
        if len(page) < page_size and deferred:
            need = page_size - len(page)
            page.extend(deferred[:need])
            deferred = deferred[need:]
        result.extend(page)
        remaining = deferred
    return result


class InterruptDebouncer:
    """
    [R4] Anti-Interrupt Storm Debouncer:
    Enforces a 10.0-second cooldown window on out-of-band interrupts.
    The first urgency >= 8 event fires immediately (<500ms latency) and opens the window.
    Subsequent events arriving within the 10s window are batched and dispatched
    in a single merged call when the window closes.
    """

    def __init__(
        self,
        dispatch_fn: Callable[[Any], Coroutine[Any, Any, None]],
        cooldown_sec: float = 10.0,
    ) -> None:
        self.dispatch_fn = dispatch_fn
        self.cooldown_sec = cooldown_sec
        self.pending_events: List[StructuredEvent] = []
        self.last_dispatch_ts: Optional[float] = None
        self.timer_task: Optional[asyncio.Task] = None
        self._bg_tasks: Set[asyncio.Task] = set()
        self._locks: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Lock]" = weakref.WeakKeyDictionary()
        self._fallback_lock = asyncio.Lock()
        self._is_batch = False
        try:
            sig = inspect.signature(dispatch_fn)
            params = list(sig.parameters.values())
            if params:
                p_name = params[0].name.lower()
                p_ann = str(params[0].annotation).lower()
                if "batch" in p_name or "events" in p_name or "list" in p_ann:
                    self._is_batch = True
        except Exception as e:
            logger.debug("Failed to inspect dispatch function signature, using per-event dispatch: %s", e)

    def _get_lock(self) -> asyncio.Lock:
        try:
            loop = asyncio.get_running_loop()
            lock = self._locks.get(loop)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[loop] = lock
            return lock
        except RuntimeError:
            return self._fallback_lock

    def _spawn(self, coro: Coroutine[Any, Any, Any]) -> asyncio.Task:
        task = asyncio.create_task(coro)
        self._bg_tasks.add(task)
        task.add_done_callback(self._bg_tasks.discard)
        return task

    async def trigger(self, event: StructuredEvent) -> None:
        async with self._get_lock():
            now = time.monotonic()
            self.pending_events.append(event)
            timer_inactive = self.timer_task is None or self.timer_task.done()
            # If outside active cooldown window, dispatch immediately (<500ms latency)
            cooldown_elapsed = (
                self.last_dispatch_ts is None
                or (now - self.last_dispatch_ts) >= self.cooldown_sec
            )
            if cooldown_elapsed and timer_inactive:
                to_dispatch = list(self.pending_events)
                self.pending_events.clear()
                self.last_dispatch_ts = now
                self._spawn(self._safe_dispatch(to_dispatch))
                # Open cooldown window timer to flush any arrivals inside 10s
                self.timer_task = self._spawn(self._cooldown_timer())
            elif timer_inactive:
                self.timer_task = self._spawn(self._cooldown_timer())

    async def _safe_dispatch(self, events: List[StructuredEvent]) -> None:
        if not events:
            return
        if self._is_batch:
            try:
                res = self.dispatch_fn(events)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as ex:
                logger.debug("Interrupt batch dispatch error: %s", ex)
        else:
            for ev in events:
                try:
                    res = self.dispatch_fn(ev)
                    if asyncio.iscoroutine(res):
                        await res
                except Exception as ex:
                    logger.debug("Interrupt dispatch error: %s", ex)

    async def _cooldown_timer(self) -> None:
        try:
            await asyncio.sleep(self.cooldown_sec)
            async with self._get_lock():
                self.timer_task = None
                if self.pending_events:
                    to_dispatch = list(self.pending_events)
                    self.pending_events.clear()
                    self.last_dispatch_ts = time.monotonic()
                    self._spawn(self._safe_dispatch(to_dispatch))
        finally:
            if self.timer_task is asyncio.current_task():
                self.timer_task = None


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
        on_urgent_interrupt: Optional[Callable[[Any], Coroutine[Any, Any, None]]] = None,
    ) -> None:
        self.client = client
        self.dedup = dedup_buffer or DeduplicationBuffer(capacity=5000)
        self.on_urgent_interrupt = on_urgent_interrupt
        self.debouncer: Optional[InterruptDebouncer] = (
            InterruptDebouncer(on_urgent_interrupt, cooldown_sec=10.0) if on_urgent_interrupt else None
        )

        # Rolling storage of recent structured events
        self.recent_structured_events: deque[StructuredEvent] = deque(maxlen=200)
        self.is_running: bool = False
        self._harvest_task: Optional[asyncio.Task] = None
        self._interrupt_tasks: Set[asyncio.Task] = set()

    def _spawn_interrupt(self, coro: Coroutine[Any, Any, Any]) -> None:
        task = asyncio.create_task(coro)
        self._interrupt_tasks.add(task)
        task.add_done_callback(self._interrupt_tasks.discard)

    @staticmethod
    def _event_iso_ts(raw_ts: Any, fallback_iso: str) -> str:
        try:
            val = float(raw_ts)
            if math.isfinite(val) and val > 0.0:
                return datetime.fromtimestamp(val, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except (TypeError, ValueError, OSError, OverflowError):
            pass
        return fallback_iso

    @staticmethod
    def _fetch_registry_entry(
        entry: Dict[str, Any],
        max_per_source: int,
        timeout_sec: float,
        max_age_hours: Optional[float] = DEFAULT_MAX_ARTICLE_AGE_HOURS,
        fetch_now: Optional[float] = None,
    ) -> List[RawEvent]:
        """Fetch + parse ONE registry entry (worker side, no shared state).

        Pure per-entry work: one requests.get plus the type-dispatched
        parser. Deliberately does NOT touch self.dedup -- dedup runs
        sequentially in the caller, in registry order, so parallel
        fetching cannot change event order or dedup outcomes. Stale
        dated articles beyond max_age_hours are dropped, and remaining
        per-source items are sorted newest-first before capping at
        max_per_source. Any failure yields [] (never fatal).
        """
        import requests

        etype = str(entry.get("type", ""))
        ua = SEC_EDGAR_USER_AGENT if entry.get("id") == "sec_edgar_8k" else USER_AGENT
        ref_now = time.time() if fetch_now is None else float(fetch_now)
        resp = None
        try:
            resp = requests.get(
                entry["url"], headers={"User-Agent": ua}, timeout=timeout_sec
            )
            if resp.status_code != 200:
                logger.debug("Registry feed %s returned HTTP %d", entry.get("id"), resp.status_code)
                return []
            if etype in ("rss", "atom"):
                raw_xml = resp.content if isinstance(getattr(resp, "content", None), (bytes, bytearray)) else resp.text
                parsed = parse_rss_atom(raw_xml, entry["name"], entry["domain"], tier=int(entry.get("tier", 2)))
            elif etype == "rest_json":
                parsed = parse_polymarket_events(resp.json())
            else:
                logger.debug("Unknown registry feed type %r for %s, skipped", etype, entry.get("id"))
                return []

            if max_age_hours is not None and max_age_hours > 0:
                max_age_sec = float(max_age_hours) * 3600.0
                parsed = [
                    e for e in parsed
                    if e.published_at is None or (ref_now - e.published_at) <= max_age_sec
                ]
            parsed.sort(key=lambda e: -(e.published_at if e.published_at is not None else ref_now))
            return parsed[:max_per_source]
        except Exception as ex:
            logger.debug("Registry feed fetch error for %s: %s", entry.get("id"), ex)
            return []
        finally:
            if resp is not None:
                try:
                    resp.close()
                except Exception:
                    pass

    def fetch_from_registry(
        self,
        max_per_source: int = 5,
        timeout_sec: float = 3.5,
        max_age_hours: Optional[float] = DEFAULT_MAX_ARTICLE_AGE_HOURS,
    ) -> List[RawEvent]:
        """
        Registry-driven fetch (item 12B): every entry in FEED_REGISTRY is a
        no-login source (user rule 2026-11-13), dispatched by its `type`:
        rss/atom -> parse_rss_atom, rest_json -> parse_polymarket_events.
        `stocktwits` entries are owned by ForumCollector (forum batch, own
        cadence) and are explicitly skipped here, so the same stream is
        never scored twice per digest. Unknown types are skipped, never
        fatal: one dead source must not take down the whole digest.

        Fetches all active registry entries concurrently (ThreadPoolExecutor,
        up to 10 workers), filters out stale items older than max_age_hours,
        dedups in registry round-robin order, and ranks newest-first with
        per-batch source diversity so fresh breaking news lands in events[:6].
        """
        fetchable = [e for e in FEED_REGISTRY if str(e.get("type", "")) != "stocktwits"]
        if not fetchable:
            return []
        fetch_now = time.time()
        max_age_sec = float(max_age_hours) * 3600.0 if (max_age_hours is not None and max_age_hours > 0) else None
        workers = min(10, len(fetchable))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            per_entry = list(
                pool.map(
                    lambda entry: self._fetch_registry_entry(
                        entry,
                        max_per_source,
                        timeout_sec,
                        max_age_hours=max_age_hours,
                        fetch_now=fetch_now,
                    ),
                    fetchable,
                )
            )

        fresh_events: List[RawEvent] = []
        max_len = max((len(p) for p in per_entry), default=0)
        for slot in range(max_len):
            for parsed in per_entry:
                if slot < len(parsed):
                    e = parsed[slot]
                    if max_age_sec is not None and e.published_at is not None and (fetch_now - e.published_at) > max_age_sec:
                        continue
                    if self.dedup.is_new(e.title, e.url):
                        fresh_events.append(e)
                    elif hasattr(self.client, "record_dedup_hit"):
                        self.client.record_dedup_hit()
        return _rank_fresh_events(
            fresh_events,
            fetch_now=fetch_now,
            page_size=6,
            max_per_source_per_page=2,
        )

    def fetch_live_feeds(
        self,
        max_per_source: int = 5,
        timeout_sec: float = 3.5,
        max_age_hours: Optional[float] = DEFAULT_MAX_ARTICLE_AGE_HOURS,
    ) -> List[RawEvent]:
        """
        Fetches genuine live RSS news items from multi-domain feeds over HTTP.
        Returns newly discovered, deduplicated RawEvents ranked newest-first.
        """
        if os.environ.get("ARENA_FAST_TEST") == "1":
            # Test fixture only: clearly marked synthetic data for the test
            # suite (conftest sets ARENA_FAST_TEST=1). Never presented as
            # real news: source is "Test Feed" and titles carry a [TEST]
            # marker, so these events can never be mistaken for genuine
            # intelligence in the veto pipeline (item 6).
            now = time.time()
            return [
                RawEvent(source="Test Feed", domain="crypto", title="[TEST] Ethereum L2 Scaling Inflows Rise 15%", url="https://coindesk.com", timestamp=now),
                RawEvent(source="Test Feed", domain="macro", title="[TEST] Fed Reiterates Rate Path Stability in Policy Note", url="https://forexlive.com", timestamp=now),
            ]

        # Registry-driven fetch (item 12B): the 4 previously hardcoded RSS
        # sources are registry entries now (Decrypt included); the single
        # source of truth is FEED_REGISTRY, which holds no-login sources
        # only (user rule 2026-11-13).
        return self.fetch_from_registry(
            max_per_source=max_per_source,
            timeout_sec=timeout_sec,
            max_age_hours=max_age_hours,
        )

    def push_raw_events(self, raw_events: List[RawEvent]) -> List[RawEvent]:
        """Filters incoming raw events through the deduplication buffer."""
        fresh = []
        for e in raw_events:
            if self.dedup.is_new(e.title, e.url):
                fresh.append(e)
            else:
                # Dedup hit: count it, do not claim a token figure
                # (item 12 / A4-3: the old 420 was a fixed estimate).
                if hasattr(self.client, "record_dedup_hit"):
                    self.client.record_dedup_hit()
        return fresh

    async def process_batch(self, events: List[RawEvent]) -> List[StructuredEvent]:
        """
        Processes a micro-batch of raw events with LLM_MODEL_INGEST to produce structured JSON events
        with Traditional Chinese (繁體中文) headlines and summaries.
        """
        if not events:
            return []

        # Build concise extraction prompt including article content snippet
        batch = events[:6]
        lines = []
        for idx, e in enumerate(batch, start=1):
            snippet = f" | 內容摘要: {e.raw_content[:220]}" if e.raw_content else ""
            lines.append(f"{idx}. [{e.source} | {e.domain}] 標題: {e.title}{snippet}")
        news_block = "\n".join(lines)

        system_prompt = (
            "You are an elite bilingual quantitative intelligence analyst. Analyze the financial/crypto/geopolitical news items.\n"
            "Output a single JSON object with key 'events' containing an array of objects using this EXACT schema:\n"
            "{\n"
            '  "events": [\n'
            "    {\n"
            '      "index": 1,\n'
            '      "entities_tickers": ["ETH", "FED"],\n'
            '      "urgency_score": 6,\n'
            '      "sentiment_score": 0.35,\n'
            '      "consensus": {"bullish": 0.6, "bearish": 0.25, "neutral": 0.15},\n'
            '      "headline_zh": "繁體中文新聞標題（精準翻譯並提煉核心事件，約15至28字）",\n'
            '      "summary": "繁體中文內容總結（以繁體中文完整總結新聞內容要點、關鍵數據及對加密貨幣或宏觀市場的多空影響，約35至70字）"\n'
            "    }\n"
            "  ]\n"
            "}\n"
            "CRITICAL REQUIREMENT: Both 'headline_zh' and 'summary' MUST be written strictly in Traditional Chinese (繁體中文). Never output English in headline_zh or summary.\n"
            "For forum threads only, also include 'consensus' with the share of replies that are bullish / bearish / neutral (three numbers summing to 1.0); omit it for news items.\n"
            "Urgency rubric: 1-4=Routine noise, 5-7=Notable market mover, 8-10=Black Swan, Fed rate shock, election result, major war, or SEC enforcement."
        )

        user_prompt = (
            "請將以下即時外電新聞逐筆提取結構化情報，並務必以「繁體中文」撰寫每筆新聞的 headline_zh（繁體中文標題）與 summary（繁體中文內容與市場影響總結）：\n\n"
            f"{news_block}"
        )

        parsed_json = None
        if not (hasattr(self.client, "is_gateway_online") and self.client.is_gateway_online is False):
            parsed_json = await self.client.chat_json(
                model=self.client.model_ingest,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.0,
                max_tokens=2500,
            )

        structured_results: List[StructuredEvent] = []
        iso_now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        if parsed_json and "events" in parsed_json and isinstance(parsed_json["events"], list):
            processed_indices: Set[int] = set()
            for pos, item in enumerate(parsed_json["events"], start=1):
                if not isinstance(item, dict):
                    continue
                try:
                    raw_idx = item.get("index", pos)
                    idx = (int(raw_idx) - 1) if raw_idx is not None else (pos - 1)
                    resolved_idx = idx if (0 <= idx < len(batch)) else min(pos - 1, len(batch) - 1)
                    raw = batch[resolved_idx]
                    raw_urg = item.get("urgency_score")
                    urg_val = int(float(raw_urg)) if raw_urg is not None else 5
                    urgency = max(1, min(10, urg_val))
                    raw_sent = item.get("sentiment_score")
                    sent_val = float(raw_sent) if raw_sent is not None else 0.0
                    if not math.isfinite(sent_val):
                        sent_val = 0.0
                    sentiment = max(-1.0, min(1.0, sent_val))
                    raw_tickers = item.get("entities_tickers", [])
                    if isinstance(raw_tickers, str):
                        tickers = [raw_tickers.strip().upper()] if raw_tickers.strip() else []
                    elif isinstance(raw_tickers, list):
                        tickers = [str(t).strip().upper() for t in raw_tickers if str(t).strip()]
                    else:
                        tickers = []
                    consensus = self._parse_consensus(item.get("consensus"))

                    raw_headline_zh = str(item.get("headline_zh") or "").strip()
                    raw_summary = str(item.get("summary") or "").strip()

                    fallback_head_zh, fallback_sum_zh = self._build_zh_headline_and_summary(
                        raw.title, raw.raw_content, raw.source, raw.domain, urgency, sentiment, tickers
                    )

                    headline_zh = raw_headline_zh if self._contains_cjk(raw_headline_zh) else fallback_head_zh
                    summary = raw_summary if self._contains_cjk(raw_summary) else fallback_sum_zh

                    se = StructuredEvent(
                        timestamp=self._event_iso_ts(raw.timestamp, iso_now),
                        source=raw.source,
                        domain=raw.domain,
                        entities_tickers=tickers,
                        urgency_score=urgency,
                        sentiment_score=sentiment,
                        summary=summary,
                        raw_title=raw.title,
                        headline_zh=headline_zh,
                        raw_content=raw.raw_content,
                        tier=raw.tier,
                        thread_id=raw.thread_id,
                        consensus=consensus,
                    )
                    structured_results.append(se)
                    processed_indices.add(resolved_idx)
                    self.recent_structured_events.append(se)

                    # Trigger out-of-band interrupt if event is critical
                    if urgency >= 8:
                        logger.warning(
                            "CRITICAL INTELLIGENCE SHOCK (Urgency %d): %s [%s]",
                            urgency, summary, raw.title[:80]
                        )
                        if self.debouncer:
                            self._spawn_interrupt(self.debouncer.trigger(se))
                        elif self.on_urgent_interrupt:
                            self._spawn_interrupt(self.on_urgent_interrupt(se))

                except Exception as ex:
                    logger.debug("Failed parsing individual event extraction: %s", ex)

            # Release dedup entries for unprocessed items within this batch AND
            # overflow events beyond the micro-batch cap so nothing is silently dropped.
            if structured_results:
                for b_idx, raw_item in enumerate(batch):
                    if b_idx not in processed_indices:
                        self.dedup.forget(raw_item.title, raw_item.url)
                if len(events) > len(batch):
                    for dropped in events[len(batch):]:
                        self.dedup.forget(dropped.title, dropped.url)

        if not structured_results:
            # Genuine Local Deterministic NLP Extraction on real news headlines & content
            fallback_batch = events[:15]
            for raw in fallback_batch:
                combined_text = f"{raw.title} {raw.raw_content}".lower()
                urgency = 5
                sentiment = 0.0

                # Real financial vocabulary polarity scoring (precompiled single-pass regexes)
                bull_cnt = len({m.group(0) for m in _BULL_RE.finditer(combined_text)})
                bear_cnt = len({m.group(0) for m in _BEAR_RE.finditer(combined_text)})

                if bull_cnt > bear_cnt:
                    sentiment = min(0.85, 0.25 * (bull_cnt - bear_cnt) + 0.2)
                elif bear_cnt > bull_cnt:
                    sentiment = max(-0.85, -0.25 * (bear_cnt - bull_cnt) - 0.2)

                # Real urgency rubric
                if _URG9_RE.search(combined_text):
                    urgency = 9
                elif _URG7_RE.search(combined_text):
                    urgency = 7
                elif _URG6_RE.search(combined_text):
                    urgency = 6

                # Ticker & Entity detection
                tickers = [sym for pat, sym in _TICKER_RES if pat.search(combined_text)]
                if not tickers:
                    tickers.append("ETH" if raw.domain == "crypto" else "MACRO")

                headline_zh, summary_zh = self._build_zh_headline_and_summary(
                    raw.title, raw.raw_content, raw.source, raw.domain, urgency, sentiment, tickers
                )

                # Forum consensus without the LLM: a deterministic split of
                # the single event score (bullish/bearish/neutral shares),
                # not a measured reply distribution (item 12B).
                s2 = round(sentiment, 2)
                consensus = {
                    "bullish": round(max(0.0, s2), 2),
                    "bearish": round(max(0.0, -s2), 2),
                    "neutral": round(1.0 - abs(s2), 2),
                } if raw.thread_id else None

                se = StructuredEvent(
                    timestamp=self._event_iso_ts(raw.timestamp, iso_now),
                    source=raw.source,
                    domain=raw.domain,
                    entities_tickers=tickers,
                    urgency_score=urgency,
                    sentiment_score=s2,
                    summary=summary_zh,
                    raw_title=raw.title,
                    headline_zh=headline_zh,
                    raw_content=raw.raw_content,
                    tier=raw.tier,
                    thread_id=raw.thread_id,
                    consensus=consensus,
                )
                structured_results.append(se)
                self.recent_structured_events.append(se)
                if urgency >= 8:
                    if self.debouncer:
                        self._spawn_interrupt(self.debouncer.trigger(se))
                    elif self.on_urgent_interrupt:
                        self._spawn_interrupt(self.on_urgent_interrupt(se))

            if len(events) > len(fallback_batch):
                for dropped in events[len(fallback_batch):]:
                    self.dedup.forget(dropped.title, dropped.url)

        return structured_results

    @staticmethod
    def _contains_cjk(text: str) -> bool:
        return bool(text and re.search(r"[\u4e00-\u9fff]", text))

    @staticmethod
    def _parse_consensus(value: Any) -> Optional[Dict[str, float]]:
        """Validates an LLM-returned reply-sentiment distribution.

        Returns normalized bullish/bearish/neutral shares summing to 1.0,
        or None when the value is missing, malformed, or all zeros.
        """
        if not isinstance(value, dict):
            return None
        try:
            b = float(value.get("bullish", 0.0))
            be = float(value.get("bearish", 0.0))
            n = float(value.get("neutral", 0.0))
        except (TypeError, ValueError):
            return None
        if not (math.isfinite(b) and math.isfinite(be) and math.isfinite(n)):
            return None
        b = max(0.0, b)
        be = max(0.0, be)
        n = max(0.0, n)
        total = b + be + n
        if not math.isfinite(total) or total <= 0.0:
            return None
        return {
            "bullish": round(b / total, 2),
            "bearish": round(be / total, 2),
            "neutral": round(n / total, 2),
        }

    @classmethod
    def ensure_traditional_chinese(cls, event: StructuredEvent) -> Tuple[str, str]:
        """
        Guarantees that any StructuredEvent has a Traditional Chinese headline and Traditional Chinese summary.
        """
        has_zh_head = cls._contains_cjk(event.headline_zh)
        has_zh_sum = cls._contains_cjk(event.summary)
        if has_zh_head and has_zh_sum:
            return event.headline_zh, event.summary

        gen_head, gen_sum = cls._build_zh_headline_and_summary(
            event.raw_title or event.summary,
            "",
            event.source,
            event.domain,
            event.urgency_score,
            event.sentiment_score,
            event.entities_tickers,
        )
        final_head = event.headline_zh if has_zh_head else (event.summary if (has_zh_sum and len(event.summary) <= 36) else gen_head)
        final_sum = event.summary if has_zh_sum else gen_sum
        return final_head, final_sum

    @classmethod
    def _build_zh_headline_and_summary(
        cls,
        title: str,
        raw_content: str,
        source: str,
        domain: str,
        urgency: int = 5,
        sentiment: float = 0.0,
        tickers: Optional[List[str]] = None,
    ) -> Tuple[str, str]:
        """
        Synthesizes a Traditional Chinese headline and comprehensive Traditional Chinese content summary
        from real English financial wires when LLM translation is unavailable or fallback is triggered.
        """
        clean_title = _clean_html_text(title)
        clean_body = _clean_html_text(raw_content)
        combined = f"{clean_title} {clean_body}".lower()

        # Extract key numerical metrics (percentages, dollar amounts, bps)
        nums = _METRICS_RE.findall(f"{clean_title} {clean_body}")
        metrics_str = f"（關鍵數據：{', '.join(nums[:3])}）" if nums else ""

        # Identify primary entities in Traditional Chinese (precompiled single-pass regexes)
        entities_zh: List[str] = []
        for pat, label_zh in _ENTITY_RES:
            if pat.search(combined) and label_zh not in entities_zh:
                entities_zh.append(label_zh)

        domain_label_map = {
            "crypto": "加密資產市場",
            "macro": "全球總體經濟",
            "tech": "科技與算力產業",
            "geopolitics": "地緣政治與局勢",
            "corporate": "企業財報與治理",
            "prediction": "預測市場共識",
        }
        primary_subject = "、".join(entities_zh[:2]) if entities_zh else domain_label_map.get(domain, "全球金融市場")

        # Identify action / theme in Traditional Chinese
        action_head = "最新市場動態與產業基本面快訊"
        action_body = "外電快訊揭示最新產業政策與資金流向變化，量化引擎已將情緒權重納入多空風控評估"
        for pat, head, body in _THEME_RES:
            if pat.search(combined):
                action_head = head
                action_body = body
                break

        sentiment_tag = "偏多利好" if sentiment > 0.15 else ("偏空警示" if sentiment < -0.15 else "中性觀望")
        ticker_str = "、".join(tickers[:3]) if tickers else ("ETH" if domain == "crypto" else "MACRO")

        headline_zh = f"【{source}】{primary_subject}{action_head}{metrics_str}"
        summary_zh = (
            f"綜合外電報導：{primary_subject}近期{action_head}{metrics_str}。"
            f"{action_body}。目前情報情緒評估為「{sentiment_tag}」（關聯標的：{ticker_str}｜原文標題：{clean_title}）。"
        )
        return headline_zh, summary_zh

    @classmethod
    def _localize_real_headline(cls, title: str, source: str, domain: str) -> str:
        """
        Backward-compatible wrapper returning the Traditional Chinese summary.
        """
        _, summary_zh = cls._build_zh_headline_and_summary(title, "", source, domain)
        return summary_zh

    def get_latest_events(self, count: int = 30) -> List[StructuredEvent]:
        """Returns the most recent structured events."""
        return list(self.recent_structured_events)[-count:]

