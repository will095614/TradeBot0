#!/usr/bin/env python3
"""Fix item 7 follow-up: close_window must fall back to destroy() when
PostMessageW reports failure.

On Windows, PostMessageW returns 0 when the handle is not a valid window
(e.g. already destroyed). The first version returned unconditionally after
the call, so a failed post silently skipped the close entirely. Now a 0
return falls through to destroy(), same as the exception path.
"""
import os
import sys

if not os.path.isdir("src/gui"):
    print("FAIL: run this script from the project root (src/gui not found)")
    sys.exit(1)

REPLACEMENTS = []
REPLACEMENTS.append(("src/gui/dashboard.py", r'''        if sys.platform == "win32":
            hwnd = _get_native_hwnd(window)
            if hwnd:
                try:
                    import ctypes
                    ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
                    return
                except Exception as e:
                    logger.debug("PostMessage WM_CLOSE failed, falling back to destroy(): %s", e)''', r'''        if sys.platform == "win32":
            hwnd = _get_native_hwnd(window)
            if hwnd:
                try:
                    import ctypes
                    posted = ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
                    if posted:
                        return
                    logger.debug("PostMessage WM_CLOSE failed, falling back to destroy()")
                except Exception as e:
                    logger.debug("PostMessage WM_CLOSE failed, falling back to destroy(): %s", e)'''))


def main():
    for rel, old, new in REPLACEMENTS:
        with open(rel, "r", encoding="utf-8", newline="") as f:
            content = f.read()
        count = content.count(old)
        if count != 1:
            print(f"FAIL {rel}: expected exactly 1 occurrence, found {count}")
            sys.exit(1)
        content = content.replace(old, new)
        with open(rel, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        print(f"OK {rel}")
    print("ALL PATCHES APPLIED")


if __name__ == "__main__":
    main()
