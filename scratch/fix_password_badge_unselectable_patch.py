# fix_password_badge_unselectable_patch.py — 密碼徽章摸不到（2026-11-13，使用者回報）。
# 根因：.pwd-badge 設了 `user-select: all;`（app.css:4869）——點一下就全選
# 整顆徽章的文字，*** 立刻反白。改為 `user-select: none;`，點按不再選取。
# 另：app.css 早就定義好 `.pwd-badge.pwd-copied` 綠色樣式（app.css:4886）卻
# 從未被使用；flashCopiedOnButton 顯示 copied! 時一併掛上該 class、恢復時
# 拿掉，沿用現成樣式不另發明。
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


APPCSS = os.path.join(BASE, "src", "gui", "assets", "app.css")
APPJS = os.path.join(BASE, "src", "gui", "assets", "app.js")

replace_once(
    APPCSS,
    """  cursor: pointer;
  user-select: all;""",
    """  cursor: pointer;
  user-select: none;""",
    "pwd-badge user-select none",
)

replace_once(
    APPJS,
    """      pwdBadge.textContent = 'copied!';
      pwdBadge._copiedTimer = setTimeout(() => {
        pwdBadge.innerHTML = pwdBadge._copiedOriginal;
        pwdBadge._copiedOriginal = undefined;
        pwdBadge._copiedTimer = undefined;
      }, 2000);""",
    """      pwdBadge.textContent = 'copied!';
      pwdBadge.classList.add('pwd-copied');
      pwdBadge._copiedTimer = setTimeout(() => {
        pwdBadge.innerHTML = pwdBadge._copiedOriginal;
        pwdBadge.classList.remove('pwd-copied');
        pwdBadge._copiedOriginal = undefined;
        pwdBadge._copiedTimer = undefined;
      }, 2000);""",
    "flash adds pwd-copied class",
)

print("PATCH DONE")
