#!/usr/bin/env python3
"""Follow-up fixes for Item 1 verification (run once from project root).

1. tests/test_risk_semantics.py: the aggressive stop-out test must tick the
   broker first (a MARKET ticket has no price; the broker needs current_price).
2. tests/test_timemachine.py: the report assertion must use ARENA_MEMORY_DIR
   (conftest redirects it to a per-test tmp dir); the old literal path only
   passed because a stale memory/arena_report.md existed at project root,
   which the 2026-11-13 .md cleanup archived.
"""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

RISK_OLD = '''    comp = AggressiveCompetitor()
    broker = _broker()
    broker.register_portfolio(comp.portfolio, max_position_ratio=comp.max_position_ratio)
    ticket = comp.evaluate_signal("BUY", Decimal("2500.00"), {"atr": Decimal("35.00")}, broker, 100.0)
'''

RISK_NEW = '''    comp = AggressiveCompetitor()
    broker = _broker()
    broker.register_portfolio(comp.portfolio, max_position_ratio=comp.max_position_ratio)
    broker.on_tick(Decimal("2500.00"), timestamp=100.0)
    ticket = comp.evaluate_signal("BUY", Decimal("2500.00"), {"atr": Decimal("35.00")}, broker, 100.0)
'''

TM_OLD = '''    assert os.path.exists(os.path.join("memory", "arena_report.md"))
'''

TM_NEW = '''    # The report lands under ARENA_MEMORY_DIR (redirected to a tmp dir by conftest).
    mem_dir = os.environ.get("ARENA_MEMORY_DIR", "memory")
    assert os.path.exists(os.path.join(mem_dir, "arena_report.md"))
'''

PATCHES = [
    ("tests/test_risk_semantics.py", [(RISK_OLD, RISK_NEW)]),
    ("tests/test_timemachine.py", [(TM_OLD, TM_NEW)]),
]


def _read(path):
    with open(path, "rb") as f:
        raw = f.read()
    nl = "\r\n" if b"\r\n" in raw else "\n"
    return raw.decode("utf-8").replace("\r\n", "\n"), nl


def main():
    staged = []
    for rel, reps in PATCHES:
        path = os.path.join(PROJECT_ROOT, rel)
        text, nl = _read(path)
        for old, new in reps:
            n = text.count(old)
            if n != 1:
                print(f"FAIL {rel}: match count {n} (expected 1)")
                sys.exit(1)
            text = text.replace(old, new)
        staged.append((path, text, nl))
    for path, text, nl in staged:
        with open(path, "wb") as f:
            f.write(text.replace("\n", nl).encode("utf-8"))
        print(f"patched {os.path.relpath(path, PROJECT_ROOT)}")
    print("ITEM1 PATCH2 OK")


if __name__ == "__main__":
    main()
