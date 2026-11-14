"""Audit 3.11: GeneticEvolver._last_records had no class-level default.

_last_records is set only at the end of evolve_generation, so when
evolve_generation returns early (fewer than 2 rankings) the attribute
does not exist yet and evolve_now raised AttributeError on the
unconditional read. The fix adds the None class-level default and
guards the read site with getattr.
"""
from src.arena.evolution import GeneticEvolver
from src.arena.leaderboard import Leaderboard
from src.data.live_engine import LiveArenaEngine


def test_last_records_class_default_present():
    # The default is defined on the class itself, so it exists before
    # any evolution has run in this process.
    assert "_last_records" in GeneticEvolver.__dict__


def test_evolve_generation_early_return_does_not_crash():
    # Fewer than 2 rankings: evolve_generation returns early without
    # setting _last_records.
    assert GeneticEvolver.evolve_generation([], [], save_history=False) == []


def test_evolve_now_with_fewer_than_two_rankings_does_not_raise(monkeypatch):
    # Simulate a fresh process in which no evolution has ever run: drop
    # any _last_records an earlier test may have set, and restore it
    # afterwards (to the class default when nothing was saved).
    saved = GeneticEvolver.__dict__.get("_last_records", None)
    had = "_last_records" in GeneticEvolver.__dict__
    if had:
        delattr(GeneticEvolver, "_last_records")
    try:
        engine = LiveArenaEngine()
        monkeypatch.setattr(
            Leaderboard, "get_rankings", staticmethod(lambda portfolios: [])
        )
        assert engine.evolve_now(trigger="manual") == []
    finally:
        GeneticEvolver._last_records = saved
