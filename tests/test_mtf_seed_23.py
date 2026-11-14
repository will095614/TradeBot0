"""Audit 2.3: the 1h MTF gate must be real -- seeded 1h history must move
htf_bias off NEUTRAL and the veto must actually block counter-trend entries.
"""
import time
from decimal import Decimal

from src.arena.order import OrderSide
from src.data.eth_feed import CandleBar
from src.data.mtf_engine import MultiTimeframeEngine


def _hourly_bars(n=60, start_price=2000.0, step=10.0, end_age_sec=0.0):
    """Synthetic 1h CandleBars, hourly spaced; last bar ends at the current
    hour open minus end_age_sec (so end_age_sec=0 is fresh)."""
    now = time.time()
    end_ts = float(int(now // 3600) * 3600) - end_age_sec
    bars = []
    price = start_price
    for i in range(n):
        bars.append(CandleBar(
            timestamp=end_ts - (n - 1 - i) * 3600.0,
            open_=Decimal(f"{price:.2f}"),
            high=Decimal(f"{price + 5:.2f}"),
            low=Decimal(f"{price - 5:.2f}"),
            close=Decimal(f"{price:.2f}"),
            volume=Decimal("15.00"),
        ))
        price += step
    return bars


def _minute_bars(n=120, start_price=3500.0):
    """1m-spaced bars shaped like the bootstrap fixtures -- must be rejected
    as 1h history even though they are fresh and numerous."""
    now = time.time()
    bars = []
    price = start_price
    for i in range(n):
        bars.append(CandleBar(
            timestamp=now - (n - i) * 60.0,
            open_=Decimal(f"{price:.2f}"),
            high=Decimal(f"{price + 5:.2f}"),
            low=Decimal(f"{price - 5:.2f}"),
            close=Decimal(f"{price:.2f}"),
            volume=Decimal("15.00"),
        ))
        price += 1.0
    return bars


def _buckets(bars):
    return [{"t": float(b.timestamp), "o": float(b.open), "h": float(b.high),
             "l": float(b.low), "c": float(b.close), "v": float(b.volume)} for b in bars]


def test_seed_1h_buckets_uptrend_goes_bullish_and_vetoes_shorts():
    mtf = MultiTimeframeEngine()
    assert mtf.seed_1h_buckets(_buckets(_hourly_bars(60, 2000.0, 10.0))) == "BULLISH"
    assert mtf.htf_bias == "BULLISH"
    assert len(mtf.candles_1h) == 60
    assert mtf.is_entry_permitted(OrderSide.BUY) is True
    assert mtf.is_entry_permitted(OrderSide.SELL) is False


def test_seed_1h_buckets_downtrend_goes_bearish_and_vetoes_longs():
    mtf = MultiTimeframeEngine()
    assert mtf.seed_1h_buckets(_buckets(_hourly_bars(60, 3000.0, -10.0))) == "BEARISH"
    assert mtf.htf_bias == "BEARISH"
    assert len(mtf.candles_1h) == 60
    assert mtf.is_entry_permitted(OrderSide.BUY) is False
    assert mtf.is_entry_permitted(OrderSide.SELL) is True


def test_seed_1h_buckets_too_few_stays_neutral():
    mtf = MultiTimeframeEngine()
    assert mtf.seed_1h_buckets(_buckets(_hourly_bars(30, 2000.0, 10.0))) == "NEUTRAL"
    assert mtf.htf_bias == "NEUTRAL"
    assert mtf.candles_1h == []
    assert mtf.is_entry_permitted(OrderSide.BUY) is True
    assert mtf.is_entry_permitted(OrderSide.SELL) is True


def test_seed_1h_buckets_rejects_minute_spaced_bars():
    """The bootstrap fixtures / soak bars are 1m-spaced; they must never
    pose as 1h history, even when fresh and numerous."""
    mtf = MultiTimeframeEngine()
    assert mtf.seed_1h_buckets(_buckets(_minute_bars(120))) == "NEUTRAL"
    assert mtf.htf_bias == "NEUTRAL"
    assert mtf.candles_1h == []


def test_seed_1h_buckets_ignores_malformed_rows():
    mtf = MultiTimeframeEngine()
    buckets = _buckets(_hourly_bars(60, 2000.0, 10.0))
    buckets.insert(5, {"t": 0.0, "o": 1.0, "h": 1.0, "l": 1.0, "c": 1.0})  # bad ts
    buckets.insert(10, {"t": 12345.0})  # missing keys
    buckets.insert(15, {"t": 12346.0, "o": -5.0, "h": 1.0, "l": 1.0, "c": 1.0})  # negative
    assert mtf.seed_1h_buckets(buckets) == "BULLISH"
    assert len(mtf.candles_1h) == 60


def test_seed_rejects_bad_seed_without_clobbering_good_history():
    mtf = MultiTimeframeEngine()
    assert mtf.seed_1h_buckets(_buckets(_hourly_bars(60, 2000.0, 10.0))) == "BULLISH"
    assert mtf.seed_1h_buckets(_buckets(_minute_bars(120))) == "BULLISH"
    assert mtf.htf_bias == "BULLISH"
    assert len(mtf.candles_1h) == 60


def test_engine_seed_wires_bias_and_survives_live_bar(monkeypatch):
    from src.data.live_engine import LiveArenaEngine
    bars = _hourly_bars(60, 2000.0, 10.0)
    monkeypatch.setattr("src.data.live_engine.ETHFeed.fetch_historical_bars",
                        staticmethod(lambda *a, **k: bars))
    engine = LiveArenaEngine()
    engine._seed_mtf_1h_history()
    assert engine.htf_bias == "BULLISH"
    assert len(engine.candles_1h) == 60
    assert engine.is_entry_permitted_by_mtf(OrderSide.SELL) is False
    assert engine.is_entry_permitted_by_mtf(OrderSide.BUY) is True
    # A later live 1m bar must merge into the seeded history, not clobber it.
    last_close = float(bars[-1].close)
    now = time.time()
    engine._update_mtf_regimes({"t": float(int(now // 60) * 60), "o": last_close,
                                "h": last_close + 5.0, "l": last_close - 5.0,
                                "c": last_close + 2.0})
    assert len(engine.candles_1h) == 60
    assert engine.htf_bias == "BULLISH"
    assert engine.is_entry_permitted_by_mtf(OrderSide.SELL) is False


def test_engine_seed_fetch_failure_stays_neutral(monkeypatch):
    from src.data.live_engine import LiveArenaEngine

    def _boom(*a, **k):
        raise RuntimeError("feed down")

    monkeypatch.setattr("src.data.live_engine.ETHFeed.fetch_historical_bars",
                        staticmethod(_boom))
    engine = LiveArenaEngine()
    engine._seed_mtf_1h_history()
    assert engine.htf_bias == "NEUTRAL"
    assert engine.candles_1h == []
    assert engine.is_entry_permitted_by_mtf(OrderSide.BUY) is True
    assert engine.is_entry_permitted_by_mtf(OrderSide.SELL) is True


def test_engine_seed_rejects_stale_bars(monkeypatch):
    from src.data.live_engine import LiveArenaEngine
    bars = _hourly_bars(60, 2000.0, 10.0, end_age_sec=5 * 3600)
    monkeypatch.setattr("src.data.live_engine.ETHFeed.fetch_historical_bars",
                        staticmethod(lambda *a, **k: bars))
    engine = LiveArenaEngine()
    engine._seed_mtf_1h_history()
    assert engine.htf_bias == "NEUTRAL"
    assert engine.candles_1h == []
