from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, replace
from decimal import Decimal, ROUND_DOWN
from typing import Optional, Dict, Any
from src.arena.order import OrderTicket, OrderSide, OrderType, PositionSide, ExecutionReason
from src.arena.portfolio import Portfolio
from src.arena.broker_sim import BrokerSim


@dataclass(frozen=True)
class CompetitorGenome:
    """
    Evolvable Risk, Exit & Leverage Parameter Genome (Homogeneous Strategy, Heterogeneous Genes).
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
    leverage_enabled: bool = False
    leverage: Decimal = Decimal("1.0")
    # News sensitivity (item 12C): how much macro news scales this
    # strategy's position size (0.0 = news-blind, 1.0 = full effect).
    # Fixed per strategy slot; evolution never mutates it. Kept last so
    # positional construction order of the other genes is unchanged.
    news_sensitivity: float = 0.5

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
        if not 0.0 <= float(self.news_sensitivity) <= 1.0:
            raise ValueError(
                f"CompetitorGenome.news_sensitivity={self.news_sensitivity} out of range [0.0, 1.0]"
            )


class BaseCompetitor(ABC):
    """
    Abstract Base Class for Arena Competitors.
    All competitors share the identical market signal input but differ in risk, exit, and leverage genes.
    Supports genetic evolution across generations.
    """
    # News sensitivity for this strategy slot (item 12C, phase 1): fixed
    # per strategy, never mutated by evolution. Subclasses override.
    NEWS_SENSITIVITY: float = 0.5

    def __init__(
        self,
        portfolio_id: str,
        name: str,
        max_position_ratio: Decimal,
        initial_cash: Decimal = Decimal("100000.00"),
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
            initial_cash=initial_cash,
            leverage=self.genome.leverage if self.genome.leverage_enabled else Decimal("1.0"),
            leverage_enabled=self.genome.leverage_enabled
        )
        self.last_exit_ts: float = 0.0

    def reset_for_new_generation(self, new_genome: CompetitorGenome, preserve_portfolio: bool = True) -> None:
        # News sensitivity is a property of the strategy slot, not the
        # genome lineage: a genome crossed from another strategy's
        # champion must not change this slot's sensitivity (item 12C:
        # fixed per strategy in phase 1).
        try:
            sens = float(getattr(new_genome, "news_sensitivity", self.NEWS_SENSITIVITY))
        except (TypeError, ValueError):
            sens = float(self.NEWS_SENSITIVITY)
        if sens != float(self.NEWS_SENSITIVITY):
            new_genome = replace(new_genome, news_sensitivity=float(self.NEWS_SENSITIVITY))
        self.genome = new_genome
        self.max_position_ratio = new_genome.position_ratio
        gen_tag = f" [G{new_genome.generation}]" if new_genome.generation > 1 else ""
        self.name = f"{self.base_name}{gen_tag}"
        eff_lev = new_genome.leverage if new_genome.leverage_enabled else Decimal("1.0")
        if not preserve_portfolio:
            self.portfolio = Portfolio(
                portfolio_id=self.portfolio_id,
                name=self.name,
                initial_cash=self.initial_cash,
                leverage=eff_lev,
                leverage_enabled=new_genome.leverage_enabled
            )
            self.last_exit_ts = 0.0
        else:
            self.portfolio.name = self.name
            self.portfolio.leverage = eff_lev
            self.portfolio.leverage_enabled = new_genome.leverage_enabled
            if self.portfolio.is_circuit_breaker_tripped:
                # Generation boundary = fresh risk clock. Resetting the flag
                # alone is not enough: max_drawdown_pct is sticky, so the
                # next bar (broker_sim) or order (risk_guard) would re-trip
                # the breaker immediately and the strategy would stay dead
                # forever while its equity-ranked genome is kept as ELITE.
                # Clear the drawdown clock as well so the strategy gets one
                # clean evaluation window next generation.
                self.portfolio.is_circuit_breaker_tripped = False
                self.portfolio.max_drawdown_pct = Decimal("0.00")
                self.portfolio.peak_equity = self.portfolio.total_equity

    def _close_ticket(self, broker: BrokerSim, timestamp: float) -> Optional[OrderTicket]:
        """Market ticket closing the full open position, if any.

        Side is the opposite of the current position (BUY covers a short,
        SELL exits a long), so a SELL signal closes either direction.
        """
        if self.portfolio.position_qty <= Decimal("0"):
            return None
        close_side = OrderSide.BUY if self.portfolio.position_side == PositionSide.SHORT else OrderSide.SELL
        return OrderTicket(
            portfolio_id=self.portfolio_id,
            symbol=broker.symbol,
            side=close_side,
            order_type=OrderType.MARKET,
            qty=self.portfolio.position_qty,
            reason=ExecutionReason.SIGNAL_EXIT,
            timestamp=timestamp
        )

    def compute_safe_buy_qty(
        self,
        target_val: Decimal,
        market_price: Decimal,
        broker: BrokerSim
    ) -> Decimal:
        """
        Computes whole-precision crypto quantity that fits within both target_val
        and available margin/cash after slippage and exchange fee buffers.
        """
        if market_price <= Decimal("0"):
            return Decimal("0")
        raw_qty = (target_val / market_price).quantize(Decimal("0.0001"), rounding=ROUND_DOWN)
        cost_mult = (Decimal("1") + broker.slippage_pct) * (Decimal("1") + self.portfolio.fee_rate)
        eff_lev = self.genome.leverage if self.genome.leverage_enabled and self.genome.leverage > Decimal("0") else Decimal("1.0")
        max_purchasing_power = self.portfolio.cash * eff_lev
        max_affordable_qty = (max_purchasing_power / (market_price * cost_mult)).quantize(
            Decimal("0.0001"), rounding=ROUND_DOWN
        )
        return min(raw_qty, max_affordable_qty)

    def compute_r_multiple_qty(
        self,
        entry_price: Decimal,
        stop_price: Decimal,
        broker: BrokerSim,
        risk_budget: Optional[Decimal] = None,
        sizing_multiplier: Decimal = Decimal("1.0"),
    ) -> Decimal:
        """
        Dynamic R-Multiple Volatility & Stop-Distance Adjusted Sizing (day-trader-skill Budget Manager).
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
        # News sizing (item 12C): scale the risk budget by the news factor.
        # The position-ratio cap below is NOT scaled: it stays the safety
        # max, so an optimistic regime can never push size past the cap.
        sizing_multiplier = max(Decimal("0.5"), min(Decimal("1.5"), sizing_multiplier))
        budget = budget * sizing_multiplier
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
        timestamp: float,
        side: OrderSide = OrderSide.BUY,
        sizing_multiplier: Decimal = Decimal("1.0"),
    ) -> Optional[OrderTicket]:
        """
        Translates a raw strategy signal into a sized, risk-managed OrderTicket.

        Single entry/exit contract shared by backtest (TimeMachine) and live
        (LiveArenaEngine): the strategy owns bracket math (SL / TP / sizing)
        from its genome; the caller owns signal generation and live-only gates
        (MTF, macro veto, MC EV gate, cooldown).
        - signal "BUY": entry intent in the direction of `side`
          (BUY = open long, SELL = open short).
        - signal "SELL": close the existing position, if any (opposite side
          of the current position; BUY to cover a short, SELL to exit a long).
        - signal "HOLD": no new ticket (trailing management still runs where
          implemented).
        """
        pass
