from decimal import Decimal
import pytest
from src.arena.broker_sim import BrokerSim
from src.arena.order import OrderSide
from src.competitors.aggressive import AggressiveCompetitor
from src.competitors.conservative import ConservativeCompetitor
from src.competitors.atr_dynamic import ATRDynamicCompetitor
from src.competitors.trailing_guard import TrailingGuardCompetitor
from src.competitors.orb import ORBCompetitor
from src.competitors.vwap import VWAPPullbackCompetitor
from src.arena.leaderboard import Leaderboard

def test_all_four_competitors_initialization_and_first_buy():
    broker = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0.0"))
    
    comp_a = AggressiveCompetitor()
    comp_b = ConservativeCompetitor()
    comp_c = ATRDynamicCompetitor()
    comp_d = TrailingGuardCompetitor()
    comp_e = ORBCompetitor()
    comp_f = VWAPPullbackCompetitor()
    
    competitors = [comp_a, comp_b, comp_c, comp_d, comp_e, comp_f]
    for c in competitors:
        broker.register_portfolio(c.portfolio, max_position_ratio=c.max_position_ratio)
        assert c.portfolio.cash == Decimal("100000.00")
        assert c.portfolio.total_equity == Decimal("100000.00")
        
    market_price = Decimal("2500.00")
    broker.on_tick(market_price, timestamp=100.0)
    
    indicators = {
        "atr": Decimal("35.00"),
        "orb_high": Decimal("2480.00"),
        "vwap": Decimal("2500.00")
    }
    
    # Send BUY signal to all competitors
    for c in competitors:
        ticket = c.evaluate_signal(
            signal="BUY",
            market_price=market_price,
            indicators=indicators,
            broker=broker,
            timestamp=100.0
        )
        assert ticket is not None
        assert ticket.side == OrderSide.BUY
        fill = broker.submit_order(ticket)
        assert fill is not None
        
    # Check that positions reflect their specific risk budgets and leverage
    # A (Aggressive 3x Lev ~70% of 100,000 * 3 = $210,000 / 2500 = 84 BTC)
    assert comp_a.portfolio.position_qty == Decimal("84.0000")
    # B (Conservative Spot 1x ~25% of 100,000 = $25,000 / 2500 = 10 BTC)
    assert comp_b.portfolio.position_qty == Decimal("10.0000")
    # C (ATR Dynamic 2x Lev)
    assert comp_c.portfolio.position_qty > Decimal("0")
    # D (Trailing Guard 2x Lev ~40% of 100,000 * 2 = $80,000 / 2500 = 32 BTC)
    assert comp_d.portfolio.position_qty == Decimal("32.0000")
    # E (ORB Breakout 2.5x Lev ~45% of 100,000 * 2.5 = $112,500 / 2500 = 45 BTC)
    assert comp_e.portfolio.position_qty == Decimal("45.0000")
    # F (VWAP Pullback Spot 1x ~50% of 100,000 = $50,000 / 2500 = 20 BTC)
    assert comp_f.portfolio.position_qty == Decimal("20.0000")
    
    # Check Leaderboard generation
    rankings = Leaderboard.get_rankings(broker.portfolios)
    assert len(rankings) == 6
    for r in rankings:
        assert r.equity > Decimal("0")
        assert r.status == "ACTIVE"


def test_orb_competitor_box_breakout_and_r_multiple():
    broker = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0.0"))
    comp = ORBCompetitor()
    broker.register_portfolio(comp.portfolio, max_position_ratio=comp.max_position_ratio)
    assert comp.portfolio.cash == Decimal("100000.00")

    # 1. Price below ORB high: should NOT trigger breakout
    market_price = Decimal("2450.00")
    broker.on_tick(market_price, timestamp=100.0)
    ticket_none = comp.evaluate_signal(
        signal="BUY",
        market_price=market_price,
        indicators={"orb_high": Decimal("2480.00"), "orb_low": Decimal("2400.00"), "atr": Decimal("20.00")},
        broker=broker,
        timestamp=100.0
    )
    assert ticket_none is None

    # 2. Price breaks above ORB high: triggers breakout BUY
    market_price = Decimal("2490.00")
    broker.on_tick(market_price, timestamp=110.0)
    ticket_buy = comp.evaluate_signal(
        signal="BUY",
        market_price=market_price,
        indicators={"orb_high": Decimal("2480.00"), "orb_low": Decimal("2400.00"), "atr": Decimal("20.00")},
        broker=broker,
        timestamp=110.0
    )
    assert ticket_buy is not None
    assert ticket_buy.side == OrderSide.BUY
    # Midpoint of 2480 and 2400 is 2440.00
    assert ticket_buy.stop_loss == Decimal("2440.00")
    # Stop distance = 2490 - 2440 = 50. 2.0R target = 2490 + 50 * 2 = 2590.00
    assert ticket_buy.take_profit == Decimal("2590.00")
    assert ticket_buy.qty > Decimal("0")


def test_vwap_competitor_pullback_and_r_multiple():
    broker = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0.0"))
    comp = VWAPPullbackCompetitor()
    broker.register_portfolio(comp.portfolio, max_position_ratio=comp.max_position_ratio)
    assert comp.portfolio.cash == Decimal("100000.00")

    vwap = Decimal("2500.00")
    atr = Decimal("20.00")

    # 1. Price too far above VWAP (> 0.85 * 20 = 17 away): should NOT trigger pullback buy
    far_price = Decimal("2530.00")
    broker.on_tick(far_price, timestamp=100.0)
    ticket_far = comp.evaluate_signal(
        signal="BUY",
        market_price=far_price,
        indicators={"vwap": vwap, "atr": atr, "rsi": Decimal("50.00")},
        broker=broker,
        timestamp=100.0
    )
    assert ticket_far is None

    # 2. Price pulls back near VWAP (within 17): triggers pullback BUY
    pullback_price = Decimal("2506.00")
    broker.on_tick(pullback_price, timestamp=110.0)
    ticket_buy = comp.evaluate_signal(
        signal="BUY",
        market_price=pullback_price,
        indicators={"vwap": vwap, "atr": atr, "rsi": Decimal("48.00")},
        broker=broker,
        timestamp=110.0
    )
    assert ticket_buy is not None
    assert ticket_buy.side == OrderSide.BUY
    # Stop is set below VWAP: 2500 - 0.5 * 20 = 2490.00
    assert ticket_buy.stop_loss == Decimal("2490.00")
    # Stop distance = 2506 - 2490 = 16. 2.2R target = 2506 + 16 * 2.2 = 2541.20
    assert ticket_buy.take_profit == Decimal("2541.20")
    assert ticket_buy.qty > Decimal("0")

