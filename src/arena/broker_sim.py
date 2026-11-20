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
                or not ticket.price.is_finite()
                or ticket.price <= Decimal("0")
            ):
                return self._execute_fill(ticket)
            is_closing = (
                (portfolio.position_side == PositionSide.LONG and ticket.side == OrderSide.SELL)
                or (portfolio.position_side == PositionSide.SHORT and ticket.side == OrderSide.BUY)
            )
            if not is_closing and (
                portfolio.is_circuit_breaker_tripped
                or portfolio.max_drawdown_pct >= MAX_DRAWDOWN_LIMIT_PCT
            ):
                return self._execute_fill(ticket)
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
                self.rejection_audit.append((ticket.portfolio_id, reason))
                if len(self.rejection_audit) > 500:
                    del self.rejection_audit[:-500]
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
                qty=ticket.qty,
                mid_price=ref_price,
                atr=self.current_atr,
            )
            val_slippage = abs(fill_price - ref_price) / ref_price

        valid, reason = RiskGuard.validate_order(
            ticket, portfolio, max_cap, ref_price, val_slippage
        )
        if not valid:
            self.rejection_audit.append((ticket.portfolio_id, reason))
            if len(self.rejection_audit) > 500:
                del self.rejection_audit[:-500]
            return None

        fee = (ticket.qty * fill_price * portfolio.fee_rate).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
        was_flat = portfolio.position_qty <= Decimal("0")

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

        # Register, sync, or clear Bracket Exits
        if portfolio.position_qty > Decimal("0"):
            if was_flat:
                # Fresh open from flat: clear any stale brackets from a prior position.
                self.active_stops.pop(ticket.portfolio_id, None)
                self.active_targets.pop(ticket.portfolio_id, None)
            exit_side = OrderSide.SELL if portfolio.position_side == PositionSide.LONG else OrderSide.BUY
            if ticket.stop_loss is not None and ticket.stop_loss.is_finite() and ticket.stop_loss > Decimal("0"):
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
            elif ticket.portfolio_id in self.active_stops:
                self.active_stops[ticket.portfolio_id] = replace(
                    self.active_stops[ticket.portfolio_id],
                    qty=portfolio.position_qty,
                    side=exit_side,
                )
            if ticket.take_profit is not None and ticket.take_profit.is_finite() and ticket.take_profit > Decimal("0"):
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
            elif ticket.portfolio_id in self.active_targets:
                self.active_targets[ticket.portfolio_id] = replace(
                    self.active_targets[ticket.portfolio_id],
                    qty=portfolio.position_qty,
                    side=exit_side,
                )
        elif portfolio.position_qty == Decimal("0"):
            self.active_stops.pop(ticket.portfolio_id, None)
            self.active_targets.pop(ticket.portfolio_id, None)

        return enriched_fill

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
    ) -> Optional[FillEvent]:
        """Evaluates maintenance-margin liquidation on an open leveraged position.

        Checks whether the open position itself carries leverage (even if a
        subsequent generation flipped genome.leverage_enabled to False), uses
        intra-bar adverse excursion (low for LONG, high for SHORT), and fills at
        the maintenance liquidation trigger price (or worse gap bar_open) rather
        than bar close so flash-crash rebounds cannot turn liquidations into profits.
        """
        if p.position_qty <= Decimal("0") or p.margin_locked <= Decimal("0"):
            return None
        entry_notional = (p.avg_entry_price * p.position_qty).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
        is_pos_leveraged = p.leverage_enabled or (entry_notional > Decimal("0") and p.margin_locked < entry_notional)
        if not is_pos_leveraged:
            return None

        is_short = p.position_side == PositionSide.SHORT
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
            liq_price = (p.avg_entry_price + (max_loss / p.position_qty)).quantize(
                PRECISION_CASH, rounding=ROUND_HALF_UP
            )
            trigger_p = max(bar_open, liq_price) if has_valid_open else max(price, liq_price)
            trigger_p = min(trigger_p, high_price)
        else:
            liq_price = max(
                PRECISION_CASH,
                (p.avg_entry_price - (max_loss / p.position_qty)).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP),
            )
            trigger_p = min(bar_open, liq_price) if has_valid_open else min(price, liq_price)
            trigger_p = max(PRECISION_CASH, max(trigger_p, low_price))

        p.is_circuit_breaker_tripped = True
        for oid in [k for k, t in self.pending_orders.items() if t.portfolio_id == p_id]:
            self.pending_orders.pop(oid, None)
        liq_exit_side = OrderSide.BUY if is_short else OrderSide.SELL
        return self._execute_fill(OrderTicket(
            portfolio_id=p_id,
            symbol=self.symbol,
            side=liq_exit_side,
            order_type=OrderType.MARKET,
            qty=p.position_qty,
            price=trigger_p,
            reason=ExecutionReason.LIQUIDATION,
            timestamp=ts,
        ))

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
        1. Evaluates intra-bar Stop-Loss, then Leveraged Liquidation, then Take-Profit
           (conservative priority: losses/liquidations before TP on ambiguous bars).
        2. Updates end-of-bar portfolio mark-to-market valuation & checks 15% circuit breakers
           (purging pending orders for tripped portfolios).
        3. Evaluates surviving resting LIMIT / STOP_MARKET orders against this bar's high/low
           and marks newly filled portfolios at bar close.
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

        # 1. Check bracket stops, leveraged liquidation, and targets across all open positions
        for p_id, p in self.portfolios.items():
            if p.position_qty <= Decimal("0"):
                continue

            is_short = (p.position_side == PositionSide.SHORT)
            exit_side = OrderSide.BUY if is_short else OrderSide.SELL

            # Check Stop-Loss (or Trailing Stop) first
            stop_order = self.active_stops.get(p_id)
            if stop_order and stop_order.price is not None and stop_order.price.is_finite():
                stop_hit = (high_price >= stop_order.price) if is_short else (low_price <= stop_order.price)
                if stop_hit:
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

            # Check leveraged maintenance liquidation BEFORE Take-Profit so an
            # intra-bar margin wipeout cannot be bypassed by a later favorable wick.
            liq_fill = self._check_leveraged_liquidation(
                p_id, p, price, high_price, low_price, bar_open, has_valid_open, ts
            )
            if liq_fill is not None:
                fills.append(liq_fill)
                continue

            # Check Take-Profit
            target_order = self.active_targets.get(p_id)
            if target_order and target_order.price is not None and target_order.price.is_finite():
                target_hit = (low_price <= target_order.price) if is_short else (high_price >= target_order.price)
                if target_hit:
                    trigger_p = (
                        (min(bar_open, target_order.price) if is_short else max(bar_open, target_order.price))
                        if has_valid_open
                        else target_order.price
                    )
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
        # evaluating pending orders so a crash bar trips the breaker and purges
        # resting orders instead of buying into a crash and immediately force-closing.
        for p_id, p in self.portfolios.items():
            p.update_market_price(price, ts, low_price=low_price, high_price=high_price)
            if not p.is_circuit_breaker_tripped and p.max_drawdown_pct >= MAX_DRAWDOWN_LIMIT_PCT:
                p.is_circuit_breaker_tripped = True
                for oid in [k for k, t in self.pending_orders.items() if t.portfolio_id == p_id]:
                    self.pending_orders.pop(oid, None)
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

        # 3. Evaluate resting (pending) LIMIT / STOP_MARKET orders against this bar's high/low.
        if self.pending_orders:
            filled_pending_pids = set()
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
                if ticket.order_type == OrderType.STOP_MARKET and has_valid_open:
                    trigger_p = (
                        max(bar_open, ticket.price)
                        if ticket.side == OrderSide.BUY
                        else min(bar_open, ticket.price)
                    )
                    pending_ticket = replace(ticket, price=trigger_p, timestamp=ts)
                else:
                    pending_ticket = replace(ticket, timestamp=ts)
                pending_fill = self._execute_fill(pending_ticket)
                if pending_fill:
                    fills.append(pending_fill)
                    filled_pending_pids.add(ticket.portfolio_id)
            for p_id in filled_pending_pids:
                p = self.portfolios.get(p_id)
                if p is not None:
                    p.update_market_price(price, ts)

        return fills

    execute_order = submit_order
