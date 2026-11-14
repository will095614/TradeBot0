"""Audit §5.2: get_ui_state_delta must not deepcopy the heavy arrays
it is about to drop.

The old path deepcopied the full snapshot (150 candles + 60 fills +
price histories) and only then popped the unchanged candles/fills from
the wire payload. The new path peeks at the candle/fill signatures
first and deepcopies everything EXCEPT the unchanged heavy arrays.
The delta output must be identical either way.
"""
from __future__ import annotations

import copy
from decimal import Decimal

from src.data.live_engine import LiveArenaEngine
from src.data.persistence import ArenaStorage


def _snapshot():
    candles = [
        {"t": 1_700_000_040.0 + i * 60, "o": 3500.0 + i, "h": 3510.0 + i, "l": 3490.0 + i, "c": 3505.0 + i}
        for i in range(150)
    ]
    fills = [
        {"seq": 60 - i, "time": "12:00:00", "strategy": "Aggressive", "side": "BUY", "price": 3500.0 + i}
        for i in range(60)
    ]
    return {
        "paused": False,
        "auto_evolve_enabled": True,
        "candles": candles,
        "fills": fills,
        "strategies": [{"id": "comp_agg", "equity": 100000.0, "nested": {"a": [1, 2, 3]}}],
        "price_history": [3500.0 + i * 0.1 for i in range(200)],
        "intel_hub": {"status": "ONLINE"},
    }


def _engine(tmp_path):
    storage = ArenaStorage(db_path=str(tmp_path / "arena_history.db"))
    return LiveArenaEngine(storage=storage, initial_cash=Decimal("100000.00"), symbol="ETH/USD")


def test_delta_output_identical_to_old_path(tmp_path):
    snap = _snapshot()
    old_eng = _engine(tmp_path)
    new_eng = _engine(tmp_path)
    old_eng._ui_state_snapshot = copy.deepcopy(snap)
    new_eng._ui_state_snapshot = copy.deepcopy(snap)

    # Poll 1 (first poll: full state both ways).
    old1 = old_eng.view_publisher.compute_delta_payload(old_eng.get_ui_state())
    new1 = new_eng.get_ui_state_delta()
    assert new1 == old1

    # Poll 2 (nothing changed: both heavy arrays omitted).
    old2 = old_eng.view_publisher.compute_delta_payload(old_eng.get_ui_state())
    new2 = new_eng.get_ui_state_delta()
    assert new2 == old2
    assert "candles" not in new2 and "fills" not in new2
    assert new2["is_delta"] is True

    # Poll 3 (a new candle lands, fills unchanged: candles included,
    # fills omitted).
    snap2 = copy.deepcopy(snap)
    snap2["candles"].append({"t": 1_700_000_040.0 + 150 * 60, "o": 3650.0, "h": 3660.0, "l": 3640.0, "c": 3655.0})
    old_eng._ui_state_snapshot = copy.deepcopy(snap2)
    new_eng._ui_state_snapshot = copy.deepcopy(snap2)
    old3 = old_eng.view_publisher.compute_delta_payload(old_eng.get_ui_state())
    new3 = new_eng.get_ui_state_delta()
    assert new3 == old3
    assert "candles" in new3 and "fills" not in new3

    # Poll 4 (force_full: full state again both ways).
    old4 = old_eng.view_publisher.compute_delta_payload(old_eng.get_ui_state(), force_full=True)
    new4 = new_eng.get_ui_state_delta(force_full=True)
    assert new4 == old4
    assert new4["is_delta"] is False


def test_deepcopy_never_receives_heavy_arrays_on_unchanged_poll(tmp_path, monkeypatch):
    """The copy-cost proof: on an unchanged poll the dict handed to
    deepcopy must not contain candles/fills at all (the old path handed
    it the whole snapshot every time)."""
    seen = []
    orig = copy.deepcopy

    def recording(obj, *args, **kwargs):
        if isinstance(obj, dict):
            seen.append(set(obj.keys()))
        return orig(obj, *args, **kwargs)

    monkeypatch.setattr(copy, "deepcopy", recording)
    eng = _engine(tmp_path)
    eng._ui_state_snapshot = _snapshot()
    eng.get_ui_state_delta()  # poll 1: full copy
    assert any("candles" in keys and "fills" in keys for keys in seen)
    seen.clear()
    eng.get_ui_state_delta()  # poll 2: unchanged
    assert seen, "expected at least one deepcopy on the unchanged poll"
    assert all("candles" not in keys and "fills" not in keys for keys in seen)


def test_delta_is_still_a_defensive_copy(tmp_path):
    eng = _engine(tmp_path)
    snap = _snapshot()
    eng._ui_state_snapshot = snap
    delta = eng.get_ui_state_delta()
    # The non-heavy parts must be copies, not aliases of the snapshot.
    assert delta["strategies"] is not snap["strategies"]
    assert delta["strategies"][0] is not snap["strategies"][0]
    # Mutating the returned delta must not corrupt the engine snapshot.
    delta["strategies"][0]["equity"] = 0.0
    delta["price_history"].append(999999.0)
    again = eng.get_ui_state_delta(force_full=True)
    assert again["strategies"][0]["equity"] == 100000.0
    assert 999999.0 not in again["price_history"]
