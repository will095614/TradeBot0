from __future__ import annotations
from dataclasses import replace
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional
import logging
import time

logger = logging.getLogger(__name__)
from src.arena.order import (
    OrderTicket,
    OrderSide,
    OrderType,
    ExecutionReason,
    FillEvent,
    PositionSide,
)
from src.arena.portfolio import Portfolio, PRECISION_CASH
from src.arena.risk_guard import RiskGuard, MAX_DRAWDOWN_LIMIT_PCT

# A4: fixed slippage-model pool depth (in ETH). The quadratic
# depth-impact term (0.0005 * (qty / pool_depth) ** 2) is struck
# against this assumed pool size -- it is a MODEL PARAMETER, not
# measured order-book depth: no live depth feed exists. It is
# configurable per BrokerSim instance for sensitivity analysis;
# the value itself is unchanged (decision: P2-A).
DEFAULT_POOL_DEPTH = Decimal("200.0")

# Maintenance margin level for liquidation (audit 2.4): a position is
# liquidated once its position equity falls to 10% of its locked margin,
# i.e. once it has lost 90% of its margin.
LIQUIDATION_MAINTENANCE_RATIO = Decimal("0.10")


class BrokerSim:
    """
    Synchronous Multi-Portfolio Paper Trading Matching Engine.
    Simulates a unified exchange venue where multiple competitor portfolios
    compete simultaneously under identical market conditions.
    Accurately models intra-bar Stop-Loss / Take-Profit triggers, gap fills, and Maker/Taker fees.
    """
    def __init__(
        self,
        symbol: str = "ETH/USD",
        slippage_pct: Decimal = Decimal("0.0002"),  # 0.02% slippage
        mode: str = "paper_arena",
        pool_depth: Decimal = DEFAULT_POOL_DEPTH,
    ):
        self.symbol: str = symbol
        self.slippage_pct: Decimal = slippage_pct
        self.mode: str = mode
        self.portfolios: Dict[str, Portfolio] = {}
        self.competitor_caps: Dict[str, Decimal] = {}
        self.active_stops: Dict[str, OrderTicket] = {}    # portfolio_id -> active stop loss order
        self.active_targets: Dict[str, OrderTicket] = {}  # portfolio_id -> active take profit order
        self.pending_orders: Dict[str, OrderTicket] = {}  # order_id -> resting LIMIT / STOP_MARKET awaiting trigger
        self.current_price: Decimal = Decimal("0.00")
        self.current_atr: Decimal = Decimal("12.00")
        self.pool_depth: Decimal = pool_depth  # A4: fixed model parameter, not measured depth (see DEFAULT_POOL_DEPTH).
        self.execution_audit: List[FillEvent] = []
        self.rejection_audit: List[tuple[str, str]] = []
        self._seq_counter: int = 0

    def reset_seq(self, start: int = 0) -> None:
        """Raises the fill-sequence floor, never lowers it.

        fill_seq is globally increasing: the ledger uses it as PRIMARY KEY
        with INSERT OR REPLACE, so reusing a number would silently overwrite
        an earlier fill. Warmup purges clear the in-memory audit but must
        never rewind the counter.
        """
        self._seq_counter = max(self._seq_counter, int(start))

    def compute_execution_slippage(
        self,
        side: OrderSide,
        order_type: OrderType,
        qty: Decimal,
        mid_price: Decimal,
        atr: Decimal = Decimal("12.0"),
    ) -> Decimal:
        """
        Computes dynamic execution fill price factoring in half-spread,
        quadratic orderbook liquidity depth exhaustion, and ATR volatility adverse selection.
        """
        if order_type == OrderType.LIMIT:
            return mid_price

        # 1. Base half-spread (0.01% or configured slippage_pct)
        base_spread_pct = self.slippage_pct if self.slippage_pct > Decimal("0") else Decimal("0.0001")
        half_spread = mid_price * base_spread_pct

        # 2. Quadratic Market Depth impact
        pool_depth = self.pool_depth if self.pool_depth > Decimal("0") else DEFAULT_POOL_DEPTH
        depth_ratio = min(Decimal("1.5"), qty / pool_depth)
        impact_pct = Decimal("0.0005") * (depth_ratio ** 2)

        # 3. Volatility adverse selection
        vol_impact = (atr / mid_price) * Decimal("0.015") if mid_price > Decimal("0") else Decimal("0")

        total_slippage = half_spread + (mid_price * (impact_pct + vol_impact))

        if side == OrderSide.BUY:
            return (mid_price + total_slippage).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
        else:
            return max(Decimal("0.01"), (mid_price - total_slippage).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP))

    def register_portfolio(
        self,
        portfolio: Portfolio,
        max_position_ratio: Decimal = Decimal("0.50")
    ) -> None:
        self.portfolios[portfolio.portfolio_id] = portfolio
        self.competitor_caps[portfolio.portfolio_id] = max_position_ratio

    def submit_order(self, ticket: OrderTicket) -> Optional[FillEvent]:
        """
        Public order entry: MARKET orders fill immediately; LIMIT and
        STOP_MARKET orders only fill once the market touches their price.

        An untriggered LIMIT / STOP_MARKET order is parked in
        ``pending_orders`` (it is NOT a rejection and is NOT logged in
        ``rejection_audit``) and re-evaluated on every ``on_tick`` against
        the bar's high/low. ``on_tick`` bracket exits (SL / TP / liquidation /
        circuit breaker) already evaluated their own triggers, so they call
        ``_execute_fill`` directly and bypass this gate.
        """
        # Resting orders need a real market price to judge the trigger;
        # before the first tick there is nothing to compare against.
        if ticket.price is not None and self.current_price > Decimal("0"):
            if ticket.order_type == OrderType.LIMIT:
                if not self._limit_hit(ticket.side, ticket.price, self.current_price, self.current_price):
                    self.pending_orders[ticket.order_id] = ticket
                    return None
            elif ticket.order_type == OrderType.STOP_MARKET:
                if not self._stop_hit(ticket.side, ticket.price, self.current_price, self.current_price):
                    self.pending_orders[ticket.order_id] = ticket
                    return None
        return self._execute_fill(ticket)

    @staticmethod
    def _limit_hit(side: OrderSide, limit_price: Decimal, low: Decimal, high: Decimal) -> bool:
        """True when the bar traded at or through a LIMIT price."""
        if side == OrderSide.BUY:
            return low <= limit_price
        return high >= limit_price

    @staticmethod
    def _stop_hit(side: OrderSide, stop_price: Decimal, low: Decimal, high: Decimal) -> bool:
        """True when the bar traded at or through a STOP trigger price."""
        if side == OrderSide.BUY:
            return high >= stop_price
        return low <= stop_price

    def _execute_fill(self, ticket: OrderTicket) -> Optional[FillEvent]:
        """
        Immediate fill path: RiskGuard validation + execution + bracket
        registration. The caller must already have evaluated any trigger
        (public ``submit_order`` for resting orders, ``on_tick`` for
        bracket exits whose trigger was checked against the bar high/low).
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
            if len(self.rejection_audit) > 500:
                del self.rejection_audit[:-500]
            return None

        # Determine execution price:
        # LIMIT orders fill at their limit price without adverse taker slippage;
        # MARKET / STOP_MARKET orders fill with realistic depth & volatility slippage around reference price.
        if ticket.order_type == OrderType.LIMIT and ticket.price is not None:
            fill_price = ticket.price.quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
        elif self.slippage_pct <= Decimal("0"):
            fill_price = ref_price.quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
        else:
            fill_price = self.compute_execution_slippage(
                side=ticket.side,
                order_type=ticket.order_type,
                qty=ticket.qty,
                mid_price=ref_price,
                atr=self.current_atr,
            )
            # Ensure dynamic depth/volatility slippage on opening orders never exceeds available cash margin
            is_closing = (
                (portfolio.position_side == PositionSide.LONG and ticket.side == OrderSide.SELL)
                or (portfolio.position_side == PositionSide.SHORT and ticket.side == OrderSide.BUY)
            )
            if not is_closing and portfolio.position_qty >= Decimal("0"):
                eff_lev = portfolio.leverage if portfolio.leverage_enabled and portfolio.leverage > Decimal("0") else Decimal("1.0")
                trade_val = (ticket.qty * fill_price).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                req_margin = (trade_val / eff_lev).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                est_fee = (trade_val * portfolio.fee_rate).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                if (req_margin + est_fee) > portfolio.cash:
                    # Fallback to base slippage price validated by RiskGuard
                    mult = (Decimal("1") + self.slippage_pct) if ticket.side == OrderSide.BUY else (Decimal("1") - self.slippage_pct)
                    fill_price = (ref_price * mult).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)

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

        # Audit 3.22: a fill the ledger cannot apply (insufficient
        # cash / oversell -- RiskGuard validated against its own price
        # basis, which can disagree with the ledger) must not kill the
        # cadence. Log it, record it like any other rejection (same
        # 500 cap), skip the fill, and let the rest of the tick run.
        # Only ValueError is caught: the KeyError for an unknown
        # portfolio above is a programming error and still raises.
        try:
            enriched_fill = portfolio.apply_fill(raw_fill)
        except ValueError as exc:
            logger.warning("apply_fill failed for %s: %s", ticket.portfolio_id, exc)
            self.rejection_audit.append((ticket.portfolio_id, f"apply_fill failed: {exc}"))
            if len(self.rejection_audit) > 500:
                del self.rejection_audit[:-500]
            return None
        self.execution_audit.append(enriched_fill)

        # Register or clear Bracket Exits
        if portfolio.position_qty > Decimal("0"):
            exit_side = OrderSide.SELL if portfolio.position_side == PositionSide.LONG else OrderSide.BUY
            if ticket.stop_loss is not None:
                self.active_stops[ticket.portfolio_id] = OrderTicket(
                    portfolio_id=ticket.portfolio_id,
                    symbol=ticket.symbol,
                    side=exit_side,
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
                    side=exit_side,
                    order_type=OrderType.LIMIT,
                    qty=portfolio.position_qty,
                    price=ticket.take_profit,
                    reason=ExecutionReason.TAKE_PROFIT,
                    timestamp=ticket.timestamp
                )
        elif portfolio.position_qty == Decimal("0"):
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

            is_short = (p.position_side == PositionSide.SHORT)
            exit_side = OrderSide.BUY if is_short else OrderSide.SELL

            # Check Stop-Loss (or Trailing Stop) first
            stop_order = self.active_stops.get(p_id)
            if stop_order and stop_order.price is not None:
                stop_hit = (high_price >= stop_order.price) if is_short else (low_price <= stop_order.price)
                if stop_hit:
                    if is_short:
                        trigger_p = max(bar_open, stop_order.price) if open_price is not None else stop_order.price
                        reason = (
                            ExecutionReason.TRAILING_STOP
                            if (p.avg_entry_price > Decimal("0") and stop_order.price < p.avg_entry_price)
                            else stop_order.reason
                        )
                    else:
                        trigger_p = min(bar_open, stop_order.price) if open_price is not None else stop_order.price
                        reason = (
                            ExecutionReason.TRAILING_STOP
                            if (p.avg_entry_price > Decimal("0") and stop_order.price > p.avg_entry_price)
                            else stop_order.reason
                        )

                    stop_fill = self._execute_fill(OrderTicket(
                        portfolio_id=p_id,
                        symbol=self.symbol,
                        side=exit_side,
                        order_type=OrderType.STOP_MARKET,
                        qty=p.position_qty,
                        price=trigger_p,
                        reason=reason,
                        timestamp=ts
                    ))
                    if stop_fill:
                        fills.append(stop_fill)
                    continue

            # Check Take-Profit
            target_order = self.active_targets.get(p_id)
            if target_order and target_order.price is not None:
                target_hit = (low_price <= target_order.price) if is_short else (high_price >= target_order.price)
                if target_hit:
                    trigger_p = (min(bar_open, target_order.price) if is_short else max(bar_open, target_order.price)) if open_price is not None else target_order.price
                    # Take-profit pays the same execution slippage as a stop
                    # fill (half-spread + depth + volatility adverse
                    # selection): a LIMIT fill lands exactly on
                    # ticket.price, so the slippage-adjusted price is baked
                    # into the ticket instead of booking the win at the
                    # exact target while the SL leg next to it pays slippage.
                    # Gated on slippage_pct > 0: the venue convention is
                    # that slippage 0 means no slippage anywhere.
                    if self.slippage_pct > Decimal("0"):
                        tp_price = self.compute_execution_slippage(
                            side=exit_side,
                            order_type=OrderType.MARKET,
                            qty=p.position_qty,
                            mid_price=trigger_p,
                            atr=self.current_atr,
                        )
                    else:
                        tp_price = trigger_p
                    target_fill = self._execute_fill(OrderTicket(
                        portfolio_id=p_id,
                        symbol=self.symbol,
                        side=exit_side,
                        order_type=OrderType.LIMIT,
                        qty=p.position_qty,
                        price=tp_price,
                        reason=ExecutionReason.TAKE_PROFIT,
                        timestamp=ts
                    ))
                    if target_fill:
                        fills.append(target_fill)

        # 1b. Evaluate resting (pending) LIMIT / STOP_MARKET orders against
        # this bar's high/low. A triggered order fills now: LIMIT at its
        # limit price, STOP_MARKET at market with slippage around the stop.
        # Validation runs again at fill time; an order that no longer
        # passes is dropped (rejection is logged by _execute_fill).
        if self.pending_orders:
            for order_id in list(self.pending_orders.keys()):
                ticket = self.pending_orders.get(order_id)
                if ticket is None or ticket.price is None:
                    continue
                if ticket.order_type == OrderType.LIMIT:
                    hit = self._limit_hit(ticket.side, ticket.price, low_price, high_price)
                elif ticket.order_type == OrderType.STOP_MARKET:
                    hit = self._stop_hit(ticket.side, ticket.price, low_price, high_price)
                else:
                    hit = False
                if not hit:
                    continue
                del self.pending_orders[order_id]
                pending_fill = self._execute_fill(replace(ticket, timestamp=ts))
                if pending_fill:
                    fills.append(pending_fill)

        # 2. Update end-of-bar valuation & check 15% drawdown circuit breaker
        for p_id, p in self.portfolios.items():
            p.update_market_price(price, ts, low_price=low_price, high_price=high_price)
            # Leverage maintenance margin liquidation (protects against negative balance).
            # Audit 2.4: compare POSITION equity against POSITION margin, not
            # total equity. total_equity includes all idle cash, so the old
            # comparison needed a ~139% adverse move on a 3x/70% long and
            # could never fire. Position equity is margin_locked +
            # unrealized_pnl; liquidation fires once the position has lost
            # 90% of its margin (maintenance level 10%).
            if p.leverage_enabled and p.position_qty > Decimal("0") and p.margin_locked > Decimal("0"):
                position_equity = p.margin_locked + p.unrealized_pnl
                if position_equity <= (p.margin_locked * LIQUIDATION_MAINTENANCE_RATIO):
                    p.is_circuit_breaker_tripped = True
                    liq_exit_side = OrderSide.BUY if p.position_side == PositionSide.SHORT else OrderSide.SELL
                    liq_fill = self._execute_fill(OrderTicket(
                        portfolio_id=p_id,
                        symbol=self.symbol,
                        side=liq_exit_side,
                        order_type=OrderType.MARKET,
                        qty=p.position_qty,
                        price=price,
                        reason=ExecutionReason.LIQUIDATION,
                        timestamp=ts
                    ))
                    if liq_fill:
                        fills.append(liq_fill)
                    continue

            if not p.is_circuit_breaker_tripped and p.max_drawdown_pct >= MAX_DRAWDOWN_LIMIT_PCT:
                p.is_circuit_breaker_tripped = True
                if p.position_qty > Decimal("0"):
                    cb_exit_side = OrderSide.BUY if p.position_side == PositionSide.SHORT else OrderSide.SELL
                    cb_fill = self._execute_fill(OrderTicket(
                        portfolio_id=p_id,
                        symbol=self.symbol,
                        side=cb_exit_side,
                        order_type=OrderType.MARKET,
                        qty=p.position_qty,
                        price=price,
                        reason=ExecutionReason.CIRCUIT_BREAKER,
                        timestamp=ts
                    ))
                    if cb_fill:
                        fills.append(cb_fill)

        return fills

    execute_order = submit_order
