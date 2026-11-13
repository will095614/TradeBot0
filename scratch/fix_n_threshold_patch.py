# fix_n_threshold_patch.py -- N>=2 -> N>=1.9 (2026-11-13, user asked for an objective call)
# Judgement: the literal N>=2 gate is a formula artefact, not a design choice.
# N = SUM(decay), any nonzero age gives decay < 1, so two fresh events give
# N ~= 1.9996 and can NEVER reach 2.0 -- the implemented bar was "effectively
# 3 events", while the design's C1 table meant "at least 2 events". N>=1.9
# implements the design intent, still blocks a single event (N < 1 < 1.9),
# and S/U already do the heavy filtering. The gate stays tunable.
import io, os, sys

ROOT = os.getcwd()

def patch(path, old, new, must=1):
    p = os.path.join(ROOT, path)
    with io.open(p, encoding="utf-8", newline="") as f:
        txt = f.read()
    n = txt.count(old)
    assert n == must, "%s: anchor %r found %d times (want %d)" % (path, old[:60], n, must)
    txt = txt.replace(old, new)
    with io.open(p, encoding="utf-8", newline="") as f:
        pass
    # preserve the file's own newline style: rewrite with same newlines
    with io.open(p, "w", encoding="utf-8", newline="") as f:
        f.write(txt)
    print("patched %s" % path)

# 1) macro_commander.py -- the two direction gates + the comment above them
patch(r"src\intelligence\macro_commander.py",
      "                # The bar is deliberately conservative: one extreme event\n"
      "                # (N < 2) can never flip the arena, and HOLD_CASH is never\n",
      "                # The bar is deliberately conservative: one extreme event\n"
      "                # (N < 1.9) can never flip the arena, and HOLD_CASH is never\n")
patch(r"src\intelligence\macro_commander.py",
      "                if w_s > 0.45 and w_u >= 7 and w_n >= 2:\n",
      "                if w_s > 0.45 and w_u >= 7 and w_n >= 1.9:\n")
patch(r"src\intelligence\macro_commander.py",
      "                elif w_s < -0.45 and w_u >= 7 and w_n >= 2:\n",
      "                elif w_s < -0.45 and w_u >= 7 and w_n >= 1.9:\n")

# 2) test_weighted_sentiment.py -- the pinned boundary test now asserts the
# relaxed gate: two fresh events DO reach N >= 1.9 and flip to SHORT_ONLY.
old_test = (
    "def test_two_fresh_events_do_not_reach_n2():\n"
    "    # Boundary behaviour of the literal C1 formula, pinned on purpose:\n"
    "    # N = SUM(decay) and any nonzero age gives decay < 1, so exactly two\n"
    "    # fresh events (N ~= 1.9996) never reach the N >= 2 direction gate.\n"
    "    # A direction flip needs three fresh events' worth of evidence.\n"
    "    c = _offline_commander()\n"
    "    s, u, n = c.compute_weighted_sentiment([_ev(-0.7, 9), _ev(-0.7, 9)])\n"
    "    assert abs(s - (-0.7)) < 0.01\n"
    "    assert abs(u - 9.0) < 0.01\n"
    "    assert 1.99 < n < 2.0\n"
    "    state = asyncio.run(c.synthesize_regime([_ev(-0.7, 9), _ev(-0.7, 9)]))\n"
    "    assert state.directional_bias == \"BIDIRECTIONAL\"\n"
)
new_test = (
    "def test_two_fresh_events_reach_n19():\n"
    "    # Relaxed C1 gate (2026-11-13): N = SUM(decay) and any nonzero age\n"
    "    # gives decay < 1, so exactly two fresh events give N ~= 1.9996 --\n"
    "    # below the literal 2.0 but above the 1.9 gate, so two events\n"
    "    # suffice to flip. One event (N < 1) still cannot flip the arena.\n"
    "    c = _offline_commander()\n"
    "    s, u, n = c.compute_weighted_sentiment([_ev(-0.7, 9), _ev(-0.7, 9)])\n"
    "    assert abs(s - (-0.7)) < 0.01\n"
    "    assert abs(u - 9.0) < 0.01\n"
    "    assert 1.9 < n < 2.0\n"
    "    state = asyncio.run(c.synthesize_regime([_ev(-0.7, 9), _ev(-0.7, 9)]))\n"
    "    assert state.directional_bias == \"SHORT_ONLY\"\n"
)
patch(r"tests\test_weighted_sentiment.py", old_test, new_test)

# 3) test_intel_veto.py -- the comment stating the old rule
patch(r"tests\test_intel_veto.py",
      "        # Three strongly bearish events with severe urgency still flip it\n"
      "        # (two are not enough under C1: N = SUM(decay) ~= 1.9996 < 2).\n",
      "        # Three strongly bearish events with severe urgency still flip it\n"
      "        # (two fresh events also reach the relaxed C1 gate N >= 1.9,\n"
      "        # since N = SUM(decay) ~= 1.9996; one event still cannot flip).\n")

print("ALL PATCHES APPLIED")
