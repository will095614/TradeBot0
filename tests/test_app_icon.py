"""Regression tests for custom TradeBot0 desktop & taskbar app icon assets and wiring."""
from __future__ import annotations

import ctypes
import pathlib
import struct
import sys

from src.gui.dashboard import _apply_window_icon, _build_html_template, _get_app_icon_path

ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_app_icon_ico_multi_resolution_and_win32_load():
    ico = ROOT / "src" / "gui" / "assets" / "app_icon.ico"
    assert ico.is_file()
    raw = ico.read_bytes()
    assert len(raw) >= 6
    reserved, ico_type, count = struct.unpack("<HHH", raw[:6])
    assert reserved == 0
    assert ico_type == 1
    assert count >= 7

    sizes = set()
    for i in range(count):
        entry = raw[6 + i * 16 : 6 + (i + 1) * 16]
        assert len(entry) == 16
        w = 256 if entry[0] == 0 else entry[0]
        h = 256 if entry[1] == 0 else entry[1]
        assert w == h
        sizes.add(w)
    assert {16, 24, 32, 48, 64, 128, 256}.issubset(sizes)

    if sys.platform == "win32":
        u32 = ctypes.windll.user32
        for sz in (16, 32, 256):
            hicon = u32.LoadImageW(None, str(ico.resolve()), 1, sz, sz, 0x0010)
            assert hicon, f"LoadImageW failed for {sz}x{sz}"
            u32.DestroyIcon(hicon)


def test_app_icon_png_dimensions_and_rgba():
    png = ROOT / "src" / "gui" / "assets" / "app_icon.png"
    assert png.is_file()
    raw = png.read_bytes()
    assert raw[:8] == b"\x89PNG\r\n\x1a\n"
    assert raw[12:16] == b"IHDR"
    width, height = struct.unpack(">II", raw[16:24])
    color_type = raw[25]
    assert (width, height) == (256, 256)
    assert color_type == 6  # RGBA


def test_packaging_configs_reference_app_icon():
    spec_src = (ROOT / "TradeBot0_Arena.spec").read_text(encoding="utf-8")
    ps1_src = (ROOT / "build_exe.ps1").read_text(encoding="utf-8")
    iss_src = (ROOT / "TradeBot0.iss").read_text(encoding="utf-8")

    assert "src/gui/assets/app_icon.ico" in spec_src
    assert '"--icon", "src/gui/assets/app_icon.ico"' in ps1_src
    assert "SetupIconFile=src\\gui\\assets\\app_icon.ico" in iss_src


def test_runtime_taskbar_and_html_icon_wiring():
    main_src = (ROOT / "main.py").read_text(encoding="utf-8")
    dash_src = (ROOT / "src" / "gui" / "dashboard.py").read_text(encoding="utf-8")

    assert "def _set_windows_app_user_model_id(" in main_src
    assert "SetCurrentProcessExplicitAppUserModelID" in main_src
    assert "_set_windows_app_user_model_id()" in main_src

    assert "def _get_app_icon_path(" in dash_src
    assert "def _apply_window_icon(" in dash_src
    assert 'webview._state["icon"] = str(ico_path)' in dash_src

    ico_path = _get_app_icon_path()
    assert ico_path is not None and ico_path.is_file()
    assert _apply_window_icon(None) is False

    html = _build_html_template()
    assert "/* __APP_ICON_DATA_URI__ */" not in html
    assert '<link rel="icon" type="image/png" href="data:image/png;base64,' in html
