"""Item 12A tests: 429 is not verification, dedup counts hits (no token
figure), fallback regime is marked and expires after 30 minutes, quota
soft-throttles the digest cadence."""
import asyncio
import io
import time
import urllib.error
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from src.intelligence.ingestion import IntelligenceHarvester, RawEvent, StructuredEvent
from src.intelligence.macro_commander import MacroCommander, MacroRegimeState
from src.intelligence.gemini_client import GeminiClient, probe_gemini_api_key


def _offline_commander():
    mock_client = MagicMock()
    mock_client.is_gateway_online = False
    mock_client.chat_json = AsyncMock(return_value=None)
    return MacroCommander(mock_client)


def _now_iso():
    # Weighted sentiment (item 12C) only counts events from the last 60
    # minutes, so threshold fixtures must be fresh at run time.
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _strong_bearish_events():
    # Three events, not two: C1 defines N = SUM(decay), so two fresh
    # events give N ~= 1.9996 and never reach the N >= 2 direction gate.
    return [
        StructuredEvent(timestamp=_now_iso(), source="Test", domain="macro", entities_tickers=["FED"], urgency_score=9, sentiment_score=-0.70, summary="Strong bearish 1"),
        StructuredEvent(timestamp=_now_iso(), source="Test", domain="macro", entities_tickers=["FED"], urgency_score=8, sentiment_score=-0.85, summary="Strong bearish 2"),
        StructuredEvent(timestamp=_now_iso(), source="Test", domain="macro", entities_tickers=["FED"], urgency_score=9, sentiment_score=-0.80, summary="Strong bearish 3"),
    ]


@patch("urllib.request.urlopen")
def test_key_rate_limit_429_is_not_verified(mock_urlopen):
    """A4-1: 429 proves the key was accepted far enough to be rate limited,
    not that it is valid. It must never be reported as verified."""
    mock_urlopen.side_effect = urllib.error.HTTPError(
        url="https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite",
        code=429,
        msg="Too Many Requests",
        hdrs={},
        fp=io.BytesIO(b'{"error":"rate limited"}'),
    )
    res = probe_gemini_api_key("AIzaRateLimitedKey12345678")
    assert res["ok"] is False
    assert "429" in res["message"]
    assert "valid" not in res["message"].lower()


def test_dedup_hits_counted_not_token_estimate():
    """A4-3: a duplicate event counts one dedup hit and claims no tokens."""
    client = GeminiClient()
    harvester = IntelligenceHarvester(client=client)
    ev = RawEvent(source="Test", domain="crypto", title="Dup title", url="https://example.com/x", timestamp=2000.0)
    assert harvester.push_raw_events([ev]) == [ev]
    assert harvester.push_raw_events([ev]) == []
    assert client.total_dedup_hits == 1
    assert client.total_tokens_saved == 0


def test_fallback_regime_is_marked_and_expires():
    """A3 option 2: a keyword-fallback regime is marked fallback=True; after
    30 minutes without the LLM it steps down to BIDIRECTIONAL."""
    commander = _offline_commander()
    state = asyncio.run(commander.synthesize_regime(_strong_bearish_events()))
    assert state.directional_bias == "SHORT_ONLY"
    assert state.fallback is True
    assert state.fallback_since_ts > 0.0

    # 31 minutes later, still no LLM: the same strong events must NOT keep
    # vetoing -- the stale fallback steps down to neutral.
    commander.current_state.fallback_since_ts = time.time() - 1860.0
    state = asyncio.run(commander.synthesize_regime(_strong_bearish_events()))
    assert state.directional_bias == "BIDIRECTIONAL"
    assert state.regime == "NORMAL"
    assert state.risk_multiplier == 1.0


def test_fallback_clears_when_llm_recovers():
    """A3 option 2: a fresh LLM synthesis clears the fallback provenance."""
    commander = _offline_commander()
    state = asyncio.run(commander.synthesize_regime(_strong_bearish_events()))
    assert state.fallback is True

    commander.client.is_gateway_online = True
    commander.client.chat_json = AsyncMock(return_value={
        "regime": "BULLISH_SURGE",
        "directional_bias": "LONG_ONLY",
        "risk_multiplier": 1.25,
        "confidence": 0.8,
        "active_headline": "LLM back online",
    })
    state = asyncio.run(commander.synthesize_regime(_strong_bearish_events()))
    assert state.directional_bias == "LONG_ONLY"
    assert state.fallback is False
    assert state.fallback_since_ts == 0.0


def test_empty_digest_expires_stale_fallback():
    """A3 option 2: with no new events at all, an expired fallback still
    steps down instead of sitting on a stale directional veto."""
    commander = _offline_commander()
    commander.current_state.fallback = True
    commander.current_state.fallback_since_ts = time.time() - 1860.0
    commander.current_state.directional_bias = "SHORT_ONLY"
    commander.current_state.regime = "BEARISH_PANIC"
    state = asyncio.run(commander.synthesize_regime([]))
    assert state.directional_bias == "BIDIRECTIONAL"
    assert state.regime == "NORMAL"


def test_quota_throttling_slows_digest(monkeypatch):
    """A4-4: at/over the daily quota the digest slows to >= 900s; under
    quota it keeps the configured base cadence."""
    # F4: the quota is the user's own DAILY_TOKEN_QUOTA budget -- the
    # client no longer invents a 100000 denominator when it is unset.
    monkeypatch.setenv("DAILY_TOKEN_QUOTA", "100000")
    client = GeminiClient()
    commander = MacroCommander(client)
    assert client.get_quota_pct() == 100.0
    assert client.is_over_quota() is False
    assert commander.digest_interval_sec() == 300.0
    assert commander.is_quota_throttled() is False

    client.total_tokens_used = 100000
    assert client.get_quota_pct() == 0.0
    assert client.is_over_quota() is True
    assert commander.digest_interval_sec() == 900.0
    assert commander.digest_interval_sec(600.0) == 900.0
    assert commander.digest_interval_sec(1200.0) == 1200.0
    assert commander.is_quota_throttled() is True

    tel = commander.get_intel_hub_telemetry()
    assert tel["ai"]["quota_throttled"] is True
    assert tel["ai"]["digest_interval_sec"] == 900.0
    assert tel["ai"]["dedup_hits"] == 0


def test_regime_state_dict_exposes_fallback():
    """A3: the view model (macro_commander.to_dict) carries the fallback
    provenance the frontend pill reads."""
    d = MacroRegimeState().to_dict()
    assert d["fallback"] is False
    assert d["fallback_since"] == ""


def test_quota_pct_has_no_invented_denominator(monkeypatch):
    """F4: with no DAILY_TOKEN_QUOTA set there is no real denominator, so
    get_quota_pct() is None and the digest never throttles on usage; the
    only throttle signal is an observed 429, which cools down again."""
    import time as _time

    monkeypatch.delenv("DAILY_TOKEN_QUOTA", raising=False)
    client = GeminiClient()
    assert client.get_quota_pct() is None
    assert client.is_over_quota() is False
    commander = MacroCommander(client)
    assert commander.is_quota_throttled() is False
    assert commander.digest_interval_sec() == 300.0
    tel = commander.get_intel_hub_telemetry()
    assert tel["ai"]["quota_pct"] is None
    assert tel["ai"]["quota_throttled"] is False

    # A 429 observed through chat_json starts the cooldown: the digest
    # throttles while the signal is fresh...
    async def _run_429():
        c = GeminiClient(api_key="test-key", max_retries=0)
        mock_resp = AsyncMock()
        mock_resp.status = 429
        mock_resp.headers = {}
        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.post.return_value.__aenter__.return_value = mock_resp
        c._session = mock_session
        c._owns_session = False
        assert await c.chat_json("gemini-3.1-flash-lite", "system", "user") is None
        return c

    limited = asyncio.run(_run_429())
    assert limited.is_rate_limited() is True
    assert limited.is_over_quota() is True
    assert MacroCommander(limited).digest_interval_sec() == 900.0
    assert MacroCommander(limited).is_quota_throttled() is True

    # ...and recovers once the cooldown has passed.
    limited._rate_limit_until = _time.monotonic() - 1.0
    assert limited.is_over_quota() is False
    assert MacroCommander(limited).digest_interval_sec() == 300.0


def test_quota_pct_uses_user_set_budget(monkeypatch):
    """F4: when the user sets their own DAILY_TOKEN_QUOTA, the denominator
    is real and the % is computed from it."""
    monkeypatch.setenv("DAILY_TOKEN_QUOTA", "200000")
    client = GeminiClient()
    assert client.get_quota_pct() == 100.0
    client.total_tokens_used = 50000
    assert client.get_quota_pct() == 75.0
    assert client.is_over_quota() is False
    client.total_tokens_used = 200000
    assert client.get_quota_pct() == 0.0
    assert client.is_over_quota() is True
