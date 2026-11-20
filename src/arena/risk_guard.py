from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP
from typing import Tuple
from src.arena.order import OrderTicket, OrderSide, OrderType, PositionSide
from src.arena.portfolio import Portfolio, PRECISION_CASH

MAX_DRAWDOWN_LIMIT_PCT = Decimal("15.00")


class RiskGuard:
    """
    ECC AgentShield & trader-risk Safety Guard for Arena Trading.
    Enforces risk invariants before simulated orders reach the matching engine.
    Supports strategy-specific leverage caps, margin validation, and bidirectional Long/Short trading.
    Crucial rule from trader-risk: Closing/reducing an open position (SELL for Long, BUY for Short)
    is NEVER blocked by a circuit breaker or drawdown limit.
    """
    @staticmethod
    def validate_order(
        ticket: OrderTicket,
        portfolio: Portfolio,
        max_position_ratio: Decimal,
        market_price: Decimal,
        slippage_pct: Decimal = Decimal("0.0002")
    ) -> Tuple[bool, str]:
        if not ticket.qty.is_finite() or ticket.qty <= Decimal("0"):
            return False, "Order quantity must be positive."
        if ticket.order_type in (OrderType.LIMIT, OrderType.STOP_MARKET) and ticket.price is None:
            return False, f"{ticket.order_type.value} order requires an explicit price."
        if not market_price.is_finite() or market_price <= Decimal("0"):
            return False, "Market price must be positive and finite."
        if not slippage_pct.is_finite() or slippage_pct < Decimal("0"):
            return False, "Slippage must be finite and non-negative."
        if not max_position_ratio.is_finite() or max_position_ratio <= Decimal("0"):
            return False, "Max position ratio must be positive and finite."

        base_price = (
            ticket.price
            if (ticket.price is not None and ticket.order_type in (OrderType.LIMIT, OrderType.STOP_MARKET))
            else market_price
        )
        if not base_price.is_finite() or base_price <= Decimal("0"):
            return False, "Market price or order price must be positive."

        # Validate optional bracket levels upfront so NaN/Inf/non-positive/inverted
        # levels can never enter BrokerSim.active_stops/active_targets.
        if ticket.stop_loss is not None:
            if not ticket.stop_loss.is_finite() or ticket.stop_loss <= Decimal("0"):
                return False, "Stop-loss price must be positive and finite."
        if ticket.take_profit is not None:
            if not ticket.take_profit.is_finite() or ticket.take_profit <= Decimal("0"):
                return False, "Take-profit price must be positive and finite."

        # 1. Closing / Reducing Position Checks (Never blocked by drawdown/breaker)
        if portfolio.position_side == PositionSide.LONG and ticket.side == OrderSide.SELL:
            if ticket.qty > portfolio.position_qty:
                return False, f"Overclosing: attempting to sell {ticket.qty}, currently holding {portfolio.position_qty}"
            return True, "PASS"

        if portfolio.position_side == PositionSide.SHORT and ticket.side == OrderSide.BUY:
            if ticket.qty > portfolio.position_qty:
                return False, f"Overcovering: attempting to cover {ticket.qty}, currently short {portfolio.position_qty}"
            return True, "PASS"

        # 2. Position Opening / Expanding Checks (Applies to BUY when flat/long, or SELL when flat/short)
        if portfolio.is_circuit_breaker_tripped:
            return False, f"Portfolio {portfolio.portfolio_id} circuit breaker is tripped."

        if portfolio.max_drawdown_pct >= MAX_DRAWDOWN_LIMIT_PCT:
            return False, f"Max drawdown exceeded ({portfolio.max_drawdown_pct}% >= {MAX_DRAWDOWN_LIMIT_PCT}%). Circuit breaker condition."

        # Factor in slippage for market and stop-market orders
        if ticket.order_type in (OrderType.MARKET, OrderType.STOP_MARKET):
            mult = (Decimal("1") + slippage_pct) if ticket.side == OrderSide.BUY else (Decimal("1") - slippage_pct)
            effective_order_price = max(
                PRECISION_CASH,
                (base_price * mult).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP),
            )
        else:
            effective_order_price = base_price

        # Directional bracket sanity for opening/expanding orders
        if ticket.side == OrderSide.BUY:
            if ticket.stop_loss is not None and ticket.stop_loss >= effective_order_price:
                return False, "Long stop-loss must be below entry price."
            if ticket.take_profit is not None and ticket.take_profit <= effective_order_price:
                return False, "Long take-profit must be above entry price."
        else:
            if ticket.stop_loss is not None and ticket.stop_loss <= effective_order_price:
                return False, "Short stop-loss must be above entry price."
            if ticket.take_profit is not None and ticket.take_profit >= effective_order_price:
                return False, "Short take-profit must be below entry price."

        order_val = (ticket.qty * effective_order_price).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
        eff_lev = portfolio.leverage if portfolio.leverage_enabled and portfolio.leverage > Decimal("0") else Decimal("1.0")

        # Check maximum single position cap relative to UNLEVERAGED total equity.
        # Leverage affects only the margin required (below), never the notional cap.
        max_allowed_val = (portfolio.total_equity * max_position_ratio * Decimal("1.005")).quantize(
            PRECISION_CASH, rounding=ROUND_HALF_UP
        )
        current_pos_val = (portfolio.position_qty * market_price).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
        if (current_pos_val + order_val) > max_allowed_val:
            return False, f"Order exceeds max position cap ({max_position_ratio * Decimal('100')}% of equity)"

        # Check cash margin sufficiency including fee buffer (matches BrokerSim fee formula)
        required_margin = (order_val / eff_lev).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
        estimated_fee = (ticket.qty * effective_order_price * portfolio.fee_rate).quantize(
            PRECISION_CASH, rounding=ROUND_HALF_UP
        )
        if (required_margin + estimated_fee) > portfolio.cash:
            return False, f"Insufficient margin: requires {required_margin + estimated_fee}, available cash {portfolio.cash}"

        return True, "PASS"
