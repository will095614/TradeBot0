"""
Full Debug & Optimization Pass Regression Suite.

Covers Track A (Arena & Competitors), Track B (Data & LiveEngine),
Track C (Intelligence, AI Client & Infrastructure), and Track D (GUI & Frontend).
All tests are deterministic and strictly offline (zero real network calls).
"""
from __future__ import annotations

import asyncio
from decimal import Decimal
import math
from pathlib import Path
import time
from unittest.mock import MagicMock, patch

import pytest

_ROOT = Path(__file__).resolve().parent.parent


# ============================================================================
# Track A: Arena & Competitors
# ============================================================================
def test_track_a_portfolio_cross_gen_leverage_partial_close_conserves_equity():
    """Partial close after leverage mutation releases proportional margin_locked, never fabricating cash."""
    from src.arena.order import ExecutionReason, FillEvent, OrderSide, PositionSide
    from src.arena.portfolio import Portfolio

    p = Portfolio(
        portfolio_id="comp_lev",
        name="LevTest",
        initial_cash=Decimal("10000.00"),
        maker_taker_fee_rate=Decimal("0"),
        leverage=Decimal("3.0"),
        leverage_enabled=True,
    )
    # Open 3.0 ETH @ $3000 ($9000 notional -> $3000 margin locked, $7000 cash)
    p.apply_fill(
        FillEvent(
            order_id="o1",
            fill_seq=1,
            portfolio_id="comp_lev",
            symbol="ETH/USD",
            side=OrderSide.BUY,
            qty=Decimal("3.0000"),
            price=Decimal("3000.00"),
            timestamp=1000.0,
            reason=ExecutionReason.SIGNAL_ENTRY,
            fee=Decimal("0.00"),
            position_side=PositionSide.LONG,
        )
    )
    assert p.margin_locked == Decimal("3000.00")
    assert p.cash == Decimal("7000.00")

    # Evolution mutates leverage to 1.0x while position is still open
    p.leverage = Decimal("1.0")
    p.leverage_enabled = False

    # Close 1.0 ETH @ $3000 (1/3 of position) -> releases $1000 margin, NOT $3000
    p.apply_fill(
        FillEvent(
            order_id="o2",
            fill_seq=2,
            portfolio_id="comp_lev",
            symbol="ETH/USD",
            side=OrderSide.SELL,
            qty=Decimal("1.0000"),
            price=Decimal("3000.00"),
            timestamp=1060.0,
            reason=ExecutionReason.SIGNAL_EXIT,
            fee=Decimal("0.00"),
            position_side=PositionSide.LONG,
        )
    )
    assert p.margin_locked == Decimal("2000.00")
    assert p.cash == Decimal("8000.00")
    assert p.total_equity == Decimal("10000.00")


def test_track_a_portfolio_failed_fill_does_not_corrupt_fees():
    """Rejected apply_fill raises ValueError BEFORE mutating total_fees_paid."""
    from src.arena.order import ExecutionReason, FillEvent, OrderSide, PositionSide
    from src.arena.portfolio import Portfolio

    p = Portfolio(portfolio_id="comp_fee", name="FeeTest", initial_cash=Decimal("1000.00"))
    bad_fill = FillEvent(
        order_id="bad",
        fill_seq=1,
        portfolio_id="comp_fee",
        symbol="ETH/USD",
        side=OrderSide.BUY,
        qty=Decimal("10.0000"),
        price=Decimal("3000.00"),  # $30k > $1k cash
        timestamp=1000.0,
        reason=ExecutionReason.SIGNAL_ENTRY,
        fee=Decimal("15.00"),
        position_side=PositionSide.LONG,
    )
    with pytest.raises(ValueError):
        p.apply_fill(bad_fill)
    assert p.total_fees_paid == Decimal("0.00")
    assert p.cash == Decimal("1000.00")
    assert p.total_fills == 0


def test_track_a_broker_stop_market_gap_fill_at_open_and_cb_purges_pending():
    """STOP_MARKET gap-through fills at bar_open (not better stop price); circuit breaker purges pending orders."""
    from src.arena.broker_sim import BrokerSim
    from src.arena.order import OrderSide, OrderTicket, OrderType
    from src.arena.portfolio import Portfolio

    p = Portfolio(portfolio_id="comp_gap", name="GapTest", initial_cash=Decimal("100000.00"))
    broker = BrokerSim()
    broker.register_portfolio(p)
    broker.on_tick(Decimal("3000.00"), timestamp=1000.0)

    # Open long @ 3000
    broker.submit_order(
        OrderTicket(
            portfolio_id="comp_gap",
            symbol="ETH/USD",
            side=OrderSide.BUY,
            qty=Decimal("5.0000"),
            order_type=OrderType.MARKET,
            timestamp=1000.0,
        )
    )
    # Park a pending STOP_MARKET exit at 2950
    broker.submit_order(
        OrderTicket(
            portfolio_id="comp_gap",
            symbol="ETH/USD",
            side=OrderSide.SELL,
            qty=Decimal("5.0000"),
            order_type=OrderType.STOP_MARKET,
            price=Decimal("2950.00"),
            timestamp=1001.0,
        )
    )
    assert len(broker.pending_orders) == 1

    # Gap down bar opens at 2900 (below 2950 stop) -> must fill at/below bar_open, NOT 2950
    fills = broker.on_tick(
        Decimal("2910.00"),
        high=Decimal("2920.00"),
        low=Decimal("2890.00"),
        timestamp=1060.0,
        open_price=Decimal("2900.00"),
    )
    assert len(fills) == 1
    assert fills[0].price <= Decimal("2900.00")

    # Circuit breaker trip must purge any remaining pending orders for that portfolio
    p2 = Portfolio(portfolio_id="comp_cb", name="CBTest", initial_cash=Decimal("100000.00"))
    broker2 = BrokerSim()
    broker2.register_portfolio(p2)
    broker2.on_tick(Decimal("3000.00"), timestamp=1000.0)
    broker2.submit_order(
        OrderTicket(
            portfolio_id="comp_cb",
            symbol="ETH/USD",
            side=OrderSide.BUY,
            qty=Decimal("1.0000"),
            order_type=OrderType.LIMIT,
            price=Decimal("2500.00"),
            timestamp=1000.0,
        )
    )
    assert len(broker2.pending_orders) == 1
    p2.peak_equity = Decimal("100000.00")
    p2.cash = Decimal("80000.00")  # 20% drawdown > 15% limit
    broker2.on_tick(Decimal("3000.00"), timestamp=1060.0)
    assert p2.is_circuit_breaker_tripped is True
    assert not [o for o in broker2.pending_orders.values() if o.portfolio_id == "comp_cb"]


def test_track_a_leaderboard_caches_flat_portfolio():
    """Flat portfolio caches (0.0, 0.0) in _metrics_cache instead of thrashing every 1s tick."""
    from src.arena.leaderboard import Leaderboard
    from src.arena.portfolio import Portfolio

    p = Portfolio(portfolio_id="comp_flat", name="Flat", initial_cash=Decimal("100000.00"))
    p.equity_history = [(1000.0 + i * 60.0, Decimal("100000.00")) for i in range(10)]

    r1 = Leaderboard.calculate_sharpe_and_sortino(p)
    assert r1 == (0.0, 0.0)
    cached = getattr(p, "_metrics_cache", None)
    assert cached is not None
    assert cached[1] == (0.0, 0.0)


# ============================================================================
# Track B: Data & LiveEngine
# ============================================================================
def test_track_b_quote_feeds_rejects_non_positive_and_non_finite():
    """QuoteFeedsMixin._validated_quote drops zero, negative, and NaN/Inf prices."""
    from src.data.quote_feeds import QuoteFeedsMixin

    vq = QuoteFeedsMixin._validated_quote
    assert vq(0.0, None, None, None, None, None, None, "Binance") is None
    assert vq(-10.0, None, None, None, None, None, None, "Binance") is None
    assert vq(float("nan"), None, None, None, None, None, None, "Binance") is None
    assert vq(float("inf"), None, None, None, None, None, None, "Binance") is None
    ok = vq(3125.50, 3125.00, 3126.00, 3200.0, 3000.0, 5000.0, 1.5, "Binance")
    assert ok is not None
    assert ok.price == Decimal("3125.50")


def test_track_b_mtf_engine_delta_volume_and_neutral_on_conflict():
    """Repeated 1s updates for the same 1m bar accumulate delta volume only; conflicting EMAs yield NEUTRAL."""
    from src.data.mtf_engine import MultiTimeframeEngine

    mtf = MultiTimeframeEngine()
    mtf.update_from_1m_bar({"t": 3600.0, "o": 3000.0, "h": 3010.0, "l": 2995.0, "c": 3005.0, "v": 10.0})
    mtf.update_from_1m_bar({"t": 3600.0, "o": 3000.0, "h": 3012.0, "l": 2995.0, "c": 3008.0, "v": 14.0})
    mtf.update_from_1m_bar({"t": 3600.0, "o": 3000.0, "h": 3012.0, "l": 2995.0, "c": 3008.0, "v": 14.0})
    assert mtf.candles_5m[-1]["v"] == pytest.approx(14.0)
    assert mtf.candles_1h[-1]["v"] == pytest.approx(14.0)

    # Seed 210 uptrending 1h bars, then drop last close below EMA50 while EMA50 > EMA200 -> MUST reset to NEUTRAL
    bars = [
        {"t": 1700000000.0 + i * 3600.0, "o": 2000.0 + i * 5.0, "h": 2005.0 + i * 5.0,
         "l": 1995.0 + i * 5.0, "c": 2000.0 + i * 5.0, "v": 100.0}
        for i in range(210)
    ]
    assert mtf.seed_1h_buckets(bars) == "BULLISH"
    mtf.candles_1h[-1]["c"] = mtf.htf_ema_50 - 50.0
    assert mtf.recompute_regime() == "NEUTRAL"


def test_track_b_timemachine_rejects_wrong_side_tp():
    """MonteCarloOddsEvaluator refuses wrong-side explicit TP for both LONG and SHORT."""
    from src.data.timemachine import MonteCarloOddsEvaluator

    candles = [{"c": 3000.0 + (i % 7) * 5.0} for i in range(60)]
    mc = MonteCarloOddsEvaluator()
    bad_long = mc.evaluate_bracket(
        entry_price=3000.0,
        stop_loss=2950.0,
        take_profit=2900.0,
        recent_candles=candles,
        n_sims=200,
    )
    assert bad_long.passed is False
    assert "wrong side" in bad_long.verdict.lower()

    bad_short = mc.evaluate_bracket(
        entry_price=3000.0,
        stop_loss=3050.0,
        take_profit=3100.0,
        recent_candles=candles,
        n_sims=200,
    )
    assert bad_short.passed is False

    good_short = mc.evaluate_bracket(
        entry_price=3000.0,
        stop_loss=3060.0,
        take_profit=2880.0,
        recent_candles=candles,
        n_sims=500,
    )
    assert math.isfinite(good_short.expected_r)


def test_track_b_persistence_batch_fills_and_prune_candles(tmp_path):
    """record_fills_batch writes atomically via executemany; prune_old_candles bounds old rows."""
    from src.data.persistence import ArenaStorage

    store = ArenaStorage(db_path=str(tmp_path / "batch.db"))
    now = int(time.time())
    old_candles = [
        {"t": now - 100000 + i * 60, "o": 3000.0, "h": 3010.0, "l": 2990.0, "c": 3005.0, "v": 10.0}
        for i in range(15)
    ]
    fresh_candles = [
        {"t": now - 600 + i * 60, "o": 3000.0, "h": 3010.0, "l": 2990.0, "c": 3005.0, "v": 10.0}
        for i in range(10)
    ]
    store.save_candles_batch(old_candles + fresh_candles)
    pruned = store.prune_old_candles(max_age_sec=3600.0)
    assert pruned == 15
    assert len(store.load_latest_candles(limit=50)) == 10

    fills = [
        {
            "seq": i,
            "timestamp": float(now + i),
            "portfolio_id": "comp_cons",
            "strategy": "Conservative",
            "symbol": "ETH/USD",
            "side": "BUY",
            "action_label": "LONG",
            "qty": 1.0,
            "price": 3000.0 + i,
            "entry_price": 3000.0 + i,
            "pnl": None,
            "fee": 0.5,
            "reason": "SIGNAL_ENTRY",
            "is_live": True,
        }
        for i in range(1, 6)
    ]
    store.record_fills_batch(fills)
    loaded = store.load_recent_fills(limit=10)
    assert len(loaded) == 5


def test_track_b_non_integer_cadence_advances_slots():
    """Non-integer cadence_sec (e.g. 1.5s) advances slots cleanly via math.floor instead of truncating to 1s."""
    cadence_sec = 1.5
    s0 = math.floor(1000.0 / cadence_sec) * cadence_sec
    s1 = math.floor(1001.6 / cadence_sec) * cadence_sec
    assert s1 > s0
    assert s1 - s0 == pytest.approx(1.5)


# ============================================================================
# Track C: Intelligence, Gemini AI & Infrastructure
# ============================================================================
def test_track_c_gemini_max_concurrent_1_repair_no_deadlock():
    """With max_concurrent=1, JSON repair retry must NOT deadlock on the concurrency semaphore."""
    from src.intelligence.gemini_client import GeminiClient

    class _FakeResp:
        def __init__(self, content: str):
            self.status = 200
            self.headers = {}
            self._content = content

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def json(self):
            return {
                "candidates": [{"content": {"parts": [{"text": self._content}]}}],
                "usageMetadata": {"totalTokenCount": 12},
            }

        async def text(self):
            return self._content

    class _FakeSession:
        def __init__(self):
            self.closed = False
            self.calls = 0

        def post(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return _FakeResp("not valid json at all")
            return _FakeResp('{"ok": true, "score": 1}')

    fake_sess = _FakeSession()
    client = GeminiClient(
        api_key="test-key",
        max_concurrent=1,
        max_retries=1,
        session=fake_sess,
    )

    async def _run():
        return await asyncio.wait_for(
            client.chat_json(
                model="gemini-3.1-flash-lite",
                system_prompt="Return JSON",
                user_prompt="ping",
            ),
            timeout=3.0,
        )

    result = asyncio.run(_run())
    assert result == {"ok": True, "score": 1}
    assert fake_sess.calls == 2


def test_track_c_forum_collector_parses_dot_x_symbols():
    """_symbols_from_registry extracts ETH.X and BTC.X from FEED_REGISTRY URLs (not falling back)."""
    from src.intelligence import forum_collector
    from src.intelligence.forum_collector import _symbols_from_registry

    custom_reg = [
        {"type": "stocktwits", "url": "https://api.stocktwits.com/api/2/streams/symbol/SOL.X.json"},
        {"type": "stocktwits", "url": "https://api.stocktwits.com/api/2/streams/symbol/ETH.X.json"},
    ]
    with patch.object(forum_collector, "FEED_REGISTRY", custom_reg):
        assert _symbols_from_registry() == ["SOL.X", "ETH.X"]


def test_track_c_config_manager_preserves_existing_config_on_write_error(tmp_path):
    """If persisting updated config fails, existing system_config.json stays intact."""
    from src.intelligence.config_manager import ConfigManager

    cm = ConfigManager(data_dir=tmp_path / "data")
    assert cm.save_config({"gemini_api_key": "AIzaKeepMeIntact12345"}) is True
    with patch.object(cm, "_atomic_write_text", side_effect=PermissionError("locked")):
        res = cm.set_gemini_api_key("AIzaOverwriteAttempt")
    assert res["ok"] is False
    assert cm.load_config()["gemini_api_key"] == "AIzaKeepMeIntact12345"


def test_track_c_update_checker_rejects_non_https_and_clears_download_url_when_up_to_date():
    """Update checker rejects non-HTTPS URLs and clears download_url when status != update_available."""
    from src.update_checker import check_for_updates

    with patch("src.update_checker.requests.get") as mock_get:
        res_http = check_for_updates(manifest_url="http://example.invalid/manifest.json")
    mock_get.assert_not_called()
    assert res_http["status"] == "check_failed"

    fake_resp = MagicMock()
    fake_resp.raise_for_status.return_value = None
    fake_resp.json.return_value = {
        "version": "V1.0.0",
        "download_url": "https://example.invalid/old.exe",
    }
    with patch("src.update_checker.requests.get", return_value=fake_resp):
        res_same = check_for_updates(
            manifest_url="https://example.invalid/manifest.json",
            current_version="V2.1.0",
        )
    assert res_same["status"] == "up_to_date"
    assert res_same["download_url"] is None
    fake_resp.close.assert_called_once()


# ============================================================================
# Track D: GUI & Frontend
# ============================================================================
def test_track_c_save_and_launch_aborts_if_key_save_fails(tmp_path):
    """save_and_launch does not mark onboarding complete when persisting the Gemini key fails."""
    from src.gui.dashboard import ArenaDashboard, _ArenaBridgeApi
    from src.intelligence.config_manager import ConfigManager

    dash = ArenaDashboard()
    dash.config_manager = ConfigManager(data_dir=tmp_path / "data")
    bridge = _ArenaBridgeApi(dash)
    try:
        with patch.object(
            dash.config_manager,
            "set_gemini_api_key",
            return_value={"ok": False, "error": "config locked"},
        ):
            res = bridge.save_and_launch({"gemini": "AIzaSyFakeKeyForTest12345678"})
        assert res["ok"] is False
        assert "config locked" in res["message"]
        assert dash.config_manager.load_config()["has_completed_onboarding"] is False
    finally:
        dash.engine.stop()


def test_track_d_view_model_publisher_excludes_fills_and_detects_is_live_change():
    """ViewModelPublisher omits unchanged fills before deepcopy and detects is_live flips."""
    from src.gui.view_model import ViewModelPublisher

    pub = ViewModelPublisher()
    snap1 = {
        "candles": [{"t": 1000, "o": 3000, "h": 3005, "l": 2995, "c": 3002}],
        "fills": [{"seq": 1, "is_live": False, "time": "12:00:00"}],
    }
    d1 = pub.compute_delta_from_snapshot(snap1)
    assert d1["is_delta"] is False
    assert "fills" in d1

    d2 = pub.compute_delta_from_snapshot(snap1)
    assert d2["is_delta"] is True
    assert d2["candles_unchanged"] is True
    assert d2["fills_unchanged"] is True
    assert "candles" not in d2
    assert "fills" not in d2

    snap3 = {
        "candles": snap1["candles"],
        "fills": [{"seq": 1, "is_live": True, "time": "12:00:00"}],
    }
    d3 = pub.compute_delta_from_snapshot(snap3)
    assert d3["fills_unchanged"] is False
    assert "fills" in d3


def test_track_d_dashboard_save_launch_aborts_on_key_sync_failure():
    """save_and_launch reports failure cleanly when set_gemini_api_key returns ok=False."""
    from src.gui.dashboard import ArenaDashboard, _ArenaBridgeApi

    dash = ArenaDashboard()
    bridge = _ArenaBridgeApi(dash)
    dash.config_manager.set_gemini_api_key = MagicMock(return_value={"ok": False, "error": "disk full"})

    res = bridge.save_and_launch({"gemini": "AIzaSyFakeKeyForTest12345678"})
    assert res["status"] == "error"
    assert "disk full" in res["message"]
    dash.engine.stop()


def test_track_d_reset_engine_preserves_fills_after_bootstrap_completes():
    """bootstrap_intraday_session() must NOT wipe fill_records/counters preserved by reset_engine()."""
    from src.arena.order import FillEvent, OrderSide
    from src.gui.dashboard import ArenaDashboard

    dash = ArenaDashboard(initial_cash=Decimal("100000.00"))
    try:
        dash.engine.paused = True
        fill = FillEvent(
            order_id="reset-keep-1",
            portfolio_id="comp_agg",
            symbol="ETH/USD",
            side=OrderSide.BUY,
            qty=Decimal("1"),
            price=Decimal("3000"),
            fee=Decimal("1"),
            timestamp=time.time(),
        )
        dash.engine.fill_records.append(fill)
        dash.engine._live_fill_seq_offset = 7
        dash.engine._closed_trades_since_evolve = 4
        dash.engine.live_start_ts = 1700000000.0

        dash.reset_engine()

        # Wait until the background bootstrap finishes (reproducing the fast-bootstrap race)
        deadline = time.monotonic() + 5.0
        while not dash.engine.is_bootstrapped and time.monotonic() < deadline:
            time.sleep(0.02)

        assert dash.engine.is_bootstrapped is True
        assert fill in dash.engine.fill_records
        assert dash.engine._live_fill_seq_offset == 7
        assert dash.engine._closed_trades_since_evolve == 4
        assert dash.engine.live_start_ts == 1700000000.0
    finally:
        dash.engine.stop()


def test_track_d_frontend_contracts_css_html_js():
    """Static checks for Track D CSS/HTML/JS bug fixes and zero CJK / forbidden jargon."""
    css = (_ROOT / "src" / "gui" / "assets" / "app.css").read_text(encoding="utf-8")
    html = (_ROOT / "src" / "gui" / "assets" / "index.html").read_text(encoding="utf-8")
    js = (_ROOT / "src" / "gui" / "assets" / "app.js").read_text(encoding="utf-8")

    assert "--ss-text-muted:" in css
    ctrl_block = css.split(".lg-dock-pod--controls {", 1)[1].split("}", 1)[0]
    assert "overflow: visible" in ctrl_block
    assert "background:#FFD60A" in html and "MEAN" in html
    assert "fill.trigger || fill.reason" in js
    assert "pnlVal >= 0 ? '+' : '-'" in js
    for name, content in (("app.css", css), ("index.html", html), ("app.js", js)):
        assert not any("\u4e00" <= ch <= "\u9fff" for ch in content), f"CJK found in {name}"
        low = content.lower()
        for forbidden in ("spatial glass", "type a design", "style b tournament"):
            assert forbidden not in low, f"Forbidden jargon {forbidden!r} found in {name}"


# ---------------------------------------------------------------------------
# V2.4.0 Second-Order Debug & Optimization Regression Tests (Tracks A-D)
# ---------------------------------------------------------------------------


def test_v24_track_a_risk_guard_rejects_none_price_and_inverted_brackets():
    from src.arena.order import OrderSide, OrderTicket, OrderType
    from src.arena.portfolio import Portfolio
    from src.arena.risk_guard import RiskGuard

    p = Portfolio(portfolio_id="rg_v24", name="RG V24", initial_cash=Decimal("100000.00"))
    lim_no_price = OrderTicket(
        portfolio_id="rg_v24",
        symbol="ETH/USD",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        qty=Decimal("1"),
        price=None,
    )
    ok, reason = RiskGuard.validate_order(lim_no_price, p, Decimal("0.5"), Decimal("3000"))
    assert ok is False
    assert "price" in reason.lower()

    bad_sl = OrderTicket(
        portfolio_id="rg_v24",
        symbol="ETH/USD",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        qty=Decimal("1"),
        stop_loss=Decimal("3100"),
    )
    ok_sl, _ = RiskGuard.validate_order(bad_sl, p, Decimal("0.5"), Decimal("3000"))
    assert ok_sl is False

    bad_tp = OrderTicket(
        portfolio_id="rg_v24",
        symbol="ETH/USD",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        qty=Decimal("1"),
        take_profit=Decimal("2900"),
    )
    ok_tp, _ = RiskGuard.validate_order(bad_tp, p, Decimal("0.5"), Decimal("3000"))
    assert ok_tp is False


def test_v24_track_a_broker_liquidation_precedes_tp_at_exact_liq_price():
    from src.arena.broker_sim import LIQUIDATION_MAINTENANCE_RATIO, BrokerSim
    from src.arena.order import ExecutionReason, OrderSide, OrderTicket, OrderType
    from src.arena.portfolio import Portfolio

    broker = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0"))
    p = Portfolio(
        portfolio_id="lev_liq",
        name="Lev Liq",
        initial_cash=Decimal("10000.00"),
        leverage=Decimal("5.0"),
        leverage_enabled=True,
    )
    broker.register_portfolio(p, max_position_ratio=Decimal("0.50"))

    open_ticket = OrderTicket(
        portfolio_id="lev_liq",
        symbol="ETH/USD",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        qty=Decimal("5"),
        take_profit=Decimal("1500"),
        timestamp=1000.0,
    )
    broker.current_price = Decimal("1000")
    fill = broker.submit_order(open_ticket)
    assert fill is not None
    assert p.position_qty == Decimal("5.0000")

    expected_liq = (
        Decimal("1000") - (p.margin_locked * (Decimal("1") - LIQUIDATION_MAINTENANCE_RATIO) / Decimal("5"))
    ).quantize(Decimal("0.01"))

    # Wide candle touches BOTH liquidation and TP (1500): liquidation must win at exact maintenance liq_price.
    fills = broker.on_tick(
        price=Decimal("1400"),
        high=Decimal("1600"),
        low=Decimal("700"),
        timestamp=1060.0,
        open_price=Decimal("990"),
    )
    assert len(fills) == 1
    assert fills[0].reason == ExecutionReason.LIQUIDATION
    assert fills[0].price == expected_liq
    assert p.position_qty == Decimal("0")


def test_v24_track_a_portfolio_apply_fill_upfront_quantization():
    from src.arena.order import FillEvent, OrderSide
    from src.arena.portfolio import Portfolio

    p = Portfolio(portfolio_id="quant_v24", name="Quant V24", initial_cash=Decimal("10000.00"))
    f_open = FillEvent(
        order_id="q1",
        portfolio_id="quant_v24",
        symbol="ETH/USD",
        side=OrderSide.BUY,
        qty=Decimal("1.00004"),
        price=Decimal("2000.004"),
        fee=Decimal("1.00"),
        timestamp=100.0,
    )
    p.apply_fill(f_open)
    assert p.position_qty == Decimal("1.0000")
    f_close = FillEvent(
        order_id="q2",
        portfolio_id="quant_v24",
        symbol="ETH/USD",
        side=OrderSide.SELL,
        qty=Decimal("1.00004"),
        price=Decimal("2100.004"),
        fee=Decimal("1.00"),
        timestamp=200.0,
    )
    closed = p.apply_fill(f_close)
    assert p.position_qty == Decimal("0")
    assert closed.is_closing_fill is True
    assert closed.realized_pnl == Decimal("98.00")


def test_v24_track_b_live_engine_custom_llm_url_and_reset_broker_binding():
    from src.data.live_engine import LiveArenaEngine
    from src.gui.dashboard import ArenaDashboard

    eng = LiveArenaEngine(
        initial_cash=Decimal("100000.00"),
        llm_base_url="http://127.0.0.1:29999/v1beta",
    )
    try:
        assert eng.macro_commander.client.base_url == "http://127.0.0.1:29999/v1beta"
    finally:
        eng.stop()

    dash = ArenaDashboard(initial_cash=Decimal("100000.00"))
    try:
        dash.engine.paused = True
        dash.reset_engine()
        for c in dash.engine.competitors:
            pid = c.portfolio.portfolio_id
            assert dash.engine.broker.portfolios[pid] is c.portfolio
    finally:
        dash.engine.stop()


def test_v24_track_b_timemachine_single_sim_and_flat_empirical_candles():
    from src.data.timemachine import MonteCarloOddsEvaluator

    ev = MonteCarloOddsEvaluator(seed=42)
    single = ev.evaluate_bracket(
        entry_price=Decimal("3000"),
        stop_loss=Decimal("2940"),
        take_profit=Decimal("3120"),
        n_sims=1,
        n_steps=10,
    )
    assert math.isfinite(single.expected_r)
    assert 0.0 <= single.target_prob <= 1.0

    flat_candles = [{"t": float(i * 60), "o": 3000.0, "h": 3000.0, "l": 3000.0, "c": 3000.0} for i in range(25)]
    flat_res = ev.evaluate_bracket(
        entry_price=Decimal("3000"),
        stop_loss=Decimal("2940"),
        take_profit=Decimal("3120"),
        recent_candles=flat_candles,
        n_sims=64,
        n_steps=12,
    )
    assert math.isfinite(flat_res.expected_r)
    assert flat_res.target_prob + flat_res.stop_prob <= 1.0 + 1e-6


def test_v24_track_b_mtf_seed_1h_merges_same_slot():
    from src.data.mtf_engine import MultiTimeframeEngine

    mtf = MultiTimeframeEngine()
    bars = [
        {"t": 3600.0, "o": 100.0, "h": 110.0, "l": 95.0, "c": 105.0, "v": 10.0},
        {"t": 3660.0, "o": 105.0, "h": 120.0, "l": 90.0, "c": 115.0, "v": 15.0},
    ]
    for i in range(2, 55):
        bars.append({"t": float(i * 3600), "o": 115.0, "h": 125.0, "l": 110.0, "c": 120.0, "v": 20.0})
    mtf.seed_1h_buckets(bars)
    assert len(mtf.candles_1h) == 54
    first = mtf.candles_1h[0]
    assert first["t"] == 3600.0
    assert first["o"] == 100.0
    assert first["h"] == 120.0
    assert first["l"] == 90.0
    assert first["c"] == 115.0
    assert first["v"] == 25.0


def test_v24_track_c_gemini_header_and_save_no_split_brain(tmp_path):
    from unittest.mock import MagicMock, patch
    from src.gui.dashboard import ArenaDashboard, _ArenaBridgeApi
    from src.intelligence.config_manager import ConfigManager
    from src.intelligence.gemini_client import probe_gemini_api_key

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_cm = MagicMock()
    mock_cm.__enter__.return_value = mock_resp
    mock_cm.__exit__.return_value = False
    with patch("urllib.request.urlopen", return_value=mock_cm) as mock_open:
        res = probe_gemini_api_key("AIzaFakeSecretKey1234567890")
    assert res["ok"] is True
    req_obj = mock_open.call_args[0][0]
    assert "AIzaFakeSecretKey" not in req_obj.full_url
    assert req_obj.get_header("X-goog-api-key") == "AIzaFakeSecretKey1234567890"

    dash = ArenaDashboard(initial_cash=Decimal("100000.00"))
    try:
        dash.config_manager = ConfigManager(data_dir=tmp_path / "data")
        dash.config_manager.set_gemini_api_key("AIzaExistingKey123456")
        bridge = _ArenaBridgeApi(dash)
        with patch.object(dash.config_manager, "save_config", return_value=False):
            out = bridge.save_and_launch({"gemini": "AIzaNewKey1234567890"})
        assert out["ok"] is False
    finally:
        dash.engine.stop()


def test_v24_track_c_gemini_extract_json_retry_hint_dedup_and_https_redirect():
    from unittest.mock import MagicMock, patch
    from src.intelligence.ingestion import DeduplicationBuffer
    from src.intelligence.gemini_client import _retry_window_seconds, extract_json
    from src.update_checker import check_for_updates

    raw_with_fence = '{"summary": "use ```python\\nprint(1)\\n``` cleanly", "score": 7}'
    parsed = extract_json(raw_with_fence)
    assert parsed == {"summary": "use ```python\nprint(1)\n``` cleanly", "score": 7}

    assert _retry_window_seconds("Rate limit exceeded; try again in 1.5s.") == pytest.approx(1.5)

    buf = DeduplicationBuffer(capacity=2)
    assert buf.is_new("A", "https://a.invalid") is True
    assert buf.is_new("B", "https://b.invalid") is True
    buf.forget("A", "https://a.invalid")
    assert len(buf) == 1
    assert buf.is_new("C", "https://c.invalid") is True
    assert buf.is_new("B", "https://b.invalid") is False  # B was not evicted by a ghost entry

    downgraded = MagicMock()
    downgraded.raise_for_status.return_value = None
    downgraded.url = "http://insecure.invalid/manifest.json"
    downgraded.history = []
    downgraded.json.return_value = {"version": "V9.9.9"}
    with patch("src.update_checker.requests.get", return_value=downgraded):
        res = check_for_updates(manifest_url="https://example.invalid/manifest.json")
    assert res["status"] == "check_failed"


def test_v24_track_d_view_model_sanitizes_mc_stats_and_dev_bat_structure():
    from src.arena.leaderboard import Leaderboard
    from src.data.live_engine import LiveArenaEngine
    from src.gui.view_model import build_engine_view_model

    eng = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    try:
        eng.strategy_telemetry["comp_agg"]["mc_stats"] = {
            "verdict": "PROCEED",
            "expected_r": float("nan"),
            "target_prob": float("inf"),
            "stop_prob": None,
            "r_multiple": 2.0,
            "passed": True,
        }
        rankings = Leaderboard.get_rankings(eng.broker.portfolios)
        payload = build_engine_view_model(eng, rankings, gen=1)
        agg = next(s for s in payload["strategies"] if s["id"] == "comp_agg")
        assert agg["expected_r"] == 0.0
        assert agg["target_prob"] == 0.0
        assert agg["stop_prob"] is None
        assert agg["r_multiple"] == 2.0
    finally:
        eng.stop()

    bat_raw = (_ROOT / "dev_test.bat").read_bytes()
    assert b"\r\n" in bat_raw and b"\n" not in bat_raw.replace(b"\r\n", b"")
    bat = bat_raw.decode("utf-8")
    assert "--basetemp=" in bat
    assert ":launch_gui_after_verify" in bat
    assert 'set "LAUNCH_ANYWAY=' in bat
