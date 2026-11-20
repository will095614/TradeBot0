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

        base_price = (
            ticket.price
            if (ticket.price is not None and ticket.order_type in (OrderType.LIMIT, OrderType.STOP_MARKET))
            else market_price
        )
        if not base_price.is_finite() or base_price <= Decimal("0"):
            return False, "Market price or order price must be positive."
        if not market_price.is_finite() or not slippage_pct.is_finite():
            return False, "Market price and slippage must be finite."

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
