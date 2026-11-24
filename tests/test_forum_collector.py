"""Item 12B tests: StockTwits-only forum collection (no-login sources only).

No Reddit code or tests exist in phase 1 (user rule 2026-11-13: Reddit
needs per-user OAuth, which conflicts with "anyone can use it").
Covers: the StockTwits parser, the registry-driven fetcher (no-login
sources only, forum streams owned by the collector), collector cadence
and hourly cap, and the offline forum flow (keyword fallback, no LLM)."""
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

from src.intelligence.forum_collector import ForumCollector
from src.intelligence.ingestion import (
    FEED_REGISTRY,
    IntelligenceHarvester,
    RawEvent,
    StructuredEvent,
    parse_stocktwits_stream,
)
from src.intelligence.macro_commander import MacroCommander
from src.intelligence.gemini_client import GeminiClient


def _stream_json(symbol, latest_id, bodies):
    msgs = []
    for i, body in enumerate(bodies):
        msgs.append({
            "id": latest_id - i,
            "body": body,
            "created_at": "2026-11-13T07:00:00Z",
            "user": {"username": f"user{i}"},
            "entities": {"sentiment": {"basic": "Bullish"}} if i == 0 else {},
        })
    return {"messages": msgs, "symbol": {"symbol": symbol}}


def test_parse_stocktwits_stream_builds_one_forum_event():
    data = _stream_json("ETH.X", 100, [
        "ETH.X breakout above resistance, momentum building",
        "Second message with more detail here",
        "Third message, short",
    ])
    events = parse_stocktwits_stream(data, "ETH.X")
    assert len(events) == 1
    ev = events[0]
    assert ev.domain == "forum"
    assert ev.tier == 2
    assert ev.thread_id == "stocktwits:ETH.X"
    assert "StockTwits ETH.X" in ev.source
    assert "breakout above resistance" in ev.title
    assert "user0" in ev.raw_content
    assert "Second message" in ev.raw_content
    assert len(ev.raw_content) <= 1200
    assert ev.url == "https://stocktwits.com/user0/message/100"
    assert ev.timestamp > 0


def test_parse_stocktwits_stream_empty_and_malformed():
    assert parse_stocktwits_stream({"messages": []}, "ETH.X") == []
    assert parse_stocktwits_stream({"messages": [{"body": "  "}]}, "ETH.X") == []
    assert parse_stocktwits_stream(None, "ETH.X") == []
    assert parse_stocktwits_stream("not a dict", "ETH.X") == []


def test_parse_stocktwits_stream_truncates_long_content():
    bodies = ["x" * 500] * 20
    events = parse_stocktwits_stream(_stream_json("BTC.X", 7, bodies), "BTC.X")
    assert len(events) == 1
    assert len(events[0].raw_content) <= 1200


def test_registry_contains_only_no_login_sources():
    """User rule 2026-11-13: the registry holds no-login sources only."""
    types = {e.get("type") for e in FEED_REGISTRY}
    assert types <= {"rss", "atom", "rest_json", "stocktwits"}
    assert "websocket" not in types  # Tree News needs a key
    assert "reddit_json" not in types  # Reddit needs per-user OAuth
    ids = {e["id"] for e in FEED_REGISTRY}
    assert "tree_news_ws" not in ids
    assert "reddit_crypto" not in ids
    assert "reddit_wsb" not in ids
    assert "decrypt_wire" in ids
    assert "stocktwits_ethx" in ids
    assert "stocktwits_btcx" in ids
    # Crypto streams are ETH.X / BTC.X: plain "ETH" on StockTwits is the
    # Grayscale ETF, not crypto (verified from the PC).
    urls = {e["url"] for e in FEED_REGISTRY if e.get("type") == "stocktwits"}
    assert urls == {
        "https://api.stocktwits.com/api/2/streams/symbol/ETH.X.json",
        "https://api.stocktwits.com/api/2/streams/symbol/BTC.X.json",
    }


def _registry_mock_get(url, headers=None, timeout=None):
    """Per-URL mock: unique RSS titles (so dedup keeps one per source),
    Polymarket JSON, and a hard failure if a forum URL is ever fetched
    by the news fetcher (the collector owns those)."""
    mock_resp = MagicMock()
    if "stocktwits" in url:
        raise AssertionError(f"news fetcher must not fetch forum URL: {url}")
    if "polymarket" in url:
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {"title": "Poly event", "volume24hr": 100, "slug": "x", "markets": []}
        ]
        mock_resp.text = ""
        return mock_resp
    mock_resp.status_code = 200
    # The SEC EDGAR URL contains bare "&" characters, which are illegal in
    # XML text; escape them or ET.fromstring fails and that source yields
    # zero events.
    safe_url = url.replace("&", "&amp;")
    mock_resp.text = (
        "<rss><channel><item>"
        f"<title>Item from {safe_url}</title><link>{safe_url}/item1</link>"
        "<description>desc</description></item></channel></rss>"
    )
    mock_resp.json.side_effect = ValueError("not json")
    return mock_resp


def test_fetch_from_registry_dispatches_by_type_and_skips_forum():
    client = GeminiClient()
    harvester = IntelligenceHarvester(client=client)
    with patch("requests.get", side_effect=_registry_mock_get):
        events = harvester.fetch_from_registry()
    fetchable = [e for e in FEED_REGISTRY if e.get("type") in ("rss", "atom", "rest_json")]
    assert len(events) == len(fetchable) == 19
    assert all(e.domain != "forum" for e in events)
    assert all(e.source != "StockTwits" for e in events)
    # Tiers ride along from the registry.
    by_source = {e.source: e for e in events}
    assert by_source["ForexLive Breaking Wire"].tier == 1
    assert by_source["CoinDesk Live"].tier == 2
    assert by_source["FRED Economic Data Releases"].tier == 3
    assert by_source["Polymarket"].tier == 1


def test_fetch_live_feeds_still_returns_test_fixtures():
    """ARENA_FAST_TEST=1 (conftest) still returns the 2 marked fixtures."""
    client = GeminiClient()
    harvester = IntelligenceHarvester(client=client)
    events = harvester.fetch_live_feeds()
    assert len(events) == 2
    assert all("[TEST]" in e.title for e in events)


def test_forum_collector_stocktwits_flow_and_cadence(monkeypatch):
    """Collector fetches both streams, then stays quiet until the 15-minute
    cadence elapses; a moved stream then yields new events."""
    monkeypatch.setenv("ARENA_FAST_TEST", "0")
    calls = {"n": 0}

    def mock_get(url, headers=None, timeout=None):
        calls["n"] += 1
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        if "ETH.X" in url:
            mock_resp.json.return_value = _stream_json("ETH.X", 100 + calls["n"], ["ETH.X moon", "more"])
        else:
            mock_resp.json.return_value = _stream_json("BTC.X", 200, ["BTC.X steady", "more"])
        return mock_resp

    collector = ForumCollector(client=MagicMock())
    assert collector.symbols == ["ETH.X", "BTC.X"]
    with patch("requests.get", side_effect=mock_get):
        first = asyncio.run(collector.collect_async())
        assert len(first) == 2
        assert {e.thread_id for e in first} == {"stocktwits:ETH.X", "stocktwits:BTC.X"}
        # Immediate second call: cadence gate, no HTTP at all.
        before = calls["n"]
        assert asyncio.run(collector.collect_async()) == []
        assert calls["n"] == before
        # 16 minutes later: fetches again.
        collector._last_collect_ts = time.time() - 961.0
        second = asyncio.run(collector.collect_async())
        assert len(second) == 2


def test_forum_collector_hourly_cap(monkeypatch):
    monkeypatch.setenv("ARENA_FAST_TEST", "0")
    collector = ForumCollector(client=MagicMock())
    collector._summary_count = 12
    collector._summary_window_start = time.time()
    with patch("requests.get") as mock_get:
        assert asyncio.run(collector.collect_async()) == []
        mock_get.assert_not_called()


def test_forum_collector_fast_test_short_circuits():
    """Under ARENA_FAST_TEST the collector never touches the network."""
    collector = ForumCollector(client=MagicMock())
    with patch("requests.get") as mock_get:
        assert asyncio.run(collector.collect_async()) == []
        mock_get.assert_not_called()


def test_forum_batch_scored_without_llm_when_offline(monkeypatch):
    """Gateway down: forum events still flow through the keyword fallback
    (no LLM call), and the news path is unaffected."""
    monkeypatch.setenv("ARENA_FAST_TEST", "0")
    mock_client = MagicMock()
    mock_client.is_gateway_online = False
    mock_client._owns_session = False
    mock_client.check_health = AsyncMock(return_value=False)
    mock_client.chat_json = AsyncMock(return_value=None)

    def mock_get(url, headers=None, timeout=None):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        if "stocktwits" in url:
            sym = "ETH.X" if "ETH.X" in url else "BTC.X"
            mock_resp.json.return_value = _stream_json(sym, 500, [f"{sym} surge rally gains", "more"])
            return mock_resp
        mock_resp.text = (
            "<rss><channel><item>"
            f"<title>News {url}</title><link>{url}/n1</link>"
            "<description>desc</description></item></channel></rss>"
        )
        mock_resp.json.side_effect = ValueError("not json")
        return mock_resp

    commander = MacroCommander(mock_client)
    with patch("requests.get", side_effect=mock_get):
        state = asyncio.run(commander.refresh_digest_async())
    mock_client.chat_json.assert_not_called()
    sources = [e.source for e in commander.harvester.recent_structured_events]
    assert any(s.startswith("StockTwits") for s in sources)
    assert state is commander.current_state


def test_process_batch_carries_tier_thread_and_consensus():
    """LLM consensus is parsed and normalized; fields ride through."""
    async def _run():
        mock_client = MagicMock()
        mock_client.is_gateway_online = True
        mock_client.model_ingest = "auto"
        mock_client.chat_json = AsyncMock(return_value={
            "events": [{
                "index": 1,
                "entities_tickers": ["ETH"],
                "urgency_score": 6,
                "sentiment_score": 0.4,
                "headline_zh": "測試標題",
                "summary": "測試摘要內容",
                "consensus": {"bullish": 6, "bearish": 2, "neutral": 2},
            }]
        })
        harvester = IntelligenceHarvester(client=mock_client)
        raw = [RawEvent(
            source="StockTwits ETH.X", domain="forum", title="t", url="https://x/1",
            timestamp=2000.0, tier=2, thread_id="stocktwits:ETH.X",
        )]
        out = await harvester.process_batch(raw)
        assert len(out) == 1
        assert out[0].tier == 2
        assert out[0].thread_id == "stocktwits:ETH.X"
        assert out[0].consensus == {"bullish": 0.6, "bearish": 0.2, "neutral": 0.2}
    asyncio.run(_run())


def test_process_batch_fallback_consensus_from_score():
    """Keyword fallback derives a deterministic consensus split for forum
    threads only; news events get none."""
    async def _run():
        mock_client = MagicMock()
        mock_client.is_gateway_online = False
        mock_client.chat_json = AsyncMock(return_value=None)
        harvester = IntelligenceHarvester(client=mock_client)
        forum = RawEvent(
            source="StockTwits ETH.X", domain="forum",
            title="ETH.X surge rally gains", url="https://x/1",
            timestamp=2000.0, tier=2, thread_id="stocktwits:ETH.X",
        )
        news = RawEvent(
            source="CoinDesk", domain="crypto",
            title="Ethereum surge rally gains", url="https://x/2",
            timestamp=2000.0, tier=2,
        )
        out = await harvester.process_batch([forum, news])
        assert len(out) == 2
        f, n = out
        assert f.consensus == {"bullish": 0.7, "bearish": 0.0, "neutral": 0.3}
        assert n.consensus is None
    asyncio.run(_run())


def test_structured_event_new_fields_default():
    se = StructuredEvent(
        timestamp="2026-11-13T00:00:00Z", source="Test", domain="crypto",
        entities_tickers=["ETH"], urgency_score=5, sentiment_score=0.0,
        summary="s",
    )
    assert se.tier == 2
    assert se.thread_id is None
    assert se.consensus is None
    d = se.to_dict()
    assert d["tier"] == 2
    assert d["thread_id"] is None
    assert d["consensus"] is None
