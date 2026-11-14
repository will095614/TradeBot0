"""Audit 3.18: data/system_config.json is runtime state and must not be
tracked in git. It stays on disk (the live app reads it); only the
versioning stops. These tests assert the untracked-but-present state.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "data" / "system_config.json"


def _git(*args):
    git = shutil.which("git")
    if git is None:
        pytest.skip("git not available")
    return subprocess.run(
        [git, *args], cwd=PROJECT_ROOT,
        capture_output=True, text=True, timeout=60,
    )


def test_system_config_is_ignored_by_git():
    result = _git("check-ignore", "data/system_config.json")
    assert result.returncode == 0, (
        "data/system_config.json must be ignored (see .gitignore, audit 3.18); "
        f"git check-ignore rc={result.returncode}"
    )


def test_system_config_is_untracked_but_present_on_disk():
    result = _git("ls-files", "data/system_config.json")
    assert result.stdout.strip() == "", "data/system_config.json must not be tracked"
    assert CONFIG_PATH.is_file(), "data/system_config.json must still exist on disk"
