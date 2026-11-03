from decimal import Decimal
import pytest
from src.arena.order import OrderTicket, OrderSide, OrderType
from src.arena.portfolio import Portfolio
from src.arena.broker_sim import BrokerSim

def test_broker_sim_multi_portfolio_simultaneous_execution():
    broker = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0.0"))
    
    p1 = Portfolio("p1", "Aggressive", initial_cash=Decimal("3000.00"))
    p2 = Portfolio("p2", "Conservative", initial_cash=Decimal("3000.00"))
    
    broker.register_portfolio(p1, max_position_ratio=Decimal("0.8"))
    broker.register_portfolio(p2, max_position_ratio=Decimal("0.3"))
    
    # Tick arrives at $2500.00
    broker.on_tick(price=Decimal("2500.00"), timestamp=100.0)
    
    # Both portfolios submit market BUY orders at the exact same tick
    t1 = OrderTicket("p1", "ETH/USD", OrderSide.BUY, OrderType.MARKET, qty=Decimal("0.8"), timestamp=100.0)
    t2 = OrderTicket("p2", "ETH/USD", OrderSide.BUY, OrderType.MARKET, qty=Decimal("0.3"), timestamp=100.0)
    
    fill1 = broker.submit_order(t1)
    fill2 = broker.submit_order(t2)
    
    assert fill1 is not None and fill1.price == Decimal("2500.00")
    assert fill2 is not None and fill2.price == Decimal("2500.00")
    
    assert p1.position_qty == Decimal("0.8000")
    assert p2.position_qty == Decimal("0.3000")

def test_broker_sim_bracket_stop_loss_trigger():
    broker = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0.0"))
    p = Portfolio("p1", "Aggressive", initial_cash=Decimal("3000.00"))
    broker.register_portfolio(p, max_position_ratio=Decimal("0.8"))
    
    # Entry at $2500 with Stop at $2450
    broker.on_tick(price=Decimal("2500.00"), timestamp=100.0)
    ticket = OrderTicket(
        portfolio_id="p1",
        symbol="ETH/USD",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        qty=Decimal("0.5"),
        stop_loss=Decimal("2450.00"),
        timestamp=100.0
    )
    fill = broker.submit_order(ticket)
    assert fill is not None
    assert p.position_qty == Decimal("0.5000")
    
    # Tick drops: high $2480, low $2440 (pierces $2450 stop)
    stop_fills = broker.on_tick(price=Decimal("2445.00"), high=Decimal("2480.00"), low=Decimal("2440.00"), timestamp=101.0)
    
    assert len(stop_fills) == 1
    assert stop_fills[0].side == OrderSide.SELL
    assert p.position_qty == Decimal("0.0000")
    assert p.realized_pnl < Decimal("0") # Realized loss taken

def test_broker_sim_position_cap_enforcement():
    broker = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0.0"))
    p = Portfolio("p_cons", "Conservative", initial_cash=Decimal("3000.00"))
    # Max cap 25% of 3000 = $750 max position
    broker.register_portfolio(p, max_position_ratio=Decimal("0.25"))
    broker.on_tick(price=Decimal("2500.00"))
    
    # 0.5 ETH at $2500 = $1250 > $750 cap
    ticket = OrderTicket("p_cons", "ETH/USD", OrderSide.BUY, OrderType.MARKET, qty=Decimal("0.5"))
    rejected_fill = broker.submit_order(ticket)
    assert rejected_fill is None # Successfully rejected by RiskGuard
    assert p.position_qty == Decimal("0.0000")

