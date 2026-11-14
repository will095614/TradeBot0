"""Audit 3.1 regression tests: snapshot publishing must hold the engine lock.

_publish_state_snapshot used to call _build_snapshot_locked (which harvests
fills: advances _audit_cursor, extends fill_records, counts closed trades)
without holding self.lock. Two callers run off-lock -- refresh_intel_digest's
finally on a daemon thread and the paused/config setters after releasing the
lock -- so the digest thread and the live loop could both enter _harvest_fills
with the same cursor and double-count fills / trigger evolution early.
"""
import threading
import time
from decimal import Decimal

from src.data.live_engine import LiveArenaEngine, LiveQuote


def _quote(price: str) -> LiveQuote:
    p = Decimal(price)
    return LiveQuote(
        price=p, bid=p - Decimal("0.05"), ask=p + Decimal("0.05"),
        high_24h=p + Decimal("40"), low_24h=p - Decimal("40"),
        volume_24h=Decimal("1000"), change_24h_pct=Decimal("1.25"),
        source="UnitTest", timestamp=time.time(),
    )


def _drive(engine: LiveArenaEngine, prices: list) -> None:
    """Feeds synthetic ticks through the same path as the live loop (no network)."""
    prev = None
    for px in prices:
        q = _quote(px)
        engine.latest_quote = q
        engine.tick_count += 1
        engine.live_ema_fast = q.price
        engine.live_ema_slow = q.price - Decimal("1")
        engine.broker.on_tick(q.price, high=q.ask, low=q.bid, timestamp=q.timestamp, open_price=prev or q.price)
        if prev is None:
            engine._ensure_active_live_positions(q.price, q.timestamp)
        engine._evaluate_live_strategies(q.price, prev or q.price, q.timestamp)
        engine._record_series_point(q.price, q.timestamp)
        prev = q.price


def _make_engine() -> LiveArenaEngine:
    return LiveArenaEngine(initial_cash=Decimal("500000.00"), symbol="ETH/USD")


def test_publish_state_snapshot_holds_engine_lock():
    """Two concurrent publishers must never be inside the snapshot build at once."""
    engine = _make_engine()
    _drive(engine, ["3500.00", "3502.50", "3498.00", "3505.00"])

    real_build = engine._build_snapshot_locked
    state = {"in_build": 0, "max_in_build": 0}
    state_lock = threading.Lock()

    def slow_build():
        with state_lock:
            state["in_build"] += 1
            state["max_in_build"] = max(state["max_in_build"], state["in_build"])
        time.sleep(0.05)
        try:
            return real_build()
        finally:
            with state_lock:
                state["in_build"] -= 1

    engine._build_snapshot_locked = slow_build  # type: ignore[method-assign]
    barrier = threading.Barrier(2)

    def publish_many():
        barrier.wait(timeout=10)
        for _ in range(5):
            engine._publish_state_snapshot()

    t1 = threading.Thread(target=publish_many)
    t2 = threading.Thread(target=publish_many)
    t1.start()
    t2.start()
    t1.join(timeout=60)
    t2.join(timeout=60)
    assert not t1.is_alive() and not t2.is_alive()
    assert state["max_in_build"] == 1


def test_concurrent_publish_harvests_each_fill_once():
    """Concurrent publishes must not duplicate fills or double-count closed trades."""
    engine = _make_engine()
    _drive(engine, ["3500.00", "3502.50", "3498.00", "3505.00", "3490.00", "3515.00", "3485.00", "3520.00"])
    total_fills = len(engine.broker.execution_audit)
    assert total_fills > 0
    closing = sum(1 for f in engine.broker.execution_audit if getattr(f, "is_closing_fill", False))

    # Reset the harvest cursor over the seeded audit tape. This recreates the
    # exact race window (two threads entering _harvest_fills with the same
    # cursor) without waiting for live fills; re-harvest is safe for SQLite
    # because record_fill is INSERT OR REPLACE keyed by fill_seq.
    engine._audit_cursor = 0
    engine.fill_records.clear()
    engine._closed_trades_since_evolve = 0

    barrier = threading.Barrier(4)

    def publish_many():
        barrier.wait(timeout=10)
        for _ in range(10):
            engine._publish_state_snapshot()

    threads = [threading.Thread(target=publish_many) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert not any(t.is_alive() for t in threads)

    seqs = [f.fill_seq for f in engine.fill_records]
    assert len(seqs) == len(set(seqs)), "duplicate FillEvents harvested"
    assert len(engine.fill_records) == total_fills
    assert engine._closed_trades_since_evolve == closing
    assert engine._audit_cursor == total_fills
