"""Phase 2 optimize regression tests (2026-11-13).

P2-1 ArenaStorage persistent connection: candles still persist across
close/reopen, the same connection object is reused, concurrent writers
stay correct, and a stale handle recovers via retry-once.
P2-2 eth_feed lazy pandas/numpy: importing eth_feed must not import
pandas/numpy; the first fetch still works and loads them.
P2-3 fetch_from_registry parallel: same events in registry order as
the sequential version, dedup + failure tolerance preserved, and the
wall time collapses (mocked 0.3 s/source must finish well under the
~4.8 s sequential floor).
"""
import os
import subprocess
import sys
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from src.data.persistence import ArenaStorage


def _candle(t, c=3500.0):
    return {"t": float(t), "o": 3500.0, "h": 3505.0, "l": 3495.0, "c": float(c), "v": 15.0}


def test_p2_persistent_connection_reused_and_candle_persists_across_close(tmp_path):
    db = str(tmp_path / "p2.db")
    store = ArenaStorage(db_path=db)
    assert store._get_connection() is store._get_connection()
    store.save_candle(_candle(1700000000, 3502.0))
    store.save_candle(_candle(1700000060, 3503.0))
    # Same-instance close + lazy reopen still serves the rows.
    store.close()
    assert store._conn is None
    store.save_candle(_candle(1700000120, 3504.0))
    loaded = store.load_latest_candles(limit=10)
    assert [c["c"] for c in loaded] == [3502.0, 3503.0, 3504.0]
    # A brand-new storage on the same file (restart) sees the same rows.
    store2 = ArenaStorage(db_path=db)
    loaded2 = store2.load_latest_candles(limit=10)
    assert [c["c"] for c in loaded2] == [3502.0, 3503.0, 3504.0]
    assert loaded2[0]["t"] == 1700000000.0
    store.close()
    store2.close()


def test_p2_persistent_connection_recovers_from_stale_handle(tmp_path):
    db = str(tmp_path / "p2b.db")
    store = ArenaStorage(db_path=db)
    store.save_candle(_candle(1700000000, 3502.0))
    # Simulate a stale handle: close the raw connection out from under it.
    store._conn.close()
    store.save_candle(_candle(1700000060, 3503.0))
    loaded = store.load_latest_candles(limit=10)
    assert [c["c"] for c in loaded] == [3502.0, 3503.0]
    store.close()


def test_p2_concurrent_candle_writes_all_persist(tmp_path):
    db = str(tmp_path / "p2c.db")
    store = ArenaStorage(db_path=db)
    errors = []

    def writer(start):
        try:
            for i in range(25):
                store.save_candle(_candle(1700000000 + (start + i) * 60, 3500.0 + i))
        except Exception as e:  # noqa: BLE001 - collected and asserted below
            errors.append(e)

    threads = [threading.Thread(target=writer, args=(k * 25,)) for k in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert not errors
    assert len(store.load_latest_candles(limit=500)) == 100
    store.close()


def test_p2_save_candle_is_fast_with_persistent_connection(tmp_path):
    # Generous bound: persistent writes measure ~0.02 ms each on the PC;
    # the old per-connection path measured ~8 ms each (200 x 8 ms = 1.6 s
    # of pure connection churn, plus variance). 5 s leaves wide margin
    # for slow CI while still catching a regression to per-call connect.
    db = str(tmp_path / "p2d.db")
    store = ArenaStorage(db_path=db)
    t0 = time.perf_counter()
    for i in range(200):
        store.save_candle(_candle(1700000000 + i * 60, 3500.0 + (i % 5)))
    elapsed = time.perf_counter() - t0
    assert elapsed < 5.0, f"200 save_candle took {elapsed:.2f}s (persistent conn expected)"
    assert len(store.load_latest_candles(limit=500)) == 200
    store.close()


def test_p2_engine_stop_closes_storage_and_restart_still_writes(tmp_path):
    import os as _os
    _os.environ["ARENA_FAST_TEST"] = "1"
    from src.data.live_engine import LiveArenaEngine

    db = str(tmp_path / "p2e.db")
    store = ArenaStorage(db_path=db)
    engine = LiveArenaEngine(storage=store)
    engine.stop()
    assert store._conn is None
    # Restarting the same engine must still persist (lazy reopen).
    engine.storage.save_candle(_candle(1700000000, 3502.0))
    assert store.load_latest_candles(limit=5)[0]["c"] == 3502.0
    engine.stop()


def test_p2_eth_feed_import_does_not_import_pandas():
    # In-process pandas is already imported by the test session, so this
    # must run in a fresh interpreter (the .venv python running pytest).
    # Only pandas is asserted: numpy still enters via src/__init__.py ->
    # timemachine's eager try-import (pre-existing, unrelated to
    # eth_feed), so numpy's presence proves nothing about eth_feed.
    code = (
        "import sys\n"
        "import src.data.eth_feed as m\n"
        "assert 'pandas' not in sys.modules, 'pandas imported at eth_feed import time'\n"
        "assert hasattr(m, 'ETHFeed') and hasattr(m, 'CandleBar')\n"
        "print('LAZY_OK')\n"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-2000:]
    assert "LAZY_OK" in r.stdout


def test_p2_eth_feed_first_fetch_loads_pandas_and_behaves(tmp_path):
    # ARENA_FAST_TEST=1 makes _fetch_dataframe return an empty frame,
    # so fetch_historical_bars raises ValueError -- after pandas has
    # been lazily imported (no NameError / ImportError from the lazy path).
    code = (
        "import os, sys\n"
        "os.environ['ARENA_FAST_TEST'] = '1'\n"
        "from src.data.eth_feed import ETHFeed\n"
        "assert 'pandas' not in sys.modules\n"
        "try:\n"
        "    ETHFeed.fetch_historical_bars(ticker='ETH-USD', period='1d', interval='1m')\n"
        "    raise SystemExit('expected ValueError for empty bars')\n"
        "except ValueError as e:\n"
        "    assert 'No market data' in str(e)\n"
        "assert 'pandas' in sys.modules, 'pandas not loaded by first fetch'\n"
        "print('FETCH_OK')\n"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-2000:]
    assert "FETCH_OK" in r.stdout


def test_p2_fetch_from_registry_parallel_same_events_faster(monkeypatch):
    import requests

    from src.intelligence.ingestion import FEED_REGISTRY, IntelligenceHarvester

    monkeypatch.setenv("ARENA_FAST_TEST", "0")
    fetchable = [e for e in FEED_REGISTRY if e.get("type") != "stocktwits"]
    assert len(fetchable) == 16

    def mock_get(url, headers=None, timeout=None):
        time.sleep(0.3)
        resp = MagicMock()
        if "polymarket" in url:
            resp.status_code = 200
            resp.json.return_value = [
                {"title": "Poly event", "volume24hr": 100, "slug": "x", "markets": []}
            ]
            resp.text = ""
            return resp
        if "sec.gov" in url:
            # Simulate one dead source: must not take down the digest.
            raise ConnectionError("sec down")
        safe_url = url.replace("&", "&amp;")
        resp.status_code = 200
        resp.text = (
            "<rss><channel><item>"
            f"<title>Item from {safe_url}</title><link>{safe_url}/item1</link>"
            "<description>desc</description></item></channel></rss>"
        )
        resp.json.side_effect = ValueError("not json")
        return resp

    client = MagicMock()
    harvester = IntelligenceHarvester(client=client)
    t0 = time.perf_counter()
    with patch.object(requests, "get", side_effect=mock_get):
        events = harvester.fetch_from_registry()
    elapsed = time.perf_counter() - t0
    # Sequential floor would be 16 x 0.3 s = 4.8 s; parallel must be far under it.
    assert elapsed < 2.5, f"parallel fetch took {elapsed:.2f}s"
    # 15 live sources (16 fetchable minus the dead SEC one), one event each,
    # in registry order, no forum entries, dedup applied.
    assert len(events) == 15
    assert all(e.domain != "forum" for e in events)
    expected_sources = [
        ("Polymarket" if e.get("type") == "rest_json" else e["name"])
        for e in fetchable
        if "sec.gov" not in e["url"]
    ]
    assert [e.source for e in events] == expected_sources
    # Second call: everything deduped -> zero fresh events, still fast.
    t0 = time.perf_counter()
    with patch.object(requests, "get", side_effect=mock_get):
        events2 = harvester.fetch_from_registry()
    assert events2 == []
    assert time.perf_counter() - t0 < 2.5
