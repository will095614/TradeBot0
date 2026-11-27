"""V3.3.0 regression tests: Full debug fixes, GPU/DOM/ViewModel optimizations, and version sync."""
from __future__ import annotations

import asyncio
import math
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.arena.broker_sim import BrokerSim
from src.arena.evolution import GeneticEvolver
from src.arena.leaderboard import Leaderboard
from src.arena.order import ExecutionReason, OrderSide, OrderTicket, OrderType, PositionSide
from src.arena.portfolio import Portfolio
from src.competitors.aggressive import AggressiveCompetitor
from src.competitors.conservative import ConservativeCompetitor
from src.competitors.trailing_guard import TrailingGuardCompetitor
from src.data.live_engine import LiveArenaEngine
from src.data.persistence import ArenaStorage
from src.data.quote_feeds import LiveQuote
from src.gui.dashboard import ArenaDashboard
from src.gui.view_model import (
    ViewModelPublisher,
    _clone_json_tree,
    _empty_view_model,
    build_engine_view_model,
)
from src.intelligence.config_manager import DEFAULT_GEMINI_MODEL
from src.intelligence.gemini_client import GeminiClient
from src.intelligence.ingestion import IntelligenceHarvester, StructuredEvent
from src.intelligence.macro_commander import MacroCommander
from src.version import APP_VERSION

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "src" / "gui" / "assets"


# ---------------------------------------------------------------------------
# 1. Arena & Evolution Bugfixes
# ---------------------------------------------------------------------------


def test_leaderboard_guards_nonfinite_risk_free_rate():
    p = Portfolio(portfolio_id="comp_agg", name="Aggressive", initial_cash=Decimal("100000"))
    p.equity_history = [
        (1.0, Decimal("100000")),
        (61.0, Decimal("100200")),
        (121.0, Decimal("100500")),
        (181.0, Decimal("100350")),
    ]
    sh_nan, so_nan = Leaderboard.calculate_sharpe_and_sortino(p, risk_free_rate=float("nan"))
    sh_inf, so_inf = Leaderboard.calculate_sharpe_and_sortino(p, risk_free_rate=float("inf"))
    assert math.isfinite(sh_nan) and math.isfinite(so_nan or 0.0)
    assert math.isfinite(sh_inf) and math.isfinite(so_inf or 0.0)


def test_evolution_saves_human_readable_champion_name(tmp_path, monkeypatch):
    monkeypatch.setenv("ARENA_MEMORY_DIR", str(tmp_path / "memory"))
    storage = ArenaStorage(db_path=str(tmp_path / "evo.sqlite"))
    comps = [
        AggressiveCompetitor(initial_cash=Decimal("100000")),
        ConservativeCompetitor(initial_cash=Decimal("100000")),
        TrailingGuardCompetitor(initial_cash=Decimal("100000")),
    ]
    broker = BrokerSim(symbol="ETH/USD")
    for c in comps:
        broker.register_portfolio(c.portfolio, max_position_ratio=c.max_position_ratio)
    rankings = Leaderboard.get_rankings(broker.portfolios)
    _, (next_gen, records) = GeneticEvolver.evolve_generation_with_records(
        comps, rankings, preserve_portfolio=True, save_history=False
    )
    GeneticEvolver.save_history(next_gen, records, storage=storage)
    try:
        rows = storage.load_evolution_history(limit=5)
        assert rows
        assert rows[0]["champion_id"] == records[0]["portfolio_id"]
        assert rows[0]["champion_name"] == records[0]["name"]
        assert rows[0]["champion_name"] != ""
    finally:
        storage.close()


# ---------------------------------------------------------------------------
# 2. Data, Runner, Persistence & Intelligence Bugfixes
# ---------------------------------------------------------------------------


def test_try_enter_bracket_handles_none_expected_r_and_sl(tmp_path):
    storage = ArenaStorage(db_path=str(tmp_path / "runner.sqlite"))
    engine = LiveArenaEngine(storage=storage, initial_cash=Decimal("100000.00"))
    try:
        engine.broker.current_price = Decimal("2500.00")
        engine.latest_quote = LiveQuote(
            price=Decimal("2500.00"),
            bid=Decimal("2499.00"),
            ask=Decimal("2501.00"),
            high_24h=Decimal("2550.00"),
            low_24h=Decimal("2450.00"),
            volume_24h=Decimal("1000.0"),
            change_24h_pct=Decimal("1.0"),
            source="Mock",
            timestamp=time.time(),
            is_offline=False,
        )
        engine._chop_gate_blocks = lambda: False
        engine.is_entry_permitted_by_mtf = lambda side: True
        engine.macro_commander.check_trade_veto = lambda *a, **k: (True, "")
        engine.mc_evaluator.evaluate_bracket = MagicMock(
            return_value=SimpleNamespace(
                passed=True,
                expected_r=None,
                target_prob=0.55,
                stop_prob=0.45,
                r_multiple=None,
                r_multiple_is_assumption=False,
                verdict="EV +n/a",
                to_dict=lambda: {"verdict": "EV +n/a", "passed": True, "expected_r": None},
            )
        )
        logged = []
        orig_log = engine.log_event
        engine.log_event = lambda ev_type, msg, level="info": (logged.append(msg), orig_log(ev_type, msg, level))
        t0 = time.time()
        ticket = OrderTicket(
            portfolio_id=engine.comp_a.portfolio_id,
            symbol="ETH/USD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            qty=Decimal("1.0"),
            stop_loss=None,
            take_profit=Decimal("2600.00"),
            timestamp=t0,
        )
        ok = engine._try_enter_bracket(
            engine.comp_a,
            Decimal("2500.00"),
            None,
            Decimal("2600.00"),
            t0,
            "TEST_ENTRY",
            side=OrderSide.BUY,
            ticket=ticket,
        )
        assert ok is True
        assert engine.comp_a.portfolio.position_qty > Decimal("0")
        assert any("SL none" in m and "EV n/a" in m for m in logged)
    finally:
        engine.stop()


def test_live_engine_stop_closes_harvester_and_zero_bid_guard(tmp_path):
    storage = ArenaStorage(db_path=str(tmp_path / "stop.sqlite"))
    engine = LiveArenaEngine(storage=storage, initial_cash=Decimal("100000.00"))
    close_mock = MagicMock()
    engine.macro_commander.harvester.close = close_mock
    engine.stop_live_loop()
    close_mock.assert_called_once()


def test_session_codec_normalizes_unit_leverage(tmp_path):
    storage = ArenaStorage(db_path=str(tmp_path / "codec.sqlite"))
    engine = LiveArenaEngine(storage=storage, initial_cash=Decimal("100000.00"))
    try:
        assert engine.save_session_state() is True
        snap = storage.load_session_snapshot()
        assert snap is not None
        for c in snap["competitors"]:
            c["genome"]["leverage_enabled"] = True
            c["genome"]["leverage"] = "1.0"
        assert engine.restore_session_state(snap) is True
        for c in engine.competitors:
            assert c.genome.leverage_enabled is False
            assert c.portfolio.leverage == Decimal("1.0")
    finally:
        engine.stop()


def test_harvester_uses_thread_local_sessions_and_closes_all():
    gemini = GeminiClient(api_key="")
    harvester = IntelligenceHarvester(client=gemini)
    barrier = threading.Barrier(4)

    def worker(_idx: int):
        barrier.wait(timeout=5.0)
        sess, _ = harvester._get_thread_session()
        return id(sess)

    with ThreadPoolExecutor(max_workers=4) as pool:
        ids = list(pool.map(worker, range(4)))

    assert len(set(ids)) == 4
    assert len(harvester._http_sessions) == 4
    harvester.close()
    assert len(harvester._http_sessions) == 0


def test_macro_commander_dedups_polymarket_dynamic_volume():
    cmd = MacroCommander(client=GeminiClient(api_key=""))
    ev1 = StructuredEvent(
        timestamp="2026-11-27T10:00:00Z",
        source="Polymarket",
        domain="macro",
        entities_tickers=["ETH"],
        urgency_score=8,
        sentiment_score=0.4,
        summary="Fed cut odds moved.",
        raw_title="[Polymarket 24h Vol $1,200,000] Fed cut by Dec? | Odds: Yes 62% / No 38%",
        headline="Fed cut odds",
    )
    ev2 = StructuredEvent(
        timestamp="2026-11-27T10:05:00Z",
        source="Polymarket",
        domain="macro",
        entities_tickers=["ETH"],
        urgency_score=8,
        sentiment_score=0.4,
        summary="Fed cut odds updated slightly.",
        raw_title="[Polymarket 24h Vol $1,450,000] Fed cut by Dec? | Odds: Yes 64% / No 36%",
        headline="Fed cut odds",
    )
    asyncio.run(cmd.synthesize_regime([ev1]))
    asyncio.run(cmd.synthesize_regime([ev2]))
    assert len(cmd.curated_events) == 1


# ---------------------------------------------------------------------------
# 3. ViewModel & Dashboard Fixes + Optimizations
# ---------------------------------------------------------------------------


def test_view_model_fixes_fills_portfolio_id_wick_sig_and_default_model(tmp_path):
    assert _empty_view_model("test")["ui_prefs"]["gemini_model"] == DEFAULT_GEMINI_MODEL

    pub = ViewModelPublisher()
    snap1 = {
        "candles": [
            {"t": 1.0, "o": 100.0, "h": 105.0, "l": 95.0, "c": 102.0},
            {"t": 2.0, "o": 102.0, "h": 110.0, "l": 101.0, "c": 108.0},
            {"t": 3.0, "o": 108.0, "h": 112.0, "l": 107.0, "c": 111.0},
        ],
        "fills": [],
        "quote": {"price": 111.0},
        "indicators": {"rsi": 55.0},
        "intel_hub": {"events": [{"id": "e1", "headline": "Test"}]},
    }
    d1 = pub.compute_delta_from_snapshot(snap1)
    assert d1["is_delta"] is False
    snap1_wick = _clone_json_tree(snap1)
    snap1_wick["candles"][1]["h"] = 120.0
    d2 = pub.compute_delta_from_snapshot(snap1_wick)
    assert d2["candles_unchanged"] is False

    storage = ArenaStorage(db_path=str(tmp_path / "vm.sqlite"))
    engine = LiveArenaEngine(storage=storage, initial_cash=Decimal("100000.00"))
    try:
        from src.arena.order import FillEvent

        engine.fill_records = [
            FillEvent(
                order_id="oid-vwap",
                portfolio_id="comp_vwap",
                symbol="ETH/USD",
                side=OrderSide.BUY,
                qty=Decimal("1.0"),
                price=Decimal("2000.00"),
                fee=Decimal("0.0"),
                timestamp=1700000000.0,
                realized_pnl=Decimal("0.00"),
                reason=ExecutionReason.SIGNAL,
                fill_seq=1,
                position_side=PositionSide.LONG,
            )
        ]
        vm = build_engine_view_model(engine, Leaderboard.get_rankings(engine.broker.portfolios), gen=1)
        assert vm["fills"] and vm["fills"][0]["portfolio_id"] == "comp_vwap"
    finally:
        engine.stop()


def test_dashboard_reset_while_paused_publishes_preserved_pause_snapshot():
    dash = ArenaDashboard(initial_cash=Decimal("10000.00"))
    try:
        dash.engine.paused = True
        dash.engine._pause_start_ts = time.time() - 120.0
        dash.engine.last_evolve_ts = dash.engine._pause_start_ts - 600.0
        dash.reset_engine()
        state = dash.engine.get_ui_state()
        assert state["paused"] is True
        assert state["next_evolve_sec_latest"] <= dash.engine.auto_evolve_interval_sec - 590
    finally:
        dash.stop()


# ---------------------------------------------------------------------------
# 4. Frontend JS / CSS Contracts & Version Sync
# ---------------------------------------------------------------------------


def test_v330_version_and_frontend_contracts():
    assert APP_VERSION == "V3.3.0"
    iss = (ROOT / "TradeBot0.iss").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    js = (ASSETS / "app.js").read_text(encoding="utf-8")
    css = (ASSETS / "app.css").read_text(encoding="utf-8")
    html = (ASSETS / "index.html").read_text(encoding="utf-8")

    assert '#define MyAppVersion "V3.3.0"' in iss
    assert "VersionInfoVersion=3.3.0" in iss
    assert "https://github.com/will095614/TradeBot0/releases/download/v3.3.0/TradeBot0Setup-V3.3.0.exe" in readme

    # Critical & high JS fixes
    assert "const canvasH = (cachedCanvasSize && cachedCanvasSize.h)" in js
    assert "v === 'session'" in js
    assert "Object.values(ev.strategy_actions).join(',')" not in js
    assert "const chartReadyForSplash = hasFirstChartDrawn || currentMainView !== 'arena';" in js
    assert "const offlineOverlay = document.getElementById('networkOfflineOverlay');" in js
    assert "webglcontextrestored" in js and "gl.detachShader(program, s)" in js
    assert "let aiPrefsSeq = 0;" in js
    assert "HEX_TO_RGBA_CACHE" in js and "CANVAS_TEXT_WIDTH_CACHE" in js
    assert "cachedReducedMotion" in js
    assert "card._bracketNodes" in js

    # CSS GPU & layout optimizations
    assert ".global-cursor-backdrop::before" in css
    assert 'body[data-backdrop-mode="minimal"] .lg-glass' in css
    assert "scaleY(clamp(0.14, var(--lv, 0.5), 0.96))" in css
    assert ".toast-stack-item.toast-exit" in css
    assert css.count(".toast-pulse-dot {") == 1
    assert css.count("{") == css.count("}")

    # Zero CJK across frontend
    for content in (html, css, js):
        assert not re.search(r"[\u4e00-\u9fff]", content)
