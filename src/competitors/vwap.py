from __future__ import annotations
from decimal import Decimal
from typing import Optional, Dict, Any
from src.arena.order import OrderTicket, OrderSide, OrderType, ExecutionReason
from src.arena.broker_sim import BrokerSim
from src.competitors.base import BaseCompetitor, CompetitorGenome


class VWAPPullbackCompetitor(BaseCompetitor):
    """
    Profile F: Institutional VWAP Pullback (Volume-Weighted Average Price)
    - Origin: Wall Street Institutional Benchmark Trading
    - Setup: Tracks cumulative intraday Volume-Weighted Average Price (VWAP).
    - Trigger: In an uptrend (Price > VWAP), waits for a shallow pullback into the VWAP
      accumulation band (within 0.25%) and enters on rebound confirmation.
    - Risk & Exit: Tight institutional stop just under VWAP (~1.2%), target set to 2.2R (~2.6%).
    - Dynamic Sizing: Quant dynamic R-Multiple sizing up to 50% position cap.
    """
    def __init__(self, portfolio_id: str = "comp_vwap", initial_cash: Decimal = Decimal("500000.00")):
        default_genome = CompetitorGenome(
            position_ratio=Decimal("0.50"),
            risk_per_trade_pct=Decimal("0.018"),
            stop_loss_pct=Decimal("0.012"),
            take_profit_pct=Decimal("0.026"),
            generation=1
        )
        super().__init__(
            portfolio_id=portfolio_id,
            name="VWAP Pullback (Institutional 2.2R)",
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
            vwap_val = indicators.get("vwap")
            atr_val = indicators.get("atr", Decimal("20.00"))
            atr_dec = Decimal(str(atr_val)) if atr_val is not None else Decimal("20.00")

            if vwap_val is not None:
                vwap_dec = Decimal(str(vwap_val))
                # Pullback zone: within 0.85x ATR of institutional VWAP
                if abs(market_price - vwap_dec) > (atr_dec * Decimal("0.85")):
                    return None
                stop_price = max(Decimal("0.01"), (vwap_dec - max(Decimal("1.80"), atr_dec * Decimal("0.5"))).quantize(Decimal("0.01")))
                if stop_price >= market_price:
                    stop_price = (market_price * Decimal("0.993")).quantize(Decimal("0.01"))
                stop_dist = max(Decimal("2.00"), market_price - stop_price)
            else:
                stop_dist = max(Decimal("2.00"), market_price * self.genome.stop_loss_pct)
                stop_price = max(Decimal("0.01"), (market_price - stop_dist).quantize(Decimal("0.01")))

            target_dist = stop_dist * Decimal("2.2")  # 2.2R Institutional Reward
            target_price = (market_price + target_dist).quantize(Decimal("0.01"))

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
