#!/usr/bin/env python3
"""Fix item 10a follow-up: is_admin_password_configured must be file-only.

Root cause of the 2 full-suite failures: _write_omni_env_vars syncs written
values into os.environ (needed so a spawned gateway child inherits them).
is_admin_password_configured() consulted os.environ as well, so a password
set earlier in the same process (test_gateway_setup_wizard passing an admin
password, or the first item-10 test) made every later check return True even
for a fresh ConfigManager with an empty env file. The ~/.omniroute/.env file
is the source of truth the gateway itself reads, so the check reads only it.
"""
import os
import sys

if not os.path.isdir("src/gui"):
    print("FAIL: run this script from the project root (src/gui not found)")
    sys.exit(1)

REPLACEMENTS = []


def rep(path, old, new):
    REPLACEMENTS.append((path, old, new))


rep("src/intelligence/config_manager.py", '''    def is_admin_password_configured(self) -> bool:
        """True when a non-empty INITIAL_PASSWORD is present in the omni env file or process env."""
        env_map = self.read_omniroute_env()
        val = (env_map.get("INITIAL_PASSWORD") or os.getenv("INITIAL_PASSWORD") or "").strip()
        return bool(val)''',
'''    def is_admin_password_configured(self) -> bool:
        """True when a non-empty INITIAL_PASSWORD is persisted in the omni env file.
        The file is the source of truth the gateway reads; the process env is
        not consulted, so a password set earlier in this process (for a
        spawned daemon, or by another test) cannot masquerade as a persisted
        password for a fresh install."""
        env_map = self.read_omniroute_env()
        return bool((env_map.get("INITIAL_PASSWORD") or "").strip())''')


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
