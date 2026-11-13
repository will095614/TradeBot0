"""Item 6 tests: intelligence veto open/close split, keyword word boundaries,
numeric parsing safety, shutdown ownership, honest counters."""
import asyncio
import socket
import subprocess
import sys
import time
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from src.arena.order import OrderSide, PositionSide
from src.data.live_engine import LiveArenaEngine
from src.intelligence.gateway_supervisor import GatewaySupervisor
from src.intelligence.ingestion import (
    IntelligenceHarvester,
    RawEvent,
    StructuredEvent,
    parse_polymarket_events,
    parse_reddit_posts,
)
from src.intelligence.macro_commander import MacroCommander
from src.intelligence.omniroute_client import OmniRouteClient


def _mock_commander(**overrides):
    mock_client = MagicMock()
    mock_client.is_gateway_online = False
    for k, v in overrides.items():
        setattr(mock_client, k, v)
    return MacroCommander(mock_client)


def test_veto_never_blocks_close():
    commander = _mock_commander()
    # HOLD_CASH: closes pass on both sides, no veto counted
    commander.current_state.directional_bias = "HOLD_CASH"
    ok, _ = commander.check_trade_veto(OrderSide.BUY, "Aggressive", is_close=True)
    assert ok is True
    ok, _ = commander.check_trade_veto(OrderSide.SELL, "Conservative", is_close=True)
    assert ok is True
    assert commander.current_state.veto_count_today == 0
    # LONG_ONLY: SELL that closes a long passes; SELL that opens a short is vetoed
    commander.current_state.directional_bias = "LONG_ONLY"
    ok, _ = commander.check_trade_veto(OrderSide.SELL, "Aggressive", is_close=True)
    assert ok is True
    ok, reason = commander.check_trade_veto(OrderSide.SELL, "Aggressive", is_close=False)
    assert ok is False
    assert "VETO_MACRO_LONG_ONLY" in reason
    # SHORT_ONLY: BUY that covers a short passes
    commander.current_state.directional_bias = "SHORT_ONLY"
    ok, _ = commander.check_trade_veto(OrderSide.BUY, "Aggressive", is_close=True)
    assert ok is True
    assert commander.current_state.veto_count_today == 1


def test_close_ticket_bypasses_veto_and_gates_under_hold_cash():
    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    engine.bootstrap_intraday_session()
    engine.macro_commander.current_state.directional_bias = "HOLD_CASH"
    engine.broker.current_price = Decimal("2600.00")
    comp = engine.comp_a
    comp.portfolio.position_qty = Decimal("5")
    comp.portfolio.position_side = PositionSide.LONG
    comp.portfolio.avg_entry_price = Decimal("2500.00")
    closed = engine._enter_via_strategy(comp, Decimal("2600.00"), 2000.0, "TEST_CLOSE", side=OrderSide.SELL, signal="SELL")
    assert closed is True
    assert comp.portfolio.position_qty == Decimal("0")
    engine.stop()


def _fallback_structured(title, domain="crypto", raw_content=""):
    async def _run():
        mock_client = MagicMock()
        mock_client.is_gateway_online = False
        mock_client.chat_json = AsyncMock(return_value=None)
        harvester = IntelligenceHarvester(client=mock_client)
        raw = [RawEvent(source="Test", domain=domain, title=title, url="https://example.com", timestamp=2000.0, raw_content=raw_content)]
        return await harvester.process_batch(raw)
    return asyncio.run(_run())


def test_keyword_word_boundaries_no_substring_false_positives():
    # "bearing" must not count as "bear", "bank" must not count as "ban",
    # "said" must not count as "ai".
    events = _fallback_structured("Bearing maker said outlook bright as bank reports earnings")
    assert len(events) == 1
    se = events[0]
    assert se.sentiment_score == 0.0  # no real bull/bear word
    assert se.urgency_score == 5  # no real urgency word ("ban" in "bank" must not fire)
    assert "AI" not in se.entities_tickers  # "ai" in "said" must not fire

    # "method" must not count as "eth", "separate" must not count as "rate",
    # "second"/"sector" must not count as "sec".
    events = _fallback_structured("Method to separate risk as second sector cools", domain="macro")
    se = events[0]
    assert se.sentiment_score == 0.0
    assert se.urgency_score == 5
    assert "ETH" not in se.entities_tickers
    assert "FED" not in se.entities_tickers
    assert "SEC" not in se.entities_tickers

    # Positive control: real whole-word keywords still fire.
    events = _fallback_structured("Bitcoin crash as exchange hack drains funds")
    se = events[0]
    assert se.sentiment_score == -0.70  # "crash" + "hack" = two bear words
    assert se.urgency_score == 7  # real "hack" word
    assert "BTC" in se.entities_tickers


def test_llm_numeric_parsing_never_raises():
    async def _run():
        mock_client = MagicMock()
        mock_client.is_gateway_online = True
        mock_client.model_commander = "auto"
        mock_client.chat_json = AsyncMock(return_value={
            "regime": "BULLISH_SURGE",
            "directional_bias": "LONG_ONLY",
            "risk_multiplier": "high",
            "confidence": "very sure",
            "active_headline": "Test headline",
        })
        commander = MacroCommander(mock_client)
        events = [StructuredEvent(timestamp="2026-11-13T00:00:00Z", source="Test", domain="crypto", entities_tickers=["ETH"], urgency_score=5, sentiment_score=0.1, summary="Test")]
        state = await commander.synthesize_regime(events)
        assert state.risk_multiplier == 1.0
        assert state.confidence == 0.70
        assert state.regime == "BULLISH_SURGE"
        assert state.directional_bias == "LONG_ONLY"
    asyncio.run(_run())


def test_feed_numeric_parsing_never_raises():
    events = parse_polymarket_events([{"title": "Test event", "volume24hr": "not-a-number", "slug": "test", "markets": []}])
    assert len(events) == 1
    assert "$0" in events[0].title  # volume falls back to 0
    assert parse_reddit_posts({"data": {"children": [{"data": {"title": "Some post", "score": "many", "permalink": "/x"}}]}}, "CryptoCurrency", "crypto") == []


def _free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _wait_port_open(port, timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def test_shutdown_does_not_kill_foreign_process():
    port = _free_port()
    server = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        assert _wait_port_open(port), "test HTTP server did not start"
        supervisor = GatewaySupervisor(port=port)
        assert supervisor.child_process is None
        supervisor.shutdown()
        assert server.poll() is None, "shutdown() killed a process it did not spawn"
        assert _wait_port_open(port), "foreign listener died after shutdown()"
        # The fail-safe helper alone must also leave foreign processes alone.
        supervisor._kill_port_owner(port)
        assert server.poll() is None
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()


def test_shutdown_kills_own_child():
    sleeper = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(120)"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        supervisor = GatewaySupervisor(port=_free_port())
        supervisor.child_process = sleeper
        supervisor.is_self_spawned = True
        supervisor.shutdown()
        assert sleeper.poll() is not None, "shutdown() did not terminate its own child"
        assert supervisor.child_process is None
        assert supervisor.is_self_spawned is False
    finally:
        if sleeper.poll() is None:
            sleeper.kill()


def test_success_counted_only_after_parseable_json():
    async def _run():
        client = OmniRouteClient(base_url="http://mock-omniroute:20128/v1", api_key="test-key")

        # 200 with unparseable content: not a success, but not a failure either.
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.headers = {}
        mock_resp.json = AsyncMock(return_value={"choices": [{"message": {"content": "not json at all"}}]})
        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.post.return_value.__aenter__.return_value = mock_resp
        client._session = mock_session
        client._owns_session = False
        result = await client.chat_json("auto", "system", "user")
        assert result is None
        assert client.successful_requests == 0
        assert client.failed_requests == 0

        # 200 with non-numeric usage + parseable content: parses fine, counts once.
        mock_resp2 = AsyncMock()
        mock_resp2.status = 200
        mock_resp2.headers = {}
        mock_resp2.json = AsyncMock(return_value={
            "usage": {"total_tokens": "many"},
            "choices": [{"message": {"content": '{"regime": "NORMAL"}'}}],
        })
        mock_session.post.return_value.__aenter__.return_value = mock_resp2
        result = await client.chat_json("auto", "system", "user")
        assert result == {"regime": "NORMAL"}
        assert client.successful_requests == 1
        assert client.total_tokens_used == 0
    asyncio.run(_run())


def test_no_fabricated_seed_events_and_honest_quota():
    commander = _mock_commander()
    assert commander.curated_events == []
    assert commander.current_state.latest_event is None
    assert commander.current_state.confidence == 0.50
    commander.record_strategy_action("comp_agg", "AGG", "Opened LONG 5.00 ETH", "buy")
    assert commander.curated_events == []  # no fake event created to attach to

    tel = commander.get_intel_hub_telemetry()
    assert tel["omniroute"]["quota_pct"] is None  # unknown, not fabricated 100.0

    real_client = OmniRouteClient()
    real_commander = MacroCommander(real_client)
    tel2 = real_commander.get_intel_hub_telemetry()
    assert tel2["omniroute"]["quota_pct"] == 100.0  # real client: 0 tokens used of 100000 budget


def test_fallback_thresholds_do_not_veto_on_single_word():
    async def _run():
        mock_client = MagicMock()
        mock_client.is_gateway_online = False
        mock_client.chat_json = AsyncMock(return_value=None)
        commander = MacroCommander(mock_client)
        # One bearish word (sentiment -0.45) + urgency 7 used to flip the
        # arena to SHORT_ONLY; the conservative fallback bar keeps NORMAL.
        weak = StructuredEvent(timestamp="2026-11-13T00:00:00Z", source="Test", domain="macro", entities_tickers=["FED"], urgency_score=7, sentiment_score=-0.45, summary="Weak signal")
        state = await commander.synthesize_regime([weak])
        assert state.directional_bias == "BIDIRECTIONAL"
        assert state.regime == "NORMAL"
        # Two strongly bearish events with severe urgency still flip it.
        strong = [
            StructuredEvent(timestamp="2026-11-13T00:00:00Z", source="Test", domain="macro", entities_tickers=["FED"], urgency_score=9, sentiment_score=-0.70, summary="Strong bearish 1"),
            StructuredEvent(timestamp="2026-11-13T00:00:00Z", source="Test", domain="macro", entities_tickers=["FED"], urgency_score=8, sentiment_score=-0.85, summary="Strong bearish 2"),
        ]
        state = await commander.synthesize_regime(strong)
        assert state.directional_bias == "SHORT_ONLY"
        assert state.regime == "BEARISH_PANIC"
    asyncio.run(_run())
