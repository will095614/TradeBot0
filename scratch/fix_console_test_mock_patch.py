# fix_console_test_mock_patch.py — 測試開分頁修復（2026-11-13）。
# 原因：tests/test_performance_and_optimizations.py 的
# test_session_state_save_and_restore_and_shutdown_bridge 直接呼叫
# bridge.open_omniroute_console() 且未 mock webbrowser.open，
# 每跑一次全量 pytest 就真的開一個 Edge 分頁到 127.0.0.1:20128。
# 2026-11-13 當天修復期間全量測試跑了多次，分頁越積越多；gateway 關著時
# 全部顯示拒絕連線。修法：mock webbrowser.open（與第 10 項的
# test_item10_packaging.py 做法一致），並斷言只呼叫一次。
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


TEST_FILE = os.path.join(BASE, "tests", "test_performance_and_optimizations.py")

replace_once(
    TEST_FILE,
    "from unittest.mock import AsyncMock, MagicMock",
    "from unittest.mock import AsyncMock, MagicMock, patch",
    "import patch",
)

replace_once(
    TEST_FILE,
    """    # Test open_omniroute_console bridge method
    res_console = bridge.open_omniroute_console()
    assert res_console["status"] == "ok"
    assert "20128" in res_console["url"]""",
    """    # Test open_omniroute_console bridge method. webbrowser must be
    # mocked: the unmocked call opened a real Edge tab on every pytest
    # run (2026-11-13: dozens of connection-refused tabs piled up
    # while the gateway was down).
    with patch("webbrowser.open", return_value=True) as mock_open:
        res_console = bridge.open_omniroute_console()
    assert res_console["status"] == "ok"
    assert "20128" in res_console["url"]
    mock_open.assert_called_once()""",
    "mock webbrowser.open in console test",
)

print("PATCH DONE")
