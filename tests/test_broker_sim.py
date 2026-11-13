from decimal import Decimal
import pytest
from src.arena.order import OrderTicket, OrderSide, OrderType, ExecutionReason, PositionSide
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


def test_broker_sim_leverage_liquidation_protection():
    from src.arena.order import ExecutionReason
    from src.arena.portfolio import PositionSide
    broker = BrokerSim(symbol="BTC/USD", slippage_pct=Decimal("0.0"))
    p = Portfolio(
        "p_lev",
        "LeveragedTrader",
        initial_cash=Decimal("10000.00"),
        leverage=Decimal("3.0"),
        leverage_enabled=True
    )
    broker.register_portfolio(p, max_position_ratio=Decimal("0.90"))

    # Short 0.1 BTC at $80,000 (notional $8,000 <= 90% cap $9,000; margin locked = $2,666.67).
    # A long-side liquidation can no longer be built under the unleveraged cap:
    # a single long can lose at most its notional, which the cap keeps below the
    # liquidation threshold - so the squeeze is tested on the short side instead.
    broker.on_tick(price=Decimal("80000.00"), timestamp=100.0)
    ticket = OrderTicket("p_lev", "BTC/USD", OrderSide.SELL, OrderType.MARKET, qty=Decimal("0.1"), timestamp=100.0)
    fill = broker.submit_order(ticket)
    assert fill is not None
    assert p.position_qty == Decimal("0.1000")
    assert p.position_side == PositionSide.SHORT
    assert p.margin_locked == Decimal("2666.67")

    # Violent short squeeze: BTC rips to $180,000
    # Unrealized loss = (180,000 - 80,000) * 0.1 = -$10,000
    # Total equity = $10,000 - $10,000 - fee = ~-$4 <= 10% of $2,666.67 ($266.67)
    fills = broker.on_tick(price=Decimal("180000.00"), timestamp=101.0)
    assert len(fills) == 1
    assert fills[0].reason == ExecutionReason.LIQUIDATION
    assert p.position_qty == Decimal("0.0000")
    assert p.is_circuit_breaker_tripped is True



def test_limit_buy_waits_until_price_reaches_limit():
    """Item 5: a BUY LIMIT must not fill above its limit price."""
    broker = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0.0"))
    p = Portfolio("p1", "Aggressive", initial_cash=Decimal("3000.00"))
    broker.register_portfolio(p, max_position_ratio=Decimal("0.8"))
    broker.on_tick(price=Decimal("2500.00"), timestamp=100.0)

    ticket = OrderTicket("p1", "ETH/USD", OrderSide.BUY, OrderType.LIMIT,
                         qty=Decimal("0.1"), price=Decimal("2400.00"), timestamp=101.0)
    assert broker.submit_order(ticket) is None  # 2500 > 2400: not triggered
    assert p.position_qty == Decimal("0.0000")
    assert ticket.order_id in broker.pending_orders
    assert broker.rejection_audit == []  # parked, not rejected

    # Bar dips to 2440: still above the limit, stays parked.
    fills = broker.on_tick(price=Decimal("2450.00"), high=Decimal("2460.00"),
                           low=Decimal("2440.00"), timestamp=102.0)
    assert fills == []
    assert ticket.order_id in broker.pending_orders

    # Bar touches 2390: limit hit, fills at the limit price (not the low).
    fills = broker.on_tick(price=Decimal("2395.00"), high=Decimal("2405.00"),
                           low=Decimal("2390.00"), timestamp=103.0)
    assert len(fills) == 1
    assert fills[0].price == Decimal("2400.00")
    assert p.position_qty == Decimal("0.1000")
    assert ticket.order_id not in broker.pending_orders


def test_limit_sell_fills_immediately_when_already_marketable():
    """Item 5: a LIMIT already through the market fills at once, at the limit price."""
    broker = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0.0"))
    p = Portfolio("p1", "Aggressive", initial_cash=Decimal("3000.00"))
    broker.register_portfolio(p, max_position_ratio=Decimal("0.8"))
    broker.on_tick(price=Decimal("2500.00"), timestamp=100.0)

    # SELL LIMIT 2400 while market is 2500: already marketable, fills now at 2400.
    ticket = OrderTicket("p1", "ETH/USD", OrderSide.SELL, OrderType.LIMIT,
                         qty=Decimal("0.1"), price=Decimal("2400.00"), timestamp=101.0)
    fill = broker.submit_order(ticket)
    assert fill is not None
    assert fill.price == Decimal("2400.00")
    assert p.position_side == PositionSide.SHORT


def test_stop_market_waits_until_trigger():
    """Item 5: a SELL STOP_MARKET must not fill before the stop is touched."""
    broker = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0.0002"))
    p = Portfolio("p1", "Aggressive", initial_cash=Decimal("3000.00"))
    broker.register_portfolio(p, max_position_ratio=Decimal("0.8"))
    broker.on_tick(price=Decimal("2500.00"), timestamp=100.0)

    # Open long 0.5 ETH at 2500 (no bracket attached).
    entry = OrderTicket("p1", "ETH/USD", OrderSide.BUY, OrderType.MARKET,
                        qty=Decimal("0.5"), timestamp=100.0)
    assert broker.submit_order(entry) is not None
    assert p.position_qty == Decimal("0.5000")

    # Resting sell-stop at 2400: market is 2500, must park, not fill.
    stop = OrderTicket("p1", "ETH/USD", OrderSide.SELL, OrderType.STOP_MARKET,
                       qty=Decimal("0.5"), price=Decimal("2400.00"), timestamp=101.0)
    assert broker.submit_order(stop) is None
    assert p.position_qty == Decimal("0.5000")
    assert stop.order_id in broker.pending_orders

    # Bar low 2410: stop not touched, still parked.
    fills = broker.on_tick(price=Decimal("2450.00"), high=Decimal("2480.00"),
                           low=Decimal("2410.00"), timestamp=102.0)
    assert fills == []
    assert stop.order_id in broker.pending_orders

    # Bar low 2390: stop triggered, fills at market with slippage (below 2400).
    fills = broker.on_tick(price=Decimal("2395.00"), high=Decimal("2405.00"),
                           low=Decimal("2390.00"), timestamp=103.0)
    assert len(fills) == 1
    assert fills[0].side == OrderSide.SELL
    assert fills[0].price < Decimal("2400.00")
    assert fills[0].price > Decimal("2390.00")
    assert p.position_qty == Decimal("0.0000")


def test_take_profit_fill_pays_slippage():
    """Item 5: TP fills pay the same slippage as SL fills (symmetric exits)."""
    broker = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0.0002"))
    p = Portfolio("p1", "Aggressive", initial_cash=Decimal("3000.00"))
    broker.register_portfolio(p, max_position_ratio=Decimal("0.8"))
    broker.on_tick(price=Decimal("2500.00"), timestamp=100.0)
    ticket = OrderTicket(
        portfolio_id="p1", symbol="ETH/USD", side=OrderSide.BUY,
        order_type=OrderType.MARKET, qty=Decimal("0.4"),
        stop_loss=Decimal("2450.00"), take_profit=Decimal("2600.00"), timestamp=100.0,
    )
    assert broker.submit_order(ticket) is not None
    fills = broker.on_tick(price=Decimal("2510.00"), high=Decimal("2620.00"),
                           low=Decimal("2495.00"), timestamp=101.0,
                           open_price=Decimal("2505.00"))
    assert len(fills) == 1
    assert fills[0].reason == ExecutionReason.TAKE_PROFIT
    assert fills[0].price < Decimal("2600.00")
    assert fills[0].price > Decimal("2599.00")
    assert p.position_qty == Decimal("0.0000")
