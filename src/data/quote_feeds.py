"""
src/data/quote_feeds.py - Market Symbol Mapping, LiveQuote & Multi-Exchange REST Cascade.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# A quote older than this is stale and never tradable.
QUOTE_STALE_SEC = 5.0


@dataclass
class LiveQuote:
    price: Decimal
    bid: Decimal
    ask: Decimal
    high_24h: Decimal
    low_24h: Decimal
    volume_24h: Decimal
    change_24h_pct: Decimal
    source: str
    timestamp: float
    is_offline: bool = False


def parse_symbol_pairs(symbol: str) -> Dict[str, str]:
    """Normalizes a trading pair string (e.g. 'ETH/USD', 'BTC/USD') into exchange-specific forms."""
    clean = str(symbol or "ETH/USD").strip().upper()
    if "/" in clean:
        base, quote = clean.split("/", 1)
    elif "-" in clean:
        base, quote = clean.split("-", 1)
    else:
        base, quote = clean or "ETH", "USD"
    quote_usdt = "USDT" if quote in ("USD", "USDT", "USDC") else quote
    return {
        "symbol": f"{base}/{quote}",
        "base": base,
        "quote": quote,
        "binance": f"{base}{quote_usdt}",
        "kraken": f"{base}{quote}",
        "coinbase": f"{base}-{quote}",
        "yahoo": f"{base}-{quote}",
        "ws_stream": f"{base.lower()}{quote_usdt.lower()}@ticker",
    }


class QuoteFeedsMixin:
    """REST exchange cascade (Binance -> Kraken -> Coinbase) and WS freshness switching."""

    def _quote_pairs(self) -> Dict[str, str]:
        return parse_symbol_pairs(getattr(self, "symbol", "ETH/USD"))

    def _fetch_binance_quote(self) -> Optional[LiveQuote]:
        pairs = self._quote_pairs()
        try:
            r_bin = self.session.get(
                f"https://api.binance.com/api/v3/ticker/24hr?symbol={pairs['binance']}",
                timeout=1.2,
            )
            if r_bin.status_code == 200:
                b = r_bin.json()
                return LiveQuote(
                    price=Decimal(str(b["lastPrice"])).quantize(Decimal("0.01")),
                    bid=Decimal(str(b["bidPrice"])).quantize(Decimal("0.01")),
                    ask=Decimal(str(b["askPrice"])).quantize(Decimal("0.01")),
                    high_24h=Decimal(str(b["highPrice"])).quantize(Decimal("0.01")),
                    low_24h=Decimal(str(b["lowPrice"])).quantize(Decimal("0.01")),
                    volume_24h=Decimal(str(b["volume"])).quantize(Decimal("0.01")),
                    change_24h_pct=Decimal(str(b["priceChangePercent"])).quantize(Decimal("0.01")),
                    source="Binance Live",
                    timestamp=time.time(),
                    is_offline=False,
                )
        except Exception as e:
            logger.debug("Binance quote feed error (%s): %s", pairs["binance"], e)
        return None

    def _fetch_kraken_quote(self) -> Optional[LiveQuote]:
        pairs = self._quote_pairs()
        try:
            r_krk = self.session.get(
                f"https://api.kraken.com/0/public/Ticker?pair={pairs['kraken']}",
                timeout=1.5,
            )
            if r_krk.status_code == 200:
                k_res = r_krk.json().get("result", {})
                if k_res:
                    pair_key = next(iter(k_res.keys()))
                    k = k_res[pair_key]
                    price = Decimal(str(k["c"][0])).quantize(Decimal("0.01"))
                    open_p = Decimal(str(k["o"]))
                    chg = (
                        (((price - open_p) / open_p) * Decimal("100")).quantize(Decimal("0.01"))
                        if open_p > 0
                        else Decimal("0.00")
                    )
                    return LiveQuote(
                        price=price,
                        bid=Decimal(str(k["b"][0])).quantize(Decimal("0.01")),
                        ask=Decimal(str(k["a"][0])).quantize(Decimal("0.01")),
                        high_24h=Decimal(str(k["h"][1])).quantize(Decimal("0.01")),
                        low_24h=Decimal(str(k["l"][1])).quantize(Decimal("0.01")),
                        volume_24h=Decimal(str(k["v"][1])).quantize(Decimal("0.01")),
                        change_24h_pct=chg,
                        source="Kraken Live",
                        timestamp=time.time(),
                        is_offline=False,
                    )
        except Exception as e:
            logger.debug("Kraken quote feed error (%s): %s", pairs["kraken"], e)
        return None

    def _fetch_coinbase_quote(self) -> Optional[LiveQuote]:
        pairs = self._quote_pairs()
        try:
            r_tick = self.session.get(
                f"https://api.exchange.coinbase.com/products/{pairs['coinbase']}/ticker",
                timeout=1.2,
            )
            r_stats = self.session.get(
                f"https://api.exchange.coinbase.com/products/{pairs['coinbase']}/stats",
                timeout=1.2,
            )
            if r_tick.status_code == 200:
                t_data = r_tick.json()
                price = Decimal(str(t_data["price"])).quantize(Decimal("0.01"))
                bid = Decimal(str(t_data.get("bid", price))).quantize(Decimal("0.01"))
                ask = Decimal(str(t_data.get("ask", price))).quantize(Decimal("0.01"))
                vol = Decimal(str(t_data.get("volume", "0"))).quantize(Decimal("0.01"))
                high_24 = price
                low_24 = price
                chg_pct = Decimal("0.00")
                if r_stats.status_code == 200:
                    s_data = r_stats.json()
                    open_24 = Decimal(str(s_data.get("open", price)))
                    high_24 = Decimal(str(s_data.get("high", price))).quantize(Decimal("0.01"))
                    low_24 = Decimal(str(s_data.get("low", price))).quantize(Decimal("0.01"))
                    if open_24 > Decimal("0"):
                        chg_pct = (((price - open_24) / open_24) * Decimal("100")).quantize(Decimal("0.01"))
                return LiveQuote(
                    price=price,
                    bid=bid,
                    ask=ask,
                    high_24h=high_24,
                    low_24h=low_24,
                    volume_24h=vol,
                    change_24h_pct=chg_pct,
                    source="Coinbase Live",
                    timestamp=time.time(),
                    is_offline=False,
                )
        except Exception as e:
            logger.debug("Coinbase quote feed error (%s): %s", pairs["coinbase"], e)
        return None

    def fetch_realtime_crypto_quote(self) -> LiveQuote:
        """
        Fetches real-time live spot quote across WebSocket -> Binance -> Kraken -> Coinbase.
        When every live source fails, returns an honest offline sentinel.
        """
        now = time.time()
        if (
            self.ws_feed.connected
            and (now - self.ws_feed.last_msg_ts) < 3.0
            and self.latest_quote is not None
            and not self.latest_quote.is_offline
        ):
            return self.latest_quote

        providers = ["binance", "kraken", "coinbase"]
        if self.preferred_quote_provider in providers:
            providers.remove(self.preferred_quote_provider)
            providers.insert(0, self.preferred_quote_provider)

        active_providers = [p for p in providers if self._quote_provider_cooldown.get(p, 0.0) <= now]
        if not active_providers:
            return self._offline_quote()

        fetchers = {
            "binance": self._fetch_binance_quote,
            "kraken": self._fetch_kraken_quote,
            "coinbase": self._fetch_coinbase_quote,
        }

        for name in active_providers:
            fetcher = fetchers.get(name)
            if not fetcher:
                continue
            quote = fetcher()
            if quote is not None:
                self.preferred_quote_provider = name
                self._quote_provider_cooldown.pop(name, None)
                return quote
            self._quote_provider_cooldown[name] = now + 15.0

        return self._offline_quote()

    @staticmethod
    def _offline_quote() -> LiveQuote:
        """Honest no-feed sentinel: price 0.00, flagged offline, never tradable."""
        return LiveQuote(
            price=Decimal("0.00"),
            bid=Decimal("0.00"),
            ask=Decimal("0.00"),
            high_24h=Decimal("0.00"),
            low_24h=Decimal("0.00"),
            volume_24h=Decimal("0.00"),
            change_24h_pct=Decimal("0.00"),
            source="Market Offline (No Feed)",
            timestamp=time.time(),
            is_offline=True,
        )

    def _is_quote_fresh(self, quote: Optional[LiveQuote], now: Optional[float] = None) -> bool:
        """True only while fresh and online."""
        if quote is None or quote.is_offline or quote.price <= Decimal("0.00"):
            return False
        current = time.time() if now is None else now
        return (current - float(quote.timestamp)) <= QUOTE_STALE_SEC

    fetch_realtime_eth_quote = fetch_realtime_crypto_quote
