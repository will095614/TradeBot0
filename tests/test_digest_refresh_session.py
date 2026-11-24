"""Fix 3b: refresh_digest_async must not close the shared client session.

Regression test for the 2026-11-15 race: the old finally block in
refresh_digest_async closed the OmniRouteClient session after every
digest refresh, while a concurrent lazy-article generation
(get_event_article, bridge thread) was still using it -- the app log
shows "Unexpected error in OmniRouteClient: Session is closed" at
16:52:53/54/59 and 16:56:16, each time killing the in-flight chat_json
and failing the article with the misleading "LLM returned no usable
JSON".

The test uses the REAL OmniRouteClient + REAL MacroCommander with a
fake aiohttp session (no real gateway is ever touched: base_url is
unroutable, and every response comes from the fake). It runs two
consecutive refreshes plus a concurrent article call and asserts the
session was never closed and the article succeeds.
"""
import asyncio
import threading

from src.intelligence.ingestion import StructuredEvent
from src.intelligence.macro_commander import MacroCommander
from src.intelligence.gemini_client import GeminiClient

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

# One response body serves both the digest synthesis and the article
# generation: the digest reads directional_bias/confidence, the
# article reads article.
RESPONSE_CONTENT = (
    '{"directional_bias": "BIDIRECTIONAL", "confidence": 0.5, '
    '"article": "' + ARTICLE_TEXT.replace('"', '\\"') + '"}'
)


class _FakeResp:
    def __init__(self, status=200, json_body=None):
        self.status = status
        self.headers = {}
        self._json_body = json_body

    async def json(self):
        return self._json_body

    async def text(self):
        return ""


class _FakeCM:
    """Async context manager for one fake request.

    The article call sleeps before answering (so the test can land a
    refresh in the middle of it); digest calls answer at once. A
    request that finds the session closed raises exactly like aiohttp
    does ("Session is closed").
    """

    def __init__(self, session, resp, slow):
        self._session = session
        self._resp = resp
        self._slow = slow

    async def __aenter__(self):
        if self._slow:
            await asyncio.sleep(0.3)
        if self._session.closed:
            raise RuntimeError("Session is closed")
        return self._resp

    async def __aexit__(self, *exc):
        return False


class _FakeSession:
    def __init__(self):
        self.closed = False
        self.close_calls = 0

    def _is_article(self, payload):
        try:
            parts = []
            sys_inst = (payload or {}).get("systemInstruction", {})
            for p in sys_inst.get("parts", []):
                if isinstance(p, dict):
                    parts.append(str(p.get("text", "")))
            for item in (payload or {}).get("contents", []):
                if isinstance(item, dict):
                    for p in item.get("parts", []):
                        if isinstance(p, dict):
                            parts.append(str(p.get("text", "")))
            text = " ".join(parts)
        except Exception:
            return False
        return "整理一篇繁體中文文章" in text

    def post(self, url, json=None, headers=None, timeout=None):
        resp = _FakeResp(
            200,
            {
                "candidates": [{"content": {"parts": [{"text": RESPONSE_CONTENT}]}}],
                "usageMetadata": {"totalTokenCount": 10},
            },
        )
        return _FakeCM(self, resp, slow=self._is_article(json))

    def get(self, url, headers=None, timeout=None):
        return _FakeCM(self, _FakeResp(200, {"name": "models/gemini-3.1-flash-lite"}), slow=False)

    async def close(self):
        self.close_calls += 1
        self.closed = True


def _make_commander():
    client = GeminiClient(api_key="test-key")
    session = _FakeSession()
    client._session = session
    client._owns_session = True
    commander = MacroCommander(client)
    commander.harvester = _FakeHarvester()
    commander.forum_collector = _FakeForum()
    return commander, client, session


class _FakeHarvester:
    def fetch_live_feeds(self, *args):
        return [object()]

    async def process_batch(self, raw_events):
        return [StructuredEvent(
            timestamp="2026-11-15T00:00:00Z",
            source="CoinDesk",
            domain="crypto",
            entities_tickers=["BTC"],
            urgency_score=6,
            sentiment_score=0.2,
            summary="測試摘要：比特幣買盤動能轉強。",
            raw_title="BTC rallies on strong inflows",
            headline_zh="比特幣買盤動能轉強",
        )]

    def get_latest_events(self, n):
        return []


class _FakeForum:
    async def collect_async(self):
        return []


def test_two_refreshes_leave_session_open():
    commander, client, session = _make_commander()
    asyncio.run(commander.refresh_digest_async())
    assert session.close_calls == 0
    assert session.closed is False
    asyncio.run(commander.refresh_digest_async())
    assert session.close_calls == 0
    assert session.closed is False
    # The digest path still worked through both refreshes.
    assert commander.curated_events, "refresh must still produce events"


def test_concurrent_article_call_survives_refresh():
    commander, client, session = _make_commander()
    asyncio.run(commander.refresh_digest_async())
    evt_id = commander.curated_events[0]["id"]
    results = []

    def _call_article():
        results.append(commander.get_event_article(evt_id))

    t = threading.Thread(target=_call_article)
    t.start()
    # The article call is now inside its slow fake post; land a full
    # refresh on top of it. The old code closed the session in the
    # refresh finally and the article died with "Session is closed".
    import time
    time.sleep(0.05)
    asyncio.run(commander.refresh_digest_async())
    t.join(timeout=10)
    assert not t.is_alive()
    assert session.close_calls == 0
    assert len(results) == 1
    res = results[0]
    assert res["ok"] is True, "article failed: %s" % res
    assert res["article"] == ARTICLE_TEXT
    assert client.chat_json is not None
