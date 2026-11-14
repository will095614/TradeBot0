"""Audit §5.4: ~/.omniroute/.env must be cached by (mtime_ns, size).

get_gateway_diagnosis polls once a second and each poll re-opened and
re-parsed the whole .env file (~86,400 reads/day). read_omniroute_env
must now serve repeated reads from cache and re-read only when the
file's mtime or size changes (or after our own write).
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.intelligence.config_manager import ConfigManager


def _counting_read_text(monkeypatch, env_path: Path):
    """Count Path.read_text calls that target exactly env_path."""
    counts = {"n": 0}
    orig = Path.read_text

    def counting(self, *args, **kwargs):
        if Path(self) == env_path:
            counts["n"] += 1
        return orig(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", counting)
    return counts


def _manager(tmp_path, content: str) -> ConfigManager:
    env_path = tmp_path / ".env"
    env_path.write_text(content, encoding="utf-8")
    return ConfigManager(data_dir=tmp_path / "data", omni_env_path=env_path)


def test_repeated_reads_hit_cache(tmp_path, monkeypatch):
    cm = _manager(tmp_path, "DEEPSEEK_API_KEY=sk-test-1234\n")
    counts = _counting_read_text(monkeypatch, cm.omni_env_file)
    for _ in range(5):
        assert cm.get_configured_providers() == ["deepseek"]
    assert counts["n"] == 1


def test_mtime_change_invalidates_even_with_same_content(tmp_path, monkeypatch):
    cm = _manager(tmp_path, "DEEPSEEK_API_KEY=sk-test-1234\n")
    counts = _counting_read_text(monkeypatch, cm.omni_env_file)
    assert cm.get_configured_providers() == ["deepseek"]
    assert counts["n"] == 1
    # Rewrite identical bytes with a newer mtime: the cache key includes
    # mtime_ns, so the next read must re-read (and return the same data).
    os.utime(cm.omni_env_file, ns=(1_800_000_000_000_000_000, 1_800_000_000_000_000_000))
    assert cm.get_configured_providers() == ["deepseek"]
    assert counts["n"] == 2


def test_content_change_is_visible_after_rewrite(tmp_path, monkeypatch):
    cm = _manager(tmp_path, "DEEPSEEK_API_KEY=sk-test-1234\n")
    counts = _counting_read_text(monkeypatch, cm.omni_env_file)
    assert cm.get_configured_providers() == ["deepseek"]
    cm.omni_env_file.write_text("GROQ_API_KEY=gsk-test-5678\n", encoding="utf-8")
    assert cm.get_configured_providers() == ["groq"]
    assert counts["n"] == 2


def test_write_then_read_sees_new_password(tmp_path, monkeypatch):
    cm = _manager(tmp_path, "DEEPSEEK_API_KEY=sk-test-1234\n")
    counts = _counting_read_text(monkeypatch, cm.omni_env_file)
    assert cm.is_admin_password_configured() is False
    assert cm.set_admin_password("new-password-123") == {"ok": True}
    # The write path itself reads the file once; the password check after
    # the write must see the new content (cache invalidated by the write).
    assert cm.is_admin_password_configured() is True
    assert counts["n"] == 3


def test_missing_file_then_created(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    cm = ConfigManager(data_dir=tmp_path / "data", omni_env_path=env_path)
    counts = _counting_read_text(monkeypatch, env_path)
    assert cm.get_configured_providers() == []
    assert counts["n"] == 0
    env_path.write_text("OPENROUTER_API_KEY=sk-or-test\n", encoding="utf-8")
    assert cm.get_configured_providers() == ["openrouter"]
    assert counts["n"] == 1


def test_returned_dict_is_a_copy(tmp_path):
    cm = _manager(tmp_path, "DEEPSEEK_API_KEY=sk-test-1234\n")
    first = cm.read_omniroute_env()
    first["DEEPSEEK_API_KEY"] = "poisoned"
    assert cm.read_omniroute_env()["DEEPSEEK_API_KEY"] == "sk-test-1234"
