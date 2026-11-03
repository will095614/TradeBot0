from __future__ import annotations
from dataclasses import dataclass, field, replace
from decimal import Decimal
from enum import Enum
from typing import Optional
import time
import uuid


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_MARKET = "STOP_MARKET"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class ExecutionReason(str, Enum):
    SIGNAL = "SIGNAL"
    SIGNAL_ENTRY = "SIGNAL_ENTRY"
    SIGNAL_EXIT = "SIGNAL_EXIT"
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    TRAILING_STOP = "TRAILING_STOP"
    CIRCUIT_BREAKER = "CIRCUIT_BREAKER"


@dataclass(frozen=True)
class OrderTicket:
    portfolio_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    qty: Decimal
    price: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    reason: ExecutionReason = ExecutionReason.SIGNAL
    order_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True)
class FillEvent:
    order_id: str
    portfolio_id: str
    symbol: str
    side: OrderSide
    qty: Decimal
    price: Decimal
    fee: Decimal
    timestamp: float
    realized_pnl: Decimal = Decimal("0.00")
    reason: ExecutionReason = ExecutionReason.SIGNAL
    fill_seq: int = 0
    entry_price: Optional[Decimal] = None

    def with_realized_pnl(self, pnl: Decimal, entry_price: Optional[Decimal] = None) -> FillEvent:
        return replace(self, realized_pnl=pnl, entry_price=entry_price if entry_price is not None else self.entry_price)

    def with_seq(self, seq: int) -> FillEvent:
        return replace(self, fill_seq=seq)

    @property
    def is_buy(self) -> bool:
        return self.side == OrderSide.BUY

    @property
    def is_sell(self) -> bool:
        return self.side == OrderSide.SELL
