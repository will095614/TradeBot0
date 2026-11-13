"""Item 12C tests: weighted sentiment (C1) - tier weights, 60-minute
half-life decay, coverage gate, and the C1 direction thresholds."""
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

from src.intelligence.ingestion import StructuredEvent
from src.intelligence.macro_commander import MacroCommander


def _now_iso(age_min: float = 0.0) -> str:
    ts = datetime.now(timezone.utc) - timedelta(minutes=age_min)
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


def _ev(sent, urg, tier=2, age_min=0.0):
    return StructuredEvent(
        timestamp=_now_iso(age_min), source="Test", domain="macro",
        entities_tickers=["ETH"], urgency_score=urg, sentiment_score=sent,
        summary="s", tier=tier,
    )


def _offline_commander():
    mock_client = MagicMock()
    mock_client.is_gateway_online = False
    mock_client.chat_json = AsyncMock(return_value=None)
    return MacroCommander(mock_client)


def test_tier_weight_tier1_outweighs_tier3():
    c = _offline_commander()
    # Same urgency, opposite sentiment: tier 1 (w 1.2) beats tier 3 (w 0.7).
    s, u, n = c.compute_weighted_sentiment([
        _ev(+1.0, 5, tier=1), _ev(-1.0, 5, tier=3),
    ])
    assert abs(s - (1.2 - 0.7) / 1.9) < 0.01
    assert abs(u - 5.0) < 0.01
    assert abs(n - 2.0) < 0.01


def test_half_life_decay_60_min_is_half_weight():
    c = _offline_commander()
    # Fresh +1.0 vs ~60-min-old -1.0: old event weighs about half
    # (decay 0.506 at 59 min, within C4's +-5% of 0.5) -> S ~= 1/3, N ~= 1.5.
    # Exactly 60 min is not used: the event would be > 60.0 min old by
    # evaluation time and fall outside the "last 60 min" window.
    s, u, n = c.compute_weighted_sentiment([
        _ev(+1.0, 5, age_min=0.0), _ev(-1.0, 5, age_min=59.0),
    ])
    assert abs(s - (1.0 / 3.0)) < 0.02
    assert abs(n - 1.5) < 0.02


def test_events_older_than_60_min_excluded():
    c = _offline_commander()
    s, u, n = c.compute_weighted_sentiment([_ev(-1.0, 10, age_min=61.0)])
    assert (s, u, n) == (0.0, 0.0, 0.0)
    assert c.compute_weighted_sentiment([]) == (0.0, 0.0, 0.0)


def test_single_extreme_event_never_flips_direction():
    c = _offline_commander()
    state = asyncio.run(c.synthesize_regime([_ev(-1.0, 10)]))
    assert state.directional_bias == "BIDIRECTIONAL"
    assert state.regime == "NORMAL"
    assert state.weighted_coverage < 2.0


def test_direction_thresholds_long_and_short():
    c = _offline_commander()
    long_state = asyncio.run(c.synthesize_regime([_ev(0.5, 8), _ev(0.5, 8), _ev(0.5, 8)]))
    assert long_state.directional_bias == "LONG_ONLY"
    assert long_state.regime == "BULLISH_SURGE"
    assert abs(long_state.weighted_sentiment - 0.5) < 0.01
    assert abs(long_state.weighted_urgency - 8.0) < 0.01
    assert abs(long_state.weighted_coverage - 3.0) < 0.01
    short_state = asyncio.run(c.synthesize_regime([_ev(-0.5, 8), _ev(-0.5, 8), _ev(-0.5, 8)]))
    assert short_state.directional_bias == "SHORT_ONLY"
    assert short_state.regime == "BEARISH_PANIC"


def test_fallback_never_enters_hold_cash():
    c = _offline_commander()
    # S=-0.7, U=9 would be HOLD_CASH territory, but the keyword fallback
    # has no LLM confidence, so it must stop at SHORT_ONLY.
    # Three events: two fresh ones give N ~= 1.9996 < 2 (C1: N = SUM(decay)).
    state = asyncio.run(c.synthesize_regime([_ev(-0.7, 9), _ev(-0.7, 9), _ev(-0.7, 9)]))
    assert state.directional_bias == "SHORT_ONLY"
    assert state.confidence == 0.50


def test_two_fresh_events_reach_n19():
    # Relaxed C1 gate (2026-11-13): N = SUM(decay) and any nonzero age
    # gives decay < 1, so exactly two fresh events give N ~= 1.9996 --
    # below the literal 2.0 but above the 1.9 gate, so two events
    # suffice to flip. One event (N < 1) still cannot flip the arena.
    c = _offline_commander()
    s, u, n = c.compute_weighted_sentiment([_ev(-0.7, 9), _ev(-0.7, 9)])
    assert abs(s - (-0.7)) < 0.01
    assert abs(u - 9.0) < 0.01
    assert 1.9 < n < 2.0
    state = asyncio.run(c.synthesize_regime([_ev(-0.7, 9), _ev(-0.7, 9)]))
    assert state.directional_bias == "SHORT_ONLY"


def test_llm_hold_cash_with_confidence_passes_through():
    mock_client = MagicMock()
    mock_client.is_gateway_online = True
    mock_client.chat_json = AsyncMock(return_value={
        "regime": "BEARISH_PANIC", "directional_bias": "HOLD_CASH",
        "risk_multiplier": 0.5, "active_headline": "Severe risk-off",
        "confidence": 0.9,
    })
    c = MacroCommander(mock_client)
    state = asyncio.run(c.synthesize_regime([_ev(-0.7, 9), _ev(-0.7, 9)]))
    assert state.directional_bias == "HOLD_CASH"
    assert state.confidence == 0.9


def test_weighted_scores_exposed_in_state_dict():
    c = _offline_commander()
    asyncio.run(c.synthesize_regime([_ev(0.5, 8), _ev(0.5, 8), _ev(0.5, 8)]))
    d = c.current_state.to_dict()
    assert abs(d["weighted_sentiment"] - 0.5) < 0.01
    assert abs(d["weighted_urgency"] - 8.0) < 0.01
    assert abs(d["weighted_coverage"] - 3.0) < 0.01
