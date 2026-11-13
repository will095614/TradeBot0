# fix_password_button_flash_patch.py — 密碼按鈕直接顯示 copied!（2026-11-13，使用者指示）。
# 問題：copyOmniPassword 成功時只發 chart toast，但 toast 顯示在主畫面
# （Arena view）的 K 線圖左上角，而按鈕在新聞頁（Intel Hub）；使用者在新聞頁
# 按的時候主畫面是藏起來的，6 秒後 toast 就消失了，永遠看不到。
# 修法：成功時按鈕本身直接顯示 "copied!" 兩秒再恢復（在哪個頁面都看得到），
# chart toast 保留（在主畫面時仍會出現）。失敗時維持原來的 .env 提示。
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


APPJS = os.path.join(BASE, "src", "gui", "assets", "app.js")

replace_once(
    APPJS,
    """  function copyOmniPassword() {
    // The password value never enters the frontend (item 7): the bridge
    // copies it to the OS clipboard server-side and only reports success,
    // so the button can truthfully show "copied!" again.
    const showEnvHint = () => {
      if (typeof showChartToast === 'function') {
        showChartToast({ triggerReason: 'Admin password is stored in ~/.omniroute/.env', action: 'INFO' });
      }
    };
    if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.copy_omniroute_password === 'function') {
      window.pywebview.api.copy_omniroute_password().then((res) => {
        if (res && res.status === 'ok') {
          if (typeof showChartToast === 'function') showChartToast({ triggerReason: 'copied!', action: 'COPY' });
        } else {
          showEnvHint();
        }
      }, showEnvHint);
      return;
    }
    showEnvHint();
  }""",
    """  function copyOmniPassword() {
    // The password value never enters the frontend (item 7): the bridge
    // copies it to the OS clipboard server-side and only reports success.
    // Success feedback is shown ON the button itself (2026-11-13): the
    // chart toast lives in the Arena view, so it is invisible while the
    // user is on the Intel Hub page where this button sits.
    const pwdBadge = document.getElementById('omniConsolePwd');
    const flashCopiedOnButton = () => {
      if (!pwdBadge) return;
      if (pwdBadge._copiedTimer) clearTimeout(pwdBadge._copiedTimer);
      if (pwdBadge._copiedOriginal === undefined) pwdBadge._copiedOriginal = pwdBadge.innerHTML;
      pwdBadge.textContent = 'copied!';
      pwdBadge._copiedTimer = setTimeout(() => {
        pwdBadge.innerHTML = pwdBadge._copiedOriginal;
        pwdBadge._copiedOriginal = undefined;
        pwdBadge._copiedTimer = undefined;
      }, 2000);
    };
    const showEnvHint = () => {
      if (typeof showChartToast === 'function') {
        showChartToast({ triggerReason: 'Admin password is stored in ~/.omniroute/.env', action: 'INFO' });
      }
    };
    if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.copy_omniroute_password === 'function') {
      window.pywebview.api.copy_omniroute_password().then((res) => {
        if (res && res.status === 'ok') {
          flashCopiedOnButton();
          if (typeof showChartToast === 'function') showChartToast({ triggerReason: 'copied!', action: 'COPY' });
        } else {
          showEnvHint();
        }
      }, showEnvHint);
      return;
    }
    showEnvHint();
  }""",
    "button flashes copied! on success",
)

print("PATCH DONE")
