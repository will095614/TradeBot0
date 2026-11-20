from __future__ import annotations
from decimal import Decimal
from typing import Optional, Dict, Any
from src.arena.order import OrderTicket, OrderSide, OrderType, ExecutionReason
from src.arena.broker_sim import BrokerSim
from src.competitors.base import BaseCompetitor, CompetitorGenome


class ConservativeCompetitor(BaseCompetitor):
    """
    Profile B: Conservative Scalper / Mean Reversion
    - Default Genome: 25% Position / Spot 1x (Leverage Disabled) / 1.0% Tight Stop-Loss / 1.8% Take-Profit
    - Supports cross-generation genetic evolution via CompetitorGenome
    """
    # News sensitivity (item 12C): conservative barely moves on news.
    NEWS_SENSITIVITY: float = 0.3

    def __init__(self, portfolio_id: str = "comp_cons", initial_cash: Decimal = Decimal("100000.00")):
        default_genome = CompetitorGenome(
            position_ratio=Decimal("0.25"),
            risk_per_trade_pct=Decimal("0.010"),
            stop_loss_pct=Decimal("0.010"),
            take_profit_pct=Decimal("0.018"),
            generation=1,
            leverage_enabled=False,
            leverage=Decimal("1.0"),
            news_sensitivity=0.3
        )
        super().__init__(
            portfolio_id=portfolio_id,
            name="Conservative (Spot 1x / 25% Size / 1.0% SL / 1.8% TP)",
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
        timestamp: float,
        side: OrderSide = OrderSide.BUY,
        sizing_multiplier: Decimal = Decimal("1.0"),
    ) -> Optional[OrderTicket]:
        if self.portfolio.is_circuit_breaker_tripped or not market_price.is_finite() or market_price <= Decimal("0"):
            return None

        if signal == "BUY" and side == OrderSide.BUY and self.portfolio.position_qty == Decimal("0"):
            stop_price = max(Decimal("0.01"), (market_price * (Decimal("1") - self.genome.stop_loss_pct)).quantize(Decimal("0.01")))
            tp_pct = self.genome.take_profit_pct if self.genome.take_profit_pct is not None else Decimal("0.018")
            target_price = (market_price * (Decimal("1") + tp_pct)).quantize(Decimal("0.01"))
            if stop_price >= market_price or target_price <= market_price:
                return None

            qty = self.compute_r_multiple_qty(market_price, stop_price, broker, sizing_multiplier=sizing_multiplier)
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
                reason=ExecutionReason.SIGNAL_ENTRY,
                timestamp=timestamp
            )

        elif signal == "BUY" and side == OrderSide.SELL and self.portfolio.position_qty == Decimal("0"):
            stop_price = (market_price * (Decimal("1") + self.genome.stop_loss_pct)).quantize(Decimal("0.01"))
            tp_pct = self.genome.take_profit_pct if self.genome.take_profit_pct is not None else Decimal("0.018")
            target_price = max(Decimal("0.01"), (market_price * (Decimal("1") - tp_pct)).quantize(Decimal("0.01")))
            if stop_price <= market_price or target_price >= market_price:
                return None

            qty = self.compute_r_multiple_qty(market_price, stop_price, broker, sizing_multiplier=sizing_multiplier)
            if qty <= Decimal("0"):
                return None

            return OrderTicket(
                portfolio_id=self.portfolio_id,
                symbol=broker.symbol,
                side=OrderSide.SELL,
                order_type=OrderType.MARKET,
                qty=qty,
                stop_loss=stop_price,
                take_profit=target_price,
                reason=ExecutionReason.SIGNAL_ENTRY,
                timestamp=timestamp
            )
        elif signal == "SELL":
            return self._close_ticket(broker, timestamp)

        return None
