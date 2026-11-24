"""Audit 3.12: the sync "failed" stage was effectively unreachable.

GeminiClient.check_health catches every Exception and returns a
bool, so the except branch around the health check never fired: a
dead AI endpoint surfaced as waiting/done. The fix reads the return
value -- False means the endpoint is unreachable -- and reports "failed"
when an unreachable endpoint also produces nothing to synthesize. When the
refresh DOES produce a digest (RSS + keyword fallback), "done"
still stands: the stream genuinely updated.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock

from src.intelligence.ingestion import StructuredEvent
from src.intelligence.macro_commander import MacroCommander


def _dead_gateway_commander():
    mock_client = MagicMock()
    mock_client.is_gateway_online = False
    mock_client.check_health = AsyncMock(return_value=False)
    mock_client._owns_session = False
    return MacroCommander(mock_client)


def _structured():
    return StructuredEvent(
        timestamp="2026-11-15T00:00:00+00:00",
        source="test",
        domain="macro",
        entities_tickers=[],
        urgency_score=5,
        sentiment_score=0.1,
        summary="Test event summary",
    )


def _mock_pipeline(commander, raw_events, structured):
    commander.harvester = MagicMock()
    commander.harvester.fetch_live_feeds = MagicMock(return_value=raw_events)
    commander.harvester.process_batch = AsyncMock(return_value=structured)
    commander.harvester.get_latest_events = MagicMock(return_value=[])
    commander.forum_collector = MagicMock()
    commander.forum_collector.collect_async = AsyncMock(return_value=[])


def test_sync_status_failed_when_gateway_dead_and_nothing_produced():
    commander = _dead_gateway_commander()
    _mock_pipeline(commander, [], [])
    asyncio.run(commander.refresh_digest_async())
    tel = commander.get_intel_hub_telemetry()
    assert tel["events"] == []
    assert tel["sync"]["stage"] == "failed"
    # Frozen at the last milestone reached (forum, 70): the pipeline
    # ran through fetching + forum collection before concluding there
    # was nothing to show. Never 100 on a failure.
    assert tel["sync"]["percent"] == 70
    assert tel["sync"]["percent"] < 100
    assert "AI unreachable" in tel["sync"]["detail"]


def test_sync_status_done_when_dead_gateway_still_yields_fallback_digest():
    # A dead gateway is not a failed sync when the refresh still
    # produces a digest: RSS feeds do not need the gateway, and
    # synthesis falls back to keyword scores. The stream is live on
    # fallback analysis, so "done" is honest here.
    commander = _dead_gateway_commander()
    _mock_pipeline(commander, [MagicMock()], [_structured()])
    asyncio.run(commander.refresh_digest_async())
    tel = commander.get_intel_hub_telemetry()
    assert tel["events"], "fallback synthesis must produce events"
    assert tel["sync"]["stage"] == "done"
    assert tel["sync"]["percent"] == 100
