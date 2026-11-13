# fix_password_copy_patch.py — 密碼複製按鈕修復（2026-11-13，使用者回報）。
# 兩個各自獨立的根因：
# (1) ctypes 64-bit handle 截斷：dashboard.py 的 _copy_text_to_clipboard_windows
#     未宣告 restype/argtypes，ctypes 預設把所有 foreign 回傳值當 c_int，
#     64-bit 的 HGLOBAL handle 被截斷成 32-bit，GlobalLock 永遠失敗，
#     helper 永遠回 False，bridge 回 error，JS 永遠顯示 hint 而非 copied!。
#     實測證據：kernel 下 GlobalAlloc 成功、GlobalLock 回 0；helper 實測回 False。
# (2) toast 簽名不符：app.js 的 showChartToast(opts={}) 只吃物件
#     （triggerReason/action/symbol/price），正確呼叫點（3212、3880）都傳物件；
#     copyOmniPassword 卻傳字串 ('copied!', '#10F5A0')，toast 內容變成
#     預設的 Arena Event／SYNC，永遠不會出現 "copied!" 字樣。改為物件形式。
# 每個 replacement 寫入前驗證在目標檔中精確匹配一次。
import os

ROOT = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
BASE = None
for c in [os.getcwd(), ROOT, os.path.dirname(ROOT)]:
    if os.path.isfile(os.path.join(c, "src", "gui", "assets", "index.html")):
        BASE = c
        break
if BASE is None:
    BASE = os.getcwd()


def load(path):
    with open(path, "rb") as f:
        raw = f.read()
    crlf = b"\r\n" in raw
    return raw.decode("utf-8"), crlf


def save(path, text, crlf):
    data = text.replace("\n", "\r\n") if crlf else text
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(data)


def replace_once(path, old, new, label):
    text, crlf = load(path)
    n = text.count(old)
    assert n == 1, f"{label}: expected exactly 1 match in {path}, found {n}"
    save(path, text.replace(old, new), crlf)
    print(f"OK {label}")


DASHBOARD = os.path.join(BASE, "src", "gui", "dashboard.py")
APPJS = os.path.join(BASE, "src", "gui", "assets", "app.js")
TEST = os.path.join(BASE, "tests", "test_ui_feedback.py")

# (1) ctypes declarations in the clipboard helper
replace_once(
    DASHBOARD,
    """        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        CF_UNICODETEXT = 13
        GMEM_MOVEABLE = 0x0002""",
    """        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        # 64-bit Windows: ctypes defaults every foreign return type to
        # c_int, which truncates the 64-bit HGLOBAL handle; GlobalLock
        # then fails on the truncated handle and the copy silently
        # returns False (2026-11-13: the password-copy button never
        # worked for this reason). Declare the real signatures.
        kernel32.GlobalAlloc.restype = ctypes.c_void_p
        kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalUnlock.restype = ctypes.c_bool
        kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalFree.restype = ctypes.c_void_p
        kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
        user32.OpenClipboard.restype = ctypes.c_bool
        user32.OpenClipboard.argtypes = [ctypes.c_void_p]
        user32.EmptyClipboard.restype = ctypes.c_bool
        user32.EmptyClipboard.argtypes = []
        user32.SetClipboardData.restype = ctypes.c_void_p
        user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
        user32.CloseClipboard.restype = ctypes.c_bool
        user32.CloseClipboard.argtypes = []
        CF_UNICODETEXT = 13
        GMEM_MOVEABLE = 0x0002""",
    "ctypes signatures in clipboard helper",
)

# (2) toast calls: string form -> object form (showChartToast takes opts={})
replace_once(
    APPJS,
    "showChartToast('Admin password is stored in ~/.omniroute/.env', '#F59E0B');",
    "showChartToast({ triggerReason: 'Admin password is stored in ~/.omniroute/.env', action: 'INFO' });",
    "env-hint toast object form",
)
replace_once(
    APPJS,
    "showChartToast('copied!', '#10F5A0');",
    "showChartToast({ triggerReason: 'copied!', action: 'COPY' });",
    "copied toast object form",
)

# (3) regression test: real ctypes roundtrip (Windows-only, save/restore)
replace_once(
    TEST,
    """copy_omniroute_password reads INITIAL_PASSWORD server-side and copies it
via the OS clipboard; the value never reaches the frontend (item 7).
The clipboard helper is monkeypatched here; the real ctypes path is
verified by clicking the button in the app.
""",
    """copy_omniroute_password reads INITIAL_PASSWORD server-side and copies it
via the OS clipboard; the value never reaches the frontend (item 7).
Most tests monkeypatch the clipboard helper; the real ctypes path is
pinned by test_copy_text_to_clipboard_windows_roundtrip below (the
64-bit handle-truncation bug made it always return False until fixed).
""",
    "test docstring update",
)
replace_once(
    TEST,
    """import json
from pathlib import Path
""",
    """import json
from pathlib import Path

import pytest
""",
    "import pytest",
)
replace_once(
    TEST,
    """def test_copy_text_to_clipboard_windows_non_windows(monkeypatch):
    monkeypatch.setattr(dashboard_mod.sys, "platform", "linux")
    assert dashboard_mod._copy_text_to_clipboard_windows("x") is False
""",
    """def test_copy_text_to_clipboard_windows_non_windows(monkeypatch):
    monkeypatch.setattr(dashboard_mod.sys, "platform", "linux")
    assert dashboard_mod._copy_text_to_clipboard_windows("x") is False


def test_copy_text_to_clipboard_windows_roundtrip():
    \"\"\"Real ctypes clipboard path (Windows-only).

    Regression test for the 2026-11-13 bug: without declared restype /
    argtypes, ctypes truncated the 64-bit HGLOBAL handle to c_int, so
    GlobalLock always failed and the helper always returned False — the
    copy button never worked. The helper is called first (its True/False
    is decided by its own declarations); the read-back below uses a
    separate WinDLL instance. Saves the previous clipboard text (when
    it is text) and restores it afterwards.
    \"\"\"
    if dashboard_mod.sys.platform != "win32":
        pytest.skip("Windows-only clipboard test")
    import ctypes

    user32 = ctypes.WinDLL("user32", use_errno=True)
    kernel32 = ctypes.WinDLL("kernel32", use_errno=True)
    user32.OpenClipboard.restype = ctypes.c_bool
    user32.OpenClipboard.argtypes = [ctypes.c_void_p]
    user32.CloseClipboard.restype = ctypes.c_bool
    user32.CloseClipboard.argtypes = []
    user32.GetClipboardData.restype = ctypes.c_void_p
    user32.GetClipboardData.argtypes = [ctypes.c_uint]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.restype = ctypes.c_bool
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]

    def _read_text():
        if not user32.OpenClipboard(None):
            return None
        try:
            handle = user32.GetClipboardData(13)  # CF_UNICODETEXT
            if not handle:
                return None
            locked = kernel32.GlobalLock(handle)
            if not locked:
                return None
            try:
                return ctypes.wstring_at(locked)
            finally:
                kernel32.GlobalUnlock(handle)
        finally:
            user32.CloseClipboard()

    previous = _read_text()
    try:
        assert dashboard_mod._copy_text_to_clipboard_windows(
            "seed-clipboard-roundtrip-123"
        ) is True
        assert _read_text() == "seed-clipboard-roundtrip-123"
    finally:
        if previous is not None:
            dashboard_mod._copy_text_to_clipboard_windows(previous)
""",
    "roundtrip regression test",
)

print("PATCH DONE")
