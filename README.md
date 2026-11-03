# TradeBot0: Multi-Agent Paper Trading & Genetic Evolution Arena (ETH/USD)

Industrial-grade quantitative multi-strategy paper trading and genetic evolution desk for ETH/USD. Features precision intra-bar order matching, cross-generation parameter evolution, zero-drift Decimal portfolio accounting, resilient multi-exchange ticker ingestion, and an obsidian high-contrast desktop GUI powered by DirectX 11 WebView2.

---

## Architectural Highlights

1. **Intra-Bar Matching & Precision Accounting (`BrokerSim` & `Portfolio`)**:
   - **True Price-Trigger Execution**: Replaces naive bar-close assumptions with realistic intra-bar tick matching. Stop-loss triggers at touch (`low <= stop_loss`) with adverse slippage, while take-profit orders fill via limit mechanics (`high >= take_profit`) without adverse execution drag.
   - **Intra-Bar Peak-to-Trough Drawdown**: Real-time tracking of extreme wick excursions throughout open position lifecycles.
   - **Annualized Risk Metrics**: Real-time Sharpe, Sortino (downside volatility only), and Profit Factor computed on true traded intervals without flat-cash distortion.

2. **Style B: Genetic Parameter Tournament (`GeneticEvolver` & `CompetitorGenome`)**:
   - Four distinct \$3,000 baseline portfolios compete simultaneously: Aggressive Momentum, Conservative Scalper, ATR Volatility Adaptive, and Trailing Profit Guard.
   - **Elitism + Crossover & Mutation**: After each competition cycle, a unified Fitness Score selects the top 2 elite genomes to survive, while the bottom 2 undergo crossover and bounded Gaussian mutation (`G1 -> G2 -> G3`), logged into `memory/arena_history.json`.

3. **Multi-Exchange Live Ingestion & Resilient Fallback (`LiveArenaEngine`)**:
   - Primary real-time stream from Coinbase Exchange API with automatic sub-second failover to Binance 24hr ticker and Kraken public market data.
   - Memory-cached fallback ensures seamless zero-interruption execution even during transient network disconnects.

4. **OmniRoute Microservice & Keyless Diagnostics**:
   - Automated local background microservice with RTK/Caveman prompt compression, providing live narrative tactical assessments without external credential dependencies.

5. **Obsidian High-Contrast Quant Terminal (`Edge WebView2 DirectX 11`)**:
   - Native GPU-accelerated desktop workstation adhering to professional dark quant terminal aesthetics (`#08090C` background, high-contrast palette).
   - Interactive 1-minute Candlestick and Trend Line vector chart with strategy bracket limits, radar pings, and real-time execution tape.

---

## Quick Start Guide

### 1. Launch Packaged Desktop Executable (`.exe`)
Run the standalone pre-packaged Windows binary directly:
```powershell
dist\TradeBot0_Arena\TradeBot0_Arena.exe
```

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
dist\TradeBot0_Arena\TradeBot0_Arena.exe --self-test
```

### 3. Run Automated Unit Test Suite (20 Tests)
```powershell
.venv\Scripts\pytest.exe -q tests
```

### 4. Build Standalone Windows Executable
```powershell
powershell -ExecutionPolicy Bypass -File build_exe.ps1
```
