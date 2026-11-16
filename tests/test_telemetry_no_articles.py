"""V2.8.0: the 1 Hz Intel Hub snapshot must not ship generated articles.

Before the fix get_intel_hub_telemetry returned the curated event dicts by
reference, and get_event_article writes the generated body onto those same
dicts, so every snapshot deep-copied and serialized up to 25 full articles
(measured: 14,817 -> 153,342 chars). The projection below keeps the event
identity/state and drops only the article body, which the UI fetches on
demand through get_event_article.
"""
import json

from src.intelligence.macro_commander import MacroCommander
from src.intelligence.omniroute_client import OmniRouteClient


def _commander_with_expanded_events(count=25):
    commander = MacroCommander(
        OmniRouteClient(base_url="http://127.0.0.1:1/v1", api_key="test-key")
    )
    commander.curated_events.clear()
    bodies = {}
    for i in range(count):
        body = ("情報本文：這是為了量測而產生的長篇文章內容。" * 260) + f"#{i}"
        bodies[f"evt-{i}"] = body
        commander.curated_events.append({
            "id": f"evt-{i}",
            "headline_zh": f"測試標題 {i}",
            "summary": f"測試摘要 {i}",
            "source": "CoinDesk",
            "urgency_score": 6,
            "article_state": "ready",
            "article": body,
        })
    commander.current_state.latest_event = commander.curated_events[0]
    return commander, bodies


def test_snapshot_carries_no_article_bodies():
    commander, bodies = _commander_with_expanded_events()
    snapshot = commander.get_intel_hub_telemetry()
    payload = json.dumps(snapshot, ensure_ascii=False)

    assert len(snapshot["events"]) == 25
    # Identity and article state survive; the body does not.
    assert [e["id"] for e in snapshot["events"]][0] == "evt-0"
    assert all(e["article_state"] == "ready" for e in snapshot["events"])
    assert all("article" not in e and "article_error" not in e for e in snapshot["events"])
    assert "article" not in (snapshot["macro_state"].get("latest_event") or {})
    for body in bodies.values():
        assert body not in payload
    # The pre-fix payload with these 25 events was ~153 KB.
    assert len(payload) < 25_000, len(payload)


def test_on_demand_article_is_intact_after_the_snapshot():
    commander, bodies = _commander_with_expanded_events()
    commander.get_intel_hub_telemetry()
    result = commander.get_event_article("evt-7")

    assert result["ok"] is True, result
    assert result["state"] == "ready"
    assert result["article"] == bodies["evt-7"]
    assert len(result["article"]) > 5_000


def test_article_lock_map_stays_bounded():
    commander, _ = _commander_with_expanded_events(count=5)
    for i in range(400):
        commander._get_article_lock(f"ghost-{i}")

    # Pruning runs before each new lock is created, so the map stays at
    # the threshold instead of growing with the number of requests.
    assert len(commander._article_locks) <= commander._ARTICLE_LOCK_PRUNE_THRESHOLD + 1
    # Still bounded after twice as many requests: growth is capped by the
    # threshold, not by the number of event ids ever seen.
    for i in range(400, 800):
        commander._get_article_lock(f"ghost-{i}")
    assert len(commander._article_locks) <= commander._ARTICLE_LOCK_PRUNE_THRESHOLD + 1
