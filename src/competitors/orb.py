from __future__ import annotations
from decimal import Decimal
from typing import Optional, Dict, Any
from src.arena.order import OrderTicket, OrderSide, OrderType, ExecutionReason
from src.arena.broker_sim import BrokerSim
from src.competitors.base import BaseCompetitor, CompetitorGenome


class ORBCompetitor(BaseCompetitor):
    """
    Profile E: Opening Range Breakout (ORB 15m/5m Volatility Box)
    - Origin: Inspired by day-trader-skill (trader-scanner & trader-entry)
    - Setup: Establishes the 15-minute Opening Range box (High, Low, Midpoint).
    - Leverage: 2.5x Active Leverage on confirmed breakout.
    - Trigger: Fires a high-conviction BUY on breakout above the range ceiling with volume confirmation.
    - Risk & Exit: Stop-loss anchored at range midpoint (~1.8%), profit target set to 2.0R (~3.6%).
    - Dynamic Sizing: Quant dynamic R-Multiple sizing up to 45% position cap.
    """
    # News sensitivity (item 12C): breakout eats macro-news sizing in full.
    NEWS_SENSITIVITY: float = 1.0

    def __init__(self, portfolio_id: str = "comp_orb", initial_cash: Decimal = Decimal("100000.00")):
        default_genome = CompetitorGenome(
            position_ratio=Decimal("0.45"),
            risk_per_trade_pct=Decimal("0.015"),
            stop_loss_pct=Decimal("0.018"),
            take_profit_pct=Decimal("0.036"),
            generation=1,
            leverage_enabled=True,
            leverage=Decimal("2.5"),
            news_sensitivity=1.0
        )
        super().__init__(
            portfolio_id=portfolio_id,
            name="ORB Breakout (2.5x Lev / 15m Box / 2.0R Target)",
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
        if self.portfolio.is_circuit_breaker_tripped:
            return None

        if signal == "BUY" and side == OrderSide.BUY and self.portfolio.position_qty == Decimal("0"):
            orb_high = indicators.get("orb_high")
            orb_low = indicators.get("orb_low")

            if orb_high is not None and orb_low is not None:
                orb_h = Decimal(str(orb_high))
                orb_l = Decimal(str(orb_low))
                orb_mid = (orb_h + orb_l) / Decimal("2")
                # Breakout condition: must pierce or trade above the range ceiling
                if market_price < orb_h:
                    return None
                stop_dist = max(Decimal("10.00"), market_price - orb_mid)
            else:
                stop_dist = max(Decimal("10.00"), market_price * self.genome.stop_loss_pct)

            stop_price = max(Decimal("0.01"), (market_price - stop_dist).quantize(Decimal("0.01")))
            target_dist = stop_dist * Decimal("2.0")  # Strict 2.0R Target
            target_price = (market_price + target_dist).quantize(Decimal("0.01"))

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
            orb_high = indicators.get("orb_high")
            orb_low = indicators.get("orb_low")

            if orb_high is not None and orb_low is not None:
                orb_h = Decimal(str(orb_high))
                orb_l = Decimal(str(orb_low))
                orb_mid = (orb_h + orb_l) / Decimal("2")
                # Breakdown condition: must pierce or trade below the range floor
                if market_price > orb_l:
                    return None
                stop_dist = max(Decimal("10.00"), orb_mid - market_price)
            else:
                stop_dist = max(Decimal("10.00"), market_price * self.genome.stop_loss_pct)

            stop_price = max(Decimal("0.01"), (market_price + stop_dist).quantize(Decimal("0.01")))
            target_dist = stop_dist * Decimal("2.0")  # Strict 2.0R Target
            target_price = (market_price - target_dist).quantize(Decimal("0.01"))

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
