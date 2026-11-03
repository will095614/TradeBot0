from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, replace
from decimal import Decimal, ROUND_DOWN
from typing import Optional, Dict, Any
from src.arena.order import OrderTicket
from src.arena.portfolio import Portfolio
from src.arena.broker_sim import BrokerSim


@dataclass(frozen=True)
class CompetitorGenome:
    """
    Evolvable Risk & Exit Parameter Genome (Style B: Homogeneous Strategy, Heterogeneous Genes).
    """
    position_ratio: Decimal = Decimal("0.40")
    risk_per_trade_pct: Decimal = Decimal("0.015")
    stop_loss_pct: Decimal = Decimal("0.015")
    take_profit_pct: Optional[Decimal] = Decimal("0.025")
    atr_risk_pct: Decimal = Decimal("0.015")
    atr_stop_mult: Decimal = Decimal("1.5")
    atr_target_mult: Decimal = Decimal("2.5")
    trailing_trigger_pct: Decimal = Decimal("2.0")
    trailing_distance_pct: Decimal = Decimal("0.006")
    cooldown_bars: int = 0
    generation: int = 1


class BaseCompetitor(ABC):
    """
    Abstract Base Class for Arena Competitors.
    All competitors share the identical market signal input but differ in risk & exit genes.
    Supports genetic evolution across generations.
    """
    def __init__(
        self,
        portfolio_id: str,
        name: str,
        max_position_ratio: Decimal,
        initial_cash: Decimal = Decimal("500000.00"),
        genome: Optional[CompetitorGenome] = None
    ):
        self.portfolio_id: str = portfolio_id
        self.base_name: str = name
        self.name: str = name
        self.max_position_ratio: Decimal = max_position_ratio
        self.initial_cash: Decimal = initial_cash
        self.genome: CompetitorGenome = genome or CompetitorGenome(position_ratio=max_position_ratio)
        self.portfolio: Portfolio = Portfolio(
            portfolio_id=portfolio_id,
            name=name,
            initial_cash=initial_cash
        )
        self.last_exit_ts: float = 0.0

    def reset_for_new_generation(self, new_genome: CompetitorGenome, preserve_portfolio: bool = True) -> None:
        self.genome = new_genome
        self.max_position_ratio = new_genome.position_ratio
        gen_tag = f" [G{new_genome.generation}]" if new_genome.generation > 1 else ""
        self.name = f"{self.base_name}{gen_tag}"
        if not preserve_portfolio:
            self.portfolio = Portfolio(
                portfolio_id=self.portfolio_id,
                name=self.name,
                initial_cash=self.initial_cash
            )
            self.last_exit_ts = 0.0
        else:
            self.portfolio.name = self.name

    def compute_safe_buy_qty(
        self,
        target_val: Decimal,
        market_price: Decimal,
        broker: BrokerSim
    ) -> Decimal:
        """
        Computes whole-precision crypto quantity that fits within both target_val
        and available cash after slippage and exchange fee buffers.
        """
        if market_price <= Decimal("0"):
            return Decimal("0")
        raw_qty = (target_val / market_price).quantize(Decimal("0.0001"), rounding=ROUND_DOWN)
        # Ensure we never exceed available cash after slippage + fee
        cost_mult = (Decimal("1") + broker.slippage_pct) * (Decimal("1") + self.portfolio.fee_rate)
        max_affordable_qty = (self.portfolio.cash / (market_price * cost_mult)).quantize(
            Decimal("0.0001"), rounding=ROUND_DOWN
        )
        return min(raw_qty, max_affordable_qty)

    def compute_r_multiple_qty(
        self,
        entry_price: Decimal,
        stop_price: Decimal,
        broker: BrokerSim,
        risk_budget: Optional[Decimal] = None
    ) -> Decimal:
        """
        Dynamic R-Multiple Volatility & Stop-Distance Adjusted Sizing (day-trader-skill Budget Manager).
        Sizes position so max loss if stopped out <= risk_budget (equity * risk_per_trade_pct).
        Strictly bounded by genome.position_ratio and broker available cash after fee & slippage.
        """
        if entry_price <= Decimal("0"):
            return Decimal("0")
        stop_dist = max(Decimal("1.00"), abs(entry_price - stop_price))
        budget = (
            risk_budget
            if risk_budget is not None
            else (self.portfolio.total_equity * self.genome.risk_per_trade_pct)
        )
        risk_qty = (budget / stop_dist).quantize(Decimal("0.0001"), rounding=ROUND_DOWN)
        max_cap_val = self.portfolio.total_equity * self.genome.position_ratio
        safe_cap_qty = self.compute_safe_buy_qty(max_cap_val, entry_price, broker)
        return min(risk_qty, safe_cap_qty)

    @abstractmethod
    def evaluate_signal(
        self,
        signal: str,  # "BUY", "SELL", or "HOLD"
        market_price: Decimal,
        indicators: Dict[str, Any],
        broker: BrokerSim,
        timestamp: float
    ) -> Optional[OrderTicket]:
        """
        Translates a raw strategy signal into a sized, risk-managed OrderTicket.
        """
        pass
