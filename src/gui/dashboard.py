from __future__ import annotations

import logging
import os
import pathlib
import sys
from decimal import Decimal
from typing import Any, Dict

from src.data.live_engine import LiveArenaEngine

logger = logging.getLogger(__name__)


def _get_assets_dir() -> pathlib.Path:
    if hasattr(sys, "_MEIPASS"):
        return pathlib.Path(sys._MEIPASS) / "src" / "gui" / "assets"
    return pathlib.Path(__file__).parent / "assets"


_ASSETS_DIR = _get_assets_dir()


def _load_asset(filename: str) -> str:
    path = _ASSETS_DIR / filename
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def _build_html_template() -> str:
    html = _load_asset("index.html")
    css = _load_asset("app.css")
    js = _load_asset("app.js")
    if not html:
        return "<html><body>Asset loading failed</body></html>"
    return html.replace("/* __APP_CSS__ */", css).replace("/* __APP_JS__ */", js)


HTML_TEMPLATE = _build_html_template()


class _ArenaBridgeApi:
    """
    Native Python <-> WebView2 GPU Frontend Bridge.
    Exposes zero-latency state polling and interactive controls to the HiDPI UI.
    """

    def __init__(self, dashboard: "ArenaDashboard") -> None:
        self._dashboard = dashboard

    def get_state(self) -> Dict[str, Any]:
        return self._dashboard.engine.get_ui_state()

    def evolve_now(self) -> Dict[str, Any]:
        self._dashboard.engine.evolve_now(trigger="manual")
        return self._dashboard.engine.get_ui_state()

    def toggle_pause(self) -> Dict[str, Any]:
        self._dashboard.engine.paused = not self._dashboard.engine.paused
        return self._dashboard.engine.get_ui_state()

    def toggle_auto_evolve(self) -> Dict[str, Any]:
        self._dashboard.engine.toggle_auto_evolve()
        return self._dashboard.engine.get_ui_state()

    def set_evolve_interval(self, seconds: int) -> Dict[str, Any]:
        self._dashboard.engine.set_auto_evolve_interval(seconds)
        return self._dashboard.engine.get_ui_state()

    def reset_arena(self) -> Dict[str, Any]:
        self._dashboard.reset_engine()
        return self._dashboard.engine.get_ui_state()

    def toggle_fullscreen(self) -> bool:
        if self._dashboard.window:
            self._dashboard.window.toggle_fullscreen()
            return True
        return False


class ArenaDashboard:
    """
    Native Windows GPU-Accelerated HiDPI Live Multi-Strategy Trading Desk.
    Powered by Edge WebView2 DirectX 11 Compositor + LiveArenaEngine.
    """

    def __init__(self, initial_cash: Decimal = Decimal("500000.00")) -> None:
        self.initial_cash = initial_cash
        self.engine = LiveArenaEngine(symbol="ETH/USD", initial_cash=initial_cash)
        self.window = None
        self._bridge = _ArenaBridgeApi(self)

    def reset_engine(self) -> None:
        old_interval = self.engine.auto_evolve_interval_sec
        old_enabled = self.engine.auto_evolve_enabled
        self.engine.stop()
        self.engine = LiveArenaEngine(symbol="ETH/USD", initial_cash=self.initial_cash)
        self.engine.auto_evolve_interval_sec = old_interval
        self.engine.auto_evolve_enabled = old_enabled
        self.engine.start_live_loop(interval_sec=1.5)

    def run(self) -> None:
        import webview

        # Start real-time live ETH/USD streaming & multi-strategy execution immediately
        self.engine.start_live_loop(interval_sec=1.5)

        window = webview.create_window(
            title="TradeBot0 — ETH/USD Multi-Strategy Quant Arena (Obsidian High-Contrast · Style B Evolution)",
            html=HTML_TEMPLATE,
            js_api=self._bridge,
            width=1540,
            height=940,
            min_size=(960, 640),
            background_color="#08090C",
            resizable=True,
            maximized=True,
            text_select=False,
        )
        self.window = window

        try:
            webview.start(debug=False)
        finally:
            self.engine.stop()
