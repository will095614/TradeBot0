"""UI feedback fixes (2026-11-13): copy-password bridge.

copy_omniroute_password reads INITIAL_PASSWORD server-side and copies it
via the OS clipboard; the value never reaches the frontend (item 7).
Most tests monkeypatch the clipboard helper; the real ctypes path is
pinned by test_copy_text_to_clipboard_windows_roundtrip below (the
64-bit handle-truncation bug made it always return False until fixed).
"""
import json
from pathlib import Path

import pytest
from unittest.mock import MagicMock

import src.gui.dashboard as dashboard_mod
from src.gui.dashboard import ArenaDashboard, _ArenaBridgeApi
from src.intelligence.config_manager import ConfigManager


def _bridge_with_env(tmp_path, env_text):
    dash = ArenaDashboard()
    dash.config_manager = ConfigManager(
        data_dir=tmp_path / "data",
        omni_env_path=tmp_path / ".omniroute" / ".env",
    )
    env_dir = tmp_path / ".omniroute"
    env_dir.mkdir(parents=True, exist_ok=True)
    (env_dir / ".env").write_text(env_text, encoding="utf-8")
    dash.gateway_supervisor = MagicMock()
    return _ArenaBridgeApi(dash)


def test_copy_password_not_configured(tmp_path, monkeypatch):
    bridge = _bridge_with_env(tmp_path, "DEEPSEEK_API_KEY=sk-test\n")
    calls = []
    monkeypatch.setattr(
        dashboard_mod, "_copy_text_to_clipboard_windows",
        lambda text: calls.append(text) or True,
    )
    res = bridge.copy_omniroute_password()
    assert res["status"] == "error"
    assert calls == []


def test_copy_password_copies_value_but_never_returns_it(tmp_path, monkeypatch):
    bridge = _bridge_with_env(tmp_path, "INITIAL_PASSWORD=Secret1234\n")
    calls = []
    monkeypatch.setattr(
        dashboard_mod, "_copy_text_to_clipboard_windows",
        lambda text: calls.append(text) or True,
    )
    res = bridge.copy_omniroute_password()
    assert res == {"status": "ok"}
    assert calls == ["Secret1234"]
    assert "Secret1234" not in json.dumps(res)


def test_copy_password_helper_failure(tmp_path, monkeypatch):
    bridge = _bridge_with_env(tmp_path, "INITIAL_PASSWORD=Secret1234\n")
    monkeypatch.setattr(
        dashboard_mod, "_copy_text_to_clipboard_windows", lambda text: False
    )
    res = bridge.copy_omniroute_password()
    assert res["status"] == "error"
    assert "Secret1234" not in json.dumps(res)


def test_copy_text_to_clipboard_windows_non_windows(monkeypatch):
    monkeypatch.setattr(dashboard_mod.sys, "platform", "linux")
    assert dashboard_mod._copy_text_to_clipboard_windows("x") is False


def test_copy_text_to_clipboard_windows_roundtrip():
    """Real ctypes clipboard path (Windows-only).

    Regression test for the 2026-11-13 bug: without declared restype /
    argtypes, ctypes truncated the 64-bit HGLOBAL handle to c_int, so
    GlobalLock always failed and the helper always returned False — the
    copy button never worked. The helper is called first (its True/False
    is decided by its own declarations); the read-back below uses a
    separate WinDLL instance. Saves the previous clipboard text (when
    it is text) and restores it afterwards.
    """
    if dashboard_mod.sys.platform != "win32":
        pytest.skip("Windows-only clipboard test")
    import ctypes

    user32 = ctypes.WinDLL("user32", use_errno=True)
    kernel32 = ctypes.WinDLL("kernel32", use_errno=True)
    user32.OpenClipboard.restype = ctypes.c_bool
    user32.OpenClipboard.argtypes = [ctypes.c_void_p]
    user32.CloseClipboard.restype = ctypes.c_bool
    user32.CloseClipboard.argtypes = []
    user32.GetClipboardData.restype = ctypes.c_void_p
    user32.GetClipboardData.argtypes = [ctypes.c_uint]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.restype = ctypes.c_bool
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]

    def _read_text():
        if not user32.OpenClipboard(None):
            return None
        try:
            handle = user32.GetClipboardData(13)  # CF_UNICODETEXT
            if not handle:
                return None
            locked = kernel32.GlobalLock(handle)
            if not locked:
                return None
            try:
                return ctypes.wstring_at(locked)
            finally:
                kernel32.GlobalUnlock(handle)
        finally:
            user32.CloseClipboard()

    previous = _read_text()
    try:
        assert dashboard_mod._copy_text_to_clipboard_windows(
            "seed-clipboard-roundtrip-123"
        ) is True
        assert _read_text() == "seed-clipboard-roundtrip-123"
    finally:
        if previous is not None:
            dashboard_mod._copy_text_to_clipboard_windows(previous)
