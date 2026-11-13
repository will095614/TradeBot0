"""Item 3: offline mode removed -- disconnect pauses trading, waits to reconnect.

- No cached price is ever served as live.
- Provider cooldowns are respected (no bypass when all are cooling down).
- fill_seq is globally increasing (reset_seq never rewinds).
- _generate_fallback_bars is gone.
"""
import time
import unittest.mock as mock
from decimal import Decimal
from typing import Optional

from src.arena.broker_sim import BrokerSim
from src.arena.order import OrderTicket, OrderSide, OrderType
from src.arena.portfolio import Portfolio
from src.data.live_engine import LiveArenaEngine, LiveQuote


def _quote(price: str, ts: Optional[float] = None, offline: bool = False) -> LiveQuote:
    p = Decimal(price)
    return LiveQuote(
        price=p, bid=p - Decimal("0.05"), ask=p + Decimal("0.05"),
        high_24h=p + Decimal("40"), low_24h=p - Decimal("40"),
        volume_24h=Decimal("1000"), change_24h_pct=Decimal("1.25"),
        source="UnitTest", timestamp=time.time() if ts is None else ts,
        is_offline=offline,
    )


def test_provider_cooldown_respected_when_all_cooling():
    engine = LiveArenaEngine(initial_cash=Decimal("3000.00"))
    engine.latest_quote = _quote("3550.00")
    with mock.patch.object(engine.session, "get", side_effect=Exception("Network Timeout")) as mocked_get:
        first = engine.fetch_realtime_crypto_quote()
        assert first.is_offline is True
        calls_after_first = mocked_get.call_count
        assert calls_after_first > 0  # all three providers were attempted once
        # Immediate retry: every provider is in its 15s cooldown, so no
        # further HTTP attempt may be made -- the backoff must not be bypassed.
        second = engine.fetch_realtime_crypto_quote()
        assert second.is_offline is True
        assert mocked_get.call_count == calls_after_first


def test_is_quote_fresh():
    engine = LiveArenaEngine(initial_cash=Decimal("3000.00"))
    now = time.time()
    assert engine._is_quote_fresh(_quote("3500.00", ts=now), now) is True
    assert engine._is_quote_fresh(_quote("3500.00", ts=now - 60.0), now) is False
    assert engine._is_quote_fresh(_quote("3500.00", ts=now, offline=True), now) is False
    assert engine._is_quote_fresh(_quote("0.00", ts=now), now) is False
    assert engine._is_quote_fresh(None, now) is False


def test_fill_seq_never_rewinds():
    broker = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0.0"))
    p = Portfolio("p1", "Test", initial_cash=Decimal("3000.00"))
    broker.register_portfolio(p, max_position_ratio=Decimal("0.8"))
    broker.on_tick(price=Decimal("2500.00"), timestamp=100.0)
    fill1 = broker.submit_order(OrderTicket("p1", "ETH/USD", OrderSide.BUY, OrderType.MARKET, qty=Decimal("0.1"), timestamp=100.0))
    assert fill1 is not None and fill1.fill_seq == 1
    # Warmup-purge behaviour used to call reset_seq(0): the counter must not rewind.
    broker.reset_seq(0)
    fill2 = broker.submit_order(OrderTicket("p1", "ETH/USD", OrderSide.BUY, OrderType.MARKET, qty=Decimal("0.1"), timestamp=101.0))
    assert fill2 is not None and fill2.fill_seq == 2
    # Restoring from a higher ledger max raises the floor.
    broker.reset_seq(10)
    fill3 = broker.submit_order(OrderTicket("p1", "ETH/USD", OrderSide.BUY, OrderType.MARKET, qty=Decimal("0.1"), timestamp=102.0))
    assert fill3 is not None and fill3.fill_seq == 11


def test_generate_fallback_bars_deleted():
    assert not hasattr(LiveArenaEngine, "_generate_fallback_bars")
