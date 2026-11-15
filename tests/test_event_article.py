"""Phase A: per-event tickers + lazy ~1000-word article (Intel Hub stream redesign).

Backend only: the curated event dict carries "tickers" (from
StructuredEvent.entities_tickers), "article" (None until first expand)
and "article_state" (none/loading/ready/failed); the dashboard bridge
method get_event_article generates the article once via the ingest
model and caches it. No real gateway is touched: chat_json is mocked.
"""
import asyncio
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from src.gui.dashboard import _ArenaBridgeApi
from src.intelligence.ingestion import StructuredEvent
from src.intelligence.macro_commander import (
    ARTICLE_MIN_CHARS,
    ARTICLE_SECTION_HEADINGS,
    MacroCommander,
    build_event_article_prompts,
)

# Six-section mock article, ~1400 chars: long enough to count as an
# article, never the one-line summary.
ARTICLE_TEXT = (
    "事件經過：這是一段用於測試的文章內容，描述情報事件的經過與發展。"
    "背景脈絡：這是一段用於測試的文章內容，描述事件的背景與脈絡。"
    "市場含義：這是一段用於測試的文章內容，描述事件對市場的含義。"
    "風險因素：這是一段用於測試的文章內容，描述事件帶來的風險。"
    "後續觀察：這是一段用於測試的文章內容，描述後續需要觀察的重點。"
    "總結：這是一段用於測試的文章內容，總結事件的整體影響。"
) * 8


def _make_commander(chat_result=None, online=True, tickers=("eth", "BTC", "eth")):
    """One synthesized curated event; the chat_json mock is reset after
    synthesis so each test counts only the article-generation calls."""
    client = MagicMock()
    client.is_gateway_online = online
    client.model_ingest = "test-ingest"
    client.model_commander = "auto"
    client.chat_json = AsyncMock(return_value=chat_result)
    commander = MacroCommander(client)
    asyncio.run(commander.synthesize_regime([
        StructuredEvent(
            timestamp="2026-11-15T00:00:00Z",
            source="CoinDesk",
            domain="crypto",
            entities_tickers=list(tickers),
            urgency_score=6,
            sentiment_score=0.2,
            summary="測試摘要：比特幣買盤動能轉強。",
            raw_title="BTC rallies on strong inflows",
            headline_zh="比特幣買盤動能轉強",
        )
    ]))
    client.chat_json.reset_mock()
    return commander, client


def _event_id(commander):
    return commander.curated_events[0]["id"]


def test_curated_event_carries_tickers_article_fields():
    commander, _ = _make_commander()
    evt = commander.curated_events[0]
    assert evt["tickers"] == ["ETH", "BTC"]  # uppercased, deduped, order kept
    assert evt["article"] is None
    assert evt["article_state"] == "none"


def test_curated_event_empty_tickers_becomes_empty_list():
    commander, _ = _make_commander(tickers=[])
    assert commander.curated_events[0]["tickers"] == []


def test_first_expand_generates_once_and_caches():
    commander, client = _make_commander(chat_result={"article": ARTICLE_TEXT})
    evt_id = _event_id(commander)
    res = commander.get_event_article(evt_id)
    assert res["ok"] is True
    assert res["state"] == "ready"
    assert res["article"] == ARTICLE_TEXT
    assert client.chat_json.await_count == 1
    call_kwargs = client.chat_json.await_args.kwargs
    assert call_kwargs["model"] == "test-ingest"
    assert call_kwargs["temperature"] == 0.0
    evt = commander.curated_events[0]
    assert evt["article"] == ARTICLE_TEXT
    assert evt["article_state"] == "ready"
    # The article rides the telemetry payload the frontend polls.
    tel_evt = commander.get_intel_hub_telemetry()["events"][0]
    assert tel_evt["article"] == ARTICLE_TEXT
    assert tel_evt["article_state"] == "ready"


def test_second_expand_returns_cache_without_llm():
    commander, client = _make_commander(chat_result={"article": ARTICLE_TEXT})
    evt_id = _event_id(commander)
    first = commander.get_event_article(evt_id)
    second = commander.get_event_article(evt_id)
    assert second == first
    assert client.chat_json.await_count == 1


def test_concurrent_expands_merge_into_one_llm_call():
    client = MagicMock()
    client.is_gateway_online = True
    client.model_ingest = "test-ingest"
    client.model_commander = "auto"

    async def _slow_article(*args, **kwargs):
        await asyncio.sleep(0.3)
        return {"article": ARTICLE_TEXT}

    client.chat_json = AsyncMock(side_effect=_slow_article)
    commander = MacroCommander(client)
    asyncio.run(commander.synthesize_regime([
        StructuredEvent(
            timestamp="2026-11-15T00:00:00Z",
            source="CoinDesk",
            domain="crypto",
            entities_tickers=["BTC"],
            urgency_score=6,
            sentiment_score=0.2,
            summary="測試摘要：比特幣買盤動能轉強。",
            raw_title="BTC rallies on strong inflows",
            headline_zh="比特幣買盤動能轉強",
        )
    ]))
    client.chat_json.reset_mock()
    evt_id = _event_id(commander)
    results = []

    def _call():
        results.append(commander.get_event_article(evt_id))

    t1 = threading.Thread(target=_call)
    t2 = threading.Thread(target=_call)
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)
    assert [r["ok"] for r in results] == [True, True]
    assert all(r["article"] == ARTICLE_TEXT for r in results)
    assert client.chat_json.await_count == 1


def test_gateway_offline_returns_failure_without_llm():
    commander, client = _make_commander(chat_result={"article": ARTICLE_TEXT}, online=False)
    evt_id = _event_id(commander)
    res = commander.get_event_article(evt_id)
    assert res["ok"] is False
    assert res["state"] == "failed"
    assert "gateway" in res["reason"].lower()
    assert client.chat_json.await_count == 0
    evt = commander.curated_events[0]
    assert evt["article"] is None
    assert evt["article_state"] == "failed"
    # The one-line summary is never passed off as the article.
    assert evt["summary"].startswith("測試摘要")


def test_llm_failure_returns_failure_honestly():
    commander, client = _make_commander(chat_result=None)
    evt_id = _event_id(commander)
    res = commander.get_event_article(evt_id)
    assert res["ok"] is False
    assert res["state"] == "failed"
    assert commander.curated_events[0]["article"] is None
    assert commander.curated_events[0]["article_state"] == "failed"


def test_too_short_article_is_rejected():
    commander, client = _make_commander(chat_result={"article": "太短"})
    res = commander.get_event_article(_event_id(commander))
    assert res["ok"] is False
    assert res["state"] == "failed"
    assert commander.curated_events[0]["article"] is None


def test_article_prompt_asks_for_1000_words_and_six_paragraphs():
    evt = {
        "source": "CoinDesk",
        "raw_title": "BTC rallies on strong inflows",
        "headline": "比特幣買盤動能轉強",
        "summary": "測試摘要：比特幣買盤動能轉強。",
    }
    system_prompt, user_prompt = build_event_article_prompts(evt)
    combined = system_prompt + "\n" + user_prompt
    assert "1000" in combined  # word-count requirement, not an exact count
    assert "6" in combined  # paragraph-count requirement
    for heading in ARTICLE_SECTION_HEADINGS:
        assert heading in combined
    assert "BTC rallies on strong inflows" in user_prompt
    assert len(ARTICLE_TEXT) > ARTICLE_MIN_CHARS


def test_unknown_event_id_returns_failure():
    commander, _ = _make_commander(chat_result={"article": ARTICLE_TEXT})
    res = commander.get_event_article("evt_does_not_exist")
    assert res["ok"] is False
    assert res["reason"] == "event not found"


def test_bridge_get_event_article():
    commander, client = _make_commander(chat_result={"article": ARTICLE_TEXT})
    dashboard = SimpleNamespace(engine=SimpleNamespace(macro_commander=commander))
    bridge = _ArenaBridgeApi(dashboard)
    res = bridge.get_event_article(_event_id(commander))
    assert res["ok"] is True
    assert res["article"] == ARTICLE_TEXT
    assert client.chat_json.await_count == 1
    # Second call through the bridge also reads the cache.
    assert bridge.get_event_article(_event_id(commander))["ok"] is True
    assert client.chat_json.await_count == 1
    assert bridge.get_event_article("evt_missing")["ok"] is False
