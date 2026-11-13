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
    # First buy 0.5000 ETH
    buy_fill = FillEvent(
        order_id="ord0",
        portfolio_id="test_p",
        symbol="ETH/USD",
        side=OrderSide.BUY,
        qty=Decimal("0.5000"),
        price=Decimal("2500.00"),
        fee=Decimal("1.25"),
        timestamp=999.0
    )
    p.apply_fill(buy_fill)

    # Attempt to sell 1.0000 ETH (overselling 0.5 held)
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


def test_portfolio_short_accounting_and_overcovering():
    p = Portfolio(portfolio_id="test_p", name="Test Portfolio", initial_cash=Decimal("3000.00"), maker_taker_fee_rate=Decimal("0.001"))
    # Short 1.0 ETH at $2500.00
    short_fill = FillEvent(
        order_id="ord_s1", portfolio_id="test_p", symbol="ETH/USD", side=OrderSide.SELL,
        qty=Decimal("1.0000"), price=Decimal("2500.00"), fee=Decimal("2.50"), timestamp=1000.0
    )
    p.apply_fill(short_fill)
    assert p.position_side.value == "SHORT"
    assert p.position_qty == Decimal("1.0000")
    assert p.margin_locked == Decimal("2500.00")
    assert p.cash == Decimal("497.50")

    # Price drops to $2400.00 (profit for short!)
    p.update_market_price(Decimal("2400.00"), timestamp=1001.0)
    assert p.unrealized_pnl == Decimal("100.00")
    assert p.total_equity == Decimal("3097.50")

    # Overcovering check
    overcover = FillEvent(
        order_id="ov1", portfolio_id="test_p", symbol="ETH/USD", side=OrderSide.BUY,
        qty=Decimal("1.5000"), price=Decimal("2400.00"), fee=Decimal("2.40"), timestamp=1002.0
    )
    with pytest.raises(ValueError, match="Overcovering"):
        p.apply_fill(overcover)

    # Cover short at $2400.00
    cover_fill = FillEvent(
        order_id="ord_s2", portfolio_id="test_p", symbol="ETH/USD", side=OrderSide.BUY,
        qty=Decimal("1.0000"), price=Decimal("2400.00"), fee=Decimal("2.40"), timestamp=1003.0
    )
    enriched = p.apply_fill(cover_fill)
    assert p.position_side.value == "FLAT"
    assert p.position_qty == Decimal("0.0000")
    assert enriched.realized_pnl == Decimal("95.10")  # 100 gross - 2.50 entry fee - 2.40 exit fee
    assert p.total_equity == Decimal("3095.10")


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


# =========================================================== P1-A
# Portfolio invariants left over from P0 (§2.9): equity conservation,
# short add-to-position, and proportional margin release on partial close.
# ===========================================================


def _fill(order_id, side, qty, price, ts, fee="0.00"):
    return FillEvent(
        order_id=order_id, portfolio_id="test_p", symbol="ETH/USD",
        side=side, qty=Decimal(qty), price=Decimal(price),
        fee=Decimal(fee), timestamp=ts,
    )


def _assert_equity_conservation(p):
    # Decimal-exact identity: total_equity == cash + margin_locked + unrealized_pnl.
    # (total_equity returns cash alone once flat, where margin and
    # unrealized are both 0, so the identity holds there too.)
    assert p.total_equity == (p.cash + p.margin_locked + p.unrealized_pnl)


def test_equity_conservation_across_all_fill_cases():
    p = Portfolio(portfolio_id="test_p", name="Test Portfolio",
                  initial_cash=Decimal("100000.00"), maker_taker_fee_rate=Decimal("0.0"))

    # Open long 1.0 @ 2500 (cash 97500, margin 2500), mark 2600.
    p.apply_fill(_fill("o1", OrderSide.BUY, "1.0000", "2500.00", 1000.0))
    p.update_market_price(Decimal("2600.00"), timestamp=1001.0)
    assert p.total_equity == Decimal("100100.00")  # 97500 + 2500 + 100
    _assert_equity_conservation(p)

    # Add long 1.0 @ 2600 (avg 2550, margin 5100), mark 2700.
    p.apply_fill(_fill("o2", OrderSide.BUY, "1.0000", "2600.00", 1002.0))
    assert p.avg_entry_price == Decimal("2550.00")
    p.update_market_price(Decimal("2700.00"), timestamp=1003.0)
    assert p.total_equity == Decimal("100300.00")  # 94900 + 5100 + 300
    _assert_equity_conservation(p)

    # Partial close long 1.0 @ 2700, mark 2650.
    p.apply_fill(_fill("o3", OrderSide.SELL, "1.0000", "2700.00", 1004.0))
    assert p.position_qty == Decimal("1.0000")
    p.update_market_price(Decimal("2650.00"), timestamp=1005.0)
    _assert_equity_conservation(p)

    # Full close long 1.0 @ 2650.
    p.apply_fill(_fill("o4", OrderSide.SELL, "1.0000", "2650.00", 1006.0))
    assert p.position_qty == Decimal("0.0000")
    assert p.margin_locked == Decimal("0.00")
    _assert_equity_conservation(p)

    # Open short 1.0 @ 2650, mark 2550.
    p.apply_fill(_fill("o5", OrderSide.SELL, "1.0000", "2650.00", 1007.0))
    assert p.position_side.value == "SHORT"
    p.update_market_price(Decimal("2550.00"), timestamp=1008.0)
    _assert_equity_conservation(p)

    # Add short 1.0 @ 2550 (avg 2600), mark 2600.
    p.apply_fill(_fill("o6", OrderSide.SELL, "1.0000", "2550.00", 1009.0))
    assert p.avg_entry_price == Decimal("2600.00")
    p.update_market_price(Decimal("2600.00"), timestamp=1010.0)
    _assert_equity_conservation(p)

    # Partial cover short 1.0 @ 2600, mark 2500.
    p.apply_fill(_fill("o7", OrderSide.BUY, "1.0000", "2600.00", 1011.0))
    assert p.position_qty == Decimal("1.0000")
    p.update_market_price(Decimal("2500.00"), timestamp=1012.0)
    _assert_equity_conservation(p)

    # Full cover short 1.0 @ 2500.
    p.apply_fill(_fill("o8", OrderSide.BUY, "1.0000", "2500.00", 1013.0))
    assert p.position_qty == Decimal("0.0000")
    assert p.position_side.value == "FLAT"
    assert p.margin_locked == Decimal("0.00")
    _assert_equity_conservation(p)


def test_add_to_short_recomputes_avg_entry_and_margin():
    p = Portfolio(portfolio_id="test_p", name="Test Portfolio",
                  initial_cash=Decimal("100000.00"), maker_taker_fee_rate=Decimal("0.0"))
    p.apply_fill(_fill("s1", OrderSide.SELL, "1.0000", "2500.00", 1000.0))
    assert p.position_side.value == "SHORT"
    assert p.position_qty == Decimal("1.0000")
    assert p.avg_entry_price == Decimal("2500.00")
    assert p.margin_locked == Decimal("2500.00")
    assert p.cash == Decimal("97500.00")

    # Add 1.0 short @ 2600: weighted average (2500 + 2600) / 2 = 2550,
    # margin grows by the new notional, cash falls by the same amount.
    p.apply_fill(_fill("s2", OrderSide.SELL, "1.0000", "2600.00", 1001.0))
    assert p.position_side.value == "SHORT"
    assert p.position_qty == Decimal("2.0000")
    assert p.avg_entry_price == Decimal("2550.00")
    assert p.margin_locked == Decimal("5100.00")
    assert p.cash == Decimal("94900.00")
    _assert_equity_conservation(p)

    # Adding to a short with too little cash raises, like the long side.
    small = Portfolio(portfolio_id="test_p", name="Test Portfolio",
                      initial_cash=Decimal("3000.00"), maker_taker_fee_rate=Decimal("0.0"))
    small.apply_fill(_fill("s1", OrderSide.SELL, "1.0000", "2500.00", 1000.0))
    assert small.cash == Decimal("500.00")
    with pytest.raises(ValueError, match="Insufficient cash"):
        small.apply_fill(_fill("s2", OrderSide.SELL, "1.0000", "2600.00", 1001.0))


def test_partial_close_releases_margin_proportionally():
    # LONG: open 1.0 @ 2500 (margin 2500), sell half @ 2600.
    p = Portfolio(portfolio_id="test_p", name="Test Portfolio",
                  initial_cash=Decimal("100000.00"), maker_taker_fee_rate=Decimal("0.0"))
    p.apply_fill(_fill("b1", OrderSide.BUY, "1.0000", "2500.00", 1000.0))
    p.apply_fill(_fill("s1", OrderSide.SELL, "0.5000", "2600.00", 1001.0))
    assert p.position_side.value == "LONG"
    assert p.position_qty == Decimal("0.5000")
    assert p.avg_entry_price == Decimal("2500.00")  # average never moves on a close
    assert p.margin_locked == Decimal("1250.00")  # exactly half released
    _assert_equity_conservation(p)

    # SHORT: open 1.0 @ 2500 (margin 2500), cover half @ 2400.
    q = Portfolio(portfolio_id="test_p", name="Test Portfolio",
                  initial_cash=Decimal("100000.00"), maker_taker_fee_rate=Decimal("0.0"))
    q.apply_fill(_fill("s1", OrderSide.SELL, "1.0000", "2500.00", 1000.0))
    q.apply_fill(_fill("c1", OrderSide.BUY, "0.5000", "2400.00", 1001.0))
    assert q.position_side.value == "SHORT"
    assert q.position_qty == Decimal("0.5000")
    assert q.avg_entry_price == Decimal("2500.00")
    assert q.margin_locked == Decimal("1250.00")
    _assert_equity_conservation(q)
