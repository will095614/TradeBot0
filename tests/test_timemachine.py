from decimal import Decimal
import os
import pytest
from src.data.eth_feed import CandleBar
from src.data.timemachine import TimeMachineArena

def test_timemachine_simulation_with_synthetic_bars():
    arena = TimeMachineArena(symbol="ETH/USD", initial_cash=Decimal("500000.00"))
    
    # Create 30 synthetic candle bars with an upward trend then downward trend
    bars = []
    base_price = Decimal("2500.00")
    for i in range(40):
        if i < 20:
            price = base_price + Decimal(i * 15)  # Rising
            ema_fast = price - Decimal("5.00")
            ema_slow = price - Decimal("20.00")
            rsi = Decimal("55.00")
        else:
            price = base_price + Decimal(20 * 15) - Decimal((i - 20) * 20) # Falling
            ema_fast = price - Decimal("10.00")
            ema_slow = price + Decimal("5.00")
            rsi = Decimal("40.00")
            
        bar = CandleBar(
            timestamp=1000.0 + (i * 900),
            open_=price - Decimal("2.00"),
            high=price + Decimal("5.00"),
            low=price - Decimal("5.00"),
            close=price,
            volume=Decimal("150.0"),
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            rsi=rsi,
            atr=Decimal("25.00")
        )
        bars.append(bar)
        
    rankings = arena.run_simulation(bars)
    assert len(rankings) == 6
    for r in rankings:
        assert r.rank in [1, 2, 3, 4, 5, 6]
        assert r.equity > Decimal("0")
        
    assert os.path.exists(os.path.join("memory", "arena_report.md"))


def test_timemachine_evolution_preserves_portfolio():
    arena = TimeMachineArena(symbol="ETH/USD", initial_cash=Decimal("500000.00"))
    
    # 25 synthetic candle bars
    bars = []
    base_price = Decimal("2500.00")
    for i in range(25):
        price = base_price + Decimal(i * 10)
        bar = CandleBar(
            timestamp=1000.0 + (i * 900),
            open_=price - Decimal("2.00"),
            high=price + Decimal("4.00"),
            low=price - Decimal("4.00"),
            close=price,
            volume=Decimal("100.0"),
            ema_fast=price - Decimal("5.00"),
            ema_slow=price - Decimal("15.00"),
            rsi=Decimal("56.00"),
            atr=Decimal("20.00")
        )
        bars.append(bar)
        
    rankings_g1 = arena.run_simulation(bars)
    assert len(rankings_g1) == 6
    
    # Evolve to Generation 2 with preserve_portfolio=True (Scheme 1)
    logs = arena.evolve_next_generation(rankings_g1, preserve_portfolio=True)
    assert len(logs) == 6
    
    # Check that generation advanced and portfolio positions/cash remain intact
    gen = max(c.genome.generation for c in arena.competitors)
    assert gen == 2
    for c in arena.competitors:
        assert c.portfolio.total_equity > Decimal("0")
        assert c.portfolio_id in arena.broker.competitor_caps


def test_r_multiple_dynamic_budget_sizing():
    from src.competitors.conservative import ConservativeCompetitor
    from src.arena.broker_sim import BrokerSim
    broker = BrokerSim(symbol="ETH/USD")
    comp = ConservativeCompetitor(initial_cash=Decimal("3000.00"))
    broker.register_portfolio(comp.portfolio, max_position_ratio=comp.max_position_ratio)
    
    # 1. Wide stop: stop loss is $200 away (risk_qty = 30 / 200 = 0.1500 ETH)
    entry = Decimal("3000.00")
    wide_stop = Decimal("2800.00")
    qty_wide = comp.compute_r_multiple_qty(entry, wide_stop, broker)
    
    # 2. Narrow stop: stop loss is $30 away (risk_qty = 30 / 30 = 1.0000 ETH, capped by 25% cap = 0.2500 ETH)
    narrow_stop = Decimal("2970.00")
    qty_narrow = comp.compute_r_multiple_qty(entry, narrow_stop, broker)
    
    # Wide stop must result in strictly smaller position than narrow stop
    assert qty_wide < qty_narrow
    assert qty_wide == Decimal("0.1500")
    assert qty_narrow == Decimal("0.2500")
    
    # Max loss at wide stop: (entry - stop) * qty <= risk_budget + buffer
    loss_at_wide_stop = (entry - wide_stop) * qty_wide
    risk_budget = comp.portfolio.total_equity * comp.genome.risk_per_trade_pct
    assert loss_at_wide_stop <= (risk_budget + Decimal("1.00"))


def test_monte_carlo_ev_gate_odds_evaluation():
    from src.data.timemachine import MonteCarloOddsEvaluator
    evaluator = MonteCarloOddsEvaluator(seed=19)
    
    # Reasonable scalper bracket: 1.5R target with realistic stop
    odds_pass = evaluator.evaluate_bracket(
        entry_price=Decimal("2500.00"),
        stop_loss=Decimal("2485.00"),
        take_profit=Decimal("2525.00"),
        atr=Decimal("4.00")
    )
    assert odds_pass.passed is True
    assert odds_pass.expected_r >= -0.05
    assert odds_pass.r_multiple > 1.0
    d = odds_pass.to_dict()
    assert "verdict" in d
    assert "expected_r" in d
    
    # Hostile / absurd bracket: stop is $5 away, but target is $200 away (40R in 30 minutes)
    odds_absurd = evaluator.evaluate_bracket(
        entry_price=Decimal("2500.00"),
        stop_loss=Decimal("2495.00"),
        take_profit=Decimal("2700.00"),
        atr=Decimal("2.00"),
        n_steps=30
    )
    assert odds_absurd.passed is False
    assert "Blocked" in odds_absurd.verdict


