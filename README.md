# TradeBot0 — ETH/USD 多策略模擬交易系統 (V2.0.0)

> 專案介紹簡報：[TradeBot0_Introduction.pdf](TradeBot0_Introduction.pdf)（V2.0.0 架構與功能介紹，點開可在 GitHub 線上瀏覽）

TradeBot0 是一套在本機運行的 ETH/USD 多策略模擬交易軟體。系統平行運行 5 個量化策略，各配置 $100,000 虛擬資金（合計 $500,000 虛擬初始資金），依據即時市場報價進行虛擬撮合，並根據夏普值、索提諾值及回撤指標以基因演算法定期調整策略參數。系統整合本機 OmniRoute 服務進行新聞情緒分析與宏觀方向過濾，前端介面由 pywebview 桌面視窗呈現。

安裝程式下載：[TradeBot0Setup.exe（V2.0.0）](https://github.com/will095614/TradeBot0/releases/latest/download/TradeBot0Setup.exe)（GitHub Release 單一載點）。

> 本軟體為模擬測試工具，不連接真實交易所帳戶，亦不執行任何真實資金交易。

---

## 快速開始

### 1. 使用安裝程式（一般使用者）

1. 下載 [TradeBot0Setup.exe（V2.0.0）](https://github.com/will095614/TradeBot0/releases/latest/download/TradeBot0Setup.exe) 並執行安裝。
2. 因安裝檔未包含商業數位簽章，Windows SmartScreen 可能顯示提示視窗，點擊「其他資訊」並選擇「仍要執行」即可繼續。
3. 首次啟動將顯示設定精靈：
   - 設定本機管理密碼。
   - 輸入支援的大語言模型 API Key（支援 NVIDIA NIM、Google Gemini、Groq、OpenRouter）。精靈將自動在本地環境安裝並啟動 OmniRoute 服務。

### 2. 原始碼執行（開發者）

```powershell
# 啟動應用程式
.\.venv\Scripts\python.exe main.py

# 執行本機自我測試（驗證核心模組與 JSON 序列化，成功輸出 SELF_TEST_OK）
.\.venv\Scripts\python.exe main.py --self-test

# 執行單元與回歸測試套件
.\.venv\Scripts\python.exe -m pytest -q tests

# 打包執行檔（透過 PyInstaller 打包，再使用 Inno Setup 編譯 TradeBot0.iss）
powershell -ExecutionPolicy Bypass -File build_exe.ps1
```

---

## 系統依賴與 OmniRoute 服務

OmniRoute 為 TradeBot0 提供人工智慧語言模型介接的核心依賴元件，預設運行於本機 `http://127.0.0.1:20128`。

### 功能職責

- **新聞資料彙整（Data Ingestion）**：抓取多來源市場新聞，經由 SHA-256 去重後產出中文摘要。
- **宏觀方向決策（Macro Commander）**：分析市場事件情緒，產出市場方向指標（`LONG_ONLY`、`SHORT_ONLY`、`HOLD_CASH`）與倉位縮放係數（`risk_multiplier`），對不符方向之策略開倉訊號執行過濾。
- **情報中心（Intel Hub）**：提供即時情報流，於使用者點擊時即時調用模型產出事件深度分析。

### 運行機制與離線行為

- **自動管理**：程式內建的 `GatewaySupervisor` 會自動啟動並監控 OmniRoute 行程；相關執行檔案位於本機 `%LOCALAPPDATA%\TradeBot0\runtime`。
- **金鑰儲存**：API Key 儲存於本機使用者目錄 `~/.omniroute/.env`，不會寫入原始碼庫。
- **離線狀態**：若未設定 API Key 或 OmniRoute 服務未啟動，系統將切換為純指標運作模式，情報面板維持待機（`STANDBY`），交易訊號改由純技術指標與本機風控邏輯判定。

---

## 五大策略規格

系統平行運作 5 個獨立策略帳戶，初始資金各為 $100,000 虛擬美元：

| 策略名稱 | 代碼 | 槓桿倍數 | 交易邏輯與風控參數 |
| :--- | :--- | :---: | :--- |
| Aggressive Momentum | `comp_agg` | 3x | 順勢追價策略。單筆配置 70% 倉位，3.5% 固定停損，無固定止盈，採動態追蹤停損。 |
| Conservative Scalper | `comp_cons` | 1x（現貨） | RSI 均值回歸短線策略。單筆配置 25% 倉位，1.0% 固定停損，1.8% 固定止盈。 |
| Trailing Profit Guard | `comp_trail` | 2x | 趨勢追蹤策略。單筆配置 40% 倉位，1.5% 固定停損；獲利達 +1.0% 啟動保本，後續依價格極值階梯式移動停利。 |
| ORB Breakout | `comp_orb` | 2.5x | 15 分鐘開盤區間突破策略。以區間中點為停損，目標獲利率 2.0R，每日 UTC 00:00 重置區間。 |
| Session Mean Pullback | `comp_vwap` | 1x（現貨） | 區間典型價均值拉回策略。以典型均價（Typical Mean）為基準，目標獲利率 2.2R。 |

排行榜評分依據包含策略帳戶總淨值（`total_equity = cash + margin_locked + unrealized_pnl`）與夏普值、索提諾值及最大回撤等風險調整後指標。

---

## 風險控制與參數演化

### 1. 進場過濾機制

交易訊號在送交撮合引擎前，依序通過以下過濾：

1. **波動效率過濾（Chop Gate）**：計算 15 分鐘線的效率比（`ER(20) < 0.25`），當市場處於低效率盤整時，禁止建立新倉位（平倉單不受此限）。
2. **多時間框架趨勢確認（MTF Confluence）**：比對 1 小時線 EMA 均線排列，確保短線訊號順應中長線趨勢。
3. **宏觀方向過濾（Macro Commander）**：由語言模型評估宏觀資訊，當策略訊號與模型判定方向衝突時直接否決。
4. **蒙地卡羅勝率驗證（Monte Carlo EV Gate）**：利用歷史報酬重抽樣與 Student-t 分布（自由度 6）進行對偶路徑模擬，結合當前 K 線影線範圍評估預期值（EV）與觸及停損/止盈之機率。

### 2. 參數演化機制

- **觸發條件**：系統每運行 6 小時或累積 30 筆平倉紀錄後執行一次參數演化（設有 30 分鐘冷卻時間）。
- **淘汰與變異**：依據複合風險調整後適應度排序，保留前 2 名策略之參數；對後 3 名策略進行參數交叉與變異微調。`comp_agg` 與 `comp_trail` 保留無固定止盈之參數結構。

### 3. 撮合與行情保護

- **滑價模型**：`BrokerSim` 撮合模組結合市場深度與 ATR 指標計算動態滑價，模擬真實成交衝擊。
- **連線中斷防護**：當市場報價連線中斷時，系統停止新增開倉委託，介面顯示連線狀態警告，避免依據過期價格撮合。
- **非同步持久化**：K 線儲存、訂單紀錄與演化歷程之 SQLite 資料庫寫入獨立於主交易迴圈之外，避免磁碟 I/O 阻塞報價更新。

---

## 專案結構

- `main.py`：主程式進入點，支援桌面 UI 介面、`--cli` 回測模式及 `--self-test` 自我測試。
- `src/arena/`：模擬撮合核心，包含虛擬券商 `BrokerSim`、資產記帳 `Portfolio`、風控模組 `RiskGuard`、排行榜 `Leaderboard` 與遺傳演算法 `GeneticEvolver`。
- `src/competitors/`：5 個量化策略實作與策略參數結構 `CompetitorGenome`。
- `src/data/`：行情與資料處理模組，包含主調度引擎 `live_engine.py`、報價來源 `quote_feeds.py`、技術指標運算 `indicator_engine.py`、策略執行器 `live_strategy_runner.py`、會話存檔 `session_codec.py`、WebSocket 行情串流 `ws_feed.py` 與歷史回測 `timemachine.py`。
- `src/intelligence/`：外部資訊整合模組，包含 OmniRoute 本機客戶端 `OmniRouteClient`、新聞採集 `IntelligenceHarvester`、宏觀方向決策 `MacroCommander` 與背景行程監控 `GatewaySupervisor`。
- `src/gui/`：使用者介面，包含 pywebview 視窗控制器 `dashboard.py`、視圖資料轉換 `view_model.py` 及前端靜態資源 `assets/`（`index.html`、`app.css`、`app.js`）。
- `tests/`：單元測試、回歸測試、合約測試與效能驗證套件。

---

## 系統需求與環境

- **作業系統**：Windows 10 / Windows 11（64 位元，需具備 Microsoft Edge WebView2 Runtime）。
- **Python 環境**（原始碼執行）：Python 3.10+，相關相依套件請參閱 `requirements.txt`。
- **本機服務**：Node.js 與 OmniRoute runtime（安裝程式之設定精靈會自動在本機安裝，無須手動配置）。

---

## 相關文件與版本

- **最新版本**：**V2.0.0**（版本定義於 `src/version.py`，與 `TradeBot0.iss` 保持一致）。
- **除錯紀錄與技術規範**：請參閱 [BUGS_AND_OPTIMIZATIONS.md](BUGS_AND_OPTIMIZATIONS.md) 與 [OptimizationFullGuide.md](OptimizationFullGuide.md)。
