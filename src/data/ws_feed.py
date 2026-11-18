"""
src/data/ws_feed.py - High-Performance Streaming WebSocket Feed for ETH/USD
Implements Phase 1 (P1): Low-Latency WebSocket Streaming & Resilient Circuit Breaking.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
from decimal import Decimal
from typing import Any, Callable, Dict, Optional

import websockets

logger = logging.getLogger(__name__)


class StreamingCryptoFeed:
    """
    Asynchronous WebSocket ticker stream client for ETH/USDT (Binance primary)
    with exponential backoff reconnection and sub-10ms quote delivery.
    """

    BINANCE_WS_URL = "wss://stream.binance.com:9443/ws/ethusdt@ticker"
    BINANCE_ALT_WS_URL = "wss://stream.binance.com:443/ws/ethusdt@ticker"

    def __init__(
        self,
        on_quote_callback: Callable[[Any], None],
        ws_url: Optional[str] = None,
        stale_threshold_sec: float = 3.0,
        symbol: str = "ETH/USD",
    ) -> None:
        from src.data.quote_feeds import parse_symbol_pairs

        stream_name = parse_symbol_pairs(symbol)["ws_stream"]
        self.symbol = symbol
        self.on_quote = on_quote_callback
        self.ws_url = ws_url or f"wss://stream.binance.com:9443/ws/{stream_name}"
        self.alt_ws_url = f"wss://stream.binance.com:443/ws/{stream_name}"
        self.stale_threshold_sec = float(stale_threshold_sec)
        self.running: bool = False
        self.connected: bool = False
        self.last_msg_ts: float = 0.0
        self.latest_ws_quote: Optional[Any] = None
        self.reconnect_count: int = 0
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._active_ws: Optional[Any] = None

    def is_fresh(self, now: Optional[float] = None) -> bool:
        """Returns True if the WebSocket is connected and delivered a tick within stale_threshold_sec."""
        if not self.connected or self.last_msg_ts <= 0.0 or self.latest_ws_quote is None:
            return False
        current = time.time() if now is None else now
        return (current - self.last_msg_ts) < self.stale_threshold_sec

    def start(self) -> None:
        if self.running:
            return
        if os.environ.get("ARENA_FAST_TEST") == "1":
            # Avoid opening real external sockets during hermetic unit tests
            return
        self.running = True
        self._thread = threading.Thread(
            target=self._run_loop,
            daemon=True,
            name="WebSocketFeedThread",
        )
        self._thread.start()

    def stop(self) -> None:
        self.running = False
        self.connected = False
        loop = self._loop
        ws = self._active_ws
        if loop and loop.is_running():
            if ws is not None:
                try:
                    asyncio.run_coroutine_threadsafe(ws.close(), loop)
                except Exception as e:
                    logger.debug("WebSocket close failed during stop: %s", e)
            try:
                loop.call_soon_threadsafe(loop.stop)
            except Exception as e:
                logger.debug("WebSocket loop stop failed: %s", e)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None

    def _run_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._connect_and_stream())
        except Exception as e:
            logger.debug("WebSocket event loop terminated: %s", e)
        finally:
            try:
                self._loop.close()
            except Exception as e:
                logger.debug("WebSocket event loop close failed: %s", e)
            self._loop = None

    async def _connect_and_stream(self) -> None:
        backoff = 1.0
        urls = [self.ws_url, getattr(self, "alt_ws_url", self.BINANCE_ALT_WS_URL)]
        url_idx = 0
        while self.running:
            target_url = urls[url_idx % len(urls)]
            try:
                logger.info("Connecting to Binance WebSocket ticker stream (%s)...", target_url)
                async with websockets.connect(
                    target_url,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=5,
                ) as ws:
                    self._active_ws = ws
                    self.connected = True
                    backoff = 1.0
                    logger.info("Binance WebSocket ticker stream connected successfully.")

                    async for message in ws:
                        if not self.running:
                            break
                        data = json.loads(message) if isinstance(message, (str, bytes)) else message
                        if isinstance(data, dict):
                            quote = self._parse_binance_ticker(data)
                            if quote is not None:
                                self.last_msg_ts = time.time()
                                self.latest_ws_quote = quote
                                self.on_quote(quote)
                # Clean stream end (server closed the socket without raising):
                # do NOT reconnect immediately; wait out the same backoff.
                self.connected = False
                self._active_ws = None
                if not self.running:
                    break
                # Audit 3.15: a clean server close is still a re-establishment
                # of the feed, so it counts as a reconnect like a failed
                # connect does (only when we actually reconnect -- after the
                # running check above).
                self.reconnect_count += 1
                logger.warning("WebSocket stream closed cleanly. Reconnecting in %.1fs...", backoff)
                for _ in range(int(backoff * 10)):
                    if not self.running:
                        break
                    await asyncio.sleep(0.1)
                backoff = min(15.0, backoff * 1.5)
            except Exception as e:
                self.connected = False
                self._active_ws = None
                self.reconnect_count += 1
                url_idx += 1
                if not self.running:
                    break
                logger.warning("WebSocket disconnected: %s. Reconnecting in %.1fs...", e, backoff)
                for _ in range(int(backoff * 10)):
                    if not self.running:
                        break
                    await asyncio.sleep(0.1)
                backoff = min(15.0, backoff * 1.5)

    def _parse_binance_ticker(self, d: Dict[str, Any]) -> Optional[Any]:
        """
        Parses Binance 24hr miniTicker/ticker payload into a LiveQuote instance.
        Fields: c (last price), b (best bid), a (best ask), h (24h high), l (24h low), v (24h vol), P (24h change %).
        """
        from src.data.live_engine import LiveQuote

        try:
            if "c" not in d:
                return None
            price = Decimal(str(d["c"])).quantize(Decimal("0.01"))
            if price <= Decimal("0"):
                return None
            bid = Decimal(str(d.get("b", price))).quantize(Decimal("0.01"))
            ask = Decimal(str(d.get("a", price))).quantize(Decimal("0.01"))
            if bid <= Decimal("0"):
                bid = price
            if ask <= Decimal("0"):
                ask = price
            high = Decimal(str(d.get("h", price))).quantize(Decimal("0.01"))
            low = Decimal(str(d.get("l", price))).quantize(Decimal("0.01"))
            vol = Decimal(str(d.get("v", "0"))).quantize(Decimal("0.01"))
            chg = Decimal(str(d.get("P", "0.00"))).quantize(Decimal("0.01"))

            return LiveQuote(
                price=price,
                bid=bid,
                ask=ask,
                high_24h=high,
                low_24h=low,
                volume_24h=vol,
                change_24h_pct=chg,
                source="Binance WS (Sub-10ms)",
                timestamp=time.time(),
                is_offline=False,
            )
        except Exception as parse_err:
            logger.debug("Failed to parse ticker payload: %s", parse_err)
            return None

