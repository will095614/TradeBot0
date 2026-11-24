"""V3.2.0 full-stack debug and performance optimization regression tests."""
import asyncio
import json
import math
import re
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

from src.arena.leaderboard import Leaderboard
from src.data.indicator_engine import CHOP_GATE_WINDOW_BARS
from src.data.live_engine import LiveArenaEngine
from src.data.persistence import ArenaStorage
from src.gui.dashboard import ArenaDashboard, _ArenaBridgeApi
from src.gui.view_model import (
    ViewModelPublisher,
    _clone_json_tree,
    build_engine_view_model,
)
from src.intelligence.config_manager import ConfigManager
from src.intelligence.gemini_client import GeminiClient
from src.intelligence.ingestion import IntelligenceHarvester
from src.intelligence.macro_commander import MacroRegimeState
from src.update_checker import _VALID_VERSION_RE, check_for_updates, compare_versions
from src.version import APP_VERSION

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "src" / "gui" / "assets"


def _make_15m_candles(closes):
    return [
        {
            "t": float(1700000000 + i * 900),
            "o": float(c),
            "h": float(c),
            "l": float(c),
            "c": float(c),
            "v": 1.0,
        }
        for i, c in enumerate(closes)
    ]


# ---------------------------------------------------------------------------
# 1. Indicator & Session Persistence
# ---------------------------------------------------------------------------

def test_chop_er_20_tail_slice_and_non_finite_guards():
    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    try:
        # Prefix with noisy invalid bars outside the O(21) trailing window;
        # trailing window is monotonic -> ER still computes cleanly ~ 1.0.
        prefix = [{"t": float(i), "o": 1.0, "h": 1.0, "l": 1.0, "c": float("nan"), "v": 1.0} for i in range(5)]
        tail = _make_15m_candles([3500.0 + i * 10.0 for i in range(CHOP_GATE_WINDOW_BARS + 2)])
        engine.candles_15m = prefix + tail
        er = engine.get_chop_er_20()
        assert er is not None and 0.99 <= er <= 1.0

        # Non-finite bar inside the active closed tail window returns None cleanly
        bad_tail = _make_15m_candles([3500.0 + i * 10.0 for i in range(CHOP_GATE_WINDOW_BARS + 2)])
        bad_tail[-3]["c"] = float("inf")
        engine.candles_15m = bad_tail
        assert engine.get_chop_er_20() is None
    finally:
        engine.stop()


def test_session_codec_persists_live_chop_gate_blocked(tmp_path):
    db_file = str(tmp_path / "db1.sqlite")
    e1 = LiveArenaEngine(initial_cash=Decimal("100000.00"), storage=ArenaStorage(db_path=db_file))
    try:
        e1.live_chop_gate_blocked = 7
        assert e1.save_session_state() is True
    finally:
        e1.stop()

    e2 = LiveArenaEngine(initial_cash=Decimal("100000.00"), storage=ArenaStorage(db_path=db_file))
    try:
        assert e2.restore_session_state() is True
        assert e2.live_chop_gate_blocked == 7
    finally:
        e2.stop()


# ---------------------------------------------------------------------------
# 2. Intelligence Stack (GeminiClient, ConfigManager, Ingestion, Macro)
# ---------------------------------------------------------------------------

def test_gemini_client_env_guards_model_reset_and_sse_long_lines(monkeypatch):
    monkeypatch.setenv("LLM_MAX_CONCURRENT_REQUESTS", "not-an-int")
    monkeypatch.setenv("LLM_REQUEST_TIMEOUT_SEC", "nan")
    monkeypatch.setenv("LLM_MAX_RETRIES", "-5")

    client = GeminiClient(api_key="AIzaSyTestKeyAsciiOnly")
    assert client.max_concurrent >= 1
    assert math.isfinite(client.timeout_sec) and client.timeout_sec > 0
    assert client.max_retries >= 0

    # Switching models clears stale quota/rate-limit failure state
    client._quota_failures["gemini-2.5-flash"] = 1234.0
    client._unattributed_quota_ts = 1234.0
    client._rate_limit_until = 9999999999.0
    client.last_failure = {"kind": "quota", "status": 429}
    client.set_models(model_ingest="gemini-2.5-flash-lite", model_commander="gemini-2.5-pro")
    assert client._quota_failures == {}
    assert client._unattributed_quota_ts is None
    assert client._rate_limit_until == 0.0
    assert client.last_failure is None

    # Non-ASCII key rejected cleanly without crashing check_health
    client.update_api_key("AIza-non-ascii-\u4e2d\u6587")
    ok = asyncio.run(client.check_health())
    assert ok is False
    assert client.last_failure is not None
    assert client.last_failure["kind"] == "auth"

    # _iter_sse_lines reassembles >64 KiB single lines cleanly
    big_payload = "x" * 100_000
    raw_stream = (f"data: {big_payload}\n\ndata: [DONE]\n").encode("utf-8")

    class _FakeStreamContent:
        async def iter_any(self):
            for idx in range(0, len(raw_stream), 7000):
                yield raw_stream[idx:idx + 7000]

    async def _collect():
        lines = []
        async for line in GeminiClient._iter_sse_lines(_FakeStreamContent()):
            lines.append(line)
        return lines

    lines = asyncio.run(_collect())
    assert f"data: {big_payload}" in lines
    assert "data: [DONE]" in lines


def test_config_manager_v320_sanitization_and_coerce_bool(tmp_path):
    assert ConfigManager.coerce_bool("false", default=True) is False
    assert ConfigManager.coerce_bool("0", default=True) is False
    assert ConfigManager.coerce_bool("OFF", default=True) is False
    assert ConfigManager.coerce_bool("true", default=False) is True
    assert ConfigManager.coerce_bool("on", default=False) is True
    assert ConfigManager.sanitize_key("abc\x7fdef\n ") == "abcdef"
    assert ConfigManager.sanitize_model_name("GEMINI/Gemini-2.5-Flash") == "gemini-2.5-flash"

    cm = ConfigManager(data_dir=tmp_path / "data")
    bad = cm.set_gemini_api_key("AIza-bad-\u4e2d\u6587")
    assert bad["ok"] is False


def test_ingestion_zero_count_and_macro_safe_timestamp():
    gemini = GeminiClient(api_key="")
    harvester = IntelligenceHarvester(client=gemini)
    assert harvester.get_latest_events(0) == []

    assert MacroRegimeState._fmt_local_hms(-999999999999.0) == ""
    assert MacroRegimeState._fmt_local_hms(float("nan")) == ""
    assert MacroRegimeState._fmt_local_hms(0.0) == ""
    st = MacroRegimeState(last_synthesis_ts=-1e12, fallback_since_ts=float("inf"))
    d = st.to_dict()
    assert d["last_synthesis_time"] == ""
    assert d["fallback_since"] == ""


# ---------------------------------------------------------------------------
# 3. ViewModel & Bridge
# ---------------------------------------------------------------------------

def test_view_model_fast_clone_and_absent_mtf_delta():
    src = {"candles": [{"t": 1.0, "c": 2.0}], "nested": {"k": [1, 2, 3]}}
    cloned = _clone_json_tree(src)
    assert cloned == src
    cloned["candles"][0]["c"] = 999.0
    cloned["nested"]["k"].append(4)
    assert src["candles"][0]["c"] == 2.0
    assert src["nested"]["k"] == [1, 2, 3]

    pub = ViewModelPublisher()
    snap1 = {"candles": [{"t": 1.0, "o": 1.0, "h": 1.0, "l": 1.0, "c": 1.0}], "fills": []}
    d1 = pub.compute_delta_payload(snap1)
    assert d1["is_delta"] is False

    # Absent candles_5m/candles_15m must never claim unchanged=True
    d2 = pub.compute_delta_payload(snap1)
    assert d2["candles_5m_unchanged"] is False
    assert d2["candles_15m_unchanged"] is False

    # Penultimate candle edit must invalidate candle signature
    snap_penult = {
        "candles": [
            {"t": 1.0, "o": 1.0, "h": 1.0, "l": 1.0, "c": 1.0},
            {"t": 2.0, "o": 1.0, "h": 2.0, "l": 1.0, "c": 2.0},
            {"t": 3.0, "o": 2.0, "h": 3.0, "l": 2.0, "c": 3.0},
        ],
        "fills": [],
    }
    pub.compute_delta_payload(snap_penult)
    snap_penult_edit = {
        "candles": [
            {"t": 1.0, "o": 1.0, "h": 1.0, "l": 1.0, "c": 1.0},
            {"t": 2.0, "o": 1.0, "h": 2.5, "l": 1.0, "c": 2.4},
            {"t": 3.0, "o": 2.0, "h": 3.0, "l": 2.0, "c": 3.0},
        ],
        "fills": [],
    }
    d3 = pub.compute_delta_payload(snap_penult_edit)
    assert d3["candles_unchanged"] is False


def test_bridge_export_cancelled_empty_string_and_vm_tail_cache(tmp_path):
    dash = ArenaDashboard()
    dash.config_manager = ConfigManager(data_dir=tmp_path / "data")
    dash.engine.storage = ArenaStorage(db_path=str(tmp_path / "arena.sqlite"))
    bridge = _ArenaBridgeApi(dash)
    try:
        # Build VM twice to exercise tail/heatmap/equity caches without error
        rankings = Leaderboard.get_rankings(dash.engine.broker.portfolios)
        vm1 = build_engine_view_model(dash.engine, rankings, gen=1)
        vm2 = build_engine_view_model(dash.engine, rankings, gen=1)
        assert vm1["risk_telemetry"]["chop_threshold"] == vm2["risk_telemetry"]["chop_threshold"]
        assert "strategies" in vm1 and "candles" in vm1

        # Cancelled pywebview save dialog returns empty string -> cancelled=True
        fake_win = MagicMock()
        fake_win.create_file_dialog.return_value = ""
        dash.window = fake_win
        res = bridge.export_trade_journal("csv")
        assert res["ok"] is False and res["cancelled"] is True
    finally:
        dash.stop()


# ---------------------------------------------------------------------------
# 4. Update Checker SemVer 2.0.0 Pre-Release Ordering
# ---------------------------------------------------------------------------

def test_update_checker_semver_prerelease_and_malformed_manifest(monkeypatch):
    assert compare_versions("V3.2.0-rc.10", "V3.2.0-rc.2") == 1
    assert compare_versions("V3.2.0-rc.2", "V3.2.0-rc.10") == -1
    assert compare_versions(" V3.2.0 ", "V3.2.0") == 0
    assert _VALID_VERSION_RE.match("V3.2.0-rc.1")
    assert not _VALID_VERSION_RE.match("bad version!!!")

    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.raise_for_status.return_value = None
    fake_resp.json.return_value = {"version": "not valid ###"}
    monkeypatch.setattr("src.update_checker.requests.get", lambda *a, **k: fake_resp)
    res = check_for_updates("https://example.invalid/update.json", current_version="V3.2.0")
    assert res["status"] == "check_failed"


# ---------------------------------------------------------------------------
# 5. Version Sync & Frontend V3.2.0 Contracts
# ---------------------------------------------------------------------------

def test_v320_version_and_frontend_optimizations():
    assert APP_VERSION == "V3.2.0"
    iss = (ROOT / "TradeBot0.iss").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    html = (ASSETS / "index.html").read_text(encoding="utf-8")
    css = (ASSETS / "app.css").read_text(encoding="utf-8")
    js = (ASSETS / "app.js").read_text(encoding="utf-8")

    assert '#define MyAppVersion "V3.2.0"' in iss
    assert "VersionInfoVersion=3.2.0" in iss
    assert "https://github.com/will095614/TradeBot0/releases/download/v3.2.0/TradeBot0Setup-V3.2.0.exe" in readme
    assert "V3.1.0" not in readme

    # Toast container fixed overlay & offline overlay stacking above setup wizard
    assert "#networkOfflineOverlay {\n  z-index: 10004;\n}" in css
    assert ".chart-notification-container" in css and "z-index: 9500;" in css
    # Zero CJK leaks across frontend
    for content in (html, css, js):
        assert not re.search(r"[\u4e00-\u9fff]", content)

    # Reduced motion block remains final block and pauses loading animations
    tail = css.rsplit("@media (prefers-reduced-motion: reduce)", 1)[-1]
    assert "#liveBadge .lg-wave-bars i" in tail
    assert ".btn.loading .btn-spin-icon" in tail
    assert ".intel-article-progress-fill::after" in tail

    # JS optimization & bugfix markers
    assert "JSON.stringify({ matrix" not in js
    assert "· 1m Candle" not in js
    assert "var(--ss-pos)" not in js
    assert "var(--ss-neg)" not in js
    assert "isCheckingWizardClose" not in js
    assert "function getActiveChartSeries(" in js
    assert "function canonicalStrategyKey(" in js
    assert "MODAL_INERT_STACK" in js
    assert "svg._curveSig" in js
    assert "gridEl._genomeSig" in js
    assert "fillsEl._fillsSig" in js
    assert "stratDetailCloseTimer" in js
