from __future__ import annotations
from decimal import Decimal
from typing import Optional, Dict, Any
from src.arena.order import OrderTicket, OrderSide, OrderType, ExecutionReason
from src.arena.broker_sim import BrokerSim
from src.competitors.base import BaseCompetitor, CompetitorGenome


class ConservativeCompetitor(BaseCompetitor):
    """
    Profile B: Conservative Scalper / Mean Reversion
    - Default Genome: 25% Position / 1.0% Tight Stop-Loss / 1.8% Take-Profit
    - Supports cross-generation genetic evolution via CompetitorGenome
    """
    def __init__(self, portfolio_id: str = "comp_cons", initial_cash: Decimal = Decimal("500000.00")):
        default_genome = CompetitorGenome(
            position_ratio=Decimal("0.25"),
            risk_per_trade_pct=Decimal("0.010"),
            stop_loss_pct=Decimal("0.010"),
            take_profit_pct=Decimal("0.018"),
            generation=1
        )
        super().__init__(
            portfolio_id=portfolio_id,
            name="Conservative (25% Size / 1.0% SL / 1.8% TP)",
            max_position_ratio=default_genome.position_ratio,
            initial_cash=initial_cash,
            genome=default_genome
        )

    def evaluate_signal(
        self,
        signal: str,
        market_price: Decimal,
        indicators: Dict[str, Any],
        broker: BrokerSim,
        timestamp: float
    ) -> Optional[OrderTicket]:
        if self.portfolio.is_circuit_breaker_tripped:
            return None

        if signal == "BUY" and self.portfolio.position_qty == Decimal("0"):
            stop_price = (market_price * (Decimal("1") - self.genome.stop_loss_pct)).quantize(Decimal("0.01"))
            tp_pct = self.genome.take_profit_pct if self.genome.take_profit_pct is not None else Decimal("0.018")
            target_price = (market_price * (Decimal("1") + tp_pct)).quantize(Decimal("0.01"))

            qty = self.compute_r_multiple_qty(market_price, stop_price, broker)
            if qty <= Decimal("0"):
                return None

            return OrderTicket(
                portfolio_id=self.portfolio_id,
                symbol=broker.symbol,
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                qty=qty,
                stop_loss=stop_price,
                take_profit=target_price,
                reason=ExecutionReason.SIGNAL,
                timestamp=timestamp
            )

        elif signal == "SELL" and self.portfolio.position_qty > Decimal("0"):
            self.last_exit_ts = timestamp
            return OrderTicket(
                portfolio_id=self.portfolio_id,
                symbol=broker.symbol,
                side=OrderSide.SELL,
                order_type=OrderType.MARKET,
                qty=self.portfolio.position_qty,
                reason=ExecutionReason.SIGNAL,
                timestamp=timestamp
            )

        return None
