"""src/intelligence/forum_collector.py - Forum thread collector (item 12B).

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
        m = re.search(r"/symbol/([^/]+)\.json", url)
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
        resp = None
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
        finally:
            if resp is not None:
                try:
                    resp.close()
                except Exception:
                    pass

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
