"""External-feed mock tests: Binance WebSocket stream (ws_feed).

All sockets are mocked; no real network is opened. The reconnect backoff
is observed through a fake asyncio.sleep, so no real waiting happens.
"""
import asyncio
import json
import time
from decimal import Decimal
from unittest.mock import patch

from src.data.ws_feed import StreamingCryptoFeed


def _ticker_msg(price="3010.50", bid="3010.00", ask="3011.00",
                high="3100.00", low="2950.00", vol="1234.56", chg="1.25"):
    return json.dumps({"c": price, "b": bid, "a": ask, "h": high,
                       "l": low, "v": vol, "P": chg})


class FakeWS:
    """Minimal stand-in for a websockets connection."""

    def __init__(self, messages):
        self.messages = list(messages)
        self.closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def __aiter__(self):
        return self._gen()

    async def _gen(self):
        for m in self.messages:
            yield m

    async def close(self):
        self.closed = True


class SlowFakeWS(FakeWS):
    """Yields one message per real 0.05s so stop() can interrupt mid-stream."""

    async def _gen(self):
        for m in self.messages:
            await asyncio.sleep(0.05)
            yield m


def _run_feed(feed, timeout=15):
    async def _main():
        await asyncio.wait_for(feed._connect_and_stream(), timeout=timeout)
    asyncio.run(_main())


def test_ws_connect_and_stream_delivers_quotes(monkeypatch):
    """3 good tickers + 1 corrupt message: 3 quotes land, corrupt is
    swallowed by the reconnect path, and the stream continues after the
    reconnect (a 4th quote arrives from the new connection)."""
    monkeypatch.delenv("ARENA_FAST_TEST", raising=False)
    quotes = []
    fresh_during_stream = []
    feed = StreamingCryptoFeed(on_quote_callback=quotes.append)
    feed.running = True

    def _on_quote(q):
        quotes.append(q)
        # Still connected here (last_msg_ts just stamped): fresh must hold.
        fresh_during_stream.append(feed.is_fresh())
        if len(quotes) >= 4:
            feed.running = False

    feed.on_quote = _on_quote
    first = FakeWS([_ticker_msg("3010.50"), _ticker_msg("3020.00"),
                    _ticker_msg("3030.25"), "not-json{{{"])
    second = FakeWS([_ticker_msg("3040.75")])
    connect_calls = []

    def _fake_connect(url, **kwargs):
        # Sync: the mock returns the FakeWS itself (an async context
        # manager), which `async with websockets.connect(...)` enters.
        connect_calls.append(url)
        if len(connect_calls) == 1:
            return first
        return second

    with patch("src.data.ws_feed.websockets.connect", side_effect=_fake_connect):
        _run_feed(feed)

    assert [str(q.price) for q in quotes] == ["3010.50", "3020.00", "3030.25", "3040.75"]
    for q in quotes:
        assert q.source == "Binance WS (Sub-10ms)"
        assert q.is_offline is False
        assert q.bid == Decimal("3010.00") and q.ask == Decimal("3011.00")
        assert q.high_24h == Decimal("3100.00") and q.low_24h == Decimal("2950.00")
        assert q.volume_24h == Decimal("1234.56") and q.change_24h_pct == Decimal("1.25")
    # Corrupt message raised inside the stream loop -> one reconnect, then
    # the second connection delivered the 4th quote. No exception escaped.
    assert feed.reconnect_count == 1
    assert connect_calls == [StreamingCryptoFeed.BINANCE_WS_URL,
                             StreamingCryptoFeed.BINANCE_ALT_WS_URL]
    assert feed.latest_ws_quote is quotes[-1]
    assert feed.last_msg_ts > 0
    assert fresh_during_stream == [True] * 4
    # NOTE: after _connect_and_stream returns, connected is False by design,
    # so is_fresh() is False once the coroutine has exited.


def test_ws_reconnect_backoff_on_disconnect(monkeypatch):
    """9 consecutive connect failures then success: backoff sleeps grow
    1.0 -> 1.5 -> 2.25 -> ... and cap at 15s (observed via fake sleep)."""
    monkeypatch.delenv("ARENA_FAST_TEST", raising=False)
    quotes = []
    feed = StreamingCryptoFeed(on_quote_callback=quotes.append)
    feed.running = True

    def _on_quote(q):
        quotes.append(q)
        feed.running = False

    feed.on_quote = _on_quote
    connect_calls = []

    def _fake_connect(url, **kwargs):
        connect_calls.append(url)
        if len(connect_calls) <= 9:
            raise ConnectionError("boom")
        return FakeWS([_ticker_msg("3050.00")])

    # Record (delay, connects-so-far) for every sleep: groups sleeps by the
    # failure cycle they belong to, so the backoff value per cycle is visible.
    sleep_log = []

    async def _fake_sleep(delay):
        sleep_log.append((delay, len(connect_calls)))

    with (
        patch("src.data.ws_feed.websockets.connect", side_effect=_fake_connect),
        patch("asyncio.sleep", side_effect=_fake_sleep),
    ):
        _run_feed(feed)

    assert len(connect_calls) == 10
    assert feed.reconnect_count == 9
    assert len(quotes) == 1 and str(quotes[0].price) == "3050.00"
    # URLs alternate primary/alt on every failed attempt.
    assert connect_calls[0] == StreamingCryptoFeed.BINANCE_WS_URL
    assert connect_calls[1] == StreamingCryptoFeed.BINANCE_ALT_WS_URL
    assert connect_calls[2] == StreamingCryptoFeed.BINANCE_WS_URL
    # Backoff per cycle = int(backoff * 10) sleeps of 0.1s:
    # 1.0, 1.5, 2.25, 3.375, 5.0625, 7.59375, 11.3906, 15.0 (cap), 15.0 (cap).
    per_cycle = {}
    for delay, n_connects in sleep_log:
        assert delay == 0.1
        per_cycle.setdefault(n_connects, 0)
        per_cycle[n_connects] += 1
    assert per_cycle == {1: 10, 2: 15, 3: 22, 4: 33, 5: 50, 6: 75, 7: 113, 8: 150, 9: 150}


def test_ws_clean_server_close_counts_as_reconnect(monkeypatch):
    """Audit 3.15: a clean server-initiated close followed by a reconnect
    increments reconnect_count, just like a failed connect does."""
    monkeypatch.delenv("ARENA_FAST_TEST", raising=False)
    quotes = []
    feed = StreamingCryptoFeed(on_quote_callback=quotes.append)
    feed.running = True

    def _on_quote(q):
        quotes.append(q)
        if len(quotes) >= 2:
            feed.running = False

    feed.on_quote = _on_quote
    first = FakeWS([_ticker_msg("3010.50")])
    second = FakeWS([_ticker_msg("3020.00")])
    connect_calls = []

    def _fake_connect(url, **kwargs):
        connect_calls.append(url)
        return first if len(connect_calls) == 1 else second

    async def _fake_sleep(delay):
        return None

    with (
        patch("src.data.ws_feed.websockets.connect", side_effect=_fake_connect),
        patch("asyncio.sleep", side_effect=_fake_sleep),
    ):
        _run_feed(feed)

    assert [str(q.price) for q in quotes] == ["3010.50", "3020.00"]
    assert len(connect_calls) == 2
    assert feed.reconnect_count == 1


def test_ws_start_stop_delivers_then_stops(monkeypatch):
    """start() spawns the streaming thread; stop() ends delivery: no quote
    arrives after stop() returns."""
    monkeypatch.delenv("ARENA_FAST_TEST", raising=False)
    quotes = []
    feed = StreamingCryptoFeed(on_quote_callback=quotes.append)
    slow = SlowFakeWS([_ticker_msg(f"{3000 + i}.00") for i in range(20)])

    def _fake_connect(url, **kwargs):
        return slow

    with patch("src.data.ws_feed.websockets.connect", side_effect=_fake_connect):
        feed.start()
        assert feed.running is True
        deadline = time.time() + 5.0
        while len(quotes) < 2 and time.time() < deadline:
            time.sleep(0.05)
        assert len(quotes) >= 2, "feed did not deliver before stop()"
        feed.stop()
        assert feed.running is False
        assert feed.connected is False
        assert feed._thread is None
        # Count only after stop() has joined the thread: anything arriving
        # before stop() is legitimate, anything after is a leak.
        count_after_stop = len(quotes)
        time.sleep(0.5)
    assert len(quotes) == count_after_stop, "quotes kept arriving after stop()"


def test_parse_binance_ticker_rejects_garbage():
    feed = StreamingCryptoFeed(on_quote_callback=lambda q: None)
    assert feed._parse_binance_ticker({}) is None  # no "c"
    assert feed._parse_binance_ticker({"c": "0"}) is None  # non-positive price
    assert feed._parse_binance_ticker({"c": "-5"}) is None
    assert feed._parse_binance_ticker({"c": "not-a-number"}) is None
    assert feed._parse_binance_ticker({"c": "3010.5", "b": "0", "a": "-1"}) is not None
    q = feed._parse_binance_ticker({"c": "3010.5", "b": "0", "a": "-1"})
    assert q.bid == q.price and q.ask == q.price  # zero/negative bid/ask fall back to price
