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
        if self.portfolio.is_circuit_breaker_tripped or not market_price.is_finite() or market_price <= Decimal("0"):
            return None

        if signal == "SELL":
            return self._close_ticket(broker, timestamp)
        if signal != "BUY" or self.portfolio.position_qty != Decimal("0"):
            return None

        min_stop_floor = min(
            Decimal("10.00"),
            max(Decimal("0.01"), (market_price * Decimal("0.004")).quantize(Decimal("0.01"))),
        )
        max_stop_cap = max(
            min_stop_floor,
            (market_price * max(self.genome.stop_loss_pct * Decimal("3"), Decimal("0.06"))).quantize(Decimal("0.01")),
        )
        raw_r_mult = (
            (self.genome.take_profit_pct / self.genome.stop_loss_pct)
            if (self.genome.take_profit_pct is not None and self.genome.stop_loss_pct > Decimal("0"))
            else Decimal("2.0")
        )
        r_mult = max(Decimal("1.5"), min(Decimal("4.0"), raw_r_mult))

        orb_high = indicators.get("orb_high")
        orb_low = indicators.get("orb_low")
        orb_valid = False
        orb_h = Decimal("0")
        orb_l = Decimal("0")
        if orb_high is not None and orb_low is not None:
            try:
                orb_h = Decimal(str(orb_high))
                orb_l = Decimal(str(orb_low))
                orb_valid = (
                    orb_h.is_finite()
                    and orb_l.is_finite()
                    and orb_h > Decimal("0")
                    and orb_l > Decimal("0")
                    and orb_h >= orb_l
                )
            except Exception:
                orb_valid = False

        if side == OrderSide.BUY:
            if orb_valid:
                # Breakout condition: must pierce or trade above the range ceiling
                if market_price < orb_h:
                    return None
                if orb_h > orb_l:
                    orb_mid = (orb_h + orb_l) / Decimal("2")
                    stop_dist = max(min_stop_floor, market_price - orb_mid)
                else:
                    stop_dist = max(min_stop_floor, market_price * self.genome.stop_loss_pct)
            else:
                stop_dist = max(min_stop_floor, market_price * self.genome.stop_loss_pct)

            stop_dist = min(stop_dist, max_stop_cap)
            stop_price = max(Decimal("0.01"), (market_price - stop_dist).quantize(Decimal("0.01")))
            if stop_price >= market_price:
                return None
            actual_stop_dist = market_price - stop_price
            target_dist = actual_stop_dist * r_mult
            target_price = (market_price + target_dist).quantize(Decimal("0.01"))
            if target_price <= market_price:
                return None

            qty = self.compute_r_multiple_qty(
                market_price, stop_price, broker, sizing_multiplier=sizing_multiplier, side=OrderSide.BUY
            )
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

        if side == OrderSide.SELL:
            if orb_valid:
                # Breakdown condition: must pierce or trade below the range floor
                if market_price > orb_l:
                    return None
                if orb_h > orb_l:
                    orb_mid = (orb_h + orb_l) / Decimal("2")
                    stop_dist = max(min_stop_floor, orb_mid - market_price)
                else:
                    stop_dist = max(min_stop_floor, market_price * self.genome.stop_loss_pct)
            else:
                stop_dist = max(min_stop_floor, market_price * self.genome.stop_loss_pct)

            stop_dist = min(stop_dist, max_stop_cap)
            stop_price = (market_price + stop_dist).quantize(Decimal("0.01"))
            if stop_price <= market_price:
                return None
            actual_stop_dist = stop_price - market_price
            target_dist = actual_stop_dist * r_mult
            target_price = max(Decimal("0.01"), (market_price - target_dist).quantize(Decimal("0.01")))
            if target_price >= market_price:
                return None

            qty = self.compute_r_multiple_qty(
                market_price, stop_price, broker, sizing_multiplier=sizing_multiplier, side=OrderSide.SELL
            )
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

        return None
