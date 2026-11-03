# Test-Driven Development (TDD) Workflow

Adopted from `affaan-m/ECC/skills/tdd-workflow`.

## 1. Golden Rule
- **No strategy or engine logic change is complete without automated test verification.**
- Before adding a feature or fixing a calculation bug:
  1. Write a failing test in `tests/` reproducing the scenario.
  2. Implement the minimal clean code to make the test pass.
  3. Refactor with confidence, ensuring zero regressions across all existing tests.

## 2. Test Coverage Requirements
- **Financial Accounting**: Tests MUST verify exact balance updates, fee deductions (Maker/Taker fees), position sizes, and average entry prices.
- **Stop-Loss / Take-Profit Triggers**: Tests MUST simulate extreme price wicks (flash crashes, rapid surges) to verify stop triggers fire at or beyond the stop threshold.
- **Zero Look-Ahead Bias**: Historical simulation tests must assert that strategies only observe information available strictly up to the current tick $t$, never $t+1$.

