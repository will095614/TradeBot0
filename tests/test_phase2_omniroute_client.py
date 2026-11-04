import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.intelligence.omniroute_client import (
    OmniRouteClient,
    extract_json,
    compute_backoff,
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
    # If the think block is unclosed and encapsulates the text, extract_json strips it and returns None
    res = extract_json(raw)
    assert res is None


def test_extract_json_invalid_or_non_dict():
    assert extract_json(None) is None
    assert extract_json("") is None
    assert extract_json("plain text without brackets") is None
    assert extract_json("[1, 2, 3]") is None  # Array is not a dict
    assert extract_json('{"malformed": }') is None


def test_compute_backoff():
    # Test retry after header
    b1 = compute_backoff(0, retry_after="12.5")
    assert b1 == 12.5

    # Test invalid retry after
    b2 = compute_backoff(0, retry_after="invalid")
    assert 0.1 <= b2 <= 2.0

    # Test exponential scaling
    b_att1 = compute_backoff(1)
    b_att3 = compute_backoff(3)
    assert b_att3 >= b_att1


def test_omniroute_client_200_ok():
    async def _run():
        client = OmniRouteClient(base_url="http://mock-omniroute:20128/v1", api_key="test-key")

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.headers = {}
        mock_resp.json = AsyncMock(return_value={
            "choices": [{
                "message": {
                    "content": '```json\n{"directional_bias": "LONG_ONLY", "confidence": 0.92}\n```'
                }
            }]
        })

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.post.return_value.__aenter__.return_value = mock_resp

        client._session = mock_session
        client._owns_session = False

        result = await client.chat_json("auto", "system instruction", "user prompt")
        assert result == {"directional_bias": "LONG_ONLY", "confidence": 0.92}
        assert client.is_gateway_online is True
        assert client.successful_requests == 1
    asyncio.run(_run())


def test_omniroute_client_429_then_200():
    async def _run():
        client = OmniRouteClient(base_url="http://mock-omniroute:20128/v1", max_retries=2)

        # First attempt: 429 Rate Limit
        mock_resp_429 = AsyncMock()
        mock_resp_429.status = 429
        mock_resp_429.headers = {"Retry-After": "0.01"}

        # Second attempt: 200 OK
        mock_resp_200 = AsyncMock()
        mock_resp_200.status = 200
        mock_resp_200.headers = {}
        mock_resp_200.json = AsyncMock(return_value={
            "choices": [{
                "message": {
                    "content": '{"regime": "NORMAL"}'
                }
            }]
        })

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.post.return_value.__aenter__.side_effect = [mock_resp_429, mock_resp_200]

        client._session = mock_session
        client._owns_session = False

        result = await client.chat_json("auto", "system", "user")
        assert result == {"regime": "NORMAL"}
        assert client.retried_requests == 1
        assert client.successful_requests == 1
    asyncio.run(_run())


def test_omniroute_client_unreachable_safe_mode():
    async def _run():
        client = OmniRouteClient(base_url="http://invalid-host-offline:20128/v1", max_retries=1)

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.post.return_value.__aenter__.side_effect = Exception("Connection refused")

        client._session = mock_session
        client._owns_session = False

        # Must return None safely without raising an unhandled exception
        result = await client.chat_json("auto", "system", "user")
        assert result is None
        assert client.failed_requests == 1
        assert client.is_gateway_online is False
    asyncio.run(_run())
