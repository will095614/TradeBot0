#!/usr/bin/env python3
"""Apply Item 1 (risk semantics) fixes to the TradeBot0 working tree.

Run once from the project root:  python scratch/fix_item1_patch.py
Verifies every replacement matches exactly once before writing anything,
and preserves each file's original newline style.
"""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------- base.py
BASE_R1_OLD = '''    leverage_enabled: bool = False
    leverage: Decimal = Decimal("1.0")
'''

BASE_R1_NEW = '''    leverage_enabled: bool = False
    leverage: Decimal = Decimal("1.0")

    def __post_init__(self) -> None:
        """Validate gene ranges (unleveraged-equity risk semantics).

        Bounds mirror the evolution clamps in GeneticEvolver.crossover_and_mutate,
        so any genome the evolver can produce passes, and anything outside is
        rejected at construction instead of silently trading on nonsense genes.
        """
        def _range(name: str, value: Decimal, low: Decimal, high: Decimal) -> None:
            if value < low or value > high:
                raise ValueError(f"CompetitorGenome.{name}={value} out of range [{low}, {high}]")

        _range("position_ratio", self.position_ratio, Decimal("0.20"), Decimal("0.75"))
        _range("risk_per_trade_pct", self.risk_per_trade_pct, Decimal("0.008"), Decimal("0.030"))
        _range("stop_loss_pct", self.stop_loss_pct, Decimal("0.006"), Decimal("0.035"))
        if self.take_profit_pct is not None:
            _range("take_profit_pct", self.take_profit_pct, Decimal("0.015"), Decimal("0.065"))
            # Risk:reward sanity: TP must pay at least 1.5R (same rule the evolver enforces).
            if self.take_profit_pct < self.stop_loss_pct * Decimal("1.5"):
                raise ValueError(
                    f"CompetitorGenome.take_profit_pct={self.take_profit_pct} < 1.5x stop_loss_pct={self.stop_loss_pct}"
                )
        _range("atr_risk_pct", self.atr_risk_pct, Decimal("0.008"), Decimal("0.025"))
        _range("atr_stop_mult", self.atr_stop_mult, Decimal("1.0"), Decimal("2.5"))
        _range("atr_target_mult", self.atr_target_mult, Decimal("2.0"), Decimal("4.5"))
        if self.atr_target_mult < self.atr_stop_mult * Decimal("1.5"):
            raise ValueError(
                f"CompetitorGenome.atr_target_mult={self.atr_target_mult} < 1.5x atr_stop_mult={self.atr_stop_mult}"
            )
        _range("trailing_trigger_pct", self.trailing_trigger_pct, Decimal("1.2"), Decimal("3.5"))
        _range("trailing_distance_pct", self.trailing_distance_pct, Decimal("0.004"), Decimal("0.012"))
        if self.cooldown_bars < 0:
            raise ValueError(f"CompetitorGenome.cooldown_bars={self.cooldown_bars} must be >= 0")
        if self.generation < 1:
            raise ValueError(f"CompetitorGenome.generation={self.generation} must be >= 1")
        _range("leverage", self.leverage, Decimal("1.0"), Decimal("5.0"))
'''

BASE_R2_OLD = '''        Dynamic R-Multiple Volatility & Stop-Distance Adjusted Sizing (day-trader-skill Budget Manager).
        Sizes position so max loss if stopped out <= risk_budget (equity * risk_per_trade_pct).
        Strictly bounded by genome.position_ratio (scaled with leverage) and broker available margin.
        """
        if entry_price <= Decimal("0"):
            return Decimal("0")
        # For ETH/Crypto, minimum stop distance is $2.00
        stop_dist = max(Decimal("2.00"), abs(entry_price - stop_price))
        eff_lev = self.genome.leverage if self.genome.leverage_enabled and self.genome.leverage > Decimal("0") else Decimal("1.0")
        budget = (
            risk_budget
            if risk_budget is not None
            else (self.portfolio.total_equity * self.genome.risk_per_trade_pct * eff_lev)
        )
        risk_qty = (budget / stop_dist).quantize(Decimal("0.0001"), rounding=ROUND_DOWN)
        max_cap_val = self.portfolio.total_equity * self.genome.position_ratio * eff_lev
'''

BASE_R2_NEW = '''        Dynamic R-Multiple Volatility & Stop-Distance Adjusted Sizing (day-trader-skill Budget Manager).
        Sizes position so max loss if stopped out <= risk_budget (equity * risk_per_trade_pct).
        Risk budget and position cap are struck on UNLEVERAGED total equity:
        leverage only affects margin affordability (inside compute_safe_buy_qty),
        never the amount of equity risked or the notional cap.
        Strictly bounded by genome.position_ratio (unleveraged equity basis) and broker available margin.
        """
        if entry_price <= Decimal("0"):
            return Decimal("0")
        # For ETH/Crypto, minimum stop distance is $2.00
        stop_dist = max(Decimal("2.00"), abs(entry_price - stop_price))
        budget = (
            risk_budget
            if risk_budget is not None
            else (self.portfolio.total_equity * self.genome.risk_per_trade_pct)
        )
        risk_qty = (budget / stop_dist).quantize(Decimal("0.0001"), rounding=ROUND_DOWN)
        max_cap_val = self.portfolio.total_equity * self.genome.position_ratio
'''

# ------------------------------------------------------- atr_dynamic.py
ATR_OLD = '''            eff_lev = self.genome.leverage if self.genome.leverage_enabled else Decimal("1.0")
            risk_budget = self.portfolio.total_equity * self.genome.atr_risk_pct * eff_lev
'''

ATR_NEW = '''            # Risk budget is struck on unleveraged equity; leverage never inflates it.
            risk_budget = self.portfolio.total_equity * self.genome.atr_risk_pct
'''

# ---------------------------------------------------------- risk_guard.py
GUARD_OLD = '''        # Check maximum single position cap relative to total equity with leverage
        max_allowed_val = (portfolio.total_equity * max_position_ratio * eff_lev * Decimal("1.005")).quantize(
            PRECISION_CASH, rounding=ROUND_HALF_UP
        )
        current_pos_val = (portfolio.position_qty * market_price).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
        if (current_pos_val + order_val) > max_allowed_val:
            return False, f"Order exceeds max position cap ({max_position_ratio * eff_lev * Decimal('100')}%)"
'''

GUARD_NEW = '''        # Check maximum single position cap relative to UNLEVERAGED total equity.
        # Leverage affects only the margin required (below), never the notional cap.
        max_allowed_val = (portfolio.total_equity * max_position_ratio * Decimal("1.005")).quantize(
            PRECISION_CASH, rounding=ROUND_HALF_UP
        )
        current_pos_val = (portfolio.position_qty * market_price).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
        if (current_pos_val + order_val) > max_allowed_val:
            return False, f"Order exceeds max position cap ({max_position_ratio * Decimal('100')}% of equity)"
'''

# ----------------------------------------------------------- evolution.py
EVO_OLD = '''        new_atr_sl = cls._clamp_decimal(blend(parent1.atr_stop_mult, parent2.atr_stop_mult, 0.12), "1.0", "2.5", "0.1")
        new_atr_tp = cls._clamp_decimal(blend(parent1.atr_target_mult, parent2.atr_target_mult, 0.15), "2.0", "4.5", "0.1")
'''

EVO_NEW = '''        new_atr_sl = cls._clamp_decimal(blend(parent1.atr_stop_mult, parent2.atr_stop_mult, 0.12), "1.0", "2.5", "0.1")
        new_atr_tp = cls._clamp_decimal(blend(parent1.atr_target_mult, parent2.atr_target_mult, 0.15), "2.0", "4.5", "0.1")
        # Ensure ATR Risk:Reward >= 1.5 (mirrors the TP rule above)
        if new_atr_tp < (new_atr_sl * Decimal("1.5")):
            new_atr_tp = cls._clamp_decimal(new_atr_sl * Decimal("1.8"), "2.0", "4.5", "0.1")
'''

# -------------------------------------------------------- live_engine.py
ENGINE_OLD = '''                        if gd:
                            new_genome = CompetitorGenome(
                                position_ratio=Decimal(str(gd.get("position_ratio", "0.40"))),
                                risk_per_trade_pct=Decimal(str(gd.get("risk_per_trade_pct", "0.015"))),
                                stop_loss_pct=Decimal(str(gd.get("stop_loss_pct", "0.015"))),
                                take_profit_pct=Decimal(str(gd["take_profit_pct"])) if gd.get("take_profit_pct") is not None else None,
                                atr_risk_pct=Decimal(str(gd.get("atr_risk_pct", "0.015"))),
                                atr_stop_mult=Decimal(str(gd.get("atr_stop_mult", "1.5"))),
                                atr_target_mult=Decimal(str(gd.get("atr_target_mult", "2.5"))),
                                trailing_trigger_pct=Decimal(str(gd.get("trailing_trigger_pct", "2.0"))),
                                trailing_distance_pct=Decimal(str(gd.get("trailing_distance_pct", "0.006"))),
                                cooldown_bars=int(gd.get("cooldown_bars", 0)),
                                generation=int(gd.get("generation", 1)),
                                leverage_enabled=bool(gd.get("leverage_enabled", False)),
                                leverage=Decimal(str(gd.get("leverage", "1.0"))),
                            )
                            c.genome = new_genome
                            c.max_position_ratio = new_genome.position_ratio
                            gen_tag = f" [G{new_genome.generation}]" if new_genome.generation > 1 else ""
                            c.name = f"{c.base_name}{gen_tag}"
'''

ENGINE_NEW = '''                        if gd:
                            try:
                                new_genome = CompetitorGenome(
                                    position_ratio=Decimal(str(gd.get("position_ratio", "0.40"))),
                                    risk_per_trade_pct=Decimal(str(gd.get("risk_per_trade_pct", "0.015"))),
                                    stop_loss_pct=Decimal(str(gd.get("stop_loss_pct", "0.015"))),
                                    take_profit_pct=Decimal(str(gd["take_profit_pct"])) if gd.get("take_profit_pct") is not None else None,
                                    atr_risk_pct=Decimal(str(gd.get("atr_risk_pct", "0.015"))),
                                    atr_stop_mult=Decimal(str(gd.get("atr_stop_mult", "1.5"))),
                                    atr_target_mult=Decimal(str(gd.get("atr_target_mult", "2.5"))),
                                    trailing_trigger_pct=Decimal(str(gd.get("trailing_trigger_pct", "2.0"))),
                                    trailing_distance_pct=Decimal(str(gd.get("trailing_distance_pct", "0.006"))),
                                    cooldown_bars=int(gd.get("cooldown_bars", 0)),
                                    generation=int(gd.get("generation", 1)),
                                    leverage_enabled=bool(gd.get("leverage_enabled", False)),
                                    leverage=Decimal(str(gd.get("leverage", "1.0"))),
                                )
                            except ValueError as e:
                                # Stored genome fails validation (e.g. written by an older
                                # version): keep the strategy default genome instead of
                                # breaking the whole restore.
                                self.log_event("RESTORE_WARN", f"{c.portfolio_id} stored genome invalid ({e}); keeping default genome", "loss")
                                new_genome = None
                            if new_genome is not None:
                                c.genome = new_genome
                                c.max_position_ratio = new_genome.position_ratio
                                gen_tag = f" [G{new_genome.generation}]" if new_genome.generation > 1 else ""
                                c.name = f"{c.base_name}{gen_tag}"
'''

# ------------------------------------------------- tests/test_competitors.py
COMP_TEST_OLD = '''    # Check that positions reflect their specific risk budgets and leverage
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
'''

COMP_TEST_NEW = '''    # Check that positions reflect their specific risk budgets on UNLEVERAGED equity.
    # Leverage affects only margin affordability, never the risk budget or notional cap.
    # A (Aggressive: risk 2.5% of 100,000 = $2,500 / $87.50 stop = 28.5714 ETH,
    #    capped by 70% position cap $70,000 / 2500 = 28.0000 ETH)
    assert comp_a.portfolio.position_qty == Decimal("28.0000")
    # B (Conservative Spot 1x ~25% of 100,000 = $25,000 / 2500 = 10 BTC)
    assert comp_b.portfolio.position_qty == Decimal("10.0000")
    # C (ATR Dynamic 2x Lev)
    assert comp_c.portfolio.position_qty > Decimal("0")
    # D (Trailing Guard: risk 1.5% of 100,000 = $1,500 / $37.50 stop = 40 ETH,
    #    capped by 40% position cap $40,000 / 2500 = 16.0000 ETH)
    assert comp_d.portfolio.position_qty == Decimal("16.0000")
    # E (ORB Breakout: risk 1.5% of 100,000 = $1,500 / $45 stop = 33.3333 ETH,
    #    capped by 45% position cap $45,000 / 2500 = 18.0000 ETH)
    assert comp_e.portfolio.position_qty == Decimal("18.0000")
'''

# ------------------------------------------------- tests/test_broker_sim.py
LIQ_OLD = '''def test_broker_sim_leverage_liquidation_protection():
    from src.arena.order import ExecutionReason
    broker = BrokerSim(symbol="BTC/USD", slippage_pct=Decimal("0.0"))
    p = Portfolio(
        "p_lev",
        "LeveragedTrader",
        initial_cash=Decimal("10000.00"),
        leverage=Decimal("3.0"),
        leverage_enabled=True
    )
    broker.register_portfolio(p, max_position_ratio=Decimal("0.90"))

    # Buy 0.3 BTC at $80,000 (Position value = $24,000, margin locked = $8,000)
    broker.on_tick(price=Decimal("80000.00"), timestamp=100.0)
    ticket = OrderTicket("p_lev", "BTC/USD", OrderSide.BUY, OrderType.MARKET, qty=Decimal("0.3"), timestamp=100.0)
    fill = broker.submit_order(ticket)
    assert fill is not None
    assert p.position_qty == Decimal("0.3000")
    assert p.margin_locked == Decimal("8000.00")

    # Severe flash crash: BTC drops to $48,000
    # Unrealized loss = (48,000 - 80,000) * 0.3 = -$9,600
    # Total equity = $10,000 - $9,600 - fee = ~$376 <= 10% of $8,000 ($800)
    fills = broker.on_tick(price=Decimal("48000.00"), timestamp=101.0)
    assert len(fills) == 1
    assert fills[0].reason == ExecutionReason.LIQUIDATION
    assert p.position_qty == Decimal("0.0000")
    assert p.is_circuit_breaker_tripped is True
'''

LIQ_NEW = '''def test_broker_sim_leverage_liquidation_protection():
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
'''

PATCHES = [
    ("src/competitors/base.py", [(BASE_R1_OLD, BASE_R1_NEW), (BASE_R2_OLD, BASE_R2_NEW)]),
    ("src/competitors/atr_dynamic.py", [(ATR_OLD, ATR_NEW)]),
    ("src/arena/risk_guard.py", [(GUARD_OLD, GUARD_NEW)]),
    ("src/arena/evolution.py", [(EVO_OLD, EVO_NEW)]),
    ("src/data/live_engine.py", [(ENGINE_OLD, ENGINE_NEW)]),
    ("tests/test_competitors.py", [(COMP_TEST_OLD, COMP_TEST_NEW)]),
    ("tests/test_broker_sim.py", [(LIQ_OLD, LIQ_NEW)]),
]

RISK_TEST = '''# Item 1: risk semantics - risk budget and position cap are struck on
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
from src.competitors.vwap import VWAPPullbackCompetitor


def _broker():
    return BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0.0"))


def test_aggressive_stopout_loss_capped_at_risk_pct():
    # Aggressive: 3x leverage, 2.5% risk. A single stop-out must lose <= 2.5% of equity.
    comp = AggressiveCompetitor()
    broker = _broker()
    broker.register_portfolio(comp.portfolio, max_position_ratio=comp.max_position_ratio)
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
                TrailingGuardCompetitor, ORBCompetitor, VWAPPullbackCompetitor):
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
'''

NEW_FILES = [
    ("tests/test_risk_semantics.py", RISK_TEST),
]


def _read(path):
    with open(path, "rb") as f:
        raw = f.read()
    nl = "\r\n" if b"\r\n" in raw else "\n"
    text = raw.decode("utf-8").replace("\r\n", "\n")
    return text, nl


def main():
    staged = []
    for rel, reps in PATCHES:
        path = os.path.join(PROJECT_ROOT, rel)
        text, nl = _read(path)
        for old, new in reps:
            n = text.count(old)
            if n != 1:
                print(f"FAIL {rel}: match count {n} (expected 1)")
                sys.exit(1)
            text = text.replace(old, new)
        staged.append((path, text, nl))
    for rel, _content in NEW_FILES:
        path = os.path.join(PROJECT_ROOT, rel)
        if os.path.exists(path):
            print(f"FAIL {rel}: already exists")
            sys.exit(1)
    for path, text, nl in staged:
        with open(path, "wb") as f:
            f.write(text.replace("\n", nl).encode("utf-8"))
        print(f"patched {os.path.relpath(path, PROJECT_ROOT)}")
    for rel, content in NEW_FILES:
        path = os.path.join(PROJECT_ROOT, rel)
        with open(path, "wb") as f:
            f.write(content.encode("utf-8"))
        print(f"created {rel}")
    print("ITEM1 PATCH OK")


if __name__ == "__main__":
    main()
