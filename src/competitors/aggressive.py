from __future__ import annotations
from decimal import Decimal
from typing import Optional, Dict, Any
from src.arena.order import OrderTicket, OrderSide, OrderType, ExecutionReason
from src.arena.broker_sim import BrokerSim
from src.competitors.base import BaseCompetitor, CompetitorGenome


class AggressiveCompetitor(BaseCompetitor):
    """
    Profile A: Aggressive Momentum Breakout
    - Default Genome: 70% Position / 3.5% Wide Stop-Loss / Uncapped Run (Ride trends until reversal)
    - Supports cross-generation genetic evolution via CompetitorGenome
    """
    def __init__(self, portfolio_id: str = "comp_agg", initial_cash: Decimal = Decimal("500000.00")):
        default_genome = CompetitorGenome(
            position_ratio=Decimal("0.70"),
            risk_per_trade_pct=Decimal("0.025"),
            stop_loss_pct=Decimal("0.035"),
            take_profit_pct=None,
            generation=1
        )
        super().__init__(
            portfolio_id=portfolio_id,
            name="Aggressive (70% Size / 3.5% SL)",
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
            target_price = (
                (market_price * (Decimal("1") + self.genome.take_profit_pct)).quantize(Decimal("0.01"))
                if self.genome.take_profit_pct is not None
                else None
            )
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
