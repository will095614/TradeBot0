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

