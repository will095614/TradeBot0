"""Item 3 follow-up patch (after first pytest run: 7 failed, 108 passed).

1. Overlay copy must be English: the project enforces zero CJK in frontend
   assets (test_zero_cjk_in_frontend_assets and friends).
2. Four tests relied on bootstrap always producing candles. Under
   ARENA_FAST_TEST=1 the live feed returns no bars and the test SQLite cache
   is empty, so previously only the (now deleted) synthetic fallback supplied
   candles. Seed those tests with deterministic fixture bars via a mocked
   ETHFeed.fetch_historical_bars instead of reintroducing production
   fabrication.

Usage: python fix_item3_patch2.py [project_root]
Verifies EVERY replacement anchor appears exactly once before writing anything.
"""
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
assert (ROOT / "src/data/live_engine.py").exists(), f"not a TradeBot0 root: {ROOT}"

REPLACEMENTS = []


def rep(rel, old, new):
    REPLACEMENTS.append((rel, old, new))


def _read(path):
    raw = path.read_bytes()
    crlf = b"\r\n" in raw
    text = raw.decode("utf-8")
    if crlf:
        text = text.replace("\r\n", "\n")
    return text, crlf


def _write(path, text, crlf):
    if crlf:
        text = text.replace("\n", "\r\n")
    path.write_bytes(text.encode("utf-8"))


FIXTURE_HELPER = '''def _fixture_bars(n=120):
    """Deterministic test-only candles so bootstrap has a warm chart.

    Tests run with ARENA_FAST_TEST=1, so the live feed returns no bars and
    the test SQLite cache is empty; previously the (now deleted) synthetic
    fallback supplied these. Fixture data, never production data.
    """
    import time
    from decimal import Decimal
    from src.data.eth_feed import CandleBar

    now = time.time()
    bars = []
    price = 3500.0
    for i in range(n):
        bars.append(CandleBar(
            timestamp=now - (n - i) * 60.0,
            open_=Decimal(f"{price:.2f}"),
            high=Decimal(f"{price + 5:.2f}"),
            low=Decimal(f"{price - 5:.2f}"),
            close=Decimal(f"{price:.2f}"),
            volume=Decimal("15.00"),
            ema_fast=Decimal(f"{price:.2f}"),
            ema_slow=Decimal(f"{price:.2f}"),
            rsi=Decimal("50.00"),
            atr=Decimal("12.00"),
        ))
        price += 1.0
    return bars


'''

SEED_LINE = '''    # Tests run with ARENA_FAST_TEST=1, so no real bars are fetched; seed the
    # bootstrap with deterministic fixture bars (test-only data).
    monkeypatch.setattr("src.data.live_engine.ETHFeed.fetch_historical_bars", staticmethod(lambda *a, **k: _fixture_bars()))
'''

# ---------------------------------------------------------------- index.html: English overlay copy
rep("src/gui/assets/index.html",
    '''        <div class="splash-title">網路已斷線 <span class="splash-highlight">等待重新連線</span></div>
        <div class="splash-subtitle">交易已暫停 · 恢復連線後自動繼續</div>
      </div>
      <div class="splash-footer-note">
        <span class="live-dot" style="margin-right:7px;"></span>
        <span>請檢查網路連線 · 遮罩會在連線恢復時自動解除</span>
      </div>''',
    '''        <div class="splash-title">Network Offline <span class="splash-highlight">Waiting to Reconnect</span></div>
        <div class="splash-subtitle">Trading paused · resumes automatically when the connection returns</div>
      </div>
      <div class="splash-footer-note">
        <span class="live-dot" style="margin-right:7px;"></span>
        <span>Check your network connection · this overlay clears automatically on reconnect</span>
      </div>''')

# ---------------------------------------------------------------- test_phase1_cadence_and_ranking.py
P1 = "tests/test_phase1_cadence_and_ranking.py"
rep(P1,
    """from src.data.live_engine import LiveArenaEngine


def test_leaderboard_ranked_strictly_by_total_equity():""",
    "from src.data.live_engine import LiveArenaEngine\n\n\n" + FIXTURE_HELPER + "def test_leaderboard_ranked_strictly_by_total_equity():")

rep(P1,
    '''def test_candle_cadence_dispatcher_timing_and_dispatch():
    """
    Verify that LiveArenaEngine's CandleCadenceDispatcher maintains stable
    candle slice publication at the configured cadence_sec.
    """
    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    engine.bootstrap_intraday_session()''',
    '''def test_candle_cadence_dispatcher_timing_and_dispatch(monkeypatch):
    """
    Verify that LiveArenaEngine's CandleCadenceDispatcher maintains stable
    candle slice publication at the configured cadence_sec.
    """
''' + SEED_LINE + '''    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    engine.bootstrap_intraday_session()''')

rep(P1,
    '''def test_micro_bar_aggregation_preserves_wick_extremes_r1():
    """
    [R1 Checkpoint] Verify that intermediate high spike and low flush
    inside a slice are preserved in micro-bar aggregation and never discarded.
    """
    from src.data.live_engine import LiveQuote
    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    engine.bootstrap_intraday_session()''',
    '''def test_micro_bar_aggregation_preserves_wick_extremes_r1(monkeypatch):
    """
    [R1 Checkpoint] Verify that intermediate high spike and low flush
    inside a slice are preserved in micro-bar aggregation and never discarded.
    """
    from src.data.live_engine import LiveQuote
''' + SEED_LINE + '''    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    engine.bootstrap_intraday_session()''')

# ---------------------------------------------------------------- test_live_engine.py
rep("tests/test_live_engine.py",
    '''def test_lifecycle_sequence_warmup_before_live_orders():
    engine = LiveArenaEngine(initial_cash=Decimal("500000.00"), symbol="ETH/USD")''',
    FIXTURE_HELPER + '''def test_lifecycle_sequence_warmup_before_live_orders(monkeypatch):
''' + SEED_LINE + '''    engine = LiveArenaEngine(initial_cash=Decimal("500000.00"), symbol="ETH/USD")''')

# ---------------------------------------------------------------- test_debug_report_fixes.py
rep("tests/test_debug_report_fixes.py",
    '''def test_offline_start_does_not_execute_stale_candles():
    """Verify Verification §3.2: start_live_trading with offline quote does not open orders from last candle."""
    os.environ["ARENA_FAST_TEST"] = "1"
    engine = LiveArenaEngine(symbol="ETH/USD", initial_cash=Decimal("100000.00"))
    engine.bootstrap_intraday_session()''',
    FIXTURE_HELPER + '''def test_offline_start_does_not_execute_stale_candles(monkeypatch):
    """Verify Verification §3.2: start_live_trading with offline quote does not open orders from last candle."""
    os.environ["ARENA_FAST_TEST"] = "1"
''' + SEED_LINE + '''    engine = LiveArenaEngine(symbol="ETH/USD", initial_cash=Decimal("100000.00"))
    engine.bootstrap_intraday_session()''')


def main():
    files = {}
    for rel, _old, _new in REPLACEMENTS:
        files.setdefault(rel, _read(ROOT / rel))
    for rel, old, _new in REPLACEMENTS:
        text, _crlf = files[rel]
        n = text.count(old)
        assert n == 1, f"{rel}: expected exactly 1 occurrence, found {n}: {old[:100]!r}"
    print(f"All {len(REPLACEMENTS)} anchors verified.")
    new_texts = {rel: text for rel, (text, _c) in files.items()}
    for rel, old, new in REPLACEMENTS:
        new_texts[rel] = new_texts[rel].replace(old, new, 1)
    for rel, text in new_texts.items():
        _write(ROOT / rel, text, files[rel][1])
        print(f"patched {rel}")
    print("ITEM3 PATCH2 OK")


if __name__ == "__main__":
    main()
