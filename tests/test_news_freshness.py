"""Regression tests for real feed timestamp parsing, staleness filtering, and newest-first ranking."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
import time
from unittest.mock import AsyncMock, MagicMock, patch

from src.intelligence.ingestion import (
    IntelligenceHarvester,
    RawEvent,
    StructuredEvent,
    _rank_fresh_events,
    parse_rss_atom,
)
from src.intelligence.macro_commander import MacroCommander


def test_parse_rss_atom_extracts_real_pubdate_and_atom_updated():
    now_dt = datetime.now(timezone.utc).replace(microsecond=0)
    rss_dt = now_dt - timedelta(hours=3)
    dc_dt = now_dt - timedelta(hours=7)
    future_dt = now_dt + timedelta(hours=5)

    rss_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
        <channel>
            <title>Wire</title>
            <item>
                <title>RFC2822 Item</title>
                <link>https://example.com/1</link>
                <pubDate>{format_datetime(rss_dt, usegmt=True)}</pubDate>
            </item>
            <item>
                <title>DC Date Item</title>
                <link>https://example.com/2</link>
                <dc:date>{dc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")}</dc:date>
            </item>
            <item>
                <title>Future Skewed Item</title>
                <link>https://example.com/3</link>
                <pubDate>{format_datetime(future_dt, usegmt=True)}</pubDate>
            </item>
            <item>
                <title>Undated Item</title>
                <link>https://example.com/4</link>
            </item>
        </channel>
    </rss>
    """
    before = time.time()
    rss_events = parse_rss_atom(rss_xml, "Wire", "crypto")
    after = time.time()

    assert len(rss_events) == 4
    assert abs(rss_events[0].timestamp - rss_dt.timestamp()) < 2.0
    assert rss_events[0].published_at == rss_events[0].timestamp
    assert abs(rss_events[1].timestamp - dc_dt.timestamp()) < 2.0
    assert rss_events[1].published_at == rss_events[1].timestamp
    assert before - 5.0 <= rss_events[2].timestamp <= after + 5.0
    assert rss_events[2].published_at is not None and rss_events[2].published_at <= after + 5.0
    assert before <= rss_events[3].timestamp <= after
    assert rss_events[3].published_at is None

    pub_dt = now_dt - timedelta(minutes=25)
    upd_dt = now_dt - timedelta(minutes=75)
    atom_xml = f"""<?xml version="1.0" encoding="utf-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
        <entry>
            <title>Atom Published Entry</title>
            <link href="https://example.com/a1"/>
            <published>{pub_dt.strftime("%Y-%m-%dT%H:%M:%SZ")}</published>
            <updated>{upd_dt.strftime("%Y-%m-%dT%H:%M:%SZ")}</updated>
        </entry>
        <entry>
            <title>Atom Updated Only</title>
            <link href="https://example.com/a2"/>
            <updated>{upd_dt.strftime("%Y-%m-%dT%H:%M:%SZ")}</updated>
        </entry>
    </feed>
    """
    atom_events = parse_rss_atom(atom_xml, "AtomWire", "macro")
    assert len(atom_events) == 2
    assert abs(atom_events[0].timestamp - pub_dt.timestamp()) < 2.0
    assert abs(atom_events[1].timestamp - upd_dt.timestamp()) < 2.0


def test_fetch_from_registry_filters_stale_articles_and_sorts_newest_first():
    now_dt = datetime.now(timezone.utc).replace(microsecond=0)
    dt_year_old = now_dt - timedelta(days=365)
    dt_20h = now_dt - timedelta(hours=20)
    dt_30m = now_dt - timedelta(minutes=30)
    dt_10m = now_dt - timedelta(minutes=10)

    def _mock_get(url, headers=None, timeout=None):
        resp = MagicMock()
        resp.status_code = 200
        if "tomshardware.com" in url:
            resp.text = (
                "<rss><channel><item><title>Ancient 2025 Post</title><link>https://toms/old</link>"
                f"<pubDate>{format_datetime(dt_year_old, usegmt=True)}</pubDate></item></channel></rss>"
            )
            return resp
        if "twz.com" in url:
            resp.text = (
                "<rss><channel><item><title>Yesterday War Zone</title><link>https://twz/20h</link>"
                f"<pubDate>{format_datetime(dt_20h, usegmt=True)}</pubDate></item></channel></rss>"
            )
            return resp
        if "coindesk.com" in url:
            resp.text = (
                "<rss><channel><item><title>CoinDesk 10m Ago</title><link>https://cd/10m</link>"
                f"<pubDate>{format_datetime(dt_10m, usegmt=True)}</pubDate></item></channel></rss>"
            )
            return resp
        if "theblock.co" in url:
            resp.text = (
                "<rss><channel><item><title>The Block 30m Ago</title><link>https://tb/30m</link>"
                f"<pubDate>{format_datetime(dt_30m, usegmt=True)}</pubDate></item></channel></rss>"
            )
            return resp
        resp.status_code = 404
        resp.text = ""
        return resp

    harvester = IntelligenceHarvester(client=MagicMock())
    with patch("requests.get", side_effect=_mock_get):
        events = harvester.fetch_from_registry(max_age_hours=48.0)

    titles = [e.title for e in events]
    assert "Ancient 2025 Post" not in titles
    assert titles == ["CoinDesk 10m Ago", "The Block 30m Ago", "Yesterday War Zone"]


def test_rank_fresh_events_caps_single_source_flooding_per_batch():
    now = time.time()
    burst = [
        RawEvent(
            source="BurstWire",
            domain="macro",
            title=f"Burst {i}",
            url=f"https://burst/{i}",
            timestamp=now - 60.0 - i,
            published_at=now - 60.0 - i,
        )
        for i in range(5)
    ]
    others = [
        RawEvent(
            source=f"Wire-{i}",
            domain="crypto",
            title=f"Other {i}",
            url=f"https://other/{i}",
            timestamp=now - 120.0 - i * 30.0,
            published_at=now - 120.0 - i * 30.0,
        )
        for i in range(4)
    ]

    ranked = _rank_fresh_events(burst + others, fetch_now=now, page_size=6, max_per_source_per_page=2)
    assert len(ranked) == 9
    first_page = ranked[:6]
    assert sum(1 for e in first_page if e.source == "BurstWire") == 2
    assert {e.source for e in first_page} == {"BurstWire", "Wire-0", "Wire-1", "Wire-2", "Wire-3"}


def test_macro_commander_curated_events_uses_real_publish_time_and_sorts():
    async def _run():
        mock_client = MagicMock()
        mock_client.is_gateway_online = True
        mock_client.model_commander = "auto/smart"
        mock_client.chat_json = AsyncMock(return_value={
            "regime": "NORMAL",
            "directional_bias": "BIDIRECTIONAL",
            "risk_multiplier": 1.0,
            "active_headline": "市場觀望宏觀數據",
            "confidence": 0.72,
        })
        commander = MacroCommander(mock_client)

        now_dt = datetime.now(timezone.utc).replace(microsecond=0)
        recent_dt = now_dt - timedelta(minutes=15)
        yesterday_dt = now_dt - timedelta(hours=26)

        ev_old = StructuredEvent(
            timestamp=yesterday_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            source="War Zone",
            domain="geopolitics",
            entities_tickers=["MACRO"],
            urgency_score=5,
            sentiment_score=0.0,
            summary="昨日地緣快訊摘要",
            raw_title="Yesterday Story",
            headline_zh="昨日地緣快訊",
        )
        ev_new = StructuredEvent(
            timestamp=recent_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            source="CoinDesk Live",
            domain="crypto",
            entities_tickers=["ETH"],
            urgency_score=6,
            sentiment_score=0.4,
            summary="今日以太坊快訊摘要",
            raw_title="Fresh ETH Story",
            headline_zh="今日以太坊快訊",
        )

        # Pass old first intentionally; commander must store curated_events newest-first
        await commander.synthesize_regime([ev_old, ev_new])
        assert len(commander.curated_events) == 2

        top, second = commander.curated_events[0], commander.curated_events[1]
        assert top["raw_title"] == "Fresh ETH Story"
        assert second["raw_title"] == "Yesterday Story"
        assert abs(top["event_ts"] - int(recent_dt.timestamp())) <= 2
        assert abs(second["event_ts"] - int(yesterday_dt.timestamp())) <= 2

        recent_local = time.localtime(recent_dt.timestamp())
        now_local = time.localtime()
        expected_top_time = (
            time.strftime("%H:%M:%S", recent_local)
            if (recent_local.tm_year, recent_local.tm_yday) == (now_local.tm_year, now_local.tm_yday)
            else time.strftime("%m-%d %H:%M", recent_local)
        )
        assert top["time"] == expected_top_time
        assert second["time"] == time.strftime("%m-%d %H:%M", time.localtime(yesterday_dt.timestamp()))
        assert second["date_time"] == time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(yesterday_dt.timestamp()))

    asyncio.run(_run())
