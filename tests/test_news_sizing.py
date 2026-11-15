"""Item 12C tests: news sizing multiplier (C2) - confidence scaling,
per-strategy sensitivity, budget math, SL untouched, TP factor, and the
backtest default of 1.0."""
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from src.arena.broker_sim import BrokerSim
from src.arena.order import OrderSide
from src.competitors.aggressive import AggressiveCompetitor
from src.competitors.base import CompetitorGenome
from src.competitors.conservative import ConservativeCompetitor
from src.competitors.orb import ORBCompetitor
from src.data.live_engine import LiveArenaEngine
from src.intelligence.macro_commander import MacroCommander


def _commander(rm=1.0, conf=0.5):
    mock_client = MagicMock()
    mock_client.is_gateway_online = True
    c = MacroCommander(mock_client)
    c.current_state.risk_multiplier = rm
    c.current_state.confidence = conf
    return c


def _broker():
    return BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0.0"))


def test_no_confidence_means_no_sizing_effect():
    c = _commander(rm=1.5, conf=0.5)
    assert c.news_sizing_multiplier(1.0) == 1.0
    c2 = _commander(rm=0.5, conf=0.5)
    assert c2.news_sizing_multiplier(1.0) == 1.0
    assert c2.news_sizing_multiplier(0.3) == 1.0


def test_sizing_formula_exact_values():
    c = _commander(rm=1.5, conf=1.0)
    assert c.news_sizing_multiplier(1.0) == 1.5
    c2 = _commander(rm=0.5, conf=1.0)
    assert c2.news_sizing_multiplier(1.0) == 0.5
    c3 = _commander(rm=1.5, conf=0.8)
    assert abs(c3.news_sizing_multiplier(1.0) - 1.30) < 1e-9
    c4 = _commander(rm=0.5, conf=0.8)
    assert abs(c4.news_sizing_multiplier(1.0) - 0.70) < 1e-9


def test_per_strategy_sensitivity_scales_the_deviation():
    c = _commander(rm=1.5, conf=1.0)
    assert c.news_sizing_multiplier(1.0) == 1.5   # ORB eats the full move
    assert abs(c.news_sizing_multiplier(0.3) - 1.15) < 1e-9  # CONS eats 30%
    assert c.news_sizing_multiplier(0.0) == 1.0   # news-blind


def test_genome_news_sensitivity_defaults_and_validation():
    assert ORBCompetitor().genome.news_sensitivity == 1.0
    assert AggressiveCompetitor().genome.news_sensitivity == 0.8
    assert ConservativeCompetitor().genome.news_sensitivity == 0.3
    with pytest.raises(ValueError):
        CompetitorGenome(news_sensitivity=1.5)
    with pytest.raises(ValueError):
        CompetitorGenome(news_sensitivity=-0.1)


def test_compute_r_multiple_qty_scales_budget_and_clamps():
    comp = AggressiveCompetitor()
    broker = _broker()
    # No sizing: budget 2500, stop dist 87.50 -> 28.5714, capped at 28.0000.
    assert comp.compute_r_multiple_qty(Decimal("2500.00"), Decimal("2412.50"), broker) == Decimal("28.0000")
    # Sizing 0.5: budget 1250 -> 14.2857; stop-out loss stays within budget.
    qty = comp.compute_r_multiple_qty(Decimal("2500.00"), Decimal("2412.50"), broker, sizing_multiplier=Decimal("0.5"))
    assert qty == Decimal("14.2857")
    assert qty * Decimal("87.50") <= Decimal("1250.00")
    # Sizing below the 0.5 floor clamps to 0.5.
    assert comp.compute_r_multiple_qty(Decimal("2500.00"), Decimal("2412.50"), broker, sizing_multiplier=Decimal("0.1")) == Decimal("14.2857")


def test_evaluate_signal_sizing_shrinks_qty_not_sl():
    comp = AggressiveCompetitor()
    broker = _broker()
    broker.register_portfolio(comp.portfolio, max_position_ratio=comp.max_position_ratio)
    broker.on_tick(Decimal("2500.00"), timestamp=100.0)
    base = comp.evaluate_signal("BUY", Decimal("2500.00"), {"atr": Decimal("35.00")}, broker, 100.0)
    small = comp.evaluate_signal("BUY", Decimal("2500.00"), {"atr": Decimal("35.00")}, broker, 100.0, sizing_multiplier=Decimal("0.5"))
    assert base is not None and small is not None
    assert small.stop_loss == base.stop_loss  # SL is a risk floor, not a mood
    assert small.qty == Decimal("14.2857")
    assert small.qty < base.qty


def test_backtest_default_sizing_is_one():
    comp = AggressiveCompetitor()
    broker = _broker()
    broker.register_portfolio(comp.portfolio, max_position_ratio=comp.max_position_ratio)
    broker.on_tick(Decimal("2500.00"), timestamp=100.0)
    default = comp.evaluate_signal("BUY", Decimal("2500.00"), {"atr": Decimal("35.00")}, broker, 100.0)
    explicit = comp.evaluate_signal("BUY", Decimal("2500.00"), {"atr": Decimal("35.00")}, broker, 100.0, sizing_multiplier=Decimal("1.0"))
    assert default is not None and explicit is not None
    assert default.qty == explicit.qty == Decimal("28.0000")


def _tp_engine(confidence):
    """Fresh engine with a passing MC gate and an optimistic macro state;
    returns the TP price armed by one LONG bracket entry."""
    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    engine.is_bootstrapped = True
    engine.live_orders_enabled = True
    engine.live_atr = Decimal("20.00")
    engine.candles = []
    engine.broker.on_tick(Decimal("2500.00"), timestamp=1000.0)
    mc = MagicMock()
    mc.passed = True
    mc.expected_r = Decimal("1.5")
    mc.green_prob = Decimal("0.6")
    mc.neither_prob = Decimal("0.1")
    mc.decided_win_rate = Decimal("0.6")
    mc.verdict = "PASS"
    mc.to_dict.return_value = {}
    engine.macro_commander.current_state.directional_bias = "LONG_ONLY"
    engine.macro_commander.current_state.risk_multiplier = 1.5
    engine.macro_commander.current_state.confidence = confidence
    with patch.object(engine, "is_entry_permitted_by_mtf", return_value=True), \
            patch.object(engine.mc_evaluator, "evaluate_bracket", return_value=mc):
        ok = engine._try_enter_bracket(
            engine.comp_a, Decimal("2500.00"), Decimal("2412.50"),
            Decimal("2600.00"), 1000.0, "TEST", side=OrderSide.BUY,
        )
    assert ok is True
    return engine.broker.active_targets["comp_agg"].price


def test_tp_stretch_uses_sizing_mult_not_raw_rm():
    # Full confidence: AGG sensitivity 0.8 -> sizing 1.40 -> TP factor 2.80:
    # 2500 + 87.50 * 2.80 = 2745.00.
    assert _tp_engine(1.0) == Decimal("2745.00")
    # No confidence: sizing 1.0 -> no stretch, TP stays as given.
    assert _tp_engine(0.5) == Decimal("2600.00")
