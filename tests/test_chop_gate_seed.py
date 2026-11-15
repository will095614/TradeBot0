"""Debug pass, Part C (V2.8.0): chop-gate cold-start seeding.

The live chop gate needs 21 CLOSED 15m bars; a 120-bar warmup only
builds ~8 buckets (7 closed), so the gate is blind for ~3.3 h of live
running after every cold start (196 more 1m bars to reach 22 buckets --
measured in dbg_v280_seed_measure.py). Bootstrap therefore loads up to
360 1m bars: the newest 120 warm up indicators exactly as before, and
the up-to-240 older bars feed ONLY the MTF 15m aggregation
(_seed_chop_gate_buckets), never the warmup broker simulation, the ORB
anchor, or the 1m candle list.

These tests pin: the seed arms the gate at startup; a gap in the stored
history truncates the seed at the gap; misaligned/empty/malformed seeds
seed nothing (degrading to today's behaviour); and the seeded bootstrap
leaves the warmup tape, ORB anchor and typical mean byte-identical to an
unseeded bootstrap on the same 120 bars.
"""
import time
from decimal import Decimal
from unittest.mock import patch

from src.data.eth_feed import ETHFeed
from src.data.live_engine import LiveArenaEngine


def _tape_slot_aligned(n):
    """n consecutive 1m bar dicts on a 900 s-aligned start (exact n/15
    buckets when n is a multiple of 15). Closes alternate 3500/3520, so
    15m bucket closes alternate too and ER ~ 0.0. No freshness guarantee
    -- use only for the helper unit tests, never for bootstrap."""
    q = int(time.time() // 900) * 900
    start = q - n * 60
    out = []
    for i in range(n):
        c = 3500.0 + (20.0 if i % 2 else 0.0)
        out.append({"t": float(start + 60 * i), "o": c, "h": c, "l": c,
                    "c": c, "v": 15.0})
    return out


def _tape_end_anchored(n, seed_high=None):
    """n consecutive 1m bar dicts ending one minute ago (fresh cache:
    last bar < 600 s old). Closes alternate 3500/3520. seed_high: if
    given, the first n-120 bars carry that high -- to prove the ORB
    anchor ignores the seed bars."""
    end = int(time.time() // 60) * 60 - 60
    start = end - (n - 1) * 60
    out = []
    for i in range(n):
        c = 3500.0 + (20.0 if i % 2 else 0.0)
        h = seed_high if (seed_high is not None and i < n - 120) else c
        out.append({"t": float(start + 60 * i), "o": c, "h": h, "l": c,
                    "c": c, "v": 15.0})
    return out


def _engine():
    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    engine.storage.save_candle = lambda *a, **k: None
    engine.storage.save_candles_batch = lambda *a, **k: None
    return engine


def _feed_1m(engine, bars):
    for b in bars:
        engine._update_candle(b["t"], Decimal(str(b["c"])),
                              Decimal(str(b["h"])), Decimal(str(b["l"])),
                              Decimal(str(b["o"])))


def test_seed_helper_feeds_continuous_chain_and_arms_gate():
    engine = _engine()
    tape = _tape_slot_aligned(360)
    fed = engine._seed_chop_gate_buckets(tape[:240], float(tape[240]["t"]))
    assert fed == 240
    assert len(engine.candles_15m) == 16
    assert len(engine.candles_15m[:-1]) == 15
    assert engine._chop_gate_blocks() is False  # only 15 closed so far
    _feed_1m(engine, tape[240:])
    assert len(engine.candles) == 120
    assert len(engine.candles_15m) == 24
    assert len(engine.candles_15m[:-1]) == 23
    assert engine._chop_gate_blocks() is True
    engine.stop()


def test_seed_helper_gap_truncates_to_suffix_after_gap():
    engine = _engine()
    tape = _tape_slot_aligned(300)
    # 60-minute hole: drop indices 120..179. Only the 120 bars after the
    # gap chain continuously into the warmup start.
    seed = tape[:120] + tape[180:]
    assert len(seed) == 240
    fed = engine._seed_chop_gate_buckets(seed, float(tape[299]["t"]) + 60.0)
    assert fed == 120
    assert len(engine.candles_15m) == 8
    engine.stop()


def test_seed_helper_misaligned_or_empty_seeds_nothing():
    engine = _engine()
    tape = _tape_slot_aligned(360)
    # Last seed bar 120 s before the warmup start: the chain cannot start.
    assert engine._seed_chop_gate_buckets(tape[:240], float(tape[240]["t"]) + 60.0) == 0
    assert engine._seed_chop_gate_buckets([], float(tape[240]["t"])) == 0
    assert engine._seed_chop_gate_buckets(tape[:240], 0.0) == 0
    assert engine.candles_15m == []
    engine.stop()


def test_seed_helper_malformed_row_skipped_not_fabricated():
    engine = _engine()
    tape = _tape_slot_aligned(30)
    tape[15] = dict(tape[15])
    tape[15]["o"] = "bad"
    fed = engine._seed_chop_gate_buckets(tape, float(tape[-1]["t"]) + 60.0)
    assert fed == 29
    assert len(engine.candles_15m) == 2
    engine.stop()


def test_seeded_bootstrap_arms_gate_and_keeps_orb_anchor():
    engine = _engine()
    tape = _tape_end_anchored(360, seed_high=4000.0)
    engine.storage.load_latest_candles = lambda limit=150: list(tape)
    with patch.object(ETHFeed, "fetch_historical_bars",
                      side_effect=RuntimeError("no network in test")):
        engine.bootstrap_intraday_session()
    # Warmup tape unchanged: exactly the newest 120 bars.
    assert len(engine.candles) == 120
    # Gate armed at startup: 24-25 buckets, >= 21 closed, choppy ER.
    assert len(engine.candles_15m) >= 22
    assert engine._chop_gate_blocks() is True
    # ORB anchor comes from the first 15 WARMUP bars only -- the seed
    # bars' 4000 high must not leak into it.
    assert engine.live_orb_high == Decimal("3520")
    assert engine.live_orb_low == Decimal("3500")
    # Typical mean is over the 120 warmup bars only (mean close 3510).
    assert engine.live_typical_mean == Decimal("3510.00")
    engine.stop()


def test_unseeded_bootstrap_gate_dark():
    engine = _engine()
    tape = _tape_end_anchored(120)
    engine.storage.load_latest_candles = lambda limit=150: list(tape)
    with patch.object(ETHFeed, "fetch_historical_bars",
                      side_effect=RuntimeError("no network in test")):
        engine.bootstrap_intraday_session()
    assert len(engine.candles) == 120
    assert len(engine.candles_15m) <= 9
    assert engine._chop_gate_blocks() is False
    assert engine.live_orb_high == Decimal("3520")
    assert engine.live_orb_low == Decimal("3500")
    assert engine.live_typical_mean == Decimal("3510.00")
    engine.stop()
