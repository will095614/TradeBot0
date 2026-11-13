# Item 1: risk semantics - risk budget and position cap are struck on
# unleveraged total equity. Leverage affects only margin affordability.
from decimal import Decimal

import pytest

from src.arena.broker_sim import BrokerSim
from src.arena.order import OrderSide, OrderTicket, OrderType
from src.arena.portfolio import Portfolio
from src.arena.risk_guard import RiskGuard
from src.competitors.aggressive import AggressiveCompetitor
from src.competitors.atr_dynamic import ATRDynamicCompetitor
from src.competitors.base import CompetitorGenome
from src.competitors.conservative import ConservativeCompetitor
from src.competitors.orb import ORBCompetitor
from src.competitors.trailing_guard import TrailingGuardCompetitor
from src.competitors.session_mean import SessionMeanPullbackCompetitor


def _broker():
    return BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0.0"))


def test_aggressive_stopout_loss_capped_at_risk_pct():
    # Aggressive: 3x leverage, 2.5% risk. A single stop-out must lose <= 2.5% of equity.
    comp = AggressiveCompetitor()
    broker = _broker()
    broker.register_portfolio(comp.portfolio, max_position_ratio=comp.max_position_ratio)
    broker.on_tick(Decimal("2500.00"), timestamp=100.0)
    ticket = comp.evaluate_signal("BUY", Decimal("2500.00"), {"atr": Decimal("35.00")}, broker, 100.0)
    assert ticket is not None
    fill = broker.submit_order(ticket)
    assert fill is not None
    assert fill.qty == Decimal("28.0000")
    notional = fill.qty * Decimal("2500.00")
    assert notional <= Decimal("70000.00")  # 70% position cap on unleveraged equity
    stop_loss = fill.qty * (Decimal("2500.00") - Decimal("2412.50"))
    assert stop_loss <= Decimal("2500.00")  # 2.5% risk budget


def test_risk_budget_ignores_leverage():
    comp = AggressiveCompetitor()  # 3x lev
    broker = _broker()
    qty = comp.compute_r_multiple_qty(Decimal("2500.00"), Decimal("2412.50"), broker)
    # budget 2500 / 87.50 = 28.5714, capped by 70% cap -> 28.0000 (NOT 84)
    assert qty == Decimal("28.0000")


def test_atr_risk_budget_ignores_leverage():
    comp = ATRDynamicCompetitor()  # 2x lev, atr risk 1.5%
    broker = _broker()
    broker.register_portfolio(comp.portfolio, max_position_ratio=comp.max_position_ratio)
    ticket = comp.evaluate_signal("BUY", Decimal("2500.00"), {"atr": Decimal("35.00")}, broker, 100.0)
    assert ticket is not None
    # risk 1500 / 52.50 = 28.5714, capped by 50% cap -> 20.0000
    assert ticket.qty == Decimal("20.0000")


def test_risk_guard_cap_ignores_leverage():
    p = Portfolio("p_cap", "Cap Tester", initial_cash=Decimal("100000.00"),
                  leverage=Decimal("3.0"), leverage_enabled=True)
    # 84 ETH @ $2500 = $210,000 (210% of equity) must be rejected even at 3x leverage.
    big = OrderTicket(portfolio_id="p_cap", symbol="ETH/USD", side=OrderSide.BUY,
                      order_type=OrderType.MARKET, qty=Decimal("84.0000"), timestamp=100.0)
    ok, _reason = RiskGuard.validate_order(big, p, Decimal("0.70"), Decimal("2500.00"))
    assert not ok
    # 28 ETH @ $2500 = $70,000 (70% of equity) is fine.
    small = OrderTicket(portfolio_id="p_cap", symbol="ETH/USD", side=OrderSide.BUY,
                        order_type=OrderType.MARKET, qty=Decimal("28.0000"), timestamp=100.0)
    ok2, _reason2 = RiskGuard.validate_order(small, p, Decimal("0.70"), Decimal("2500.00"))
    assert ok2


def test_genome_rejects_nonsense():
    with pytest.raises(ValueError):
        CompetitorGenome(stop_loss_pct=Decimal("-0.01"))
    with pytest.raises(ValueError):
        CompetitorGenome(position_ratio=Decimal("1.50"))
    with pytest.raises(ValueError):
        CompetitorGenome(position_ratio=Decimal("0.10"))
    with pytest.raises(ValueError):
        CompetitorGenome(risk_per_trade_pct=Decimal("0.50"))
    with pytest.raises(ValueError):
        CompetitorGenome(take_profit_pct=Decimal("0.010"), stop_loss_pct=Decimal("0.015"))
    with pytest.raises(ValueError):
        CompetitorGenome(take_profit_pct=Decimal("0.020"), stop_loss_pct=Decimal("0.015"))
    with pytest.raises(ValueError):
        CompetitorGenome(leverage=Decimal("0"))
    with pytest.raises(ValueError):
        CompetitorGenome(leverage=Decimal("6.0"), leverage_enabled=True)
    with pytest.raises(ValueError):
        CompetitorGenome(atr_target_mult=Decimal("2.0"), atr_stop_mult=Decimal("2.0"))
    with pytest.raises(ValueError):
        CompetitorGenome(cooldown_bars=-1)
    with pytest.raises(ValueError):
        CompetitorGenome(generation=0)


def test_genome_accepts_all_default_genomes():
    for cls in (AggressiveCompetitor, ConservativeCompetitor, ATRDynamicCompetitor,
                TrailingGuardCompetitor, ORBCompetitor, SessionMeanPullbackCompetitor):
        comp = cls()
        assert comp.genome.position_ratio > Decimal("0")
    # Evolution clamp extremes must also pass validation.
    g = CompetitorGenome(
        position_ratio=Decimal("0.75"), risk_per_trade_pct=Decimal("0.030"),
        stop_loss_pct=Decimal("0.035"), take_profit_pct=Decimal("0.065"),
        atr_risk_pct=Decimal("0.025"), atr_stop_mult=Decimal("2.5"),
        atr_target_mult=Decimal("4.5"), trailing_trigger_pct=Decimal("3.5"),
        trailing_distance_pct=Decimal("0.012"), leverage=Decimal("5.0"),
        leverage_enabled=True,
    )
    assert g.position_ratio == Decimal("0.75")
