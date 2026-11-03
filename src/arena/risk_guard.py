from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP
from typing import Tuple
from src.arena.order import OrderTicket, OrderSide, OrderType
from src.arena.portfolio import Portfolio, PRECISION_CASH

MAX_DRAWDOWN_LIMIT_PCT = Decimal("15.00")


class RiskGuard:
    """
    ECC AgentShield & trader-risk Safety Guard for Arena Trading.
    Enforces risk invariants before simulated orders reach the matching engine.
    Supports strategy-specific leverage caps and margin validation.
    Crucial rule from trader-risk: Closing/reducing an open position (SELL) is NEVER
    blocked by a circuit breaker or drawdown limit.
    """
    @staticmethod
    def validate_order(
        ticket: OrderTicket,
        portfolio: Portfolio,
        max_position_ratio: Decimal,
        market_price: Decimal,
        slippage_pct: Decimal = Decimal("0.0002")
    ) -> Tuple[bool, str]:
        if ticket.qty <= Decimal("0"):
            return False, "Order quantity must be positive."

        base_price = ticket.price if (ticket.price is not None and ticket.order_type == OrderType.LIMIT) else market_price
        if base_price <= Decimal("0"):
            return False, "Market price or order price must be positive."

        if ticket.side == OrderSide.SELL:
            if ticket.qty > portfolio.position_qty:
                return False, f"Overselling: attempting to sell {ticket.qty}, currently holding {portfolio.position_qty}"
            return True, "PASS"

        # Below checks apply strictly to new BUY entries
        if portfolio.is_circuit_breaker_tripped:
            return False, f"Portfolio {portfolio.portfolio_id} circuit breaker is tripped."

        if portfolio.max_drawdown_pct >= MAX_DRAWDOWN_LIMIT_PCT:
            portfolio.is_circuit_breaker_tripped = True
            return False, f"Max drawdown exceeded ({portfolio.max_drawdown_pct}% >= {MAX_DRAWDOWN_LIMIT_PCT}%). Tripping breaker."

        # Factor in slippage for market BUY orders
        if ticket.order_type == OrderType.MARKET:
            effective_buy_price = (market_price * (Decimal("1") + slippage_pct)).quantize(
                PRECISION_CASH, rounding=ROUND_HALF_UP
            )
        else:
            effective_buy_price = base_price

        order_val = (ticket.qty * effective_buy_price).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
        eff_lev = portfolio.leverage if portfolio.leverage_enabled and portfolio.leverage > Decimal("0") else Decimal("1.0")

        # Check maximum single position cap relative to total equity with leverage
        max_allowed_val = (portfolio.total_equity * max_position_ratio * eff_lev * Decimal("1.005")).quantize(
            PRECISION_CASH, rounding=ROUND_HALF_UP
        )
        current_pos_val = (portfolio.position_qty * market_price).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
        if (current_pos_val + order_val) > max_allowed_val:
            return False, f"Order exceeds max position cap ({max_position_ratio * eff_lev * Decimal('100')}%)"

        # Check cash margin sufficiency including fee buffer
        required_margin = (order_val / eff_lev).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
        estimated_fee = (order_val * portfolio.fee_rate).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
        if (required_margin + estimated_fee) > portfolio.cash:
            return False, f"Insufficient margin: requires {required_margin + estimated_fee}, available cash {portfolio.cash}"

        return True, "PASS"
