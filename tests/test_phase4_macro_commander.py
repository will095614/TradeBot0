import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from src.arena.order import OrderSide
from src.data.live_engine import LiveArenaEngine
from src.intelligence.ingestion import StructuredEvent
from src.intelligence.macro_commander import MacroCommander, MacroRegimeState


def test_macro_commander_strict_veto_logic():
    mock_client = MagicMock()
    commander = MacroCommander(mock_client)

    # 1. Normal / Bidirectional regime: all sides pass
    commander.current_state.directional_bias = "BIDIRECTIONAL"
    ok, _ = commander.check_trade_veto(OrderSide.BUY, "Aggressive")
    assert ok is True
    ok, _ = commander.check_trade_veto(OrderSide.SELL, "Conservative")
    assert ok is True
    assert commander.current_state.veto_count_today == 0

    # 2. LONG_ONLY regime (e.g. US election surge): SHORT must be strictly vetoed
    commander.current_state.directional_bias = "LONG_ONLY"
    commander.current_state.active_headline = "Pro-crypto candidate leads; massive surge"
    ok, _ = commander.check_trade_veto(OrderSide.BUY, "Aggressive")
    assert ok is True
    ok, reason = commander.check_trade_veto(OrderSide.SELL, "Conservative")
    assert ok is False
    assert "VETO_MACRO_LONG_ONLY" in reason
    assert commander.current_state.veto_count_today == 1

    # 3. SHORT_ONLY regime (e.g. Black Swan / Regulatory shock): LONG must be strictly vetoed
    commander.current_state.directional_bias = "SHORT_ONLY"
    commander.current_state.active_headline = "Regulatory crackdown initiated"
    ok, reason = commander.check_trade_veto(OrderSide.BUY, "Aggressive")
    assert ok is False
    assert "VETO_MACRO_SHORT_ONLY" in reason
    assert commander.current_state.veto_count_today == 2
    ok, _ = commander.check_trade_veto(OrderSide.SELL, "Aggressive")
    assert ok is True

    # 4. HOLD_CASH regime: All opening orders blocked [R5]
    commander.current_state.directional_bias = "HOLD_CASH"
    ok, reason = commander.check_trade_veto(OrderSide.BUY, "ORB")
    assert ok is False
    assert "VETO_MACRO_HOLD_CASH" in reason
    ok, reason = commander.check_trade_veto(OrderSide.SELL, "VWAP")
    assert ok is False
    assert "VETO_MACRO_HOLD_CASH" in reason
    assert commander.current_state.veto_count_today == 4


def test_macro_commander_synthesis_llm_flow():
    async def _run():
        mock_client = MagicMock()
        mock_client.model_commander = "auto/smart"
        mock_client.is_gateway_online = True
        mock_client.chat_json = AsyncMock(return_value={
            "regime": "BULLISH_SURGE",
            "directional_bias": "LONG_ONLY",
            "risk_multiplier": 1.4,
            "active_headline": "US Election: Crypto-friendly policy momentum triggers historic inflows",
            "confidence": 0.95,
        })

        commander = MacroCommander(mock_client)
        events = [
            StructuredEvent(
                timestamp="2026-11-04T12:00:00Z",
                source="TreeNews",
                domain="politics",
                entities_tickers=["BTC"],
                urgency_score=9,
                sentiment_score=0.90,
                summary="Election results reveal massive pro-crypto majority",
            )
        ]

        state = await commander.synthesize_regime(events)
        assert state.regime == "BULLISH_SURGE"
        assert state.directional_bias == "LONG_ONLY"
        assert state.risk_multiplier == 1.4
        assert state.confidence == 0.95
        assert state.status == "ONLINE"
        assert state.total_evaluations == 1

    asyncio.run(_run())


def test_live_engine_enforces_macro_commander_veto():
    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    engine.bootstrap_intraday_session()

    # Verify macro_commander is exposed in UI state
    ui_state = engine.get_ui_state()
    assert "macro_commander" in ui_state
    assert ui_state["macro_commander"]["status"] in {"ONLINE", "STANDBY"}

    # Simulate setting Macro Commander to LONG_ONLY
    engine.macro_commander.current_state.directional_bias = "LONG_ONLY"
    engine.macro_commander.current_state.active_headline = "US Presidential Election: Historic Crypto Surge"

    # Attempt to execute a SHORT bracket order for any of the 6 competitors
    for comp in engine.competitors:
        vetoed = engine._try_enter_bracket(
            competitor=comp,
            price=Decimal("100000.00"),
            sl=Decimal("101000.00"),
            tp=Decimal("98000.00"),
            ts=1700000000.0,
            event_label="TEST_SHORT",
            side=OrderSide.SELL
        )
        # All competitors attempting SHORT must be strictly vetoed!
        assert vetoed is False

    # Check that veto logs were created
    veto_logs = [l for l in engine.live_logs if l["tag"] == "VETO_MACRO"]
    assert len(veto_logs) == 6
    assert engine.macro_commander.current_state.veto_count_today == 6

