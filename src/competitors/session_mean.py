from __future__ import annotations
from decimal import Decimal
from typing import Optional, Dict, Any
from src.arena.order import OrderTicket, OrderSide, OrderType, ExecutionReason
from src.arena.broker_sim import BrokerSim
from src.competitors.base import BaseCompetitor, CompetitorGenome

_BASE_RATIO = Decimal("0.026") / Decimal("0.012")


def _parse_pos_dec(raw: Any, default: Optional[Decimal] = None) -> Optional[Decimal]:
    if raw is None:
        return default
    try:
        val = Decimal(str(raw))
        return val if (val.is_finite() and val > Decimal("0")) else default
    except Exception:
        return default


class SessionMeanPullbackCompetitor(BaseCompetitor):
    """
    Profile F: Session Mean Pullback (NOT volume-weighted VWAP)
    - Origin: Wall Street Institutional Benchmark Trading
    - Setup: Tracks the session typical-price mean (mean of (H+L+C)/3 over the
      last 200 1-minute bars). It is deliberately NOT called VWAP: live 1-minute
      candles carry no per-bar volume, so a true volume-weighted VWAP cannot be
      computed live. Backtest bars do carry volume, so the backtest reference
      passed in as "mean_ref" is the genuine session VWAP; live passes the
      typical-price mean under the same key.
    - Leverage: Spot 1x (Leverage Disabled / Institutional Balance Sheet Mode)
    - Trigger: In an uptrend (Price > mean), waits for a shallow pullback into the
      mean accumulation band (within 0.85x ATR) and enters on rebound confirmation.
    - Risk & Exit: Tight institutional stop just under the mean (~1.2%), target set to 2.2R (~2.6%).
    - Dynamic Sizing: Quant dynamic R-Multiple sizing up to 50% position cap.
    """
    # News sensitivity (item 12C): mean reversion often runs against the
    # news direction, so it barely moves on news.
    NEWS_SENSITIVITY: float = 0.3

    def __init__(self, portfolio_id: str = "comp_vwap", initial_cash: Decimal = Decimal("100000.00")):
        default_genome = CompetitorGenome(
            position_ratio=Decimal("0.50"),
            risk_per_trade_pct=Decimal("0.018"),
            stop_loss_pct=Decimal("0.012"),
            take_profit_pct=Decimal("0.026"),
            generation=1,
            leverage_enabled=False,
            leverage=Decimal("1.0"),
            news_sensitivity=0.3
        )
        super().__init__(
            portfolio_id=portfolio_id,
            name="Session Mean Pullback (Spot 1x / 2.2R)",
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
        raw_r_mult = (
            Decimal("2.2") * ((self.genome.take_profit_pct / self.genome.stop_loss_pct) / _BASE_RATIO)
            if (self.genome.take_profit_pct is not None and self.genome.stop_loss_pct > Decimal("0"))
            else Decimal("2.2")
        )
        r_mult = max(Decimal("1.5"), min(Decimal("4.0"), raw_r_mult))
        default_atr = max(Decimal("0.01"), (market_price * Decimal("0.008")).quantize(Decimal("0.01")))
        mean_dec = _parse_pos_dec(indicators.get("mean_ref"))
        atr_dec = _parse_pos_dec(indicators.get("atr"), default_atr) or default_atr

        if side == OrderSide.BUY:
            if mean_dec is not None:
                # Pullback zone: within 0.85x ATR of the session mean
                if abs(market_price - mean_dec) > (atr_dec * Decimal("0.85")):
                    return None
                stop_price = max(Decimal("0.01"), (mean_dec - max(min_stop_floor, atr_dec * Decimal("0.5"))).quantize(Decimal("0.01")))
                if (market_price - stop_price) < min_stop_floor:
                    fallback_dist = max(min_stop_floor, (market_price * self.genome.stop_loss_pct).quantize(Decimal("0.01")))
                    stop_price = max(Decimal("0.01"), (market_price - fallback_dist).quantize(Decimal("0.01")))
                stop_dist = max(min_stop_floor, market_price - stop_price)
            else:
                stop_dist = max(min_stop_floor, market_price * self.genome.stop_loss_pct)
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
            if mean_dec is not None:
                # Pullback zone: within 0.85x ATR of the session mean
                if abs(market_price - mean_dec) > (atr_dec * Decimal("0.85")):
                    return None
                stop_price = (mean_dec + max(min_stop_floor, atr_dec * Decimal("0.5"))).quantize(Decimal("0.01"))
                if (stop_price - market_price) < min_stop_floor:
                    fallback_dist = max(min_stop_floor, (market_price * self.genome.stop_loss_pct).quantize(Decimal("0.01")))
                    stop_price = (market_price + fallback_dist).quantize(Decimal("0.01"))
                stop_dist = max(min_stop_floor, stop_price - market_price)
            else:
                stop_dist = max(min_stop_floor, market_price * self.genome.stop_loss_pct)
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
