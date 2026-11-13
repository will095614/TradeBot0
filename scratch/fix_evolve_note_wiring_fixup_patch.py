# fix_evolve_note_wiring_fixup_patch.py — 演化註記接線修正：中文標籤改由 view model 產生（2026-11-13）。
# 原因：第一版把「還差 N 筆／即將觸發」中文字面寫進 app.js，觸發三項前端
# 無 CJK 測試（test_zero_cjk_in_frontend_assets 等），318 項變 315 項。
# 修正：中文標籤改在 view_model.py（Python，CJK 無礙，沿用 P2 的 \u 轉義寫法）
# 以 next_evolve_trades_label 欄位產生，前端只負責原樣顯示，不再出現中文字面。
# 倒數 tooltip 用的已是 state.next_evolve_sec_note 欄位引用，本身無中文字面，不動。
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


VM = os.path.join(BASE, "src", "gui", "view_model.py")
APPJS = os.path.join(BASE, "src", "gui", "assets", "app.js")

replace_once(
    VM,
    """    next_evolve_note = (
        f"\\u6700\\u665a {int(next_evolve_sec_latest)}s"
        f"\\uff08{int(engine.auto_evolve_interval_sec)}s \\u4e0a\\u9650\\uff09\\uff1b"
        f"\\u9084\\u5dee {trades_remaining} \\u7b46\\u5e73\\u5009\\u5373\\u89f8\\u767c"
    )""",
    """    next_evolve_note = (
        f"\\u6700\\u665a {int(next_evolve_sec_latest)}s"
        f"\\uff08{int(engine.auto_evolve_interval_sec)}s \\u4e0a\\u9650\\uff09\\uff1b"
        f"\\u9084\\u5dee {trades_remaining} \\u7b46\\u5e73\\u5009\\u5373\\u89f8\\u767c"
    )
    # Display label for the Genetic Engine card. Frontend assets must stay
    # CJK-free (see test_zero_cjk_in_frontend_assets), so the Chinese label
    # is rendered here in Python and the frontend only displays it opaquely.
    next_evolve_trades_label = (
        f"\\u9084\\u5dee {trades_remaining} \\u7b46" if trades_remaining > 0 else "\\u5373\\u5c07\\u89f8\\u767c"
    )""",
    "add trades label in view model",
)

replace_once(
    VM,
    """        "next_evolve_sec_note": next_evolve_note,""",
    """        "next_evolve_sec_note": next_evolve_note,
        "next_evolve_trades_label": next_evolve_trades_label,""",
    "expose trades label in dict",
)

replace_once(
    VM,
    """        "next_evolve_sec_note": "\\u6700\\u665a 0s\\uff0821600s \\u4e0a\\u9650\\uff09\\uff1b\\u9084\\u5dee 30 \\u7b46\\u5e73\\u5009\\u5373\\u89f8\\u767c",""",
    """        "next_evolve_sec_note": "\\u6700\\u665a 0s\\uff0821600s \\u4e0a\\u9650\\uff09\\uff1b\\u9084\\u5dee 30 \\u7b46\\u5e73\\u5009\\u5373\\u89f8\\u767c",
        "next_evolve_trades_label": "\\u9084\\u5dee 30 \\u7b46",""",
    "expose trades label in empty fallback",
)

replace_once(
    APPJS,
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
    """  const genSubEl = document.getElementById('hudGenSub');
  if (genSubEl) {
    const hVal = Math.round((state.auto_evolve_interval_sec || 21600) / 3600);
    // P2 note wiring (2026-11-13): the trades-remaining label is rendered
    // by the view model (Python) because frontend assets must stay CJK-free
    // (see test_zero_cjk_in_frontend_assets); JS only displays it opaquely.
    const tradesLabel = (typeof state.next_evolve_trades_label === 'string' && state.next_evolve_trades_label)
      ? state.next_evolve_trades_label
      : '';
    genSubEl.textContent = tradesLabel ? `EV Gate (${hVal}H) · ${tradesLabel}` : `EV Gate (${hVal}H)`;
  }""",
    "hudGenSub renders label opaquely",
)

print("PATCH DONE")
