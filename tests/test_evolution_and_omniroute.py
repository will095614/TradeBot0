from decimal import Decimal
import os
import pytest
from src.arena.broker_sim import BrokerSim
from src.arena.order import OrderTicket, OrderSide, OrderType, ExecutionReason
from src.arena.portfolio import Portfolio
from src.arena.leaderboard import Leaderboard
from src.arena.evolution import GeneticEvolver
from src.ai.omniroute_client import OmniRouteGateway
from src.competitors.aggressive import AggressiveCompetitor
from src.competitors.conservative import ConservativeCompetitor
from src.competitors.atr_dynamic import ATRDynamicCompetitor
from src.competitors.trailing_guard import TrailingGuardCompetitor


def test_exact_take_profit_and_win_rate_calculation():
    broker = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0.0"))
    p = Portfolio("p_tp", "TP Tester", initial_cash=Decimal("3000.00"))
    broker.register_portfolio(p, max_position_ratio=Decimal("0.50"))

    # Enter at $2500 with TP at $2600, SL at $2450
    broker.on_tick(price=Decimal("2500.00"), timestamp=1000.0)
    ticket = OrderTicket(
        portfolio_id="p_tp",
        symbol="ETH/USD",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        qty=Decimal("0.4000"),
        stop_loss=Decimal("2450.00"),
        take_profit=Decimal("2600.00"),
        timestamp=1000.0
    )
    buy_fill = broker.submit_order(ticket)
    assert buy_fill is not None

    # Candle spikes to high $2620 (piercing $2600 TP), even though close pulls back to $2510
    fills = broker.on_tick(
        price=Decimal("2510.00"),
        high=Decimal("2620.00"),
        low=Decimal("2495.00"),
        timestamp=1900.0,
        open_price=Decimal("2505.00")
    )
    assert len(fills) == 1
    tp_fill = fills[0]
    # Must fill at exact $2600.00 Take-Profit limit price, NOT $2510.00 close!
    assert tp_fill.price == Decimal("2600.00")
    assert tp_fill.reason == ExecutionReason.TAKE_PROFIT
    assert tp_fill.realized_pnl > Decimal("0")
    assert p.win_count == 1
    assert Leaderboard.calculate_win_rate(p) == Decimal("100.00")


def test_style_b_genetic_evolution_elitism_and_mutation():
    comp_a = AggressiveCompetitor()
    comp_b = ConservativeCompetitor()
    comp_c = ATRDynamicCompetitor()
    comp_d = TrailingGuardCompetitor()
    competitors = [comp_a, comp_b, comp_c, comp_d]

    broker = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0.0"))
    for c in competitors:
        broker.register_portfolio(c.portfolio, max_position_ratio=c.max_position_ratio)

    # Simulate different equity outcomes
    comp_d.portfolio.cash = Decimal("518000.00")
    comp_d.portfolio.update_market_price(Decimal("2500.00"), timestamp=1000.0)
    comp_b.portfolio.cash = Decimal("505000.00")
    comp_b.portfolio.update_market_price(Decimal("2500.00"), timestamp=1000.0)
    comp_c.portfolio.cash = Decimal("496000.00")
    comp_c.portfolio.update_market_price(Decimal("2500.00"), timestamp=1000.0)
    comp_a.portfolio.cash = Decimal("479000.00")
    comp_a.portfolio.update_market_price(Decimal("2500.00"), timestamp=1000.0)

    rankings = Leaderboard.get_rankings(broker.portfolios)
    assert rankings[0].portfolio_id == "comp_trail"
    assert rankings[1].portfolio_id == "comp_cons"

    old_trail_sl = comp_d.genome.stop_loss_pct
    # Test Scheme 1: Compounded portfolio equity preserved across generations
    logs = GeneticEvolver.evolve_generation(competitors, rankings, preserve_portfolio=True)
    assert len(logs) == 4
    for c in competitors:
        assert c.genome.generation == 2
    assert comp_d.portfolio.total_equity == Decimal("518000.00")
    assert comp_b.portfolio.total_equity == Decimal("505000.00")
    # Champion elite stop loss must be preserved
    assert comp_d.genome.stop_loss_pct == old_trail_sl

    # Test clean reset mode when preserve_portfolio=False
    GeneticEvolver.evolve_generation(competitors, rankings, preserve_portfolio=False)
    for c in competitors:
        assert c.portfolio.total_equity == Decimal("500000.00")
    assert os.path.exists(os.path.join("memory", "arena_history.json"))


def test_omniroute_token_compression_and_quota_fallback():
    gw = OmniRouteGateway(base_url="http://127.0.0.1:59999/v1", daily_token_limit=10000)
    raw = "Please kindly analyze   in order to   essentially evaluate the ETH/USD arena results.\n\n\nThank you."
    compressed, saved = gw.compress_prompt(raw)
    assert len(compressed) < len(raw)
    assert saved > 0

    p = Portfolio("comp_cons", "Conservative", initial_cash=Decimal("3000.00"))
    rankings = Leaderboard.get_rankings({"comp_cons": p})
    report = gw.synthesize_post_mortem(rankings, generation=1, bar_count=100)
    assert "Quant Synthesis" in report
    assert gw.metrics.fallback_count == 1
    assert gw.metrics.quota_remaining_pct == 100.0

