#!/usr/bin/env python3
"""TradeBot0 外部連線冒煙測試（獨立腳本，不進 pytest 全量）。

唯讀：只發 GET／訂閱公開行情，不下單、不寫入任何狀態、不改任何檔案。
按需跑：``python scripts/smoke_external.py``（從專案根目錄），加 ``--quick``
只跑 30 秒內項目（跳過 WS、Yahoo、CCXT 與 FEED_REGISTRY 全掃）。

覆蓋（見稽核報告 §4.4）：
  Binance REST / Kraken REST / Coinbase REST（各 1 次，欄位齊全）
  Binance WS（連上、3 秒內 ≥1 則 ticker、斷線重連 1 次）
  Yahoo yfinance.download("ETH-USD", period="1d", interval="1m") 非空
  CCXT Kraken fetch_ohlcv 非空
  FEED_REGISTRY 18 項逐一 GET（timeout 5 秒；任一非 200 只警告，不讓整體失敗）
  StockTwits ETH.X／BTC.X 200 且含 messages
  OmniRoute /api/health（gateway 未跑時印提示、不算失敗）
  Node 下載 URL 可 HEAD 到（不下載本體）

結束碼：0＝無 FAIL；1＝至少一項 FAIL。WARN／SKIP 不影響結束碼。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time

# 讓 `python scripts/smoke_external.py` 從任何 cwd 都找得到專案的 src。
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import requests
except ImportError:
    print("FAIL requests is not installed; cannot run smoke checks.")
    sys.exit(2)

# FEED_REGISTRY 與 Node URL 以專案程式碼為準；import 失敗時用內嵌副本。
_FALLBACK_REGISTRY = [
    ("polymarket_gamma", "https://gamma-api.polymarket.com/events?limit=25&active=true"),
    ("sec_edgar_8k", "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&CIK=&type=8-K&company=&dateb=&owner=include&start=0&count=40&output=atom"),
    ("isw_updates", "https://www.understandingwar.org/rss.xml"),
    ("war_zone", "https://www.twz.com/feed"),
    ("liveuamap", "https://liveuamap.com/rss"),
    ("gcaptain", "https://gcaptain.com/feed/"),
    ("forexlive", "https://www.forexlive.com/feed/news"),
    ("semianalysis", "https://www.semianalysis.com/feed"),
    ("trendforce", "https://www.trendforce.com/rss"),
    ("digitimes", "https://www.digitimes.com/rss/daily.xml"),
    ("technews_tw", "https://technews.tw/feed/"),
    ("coindesk_wire", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ("cointelegraph_wire", "https://cointelegraph.com/rss"),
    ("decrypt_wire", "https://decrypt.co/feed"),
    ("stocktwits_ethx", "https://api.stocktwits.com/api/2/streams/symbol/ETH.X.json"),
    ("stocktwits_btcx", "https://api.stocktwits.com/api/2/streams/symbol/BTC.X.json"),
    ("fred_releases", "https://fred.stlouisfed.org/rss/releases.xml"),
    ("us_treasury", "https://home.treasury.gov/rss/press-releases.xml"),
]
_FALLBACK_NODE_URL = "https://nodejs.org/dist/v24.21.0/node-v24.21.0-win-x64.zip"

try:
    from src.intelligence.gateway_supervisor import RUNTIME_NODE_ZIP_URL
    from src.intelligence.ingestion import FEED_REGISTRY, USER_AGENT

    REGISTRY = [(e["id"], e["url"]) for e in FEED_REGISTRY]
    NODE_URL = RUNTIME_NODE_ZIP_URL
    HEADERS = {"User-Agent": USER_AGENT}
    REGISTRY_SOURCE = "src.intelligence.ingestion.FEED_REGISTRY"
except Exception as e:  # pragma: no cover - import fallback only
    print(f"WARN could not import project registry ({e}); using embedded copy.")
    REGISTRY = list(_FALLBACK_REGISTRY)
    NODE_URL = _FALLBACK_NODE_URL
    HEADERS = {"User-Agent": "TradeBot0-Smoke/1.0"}
    REGISTRY_SOURCE = "embedded fallback (import failed)"

RESULTS = []  # (name, status, detail)


def record(name, status, detail=""):
    RESULTS.append((name, status, detail))
    print(f"{status:4} {name}: {detail}")


def check_binance_rest():
    name = "binance_rest"
    try:
        t0 = time.time()
        r = requests.get(
            "https://api.binance.com/api/v3/ticker/24hr?symbol=ETHUSDT",
            timeout=10, headers=HEADERS,
        )
        dt = time.time() - t0
        if r.status_code != 200:
            return record(name, "FAIL", f"HTTP {r.status_code} in {dt:.1f}s")
        body = r.json()
        missing = [k for k in (
            "lastPrice", "bidPrice", "askPrice", "highPrice",
            "lowPrice", "volume", "priceChangePercent",
        ) if k not in body]
        if missing:
            return record(name, "FAIL", f"missing fields: {missing}")
        record(name, "PASS", f"200 in {dt:.1f}s lastPrice={body['lastPrice']} "
                             f"change={body['priceChangePercent']}%")
    except Exception as e:
        record(name, "FAIL", f"{type(e).__name__}: {e}")


def check_kraken_rest():
    name = "kraken_rest"
    try:
        t0 = time.time()
        r = requests.get(
            "https://api.kraken.com/0/public/Ticker?pair=ETHUSD",
            timeout=10, headers=HEADERS,
        )
        dt = time.time() - t0
        if r.status_code != 200:
            return record(name, "FAIL", f"HTTP {r.status_code} in {dt:.1f}s")
        result = r.json().get("result") or {}
        if not result:
            return record(name, "FAIL", "empty result")
        pair = next(iter(result.values()))
        record(name, "PASS", f"200 in {dt:.1f}s last={pair['c'][0]}")
    except Exception as e:
        record(name, "FAIL", f"{type(e).__name__}: {e}")


def check_coinbase_rest():
    name = "coinbase_rest"
    try:
        t0 = time.time()
        r = requests.get(
            "https://api.exchange.coinbase.com/products/ETH-USD/ticker",
            timeout=10, headers=HEADERS,
        )
        s = requests.get(
            "https://api.exchange.coinbase.com/products/ETH-USD/stats",
            timeout=10, headers=HEADERS,
        )
        dt = time.time() - t0
        if r.status_code != 200 or s.status_code != 200:
            return record(name, "FAIL", f"ticker HTTP {r.status_code}, stats HTTP {s.status_code}")
        tick = r.json()
        stats = s.json()
        if "price" not in tick:
            return record(name, "FAIL", "ticker has no price field")
        record(name, "PASS", f"200 in {dt:.1f}s price={tick['price']} "
                             f"24h high={stats.get('high')} low={stats.get('low')}")
    except Exception as e:
        record(name, "FAIL", f"{type(e).__name__}: {e}")


async def _ws_once(connect_fn, url, label):
    """One WS connect + wait <=3s for a ticker message. Returns (ok, detail)."""
    try:
        async with connect_fn(url, ping_interval=20, ping_timeout=10,
                              close_timeout=5) as ws:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=3.0)
            except asyncio.TimeoutError:
                return False, f"{label}: connected but no message within 3s"
            msg = json.loads(raw)
            price = msg.get("c") or msg.get("lastPrice")
            if price is None:
                return False, f"{label}: message has no price field: {str(raw)[:120]}"
            return True, f"{label}: last={price}"
    except Exception as e:
        return False, f"{label}: {type(e).__name__}: {e}"


def check_binance_ws():
    name = "binance_ws"
    try:
        import websockets
    except ImportError:
        return record(name, "SKIP", "websockets is not installed")
    connect_fn = getattr(websockets, "connect", None)
    if connect_fn is None:  # older websockets layout
        try:
            from websockets.client import connect as connect_fn
        except ImportError:
            return record(name, "SKIP", "websockets.connect is unavailable")
    url = "wss://stream.binance.com:9443/ws/ethusdt@ticker"

    async def _run():
        ok1, d1 = await _ws_once(connect_fn, url, "connect#1")
        if not ok1:
            return ok1, d1
        ok2, d2 = await _ws_once(connect_fn, url, "reconnect#2")
        return ok2, f"{d1}; {d2}"

    try:
        ok, detail = asyncio.run(_run())
    except Exception as e:
        return record(name, "FAIL", f"{type(e).__name__}: {e}")
    record(name, "PASS" if ok else "FAIL", detail)


def check_yahoo():
    name = "yahoo_yfinance"
    try:
        import yfinance as yf
    except ImportError:
        return record(name, "SKIP", "yfinance is not installed")
    try:
        df = yf.download("ETH-USD", period="1d", interval="1m", progress=False)
        if df is None or df.empty:
            return record(name, "FAIL", "empty DataFrame")
        last_close = float(df["Close"].iloc[-1].item()) if hasattr(df["Close"].iloc[-1], "item") else float(df["Close"].iloc[-1])
        record(name, "PASS", f"{len(df)} rows, last close={last_close:.2f}")
    except Exception as e:
        record(name, "FAIL", f"{type(e).__name__}: {e}")


def check_ccxt_kraken():
    name = "ccxt_kraken_ohlcv"
    try:
        import ccxt
    except ImportError:
        return record(name, "SKIP", "ccxt is not installed")
    try:
        ex = ccxt.kraken()
        rows = ex.fetch_ohlcv("ETH/USD", timeframe="1m", limit=5)
        if not rows:
            return record(name, "FAIL", "empty OHLCV list")
        record(name, "PASS", f"{len(rows)} candles, last close={rows[-1][4]}")
    except Exception as e:
        record(name, "FAIL", f"{type(e).__name__}: {e}")


def check_feed_registry():
    name = "feed_registry"
    ok = 0
    warned = []
    for feed_id, url in REGISTRY:
        try:
            t0 = time.time()
            r = requests.get(url, timeout=5, headers=HEADERS)
            dt = time.time() - t0
            if r.status_code == 200:
                ok += 1
            else:
                warned.append(f"{feed_id}=HTTP {r.status_code} ({dt:.1f}s)")
        except Exception as e:
            warned.append(f"{feed_id}={type(e).__name__}")
    detail = f"{ok}/{len(REGISTRY)} HTTP 200 ({REGISTRY_SOURCE})"
    if warned:
        detail += "; WARN: " + "; ".join(warned)
    # Any non-200 only warns: sources go down on their own; never fail the run.
    record(name, "WARN" if warned else "PASS", detail)


def check_stocktwits(symbol):
    name = f"stocktwits_{symbol.lower().replace('.', '_')}"
    url = f"https://api.stocktwits.com/api/2/streams/symbol/{symbol}.json"
    try:
        t0 = time.time()
        r = requests.get(url, timeout=10, headers=HEADERS)
        dt = time.time() - t0
        if r.status_code != 200:
            return record(name, "FAIL", f"HTTP {r.status_code} in {dt:.1f}s")
        body = r.json()
        msgs = body.get("messages")
        if not isinstance(msgs, list):
            return record(name, "FAIL", "response has no messages list")
        record(name, "PASS", f"200 in {dt:.1f}s, {len(msgs)} messages")
    except Exception as e:
        record(name, "FAIL", f"{type(e).__name__}: {e}")


def check_omniroute_health():
    name = "omniroute_health"
    try:
        r = requests.get("http://127.0.0.1:20128/api/health", timeout=2, headers=HEADERS)
        if r.status_code == 200:
            return record(name, "PASS", f"200 body={r.text[:120]}")
        record(name, "FAIL", f"HTTP {r.status_code}")
    except Exception:
        # Gateway is optional for the smoke run: not running is a hint, not a failure.
        record(name, "SKIP", "gateway is not running on 127.0.0.1:20128 "
                             "(start it first if you want this checked)")


def check_node_head():
    name = "node_download_head"
    try:
        r = requests.head(NODE_URL, timeout=10, allow_redirects=True, headers=HEADERS)
        if 200 <= r.status_code < 300:
            return record(name, "PASS", f"HEAD {r.status_code} (body not downloaded)")
        record(name, "FAIL", f"HEAD HTTP {r.status_code}")
    except Exception as e:
        record(name, "FAIL", f"{type(e).__name__}: {e}")


def main():
    ap = argparse.ArgumentParser(description="TradeBot0 external connectivity smoke test (read-only).")
    ap.add_argument("--quick", action="store_true",
                    help="only run checks expected to finish within 30s "
                         "(skips WS, Yahoo, CCXT and the FEED_REGISTRY sweep)")
    args = ap.parse_args()
    print(f"TradeBot0 smoke_external.py (quick={args.quick})")

    check_binance_rest()
    check_kraken_rest()
    check_coinbase_rest()
    if not args.quick:
        check_binance_ws()
        check_yahoo()
        check_ccxt_kraken()
        check_feed_registry()
    check_stocktwits("ETH.X")
    check_stocktwits("BTC.X")
    check_omniroute_health()
    check_node_head()

    counts = {}
    for _, status, _ in RESULTS:
        counts[status] = counts.get(status, 0) + 1
    summary = " ".join(f"{k}={v}" for k, v in sorted(counts.items()))
    failed = counts.get("FAIL", 0)
    print(f"SUMMARY {summary} -> {'FAIL' if failed else 'OK'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
