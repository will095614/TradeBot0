# TradeBot0 for Windows — ETH/USD Multi-Strategy Simulated Trading System


TradeBot0 for Windows is a simulated trading app that runs on your own Windows computer. It trades ETH/USD with 5 quantitative strategies running in parallel, each funded with $100,000 in virtual money ($500,000 total), matching virtual orders against live market prices and tuning strategy parameters automatically over time. A built-in AI reads the news and judges market direction, filtering out trade signals that go against the trend.

> This is a simulation tool. It does not connect to any real exchange account and never executes real-money trades.

---

## Quick Start

### 1. Using the Installer (Most Users)

1. Download [TradeBot0Setup-V3.3.0.exe](https://github.com/will095614/TradeBot0/releases/download/v3.3.0/TradeBot0Setup-V3.3.0.exe) and run the installer.
2. The installer is not commercially code-signed, so Windows SmartScreen may show a prompt. Click "More info" and choose "Run anyway" to continue.
3. On first launch, a setup wizard appears:
   - Enter your Google Gemini API key, click test and launch, and you are ready to go.

### 2. Running from Source (Developers)

```powershell
# Launch the app
.\.venv\Scripts\python.exe main.py

# Run the built-in self-test (checks core modules and JSON serialization; prints SELF_TEST_OK on success)
.\.venv\Scripts\python.exe main.py --self-test

# Run the unit and regression test suite
.\.venv\Scripts\python.exe -m pytest -q tests

# Package the executable (PyInstaller, then compile TradeBot0.iss with Inno Setup)
powershell -ExecutionPolicy Bypass -File build_exe.ps1
```

---

## AI Intelligence

TradeBot0's built-in AI reads market news and judges market direction for you.

### What It Does

- **News summaries**: Collects market news from multiple public sources and condenses it into concise English summaries.
- **Market direction**: Analyzes news and market events to judge whether the market favors going long, going short, or staying out. Entry signals that disagree with the AI's direction are blocked outright, and position sizes are adjusted to current conditions.
- **Intelligence Hub**: A live intelligence stream. Open any item to read the AI's in-depth analysis.

### It Works Without an API Key Too

- **Your key stays on your computer**: The API key you enter is stored locally only. It is never uploaded and never written into the project files.
- **Trading continues while the AI is on standby**: Without an API key, the AI intelligence features go on standby and trading continues as usual, driven by technical indicators and risk rules.

---

## Five Strategies

The system runs 5 independent strategy accounts in parallel, each starting with $100,000 in virtual funds:

| Strategy | Leverage | Logic & Risk Parameters |
| :--- | :---: | :--- |
| Aggressive Momentum | 3x | Trend-following momentum strategy. Allocates 70% per trade, 3.5% fixed stop-loss, no fixed take-profit, dynamic trailing stop. |
| Conservative Scalper | 1x (spot) | RSI mean-reversion scalping strategy. Allocates 25% per trade, 1.0% fixed stop-loss, 1.8% fixed take-profit. |
| Trailing Profit Guard | 2x | Trend-following strategy. Allocates 40% per trade, 1.5% fixed stop-loss; once profit reaches +1.0%, break-even protection kicks in, then the stop moves up in steps with price extremes. |
| ORB Breakout | 2.5x | 15-minute opening-range breakout strategy. Stop-loss at the range midpoint, target 2.0R, range resets daily at 00:00 UTC. |
| Session Mean Pullback | 1x (spot) | Range typical-price mean-reversion strategy, using the typical price as its reference, target 2.2R. |

The leaderboard ranks accounts by total equity (equity = cash + margin + unrealized P&L). Sharpe ratio, Sortino ratio, and maximum drawdown are used to score strategies when evolution tunes their parameters.

---

## Risk Controls & Parameter Evolution

### 1. Entry Filters

Before a trade signal reaches the matching engine, it passes through these filters in order:

1. **Chop filter**: Reads the efficiency ratio on the 15-minute chart and blocks new entries while the market is choppy (exits are never blocked).
2. **Trend confirmation**: Compares the moving-average alignment on the 1-hour chart to make sure short-term signals follow the medium-to-long-term trend.
3. **Macro direction filter**: The AI assesses macro information and vetoes any strategy signal that conflicts with its direction.
4. **Win-rate check**: Simulates many possible price paths from historical returns to judge whether the trade is worth taking and how likely it is to hit the stop-loss or take-profit.

### 2. Parameter Evolution

- **When it runs**: Evolution runs after every 6 hours of operation or 30 closed trades (with a 30-minute cooldown).
- **Selection and mutation**: Strategies are ranked by overall performance. The top 2 keep their parameters; the bottom 3 have theirs crossed over and mutated. Aggressive Momentum and Trailing Profit Guard keep their no-fixed-take-profit design.

### 3. Matching & Market-Price Protection

- **Slippage simulation**: Matching calculates slippage from market depth and volatility to simulate the impact of a real fill.
- **Connection-loss protection**: If the market price feed drops, the system stops placing new entry orders and shows a connection warning in the interface. It never trades on stale prices.

---

## Project Structure

- `main.py`: Main entry point, supporting the desktop UI, `--cli` backtest mode, and `--self-test`.
- `src/arena/`: Simulated matching core, with the virtual broker `BrokerSim`, portfolio accounting `Portfolio`, risk module `RiskGuard`, leaderboard `Leaderboard`, and genetic algorithm `GeneticEvolver`.
- `src/competitors/`: The 5 quantitative strategy implementations and the strategy parameter structure `CompetitorGenome`.
- `src/data/`: Market data and processing, with the main engine `live_engine.py`, quote sources `quote_feeds.py`, indicator calculations `indicator_engine.py`, strategy runner `live_strategy_runner.py`, session persistence `session_codec.py`, WebSocket stream `ws_feed.py`, and historical backtesting `timemachine.py`.
- `src/intelligence/`: External information, with the direct Google Gemini client `GeminiClient`, news harvesting `IntelligenceHarvester`, macro direction `MacroCommander`, and settings `ConfigManager`.
- `src/gui/`: User interface, with the desktop window controller `dashboard.py`, view data `view_model.py`, and frontend pages in `assets/` (`index.html`, `app.css`, `app.js`).
- `tests/`: Unit, regression, contract, and performance test suites.

---

## System Requirements

- **Operating system**: Windows 10 / Windows 11 (64-bit).
- **Python** (running from source): Python 3.10+, see `requirements.txt` for dependencies.
- **Google Gemini, direct connection**: The app connects to the Google Gemini API over HTTPS for news classification and macro decisions. No local AI gateway or Node.js runtime is needed.

---

## Download

[TradeBot0Setup-V3.3.0.exe](https://github.com/will095614/TradeBot0/releases/download/v3.3.0/TradeBot0Setup-V3.3.0.exe) (single download link on GitHub Releases).
