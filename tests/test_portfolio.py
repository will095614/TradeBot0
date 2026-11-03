from decimal import Decimal
import pytest
from src.arena.order import FillEvent, OrderSide
from src.arena.portfolio import Portfolio

def test_portfolio_initialization():
    p = Portfolio(portfolio_id="test_p", name="Test Portfolio", initial_cash=Decimal("3000.00"))
    assert p.cash == Decimal("3000.00")
    assert p.position_qty == Decimal("0.0000")
    assert p.total_equity == Decimal("3000.00")
    assert p.roi_pct == Decimal("0.00")
    assert p.unrealized_pnl == Decimal("0.00")

def test_portfolio_buy_and_sell_accounting():
    p = Portfolio(portfolio_id="test_p", name="Test Portfolio", initial_cash=Decimal("3000.00"), maker_taker_fee_rate=Decimal("0.001")) # 0.1% fee
    
    # Buy 1.0 ETH at $2500.00
    # Cost = 2500.00, Fee = 2.50, Total = 2502.50
    buy_fill = FillEvent(
        order_id="ord1",
        portfolio_id="test_p",
        symbol="ETH/USD",
        side=OrderSide.BUY,
        qty=Decimal("1.0000"),
        price=Decimal("2500.00"),
        fee=Decimal("2.50"),
        timestamp=1000.0
    )
    p.apply_fill(buy_fill)
    
    assert p.cash == Decimal("497.50")  # 3000 - 2502.50
    assert p.position_qty == Decimal("1.0000")
    assert p.avg_entry_price == Decimal("2500.00")
    assert p.total_fees_paid == Decimal("2.50")
    
    # Price rises to $2600.00
    p.update_market_price(Decimal("2600.00"), timestamp=1001.0)
    assert p.unrealized_pnl == Decimal("100.00")
    assert p.total_equity == Decimal("3097.50") # 497.50 + 2600.00
    
    # Sell 1.0 ETH at $2600.00
    # Proceeds = 2600.00, Fee = 2.60, Net cash from sale = 2597.40
    # Net Realized PnL = (2600 - 2500)*1 - 2.60 (exit fee) - 2.50 (entry fee) = 94.90
    sell_fill = FillEvent(
        order_id="ord2",
        portfolio_id="test_p",
        symbol="ETH/USD",
        side=OrderSide.SELL,
        qty=Decimal("1.0000"),
        price=Decimal("2600.00"),
        fee=Decimal("2.60"),
        timestamp=1002.0
    )
    p.apply_fill(sell_fill)
    
    assert p.position_qty == Decimal("0.0000")
    assert p.cash == Decimal("3094.90") # 497.50 + 2597.40
    assert p.realized_pnl == Decimal("94.90") # 100.00 gross - 2.50 buy fee - 2.60 sell fee
    assert p.total_equity == Decimal("3094.90")
    assert p.roi_pct == Decimal("3.16") # (3094.90 - 3000)/3000 * 100 = 3.1633% -> 3.16%

def test_portfolio_insufficient_cash():
    p = Portfolio(portfolio_id="test_p", name="Test Portfolio", initial_cash=Decimal("1000.00"))
    fill = FillEvent(
        order_id="ord1",
        portfolio_id="test_p",
        symbol="ETH/USD",
        side=OrderSide.BUY,
        qty=Decimal("1.0000"),
        price=Decimal("2000.00"),
        fee=Decimal("2.00"),
        timestamp=1000.0
    )
    with pytest.raises(ValueError, match="Insufficient cash"):
        p.apply_fill(fill)

def test_portfolio_overselling():
    p = Portfolio(portfolio_id="test_p", name="Test Portfolio", initial_cash=Decimal("3000.00"))
    fill = FillEvent(
        order_id="ord1",
        portfolio_id="test_p",
        symbol="ETH/USD",
        side=OrderSide.SELL,
        qty=Decimal("1.0000"),
        price=Decimal("2500.00"),
        fee=Decimal("2.50"),
        timestamp=1000.0
    )
    with pytest.raises(ValueError, match="Overselling"):
        p.apply_fill(fill)


def test_portfolio_breakeven_trade_does_not_count_as_loss():
    # 0% fee scenario to test exact 0.00 PnL
    p = Portfolio(portfolio_id="test_p", name="Test Portfolio", initial_cash=Decimal("1000.00"), maker_taker_fee_rate=Decimal("0.0"))
    buy_fill = FillEvent("b1", "test_p", "ETH/USD", OrderSide.BUY, Decimal("1.0"), Decimal("500.00"), Decimal("0.0"), 100.0)
    p.apply_fill(buy_fill)
    sell_fill = FillEvent("s1", "test_p", "ETH/USD", OrderSide.SELL, Decimal("1.0"), Decimal("500.00"), Decimal("0.0"), 101.0)
    enriched = p.apply_fill(sell_fill)

    assert enriched.realized_pnl == Decimal("0.00")
    assert p.win_count == 0
    assert p.loss_count == 0


