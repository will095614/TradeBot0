#!/usr/bin/env python3
"""Fix item 9 follow-up: two test fixes found by the PC pytest run.

1. tests/test_performance_and_optimizations.py::test_session_state_save_and_
   restore_and_shutdown_bridge pointed the dashboard bridge at engine1 AFTER
   engine2 had been created. Under the item-9 generation fence engine1 is
   superseded, so its session save is (correctly) refused. The bridge part
   of the test only checks that bridge save/cancel/shutdown work, so it now
   uses the dashboard's own engine -- the current generation, exactly as in
   production (reset_engine always hands the dashboard the newest engine).
2. tests/test_generation_fence.py::_keyframes_block used "next @keyframes"
   as the block end; arenaFadeIn is the LAST @keyframes in app.css, so the
   slice ran to EOF and picked up later blur() uses. Now matches braces.
"""
import os
import sys

if not os.path.isdir("src/gui"):
    print("FAIL: run this script from the project root (src/gui not found)")
    sys.exit(1)

REPLACEMENTS = []


def rep(path, old, new):
    REPLACEMENTS.append((path, old, new))


rep("tests/test_performance_and_optimizations.py", """    # Test dashboard bridge save, cancel, and shutdown methods
    dash = ArenaDashboard(initial_cash=Decimal("100000.00"))
    dash.engine = engine1
    bridge = _ArenaBridgeApi(dash)""",
"""    # Test dashboard bridge save, cancel, and shutdown methods. The bridge
    # uses the dashboard's own engine (the current generation); pointing it
    # at engine1 would trip the item-9 generation fence, since engine2 is
    # newer -- a superseded engine must not overwrite the new generation.
    dash = ArenaDashboard(initial_cash=Decimal("100000.00"))
    bridge = _ArenaBridgeApi(dash)""")

rep("tests/test_generation_fence.py", """def _keyframes_block(css, name):
    start = css.index(f"@keyframes {name}")
    end = css.find("@keyframes", start + 1)
    return css[start:end if end != -1 else len(css)]""",
"""def _keyframes_block(css, name):
    # Brace-matched block: @keyframes rules are not terminated by the next
    # @keyframes (arenaFadeIn is the last one in the file), so scan braces.
    start = css.index(f"@keyframes {name}")
    brace = css.index("{", start)
    depth = 0
    for i in range(brace, len(css)):
        if css[i] == "{":
            depth += 1
        elif css[i] == "}":
            depth -= 1
            if depth == 0:
                return css[start:i + 1]
    return css[start:]""")


def main():
    failed = []
    for path, old, new in REPLACEMENTS:
        with open(path, "r", encoding="utf-8", newline="") as f:
            content = f.read()
        n = content.count(old)
        if n != 1:
            failed.append(f"{path}: expected 1 occurrence, found {n} for: {old[:80]!r}")
            continue
        content = content.replace(old, new)
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        print(f"OK {path}")
    if failed:
        print("FAILURES:")
        for msg in failed:
            print(" -", msg)
        sys.exit(1)
    print(f"Applied {len(REPLACEMENTS)} replacements.")


if __name__ == "__main__":
    main()
