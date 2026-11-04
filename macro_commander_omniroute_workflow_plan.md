# Macro Commander & OmniRoute Intelligence Ingestion Workflow Plan (Updated v2 - Approved, 5 Refinements Integrated)

> **Objective:** 
> 1. Fix the **candlestick chart pacing issue**, replacing bursty API rendering with a **paced 3~5 second time-sliced cadence dispatcher** for smooth visualization.
> 2. Ensure the **Right-Side Strategy Leaderboard is ranked strictly by Total Equity** in descending order (highest net worth is #1).
> 3. Integrate a **real, fully functional OmniRoute gateway connection layer** (`http://localhost:20128/v1`) with high-throughput multi-domain intelligence ingestion (Tier 0–3 feeds across WebSockets, Polymarket, RSS, SEC filings, Reddit, Macro feeds, Semiconductor/AI supply chain, Geopolitics/Maritime).
> 4. Implement the **Macro Commander with Strict Veto (Option A)** directly governing all 6 arena competitors (`Aggressive`, `Conservative`, `ATR Dynamic`, `Trailing Guard`, `ORB Breakout`, `VWAP Pullback`).
> 5. Ensure **every phase** contains dedicated **Debug & Optimize** checkpoints to eliminate logic errors, mocks, and hallucinations.
6. Incorporate the **5 approved architectural refinements (R1-R5)** listed below into Phases 1-4 before implementation begins.

---

## Approved Architectural Refinements (R1-R5)

Each refinement is tagged **[R1]** to **[R5]** inside the affected tasks and checkpoint tests below.

| ID | Phase / Task | Refinement | Key Requirement |
|----|--------------|------------|-----------------|
| **R1** | Phase 1 / Task 1.1 | Micro-Bar OHLCV Aggregation in `CandleCadenceDispatcher` | Aggregate ticks per 3.0s/5.0s slice (`Open` = first, `High` = max, `Low` = min, `Close` = latest, `Volume` = sum). Never discard intermediate highs/lows, so wick extremes reach ATR/ORB strategies with zero lag. |
| **R2** | Phase 2 / Task 2.2 | Resilient JSON Extraction for OmniRoute Models | In `omniroute_client.py`, strip `<think>...</think>` blocks and Markdown code fences, then extract the outermost `{...}` object before `json.loads()`. |
| **R3** | Phase 3 / Task 3.1 | Retain Semiconductor, Tech & Geopolitical Feeds | Feed registry explicitly includes Semiconductor/AI Supply Chain feeds (SemiAnalysis, TrendForce, DigiTimes, TechNews) and Geopolitics/War/Maritime Chokepoint feeds (ISW, The War Zone, Liveuamap, gCaptain), alongside Tree News, Polymarket, SEC EDGAR, Reddit, and Macro feeds. |
| **R4** | Phase 3 / Task 3.3 | Stage 2 Interrupt Debouncing (Anti-Interrupt Storm) | 10-second debounce/cooldown on the out-of-band interrupt, so simultaneous `urgency_score >= 8` items from different sources are batched into a single `MacroCommander` synthesis call instead of parallel redundant calls. |
| **R5** | Phase 4 / Task 4.2 | Complete `HOLD_CASH` Veto Enforcement | When `directional_bias == "HOLD_CASH"`, veto ALL new LONG and SHORT entries across all 6 competitors (`VETO_MACRO_HOLD_CASH`); only exits / stop-losses may execute. |

---

## Architecture Overview

```
                      【OmniRoute Gateway】
                    http://localhost:20128/v1
                               ▲
                               │ OpenAI-compatible API
┌──────────────────────────────┴──────────────────────────────┐
│  src/intelligence/omniroute_client.py (Real, No Mocks)      │
│  • Concurrency: 25 requests | Timeout: 60s | Max Retries: 5 │
│  • Models: LLM_MODEL_INGEST (Fast) & LLM_MODEL_COMMANDER    │
│  • Defensive JSON Parser: strips <think> & code fences,     │
│    then extracts outermost {...} before json.loads()        │
└──────────────────────────────▲──────────────────────────────┘
                               │
┌──────────────────────────────┴──────────────────────────────┐
│  src/intelligence/ingestion.py                              │
│  • Tier 0: Tree News WebSocket (wss://news.treeofalpha.com) │
│  • Tier 1: Polymarket, Breaking RSS, SEC EDGAR 8-K,         │
│            Geopolitics (ISW, War Zone, Liveuamap, gCaptain) │
│  • Tier 2: Crypto (CryptoPanic, CoinDesk), Reddit, Semis/AI │
│            (SemiAnalysis, TrendForce, DigiTimes, TechNews)  │
│  • Tier 3: FRED, US Treasury, Central Banks                 │
│  • In-Memory Deduplication: SHA-256 Title+URL Ring Buffer   │
│  • Interrupt Debounce: 10s cooldown (batched urgency >= 8)  │
└──────────────────────────────┬──────────────────────────────┘
                               │ Structured Events (Urgency >= 8 -> 10s-debounced sync)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│  src/intelligence/macro_commander.py (The Brain)            │
│  • Synthesizes MacroRegimeState (1-3m / debounced interrupt)│
│  • Directional Bias: LONG_ONLY | SHORT_ONLY | BIDIRECTIONAL │
│    | HOLD_CASH (vetoes ALL new entries; exits still allowed)│
│  • Risk Multiplier: 0.5x ~ 1.5x (De-leverage on shock)      │
└──────────────────────────────┬──────────────────────────────┘
                               │ Global Macro Regime State
                               ▼
┌─────────────────────────────────────────────────────────────┐
│  src/data/live_engine.py & src/arena/leaderboard.py         │
│  • Strict Veto Gate: Intercepts all 6 competitors' orders   │
│  • When LONG_ONLY: Blocks all SHORT orders                  │
│  • When SHORT_ONLY: Blocks all LONG orders                  │
│  • When HOLD_CASH: Blocks ALL new LONG & SHORT entries      │
│    (exits / stop-losses always execute)                     │
│  • Leaderboard: Ranked strictly by Total Equity (Descending)│
│  • CandleCadenceDispatcher: 3s/5s OHLCV Micro-Bar Stream    │
└──────────────────────────────┬──────────────────────────────┘
                               │ Paced 3~5s UI State Stream
                               ▼
┌─────────────────────────────────────────────────────────────┐
│  Frontend Dashboard (Web UI & Standalone .exe)              │
│  • Paced Candlestick Chart: Steady 3s/5s cadence (No Jitter)│
│  • Strategy Rankings: Ranked strictly by Total Equity       │
│  • Top Macro Ticker: Live Regime, Bias, Headline, Confidence│
│  • 0 CJK Characters in app.js, app.css, index.html          │
└─────────────────────────────────────────────────────────────┘
```

---

## Detailed Execution Phases & Tasks

### Phase 1: Paced 3~5s Candlestick Cadence Dispatcher & Equity-Ranked Leaderboard
*Address the fluctuating "bursty" chart updates and re-align strategy rankings to Total Equity.*

- [ ] **Task 1.1: Backend Cadence Buffer with Micro-Bar OHLCV Aggregation (`CandleCadenceDispatcher`)**
  - Implement a dedicated temporal queue in `src/data/live_engine.py` that buffers incoming raw market ticks/bars from the external API.
  - Slices and releases updates at a strictly metered heartbeat interval (configurable: default **3.0 seconds**, option **5.0 seconds**).
  - Ensures that even when external APIs burst or experience brief jitter, the output to the engine state and UI is evenly spaced and predictable.
  - **[R1] Micro-Bar OHLCV Aggregation (no naive "latest-quote compression"):** When compressing rapid incoming ticks inside each 3.0s/5.0s cadence window, do **NOT** simply discard intermediate highs and lows. Aggregate every tick received within a slice into one micro-bar:
    - `Open` = price of the **first** tick in the slice
    - `High` = **max** price in the slice
    - `Low` = **min** price in the slice
    - `Close` = price of the **latest** tick in the slice
    - `Volume` = **sum** of tick volume in the slice
  - Wick extremes are therefore preserved for ATR / ORB strategies with **zero lag**, while the emitted cadence to the engine state and UI stays evenly spaced.
- [ ] **Task 1.2: Frontend Kinetic Interpolation Alignment**
  - Adjust `src/gui/assets/app.js` polling interval and transition parameters to perfectly synchronize with the 3s/5s dispatch rate.
  - Smooth out the horizontal sliding animation so that each candle transition moves with uniform velocity, avoiding sudden accelerations or stalls.
- [ ] **Task 1.3: Strategy Leaderboard Ranked Strictly by Total Equity**
  - Update `src/arena/leaderboard.py` (`Leaderboard.get_rankings`):
    - Primary sort key: `s.equity` (Total Equity, descending: highest equity = Rank #1).
    - Secondary sort keys: `s.status == "ACTIVE"`, `s.roi_pct`.
  - Update `src/gui/assets/app.js` table rendering to guarantee that card animations, position rank badges, and table rows are sorted strictly by `total_equity` (or `rank` which reflects total equity).
- [ ] **Task 1.4: Debug & Optimize (Phase 1 Checkpoint)**
  - **Cadence Jitter Test:** Verify candle emission intervals stay within $\pm 50\text{ ms}$ of target cadence under synthetic burst conditions.
  - **Micro-Bar OHLCV Aggregation Test [R1]:** Feed a synthetic tick burst containing an intermediate spike high and an intermediate flush low inside a single slice. Assert `Open` = first, `High` = max, `Low` = min, `Close` = last, `Volume` = sum exactly, that the intermediate extremes are never dropped, and that ATR/ORB inputs see the wick extremes with zero added lag.
  - **Equity Ranking Validation Test:** Unit test comparing 6 competitor portfolios with varying equities (e.g. \$110,000, \$104,500, \$98,000) to confirm rank 1 through 6 strictly mirrors Total Equity descending.
  - **Code Quality & 0 CJK Verification:** Confirm `app.js` adheres strictly to English/ASCII code standards.

---

### Phase 2: Real OmniRoute Gateway Connection Layer
*Implement genuine, production-grade connection to `http://localhost:20128/v1` with zero fake stubs.*

- [ ] **Task 2.1: OpenAI-Compatible Asynchronous Client (`src/intelligence/omniroute_client.py`)**
  - Connect to `http://localhost:20128/v1` using standard `POST /v1/chat/completions`.
  - Read environment variables (`LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL_INGEST`, `LLM_MODEL_COMMANDER`).
  - Implement concurrent request limiter (`asyncio.Semaphore(25)`).
- [ ] **Task 2.2: Resilient Fallback, Exponential Jitter Backoff & Defensive JSON Extraction**
  - Implement retry logic (max 5 retries) with randomized exponential jitter backoff (`0.5s` $\rightarrow$ `1.0s` $\rightarrow$ `2.0s`) for HTTP 429/502/503.
  - Implement offline safe mode: if the local OmniRoute gateway is not running, log graceful diagnostic warnings and default to safe `NEUTRAL` macro state without crashing the trading engine.
  - **[R2] Resilient JSON Extraction for OmniRoute Models:** OmniRoute routes across diverse upstream providers (including reasoning models such as DeepSeek-R1 / Qwen and free tiers), so raw responses may carry reasoning traces or formatting wrappers. Implement a defensive JSON parser in `omniroute_client.py` that, **before** calling `json.loads()`:
    1. Strips `<think>...</think>` blocks
    2. Strips Markdown code fences (`` ```json ... ``` ``)
    3. Extracts the outermost `{...}` object
  - If no valid object can be extracted, log a diagnostic warning and degrade gracefully (skip the event / fall back to the safe `NEUTRAL` state) without raising into the trading engine.
- [ ] **Task 2.3: Debug & Optimize (Phase 2 Checkpoint)**
  - **Unit Test Suite:** Test HTTP 200, 429 rate limit, 503 gateway error, and gateway unreachable scenarios.
  - **Real Payload Validation:** Test real prompt structure and ensure JSON parsing handles malformed responses cleanly.
  - **Defensive JSON Extraction Test [R2]:** Cover `<think>` blocks (including braces inside the reasoning text), fenced `` ```json `` output, prose-wrapped JSON, nested objects, and truncated/malformed output (must fall back cleanly).
  - **Memory & Resource Leak Check:** Verify persistent `aiohttp.ClientSession` lifecycle is properly closed upon engine shutdown.

---

### Phase 3: Multi-Domain Intelligence Ingestion Pipeline
*Ingest real-time multi-source data according to the specification with two-stage processing.*

- [ ] **Task 3.1: Ingestion Feeds Collector (`src/intelligence/ingestion.py`)**
  - **Tier 0:** Tree News WebSocket (`wss://news.treeofalpha.com/ws`) for sub-second breaking tape.
  - **Tier 1 (30–60s):** Polymarket Gamma API (macro event delta tracking $\Delta P > 5\%$), Breaking News RSS (ForexLive, MarketWatch, CNBC), SEC EDGAR 8-K Atom feed, **Geopolitics / War / Maritime Chokepoint feeds** (ISW, The War Zone, Liveuamap, gCaptain) **[R3]**.
  - **Tier 2 (3–5m):** Crypto feeds (CryptoPanic, CoinDesk, CoinTelegraph), Reddit (`r/wallstreetbets`, `r/CryptoCurrency`, `r/stocks` via JSON/RSS), **Semiconductor / AI Supply Chain feeds** (SemiAnalysis, TrendForce, DigiTimes, TechNews) **[R3]**.
  - **Tier 3 (15–30m):** FRED, US Treasury, Global Central Banks.
  - **[R3] Retain Semiconductor, Tech & Geopolitical Feeds:** `ingestion.py` must NOT be limited to crypto/finance feeds. The feed registry explicitly includes:
    - **Semiconductor / AI Supply Chain:** SemiAnalysis, TrendForce, DigiTimes, TechNews
    - **Geopolitics / War / Maritime Chokepoints:** ISW, The War Zone, Liveuamap, gCaptain
    - ...alongside Tree News, Polymarket, SEC EDGAR, Reddit, and Macro feeds.
    - Default polling tier (adjustable per feed in the registry): breaking geopolitical wires in Tier 1, Semiconductor/AI analysis feeds in Tier 2.
- [ ] **Task 3.2: High-Performance In-Memory Deduplication**
  - Use a SHA-256 Title+URL hash ring buffer (capacity: 5,000 items) to guarantee zero duplicate LLM token consumption.
- [ ] **Task 3.3: Stage 1 Harvester Worker**
  - Concurrently batch-process incoming text using `LLM_MODEL_INGEST` to extract structured event objects:
    ```json
    {
      "timestamp": "ISO8601",
      "source": "string",
      "domain": "string",
      "entities_tickers": ["BTC", "FED"],
      "urgency_score": 1_to_10,
      "sentiment_score": -1.0_to_1.0,
      "summary": "string"
    }
    ```
  - If `urgency_score >= 8`, emit an out-of-band interrupt signal to trigger Stage 2 Macro Commander re-evaluation (subject to the R4 debounce below).
  - **[R4] Stage 2 Interrupt Debouncing (Anti-Interrupt Storm):** Multiple breaking items with `urgency_score >= 8` can arrive simultaneously from different sources and bypass the SHA-256 Title+URL deduplication. Enforce a **10-second debounce / cooldown window** on the out-of-band interrupt signal so consecutive high-urgency events are **batched into a single `MacroCommander` synthesis call** rather than triggering parallel redundant calls.
    - Mechanism (planning default): the first qualifying event outside an active window dispatches immediately and opens the 10s window; qualifying events arriving inside the window are queued and merged into one batched synthesis call when the window closes. Synthesis calls never run in parallel.
    - An isolated high-urgency event outside any window keeps the < 500 ms interrupt latency target.
- [ ] **Task 3.4: Debug & Optimize (Phase 3 Checkpoint)**
  - **Feed Connection Diagnostic Test:** Verify each feed handler gracefully tolerates network timeouts, 403 blocks (custom User-Agent validation for Reddit/SEC), and malformed XML/JSON.
  - **Feed Registry Completeness Test [R3]:** Assert the registry contains SemiAnalysis, TrendForce, DigiTimes, TechNews, ISW, The War Zone, Liveuamap, and gCaptain, alongside Tree News, Polymarket, SEC EDGAR, Reddit, and Macro feeds.
  - **Throughput & Deduplication Benchmark:** Verify duplicate feed items are filtered out in $< 0.1\text{ ms}$.
  - **Interrupt Latency Test:** Verify an isolated high-urgency event (outside an active debounce window) triggers downstream evaluation within $< 500\text{ ms}$.
  - **Interrupt Debounce Test [R4]:** Simulate a burst of 10+ distinct `urgency_score >= 8` events (different sources, titles and URLs) inside a 10s window. Assert no parallel `MacroCommander` calls, that the burst is batched into a single synthesis call, and that a new window opens correctly after the cooldown expires.

---

### Phase 4: Macro Commander with Strict Veto (Option A)
*Deploy the overarching military commander over all 6 competitors.*

- [ ] **Task 4.1: Macro Synthesis Engine (`src/intelligence/macro_commander.py`)**
  - Aggregate Stage 1 event stream into a comprehensive Macro Regime prompt for `LLM_MODEL_COMMANDER`.
  - Maintain the authoritative `MacroRegimeState`:
    - `regime`: `BULLISH_SURGE` | `BEARISH_PANIC` | `HIGH_VOLATILITY_CHOP` | `NORMAL`
    - `directional_bias`: `LONG_ONLY` | `SHORT_ONLY` | `BIDIRECTIONAL` | `HOLD_CASH`
    - `risk_multiplier`: Float between `0.5` and `1.5`
    - `active_headline`: Concise headline driving the regime
    - `confidence`: Float between `0.0` and `1.0`
- [ ] **Task 4.2: Strict Veto Integration in `LiveArenaEngine`**
  - Hook into `_evaluate_live_strategies()`:
    - **Long-Only Veto:** If `directional_bias == "LONG_ONLY"`, any competitor signal to open a SHORT position is **immediately blocked with a veto record** (`VETO_MACRO_LONG_ONLY`).
    - **Short-Only Veto:** If `directional_bias == "SHORT_ONLY"`, any competitor signal to open a LONG position is **immediately blocked**.
    - **[R5] Hold-Cash Veto:** If `directional_bias == "HOLD_CASH"`, **ALL** new LONG and SHORT entry signals across **all 6 competitors** are vetoed (`VETO_MACRO_HOLD_CASH`). Only position exits / stop-losses are allowed to execute.
    - **De-leverage Protection:** If `regime == "HIGH_VOLATILITY_CHOP"` or `risk_multiplier < 1.0`, reduce all competitors' active position size and leverage cap.
    - **Trend Expansion:** If `directional_bias == "LONG_ONLY"` and a LONG trade passes, dynamically scale take-profit target (e.g. from 2R to 3.5R).
- [ ] **Task 4.3: Debug & Optimize (Phase 4 Checkpoint)**
  - **Veto Enforcement Unit Tests:**
    - Verify that all 6 competitors (`Aggressive`, `Conservative`, `ATR`, `Trailing Guard`, `ORB`, `VWAP`) have their counter-trend trades strictly vetoed.
    - Verify that compliant trades pass through and execute normally with correct position sizing.
    - **HOLD_CASH Veto Test [R5]:** With `directional_bias == "HOLD_CASH"`, verify every new LONG and SHORT entry from all 6 competitors is vetoed (`VETO_MACRO_HOLD_CASH`), while exits / stop-losses on existing positions still execute.
  - **Audit Logging Verification:** Verify every veto event (including `VETO_MACRO_HOLD_CASH`) is recorded in the execution log with timestamp, competitor name, and driving headline.

---

### Phase 5: UI Macro Ticker & End-to-End Validation
*Deliver full visual visibility and ensure zero regression across the standalone app.*

- [ ] **Task 5.1: State API Payload Enrichment (`src/gui/dashboard.py`)**
  - Expose `macro_commander` state in the `/api/state` response:
    - `status` (`ONLINE` / `CONNECTING` / `OFFLINE`)
    - `regime`, `directional_bias`, `risk_multiplier`, `confidence`
    - `headline`, `last_updated_ts`, `veto_count_today`
- [ ] **Task 5.2: Frontend Macro Command Ribbon (`src/gui/assets/app.js` & `app.css`)**
  - Add a sleek, futuristic top status pill/ribbon in the UI header displaying:
    `[MACRO: BULLISH SURGE] Bias: LONG ONLY | Multiplier: 1.2x | OmniRoute: Active (24/7) | "US Election: Crypto Surge"`
  - Enforce strictly **0 CJK characters** in all frontend files.
- [ ] **Task 5.3: Debug & Optimize (Phase 5 Checkpoint & Final Regression)**
  - **Full Pytest Suite:** Run all existing tests + newly added tests (target: 100% pass).
  - **Frontend CJK Audit:** Run python CJK detector across `index.html`, `app.js`, and `app.css`.
  - **Standalone Executable Compilation:** Re-compile `dist/TradeBot0_Arena.exe` via `build_exe.ps1` and run `--self-test` to guarantee binary integrity.
