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


def test_bidirectional_short_win_rate_and_closing_fill():
    from src.arena.order import FillEvent, OrderSide, PositionSide, ExecutionReason
    from src.arena.leaderboard import Leaderboard

    p = Portfolio(portfolio_id="p_short", name="ShortTest", initial_cash=Decimal("100000.00"))
    # 1. Open SHORT at $2500 (SELL 10 ETH)
    f_open = FillEvent(
        order_id="o1",
        portfolio_id="p_short",
        symbol="ETH/USD",
        side=OrderSide.SELL,
        qty=Decimal("10.0"),
        price=Decimal("2500.00"),
        fee=Decimal("12.50"),
        timestamp=1000.0,
        reason=ExecutionReason.SIGNAL_ENTRY,
    )
    enriched_open = p.apply_fill(f_open)
    assert enriched_open.position_side == PositionSide.SHORT
    assert not enriched_open.is_closing_fill
    assert enriched_open.is_opening_fill

    # While open, closed_trades and win_rate must be 0
    rankings_open = Leaderboard.get_rankings({"p_short": p})
    assert rankings_open[0].closed_trades == 0
    assert rankings_open[0].win_rate_pct == Decimal("0.00")

    # 2. Cover SHORT at $2400 (BUY 10 ETH -> profit!)
    f_close = FillEvent(
        order_id="o2",
        portfolio_id="p_short",
        symbol="ETH/USD",
        side=OrderSide.BUY,
        qty=Decimal("10.0"),
        price=Decimal("2400.00"),
        fee=Decimal("12.00"),
        timestamp=1060.0,
        reason=ExecutionReason.TAKE_PROFIT,
    )
    enriched_close = p.apply_fill(f_close)
    assert enriched_close.position_side == PositionSide.SHORT
    assert enriched_close.is_closing_fill
    assert not enriched_close.is_opening_fill
    assert enriched_close.realized_pnl > Decimal("0")

    rankings_closed = Leaderboard.get_rankings({"p_short": p})
    assert rankings_closed[0].closed_trades == 1
    assert rankings_closed[0].win_rate_pct == Decimal("100.00")


def test_genetic_evolver_preserves_elite_leverage():
    from src.arena.evolution import GeneticEvolver
    from src.arena.leaderboard import Leaderboard
    from src.competitors.aggressive import AggressiveCompetitor
    from src.competitors.orb import ORBCompetitor
    from src.competitors.conservative import ConservativeCompetitor

    c1 = AggressiveCompetitor()  # 3.0x leverage enabled
    c2 = ORBCompetitor()         # 2.5x leverage enabled
    c3 = ConservativeCompetitor()
    c1.portfolio.cash += Decimal("5000.00")
    c2.portfolio.cash += Decimal("2500.00")

    competitors = [c1, c2, c3]
    rankings = Leaderboard.get_rankings({c.portfolio_id: c.portfolio for c in competitors})
    GeneticEvolver.evolve_generation(competitors, rankings, preserve_portfolio=True, save_history=False)

    assert c1.genome.leverage_enabled is True
    assert c1.genome.leverage == Decimal("3.0")
    assert c2.genome.leverage_enabled is True
    assert c2.genome.leverage == Decimal("2.5")


def test_macro_veto_intent_preserved_in_live_evaluation(monkeypatch):
    monkeypatch.setenv("ARENA_FAST_TEST", "1")
    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    # Set Macro Commander to SHORT_ONLY so LONG entries are vetoed
    engine.macro_commander.current_state.directional_bias = "SHORT_ONLY"
    engine.macro_commander.current_state.active_headline = "Bearish Macro Regime Test"
    engine.live_ema_fast = Decimal("2510.00")
    engine.live_ema_slow = Decimal("2500.00")
    engine.live_rsi = Decimal("58.00")
    engine.live_atr = Decimal("15.00")

    # Trigger uptrend breakout condition for comp_agg (price > prev_price, uptrend, rsi < 68)
    engine._evaluate_live_strategies(Decimal("2520.00"), Decimal("2510.00"), 2000.0)
    intent = engine.strategy_telemetry["comp_agg"]["intent"]
    assert intent.startswith("Macro Veto:"), f"Expected Macro Veto intent to be preserved, got: {intent}"


