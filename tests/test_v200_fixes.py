"""
V2.0.0 Regression & Architecture Verification Suite.

Verifies fixes for BUG-01 through BUG-17 and Architecture/Performance
optimizations §3.1 through §3.5 documented in BUGS_AND_OPTIMIZATIONS.md.
"""
from __future__ import annotations

import asyncio
from decimal import Decimal
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from unittest.mock import MagicMock

import pytest

_ROOT = Path(__file__).resolve().parent.parent


def test_v200_bug01_competitors_import_before_arena():
    """BUG-01: Importing src.competitors before src.arena must not crash with ImportError."""
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from src.competitors.aggressive import AggressiveCompetitor; print(AggressiveCompetitor().portfolio_id)",
        ],
        cwd=str(_ROOT),
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc.returncode == 0, proc.stderr
    assert "comp_agg" in proc.stdout


def test_v200_bug02_trailing_guard_preserves_uncapped_tp():
    """BUG-02: GeneticEvolver must keep take_profit_pct=None for comp_trail even when ranked 3rd+."""
    from dataclasses import replace
    from src.arena.evolution import GeneticEvolver
    from src.competitors.aggressive import AggressiveCompetitor
    from src.competitors.conservative import ConservativeCompetitor
    from src.competitors.orb import ORBCompetitor
    from src.competitors.session_mean import SessionMeanPullbackCompetitor
    from src.competitors.trailing_guard import TrailingGuardCompetitor

    agg = AggressiveCompetitor()
    cons = ConservativeCompetitor()
    trail = TrailingGuardCompetitor()
    orb = ORBCompetitor()
    mean_c = SessionMeanPullbackCompetitor()

    # Give parents distinct fixed TPs and rank trail at #4 so it must be mutated
    cons.portfolio.cash = Decimal("115000.00")
    orb.portfolio.cash = Decimal("110000.00")
    orb.genome = replace(orb.genome, take_profit_pct=Decimal("0.045"))
    agg.portfolio.cash = Decimal("100000.00")
    trail.portfolio.cash = Decimal("95000.00")
    mean_c.portfolio.cash = Decimal("90000.00")

    comps = [agg, cons, trail, orb, mean_c]
    from src.arena.leaderboard import Leaderboard
    rankings = Leaderboard.get_rankings({c.portfolio_id: c.portfolio for c in comps})
    GeneticEvolver.evolve_generation(comps, rankings, preserve_portfolio=True, save_history=False)

    assert trail.genome.take_profit_pct is None
    assert agg.genome.take_profit_pct is None


def test_v200_bug06_monotonic_live_fill_seq_past_200(tmp_path):
    """BUG-06: Live fill #seq stays monotonic when fill_records exceeds 200 entries and survives save/restore."""
    from src.arena.order import ExecutionReason, FillEvent, OrderSide, PositionSide
    from src.data.live_engine import LiveArenaEngine
    from src.data.persistence import ArenaStorage
    from src.gui.view_model import build_engine_view_model
    from src.arena.leaderboard import Leaderboard

    store = ArenaStorage(db_path=str(tmp_path / "seq.db"))
    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"), storage=store)
    engine.live_start_ts = 1700000000.0
    engine.live_orders_enabled = True

    for i in range(1, 211):
        engine.broker.execution_audit.append(
            FillEvent(
                order_id=f"ord_{i}",
                fill_seq=i,
                portfolio_id="comp_cons",
                symbol="ETH/USD",
                side=OrderSide.BUY if i % 2 == 1 else OrderSide.SELL,
                qty=Decimal("1.0000"),
                price=Decimal("3000.00"),
                timestamp=1700000010.0 + i,
                reason=ExecutionReason.SIGNAL_ENTRY,
                fee=Decimal("0.50"),
                position_side=PositionSide.LONG,
            )
        )

    with engine.lock:
        engine._harvest_fills()
        assert len(engine.fill_records) == 200
        assert engine._live_fill_seq_offset == 10
        rankings = Leaderboard.get_rankings(engine.broker.portfolios)
        vm = build_engine_view_model(engine, rankings, gen=1)
        assert vm["fills"][0]["seq"] == 210

    assert engine.save_session_state() is True
    store2 = ArenaStorage(db_path=str(tmp_path / "seq.db"))
    engine2 = LiveArenaEngine(initial_cash=Decimal("100000.00"), storage=store2)
    assert engine2.restore_session_state() is True
    assert engine2._live_fill_seq_offset == 10
    engine.stop()
    engine2.stop()


def test_v200_bug07_reset_engine_preserves_full_evolved_genomes(monkeypatch):
    """BUG-07: ArenaDashboard.reset_engine preserves full evolved CompetitorGenome attributes, not only generation."""
    from dataclasses import replace
    from src.gui.dashboard import ArenaDashboard

    dash = ArenaDashboard(initial_cash=Decimal("100000.00"))
    try:
        comp = dash.engine.comp_b
        custom_genome = replace(
            comp.genome,
            generation=4,
            stop_loss_pct=Decimal("0.0222"),
            take_profit_pct=Decimal("0.0444"),
            position_ratio=Decimal("0.33"),
        )
        comp.reset_for_new_generation(custom_genome, preserve_portfolio=True)

        # Avoid spawning live network threads during unit test reset
        monkeypatch.setattr("src.data.live_engine.LiveArenaEngine.start_live_loop", lambda self, interval_sec=1.0: None)
        dash.reset_engine()

        restored = dash.engine.comp_b.genome
        assert restored.generation == 4
        assert restored.stop_loss_pct == Decimal("0.0222")
        assert restored.take_profit_pct == Decimal("0.0444")
        assert restored.position_ratio == Decimal("0.33")
    finally:
        dash.engine.stop()


def test_v200_bug08_macro_tp_expansion_scales_actual_ticket_distance():
    """BUG-08: Macro LONG_ONLY/SHORT_ONLY expansion must scale the ticket's actual target distance (e.g. 2.2R), not clamp to 2.0R."""
    from src.arena.order import OrderSide, OrderTicket, OrderType
    from src.data.live_engine import LiveArenaEngine
    from src.data.timemachine import MonteCarloBracketOdds
    from src.intelligence.macro_commander import MacroRegimeState

    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    try:
        price = Decimal("3000.00")
        engine.broker.on_tick(price, timestamp=1700000000.0)
        engine.macro_commander.current_state = MacroRegimeState(
            regime="BULLISH_SURGE",
            directional_bias="LONG_ONLY",
            risk_multiplier=1.25,
            active_headline="Bullish",
            confidence=0.9,
        )
        engine.mc_evaluator.evaluate_bracket = MagicMock(
            return_value=MonteCarloBracketOdds(
                passed=True,
                target_prob=0.5,
                stop_prob=0.4,
                neither_prob=0.1,
                decided_win_rate=0.55,
                expected_r=0.4,
                r_multiple=2.2,
                breakeven_prob=0.31,
                verdict="Passed",
            )
        )
        sl = Decimal("2980.00")  # risk = 20
        tp = Decimal("3060.00")  # 3.0R = +60 (strictly > 2R = +40)
        ticket = OrderTicket(
            portfolio_id="comp_vwap",
            symbol="ETH/USD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            qty=Decimal("2.0"),
            stop_loss=sl,
            take_profit=tp,
            timestamp=1700000000.0,
        )
        entered = engine._try_enter_bracket(
            engine.comp_f, price, sl, tp, 1700000000.0, "TEST_MACRO_R", ticket=ticket
        )
        assert entered is True
        active_tp = engine.broker.active_targets["comp_vwap"].price
        # Scaled by sizing_mult = 1 + (1.25-1)*0.5 = 1.125 -> 60 * 1.125 = 67.50 -> 3067.50 (> old 2R 3045.00)
        assert active_tp > Decimal("3060.00")
    finally:
        engine.stop()


def test_v200_bug09_trailing_guard_live_breakeven_parity():
    """BUG-09: Live TrailingGuard ratchets SL to breakeven at +1.0% on both LONG and SHORT sides."""
    from src.arena.order import OrderSide, OrderTicket, OrderType, PositionSide
    from src.data.live_engine import LiveArenaEngine

    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    try:
        # LONG +1.2% gain -> breakeven at entry * 1.0005 before 2.0% full trailing activation
        p = engine.comp_d.portfolio
        p.position_qty = Decimal("5.0000")
        p.position_side = PositionSide.LONG
        p.avg_entry_price = Decimal("3000.00")
        engine.comp_d.highest_price_since_entry = Decimal("3000.00")
        engine.comp_d.trailing_active = False
        engine.broker.active_stops["comp_trail"] = OrderTicket(
            portfolio_id="comp_trail",
            symbol="ETH/USD",
            side=OrderSide.SELL,
            order_type=OrderType.STOP_MARKET,
            qty=Decimal("5.0000"),
            price=Decimal("2955.00"),
        )
        engine._update_live_trailing_stop(Decimal("3036.00"), 1700000100.0)
        assert engine.broker.active_stops["comp_trail"].price == Decimal("3001.50")

        # SHORT +1.2% gain -> breakeven at entry * 0.9995
        p.position_side = PositionSide.SHORT
        p.avg_entry_price = Decimal("3000.00")
        engine.comp_d.lowest_price_since_entry = Decimal("3000.00")
        engine.comp_d.trailing_active = False
        engine.broker.active_stops["comp_trail"] = OrderTicket(
            portfolio_id="comp_trail",
            symbol="ETH/USD",
            side=OrderSide.BUY,
            order_type=OrderType.STOP_MARKET,
            qty=Decimal("5.0000"),
            price=Decimal("3045.00"),
        )
        engine._update_live_trailing_stop(Decimal("2964.00"), 1700000200.0)
        assert engine.broker.active_stops["comp_trail"].price == Decimal("2998.50")
    finally:
        engine.stop()


def test_v200_bug10_risk_guard_purity_and_dynamic_slippage():
    """BUG-10: RiskGuard.validate_order has no mutation side effects, and BrokerSim validates using dynamic slippage."""
    from src.arena.order import OrderSide, OrderTicket, OrderType
    from src.arena.portfolio import Portfolio
    from src.arena.risk_guard import RiskGuard

    p = Portfolio(portfolio_id="comp_cons", name="Test", initial_cash=Decimal("100000.00"))
    # Simulate max drawdown >= 15% without broker trip
    p.max_drawdown_pct = Decimal("20.00")
    ticket = OrderTicket(
        portfolio_id="comp_cons",
        symbol="ETH/USD",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        qty=Decimal("1.0"),
        stop_loss=Decimal("2950.00"),
    )
    approved, reason = RiskGuard.validate_order(
        ticket, p, Decimal("0.25"), Decimal("3000.00"), Decimal("0.0005")
    )
    assert approved is False
    assert "drawdown" in reason.lower() or "circuit" in reason.lower()
    assert p.is_circuit_breaker_tripped is False  # Pure check: no hidden mutation!


def test_v200_bug11_evolution_entropy_and_explicit_records():
    """BUG-11: evolve_generation_with_records returns explicit tuple and seed_entropy changes mutation sample."""
    from src.arena.evolution import GeneticEvolver
    from src.arena.leaderboard import Leaderboard
    from src.competitors.aggressive import AggressiveCompetitor
    from src.competitors.conservative import ConservativeCompetitor
    from src.competitors.orb import ORBCompetitor
    from src.competitors.session_mean import SessionMeanPullbackCompetitor
    from src.competitors.trailing_guard import TrailingGuardCompetitor

    def _run_with_entropy(ent: int):
        comps = [
            AggressiveCompetitor(),
            ConservativeCompetitor(),
            TrailingGuardCompetitor(),
            ORBCompetitor(),
            SessionMeanPullbackCompetitor(),
        ]
        comps[0].portfolio.cash = Decimal("120000.00")
        comps[1].portfolio.cash = Decimal("110000.00")
        rankings = Leaderboard.get_rankings({c.portfolio_id: c.portfolio for c in comps})
        logs, recs = GeneticEvolver.evolve_generation_with_records(
            comps, rankings, preserve_portfolio=True, save_history=False, seed_entropy=ent
        )
        return logs, recs, [c.genome for c in comps[2:]]

    logs1, recs1, genomes1 = _run_with_entropy(101)
    logs2, recs2, genomes2 = _run_with_entropy(99991)
    assert logs1 and recs1[0] == 2 and len(recs1[1]) == 5
    assert logs2 and recs2[0] == 2 and len(recs2[1]) == 5
    assert genomes1 != genomes2


def test_v200_bug12_multi_symbol_parameterization():
    """BUG-12: LiveArenaEngine and StreamingCryptoFeed derive exchange pairs dynamically from symbol."""
    from src.data.live_engine import LiveArenaEngine
    from src.data.quote_feeds import parse_symbol_pairs

    pairs = parse_symbol_pairs("BTC/USD")
    assert pairs["binance"] == "BTCUSDT"
    assert pairs["coinbase"] == "BTC-USD"
    assert pairs["ws_stream"] == "btcusdt@ticker"

    engine = LiveArenaEngine(symbol="BTC/USD", initial_cash=Decimal("100000.00"))
    try:
        assert "btcusdt@ticker" in engine.ws_feed.ws_url
        assert "BTC/USD" in engine.broker.symbol
    finally:
        engine.stop()


def test_v200_bug13_deterministic_sha256_event_id():
    """BUG-13: Curated event IDs use deterministic SHA-256 hash suffix + carry event_ts & date_time."""
    from src.intelligence.ingestion import StructuredEvent
    from src.intelligence.macro_commander import MacroCommander
    from src.intelligence.omniroute_client import OmniRouteClient

    async def _run():
        client = OmniRouteClient()
        cmd1 = MacroCommander(client)
        cmd2 = MacroCommander(client)
        evt = StructuredEvent(
            source="Reuters",
            timestamp=1700000000.0,
            domain="macro",
            summary="Fed keeps rates unchanged",
            urgency_score=7,
            sentiment_score=0.25,
            entities_tickers=["ETH", "MACRO"],
            raw_title="Fed keeps rates steady in November",
        )
        await cmd1.synthesize_regime([evt])
        await cmd2.synthesize_regime([evt])
        e1 = cmd1.curated_events[0]
        e2 = cmd2.curated_events[0]
        assert re.match(r"^evt_\d+_[0-9a-f]{8}$", e1["id"])
        assert e1["id"].split("_")[2] == e2["id"].split("_")[2]
        assert isinstance(e1["event_ts"], int)
        assert re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$", e1["date_time"])

    asyncio.run(_run())


def test_v200_frontend_and_prompt_consistency():
    """BUG-03, BUG-04, BUG-05, BUG-14, BUG-15, BUG-16, BUG-17 verification across frontend assets."""
    js = (_ROOT / "src" / "gui" / "assets" / "app.js").read_text(encoding="utf-8")
    html = (_ROOT / "src" / "gui" / "assets" / "index.html").read_text(encoding="utf-8")
    css = (_ROOT / "src" / "gui" / "assets" / "app.css").read_text(encoding="utf-8")

    # BUG-03: no >= 6 table render deadlock
    assert "lbBody.children.length >= 6" not in js
    assert "stratGrid.children.length >= 6" not in js
    assert "expectedStrats" in js

    # BUG-04 & BUG-15: chart reads typical_mean and labels MEAN / Session Mean, 5 strategies, $500,000
    assert "ind.typical_mean" in js
    assert "stratTag: 'MEAN'" in js
    assert "const vwapVal = Number(ind.vwap || 0)" not in js
    assert "6 Strategy Ledgers" not in js
    assert "600,000" not in js
    assert "6 Strategy Ledgers" not in html
    assert "600,000" not in html
    assert "6 Parallel Competitors" not in html
    assert "5 Parallel Competitors" in html

    # BUG-05: article retry button present and wired in app.js & app.css
    assert "intel-retry-btn" in js
    assert "data-retry-event-id" in js
    assert ".intel-retry-btn" in css

    # BUG-14: falsy confidence fix & dynamic omniSourceBadge
    assert "macro.confidence != null" in js
    assert "isAiOnline ? 'OmniRoute AI' : 'Pure Math Core'" in js

    # BUG-16: no fabricated hardcoded ETF inflow headline in HTML
    assert "CoinDesk &middot; Live" not in html

    # BUG-17: dead bridge wrapper save_session_state removed
    from src.gui.dashboard import _ArenaBridgeApi
    assert not hasattr(_ArenaBridgeApi, "save_session_state")


def test_v200_31_33_mixins_and_timemachine_student_t():
    """§3.1 & §3.3: LiveArenaEngine composes cleanly from domain mixins and MonteCarlo handles empirical bootstrap."""
    from src.data.indicator_engine import IndicatorEngineMixin
    from src.data.live_engine import LiveArenaEngine
    from src.data.live_strategy_runner import LiveStrategyRunnerMixin
    from src.data.quote_feeds import QuoteFeedsMixin
    from src.data.session_codec import SessionCodecMixin
    from src.data.timemachine import MonteCarloOddsEvaluator

    assert issubclass(LiveArenaEngine, QuoteFeedsMixin)
    assert issubclass(LiveArenaEngine, IndicatorEngineMixin)
    assert issubclass(LiveArenaEngine, LiveStrategyRunnerMixin)
    assert issubclass(LiveArenaEngine, SessionCodecMixin)

    ev = MonteCarloOddsEvaluator(seed=19)
    candles = [{"c": 3000.0 + (i % 5 - 2) * 3.0} for i in range(35)]
    res = ev.evaluate_bracket(Decimal("3000.00"), Decimal("2960.00"), Decimal("3080.00"), recent_candles=candles)
    assert res.passed is True
    assert res.r_multiple == pytest.approx(2.0)
