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
from src.arena.portfolio import Portfolio, PRECISION_CASH, PRECISION_CRYPTO
from src.arena.risk_guard import RiskGuard, MAX_DRAWDOWN_LIMIT_PCT

# Exit reasons that should be cancelled automatically when a position returns to FLAT.
_EXIT_PENDING_REASONS = frozenset((
    ExecutionReason.STOP_LOSS,
    ExecutionReason.TAKE_PROFIT,
    ExecutionReason.TRAILING_STOP,
    ExecutionReason.SIGNAL_EXIT,
))

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
        max_audit_size: Optional[int] = None,
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
        self.max_audit_size: Optional[int] = max_audit_size
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
        safe_atr = atr if (atr.is_finite() and atr > Decimal("0")) else Decimal("0")
        vol_impact = (safe_atr / mid_price) * Decimal("0.015") if mid_price > Decimal("0") else Decimal("0")

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

    def _record_rejection(self, portfolio_id: str, reason: str) -> None:
        self.rejection_audit.append((portfolio_id, reason))
        if len(self.rejection_audit) > 500:
            del self.rejection_audit[:-500]

    @staticmethod
    def _is_closing_ticket(portfolio: Portfolio, ticket: OrderTicket) -> bool:
        return (
            (portfolio.position_side == PositionSide.LONG and ticket.side == OrderSide.SELL)
            or (portfolio.position_side == PositionSide.SHORT and ticket.side == OrderSide.BUY)
        )

    @staticmethod
    def _clamp_bar_trigger(trigger_p: Decimal, low_price: Decimal, high_price: Decimal) -> Decimal:
        clamped = max(low_price, min(high_price, trigger_p))
        return max(PRECISION_CASH, clamped)

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
        if ticket.order_type in (OrderType.LIMIT, OrderType.STOP_MARKET) and ticket.price is not None:
            portfolio = self.portfolios.get(ticket.portfolio_id)
            if portfolio is None:
                raise KeyError(f"Unknown portfolio {ticket.portfolio_id}")
            if (
                not ticket.qty.is_finite()
                or ticket.qty <= Decimal("0")
                or ticket.qty.quantize(PRECISION_CRYPTO, rounding=ROUND_HALF_UP) <= Decimal("0")
                or not ticket.price.is_finite()
                or ticket.price <= Decimal("0")
                or ticket.price.quantize(PRECISION_CASH, rounding=ROUND_HALF_UP) <= Decimal("0")
            ):
                return self._execute_fill(ticket)
            is_closing = self._is_closing_ticket(portfolio, ticket)
            # Validate optional brackets before parking so malformed/inverted resting
            # orders are rejected immediately rather than silently parked.
            if ticket.stop_loss is not None:
                if not ticket.stop_loss.is_finite() or ticket.stop_loss <= Decimal("0"):
                    return self._execute_fill(ticket)
                if not is_closing:
                    if ticket.side == OrderSide.BUY and ticket.stop_loss >= ticket.price:
                        return self._execute_fill(ticket)
                    if ticket.side == OrderSide.SELL and ticket.stop_loss <= ticket.price:
                        return self._execute_fill(ticket)
            if ticket.take_profit is not None:
                if not ticket.take_profit.is_finite() or ticket.take_profit <= Decimal("0"):
                    return self._execute_fill(ticket)
                if not is_closing:
                    if ticket.side == OrderSide.BUY and ticket.take_profit <= ticket.price:
                        return self._execute_fill(ticket)
                    if ticket.side == OrderSide.SELL and ticket.take_profit >= ticket.price:
                        return self._execute_fill(ticket)
            if not is_closing and (
                portfolio.is_circuit_breaker_tripped
                or portfolio.max_drawdown_pct >= MAX_DRAWDOWN_LIMIT_PCT
            ):
                return self._execute_fill(ticket)
            if ticket.order_id in self.pending_orders:
                self._record_rejection(ticket.portfolio_id, f"Duplicate pending order_id: {ticket.order_id}")
                return None
            if self.current_price <= Decimal("0"):
                self.pending_orders[ticket.order_id] = ticket
                return None
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

    def _execute_fill(
        self,
        ticket: OrderTicket,
        override_price: Optional[Decimal] = None,
    ) -> Optional[FillEvent]:
        """
        Immediate fill path: RiskGuard validation + execution + bracket
        registration. The caller must already have evaluated any trigger
        (public ``submit_order`` for resting orders, ``on_tick`` for
        bracket exits whose trigger was checked against the bar high/low).
        """
        portfolio = self.portfolios.get(ticket.portfolio_id)
        if not portfolio:
            raise KeyError(f"Unknown portfolio {ticket.portfolio_id}")

        if override_price is not None:
            ref_price = override_price
        else:
            ref_price = ticket.price if ticket.price is not None else self.current_price
        max_cap = self.competitor_caps.get(ticket.portfolio_id, Decimal("0.50"))

        # Guard non-finite/non-positive inputs BEFORE any quantize or slippage math
        # so malformed tickets are cleanly rejected by RiskGuard instead of raising InvalidOperation.
        if (
            not ticket.qty.is_finite()
            or ticket.qty <= Decimal("0")
            or not ref_price.is_finite()
            or ref_price <= Decimal("0")
            or (ticket.order_type in (OrderType.LIMIT, OrderType.STOP_MARKET) and ticket.price is None)
        ):
            valid, reason = RiskGuard.validate_order(
                ticket, portfolio, max_cap, ref_price, Decimal("0")
            )
            if not valid:
                self._record_rejection(ticket.portfolio_id, reason)
                return None

        qty_q = ticket.qty.quantize(PRECISION_CRYPTO, rounding=ROUND_HALF_UP)
        if qty_q <= Decimal("0"):
            self._record_rejection(ticket.portfolio_id, "Order quantity must be positive after quantization.")
            return None

        # Determine execution price before pre-trade RiskGuard validation so
        # RiskGuard and Portfolio.apply_fill validate on the exact same basis.
        # LIMIT orders fill at their limit price without adverse taker slippage;
        # MARKET / STOP_MARKET orders fill with realistic depth & volatility slippage.
        if ticket.order_type == OrderType.LIMIT and ticket.price is not None:
            fill_price = ticket.price.quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
            val_slippage = Decimal("0")
        elif self.slippage_pct <= Decimal("0") or ref_price <= Decimal("0"):
            fill_price = ref_price.quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
            val_slippage = Decimal("0")
        else:
            fill_price = self.compute_execution_slippage(
                side=ticket.side,
                order_type=ticket.order_type,
                qty=qty_q,
                mid_price=ref_price,
                atr=self.current_atr,
            )
            val_slippage = abs(fill_price - ref_price) / ref_price

        if fill_price <= Decimal("0"):
            self._record_rejection(ticket.portfolio_id, "Execution price must be positive after quantization.")
            return None

        valid, reason = RiskGuard.validate_order(
            ticket, portfolio, max_cap, ref_price, val_slippage
        )
        if not valid:
            self._record_rejection(ticket.portfolio_id, reason)
            return None

        fee = (qty_q * fill_price * portfolio.fee_rate).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
        was_flat = portfolio.position_qty <= Decimal("0")

        next_seq = self._seq_counter + 1
        raw_fill = FillEvent(
            order_id=ticket.order_id,
            portfolio_id=ticket.portfolio_id,
            symbol=ticket.symbol,
            side=ticket.side,
            qty=qty_q,
            price=fill_price,
            fee=fee,
            timestamp=ticket.timestamp,
            reason=ticket.reason,
            fill_seq=next_seq
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
            self._record_rejection(ticket.portfolio_id, f"apply_fill failed: {exc}")
            return None
        self._seq_counter = next_seq
        self.execution_audit.append(enriched_fill)
        if self.max_audit_size is not None and len(self.execution_audit) > self.max_audit_size:
            del self.execution_audit[:-self.max_audit_size]

        # Register, sync, or clear Bracket Exits
        if portfolio.position_qty > Decimal("0"):
            if was_flat:
                # Fresh open from flat: clear any stale brackets from a prior position.
                self.active_stops.pop(ticket.portfolio_id, None)
                self.active_targets.pop(ticket.portfolio_id, None)
            exit_side = OrderSide.SELL if portfolio.position_side == PositionSide.LONG else OrderSide.BUY
            is_opening_or_expanding = not enriched_fill.is_closing_fill
            if (
                is_opening_or_expanding
                and ticket.stop_loss is not None
                and ticket.stop_loss.is_finite()
                and ticket.stop_loss > Decimal("0")
            ):
                sl_q = max(PRECISION_CASH, ticket.stop_loss.quantize(PRECISION_CASH, rounding=ROUND_HALF_UP))
                self.active_stops[ticket.portfolio_id] = OrderTicket(
                    portfolio_id=ticket.portfolio_id,
                    symbol=ticket.symbol,
                    side=exit_side,
                    order_type=OrderType.STOP_MARKET,
                    qty=portfolio.position_qty,
                    price=sl_q,
                    reason=ExecutionReason.STOP_LOSS,
                    timestamp=ticket.timestamp
                )
            elif ticket.portfolio_id in self.active_stops:
                self.active_stops[ticket.portfolio_id] = replace(
                    self.active_stops[ticket.portfolio_id],
                    qty=portfolio.position_qty,
                    side=exit_side,
                )
            if (
                is_opening_or_expanding
                and ticket.take_profit is not None
                and ticket.take_profit.is_finite()
                and ticket.take_profit > Decimal("0")
            ):
                tp_q = max(PRECISION_CASH, ticket.take_profit.quantize(PRECISION_CASH, rounding=ROUND_HALF_UP))
                self.active_targets[ticket.portfolio_id] = OrderTicket(
                    portfolio_id=ticket.portfolio_id,
                    symbol=ticket.symbol,
                    side=exit_side,
                    order_type=OrderType.LIMIT,
                    qty=portfolio.position_qty,
                    price=tp_q,
                    reason=ExecutionReason.TAKE_PROFIT,
                    timestamp=ticket.timestamp
                )
            elif ticket.portfolio_id in self.active_targets:
                self.active_targets[ticket.portfolio_id] = replace(
                    self.active_targets[ticket.portfolio_id],
                    qty=portfolio.position_qty,
                    side=exit_side,
                )
        elif portfolio.position_qty == Decimal("0"):
            self.active_stops.pop(ticket.portfolio_id, None)
            self.active_targets.pop(ticket.portfolio_id, None)
            # Cancel orphaned exit-tagged resting orders so they can never flip a flat account.
            for oid in [
                k for k, t in self.pending_orders.items()
                if t.portfolio_id == ticket.portfolio_id and t.reason in _EXIT_PENDING_REASONS
            ]:
                self.pending_orders.pop(oid, None)

        return enriched_fill

    @staticmethod
    def _liquidation_price_if_breached(
        p: Portfolio,
        price: Decimal,
        high_price: Decimal,
        low_price: Decimal,
    ) -> Optional[Decimal]:
        """Returns the maintenance liquidation price if the open position is eligible
        for margin liquidation AND this bar breached maintenance margin; otherwise None."""
        if p.position_qty <= Decimal("0") or p.margin_locked <= Decimal("0"):
            return None
        is_short = p.position_side == PositionSide.SHORT
        if not is_short:
            # Position-intrinsic leverage check: a 1x cash-paid LONG cannot be
            # liquidated even if a later generation enables leverage on the genome.
            is_pos_leveraged = bool(getattr(p, "position_is_leveraged", False))
            if not is_pos_leveraged:
                entry_notional = (p.avg_entry_price * p.position_qty).quantize(
                    PRECISION_CASH, rounding=ROUND_HALF_UP
                )
                is_pos_leveraged = entry_notional > Decimal("0") and p.margin_locked < (
                    entry_notional - Decimal("0.05")
                )
            if not is_pos_leveraged:
                return None

        adverse_price = high_price if is_short else low_price
        close_upnl = (
            ((p.avg_entry_price - price) * p.position_qty).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
            if is_short
            else ((price - p.avg_entry_price) * p.position_qty).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
        )
        adverse_upnl = (
            ((p.avg_entry_price - adverse_price) * p.position_qty).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
            if is_short
            else ((adverse_price - p.avg_entry_price) * p.position_qty).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
        )
        worst_upnl = min(close_upnl, adverse_upnl)
        position_equity = p.margin_locked + worst_upnl
        if position_equity > (p.margin_locked * LIQUIDATION_MAINTENANCE_RATIO):
            return None

        max_loss = p.margin_locked * (Decimal("1") - LIQUIDATION_MAINTENANCE_RATIO)
        if is_short:
            return (p.avg_entry_price + (max_loss / p.position_qty)).quantize(
                PRECISION_CASH, rounding=ROUND_HALF_UP
            )
        return max(
            PRECISION_CASH,
            (p.avg_entry_price - (max_loss / p.position_qty)).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP),
        )

    def _check_leveraged_liquidation(
        self,
        p_id: str,
        p: Portfolio,
        price: Decimal,
        high_price: Decimal,
        low_price: Decimal,
        bar_open: Decimal,
        has_valid_open: bool,
        ts: float,
        precomputed_liq_price: Optional[Decimal] = None,
    ) -> Optional[FillEvent]:
        """Evaluates maintenance-margin liquidation on an open leveraged position.

        Checks whether the open position itself carries leverage (even if a
        subsequent generation flipped genome.leverage_enabled to False), uses
        intra-bar adverse excursion (low for LONG, high for SHORT), and fills at
        the maintenance liquidation trigger price (or worse gap bar_open) clamped
        inside the bar's traded [low_price, high_price] range.
        """
        liq_price = (
            precomputed_liq_price
            if precomputed_liq_price is not None
            else self._liquidation_price_if_breached(p, price, high_price, low_price)
        )
        if liq_price is None:
            return None

        is_short = p.position_side == PositionSide.SHORT
        if is_short:
            trigger_p = max(bar_open, liq_price) if has_valid_open else max(price, liq_price)
        else:
            trigger_p = min(bar_open, liq_price) if has_valid_open else min(price, liq_price)
        trigger_p = self._clamp_bar_trigger(trigger_p, low_price, high_price)

        p.is_circuit_breaker_tripped = True
        for oid in [k for k, t in self.pending_orders.items() if t.portfolio_id == p_id]:
            self.pending_orders.pop(oid, None)
        liq_exit_side = OrderSide.BUY if is_short else OrderSide.SELL
        return self._execute_fill(
            OrderTicket(
                portfolio_id=p_id,
                symbol=self.symbol,
                side=liq_exit_side,
                order_type=OrderType.MARKET,
                qty=p.position_qty,
                price=trigger_p,
                reason=ExecutionReason.LIQUIDATION,
                timestamp=ts,
            ),
            override_price=trigger_p,
        )

    def _execute_pending_order(
        self,
        order_id: str,
        ticket: OrderTicket,
        low_price: Decimal,
        high_price: Decimal,
        bar_open: Decimal,
        has_valid_open: bool,
        ts: float,
    ) -> Optional[FillEvent]:
        if ticket.price is None:
            return None
        if ticket.order_type == OrderType.LIMIT:
            hit = self._limit_hit(ticket.side, ticket.price, low_price, high_price)
        elif ticket.order_type == OrderType.STOP_MARKET:
            hit = self._stop_hit(ticket.side, ticket.price, low_price, high_price)
        else:
            hit = False
        if not hit:
            return None
        self.pending_orders.pop(order_id, None)
        if ticket.order_type == OrderType.STOP_MARKET:
            if has_valid_open:
                trigger_p = (
                    max(bar_open, ticket.price)
                    if ticket.side == OrderSide.BUY
                    else min(bar_open, ticket.price)
                )
            else:
                trigger_p = ticket.price
            trigger_p = self._clamp_bar_trigger(trigger_p, low_price, high_price)
            pending_ticket = replace(ticket, price=trigger_p, timestamp=ts)
        else:
            pending_ticket = replace(ticket, timestamp=ts)
        return self._execute_fill(pending_ticket)

    def _check_and_trip_circuit_breaker(
        self,
        p_id: str,
        p: Portfolio,
        price: Decimal,
        ts: float,
    ) -> Optional[FillEvent]:
        if p.is_circuit_breaker_tripped or p.max_drawdown_pct < MAX_DRAWDOWN_LIMIT_PCT:
            return None
        p.is_circuit_breaker_tripped = True
        for oid in [k for k, t in self.pending_orders.items() if t.portfolio_id == p_id]:
            self.pending_orders.pop(oid, None)
        if p.position_qty <= Decimal("0"):
            return None
        cb_exit_side = OrderSide.BUY if p.position_side == PositionSide.SHORT else OrderSide.SELL
        return self._execute_fill(
            OrderTicket(
                portfolio_id=p_id,
                symbol=self.symbol,
                side=cb_exit_side,
                order_type=OrderType.MARKET,
                qty=p.position_qty,
                price=price,
                reason=ExecutionReason.CIRCUIT_BREAKER,
                timestamp=ts,
            ),
            override_price=price,
        )

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
        1. Evaluates intra-bar Stop-Loss, Leveraged Liquidation (preempting SL if
           maintenance margin is hit first or breached at bar open), closing
           pending orders, and Take-Profit (conservative priority: losses/liquidations
           before TP on ambiguous bars).
        2. Updates end-of-bar portfolio mark-to-market valuation & checks 15% circuit breakers
           (purging opening pending orders for tripped portfolios).
        3. Evaluates surviving opening/expanding resting LIMIT / STOP_MARKET orders against
           this bar's high/low, marks newly filled portfolios at bar close, and runs
           liquidation & circuit-breaker checks on those fills.
        """
        if not price.is_finite() or price <= Decimal("0"):
            return []
        ts = timestamp if timestamp is not None else time.time()
        self.current_price = price
        high_price = high if (high is not None and high.is_finite() and high > Decimal("0")) else price
        low_price = low if (low is not None and low.is_finite() and low > Decimal("0")) else price
        high_price = max(high_price, price)
        low_price = min(low_price, price)
        has_valid_open = (
            open_price is not None and open_price.is_finite() and open_price > Decimal("0")
        )
        bar_open = open_price if has_valid_open else price

        fills: List[FillEvent] = []

        # 1. Check bracket stops, leveraged liquidation, closing pending orders, and targets
        for p_id, p in self.portfolios.items():
            if p.position_qty <= Decimal("0"):
                continue

            is_short = (p.position_side == PositionSide.SHORT)
            exit_side = OrderSide.BUY if is_short else OrderSide.SELL

            stop_order = self.active_stops.get(p_id)
            valid_stop = (
                stop_order is not None
                and stop_order.price is not None
                and stop_order.price.is_finite()
                and stop_order.price > Decimal("0")
            )
            stop_hit = (
                ((high_price >= stop_order.price) if is_short else (low_price <= stop_order.price))
                if valid_stop
                else False
            )

            liq_price = self._liquidation_price_if_breached(p, price, high_price, low_price)
            liq_precedes_stop = False
            if liq_price is not None:
                if not stop_hit:
                    liq_precedes_stop = True
                elif stop_order is not None and stop_order.price is not None:
                    if is_short:
                        liq_precedes_stop = (
                            stop_order.price >= liq_price
                            or (has_valid_open and bar_open >= liq_price)
                        )
                    else:
                        liq_precedes_stop = (
                            stop_order.price <= liq_price
                            or (has_valid_open and bar_open <= liq_price)
                        )

            if liq_precedes_stop:
                liq_fill = self._check_leveraged_liquidation(
                    p_id, p, price, high_price, low_price, bar_open, has_valid_open, ts,
                    precomputed_liq_price=liq_price,
                )
                if liq_fill is not None:
                    fills.append(liq_fill)
                    continue

            # Check Stop-Loss (or Trailing Stop)
            if stop_hit and stop_order is not None and stop_order.price is not None:
                if is_short:
                    trigger_p = max(bar_open, stop_order.price) if has_valid_open else stop_order.price
                    reason = (
                        ExecutionReason.TRAILING_STOP
                        if (p.avg_entry_price > Decimal("0") and stop_order.price < p.avg_entry_price)
                        else stop_order.reason
                    )
                else:
                    trigger_p = min(bar_open, stop_order.price) if has_valid_open else stop_order.price
                    reason = (
                        ExecutionReason.TRAILING_STOP
                        if (p.avg_entry_price > Decimal("0") and stop_order.price > p.avg_entry_price)
                        else stop_order.reason
                    )
                trigger_p = self._clamp_bar_trigger(trigger_p, low_price, high_price)

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

            # Fallback liquidation check if stop_fill failed or was not hit
            if liq_price is not None and p.position_qty > Decimal("0"):
                liq_fill = self._check_leveraged_liquidation(
                    p_id, p, price, high_price, low_price, bar_open, has_valid_open, ts,
                    precomputed_liq_price=liq_price,
                )
                if liq_fill is not None:
                    fills.append(liq_fill)
                    continue

            # Evaluate resting CLOSING pending orders BEFORE Step 2 mark-to-market & circuit breaker
            # so a protective resting stop/limit exit fires instead of being wiped by the breaker.
            if self.pending_orders and p.position_qty > Decimal("0"):
                for order_id in list(self.pending_orders.keys()):
                    t = self.pending_orders.get(order_id)
                    if t is None or t.portfolio_id != p_id:
                        continue
                    if not self._is_closing_ticket(p, t):
                        continue
                    pfill = self._execute_pending_order(
                        order_id, t, low_price, high_price, bar_open, has_valid_open, ts
                    )
                    if pfill:
                        fills.append(pfill)
                    if p.position_qty <= Decimal("0"):
                        break
                if p.position_qty <= Decimal("0"):
                    continue

            # Check Take-Profit
            target_order = self.active_targets.get(p_id)
            if (
                target_order is not None
                and target_order.price is not None
                and target_order.price.is_finite()
                and target_order.price > Decimal("0")
            ):
                target_hit = (low_price <= target_order.price) if is_short else (high_price >= target_order.price)
                if target_hit:
                    trigger_p = (
                        (min(bar_open, target_order.price) if is_short else max(bar_open, target_order.price))
                        if has_valid_open
                        else target_order.price
                    )
                    trigger_p = self._clamp_bar_trigger(trigger_p, low_price, high_price)
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

        # 2. Update end-of-bar valuation & check 15% drawdown circuit breaker BEFORE
        # evaluating opening pending orders so a crash bar trips the breaker and purges
        # resting opening orders instead of buying into a crash and immediately force-closing.
        for p_id, p in self.portfolios.items():
            p.update_market_price(price, ts, low_price=low_price, high_price=high_price)
            cb_fill = self._check_and_trip_circuit_breaker(p_id, p, price, ts)
            if cb_fill:
                fills.append(cb_fill)

        # 3. Evaluate remaining (opening/expanding) resting LIMIT / STOP_MARKET orders.
        if self.pending_orders:
            filled_pending_pids = set()
            for order_id in list(self.pending_orders.keys()):
                ticket = self.pending_orders.get(order_id)
                if ticket is None or ticket.price is None:
                    continue
                pending_fill = self._execute_pending_order(
                    order_id, ticket, low_price, high_price, bar_open, has_valid_open, ts
                )
                if pending_fill:
                    fills.append(pending_fill)
                    filled_pending_pids.add(ticket.portfolio_id)
            for p_id in filled_pending_pids:
                p = self.portfolios.get(p_id)
                if p is not None:
                    p.update_market_price(price, ts)
                    if p.position_qty > Decimal("0"):
                        post_liq = self._check_leveraged_liquidation(
                            p_id, p, price, price, price, price, False, ts
                        )
                        if post_liq is not None:
                            fills.append(post_liq)
                            continue
                    post_cb = self._check_and_trip_circuit_breaker(p_id, p, price, ts)
                    if post_cb is not None:
                        fills.append(post_cb)

        return fills

    execute_order = submit_order
