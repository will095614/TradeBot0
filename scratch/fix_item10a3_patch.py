#!/usr/bin/env python3
"""Fix item 10a follow-up 2: run() auto-spawn test vs the new password gate.

test_run_auto_spawn_waits_30_seconds sets up an onboarding-complete install
with no admin password in its tmp env, so run() now (correctly, item 10 A1)
skips auto-spawn and the test's start_daemon assertion fails. The test is
updated to set a password first (the new precondition), and a companion test
pins the new behavior: without a password, run() never auto-spawns.
"""
import os
import sys

if not os.path.isdir("src/gui"):
    print("FAIL: run this script from the project root (src/gui not found)")
    sys.exit(1)

REPLACEMENTS = []


def rep(path, old, new):
    REPLACEMENTS.append((path, old, new))


rep("tests/test_gateway_item8.py", '''    dash.config_manager.save_config({
        "has_completed_onboarding": True,
        "skip_ai_mode": False,
        "gateway_auto_spawn": True,
    })
    fake_supervisor = MagicMock()''',
'''    dash.config_manager.save_config({
        "has_completed_onboarding": True,
        "skip_ai_mode": False,
        "gateway_auto_spawn": True,
    })
    # Item 10 A1: auto-spawn now requires a configured admin password.
    dash.config_manager.set_admin_password("TestAdmin123")
    fake_supervisor = MagicMock()''')

rep("tests/test_gateway_item8.py", '''    assert fake_webview.started is True
    fake_supervisor.start_daemon.assert_called_once_with(max_wait_sec=30.0)''',
'''    assert fake_webview.started is True
    fake_supervisor.start_daemon.assert_called_once_with(max_wait_sec=30.0)


def test_run_skips_auto_spawn_without_admin_password(tmp_path, monkeypatch):
    """run() never auto-spawns a gateway whose console is still on OmniRoute's
    built-in default password (item 10 A1); the wizard forces one first."""
    dash = ArenaDashboard()
    dash.config_manager = ConfigManager(
        data_dir=tmp_path / "data",
        omni_env_path=tmp_path / ".omniroute" / ".env",
    )
    dash.config_manager.save_config({
        "has_completed_onboarding": True,
        "skip_ai_mode": False,
        "gateway_auto_spawn": True,
    })
    fake_supervisor = MagicMock()
    fake_supervisor.is_port_open.return_value = False
    fake_supervisor.start_daemon.return_value = (True, "ok")
    dash.gateway_supervisor = fake_supervisor
    fake_webview = _FakeWebview()
    monkeypatch.setitem(sys.modules, "webview", fake_webview)
    try:
        dash.run()
    finally:
        dash.engine.stop()
    assert fake_webview.started is True
    fake_supervisor.start_daemon.assert_not_called()''')


def main():
    check_only = "--check" in sys.argv
    failed = []
    for path, old, new in REPLACEMENTS:
        with open(path, "r", encoding="utf-8", newline="") as f:
            content = f.read()
        n = content.count(old)
        if n != 1:
            failed.append(f"{path}: expected 1 occurrence, found {n} for: {old[:80]!r}")
            continue
        if check_only:
            print(f"CHECK-OK {path}")
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
    print(f"{'Check passed' if check_only else 'Applied'}: {len(REPLACEMENTS)} replacements.")


if __name__ == "__main__":
    main()
