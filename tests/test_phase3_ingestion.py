import asyncio
from unittest.mock import AsyncMock, MagicMock
from src.intelligence.ingestion import (
    DeduplicationBuffer,
    RawEvent,
    StructuredEvent,
    IntelligenceHarvester,
    parse_rss_atom,
    parse_polymarket_events,
    parse_reddit_posts,
)


def test_deduplication_buffer():
    buf = DeduplicationBuffer(capacity=3)
    assert buf.is_new("Bitcoin Breaks 100k", "https://news.com/1") is True
    # Identical title and url should be rejected
    assert buf.is_new("Bitcoin Breaks 100k", "https://news.com/1") is False
    # Case insensitive
    assert buf.is_new("bitcoin breaks 100k", "https://news.com/1") is False

    assert buf.is_new("Ethereum ETF Approved", "https://news.com/2") is True
    assert buf.is_new("Fed Cuts Rates 50bps", "https://news.com/3") is True
    assert len(buf) == 3

    # Pushing 4th item should evict 1st item (capacity=3)
    assert buf.is_new("US Election Surge", "https://news.com/4") is True
    assert len(buf) == 3
    # 1st item is now forgotten and can be added again
    assert buf.is_new("Bitcoin Breaks 100k", "https://news.com/1") is True


def test_parse_rss_20():
    sample_rss = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
        <channel>
            <title>Crypto News</title>
            <item>
                <title>Pro-Crypto Candidate Takes Lead in Key Swing States</title>
                <link>https://coindesk.com/election-update</link>
                <description>Bitcoin surges towards new all time high as markets react.</description>
            </item>
        </channel>
    </rss>
    """
    events = parse_rss_atom(sample_rss, "CoinDesk", "crypto")
    assert len(events) == 1
    assert events[0].title == "Pro-Crypto Candidate Takes Lead in Key Swing States"
    assert events[0].url == "https://coindesk.com/election-update"
    assert events[0].source == "CoinDesk"
    assert events[0].domain == "crypto"


def test_parse_atom():
    sample_atom = """<?xml version="1.0" encoding="utf-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
        <title>SEC 8-K Feed</title>
        <entry>
            <title>8-K: MicroStrategy Purchases Additional 25,000 BTC</title>
            <link href="https://sec.gov/edgar/data/12345/8k"/>
        </entry>
    </feed>
    """
    events = parse_rss_atom(sample_atom, "SEC EDGAR", "corporate")
    assert len(events) == 1
    assert "MicroStrategy" in events[0].title
    assert "https://sec.gov" in events[0].url


def test_parse_polymarket():
    sample_data = [
        {
            "title": "US Presidential Election Winner 2024",
            "volume24hr": 45000000.0,
            "slug": "us-presidential-election-2024",
            "markets": [{
                "outcomes": ["Candidate A", "Candidate B"],
                "outcomePrices": ["0.68", "0.32"]
            }]
        }
    ]
    events = parse_polymarket_events(sample_data)
    assert len(events) == 1
    assert "US Presidential Election Winner 2024" in events[0].title
    assert "Candidate A: 68%" in events[0].title
    assert "Candidate B: 32%" in events[0].title


def test_parse_reddit():
    sample_reddit = {
        "data": {
            "children": [
                {
                    "data": {
                        "title": "Institutional inflows into BTC reach record high",
                        "score": 420,
                        "permalink": "/r/CryptoCurrency/comments/123/institutional_inflows/"
                    }
                },
                {
                    "data": {
                        "title": "Spam post with low engagement",
                        "score": 1,
                        "permalink": "/r/CryptoCurrency/comments/124/spam/"
                    }
                }
            ]
        }
    }
    events = parse_reddit_posts(sample_reddit, "CryptoCurrency", "crypto")
    assert len(events) == 1
    assert "Institutional inflows" in events[0].title
    assert "↑420" in events[0].title


def test_harvester_stage1_processing_and_urgent_interrupt():
    async def _run():
        mock_client = MagicMock()
        mock_client.model_ingest = "auto/fast"
        mock_client.chat_json = AsyncMock(return_value={
            "events": [
                {
                    "index": 1,
                    "entities_tickers": ["BTC", "USA"],
                    "urgency_score": 9,
                    "sentiment_score": 0.95,
                    "summary": "Pro-crypto victory confirmed; massive institutional breakout imminent"
                }
            ]
        })

        urgent_called = []

        async def _on_urgent(event: StructuredEvent):
            urgent_called.append(event)

        harvester = IntelligenceHarvester(
            client=mock_client,
            on_urgent_interrupt=_on_urgent
        )

        raw = [
            RawEvent(
                source="TreeNews",
                domain="politics",
                title="BREAKING: Election Results Declare Victory for Pro-Crypto Candidate",
                url="https://news.treeofalpha.com/breaking",
                timestamp=1700000000.0
            )
        ]

        structured = await harvester.process_batch(raw)
        assert len(structured) == 1
        assert structured[0].urgency_score == 9
        assert structured[0].sentiment_score == 0.95
        assert "BTC" in structured[0].entities_tickers

        # Allow event loop task for _on_urgent to execute
        await asyncio.sleep(0.05)
        assert len(urgent_called) == 1
        assert urgent_called[0].urgency_score == 9

    asyncio.run(_run())


def test_feed_registry_completeness_r3():
    """
    [R3 Checkpoint] Assert that the feed registry covers all live no-login
    domains: Semiconductor/AI, Geopolitics/Defense/Maritime, Crypto, Macro/CBs,
    Prediction markets, and SEC corporate filings.
    """
    from src.intelligence.ingestion import FEED_REGISTRY
    ids = {f["id"] for f in FEED_REGISTRY}

    # Semiconductor / AI Supply Chain
    assert {"tomshardware_ai", "trendforce", "digitimes", "technews_tw"}.issubset(ids)

    # Geopolitics / Defense / Maritime
    assert {"aljazeera_world", "breaking_defense", "war_zone", "gcaptain"}.issubset(ids)

    # Crypto & Forum
    assert {"theblock_wire", "coindesk_wire", "cointelegraph_wire", "decrypt_wire"}.issubset(ids)
    assert {"stocktwits_ethx", "stocktwits_btcx"}.issubset(ids)

    # Macro / Central Banks / Prediction / Corporate
    assert {"forexlive", "fxstreet_wire", "ecb_press", "fred_releases", "fed_press_releases"}.issubset(ids)
    assert {"polymarket_gamma", "sec_edgar_8k"}.issubset(ids)


def test_stage2_interrupt_debouncing_r4():
    """
    [R4 Checkpoint] Simulate consecutive high-urgency events (urgency >= 8)
    within the cooldown window. Verify anti-interrupt storm debouncing.
    """
    async def _run():
        from src.intelligence.ingestion import InterruptDebouncer, StructuredEvent

        dispatched_batches = []

        async def _mock_dispatch(events):
            dispatched_batches.append(events)

        # 0.2s fast cooldown for test
        debouncer = InterruptDebouncer(_mock_dispatch, cooldown_sec=0.2)

        ev1 = StructuredEvent("ts", "s1", "m", ["BTC"], 9, 0.8, "Event 1")
        ev2 = StructuredEvent("ts", "s2", "m", ["BTC"], 8, 0.7, "Event 2")
        ev3 = StructuredEvent("ts", "s3", "m", ["BTC"], 9, 0.9, "Event 3")

        # First trigger outside active window: dispatches ev1 immediately
        await debouncer.trigger(ev1)
        await asyncio.sleep(0.02)
        assert len(dispatched_batches) == 1
        assert len(dispatched_batches[0]) == 1
        assert dispatched_batches[0][0].summary == "Event 1"

        # Rapid arrivals inside cooldown window: queued
        await debouncer.trigger(ev2)
        await debouncer.trigger(ev3)
        # Should not have dispatched yet
        assert len(dispatched_batches) == 1

        # Wait for cooldown to expire
        await asyncio.sleep(0.25)
        # Merged batched call executed
        assert len(dispatched_batches) == 2
        assert len(dispatched_batches[1]) == 2
        assert dispatched_batches[1][0].summary == "Event 2"
        assert dispatched_batches[1][1].summary == "Event 3"

    asyncio.run(_run())

# ---------------------------------------------------------------------------
# fetch_from_registry: real HTTP payloads, mocked transport (P0C)
# ---------------------------------------------------------------------------
from datetime import datetime, timezone
from email.utils import format_datetime
import time

import requests
from unittest.mock import patch


def _rss_and_atom_payloads(now: float):
    t_cd1 = datetime.fromtimestamp(int(now) - 600, tz=timezone.utc)
    t_cd2 = datetime.fromtimestamp(int(now) - 2400, tz=timezone.utc)
    t_sec = datetime.fromtimestamp(int(now) - 5400, tz=timezone.utc)
    coindesk_rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
    <channel>
        <title>CoinDesk</title>
        <item>
            <title>Bitcoin ETF Sees Record Inflows as ETH Rallies</title>
            <link>https://www.coindesk.com/markets/2026/11/13/bitcoin-etf-inflows</link>
            <description>Spot bitcoin ETFs drew record inflows while ether climbed past key resistance.</description>
            <pubDate>{format_datetime(t_cd1, usegmt=True)}</pubDate>
        </item>
        <item>
            <title>Ethereum Upgrade Scheduled for December</title>
            <link>https://www.coindesk.com/tech/2026/11/13/ethereum-upgrade-december</link>
            <description>Developers confirm the next network upgrade date.</description>
            <pubDate>{format_datetime(t_cd2, usegmt=True)}</pubDate>
        </item>
    </channel>
</rss>
"""
    sec_atom = f"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
    <title>SEC 8-K Feed</title>
    <entry>
        <title>8-K: MicroStrategy Purchases Additional 25,000 BTC</title>
        <link href="https://www.sec.gov/edgar/data/12345/8k-20261113.htm"/>
        <summary>Registrant reports acquisition of additional bitcoin.</summary>
        <updated>{t_sec.strftime("%Y-%m-%dT%H:%M:%SZ")}</updated>
    </entry>
</feed>
"""
    return coindesk_rss, sec_atom, t_cd1.timestamp(), t_cd2.timestamp(), t_sec.timestamp()

_POLYMARKET_JSON = [
    {
        "title": "Fed Rate Decision December 2026",
        "volume24hr": 1250000.0,
        "slug": "fed-rate-decision-december-2026",
        "markets": [{
            "outcomes": ["25bps cut", "No change"],
            "outcomePrices": ["0.62", "0.38"],
        }],
    }
]


def _fake_registry_response(status_code=200, text="", json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    resp.json = MagicMock(return_value=json_data)
    return resp


def _registry_get_ok(url, headers=None, timeout=None, now=None):
    ref_now = time.time() if now is None else now
    coindesk_rss, sec_atom, *_ = _rss_and_atom_payloads(ref_now)
    if "coindesk.com" in url:
        return _fake_registry_response(text=coindesk_rss)
    if "sec.gov" in url:
        return _fake_registry_response(text=sec_atom)
    if "gamma-api.polymarket.com" in url:
        return _fake_registry_response(text="{}", json_data=_POLYMARKET_JSON)
    return _fake_registry_response(status_code=404, text="not found")


def _new_harvester():
    return IntelligenceHarvester(client=MagicMock())


def test_fetch_from_registry_parses_real_rss_xml():
    """RSS (CoinDesk x2) + Atom (SEC x1) + Polymarket JSON (x1) via mocked
    requests.get: titles/urls/tier/domain/timestamps and newest-first order."""
    from src.intelligence.ingestion import FEED_REGISTRY

    harvester = _new_harvester()
    requested = []
    ref_now = time.time()
    _, _, ts_cd1, ts_cd2, ts_sec = _rss_and_atom_payloads(ref_now)

    def _recording_get(url, headers=None, timeout=None):
        requested.append(url)
        return _registry_get_ok(url, headers=headers, timeout=timeout, now=ref_now)

    before = time.time()
    with patch("requests.get", side_effect=_recording_get):
        events = harvester.fetch_from_registry()
    after = time.time()

    assert len(events) == 4
    # Undated Polymarket snapshot ranks with fetch_now, then real publish dates newest-first.
    poly, cd1, cd2, sec = events
    assert poly.source == "Polymarket" and poly.domain == "prediction" and poly.tier == 1
    assert poly.published_at is None
    assert before <= poly.timestamp <= after
    assert "Fed Rate Decision December 2026" in poly.title
    assert "[Polymarket 24h Vol $1,250,000]" in poly.title
    assert "25bps cut: 62%" in poly.title and "No change: 38%" in poly.title
    assert poly.url == "https://polymarket.com/event/fed-rate-decision-december-2026"

    assert cd1.source == "CoinDesk Live" and cd1.domain == "crypto" and cd1.tier == 2
    assert cd1.title == "Bitcoin ETF Sees Record Inflows as ETH Rallies"
    assert cd1.url == "https://www.coindesk.com/markets/2026/11/13/bitcoin-etf-inflows"
    assert "Spot bitcoin ETFs drew record inflows" in cd1.raw_content
    assert abs(cd1.timestamp - ts_cd1) < 2.0 and cd1.published_at == cd1.timestamp
    assert cd2.title == "Ethereum Upgrade Scheduled for December"
    assert cd2.url == "https://www.coindesk.com/tech/2026/11/13/ethereum-upgrade-december"
    assert abs(cd2.timestamp - ts_cd2) < 2.0 and cd2.published_at == cd2.timestamp

    assert sec.source == "SEC EDGAR 8-K" and sec.domain == "corporate" and sec.tier == 1
    assert "MicroStrategy" in sec.title
    assert sec.url == "https://www.sec.gov/edgar/data/12345/8k-20261113.htm"
    assert "acquisition of additional bitcoin" in sec.raw_content
    assert abs(sec.timestamp - ts_sec) < 2.0 and sec.published_at == sec.timestamp

    # Every non-stocktwits registry entry was attempted; stocktwits never was.
    fetchable_count = sum(1 for e in FEED_REGISTRY if e.get("type") != "stocktwits")
    assert len(requested) == fetchable_count == 19
    assert not any("stocktwits.com" in u for u in requested)

    # Same payloads again: dedup buffer yields nothing new.
    with patch("requests.get", side_effect=lambda u, headers=None, timeout=None: _registry_get_ok(u, headers, timeout, now=ref_now)):
        assert harvester.fetch_from_registry() == []


def test_fetch_from_registry_skips_bad_sources():
    """Non-200 / timeout / corrupt XML sources are skipped; the healthy
    Polymarket source still delivers."""
    requested = []

    def _bad_get(url, headers=None, timeout=None):
        requested.append(url)
        if "coindesk.com" in url:
            return _fake_registry_response(status_code=500, text="server error")
        if "sec.gov" in url:
            raise requests.exceptions.ConnectTimeout("timed out")
        if "forexlive.com" in url:
            return _fake_registry_response(text="this is not xml <<< garbage")
        if "gamma-api.polymarket.com" in url:
            return _fake_registry_response(text="{}", json_data=_POLYMARKET_JSON)
        return _fake_registry_response(status_code=404, text="not found")

    harvester = _new_harvester()
    with patch("requests.get", side_effect=_bad_get):
        events = harvester.fetch_from_registry()

    assert len(events) == 1
    assert events[0].source == "Polymarket"
    # The bad sources were actually attempted (not silently unvisited).
    assert any("coindesk.com" in u for u in requested)
    assert any("sec.gov" in u for u in requested)
    assert any("forexlive.com" in u for u in requested)


def test_fetch_from_registry_skips_stocktwits_entries():
    """Registry stocktwits entries are forum-owned: news fetch never calls
    their URLs, so the same stream is never scored twice per digest."""
    from src.intelligence.ingestion import FEED_REGISTRY

    stocktwits_ids = [e["id"] for e in FEED_REGISTRY if e.get("type") == "stocktwits"]
    assert len(stocktwits_ids) == 2  # guard: the skip is exercised, not vacuous

    requested = []

    def _recording_get(url, headers=None, timeout=None):
        requested.append(url)
        return _fake_registry_response(status_code=404, text="not found")

    harvester = _new_harvester()
    with patch("requests.get", side_effect=_recording_get):
        events = harvester.fetch_from_registry()

    assert events == []
    assert not any("stocktwits.com" in u for u in requested)
    assert len(requested) == len(FEED_REGISTRY) - len(stocktwits_ids)

