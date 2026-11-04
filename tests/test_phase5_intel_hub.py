from decimal import Decimal
import time
from unittest.mock import MagicMock
from src.arena.order import OrderSide
from src.data.live_engine import LiveArenaEngine
from src.gui.dashboard import ArenaDashboard, _ArenaBridgeApi
from src.intelligence.macro_commander import MacroCommander


def test_intel_hub_telemetry_structure():
    mock_client = MagicMock()
    mock_client.base_url = "http://localhost:20128/v1"
    mock_client.model_ingest = "auto"
    mock_client.model_commander = "auto"
    mock_client.is_gateway_online = True
    mock_client.total_requests = 10
    mock_client.successful_requests = 10
    mock_client.retried_requests = 0
    mock_client.failed_requests = 0
    mock_client.max_concurrent = 25

    commander = MacroCommander(mock_client)
    tel = commander.get_intel_hub_telemetry()

    assert "omniroute" in tel
    assert tel["omniroute"]["status"] == "ONLINE"
    assert tel["omniroute"]["endpoint"] == "http://localhost:20128/v1"
    assert tel["omniroute"]["quota_pct"] == 100.0
    assert tel["omniroute"]["concurrency_limit"] == 25
    assert "macro_state" in tel
    assert "events" in tel
    assert len(tel["events"]) >= 5


def test_record_strategy_actions_mapped_to_events():
    mock_client = MagicMock()
    mock_client.is_gateway_online = False
    commander = MacroCommander(mock_client)

    # Record action for Strategy 1 (comp_agg)
    commander.record_strategy_action("comp_agg", "AGG", "Opened LONG 0.50 BTC", "buy")
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
    assert state_before["cadence_sec"] == 5.0

    # Call refresh_intel_digest
    res = engine.refresh_intel_digest()
    assert "omniroute" in res
    assert "events" in res
    assert len(res["events"]) > 0

    state_after = engine.get_ui_state()
    assert "intel_hub" in state_after
    assert len(state_after["intel_hub"]["events"]) > 0


def test_arena_bridge_api_refresh_intel():
    dash = ArenaDashboard(initial_cash=Decimal("100000.00"))
    bridge = _ArenaBridgeApi(dash)

    # Ensure refresh_intel_digest is callable via bridge
    new_state = bridge.refresh_intel_digest()
    assert "intel_hub" in new_state
    assert "macro_commander" in new_state
    assert "candles" in new_state

