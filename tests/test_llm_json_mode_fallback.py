"""V2.8.0: a provider that rejects response_format must still yield a signal.

The client used to send response_format={"type": "json_object"} on every
chat_json call. A provider that answers 400/422 for that field (instead of
ignoring it) lost the whole call. The client now retries once without the
field and remembers the model, so later calls skip it up front.
"""
import asyncio
import copy
import json

from src.intelligence.gemini_client import GeminiClient


class _Resp:
    def __init__(self, status, body):
        self.status = status
        self.headers = {}
        self._body = body

    async def json(self):
        return self._body

    async def text(self):
        return json.dumps(self._body)


class _CM:
    def __init__(self, resp):
        self._resp = resp

    async def __aenter__(self):
        return self._resp

    async def __aexit__(self, *exc):
        return False


class _FakeSession:
    def __init__(self, responses):
        self.closed = False
        self._responses = list(responses)
        self.calls = []

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append(copy.deepcopy(json))
        return _CM(self._responses.pop(0))


def _client_with(responses):
    client = GeminiClient(base_url="http://127.0.0.1:1/v1beta", api_key="test-key")
    fake = _FakeSession(responses)
    client._session = fake
    client._owns_session = False
    return client, fake


def test_rejected_response_format_retries_without_it_and_parses():
    client, fake = _client_with([
        _Resp(400, {"error": {"message": "responseMimeType is not supported"}}),
        _Resp(200, {"candidates": [{"content": {"parts": [{"text": '{"signal": "LONG"}'}]}}]}),
    ])

    parsed = asyncio.run(client.chat_json("test/model", "sys", "user"))

    assert parsed == {"signal": "LONG"}
    assert len(fake.calls) == 2
    assert fake.calls[0]["generationConfig"].get("responseMimeType") == "application/json"
    assert "responseMimeType" not in fake.calls[1]["generationConfig"]
    assert "test/model" in client._json_mode_unsupported


def test_rejected_format_is_remembered_for_later_calls():
    client, fake = _client_with([
        _Resp(200, {"candidates": [{"content": {"parts": [{"text": '{"signal": "SHORT"}'}]}}]}),
    ])
    client._json_mode_unsupported.add("test/model")

    parsed = asyncio.run(client.chat_json("test/model", "sys", "user"))

    assert parsed == {"signal": "SHORT"}
    assert len(fake.calls) == 1
    assert "responseMimeType" not in fake.calls[0]["generationConfig"]


def test_generic_400_does_not_trigger_the_format_retry():
    client, fake = _client_with([
        _Resp(400, {"error": {"message": "invalid api key"}}),
        _Resp(200, {"candidates": [{"content": {"parts": [{"text": '{"signal": "LONG"}'}]}}]}),
    ])

    parsed = asyncio.run(client.chat_json("test/model", "sys", "user"))

    assert parsed is None
    assert len(fake.calls) == 1
    assert "test/model" not in client._json_mode_unsupported
