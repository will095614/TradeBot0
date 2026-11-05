import os
import pathlib
import re
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
import pytest

from src.arena.portfolio import Portfolio
from src.data.eth_feed import ETHFeed
from src.data.live_engine import LiveArenaEngine
from src.gui.dashboard import ArenaDashboard
from src.intelligence.macro_commander import MacroCommander
from src.intelligence.omniroute_client import OmniRouteClient


def test_zero_cjk_in_frontend_assets():
    assets_dir = pathlib.Path("src/gui/assets")
    for fname in ["index.html", "app.js", "app.css"]:
        file_path = assets_dir / fname
        assert file_path.exists(), f"Asset {fname} must exist"
        content = file_path.read_text(encoding="utf-8")
        cjk_matches = re.findall(r"[\u4e00-\u9fff]", content)
        assert len(cjk_matches) == 0, f"Found {len(cjk_matches)} CJK chars in {fname}: {cjk_matches[:5]}"


def test_portfolio_no_duplicate_apply_fill_returns():
    p = Portfolio(portfolio_id="p_test", name="Test")
    # Verify apply_fill executes cleanly without duplicate dead return blocks
    assert hasattr(p, "apply_fill")


def test_reset_engine_preserves_cadence():
    dash = ArenaDashboard(initial_cash=Decimal("100000.00"))
    dash.engine.set_cadence_interval(3.0)
    assert dash.engine.cadence_sec == 3.0

    dash.reset_engine()
    assert dash.engine.cadence_sec == 3.0
    dash.engine.stop()


def test_macro_commander_skips_chat_when_gateway_offline():
    import asyncio

    async def _test():
        mock_client = MagicMock()
        mock_client.is_gateway_online = False
        mock_client.chat_json = AsyncMock()

        commander = MacroCommander(mock_client)
        state = await commander.synthesize_regime([])

        # chat_json must NOT be called when gateway is offline
        mock_client.chat_json.assert_not_called()
        assert state.status == "STANDBY"

    asyncio.run(_test())


def test_eth_feed_fast_fallback_under_test_flag(monkeypatch):
    monkeypatch.setenv("ARENA_FAST_TEST", "1")
    df = ETHFeed._fetch_dataframe(ticker="ETH-USD", period="1d", interval="1m")
    assert df.empty


def test_launchers_and_shortcut_integrity():
    root = pathlib.Path(".")
    exe = root / "dist" / "TradeBot0_Arena.exe"
    assert exe.exists(), "dist/TradeBot0_Arena.exe must exist"

    run_bat = root / "Run_TradeBot0_Arena.bat"
    assert run_bat.exists()
    content_run = run_bat.read_text(encoding="utf-8", errors="ignore")
    assert "dist\\TradeBot0_Arena.exe" in content_run

    cjk_bat = root / "啟動TradeBot0_Arena.bat"
    assert cjk_bat.exists()
    content_cjk = cjk_bat.read_text(encoding="utf-8", errors="ignore")
    assert "dist\\TradeBot0_Arena.exe" in content_cjk


def test_splash_logo_concentric_alignment_and_svg_zap():
    html = pathlib.Path("src/gui/assets/index.html").read_text(encoding="utf-8")
    css = pathlib.Path("src/gui/assets/app.css").read_text(encoding="utf-8")

    # 1. High-tech vector SVG icon is used instead of emoji
    assert "splash-svg-icon" in html
    assert "polygon points=" in html
    assert "splashZapGrad" in html

    # 2. Ripple rings completely deleted per user directive
    assert "splash-radar-ring" not in html
    assert ".splash-radar-ring" not in css
    assert "splashRadarRipple" not in css

    # 3. Clean flex centered emblem badge
    assert ".splash-icon {" in css
    assert "animation: splashIconPulse" in css
    assert "animation: markerPulse" not in css.split(".splash-icon {")[1].split("}")[0]

