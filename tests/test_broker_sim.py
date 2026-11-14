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


def test_backtest_slippage_uses_measured_atr():
    """F3: the backtest ATR is measured from the replayed bars, not the
    broker's fixed 12.00 start value.

    Two 15-bar runs at a flat $2500 close: calm bars (true range 4) end
    with current_atr 4.00, wild bars (true range 200) end with 200.00,
    and the same BUY then pays visibly different volatility slippage.
    """
    from src.data.eth_feed import CandleBar
    from src.data.timemachine import TimeMachineArena

    def _bars(range_size):
        price = Decimal("2500.00")
        half = range_size / Decimal("2")
        return [
            CandleBar(
                timestamp=1000.0 + (i * 900), open_=price,
                high=price + half, low=price - half, close=price,
                volume=Decimal("100.0"), ema_fast=price, ema_slow=price,
                rsi=Decimal("50.00"), atr=Decimal("25.00"),
            )
            for i in range(15)
        ]

    calm = TimeMachineArena(symbol="ETH/USD", initial_cash=Decimal("500000.00"))
    calm.run_simulation(_bars(Decimal("4.00")))
    assert calm.broker.current_atr == Decimal("4.00")

    wild = TimeMachineArena(symbol="ETH/USD", initial_cash=Decimal("500000.00"))
    wild.run_simulation(_bars(Decimal("200.00")))
    assert wild.broker.current_atr == Decimal("200.00")
    assert wild.broker.current_atr != calm.broker.current_atr

    calm_px = calm.broker.compute_execution_slippage(
        OrderSide.BUY, OrderType.MARKET, Decimal("1.0"), Decimal("2500.00"),
        atr=calm.broker.current_atr,
    )
    wild_px = wild.broker.compute_execution_slippage(
        OrderSide.BUY, OrderType.MARKET, Decimal("1.0"), Decimal("2500.00"),
        atr=wild.broker.current_atr,
    )
    assert wild_px > calm_px
# =========================================================== P1-A
# Broker invariants (§2.9): fill-price bounds, stop trigger prices,
# and TP >= SL on every strategy ticket.
# ===========================================================


def test_fill_price_within_bar_range_and_slippage_direction():
    """P1 §2.9: fills land inside the bar's [low, high] and slippage
    points the right way (buys pay above mid, sells below it); LIMIT
    orders pay no slippage at all."""
    # (a) MARKET with slippage: buy above mid, sell below mid, both in range.
    broker = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0.0002"))
    p_buy = Portfolio("p_buy", "Buyer", initial_cash=Decimal("3000.00"))
    p_sell = Portfolio("p_sell", "Seller", initial_cash=Decimal("3000.00"))
    broker.register_portfolio(p_buy, max_position_ratio=Decimal("0.8"))
    broker.register_portfolio(p_sell, max_position_ratio=Decimal("0.8"))
    broker.on_tick(price=Decimal("2500.00"), high=Decimal("2510.00"),
                   low=Decimal("2490.00"), timestamp=100.0)
    buy_fill = broker.submit_order(OrderTicket(
        "p_buy", "ETH/USD", OrderSide.BUY, OrderType.MARKET,
        qty=Decimal("0.1"), timestamp=100.0))
    assert buy_fill is not None
    assert Decimal("2500.00") < buy_fill.price <= Decimal("2510.00")
    assert buy_fill.price >= Decimal("2490.00")
    sell_fill = broker.submit_order(OrderTicket(
        "p_sell", "ETH/USD", OrderSide.SELL, OrderType.MARKET,
        qty=Decimal("0.1"), timestamp=100.0))
    assert sell_fill is not None
    assert Decimal("2490.00") <= sell_fill.price < Decimal("2500.00")
    assert sell_fill.price <= Decimal("2510.00")

    # (b) MARKET with zero slippage fills exactly at the mid price.
    broker0 = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0.0"))
    p0 = Portfolio("p0", "ZeroSlip", initial_cash=Decimal("3000.00"))
    broker0.register_portfolio(p0, max_position_ratio=Decimal("0.8"))
    broker0.on_tick(price=Decimal("2500.00"), high=Decimal("2510.00"),
                    low=Decimal("2490.00"), timestamp=100.0)
    fill0 = broker0.submit_order(OrderTicket(
        "p0", "ETH/USD", OrderSide.BUY, OrderType.MARKET,
        qty=Decimal("0.1"), timestamp=100.0))
    assert fill0 is not None
    assert fill0.price == Decimal("2500.00")

    # (c) LIMIT fills at its limit price -- no slippage -- inside the bar.
    broker_l = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0.0002"))
    p_l = Portfolio("p_l", "Limiter", initial_cash=Decimal("3000.00"))
    broker_l.register_portfolio(p_l, max_position_ratio=Decimal("0.8"))
    broker_l.on_tick(price=Decimal("2500.00"), timestamp=100.0)
    ticket = OrderTicket("p_l", "ETH/USD", OrderSide.BUY, OrderType.LIMIT,
                         qty=Decimal("0.1"), price=Decimal("2400.00"), timestamp=101.0)
    assert broker_l.submit_order(ticket) is None  # parked above the limit
    fills = broker_l.on_tick(price=Decimal("2395.00"), high=Decimal("2405.00"),
                             low=Decimal("2390.00"), timestamp=102.0)
    assert len(fills) == 1
    assert fills[0].price == Decimal("2400.00")
    assert Decimal("2390.00") <= fills[0].price <= Decimal("2405.00")


def test_pending_stop_market_trigger_price():
    """P1 §2.8 (broker_sim.py:274-275): a resting STOP_MARKET only fills
    once the bar touches its stop, at market with slippage around the
    stop; a bracket stop for a SHORT fills from max(bar_open, stop)
    (the LONG side mirrors it with min(bar_open, stop))."""
    # (a) Resting SELL stop for a long: untouched bar -> parked; touched bar -> fills.
    broker = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0.0002"))
    p = Portfolio("p1", "Aggressive", initial_cash=Decimal("3000.00"))
    broker.register_portfolio(p, max_position_ratio=Decimal("0.8"))
    broker.on_tick(price=Decimal("2500.00"), timestamp=100.0)
    assert broker.submit_order(OrderTicket(
        "p1", "ETH/USD", OrderSide.BUY, OrderType.MARKET,
        qty=Decimal("0.5"), timestamp=100.0)) is not None
    stop = OrderTicket("p1", "ETH/USD", OrderSide.SELL, OrderType.STOP_MARKET,
                       qty=Decimal("0.5"), price=Decimal("2400.00"), timestamp=101.0)
    assert broker.submit_order(stop) is None
    assert stop.order_id in broker.pending_orders
    fills = broker.on_tick(price=Decimal("2450.00"), high=Decimal("2480.00"),
                           low=Decimal("2410.00"), timestamp=102.0)
    assert fills == []  # low 2410 never touched the 2400 stop
    assert stop.order_id in broker.pending_orders
    fills = broker.on_tick(price=Decimal("2395.00"), high=Decimal("2405.00"),
                           low=Decimal("2390.00"), timestamp=103.0,
                           open_price=Decimal("2405.00"))
    assert len(fills) == 1
    assert fills[0].side == OrderSide.SELL
    # Slippage around the 2400 stop, inside the triggering bar.
    assert Decimal("2390.00") < fills[0].price < Decimal("2400.00")
    assert p.position_qty == Decimal("0.0000")

    # (b) Bracket stop for a SHORT: bar opens above the stop, so the
    # trigger price is the bar open (max(bar_open, stop) = 3560), and a
    # BUY fill pays slippage above it.
    broker2 = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0.0002"))
    p2 = Portfolio("p2", "Shorter", initial_cash=Decimal("100000.00"))
    broker2.register_portfolio(p2, max_position_ratio=Decimal("0.8"))
    broker2.on_tick(price=Decimal("3500.00"), timestamp=100.0)
    assert broker2.submit_order(OrderTicket(
        "p2", "ETH/USD", OrderSide.SELL, OrderType.MARKET, qty=Decimal("0.5"),
        stop_loss=Decimal("3552.50"), take_profit=Decimal("3430.00"),
        timestamp=100.0)) is not None
    fills = broker2.on_tick(price=Decimal("3510.00"), high=Decimal("3570.00"),
                            low=Decimal("3500.00"), timestamp=101.0,
                            open_price=Decimal("3560.00"))
    assert len(fills) == 1
    assert fills[0].side == OrderSide.BUY
    assert fills[0].reason == ExecutionReason.STOP_LOSS
    assert fills[0].price > Decimal("3560.00")
    assert fills[0].price <= Decimal("3570.00")
    assert p2.position_qty == Decimal("0.0000")

    # (b2) Same short stop, bar opens below the stop: the trigger price
    # is the stop itself (max(3540, 3552.50) = 3552.50).
    broker3 = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0.0002"))
    p3 = Portfolio("p3", "Shorter", initial_cash=Decimal("100000.00"))
    broker3.register_portfolio(p3, max_position_ratio=Decimal("0.8"))
    broker3.on_tick(price=Decimal("3500.00"), timestamp=100.0)
    assert broker3.submit_order(OrderTicket(
        "p3", "ETH/USD", OrderSide.SELL, OrderType.MARKET, qty=Decimal("0.5"),
        stop_loss=Decimal("3552.50"), take_profit=Decimal("3430.00"),
        timestamp=100.0)) is not None
    fills = broker3.on_tick(price=Decimal("3510.00"), high=Decimal("3560.00"),
                            low=Decimal("3500.00"), timestamp=101.0,
                            open_price=Decimal("3540.00"))
    assert len(fills) == 1
    assert fills[0].price > Decimal("3552.50")
    assert fills[0].price < Decimal("3555.00")
    assert p3.position_qty == Decimal("0.0000")

    # (c) LONG mirror: bar opens below the stop, trigger is the bar open
    # (min(bar_open, stop) = 2440), and a SELL fill pays slippage below it.
    broker4 = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0.0002"))
    p4 = Portfolio("p4", "Longer", initial_cash=Decimal("100000.00"))
    broker4.register_portfolio(p4, max_position_ratio=Decimal("0.8"))
    broker4.on_tick(price=Decimal("2500.00"), timestamp=100.0)
    assert broker4.submit_order(OrderTicket(
        "p4", "ETH/USD", OrderSide.BUY, OrderType.MARKET, qty=Decimal("0.5"),
        stop_loss=Decimal("2450.00"), take_profit=Decimal("2600.00"),
        timestamp=100.0)) is not None
    fills = broker4.on_tick(price=Decimal("2435.00"), high=Decimal("2450.00"),
                            low=Decimal("2430.00"), timestamp=101.0,
                            open_price=Decimal("2440.00"))
    assert len(fills) == 1
    assert fills[0].side == OrderSide.SELL
    assert fills[0].reason == ExecutionReason.STOP_LOSS
    assert fills[0].price < Decimal("2440.00")
    assert fills[0].price >= Decimal("2430.00")
    assert p4.position_qty == Decimal("0.0000")


def test_every_ticket_satisfies_tp_ge_sl():
    """P1 §2.9 (order-level invariant): for all six strategies x both
    directions, an entry ticket's bracket straddles the entry price --
    long TP > entry > SL, short SL > entry > TP. Aggressive and Trailing
    Guard are uncapped runners (TP None on both sides), so for them only
    the stop ordering is asserted; the other four must carry a TP on
    both sides."""
    from src.competitors.aggressive import AggressiveCompetitor
    from src.competitors.atr_dynamic import ATRDynamicCompetitor
    from src.competitors.conservative import ConservativeCompetitor
    from src.competitors.orb import ORBCompetitor
    from src.competitors.session_mean import SessionMeanPullbackCompetitor
    from src.competitors.trailing_guard import TrailingGuardCompetitor

    # (name, class, long_price, long_indicators, short_price, short_indicators)
    cases = [
        ("Aggressive", AggressiveCompetitor,
         Decimal("2500.00"), {"atr": Decimal("35.00")},
         Decimal("2500.00"), {"atr": Decimal("35.00")}),
        ("ATR Dynamic", ATRDynamicCompetitor,
         Decimal("2500.00"), {"atr": Decimal("35.00")},
         Decimal("2500.00"), {"atr": Decimal("35.00")}),
        ("Conservative", ConservativeCompetitor,
         Decimal("2500.00"), {},
         Decimal("2500.00"), {}),
        ("Trailing Guard", TrailingGuardCompetitor,
         Decimal("2500.00"), {},
         Decimal("2500.00"), {}),
        ("ORB", ORBCompetitor,
         Decimal("2490.00"), {"orb_high": Decimal("2480.00"), "orb_low": Decimal("2400.00"), "atr": Decimal("20.00")},
         Decimal("2390.00"), {"orb_high": Decimal("2480.00"), "orb_low": Decimal("2400.00"), "atr": Decimal("20.00")}),
        ("Session Mean", SessionMeanPullbackCompetitor,
         Decimal("2506.00"), {"mean_ref": Decimal("2500.00"), "atr": Decimal("20.00"), "rsi": Decimal("48.00")},
         Decimal("2494.00"), {"mean_ref": Decimal("2500.00"), "atr": Decimal("20.00"), "rsi": Decimal("52.00")}),
    ]
    capped = 0
    for name, cls, long_price, long_ind, short_price, short_ind in cases:
        for side, price, ind in ((OrderSide.BUY, long_price, long_ind),
                                 (OrderSide.SELL, short_price, short_ind)):
            broker = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0.0"))
            comp = cls()
            broker.register_portfolio(comp.portfolio, max_position_ratio=comp.max_position_ratio)
            broker.on_tick(price, timestamp=100.0)
            ticket = comp.evaluate_signal(
                signal="BUY", market_price=price, indicators=ind,
                broker=broker, timestamp=100.0, side=side)
            assert ticket is not None, f"{name} {side}: no ticket"
            assert ticket.qty > Decimal("0"), f"{name} {side}: zero qty"
            entry = price  # MARKET ticket: the strategy brackets off the call price
            if side == OrderSide.BUY:
                assert ticket.stop_loss is not None, f"{name} long: missing SL"
                assert ticket.stop_loss < entry, f"{name} long: SL {ticket.stop_loss} not below {entry}"
                if ticket.take_profit is not None:
                    assert ticket.take_profit > entry, f"{name} long: TP {ticket.take_profit} not above {entry}"
                    capped += 1
            else:
                assert ticket.stop_loss is not None, f"{name} short: missing SL"
                assert ticket.stop_loss > entry, f"{name} short: SL {ticket.stop_loss} not above {entry}"
                if ticket.take_profit is not None:
                    assert ticket.take_profit < entry, f"{name} short: TP {ticket.take_profit} not below {entry}"
                    capped += 1
            assert broker.submit_order(ticket) is not None, f"{name} {side}: ticket rejected"
    # Four capped strategies x two sides = 8 tickets must carry a TP;
    # the other four tickets are the uncapped runners' (TP None).
    assert capped == 8

# =========================================================== P2-A
# A4: pool depth 200.0 is a configurable, disclosed model parameter.
# ===========================================================


def test_depth_impact_pool_depth_is_disclosed():
    """A4: the 200.0 pool depth is a fixed slippage-model parameter, not
    measured order-book depth. It is now a named, configurable
    constructor parameter (default unchanged) and disclosed in the
    module comment; a deeper pool charges less depth impact for the
    same quantity."""
    import inspect

    import src.arena.broker_sim as bs_mod
    from src.arena.broker_sim import BrokerSim, DEFAULT_POOL_DEPTH

    assert DEFAULT_POOL_DEPTH == Decimal("200.0")
    broker = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0.0002"))
    assert broker.pool_depth == Decimal("200.0")
    # Configurable: same qty / mid / ATR, deeper pool -> less depth impact.
    deep = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0.0002"),
                     pool_depth=Decimal("2000.0"))
    assert deep.pool_depth == Decimal("2000.0")
    px_shallow = broker.compute_execution_slippage(
        OrderSide.BUY, OrderType.MARKET, Decimal("100.0"), Decimal("2500.00"),
        atr=Decimal("12.0"),
    )
    px_deep = deep.compute_execution_slippage(
        OrderSide.BUY, OrderType.MARKET, Decimal("100.0"), Decimal("2500.00"),
        atr=Decimal("12.0"),
    )
    assert px_deep < px_shallow
    # The module discloses the value as a model parameter, not depth data.
    mod_src = inspect.getsource(bs_mod)
    assert "MODEL PARAMETER" in mod_src or "model parameter" in mod_src
    assert "not measured" in mod_src


def test_broker_sim_leverage_liquidation_long_crash():
    """Audit 2.4: a leveraged LONG must be liquidated by a crash that wipes
    out its position margin. Under the old total-equity comparison this
    branch was unreachable on the long side (it needed a ~139% adverse
    move); the position-equity comparison fires once the position has
    lost 90% of its margin (maintenance level 10%).

    Setup mirrors the audit's arithmetic: $100k, 3x leverage, 70% cap.
    Long 20 ETH @ $3,500 (notional $70,000, margin locked $23,333.33).
    """
    broker = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0.0"))
    p = Portfolio(
        "p_lev_long",
        "LeveragedLong",
        initial_cash=Decimal("100000.00"),
        leverage=Decimal("3.0"),
        leverage_enabled=True,
    )
    broker.register_portfolio(p, max_position_ratio=Decimal("0.70"))

    broker.on_tick(price=Decimal("3500.00"), timestamp=100.0)
    ticket = OrderTicket("p_lev_long", "ETH/USD", OrderSide.BUY, OrderType.MARKET,
                         qty=Decimal("20"), timestamp=100.0)
    fill = broker.submit_order(ticket)
    assert fill is not None
    assert p.position_qty == Decimal("20.0000")
    assert p.position_side == PositionSide.LONG
    assert p.margin_locked == Decimal("23333.33")

    # -20% dip: position equity $9,333.33 is still far above the $2,333.33
    # maintenance level, and total drawdown (14.04%) is below the 15%
    # breaker, so nothing fires and the position survives.
    fills = broker.on_tick(price=Decimal("2800.00"), timestamp=101.0)
    assert fills == []
    assert p.position_qty == Decimal("20.0000")
    # The old comparison could not fire here either: total equity (~$86k)
    # is far above 10% of locked margin (~$2.3k).
    assert p.total_equity > p.margin_locked * Decimal("0.10")

    # -31.4% crash: unrealized loss $22,000 leaves position equity
    # $1,333.33 <= $2,333.33, so the liquidation branch fires. The old
    # comparison still could not fire (total equity ~$78k), so a
    # LIQUIDATION reason here proves the new comparison ran.
    fills = broker.on_tick(price=Decimal("2400.00"), timestamp=102.0)
    assert len(fills) == 1
    assert fills[0].reason == ExecutionReason.LIQUIDATION
    assert p.position_qty == Decimal("0.0000")
    assert p.is_circuit_breaker_tripped is True
