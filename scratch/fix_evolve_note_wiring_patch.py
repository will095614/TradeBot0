# fix_evolve_note_wiring_patch.py — 把 next_evolve_sec 註記接上畫面（2026-11-13，使用者指示）。
# 背景：P2 已在 view model 加了誠實欄位（next_evolve_sec_latest「最晚」上限、
# closed_trades_to_next_evolve、next_evolve_sec_note），但前端只顯示混合倒數
# state.next_evolve_sec，註記沒出現在畫面上。
# 接線方式（只用現成元素，不新增 HTML／CSS、不動版面）：
# 1. 倒數計時（#countdownLabel，頂部 dock）加 title tooltip，內容就是 view model
#    的 next_evolve_sec_note 原文（「最晚 21599s（21600s 上限）；還差 1 筆平倉即觸發」）。
# 2. Genetic Engine 卡片副標（#hudGenSub）由「EV Gate (6H)」改為
#    「EV Gate (6H) · 還差 N 筆」；還差 0 筆時顯示「· 即將觸發」；欄位缺失時
#    保持原樣。hudVesselGen 液面仍用混合倒數（進度意義正確），不動。
# 每個 replacement 寫入前驗證在目標檔中精確匹配一次。
import os

ROOT = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
BASE = None
for c in [os.getcwd(), ROOT, os.path.dirname(ROOT)]:
    if os.path.isfile(os.path.join(c, "src", "gui", "assets", "index.html")):
        BASE = c
        break
if BASE is None:
    BASE = os.getcwd()


def load(path):
    with open(path, "rb") as f:
        raw = f.read()
    crlf = b"\r\n" in raw
    return raw.decode("utf-8"), crlf


def save(path, text, crlf):
    data = text.replace("\n", "\r\n") if crlf else text
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(data)


def replace_once(path, old, new, label):
    text, crlf = load(path)
    n = text.count(old)
    assert n == 1, f"{label}: expected exactly 1 match in {path}, found {n}"
    save(path, text.replace(old, new), crlf)
    print(f"OK {label}")


APPJS = os.path.join(BASE, "src", "gui", "assets", "app.js")

replace_once(
    APPJS,
    """  const autoLbl = document.getElementById('autoEvolveLabelText');
  cdEl.textContent = fmtTimeSec(state.next_evolve_sec || 0);""",
    """  const autoLbl = document.getElementById('autoEvolveLabelText');
  cdEl.textContent = fmtTimeSec(state.next_evolve_sec || 0);
  // P2 note wiring (2026-11-13): the countdown blends both triggers, so
  // the full honest note (latest time cap + trades still needed) rides on
  // the countdown tooltip; the trades-remaining part is also visible in
  // the Genetic Engine card (hudGenSub below).
  if (cdEl && typeof state.next_evolve_sec_note === 'string' && state.next_evolve_sec_note) {
    cdEl.title = state.next_evolve_sec_note;
  }""",
    "countdown tooltip shows evolve note",
)

replace_once(
    APPJS,
    """  const genSubEl = document.getElementById('hudGenSub');
  if (genSubEl) {
    const hVal = Math.round((state.auto_evolve_interval_sec || 21600) / 3600);
    genSubEl.textContent = `EV Gate (${hVal}H)`;
  }""",
    """  const genSubEl = document.getElementById('hudGenSub');
  if (genSubEl) {
    const hVal = Math.round((state.auto_evolve_interval_sec || 21600) / 3600);
    // P2 note wiring (2026-11-13): show how many closed trades are still
    // needed for the trade trigger, next to the time cap.
    const tradesLeftRaw = Number(state.closed_trades_to_next_evolve);
    const tradesLeft = Number.isFinite(tradesLeftRaw) ? Math.max(0, Math.round(tradesLeftRaw)) : null;
    genSubEl.textContent = tradesLeft === null
      ? `EV Gate (${hVal}H)`
      : (tradesLeft > 0 ? `EV Gate (${hVal}H) · 還差 ${tradesLeft} 筆` : `EV Gate (${hVal}H) · 即將觸發`);
  }""",
    "hudGenSub shows trades remaining",
)

print("PATCH DONE")
