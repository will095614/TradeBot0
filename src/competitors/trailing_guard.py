from __future__ import annotations
from decimal import Decimal
from typing import Optional, Dict, Any
from src.arena.order import OrderTicket, OrderSide, OrderType, ExecutionReason
from src.arena.broker_sim import BrokerSim
from src.competitors.base import BaseCompetitor, CompetitorGenome


class TrailingGuardCompetitor(BaseCompetitor):
    """
    Profile D: Trailing Profit Guard / Ratchet Stop
    - Default Position: 40% Available Capital
    - Initial Stop-Loss: Fixed 1.5% (automatically ratchets to Breakeven at +1.0% gain)
    - Trailing Lock: Activates 0.6% trailing stop at +2.0% profit to capture peaks
    """
    def __init__(self, portfolio_id: str = "comp_trail", initial_cash: Decimal = Decimal("500000.00")):
        default_genome = CompetitorGenome(
            position_ratio=Decimal("0.40"),
            risk_per_trade_pct=Decimal("0.015"),
            stop_loss_pct=Decimal("0.015"),
            take_profit_pct=None,
            trailing_trigger_pct=Decimal("2.0"),
            trailing_distance_pct=Decimal("0.006"),
            generation=1
        )
        super().__init__(
            portfolio_id=portfolio_id,
            name="Trailing Guard (40% / 1.5% SL / 0.6% Trailing)",
            max_position_ratio=default_genome.position_ratio,
            initial_cash=initial_cash,
            genome=default_genome
        )
        self.highest_price_since_entry: Decimal = Decimal("0")
        self.trailing_active: bool = False

    def reset_for_new_generation(self, new_genome: CompetitorGenome, preserve_portfolio: bool = True) -> None:
        super().reset_for_new_generation(new_genome, preserve_portfolio=preserve_portfolio)
        if not preserve_portfolio or self.portfolio.position_qty == Decimal("0"):
            self.highest_price_since_entry = Decimal("0")
            self.trailing_active = False

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

        # If holding position, update dynamic trailing stop using intra-bar high if available
        if self.portfolio.position_qty > Decimal("0"):
            bar_high = indicators.get("high", market_price)
            if not isinstance(bar_high, Decimal):
                bar_high = Decimal(str(bar_high)) if bar_high is not None else market_price
            peak_candidate = max(market_price, bar_high)

            if peak_candidate > self.highest_price_since_entry:
                self.highest_price_since_entry = peak_candidate

            entry_p = self.portfolio.avg_entry_price
            if entry_p > Decimal("0"):
                gain_pct = ((self.highest_price_since_entry - entry_p) / entry_p) * Decimal("100")
                if gain_pct >= self.genome.trailing_trigger_pct and not self.trailing_active:
                    self.trailing_active = True

                # Stage 1: Breakeven lock when gain >= half of trailing trigger (e.g. +1.0%)
                half_trigger = self.genome.trailing_trigger_pct * Decimal("0.5")
                if gain_pct >= half_trigger and not self.trailing_active:
                    breakeven_stop = (entry_p * Decimal("1.0015")).quantize(Decimal("0.01"))
                    current_stop = broker.active_stops.get(self.portfolio_id)
                    if current_stop and (current_stop.price is None or breakeven_stop > current_stop.price):
                        broker.active_stops[self.portfolio_id] = OrderTicket(
                            portfolio_id=self.portfolio_id,
                            symbol=broker.symbol,
                            side=OrderSide.SELL,
                            order_type=OrderType.STOP_MARKET,
                            qty=self.portfolio.position_qty,
                            price=breakeven_stop,
                            reason=ExecutionReason.TRAILING_STOP,
                            timestamp=timestamp
                        )

            # Stage 2: Full dynamic trailing stop ratchet
            if self.trailing_active and self.highest_price_since_entry > Decimal("0"):
                new_trailing_stop = (
                    self.highest_price_since_entry * (Decimal("1") - self.genome.trailing_distance_pct)
                ).quantize(Decimal("0.01"))
                current_stop = broker.active_stops.get(self.portfolio_id)
                if current_stop and (current_stop.price is None or new_trailing_stop > current_stop.price):
                    broker.active_stops[self.portfolio_id] = OrderTicket(
                        portfolio_id=self.portfolio_id,
                        symbol=broker.symbol,
                        side=OrderSide.SELL,
                        order_type=OrderType.STOP_MARKET,
                        qty=self.portfolio.position_qty,
                        price=new_trailing_stop,
                        reason=ExecutionReason.TRAILING_STOP,
                        timestamp=timestamp
                    )

        if self.portfolio.position_qty == Decimal("0"):
            self.highest_price_since_entry = Decimal("0")
            self.trailing_active = False

        if signal == "BUY" and self.portfolio.position_qty == Decimal("0"):
            stop_price = (market_price * (Decimal("1") - self.genome.stop_loss_pct)).quantize(Decimal("0.01"))
            qty = self.compute_r_multiple_qty(market_price, stop_price, broker)
            if qty <= Decimal("0"):
                return None

            self.highest_price_since_entry = market_price
            self.trailing_active = False

            return OrderTicket(
                portfolio_id=self.portfolio_id,
                symbol=broker.symbol,
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                qty=qty,
                stop_loss=stop_price,
                take_profit=None,
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
