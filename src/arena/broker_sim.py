from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional
import time
from src.arena.order import (
    OrderTicket,
    OrderSide,
    OrderType,
    ExecutionReason,
    FillEvent,
)
from src.arena.portfolio import Portfolio, PRECISION_CASH
from src.arena.risk_guard import RiskGuard, MAX_DRAWDOWN_LIMIT_PCT


class BrokerSim:
    """
    Synchronous Multi-Portfolio Paper Trading Matching Engine.
    Simulates a unified exchange venue where multiple competitor portfolios
    compete simultaneously under identical market conditions.
    Accurately models intra-bar Stop-Loss / Take-Profit triggers, gap fills, and Maker/Taker fees.
    """
    def __init__(
        self,
        symbol: str = "BTC/USD",
        slippage_pct: Decimal = Decimal("0.0002"),  # 0.02% slippage
        mode: str = "paper_arena"
    ):
        self.symbol: str = symbol
        self.slippage_pct: Decimal = slippage_pct
        self.mode: str = mode
        self.portfolios: Dict[str, Portfolio] = {}
        self.competitor_caps: Dict[str, Decimal] = {}
        self.active_stops: Dict[str, OrderTicket] = {}    # portfolio_id -> active stop loss order
        self.active_targets: Dict[str, OrderTicket] = {}  # portfolio_id -> active take profit order
        self.current_price: Decimal = Decimal("0.00")
        self.execution_audit: List[FillEvent] = []
        self.rejection_audit: List[tuple[str, str]] = []
        self._seq_counter: int = 0

    def register_portfolio(
        self,
        portfolio: Portfolio,
        max_position_ratio: Decimal = Decimal("0.50")
    ) -> None:
        self.portfolios[portfolio.portfolio_id] = portfolio
        self.competitor_caps[portfolio.portfolio_id] = max_position_ratio

    def submit_order(self, ticket: OrderTicket) -> Optional[FillEvent]:
        """
        Executes an order ticket in paper arena mode without interactive blockage.
        """
        portfolio = self.portfolios.get(ticket.portfolio_id)
        if not portfolio:
            raise KeyError(f"Unknown portfolio {ticket.portfolio_id}")

        ref_price = ticket.price if ticket.price is not None else self.current_price
        max_cap = self.competitor_caps.get(ticket.portfolio_id, Decimal("0.50"))
        valid, reason = RiskGuard.validate_order(
            ticket, portfolio, max_cap, ref_price, self.slippage_pct
        )
        if not valid:
            self.rejection_audit.append((ticket.portfolio_id, reason))
            return None

        # Determine execution price:
        # LIMIT orders fill at their limit price without adverse taker slippage;
        # MARKET / STOP_MARKET orders fill with realistic slippage around reference price.
        if ticket.order_type == OrderType.LIMIT and ticket.price is not None:
            fill_price = ticket.price
        else:
            if ticket.side == OrderSide.BUY:
                fill_price = ref_price * (Decimal("1") + self.slippage_pct)
            else:
                fill_price = ref_price * (Decimal("1") - self.slippage_pct)

        fill_price = fill_price.quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
        fee = (ticket.qty * fill_price * portfolio.fee_rate).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)

        self._seq_counter += 1
        raw_fill = FillEvent(
            order_id=ticket.order_id,
            portfolio_id=ticket.portfolio_id,
            symbol=ticket.symbol,
            side=ticket.side,
            qty=ticket.qty,
            price=fill_price,
            fee=fee,
            timestamp=ticket.timestamp,
            reason=ticket.reason,
            fill_seq=self._seq_counter
        )

        enriched_fill = portfolio.apply_fill(raw_fill)
        self.execution_audit.append(enriched_fill)

        # Register or clear Bracket Exits
        if ticket.side == OrderSide.BUY and portfolio.position_qty > Decimal("0"):
            if ticket.stop_loss is not None:
                self.active_stops[ticket.portfolio_id] = OrderTicket(
                    portfolio_id=ticket.portfolio_id,
                    symbol=ticket.symbol,
                    side=OrderSide.SELL,
                    order_type=OrderType.STOP_MARKET,
                    qty=portfolio.position_qty,
                    price=ticket.stop_loss,
                    reason=ExecutionReason.STOP_LOSS,
                    timestamp=ticket.timestamp
                )
            if ticket.take_profit is not None:
                self.active_targets[ticket.portfolio_id] = OrderTicket(
                    portfolio_id=ticket.portfolio_id,
                    symbol=ticket.symbol,
                    side=OrderSide.SELL,
                    order_type=OrderType.LIMIT,
                    qty=portfolio.position_qty,
                    price=ticket.take_profit,
                    reason=ExecutionReason.TAKE_PROFIT,
                    timestamp=ticket.timestamp
                )
        elif ticket.side == OrderSide.SELL and portfolio.position_qty == Decimal("0"):
            self.active_stops.pop(ticket.portfolio_id, None)
            self.active_targets.pop(ticket.portfolio_id, None)

        return enriched_fill

    def on_tick(
        self,
        price: Decimal,
        high: Optional[Decimal] = None,
        low: Optional[Decimal] = None,
        timestamp: Optional[float] = None,
        open_price: Optional[Decimal] = None
    ) -> List[FillEvent]:
        """
        Advances the venue clock and evaluates all portfolios & bracket orders.
        1. Evaluates intra-bar Stop-Loss first (conservative priority per trader-timemachine).
        2. Evaluates intra-bar Take-Profit at exact target price.
        3. Updates end-of-bar portfolio mark-to-market valuation & checks circuit breakers.
        """
        ts = timestamp if timestamp is not None else time.time()
        self.current_price = price
        high_price = high if high is not None else price
        low_price = low if low is not None else price
        bar_open = open_price if open_price is not None else price

        fills: List[FillEvent] = []

        # 1. Check bracket stops & targets across all open positions
        for p_id in list(self.portfolios.keys()):
            p = self.portfolios[p_id]
            if p.position_qty <= Decimal("0"):
                continue

            # Check Stop-Loss (or Trailing Stop) first
            stop_order = self.active_stops.get(p_id)
            if stop_order and stop_order.price is not None:
                if low_price <= stop_order.price:
                    # If bar opened below stop, fill at open; otherwise fill at stop trigger price
                    trigger_p = min(bar_open, stop_order.price) if open_price is not None else stop_order.price
                    reason = (
                        ExecutionReason.TRAILING_STOP
                        if (p.avg_entry_price > Decimal("0") and stop_order.price > p.avg_entry_price)
                        else stop_order.reason
                    )
                    stop_fill = self.submit_order(OrderTicket(
                        portfolio_id=p_id,
                        symbol=self.symbol,
                        side=OrderSide.SELL,
                        order_type=OrderType.STOP_MARKET,
                        qty=p.position_qty,
                        price=trigger_p,
                        reason=reason,
                        timestamp=ts
                    ))
                    if stop_fill:
                        fills.append(stop_fill)
                    continue

            # Check Take-Profit (Limit fill at target price or better if gapped up)
            target_order = self.active_targets.get(p_id)
            if target_order and target_order.price is not None:
                if high_price >= target_order.price:
                    trigger_p = max(bar_open, target_order.price) if open_price is not None else target_order.price
                    target_fill = self.submit_order(OrderTicket(
                        portfolio_id=p_id,
                        symbol=self.symbol,
                        side=OrderSide.SELL,
                        order_type=OrderType.LIMIT,
                        qty=p.position_qty,
                        price=trigger_p,
                        reason=ExecutionReason.TAKE_PROFIT,
                        timestamp=ts
                    ))
                    if target_fill:
                        fills.append(target_fill)

        # 2. Update end-of-bar valuation & check 15% drawdown circuit breaker
        for p_id, p in self.portfolios.items():
            p.update_market_price(price, ts, low_price=low_price, high_price=high_price)
            if not p.is_circuit_breaker_tripped and p.max_drawdown_pct >= MAX_DRAWDOWN_LIMIT_PCT:
                p.is_circuit_breaker_tripped = True
                if p.position_qty > Decimal("0"):
                    cb_fill = self.submit_order(OrderTicket(
                        portfolio_id=p_id,
                        symbol=self.symbol,
                        side=OrderSide.SELL,
                        order_type=OrderType.MARKET,
                        qty=p.position_qty,
                        price=price,
                        reason=ExecutionReason.CIRCUIT_BREAKER,
                        timestamp=ts
                    ))
                    if cb_fill:
                        fills.append(cb_fill)

        return fills
