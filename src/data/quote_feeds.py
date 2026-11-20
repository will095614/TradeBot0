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

    @staticmethod
    def _validated_quote(
        price_raw: Any,
        bid_raw: Any,
        ask_raw: Any,
        high_raw: Any,
        low_raw: Any,
        vol_raw: Any,
        chg_raw: Any,
        source: str,
    ) -> Optional[LiveQuote]:
        """Validates exchange quote fields so non-positive/NaN prices never reach BrokerSim."""
        quant = Decimal("0.01")
        zero = Decimal("0")
        try:
            price = Decimal(str(price_raw)).quantize(quant)
        except Exception:
            return None
        if not price.is_finite() or price <= zero:
            return None

        def _opt_pos(raw: Any, fallback: Decimal) -> Decimal:
            if raw is None:
                return fallback
            try:
                v = Decimal(str(raw)).quantize(quant)
                return v if (v.is_finite() and v > zero) else fallback
            except Exception:
                return fallback

        def _opt_fin(raw: Any, fallback: Decimal) -> Decimal:
            if raw is None:
                return fallback
            try:
                v = Decimal(str(raw)).quantize(quant)
                return v if v.is_finite() else fallback
            except Exception:
                return fallback

        bid = _opt_pos(bid_raw, price)
        ask = _opt_pos(ask_raw, price)
        if bid > ask:
            bid = price
            ask = price
        high_24h = _opt_pos(high_raw, price)
        low_24h = _opt_pos(low_raw, price)
        volume_24h = max(Decimal("0.00"), _opt_fin(vol_raw, Decimal("0.00")))
        change_24h_pct = _opt_fin(chg_raw, Decimal("0.00"))
        return LiveQuote(
            price=price,
            bid=bid,
            ask=ask,
            high_24h=high_24h,
            low_24h=low_24h,
            volume_24h=volume_24h,
            change_24h_pct=change_24h_pct,
            source=source,
            timestamp=time.time(),
            is_offline=False,
        )

    def _fetch_binance_quote(self) -> Optional[LiveQuote]:
        pairs = self._quote_pairs()
        r_bin = None
        try:
            r_bin = self.session.get(
                f"https://api.binance.com/api/v3/ticker/24hr?symbol={pairs['binance']}",
                timeout=1.2,
            )
            if r_bin.status_code == 200:
                b = r_bin.json()
                return self._validated_quote(
                    price_raw=b["lastPrice"],
                    bid_raw=b.get("bidPrice"),
                    ask_raw=b.get("askPrice"),
                    high_raw=b.get("highPrice"),
                    low_raw=b.get("lowPrice"),
                    vol_raw=b.get("volume"),
                    chg_raw=b.get("priceChangePercent"),
                    source="Binance Live",
                )
        except Exception as e:
            logger.debug("Binance quote feed error (%s): %s", pairs["binance"], e)
        finally:
            if r_bin is not None and hasattr(r_bin, "close"):
                try:
                    r_bin.close()
                except Exception:
                    pass
        return None

    def _fetch_kraken_quote(self) -> Optional[LiveQuote]:
        pairs = self._quote_pairs()
        r_krk = None
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
                    price = Decimal(str(k["c"][0]))
                    open_p = Decimal(str(k["o"]))
                    chg = (
                        ((price - open_p) / open_p) * Decimal("100")
                        if (price.is_finite() and open_p.is_finite() and open_p > 0)
                        else Decimal("0.00")
                    )
                    return self._validated_quote(
                        price_raw=k["c"][0],
                        bid_raw=k["b"][0],
                        ask_raw=k["a"][0],
                        high_raw=k["h"][1],
                        low_raw=k["l"][1],
                        vol_raw=k["v"][1],
                        chg_raw=chg,
                        source="Kraken Live",
                    )
        except Exception as e:
            logger.debug("Kraken quote feed error (%s): %s", pairs["kraken"], e)
        finally:
            if r_krk is not None and hasattr(r_krk, "close"):
                try:
                    r_krk.close()
                except Exception:
                    pass
        return None

    def _fetch_coinbase_quote(self) -> Optional[LiveQuote]:
        pairs = self._quote_pairs()
        r_tick = None
        r_stats = None
        try:
            r_tick = self.session.get(
                f"https://api.exchange.coinbase.com/products/{pairs['coinbase']}/ticker",
                timeout=1.2,
            )
            if r_tick.status_code == 200:
                t_data = r_tick.json()
                price = Decimal(str(t_data["price"]))
                if not price.is_finite() or price <= Decimal("0"):
                    return None
                high_24: Any = price
                low_24: Any = price
                chg_pct: Any = Decimal("0.00")
                try:
                    r_stats = self.session.get(
                        f"https://api.exchange.coinbase.com/products/{pairs['coinbase']}/stats",
                        timeout=1.2,
                    )
                    if r_stats.status_code == 200:
                        s_data = r_stats.json()
                        open_24 = Decimal(str(s_data.get("open", price)))
                        high_24 = s_data.get("high", price)
                        low_24 = s_data.get("low", price)
                        if open_24.is_finite() and open_24 > Decimal("0"):
                            chg_pct = ((price - open_24) / open_24) * Decimal("100")
                except Exception as stats_err:
                    logger.debug("Coinbase stats optional fetch skipped (%s): %s", pairs["coinbase"], stats_err)
                return self._validated_quote(
                    price_raw=t_data["price"],
                    bid_raw=t_data.get("bid"),
                    ask_raw=t_data.get("ask"),
                    high_raw=high_24,
                    low_raw=low_24,
                    vol_raw=t_data.get("volume", "0"),
                    chg_raw=chg_pct,
                    source="Coinbase Live",
                )
        except Exception as e:
            logger.debug("Coinbase quote feed error (%s): %s", pairs["coinbase"], e)
        finally:
            for r in (r_tick, r_stats):
                if r is not None and hasattr(r, "close"):
                    try:
                        r.close()
                    except Exception:
                        pass
        return None

    def fetch_realtime_crypto_quote(self) -> LiveQuote:
        """
        Fetches real-time live spot quote across WebSocket -> Binance -> Kraken -> Coinbase.
        When every live source fails, returns an honest offline sentinel.
        """
        now = time.time()
        if self.ws_feed.connected and (now - self.ws_feed.last_msg_ts) < 3.0:
            ws_q = getattr(self.ws_feed, "latest_ws_quote", None)
            if ws_q is not None and not ws_q.is_offline and ws_q.price > Decimal("0"):
                return ws_q
            if self.latest_quote is not None and not self.latest_quote.is_offline and self.latest_quote.price > Decimal("0"):
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
