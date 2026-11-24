from decimal import Decimal
import time
from unittest.mock import MagicMock
from src.arena.order import OrderSide
from src.data.live_engine import LiveArenaEngine
from src.gui.dashboard import ArenaDashboard, _ArenaBridgeApi
from src.intelligence.macro_commander import MacroCommander


def test_intel_hub_telemetry_structure():
    mock_client = MagicMock()
    mock_client.base_url = "https://generativelanguage.googleapis.com/v1beta"
    mock_client.model_ingest = "gemini-3.1-flash-lite"
    mock_client.model_commander = "gemini-3.1-flash-lite"
    mock_client.is_gateway_online = True
    mock_client.total_requests = 10
    mock_client.successful_requests = 10
    mock_client.retried_requests = 0
    mock_client.failed_requests = 0
    mock_client.max_concurrent = 25

    commander = MacroCommander(mock_client)
    tel = commander.get_intel_hub_telemetry()

    assert "ai" in tel
    assert tel["ai"]["status"] == "ONLINE"
    assert tel["ai"]["endpoint"] == "https://generativelanguage.googleapis.com/v1beta"
    assert tel["ai"]["quota_pct"] is None  # mock client reports no usable quota: unknown, not fabricated 100.0 (item 6)
    assert tel["ai"]["concurrency_limit"] == 25
    assert "macro_state" in tel
    assert "events" in tel
    assert tel["events"] == []  # no fabricated seed events at construction (item 6)


def test_record_strategy_actions_mapped_to_events():
    import asyncio
    from unittest.mock import AsyncMock
    from src.intelligence.ingestion import StructuredEvent

    mock_client = MagicMock()
    mock_client.is_gateway_online = False
    mock_client.chat_json = AsyncMock(return_value=None)
    commander = MacroCommander(mock_client)

    # Actions annotate the latest REAL event: synthesize one first (the
    # old test relied on fabricated seed events, removed in item 6).
    asyncio.run(commander.synthesize_regime([
        StructuredEvent(
            timestamp="2026-11-13T00:00:00Z",
            source="CoinDesk",
            domain="crypto",
            entities_tickers=["ETH"],
            urgency_score=5,
            sentiment_score=0.1,
            summary="Test event for strategy action mapping",
        )
    ]))

    # Record action for Strategy 1 (comp_agg)
    commander.record_strategy_action("comp_agg", "AGG", "Opened LONG 5.00 ETH", "buy")
    # Record veto for Strategy 2 (comp_cons)
    commander.record_strategy_action("comp_cons", "CONS", "SHORT Vetoed by Macro Commander", "loss")

    events = commander.get_intel_hub_telemetry()["events"]
    assert len(events) > 0
    active_evt = events[0]
    actions = active_evt["strategy_actions"]
    assert any(a["name"] == "Strategy 1 (AGG)" and "LONG" in a["action"] for a in actions)
    assert any(a["name"] == "Strategy 2 (CONS)" and "Vetoed" in a["action"] for a in actions)


def test_live_engine_refresh_intel_digest():
    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    engine.bootstrap_intraday_session()

    state_before = engine.get_ui_state()
    assert "intel_hub" in state_before
    assert state_before["cadence_sec"] == 1.0

    # Call refresh_intel_digest
    res = engine.refresh_intel_digest()
    assert "ai" in res
    assert "events" in res
    assert len(res["events"]) > 0

    state_after = engine.get_ui_state()
    assert "intel_hub" in state_after
    assert len(state_after["intel_hub"]["events"]) > 0
    engine.stop()


def test_arena_bridge_api_refresh_intel():
    dash = ArenaDashboard(initial_cash=Decimal("100000.00"))
    bridge = _ArenaBridgeApi(dash)

    # Ensure refresh_intel_digest is callable via bridge
    new_state = bridge.refresh_intel_digest()
    assert "intel_hub" in new_state
    assert "macro_commander" in new_state
    assert "candles" in new_state
    dash.engine.stop()

