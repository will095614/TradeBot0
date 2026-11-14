"""Workstream 3: Intel Hub layout + honest stream sync progress.

Backend: MacroCommander records the real first-sync pipeline stage
(gateway health -> RSS fetch + dedup -> ingest -> forum -> synthesis)
in telemetry["sync"] with a milestone percent that never claims 100
while the stream is still empty. Frontend: the empty stream is a
centered loading block (label + meter + percent) and the top-deck
cards share their height instead of leaving a dead void.
"""
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.intelligence.ingestion import StructuredEvent
from src.intelligence.macro_commander import MacroCommander

_ASSETS = Path(__file__).resolve().parents[1] / "src" / "gui" / "assets"


def _html():
    return (_ASSETS / "index.html").read_text(encoding="utf-8")


def _js():
    return (_ASSETS / "app.js").read_text(encoding="utf-8")


def _css():
    return (_ASSETS / "app.css").read_text(encoding="utf-8")


def _rule(css, selector):
    start = css.index(selector)
    return css[start:css.index("}", start)]


def _commander():
    mock_client = MagicMock()
    mock_client.is_gateway_online = False
    mock_client.check_health = AsyncMock(return_value=None)
    # The refresh finally-block only closes the client when it owns
    # the session; a MagicMock attribute would be truthy and await on
    # a non-async close, so pin it off explicitly.
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


def test_sync_status_starts_idle():
    commander = _commander()
    sync = commander.get_intel_hub_telemetry()["sync"]
    assert sync["stage"] == "idle"
    assert sync["percent"] == 0
    assert sync["detail"] == ""
    assert sync["updated_at"] == 0.0
    assert "events" in commander.get_intel_hub_telemetry()


def test_sync_status_reaches_done_100_with_events():
    commander = _commander()
    _mock_pipeline(commander, [MagicMock()], [_structured()])
    asyncio.run(commander.refresh_digest_async())
    tel = commander.get_intel_hub_telemetry()
    assert tel["events"], "first successful sync must produce events"
    assert tel["sync"]["stage"] == "done"
    assert tel["sync"]["percent"] == 100
    assert tel["sync"]["detail"] == "Stream live"
    # Telemetry hands out a copy, so a reader cannot rewrite live state.
    tel["sync"]["percent"] = 999
    assert commander.sync_status["percent"] == 100


def test_sync_status_failed_when_gateway_down():
    mock_client = MagicMock()
    mock_client.is_gateway_online = False
    mock_client.check_health = AsyncMock(side_effect=RuntimeError("gateway down"))
    mock_client._owns_session = False
    commander = MacroCommander(mock_client)
    # A health-check failure still propagates, exactly as before --
    # the refresh now records "failed" first.
    with pytest.raises(RuntimeError):
        asyncio.run(commander.refresh_digest_async())
    tel = commander.get_intel_hub_telemetry()
    assert tel["events"] == []
    assert tel["sync"]["stage"] == "failed"
    assert tel["sync"]["percent"] == 10
    assert tel["sync"]["percent"] < 100


def test_sync_status_failed_when_feeds_down():
    commander = _commander()
    commander.harvester = MagicMock()
    commander.harvester.fetch_live_feeds = MagicMock(side_effect=RuntimeError("feeds down"))
    commander.harvester.get_latest_events = MagicMock(return_value=[])
    commander.forum_collector = MagicMock()
    asyncio.run(commander.refresh_digest_async())
    tel = commander.get_intel_hub_telemetry()
    assert tel["events"] == []
    assert tel["sync"]["stage"] == "failed"
    assert tel["sync"]["percent"] == 30
    assert tel["sync"]["percent"] < 100


def test_sync_status_waiting_when_no_events_anywhere():
    commander = _commander()
    _mock_pipeline(commander, [], [])
    asyncio.run(commander.refresh_digest_async())
    tel = commander.get_intel_hub_telemetry()
    assert tel["events"] == []
    assert tel["sync"]["stage"] == "waiting"
    assert tel["sync"]["percent"] == 85
    assert tel["sync"]["percent"] < 100


def test_stream_loading_block_is_centered_with_meter():
    js = _js()
    css = _css()
    # The old top-aligned one-line empty state must be gone.
    assert "Synchronizing multi-domain live intelligence stream..." not in js
    # The empty branch renders a centered loading block (label + meter
    # + percent) and caps the backend milestone below 100.
    assert "intel-stream-loading" in js
    assert "intel-stream-progress-fill" in js
    assert "ss-meter" in js
    assert "Math.min(Number.isFinite(rawPct) ? rawPct : 0, 90)" in js
    assert "is-loading" in js
    loading = _rule(css, ".intel-events-list.is-loading {")
    assert "display: flex;" in loading
    assert "align-items: center;" in loading
    assert "justify-content: center;" in loading
    assert "min-height: 100%;" in loading
    assert ".intel-stream-progress-fill {" in css


def test_top_deck_cards_share_height_without_dead_void():
    css = _css()
    body = _rule(css, ".intel-panel-body {")
    assert "flex: 1;" in body
    # The Market Direction metric row takes the free height and its
    # cells center vertically; the Refresh row pins to the bottom of
    # the AI Services card.
    row = _rule(css, ".intel-top-deck .intel-panel:last-child .intel-metrics-row {")
    assert "flex: 1;" in row
    assert "align-content: stretch;" in row
    metric = _rule(css, ".intel-top-deck .intel-panel:last-child .intel-metric {")
    assert "justify-content: center;" in metric
    subrow = _rule(css, ".intel-top-deck .intel-panel:first-child .intel-meta-subrow {")
    assert "margin-top: auto;" in subrow
