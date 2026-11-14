"""Audit 3.20: save_history created a new ArenaStorage per evolution and
never closed it. Now it accepts an optional caller-owned storage (used,
never closed here) and otherwise creates one and closes it in a finally.

The JSON history writes go to ARENA_MEMORY_DIR, which conftest already
redirects to tmp_path for every test.
"""
from src.arena.evolution import GeneticEvolver
from src.data import persistence


def _records():
    return [{
        "portfolio_id": "comp_agg",
        "prev_roi_pct": 1.0,
        "prev_sharpe": 0.5,
        "prev_max_dd_pct": 2.0,
        "new_genome": {},
    }]


def test_save_history_closes_storage_it_creates(monkeypatch):
    created = []

    class CountingStorage(persistence.ArenaStorage):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            created.append(self)
            self.close_calls = 0

        def close(self):
            self.close_calls += 1
            super().close()

    monkeypatch.setattr(persistence, "ArenaStorage", CountingStorage)
    for _ in range(3):
        GeneticEvolver.save_history(1, _records(), evolution_seed=7)
    assert len(created) == 3
    assert [c.close_calls for c in created] == [1, 1, 1]


def test_save_history_reuses_caller_storage_without_closing(monkeypatch):
    storage = persistence.ArenaStorage()
    close_calls = []
    real_close = storage.close
    monkeypatch.setattr(storage, "close", lambda: (close_calls.append(1), real_close()))

    created = []

    class CountingStorage(persistence.ArenaStorage):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            created.append(self)

    monkeypatch.setattr(persistence, "ArenaStorage", CountingStorage)
    GeneticEvolver.save_history(1, _records(), evolution_seed=7, storage=storage)
    assert created == [], "no new storage may be built when one is passed in"
    assert close_calls == [], "caller-owned storage must not be closed by save_history"
    storage.close()
