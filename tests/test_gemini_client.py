"""
tests/test_gemini_client.py - Direct Google Gemini REST Client, Migration & Splash Toast Verification
"""
import asyncio
import io
import json
import re
import urllib.error
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp

from src.gui.dashboard import ArenaDashboard, _ArenaBridgeApi
from src.intelligence.config_manager import ConfigManager
from src.intelligence.gemini_client import (
    DEFAULT_GEMINI_BASE_URL,
    DEFAULT_GEMINI_MODEL,
    GeminiClient,
    classify_llm_error,
    compute_backoff,
    extract_json,
    probe_gemini_api_key,
    resolve_gemini_model,
)

_ASSETS = Path(__file__).resolve().parents[1] / "src" / "gui" / "assets"


class _FakeResp:
    def __init__(self, status=200, json_body=None, headers=None, sse_lines=None, text_body=None):
        self.status = status
        self.headers = headers or {}
        self._json_body = json_body
        self._text_body = text_body
        self._sse_lines = sse_lines or []

    async def json(self):
        return self._json_body

    async def text(self):
        if self._text_body is not None:
            return self._text_body
        return json.dumps(self._json_body) if self._json_body is not None else ""

    @property
    def content(self):
        async def _iter():
            for ln in self._sse_lines:
                yield (ln if isinstance(ln, bytes) else ln.encode("utf-8"))
        return _iter()


class _FakeCM:
    def __init__(self, resp):
        self._resp = resp

    async def __aenter__(self):
        return self._resp

    async def __aexit__(self, *exc):
        return False


def test_resolve_gemini_model_aliases():
    assert resolve_gemini_model(None) == DEFAULT_GEMINI_MODEL
    assert resolve_gemini_model("") == DEFAULT_GEMINI_MODEL
    assert resolve_gemini_model("auto") == DEFAULT_GEMINI_MODEL
    assert resolve_gemini_model("auto/fast") == DEFAULT_GEMINI_MODEL
    assert resolve_gemini_model("gemini/gemini-3.1-flash-lite") == "gemini-3.1-flash-lite"
    assert resolve_gemini_model("GEMINI/gemini-2.5-flash") == "gemini-2.5-flash"
    assert resolve_gemini_model("test/model") == "test/model"


def test_classify_llm_error_structured_gemini_429_and_spend_cap():
    # Per-minute QuotaFailure is transient (never misreported as daily quota exhaustion)
    per_min = {
        "error": {
            "code": 429,
            "status": "RESOURCE_EXHAUSTED",
            "message": "Quota exceeded for metric: generate_content_free_tier_requests",
            "details": [
                {"@type": "type.googleapis.com/google.rpc.QuotaFailure",
                 "violations": [{"quotaId": "GenerateRequestsPerMinutePerProjectPerModel-FreeTier"}]},
                {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "18s"},
            ],
        }
    }
    assert classify_llm_error(429, per_min)["kind"] == "transient"

    # Per-day QuotaFailure or long RetryInfo (>= 3600s) is daily quota exhaustion
    per_day = {
        "error": {
            "code": 429,
            "status": "RESOURCE_EXHAUSTED",
            "message": "Quota exceeded for metric",
            "details": [
                {"@type": "type.googleapis.com/google.rpc.QuotaFailure",
                 "violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]},
                {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "67152s"},
            ],
        }
    }
    assert classify_llm_error(429, per_day)["kind"] == "quota"

    # Monthly spend cap 429 is terminal quota
    spend_cap = {"error": {"code": 429, "message": "Your project has exceeded its monthly spending cap."}}
    assert classify_llm_error(429, spend_cap)["kind"] == "quota"

    # Invalid API key 400 API_KEY_INVALID -> auth
    bad_key = {"error": {"code": 400, "message": "API key not valid. Please pass a valid API key.", "status": "INVALID_ARGUMENT"}}
    assert classify_llm_error(400, bad_key)["kind"] == "auth"


def test_gemini_client_rest_payload_thought_skipping_and_block_reason():
    async def _run():
        client = GeminiClient(api_key="AIzaSyTestKey123456", model_commander="gemini/gemini-3.1-flash-lite")
        fake_sess = MagicMock()
        fake_sess.closed = False

        # Candidate contains a thought part that must be ignored + real JSON text + usageMetadata
        body_ok = {
            "candidates": [{
                "finishReason": "STOP",
                "content": {
                    "parts": [
                        {"text": "internal thought {invalid json", "thought": True},
                        {"text": '{"regime": "BULLISH_SURGE", "directional_bias": "LONG_ONLY"}'},
                    ]
                },
            }],
            "usageMetadata": {"promptTokenCount": 120, "candidatesTokenCount": 40, "totalTokenCount": 160},
        }
        fake_sess.post.return_value = _FakeCM(_FakeResp(200, json_body=body_ok))
        client._session = fake_sess
        client._owns_session = False

        res = await client.chat_json("auto", "sys prompt", "user prompt", max_tokens=500, temperature=0.1)
        assert res == {"regime": "BULLISH_SURGE", "directional_bias": "LONG_ONLY"}
        assert client.is_gateway_online is True
        assert client.total_tokens_used == 160

        call_url = fake_sess.post.call_args[0][0]
        call_kwargs = fake_sess.post.call_args[1]
        assert call_url == f"{DEFAULT_GEMINI_BASE_URL}/models/gemini-3.1-flash-lite:generateContent"
        assert call_kwargs["headers"]["x-goog-api-key"] == "AIzaSyTestKey123456"
        sent = call_kwargs["json"]
        assert "model" not in sent
        assert sent["systemInstruction"] == {"parts": [{"text": "sys prompt"}]}
        assert sent["contents"] == [{"role": "user", "parts": [{"text": "user prompt"}]}]
        assert sent["generationConfig"]["maxOutputTokens"] == 500
        assert sent["generationConfig"]["responseMimeType"] == "application/json"

        # Empty candidates (e.g. safety block) returns None cleanly without crashing
        fake_sess.post.return_value = _FakeCM(_FakeResp(200, json_body={"promptFeedback": {"blockReason": "SAFETY"}}))
        res_empty = await client.chat_json("gemini-3.1-flash-lite", "sys", "user")
        assert res_empty is None
        assert client.failed_requests == 1

    asyncio.run(_run())


def test_gemini_client_sse_streaming_and_real_error_code():
    async def _run():
        client = GeminiClient(api_key="AIzaSyStreamKey12345")
        fake_sess = MagicMock()
        fake_sess.closed = False
        events = []

        sse_lines = [
            b'data: {"candidates":[{"content":{"parts":[{"text":"hidden thought","thought":true}]}}]}\n',
            b'data: {"candidates":[{"content":{"parts":[{"text":"{\\"article\\": \\""}]}}]}\n',
            b'data: {"candidates":[{"content":{"parts":[{"text":"' + (b"A" * 800) + b'"}]}}]}\n',
            b'data: {"candidates":[{"content":{"parts":[{"text":"\\"}","thought":false}],"role":"model"},"finishReason":"STOP"}],"usageMetadata":{"totalTokenCount":321}}\n',
        ]
        fake_sess.post.return_value = _FakeCM(
            _FakeResp(200, headers={"Content-Type": "text/event-stream"}, sse_lines=sse_lines)
        )
        client._session = fake_sess
        client._owns_session = False

        res = await client.chat_json(
            "gemini/gemini-3.1-flash-lite", "sys", "user", max_tokens=2000,
            on_progress=lambda st, pct, d: events.append((st, pct)), stream_progress=True,
        )
        assert res == {"article": "A" * 800}
        assert client.total_tokens_used == 321
        assert fake_sess.post.call_args[0][0].endswith(":streamGenerateContent?alt=sse")
        assert any(pct >= 90 for _, pct in events)

        # In-band SSE error frame with code 429 + daily quota marker must classify as 'quota', NOT 500/'unknown'!
        sse_err = [
            b'data: {"error":{"code":429,"message":"Requests per day limit exceeded","status":"RESOURCE_EXHAUSTED"}}\n',
        ]
        fake_sess.post.return_value = _FakeCM(
            _FakeResp(200, headers={"Content-Type": "text/event-stream"}, sse_lines=sse_err)
        )
        res_err = await client.chat_json("gemini-3.1-flash-lite", "sys", "user", stream_progress=True)
        assert res_err is None
        assert client.last_failure is not None
        assert client.last_failure["kind"] == "quota"
        assert client.has_quota_failures() is True

    asyncio.run(_run())


def test_gemini_client_check_health_and_update_api_key():
    async def _run():
        client = GeminiClient(api_key="", model_commander="gemini/gemini-3.1-flash-lite")
        assert await client.check_health() is False

        client.note_failure({"kind": "quota", "provider": "gemini", "status": 429, "detail": "daily limit"})
        assert client.has_quota_failures() is True

        client.update_api_key("AIzaSyNewKey999999")
        assert client.api_key == "AIzaSyNewKey999999"
        assert client.has_quota_failures() is False
        assert client.last_failure is None

        fake_sess = MagicMock()
        fake_sess.closed = False
        fake_sess.get.return_value = _FakeCM(_FakeResp(200, json_body={"name": "models/gemini-3.1-flash-lite"}))
        client._session = fake_sess
        client._owns_session = False

        assert await client.check_health() is True
        assert fake_sess.get.call_args[0][0] == f"{DEFAULT_GEMINI_BASE_URL}/models/gemini-3.1-flash-lite"
        assert fake_sess.get.call_args[1]["headers"]["x-goog-api-key"] == "AIzaSyNewKey999999"

    asyncio.run(_run())


def test_config_manager_legacy_omniroute_migration_once(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    env_file = tmp_path / "legacy" / ".omniroute" / ".env"
    env_file.parent.mkdir(parents=True)
    env_file.write_text('INITIAL_PASSWORD=Secret123!\nGEMINI_API_KEY="AIzaSyMigratedKey777"\n', encoding="utf-8")

    rt_dir = tmp_path / "runtime"
    (rt_dir / "node").mkdir(parents=True)
    (rt_dir / "node" / "node.exe").write_text("stub", encoding="utf-8")

    cm = ConfigManager(data_dir=tmp_path / "data")
    # Simulate old V2 config keys present on disk
    cm.save_config({"has_completed_onboarding": True, "gateway_port": 20128, "configured_providers": ["gemini"]})

    res = cm.migrate_legacy_omniroute_once(legacy_env_path=env_file, legacy_runtime_dir=rt_dir)
    assert res["imported_key"] is True
    assert res["cleaned_runtime"] is True
    assert cm.get_gemini_api_key() == "AIzaSyMigratedKey777"
    assert env_file.exists()  # Never deletes user's ~/.omniroute/.env
    assert not rt_dir.exists()  # Deletes orphaned runtime directory

    cfg = cm.load_config()
    assert cfg["legacy_omniroute_migrated"] is True
    assert cfg["legacy_runtime_cleaned"] is True
    assert cfg["has_completed_onboarding"] is True
    assert "gateway_port" not in cfg

    # Second run is a no-op and won't overwrite a user's cleared key
    res2 = cm.migrate_legacy_omniroute_once(legacy_env_path=env_file, legacy_runtime_dir=rt_dir)
    assert res2 == {"imported_key": False, "cleaned_runtime": False}


def test_dashboard_save_and_launch_hot_reloads_client_key(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    dash = ArenaDashboard()
    dash.config_manager = ConfigManager(data_dir=tmp_path / "data")
    bridge = _ArenaBridgeApi(dash)
    try:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__.return_value = mock_resp
        with patch("urllib.request.urlopen", return_value=mock_resp), \
             patch.object(dash.engine, "start_live_loop"):
            res = bridge.save_and_launch({"gemini": "AIzaSyHotReloadKey888"})
        assert res["ok"] is True
        assert res["ai_online"] is True
        assert dash.engine.llm_client.api_key == "AIzaSyHotReloadKey888"
        assert dash.config_manager.get_gemini_api_key() == "AIzaSyHotReloadKey888"

        # Quota failure surfaces cleanly via get_ai_diagnosis
        dash.engine.llm_client.note_failure({"kind": "quota", "provider": "gemini", "status": 429, "detail": "daily"})
        assert dash.get_ai_diagnosis() == "quota_exhausted"
    finally:
        dash.engine.stop()


def test_splash_toast_catchup_present_with_restored_guard():
    js = (_ASSETS / "app.js").read_text(encoding="utf-8")
    m = re.search(r"const finishPostReveal = \(\) => \{(.*?)\n          \};", js, re.S)
    assert m, "finishPostReveal not found in app.js"
    body = m.group(1)
    assert "hasInitializedPositions = true;" in body
    assert "isRestoredSession" in body
    assert "session_restored === true" in body
    assert "showPositionToast(s)" in body
    assert "addChartBeacon(s)" in body
