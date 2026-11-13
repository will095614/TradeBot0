# TradeBot0 — ETH/USD 多策略模擬交易競技場

六個策略各拿 $100,000 虛擬資金，在即時 ETH/USD 行情下競賽淨值，定期用基因演算法演化參數；外層有 OmniRoute AI 情報否決（可選），桌面終端以 pywebview 呈現。

> 模擬盤，不是實盤。不接真實交易所帳戶、不下真單。

## 快速開始

```powershell
# 方式一：打包好的 exe
dist\TradeBot0_Arena.exe

# 方式二：原始碼執行
.venv\Scripts\python.exe main.py

# 自我測試（應回 SELF_TEST_OK）
.venv\Scripts\python.exe main.py --self-test

# 單元測試（2026-11-13 實測：103 passed）
.venv\Scripts\pytest.exe -q tests

# 重新打包 exe
powershell -ExecutionPolicy Bypass -File build_exe.ps1
```

首次啟動會跳設定精靈：填 DeepSeek／Gemini／Groq／OpenRouter 的 API Key（可跳過，跳過則只用純數學核心），存檔後啟動 OmniRoute gateway（port 20128）。

## 六個策略

| 策略 | 槓桿 | 做法 |
| :--- | :---: | :--- |
| Aggressive Momentum | 3x | 動量追價 |
| Conservative Scalper | 1x | 小波動剝頭皮 |
| ATR Volatility Adaptive | 2x | 依波動率調停損／止盈 |
| Trailing Profit Guard | 2x | 移動停損守住獲利 |
| ORB Breakout | 2.5x | 開盤區間突破 |
| Institutional VWAP | 1x | VWAP 拉回 |

## 架構

- `main.py` — 進入點
- `src/arena/` — 撮合（BrokerSim）、投資組合（Decimal 記帳）、排名、基因演化、風控
- `src/competitors/` — 六個策略
- `src/data/` — 即時行情（Binance／Kraken／Coinbase）、WebSocket、SQLite 持久化、回測 TimeMachine
- `src/intelligence/` — OmniRoute 客戶端、情報 ingestion、Macro Commander 否決
- `src/gui/` — pywebview 桌面終端（`assets/index.html`、`app.css`、`app.js`）
- `data/` — 設定與執行期資料（`system_config.json`）
- `memory/` — 演化歷史等 agent 記憶
- `.agent/skills/` — Antigravity skills（美術：frontend-design、aimran-library、stageshow；交易：trader-*；工具：graphify 等）

## 設定

- `data/system_config.json`：gateway 自動啟動、port、provider 等。
- OmniRoute gateway：全域安裝（`%APPDATA%\npm\node_modules\omniroute`），由 `gateway_supervisor` 啟動，預設 `http://127.0.0.1:20128`。

## 注意事項

- 斷網處理正在重構：離線模式將移除，改為斷網時等待重連、畫面遮蔽不讓人使用（2026-11-13 決定）。
- 已知問題與維修清單另外維護（程式審查報告 2026-11-13 版，1–12 項已完成，待打包）。
- 舊的審查／除錯／部署報告已於 2026-11-13 程式瘦身時移除，內容仍在 git 歷史（HEAD 5b6b7d5）可還原；設計參考見 `OptimizationFullGuide.md`。
