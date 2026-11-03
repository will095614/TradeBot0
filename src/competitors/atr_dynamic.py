from __future__ import annotations
from decimal import Decimal, ROUND_DOWN
from typing import Optional, Dict, Any
from src.arena.order import OrderTicket, OrderSide, OrderType, ExecutionReason
from src.arena.broker_sim import BrokerSim
from src.competitors.base import BaseCompetitor, CompetitorGenome


class ATRDynamicCompetitor(BaseCompetitor):
    """
    Profile C: ATR Dynamic Volatility Adaptive
    - Position Sizing: Scales dynamically based on 14-period ATR volatility.
    - Default Stop-Loss: 1.5x ATR
    - Default Take-Profit: 2.5x ATR (1:1.67 Risk/Reward)
    """
    def __init__(self, portfolio_id: str = "comp_atr", initial_cash: Decimal = Decimal("500000.00")):
        default_genome = CompetitorGenome(
            position_ratio=Decimal("0.50"),
            atr_risk_pct=Decimal("0.015"),
            atr_stop_mult=Decimal("1.5"),
            atr_target_mult=Decimal("2.5"),
            generation=1
        )
        super().__init__(
            portfolio_id=portfolio_id,
            name="ATR Dynamic (Adaptive SL/TP)",
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
            atr_val = indicators.get("atr", market_price * Decimal("0.015"))
            if atr_val is None:
                atr_val = market_price * Decimal("0.015")
            elif not isinstance(atr_val, Decimal):
                atr_val = Decimal(str(atr_val))
            if atr_val <= Decimal("0"):
                atr_val = market_price * Decimal("0.015")

            stop_dist = max(Decimal("1.00"), (atr_val * self.genome.atr_stop_mult).quantize(Decimal("0.01")))
            target_dist = max(Decimal("1.50"), (atr_val * self.genome.atr_target_mult).quantize(Decimal("0.01")))
            stop_price = max(Decimal("0.01"), (market_price - stop_dist).quantize(Decimal("0.01")))
            target_price = (market_price + target_dist).quantize(Decimal("0.01"))

            # Sized via Dynamic R-Multiple with ATR Risk Budget
            risk_budget = self.portfolio.total_equity * self.genome.atr_risk_pct
            qty = self.compute_r_multiple_qty(market_price, stop_price, broker, risk_budget=risk_budget)

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
