"""UI feedback fixes (2026-11-13): copy-password bridge.

copy_omniroute_password reads INITIAL_PASSWORD server-side and copies it
via the OS clipboard; the value never reaches the frontend (item 7).
The clipboard helper is monkeypatched here; the real ctypes path is
verified by clicking the button in the app.
"""
import json
from pathlib import Path
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
