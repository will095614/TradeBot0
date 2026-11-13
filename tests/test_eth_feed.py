"""External-feed mock tests: Yahoo Finance / CCXT fallback (eth_feed).

All network access is mocked; no real HTTP is performed.
"""
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.data.eth_feed import CandleBar, ETHFeed

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

N_BARS = 30  # Bollinger window is 20 -> first 19 rows are dropped, 11 bars out


def _yahoo_dataframe():
    """Fixed 30-row Yahoo-style DataFrame (flat columns, 15m bars)."""
    idx = pd.date_range("2026-11-01 00:00", periods=N_BARS, freq="15min", tz="UTC")
    closes = [3000.00 + 2.0 * i + (0.50 if i % 2 else 0.0) for i in range(N_BARS)]
    return pd.DataFrame(
        {
            "Open": [c - 1.00 for c in closes],
            "High": [c + 1.50 for c in closes],
            "Low": [c - 2.00 for c in closes],
            "Close": closes,
            "Volume": [100.0 + float(i) for i in range(N_BARS)],
        },
        index=idx,
    )


def _ccxt_ohlcv():
    """Fixed 30-row CCXT OHLCV: [ms, open, high, low, close, volume]."""
    base_ms = 1761955200000  # 2026-11-01 00:00:00 UTC
    rows = []
    for i in range(N_BARS):
        c = 3000.00 + 2.0 * i + (0.50 if i % 2 else 0.0)
        rows.append([base_ms + i * 900_000, c - 1.00, c + 1.50, c - 2.00, c, 100.0 + float(i)])
    return rows


def _bar(**over):
    """Hand-built CandleBar with sane defaults for generate_signal tests."""
    kw = dict(
        timestamp=1700000000.0,
        open_=Decimal("3000.00"),
        high=Decimal("3010.00"),
        low=Decimal("2990.00"),
        close=Decimal("3005.00"),
        volume=Decimal("100.00"),
        ema_fast=Decimal("3002.00"),
        ema_slow=Decimal("3000.00"),
        ema_macro=Decimal("2990.00"),
        rsi=Decimal("55.00"),
        atr=Decimal("10.00"),
        bb_upper=Decimal("3050.00"),
        bb_lower=Decimal("2950.00"),
        macd_hist=Decimal("0.50"),
    )
    kw.update(over)
    return CandleBar(**kw)


# ---------------------------------------------------------------------------
# fetch_historical_bars via Yahoo
# ---------------------------------------------------------------------------

def test_fetch_historical_bars_yahoo_success(monkeypatch):
    monkeypatch.delenv("ARENA_FAST_TEST", raising=False)
    df = _yahoo_dataframe()
    mock_kraken = MagicMock()
    with (
        patch("yfinance.download", return_value=df) as mock_dl,
        patch("ccxt.kraken", mock_kraken),
    ):
        bars = ETHFeed.fetch_historical_bars(ticker="ETH-USD", period="1mo", interval="15m")

    # Yahoo called once with the requested ticker/period/interval; no fallback.
    mock_dl.assert_called_once()
    assert mock_dl.call_args.args[0] == "ETH-USD"
    mock_kraken.assert_not_called()

    # Bollinger window (20) drops the first 19 rows.
    assert len(bars) == N_BARS - 19
    closes = list(df["Close"])
    for k, bar in enumerate(bars):
        i = 19 + k
        assert bar.timestamp == pytest.approx(df.index[i].timestamp())
        assert bar.open == Decimal(f"{closes[i] - 1.00:.2f}")
        assert bar.high == Decimal(f"{closes[i] + 1.50:.2f}")
        assert bar.low == Decimal(f"{closes[i] - 2.00:.2f}")
        assert bar.close == Decimal(f"{closes[i]:.2f}")
        assert bar.volume == Decimal(f"{100.0 + i:.4f}")
        # Indicators are computed for every returned bar.
        for field in ("ema_fast", "ema_slow", "ema_macro", "rsi", "atr",
                      "bb_upper", "bb_lower", "macd_hist"):
            assert getattr(bar, field) is not None, f"{field} is None on bar {k}"
    assert [b.timestamp for b in bars] == sorted(b.timestamp for b in bars)

    # generate_signal on the fixed fetched sequence: deterministic, valid label.
    sig1 = ETHFeed.generate_signal(bars[-1], bars[-2])
    sig2 = ETHFeed.generate_signal(bars[-1], bars[-2])
    assert sig1 == sig2
    assert sig1 in ("BUY", "SELL", "HOLD")
    assert ETHFeed.generate_signal(bars[-1], None) == "HOLD"


def test_fetch_historical_bars_yahoo_multiindex_columns(monkeypatch):
    """yfinance multi-ticker shape (MultiIndex columns) is flattened."""
    monkeypatch.delenv("ARENA_FAST_TEST", raising=False)
    df = _yahoo_dataframe()
    df.columns = pd.MultiIndex.from_product(
        [["Open", "High", "Low", "Close", "Volume"], ["ETH-USD"]]
    )
    with patch("yfinance.download", return_value=df):
        bars = ETHFeed.fetch_historical_bars(ticker="ETH-USD")
    assert len(bars) == N_BARS - 19
    assert bars[0].close == Decimal(f"{list(_yahoo_dataframe()['Close'])[19]:.2f}")


# ---------------------------------------------------------------------------
# CCXT Kraken fallback
# ---------------------------------------------------------------------------

def test_fetch_dataframe_falls_back_to_ccxt_kraken(monkeypatch):
    monkeypatch.delenv("ARENA_FAST_TEST", raising=False)
    mock_exchange = MagicMock()
    mock_exchange.fetch_ohlcv.return_value = _ccxt_ohlcv()
    with (
        patch("yfinance.download", side_effect=RuntimeError("yahoo down")),
        patch("ccxt.kraken", return_value=mock_exchange) as mock_kraken,
    ):
        bars = ETHFeed.fetch_historical_bars(ticker="ETH-USD", period="1mo", interval="15m")

    # Kraken built once with rate-limit/timeout opts; ETH-USD mapped to ETH/USD.
    mock_kraken.assert_called_once()
    assert mock_kraken.call_args.args[0] == {"enableRateLimit": True, "timeout": 2500}
    mock_exchange.fetch_ohlcv.assert_called_once_with("ETH/USD", timeframe="15m", limit=720)

    assert len(bars) == N_BARS - 19
    rows = _ccxt_ohlcv()
    for k, bar in enumerate(bars):
        i = 19 + k
        ms, o, h, low, c, v = rows[i]
        assert bar.timestamp == pytest.approx(ms / 1000.0)
        assert bar.open == Decimal(f"{o:.2f}")
        assert bar.high == Decimal(f"{h:.2f}")
        assert bar.low == Decimal(f"{low:.2f}")
        assert bar.close == Decimal(f"{c:.2f}")
        assert bar.volume == Decimal(f"{v:.4f}")


def test_fetch_dataframe_both_sources_fail_raises(monkeypatch):
    """Yahoo down AND CCXT down: _fetch_dataframe returns empty -> ValueError."""
    monkeypatch.delenv("ARENA_FAST_TEST", raising=False)
    with (
        patch("yfinance.download", side_effect=RuntimeError("yahoo down")),
        patch("ccxt.kraken", side_effect=RuntimeError("kraken down")),
    ):
        with pytest.raises(ValueError, match="No market data returned for ETH-USD"):
            ETHFeed.fetch_historical_bars(ticker="ETH-USD")


# ---------------------------------------------------------------------------
# generate_signal branches on hand-built bars
# ---------------------------------------------------------------------------

def test_generate_signal_synthetic_path():
    # macd_hist=None -> synthetic compatibility path.
    prev = _bar(ema_fast=Decimal("100.00"), ema_slow=Decimal("110.00"),
                rsi=Decimal("50.00"), macd_hist=None)
    bar = _bar(ema_fast=Decimal("112.00"), ema_slow=Decimal("110.00"),
               rsi=Decimal("60.00"), macd_hist=None)
    assert ETHFeed.generate_signal(bar, prev) == "BUY"  # golden cross

    prev = _bar(ema_fast=Decimal("110.00"), ema_slow=Decimal("100.00"),
                rsi=Decimal("55.00"), macd_hist=None)
    bar = _bar(ema_fast=Decimal("115.00"), ema_slow=Decimal("100.00"),
               close=Decimal("3010.00"), rsi=Decimal("60.00"), macd_hist=None)
    assert ETHFeed.generate_signal(bar, prev) == "BUY"  # trend continuation

    prev = _bar(ema_fast=Decimal("110.00"), ema_slow=Decimal("100.00"), macd_hist=None)
    bar = _bar(ema_fast=Decimal("98.00"), ema_slow=Decimal("100.00"), macd_hist=None)
    assert ETHFeed.generate_signal(bar, prev) == "SELL"  # cross down

    prev = _bar(ema_fast=Decimal("110.00"), ema_slow=Decimal("100.00"), macd_hist=None)
    bar = _bar(ema_fast=Decimal("115.00"), ema_slow=Decimal("100.00"),
               close=Decimal("3001.00"), rsi=Decimal("80.00"), macd_hist=None)
    assert ETHFeed.generate_signal(bar, prev) == "SELL"  # overbought rsi > 78

    prev = _bar(ema_fast=Decimal("110.00"), ema_slow=Decimal("100.00"),
                rsi=Decimal("50.00"), macd_hist=None)
    bar = _bar(ema_fast=Decimal("111.00"), ema_slow=Decimal("100.00"),
               close=Decimal("3001.00"), rsi=Decimal("70.00"), macd_hist=None)
    # rsi 70 fails the continuation branch (needs < 65) and the SELL branch
    # (needs > 78): HOLD.
    assert ETHFeed.generate_signal(bar, prev) == "HOLD"


def test_generate_signal_real_path_setups_and_exits():
    # Setup 1: macro uptrend + golden cross + bullish reclaim + rising MACD.
    prev = _bar(ema_fast=Decimal("2998.00"), ema_slow=Decimal("3000.00"),
                high=Decimal("3004.00"), macd_hist=Decimal("0.10"))
    bar = _bar(open_=Decimal("3001.00"), close=Decimal("3006.00"),
               ema_fast=Decimal("3002.00"), ema_slow=Decimal("3000.00"),
               rsi=Decimal("60.00"), macd_hist=Decimal("0.50"))
    assert ETHFeed.generate_signal(bar, prev) == "BUY"

    # Setup 2: capitulation reversal (prev pierced lower band, rsi < 27.5,
    # then strong bullish reclaim). Trend is down so Setup 1 cannot fire.
    prev = _bar(ema_fast=Decimal("2990.00"), ema_slow=Decimal("3000.00"),
                high=Decimal("2940.00"), low=Decimal("2890.00"),
                bb_lower=Decimal("2900.00"),
                rsi=Decimal("25.00"), macd_hist=Decimal("0.10"))
    bar = _bar(open_=Decimal("2900.00"), close=Decimal("2950.00"),
               high=Decimal("2955.00"), ema_fast=Decimal("2990.00"),
               ema_slow=Decimal("3000.00"), rsi=Decimal("29.00"),
               macd_hist=Decimal("0.50"))
    assert ETHFeed.generate_signal(bar, prev) == "BUY"

    # Exit: fast EMA crosses below slow with negative MACD.
    prev = _bar(ema_fast=Decimal("3010.00"), ema_slow=Decimal("3000.00"),
                macd_hist=Decimal("0.10"))
    bar = _bar(ema_fast=Decimal("2995.00"), ema_slow=Decimal("3000.00"),
               macd_hist=Decimal("-0.50"))
    assert ETHFeed.generate_signal(bar, prev) == "SELL"

    # Exit: rsi > 73 on a bearish candle.
    prev = _bar(macd_hist=Decimal("0.10"))
    bar = _bar(open_=Decimal("3010.00"), close=Decimal("3005.00"),
               rsi=Decimal("75.00"), macd_hist=Decimal("0.40"))
    assert ETHFeed.generate_signal(bar, prev) == "SELL"

    # No setup: trend up, rsi mid, MACD negative -> HOLD.
    prev = _bar(macd_hist=Decimal("-0.10"))
    bar = _bar(macd_hist=Decimal("-0.20"), rsi=Decimal("50.00"))
    assert ETHFeed.generate_signal(bar, prev) == "HOLD"
