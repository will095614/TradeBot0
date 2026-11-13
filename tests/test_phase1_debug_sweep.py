"""Phase 1 debug-sweep regression tests (2026-11-13).

Each test pins one Phase 1 fix: concurrent intel refresh, cooldown
bypass in forced entries, garbage-ticket restore abort, double live
loop, unclosed quote session, stale slice ticks, broker-rejection
retry storm, gateway double-spawn, and atexit retention.
"""
import asyncio
import gc
import threading
import time
import weakref
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import MagicMock, patch

from src.arena.broker_sim import BrokerSim
from src.arena.order import OrderSide, OrderTicket, OrderType
from src.data.live_engine import LiveArenaEngine, LiveQuote
from src.data.persistence import ArenaStorage
from src.intelligence.gateway_supervisor import GatewaySupervisor


def _quote(price: str) -> LiveQuote:
    p = Decimal(price)
    return LiveQuote(
        price=p, bid=p - Decimal("0.05"), ask=p + Decimal("0.05"),
        high_24h=p + Decimal("40"), low_24h=p - Decimal("40"),
        volume_24h=Decimal("1000"), change_24h_pct=Decimal("1.25"),
        source="UnitTest", timestamp=time.time(),
    )


# ---------------------------------------------------------------- F1
def test_refresh_intel_digest_is_serialized_under_concurrent_calls():
    """Two threads calling refresh_intel_digest at once must not run two
    digests concurrently: the loser's finally would close the shared
    aiohttp session while the winner is still using it."""
    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    state = {"current": 0, "max": 0}
    lock = threading.Lock()

    async def fake_refresh():
        with lock:
            state["current"] += 1
            state["max"] = max(state["max"], state["current"])
        await asyncio.sleep(0.2)
        with lock:
            state["current"] -= 1
        return engine.macro_commander.current_state

    engine.macro_commander.refresh_digest_async = fake_refresh
    engine.macro_commander.get_intel_hub_telemetry = lambda: {}
    errors = []

    def _run():
        err = _safe_refresh(engine)
        if err is not None:
            errors.append(err)

    threads = []
    for _ in range(5):
        t = threading.Thread(target=_run, daemon=True)
        threads.append(t)
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert not errors
    assert state["max"] == 1


def _safe_refresh(engine):
    try:
        engine.refresh_intel_digest()
        return None
    except Exception as e:  # pragma: no cover - surfaced via errors list
        return e


# ---------------------------------------------------------------- F2
def test_ensure_active_live_positions_respects_strategy_cooldown():
    """A strategy inside its 60 s post-close cooldown must not be
    force-re-entered by _ensure_active_live_positions on the next cadence."""
    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    engine.broker.on_tick(price=Decimal("3500.00"), timestamp=1700000000.0)
    engine.live_ema_fast = Decimal("3490.00")
    engine.live_ema_slow = Decimal("3500.00")
    engine.live_rsi = Decimal("60.00")
    engine.live_atr = Decimal("20.00")
    engine.live_orb_high = Decimal("3600.00")
    engine.live_orb_low = Decimal("3500.00")
    engine.live_typical_mean = Decimal("3600.00")
    engine.htf_bias = "NEUTRAL"
    ts = 1700000000.0
    engine.strategy_cooldown["comp_agg"] = ts + 3600.0  # still cooling down
    engine._ensure_active_live_positions(Decimal("3500.00"), ts)
    assert engine.comp_a.portfolio.position_qty == Decimal("0")
    assert engine.comp_a.portfolio.position_side.value == "FLAT"
    for c in engine.competitors[1:]:
        assert c.portfolio.position_qty > Decimal("0"), c.portfolio_id
        assert c.portfolio.position_side.value == "SHORT", c.portfolio_id


# ---------------------------------------------------------------- F3
def test_deserialize_ticket_garbage_numbers_return_none():
    bad_qty = {
        "portfolio_id": "comp_agg", "side": "BUY", "order_type": "MARKET",
        "qty": "abc", "price": "3500",
    }
    assert LiveArenaEngine._deserialize_ticket(bad_qty) is None
    bad_price = {
        "portfolio_id": "comp_agg", "side": "BUY", "order_type": "MARKET",
        "qty": "1", "price": {"not": "a number"},
    }
    assert LiveArenaEngine._deserialize_ticket(bad_price) is None
    bad_stop = {
        "portfolio_id": "comp_agg", "side": "BUY", "order_type": "STOP_MARKET",
        "qty": "1", "price": "3400", "stop_loss": [1, 2, 3],
    }
    assert LiveArenaEngine._deserialize_ticket(bad_stop) is None


def test_restore_survives_garbage_stop_ticket_and_entry_ts(tmp_path):
    """One corrupt stop ticket (or entry timestamp) used to abort the
    whole session restore; the rest of the snapshot must still load."""
    db = tmp_path / "arena_history.db"
    storage = ArenaStorage(db_path=str(db))
    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"), storage=storage)
    engine.live_orders_enabled = True
    assert engine.save_session_state() is True
    snapshot = storage.load_session_snapshot()
    assert snapshot is not None
    snapshot["active_stops"] = {
        "comp_agg": {
            "portfolio_id": "comp_agg", "side": "BUY",
            "order_type": "STOP_MARKET", "qty": "abc", "price": "3400",
        }
    }
    snapshot["position_entry_ts"] = {"comp_agg": "not-a-timestamp"}
    engine2 = LiveArenaEngine(initial_cash=Decimal("100000.00"), storage=storage)
    assert engine2.restore_session_state(snapshot) is True
    assert engine2._has_restored_session is True


# ---------------------------------------------------------------- F4
def test_start_live_loop_refuses_second_thread_while_old_alive():
    """If the previous worker thread has not exited after stop(), starting
    the loop again must not spawn a second thread on the same engine."""
    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    gate = threading.Event()
    dummy = threading.Thread(target=gate.wait, args=(30.0,), daemon=True)
    dummy.start()
    engine.worker_thread = dummy
    engine.running = False
    try:
        engine.start_live_loop()
    finally:
        gate.set()
        dummy.join(timeout=5)
    assert engine.running is False
    assert engine.worker_thread is dummy


# ---------------------------------------------------------------- F6
class _OKHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *a):
        pass


def test_engine_stop_closes_quote_session_pool():
    """stop() must release the requests keep-alive pool (each reset builds
    a new engine + Session), and the session must stay usable afterwards."""
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _OKHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
        url = f"http://127.0.0.1:{srv.server_address[1]}/"
        assert engine.session.get(url, timeout=5).status_code == 200
        pools = engine.session.adapters["http://"].poolmanager.pools
        assert len(pools) >= 1
        engine.stop()
        # RecentlyUsedContainer forbids iteration/== on this urllib3
        # version, so assert emptiness by length.
        assert len(engine.session.adapters["http://"].poolmanager.pools) == 0
        # Reusable after close: requests re-opens pools lazily.
        assert engine.session.get(url, timeout=5).status_code == 200
    finally:
        srv.shutdown()


# ---------------------------------------------------------------- F7
def test_slice_ticks_capped_while_paused_and_cleared_on_resume():
    """WS ticks arriving while paused must neither grow _slice_ticks
    without bound nor be aggregated into the first post-resume candle."""
    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    engine.paused = True
    for _ in range(1300):
        engine._handle_ws_quote(_quote("3500.00"))
    assert len(engine._slice_ticks) == 1200
    engine.paused = False
    assert engine._slice_ticks == []


# ------------------------------------------------------------- F8a/b
def test_rejected_entry_sets_cooldown_and_rejection_audit_capped():
    """A broker-rejected entry cools the strategy down for 20 s (no
    retry-every-cadence storm), and rejection_audit is capped at 500."""
    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    engine.comp_a.portfolio.is_circuit_breaker_tripped = True
    # Force the MC EV gate to pass so the ticket actually reaches the
    # broker (and its RiskGuard rejection) instead of stopping earlier.
    from src.data.timemachine import MonteCarloBracketOdds
    engine.mc_evaluator.evaluate_bracket = lambda *a, **k: MonteCarloBracketOdds(
        passed=True, target_prob=0.5, stop_prob=0.3, neither_prob=0.2,
        decided_win_rate=0.6, expected_r=0.5, r_multiple=1.0,
        breakeven_prob=0.5, verdict="Passed", green_prob=0.5,
    )
    ts = 1700000000.0
    ok = engine._try_enter_bracket(
        engine.comp_a, Decimal("3500.00"), Decimal("3400.00"),
        Decimal("3600.00"), ts, "TEST", side=OrderSide.BUY,
    )
    assert ok is False
    assert engine.strategy_cooldown["comp_agg"] == ts + 20.0
    assert len(engine.broker.rejection_audit) >= 1

    broker = BrokerSim()
    portfolio = engine.comp_a.portfolio
    broker.register_portfolio(portfolio)
    for _ in range(600):
        broker.submit_order(OrderTicket(
            portfolio_id="comp_agg", symbol="ETH/USD", side=OrderSide.BUY,
            order_type=OrderType.MARKET, qty=Decimal("1000000"),
            timestamp=ts,
        ))
    assert len(broker.rejection_audit) == 500


# ---------------------------------------------------------------- F5
def test_start_daemon_concurrent_calls_spawn_once(tmp_path):
    """Two threads calling start_daemon at once must spawn exactly one
    daemon; the second waits on the health probe instead."""
    log_path = tmp_path / "logs" / "omniroute_daemon.log"
    gs = GatewaySupervisor(daemon_log_path=log_path)
    up = threading.Event()
    fake_proc = MagicMock()
    fake_proc.pid = 12345
    results = []

    def fake_popen(*args, **kwargs):
        up.set()
        return fake_proc

    def fake_port_open(timeout=0.35):
        return up.is_set()

    def fake_probe(timeout=1.0):
        return (up.is_set(), {"status": "ok"})

    try:
        with patch.object(GatewaySupervisor, "_get_daemon_command", return_value=["fake-cmd"]), \
             patch("subprocess.Popen", side_effect=fake_popen) as mock_popen, \
             patch.object(gs, "is_port_open", side_effect=fake_port_open), \
             patch.object(gs, "probe_health", side_effect=fake_probe):
            threads = [
                threading.Thread(target=lambda: results.append(gs.start_daemon(max_wait_sec=10.0)), daemon=True)
                for _ in range(2)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=30)
        assert len(results) == 2
        assert all(ok is True for ok, _ in results)
        assert mock_popen.call_count == 1
    finally:
        gs.shutdown()


def test_gateway_supervisor_atexit_does_not_retain_instances(tmp_path):
    """Supervisors must drop out of the atexit registry when garbage
    collected (the old per-instance atexit.register retained them all)."""
    log_path = tmp_path / "logs" / "omniroute_daemon.log"
    gs = GatewaySupervisor(daemon_log_path=log_path)
    assert GatewaySupervisor._atexit_registered is True
    assert gs in GatewaySupervisor._live_supervisors
    weak = weakref.ref(gs)
    del gs
    gc.collect()
    assert weak() is None
