"""Audit 2.5: the 1h MTF seed fetch must not block bootstrap.

Bootstrap starts it in a daemon thread after the engine is up; the
fetch happens without the engine lock and only the apply takes it.
The MTF gate degrades to NEUTRAL until the seed lands.
"""
from __future__ import annotations

import time
from decimal import Decimal

from src.data.eth_feed import CandleBar
from src.data.live_engine import LiveArenaEngine
from src.data.mtf_engine import MultiTimeframeEngine


def _fixture_bars(n=120):
    now = time.time()
    price = 3500.0
    bars = []
    for i in range(n):
        bars.append(CandleBar(
            timestamp=now - (n - i) * 60.0,
            open_=Decimal(f"{price:.2f}"),
            high=Decimal(f"{price + 5:.2f}"),
            low=Decimal(f"{price - 5:.2f}"),
            close=Decimal(f"{price:.2f}"),
            volume=Decimal("15.00"),
            ema_fast=Decimal(f"{price:.2f}"),
            ema_slow=Decimal(f"{price:.2f}"),
            rsi=Decimal("50.00"),
        ))
        price += 1.0
    return bars


class _FakeThread:
    """Records (target, daemon); start() is a no-op so no real thread --
    and no real network fetch -- ever runs in the test."""

    seen = []

    def __init__(self, *args, **kwargs):
        self.target = kwargs.get("target")
        self.daemon = kwargs.get("daemon")
        _FakeThread.seen.append(self)

    def start(self):
        pass

    def join(self, *args, **kwargs):
        pass

    def is_alive(self):
        return False


def test_bootstrap_spawns_mtf_seed_thread_instead_of_blocking(monkeypatch):
    monkeypatch.setattr(
        "src.data.live_engine.ETHFeed.fetch_historical_bars",
        staticmethod(lambda *a, **k: _fixture_bars()),
    )
    monkeypatch.delenv("ARENA_FAST_TEST")
    _FakeThread.seen.clear()
    monkeypatch.setattr("src.data.live_engine.threading.Thread", _FakeThread)
    engine = LiveArenaEngine(initial_cash=Decimal("500000.00"), symbol="ETH/USD")
    engine.bootstrap_intraday_session()
    assert engine.is_bootstrapped is True
    # The seed never ran synchronously: the gate is still NEUTRAL and
    # only the warmup's own 1m bars built 1h buckets -- a couple at
    # most, far below the 50 the gate needs (the thread is fake, so it
    # never ran).
    assert engine.htf_bias == "NEUTRAL"
    assert len(engine.candles_1h) < MultiTimeframeEngine.MIN_HTF_BARS
    seeds = [
        t for t in _FakeThread.seen
        if getattr(t.target, "__func__", None) is LiveArenaEngine._seed_mtf_1h_history
        and getattr(t.target, "__self__", None) is engine
    ]
    assert len(seeds) == 1
    assert seeds[0].daemon is True
    # Sanity: the digest thread was captured too, so the fake works.
    assert any(
        getattr(t.target, "__func__", None) is LiveArenaEngine.refresh_intel_digest
        for t in _FakeThread.seen
    )
