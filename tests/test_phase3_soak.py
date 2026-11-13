"""Phase 3 soak smoke test (slow, skipped by default).

Runs a miniature version of scripts/soak_engine.py -- a few hundred
accelerated ticks of the real per-cadence slice body with synthetic
sine+noise prices, mocked feeds, zero network -- plus the compact
circuit-breaker trip/reset scenario. It is a smoke test, not the soak
itself: the full soak (15,000 ticks, ~4.2 sim-hours) lives in
scripts/soak_engine.py and is run on demand, never inside pytest.

Run it explicitly with:
    TRADEBOT0_RUN_SOAK=1 python -m pytest tests/test_phase3_soak.py -q
"""
import importlib.util
import os
import random
import time
from decimal import Decimal
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("TRADEBOT0_RUN_SOAK") != "1",
    reason="slow soak smoke test; set TRADEBOT0_RUN_SOAK=1 to run",
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_soak_helpers():
    spec = importlib.util.spec_from_file_location(
        "soak_engine", REPO_ROOT / "scripts" / "soak_engine.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def soak():
    return _load_soak_helpers()


def _bootstrapped_engine(soak, tmp_path, monkeypatch):
    from src.data.eth_feed import ETHFeed
    from src.data.live_engine import LiveArenaEngine
    from src.data.persistence import ArenaStorage

    storage = ArenaStorage(db_path=str(tmp_path / "arena_history.db"))
    eng = LiveArenaEngine(storage=storage,
                          initial_cash=Decimal("500000.00"), symbol="ETH/USD")
    bars = soak.synth_bars(120)
    monkeypatch.setattr(ETHFeed, "fetch_historical_bars",
                        classmethod(lambda cls, **kw: list(bars)))
    eng.auto_evolve_enabled = True
    eng.intel_refresh_interval_sec = 3600.0 * 24
    eng.last_intel_refresh_ts = time.time()
    eng.bootstrap_intraday_session()
    eng.live_orders_enabled = True
    return eng, bars


def test_p3_mini_soak_many_ticks_no_growth_blowup(soak, tmp_path, monkeypatch):
    """600 accelerated ticks: no crash, fills happen, bounded structures stay bounded."""
    eng, bars = _bootstrapped_engine(soak, tmp_path, monkeypatch)
    rng = random.Random(20261113 + 1)
    price = bars[-1].close
    slot0 = int(time.time())
    try:
        for i in range(600):
            prev = price
            price = soak.synth_price(i, rng)
            soak.do_slice(eng, price, prev, slot0 + i)
            # Real auto-evolve trigger check, exactly like _live_loop.
            if eng._auto_evolve_reason(now=float(slot0 + i)) is not None:
                eng.evolve_now(trigger="auto:test")
        assert eng.tick_count == 600
        assert len(eng.fill_records) > 0, "volatile series should produce fills"
        assert eng._closed_trades_since_evolve > 0
        # Bounded structures (Phase 1 caps) hold under sustained ticks.
        assert len(eng.candles) <= eng.max_candles
        assert len(eng.live_logs) <= 120
        assert len(eng.fill_records) <= 200
        assert len(eng.broker.rejection_audit) <= 500
        for c in eng.competitors:
            assert len(c.portfolio.equity_history) <= 2000
            assert not soak.genome_valid(c), f"{c.portfolio_id} genome invalid"
        # One forced generation advance: genomes stay valid, gen +1.
        gen_before = max(c.genome.generation for c in eng.competitors)
        eng.last_evolve_ts = time.time() - (eng.auto_evolve_interval_sec + 1)
        assert eng._auto_evolve_reason(now=time.time()) == "time"
        eng.evolve_now(trigger="auto:time")
        assert max(c.genome.generation for c in eng.competitors) == gen_before + 1
        for c in eng.competitors:
            assert not soak.genome_valid(c)
        # Save / restore round-trips the generation.
        assert eng.save_session_state()
        from src.data.live_engine import LiveArenaEngine
        from src.data.persistence import ArenaStorage
        eng2 = LiveArenaEngine(
            storage=ArenaStorage(db_path=str(tmp_path / "arena_history.db")),
            initial_cash=Decimal("500000.00"), symbol="ETH/USD")
        assert eng2.restore_session_state()
        assert max(c.genome.generation for c in eng2.competitors) == gen_before + 1
        eng2.stop()
    finally:
        eng.stop()


def test_p3_breaker_trips_force_closes_and_resets_on_evolve(soak, tmp_path, monkeypatch):
    """Engineered crash: breaker trips + force-closes, blocks re-entry,
    and the next generation resets it so trading resumes (Phase 1 / item 4)."""
    from src.arena.order import ExecutionReason, OrderSide, OrderTicket, OrderType
    eng, bars = _bootstrapped_engine(soak, tmp_path, monkeypatch)
    try:
        comp = eng.comp_a  # Aggressive, position_ratio 0.70 (largest cap)
        p = comp.portfolio
        entry = Decimal("3500.00")
        # Naked long, no TP/SL bracket: only the breaker can exit it.
        fill = eng.broker.submit_order(OrderTicket(
            portfolio_id=comp.portfolio_id, symbol="ETH/USD",
            side=OrderSide.BUY, order_type=OrderType.MARKET,
            qty=Decimal("90"), price=entry,
            reason=ExecutionReason.SIGNAL_ENTRY, timestamp=time.time()))
        assert fill is not None
        assert p.position_qty == Decimal("90")
        prev = entry
        for k in range(1, 26):
            crash = (entry * (Decimal("1") - Decimal("0.35") * Decimal(k) / Decimal("25"))).quantize(Decimal("0.01"))
            with eng.lock:
                eng.broker.on_tick(price=crash, high=prev, low=crash,
                                   timestamp=time.time(), open_price=prev)
                eng._harvest_fills()
            prev = crash
            if p.is_circuit_breaker_tripped:
                break
        assert p.is_circuit_breaker_tripped
        assert float(p.max_drawdown_pct) >= 15.0
        assert p.position_qty == Decimal("0")
        assert any(f.reason.value == "CIRCUIT_BREAKER" for f in eng.fill_records)
        # Blocked re-entry while tripped.
        blocked = eng.broker.submit_order(OrderTicket(
            portfolio_id=comp.portfolio_id, symbol="ETH/USD",
            side=OrderSide.BUY, order_type=OrderType.MARKET,
            qty=Decimal("1"), price=Decimal("2300.00"),
            reason=ExecutionReason.SIGNAL_ENTRY, timestamp=time.time()))
        assert blocked is None
        # Generation boundary resets the breaker (flag + drawdown + peak).
        eng.evolve_now(trigger="soak:breaker-reset")
        assert not p.is_circuit_breaker_tripped
        assert p.max_drawdown_pct == Decimal("0.00")
        assert p.peak_equity == p.total_equity
        # Trading resumes.
        resumed = eng.broker.submit_order(OrderTicket(
            portfolio_id=comp.portfolio_id, symbol="ETH/USD",
            side=OrderSide.BUY, order_type=OrderType.MARKET,
            qty=Decimal("1"), price=Decimal("2300.00"),
            reason=ExecutionReason.SIGNAL_ENTRY, timestamp=time.time()))
        assert resumed is not None
        assert p.position_qty == Decimal("1")
    finally:
        eng.stop()
