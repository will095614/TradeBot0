from __future__ import annotations
from collections import deque
from decimal import Decimal, ROUND_HALF_UP
from itertools import islice
from typing import List, Optional, Tuple
import time
from dataclasses import replace
from src.arena.order import FillEvent, OrderSide, PositionSide

PRECISION_CASH = Decimal("0.01")
PRECISION_CRYPTO = Decimal("0.0001")
_ZERO = Decimal("0")
_ZERO_CASH = Decimal("0.00")
_ZERO_QTY = Decimal("0.0000")
_ONE = Decimal("1")
_HUNDRED = Decimal("100")


class _SliceableDeque(deque):
    """O(1)-append bounded deque that also supports Python list slicing (e.g. hist[-100:])."""

    def __getitem__(self, item):
        if isinstance(item, slice):
            start, stop, step = item.indices(len(self))
            if step == 1:
                return list(islice(self, start, stop))
            return list(self)[item]
        return super().__getitem__(item)


class Portfolio:
    """
    Precision Portfolio Ledger for Paper Trading Arena.
    Strictly uses Decimal arithmetic to eliminate IEEE 754 floating-point drift.
    Tracks exact round-trip realized PnL, intra-bar peak-to-trough drawdown, leverage margin, and deduplicated equity curves.
    """
    def __init__(
        self,
        portfolio_id: str,
        name: str,
        initial_cash: Decimal = Decimal("100000.00"),
        maker_taker_fee_rate: Decimal = Decimal("0.0005"),  # 0.05% standard fee
        leverage: Decimal = Decimal("1.0"),
        leverage_enabled: bool = False
    ):
        self.portfolio_id: str = portfolio_id
        self.name: str = name
        self.initial_cash: Decimal = initial_cash.quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
        self.cash: Decimal = self.initial_cash
        self.position_qty: Decimal = Decimal("0.0000")
        self.position_side: PositionSide = PositionSide.FLAT
        self.avg_entry_price: Decimal = Decimal("0.00")
        self.open_position_entry_fee: Decimal = Decimal("0.00")
        self.leverage: Decimal = leverage
        self.leverage_enabled: bool = leverage_enabled
        self.margin_locked: Decimal = Decimal("0.00")

        self.realized_pnl: Decimal = Decimal("0.00")
        self.total_fees_paid: Decimal = Decimal("0.00")
        self.gross_profit: Decimal = Decimal("0.00")
        self.gross_loss: Decimal = Decimal("0.00")
        self.win_count: int = 0
        self.loss_count: int = 0
        # Audit 2.9: breakeven closes (realized_pnl == 0) are
        # closed trades too -- they enter closed_trades_count
        # but neither win_count nor loss_count, so the win rate
        # (wins / decided trades) is unchanged.
        self.breakeven_count: int = 0
        # Audit 3.7: lifetime fill count. trade_history is truncated to
        # the last 50 fills at save time, but the leaderboard's
        # total_trades must still describe the whole session, so the
        # count lives here next to win_count/loss_count.
        self.total_fills: int = 0
        self.fee_rate: Decimal = maker_taker_fee_rate

        self.current_market_price: Decimal = Decimal("0.00")
        self.peak_equity: Decimal = self.initial_cash
        self.max_drawdown_pct: Decimal = Decimal("0.00")

        self.trade_history: List[FillEvent] = []
        self.equity_history: List[Tuple[float, Decimal]] = _SliceableDeque(maxlen=2000)  # type: ignore[assignment]
        self._equity_floats: deque[float] = deque(maxlen=2000)
        # Audit §5.5: version of the equity history, bumped whenever the
        # history is wholesale replaced (reset/restore). The leaderboard
        # Sharpe/Sortino cache keys on it, so a stale cache can never
        # survive a reset or a restore that reuses the same fill counts.
        self._equity_history_version: int = 0
        self.is_circuit_breaker_tripped: bool = False

    @property
    def max_drawdown(self) -> Decimal:
        return self.max_drawdown_pct

    @max_drawdown.setter
    def max_drawdown(self, value: Decimal) -> None:
        self.max_drawdown_pct = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def unrealized_pnl(self) -> Decimal:
        if self.position_qty <= _ZERO or self.current_market_price <= _ZERO:
            return _ZERO_CASH
        if self.position_side == PositionSide.SHORT:
            return ((self.avg_entry_price - self.current_market_price) * self.position_qty).quantize(
                PRECISION_CASH, rounding=ROUND_HALF_UP
            )
        return ((self.current_market_price - self.avg_entry_price) * self.position_qty).quantize(
            PRECISION_CASH, rounding=ROUND_HALF_UP
        )

    @property
    def total_equity(self) -> Decimal:
        if self.position_qty <= _ZERO:
            return self.cash
        if self.current_market_price <= _ZERO:
            return (self.cash + self.margin_locked).quantize(
                PRECISION_CASH, rounding=ROUND_HALF_UP
            )
        return (self.cash + self.margin_locked + self.unrealized_pnl).quantize(
            PRECISION_CASH, rounding=ROUND_HALF_UP
        )

    @property
    def roi_pct(self) -> Decimal:
        if self.initial_cash <= Decimal("0"):
            return Decimal("0.00")
        return (((self.total_equity - self.initial_cash) / self.initial_cash) * Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    @property
    def closed_trades_count(self) -> int:
        return self.win_count + self.loss_count + self.breakeven_count

    @property
    def profit_factor(self) -> float:
        if self.gross_loss <= Decimal("0"):
            return 99.99 if self.gross_profit > Decimal("0") else 0.0
        return round(float(self.gross_profit / self.gross_loss), 2)

    def reset(self, initial_cash: Optional[Decimal] = None) -> None:
        """
        Completely resets the portfolio to its initial flat state, clearing all
        positions, locked margin, entry fees, realized PnL, trade history, and drawdowns.
        """
        if initial_cash is not None:
            self.initial_cash = initial_cash.quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
            self.cash = self.initial_cash
        else:
            self.cash = self.initial_cash

        self.position_qty = Decimal("0.0000")
        self.position_side = PositionSide.FLAT
        self.avg_entry_price = Decimal("0.00")
        self.open_position_entry_fee = Decimal("0.00")
        self.margin_locked = Decimal("0.00")

        self.realized_pnl = Decimal("0.00")
        self.total_fees_paid = Decimal("0.00")
        self.gross_profit = Decimal("0.00")
        self.gross_loss = Decimal("0.00")
        self.win_count = 0
        self.loss_count = 0
        self.breakeven_count = 0
        self.total_fills = 0

        self.current_market_price = Decimal("0.00")
        self.peak_equity = self.cash
        self.max_drawdown_pct = Decimal("0.00")

        self.trade_history.clear()
        self.equity_history = _SliceableDeque(maxlen=2000)  # type: ignore[assignment]
        self._equity_floats.clear()
        # Audit §5.5: the counters are zeroed too, so without a version
        # bump the leaderboard cache key would collide with the
        # pre-reset one and serve stale metrics for the new history.
        self._equity_history_version += 1
        self.is_circuit_breaker_tripped = False

    def replace_equity_history(self, points: List[Tuple[float, Decimal]]) -> None:
        """Wholesale-replace the equity history (snapshot restore path).

        Audit §5.5: bumps the history version so the leaderboard
        Sharpe/Sortino cache invalidates even though no fill happened
        and the fill counters are unchanged.
        """
        trimmed = list(points)[-2000:]
        self.equity_history = _SliceableDeque(trimmed, maxlen=2000)  # type: ignore[assignment]
        self._equity_floats = deque((float(eq) for _, eq in trimmed), maxlen=2000)
        self._equity_history_version += 1

    def update_market_price(
        self,
        price: Decimal,
        timestamp: Optional[float] = None,
        low_price: Optional[Decimal] = None,
        high_price: Optional[Decimal] = None
    ) -> None:
        if not price.is_finite() or price <= _ZERO:
            return
        px = price.quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
        self.current_market_price = px

        # Evaluate intra-bar peak & trough (base_eq and *_upnl are both 2dp PRECISION_CASH)
        if self.position_qty > _ZERO:
            base_eq = self.cash + self.margin_locked
            qty = self.position_qty
            entry = self.avg_entry_price
            low_ok = low_price if (low_price is not None and low_price.is_finite() and low_price > _ZERO) else None
            high_ok = high_price if (high_price is not None and high_price.is_finite() and high_price > _ZERO) else None

            if self.position_side == PositionSide.SHORT:
                # For SHORT positions: lower price is favorable (peak), higher price is adverse (drawdown)
                if low_ok is not None and low_ok != px:
                    peak_upnl = ((entry - low_ok) * qty).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                    peak_eq = base_eq + peak_upnl
                    if peak_eq > self.peak_equity:
                        self.peak_equity = peak_eq
                if high_ok is not None and high_ok != px and self.peak_equity > _ZERO:
                    trough_upnl = ((entry - high_ok) * qty).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                    trough_eq = base_eq + trough_upnl
                    if trough_eq < self.peak_equity:
                        intra_dd = ((self.peak_equity - trough_eq) / self.peak_equity) * _HUNDRED
                        if intra_dd > self.max_drawdown_pct:
                            self.max_drawdown_pct = intra_dd.quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                close_upnl = ((entry - px) * qty).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
            else:
                # For LONG positions: higher price is favorable (peak), lower price is adverse (drawdown)
                if high_ok is not None and high_ok != px:
                    high_upnl = ((high_ok - entry) * qty).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                    high_eq = base_eq + high_upnl
                    if high_eq > self.peak_equity:
                        self.peak_equity = high_eq
                if low_ok is not None and low_ok != px and self.peak_equity > _ZERO:
                    low_upnl = ((low_ok - entry) * qty).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                    low_eq = base_eq + low_upnl
                    if low_eq < self.peak_equity:
                        intra_dd = ((self.peak_equity - low_eq) / self.peak_equity) * _HUNDRED
                        if intra_dd > self.max_drawdown_pct:
                            self.max_drawdown_pct = intra_dd.quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                close_upnl = ((px - entry) * qty).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)

            current_eq = base_eq + close_upnl
        else:
            current_eq = self.cash

        if current_eq > self.peak_equity:
            self.peak_equity = current_eq
        elif current_eq < self.peak_equity and self.peak_equity > _ZERO:
            dd = ((self.peak_equity - current_eq) / self.peak_equity) * _HUNDRED
            if dd > self.max_drawdown_pct:
                self.max_drawdown_pct = dd.quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)

        ts = timestamp if timestamp is not None else time.time()
        hist = self.equity_history
        eq_f = float(current_eq)
        if hist and hist[-1][0] == ts:
            hist[-1] = (ts, current_eq)
            if isinstance(hist, _SliceableDeque) and len(self._equity_floats) == len(hist):
                self._equity_floats[-1] = eq_f
        else:
            hist.append((ts, current_eq))
            if isinstance(hist, _SliceableDeque):
                if len(self._equity_floats) == len(hist) - 1 or len(self._equity_floats) == 2000:
                    self._equity_floats.append(eq_f)
                else:
                    self._equity_floats = deque((float(e) for _, e in hist), maxlen=2000)
            elif len(hist) > 2000:
                del hist[:-2000]

    def apply_fill(self, fill: FillEvent) -> FillEvent:
        """
        Applies a trade execution fill with exact Decimal accounting.
        Supports bidirectional LONG and SHORT positions.
        """
        if not fill.qty.is_finite() or fill.qty <= _ZERO:
            raise ValueError(f"Invalid fill qty in {self.portfolio_id}: {fill.qty}")
        if not fill.price.is_finite() or fill.price <= _ZERO:
            raise ValueError(f"Invalid fill price in {self.portfolio_id}: {fill.price}")
        if not fill.fee.is_finite() or fill.fee < _ZERO:
            raise ValueError(f"Invalid fill fee in {self.portfolio_id}: {fill.fee}")

        qty_q = fill.qty.quantize(PRECISION_CRYPTO, rounding=ROUND_HALF_UP)
        if qty_q <= _ZERO:
            raise ValueError(f"Invalid quantized fill qty in {self.portfolio_id}: {fill.qty}")
        price_q = fill.price.quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
        if price_q <= _ZERO:
            raise ValueError(f"Invalid quantized fill price in {self.portfolio_id}: {fill.price}")
        fee_q = fill.fee.quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
        trade_val = (qty_q * price_q).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
        eff_lev = self.leverage if self.leverage_enabled and self.leverage > _ZERO else _ONE
        enriched_fill = replace(fill, qty=qty_q, price=price_q, fee=fee_q)

        # Case 1: Currently FLAT -> Open a new position (BUY opens LONG, SELL opens SHORT)
        if self.position_side == PositionSide.FLAT or self.position_qty == _ZERO:
            required_margin = (trade_val / eff_lev).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
            total_initial_cost = (required_margin + fee_q).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
            if total_initial_cost > self.cash:
                raise ValueError(f"Insufficient cash in {self.portfolio_id}: need {total_initial_cost}, have {self.cash}")

            self.position_side = PositionSide.LONG if fill.side == OrderSide.BUY else PositionSide.SHORT
            self.position_qty = qty_q
            self.avg_entry_price = price_q
            self.open_position_entry_fee = fee_q
            self.margin_locked = required_margin
            self.cash = (self.cash - total_initial_cost).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
            enriched_fill = replace(enriched_fill, position_side=self.position_side)

        # Case 2: Currently LONG
        elif self.position_side == PositionSide.LONG:
            if fill.side == OrderSide.BUY:
                # Add to LONG
                required_margin = (trade_val / eff_lev).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                total_initial_cost = (required_margin + fee_q).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                if total_initial_cost > self.cash:
                    raise ValueError(f"Insufficient cash in {self.portfolio_id}: need {total_initial_cost}, have {self.cash}")
                new_qty = (self.position_qty + qty_q).quantize(PRECISION_CRYPTO, rounding=ROUND_HALF_UP)
                if new_qty <= _ZERO:
                    raise ValueError(f"Invalid resulting qty in {self.portfolio_id}: {new_qty}")
                new_avg = ((self.position_qty * self.avg_entry_price) + trade_val) / new_qty
                self.avg_entry_price = new_avg.quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                self.position_qty = new_qty
                self.open_position_entry_fee += fee_q
                self.margin_locked += required_margin
                self.cash = (self.cash - total_initial_cost).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                enriched_fill = replace(enriched_fill, position_side=PositionSide.LONG)
            else:
                # SELL closes/reduces LONG
                if qty_q > self.position_qty:
                    raise ValueError(f"Overselling in {self.portfolio_id}: selling {qty_q}, hold {self.position_qty}")
                remaining_qty = (self.position_qty - qty_q).quantize(PRECISION_CRYPTO, rounding=ROUND_HALF_UP)
                is_full_close = qty_q >= self.position_qty or remaining_qty <= _ZERO
                if is_full_close:
                    entry_fee_share = self.open_position_entry_fee
                    margin_release = self.margin_locked
                    new_margin_locked = _ZERO_CASH
                    remaining_qty = _ZERO_QTY
                else:
                    close_ratio = qty_q / self.position_qty
                    entry_fee_share = (self.open_position_entry_fee * close_ratio).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                    margin_release = min(
                        self.margin_locked,
                        (self.margin_locked * close_ratio).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP),
                    )
                    new_margin_locked = (self.margin_locked - margin_release).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)

                closing_entry_price = self.avg_entry_price
                gross_gain = ((price_q - closing_entry_price) * qty_q).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                pnl = (gross_gain - fee_q - entry_fee_share).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                self.realized_pnl += pnl
                enriched_fill = enriched_fill.with_realized_pnl(pnl, entry_price=closing_entry_price)
                enriched_fill = replace(enriched_fill, position_side=PositionSide.LONG)

                if pnl > _ZERO:
                    self.win_count += 1
                    self.gross_profit += pnl
                elif pnl < _ZERO:
                    self.loss_count += 1
                    self.gross_loss += abs(pnl)
                else:
                    self.breakeven_count += 1

                self.margin_locked = new_margin_locked
                self.position_qty = remaining_qty
                cash_settlement = (margin_release + gross_gain - fee_q).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                self.cash = (self.cash + cash_settlement).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                self.open_position_entry_fee = max(_ZERO_CASH, self.open_position_entry_fee - entry_fee_share)

                if self.position_qty == _ZERO:
                    self.position_side = PositionSide.FLAT
                    self.avg_entry_price = _ZERO_CASH
                    self.open_position_entry_fee = _ZERO_CASH
                    self.margin_locked = _ZERO_CASH

        # Case 3: Currently SHORT
        elif self.position_side == PositionSide.SHORT:
            if fill.side == OrderSide.SELL:
                # Add to SHORT
                required_margin = (trade_val / eff_lev).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                total_initial_cost = (required_margin + fee_q).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                if total_initial_cost > self.cash:
                    raise ValueError(f"Insufficient cash in {self.portfolio_id}: need {total_initial_cost}, have {self.cash}")
                new_qty = (self.position_qty + qty_q).quantize(PRECISION_CRYPTO, rounding=ROUND_HALF_UP)
                if new_qty <= _ZERO:
                    raise ValueError(f"Invalid resulting qty in {self.portfolio_id}: {new_qty}")
                new_avg = ((self.position_qty * self.avg_entry_price) + trade_val) / new_qty
                self.avg_entry_price = new_avg.quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                self.position_qty = new_qty
                self.open_position_entry_fee += fee_q
                self.margin_locked += required_margin
                self.cash = (self.cash - total_initial_cost).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                enriched_fill = replace(enriched_fill, position_side=PositionSide.SHORT)
            else:
                # BUY closes/covers SHORT
                if qty_q > self.position_qty:
                    raise ValueError(f"Overcovering short in {self.portfolio_id}: buying {qty_q}, short {self.position_qty}")
                remaining_qty = (self.position_qty - qty_q).quantize(PRECISION_CRYPTO, rounding=ROUND_HALF_UP)
                is_full_close = qty_q >= self.position_qty or remaining_qty <= _ZERO
                if is_full_close:
                    entry_fee_share = self.open_position_entry_fee
                    margin_release = self.margin_locked
                    new_margin_locked = _ZERO_CASH
                    remaining_qty = _ZERO_QTY
                else:
                    close_ratio = qty_q / self.position_qty
                    entry_fee_share = (self.open_position_entry_fee * close_ratio).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                    margin_release = min(
                        self.margin_locked,
                        (self.margin_locked * close_ratio).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP),
                    )
                    new_margin_locked = (self.margin_locked - margin_release).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)

                closing_entry_price = self.avg_entry_price
                # For SHORT: profit is (entry_price - exit_price) * qty
                gross_gain = ((closing_entry_price - price_q) * qty_q).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                pnl = (gross_gain - fee_q - entry_fee_share).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                self.realized_pnl += pnl
                enriched_fill = enriched_fill.with_realized_pnl(pnl, entry_price=closing_entry_price)
                enriched_fill = replace(enriched_fill, position_side=PositionSide.SHORT)

                if pnl > _ZERO:
                    self.win_count += 1
                    self.gross_profit += pnl
                elif pnl < _ZERO:
                    self.loss_count += 1
                    self.gross_loss += abs(pnl)
                else:
                    self.breakeven_count += 1

                self.margin_locked = new_margin_locked
                self.position_qty = remaining_qty
                cash_settlement = (margin_release + gross_gain - fee_q).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                self.cash = (self.cash + cash_settlement).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                self.open_position_entry_fee = max(_ZERO_CASH, self.open_position_entry_fee - entry_fee_share)

                if self.position_qty == _ZERO:
                    self.position_side = PositionSide.FLAT
                    self.avg_entry_price = _ZERO_CASH
                    self.open_position_entry_fee = _ZERO_CASH
                    self.margin_locked = _ZERO_CASH

        self.total_fees_paid = (self.total_fees_paid + fee_q).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
        self.total_fills += 1
        self.trade_history.append(enriched_fill)
        if len(self.trade_history) > 2000:
            del self.trade_history[:-2000]
        self.update_market_price(price_q, fill.timestamp)
        return enriched_fill
