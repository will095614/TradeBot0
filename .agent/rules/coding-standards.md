# Python & Financial Engineering Standards (TradeBot0)

Adopted from `affaan-m/ECC` engineering principles.

## 1. High-Precision Financial Math
- **NEVER use standard IEEE 754 `float` for cash balances, positions, or order sizes.**
  Always use Python's built-in `decimal.Decimal` with explicitly rounded quantizing (e.g. `Decimal('0.0001')` for crypto amounts, `Decimal('0.01')` for USD/USDT values).
- All calculations involving PnL, commissions, slippage, and fees MUST preserve exact arithmetic consistency.
- Avoid implicit float conversions: convert via strings, e.g., `Decimal(str(price))`.

## 2. Strong Typing & Documentation
- Use Python 3.12+ type annotations everywhere (`from typing import Optional, Dict, List, Tuple`).
- Use `@dataclass(frozen=True)` or Pydantic models for immutable event data, order tickets, and trade results.
- Every function and class must include clear docstrings explaining inputs, outputs, side effects, and error conditions.

## 3. Concurrency & Thread Safety
- The multi-portfolio simulated broker (`BrokerSim`) must process market ticks deterministically.
- All competitor portfolios execute against the identical price tick within the same event loop step.
- State mutation must be thread-safe when bridged to GUI rendering threads.

## 4. Defensive Exception Handling & Logging
- Never catch raw `Exception` silently without structured logging.
- Maintain an audit trail of every simulated order, cancellation, fill, and rejection in structured JSON.

