"""
src/data/quote_manager.py - WebSocket Quote Manager.
Implements Phase 1: low-latency WS primary stream with resilient quote
caching. Audit 3.13: this class never implemented the REST cascade its
old docstring promised -- the real Binance -> Kraken -> Coinbase
cascade with provider cooldowns lives in
LiveArenaEngine.fetch_realtime_crypto_quote.
"""
from __future__ import annotations

import logging
import time
from decimal import Decimal
from typing import Any, Callable, Dict, Optional

import requests

from src.data.ws_feed import StreamingCryptoFeed

logger = logging.getLogger(__name__)


class QuoteManager:
    """
    Coordinates sub-10ms WebSocket ticker streaming with resilient quote
    caching. It does NOT implement a REST provider cascade: when the WS
    feed goes stale, the engine falls back to its own REST cascade
    (LiveArenaEngine.fetch_realtime_crypto_quote).
    """

    def __init__(
        self,
        session: Optional[requests.Session] = None,
        on_ws_quote: Optional[Callable[[Any], None]] = None,
        ws_stale_threshold_sec: float = 3.0,
        symbol: str = "ETH/USD",
    ) -> None:
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": "TradeBot0-LiveArena/2.0"})
        self.ws_feed = StreamingCryptoFeed(
            on_quote_callback=self._on_internal_ws_quote,
            stale_threshold_sec=ws_stale_threshold_sec,
            symbol=symbol,
        )
        self._external_ws_callback = on_ws_quote
        self.latest_quote: Optional[Any] = None

    def _on_internal_ws_quote(self, quote: Any) -> None:
        self.latest_quote = quote
        if self._external_ws_callback is not None:
            self._external_ws_callback(quote)

    def start_ws(self) -> None:
        self.ws_feed.start()

    def stop_ws(self) -> None:
        self.ws_feed.stop()

    def get_fresh_ws_quote(self, now: Optional[float] = None) -> Optional[Any]:
        if self.ws_feed.is_fresh(now=now):
            return self.ws_feed.latest_ws_quote
        return None

