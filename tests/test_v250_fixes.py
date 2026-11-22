"""V2.5.0 regression tests covering Track A, B, C, and D bug fixes and optimizations."""
from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal
import io
import json
from pathlib import Path
import sqlite3
import time
from unittest.mock import MagicMock, patch
import urllib.error

import pytest

from src.arena.broker_sim import BrokerSim
from src.arena.evolution import GeneticEvolver
from src.arena.leaderboard import Leaderboard
from src.arena.order import ExecutionReason, OrderSide, OrderTicket, OrderType, PositionSide
from src.arena.portfolio import Portfolio
from src.competitors.base import CompetitorGenome
from src.data.eth_feed import ETHFeed
from src.data.live_engine import LiveArenaEngine
from src.data.persistence import ArenaStorage
from src.gui.dashboard import ArenaDashboard
from src.gui.view_model import ViewModelPublisher, build_engine_view_model
from src.intelligence.gateway_supervisor import GatewaySupervisor
from src.intelligence.ingestion import DeduplicationBuffer, StructuredEvent, _clean_html_text
from src.intelligence.macro_commander import MacroCommander
from src.intelligence.omniroute_client import OmniRouteClient, extract_json
from src.update_checker import check_for_updates, compare_versions
from src.version import APP_VERSION

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Track A: Portfolio, BrokerSim, GeneticEvolver
# ---------------------------------------------------------------------------

def test_portfolio_unrounded_notional_addition_and_leveraged_flag():
    p = Portfolio(
        "p_test",
        "Test",
        initial_cash=Decimal("10000.00"),
        maker_taker_fee_rate=Decimal("0"),
        leverage=Decimal("2.0"),
        leverage_enabled=True,
    )
    broker = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0"))
    broker.register_portfolio(p, max_position_ratio=Decimal("0.90"))
    broker.current_price = Decimal("2000.01")

    t1 = OrderTicket("p_test", "ETH/USD", OrderSide.BUY, OrderType.LIMIT, Decimal("0.3333"), price=Decimal("2000.01"))
    t2 = OrderTicket("p_test", "ETH/USD", OrderSide.BUY, OrderType.LIMIT, Decimal("0.3333"), price=Decimal("2000.04"))
    t3 = OrderTicket("p_test", "ETH/USD", OrderSide.BUY, OrderType.LIMIT, Decimal("0.3334"), price=Decimal("2000.07"))

    assert broker.submit_order(t1) is not None
    assert p.position_is_leveraged is True
    # Flip leverage_enabled mid-position; open position must remain marked leveraged until flat.
    p.leverage_enabled = False
    assert broker.submit_order(t2) is not None
    assert broker.submit_order(t3) is not None
    assert p.position_is_leveraged is True

    expected_avg = (
        Decimal("0.3333") * Decimal("2000.01")
        + Decimal("0.3333") * Decimal("2000.04")
        + Decimal("0.3334") * Decimal("2000.07")
    ) / Decimal("1.0000")
    assert abs(p.avg_entry_price - expected_avg) <= Decimal("0.000002")


def test_brokersim_closing_allowed_under_circuit_breaker():
    p = Portfolio("p_cb", "CB", initial_cash=Decimal("10000.00"), maker_taker_fee_rate=Decimal("0"))
    broker = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0"))
    broker.register_portfolio(p, max_position_ratio=Decimal("0.80"))
    broker.current_price = Decimal("2000.00")

    # Open 2 ETH LONG ($4000 notional)
    open_t = OrderTicket("p_cb", "ETH/USD", OrderSide.BUY, OrderType.LIMIT, Decimal("2.0"), price=Decimal("2000.00"))
    assert broker.submit_order(open_t) is not None

    # Force drawdown past circuit breaker (>15% drawdown)
    p.peak_equity = Decimal("10000.00")
    p.max_drawdown_pct = Decimal("20.00")
    p.is_circuit_breaker_tripped = True
    broker.current_price = Decimal("1100.00")
    p.update_market_price(Decimal("1100.00"))

    # New BUY (increasing risk) must be blocked by circuit breaker
    add_t = OrderTicket("p_cb", "ETH/USD", OrderSide.BUY, OrderType.LIMIT, Decimal("0.5"), price=Decimal("1100.00"))
    assert broker.submit_order(add_t) is None

    # Closing SELL must still be allowed so the trader can exit risk!
    close_t = OrderTicket(
        "p_cb", "ETH/USD", OrderSide.SELL, OrderType.MARKET, Decimal("2.0"),
        price=Decimal("1100.00"), reason=ExecutionReason.SIGNAL_EXIT,
    )
    fill = broker.submit_order(close_t)
    assert fill is not None
    assert p.position_side == PositionSide.FLAT


def test_brokersim_liquidation_preempts_stop_loss():
    p = Portfolio(
        "p_liq",
        "Liq",
        initial_cash=Decimal("10000.00"),
        maker_taker_fee_rate=Decimal("0"),
        leverage=Decimal("5.0"),
        leverage_enabled=True,
    )
    broker = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0"))
    broker.register_portfolio(p, max_position_ratio=Decimal("0.50"))
    broker.current_price = Decimal("2000.00")

    # Open 5x leveraged LONG: notional = $5000 (2.5 ETH), margin = $1000.
    # Liquidation occurs when loss reaches 90% of margin ($900 -> drop of $360/ETH -> $1640).
    open_t = OrderTicket(
        "p_liq", "ETH/USD", OrderSide.BUY, OrderType.LIMIT, Decimal("2.5"),
        price=Decimal("2000.00"), stop_loss=Decimal("1600.00"),
    )
    assert broker.submit_order(open_t) is not None
    assert "p_liq" in broker.active_stops

    # Bar crashes straight down to $1500 — hits liquidation ($1640) BEFORE SL ($1600).
    fills = broker.on_tick(
        price=Decimal("1550.00"),
        high=Decimal("1990.00"),
        low=Decimal("1500.00"),
        open_price=Decimal("1980.00"),
    )
    assert any(f.reason == ExecutionReason.LIQUIDATION for f in fills)
    assert p.position_side == PositionSide.FLAT


def test_brokersim_trigger_clamped_inside_bar():
    p = Portfolio("p_gap", "Gap", initial_cash=Decimal("10000.00"), maker_taker_fee_rate=Decimal("0"))
    broker = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0"))
    broker.register_portfolio(p, max_position_ratio=Decimal("0.80"))
    broker.current_price = Decimal("2000.00")

    open_t = OrderTicket(
        "p_gap", "ETH/USD", OrderSide.BUY, OrderType.LIMIT, Decimal("1.0"),
        price=Decimal("2000.00"), stop_loss=Decimal("1950.00"),
    )
    assert broker.submit_order(open_t) is not None

    # Gap-down bar completely below SL: [1850, 1900]
    fills = broker.on_tick(
        price=Decimal("1880.00"),
        high=Decimal("1900.00"),
        low=Decimal("1850.00"),
        open_price=Decimal("1890.00"),
    )
    sl_fills = [f for f in fills if f.reason == ExecutionReason.STOP_LOSS]
    assert len(sl_fills) == 1
    assert Decimal("1850.00") <= sl_fills[0].price <= Decimal("1900.00")


def test_brokersim_partial_close_preserves_brackets_and_full_close_purges_exit_pending():
    p = Portfolio("p_part", "Part", initial_cash=Decimal("10000.00"), maker_taker_fee_rate=Decimal("0"))
    broker = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0"))
    broker.register_portfolio(p, max_position_ratio=Decimal("0.80"))
    broker.current_price = Decimal("2000.00")

    open_t = OrderTicket(
        "p_part", "ETH/USD", OrderSide.BUY, OrderType.LIMIT, Decimal("2.0"),
        price=Decimal("2000.00"), stop_loss=Decimal("1900.00"), take_profit=Decimal("2200.00"),
    )
    assert broker.submit_order(open_t) is not None

    # Add a pending exit order and a pending entry order
    exit_pending = OrderTicket(
        "p_part", "ETH/USD", OrderSide.SELL, OrderType.STOP_MARKET, Decimal("1.0"),
        price=Decimal("1920.00"), reason=ExecutionReason.TRAILING_STOP,
    )
    entry_pending = OrderTicket(
        "p_part", "ETH/USD", OrderSide.BUY, OrderType.LIMIT, Decimal("0.5"),
        price=Decimal("1800.00"), reason=ExecutionReason.SIGNAL,
    )
    broker.pending_orders[exit_pending.order_id] = exit_pending
    broker.pending_orders[entry_pending.order_id] = entry_pending

    # Partial close 1.0 ETH at current market >= limit -> brackets must survive with remaining qty 1.0
    broker.current_price = Decimal("2060.00")
    part_close = OrderTicket(
        "p_part", "ETH/USD", OrderSide.SELL, OrderType.LIMIT, Decimal("1.0"),
        price=Decimal("2050.00"), reason=ExecutionReason.SIGNAL_EXIT,
    )
    assert broker.submit_order(part_close) is not None
    assert p.position_qty == Decimal("1.0000")
    assert "p_part" in broker.active_stops
    assert "p_part" in broker.active_targets
    assert broker.active_stops["p_part"].qty == Decimal("1.0000")

    # Full close remaining 1.0 ETH -> brackets cleared, exit pending purged, entry pending preserved
    full_close = OrderTicket(
        "p_part", "ETH/USD", OrderSide.SELL, OrderType.LIMIT, Decimal("1.0"),
        price=Decimal("2060.00"), reason=ExecutionReason.SIGNAL_EXIT,
    )
    assert broker.submit_order(full_close) is not None
    assert p.position_side == PositionSide.FLAT
    assert "p_part" not in broker.active_stops
    assert "p_part" not in broker.active_targets
    assert exit_pending.order_id not in broker.pending_orders
    assert entry_pending.order_id in broker.pending_orders


def test_genetic_evolver_never_emits_1x_leveraged_genome():
    p1 = CompetitorGenome(leverage_enabled=True, leverage=Decimal("1.1"))
    p2 = CompetitorGenome(leverage_enabled=False, leverage=Decimal("1.0"))
    for seed_offset in range(40):
        child = GeneticEvolver.crossover_and_mutate(p1, p2, next_gen=2, seed_offset=seed_offset)
        if child.leverage_enabled:
            assert child.leverage > Decimal("1.0")
        else:
            assert child.leverage == Decimal("1.0")


# ---------------------------------------------------------------------------
# Track B: Persistence, SessionCodec, LiveArenaEngine, ETHFeed
# ---------------------------------------------------------------------------

def test_persistence_sanitizes_nan_and_inf_strict_json(tmp_path):
    db_file = tmp_path / "strict_json.db"
    storage = ArenaStorage(db_path=str(db_file))
    try:
        payload = {
            "symbol": "ETH/USD",
            "generation": 1,
            "bad_nan": float("nan"),
            "bad_inf": float("inf"),
            "nested": [1.5, float("-inf"), {"k": float("nan")}],
        }
        storage.save_session_snapshot(payload)

        # Verify raw DB payload has zero NaN/Infinity tokens (strict RFC 8259)
        conn = sqlite3.connect(str(db_file))
        row = conn.execute("SELECT data FROM session_snapshot WHERE key='latest_session'").fetchone()
        conn.close()
        assert row is not None
        raw = row[0]
        assert "NaN" not in raw
        assert "Infinity" not in raw

        loaded = storage.load_session_snapshot()
        assert loaded is not None
        assert loaded["bad_nan"] is None
        assert loaded["bad_inf"] is None
        assert loaded["nested"] == [1.5, None, {"k": None}]
    finally:
        storage.close()


def test_session_codec_rejects_symbol_mismatch_and_roundtrips_pending_and_orb(tmp_path):
    db_file = tmp_path / "codec_test.db"
    storage = ArenaStorage(db_path=str(db_file))
    eng = LiveArenaEngine(symbol="ETH/USD", storage=storage)
    try:
        # 1. Symbol mismatch snapshot must be rejected
        assert eng.save_session_state() is True
        saved = storage.load_session_snapshot()
        assert saved is not None
        saved["symbol"] = "BTC/USD"
        saved["generation"] = 99
        storage.save_session_snapshot(saved)
        assert eng.restore_session_state() is False
        assert max(c.genome.generation for c in eng.competitors) == 1

        # 2. Pending orders + ORB state round-trip
        pending = OrderTicket(
            portfolio_id="comp_orb",
            symbol="ETH/USD",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            qty=Decimal("0.75"),
            price=Decimal("2450.00"),
            reason=ExecutionReason.SIGNAL,
        )
        eng.broker.pending_orders[pending.order_id] = pending
        today = date.today()
        eng.live_orb_high = Decimal("2610.50")
        eng.live_orb_low = Decimal("2580.25")
        eng._orb_range_frozen = True
        eng._orb_session_day = today

        assert eng.save_session_state() is True

        eng2 = LiveArenaEngine(symbol="ETH/USD", storage=storage)
        try:
            assert eng2.restore_session_state() is True
            assert len(eng2.broker.pending_orders) == 1
            restored_ticket = next(iter(eng2.broker.pending_orders.values()))
            assert restored_ticket.portfolio_id == "comp_orb"
            assert restored_ticket.price == Decimal("2450.00")

            assert eng2.live_orb_high == Decimal("2610.50")
            assert eng2.live_orb_low == Decimal("2580.25")
            assert eng2._orb_range_frozen is True
            assert eng2._orb_session_day == today
        finally:
            eng2.stop()
    finally:
        eng.stop()
        storage.close()


@pytest.mark.parametrize(
    "sequence,expected_pos_shift",
    [
        # (action, ts) where P=toggle_pause, D=toggle_auto_evolve
        ([("P", 1010.0), ("D", 1020.0), ("P", 1030.0), ("D", 1040.0)], 20.0),
        ([("D", 1010.0), ("P", 1020.0), ("P", 1030.0), ("D", 1040.0)], 10.0),
        ([("P", 1010.0), ("D", 1020.0), ("D", 1030.0), ("P", 1040.0)], 30.0),
        ([("D", 1010.0), ("P", 1020.0), ("D", 1030.0), ("P", 1040.0)], 20.0),
    ],
)
def test_live_engine_toggle_pause_and_auto_evolve_shift_math(tmp_path, sequence, expected_pos_shift):
    storage = ArenaStorage(db_path=str(tmp_path / "toggle.db"))
    eng = LiveArenaEngine(symbol="ETH/USD", storage=storage)
    try:
        base_ts = 1000.0
        eng.last_evolve_ts = base_ts
        eng.position_entry_ts["comp_agg"] = base_ts
        eng._paused = False
        eng._pause_start_ts = None
        eng.auto_evolve_enabled = True
        eng._auto_evolve_disabled_ts = None

        for action, ts in sequence:
            with patch("src.data.live_engine.time.time", return_value=ts):
                if action == "P":
                    eng.toggle_pause()
                else:
                    eng.toggle_auto_evolve()

        # Total frozen interval across all 4 overlap orderings is [1010, 1040] = 30s
        assert eng.paused is False
        assert eng.auto_evolve_enabled is True
        assert eng.last_evolve_ts == pytest.approx(1030.0, abs=1e-6)
        assert eng.position_entry_ts["comp_agg"] == pytest.approx(base_ts + expected_pos_shift, abs=1e-6)
    finally:
        eng.stop()
        storage.close()


def test_eth_feed_ohlc_invariant_normalization():
    import pandas as pd

    n = 25
    idx = pd.date_range("2026-11-20 00:00:00", periods=n, freq="15min", tz="UTC")
    opens = [2500.0 + i for i in range(n)]
    highs = [2510.0 + i for i in range(n)]
    lows = [2490.0 + i for i in range(n)]
    closes = [2505.0 + i for i in range(n)]
    # Row 22 deliberately has inverted High < Low and Close > High
    opens[22] = 2520.0
    highs[22] = 2490.0
    lows[22] = 2550.0
    closes[22] = 2560.0
    df = pd.DataFrame(
        {"Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": [100.0] * n},
        index=idx,
    )
    with patch.object(ETHFeed, "_fetch_dataframe", return_value=df):
        bars = ETHFeed.fetch_historical_bars("ETH-USD", period="1d", interval="15m")
    assert len(bars) >= 5
    for b in bars:
        assert b.low <= min(b.open, b.close)
        assert max(b.open, b.close) <= b.high


# ---------------------------------------------------------------------------
# Track C: GatewaySupervisor, OmniRouteClient, MacroCommander, Harvester, UpdateChecker
# ---------------------------------------------------------------------------

def test_gateway_env_sets_server_host_and_strips_provider_keys_when_env_exists(tmp_path, monkeypatch):
    omni_dir = tmp_path / "omni"
    omni_dir.mkdir()
    (omni_dir / ".env").write_text("INITIAL_PASSWORD=from_file\n", encoding="utf-8")

    monkeypatch.setenv("INITIAL_PASSWORD", "from_os_env")
    monkeypatch.setenv("GEMINI_API_KEY", "AIza_stale_os_env_key")
    monkeypatch.setenv("STORAGE_ENCRYPTION_KEY", "stale_enc_key")

    sup = GatewaySupervisor(
        host="127.0.0.1",
        port=20128,
        omni_data_dir=omni_dir,
        daemon_log_path=tmp_path / "daemon.log",
    )
    captured: dict = {}

    class _FakeProc:
        pid = 42424
        def poll(self):
            return None

    def _fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["env"] = kwargs["env"]
        return _FakeProc()

    port_calls = iter([False, True])
    with (
        patch.object(GatewaySupervisor, "_get_daemon_command", classmethod(lambda cls, port: ["node", "omni.mjs"])),
        patch.object(sup, "is_port_open", side_effect=lambda timeout=0.2: next(port_calls, True)),
        patch.object(sup, "probe_health", return_value=(True, {"ok": True})),
        patch("src.intelligence.gateway_supervisor.subprocess.Popen", side_effect=_fake_popen),
        patch("src.intelligence.gateway_supervisor.time.sleep", return_value=None),
    ):
        ok, _ = sup.start_daemon(max_wait_sec=2.0)

    # Clean up fake handle without invoking taskkill on fake PID
    sup.is_self_spawned = False
    sup.child_process = None
    if sup._daemon_log_file is not None:
        sup._daemon_log_file.close()
        sup._daemon_log_file = None

    assert ok is True
    env = captured["env"]
    assert env["OMNIROUTE_SERVER_HOST"] == "127.0.0.1"
    assert env["OMNIROUTE_CLI_SKIP_REPO_ENV"] == "1"
    assert env["OMNIROUTE_NO_UPDATE_NOTIFIER"] == "1"
    assert "INITIAL_PASSWORD" not in env
    assert "GEMINI_API_KEY" not in env
    assert "STORAGE_ENCRYPTION_KEY" not in env


def test_gateway_cli_command_never_falls_back_to_npx():
    with (
        patch.object(GatewaySupervisor, "_resolve_node_bin", return_value=None),
        patch("src.intelligence.gateway_supervisor.shutil.which", return_value=None),
    ):
        assert GatewaySupervisor._get_cli_base_command() is None
        assert GatewaySupervisor._get_daemon_command(20128) is None


def test_gateway_test_single_key_non_ascii_and_gemini_400():
    sup = GatewaySupervisor()
    # Non-ASCII key rejected without issuing HTTP request
    res_bad_chars = sup.test_single_key("gemini", "AIza中文金鑰")
    assert res_bad_chars["ok"] is False

    # Gemini HTTP 400 with API_KEY_INVALID body reports invalid/unauthorized key
    err_body = io.BytesIO(
        json.dumps({"error": {"status": "INVALID_ARGUMENT", "details": [{"reason": "API_KEY_INVALID"}]}}).encode("utf-8")
    )
    http_err = urllib.error.HTTPError(
        url="https://generativelanguage.googleapis.com/v1beta/models",
        code=400,
        msg="Bad Request",
        hdrs={},
        fp=err_body,
    )
    with patch("urllib.request.urlopen", side_effect=http_err):
        res_400 = sup.test_single_key("gemini", "AIzaBadKey12345")
    assert res_400["ok"] is False
    assert "400" in res_400["message"]
    assert "invalid key" in res_400["message"].lower()


def test_omniroute_client_shutdown_short_circuit_and_bounded_extract_json():
    client = OmniRouteClient(base_url="http://127.0.0.1:20128/v1")
    assert client.is_shutting_down() is False
    client.mark_shutting_down()
    assert client.is_shutting_down() is True

    # chat_json returns None immediately when shutting down (zero network I/O)
    result = asyncio.run(client.chat_json(model="auto", system_prompt="sys", user_prompt="hi"))
    assert result is None

    # Pathological input with thousands of `{` returns quickly (bounded to 64 scan attempts)
    t0 = time.perf_counter()
    assert extract_json("{" * 5000 + " not json") is None
    assert (time.perf_counter() - t0) < 0.5


def test_macro_commander_veto_expires_stale_fallback_and_raw_title_dedup():
    client = OmniRouteClient(base_url="http://127.0.0.1:20128/v1")
    client.is_gateway_online = False
    cmd = MacroCommander(client=client)
    # Seed a stale fallback state (>1800s old)
    cmd.current_state.regime = "BEARISH_PANIC"
    cmd.current_state.directional_bias = "SHORT_ONLY"
    cmd.current_state.risk_multiplier = 0.75
    cmd.current_state.fallback = True
    cmd.current_state.fallback_since_ts = time.time() - 3600.0

    allowed, reason = cmd.check_trade_veto(OrderSide.BUY, "Aggressive")
    assert allowed is True
    assert reason == "PASSED"
    assert cmd.current_state.regime == "NORMAL"
    assert cmd.current_state.directional_bias == "BIDIRECTIONAL"

    # raw_title deduplication prevents duplicate curated events even when translated headlines vary
    ev1 = StructuredEvent(
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        entities_tickers=["ETH"],
        raw_title="ETH ETF inflows hit record",
        source="Reuters",
        domain="crypto",
        urgency_score=7,
        sentiment_score=0.6,
        headline_zh="以太幣 ETF 資金流入創新高",
        summary="以太幣現貨 ETF 資金流入創紀錄。",
    )
    ev2 = StructuredEvent(
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        entities_tickers=["ETH"],
        raw_title="ETH ETF inflows hit record",
        source="Reuters",
        domain="crypto",
        urgency_score=7,
        sentiment_score=0.6,
        headline_zh="以太坊 ETF 單日流入破紀錄",
        summary="以太坊 ETF 單日流入破紀錄。",
    )
    asyncio.run(cmd.synthesize_regime([ev1]))
    asyncio.run(cmd.synthesize_regime([ev2]))
    assert len(cmd.curated_events) == 1


def test_ingestion_clean_html_strips_script_style_and_dedup_forget():
    dirty = "<style>.a{color:red}</style><script>alert(1)</script><p>ETH &amp;amp; BTC rally</p>"
    cleaned = _clean_html_text(dirty)
    assert "alert" not in cleaned
    assert "color:red" not in cleaned
    assert "ETH & BTC rally" == cleaned

    buf = DeduplicationBuffer(capacity=10)
    assert buf.is_new("Headline A", "https://example.com/a") is True
    assert buf.is_new("Headline A", "https://example.com/a") is False
    buf.forget("Headline A", "https://example.com/a")
    assert buf.is_new("Headline A", "https://example.com/a") is True


def test_update_checker_semver_prerelease_and_non_string_version():
    assert APP_VERSION == "V2.5.2"
    assert compare_versions("V2.5.0-rc.1", "V2.5.0") == -1
    assert compare_versions("V2.5.0", "V2.5.0-rc.1") == 1
    assert compare_versions("V2.5.0-alpha.1", "V2.5.0-beta.1") == -1
    assert compare_versions("2026.11.20", "V2.5.0") == -1

    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.raise_for_status.return_value = None
    fake_resp.json.return_value = {"version": 250}
    with patch("src.update_checker.requests.get", return_value=fake_resp):
        res = check_for_updates(manifest_url="https://example.invalid/manifest.json")
    assert res["status"] == "check_failed"


# ---------------------------------------------------------------------------
# Track D: ViewModelPublisher, ArenaDashboard, app.js, TradeBot0.iss
# ---------------------------------------------------------------------------

def test_view_model_delta_omits_unchanged_history_and_intel_events_equivalently():
    snap1 = {
        "generation": 1,
        "spot_price": 2500.0,
        "candles": [{"t": 1000, "o": 2490, "h": 2510, "l": 2480, "c": 2500, "v": 10}],
        "fills": [{"seq": 1, "portfolio_id": "a", "price": 2500.0, "is_live": True, "time": "12:00:00"}],
        "price_history": [2490.0, 2495.0, 2500.0],
        "ema_fast_history": [2491.0, 2494.0, 2498.0],
        "ema_slow_history": [2488.0, 2490.0, 2492.0],
        "intel_hub": {
            "regime": "NEUTRAL",
            "events": [
                {
                    "id": "evt_1",
                    "headline": "Test",
                    "article_state": "none",
                    "strategy_actions": [{"strat_id": "comp_agg", "action": "BUY", "time": "12:00:00"}],
                }
            ],
        },
    }
    snap2 = {
        **snap1,
        "spot_price": 2501.0,  # Only spot changed; heavy arrays & intel events unchanged
    }

    pub_a = ViewModelPublisher()
    pub_b = ViewModelPublisher()

    first_a = pub_a.compute_delta_from_snapshot(snap1)
    first_b = pub_b.compute_delta_payload(snap1)
    assert first_a == first_b
    assert first_a["is_delta"] is False

    delta_a = pub_a.compute_delta_from_snapshot(snap2)
    delta_b = pub_b.compute_delta_payload(snap2)
    assert delta_a == delta_b
    assert delta_a["is_delta"] is True
    assert delta_a["history_unchanged"] is True
    assert delta_a["intel_events_unchanged"] is True
    assert "price_history" not in delta_a
    assert "ema_fast_history" not in delta_a
    assert "ema_slow_history" not in delta_a
    assert "events" not in delta_a["intel_hub"]
    assert delta_a["intel_hub"]["regime"] == "NEUTRAL"

    # Mutate strategy_actions in-place (same length!) & price_history -> both must reappear
    snap3 = {
        **snap2,
        "price_history": [2490.0, 2495.0, 2501.0],
        "intel_hub": {
            "regime": "BULLISH",
            "events": [
                {
                    "id": "evt_1",
                    "headline": "Test",
                    "article_state": "none",
                    "strategy_actions": [{"strat_id": "comp_agg", "action": "SELL", "time": "12:01:00"}],
                }
            ],
        },
    }
    delta3_a = pub_a.compute_delta_from_snapshot(snap3)
    delta3_b = pub_b.compute_delta_payload(snap3)
    assert delta3_a == delta3_b
    assert delta3_a["history_unchanged"] is False
    assert delta3_a["intel_events_unchanged"] is False
    assert "price_history" in delta3_a
    assert len(delta3_a["intel_hub"]["events"]) == 1


def test_view_model_preserves_gen1_tv_champion_and_sanitizes_nonfinite(tmp_path):
    storage = ArenaStorage(db_path=str(tmp_path / "vm.db"))
    eng = LiveArenaEngine(symbol="ETH/USD", storage=storage)
    try:
        rankings = Leaderboard.get_rankings(eng.broker.portfolios)
        # Stored Gen #1 champion with non-finite fields to verify preservation & sanitization on Gen #2
        eng.tv_champion = {
            "strategy_id": "comp_trail",
            "name": "Trail",
            "generation": 1,
            "roi_pct": float("nan"),
            "fitness": float("inf"),
            "win_rate_pct": float("-inf"),
            "status": "Gen #1 Champion",
        }
        # On Gen #1 itself, hourly leader is dispatched
        vm_gen1 = build_engine_view_model(eng, rankings, gen=1)
        assert vm_gen1["tv_hub"]["champion"]["generation"] == 1
        assert vm_gen1["tv_hub"]["champion"]["status"] == "Hourly Leader (Active Dispatch)"

        # On Gen #2, stored Gen #1 champion MUST be preserved (not overwritten) and sanitized
        vm_gen2 = build_engine_view_model(eng, rankings, gen=2)
        champ2 = vm_gen2["tv_hub"]["champion"]
        assert champ2["strategy_id"] == "comp_trail"
        assert champ2["generation"] == 1
        assert champ2["status"] == "Gen #1 Champion"
        assert champ2["roi_pct"] == 0.0
        assert champ2["fitness"] == 0.0
        assert champ2["win_rate_pct"] == 0.0
    finally:
        eng.stop()
        storage.close()


def test_dashboard_stop_is_idempotent_and_blocks_reset_engine():
    fake_engine = MagicMock()
    fake_engine.storage = MagicMock()
    fake_sup = MagicMock()

    with (
        patch("src.gui.dashboard.LiveArenaEngine", return_value=fake_engine) as mock_cls,
        patch("src.gui.dashboard.GatewaySupervisor", return_value=fake_sup),
    ):
        dash = ArenaDashboard()
        mock_cls.reset_mock()

        dash.stop()
        dash.stop()
        assert fake_engine.stop.call_count == 1
        assert fake_sup.shutdown.call_count == 1
        assert dash._stopped is True

        # Calling reset_engine after stop must be a safe no-op
        dash.reset_engine()
        mock_cls.assert_not_called()


def test_app_js_and_installer_v250_contracts():
    js = (ROOT / "src" / "gui" / "assets" / "app.js").read_text(encoding="utf-8")
    iss = (ROOT / "TradeBot0.iss").read_text(encoding="utf-8")

    # Strategy tag disambiguation & UI contracts
    assert "'Trailing': 'TRAIL'" in js
    assert "'Session': 'MEAN'" in js
    assert "omniStatus !== 'ONLINE'" in js
    assert "pendingControlActions" in js
    assert "2650.0" not in js

    # Escape key modal priority: shutdownModal before wizardCloseConfirmModal
    idx_shutdown = js.find("shutdownModal.classList.contains('modal-visible')")
    idx_wiz_close = js.find("wizardCloseModal.classList.contains('modal-visible')")
    assert idx_shutdown != -1 and idx_wiz_close != -1
    assert idx_shutdown < idx_wiz_close

    # Installer version & silent-safe contracts (sync with src/version.py)
    assert f'#define MyAppVersion "{APP_VERSION}"' in iss
    assert f"VersionInfoVersion={APP_VERSION.lstrip('Vv')}" in iss
    assert "SuppressibleMsgBox" in iss
    assert r"TradeBot0\runtime\node\node.exe" in iss
