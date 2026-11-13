import os
import pathlib
import re
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
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


def test_newly_fetched_news_always_summarized_in_traditional_chinese():
    import asyncio
    from src.intelligence.ingestion import IntelligenceHarvester, RawEvent

    async def _run():
        mock_client = MagicMock()
        mock_client.model_ingest = "auto"
        mock_client.model_commander = "auto"
        mock_client.is_gateway_online = False
        mock_client.chat_json = AsyncMock(return_value=None)

        harvester = IntelligenceHarvester(client=mock_client)
        commander = MacroCommander(client=mock_client, harvester=harvester)

        raw_items = [
            RawEvent(
                source="CoinDesk",
                domain="crypto",
                title="Ethereum Spot ETF Inflows Surge $250M as Institutional Staking Demand Rises 18%",
                url="https://coindesk.com/eth-etf-inflows",
                timestamp=2000.0,
                raw_content="<p>BlackRock and Fidelity recorded $250M in net inflows as Ethereum L2 activity hits record highs.</p>",
            ),
            RawEvent(
                source="ForexLive",
                domain="macro",
                title="Federal Reserve Signals Steady Interest Rate Path Amid Cooling Inflation Data",
                url="https://forexlive.com/fed-rate-path",
                timestamp=2005.0,
                raw_content="FOMC officials noted inflation continues to moderate toward the 2% target.",
            ),
        ]

        structured = await harvester.process_batch(raw_items)
        assert len(structured) == 2
        for se in structured:
            assert re.search(r"[\u4e00-\u9fff]", se.headline_zh), f"headline_zh must be Chinese: {se.headline_zh}"
            assert re.search(r"[\u4e00-\u9fff]", se.summary), f"summary must be Chinese: {se.summary}"

        await commander.synthesize_regime(structured)
        top_event = commander.curated_events[0]
        assert re.search(r"[\u4e00-\u9fff]", top_event["headline"]), f"Curated headline must be Chinese: {top_event['headline']}"
        assert re.search(r"[\u4e00-\u9fff]", top_event["summary"]), f"Curated summary must be Chinese: {top_event['summary']}"

    asyncio.run(_run())


def test_stageshow_ui_design_system_integrity():
    from pathlib import Path
    assets_dir = Path(__file__).resolve().parent.parent / "src" / "gui" / "assets"
    html = (assets_dir / "index.html").read_text(encoding="utf-8")
    css = (assets_dir / "app.css").read_text(encoding="utf-8")
    js = (assets_dir / "app.js").read_text(encoding="utf-8")

    # Unified Stageshow + AIMRAN Liquid Glass tokens & surface ladder
    for token in [
        "--ss-well", "--ss-canvas", "--ss-surface", "--ss-chrome", "--ss-raised",
        "--ss-line", "--ss-shadow-window", "--lg-blur", "--lg-spring"
    ]:
        assert token in css, f"Missing unified UI token {token} in app.css"

    # Balanced CSS braces check (prevents dangling closing braces)
    assert css.count("{") == css.count("}"), f"Unbalanced braces in app.css: {css.count('{')} open vs {css.count('}')} close"

    # Unified Stageshow + AIMRAN Liquid Glass components in HTML & JS
    for marker in [
        "lg-brand-emblem", "ss-seg__thumb", "ss-badge", "ss-meter",
        "chartScrubReadout", "rightTabSeg", "lg-glass", "lg-spot-card",
        "lg-seg", "lg-switch", "lg-orbits", "spatial-dock-bar",
        "lg-dock-pod--island", "spatial-upper-stage", "lg-vessel-card",
        "lg-fluid-tube", "lg-optical-iris", "strategies-bento-dock",
        "isoClockPill"
    ]:
        assert marker in html, f"Missing unified UI element {marker} in index.html"

    for wall in ['data-wallpaper="ocean"', 'data-wallpaper="aurora"', 'data-wallpaper="sunset"', 'data-wallpaper="emerald"']:
        assert wall in css, f"Missing AIMRAN wallpaper preset {wall} in app.css"

    assert "function syncSegThumb" in js
    assert "function trackLgSpotlight" in js
    assert "function setLgWallpaper" in js
    assert "lg-strat-orb" in js
    assert "chartScrubReadout" in js

    # 100% DOM ID parity check: every static getElementById in app.js must exist in index.html
    html_ids = set(re.findall(r'id="([a-zA-Z0-9_-]+)"', html))
    js_ids = set(re.findall(r"getElementById\(['\"]([a-zA-Z0-9_-]+)['\"]\)", js))
    missing_ids = js_ids - html_ids
    assert not missing_ids, f"DOM IDs referenced in app.js but missing in index.html: {missing_ids}"


def test_phase1_websocket_feed_parsing_and_fast_path_fallback():
    import time
    from src.data.ws_feed import StreamingCryptoFeed
    from src.data.live_engine import LiveArenaEngine

    received = []
    feed = StreamingCryptoFeed(on_quote_callback=lambda q: received.append(q))
    sample_payload = {
        "c": "2645.50",
        "b": "2645.40",
        "a": "2645.60",
        "h": "2710.00",
        "l": "2590.00",
        "v": "145230.75",
        "P": "2.15",
    }
    quote = feed._parse_binance_ticker(sample_payload)
    assert quote is not None
    assert quote.price == Decimal("2645.50")
    assert quote.bid == Decimal("2645.40")
    assert quote.ask == Decimal("2645.60")
    assert quote.source.startswith("Binance WS")
    assert quote.is_offline is False

    # Verify LiveArenaEngine uses WebSocket fast-path when connected & fresh (< 3.0s)
    engine = LiveArenaEngine()
    assert engine.ws_feed is engine.quote_manager.ws_feed  # single shared socket
    engine._handle_ws_quote(quote)
    engine.ws_feed.connected = True
    engine.ws_feed.last_msg_ts = time.time()

    fast_q = engine.fetch_realtime_crypto_quote()
    assert fast_q.price == Decimal("2645.50")
    assert fast_q.source.startswith("Binance WS")

    # Stale WS (> 3s) with all REST providers failing must report offline,
    # never return the stale WS quote or a cached price as if live.
    import unittest.mock as mock
    engine.ws_feed.last_msg_ts = time.time() - 10.0
    with mock.patch.object(engine.session, "get", side_effect=Exception("Network Timeout")):
        fb = engine.fetch_realtime_crypto_quote()
    assert fb.is_offline is True
    assert fb.price == Decimal("0.00")


def test_phase2_sqlite_wal_persistence_and_cold_start_hydration(tmp_path):
    from src.data.persistence import ArenaStorage

    db_file = tmp_path / "test_arena.db"
    store = ArenaStorage(db_path=str(db_file))

    with store._get_connection() as conn:
        mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
        assert mode.lower() == "wal"

    bars = [
        {"t": 1700000000.0 + i * 60, "o": 2500.0 + i, "h": 2510.0 + i, "l": 2495.0 + i, "c": 2505.0 + i}
        for i in range(40)
    ]
    store.save_candles_batch(bars)
    loaded = store.load_latest_candles(limit=40)
    assert len(loaded) == 40
    assert loaded[0]["t"] == 1700000000.0
    assert loaded[-1]["c"] == 2505.0 + 39

    store.record_fill({
        "seq": 1,
        "timestamp": 1700001000.0,
        "portfolio_id": "comp_agg",
        "side": "BUY",
        "position_side": "LONG",
        "qty": 2.5,
        "price": 2520.0,
        "realized_pnl": 0.0,
        "reason": "SIGNAL_ENTRY",
    })
    fills = store.load_recent_fills(limit=10)
    assert len(fills) == 1
    assert fills[0]["portfolio_id"] == "comp_agg"
    assert fills[0]["qty"] == 2.5


def test_phase3_dynamic_depth_and_volatility_slippage():
    from src.arena.broker_sim import BrokerSim
    from src.arena.order import OrderSide, OrderType

    broker = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0.0001"))
    p_small = broker.compute_execution_slippage(
        OrderSide.BUY, OrderType.MARKET, Decimal("1.0"), Decimal("2500.00"), Decimal("10.00")
    )
    p_whale = broker.compute_execution_slippage(
        OrderSide.BUY, OrderType.MARKET, Decimal("150.0"), Decimal("2500.00"), Decimal("45.00")
    )
    assert p_whale > p_small > Decimal("2500.00")

    s_small = broker.compute_execution_slippage(
        OrderSide.SELL, OrderType.MARKET, Decimal("1.0"), Decimal("2500.00"), Decimal("10.00")
    )
    s_whale = broker.compute_execution_slippage(
        OrderSide.SELL, OrderType.MARKET, Decimal("150.0"), Decimal("2500.00"), Decimal("45.00")
    )
    assert s_whale < s_small < Decimal("2500.00")


def test_phase4_mtf_trend_confluence_gatekeeper():
    from src.arena.order import OrderSide
    from src.data.live_engine import LiveArenaEngine

    engine = LiveArenaEngine()
    # Populate 60 synthetic 1h bars in a strong uptrend
    engine.candles_1h = [
        {"t": float(i * 3600), "o": 2000.0 + i * 10, "h": 2015.0 + i * 10, "l": 1995.0 + i * 10, "c": 2010.0 + i * 10}
        for i in range(60)
    ]
    engine._update_mtf_regimes({"t": float(60 * 3600), "o": 2600.0, "h": 2620.0, "l": 2595.0, "c": 2615.0})
    assert engine.htf_bias == "BULLISH"
    assert engine.is_entry_permitted_by_mtf(OrderSide.BUY) is True
    assert engine.is_entry_permitted_by_mtf(OrderSide.SELL) is False

    # Populate 60 synthetic 1h bars in a strong downtrend
    engine.candles_1h = [
        {"t": float(i * 3600), "o": 3000.0 - i * 10, "h": 3005.0 - i * 10, "l": 2985.0 - i * 10, "c": 2990.0 - i * 10}
        for i in range(60)
    ]
    engine._update_mtf_regimes({"t": float(60 * 3600), "o": 2400.0, "h": 2405.0, "l": 2380.0, "c": 2385.0})
    assert engine.htf_bias == "BEARISH"
    assert engine.is_entry_permitted_by_mtf(OrderSide.BUY) is False
    assert engine.is_entry_permitted_by_mtf(OrderSide.SELL) is True


def test_phase5_multi_objective_composite_fitness():
    from types import SimpleNamespace
    from src.arena.evolution import GeneticEvolver

    steady_champ = SimpleNamespace(
        roi_pct=Decimal("8.5"),
        sharpe_ratio=2.4,
        sortino_ratio=3.0,
        max_drawdown_pct=Decimal("2.0"),
        closed_trades=18,
        status="ACTIVE",
    )
    reckless_gambler = SimpleNamespace(
        roi_pct=Decimal("9.0"),
        sharpe_ratio=0.4,
        sortino_ratio=0.5,
        max_drawdown_pct=Decimal("18.5"),
        closed_trades=110,
        status="ACTIVE",
    )
    f_steady = GeneticEvolver.calculate_composite_fitness(steady_champ)
    f_reckless = GeneticEvolver.calculate_composite_fitness(reckless_gambler)
    assert f_steady > f_reckless


def test_phase6_modular_view_model_and_state_delta_streaming():
    from src.data.live_engine import LiveArenaEngine, LiveQuote

    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    q = LiveQuote(
        price=Decimal("2600.00"),
        bid=Decimal("2599.90"),
        ask=Decimal("2600.10"),
        high_24h=Decimal("2650.00"),
        low_24h=Decimal("2550.00"),
        volume_24h=Decimal("10000.00"),
        change_24h_pct=Decimal("1.20"),
        source="UnitTest",
        timestamp=1700000000.0,
    )
    engine.latest_quote = q
    engine._update_candle(1700000000.0, Decimal("2600.00"))

    first_payload = engine.get_ui_state_delta(force_full=True)
    assert first_payload["is_delta"] is False
    assert "candles" in first_payload
    assert "fills" in first_payload

    # Consecutive poll with unchanged candle and fills omits redundant arrays
    second_payload = engine.get_ui_state_delta(force_full=False)
    assert second_payload["is_delta"] is True
    assert second_payload["candles_unchanged"] is True
    assert second_payload["fills_unchanged"] is True
    assert "candles" not in second_payload
    assert "fills" not in second_payload


def test_session_state_save_and_restore_and_shutdown_bridge():
    import tempfile
    from src.data.persistence import ArenaStorage
    from src.data.live_engine import LiveArenaEngine
    from src.gui.dashboard import ArenaDashboard, _ArenaBridgeApi
    from src.arena.portfolio import PositionSide

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        db_path = tf.name

    store1 = ArenaStorage(db_path=db_path)
    engine1 = LiveArenaEngine(initial_cash=Decimal("100000.00"), storage=store1)
    engine1.bootstrap_intraday_session()

    # Modify competitor state: simulate trade and generation advancement
    comp = engine1.competitors[0]
    comp.portfolio.cash = Decimal("95000.00")
    comp.portfolio.position_qty = Decimal("2.1500")
    comp.portfolio.position_side = PositionSide.LONG
    comp.portfolio.avg_entry_price = Decimal("2325.50")
    comp.portfolio.realized_pnl = Decimal("1250.00")
    engine1.cadence_sec = 2.5

    # Save session state
    ok = engine1.save_session_state()
    assert ok is True

    # Initialize a new engine from the same DB and verify state restoration
    store2 = ArenaStorage(db_path=db_path)
    engine2 = LiveArenaEngine(initial_cash=Decimal("100000.00"), storage=store2)
    restore_ok = engine2.restore_session_state()
    assert restore_ok is True
    assert engine2.cadence_sec == 2.5

    c2 = engine2.competitors[0]
    assert c2.portfolio.cash == Decimal("95000.00")
    assert c2.portfolio.position_qty == Decimal("2.1500")
    assert c2.portfolio.position_side == PositionSide.LONG
    assert c2.portfolio.avg_entry_price == Decimal("2325.50")
    assert c2.portfolio.realized_pnl == Decimal("1250.00")

    # Test dashboard bridge save, cancel, and shutdown methods. The bridge
    # uses the dashboard's own engine (the current generation); pointing it
    # at engine1 would trip the item-9 generation fence, since engine2 is
    # newer -- a superseded engine must not overwrite the new generation.
    dash = ArenaDashboard(initial_cash=Decimal("100000.00"))
    bridge = _ArenaBridgeApi(dash)

    res_save = bridge.save_session_state()
    assert res_save["status"] == "ok"
    assert res_save["saved"] is True

    dash.closing_prompt_active = True
    res_cancel = bridge.cancel_shutdown_prompt()
    assert res_cancel["status"] == "cancelled"
    assert dash.closing_prompt_active is False

    res_shut = bridge.shutdown(save_progress=True)
    assert res_shut["status"] == "shutting_down"
    assert res_shut["saved"] is True
    assert dash.allow_exit is True

    # Test open_omniroute_console bridge method. webbrowser must be
    # mocked: the unmocked call opened a real Edge tab on every pytest
    # run (2026-11-13: dozens of connection-refused tabs piled up
    # while the gateway was down).
    with patch("webbrowser.open", return_value=True) as mock_open:
        res_console = bridge.open_omniroute_console()
    assert res_console["status"] == "ok"
    assert "20128" in res_console["url"]
    mock_open.assert_called_once()

    # Test automated intel refresh cadence configuration
    assert engine1.intel_refresh_interval_sec == 300.0
    new_interval = engine1.set_intel_refresh_interval(600.0)
    assert new_interval == 600.0
    assert engine1.intel_refresh_interval_sec == 600.0


def test_pause_time_freezing_and_arena_transitions():
    import time
    from pathlib import Path
    from decimal import Decimal
    from src.data.live_engine import LiveArenaEngine

    engine = LiveArenaEngine(initial_cash=Decimal("50000.00"))
    engine.auto_evolve_interval_sec = 3600
    engine.last_evolve_ts = time.time()

    state1 = engine.get_ui_state()
    rem1 = state1["next_evolve_sec"]
    assert rem1 > 0

    # Pause the engine
    engine.paused = True
    assert engine.paused is True
    assert engine._pause_start_ts is not None

    state_paused1 = engine.get_ui_state()
    assert state_paused1["paused"] is True

    time.sleep(0.05)
    state_paused2 = engine.get_ui_state()
    assert state_paused2["paused"] is True
    # In paused state, countdown must remain completely frozen
    assert state_paused2["next_evolve_sec"] == state_paused1["next_evolve_sec"]

    # Resume the engine
    prev_evolve_ts = engine.last_evolve_ts
    engine.paused = False
    assert engine.paused is False
    assert engine._pause_start_ts is None
    # last_evolve_ts must have been compensated forward
    assert engine.last_evolve_ts >= prev_evolve_ts

    # Verify frontend assets have the required elements and CSS classes
    assets_dir = Path(__file__).resolve().parent.parent / "src" / "gui" / "assets"
    html = (assets_dir / "index.html").read_text(encoding="utf-8")
    css = (assets_dir / "app.css").read_text(encoding="utf-8")

    assert "globalCursorBackdrop" in html
    assert "global-cursor-backdrop" in css
    assert "arena-entering" in css
    assert "arenaFadeIn" in css


def test_window_startup_foreground_configuration():
    """Validates that the pywebview window is created maximized (not
    always-on-top) and the startup foreground-activation logic exists in
    dashboard.run. (The Pin / always-on-top toggle was removed 2026-11-14;
    the startup pop-to-front-then-release logic is separate and stays.)"""
    from src.gui.dashboard import ArenaDashboard
    import inspect

    dash = ArenaDashboard(initial_cash=Decimal("100000.00"))

    # Verify dashboard.py source contains maximized=True, on_top=False, and startup foreground maximize logic
    dash_src = inspect.getsource(dash.run)
    assert "on_top=False" in dash_src
    assert "maximized=True" in dash_src
    assert "SW_MAXIMIZE" in dash_src
    assert "HWND_NOTOPMOST" in dash_src
    assert "_activate_foreground_startup" in dash_src


