"""Item 3 patch: remove offline mode; pause-and-wait on disconnect; blocking UI; fill_seq global.

Usage: python fix_item3_patch.py [project_root]
Verifies EVERY replacement anchor appears exactly once before writing anything.
Preserves each file's original newline style (CRLF stays CRLF).
"""
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
assert (ROOT / "src/data/live_engine.py").exists(), f"not a TradeBot0 root: {ROOT}"

# (rel_path, old, new) — old must occur exactly once.
REPLACEMENTS = []
# (rel_path, old, expected_count, new) — old must occur exactly expected_count times.
REPLACEMENTS_ALL = []


def rep(rel, old, new):
    REPLACEMENTS.append((rel, old, new))


def rep_all(rel, old, count, new):
    REPLACEMENTS_ALL.append((rel, old, count, new))


def _read(path):
    raw = path.read_bytes()
    crlf = b"\r\n" in raw
    text = raw.decode("utf-8")
    if crlf:
        text = text.replace("\r\n", "\n")
    return text, crlf


def _write(path, text, crlf):
    if crlf:
        text = text.replace("\n", "\r\n")
    path.write_bytes(text.encode("utf-8"))


# ---------------------------------------------------------------- live_engine.py
LE = "src/data/live_engine.py"

rep(LE,
    "logger = logging.getLogger(__name__)",
    "logger = logging.getLogger(__name__)\n\n"
    "# A quote older than this is stale and never tradable. On disconnect the\n"
    "# engine pauses and waits for a fresh quote instead of trading on a cached\n"
    "# price (offline mode removed, item 3).\n"
    "QUOTE_STALE_SEC = 5.0")

rep(LE,
    "        self._raw_quote_cache: Optional[LiveQuote] = None",
    "        # Last FRESH quote only. It is never served once stale: the live loop\n"
    "        # gates on _is_quote_fresh() and pauses when the feed goes down.\n"
    "        self._raw_quote_cache: Optional[LiveQuote] = None")

# --- fetch_realtime_crypto_quote: delete cache fallback + cooldown bypass ---
# (surgical replacements; the method text below is verbatim from the file)
rep(LE,
    '''        """
        Fetches real-time live ETH/USD spot quote with sub-second latency across
        WebSocket Push -> Binance -> Kraken -> Coinbase with adaptive provider ranking & circuit breaking.
        """''',
    '''        """
        Fetches real-time live ETH/USD spot quote with sub-second latency across
        WebSocket Push -> Binance -> Kraken -> Coinbase with adaptive provider ranking & circuit breaking.
        There is deliberately NO cached-price fallback: when every live source
        fails, the honest offline sentinel is returned and the engine pauses
        trading until a fresh quote arrives (offline mode removed, item 3).
        """''')

rep(LE,
    "        candidate_providers = active_providers if active_providers else providers",
    """        # Providers in cooldown are skipped. When ALL of them are cooling down
        # the backoff is respected, not bypassed: no fetch is attempted and the
        # offline sentinel is returned until a cooldown expires.
        if not active_providers:
            return self._offline_quote()""")

rep(LE,
    "        for name in candidate_providers:",
    "        for name in active_providers:")

rep(LE,
    '''        # In-Memory Resilient Cache Fallback (survives transient network disconnects)
        if self.latest_quote is not None and not self.latest_quote.is_offline and self.latest_quote.price > Decimal("0.00"):
            return LiveQuote(
                price=self.latest_quote.price,
                bid=self.latest_quote.bid,
                ask=self.latest_quote.ask,
                high_24h=self.latest_quote.high_24h,
                low_24h=self.latest_quote.low_24h,
                volume_24h=self.latest_quote.volume_24h,
                change_24h_pct=self.latest_quote.change_24h_pct,
                source=f"{self.latest_quote.source} (Cache)",
                timestamp=time.time(),
                is_offline=False
            )''',
    '''        # Every live source failed: report offline. The engine pauses trading
        # and waits for the next retry instead of trading on a stale price.''')

rep(LE,
    '''        # Cold-boot default baseline if completely offline on first start: marked offline to safely block mock fills
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
            is_offline=True
        )''',
    '''        return self._offline_quote()

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
            is_offline=True
        )''')

# --- _is_quote_fresh helper, inserted before the eth_quote alias ---
rep(LE,
    "    fetch_realtime_eth_quote = fetch_realtime_crypto_quote",
    '''    def _is_quote_fresh(self, quote: Optional[LiveQuote], now: Optional[float] = None) -> bool:
        """A quote is tradable only while fresh. A stale cached quote is never
        traded as if live: on disconnect the engine pauses until a fresh
        quote arrives (offline mode removed, item 3)."""
        if quote is None or quote.is_offline or quote.price <= Decimal("0.00"):
            return False
        current = time.time() if now is None else now
        return (current - float(quote.timestamp)) <= QUOTE_STALE_SEC

    fetch_realtime_eth_quote = fetch_realtime_crypto_quote''')

# --- delete _generate_fallback_bars entirely ---
rep(LE,
    '''    @staticmethod
    def _generate_fallback_bars(anchor_price: Decimal, count: int = 120) -> List[CandleBar]:
        """
        Synthesizes a continuous, realistic sequence of 1-minute historical candles
        anchored directly to the anchor_price if external web feeds are unreachable or slow.
        Ensures the tactical K-line viewport is densely populated with zero cold-boot blankness.
        """
        import random
        bars: List[CandleBar] = []
        now = time.time()
        start_ts = now - (count * 60)
        curr = float(anchor_price) * (1.0 - random.uniform(-0.003, 0.003))
        for i in range(count):
            ts = start_ts + (i * 60)
            drift = (float(anchor_price) - curr) / max(1, count - i)
            volatility = float(anchor_price) * 0.0006
            change = drift + random.gauss(0, volatility)
            open_p = curr
            close_p = open_p + change
            high_p = max(open_p, close_p) + abs(random.gauss(0, volatility * 0.45))
            low_p = min(open_p, close_p) - abs(random.gauss(0, volatility * 0.45))
            curr = close_p
            bars.append(CandleBar(
                timestamp=ts,
                open_=Decimal(f"{open_p:.2f}"),
                high=Decimal(f"{high_p:.2f}"),
                low=Decimal(f"{low_p:.2f}"),
                close=Decimal(f"{close_p:.2f}"),
                volume=Decimal(f"{random.uniform(2.5, 30.0):.2f}"),
                ema_fast=Decimal(f"{close_p:.2f}"),
                ema_slow=Decimal(f"{close_p:.2f}"),
                rsi=Decimal("50.00"),
                atr=Decimal("12.00")
            ))
        return bars

''',
    "")

# --- bootstrap docstring ---
rep(LE,
    """        First attempts cold-start hydration from SQLite WAL storage; if empty, queries live
        feed and falls back to synthetic realistic continuous bars anchored to spot price.""",
    """        First attempts cold-start hydration from SQLite WAL storage; if empty, queries live
        feed. If no real bars are available (offline), no bars are fabricated:
        the engine starts with an empty chart and waits for live quotes.""")

# --- bootstrap: prefer persisted SQLite cache (real data only) ---
rep(LE,
    "        # Fallback guarantee: prefer persisted SQLite cache over pure synthetic fallback",
    "        # Prefer persisted SQLite cache (real data only) when the live feed is unreachable.")

# --- bootstrap: no synthetic bars when nothing real is available ---
rep(LE,
    '''        if not recent_bars:
            anchor = self.latest_quote.price if (self.latest_quote and self.latest_quote.price > Decimal("0")) else Decimal("2650.00")
            recent_bars = self._generate_fallback_bars(anchor, count=120)''',
    '''        if not recent_bars:
            # No real bars available (offline): do NOT fabricate candles.
            # The engine starts with an empty chart and waits for live quotes;
            # indicators stay at defaults until the feed reconnects.
            logger.info("Bootstrap: no real intraday bars available; waiting for live feed.")''')

# --- remove both reset_seq(0) calls (bootstrap cleanup + start_live_trading) ---
rep_all(LE, "                    self.broker.reset_seq(0)\n", 2, "")

# --- _init_broker: seed fill seq from the SQLite ledger max ---
rep(LE,
    '''    def _init_broker(self) -> None:
        self.broker = BrokerSim(symbol=self.symbol, slippage_pct=Decimal("0.0001"))
        self._audit_cursor = 0''',
    '''    def _init_broker(self) -> None:
        self.broker = BrokerSim(symbol=self.symbol, slippage_pct=Decimal("0.0001"))
        self._audit_cursor = 0
        # Seed the fill sequence past the SQLite ledger's max so fill_seq never
        # reuses a number across restarts (INSERT OR REPLACE would overwrite
        # an earlier fill). Monotonic floor: reset_seq() never lowers it.
        try:
            recent = self.storage.load_recent_fills(limit=1)
            if recent:
                self.broker.reset_seq(int(recent[0].get("seq", 0)))
        except Exception as e:
            logger.debug("Fill-seq seeding skipped: %s", e)''')

# --- live loop: gate the cadence on quote freshness + FEED_ONLINE transition ---
rep(LE,
    '''                        if raw and not raw.is_offline and raw.price > Decimal("0.00"):
                            self.market_online = True''',
    '''                        if self._is_quote_fresh(raw, now):
                            if not self.market_online:
                                self.market_online = True
                                self.log_event("FEED_ONLINE", "Market feed reconnected: trading resumed.", "success")''')

# --- live loop: FEED_OFFLINE transition when the quote goes stale ---
rep(LE,
    '''                            self._record_series_point(cadenced_quote.price, float(current_slot))

                        if self.live_orders_enabled and self._auto_evolve_due():''',
    '''                            self._record_series_point(cadenced_quote.price, float(current_slot))
                        elif self.market_online:
                            self.market_online = False
                            self.log_event("FEED_OFFLINE", "Market feed offline: trading paused, waiting to reconnect...", "loss")

                        if self.live_orders_enabled and self._auto_evolve_due():''')

# ---------------------------------------------------------------- ws_feed.py
WF = "src/data/ws_feed.py"
rep(WF,
    '''                    async for message in ws:
                        if not self.running:
                            break
                        data = json.loads(message) if isinstance(message, (str, bytes)) else message
                        if isinstance(data, dict):
                            quote = self._parse_binance_ticker(data)
                            if quote is not None:
                                self.last_msg_ts = time.time()
                                self.latest_ws_quote = quote
                                self.on_quote(quote)
            except Exception as e:''',
    '''                    async for message in ws:
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
                logger.warning("WebSocket stream closed cleanly. Reconnecting in %.1fs...", backoff)
                for _ in range(int(backoff * 10)):
                    if not self.running:
                        break
                    await asyncio.sleep(0.1)
                backoff = min(15.0, backoff * 1.5)
            except Exception as e:''')

# ---------------------------------------------------------------- broker_sim.py
BS = "src/arena/broker_sim.py"
rep(BS,
    '''    def reset_seq(self, start: int = 0) -> None:
        """Resets the fill sequence counter, e.g. when transitioning from historical simulation to live orderflow."""
        self._seq_counter = int(start)''',
    '''    def reset_seq(self, start: int = 0) -> None:
        """Raises the fill-sequence floor, never lowers it.

        fill_seq is globally increasing: the ledger uses it as PRIMARY KEY
        with INSERT OR REPLACE, so reusing a number would silently overwrite
        an earlier fill. Warmup purges clear the in-memory audit but must
        never rewind the counter.
        """
        self._seq_counter = max(self._seq_counter, int(start))''')

# ---------------------------------------------------------------- frontend
IH = "src/gui/assets/index.html"
rep(IH,
    '''    </div>
  </div>

  <!-- ========================================================================
       TRADEBOT0 CORE APPLICATION SHELL''',
    '''    </div>
  </div>

  <!-- Network Offline Blocking Overlay: shown while the market feed is down.
       Trading is paused until a fresh quote arrives; clears automatically. -->
  <div id="networkOfflineOverlay" class="network-offline-overlay hidden">
    <div class="splash-container lg-glass lg-spot-card">
      <div class="splash-brand">
        <div class="splash-title">網路已斷線 <span class="splash-highlight">等待重新連線</span></div>
        <div class="splash-subtitle">交易已暫停 · 恢復連線後自動繼續</div>
      </div>
      <div class="splash-footer-note">
        <span class="live-dot" style="margin-right:7px;"></span>
        <span>請檢查網路連線 · 遮罩會在連線恢復時自動解除</span>
      </div>
    </div>
  </div>

  <!-- ========================================================================
       TRADEBOT0 CORE APPLICATION SHELL''')

AC = "src/gui/assets/app.css"
rep(AC,
    '''.splash-overlay.hidden {
  opacity: 0;
  visibility: hidden;
  pointer-events: none;
}''',
    '''.splash-overlay.hidden {
  opacity: 0;
  visibility: hidden;
  pointer-events: none;
}

/* Network Offline Blocking Overlay (reuses the splash overlay pattern) */
.network-offline-overlay {
  position: fixed;
  inset: 0;
  z-index: 10000;
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    radial-gradient(circle at 50% 40%, rgba(255, 255, 255, 0.03), transparent 70%),
    rgba(2, 6, 15, 0.50);
  backdrop-filter: blur(1px) saturate(115%);
  -webkit-backdrop-filter: blur(1px) saturate(115%);
  opacity: 1;
  visibility: visible;
  transition: opacity 0.4s ease, visibility 0.4s ease;
}

.network-offline-overlay.hidden {
  opacity: 0;
  visibility: hidden;
  pointer-events: none;
}''')

AJ = "src/gui/assets/app.js"
rep(AJ,
    "  const isOffline = Boolean(latestState && (latestState.market_online === false || (q && q.is_offline)));",
    '''  const isOffline = Boolean(latestState && (latestState.market_online === false || (q && q.is_offline)));

  // Network offline blocking overlay: shown only after the arena has
  // revealed, so it never flashes over the startup splash.
  const netOverlay = document.getElementById('networkOfflineOverlay');
  if (netOverlay) {
    const showNetOverlay = isOffline && document.body && document.body.classList.contains('arena-ready');
    netOverlay.classList.toggle('hidden', !showNetOverlay);
  }''')

rep(AJ,
    "    '* Offline Resilience: Active (Fills and orders safely freeze upon disconnect)\\n' +",
    "    '* Network Loss: Trading pauses and waits to reconnect (no stale quotes, no synthetic bars)\\n' +")

# ---------------------------------------------------------------- tests
TLE = "tests/test_live_engine.py"
rep(TLE,
    '''def test_resilient_quote_cache_fallback():
    engine = LiveArenaEngine(initial_cash=Decimal("3000.00"))
    # Seed latest_quote
    cached_q = _quote("3550.00")
    engine.latest_quote = cached_q
    # Test fetch_realtime_eth_quote fallback by simulating connection error
    import unittest.mock as mock
    with mock.patch.object(engine.session, "get", side_effect=Exception("Network Timeout")):
        q = engine.fetch_realtime_eth_quote()
        assert q.price == Decimal("3550.00")
        assert "Cache" in q.source''',
    '''def test_no_cached_price_when_feed_down():
    # Offline mode removed (item 3): when every live source fails, the fetch
    # must report offline instead of returning the last price as if live.
    engine = LiveArenaEngine(initial_cash=Decimal("3000.00"))
    # Seed latest_quote with a perfectly good price
    cached_q = _quote("3550.00")
    engine.latest_quote = cached_q
    import unittest.mock as mock
    with mock.patch.object(engine.session, "get", side_effect=Exception("Network Timeout")):
        q = engine.fetch_realtime_eth_quote()
        assert q.is_offline is True
        assert q.price == Decimal("0.00")
        assert q.source == "Market Offline (No Feed)"''')

TPO = "tests/test_performance_and_optimizations.py"
rep(TPO,
    '''    # Stale WS (> 3s) must fall back to REST cascade / cache, never return the stale WS object
    import unittest.mock as mock
    engine.ws_feed.last_msg_ts = time.time() - 10.0
    with mock.patch.object(engine.session, "get", side_effect=Exception("Network Timeout")):
        fb = engine.fetch_realtime_crypto_quote()
    assert "Cache" in fb.source''',
    '''    # Stale WS (> 3s) with all REST providers failing must report offline,
    # never return the stale WS quote or a cached price as if live.
    import unittest.mock as mock
    engine.ws_feed.last_msg_ts = time.time() - 10.0
    with mock.patch.object(engine.session, "get", side_effect=Exception("Network Timeout")):
        fb = engine.fetch_realtime_crypto_quote()
    assert fb.is_offline is True
    assert fb.price == Decimal("0.00")''')

# ---------------------------------------------------------------- new test file
NEW_TEST = '''"""Item 3: offline mode removed -- disconnect pauses trading, waits to reconnect.

- No cached price is ever served as live.
- Provider cooldowns are respected (no bypass when all are cooling down).
- fill_seq is globally increasing (reset_seq never rewinds).
- _generate_fallback_bars is gone.
"""
import time
import unittest.mock as mock
from decimal import Decimal
from typing import Optional

from src.arena.broker_sim import BrokerSim
from src.arena.order import OrderTicket, OrderSide, OrderType
from src.arena.portfolio import Portfolio
from src.data.live_engine import LiveArenaEngine, LiveQuote


def _quote(price: str, ts: Optional[float] = None, offline: bool = False) -> LiveQuote:
    p = Decimal(price)
    return LiveQuote(
        price=p, bid=p - Decimal("0.05"), ask=p + Decimal("0.05"),
        high_24h=p + Decimal("40"), low_24h=p - Decimal("40"),
        volume_24h=Decimal("1000"), change_24h_pct=Decimal("1.25"),
        source="UnitTest", timestamp=time.time() if ts is None else ts,
        is_offline=offline,
    )


def test_provider_cooldown_respected_when_all_cooling():
    engine = LiveArenaEngine(initial_cash=Decimal("3000.00"))
    engine.latest_quote = _quote("3550.00")
    with mock.patch.object(engine.session, "get", side_effect=Exception("Network Timeout")) as mocked_get:
        first = engine.fetch_realtime_crypto_quote()
        assert first.is_offline is True
        calls_after_first = mocked_get.call_count
        assert calls_after_first > 0  # all three providers were attempted once
        # Immediate retry: every provider is in its 15s cooldown, so no
        # further HTTP attempt may be made -- the backoff must not be bypassed.
        second = engine.fetch_realtime_crypto_quote()
        assert second.is_offline is True
        assert mocked_get.call_count == calls_after_first


def test_is_quote_fresh():
    engine = LiveArenaEngine(initial_cash=Decimal("3000.00"))
    now = time.time()
    assert engine._is_quote_fresh(_quote("3500.00", ts=now), now) is True
    assert engine._is_quote_fresh(_quote("3500.00", ts=now - 60.0), now) is False
    assert engine._is_quote_fresh(_quote("3500.00", ts=now, offline=True), now) is False
    assert engine._is_quote_fresh(_quote("0.00", ts=now), now) is False
    assert engine._is_quote_fresh(None, now) is False


def test_fill_seq_never_rewinds():
    broker = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0.0"))
    p = Portfolio("p1", "Test", initial_cash=Decimal("3000.00"))
    broker.register_portfolio(p, max_position_ratio=Decimal("0.8"))
    broker.on_tick(price=Decimal("2500.00"), timestamp=100.0)
    fill1 = broker.submit_order(OrderTicket("p1", "ETH/USD", OrderSide.BUY, OrderType.MARKET, qty=Decimal("0.1"), timestamp=100.0))
    assert fill1 is not None and fill1.fill_seq == 1
    # Warmup-purge behaviour used to call reset_seq(0): the counter must not rewind.
    broker.reset_seq(0)
    fill2 = broker.submit_order(OrderTicket("p1", "ETH/USD", OrderSide.BUY, OrderType.MARKET, qty=Decimal("0.1"), timestamp=101.0))
    assert fill2 is not None and fill2.fill_seq == 2
    # Restoring from a higher ledger max raises the floor.
    broker.reset_seq(10)
    fill3 = broker.submit_order(OrderTicket("p1", "ETH/USD", OrderSide.BUY, OrderType.MARKET, qty=Decimal("0.1"), timestamp=102.0))
    assert fill3 is not None and fill3.fill_seq == 11


def test_generate_fallback_bars_deleted():
    assert not hasattr(LiveArenaEngine, "_generate_fallback_bars")
'''

# ---------------------------------------------------------------- verify + apply
def main():
    # Load every touched file once.
    files = {}
    for rel, _old, _new in REPLACEMENTS:
        files.setdefault(rel, _read(ROOT / rel))
    for rel, _old, _count, _new in REPLACEMENTS_ALL:
        files.setdefault(rel, _read(ROOT / rel))

    # Verify ALL anchors before writing anything.
    for rel, old, _new in REPLACEMENTS:
        text, _crlf = files[rel]
        n = text.count(old)
        assert n == 1, f"{rel}: expected exactly 1 occurrence, found {n}: {old[:100]!r}"
    for rel, old, count, _new in REPLACEMENTS_ALL:
        text, _crlf = files[rel]
        n = text.count(old)
        assert n == count, f"{rel}: expected {count} occurrences, found {n}: {old[:100]!r}"
    print(f"All {len(REPLACEMENTS)} single + {len(REPLACEMENTS_ALL)} multi anchors verified.")

    # Apply.
    new_texts = {rel: text for rel, (text, _c) in files.items()}
    for rel, old, new in REPLACEMENTS:
        new_texts[rel] = new_texts[rel].replace(old, new, 1)
    for rel, old, _count, new in REPLACEMENTS_ALL:
        new_texts[rel] = new_texts[rel].replace(old, new)
    for rel, text in new_texts.items():
        _write(ROOT / rel, text, files[rel][1])
        print(f"patched {rel}")

    # New test file.
    target = ROOT / "tests/test_offline_removal.py"
    assert not target.exists(), f"{target} already exists; refusing to overwrite"
    target.write_text(NEW_TEST, encoding="utf-8")
    print("created tests/test_offline_removal.py")
    print("ITEM3 PATCH OK")


if __name__ == "__main__":
    main()
