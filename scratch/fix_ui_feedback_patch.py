# fix_ui_feedback_patch.py — 三個 UI 回饋修復（2026-11-13 使用者回報）。
# 1. Pause Feed 時新聞頁（Intel Hub）也要變黑白：暫停灰階原本只套在 arena
#    視圖（.workspace-grid），新聞在 #intelHubMainView 裡沒被蓋到。
# 2. 複製 OmniRoute 密碼按鈕恢復 "copied!"：密碼值永不進前端（第 7 項），改由
#    後端 bridge 讀 INITIAL_PASSWORD、經 OS 剪貼簿複製，只回成功狀態。
# 3. 開啟 OmniRoute console 按鈕顯示 "opening..." 並防重複點擊：之前按下去
#    毫無回饋，使用者會重複按，每按一次就多開一個瀏覽器分頁。
# 改動：src/gui/assets/app.css、app.js、src/gui/dashboard.py；新增 tests/test_ui_feedback.py。
# 每個 replacement 寫入前驗證在目標檔中精確匹配一次；保留各檔換行風格。
import os

# 專案根目錄判定：kernel 執行時 cwd 即專案根目錄；patch 腳本放在 scratch/，
# 所以 __file__ 所在目錄是 scratch，必須往上找（cwd 優先）。
ROOT = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
BASE = None
for c in [os.getcwd(), ROOT, os.path.dirname(ROOT)]:
    if os.path.isfile(os.path.join(c, "src", "gui", "assets", "index.html")):
        BASE = c
        break
if BASE is None:
    BASE = os.getcwd()
ASSETS = os.path.join(BASE, "src", "gui", "assets")
SRC = os.path.join(BASE, "src")
TESTS = os.path.join(BASE, "tests")


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


# --- 1. app.css：暫停灰階蓋到 Intel Hub（新聞頁） ---
OLD_CSS_TRANS = """/* Smooth grayscale transition for paused arena (keeps #liveBadge and #pauseBtn in full red color) */
.workspace-grid,
.spatial-dock-bar .lg-dock-pod--island,"""
NEW_CSS_TRANS = """/* Smooth grayscale transition for paused arena + Intel Hub news (keeps #liveBadge and #pauseBtn in full red color) */
.workspace-grid,
#intelHubMainView,
.spatial-dock-bar .lg-dock-pod--island,"""
replace_once(os.path.join(ASSETS, "app.css"), OLD_CSS_TRANS, NEW_CSS_TRANS, "app.css paused transition covers intel hub")

OLD_CSS_PAUSED = """body.arena-paused .workspace-grid,
body.arena-paused .spatial-dock-bar .lg-dock-pod--island,"""
NEW_CSS_PAUSED = """body.arena-paused .workspace-grid,
body.arena-paused #intelHubMainView,
body.arena-paused .spatial-dock-bar .lg-dock-pod--island,"""
replace_once(os.path.join(ASSETS, "app.css"), OLD_CSS_PAUSED, NEW_CSS_PAUSED, "app.css paused grayscale covers intel hub")

# --- 2. app.js：開啟 console 按鈕顯示 opening... 並防重複點擊 ---
OLD_CONSOLE = """  function openOmniRouteConsole() {
    // Console URL follows the configured gateway port (item 10 A2): the
    // bridge is the primary path; the fallback reuses the last port the
    // setup status reported (20128 until the first status call).
    const port = (typeof window.__tradebotGatewayPort === 'number') ? window.__tradebotGatewayPort : 20128;
    const fallbackUrl = `http://127.0.0.1:${port}`;
    if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.open_omniroute_console === 'function') {
      window.pywebview.api.open_omniroute_console().catch(() => {
        window.open(fallbackUrl, '_blank');
      });
    } else {
      window.open(fallbackUrl, '_blank');
    }
  }"""
NEW_CONSOLE = """  function openOmniRouteConsole() {
    // Console URL follows the configured gateway port (item 10 A2): the
    // bridge is the primary path; the fallback reuses the last port the
    // setup status reported (20128 until the first status call).
    const btn = document.getElementById('btnOpenOmniConsole');
    // No feedback used to make repeated clicks open a new tab each time:
    // show "opening..." immediately and ignore re-clicks until it settles.
    if (btn && btn.dataset.opening === '1') return;
    const labelEl = btn ? btn.querySelector('span') : null;
    const prevLabel = labelEl ? labelEl.textContent : '';
    if (btn) { btn.dataset.opening = '1'; btn.disabled = true; }
    if (labelEl) labelEl.textContent = 'opening...';
    const done = () => {
      if (btn) { delete btn.dataset.opening; btn.disabled = false; }
      if (labelEl) labelEl.textContent = prevLabel || 'Launch Console';
    };
    const port = (typeof window.__tradebotGatewayPort === 'number') ? window.__tradebotGatewayPort : 20128;
    const fallbackUrl = `http://127.0.0.1:${port}`;
    if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.open_omniroute_console === 'function') {
      window.pywebview.api.open_omniroute_console().then(done, () => {
        window.open(fallbackUrl, '_blank');
        done();
      });
    } else {
      window.open(fallbackUrl, '_blank');
      setTimeout(done, 1200);
    }
  }"""
replace_once(os.path.join(ASSETS, "app.js"), OLD_CONSOLE, NEW_CONSOLE, "app.js console button opening feedback + guard")

# --- 3. app.js：複製密碼走後端 bridge，成功顯示 copied! ---
OLD_COPY = """  function copyOmniPassword() {
    // The password is never exposed to the frontend (item 7): clicking the
    // badge only points at where it lives instead of copying it.
    if (typeof showChartToast === 'function') {
      showChartToast('Admin password is stored in ~/.omniroute/.env', '#F59E0B');
    }
  }"""
NEW_COPY = """  function copyOmniPassword() {
    // The password value never enters the frontend (item 7): the bridge
    // copies it to the OS clipboard server-side and only reports success,
    // so the button can truthfully show "copied!" again.
    const showEnvHint = () => {
      if (typeof showChartToast === 'function') {
        showChartToast('Admin password is stored in ~/.omniroute/.env', '#F59E0B');
      }
    };
    if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.copy_omniroute_password === 'function') {
      window.pywebview.api.copy_omniroute_password().then((res) => {
        if (res && res.status === 'ok') {
          if (typeof showChartToast === 'function') showChartToast('copied!', '#10F5A0');
        } else {
          showEnvHint();
        }
      }, showEnvHint);
      return;
    }
    showEnvHint();
  }"""
replace_once(os.path.join(ASSETS, "app.js"), OLD_COPY, NEW_COPY, "app.js copy password via bridge + copied!")

# --- 4. dashboard.py：OS 剪貼簿 helper（放 _ArenaBridgeApi 之前） ---
OLD_CLASS = """HTML_TEMPLATE = _build_html_template()


class _ArenaBridgeApi:"""
NEW_CLASS = """HTML_TEMPLATE = _build_html_template()


def _copy_text_to_clipboard_windows(text: str) -> bool:
    \"\"\"Best-effort copy of text to the Windows clipboard via ctypes.

    Returns False on non-Windows or any failure; never raises and never
    logs the text (it may be a password). The clipboard takes ownership
    of the allocated memory on success, so it is freed only on failure.
    \"\"\"
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        CF_UNICODETEXT = 13
        GMEM_MOVEABLE = 0x0002
        data = text.encode("utf-16-le") + b"\\x00\\x00"
        hglobal = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not hglobal:
            return False
        locked = kernel32.GlobalLock(hglobal)
        if not locked:
            kernel32.GlobalFree(hglobal)
            return False
        try:
            ctypes.memmove(locked, data, len(data))
        finally:
            kernel32.GlobalUnlock(hglobal)
        if not user32.OpenClipboard(None):
            kernel32.GlobalFree(hglobal)
            return False
        try:
            user32.EmptyClipboard()
            if not user32.SetClipboardData(CF_UNICODETEXT, hglobal):
                kernel32.GlobalFree(hglobal)
                return False
        finally:
            user32.CloseClipboard()
        return True
    except Exception as e:
        logger.debug("Clipboard copy failed: %s", e)
        return False


class _ArenaBridgeApi:"""
replace_once(os.path.join(SRC, "gui", "dashboard.py"), OLD_CLASS, NEW_CLASS, "dashboard.py clipboard helper")

# --- 5. dashboard.py：copy_omniroute_password bridge（接在 open_omniroute_console 後） ---
OLD_BRIDGE = """        except Exception as e:
            logger.error("Failed to open OmniRoute console: %s", e)
            return {"status": "error", "message": str(e)}

    def get_setup_status(self) -> Dict[str, Any]:"""
NEW_BRIDGE = """        except Exception as e:
            logger.error("Failed to open OmniRoute console: %s", e)
            return {"status": "error", "message": str(e)}

    def copy_omniroute_password(self) -> Dict[str, Any]:
        \"\"\"Copies the OmniRoute admin password to the OS clipboard.

        The password value never enters the frontend (item 7): it is read
        from INITIAL_PASSWORD in ~/.omniroute/.env server-side, copied
        via the OS clipboard, and only the success status is returned
        so the frontend can show "copied!". The value is never logged.
        \"\"\"
        try:
            env_map = self._dashboard.config_manager.read_omniroute_env()
        except Exception as e:
            logger.error("Failed to read omniroute env for password copy: %s", e)
            return {"status": "error", "message": "could not read password store"}
        password = (env_map.get("INITIAL_PASSWORD") or "").strip()
        if not password:
            return {"status": "error", "message": "password not configured"}
        try:
            ok = _copy_text_to_clipboard_windows(password)
        except Exception as e:
            logger.error("Failed to copy OmniRoute password to clipboard: %s", e)
            return {"status": "error", "message": str(e)}
        if not ok:
            return {"status": "error", "message": "clipboard unavailable"}
        return {"status": "ok"}

    def get_setup_status(self) -> Dict[str, Any]:"""
replace_once(os.path.join(SRC, "gui", "dashboard.py"), OLD_BRIDGE, NEW_BRIDGE, "dashboard.py copy_omniroute_password bridge")

# --- 6. 新增測試 ---
TEST_CONTENT = '''"""UI feedback fixes (2026-11-13): copy-password bridge.

copy_omniroute_password reads INITIAL_PASSWORD server-side and copies it
via the OS clipboard; the value never reaches the frontend (item 7).
The clipboard helper is monkeypatched here; the real ctypes path is
verified by clicking the button in the app.
"""
import json
from pathlib import Path
from unittest.mock import MagicMock

import src.gui.dashboard as dashboard_mod
from src.gui.dashboard import ArenaDashboard, _ArenaBridgeApi
from src.intelligence.config_manager import ConfigManager


def _bridge_with_env(tmp_path, env_text):
    dash = ArenaDashboard()
    dash.config_manager = ConfigManager(
        data_dir=tmp_path / "data",
        omni_env_path=tmp_path / ".omniroute" / ".env",
    )
    env_dir = tmp_path / ".omniroute"
    env_dir.mkdir(parents=True, exist_ok=True)
    (env_dir / ".env").write_text(env_text, encoding="utf-8")
    dash.gateway_supervisor = MagicMock()
    return _ArenaBridgeApi(dash)


def test_copy_password_not_configured(tmp_path, monkeypatch):
    bridge = _bridge_with_env(tmp_path, "DEEPSEEK_API_KEY=sk-test\\n")
    calls = []
    monkeypatch.setattr(
        dashboard_mod, "_copy_text_to_clipboard_windows",
        lambda text: calls.append(text) or True,
    )
    res = bridge.copy_omniroute_password()
    assert res["status"] == "error"
    assert calls == []


def test_copy_password_copies_value_but_never_returns_it(tmp_path, monkeypatch):
    bridge = _bridge_with_env(tmp_path, "INITIAL_PASSWORD=Secret1234\\n")
    calls = []
    monkeypatch.setattr(
        dashboard_mod, "_copy_text_to_clipboard_windows",
        lambda text: calls.append(text) or True,
    )
    res = bridge.copy_omniroute_password()
    assert res == {"status": "ok"}
    assert calls == ["Secret1234"]
    assert "Secret1234" not in json.dumps(res)


def test_copy_password_helper_failure(tmp_path, monkeypatch):
    bridge = _bridge_with_env(tmp_path, "INITIAL_PASSWORD=Secret1234\\n")
    monkeypatch.setattr(
        dashboard_mod, "_copy_text_to_clipboard_windows", lambda text: False
    )
    res = bridge.copy_omniroute_password()
    assert res["status"] == "error"
    assert "Secret1234" not in json.dumps(res)


def test_copy_text_to_clipboard_windows_non_windows(monkeypatch):
    monkeypatch.setattr(dashboard_mod.sys, "platform", "linux")
    assert dashboard_mod._copy_text_to_clipboard_windows("x") is False
'''
test_path = os.path.join(TESTS, "test_ui_feedback.py")
assert not os.path.exists(test_path), f"test file already exists: {test_path}"
with open(test_path, "w", encoding="utf-8", newline="") as f:
    f.write(TEST_CONTENT)
print("OK tests/test_ui_feedback.py created")

print("PATCH DONE")
