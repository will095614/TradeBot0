from decimal import Decimal
import pytest
from src.arena.broker_sim import BrokerSim
from src.arena.order import OrderSide
from src.competitors.aggressive import AggressiveCompetitor
from src.competitors.conservative import ConservativeCompetitor
from src.competitors.trailing_guard import TrailingGuardCompetitor
from src.competitors.orb import ORBCompetitor
from src.competitors.session_mean import SessionMeanPullbackCompetitor
from src.arena.leaderboard import Leaderboard

def test_all_four_competitors_initialization_and_first_buy():
    broker = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0.0"))
    
    comp_a = AggressiveCompetitor()
    comp_b = ConservativeCompetitor()
    comp_d = TrailingGuardCompetitor()
    comp_e = ORBCompetitor()
    comp_f = SessionMeanPullbackCompetitor()
    
    competitors = [comp_a, comp_b, comp_d, comp_e, comp_f]
    for c in competitors:
        broker.register_portfolio(c.portfolio, max_position_ratio=c.max_position_ratio)
        assert c.portfolio.cash == Decimal("100000.00")
        assert c.portfolio.total_equity == Decimal("100000.00")
        
    market_price = Decimal("2500.00")
    broker.on_tick(market_price, timestamp=100.0)
    
    indicators = {
        "atr": Decimal("35.00"),
        "orb_high": Decimal("2480.00"),
        "mean_ref": Decimal("2500.00")
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
        
    # Check that positions reflect their specific risk budgets on UNLEVERAGED equity.
    # Leverage affects only margin affordability, never the risk budget or notional cap.
    # A (Aggressive: risk 2.5% of 100,000 = $2,500 / $87.50 stop = 28.5714 ETH,
    #    capped by 70% position cap $70,000 / 2500 = 28.0000 ETH)
    assert comp_a.portfolio.position_qty == Decimal("28.0000")
    # B (Conservative Spot 1x ~25% of 100,000 = $25,000 / 2500 = 10 BTC)
    assert comp_b.portfolio.position_qty == Decimal("10.0000")
    # D (Trailing Guard: risk 1.5% of 100,000 = $1,500 / $37.50 stop = 40 ETH,
    #    capped by 40% position cap $40,000 / 2500 = 16.0000 ETH)
    assert comp_d.portfolio.position_qty == Decimal("16.0000")
    # E (ORB Breakout: risk 1.5% of 100,000 = $1,500 / $45 stop = 33.3333 ETH,
    #    capped by 45% position cap $45,000 / 2500 = 18.0000 ETH)
    assert comp_e.portfolio.position_qty == Decimal("18.0000")
    # F (Session Mean Pullback Spot 1x ~50% of 100,000 = $50,000 / 2500 = 20 BTC)
    assert comp_f.portfolio.position_qty == Decimal("20.0000")
    
    # Check Leaderboard generation
    rankings = Leaderboard.get_rankings(broker.portfolios)
    assert len(rankings) == 5
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


def test_session_mean_competitor_pullback_and_r_multiple():
    broker = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0.0"))
    comp = SessionMeanPullbackCompetitor()
    broker.register_portfolio(comp.portfolio, max_position_ratio=comp.max_position_ratio)
    assert comp.portfolio.cash == Decimal("100000.00")

    mean_ref = Decimal("2500.00")
    atr = Decimal("20.00")

    # 1. Price too far above the session mean (> 0.85 * 20 = 17 away): should NOT trigger pullback buy
    far_price = Decimal("2530.00")
    broker.on_tick(far_price, timestamp=100.0)
    ticket_far = comp.evaluate_signal(
        signal="BUY",
        market_price=far_price,
        indicators={"mean_ref": mean_ref, "atr": atr, "rsi": Decimal("50.00")},
        broker=broker,
        timestamp=100.0
    )
    assert ticket_far is None

    # 2. Price pulls back near the session mean (within 17): triggers pullback BUY
    pullback_price = Decimal("2506.00")
    broker.on_tick(pullback_price, timestamp=110.0)
    ticket_buy = comp.evaluate_signal(
        signal="BUY",
        market_price=pullback_price,
        indicators={"mean_ref": mean_ref, "atr": atr, "rsi": Decimal("48.00")},
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



def test_evaluate_signal_short_entries_mirror_long_brackets():
    """Item 2: evaluate_signal supports short entries (new `side` param).

    Live routes short entries through evaluate_signal, so the mirrored
    bracket must be the exact mirror of the long bracket, and a SELL
    signal must close a short with a BUY ticket.
    """
    broker = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0.0"))
    comp = AggressiveCompetitor()
    broker.register_portfolio(comp.portfolio, max_position_ratio=comp.max_position_ratio)
    broker.on_tick(Decimal("2500.00"), timestamp=100.0)

    ticket = comp.evaluate_signal(
        signal="BUY",
        market_price=Decimal("2500.00"),
        indicators={"atr": Decimal("35.00")},
        broker=broker,
        timestamp=100.0,
        side=OrderSide.SELL,
    )
    assert ticket is not None
    assert ticket.side == OrderSide.SELL
    # Aggressive genome SL 3.5%: short stop sits above entry, no TP (uncapped).
    assert ticket.stop_loss == Decimal("2587.50")
    assert ticket.take_profit is None
    fill = broker.submit_order(ticket)
    assert fill is not None
    assert comp.portfolio.position_side.value == "SHORT"

    close_ticket = comp.evaluate_signal(
        signal="SELL",
        market_price=Decimal("2500.00"),
        indicators={},
        broker=broker,
        timestamp=110.0,
    )
    assert close_ticket is not None
    assert close_ticket.side == OrderSide.BUY
    assert close_ticket.qty == comp.portfolio.position_qty


def _fresh_broker_competitor(cls, tick_price):
    # Tick the broker at the entry price the strategy will be evaluated at:
    # BrokerSim fills MARKET orders at its current price and RiskGuard
    # re-checks the position cap at that price, so a divergent tick price
    # can reject a ticket the strategy sized correctly (live: both are the
    # same tick, so they never diverge).
    broker = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0.0"))
    comp = cls()
    broker.register_portfolio(comp.portfolio, max_position_ratio=comp.max_position_ratio)
    broker.on_tick(tick_price, timestamp=100.0)
    return broker, comp


def _r_multiple(entry, stop, target, is_short):
    """Reward/risk of a bracket: long (TP-entry)/(entry-SL), short (entry-TP)/(SL-entry)."""
    if target is None:
        return None
    if is_short:
        return (entry - target) / (stop - entry)
    return (target - entry) / (entry - stop)


# (name, class, long_price, long_indicators, short_price, short_indicators,
#  expected long SL, expected long TP, expected short SL, expected short TP)
# ORB uses different entries per side (long breaks above 2480, short breaks
# below 2400) but the same 50.00 stop distance, so R is 2.0 on both sides.
# Session Mean uses mirrored pullbacks around the 2500 mean (2506 / 2494).
_MIRROR_CASES = [
    ("Aggressive", AggressiveCompetitor,
     Decimal("2500.00"), {"atr": Decimal("35.00")},
     Decimal("2500.00"), {"atr": Decimal("35.00")},
     Decimal("2412.50"), None, Decimal("2587.50"), None),
    ("Conservative", ConservativeCompetitor,
     Decimal("2500.00"), {},
     Decimal("2500.00"), {},
     Decimal("2475.00"), Decimal("2545.00"), Decimal("2525.00"), Decimal("2455.00")),
    ("Trailing Guard", TrailingGuardCompetitor,
     Decimal("2500.00"), {},
     Decimal("2500.00"), {},
     Decimal("2462.50"), None, Decimal("2537.50"), None),
    ("ORB", ORBCompetitor,
     Decimal("2490.00"), {"orb_high": Decimal("2480.00"), "orb_low": Decimal("2400.00"), "atr": Decimal("20.00")},
     Decimal("2390.00"), {"orb_high": Decimal("2480.00"), "orb_low": Decimal("2400.00"), "atr": Decimal("20.00")},
     Decimal("2440.00"), Decimal("2590.00"), Decimal("2440.00"), Decimal("2290.00")),
    ("Session Mean", SessionMeanPullbackCompetitor,
     Decimal("2506.00"), {"mean_ref": Decimal("2500.00"), "atr": Decimal("20.00"), "rsi": Decimal("48.00")},
     Decimal("2494.00"), {"mean_ref": Decimal("2500.00"), "atr": Decimal("20.00"), "rsi": Decimal("52.00")},
     Decimal("2490.00"), Decimal("2541.20"), Decimal("2510.00"), Decimal("2458.80")),
]


def test_evaluate_signal_short_entries_mirror_long_brackets_all_strategies():
    """P0 §2.1: every strategy's SELL ticket is the exact mirror of its BUY bracket.

    Extends test_evaluate_signal_short_entries_mirror_long_brackets (which
    only covers Aggressive) to all five strategies: the short stop sits above
    entry, the short target below entry, and the R multiple equals the long
    version's. Uncapped runners (Aggressive, Trailing Guard) have TP None on
    both sides and equal stop distances instead.
    """
    for (name, cls, long_price, long_ind, short_price, short_ind,
         exp_long_sl, exp_long_tp, exp_short_sl, exp_short_tp) in _MIRROR_CASES:
        broker, comp = _fresh_broker_competitor(cls, long_price)
        long_ticket = comp.evaluate_signal(
            signal="BUY", market_price=long_price, indicators=long_ind,
            broker=broker, timestamp=100.0, side=OrderSide.BUY,
        )
        assert long_ticket is not None, f"{name}: long entry returned None"
        assert long_ticket.side == OrderSide.BUY
        assert long_ticket.stop_loss == exp_long_sl, name
        assert long_ticket.take_profit == exp_long_tp, name
        assert long_ticket.qty > Decimal("0"), name

        broker, comp = _fresh_broker_competitor(cls, short_price)
        short_ticket = comp.evaluate_signal(
            signal="BUY", market_price=short_price, indicators=short_ind,
            broker=broker, timestamp=100.0, side=OrderSide.SELL,
        )
        assert short_ticket is not None, f"{name}: short entry returned None"
        assert short_ticket.side == OrderSide.SELL
        assert short_ticket.stop_loss == exp_short_sl, name
        assert short_ticket.take_profit == exp_short_tp, name
        assert short_ticket.qty > Decimal("0"), name
        # Mirror ordering: long stop below entry, short stop above entry.
        assert long_ticket.stop_loss < long_price, name
        assert short_ticket.stop_loss > short_price, name
        if short_ticket.take_profit is not None:
            assert long_ticket.take_profit is not None, f"{name}: long capped but short uncapped"
            assert long_ticket.take_profit > long_price, name
            assert short_ticket.take_profit < short_price, name
            assert _r_multiple(short_price, short_ticket.stop_loss, short_ticket.take_profit, True) == \
                _r_multiple(long_price, long_ticket.stop_loss, long_ticket.take_profit, False), name
        else:
            assert long_ticket.take_profit is None, f"{name}: short uncapped but long capped"
            assert short_ticket.stop_loss - short_price == long_price - long_ticket.stop_loss, name
        # The short ticket must actually open a short when submitted.
        fill = broker.submit_order(short_ticket)
        assert fill is not None, name
        assert comp.portfolio.position_side.value == "SHORT", name


def test_evaluate_signal_returns_none_when_breaker_tripped_all_strategies():
    """P0 §2.1: all five strategies return None once the breaker has tripped.

    The guard lives on the portfolio (portfolio.is_circuit_breaker_tripped)
    and sits at the top of every evaluate_signal, ahead of both the entry
    branches and the SELL-close (_close_ticket) path -- so a tripped breaker
    refuses BUY entries in either direction and also refuses to close an
    already-open position via evaluate_signal. The entry inputs below are
    the same ones that produce tickets in the mirror test, so None here can
    only come from the guard, not from failing entry conditions.
    """
    for (name, cls, long_price, long_ind, short_price, short_ind,
         _exp_long_sl, _exp_long_tp, _exp_short_sl, _exp_short_tp) in _MIRROR_CASES:
        broker, comp = _fresh_broker_competitor(cls, long_price)
        comp.portfolio.is_circuit_breaker_tripped = True
        assert comp.evaluate_signal(
            signal="BUY", market_price=long_price, indicators=long_ind,
            broker=broker, timestamp=100.0, side=OrderSide.BUY,
        ) is None, f"{name}: tripped BUY/long must return None"
        assert comp.evaluate_signal(
            signal="BUY", market_price=short_price, indicators=short_ind,
            broker=broker, timestamp=100.0, side=OrderSide.SELL,
        ) is None, f"{name}: tripped BUY/short must return None"
        assert comp.evaluate_signal(
            signal="SELL", market_price=long_price, indicators={},
            broker=broker, timestamp=100.0,
        ) is None, f"{name}: tripped SELL must return None"

        # SELL-close must also be refused when a position is already open:
        # without the guard, _close_ticket would return a covering ticket.
        broker, comp = _fresh_broker_competitor(cls, long_price)
        long_ticket = comp.evaluate_signal(
            signal="BUY", market_price=long_price, indicators=long_ind,
            broker=broker, timestamp=100.0, side=OrderSide.BUY,
        )
        assert long_ticket is not None, name
        assert broker.submit_order(long_ticket) is not None, name
        assert comp.portfolio.position_qty > Decimal("0"), name
        comp.portfolio.is_circuit_breaker_tripped = True
        assert comp.evaluate_signal(
            signal="SELL", market_price=long_price, indicators={},
            broker=broker, timestamp=110.0,
        ) is None, f"{name}: tripped SELL-close of open long must return None"

# =========================================================== P2-A
# P2 §2.10: zero-qty entries return None on all five strategies.
# ===========================================================


def test_strategy_qty_zero_returns_none():
    """P2 §2.10: all five strategies return None when the sized quantity
    computes to <= 0 -- no empty (zero-qty) ticket is ever sent, on
    either side. The entry inputs are the same ones that produce tickets
    in the mirror test; zeroing the portfolio cash drives
    compute_r_multiple_qty to exactly 0 (zero risk budget and zero
    affordable quantity), so None here can only come from the qty guard
    and not from failing entry conditions."""
    for (name, cls, long_price, long_ind, short_price, short_ind,
         _exp_long_sl, _exp_long_tp, _exp_short_sl, _exp_short_tp) in _MIRROR_CASES:
        for side, price, ind in ((OrderSide.BUY, long_price, long_ind),
                                 (OrderSide.SELL, short_price, short_ind)):
            broker, comp = _fresh_broker_competitor(cls, long_price)
            broker.on_tick(price, timestamp=100.0)
            comp.portfolio.cash = Decimal("0")
            # The sizing really does compute to zero on this setup.
            assert comp.compute_r_multiple_qty(price, Decimal("2400.00"), broker) == Decimal("0"), name
            assert comp.evaluate_signal(
                signal="BUY", market_price=price, indicators=ind,
                broker=broker, timestamp=100.0, side=side,
            ) is None, f"{name} {side}: zero-qty entry must return None"
            assert len(broker.execution_audit) == 0, f"{name} {side}: nothing was sent"
