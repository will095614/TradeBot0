# fix_best_effort_sources_patch.py — 外部來源改為 best-effort（2026-11-13，使用者決定）。
# 政策：「嘗試對接，連不到也沒關係，因為不同使用者可能有不同的過濾」。
# 查證結果：程式本身早已是 best-effort——報價三家各包 try/except（1.2–1.5 秒
# timeout，SSLError 也接住，回 None 後走下一家）；FEED_REGISTRY 逐家 try/except
#（3 秒 timeout，非 200 只記 debug 繼續）；歷史 K 線 Yahoo 失敗走 CCXT 備援；
# 論壇 5 秒 timeout 失敗回空；WS 指數退避重連；gateway 掛了走關鍵字 fallback；
# Node 下載失敗走純量化模式。沒有任何一家來源能拖垮程式。
# 本次只改兩處，讓政策成為明文、讓檢查結果與政策一致：
# 1. smoke_external.py 的整體判定：以前任一 FAIL 就整體 FAIL（RC=1），
#    現在只有核心報價路徑全滅（Binance REST、Kraken REST、Binance WS 三家
#    全 FAIL）才算 FAIL；核心至少一家通就 RC=0，個別 FAIL 仍列在結果中。
# 2. live_engine.py 報價鏈上方加政策註解（行為不變）。
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


SMOKE = os.path.join(BASE, "scripts", "smoke_external.py")
ENGINE = os.path.join(BASE, "src", "data", "live_engine.py")

replace_once(
    SMOKE,
    "結束碼：0＝無 FAIL；1＝至少一項 FAIL。WARN／SKIP 不影響結束碼。",
    "結束碼：0＝核心報價路徑暢通（Binance REST、Kraken REST、Binance WS 至少一項 PASS）；"
    "1＝核心路徑全滅。個別來源 FAIL 只列在結果中，不影響結束碼——使用者政策"
    "（2026-11-13）：外部來源皆為 best-effort，不同使用者的網路過濾不同，連不到也沒關係。",
    "smoke docstring exit codes",
)

replace_once(
    SMOKE,
    """    counts = {}
    for _, status, _ in RESULTS:
        counts[status] = counts.get(status, 0) + 1
    summary = " ".join(f"{k}={v}" for k, v in sorted(counts.items()))
    failed = counts.get("FAIL", 0)
    print(f"SUMMARY {summary} -> {'FAIL' if failed else 'OK'}")
    return 1 if failed else 0""",
    """    counts = {}
    for _, status, _ in RESULTS:
        counts[status] = counts.get(status, 0) + 1
    summary = " ".join(f"{k}={v}" for k, v in sorted(counts.items()))
    # Best-effort policy (user decision 2026-11-13): every external source
    # is tried, and a blocked one is fine — different users sit behind
    # different filters. Only the core quote path decides the exit code:
    # the app can trade as long as at least one of Binance REST, Kraken
    # REST or Binance WS answers. Individual FAILs stay visible above.
    core_names = {"binance_rest", "kraken_rest", "binance_ws"}
    core_ok = any(name in core_names and status == "PASS" for name, status, _ in RESULTS)
    failed = counts.get("FAIL", 0)
    if core_ok:
        print(f"SUMMARY {summary} -> OK (core quote path live; {failed} optional source(s) blocked)")
        return 0
    print(f"SUMMARY {summary} -> FAIL (no core quote source)")
    return 1""",
    "smoke verdict core-only",
)

replace_once(
    ENGINE,
    """            if len(self.live_logs) > 120:
                self.live_logs.pop()

    def _fetch_binance_quote(self) -> Optional[LiveQuote]:""",
    """            if len(self.live_logs) > 120:
                self.live_logs.pop()

    # Quote chain policy (user decision 2026-11-13): every external source
    # is best-effort — try it, and a blocked one is fine, because different
    # users sit behind different network filters. Each fetcher below catches
    # all exceptions (incl. SSLError from DNS-filter landing pages) and
    # returns None; the caller walks Binance -> Kraken -> Coinbase and uses
    # the first live quote. No single source may take down the quote path.
    def _fetch_binance_quote(self) -> Optional[LiveQuote]:""",
    "quote chain policy comment",
)

print("PATCH DONE")
