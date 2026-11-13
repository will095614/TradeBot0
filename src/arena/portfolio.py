from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional, Tuple
import time
from dataclasses import replace
from src.arena.order import FillEvent, OrderSide, PositionSide

PRECISION_CASH = Decimal("0.01")
PRECISION_CRYPTO = Decimal("0.0001")


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
        self.fee_rate: Decimal = maker_taker_fee_rate

        self.current_market_price: Decimal = Decimal("0.00")
        self.peak_equity: Decimal = self.initial_cash
        self.max_drawdown_pct: Decimal = Decimal("0.00")

        self.trade_history: List[FillEvent] = []
        self.equity_history: List[Tuple[float, Decimal]] = []
        self.is_circuit_breaker_tripped: bool = False

    @property
    def max_drawdown(self) -> Decimal:
        return self.max_drawdown_pct

    @max_drawdown.setter
    def max_drawdown(self, value: Decimal) -> None:
        self.max_drawdown_pct = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def unrealized_pnl(self) -> Decimal:
        if self.position_qty <= Decimal("0") or self.current_market_price <= Decimal("0"):
            return Decimal("0.00")
        if self.position_side == PositionSide.SHORT:
            return ((self.avg_entry_price - self.current_market_price) * self.position_qty).quantize(
                PRECISION_CASH, rounding=ROUND_HALF_UP
            )
        return ((self.current_market_price - self.avg_entry_price) * self.position_qty).quantize(
            PRECISION_CASH, rounding=ROUND_HALF_UP
        )

    @property
    def total_equity(self) -> Decimal:
        if self.position_qty <= Decimal("0") or self.current_market_price <= Decimal("0"):
            return self.cash
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
        return self.win_count + self.loss_count

    @property
    def profit_factor(self) -> float:
        if self.gross_loss <= Decimal("0"):
            return float(self.gross_profit) if self.gross_profit > Decimal("0") else 0.0
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

        self.current_market_price = Decimal("0.00")
        self.peak_equity = self.cash
        self.max_drawdown_pct = Decimal("0.00")

        self.trade_history.clear()
        self.equity_history.clear()
        self.is_circuit_breaker_tripped = False

    def update_market_price(
        self,
        price: Decimal,
        timestamp: Optional[float] = None,
        low_price: Optional[Decimal] = None,
        high_price: Optional[Decimal] = None
    ) -> None:
        self.current_market_price = price.quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)

        # Evaluate intra-bar peak & trough
        if self.position_qty > Decimal("0"):
            if self.position_side == PositionSide.SHORT:
                # For SHORT positions: lower price is favorable (peak), higher price is adverse (drawdown)
                if low_price is not None:
                    peak_upnl = ((self.avg_entry_price - low_price) * self.position_qty).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                    peak_eq = (self.cash + self.margin_locked + peak_upnl).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                    if peak_eq > self.peak_equity:
                        self.peak_equity = peak_eq
                if high_price is not None and self.peak_equity > Decimal("0"):
                    trough_upnl = ((self.avg_entry_price - high_price) * self.position_qty).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                    trough_eq = (self.cash + self.margin_locked + trough_upnl).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                    intra_dd = ((self.peak_equity - trough_eq) / self.peak_equity) * Decimal("100")
                    if intra_dd > self.max_drawdown_pct:
                        self.max_drawdown_pct = intra_dd.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            else:
                # For LONG positions: higher price is favorable (peak), lower price is adverse (drawdown)
                if high_price is not None:
                    high_upnl = ((high_price - self.avg_entry_price) * self.position_qty).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                    high_eq = (self.cash + self.margin_locked + high_upnl).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                    if high_eq > self.peak_equity:
                        self.peak_equity = high_eq
                if low_price is not None and self.peak_equity > Decimal("0"):
                    low_upnl = ((low_price - self.avg_entry_price) * self.position_qty).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                    low_eq = (self.cash + self.margin_locked + low_upnl).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                    intra_dd = ((self.peak_equity - low_eq) / self.peak_equity) * Decimal("100")
                    if intra_dd > self.max_drawdown_pct:
                        self.max_drawdown_pct = intra_dd.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        current_eq = self.total_equity
        if current_eq > self.peak_equity:
            self.peak_equity = current_eq

        if self.peak_equity > Decimal("0"):
            dd = ((self.peak_equity - current_eq) / self.peak_equity) * Decimal("100")
            if dd > self.max_drawdown_pct:
                self.max_drawdown_pct = dd.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        ts = timestamp if timestamp is not None else time.time()
        if self.equity_history and self.equity_history[-1][0] == ts:
            self.equity_history[-1] = (ts, current_eq)
        else:
            self.equity_history.append((ts, current_eq))
            if len(self.equity_history) > 2000:
                self.equity_history = self.equity_history[-2000:]

    def apply_fill(self, fill: FillEvent) -> FillEvent:
        """
        Applies a trade execution fill with exact Decimal accounting.
        Supports bidirectional LONG and SHORT positions.
        """
        fee_q = fill.fee.quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
        self.total_fees_paid = (self.total_fees_paid + fee_q).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
        trade_val = (fill.qty * fill.price).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
        eff_lev = self.leverage if self.leverage_enabled and self.leverage > Decimal("0") else Decimal("1.0")
        enriched_fill = fill

        # Case 1: Currently FLAT -> Open a new position (BUY opens LONG, SELL opens SHORT)
        if self.position_side == PositionSide.FLAT or self.position_qty == Decimal("0"):
            required_margin = (trade_val / eff_lev).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
            total_initial_cost = (required_margin + fee_q).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
            if total_initial_cost > self.cash:
                raise ValueError(f"Insufficient cash in {self.portfolio_id}: need {total_initial_cost}, have {self.cash}")

            self.position_side = PositionSide.LONG if fill.side == OrderSide.BUY else PositionSide.SHORT
            self.position_qty = fill.qty
            self.avg_entry_price = fill.price
            self.open_position_entry_fee = fee_q
            self.margin_locked = required_margin
            self.cash = (self.cash - total_initial_cost).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
            enriched_fill = replace(fill, position_side=self.position_side)

        # Case 2: Currently LONG
        elif self.position_side == PositionSide.LONG:
            if fill.side == OrderSide.BUY:
                # Add to LONG
                required_margin = (trade_val / eff_lev).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                total_initial_cost = (required_margin + fee_q).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                if total_initial_cost > self.cash:
                    raise ValueError(f"Insufficient cash in {self.portfolio_id}: need {total_initial_cost}, have {self.cash}")
                new_qty = (self.position_qty + fill.qty).quantize(PRECISION_CRYPTO, rounding=ROUND_HALF_UP)
                new_avg = ((self.position_qty * self.avg_entry_price) + trade_val) / new_qty
                self.avg_entry_price = new_avg.quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                self.position_qty = new_qty
                self.open_position_entry_fee += fee_q
                self.margin_locked += required_margin
                self.cash = (self.cash - total_initial_cost).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                enriched_fill = replace(fill, position_side=PositionSide.LONG)
            else:
                # SELL closes/reduces LONG
                if fill.qty > self.position_qty:
                    raise ValueError(f"Overselling in {self.portfolio_id}: selling {fill.qty}, hold {self.position_qty}")
                entry_fee_share = (self.open_position_entry_fee * (fill.qty / self.position_qty)).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                closing_entry_price = self.avg_entry_price
                gross_gain = ((fill.price - closing_entry_price) * fill.qty).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                pnl = (gross_gain - fee_q - entry_fee_share).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                self.realized_pnl += pnl
                enriched_fill = fill.with_realized_pnl(pnl, entry_price=closing_entry_price)
                enriched_fill = replace(enriched_fill, position_side=PositionSide.LONG)

                if pnl > Decimal("0"):
                    self.win_count += 1
                    self.gross_profit += pnl
                elif pnl < Decimal("0"):
                    self.loss_count += 1
                    self.gross_loss += abs(pnl)

                cost_basis = (fill.qty * self.avg_entry_price).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                margin_release = (cost_basis / eff_lev).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                if fill.qty >= self.position_qty:
                    margin_release = self.margin_locked
                    self.margin_locked = Decimal("0.00")
                else:
                    self.margin_locked = max(Decimal("0.00"), (self.margin_locked - margin_release).quantize(PRECISION_CASH))

                self.position_qty = (self.position_qty - fill.qty).quantize(PRECISION_CRYPTO, rounding=ROUND_HALF_UP)
                cash_settlement = (margin_release + gross_gain - fee_q).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                self.cash = (self.cash + cash_settlement).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                self.open_position_entry_fee = max(Decimal("0.00"), self.open_position_entry_fee - entry_fee_share)

                if self.position_qty == Decimal("0"):
                    self.position_side = PositionSide.FLAT
                    self.avg_entry_price = Decimal("0.00")
                    self.open_position_entry_fee = Decimal("0.00")
                    self.margin_locked = Decimal("0.00")

        # Case 3: Currently SHORT
        elif self.position_side == PositionSide.SHORT:
            if fill.side == OrderSide.SELL:
                # Add to SHORT
                required_margin = (trade_val / eff_lev).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                total_initial_cost = (required_margin + fee_q).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                if total_initial_cost > self.cash:
                    raise ValueError(f"Insufficient cash in {self.portfolio_id}: need {total_initial_cost}, have {self.cash}")
                new_qty = (self.position_qty + fill.qty).quantize(PRECISION_CRYPTO, rounding=ROUND_HALF_UP)
                new_avg = ((self.position_qty * self.avg_entry_price) + trade_val) / new_qty
                self.avg_entry_price = new_avg.quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                self.position_qty = new_qty
                self.open_position_entry_fee += fee_q
                self.margin_locked += required_margin
                self.cash = (self.cash - total_initial_cost).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                enriched_fill = replace(fill, position_side=PositionSide.SHORT)
            else:
                # BUY closes/covers SHORT
                if fill.qty > self.position_qty:
                    raise ValueError(f"Overcovering short in {self.portfolio_id}: buying {fill.qty}, short {self.position_qty}")
                entry_fee_share = (self.open_position_entry_fee * (fill.qty / self.position_qty)).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                closing_entry_price = self.avg_entry_price
                # For SHORT: profit is (entry_price - exit_price) * qty
                gross_gain = ((closing_entry_price - fill.price) * fill.qty).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                pnl = (gross_gain - fee_q - entry_fee_share).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                self.realized_pnl += pnl
                enriched_fill = fill.with_realized_pnl(pnl, entry_price=closing_entry_price)
                enriched_fill = replace(enriched_fill, position_side=PositionSide.SHORT)

                if pnl > Decimal("0"):
                    self.win_count += 1
                    self.gross_profit += pnl
                elif pnl < Decimal("0"):
                    self.loss_count += 1
                    self.gross_loss += abs(pnl)

                cost_basis = (fill.qty * self.avg_entry_price).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                margin_release = (cost_basis / eff_lev).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                if fill.qty >= self.position_qty:
                    margin_release = self.margin_locked
                    self.margin_locked = Decimal("0.00")
                else:
                    self.margin_locked = max(Decimal("0.00"), (self.margin_locked - margin_release).quantize(PRECISION_CASH))

                self.position_qty = (self.position_qty - fill.qty).quantize(PRECISION_CRYPTO, rounding=ROUND_HALF_UP)
                cash_settlement = (margin_release + gross_gain - fee_q).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                self.cash = (self.cash + cash_settlement).quantize(PRECISION_CASH, rounding=ROUND_HALF_UP)
                self.open_position_entry_fee = max(Decimal("0.00"), self.open_position_entry_fee - entry_fee_share)

                if self.position_qty == Decimal("0"):
                    self.position_side = PositionSide.FLAT
                    self.avg_entry_price = Decimal("0.00")
                    self.open_position_entry_fee = Decimal("0.00")
                    self.margin_locked = Decimal("0.00")

        self.trade_history.append(enriched_fill)
        self.update_market_price(fill.price, fill.timestamp)
        return enriched_fill
