# TradeBot0 Full-Project Audit: Bugs & Optimization Roadmap

> **Audit Scope**: Full source tree (`main.py`, 36 `src/**/*.py` files totaling 13,236 lines, frontend assets `index.html` / `app.js` / `app.css`), 81 test suites (17,049 lines), packaging specs (`TradeBot0_Arena.spec`, `TradeBot0.iss`, `build_exe.ps1`), operational scripts (`scripts/`), documentation (`README.md`, `OptimizationFullGuide.md`), and knowledge graph (`graphify-out/`).
> **Repository Snapshot**: Audited at `V1.0.0` (`876f2bc`); **all items resolved in local `V2.0.0` release**.

### V2.0.0 Resolution Summary

All 17 verified defects (`BUG-01`–`BUG-17`), architecture optimizations (`§3.1`–`§3.5`), and documentation/DX updates (`§4`) below were implemented and verified in `V2.0.0`:
- **Engine Modularization & Lock Narrowing (`§3.1`, `§3.2`, `BUG-08`, `BUG-09`, `BUG-12`)**: Split `LiveArenaEngine` (`2,783` LOC -> `1,192` LOC) into 4 cohesive mixins ([quote_feeds.py](file:///c:/Users/will0/Dropbox/TradeBot0/src/data/quote_feeds.py), [indicator_engine.py](file:///c:/Users/will0/Dropbox/TradeBot0/src/data/indicator_engine.py), [live_strategy_runner.py](file:///c:/Users/will0/Dropbox/TradeBot0/src/data/live_strategy_runner.py), [session_codec.py](file:///c:/Users/will0/Dropbox/TradeBot0/src/data/session_codec.py)); moved SQLite WAL flushes & auto-evolution DB writes outside `self.lock`; parameterized `symbol` across WebSocket/REST/bootstrap/MTF; preserved `>2R` macro TP scaling; added `+1.0%` breakeven ratchet step for live `TrailingGuard` on both LONG and SHORT.
- **Core Correctness (`BUG-01`, `BUG-02`, `BUG-06`, `BUG-07`, `BUG-10`, `BUG-11`, `BUG-13`, `§3.3`)**: Eliminated `src.competitors` -> `src.arena` circular import via PEP 562 lazy import; preserved `take_profit_pct=None` for `comp_trail` in evolution + added entropy-seeded `evolve_generation_with_records`; tracked `_live_fill_seq_offset` for monotonic `#seq` past 200 fills; preserved full evolved genomes across `reset_engine()`; aligned dynamic slippage between `BrokerSim` and side-effect-free `RiskGuard`; switched `evt_id` to deterministic SHA-256 + added `event_ts`/`date_time`; upgraded `MonteCarloOddsEvaluator` (`timemachine.py`) with Student-t(`df=6`)/empirical bootstrap, antithetic variates, risk-neutral Ito adjustment, and intra-step wick excursion.
- **Frontend & DX (`BUG-03`–`BUG-05`, `BUG-14`–`BUG-17`, `§3.5`, `§4`)**: Fixed `>= 6` splash table gate deadlock; aligned chart `typical_mean` & `Session Mean`/`MEAN`; added clickable `.intel-retry-btn` for failed article loads; removed falsy `0` confidence coercion and hardcoded `'Pure Math Core'` pill; replaced stale `6 strategies`/`$600,000` copy and static fake news HTML; deleted dead bridge wrapper `save_session_state`; bumped version to `V2.0.0`, fixed `ETH/USD` docs in `README.md`/`OptimizationFullGuide.md`, updated `.gitignore`, added `.graphifyignore`, pinned `win7` compat DLL locally, and added regression suite `tests/test_v200_fixes.py`.

---

## 1. Executive Summary & Verification Baseline

TradeBot0 is a desktop quantitative paper-trading arena in **ETH/USD** combining five autonomous strategies (`Aggressive`, `Conservative`, `Trailing Guard`, `ORB Breakout`, `Session Mean Pullback`), a `Decimal`-precision broker/portfolio simulator, Monte Carlo EV gating, genetic algorithm parameter evolution, an 18-source + OmniRoute LLM macro-intelligence stack, and a hardware-accelerated `pywebview` HTML5/Canvas desktop UI.

Despite extensive regression testing and prior repair passes (`V2.6.0` -> `V2.8.7` -> `V1.0.0`), deep-dive static analysis, architecture inspection, and live in-memory reproduction uncovered **17 verified bugs/defects** (7 High, 7 Medium, 3 Low/Stale-Asset) alongside **major optimization and documentation/DX opportunities**—most notably a reproducible circular import crash, genetic evolution corrupting `comp_trail`'s uncapped runner gene, a hardcoded `>= 6` splash gate stalling UI startup for 3.5s on every launch, a chart key mismatch hiding the session mean indicator line, permanent caching of transient article failures, and heavy architectural coupling inside the 2,783-line `LiveArenaEngine`.

### Observed Test & Diagnostic Results

| Check Executed | Command | Result | Key Observations |
| :--- | :--- | :--- | :--- |
| Full pytest suite | `.\.venv\Scripts\python.exe -u -m pytest tests -v --tb=short --durations=15` | **604 passed, 2 skipped** in `293.01s` | `tests/test_eth_feed.py::test_fetch_historical_bars_yahoo_success` accounted for **219.23s** due to cold Dropbox Smart Sync hydration of `yfinance` dependencies; the other 605 tests finished in `73.78s`. Both skipped tests live in `tests/test_phase3_soak.py`. |
| Warm feed re-test | `.\.venv\Scripts\python.exe -m pytest tests\test_eth_feed.py -v` | **6 passed** in `3.71s` | Confirms the 219s stall was environment/Dropbox I/O hydration rather than slow test logic. |
| Opt-in soak tests | `$env:TRADEBOT0_RUN_SOAK="1"; .\.venv\Scripts\python.exe -m pytest tests\test_phase3_soak.py -v` | **2 passed** in `2.53s` | `test_p3_mini_soak_many_ticks_no_growth_blowup` & `test_p3_breaker_trips_force_closes_and_resets_on_evolve` pass when enabled. |
| App self-test | `.\.venv\Scripts\python.exe main.py --self-test` | **Exit 0 (`SELF_TEST_OK`)** | Restored Generation #1 snapshot from `data/arena_history.db` (`candles_1m`: 870 rows, `execution_ledger`: 330 rows, `evolution_history`: 2 rows, `session_snapshot`: 1 row). |
| Broken venv `.exe` launchers | `.venv\Scripts\pytest.exe`, `.venv\Scripts\graphify.exe` | **Silent exit 1** | `.venv\pyvenv.cfg` points to pre-move path `C:\Users\will0\TradeBot0\.venv`; must invoke via `.\.venv\Scripts\python.exe -m ...`. |

---

## 2. Confirmed Bugs & Functional Defects

### 2.1 High-Severity Bugs (Runtime Failures, Broken Features, or Silently Corrupted Logic)

#### [BUG-01] Reproducible Circular Import Crash (`src.competitors` -> `src.arena` -> `src.competitors`)
- **Locations**: [src/competitors/base.py](file:///c:/Users/will0/Dropbox/TradeBot0/src/competitors/base.py#L6), [src/arena/__init__.py](file:///c:/Users/will0/Dropbox/TradeBot0/src/arena/__init__.py#L6), [src/arena/evolution.py](file:///c:/Users/will0/Dropbox/TradeBot0/src/arena/evolution.py#L13)
- **Root Cause**: Importing any competitor module before `src.arena` executes `src/competitors/__init__.py` -> `base.py` -> `from src.arena.order import ...`, which runs `src/arena/__init__.py` -> imports `GeneticEvolver` from `src/arena/evolution.py` -> imports `BaseCompetitor` from `src.competitors.base` while `base.py` is still partially initialized.
- **Reproduction**: Running `.\.venv\Scripts\python.exe -c "from src.competitors.aggressive import AggressiveCompetitor"` raises:
  `ImportError: cannot import name 'BaseCompetitor' from partially initialized module 'src.competitors.base'`.
- **Impact**: Existing code/tests mask this only because they happen to import `src.arena` before `src.competitors`. Any standalone script or external caller importing `src.competitors` first immediately crashes.
- **Recommended Fix**: Remove eager `evolution` import from `src/arena/__init__.py` (or guard `BaseCompetitor` import inside `evolution.py` under `TYPE_CHECKING`, importing only `CompetitorGenome` or lazily).

#### [BUG-02] `GeneticEvolver` Silently Destroys `TrailingGuardCompetitor`'s Uncapped Runner Gene
- **Locations**: [src/arena/evolution.py](file:///c:/Users/will0/Dropbox/TradeBot0/src/arena/evolution.py#L88-L90), [src/arena/evolution.py](file:///c:/Users/will0/Dropbox/TradeBot0/src/arena/evolution.py#L331-L348), [src/competitors/trailing_guard.py](file:///c:/Users/will0/Dropbox/TradeBot0/src/competitors/trailing_guard.py)
- **Root Cause**: Both `AggressiveCompetitor` (`comp_agg`) and `TrailingGuardCompetitor` (`comp_trail`) intentionally initialize with `take_profit_pct=None` (uncapped trend runners). However, `GeneticEvolver.evolve_generation` only preserves `take_profit_pct=None` for `comp.portfolio_id == "comp_agg"` (line 332-337), omitting `comp_trail`. When `comp_trail` finishes Rank #3-#5 and goes through `crossover_and_mutate`, blended parents inject a fixed `take_profit_pct`.
- **Reproduction (verified in-memory)**: With `comp_agg` & `comp_cons` ranked #1/#2 and `comp_trail` at #3, `GeneticEvolver.evolve_generation` changed `comp_trail.genome.take_profit_pct` from `None` to **`0.032`**, turning the trailing runner into a fixed-TP strategy.
- **Recommended Fix**: Preserve `take_profit_pct=None` (and archetype-defining invariants) for `comp_trail` as well (or model archetype traits as an explicit `preserve_uncapped_tp: bool` flag on `BaseCompetitor`/`CompetitorGenome`).

#### [BUG-03] Splash Screen Exit Gate Deadlocked at `>= 6` Strategies (Always Hits 3.5s Timeout)
- **Locations**: [src/gui/assets/app.js](file:///c:/Users/will0/Dropbox/TradeBot0/src/gui/assets/app.js#L1222-L1227), [src/gui/assets/app.js](file:///c:/Users/will0/Dropbox/TradeBot0/src/gui/assets/app.js#L308)
- **Root Cause**: After `comp_atr` was removed in `V2.8.0` leaving 5 strategies (`comp_agg`, `comp_cons`, `comp_trail`, `comp_orb`, `comp_vwap`), `updateDashboard` still checks:
  ```javascript
  if (lbBody && lbBody.children.length >= 6 && stratGrid && stratGrid.children.length >= 6) {
    hasFirstTableRendered = true;
  }
  ```
- **Impact**: `lbBody.children.length` and `stratGrid.children.length` are both `5`, so `hasFirstTableRendered` never becomes `true`. Every cold launch and reset stalls unnecessarily until the `3500` ms `splashSafetyTimer` fallback forces dismissal.
- **Recommended Fix**: Compare dynamically against `(state.strategies || []).length > 0` (`lbBody.children.length >= expectedCount && stratGrid.children.length >= expectedCount`).

#### [BUG-04] Candlestick Chart Never Renders the Session Mean Reference Line (`ind.vwap` vs `typical_mean`)
- **Locations**: [src/gui/assets/app.js](file:///c:/Users/will0/Dropbox/TradeBot0/src/gui/assets/app.js#L2574-L2598), [src/data/live_engine.py](file:///c:/Users/will0/Dropbox/TradeBot0/src/data/live_engine.py#L2282-L2290)
- **Root Cause**: Backend `_build_snapshot_locked()` emits `indicators["typical_mean"] = float(self.live_typical_mean)`. Meanwhile `drawPriceChart()` reads `const vwapVal = Number(ind.vwap || 0);` and only draws when `vwapVal >= minP && vwapVal <= maxP`.
- **Impact**: `ind.vwap` is always `undefined -> 0`, so the horizontal `MEAN` / `VWAP` reference line and right-axis price pill never draw on the live candlestick chart.
- **Recommended Fix**: Read `Number(ind.typical_mean ?? ind.vwap ?? 0)` and update the chart badge tag from `'VWAP'` to `'MEAN'`.

#### [BUG-05] Frontend Permanently Caches Article Generation Failures, Blocking Retries After Recovery
- **Locations**: [src/gui/assets/app.js](file:///c:/Users/will0/Dropbox/TradeBot0/src/gui/assets/app.js#L3513-L3548), [src/intelligence/macro_commander.py](file:///c:/Users/will0/Dropbox/TradeBot0/src/intelligence/macro_commander.py#L537-L569)
- **Root Cause**: `MacroCommander.get_event_article()` docstring explicitly specifies that a failed generation leaves `article_state = "failed"` and *"a later explicit call retries (the gateway may have recovered since)"*. However, `requestIntelArticle(eventId)` in `app.js` stores `{ state: 'failed', reason }` directly into `intelArticleCache[eventId]` and immediately short-circuits on `if (cached) { renderIntelArticle(eventId, cached); return; }` on every future expand/collapse.
- **Impact**: If a user expands an Intel Hub card while OmniRoute is briefly starting or rate-limited, that article stays broken for the entire session with no retry option.
- **Recommended Fix**: Cache only `state === 'ready'` permanently (or offer a Retry button / invalidate failed cache entries after a short cooldown or on gateway reconnect).

#### [BUG-06] Live Fill Sequence Numbers (`#seq`) Shift Backward Once History Exceeds 200 Fills
- **Locations**: [src/gui/view_model.py](file:///c:/Users/will0/Dropbox/TradeBot0/src/gui/view_model.py#L251-L277), [src/data/live_engine.py](file:///c:/Users/will0/Dropbox/TradeBot0/src/data/live_engine.py#L328-L329)
- **Root Cause**: `_harvest_fills` caps `self.fill_records` in RAM to the newest 200 entries (`self.fill_records = self.fill_records[-200:]`). Yet `view_model.py` numbers live rows by enumerating `for f in engine.fill_records` starting `live_counter = 0 -> 1, 2, ...` on every snapshot.
- **Impact**: After 200 live fills accrue and old records drop off the front of `fill_records`, every new fill shifts the assigned `#seq` of all visible fills backward (`#1` keeps moving to newer fills). Note SQLite already has a monotonic `fill_seq` (and `data/arena_history.db` currently has `330` rows in `execution_ledger`, so long sessions hit this immediately).
- **Recommended Fix**: Track a monotonic `_live_fill_seq_offset` on `LiveArenaEngine` (or persist/assign a monotonic `live_seq` once at harvest time) instead of re-indexing the truncated 200-element tail.

#### [BUG-07] `ArenaDashboard.reset_engine()` Stitches Old `Gen #N` Label onto Fresh Gen-1 Genomes
- **Locations**: [src/gui/dashboard.py](file:///c:/Users/will0/Dropbox/TradeBot0/src/gui/dashboard.py#L712-L728)
- **Root Cause**: When resetting the arena, `reset_engine()` constructs a new `LiveArenaEngine` (initializing all 5 competitors to default Generation-1 genomes) and then loops `c.genome = _dc_replace(c.genome, generation=gen)` to keep the old `generation` integer without restoring evolved parameters.
- **Impact**: If the user resets at `Gen #7`, the UI displays `Gen #7` even though every strategy parameter silently reverted to baseline Gen #1 defaults.
- **Recommended Fix**: Either reset generation counter cleanly to `Gen #1` during a full parameter reset, or offer distinct "Reset Balances/Positions (Keep Evolved Genomes)" vs "Full Reset to Gen #1".

---

### 2.2 Medium-Severity Bugs & Behavioral Subtlety

#### [BUG-08] Macro Trend TP Expansion Overwrites Evolved >2.0R Targets Downward
- **Locations**: [src/data/live_engine.py](file:///c:/Users/will0/Dropbox/TradeBot0/src/data/live_engine.py#L1200-L1208)
- **Behavior**: Under `LONG_ONLY` or `SHORT_ONLY` with `sizing_mult > 1.0`, `_try_enter_bracket` recalculates `tp = price ± r_dist * Decimal(str(round(2.0 * float(sizing_mult), 2)))`.
- **Defect**: It hardcodes `2.0` as the base R-multiple instead of computing the ticket's actual `(tp - price) / r_dist` (e.g., `comp_vwap` uses `2.2R`, `comp_cons` uses `1.8R`, evolved genomes can exceed `2.5R`). At `sizing_mult = 1.05`, a `3.0R` target gets shrunk down to `2.1R`.
- **Fix**: Scale the existing `(tp - price)` distance by `sizing_mult` (`price + (tp - price) * sizing_mult`).

#### [BUG-09] Live Engine vs. TimeMachine Backtest Parity Drift
- **Locations**: [src/data/live_engine.py](file:///c:/Users/will0/Dropbox/TradeBot0/src/data/live_engine.py#L1258-L1531), [src/data/timemachine.py](file:///c:/Users/will0/Dropbox/TradeBot0/src/data/timemachine.py#L179-L210), [src/competitors/trailing_guard.py](file:///c:/Users/will0/Dropbox/TradeBot0/src/competitors/trailing_guard.py#L64-L85)
- **Details**:
  - Backtest calls unified `ETHFeed.generate_signal(bar, prev_bar)` on 15m bars with real volume-weighted VWAP; live `_evaluate_live_strategies` duplicates 5 custom inline entry/exit blocks on 1m indicators and unweighted `live_typical_mean` (since live 1m bars have no volume).
  - `TrailingGuardCompetitor.evaluate_signal` applies a `+1.0%` breakeven stop ratchet (`trailing_guard.py:68-72`), whereas live `comp_trail` inline ratchet (`live_engine.py:1394-1427`) omits the breakeven step completely.
  - The 40-minute channel stagnation exit (`abs(gain_pct) < 0.10` at `live_engine.py:1274-1293`) exists only in live trading, not in backtest/evolution fitness evaluation.

#### [BUG-10] `RiskGuard.validate_order` Mutates State & Diverges from `BrokerSim` Slippage
- **Locations**: [src/arena/risk_guard.py](file:///c:/Users/will0/Dropbox/TradeBot0/src/arena/risk_guard.py#L24), [src/arena/risk_guard.py](file:///c:/Users/will0/Dropbox/TradeBot0/src/arena/risk_guard.py#L48-L50), [src/arena/broker_sim.py](file:///c:/Users/will0/Dropbox/TradeBot0/src/arena/broker_sim.py#L73-L105), [src/arena/broker_sim.py](file:///c:/Users/will0/Dropbox/TradeBot0/src/arena/broker_sim.py#L196-L236)
- **Reproduction (verified in-memory)**: Calling read-only-sounding `RiskGuard.validate_order(...)` when `max_drawdown_pct >= 15.00` directly mutates `portfolio.is_circuit_breaker_tripped = True`. Furthermore, `RiskGuard` validates affordability using fixed `slippage_pct = 0.0002`, while `BrokerSim` prices execution via `compute_execution_slippage` (half-spread + quadratic depth exhaustion + ATR volatility), forcing ad-hoc slippage clamping (`broker_sim.py:201-204`) and defensive `ValueError` recovery (`broker_sim.py:229-236`).

#### [BUG-11] `GeneticEvolver._last_records` Global Class State & Static Generation Seed
- **Locations**: [src/arena/evolution.py](file:///c:/Users/will0/Dropbox/TradeBot0/src/arena/evolution.py#L34), [src/arena/evolution.py](file:///c:/Users/will0/Dropbox/TradeBot0/src/arena/evolution.py#L37-L39)
- **Details**: `evolve_generation()` stores evolution records on class attribute `GeneticEvolver._last_records`, which `evolve_now()` reads outside the engine lock—unsafe if two instances evolve concurrently. Additionally, `_generation_seed(next_gen) = 20261113 + next_gen * 97` ignores equity/market entropy, so identical parent rank orders in different runs mutate identically.

#### [BUG-12] Symbol Parameter Ignored Across Live Feeds & Global `_active_epoch` Singleton
- **Locations**: [src/data/ws_feed.py](file:///c:/Users/will0/Dropbox/TradeBot0/src/data/ws_feed.py#L27-L28), [src/data/live_engine.py](file:///c:/Users/will0/Dropbox/TradeBot0/src/data/live_engine.py#L136), [src/data/live_engine.py](file:///c:/Users/will0/Dropbox/TradeBot0/src/data/live_engine.py#L1870)
- **Details**: `LiveArenaEngine.__init__(..., symbol="ETH/USD")` accepts `symbol`, yet `StreamingCryptoFeed` hardcodes `ethusdt@ticker`, REST quotes hardcode `ETHUSDT`/`ETH-USD`/`XETHZUSD`, logs hardcode `"ETH"`, and bootstrap/MTF seeds hardcode `"ETH-USD"`. Separately, class-level `LiveArenaEngine._active_epoch` assumes only one engine ever exists per process; instantiating a second engine silently fences out the first.

#### [BUG-13] Non-Deterministic `hash()` Event IDs & Date-Less `HH:MM:SS` Event Timestamps
- **Locations**: [src/intelligence/macro_commander.py](file:///c:/Users/will0/Dropbox/TradeBot0/src/intelligence/macro_commander.py#L822), [src/intelligence/macro_commander.py](file:///c:/Users/will0/Dropbox/TradeBot0/src/intelligence/macro_commander.py#L830), [src/gui/assets/app.js](file:///c:/Users/will0/Dropbox/TradeBot0/src/gui/assets/app.js#L3478)
- **Details**: `evt_id = f"evt_{int(now)}_{abs(hash(dedup_key)) % 10000}"` relies on Python's per-process salted `hash()` modulo 10,000, creating collision risk within the same second and unstable IDs across restarts. Event `"time"` stores only `HH:MM:SS` without date context.

#### [BUG-14] JS UI Falsy Confidence Coercion & Hardcoded `'Pure Math Core'` Pill
- **Locations**: [src/gui/assets/app.js](file:///c:/Users/will0/Dropbox/TradeBot0/src/gui/assets/app.js#L1457-L1462), [src/gui/assets/app.js](file:///c:/Users/will0/Dropbox/TradeBot0/src/gui/assets/app.js#L3841)
- **Details**:
  - `Number(macro.confidence || 0.8)` turns an explicit `0.0` confidence (e.g., offline / uncertain fallback) into `80%`. Use `macro.confidence != null ? Number(macro.confidence) : 0.8`.
  - `omniSourceBadge` always sets `srcEl.textContent = 'Pure Math Core'` statically instead of reflecting OmniRoute vs local core status (`state.quant_meta.source` or `mc.status`).

---

### 2.3 Low-Severity / Stale Labels / Incomplete Scaffolding

#### [BUG-15] Stale `"6 Strategies"`, `"$600,000"`, and `"Inst. VWAP"` Nomenclature Across UI & LLM Prompt
- **Locations**: [src/gui/assets/index.html](file:///c:/Users/will0/Dropbox/TradeBot0/src/gui/assets/index.html#L60), [src/gui/assets/index.html](file:///c:/Users/will0/Dropbox/TradeBot0/src/gui/assets/index.html#L126), [src/gui/assets/index.html](file:///c:/Users/will0/Dropbox/TradeBot0/src/gui/assets/index.html#L542), [src/gui/assets/app.js](file:///c:/Users/will0/Dropbox/TradeBot0/src/gui/assets/app.js#L47), [src/gui/assets/app.js](file:///c:/Users/will0/Dropbox/TradeBot0/src/gui/assets/app.js#L56), [src/gui/assets/app.js](file:///c:/Users/will0/Dropbox/TradeBot0/src/gui/assets/app.js#L1333), [src/gui/assets/app.js](file:///c:/Users/will0/Dropbox/TradeBot0/src/gui/assets/app.js#L1583), [src/gui/assets/app.js](file:///c:/Users/will0/Dropbox/TradeBot0/src/gui/assets/app.js#L3255), [src/intelligence/macro_commander.py](file:///c:/Users/will0/Dropbox/TradeBot0/src/intelligence/macro_commander.py#L869)
- **Details**:
  - HTML & JS still show `6 Strategy Ledgers ($100,000 U x 6)`, `$600,000 Arena Pool`, `6 Parallel Competitors`, and `\u7b56\u7565\u653e\u884c: 6\u5927\u7b56\u7565...`, while `MacroCommander` sends `"governing a 6-strategy crypto trading arena"` to the LLM despite only 5 competitors ($500,000 total pool) existing.
  - Backend explicitly rebranded `comp_vwap` to `"Session Mean"` / `"MEAN"` (because live 1m bars lack volume), yet `app.js` still maps `'comp_vwap'` to `'Inst. VWAP'`, `'Institutional VWAP'`, and `'VWAP'` at lines `428, 588, 732, 1583, 1836, 1956-1959, 2361`.

#### [BUG-16] Hardcoded Fake News Catalyst & Entity-Escape Circumvention of Zero-CJK Policy
- **Locations**: [src/gui/assets/index.html](file:///c:/Users/will0/Dropbox/TradeBot0/src/gui/assets/index.html#L356-L362), [src/gui/assets/app.js](file:///c:/Users/will0/Dropbox/TradeBot0/src/gui/assets/app.js#L1258-L1335), [tests/test_performance_and_optimizations.py](file:///c:/Users/will0/Dropbox/TradeBot0/tests/test_performance_and_optimizations.py#L16-L23)
- **Details**: Static `index.html` ships a fabricated placeholder news item (`以太坊現貨 ETF 淨流入大幅激增... 單日吸資達 2.5 億美元`, `CoinDesk · Live`), encoded as **111 HTML numeric CJK entities** (`&#x...;`), alongside **132 `\u4e00-\u9fff` Unicode escapes** in `app.js`. While literal CJK count is `0` (passing `test_zero_cjk_in_frontend_assets`), it violates the zero-CJK intent and harms maintainability.

#### [BUG-17] Dead Bridge Wrapper `save_session_state` & Unwired `update_checker.py`
- **Locations**: [tests/test_ui_contract.py](file:///c:/Users/will0/Dropbox/TradeBot0/tests/test_ui_contract.py#L51-L71), [src/update_checker.py](file:///c:/Users/will0/Dropbox/TradeBot0/src/update_checker.py#L37-L51), [src/gui/dashboard.py](file:///c:/Users/will0/Dropbox/TradeBot0/src/gui/dashboard.py#L734-L742)
- **Details**: `_ArenaBridgeApi.save_session_state` has zero callers anywhere in JS or Python (only preserved via `KNOWN_DEAD_BRIDGE_METHODS`), and `check_for_updates` / `update_checker.py` has no manifest URL, no download/install flow, and no UI banner because the upstream GitHub account is noted as suspended (`src/update_checker.py:40`). Also note `main.py --self-test` (`main.py:72-86`) exits without calling `app.stop()` to close the persistent SQLite handle cleanly.

---

## 3. Architecture, Performance & Code Optimizations

### 3.1 Decompose the `LiveArenaEngine` Monolith (`2,783` lines / `64` methods)
- `src/data/live_engine.py` accounts for **21.0% of all `src/` Python lines** (`2,783 / 13,236`), with graph node degree `140` (`LiveArenaEngine`) + `74` (`live_engine.py`). Milestone 6 of `OptimizationFullGuide.md` targeted `<500` lines and marked itself done, yet HTTP REST quote fetching, WebSocket integration, historical Yahoo/CCXT bootstrap, technical indicator smoothing, 1m candle synthesis, 5 inline strategy evaluators, 4-gate entry filtering, Monte Carlo gating, fill harvesting, SQLite autosave, evolution scheduling, and double-buffered snapshot building all remain coupled in one class.
- **Optimization**: Split into focused collaborators: `QuoteFeedService`, `LiveIndicatorTracker`, `LiveStrategyRunner` (calling strategy `evaluate_signal` directly), and `EngineSnapshotCoordinator`.

### 3.2 Narrow `self.lock` Scope & Fix Cadence Doc Drift
- `LiveArenaEngine._live_loop` (`live_engine.py:1898-2020`) holds `self.lock` (`RLock`) for the entire cadence cycle—including `_harvest_fills` SQLite disk I/O, up to 5 calls to 500-path Monte Carlo simulation (`mc_evaluator.evaluate_bracket`), `evolve_now()`, and `_build_snapshot_locked()`. Meanwhile `get_ui_state()` still calls `copy.deepcopy(snap)` at 1 Hz (though `get_ui_state_delta()` avoids deepcopying unchanged `candles`/`fills`).
- Also resolve internal cadence comment drift: comments at `live_engine.py:1960, 2000, 2032` and `live_engine.py:1540` say `"5-second"`, `self.interval_sec` initializes to `1.5`, while `start_live_loop(interval_sec=1.0)` actually ticks every `1.0s`.
- **Optimization**: Copy immutable tick/bar state under lock, run SQLite I/O and Monte Carlo outside `self.lock`, and unify cadence constants.

### 3.3 Improve Monte Carlo EV Gate Realism (`timemachine.py:454-485`)
- `MonteCarloOddsEvaluator.evaluate_bracket` currently draws **i.i.d. normal log-returns** (`np.random.normal`), clamps `sigma` cleanly between `[0.0006, 0.008]`, checks hits only at discrete 1-minute close steps (missing intra-bar wicks that trigger stop-losses in `BrokerSim.on_tick`), and substitutes a hardcoded `UNCAPPED_RUNNER_R_MULTIPLE = 1.8` (`timemachine.py:435, 448`) for `comp_agg` and `comp_trail`.
- **Optimization**: Sample Student-t / empirical block-bootstrapped intraday 1m returns from the 120-bar window, include brownian-bridge / intra-bar high-low hit probability adjustment, and simulate trailing stop ratcheting instead of fixed `1.8R` for trailing/runner strategies.

### 3.4 Frontend Rendering, CSS Compositor & Code Structure (`app.css` 5,743L, `app.js` 4,721L)
- Despite `V2.8.7` DOM write guards, `src/gui/assets/app.css` still triggers expensive software/GPU compositing during animations: **22** `backdrop-filter` declarations, **22** `filter: blur(...)` declarations, **34** `animation` properties across **25** `@keyframes`, including **`filter: blur(8px) -> blur(0)` animated per-frame inside `@keyframes toastSpringIn` and `toastSpringOut`** (`app.css:2250-2274`). Animating `filter: blur()` invalidates texture caches every frame inside Edge WebView2.
- `app.js` (184.7 KB, single global-heavy script) has **34 `.innerHTML =` assignments** and mixes canvas rendering, delta diffing, wizard flows, toast timers, and Intel Hub cards in one 4,721-line file.
- **Optimization**: Remove `filter: blur(...)` from `@keyframes toastSpringIn`/`toastSpringOut` (animate only `opacity` + `transform: translate3d/scale`), consolidate strategy display metadata from a single backend-driven config payload (eliminating stale JS name maps), and split `app.js` into ES modules (`chart.js`, `intel.js`, `wizard.js`, `state.js`).

### 3.5 Exception Handling & Telemetry Cleanliness
- AST scan across `src/` + `main.py` found **`15` silent `except Exception: pass` blocks** (`7` in `src/intelligence/omniroute_client.py`, `3` in `main.py`, `2` in `src/data/persistence.py`, `1` each in `src/intelligence/ingestion.py`, `src/intelligence/gateway_supervisor.py`, and `src/logging_setup.py`). Log debug context or narrow exception types inside `omniroute_client.py` (especially around response parsing/header extraction).
- Similarly, `MacroCommander.get_intel_hub_telemetry` (`macro_commander.py:452`) and `view_model.py:304` always emit `tokens_saved = 0`, while `app.js:3767` still renders `"X used / 0 saved"`—omit `"saved"` or display deduplication hits directly in the main metric.

---

## 4. Documentation, Packaging & Developer Experience (DX) Gaps

| Area | Verified Discrepancy / Risk | Actionable Fix |
| :--- | :--- | :--- |
| **`README.md` vs Code** | Line 1–3 claims **`BTC/USD`** ("在即時 BTC/USD 行情下競賽淨值"), while every engine, WebSocket (`ethusdt@ticker`), REST cascade, SQLite table, backtest CLI (`ETH-USD`), and UI header runs **ETH/USD**. Line 5 links GitHub Releases download URL even though `src/update_checker.py:40` notes GitHub account suspension. | Update `README.md` hero/architecture sections to **ETH/USD** and update download/hosting URL once finalized. |
| **`OptimizationFullGuide.md`** | Still depicts **6 Competitors**, **$600,000** baseline references, `73/73 tests`, and checks off `live_engine.py <500 lines` (actually 2,783 lines). | Archive or update status markers to match `V1.0.0` reality (`5` competitors, `604` tests). |
| **Dropbox `.venv` & DLL Trap** | `.venv\pyvenv.cfg` hardcodes old pre-move path `C:\Users\will0\TradeBot0\.venv`, causing `.venv\Scripts\pytest.exe` and `graphify.exe` to exit `1` silently. Worse, **~15,437 files in `.venv\Lib\site-packages`** and `src\compat\win7\api-ms-win-core-path-l1-1-0.dll` carried Dropbox Cloud-Only (`Offline`) attributes, causing cold imports (`yfinance`) to stall for **219s**. Running PyInstaller while `api-ms-win-core-path-l1-1-0.dll` is dehydrated risks build hangs or corrupt bundling. | Exclude `.venv/` from Dropbox sync (or recreate `.venv` in `%LOCALAPPDATA%`), hydrate/pin `src/compat/win7/` local before `build_exe.ps1`, and recreate venv shims cleanly. |
| **Stale/Noisy `graphify-out/`** | Built at old commit `6852ed05` (behind `876f2bc`). Out of **3,452** nodes, **2,108 (61.1%)** come from `.agent/` skill templates and **115** from deleted `scratch/` patch scripts (`fix_item2_patch.py`, etc.). | Add `.graphifyignore` excluding `.agent/**` and `scratch/**`, then run `.\.venv\Scripts\python.exe -m graphify update .` when editing code. |
| **`.gitignore` & Orphan Cache Files** | `.gitignore` omits `data/*.db*` (though `data/arena_history.db` is currently untracked in git), `memory/arena_history.json` holds `21,370` lines of legacy `comp_atr` JSON history, and `src\competitors\__pycache__\atr_dynamic.cpython-312.pyc` lingers from deleted code. | Add `data/*.db*` to `.gitignore`, clean stale `__pycache__/*.pyc`, and prune/archive `memory/arena_history.json` once SQLite history is canonical. |
