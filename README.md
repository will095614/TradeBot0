# TradeBot0 — BTC/USD 多策略模擬交易競技場

五個策略各拿 $100,000 虛擬資金，在即時 BTC/USD 行情下競賽淨值，定期用基因演算法演化參數；OmniRoute AI 情報（必要元件）提供新聞 ingestion 與 Market Direction 否決；桌面終端以 pywebview 呈現。

下載：[TradeBot0Setup.exe（V1.0.0）](https://github.com/will095614/TradeBot0/releases/latest/download/TradeBot0Setup.exe)（GitHub Release，單一載點）。

> 模擬盤，不是實盤。不接真實交易所帳戶、不下真單。

## 快速開始

### 方式一：安裝程式（一般使用者）

下載 `TradeBot0Setup.exe` 執行安裝。安裝程式未簽署，Windows SmartScreen 出現警告是預期的，選擇「仍要執行」即可。

首次啟動會跳設定精靈：設定管理密碼（必填），再填 NVIDIA NIM／Google Gemini／Groq／OpenRouter 任一家的 API Key（建議至少填一家免費額度的 key，AI 功能才會運作）。精靈會自動安裝並啟動 OmniRoute gateway。

### 方式二：原始碼執行（開發者）

```powershell
.venv\Scripts\python.exe main.py

# 自我測試（應回 SELF_TEST_OK）
.venv\Scripts\python.exe main.py --self-test

# 單元測試（2026-11-16 實測：604 passed、2 skipped）
.venv\Scripts\pytest.exe -q tests

# 重新打包 exe（安裝程式再以 Inno Setup 編譯 TradeBot0.iss）
powershell -ExecutionPolicy Bypass -File build_exe.ps1
```

## OmniRoute 是必要元件，不是可選

TradeBot0 的 AI 功能全部走 OmniRoute（本機 gateway，預設 `http://127.0.0.1:20128`）：

- 情報 ingestion：新聞事件收集、去重、摘要
- Market Direction（Macro Commander）：方向判斷與否決
- Intel Hub：Market Intelligence Stream，點開卡片才由 LLM 生成約 1000 字文章

沒有 OmniRoute，程式仍能跑純數學核心，但情報與方向功能會停在待機／關鍵字備援（Market Direction 顯示 `STANDBY / KEYWORD FALLBACK`，信心 0.5），等於少了 AI 的一半。

- Gateway 由程式內的 supervisor 自動啟動、看門狗自動重啟；首次使用時精靈會一鍵安裝 Node.js 與 OmniRoute（約 2.6 GB，優先放在 `%LOCALAPPDATA%\TradeBot0\runtime`，本機安裝，不污染全域 npm）。
- 只用各家免費額度，不儲值、不綁支付方式。沒有額度的供應商就不用。
- Key 存在 `~/.omniroute/.env`（gateway 讀取）；精靈填的 key 只寫進 `.env`，其餘供應商須在 gateway console 接上才有用。
- 模型：ingest 與 commander 皆為 `gemini/gemini-3.1-flash-lite`（環境變數 `LLM_MODEL_INGEST`／`LLM_MODEL_COMMANDER`，下次啟動生效）。

## 五個策略

| 策略 | 槓桿 | 做法 |
| :--- | :---: | :--- |
| Aggressive Momentum | 3x | 動量追價（70% 倉位、3.5% 停損） |
| Conservative Scalper | 1x（現貨） | 小波動剝頭皮（25% 倉位、1.0% 停損／1.8% 止盈） |
| Trailing Profit Guard | 2x | 移動停損守住獲利（40% 倉位、1.5% 停損／0.6% 追蹤） |
| ORB Breakout | 2.5x | 開盤區間突破（15 分鐘箱體、2.0R 目標） |
| Session Mean Pullback | 1x（現貨） | 均值拉回（2.2R；即時 1 分鐘 K 線無逐根成交量，故非嚴格 VWAP） |

排名標準就是淨值（`total_equity` = cash + margin_locked + unrealized_pnl）。矩陣第六格保留給未來的手動模式，尚未實作。

## 演化與風控

- 自動演化預設開啟，每 6 小時／每 30 筆平倉觸發一次；前 2 名保留基因、後 4 名交叉變異。
- 實盤基因維持第一代預設值（gen-1）；2026-11-15 的重演基因在新鮮月份全數虧損，暫不啟用。
- 盤整過濾已上線：ER(20) < 0.25 時不開新倉（平倉永不擋）。
- 斷網時等待重連，進 arena 後全螢幕琥珀色「Network Offline」遮罩（交易暫停、不用舊報價下單、無關閉按鈕，連線恢復自動消失）。

## 架構

- `main.py` — 進入點
- `src/arena/` — 撮合（BrokerSim）、投資組合（Decimal 記帳）、排名、基因演化、風控
- `src/competitors/` — 五個策略
- `src/data/` — 即時行情（Binance／Kraken／Coinbase）、WebSocket、SQLite 持久化、回測 TimeMachine
- `src/intelligence/` — OmniRoute 客戶端、情報 ingestion、Macro Commander、gateway supervisor
- `src/gui/` — pywebview 桌面終端（`assets/index.html`、`app.css`、`app.js`）
- `data/` — 設定與執行期資料（`system_config.json`，不進版控）
- `memory/` — 演化歷史等 agent 記憶
- `.agent/skills/` — Antigravity skills（美術：frontend-design、aimran-library、stageshow；交易與工具類）

## 版本

版本號 `VX.Y.Z`：X＝大改動／breaking、Y＝功能群組、Z＝修復／優化群組；同一子系統只算一版。`src/version.py` 是唯一來源，`TradeBot0.iss` 的 MyAppVersion 須同步。目前最新版：**V1.0.0**（GitHub 公開第一版，2026-11-18；程式碼與 V2.8.7 相同，僅重置編號）。

## 系統需求

- Windows 10／11（64 位元），僅支援 Windows（用到 winreg、ctypes windll）
- 安裝程式會處理 Node.js／OmniRoute runtime，不需另外安裝

## 注意事項

- 模擬盤：虛擬資金，不下真單；行情為即時公開報價。
- 外部來源 best-effort：嘗試對接，連不到也沒關係（不同使用者可能有不同過濾）；冒煙測試只看核心報價路徑。
- 外部連線冒煙測試（唯讀、不下單、不進 pytest）：`python scripts/smoke_external.py`（加 `--quick` 只跑 30 秒內項目）。
- 設計參考見 `OptimizationFullGuide.md`。
