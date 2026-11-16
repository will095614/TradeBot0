"""Audit 2.10: the article prompt is grounded in the event's own raw
snippet (RSS 450 / StockTwits 1200 chars), not only its 35-70 word
summary. The snippet rides StructuredEvent.raw_content -> curated event
"raw_snippet" -> prompt, and is stripped from the 1 Hz telemetry.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

from src.intelligence.ingestion import StructuredEvent
from src.intelligence.macro_commander import (
    MacroCommander,
    build_event_article_prompts,
)

_SNIPPET = "美國證券交易委員會批准現貨以太幣 ETF，資金流入創單日新高，機構買盤持續。"


def _event_dict(snippet=_SNIPPET):
    evt = {
        "source": "CoinDesk",
        "raw_title": "ETH ETF approval drives inflows",
        "headline": "以太幣 ETF 獲批",
        "summary": "測試摘要：以太幣 ETF 獲批。",
    }
    if snippet is not None:
        evt["raw_snippet"] = snippet
    return evt


def test_prompt_includes_raw_snippet():
    _, user_prompt = build_event_article_prompts(_event_dict())
    assert _SNIPPET in user_prompt
    assert "原文片段：" in user_prompt


def test_prompt_without_snippet_omits_line():
    _, user_prompt = build_event_article_prompts(_event_dict(snippet=None))
    assert "原文片段" not in user_prompt


def test_synthesize_plumbs_raw_snippet():
    client = MagicMock()
    client.is_gateway_online = True
    client.model_ingest = "test-ingest"
    client.model_commander = "auto"
    client.chat_json = AsyncMock(return_value=None)
    commander = MacroCommander(client)
    asyncio.run(commander.synthesize_regime([
        StructuredEvent(
            timestamp="2026-11-15T00:00:00Z",
            source="CoinDesk",
            domain="crypto",
            entities_tickers=["ETH"],
            urgency_score=6,
            sentiment_score=0.2,
            summary="測試摘要：以太幣 ETF 獲批。",
            raw_title="ETH ETF approval drives inflows",
            headline_zh="以太幣 ETF 獲批",
            raw_content=_SNIPPET,
        )
    ]))
    assert len(commander.curated_events) == 1
    assert commander.curated_events[0]["raw_snippet"] == _SNIPPET


def test_telemetry_strips_raw_snippet():
    evt = _event_dict()
    evt["article"] = None
    evt["article_state"] = "none"
    tele = MacroCommander._telemetry_event(evt)
    assert "raw_snippet" not in tele
    assert "article" not in tele
    assert tele["headline"] == "以太幣 ETF 獲批"
