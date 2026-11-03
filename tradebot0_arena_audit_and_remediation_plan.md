# TradeBot0 Arena — Verification Report & Remediation Plan

This document contains the complete findings from the read-only verification audit of `TradeBot0_Arena` (`v2.0.0`), organized into an actionable task list for the next engineering pass followed by the full verbatim audit report for context.

---

## Part 1: Actionable Task List for the Programming Agent

### Do Not Break (Verified Green Baseline)
Before and after making changes, ensure the following verified guarantees remain intact:
- **Test Suite:** `pytest -q` passes all 28+ tests with exit code `0`.
- **Hermeticity:** `memory/arena_history.json` MD5 checksum must remain identical before and after running `pytest`.
- **Packaging & Self-Test:** `TradeBot0_Arena.spec` and `build_exe.ps1` correctly bundle `src/gui/assets` into `sys._MEIPASS / "src" / "gui" / "assets"`, and `dist/TradeBot0_Arena.exe --self-test` exits `0`.
- **Splash Screen State Gate (`src/gui/assets/app.js:249-253`):** Keep the real state check (`latestState.quote.price > 0` and `latestState.candles.length >= 2`), while adding the offline/timeout fallback detailed below.

---

### Priority 1: Core Safety, Correctness & Performance Fixes

- [ ] **1. Stop Trading on Hardcoded Offline Fallback Price (`src/data/live_engine.py:288-295`)**
  - **Current Bug:** When all three exchanges fail, the quote fetcher returns `Decimal("2250.00")` with `source="Offline Default"`, and the engine continues executing and filling trades against `2250.00` indefinitely.
  - **Required Fix:** Do not allow the engine to execute or fill trades against a hardcoded fallback price when all exchange feeds fail. Explicitly mark the feed/quote state as offline/stale, block order execution/fills while offline, and surface the offline status to the UI.

- [ ] **2. Fix Splash Screen Infinite Hang on Feed/History Failure (`src/gui/assets/app.js:249-253`)**
  - **Current Bug:** There is no failure path on the splash screen. If the history/candle fetch fails, or if the price feed is offline, progress pins at `85%` (or earlier once hardcoded `2250` price is removed) and the overlay never fades—leaving an unkillable loading screen with no error text.
  - **Required Fix:** Add a 10-second timeout to the splash screen initialization. If live quotes and candles have not completed loading within 10 seconds (or if the backend reports an offline feed), fade the splash overlay and display a clear UI status banner: `"Offline — price feed unavailable"`.

- [ ] **3. Implement Real Logging & Replace Silent Exception Swallowing (`src/gui/dashboard.py:12` & across codebase)**
  - **Current Bug:** There are 11 `except Exception:` blocks and 7 bare `pass` statements across the codebase. `src/gui/dashboard.py:12` defines `logger = logging.getLogger(__name__)`, but there is no `basicConfig`, no handler configured, and `logger` is never called (making it a dead import).
  - **Required Fix:** Configure standard logging (e.g., `logging.basicConfig` or a rotating file/stream handler), wire up `logger` in `dashboard.py` and `live_engine.py`, and replace bare `pass` / silent `except Exception:` blocks with appropriate `logger.warning(...)` or `logger.debug(..., exc_info=True)` calls so runtime errors are observable.

- [ ] **4. Remove Dead Equity Curve Accumulation (`src/data/live_engine.py:796-802` and all write sites)**
  - **Current Bug:** Per Plan §2.1, the dead equity curve was supposed to be removed. However, `src/data/live_engine.py:796-802` still appends `equity_ts` and six `equity_series` lists on every tick and re-slices them at 3,000 points. Across the codebase, `grep` shows **8 references—all writes and zero readers**.
  - **Required Fix:** Remove all 8 write-only references to `equity_ts` and `equity_series` so the engine stops allocating and slicing unused lists every tick.

- [ ] **5. Release Engine Lock Before Disk I/O in `evolve_now` (`src/data/live_engine.py:911-912`)**
  - **Current Bug:** `evolve_now` acquires `self.lock` and then calls `GeneticEvolver.evolve_generation`, which writes the ~621 KB history file to disk while still holding `self.lock`. Because `get_ui_state` requires `self.lock`, the entire UI stalls during evolution.
  - **Required Fix:** Refactor `evolve_now` / `GeneticEvolver.evolve_generation` so that in-memory state updates or snapshots happen minimally under `self.lock`, and the 621 KB JSON serialization + disk persistence happens **outside** `self.lock` (using atomic write via a temp file if needed).

---

### Priority 2: Polling, Timeouts, Config Hygiene & Verification

- [ ] **6. Address Worst-Case Sequential Quote Fallback Latency (`src/data/live_engine.py`)**
  - **Current Issue:** Sequential quote fallback timeouts sum to $1.8 + 2.0 + 1.8 + 1.8 = 7.4\text{ s}$ worst case against a $1.5\text{ s}$ engine tick.
  - **Required Fix:** Reduce per-provider timeouts, query fallbacks concurrently, or circuit-break failing providers briefly so a network outage does not stall the tick loop for $7.4\text{ s}$ every cycle.

- [ ] **7. Gate Frontend Polling on `document.hidden` (`src/gui/assets/app.js`)**
  - **Current Issue:** `setInterval(pollBackend, 1000)` runs unconditionally without checking `document.hidden`.
  - **Required Fix:** Check `if (document.hidden) return;` inside the interval callback (and optionally trigger an immediate poll on `visibilitychange` when the window becomes visible again).

- [ ] **8. Clean Up Stale `pytest.ini` Setting (`pytest.ini`)**
  - **Current Issue:** `pytest.ini` still sets `asyncio_default_fixture_loop_scope` even though `pytest-asyncio` was removed.
  - **Required Fix:** Remove `asyncio_default_fixture_loop_scope` from `pytest.ini` so pytest does not emit unknown-config warnings.

- [ ] **9. Amend Documentation & Perform Live GUI Verification**
  - **Payload Size Gate Doc:** Update the documentation/plan note on the UI payload gate from `< 15 KB` to `< 35 KB` (steady-state payload is `32,983 B`, down $-91\%$ from `361 KB`, and the remaining heavy keys—`fills` at `14,129 B`, `candles` at `9,189 B`, and `strategies` at `4,139 B`—are all actively rendered). Do **not** strip needed UI data just to hit the old arbitrary 15 KB text.
  - **SmartScreen Note:** Document in `README.md` / release notes that `dist/TradeBot0_Arena.exe` is an unsigned binary and will trigger a standard Windows SmartScreen prompt on first launch on another machine.
  - **GUI Smoke Test:** Run the actual `pywebview` GUI (not just `--self-test`) to verify that `index.html`, `app.css`, `app.js`, charts, and splash transitions render and operate cleanly without console errors.

---

## Part 2: Complete Verbatim Audit Report

> **Context:** Read-only verification pass; nothing modified. Everything was re-verified, including running the test suite and the shipped executable.

### 1. Correction on Splash Screen & Packaging
In the previous review, it was stated that the splash "hits 100% even if no candle ever loaded" and had "no connection to the backend." **That was wrong.** Only the first 130 lines of `app.js` had been read without opening the poll handler. `src/gui/assets/app.js:249-253` does gate on real state:

```js
if (!splashCompleted) {
  if (latestState && latestState.quote && latestState.quote.price > 0 && latestState.candles && latestState.candles.length >= 2) {
    updateSplashProgress(100);
  } else if (latestState && latestState.quote && latestState.quote.price > 0) {
    updateSplashProgress(85);
  }
}
```

So the overlay genuinely waits for a live quote **and** at least two candles before fading. The packaging also properly includes the assets and does not ship a blank window.

### 2. What Is Verified Green

Executed checks and results:

| Check | Result |
|---|---|
| `pytest -q` | **28 passed in 2.67 s**, exit 0 |
| Hermeticity | `memory/arena_history.json` md5 **identical** before/after the run — isolation genuinely works |
| `dist/TradeBot0_Arena.exe --self-test` | **exit 0 in 3 s** |
| Assets inside the exe | present in the archive at `src\gui\assets\app.css` (34,620 B), `app.js` (63,861 B), `index.html` (13,147 B) |
| Git state | 5 commits, tag `v2.0.0`, clean tree, 61 tracked files |
| `.gitignore` | correctly ignores `dist/`, `build/`, `.venv/`, `memory/*.json`; assets are tracked |

Both build configs were fixed properly — `TradeBot0_Arena.spec` has `datas = [('src/gui/assets', 'src/gui/assets')]` and `build_exe.ps1` has `--add-data "src/gui/assets;src/gui/assets"`. The path matches `_get_assets_dir()`'s `sys._MEIPASS / "src" / "gui" / "assets"` exactly. The 54 MB single-file exe is real and it runs.

The P0 correctness work that *was* done is also genuinely tested, not eyeballed — `test_startup_ev_gate_enforcement` mocks a failing `MonteCarloBracketOdds` and asserts every competitor ends flat with an `"EV Gate Blocked"` intent. Same for `test_portfolio_breakeven_trade_does_not_count_as_loss`. And `stop_live_loop` now joins with a 3.0 s timeout (`src/data/live_engine.py:815`).

### 3. The One Claim That Didn't Hold: The 15 KB Gate

Measured payload at steady state (6 ticks, engine running):

```text
TOTAL: 32,983 B
  fills          14,129 B  (42.8%)
  candles         9,189 B  (27.9%)
  strategies      4,139 B  (12.5%)
  price_history   1,116 B   tv_hub 1,143 B   emas ~2.2 KB
```

**33 KB, not under 15 KB.** However, the reduction is real — $361\text{ KB} \rightarrow 33\text{ KB}$ is **$-91\%$**, and crucially the three remaining heavy keys are all actually rendered (fills table, candle chart, strategy cards). This is a gate whose stated number was wrong, not a code defect; amend the document line rather than stripping required data from the code.

### 4. Four Items From the Audit Still Untouched

1. **Still trades on a hardcoded price:** `src/data/live_engine.py:288-295` returns `Decimal("2250.00")` / `source="Offline Default"` when all three exchanges fail, and the engine will fill against it indefinitely. This is the top priority to fix next.
2. **Still zero logging:** 11 `except Exception:`, 7 bare `pass`. `src/gui/dashboard.py:12` now does `logger = logging.getLogger(__name__)` but there's no `basicConfig`, no handler, and `logger` is never used — so the only new artefact is a dead import.
3. **The dead equity curve is still being built:** The plan's own §2.1 said to stop maintaining it; `src/data/live_engine.py:796-802` still appends `equity_ts` + six `equity_series` lists every tick and re-slices them at 3,000 points. `grep` finds **8 references, all writes, zero readers**.
4. **`evolve_now` still holds the engine lock across disk I/O:** `src/data/live_engine.py:911-912` takes `self.lock`, then calls `GeneticEvolver.evolve_generation` which persists the 621 KB history. `get_ui_state` needs that same lock, so the whole UI stalls during Evolve.

**Also unchanged:**
- Sequential quote fallback of $1.8 + 2.0 + 1.8 + 1.8 = 7.4\text{ s}$ worst case against a $1.5\text{ s}$ tick.
- `setInterval(pollBackend, 1000)` with no `document.hidden` check.
- `pytest.ini` still sets `asyncio_default_fixture_loop_scope` after `pytest-asyncio` was removed.

### 5. Two Remaining Risks Worth Naming

- **The splash can strand the app:** There is no failure path. If the history fetch fails, progress pins at 85% and the overlay never fades — producing an unkillable loading screen with no error text. Since the offline path returns a `2250` price, `price > 0` is always true, sitting at 85% forever. A 10-second timeout that fades the overlay and shows `"Offline — price feed unavailable"` closes that hole.
- **Nobody has looked at the GUI:** `--self-test` proves imports, engine construction, and `json.dumps` succeed. It does not execute the splash, the charts, or a single line of `app.js`. Also, the exe is unsigned, so first launch on another machine triggers a Windows SmartScreen warning; that is expected and should be documented.

### 6. Verdict
Phases 1–5 landed accurately, the tree is clean, tests are real and hermetic, and the binary works. What remains are the four safety/correctness items above, a splash timeout, minor hygiene items, and a live `pywebview` GUI run.