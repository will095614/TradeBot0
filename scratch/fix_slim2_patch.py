# fix_slim2_patch.py — TradeBot0 程式瘦身第二遍（2026-11-13）
# 刪除（皆經 import 關係圖＋全 repo 字串引用搜尋交叉驗證為零有效引用）：
#   1. scratch/exe_launch_stdout.txt（探測輸出，第一遍被行程鎖住未刪；本次已確認鎖已解除）
#   2. .pytest_cache/ 整目錄（pytest 快取，可重建）
#   3. graphify-out/cache/.gfy-replace-bak-o5w6rq3q.tmp（graphify 更新時的暫存備份）
# 修改：README.md:59 過時敘述「1–9 項待修」→目前狀態。
# 安全規則：刪除前逐檔驗證零「有效引用」；任一驗證失敗即全數中止，不刪任何檔案。
# 「有效引用」排除（非程式引用）：本 patch 腳本自身、scratch/fix_*.py 維修紀錄、
#   graphify-out/cache/**（過期快取）、.cloud-attachments/**（使用者匯入對話紀錄）。
# 以 bytes 操作 README，保留原檔換行風格。缺檔時視為已刪、跳過（本地副本無此等檔案亦可跑）。
import os
import shutil
import sys

ROOT = os.getcwd()
SKIP_DIRS = {".venv", ".git", "__pycache__"}
TEXT_EXTS = (".py", ".md", ".txt", ".js", ".html", ".css", ".json", ".spec",
            ".ps1", ".bat", ".ini", ".yaml", ".yml", ".toml")
EXCLUDE_PREFIXES = ("scratch" + os.sep + "fix_", "graphify-out" + os.sep + "cache",
                    ".cloud-attachments" + os.sep)


def is_excluded(rel):
    rel_n = rel.replace("/", os.sep)
    if os.path.basename(rel_n).startswith("fix_slim2_patch"):
        return True
    return any(rel_n.startswith(p) for p in EXCLUDE_PREFIXES)


def iter_text_files():
    for dp, dn, fn in os.walk(ROOT):
        dn[:] = [d for d in dn if d not in SKIP_DIRS]
        for f in fn:
            if f.lower().endswith(TEXT_EXTS):
                yield os.path.relpath(os.path.join(dp, f), ROOT)


def verify_zero_refs(basename):
    hits = []
    for rel in iter_text_files():
        if is_excluded(rel):
            continue
        try:
            with open(os.path.join(ROOT, rel), encoding="utf-8", errors="replace") as fh:
                if basename in fh.read():
                    hits.append(rel)
        except OSError:
            continue
    return hits


def delete_path(rel, freed):
    p = os.path.join(ROOT, rel)
    if not os.path.lexists(p):
        print(f"SKIP (absent): {rel}")
        return freed, True
    try:
        if os.path.isdir(p) and not os.path.islink(p):
            total = 0
            for dp, dn, fn in os.walk(p):
                for f in fn:
                    try:
                        total += os.path.getsize(os.path.join(dp, f))
                    except OSError:
                        pass
            shutil.rmtree(p)
            freed += total
        else:
            freed += os.path.getsize(p)
            os.remove(p)
        print(f"DELETED: {rel}")
        return freed, True
    except OSError as e:
        print(f"FAILED to delete {rel}: {type(e).__name__}: {e}")
        return freed, False


def main():
    targets = [
        "scratch" + os.sep + "exe_launch_stdout.txt",
        ".pytest_cache",
        "graphify-out" + os.sep + "cache" + os.sep + ".gfy-replace-bak-o5w6rq3q.tmp",
    ]
    # ---- 驗證階段：任一失敗即全數中止 ----
    for rel in targets:
        hits = verify_zero_refs(os.path.basename(rel))
        if hits:
            print(f"ABORT: {rel} 仍有有效引用：{hits}")
            return 2
        print(f"VERIFIED zero refs: {rel}")
    # ---- README 修改（bytes，精確命中一次） ----
    readme = os.path.join(ROOT, "README.md")
    readme_done = False
    if os.path.exists(readme):
        data = open(readme, "rb").read()
        old = "1–9 項待修".encode("utf-8")
        new = "1–12 項已完成，待打包".encode("utf-8")
        if data.count(old) != 1:
            print(f"ABORT: README.md 預期錨點出現次數 != 1（實際 {data.count(old)}）")
            return 2
        open(readme, "wb").write(data.replace(old, new, 1))
        readme_done = True
        print("EDITED: README.md:59「1–9 項待修」→「1–12 項已完成，待打包」")
    else:
        print("SKIP: README.md absent (local copy), no edit")
    # ---- 刪除階段 ----
    freed = 0
    ok_all = True
    for rel in targets:
        freed, ok = delete_path(rel, freed)
        ok_all = ok_all and ok
    print(f"FREED_BYTES: {freed} (~{freed / 1048576:.2f} MB)")
    print(f"README_EDITED: {readme_done}")
    if not ok_all:
        print("RESULT: PARTIAL — some deletions failed (see FAILED lines); verify manually")
        return 1
    print("RESULT: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
