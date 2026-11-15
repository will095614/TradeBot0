"""Audit 3.5: periodic autosave (every 60 s + after every evolution).

Before the fix save_session_state() ran only on manual save, shutdown and
window close, so a crash lost the whole session. After the fix the live
loop calls _maybe_autosave() once per iteration and evolve_now() marks an
autosave pending, so the snapshot is at most 60 s stale (and never older
than the last evolution). The autosave IS save_session_state(), so the
snapshot lands in the same SQLite row in the same format as the manual
save and restore works unchanged.

All storage here is a tmp_path ArenaStorage -- never the real %APPDATA% /
project database.
"""
import os
import time
from decimal import Decimal

import pytest

from src.data.eth_feed import CandleBar
from src.data.live_engine import LiveArenaEngine
from src.data.persistence import ArenaStorage


def _bars():
    """120 deterministic 1m bars (same shape as the 3.4 fixture)."""
    now = time.time()
    return [
        CandleBar(
            timestamp=now - (120 - i) * 60.0,
            open_=Decimal("3500.00"),
            high=Decimal("3520.00"),
            low=Decimal("3480.00"),
            close=Decimal("3500.00"),
            volume=Decimal("15.00"),
            ema_fast=Decimal("3500.00"),
            ema_slow=Decimal("3500.00"),
            rsi=Decimal("50.00"),
            atr=Decimal("12.00"),
        )
        for i in range(120)
    ]


def _engine(tmp_path, monkeypatch, bootstrap=True):
    storage = ArenaStorage(db_path=str(tmp_path / "arena_history.db"))
    eng = LiveArenaEngine(storage=storage,
                          initial_cash=Decimal("500000.00"), symbol="ETH/USD")
    monkeypatch.setattr(
        "src.data.live_engine.ETHFeed.fetch_historical_bars",
        staticmethod(lambda *a, **k: _bars()),
    )
    if bootstrap:
        eng.bootstrap_intraday_session()
    eng.live_orders_enabled = True
    return eng


def test_periodic_autosave_writes_snapshot_when_interval_elapses(tmp_path, monkeypatch):
    """_maybe_autosave: silent before the interval, writes at/after it, then quiet again."""
    eng = _engine(tmp_path, monkeypatch)
    try:
        eng.autosave_interval_sec = 60.0
        eng._last_autosave_ts = 1000.0
        assert eng.storage.load_session_snapshot() is None

        assert eng._maybe_autosave(now=1000.0 + 30.0) is False
        assert eng.storage.load_session_snapshot() is None

        assert eng._maybe_autosave(now=1000.0 + 60.0) is True
        snap = eng.storage.load_session_snapshot()
        assert snap is not None
        assert snap["schema_version"] == 2
        assert snap["generation"] == 1
        assert len(snap["competitors"]) == 5

        # Just saved: not due again 10 s later.
        assert eng._maybe_autosave(now=1000.0 + 70.0) is False
        # Due again a full interval after the save.
        assert eng._maybe_autosave(now=1000.0 + 120.0) is True
    finally:
        eng.stop()


def test_evolution_marks_autosave_pending_and_it_fires_immediately(tmp_path, monkeypatch):
    """evolve_now() marks an autosave pending; the next check saves at once,
    even though the periodic interval has not elapsed."""
    eng = _engine(tmp_path, monkeypatch)
    try:
        eng.autosave_interval_sec = 60.0
        eng._last_autosave_ts = time.time()
        assert eng._autosave_pending is False

        logs = eng.evolve_now(trigger="manual:test")
        assert logs  # evolution actually ran
        assert eng._autosave_pending is True
        assert max(c.genome.generation for c in eng.competitors) == 2

        assert eng._maybe_autosave(now=time.time()) is True
        assert eng._autosave_pending is False
        snap = eng.storage.load_session_snapshot()
        assert snap is not None
        assert snap["generation"] == 2
    finally:
        eng.stop()


def test_crash_like_stop_leaves_restorable_autosave(tmp_path, monkeypatch):
    """Crash simulation: evolve (gen 2), autosave, then drop the engine
    WITHOUT any graceful shutdown/manual save. A fresh engine on the same
    storage file restores the autosaved generation."""
    eng = _engine(tmp_path, monkeypatch)
    eng.evolve_now(trigger="manual:test")
    assert eng._maybe_autosave(now=time.time()) is True
    # No stop(), no save_session_state(), no shutdown -- the process dies here.
    del eng

    eng2 = LiveArenaEngine(
        storage=ArenaStorage(db_path=str(tmp_path / "arena_history.db")),
        initial_cash=Decimal("500000.00"), symbol="ETH/USD")
    try:
        assert eng2.restore_session_state() is True
        assert max(c.genome.generation for c in eng2.competitors) == 2
    finally:
        eng2.stop()


def test_autosave_does_not_fire_when_stopped_or_superseded(tmp_path, monkeypatch):
    """A stopped engine and a superseded-generation engine never autosave."""
    eng = _engine(tmp_path, monkeypatch)
    eng.autosave_interval_sec = 60.0
    eng._last_autosave_ts = 0.0  # long overdue -- would fire if allowed
    eng.stop()
    assert eng._maybe_autosave(now=time.time()) is False
    assert eng.storage.load_session_snapshot() is None

    eng1 = _engine(tmp_path, monkeypatch)
    eng1.autosave_interval_sec = 60.0
    eng1._last_autosave_ts = 0.0
    try:
        # A newer engine supersedes eng1's generation.
        eng2 = LiveArenaEngine(
            storage=ArenaStorage(db_path=str(tmp_path / "arena_history.db")),
            initial_cash=Decimal("500000.00"), symbol="ETH/USD")
        try:
            assert eng1._maybe_autosave(now=time.time()) is False
            assert eng1.storage.load_session_snapshot() is None
        finally:
            eng2.stop()
    finally:
        eng1.stop()


def _raise_no_network(*a, **k):
    raise ConnectionError("hermetic test: no real network (mocked session.get)")


def test_live_loop_triggers_periodic_autosave(tmp_path, monkeypatch):
    """Integration: the real live loop fires the autosave on its own with a
    short interval (no manual _maybe_autosave call). Hermetic: ARENA_FAST_TEST
    (conftest) keeps the ws feed inert and session.get raises."""
    os.environ["ARENA_FAST_TEST"] = "1"
    # No bootstrap here: the loop itself bootstraps once (mocked bars).
    eng = _engine(tmp_path, monkeypatch, bootstrap=False)
    monkeypatch.setattr(eng.session, "get", _raise_no_network)
    eng.autosave_interval_sec = 0.2
    try:
        eng.start_live_loop(interval_sec=1.0)
        deadline = time.time() + 10.0
        snap = None
        while time.time() < deadline:
            snap = eng.storage.load_session_snapshot()
            if snap is not None:
                break
            time.sleep(0.1)
        assert snap is not None, "live loop never autosaved within 10 s"
        assert snap["schema_version"] == 2
        assert len(snap["competitors"]) == 5
    finally:
        eng.stop()
