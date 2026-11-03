# TradeBot0 — Optimization Audit & Work Order

**Audience:** the next coding agent picking this up.
**Status:** audit only. **No source files were modified.** Every finding below was verified by reading the code, not guessed.
**Snapshot:** 2026-11-03, Windows, Python 3.12.8, `.venv` at project root.
**Line numbers are from this snapshot** and will drift once you start editing — search for the symbol, don't trust the number blindly.

---

## 0. TL;DR

The quantitative core is solid: `Decimal`-only accounting, correct intra-bar stop/target ordering, sensible risk guards. The problems are concentrated in three places:

1. **`LiveArenaEngine` ships ~380 KB of JSON to the UI every second, ~94% of which the front-end never reads.** This is the single biggest waste in the project and it also causes a thread race.
2. **`_evaluate_live_strategies` is ~305 lines of six copy-pasted strategy blocks.** That duplication has already produced a real bug: the Monte Carlo EV gate is enforced during live ticks but silently bypassed at startup.
3. **The front-end is a 3,190-line HTML/CSS/JS raw string inside a `.py` file**, re-rendering its entire DOM every second, with no lint, no syntax check, and no meaningful test.

If you only do three things: **delete the dead payload, fix the EV-gate bypass, and table-drive the strategy logic.**

---

## 1. Project context (read this first)

A Windows desktop ETH/USD paper-trading arena. Six strategy "competitors" each run a `$500,000` paper portfolio against the same live market feed; every N hours a genetic algorithm keeps the top 2 genomes and mutates the rest. A pywebview (Edge WebView2) window renders a dark trading terminal.

```
main.py                     entry point: GUI, --cli, --self-test
src/data/live_engine.py     1367  live trading loop + UI state builder  <-- most work
src/gui/dashboard.py        3288  Python 98 lines + 3190-line HTML string <-- most work
src/data/timemachine.py      361  backtest runner + Monte Carlo EV gate
src/data/eth_feed.py         286  yfinance/ccxt candle loader + signal core
src/ai/omniroute_client.py   283  embedded fake LLM gateway
src/arena/broker_sim.py      218  matching engine
src/arena/evolution.py       214  genetic algorithm + history persistence
src/arena/portfolio.py       184  ledger
src/arena/leaderboard.py     172  Sharpe/Sortino/fitness/ranking
src/arena/order.py            78  dataclasses
src/arena/risk_guard.py       68  pre-trade validation
src/competitors/*.py         620  six strategies + base class
tests/*.py                   806  26 tests
```

8,082 lines of Python total.

### Not a git repository

`git status` fails with `fatal: not a git repository`. There is also **no `.gitignore`** (only `.freebuff/.gitignore`). `build/` (64 MB), `dist/` (113 MB), `.venv/` (315 MB), `__pycache__/`, `.pytest_cache/` and runtime `memory/` state are all sitting in the project root.

**Before you edit anything:** make a backup or `git init` + initial commit, so changes are reviewable. The user is handing this file to you precisely because there is no version control safety net.

### Commands

```bash
# tests
.venv/Scripts/python.exe -m pytest -q tests

# GUI
.venv/Scripts/python.exe main.py

# headless backtest / evolution
.venv/Scripts/python.exe main.py --cli --evolve 3

# packaged-build sanity check (constructs the full app, binds a local port)
.venv/Scripts/python.exe main.py --self-test
```

**Warning — tests are not hermetic.** `test_timemachine.py`, `test_evolution_and_omniroute.py` and parts of `test_live_engine.py` reach `evolve_now()` / `run_simulation()`, which rewrite the real `memory/arena_history.json` (~590 KB) and `memory/arena_report.md`. Back those two files up before running the suite, and fix this (see **H3**).

---

## 2. Ground rules — do not break these

These are correct and deliberately implemented. Leave them alone unless a task explicitly says otherwise:

- **All money math in `Decimal`, quantized via `PRECISION_CASH` / `PRECISION_CRYPTO`.** Never introduce floats into `Portfolio`, `BrokerSim` or `RiskGuard`. Floats are acceptable only at the JSON/UI boundary.
- **Stops are evaluated before targets** inside `BrokerSim.on_tick`, with gap-fill at bar open. That's the conservative model and it is intentional.
- **`RiskGuard` never blocks a SELL that reduces exposure** (close/reduce is always allowed, even when the circuit breaker is tripped).
- **`_finite()`** in `live_engine.py` exists so the WebView bridge never receives `NaN`/`Infinity`. Every new numeric field in the UI payload must go through it.
- **The genome/evolution semantics** (elitism, `comp_agg` always keeping `take_profit_pct=None`) are product behavior, not bugs.
- **The canvas chart** (`setupHiDPICanvas`, rAF-throttled resize, lerp animation) is properly implemented. Don't rewrite it.

The UI is dark-themed obsidian/cyan. Do not restyle it as part of these tasks.

---

## 3. Findings

Severity: **P0** = user-visible bug or data corruption · **P1** = significant waste · **P2** = maintainability · **P3** = cleanup.

### P0 — Correctness

---

#### C1. Monte Carlo EV gate is bypassed at startup

**Severity:** P0 · **Effort:** S

`_ensure_active_live_positions` ([src/data/live_engine.py:674-759](src/data/live_engine.py#L674)) computes `mc_odds` for each of the six strategies, stores it into telemetry, and then submits the order **without ever checking `mc_odds.passed`**:

```python
mc_odds = self.mc_evaluator.evaluate_bracket(price, sl, tp, atr=self.live_atr, recent_candles=self.candles)
self.strategy_telemetry["comp_agg"]["mc_stats"] = mc_odds.to_dict()
qty = self.comp_a.compute_r_multiple_qty(price, sl, self.broker)
if qty > Decimal("0"):                       # <-- gate never consulted
    fill = self.broker.submit_order(...)
```

Compare the live path ([src/data/live_engine.py:365-672](src/data/live_engine.py#L365)), which does:

```python
if not mc_odds.passed:
    self.strategy_cooldown[pid] = ts + 20.0
    self.strategy_telemetry[pid]["intent"] = f"EV Gate Blocked: ..."
    self.log_event("EV_GATE_BLOCK", ...)
else:
    ...submit...
```

**Consequence:** on every launch (and after every Reset), all six strategies are forced long even when the gate says "Blocked". The UI then displays the card text *"TimeMachine EV Gate · Blocked"* while the portfolio is holding a position — self-contradictory state visible to the user.

This is called from two places: `bootstrap_intraday_session` ([live_engine.py:299](src/data/live_engine.py#L299)) and the `_live_loop` re-arm branch ([live_engine.py:910](src/data/live_engine.py#L910)).

**Expected fix:** `_ensure_active_live_positions` must obey the same gate. When blocked, leave the strategy flat, set the cooldown, write the blocked telemetry/intent, and log `EV_GATE_BLOCK` — identical to the live path. Prefer doing this by making both paths call the *same* function (see **A1**), not by copy-pasting the gate a second time.

**Acceptance criteria:**
- With `MonteCarloOddsEvaluator.evaluate_bracket` monkeypatched to always return `passed=False`, `_ensure_active_live_positions()` leaves all six `position_qty == 0` and produces `EV_GATE_BLOCK` log entries.
- With it returning `passed=True`, all six still enter as before (existing tests must not regress).
- New test in `tests/test_live_engine.py` covering both branches.

---

#### C2. Offline fallback trades against a hardcoded price

**Severity:** P0 · **Effort:** S

`fetch_realtime_eth_quote` ([live_engine.py:189](src/data/live_engine.py#L189)) falls through four source levels and ends at:

```python
return LiveQuote(price=Decimal("2250.00"), ..., source="Offline Default", ...)
```

([live_engine.py:295](src/data/live_engine.py#L295))

The live loop then executes real paper trades against `$2250` indefinitely. Nothing in the engine or the UI treats this as degraded — it looks like a live quote with a slightly odd source label.

**Expected fix:** make staleness explicit in the data model rather than implicit in a string. Add a `stale: bool` (or `is_live: bool`) field to `LiveQuote`, set it for the cache path and the offline default, and have `_live_loop` skip order submission while stale. Keep the last good price for mark-to-market so existing equity doesn't collapse. Surface it in the UI: the source badge should go amber/grey with "OFFLINE — feed degraded" instead of silently showing a price.

**Acceptance criteria:**
- With all three exchange calls failing and no cached quote, `_live_loop` performs **zero** orders.
- `get_ui_state()["quote"]` exposes the degraded flag and the JS renders a visible degraded state.
- Existing cache-fallback test (`test_resilient_quote_cache_fallback`) still passes, extended to assert the stale flag.

---

#### C3. `stop()` does not join the worker thread

**Severity:** P0 · **Effort:** S

```python
def stop_live_loop(self) -> None:
    self.running = False

def stop(self) -> None:
    self.stop_live_loop()
```

([live_engine.py:904-908](src/data/live_engine.py#L904))

`ArenaDashboard.reset_engine` ([src/gui/dashboard.py:3256](src/gui/dashboard.py#L3256)) then immediately constructs a **new** engine and starts a **new** loop:

```python
def reset_engine(self) -> None:
    self.engine.stop()
    self.engine = LiveArenaEngine(...)
    ...
    self.engine.start_live_loop(interval_sec=1.5)
```

The old thread may still be mid-tick, mid-HTTP-request, and will keep logging into its own dead engine. Rapidly clicking Reset stacks concurrent loops all hitting the same public rate-limited APIs. `start_live_loop` also has a check-then-act race on `self.running` ([live_engine.py:897](src/data/live_engine.py#L897)) that isn't atomic across threads.

**Expected fix:** `stop_live_loop()` should set the flag *and* `join(timeout=...)` the worker, with a bounded timeout (e.g. `2 * interval_sec + max request timeout`) and a warning if it doesn't exit. Guard against joining from the worker thread itself (`threading.current_thread() is not self.worker_thread`). Set `worker_thread = None` after join.

**Acceptance criteria:**
- `reset_engine()` called 5× in a loop leaves exactly one live thread (`threading.active_count()` stable).
- A test that starts the loop, stops it, and asserts `worker_thread` is not alive.

---

#### C4. Eleven silent `except Exception: pass` blocks, zero logging

**Severity:** P0 · **Effort:** M

`grep -rn "except Exception" src | wc -l` → **12**, of which **11** are the bare `except Exception: pass` shape. Sites: `fetch_realtime_eth_quote` (4×), `bootstrap_intraday_session`, `ETHFeed._fetch_dataframe` (2×), `evolve_now`, `_save_evolution_history`, `EmbeddedOmniRouteServer.ensure_running`, `synthesize_post_mortem`.

There is **no logging anywhere in `src`**. `dashboard.py:9` creates `logger = logging.getLogger(__name__)` and never calls it. `src` contains 3 bare `print()` calls, all in `timemachine.py`.

This already produces a misleading message: if `Portfolio.apply_fill` raises `ValueError` ([portfolio.py:131](src/arena/portfolio.py#L131) / [:144](src/arena/portfolio.py#L144)), it propagates into `_live_loop`'s blanket handler and is reported as:

```
FEED_WARN  Retrying live quote stream: Insufficient cash in comp_agg: ...
```

An accounting bug is presented as a network hiccup.

**Expected fix:**
- Add a module-level `logging.getLogger(__name__)` to each module and replace `pass` with `logger.warning(..., exc_info=True)` (or `debug` for the expected/benign cases — document which is which).
- In `_live_loop`, distinguish transient feed errors (`requests.RequestException`) from logic errors (anything else) and log the latter at `error` with a traceback.
- Replace `print()` in `timemachine.py` with logger calls; the CLI output in `main.py` can stay as `print()` since it is user-facing.

**Acceptance criteria:**
- No `except Exception: pass` remains in `src`.
- Running the GUI with an intentionally unreachable feed produces a readable warning, not silence.
- `logging.basicConfig` (or equivalent) is configured once in `main.py`.

---

#### C5. Returned list references race with the worker thread

**Severity:** P0 · **Effort:** S — **fixed for free by P1**

`get_ui_state` holds `self.lock` while building the dict, then releases it. But the `series` block ([live_engine.py:1355-1361](src/data/live_engine.py#L1355)) returns **live list objects by reference**:

```python
"series": {
    "timestamps": self.tick_timestamps,     # aliased
    "eth_price": self.eth_price_series,     # aliased
    "ema_fast": self.ema_fast_series,       # aliased
    "ema_slow": self.ema_slow_series,       # aliased
    "equity": self.equity_series,           # aliased
},
```

pywebview serializes this dict on a *different* thread, after the lock is released, while `_live_loop` is appending to those same lists. Note that `price_history` / `equity_curves` elsewhere are defensively copied (`[fz(v) for v in ...]`) — `series` is the one that isn't.

**Expected fix:** delete `series` entirely (see **P1**). If it must stay, deep-copy it under the lock.

---

#### C6. Breakeven exits are counted as losses

**Severity:** P0 (metrics correctness) · **Effort:** XS

[src/arena/portfolio.py:165](src/arena/portfolio.py#L165):

```python
if pnl > Decimal("0"):
    self.win_count += 1
    self.gross_profit = ...
else:
    self.loss_count += 1
    self.gross_loss = (self.gross_loss + abs(pnl))...
```

A close at exactly `0.00` PnL increments `loss_count` and leaves `gross_loss` unchanged, so `win_rate` is biased down and `closed_trades` counts a flat exit as a losing trade.

**Expected fix:** treat `pnl == 0` as its own bucket (e.g. `breakeven_count`) or exclude it from the win-rate denominator. `closed_trades_count` should probably still count it. Update `Leaderboard.calculate_win_rate` accordingly, and the docstring claims in the README.

**Acceptance criteria:** a test that buys and sells at the same price across a zero-fee portfolio yields `win_rate_pct == 0.0` and `loss_count == 0` (or the chosen breakeven semantics), not `loss_count == 1`.

---

#### C7. Sharpe / Sortino are numerically meaningless as displayed

**Severity:** P0 (metrics correctness) · **Effort:** M

Two separate defects in [src/arena/leaderboard.py:48-91](src/arena/leaderboard.py#L48):

1. **Dead filter.** `non_zero = [r for r in returns if abs(r) > 1e-9]` at [:63](src/arena/leaderboard.py#L63) is only used for a length check at [:64](src/arena/leaderboard.py#L64). The *filtered* list is never used, so flat-cash zero returns still enter `mean_ret` and `variance`. The README's claim of metrics "computed on true traded intervals without flat-cash distortion" is not implemented.
2. **Absurd annualization, hidden by a clamp.** `_estimate_periods_per_year` derives the annualization factor from equity-history timestamp spacing. In live mode ticks arrive every ~1.5 s, giving ≈21M periods/year and `sqrt(21_000_000) ≈ 4583`. The result is then clamped to `±25` at [:76](src/arena/leaderboard.py#L76), so the displayed Sharpe is almost always exactly `±25` or `0` — it carries no information and it feeds `calculate_fitness`, which means it distorts the genetic selection too.

**Expected fix:** pick one coherent definition and document it in a docstring.
- Compute returns from **traded intervals or fixed time buckets** (e.g. group equity history into 1-minute buckets, take the last sample in each bucket), then annualize with a constant appropriate to that bucket size.
- Delete the `non_zero` dead code, or actually use it.
- Decide whether the clamp stays (it's reasonable as a rail against division blowups, but must no longer be the normal case). Add an assertion/log when clamping occurs.

**Acceptance criteria:** a synthetic portfolio with a constant 1%/min return produces a large-but-not-clamped Sharpe; a flat portfolio produces exactly `0.0`. Add both as tests.

---

### P1 — Performance

---

#### P1. ~94% of every UI poll is built and thrown away

**Severity:** P1 · **Effort:** S (biggest win in the project)

`get_ui_state` ([live_engine.py:1278](src/data/live_engine.py#L1278)) returns four large blocks that **no front-end code ever reads**. Verified by grepping `dashboard.py` for each key:

| Key | Where built | References in `dashboard.py` |
|---|---|---|
| `competitors` | [live_engine.py:1362](src/data/live_engine.py#L1362) | **0** |
| `equity_curves` | [live_engine.py:1275](src/data/live_engine.py#L1275) | **0** |
| `series` | [live_engine.py:1355](src/data/live_engine.py#L1355) | **0** |
| `logs` | [live_engine.py:1363](src/data/live_engine.py#L1363) | **0** |

`competitor_cards` also duplicates every field already in `strategies` (equity, cash, roi, win rate, drawdown, fitness, intent, stop/target).

**Estimated payload at steady state** (arithmetic from the list caps, not a runtime measurement — re-measure if you doubt it):

| Field | Values | ≈ bytes |
|---|---|---|
| `equity_curves` (6 × 3000 floats) | 18,000 | ~171 KB |
| `series.equity` (**same 18,000 floats again**) | 18,000 | ~171 KB |
| `series.timestamps` + 3 price series | 720 | ~6 KB |
| `price_history` / `ema_*_history` | 540 | ~4 KB |
| `candles` (150) | 150 | ~7 KB |
| `fills` (60) | 60 | ~11 KB |
| `logs` (50) | 50 | ~5.5 KB |
| `strategies` + `competitors` | 12 | ~6 KB |
| **Total** | | **≈380 KB** |

At 1 Hz that is **~0.4 MB/s, ~1.3 GB/hour** of `json.dumps` → bridge injection → `JSON.parse`, of which ≈94% is discarded. `series.equity` and `equity_curves` are byte-for-byte the same 18,000 numbers serialized twice.

**Expected fix:** delete `competitors`, `equity_curves`, `series` and `logs` from the payload. If a log panel is planned, add a separate cheap `get_logs(since_seq)` bridge method instead of embedding it in the 1 Hz state.

**Do not** just delete them from the dict and leave the producers running — also remove the now-unused producers (see **P2**) so the hot loop stops doing the work.

**Acceptance criteria:**
- `json.dumps(get_ui_state())` length drops below ~40 KB at steady state.
- `test_live_engine_ui_state_is_json_safe_and_complete` is updated: it currently asserts `len(state["equity_curves"][k]) == 4` ([tests/test_live_engine.py:44](tests/test_live_engine.py#L44)), i.e. it is the only thing keeping the dead field alive. Replace that assertion with one that asserts the key is **absent**.

---

#### P2. The equity-curve apparatus feeds nothing

**Severity:** P1 · **Effort:** M (needs a product decision — see §6)

`_record_series_point` ([live_engine.py:871](src/data/live_engine.py#L871)) runs on **every tick** and:

- appends a `strftime` timestamp (a formatting call per tick),
- appends 3 floats,
- appends 6 `float(Decimal)` conversions (one per competitor),
- trims four lists to 180 entries and six lists to 3000.

That is ~75 minutes of 6-series equity history, ~18,000 floats, maintained in the hot loop. There is **no consumer**: the JS never reads `equity_curves`, and `equity_ts` — the x-axis — isn't even included in the payload, so the data is unplottable as shipped.

**Expected fix:** since nothing plots it, drop `equity_series` / `equity_ts` from the live engine (keep `Portfolio.equity_history`, which Sharpe needs). If an equity chart *is* planned, keep the data but sample it (e.g. one point per 15 s, not per 1.5 s tick) and ship only the downsampled series on a separate, slower endpoint.

**Acceptance criteria:** if removed, `max_equity_pts`, `equity_ts`, `equity_series` and all references disappear; no test references them; a code comment at `_record_series_point` explains what it now does (price/EMA series only, 180 points, consumed by the chart).

---

#### P3. Rankings recomputed on every poll, over ever-growing data

**Severity:** P1 · **Effort:** M

`get_ui_state` calls `Leaderboard.get_rankings(self.broker.portfolios)` ([live_engine.py:1280](src/data/live_engine.py#L1280)) once per second, which for each of 6 portfolios:

- iterates up to **2000** equity-history points building a returns list (12,000 float conversions + divisions per poll),
- builds a list of every SELL in `trade_history` ([leaderboard.py:96](src/arena/leaderboard.py#L96)),
- then scans `trade_history` **again** for `sells_count` with an identical predicate ([:129](src/arena/leaderboard.py#L129)),
- then `len()` again ([:149](src/arena/leaderboard.py#L149)).

`equity_history` is capped at 2000 ([portfolio.py:114](src/arena/portfolio.py#L114)), but **`trade_history` is never trimmed** ([portfolio.py:182](src/arena/portfolio.py#L182)). Over a multi-day session this becomes an unbounded per-second scan.

**Expected fix:**
- Derive `sells_count` / `total_trades` from the counters `Portfolio` already maintains (`win_count + loss_count`, and a `trade_count` you increment on every fill) instead of rescanning.
- Cache the rankings on the engine and invalidate them on `apply_fill` / `evolve_now` / price change beyond a threshold; or recompute at most every N seconds.
- Optionally cap `trade_history` (e.g. deque(maxlen=5000)) — but note `Leaderboard` and any reporting need totals, so prefer counters over truncation.

**Acceptance criteria:** `get_rankings` is called at most once per fill/evolution, not once per poll; a 10,000-trade portfolio does not slow the poll measurably.

---

#### P4. Per-tick recomputation of history-derived state

**Severity:** P1 · **Effort:** M

Two hot spots recompute O(n) state from scratch even though only the newest element changed:

1. `_recompute_candle_indicators` ([live_engine.py:826](src/data/live_engine.py#L826)) re-derives Wilder RSI(14), ATR(14), the ORB 15-bar box, and VWAP over **all 200 candles** on every 1.5 s tick.
2. `MonteCarloOddsEvaluator.evaluate_bracket` ([timemachine.py:249](src/data/timemachine.py#L249)) rebuilds σ and μ from `recent_candles` — a 200-element list comprehension plus **199 `log()` calls** — on *every* call, and it is called up to **6× per tick** ([live_engine.py:400](src/data/live_engine.py#L400), 454, 496, 554, 589, 638). The final candle is identical across all six calls.

**Expected fix:**
- Keep incremental Wilder state (running `avg_gain` / `avg_loss` / `atr`) on the engine and update it with the newest candle only; recompute from scratch only on bootstrap or after a gap.
- Memoize σ/μ per tick (e.g. cache keyed on `len(self.candles)` + last close, or pass a precomputed `(sigma, drift)` into `evaluate_bracket` from the engine).
- Downsample the MC call: it is a *pre-trade* check, so it does not need to run for six strategies on every tick when the entry conditions already failed.

**Acceptance criteria:** a before/after timing of `_live_loop` body shows a measurable reduction; indicator values are bit-identical to the from-scratch implementation for a fixed candle sequence (add a regression test comparing incremental vs. full recompute).

---

#### P5. Network and disk I/O performed while holding the engine lock

**Severity:** P1 · **Effort:** M

`evolve_now` takes `with self.lock:` at [live_engine.py:1000](src/data/live_engine.py#L1000) and holds it across:

- `self.omniroute.synthesize_post_mortem(...)`, which does a **`requests.post(..., timeout=0.35)`** ([omniroute_client.py:252](src/ai/omniroute_client.py#L252)),
- `GeneticEvolver.evolve_generation` → `_save_evolution_history`, which **reads, parses, re-dumps and rewrites** a ~590 KB JSON file with `indent=2` ([evolution.py:194-213](src/arena/evolution.py#L194)).

`evolve_now` is invoked from the GUI bridge on the main thread. So a manual "Evolve" click freezes the window *and* starves the tick loop for the duration of an HTTP timeout plus a full file rewrite.

**Expected fix:**
- Build the rankings and summaries under the lock, release it, then do synthesis + persistence off-lock (or on a worker thread), then re-acquire briefly to append the evolution event.
- `_save_evolution_history`: write compact JSON (`separators=(",", ":")`) — that alone is a 1.59× size reduction (590 KB → 370 KB measured) — or switch to JSONL append (one line per generation), which makes the write O(1) instead of O(file).
- Consider lowering the 0.35 s timeout or making synthesis fire-and-forget.

**Acceptance criteria:** clicking Evolve does not block the UI thread for more than ~50 ms; `arena_history.json` no longer doubles in size on each write.

---

#### P6. Front-end rebuilds its whole DOM every second

**Severity:** P1 · **Effort:** M

- `renderStrategies` ([dashboard.py:2035](src/gui/dashboard.py#L2035)) assigns `card.innerHTML = cardInner` for all six cards every poll ([:2145](src/gui/dashboard.py#L2145)), then calls `getBoundingClientRect()` **twice per card** for the FLIP animation — six full HTML re-parses and twelve forced layouts per second. This also restarts CSS animations, kills in-progress text selection, and discards `:hover` state.
- `renderFills` ([:2327](src/gui/dashboard.py#L2327)) rebuilds **all 60 `<tr>`** via `tbody.innerHTML = fills.map(...)` ([:2343](src/gui/dashboard.py#L2343)) to reflect a single new row.

**Expected fix:** update in place.
- Cards already carry `data-strat-id` and a `stratCardDomMap`; keep the element, query its stable children once, and set `textContent` / `style.width` / `className` on the values that changed. Only rebuild when the card's *structure* changes (in-position ↔ flat).
- Fills already carry a monotonic `seq`; prepend a new `<tr>` when `fills[0].seq` advances and drop trailing rows past 60, instead of re-rendering the table.
- Batch the FLIP measurements into a single pass (read all `top`s, then write all transforms) instead of interleaving per card.

**Acceptance criteria:** DOM mutation count per second drops by an order of magnitude (verifiable with a `MutationObserver` in the page); the visual result is unchanged; the `new-fill-row` animation still fires on the newest row.

---

#### P7. Polling ignores visibility and has no delta channel

**Severity:** P1 · **Effort:** S

`setInterval(pollBackend, 1000)` ([dashboard.py:3236](src/gui/dashboard.py#L3236)) runs at full rate forever, including when the window is backgrounded and when nothing has changed. The backend already exposes a cheap monotonic `tick_count` in every payload, which is a ready-made version key.

**Expected fix:** skip the poll when `document.hidden`; add `get_state_since(tick_count)` that returns a small `{"unchanged": true}` when the tick count matches. Long poll or back off to 5 s when the feed is paused (`state.paused`).

**Acceptance criteria:** backgrounding the window stops the bridge traffic; a paused arena drops to a slow poll.

---

### P2 — Architecture & maintainability

---

#### A1. ~250 lines of duplicated strategy logic (also the root cause of C1)

**Severity:** P2 (but high leverage) · **Effort:** L

`_evaluate_live_strategies` spans [live_engine.py:365-672](src/data/live_engine.py#L365) — **~305 lines** — and consists of six near-identical blocks that differ only in:

- the entry predicate (RSI / EMA cross / velocity / VWAP distance / ORB distance),
- how SL and TP are built (fixed % vs. ATR multiple vs. R-multiple vs. ORB midpoint),
- the exit predicate (profit % threshold, trend-stall, VWAP distance),
- the cooldown and the log tags.

`_ensure_active_live_positions` ([:674-759](src/data/live_engine.py#L674)) repeats the same six blocks a second time.

Measured duplication: `fill = self.broker.submit_order(OrderTicket(` appears **13×**, `mc_odds = self.mc_evaluator.evaluate_bracket(...)` **10×**, `reason=ExecutionReason.TAKE_PROFIT, timestamp=ts` 5×, `order_type=OrderType.MARKET, qty=qty, stop_loss=sl, take_profit=tp, timestamp=ts` 5×.

This is exactly how **C1** happened: the gate lives in one copy of the block and not the other.

**Proposed shape** (adapt as you see fit, but keep the property that there is exactly one code path that submits a strategy entry):

```python
@dataclass(frozen=True)
class StrategyRule:
    pid: str
    label: str
    entry_rule_desc: str
    cooldown_sec: float
    # return (stop, target) or None to skip entering
    bracket: Callable[[Decimal, Decimal, CompetitorGenome, MarketView], Optional[tuple[Decimal, Optional[Decimal]]]]
    should_enter: Callable[[MarketView], bool]
    should_exit: Callable[[MarketView, Portfolio, Competitor], bool]
    exit_reason: Callable[[...], ExecutionReason]
```

Then a single loop: compute the view once, and per rule → `should_enter` → `bracket` → **EV gate** → size → submit → log. `_ensure_active_live_positions` becomes "run the same rule set with `force=True`", which makes C1 structurally impossible.

**Acceptance criteria:**
- Entry submission exists in exactly one place.
- `_evaluate_live_strategies` is under ~120 lines.
- All 26 existing tests pass unchanged (behavior-preserving refactor), plus a new test asserting the boot path respects the EV gate.

**Do this refactor before or with C1** — fixing C1 by duplication makes the code worse.

---

#### A2. `dashboard.py` is a 3,288-line file whose middle is a raw HTML string

**Severity:** P2 · **Effort:** L (mechanical, low risk)

Lines 51–3241 of [src/gui/dashboard.py](src/gui/dashboard.py) are a single `HTML_TEMPLATE = r"""..."""` containing ~1,600 lines of CSS and ~1,630 lines of JS. Consequences:

- The JS is never syntax-checked. A typo yields a blank window with no error surface (`debug=False`).
- No linting, formatting, or editor support.
- Diffs are unreviewable.
- The only "test" of the front-end is substring assertion (see **H5**).

**Expected fix:** move the assets out:
```
src/gui/assets/index.html
src/gui/assets/app.css
src/gui/assets/app.js
```
and load them with `webview.create_window(url=...)` served from a small local HTTP server, or read the files at startup and inject them into the template (simpler, keeps the single-window model, avoids adding a server dependency). Keep the HTML/CSS/JS split either way.

Then add a syntax gate: `node --check src/gui/assets/app.js` in the build script (or a Python test that shells out to `node` if available and *skips* otherwise — do not hard-fail machines without Node).

**Acceptance criteria:** `dashboard.py` is under ~150 lines; the app renders identically; a deliberately broken JS file is caught by a check rather than by a blank screen.

---

#### A3. Dead module and dead dependency: `theme.py` / `dearpygui`

**Severity:** P2 · **Effort:** XS

[src/gui/theme.py](src/gui/theme.py) is 73 lines of dearpygui theming. **Nothing imports it** (`grep -rn "gui.theme"` → 0 hits). Yet:

- `dearpygui>=1.11.0` is in [requirements.txt:11](requirements.txt#L11) and installed (2.3.1),
- `build_exe.ps1` and the `.spec` both pass `--exclude-module dearpygui`.

So every user pays the install for a windowing toolkit that is excluded from the shipped binary and referenced by nothing.

**Expected fix:** delete `theme.py` and drop `dearpygui` from `requirements.txt`. (The palette it defines was already re-implemented as CSS variables in the HTML template — verify before deleting that no color values are needed from it.)

---

#### A4. Repeated wiring, scattered constants, lookup tables in the wrong place

**Severity:** P2 · **Effort:** M

- **Competitor wiring is duplicated** between `LiveArenaEngine.__init__` ([live_engine.py:62-70](src/data/live_engine.py#L62)) and `TimeMachineArena.__init__` ([timemachine.py:41-51](src/data/timemachine.py#L41)). A `build_competitors(initial_cash) -> list[BaseCompetitor]` factory removes the drift risk (there are already 6 competitors to keep in sync across both).
- **Magic numbers in the hot path:** 60 s post-exit cooldown, 20 s EV-block cooldown, 2400 s stagnation timeout, `0.9985` trailing ratchet, `0.12/0.15/0.25/0.30/0.35%` profit triggers, `1.8R` assumed target for uncapped runners, 200 candles, 3000 equity points, 180 tick points, 120 log lines, `1.5 s` interval. These belong in one `src/config.py` (or on the genome, where they'd also become evolvable). Several are currently duplicated as literals in more than one branch.
- `STRATEGY_COLORS`, `STRATEGY_SHORT`, `STRATEGY_DISPLAY`, `REASON_DISPLAY` are class attributes on `LiveArenaEngine` ([live_engine.py:1065-1096](src/data/live_engine.py#L1065)) but they describe *strategies*, not the engine; `_build_view_model` and `_get_strategy_label` both re-derive display names. Move them next to the competitor definitions and key everything off one registry.
- `_update_telemetry_snapshot` ([:761](src/data/live_engine.py#L761)) uses a per-strategy `if/elif` chain over `pid`; a dict of `pid -> formatter` reads better and matches the registry above.
- `_build_view_model` does `next(comp for comp in self.competitors if comp.portfolio_id == r.portfolio_id)` **inside** the rankings loop (O(n²); trivial at n=6, but it is a per-poll allocation).

---

#### A5. `main.py --self-test` is opaque and has side effects

**Severity:** P2 · **Effort:** S

[main.py:9-22](main.py#L9) imports `ctypes`, `ssl`, `sqlite3`, `lzma`, `bz2`, `pandas`, `webview` and binds them to unused names. The intent is to force PyInstaller to bundle those DLLs, and it works — but:

- there is no comment saying so, so every linter flags them as unused,
- the function then constructs a full `ArenaDashboard`, which constructs `LiveArenaEngine`, which constructs `OmniRouteGateway`, which **binds a listening TCP socket on 127.0.0.1:20128** ([omniroute_client.py:186](src/ai/omniroute_client.py#L186)).

So a "self test" opens a port as a side effect and can fail in restricted environments for reasons unrelated to packaging.

**Expected fix:** add a clear comment explaining the import block's purpose, mark it with `# noqa` if a linter is added, and make the omniroute server opt-in (`auto_spawn=False` for self-test) so the test verifies bundling without network side effects.

---

### P3 — Packaging, dependencies, hygiene

---

#### H1. Dependencies are unpinned, unpinned-past-major, and mix concerns

[requirements.txt](requirements.txt) uses `>=` everywhere, with **no lockfile**. The installed environment already carries `numpy 2.5.4` and `pandas 3.1.0` — major versions that a fresh `pip install -r requirements.txt` may not reproduce, which matters a lot for a numeric codebase.

Also:

| Line | Package | Problem |
|---|---|---|
| 2 | `pytest` | dev tool in the runtime file |
| 3 | `pytest-asyncio` | **unused** — there are zero `async def` tests |
| 8 | `websockets` | **unused** — nothing imports it |
| 11 | `dearpygui` | **unused** — see A3 |
| 12 | `pyinstaller` | build tool in the runtime file |

`pytest.ini` also sets `asyncio_default_fixture_loop_scope = function`, which is a config for the unused plugin.

**Expected fix:** add a `pyproject.toml` with `[project] dependencies` (runtime only: `requests`, `numpy`, `pandas`, `yfinance`, `ccxt`, `pywebview`) and `[project.optional-dependencies] dev = ["pytest", ...]`, `build = ["pyinstaller"]`. Remove `pytest-asyncio`, `websockets`, `dearpygui`. Pin with `~=` or a `requirements.lock` produced by `pip freeze`.

---

#### H2. Two build configs that will drift

[build_exe.ps1](build_exe.ps1) passes the PyInstaller flags on the command line; [TradeBot0_Arena.spec](TradeBot0_Arena.spec) re-declares the same configuration (plus `upx=True`, `console=False`) as a checked-in file. PyInstaller **regenerates the spec** on every `build_exe.ps1` run, so the checked-in spec is stale the moment anyone builds.

**Expected fix:** pick one. Either commit the spec and have the script run `pyinstaller TradeBot0_Arena.spec`, or delete the spec and let PyInstaller generate it into a gitignored directory. Do not keep both.

Minor, in the same file: `Get-Process ... | Stop-Process -Force` kills *any* process named `TradeBot0_Arena*`, not just the one this build owns.

---

#### H3. Tests are not hermetic — they mutate user data

`evolve_now()` and `run_simulation()` call `GeneticEvolver._save_evolution_history`, which writes `memory/arena_history.json` relative to the **current working directory**, and `_generate_post_mortem_report` writes `memory/arena_report.md`. Both are invoked by tests. Current file: **590 KB / 209 generations**.

Effects: running the suite rewrites the user's real arena history; test outcomes can depend on prior runs; the suite cannot run in parallel.

**Expected fix:** make the memory directory injectable (e.g. `GeneticEvolver(memory_dir=...)` or a module-level `set_memory_dir()`) and have a `conftest.py` fixture point it at `tmp_path`. Keep the production default at `./memory`.

**Acceptance criteria:** running the full suite twice in a row leaves `memory/` byte-identical; `grep -r "memory/" tests/` finds no hardcoded paths.

---

#### H4. No `.gitignore`, no version control, build artifacts in the tree

Project root contains `build/` (64 MB), `dist/` (113 MB), `.venv/` (315 MB), `__pycache__/`, `.pytest_cache/`, runtime `memory/`, and a Windows shortcut `TradeBot0_Arena.lnk`. `git status` reports *not a repository*.

**Expected fix:** add a `.gitignore` covering `.venv/`, `build/`, `dist/`, `__pycache__/`, `.pytest_cache/`, `memory/*.json`, `*.spec` (if H2 deletes it), and **do not** version the `.lnk`. If the user wants version control, `git init` and make an initial commit *before* the refactors in A1/A2 so they are reviewable. Ask before doing this — it is the user's call whether to create a repo.

---

#### H5. The front-end test asserts substrings, not behavior

[tests/test_live_engine.py:177-206](tests/test_live_engine.py#L177):

```python
assert "radarRipple" in HTML_TEMPLATE
assert "tickUpGlow" in HTML_TEMPLATE
assert "markerPulse" in HTML_TEMPLATE
...
```

This breaks on any cosmetic CSS rename, verifies nothing about rendering, and (via the `equity_curves` assertion at line 44) actively pins dead code in place. The Chinese-character check is reasonable as a copy guard; the animation-name checks are not.

**Expected fix:** replace with (a) a JS syntax check per **A2**, (b) a DOM contract test — assert that every `data-*` hook and element id the JS queries actually exists in the HTML (parse both with a regex or a tiny HTML parser and diff the id sets). That catches the real failure mode (JS querying a missing element) without brittle string matching.

---

#### H6. Doc drift and small inconsistencies

- [README.md](README.md) says "Automated Unit Test Suite (20 Tests)"; there are **26** test functions.
- README markets "OmniRoute Microservice & Keyless Diagnostics" and "RTK/Caveman prompt compression". The embedded gateway ([omniroute_client.py](src/ai/omniroute_client.py)) returns a **fixed canned paragraph** regardless of prompt, so `gateway_online`, `tokens_used`, `quota_remaining_pct` and `tokens_saved` are fabricated numbers. Either label it honestly as a deterministic local stub in both README and UI, or remove the metrics. **Do not silently "fix" this by removing the feature** — it may be intentional demo scaffolding; see §6.
- README claims Sharpe/Sortino are computed "without flat-cash distortion" — not true today (see **C7**).
- 15 unused imports across the tree: `ROUND_HALF_UP`/`ROUND_DOWN`/`CandleBar`/`MonteCarloBracketOdds` in [live_engine.py](src/data/live_engine.py), `OrderStatus` in [broker_sim.py](src/arena/broker_sim.py), `replace` in [base.py](src/competitors/base.py), `ROUND_DOWN` in [atr_dynamic.py](src/competitors/atr_dynamic.py), `asdict` in [timemachine.py](src/data/timemachine.py), `Dict`/`Any` in [omniroute_client.py](src/ai/omniroute_client.py), `Optional` and `logger` in [dashboard.py](src/gui/dashboard.py).

---

### P3 — UX / accessibility (only if the user asks for polish)

- `user-select: none` on `*` ([dashboard.py:109](src/gui/dashboard.py#L109)) means a trader **cannot copy** a price, PnL or fill out of the terminal. Allow selection inside `.num` / table cells.
- Two blocking `alert()` dialogs for the TradingView explanation ([dashboard.py:1896](src/gui/dashboard.py#L1896), [:2017](src/gui/dashboard.py#L2017)) — a modal `<dialog>` would fit the terminal aesthetic and not block the JS thread.
- No ARIA roles, no keyboard navigation beyond F11 fullscreen.
- The stale/offline quote is not visually distinguished from a live one (see **C2**).

---

## 4. Suggested execution order

Each batch should build, pass tests, and leave the app runnable.

**Batch 0 — safety (do first)**
1. Back up `memory/arena_history.json` and `memory/arena_report.md`.
2. Add `.gitignore`; ask the user whether to `git init` + initial commit (**H4**).
3. Run the suite to establish a baseline; note any pre-existing failures.
4. Fix test hermeticity (**H3**) so the baseline is reproducible.

**Batch 1 — quick wins, no behavior change**
5. Delete `competitors` / `equity_curves` / `series` / `logs` from the payload and remove their producers (**P1**, **P2**, **C5**). Update the test that pins them.
6. Delete `theme.py`, drop `dearpygui` / `websockets` / `pytest-asyncio` (**A3**, **H1** partial).
7. Remove the 15 unused imports (**H6**).
8. Add logging and remove the `except: pass` blocks (**C4**).

**Batch 2 — correctness**
9. Fix the EV-gate bypass (**C1**) — ideally *after* or *as part of* A1.
10. Fix breakeven-as-loss (**C6**) and the Sharpe/Sortino definition (**C7**).
11. Fix `stop()` join semantics and `reset_engine` (**C3**).
12. Degraded-feed handling (**C2**).

**Batch 3 — the big refactor**
13. Table-drive the strategy rules (**A1**). This is behavior-preserving; run the full suite before and after.
14. Split the front-end assets and add a JS syntax check (**A2**).

**Batch 4 — performance polish**
15. Cache rankings / replace rescans with counters (**P3**).
16. Incremental indicators + memoized Monte Carlo σ (**P4**).
17. Move synthesis/persistence off the lock; compact or JSONL the history file (**P5**).
18. In-place DOM updates (**P6**), visibility-aware polling (**P7**).
19. Consolidate build configs and dependencies (**H2**, **H1**).

---

## 5. Verification checklist

After each batch:

```bash
.venv/Scripts/python.exe -m pytest -q tests        # must be green, count >= baseline
.venv/Scripts/python.exe main.py --cli --evolve 3  # headless path must not crash
.venv/Scripts/python.exe main.py --self-test       # must print SELF_TEST_OK
.venv/Scripts/python.exe main.py                   # manual: window renders, cards tick
```

For A2/P6 you additionally need the UI open: confirm the six strategy cards update, the fill tape prepends, the chart animates, and **no** console errors (`webview` devtools are off, so temporarily flip `webview.start(debug=True)` while verifying, then revert).

For P1, measure before/after with:

```python
import json
from src.data.live_engine import LiveArenaEngine
len(json.dumps(LiveArenaEngine().get_ui_state()))
```

and drive it with synthetic ticks (see the `_drive` helper at `tests/test_live_engine.py:17`) rather than the network.

---

## 6. Decisions the human must make before you start

Do not guess these — ask:

1. **Is the equity curve a planned feature?** If yes, keep the data and sample it (P2 becomes "downsample + separate endpoint"). If no, delete it. It is currently maintained every tick and shipped every second with no consumer.
2. **Is OmniRoute's embedded gateway intentional demo scaffolding?** It returns a canned string, and the token/quota metrics are invented. Options: (a) label it honestly as a stub in README + UI, (b) remove the metrics and keep the deterministic synthesis, (c) keep as is.
3. **Should `git init` be run?** The project has no version control and the refactors in A1/A2 are large. Strongly recommended, but it is the user's repo.
4. **Is the startup "force all six strategies into positions" behavior wanted at all?** C1 assumes the intent is "respect the gate". There is a plausible alternative product intent: "on boot, always show the user six live positions". If so, the fix is to keep forcing entry but stop *displaying* "EV Gate Blocked" for a position that exists — do not silently make the UI honest in the wrong direction.

---

## 7. Appendix — measured facts

| Metric | Value |
|---|---|
| Python LOC (src + tests + main) | 8,082 |
| `dashboard.py` total / of which HTML string | 3,288 / 3,190 |
| `live_engine.py` | 1,367 |
| Test functions | 26 (README claims 20) |
| `except Exception` in `src` | 12 (11 are bare `pass`) |
| `logger.*` calls in `src` | 0 |
| Unused imports | 15 |
| UI payload at steady state | ≈380 KB/poll, ≈94% unread |
| `equity_series` retained | 6 × 3,000 floats |
| `memory/arena_history.json` | 590 KB / 209 generations / 2,950 B per record |
| Same file as compact JSON | 370 KB (indent costs 1.59×) |
| Tree sizes | `.venv` 315 MB, `dist` 113 MB, `build` 64 MB |
| Exchange fetch worst case per tick | 1.8 + 2.0 + 1.8 + 1.8 = **7.4 s** against a **1.5 s** interval |

That last row is worth a moment: if Binance times out *and* Kraken times out *and* Coinbase is slow, one tick can occupy 7.4 seconds while `interval_sec` is 1.5. The loop simply falls 5 intervals behind with no deadline handling. Consider a total time budget per tick (e.g. 2.5 s) enforced across the fallback chain, and/or running the quote fetch on a separate thread from the strategy evaluation.
