import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

from src.intelligence.gemini_client import (
    GeminiClient,
    classify_llm_error,
    compute_backoff,
    extract_json,
)


def test_extract_json_valid_dict():
    raw = '{"sentiment": 0.85, "urgency": 9, "bias": "LONG_ONLY"}'
    res = extract_json(raw)
    assert res == {"sentiment": 0.85, "urgency": 9, "bias": "LONG_ONLY"}


def test_extract_json_with_code_fences():
    raw = """
    Here is the analysis:
    ```json
    {
        "status": "OK",
        "regime": "BULLISH_SURGE"
    }
    ```
    """
    res = extract_json(raw)
    assert res == {"status": "OK", "regime": "BULLISH_SURGE"}


def test_extract_json_with_closed_think_block():
    raw = """
    <think>
    The user wants me to parse election sentiment.
    Candidate X is leading which is pro-crypto.
    </think>
    {
        "confidence": 0.95,
        "directional_bias": "LONG_ONLY"
    }
    """
    res = extract_json(raw)
    assert res == {"confidence": 0.95, "directional_bias": "LONG_ONLY"}


def test_extract_json_with_unclosed_think_block():
    raw = """
    <think>
    Truncated reasoning that never closed properly
    {"directional_bias": "SHORT_ONLY"}
    """
    res = extract_json(raw)
    assert res is None


def test_extract_json_invalid_or_non_dict():
    assert extract_json(None) is None
    assert extract_json("") is None
    assert extract_json("plain text without brackets") is None
    assert extract_json("[1, 2, 3]") is None
    assert extract_json('{"malformed": }') is None


def test_compute_backoff():
    b1 = compute_backoff(0, retry_after="12.5")
    assert b1 == 12.5

    b2 = compute_backoff(0, retry_after="invalid")
    assert 0.1 <= b2 <= 2.0

    b_att1 = compute_backoff(1)
    b_att3 = compute_backoff(3)
    assert b_att3 >= b_att1


def test_gemini_client_200_ok():
    async def _run():
        client = GeminiClient(base_url="http://127.0.0.1:1/v1beta", api_key="test-key")

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.headers = {}
        mock_resp.json = AsyncMock(return_value={
            "candidates": [{
                "content": {
                    "parts": [{"text": '```json\n{"directional_bias": "LONG_ONLY", "confidence": 0.92}\n```'}]
                }
            }]
        })

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.post.return_value.__aenter__.return_value = mock_resp

        client._session = mock_session
        client._owns_session = False

        result = await client.chat_json("gemini-3.1-flash-lite", "system instruction", "user prompt")
        assert result == {"directional_bias": "LONG_ONLY", "confidence": 0.92}
        assert client.is_gateway_online is True
        assert client.successful_requests == 1
    asyncio.run(_run())


def test_gemini_client_429_then_200():
    async def _run():
        client = GeminiClient(base_url="http://127.0.0.1:1/v1beta", api_key="test-key", max_retries=2)

        mock_resp_429 = AsyncMock()
        mock_resp_429.status = 429
        mock_resp_429.headers = {"Retry-After": "0.01"}
        mock_resp_429.json = AsyncMock(return_value={"error": {"message": "rate limit"}})
        mock_resp_429.text = AsyncMock(return_value='{"error":{"message":"rate limit"}}')

        mock_resp_200 = AsyncMock()
        mock_resp_200.status = 200
        mock_resp_200.headers = {}
        mock_resp_200.json = AsyncMock(return_value={
            "candidates": [{"content": {"parts": [{"text": '{"regime": "NORMAL"}'}]}}]
        })

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.post.return_value.__aenter__.side_effect = [mock_resp_429, mock_resp_200]

        client._session = mock_session
        client._owns_session = False

        result = await client.chat_json("gemini-3.1-flash-lite", "system", "user")
        assert result == {"regime": "NORMAL"}
        assert client.retried_requests == 1
        assert client.successful_requests == 1
    asyncio.run(_run())


def test_gemini_client_unreachable_safe_mode():
    async def _run():
        client = GeminiClient(base_url="http://127.0.0.1:1/v1beta", api_key="test-key", max_retries=1)

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.post.return_value.__aenter__.side_effect = Exception("Connection refused")

        client._session = mock_session
        client._owns_session = False

        result = await client.chat_json("gemini-3.1-flash-lite", "system", "user")
        assert result is None
        assert client.failed_requests == 1
        assert client.is_gateway_online is False
    asyncio.run(_run())


def _mock_429_session(responses):
    """Builds a mock aiohttp session yielding the given responses in order."""
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
        resp.text = AsyncMock(return_value=json.dumps(json_body))
    else:
        resp.json = AsyncMock(return_value={})
        resp.text = AsyncMock(return_value="")
    return resp


def test_chat_json_retries_then_succeeds():
    """First 429 (with Retry-After), second 200+valid JSON -> retried==1, successful==1."""
    async def _run():
        client = GeminiClient(base_url="http://127.0.0.1:1/v1beta", api_key="test-key", max_retries=2)
        mock_session = _mock_429_session([
            _mock_resp(429, {"Retry-After": "0.01"}),
            _mock_resp(200, {}, {"candidates": [{"content": {"parts": [{"text": '{"regime": "NORMAL"}'}]}}]}),
        ])
        client._session = mock_session
        client._owns_session = False

        result = await client.chat_json("gemini-3.1-flash-lite", "system", "user")
        assert result == {"regime": "NORMAL"}
        assert client.total_requests == 1
        assert client.retried_requests == 1
        assert client.successful_requests == 1
        assert client.failed_requests == 0
        assert mock_session.post.call_count == 2
    asyncio.run(_run())


def test_chat_json_all_retries_429_returns_none():
    """Three 429 responses (max_retries=2) -> returns None, retried==2, failed==1, successful==0."""
    async def _run():
        client = GeminiClient(base_url="http://127.0.0.1:1/v1beta", api_key="test-key", max_retries=2)
        mock_session = _mock_429_session([
            _mock_resp(429, {"Retry-After": "0.01"}),
            _mock_resp(429, {"Retry-After": "0.01"}),
            _mock_resp(429, {"Retry-After": "0.01"}),
        ])
        client._session = mock_session
        client._owns_session = False

        result = await client.chat_json("gemini-3.1-flash-lite", "system", "user")
        assert result is None
        assert client.total_requests == 1
        assert client.retried_requests == 2
        assert client.failed_requests == 1
        assert client.successful_requests == 0
        assert mock_session.post.call_count == 3
    asyncio.run(_run())


def test_chat_json_sends_response_mime_type_json():
    """chat_json sends Gemini generationConfig.responseMimeType='application/json'."""
    async def _run():
        client = GeminiClient(base_url="http://127.0.0.1:1/v1beta", api_key="test-key")
        mock_session = _mock_429_session([
            _mock_resp(200, {}, {"candidates": [{"content": {"parts": [{"text": '{"regime": "NORMAL"}'}]}}]}),
        ])
        client._session = mock_session
        client._owns_session = False

        result = await client.chat_json("auto", "system", "user")
        assert result == {"regime": "NORMAL"}
        sent = mock_session.post.call_args.kwargs["json"]
        assert sent["generationConfig"]["responseMimeType"] == "application/json"
        assert mock_session.post.call_args[0][0].endswith("/models/gemini-3.1-flash-lite:generateContent")
    asyncio.run(_run())


def test_chat_json_400_format_rejection_is_not_quota():
    """HTTP 400 rejecting JSON mode retries cleanly without quota misattribution."""
    async def _run():
        client = GeminiClient(base_url="http://127.0.0.1:1/v1beta", api_key="test-key")
        body = {"error": {"message": "responseMimeType is not supported by this model", "status": "INVALID_ARGUMENT"}}
        resp1 = _mock_resp(400, {}, body)
        resp2 = _mock_resp(400, {}, {"error": {"message": "generic 400"}})
        mock_session = _mock_429_session([resp1, resp2])
        client._session = mock_session
        client._owns_session = False

        result = await client.chat_json("gemini-3.1-flash-lite", "system", "user")
        assert result is None
        assert client.failed_requests == 1
        assert client._quota_failures == {}
        assert client._unattributed_quota_ts is None
        assert classify_llm_error(400, body)["kind"] == "unknown"
    asyncio.run(_run())


def test_chat_json_repair_retry_turns_prose_into_json():
    """200 with prose triggers one bounded repair POST and succeeds if repair yields JSON."""
    async def _run():
        client = GeminiClient(base_url="http://127.0.0.1:1/v1beta", api_key="test-key")
        prose = _mock_resp(200, {}, {"candidates": [{"content": {"parts": [{"text": "**Analysis Summary:** prose, no braces"}]}}]})
        fixed = _mock_resp(200, {}, {"candidates": [{"content": {"parts": [{"text": '{"regime": "NORMAL"}'}]}}]})
        mock_session = _mock_429_session([prose, fixed])
        client._session = mock_session
        client._owns_session = False

        result = await client.chat_json("gemini-3.1-flash-lite", "system", "user")
        assert result == {"regime": "NORMAL"}
        assert mock_session.post.call_count == 2
        assert client.successful_requests == 1
        assert client.retried_requests == 1
        repair_payload = mock_session.post.call_args_list[1].kwargs["json"]
        assert repair_payload["contents"][-1]["parts"][0]["text"].startswith("Your previous reply was not a JSON object")
        assert repair_payload["systemInstruction"] == {"parts": [{"text": "system"}]}
        assert repair_payload["generationConfig"]["responseMimeType"] == "application/json"
    asyncio.run(_run())


def test_chat_json_repair_retry_gives_up_after_one_failure():
    """Both initial 200 and repair 200 return prose -> returns None after 2 POSTs."""
    async def _run():
        client = GeminiClient(base_url="http://127.0.0.1:1/v1beta", api_key="test-key")
        prose = lambda: _mock_resp(200, {}, {"candidates": [{"content": {"parts": [{"text": "plain prose, no braces"}]}}]})
        mock_session = _mock_429_session([prose(), prose()])
        client._session = mock_session
        client._owns_session = False

        result = await client.chat_json("gemini-3.1-flash-lite", "system", "user")
        assert result is None
        assert mock_session.post.call_count == 2
        assert client.successful_requests == 0
    asyncio.run(_run())


def test_chat_json_per_call_timeout_override():
    """timeout_sec=150 reaches the post call as ClientTimeout(total=150)."""
    async def _run():
        client = GeminiClient(base_url="http://127.0.0.1:1/v1beta", api_key="test-key")
        mock_session = _mock_429_session([
            _mock_resp(200, {}, {"candidates": [{"content": {"parts": [{"text": '{"regime": "NORMAL"}'}]}}]}),
        ])
        client._session = mock_session
        client._owns_session = False

        result = await client.chat_json("gemini-3.1-flash-lite", "system", "user", timeout_sec=150.0)
        assert result == {"regime": "NORMAL"}
        sent_timeout = mock_session.post.call_args.kwargs["timeout"]
        assert sent_timeout.total == 150.0
    asyncio.run(_run())
