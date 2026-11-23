"""V2.5.3 regression tests for installer Launch TradeBot0 option and native startup splash screen."""
from __future__ import annotations

from pathlib import Path
import struct
import sys
from types import ModuleType

from src.gui.dashboard import close_native_splash
from src.version import APP_VERSION

ROOT = Path(__file__).resolve().parent.parent


def test_installer_has_launch_checkbox_checked_by_default():
    iss = (ROOT / "TradeBot0.iss").read_text(encoding="utf-8")
    assert f'#define MyAppVersion "{APP_VERSION}"' in iss
    assert f"VersionInfoVersion={APP_VERSION.lstrip('Vv')}" in iss
    assert "[Run]" in iss
    run_section = iss.split("[Run]", 1)[1].split("[", 1)[0]
    assert r'Filename: "{app}\{#MyAppExeName}"' in run_section
    assert "{cm:LaunchProgram" in run_section
    assert "nowait" in run_section
    assert "postinstall" in run_section
    assert "skipifsilent" in run_section
    assert "unchecked" not in run_section.lower()


def test_splash_logo_png_and_build_wiring():
    splash_png = ROOT / "src" / "gui" / "assets" / "splash_logo.png"
    assert splash_png.is_file()
    raw = splash_png.read_bytes()
    assert raw[:8] == b"\x89PNG\r\n\x1a\n"
    assert raw[12:16] == b"IHDR"
    width, height = struct.unpack(">II", raw[16:24])
    color_type = raw[25]
    assert 0 < width <= 760
    assert 0 < height <= 480
    # Opaque RGB PNG avoids Windows magenta color-key fringes on anti-aliased edges
    assert color_type == 2

    build_ps1 = (ROOT / "build_exe.ps1").read_text(encoding="utf-8")
    assert '"--splash", "src/gui/assets/splash_logo.png"' in build_ps1


def test_close_native_splash_safe_and_calls_pyi_splash(monkeypatch):
    # Source run (no pyi_splash module) returns False safely
    monkeypatch.delitem(sys.modules, "pyi_splash", raising=False)
    assert close_native_splash() is False

    # Frozen run with alive splash calls close() and returns True
    calls = []
    fake_alive = ModuleType("pyi_splash")
    fake_alive.is_alive = lambda: True  # type: ignore[attr-defined]
    fake_alive.close = lambda: calls.append("closed")  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pyi_splash", fake_alive)
    assert close_native_splash() is True
    assert calls == ["closed"]

    # Already-closed splash returns False without calling close() again
    fake_dead = ModuleType("pyi_splash")
    fake_dead.is_alive = lambda: False  # type: ignore[attr-defined]
    fake_dead.close = lambda: calls.append("unexpected")  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pyi_splash", fake_dead)
    assert close_native_splash() is False
    assert calls == ["closed"]


def test_dashboard_and_main_wire_close_native_splash():
    dash_src = (ROOT / "src" / "gui" / "dashboard.py").read_text(encoding="utf-8")
    main_src = (ROOT / "main.py").read_text(encoding="utf-8")

    # Dashboard closes splash on window shown and in run()'s finally guard
    shown_block = dash_src.split("def _on_window_shown(", 1)[1].split("window.events.shown", 1)[0]
    assert "close_native_splash()" in shown_block
    run_finally = dash_src.rsplit("webview.start(debug=False)", 1)[1]
    assert "close_native_splash()" in run_finally

    # main.py closes splash on early exit paths (--self-test, --cli, WebView2 prompt, finally)
    assert "from src.gui.dashboard import ArenaDashboard, close_native_splash" in main_src
    assert main_src.count("close_native_splash()") >= 4
