#!/usr/bin/env python3
"""Fix patch 1 for item 12C (post-pytest: 4 failures, all one boundary).

Root cause (design C1, literal formula): N = SUM(decay). Any event of
nonzero age has decay < 1, so TWO fresh events give N ~= 1.9996, never
quite reaching the N >= 2 gate -- direction can never flip on exactly
two events. The design's own C4 direction examples use N = 3, and the
half-life example (C4: "60 分鐘前的事件權重約為當下的一半") sits on the
window edge: an event stamped exactly 60 min ago is always > 60.0 min
old when evaluated, so it is excluded by the "last 60 min" filter.

Fix (implementation kept literal to the approved design; fixtures
updated, behaviour flagged in the report):
  - direction fixtures use 3 events (N ~= 3);
  - half-life test uses a 59-min-old event (decay 0.506, within C4's
    +-5% of 0.5) instead of exactly 60 min;
  - a new test pins the 2-event boundary behaviour so it is deliberate,
    not an accident.

Same verify-then-apply pattern as fix_item12c_patch.py.
Run from the project root (PC: C:\\Users\\will0\\TradeBot0, local audit
copy: ~/workspace/tradebot_audit/src).
"""
import os
import sys

REPLACEMENTS = []
NEW_FILES = {}


def rep(path, old, new):
    REPLACEMENTS.append((path, old, new))


# =========================================================== 1. 12A helper: 3 events
rep("tests/test_item12a_omniroute.py", '''def _strong_bearish_events():
    return [
        StructuredEvent(timestamp=_now_iso(), source="Test", domain="macro", entities_tickers=["FED"], urgency_score=9, sentiment_score=-0.70, summary="Strong bearish 1"),
        StructuredEvent(timestamp=_now_iso(), source="Test", domain="macro", entities_tickers=["FED"], urgency_score=8, sentiment_score=-0.85, summary="Strong bearish 2"),
    ]''',
'''def _strong_bearish_events():
    # Three events, not two: C1 defines N = SUM(decay), so two fresh
    # events give N ~= 1.9996 and never reach the N >= 2 direction gate.
    return [
        StructuredEvent(timestamp=_now_iso(), source="Test", domain="macro", entities_tickers=["FED"], urgency_score=9, sentiment_score=-0.70, summary="Strong bearish 1"),
        StructuredEvent(timestamp=_now_iso(), source="Test", domain="macro", entities_tickers=["FED"], urgency_score=8, sentiment_score=-0.85, summary="Strong bearish 2"),
        StructuredEvent(timestamp=_now_iso(), source="Test", domain="macro", entities_tickers=["FED"], urgency_score=9, sentiment_score=-0.80, summary="Strong bearish 3"),
    ]''')

# =========================================================== 2. intel_veto threshold test: 3 events
rep("tests/test_intel_veto.py", '''        # Two strongly bearish events with severe urgency still flip it.
        strong = [
            StructuredEvent(timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), source="Test", domain="macro", entities_tickers=["FED"], urgency_score=9, sentiment_score=-0.70, summary="Strong bearish 1"),
            StructuredEvent(timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), source="Test", domain="macro", entities_tickers=["FED"], urgency_score=8, sentiment_score=-0.85, summary="Strong bearish 2"),
        ]''',
'''        # Three strongly bearish events with severe urgency still flip it
        # (two are not enough under C1: N = SUM(decay) ~= 1.9996 < 2).
        strong = [
            StructuredEvent(timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), source="Test", domain="macro", entities_tickers=["FED"], urgency_score=9, sentiment_score=-0.70, summary="Strong bearish 1"),
            StructuredEvent(timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), source="Test", domain="macro", entities_tickers=["FED"], urgency_score=8, sentiment_score=-0.85, summary="Strong bearish 2"),
            StructuredEvent(timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), source="Test", domain="macro", entities_tickers=["FED"], urgency_score=9, sentiment_score=-0.80, summary="Strong bearish 3"),
        ]''')

# =========================================================== 3. weighted sentiment tests
rep("tests/test_weighted_sentiment.py", '''def test_half_life_decay_60_min_is_half_weight():
    c = _offline_commander()
    # Fresh +1.0 vs 60-min-old -1.0: old event weighs half -> S = (1-0.5)/1.5.
    s, u, n = c.compute_weighted_sentiment([
        _ev(+1.0, 5, age_min=0.0), _ev(-1.0, 5, age_min=60.0),
    ])
    assert abs(s - (1.0 / 3.0)) < 0.02
    assert abs(n - 1.5) < 0.02''',
'''def test_half_life_decay_60_min_is_half_weight():
    c = _offline_commander()
    # Fresh +1.0 vs ~60-min-old -1.0: old event weighs about half
    # (decay 0.506 at 59 min, within C4's +-5% of 0.5) -> S ~= 1/3, N ~= 1.5.
    # Exactly 60 min is not used: the event would be > 60.0 min old by
    # evaluation time and fall outside the "last 60 min" window.
    s, u, n = c.compute_weighted_sentiment([
        _ev(+1.0, 5, age_min=0.0), _ev(-1.0, 5, age_min=59.0),
    ])
    assert abs(s - (1.0 / 3.0)) < 0.02
    assert abs(n - 1.5) < 0.02''')

rep("tests/test_weighted_sentiment.py", '''def test_fallback_never_enters_hold_cash():
    c = _offline_commander()
    # S=-0.7, U=9 would be HOLD_CASH territory, but the keyword fallback
    # has no LLM confidence, so it must stop at SHORT_ONLY.
    state = asyncio.run(c.synthesize_regime([_ev(-0.7, 9), _ev(-0.7, 9)]))
    assert state.directional_bias == "SHORT_ONLY"
    assert state.confidence == 0.50''',
'''def test_fallback_never_enters_hold_cash():
    c = _offline_commander()
    # S=-0.7, U=9 would be HOLD_CASH territory, but the keyword fallback
    # has no LLM confidence, so it must stop at SHORT_ONLY.
    # Three events: two fresh ones give N ~= 1.9996 < 2 (C1: N = SUM(decay)).
    state = asyncio.run(c.synthesize_regime([_ev(-0.7, 9), _ev(-0.7, 9), _ev(-0.7, 9)]))
    assert state.directional_bias == "SHORT_ONLY"
    assert state.confidence == 0.50


def test_two_fresh_events_do_not_reach_n2():
    # Boundary behaviour of the literal C1 formula, pinned on purpose:
    # N = SUM(decay) and any nonzero age gives decay < 1, so exactly two
    # fresh events (N ~= 1.9996) never reach the N >= 2 direction gate.
    # A direction flip needs three fresh events' worth of evidence.
    c = _offline_commander()
    s, u, n = c.compute_weighted_sentiment([_ev(-0.7, 9), _ev(-0.7, 9)])
    assert abs(s - (-0.7)) < 0.01
    assert abs(u - 9.0) < 0.01
    assert 1.99 < n < 2.0
    state = asyncio.run(c.synthesize_regime([_ev(-0.7, 9), _ev(-0.7, 9)]))
    assert state.directional_bias == "BIDIRECTIONAL"''')


def main():
    contents = {}
    for path, old, new in REPLACEMENTS:
        if path not in contents:
            with open(path, "r", encoding="utf-8", newline="") as f:
                contents[path] = f.read()
        n = contents[path].count(old)
        if n != 1:
            print(f"FAIL {path}: expected 1 occurrence, found {n} for: {old[:80]!r}")
            sys.exit(1)
    for path in NEW_FILES:
        if os.path.exists(path):
            print(f"FAIL {path}: already exists, refusing to overwrite")
            sys.exit(1)
    for path, old, new in REPLACEMENTS:
        contents[path] = contents[path].replace(old, new)
        print(f"OK {path}")
    for path, content in contents.items():
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(content)
    for path, content in NEW_FILES.items():
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        print(f"NEW {path}")
    print(f"Applied {len(REPLACEMENTS)} replacements + {len(NEW_FILES)} new files.")


if __name__ == "__main__":
    main()
