"""Audit §5.7: persist a 1-minute candle only when its bar closes.

_update_candle used to call storage.save_candle on EVERY tick for the
still-forming current bar (~1 write/second, ~60 per bar). The write
must now happen exactly once per closed bar: when a tick lands in a
new minute, the previous bar is final and is persisted; ticks inside
the open bar must not write at all.
"""
from __future__ import annotations

from decimal import Decimal

from src.data.live_engine import LiveArenaEngine
from src.data.persistence import ArenaStorage


def _engine(tmp_path):
    storage = ArenaStorage(db_path=str(tmp_path / "arena_history.db"))
    eng = LiveArenaEngine(storage=storage, initial_cash=Decimal("100000.00"), symbol="ETH/USD")
    eng.is_bootstrapped = True
    return eng, storage


def _counting_save(monkeypatch, storage):
    calls = []
    orig = storage.save_candle

    def counting(c):
        calls.append(dict(c))
        return orig(c)

    monkeypatch.setattr(storage, "save_candle", counting)
    return calls


def test_ticks_within_one_minute_write_nothing(tmp_path, monkeypatch):
    eng, storage = _engine(tmp_path)
    calls = _counting_save(monkeypatch, storage)
    minute = 1_700_000_040.0
    for i in range(59):
        eng._update_candle(minute + i, Decimal("3500.00") + i, Decimal("3510.00"), Decimal("3490.00"), Decimal("3500.00"))
    assert calls == []
    # The in-memory candle still tracks every tick.
    assert eng.candles[-1]["c"] == 3500.00 + 58
    assert eng.candles[-1]["h"] == 3510.00
    assert eng.candles[-1]["l"] == 3490.00


def test_bar_close_persists_final_bar_once(tmp_path, monkeypatch):
    eng, storage = _engine(tmp_path)
    calls = _counting_save(monkeypatch, storage)
    minute = 1_700_000_040.0
    eng._update_candle(minute + 0, Decimal("3500.00"), Decimal("3505.00"), Decimal("3495.00"), Decimal("3500.00"))
    eng._update_candle(minute + 10, Decimal("3502.00"), Decimal("3508.00"), Decimal("3498.00"), Decimal("3500.00"))
    eng._update_candle(minute + 50, Decimal("3499.00"), Decimal("3503.00"), Decimal("3490.00"), Decimal("3500.00"))
    assert calls == []
    # A tick in the next minute closes the bar: exactly one write, with
    # the final OHLC of the closed bar.
    eng._update_candle(minute + 60, Decimal("3501.00"), Decimal("3501.00"), Decimal("3501.00"), Decimal("3501.00"))
    assert len(calls) == 1
    assert calls[0]["t"] == minute
    assert calls[0]["o"] == 3500.00
    assert calls[0]["h"] == 3508.00
    assert calls[0]["l"] == 3490.00
    assert calls[0]["c"] == 3499.00
    # More ticks inside the new open bar: still exactly one write.
    eng._update_candle(minute + 61, Decimal("3502.00"), Decimal("3502.00"), Decimal("3502.00"), Decimal("3501.00"))
    eng._update_candle(minute + 119, Decimal("3503.00"), Decimal("3503.00"), Decimal("3503.00"), Decimal("3501.00"))
    assert len(calls) == 1


def test_three_minutes_persist_two_closed_bars(tmp_path, monkeypatch):
    eng, storage = _engine(tmp_path)
    calls = _counting_save(monkeypatch, storage)
    minute = 1_700_000_040.0
    eng._update_candle(minute + 0, Decimal("3500.00"), Decimal("3500.00"), Decimal("3500.00"), Decimal("3500.00"))
    eng._update_candle(minute + 60, Decimal("3510.00"), Decimal("3510.00"), Decimal("3510.00"), Decimal("3510.00"))
    eng._update_candle(minute + 120, Decimal("3520.00"), Decimal("3520.00"), Decimal("3520.00"), Decimal("3520.00"))
    assert [c["t"] for c in calls] == [minute, minute + 60]
    assert [c["c"] for c in calls] == [3500.00, 3510.00]
    # The open minute-120 bar is not persisted yet.
    assert eng.candles[-1]["t"] == minute + 120


def test_closed_bar_is_in_sqlite_after_close(tmp_path, monkeypatch):
    eng, storage = _engine(tmp_path)
    _counting_save(monkeypatch, storage)
    minute = 1_700_000_040.0
    eng._update_candle(minute + 0, Decimal("3500.00"), Decimal("3505.00"), Decimal("3495.00"), Decimal("3500.00"))
    eng._update_candle(minute + 30, Decimal("3502.00"), Decimal("3502.00"), Decimal("3498.00"), Decimal("3500.00"))
    eng._update_candle(minute + 60, Decimal("3501.00"), Decimal("3501.00"), Decimal("3501.00"), Decimal("3501.00"))
    # No graceful shutdown: the closed bar must already be durable.
    rows = storage.load_latest_candles(10)
    assert len(rows) == 1
    assert rows[0]["t"] == minute
    assert rows[0]["c"] == 3502.00
    assert rows[0]["h"] == 3505.00
    assert rows[0]["l"] == 3495.00


def test_out_of_order_tick_does_not_double_save(tmp_path, monkeypatch):
    eng, storage = _engine(tmp_path)
    calls = _counting_save(monkeypatch, storage)
    minute = 1_700_000_040.0
    eng._update_candle(minute + 0, Decimal("3500.00"), Decimal("3500.00"), Decimal("3500.00"), Decimal("3500.00"))
    eng._update_candle(minute + 60, Decimal("3510.00"), Decimal("3510.00"), Decimal("3510.00"), Decimal("3510.00"))
    assert len(calls) == 1
    # A late tick for the already-closed minute must not re-save it.
    eng._update_candle(minute + 30, Decimal("3501.00"), Decimal("3501.00"), Decimal("3501.00"), Decimal("3500.00"))
    assert len(calls) == 1
