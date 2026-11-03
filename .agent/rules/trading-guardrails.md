# Trading Safety & Multi-Portfolio Guardrails

Adopted from `affaan-m/ECC/the-security-guide.md` & `Jakeschincariol/day-trader-skill/trader-risk`.

## 1. Dual Mode Operation
- **Paper Arena Mode (`mode="paper_arena"`)**:
  - Unblocked, zero manual confirmation delay.
  - Allows autonomous, millisecond-level execution for all competitor portfolios simultaneously.
  - Completely isolated from real exchange order endpoints.
- **Live Execution Mode (`mode="live"`)**:
  - HARD BLOCKED by default.
  - Requires explicit two-gate manual confirmation before any external API payload is dispatched.
  - Strictly requires valid API credentials stored in secure environment variables, never hardcoded in files.

## 2. Invariant Risk Limits (AgentShield)
- **Max Account Drawdown Circuit Breaker**: If any portfolio loses > 15% of initial equity within a single session, all its active orders are cancelled and trading is suspended for that portfolio until reset.
- **Max Position Size Cap**: No single order can exceed the specified competitor maximum budget (e.g. 70% for aggressive, 25% for conservative).
- **Sanity Checks**:
  - Price cannot be $\le 0$.
  - Quantity cannot be $\le 0$.
  - Total allocated margin cannot exceed available cash.

