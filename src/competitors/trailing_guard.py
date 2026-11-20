from __future__ import annotations
from decimal import Decimal
from typing import Optional, Dict, Any
from src.arena.order import OrderTicket, OrderSide, OrderType, PositionSide, ExecutionReason
from src.arena.broker_sim import BrokerSim
from src.competitors.base import BaseCompetitor, CompetitorGenome


class TrailingGuardCompetitor(BaseCompetitor):
    """
    Profile D: Trailing Profit Guard / Ratchet Stop
    - Default Position: 40% Available Capital / 2.0x Leverage Active
    - Initial Stop-Loss: Fixed 1.5% (automatically ratchets to Breakeven at +1.0% gain)
    - Trailing Lock: Activates 0.6% trailing stop at +2.0% profit to capture peaks
    """
    # News sensitivity (item 12C): trend follower, news impact is indirect.
    NEWS_SENSITIVITY: float = 0.5

    def __init__(self, portfolio_id: str = "comp_trail", initial_cash: Decimal = Decimal("100000.00")):
        default_genome = CompetitorGenome(
            position_ratio=Decimal("0.40"),
            risk_per_trade_pct=Decimal("0.015"),
            stop_loss_pct=Decimal("0.015"),
            take_profit_pct=None,
            trailing_trigger_pct=Decimal("2.0"),
            trailing_distance_pct=Decimal("0.006"),
            generation=1,
            leverage_enabled=True,
            leverage=Decimal("2.0"),
            news_sensitivity=0.5
        )
        super().__init__(
            portfolio_id=portfolio_id,
            name="Trailing Guard (2x Lev / 40% / 1.5% SL / 0.6% Trailing)",
            max_position_ratio=default_genome.position_ratio,
            initial_cash=initial_cash,
            genome=default_genome
        )
        self.highest_price_since_entry: Decimal = Decimal("0")
        self.lowest_price_since_entry: Decimal = Decimal("0")
        self.trailing_active: bool = False

    def reset_for_new_generation(self, new_genome: CompetitorGenome, preserve_portfolio: bool = True) -> None:
        super().reset_for_new_generation(new_genome, preserve_portfolio=preserve_portfolio)
        if not preserve_portfolio or self.portfolio.position_qty == Decimal("0"):
            self.highest_price_since_entry = Decimal("0")
            self.lowest_price_since_entry = Decimal("0")
            self.trailing_active = False

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

        if self.portfolio.position_qty <= Decimal("0"):
            self.highest_price_since_entry = Decimal("0")
            self.lowest_price_since_entry = Decimal("0")
            self.trailing_active = False

        # Check existing position for dynamic ratchet trailing stop.
        # Audit 3.6: the old code ran the LONG branch for both sides
        # (position_qty > 0 holds for shorts too): it armed "trailing"
        # when the price ROSE 2% -- a 2% loss for a short -- and wrote a
        # SELL stop whose price chased the rally upward instead of
        # ratcheting down. The SHORT branch below is the mirror of the
        # live engine's comp_trail SHORT ratchet (live_engine.py
        # _evaluate_live_strategies) plus the breakeven step this method
        # already applies to longs; the live inline ratchet itself is
        # untouched, so live behaviour does not change.
        if self.portfolio.position_qty > Decimal("0") and self.portfolio.avg_entry_price > Decimal("0"):
            entry = self.portfolio.avg_entry_price
            current_stop_order = broker.active_stops.get(self.portfolio_id)
            curr_stop_price = current_stop_order.price if current_stop_order is not None else None

            if self.portfolio.position_side == PositionSide.SHORT:
                if self.lowest_price_since_entry == Decimal("0") or market_price < self.lowest_price_since_entry:
                    self.lowest_price_since_entry = market_price

                gain_pct = ((entry - self.lowest_price_since_entry) / entry) * Decimal("100")

                if gain_pct >= self.genome.trailing_trigger_pct:
                    self.trailing_active = True

                be_stop = (entry * Decimal("0.9995")).quantize(Decimal("0.01"))
                if self.trailing_active:
                    trail_stop = min(
                        be_stop,
                        (self.lowest_price_since_entry * (Decimal("1") + self.genome.trailing_distance_pct)).quantize(Decimal("0.01")),
                    )
                    if curr_stop_price is None or trail_stop < curr_stop_price:
                        broker.active_stops[self.portfolio_id] = OrderTicket(
                            portfolio_id=self.portfolio_id,
                            symbol=broker.symbol,
                            side=OrderSide.BUY,
                            order_type=OrderType.STOP_MARKET,
                            qty=self.portfolio.position_qty,
                            price=trail_stop,
                            reason=ExecutionReason.TRAILING_STOP,
                            timestamp=timestamp
                        )
                elif gain_pct >= Decimal("1.0"):
                    if curr_stop_price is None or be_stop < curr_stop_price:
                        broker.active_stops[self.portfolio_id] = OrderTicket(
                            portfolio_id=self.portfolio_id,
                            symbol=broker.symbol,
                            side=OrderSide.BUY,
                            order_type=OrderType.STOP_MARKET,
                            qty=self.portfolio.position_qty,
                            price=be_stop,
                            reason=ExecutionReason.TRAILING_STOP,
                            timestamp=timestamp
                        )
            else:
                if market_price > self.highest_price_since_entry:
                    self.highest_price_since_entry = market_price

                gain_pct = ((self.highest_price_since_entry - entry) / entry) * Decimal("100")

                if gain_pct >= self.genome.trailing_trigger_pct:
                    self.trailing_active = True

                be_stop = (entry * Decimal("1.0005")).quantize(Decimal("0.01"))
                if self.trailing_active:
                    trail_stop = max(
                        be_stop,
                        (self.highest_price_since_entry * (Decimal("1") - self.genome.trailing_distance_pct)).quantize(Decimal("0.01")),
                    )
                    if curr_stop_price is None or trail_stop > curr_stop_price:
                        broker.active_stops[self.portfolio_id] = OrderTicket(
                            portfolio_id=self.portfolio_id,
                            symbol=broker.symbol,
                            side=OrderSide.SELL,
                            order_type=OrderType.STOP_MARKET,
                            qty=self.portfolio.position_qty,
                            price=trail_stop,
                            reason=ExecutionReason.TRAILING_STOP,
                            timestamp=timestamp
                        )
                elif gain_pct >= Decimal("1.0"):
                    if curr_stop_price is None or be_stop > curr_stop_price:
                        broker.active_stops[self.portfolio_id] = OrderTicket(
                            portfolio_id=self.portfolio_id,
                            symbol=broker.symbol,
                            side=OrderSide.SELL,
                            order_type=OrderType.STOP_MARKET,
                            qty=self.portfolio.position_qty,
                            price=be_stop,
                            reason=ExecutionReason.TRAILING_STOP,
                            timestamp=timestamp
                        )

            if signal == "SELL":
                self.highest_price_since_entry = Decimal("0")
                self.lowest_price_since_entry = Decimal("0")
                self.trailing_active = False
                return self._close_ticket(broker, timestamp)

        # Opening new position
        if signal == "BUY" and side == OrderSide.BUY and self.portfolio.position_qty == Decimal("0"):
            self.highest_price_since_entry = market_price
            self.lowest_price_since_entry = Decimal("0")
            self.trailing_active = False

            stop_price = (market_price * (Decimal("1") - self.genome.stop_loss_pct)).quantize(Decimal("0.01"))
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
                take_profit=None,
                reason=ExecutionReason.SIGNAL_ENTRY,
                timestamp=timestamp
            )

        elif signal == "BUY" and side == OrderSide.SELL and self.portfolio.position_qty == Decimal("0"):
            self.highest_price_since_entry = Decimal("0")
            self.lowest_price_since_entry = market_price
            self.trailing_active = False

            stop_price = (market_price * (Decimal("1") + self.genome.stop_loss_pct)).quantize(Decimal("0.01"))
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
                take_profit=None,
                reason=ExecutionReason.SIGNAL_ENTRY,
                timestamp=timestamp
            )

        return None
