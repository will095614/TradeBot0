import os
import pytest


@pytest.fixture(autouse=True)
def isolate_arena_memory(tmp_path, monkeypatch):
    """
    Hermetic test fixture: redirects all evolution history and reports
    to a temporary directory during test execution.
    """
    test_mem = tmp_path / "memory"
    test_mem.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("ARENA_MEMORY_DIR", str(test_mem))
    monkeypatch.setenv("ARENA_FAST_TEST", "1")
    yield

