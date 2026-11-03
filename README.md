# TradeBot0: Multi-Agent Paper Trading & Genetic Evolution Arena (BTC/USD)

Industrial-grade quantitative multi-strategy paper trading and genetic evolution desk for BTC/USD. Features precision intra-bar order matching, cross-generation parameter evolution, strategy-specific active leverage, maintenance margin liquidation protection, zero-drift Decimal portfolio accounting, resilient multi-exchange ticker ingestion, and an obsidian high-contrast desktop GUI powered by DirectX 11 WebView2.

---

## Architectural Highlights

1. **Intra-Bar Matching & Precision Accounting (`BrokerSim` & `Portfolio`)**:
   - **True Price-Trigger Execution**: Replaces naive bar-close assumptions with realistic intra-bar tick matching. Stop-loss triggers at touch (`low <= stop_loss`) with adverse slippage, while take-profit orders fill via limit mechanics (`high >= take_profit`) without adverse execution drag.
   - **Strategy-Specific Leverage & Margin Accounting**: Supports autonomous strategy leverage (up to 3.0x), margin reservation, margin release on close, and automated maintenance margin liquidation protection if equity drops below 10% of margin locked.
   - **Intra-Bar Peak-to-Trough Drawdown**: Real-time tracking of extreme wick excursions throughout open position lifecycles.
   - **Annualized Risk Metrics**: Real-time Sharpe, Sortino (downside volatility only), and Profit Factor computed on true traded intervals without flat-cash distortion.

2. **Style B: Genetic Parameter Tournament (`GeneticEvolver` & `CompetitorGenome`)**:
   - Six distinct \$100,000 baseline portfolios compete simultaneously: Aggressive Momentum (3x Lev), Conservative Scalper (Spot 1x), ATR Volatility Adaptive (2x Lev), Trailing Profit Guard (2x Lev), ORB Breakout (2.5x Lev), and Institutional VWAP (Spot 1x).
   - **Elitism + Crossover & Mutation**: After each competition cycle, a unified Fitness Score selects the top 2 elite genomes to survive, while the lower ranks undergo crossover and bounded Gaussian mutation (`G1 -> G2 -> G3`), logged into `memory/arena_history.json`.

3. **Multi-Exchange Live Ingestion & Adaptive Fast Failover (`LiveArenaEngine`)**:
   - High-speed real-time quotes across Binance (`BTCUSDT`), Kraken (`XBTUSD`), and Coinbase Exchange (`BTC-USD`) with adaptive provider circuit-breaking and preferred ranking.
   - Resilient in-memory caching ensures zero interruption during transient network hiccups.

4. **Deterministic Pure-Math Quant Core & Monte Carlo EV Gating**:
   - Zero external AI socket or token quota dependencies; 100% offline-capable mathematical core.
   - Evaluates each bracket setup across 10,000 synthetic paths before placing orders, strictly blocking negative expectation entries.

5. **Obsidian High-Contrast Quant Terminal (`Edge WebView2 DirectX 11`)**:
   - Native GPU-accelerated desktop workstation adhering to professional dark quant terminal aesthetics (`#08090C` background, high-contrast palette).
   - Interactive 1-minute Candlestick with kinetic smooth slide and Trend Line vector chart with strategy bracket limits, radar beacons, and real-time execution tape.

---

## Quick Start Guide

### 1. Launch Packaged Desktop Executable (`.exe`)
Run the standalone pre-packaged Windows binary directly:
```powershell
dist\TradeBot0_Arena.exe
```
> **Note on Windows SmartScreen**: Because `dist\TradeBot0_Arena.exe` is a self-packaged unsigned binary, Windows SmartScreen may show a one-time "Windows protected your PC" dialog on first launch. Click **More info** -> **Run anyway**.

Or run via the Python virtual environment:
```powershell
.venv\Scripts\python.exe main.py
```

### 2. Run Self-Test Verification
```powershell
.venv\Scripts\python.exe main.py --self-test
```
or with the packaged executable:
```powershell
dist\TradeBot0_Arena.exe --self-test
```

### 3. Run Automated Unit Test Suite (32 Tests)
```powershell
.venv\Scripts\pytest.exe -q tests
```

### 4. Build Standalone Windows Executable
```powershell
powershell -ExecutionPolicy Bypass -File build_exe.ps1
```
