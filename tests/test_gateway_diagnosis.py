"""Gateway failure diagnosis + auto-restart watchdog.

Covers: error-body classification per provider (quota vs transient
rate limit), the all-providers-exhausted aggregation, the watchdog's
restart / backoff / give-up / install-guard behaviour, the dashboard
diagnosis state, and the frontend diagnosis-line wiring.
Decisions: ai-panels-decisions.md (NEW item).
"""
import asyncio
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from src.gui.dashboard import ArenaDashboard, _ArenaBridgeApi
from src.intelligence.config_manager import ConfigManager
from src.intelligence.gateway_supervisor import (
    GatewaySupervisor,
    WATCHDOG_MAX_CONSECUTIVE_FAILURES,
)
from src.intelligence.omniroute_client import (
    OmniRouteClient,
    classify_llm_error,
)

_ASSETS = Path(__file__).resolve().parents[1] / "src" / "gui" / "assets"

# --- canned error bodies (real shapes, per provider) -----------------------

OPENROUTER_402 = {
    "error": {
        "message": "Your account or API key has insufficient credits.",
        "code": 402,
        "metadata": {"limit_source": "free"},
    }
}
OPENROUTER_429_DAILY = {
    "error": {
        "message": "Rate limit exceeded: free-models-per-day. Add 10 credits to unlock 1000 free model requests per day.",
        "code": 429,
        "metadata": {"provider_code": "rate_limit_exceeded"},
    }
}
OPENROUTER_429_PER_MINUTE = {
    "error": {
        "message": "Rate limit exceeded: 20 requests per minute. Please try again in 30 seconds.",
        "code": 429,
    }
}
DEEPSEEK_402 = {
    "error": {
        "message": "Insufficient Balance",
        "type": "insufficient_balance",
        "code": "insufficient_balance",
    }
}
DEEPSEEK_429 = {
    "error": {
        "message": "Rate limit reached for requests per minute. Please try again in 20 seconds.",
        "type": "rate_limit",
        "code": "rate_limit_exceeded",
    }
}
GROQ_429_TPM = {
    "error": {
        "message": "Rate limit reached for model llama-3.3-70b-versatile in organization org_123 on tokens per minute (TPM): Limit 6000, Used 46812, Requested 100. Please try again in 7m 48s.",
        "type": "rate_limit_exceeded",
        "code": "rate_limit_exceeded",
    }
}
GROQ_429_TPD = {
    "error": {
        "message": "Rate limit reached for model llama-3.3-70b-versatile in organization org_123 on tokens per day (TPD): Limit 100000, Used 100000, Requested 100. Please try again in 3h 12m.",
        "type": "rate_limit_exceeded",
        "code": "rate_limit_exceeded",
    }
}
GEMINI_429_PERDAY = {
    "error": {
        "code": 429,
        "message": "Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 0",
        "status": "RESOURCE_EXHAUSTED",
        "details": [
            {
                "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                "violations": [
                    {
                        "quotaMetric": "generativelanguage.googleapis.com/generate_content_free_tier_requests",
                        "quotaId": "GenerateRequestsPerDayPerProject",
                        "quotaDimensions": {"location": "global"},
                    }
                ],
            }
        ],
    }
}
GEMINI_429_PERMINUTE = {
    "error": {
        "code": 429,
        "message": "Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 0",
        "status": "RESOURCE_EXHAUSTED",
        "details": [
            {
                "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                "violations": [
                    {
                        "quotaMetric": "generativelanguage.googleapis.com/generate_content_free_tier_requests",
                        "quotaId": "GenerateRequestsPerMinutePerProject",
                        "quotaDimensions": {"location": "global"},
                    }
                ],
            }
        ],
    }
}
GEMINI_402 = {
    "error": {
        "code": 402,
        "message": "Your account has insufficient funds. Please add funds to continue.",
        "status": "FAILED_PRECONDITION",
    }
}
NAMED_402_GROQ = {
    "error": {
        "message": "[groq] All 1 connection(s) credits exhausted — please reconnect in the dashboard",
        "code": 402,
    }
}
AUTH_401 = {
    "error": {
        "message": "Incorrect API key provided",
        "type": "invalid_request_error",
        "code": "invalid_api_key",
    }
}
SERVER_500 = {
    "error": {
        "message": "The server had an error processing your request.",
        "type": "server_error",
    }
}


# --- classifier ------------------------------------------------------------

def test_classifier_openrouter_402_is_quota():
    res = classify_llm_error(402, OPENROUTER_402)
    assert res["kind"] == "quota"


def test_classifier_openrouter_429_daily_is_quota():
    # Free-model daily allowance (per-day in the body) is a daily quota,
    # not a per-minute limit.
    res = classify_llm_error(429, OPENROUTER_429_DAILY)
    assert res["kind"] == "quota"


def test_classifier_openrouter_429_per_minute_is_transient():
    res = classify_llm_error(429, OPENROUTER_429_PER_MINUTE, retry_after="30")
    assert res["kind"] == "transient"


def test_classifier_deepseek_402_vs_429():
    assert classify_llm_error(402, DEEPSEEK_402)["kind"] == "quota"
    assert classify_llm_error(429, DEEPSEEK_429)["kind"] == "transient"


def test_classifier_groq_429_tpm_is_transient_but_tpd_is_quota():
    # Same status, same code: the body message decides. "Limit 6000 TPM
    # ... try again in 7m 48s" clears in minutes; "tokens per day (TPD)"
    # does not clear until tomorrow.
    assert classify_llm_error(429, GROQ_429_TPM)["kind"] == "transient"
    assert classify_llm_error(429, GROQ_429_TPD)["kind"] == "quota"


def test_classifier_gemini_429_perday_vs_perminute():
    # Both say "Quota exceeded" in the message: only the quotaId tells
    # them apart. A bare "quota exceeded" must never claim quota.
    assert classify_llm_error(429, GEMINI_429_PERDAY)["kind"] == "quota"
    assert classify_llm_error(429, GEMINI_429_PERMINUTE)["kind"] == "transient"


def test_classifier_gemini_402_is_quota():
    assert classify_llm_error(402, GEMINI_402)["kind"] == "quota"


def test_classifier_named_402_attributes_provider():
    res = classify_llm_error(402, NAMED_402_GROQ)
    assert res["kind"] == "quota"
    assert res["provider"] == "groq"


def test_classifier_header_attributes_provider():
    res = classify_llm_error(
        402, OPENROUTER_402, headers={"X-OmniRoute-Provider": "deepseek"}
    )
    assert res["kind"] == "quota"
    assert res["provider"] == "deepseek"


def test_classifier_metadata_provider_name_is_not_attribution():
    # error.metadata.provider_name can name OpenRouter's own upstream,
    # not the TradeBot0 leg that failed, so it must not attribute.
    body = {"error": {"message": "Insufficient Balance", "metadata": {"provider_name": "groq"}}}
    res = classify_llm_error(402, body)
    assert res["kind"] == "quota"
    assert res["provider"] is None


def test_classifier_auth_and_unknown():
    assert classify_llm_error(401, AUTH_401)["kind"] == "auth"
    assert classify_llm_error(403, AUTH_401)["kind"] == "auth"
    assert classify_llm_error(500, SERVER_500)["kind"] == "unknown"
    assert classify_llm_error(500, SERVER_500)["provider"] is None


def test_classifier_429_without_markers_is_transient():
    # A bare 429 is a rate limit by definition, never "quota exhausted".
    assert classify_llm_error(429, {"error": {"message": "Slow down"}})["kind"] == "transient"
    assert classify_llm_error(429, None)["kind"] == "transient"
    assert classify_llm_error(429, "not json at all")["kind"] == "transient"


def test_classifier_retry_after_header_long_window_is_quota():
    res = classify_llm_error(429, {"error": {"message": "Slow down"}}, retry_after="86400")
    assert res["kind"] == "quota"
    res = classify_llm_error(429, {"error": {"message": "Slow down"}}, retry_after="60")
    assert res["kind"] == "transient"


def test_classifier_402_plain_text_body_is_quota():
    assert classify_llm_error(402, "Payment Required")["kind"] == "quota"


# --- aggregation -----------------------------------------------------------

def _client():
    return OmniRouteClient(base_url="http://mock:20128/v1", api_key="k")


def test_all_providers_quota_exhausted_needs_every_provider():
    c = _client()
    cfg = ["deepseek", "gemini", "groq", "openrouter"]
    assert c.is_all_providers_quota_exhausted(cfg) is False
    for prov in ("deepseek", "gemini", "groq"):
        c.note_failure({"kind": "quota", "provider": prov, "status": 402, "detail": ""})
    assert c.is_all_providers_quota_exhausted(cfg) is False
    c.note_failure({"kind": "quota", "provider": "openrouter", "status": 402, "detail": ""})
    assert c.is_all_providers_quota_exhausted(cfg) is True


def test_unattributed_quota_counts_only_for_single_provider():
    c = _client()
    c.note_failure({"kind": "quota", "provider": None, "status": 402, "detail": ""})
    assert c.is_all_providers_quota_exhausted(["deepseek", "groq"]) is False
    assert c.is_all_providers_quota_exhausted(["deepseek"]) is True


def test_success_clears_quota_records():
    c = _client()
    for prov in ("deepseek", "gemini", "groq", "openrouter"):
        c.note_failure({"kind": "quota", "provider": prov, "status": 402, "detail": ""})
    assert c.is_all_providers_quota_exhausted(["deepseek", "gemini", "groq", "openrouter"]) is True
    c.note_success()
    assert c.is_all_providers_quota_exhausted(["deepseek", "gemini", "groq", "openrouter"]) is False


def test_stale_quota_records_expire():
    c = _client()
    c.note_failure({"kind": "quota", "provider": "deepseek", "status": 402, "detail": ""})
    c._quota_failures["deepseek"] = time.monotonic() - 90000  # > 24h ago
    assert c.is_all_providers_quota_exhausted(["deepseek"]) is False


def test_transient_failures_never_count_as_quota():
    c = _client()
    for _ in range(3):
        c.note_failure({"kind": "transient", "provider": "deepseek", "status": 429, "detail": ""})
    assert c.is_all_providers_quota_exhausted(["deepseek"]) is False
    assert c.last_failure["kind"] == "transient"


def test_daily_budget_exhausted():
    c = _client()
    c.daily_quota_limit = 100
    c.total_tokens_used = 99
    assert c.is_daily_budget_exhausted() is False
    c.total_tokens_used = 100
    assert c.is_daily_budget_exhausted() is True
    c.daily_quota_limit = None
    assert c.is_daily_budget_exhausted() is False


def test_no_configured_providers_is_never_exhausted():
    c = _client()
    c.note_failure({"kind": "quota", "provider": "deepseek", "status": 402, "detail": ""})
    assert c.is_all_providers_quota_exhausted([]) is False
    assert c.is_all_providers_quota_exhausted(None) is False


# --- chat_json integration ---------------------------------------------------

def _mock_session(responses):
    mock_session = MagicMock()
    mock_session.closed = False
    mock_session.post.return_value.__aenter__.side_effect = responses
    return mock_session


def _mock_resp(status, headers=None, json_body=None):
    resp = AsyncMock()
    resp.status = status
    resp.headers = headers or {}
    if json_body is not None:
        resp.json = AsyncMock(return_value=json_body)
    return resp


def test_chat_json_402_records_quota_failure():
    async def _run():
        client = OmniRouteClient(base_url="http://mock:20128/v1", api_key="k", max_retries=0)
        mock_session = _mock_session([_mock_resp(402, {}, NAMED_402_GROQ)])
        client._session = mock_session
        client._owns_session = False
        result = await client.chat_json("auto", "system", "user")
        assert result is None
        assert client.failed_requests == 1
        assert client.last_failure["kind"] == "quota"
        assert client.last_failure["provider"] == "groq"
        assert client.is_all_providers_quota_exhausted(["groq"]) is True
    asyncio.run(_run())


def test_chat_json_transient_429_then_200_clears_quota_records():
    async def _run():
        client = OmniRouteClient(base_url="http://mock:20128/v1", api_key="k", max_retries=2)
        client.note_failure({"kind": "quota", "provider": "deepseek", "status": 402, "detail": ""})
        mock_session = _mock_session([
            _mock_resp(429, {"Retry-After": "0.01"}, GROQ_429_TPM),
            _mock_resp(200, {}, {"choices": [{"message": {"content": '{"regime": "NORMAL"}'}}], "usage": {"total_tokens": 10}}),
        ])
        client._session = mock_session
        client._owns_session = False
        result = await client.chat_json("auto", "system", "user")
        assert result == {"regime": "NORMAL"}
        assert client.last_failure["kind"] == "transient"
        assert client.last_failure["provider"] is None
        # A success proves a provider has quota: the stale record drops.
        assert client.is_all_providers_quota_exhausted(["deepseek"]) is False
    asyncio.run(_run())


def test_chat_json_connection_refused_records_connection():
    async def _run():
        client = OmniRouteClient(base_url="http://mock:20128/v1", api_key="k", max_retries=0)
        mock_session = MagicMock()
        mock_session.closed = False
        err = aiohttp.ClientConnectorError(MagicMock(), OSError("Connection refused"))
        mock_session.post.return_value.__aenter__.side_effect = err
        client._session = mock_session
        client._owns_session = False
        result = await client.chat_json("auto", "system", "user")
        assert result is None
        assert client.failed_requests == 1
        assert client.is_gateway_online is False
        assert client.last_failure["kind"] == "connection"
    asyncio.run(_run())


# --- watchdog ---------------------------------------------------------------

def _supervisor(tmp_path):
    return GatewaySupervisor(daemon_log_path=tmp_path / "logs" / "omniroute_daemon.log")


def test_watchdog_backoff_schedule():
    assert GatewaySupervisor._watchdog_backoff_sec(0) == 10.0
    assert GatewaySupervisor._watchdog_backoff_sec(1) == 10.0
    assert GatewaySupervisor._watchdog_backoff_sec(2) == 20.0
    assert GatewaySupervisor._watchdog_backoff_sec(3) == 40.0
    assert GatewaySupervisor._watchdog_backoff_sec(5) == 160.0
    assert GatewaySupervisor._watchdog_backoff_sec(10) == 300.0


def test_watchdog_restarts_dead_gateway_it_has_seen_healthy(tmp_path):
    gs = _supervisor(tmp_path)
    try:
        with patch.object(gs, "is_port_open", return_value=False), \
             patch.object(gs, "start_daemon", return_value=(True, "ok")) as mock_start:
            gs._watchdog_armed = True
            gs._watchdog_tick()
        assert mock_start.call_count == 1
        st = gs.watchdog_status()
        assert st["healthy"] is True
        assert st["consecutive_failures"] == 0
        assert st["state"] == "ok"
    finally:
        gs.stop_watchdog()


def test_watchdog_skips_restart_when_never_seen_healthy(tmp_path):
    gs = _supervisor(tmp_path)
    try:
        with patch.object(gs, "is_port_open", return_value=False), \
             patch.object(gs, "start_daemon", return_value=(True, "ok")) as mock_start:
            gs._watchdog_tick()
        mock_start.assert_not_called()
        assert gs.watchdog_status()["healthy"] is False
    finally:
        gs.stop_watchdog()


def test_watchdog_does_not_restart_healthy_gateway(tmp_path):
    gs = _supervisor(tmp_path)
    try:
        with patch.object(gs, "is_port_open", return_value=True), \
             patch.object(gs, "probe_health", return_value=(True, {})), \
             patch.object(gs, "start_daemon") as mock_start:
            gs._watchdog_tick()
        mock_start.assert_not_called()
        assert gs.watchdog_status()["healthy"] is True
    finally:
        gs.stop_watchdog()


def test_watchdog_backs_off_between_failures(tmp_path):
    gs = _supervisor(tmp_path)
    try:
        with patch.object(gs, "is_port_open", return_value=False), \
             patch.object(gs, "start_daemon", return_value=(False, "spawn failed")) as mock_start:
            gs._watchdog_armed = True
            gs._watchdog_tick()
            assert mock_start.call_count == 1
            # Inside the backoff window: a second tick does not retry.
            gs._watchdog_tick()
            assert mock_start.call_count == 1
            # After the window elapses: it retries.
            gs._watchdog_next_retry_ts = 0.0
            gs._watchdog_tick()
            assert mock_start.call_count == 2
    finally:
        gs.stop_watchdog()


def test_watchdog_gives_up_after_repeated_failures(tmp_path):
    gs = _supervisor(tmp_path)
    try:
        with patch.object(gs, "is_port_open", return_value=False), \
             patch.object(gs, "start_daemon", return_value=(False, "spawn failed")) as mock_start:
            gs._watchdog_armed = True
            for _ in range(WATCHDOG_MAX_CONSECUTIVE_FAILURES):
                gs._watchdog_next_retry_ts = 0.0
                gs._watchdog_tick()
        assert mock_start.call_count == WATCHDOG_MAX_CONSECUTIVE_FAILURES
        assert gs.watchdog_status()["state"] == "stopped"
        # One more tick: no further restart attempts, ever.
        with patch.object(gs, "is_port_open", return_value=False), \
             patch.object(gs, "start_daemon", return_value=(True, "ok")) as mock_start2:
            gs._watchdog_tick()
        mock_start2.assert_not_called()
        assert gs.watchdog_status()["state"] == "stopped"
        assert gs.watchdog_status()["healthy"] is False
    finally:
        gs.stop_watchdog()


def test_watchdog_never_restarts_during_install(tmp_path):
    gs = _supervisor(tmp_path)
    try:
        gs.install_status = "installing-omniroute"
        with patch.object(gs, "is_port_open", return_value=False), \
             patch.object(gs, "start_daemon") as mock_start:
            gs._watchdog_armed = True
            gs._watchdog_tick()
        mock_start.assert_not_called()
        assert gs.watchdog_status()["healthy"] is None
    finally:
        gs.stop_watchdog()


def test_watchdog_recovers_when_gateway_comes_back(tmp_path):
    gs = _supervisor(tmp_path)
    try:
        with patch.object(gs, "is_port_open", return_value=False), \
             patch.object(gs, "start_daemon", return_value=(False, "nope")):
            gs._watchdog_armed = True
            for _ in range(WATCHDOG_MAX_CONSECUTIVE_FAILURES):
                gs._watchdog_next_retry_ts = 0.0
                gs._watchdog_tick()
        assert gs.watchdog_status()["state"] == "stopped"
        # The gateway comes back on its own (user started it): the
        # watchdog notices health and goes back to ok.
        with patch.object(gs, "is_port_open", return_value=True), \
             patch.object(gs, "probe_health", return_value=(True, {})):
            gs._watchdog_tick()
        st = gs.watchdog_status()
        assert st["state"] == "ok"
        assert st["healthy"] is True
        assert st["consecutive_failures"] == 0
    finally:
        gs.stop_watchdog()


def test_watchdog_thread_starts_and_stops(tmp_path):
    gs = _supervisor(tmp_path)
    try:
        with patch.object(gs, "is_port_open", return_value=True), \
             patch.object(gs, "probe_health", return_value=(True, {})), \
             patch.object(gs, "start_daemon") as mock_start, \
             patch("src.intelligence.gateway_supervisor.WATCHDOG_POLL_SEC", 0.05):
            assert gs.start_watchdog() is True
            assert gs.start_watchdog() is False  # idempotent
            time.sleep(0.2)
            assert gs.watchdog_status()["healthy"] is True
            mock_start.assert_not_called()
    finally:
        gs.stop_watchdog()
    assert gs._watchdog_thread is None


def test_watchdog_first_tick_waits_one_interval(tmp_path):
    """The watchdog waits one poll interval before its first probe, so a
    caller that stops it immediately after start never sees a tick."""
    gs = _supervisor(tmp_path)
    try:
        with patch.object(gs, "is_port_open", return_value=True), \
             patch.object(gs, "probe_health", return_value=(True, {})), \
             patch.object(gs, "_watchdog_tick", wraps=gs._watchdog_tick) as mock_tick, \
             patch("src.intelligence.gateway_supervisor.WATCHDOG_POLL_SEC", 0.2):
            assert gs.start_watchdog() is True
            time.sleep(0.05)
            mock_tick.assert_not_called()
            time.sleep(0.25)
            assert mock_tick.call_count >= 1
            assert gs.watchdog_status()["healthy"] is True
    finally:
        gs.stop_watchdog()


# --- dashboard diagnosis -----------------------------------------------------

def _make_dash(tmp_path):
    dash = ArenaDashboard()
    dash.config_manager = ConfigManager(
        data_dir=tmp_path / "data",
        omni_env_path=tmp_path / ".omniroute" / ".env",
    )
    dash.gateway_supervisor = GatewaySupervisor(
        daemon_log_path=tmp_path / "logs" / "omniroute_daemon.log"
    )
    return dash


def test_dashboard_diagnosis_states(tmp_path):
    dash = _make_dash(tmp_path)
    try:
        sup = dash.gateway_supervisor
        client = dash.engine.omniroute_client
        # No watchdog activity yet: no line.
        assert dash.get_gateway_diagnosis() == "ok"
        # Restarting beats everything.
        with patch.object(sup, "watchdog_status", return_value={"state": "restarting", "healthy": False, "consecutive_failures": 1, "last_restart_ts": None}):
            assert dash.get_gateway_diagnosis() == "restarting"
        # Dead gateway: connection problem, even with quota records present.
        for prov in ("deepseek", "gemini"):
            client.note_failure({"kind": "quota", "provider": prov, "status": 402, "detail": ""})
        with patch.object(sup, "watchdog_status", return_value={"state": "ok", "healthy": False, "consecutive_failures": 1, "last_restart_ts": None}), \
             patch.object(dash.config_manager, "get_configured_providers", return_value=["deepseek", "gemini"]):
            assert dash.get_gateway_diagnosis() == "connection_problem"
        # Healthy gateway + all providers out: quota exhausted.
        with patch.object(sup, "watchdog_status", return_value={"state": "ok", "healthy": True, "consecutive_failures": 0, "last_restart_ts": None}), \
             patch.object(dash.config_manager, "get_configured_providers", return_value=["deepseek", "gemini"]):
            assert dash.get_gateway_diagnosis() == "quota_exhausted"
        # Healthy gateway + daily budget used up: quota exhausted too.
        client.note_success()
        client.daily_quota_limit = 10
        client.total_tokens_used = 10
        with patch.object(sup, "watchdog_status", return_value={"state": "ok", "healthy": True, "consecutive_failures": 0, "last_restart_ts": None}):
            assert dash.get_gateway_diagnosis() == "quota_exhausted"
    finally:
        dash.gateway_supervisor.stop_watchdog()
        dash.engine.stop()


def test_bridge_state_carries_diagnosis(tmp_path):
    dash = _make_dash(tmp_path)
    try:
        bridge = _ArenaBridgeApi(dash)
        with patch.object(dash.gateway_supervisor, "watchdog_status", return_value={"state": "ok", "healthy": True, "consecutive_failures": 0, "last_restart_ts": None}), \
             patch.object(dash.config_manager, "get_configured_providers", return_value=["deepseek"]):
            dash.engine.omniroute_client.note_failure({"kind": "quota", "provider": "deepseek", "status": 402, "detail": ""})
            state = bridge.get_state()
            assert state["intel_hub"]["omniroute"]["diagnosis"] == "quota_exhausted"
            delta = bridge.get_state_delta()
            assert delta["intel_hub"]["omniroute"]["diagnosis"] == "quota_exhausted"
    finally:
        dash.gateway_supervisor.stop_watchdog()
        dash.engine.stop()


def test_save_and_launch_starts_watchdog(tmp_path):
    dash = _make_dash(tmp_path)
    try:
        bridge = _ArenaBridgeApi(dash)
        dash.config_manager.set_admin_password("TestAdmin123")
        with patch.object(dash.gateway_supervisor, "is_port_open", return_value=False), \
             patch.object(dash.gateway_supervisor, "start_daemon", return_value=(True, "ok")), \
             patch.object(dash.gateway_supervisor, "start_watchdog", return_value=True) as mock_watch:
            res = bridge.save_and_launch_gateway({"deepseek": "sk-test-key"}, admin_password="TestAdmin123")
        assert res["ok"] is True
        mock_watch.assert_called_once_with(armed=True)
    finally:
        dash.gateway_supervisor.stop_watchdog()
        dash.engine.stop()


class _FakeEvent:
    def __iadd__(self, handler):
        return self


class _FakeWindow:
    def __init__(self):
        self.events = SimpleNamespace(
            shown=_FakeEvent(), closing=_FakeEvent(), closed=_FakeEvent()
        )
        self.on_top = False

    def maximize(self):
        pass

    def destroy(self):
        pass

    def toggle_fullscreen(self):
        pass


class _FakeWebview:
    def __init__(self):
        self.window = _FakeWindow()
        self.started = False

    def create_window(self, *args, **kwargs):
        return self.window

    def start(self, debug=False):
        self.started = True


def test_run_starts_watchdog_when_gateway_expected(tmp_path, monkeypatch):
    dash = _make_dash(tmp_path)
    dash.config_manager.save_config({
        "has_completed_onboarding": True,
        "skip_ai_mode": False,
    })
    dash.config_manager.set_admin_password("TestAdmin123")
    fake_supervisor = MagicMock()
    fake_supervisor.is_port_open.return_value = False
    fake_supervisor.start_daemon.return_value = (True, "ok")
    dash.gateway_supervisor = fake_supervisor
    fake_webview = _FakeWebview()
    monkeypatch.setitem(sys.modules, "webview", fake_webview)
    try:
        dash.run()
    finally:
        dash.engine.stop()
    assert fake_webview.started is True
    fake_supervisor.start_watchdog.assert_called_once_with(armed=True)


def test_run_skips_watchdog_without_admin_password(tmp_path, monkeypatch):
    dash = _make_dash(tmp_path)
    dash.config_manager.save_config({
        "has_completed_onboarding": True,
        "skip_ai_mode": False,
    })
    fake_supervisor = MagicMock()
    fake_supervisor.is_port_open.return_value = False
    fake_supervisor.start_daemon.return_value = (True, "ok")
    dash.gateway_supervisor = fake_supervisor
    fake_webview = _FakeWebview()
    monkeypatch.setitem(sys.modules, "webview", fake_webview)
    try:
        dash.run()
    finally:
        dash.engine.stop()
    assert fake_webview.started is True
    fake_supervisor.start_daemon.assert_not_called()
    fake_supervisor.start_watchdog.assert_not_called()


# --- frontend wiring (static) -------------------------------------------------

def _js():
    return (_ASSETS / "app.js").read_text(encoding="utf-8")


def _css():
    return (_ASSETS / "app.css").read_text(encoding="utf-8")


def test_frontend_diagnosis_line_wiring():
    js = _js()
    assert "intelDiagnosisLine" in js
    assert "omni.diagnosis" in js
    for state in ("quota_exhausted", "connection_problem", "restarting"):
        assert state in js
    assert "AI quota exhausted — all providers out of credits" in js
    assert "Connection problem — AI services unreachable" in js
    assert "AI services stopped — restarting…" in js


def test_frontend_diagnosis_line_never_wraps():
    css = _css()
    block = css.split(".intel-diagnosis-line")[1].split("}")[0]
    assert "white-space: nowrap" in block
    assert "text-overflow: ellipsis" in block


def test_diagnosis_line_element_still_reserved():
    html = (_ASSETS / "index.html").read_text(encoding="utf-8")
    assert 'id="intelDiagnosisLine"' in html
