"""V2.6.0 debug & optimization regression tests covering Workstreams 1, 2, and 3."""
from __future__ import annotations

import asyncio
from decimal import Decimal
import logging
from pathlib import Path
import sys
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from src.arena.leaderboard import CompetitorStats
from src.arena.order import OrderSide, OrderTicket, OrderType, ExecutionReason, PositionSide, FillEvent
from src.data.live_engine import LiveArenaEngine, _safe_fmt_hms
from src.data.timemachine import TimeMachineArena
from src.gui.dashboard import ArenaDashboard, _ArenaBridgeApi
from src.gui.view_model import ViewModelPublisher
from src.intelligence.gemini_client import GeminiClient
from src.intelligence.ingestion import StructuredEvent, _parse_feed_ts
from src.intelligence.macro_commander import MacroCommander, _parse_event_epoch
from src.logging_setup import _SafeRotatingFileHandler
from src.version import APP_VERSION

ROOT = Path(__file__).resolve().parent.parent


def test_indicator_update_candle_enforces_ohlc_bounds():
    engine = LiveArenaEngine(initial_cash=Decimal("10000.00"))
    try:
        engine.candles.clear()
        # Inverted explicit high/low are normalized so h >= l without breaking explicit bounds
        engine._update_candle(
            ts=1800.0,
            close=Decimal("2005.00"),
            high=Decimal("1990.00"),
            low=Decimal("2010.00"),
            open_=Decimal("2000.00"),
        )
        assert len(engine.candles) == 1
        c0 = engine.candles[-1]
        assert c0["h"] == 2010.0
        assert c0["l"] == 1990.0

        # When high/low are omitted (None), bounds expand safely around open & close
        engine._update_candle(
            ts=1860.0,
            close=Decimal("2050.00"),
            high=None,
            low=None,
            open_=Decimal("2000.00"),
        )
        c1 = engine.candles[-1]
        assert c1["h"] >= max(c1["o"], c1["c"]) == 2050.0
        assert c1["l"] <= min(c1["o"], c1["c"]) == 2000.0

        engine._update_candle(ts=1880.0, close=Decimal("1950.00"), high=None, low=None)
        c2 = engine.candles[-1]
        assert c2["l"] == 1950.0
        assert c2["h"] == 2050.0
    finally:
        engine.stop()


def test_try_enter_bracket_passes_side_for_short_sizing():
    captured: dict = {}
    engine = LiveArenaEngine(initial_cash=Decimal("10000.00"))
    try:
        comp = engine.competitors[0]
        comp.compute_r_multiple_qty = lambda price, sl, broker, **kwargs: (
            captured.update(kwargs) or Decimal("0")
        )
        engine._chop_gate_blocks = lambda: False
        engine._htf_trend_allows = lambda side: True
        engine.macro_commander.check_trade_veto = lambda *a, **k: (True, "")
        engine.mc_evaluator.evaluate_bracket = lambda *a, **k: SimpleNamespace(
            passed=True,
            neither_prob=0.1,
            green_prob=0.6,
            decided_win_rate=0.6,
            expected_r=0.5,
            verdict="OK",
            to_dict=lambda: {"passed": True},
        )
        ok = engine._try_enter_bracket(
            comp,
            price=Decimal("2000.00"),
            sl=Decimal("2040.00"),
            tp=Decimal("1920.00"),
            ts=1000.0,
            event_label="TEST",
            side=OrderSide.SELL,
        )
        assert ok is False
        assert captured.get("side") == OrderSide.SELL
    finally:
        engine.stop()


def test_safe_rotating_handler_rollover_cooldown(tmp_path):
    log_file = tmp_path / "app.log"
    handler = _SafeRotatingFileHandler(str(log_file), maxBytes=10, backupCount=2, encoding="utf-8")
    try:
        rec = logging.LogRecord("test", logging.INFO, __file__, 1, "x" * 64, (), None)
        with patch("logging.handlers.RotatingFileHandler.doRollover", side_effect=PermissionError("locked")):
            handler.doRollover()
        assert handler._rollover_cooldown_until > time.monotonic()
        assert handler.shouldRollover(rec) == 0
    finally:
        handler.close()


def test_timemachine_frozen_report_uses_appdata_memory_dir(tmp_path, monkeypatch):
    monkeypatch.delenv("ARENA_MEMORY_DIR", raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    tm = TimeMachineArena.__new__(TimeMachineArena)
    tm.symbol = "ETH/USD"
    tm.initial_cash = Decimal("100000.00")
    tm.competitors = []
    stats = CompetitorStats(
        rank=1,
        portfolio_id="comp_cons",
        name="Conservative Scalper",
        equity=Decimal("101234.56"),
        roi_pct=Decimal("1.23"),
        max_drawdown_pct=Decimal("0.90"),
        sharpe_ratio=Decimal("1.50"),
        sortino_ratio=Decimal("1.80"),
        profit_factor=Decimal("1.60"),
        win_rate_pct=Decimal("60.0"),
        total_trades=10,
        closed_trades=10,
        current_qty=Decimal("0"),
        cash=Decimal("101234.56"),
        fitness_score=Decimal("8.00"),
        status="ACTIVE",
    )
    tm._generate_post_mortem_report([stats], bar_count=120, generation=2)
    report_path = tmp_path / "TradeBot0" / "memory" / "arena_report.md"
    assert report_path.is_file()
    assert "Conservative Scalper" in report_path.read_text(encoding="utf-8")


def test_safe_fmt_hms_handles_invalid_and_valid_timestamps():
    assert _safe_fmt_hms(float("nan")) == ""
    assert _safe_fmt_hms(float("inf")) == ""
    assert _safe_fmt_hms(-5.0) == ""
    assert _safe_fmt_hms("not-a-number") == ""
    formatted = _safe_fmt_hms(1700000000.0)
    assert len(formatted) == 8 and formatted.count(":") == 2


def test_session_codec_order_id_roundtrip_and_atomic_rollback():
    engine = LiveArenaEngine(initial_cash=Decimal("10000.00"))
    try:
        ticket = OrderTicket(
            portfolio_id="comp_cons",
            symbol="ETH/USD",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            qty=Decimal("1.25"),
            price=Decimal("2000.00"),
            stop_loss=Decimal("1950.00"),
            take_profit=Decimal("2100.00"),
            reason=ExecutionReason.SIGNAL,
            timestamp=1700000000.0,
            order_id="custom-oid-v260",
        )
        raw_t = engine._serialize_ticket(ticket)
        assert raw_t["order_id"] == "custom-oid-v260"
        restored_t = engine._deserialize_ticket(raw_t)
        assert restored_t is not None and restored_t.order_id == "custom-oid-v260"

        # Non-finite / invalid ticket qty or negative timestamp is dropped cleanly
        bad_qty = dict(raw_t, qty="NaN")
        assert engine._deserialize_ticket(bad_qty) is None

        # Atomic rollback: corrupt post-portfolio scalar ("cadence_sec": "nan") must not mutate portfolio cash
        comp = engine.competitors[0]
        orig_cash = comp.portfolio.cash
        assert engine.save_session_state() is True
        snapshot = engine.storage.load_session_snapshot()
        assert isinstance(snapshot, dict)
        comp_entry = next(c for c in snapshot["competitors"] if c.get("portfolio_id") == comp.portfolio_id)
        comp_entry["cash"] = "1234.56"
        snapshot["cadence_sec"] = "nan"
        ok = engine.restore_session_state(snapshot)
        assert ok is False
        assert comp.portfolio.cash == orig_cash
    finally:
        engine.stop()


def test_view_model_delta_shallow_clones_and_cache():
    pub = ViewModelPublisher()
    snap1 = {
        "generation": 1,
        "quote": {"price": 2000.0},
        "candles": [{"t": 60.0, "o": 2000.0, "h": 2005.0, "l": 1995.0, "c": 2002.0}],
        "fills": [{"seq": 1, "price": 2000.0}],
        "price_history": [2000.0],
        "ema_fast_history": [2000.0],
        "ema_slow_history": [2000.0],
        "intel_hub": {"events": [{"id": "e1"}], "macro_state": {"regime": "NORMAL"}},
    }
    first = pub.compute_delta_from_snapshot(snap1, force_full=True)
    first["candles"][0]["c"] = 9999.0
    assert snap1["candles"][0]["c"] == 2002.0

    second = pub.compute_delta_from_snapshot(snap1, force_full=False)
    assert "candles" not in second
    assert "fills" not in second
    assert "price_history" not in second


def test_gemini_client_quota_fastpath_sse_error_and_timeout():
    client = GeminiClient(api_key="AIzaTestKey")
    assert client.has_quota_failures() is False
    client.note_failure({"kind": "quota", "provider": "gemini", "status": 429, "detail": "quota exceeded"})
    assert client.has_quota_failures() is True

    # SSE 200 frame containing in-band error must count as failure and return None
    sse_lines = [
        b'data: {"error": {"message": "insufficient_quota", "code": 429}}\n',
        b"data: [DONE]\n",
    ]

    class _FakeContent:
        def __aiter__(self):
            return self

        async def __anext__(self):
            if not sse_lines:
                raise StopAsyncIteration
            return sse_lines.pop(0)

    class _FakeResp:
        status = 200
        headers = {"Content-Type": "text/event-stream"}
        content = _FakeContent()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    class _FakeSession:
        closed = False

        def post(self, *args, **kwargs):
            return _FakeResp()

        async def close(self):
            pass

    async def _run_sse():
        client._session = _FakeSession()
        client._owns_session = False
        return await client.chat_json("gemini-3.1-flash-lite", "system", "user", timeout_sec=30.0, stream_progress=True)

    res = asyncio.run(_run_sse())
    assert res is None
    assert client.failed_requests >= 1

    # Timeout >= 60s returns None with 0 retries and preserves is_gateway_online=True
    client.is_gateway_online = True
    prev_fails = client.failed_requests

    class _TimeoutResp:
        async def __aenter__(self):
            raise asyncio.TimeoutError("slow gateway")

        async def __aexit__(self, *args):
            return False

    class _TimeoutSession:
        closed = False

        def post(self, *args, **kwargs):
            return _TimeoutResp()

        async def close(self):
            pass

    async def _run_timeout():
        client._session = _TimeoutSession()
        client._owns_session = False
        return await client.chat_json("gemini-3.1-flash-lite", "system", "user", timeout_sec=60.0)

    res_to = asyncio.run(_run_timeout())
    assert res_to is None
    assert client.failed_requests == prev_fails + 1
    assert client.is_gateway_online is True


def test_iso_z_parsing_and_macro_quiet_cycle_skip():
    ts_low = _parse_feed_ts("2026-11-23T10:00:00z")
    ts_up = _parse_feed_ts("2026-11-23T10:00:00Z")
    assert ts_low is not None and ts_low == ts_up
    assert _parse_event_epoch("2026-11-23T10:00:00z", ts_up + 100.0) == ts_up

    mock_client = MagicMock()
    mock_client.is_shutting_down.return_value = False
    mock_client.check_health = AsyncMock(return_value=True)
    cmd = MacroCommander(client=mock_client)
    evt = StructuredEvent(
        timestamp="2026-11-23T10:00:00Z",
        source="UnitTest",
        domain="crypto",
        entities_tickers=["ETH"],
        urgency_score=7,
        sentiment_score=0.4,
        summary="ETH upgrade live",
        raw_title="ETH upgrade live",
    )
    cmd.harvester.fetch_live_feeds = MagicMock(return_value=[])
    cmd.forum_collector.collect_async = AsyncMock(return_value=[])
    cmd.harvester.get_latest_events = MagicMock(return_value=[evt])
    cmd._last_synthesized_keys = ("ETH upgrade live", "Older event")
    cmd.current_state.fallback = False
    cmd.curated_events = [{"raw_title": "ETH upgrade live", "headline": "ETH upgrade live"}]
    state = cmd.run_digest_sync()
    assert state is cmd.current_state
    mock_client.chat_json.assert_not_called()

    # synthesize_regime uses newest-first slice recent_events[:15]
    seen_prompts = []

    async def _fake_chat_json(*args, **kwargs):
        user_p = args[2] if len(args) > 2 else kwargs.get("user_prompt", "")
        seen_prompts.append(user_p)
        return {
            "regime": "NORMAL",
            "directional_bias": "BIDIRECTIONAL",
            "risk_multiplier": 1.0,
            "confidence": 0.85,
            "active_headline": "Balanced",
            "reasoning_summary": "Steady flow",
        }

    mock_client.chat_json = _fake_chat_json
    events_20 = [
        StructuredEvent(
            timestamp="2026-11-23T10:00:00Z",
            source="UnitTest",
            domain="crypto",
            entities_tickers=["ETH"],
            urgency_score=6,
            sentiment_score=0.1,
            summary=f"Summary #{i}",
            raw_title=f"Event #{i}",
        )
        for i in range(20)
    ]
    asyncio.run(cmd.synthesize_regime(events_20))
    assert seen_prompts
    assert "Summary #0" in seen_prompts[0]
    assert "Summary #19" not in seen_prompts[0]


def test_dashboard_deferred_shutdown_and_reset_seq_carryover():
    dash = MagicMock()
    dash.allow_exit = False
    dash.window = object()
    dash.engine = MagicMock()
    api = _ArenaBridgeApi(dash)

    with (
        patch("src.gui.dashboard._get_native_hwnd", return_value=12345),
        patch("threading.Thread") as mock_thread,
    ):
        resp = api.shutdown(save_progress=False)
    assert resp["status"] == "shutting_down"
    mock_thread.return_value.start.assert_called_once()
    dash.close_window.assert_not_called()

    real_dash = ArenaDashboard(initial_cash=Decimal("10000.00"))
    try:
        real_dash.engine.fill_records = [
            FillEvent(
                order_id="oid-17",
                portfolio_id="comp_cons",
                symbol="ETH/USD",
                side=OrderSide.BUY,
                qty=Decimal("1.0"),
                price=Decimal("2000.00"),
                fee=Decimal("0.50"),
                timestamp=1700000000.0,
                realized_pnl=Decimal("0.00"),
                reason=ExecutionReason.SIGNAL,
                fill_seq=17,
                position_side=PositionSide.LONG,
            )
        ]
        real_dash.reset_engine()
        assert real_dash.engine.broker._seq_counter >= 17
    finally:
        real_dash.stop()


def test_v260_frontend_and_installer_contracts():
    assert APP_VERSION == "V3.2.1"
    iss = (ROOT / "TradeBot0.iss").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    css = (ROOT / "src" / "gui" / "assets" / "app.css").read_text(encoding="utf-8")
    js = (ROOT / "src" / "gui" / "assets" / "app.js").read_text(encoding="utf-8")

    assert '#define MyAppVersion "V3.2.1"' in iss
    assert "VersionInfoVersion=3.2.1" in iss
    assert iss.count('AppUserModelID: "TradeBot0.QuantArena"') == 2
    assert "TradeBot0Setup-V3.2.1.exe" in readme
    assert "nf-is-rolling" not in js
    assert "@keyframes nfRollCurrUp" in css
    assert ".border-beam-ring::before" in css
    assert "body.arena-ready .app-shell:not(.arena-entering)" in css
    assert "view-transition-leaving-base" in js
    assert "density: 56" in js
    assert "webglcontextlost" in js
    assert "has-query" in css and "has-query" in js
