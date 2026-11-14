"""Audit 3.16: the bootstrap block `if not live_orders_enabled:` had one
dead line -- `self.live_orders_enabled = False` inside its own `not`
branch -- and two real resets. The dead line was deleted; this test
pins the surviving behaviour: with orders disabled, bootstrap clears
any stale live-trading-active state.
"""
import time
from decimal import Decimal

from src.data.eth_feed import CandleBar
from src.data.live_engine import LiveArenaEngine


def _fixture_bars(n=120):
    now = time.time()
    price = 3500.0
    bars = []
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
        ))
        price += 1.0
    return bars


def test_bootstrap_resets_live_trading_state_when_orders_disabled(monkeypatch):
    monkeypatch.setattr(
        "src.data.live_engine.ETHFeed.fetch_historical_bars",
        staticmethod(lambda *a, **k: _fixture_bars()),
    )
    engine = LiveArenaEngine(initial_cash=Decimal("500000.00"), symbol="ETH/USD")
    assert engine.live_orders_enabled is False
    # Simulate stale state from a previous session (e.g. restored state
    # while orders were off): the surviving reset lines must clear it.
    engine.live_trading_active = True
    engine.live_start_ts = 12345.0

    engine.bootstrap_intraday_session()

    assert engine.is_bootstrapped is True
    assert engine.live_orders_enabled is False
    assert engine.live_trading_active is False
    assert engine.live_start_ts is None
