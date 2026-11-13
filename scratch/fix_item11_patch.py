# fix_item11_patch.py - TradeBot0 維修清單第 11 項：程式瘦身
# 刪除經完整搜尋確認零引用的檔案 + 更新兩處 README 說明。
# 執行方式：上傳到 PC 的 scratch/fix_item11_patch.py，經 kernel 用
# C:\jupyter-env\Scripts\python.exe 執行（cwd = TradeBot0 根目錄）。
# 只刪清單內的檔案；任何一項預驗證失敗就整個中止，不刪任何東西。
from __future__ import annotations

import os
import shutil
import sys

# ---- 刪除清單 -------------------------------------------------------------
# scratch/ 探測腳本與輸出（fix_*.py 是維修 patch 紀錄，絕對不刪）
SCRATCH_DELETE = [
    "scratch/audit_all_components.py",
    "scratch/exe_launch_stdout.txt",
    "scratch/gui_launch_out.txt",
    "scratch/gui_launch_stdout.txt",
    "scratch/probe_gateway_daemon.py",
    "scratch/probe_gui_launch.py",
    "scratch/probe_omni_dashboard.py",
    "scratch/probe_out_20261113.txt",
    "scratch/pytest_run_20261113.txt",
    "scratch/repro_audit.py",
    "scratch/repro_out_20261113.txt",
    "scratch/test_live_quote.py",
    "scratch/test_omniroute_live.py",
    "scratch/test_start_daemon.py",
    "scratch/verify_all_modifications.py",
    "scratch/inventory_item11.txt",
]
# archive/md_20261113/ 已封存的舊除錯報告（內容仍在 git HEAD 5b6b7d5 原始位置）
ARCHIVE_DELETE = [
    "archive/md_20261113/DEBUG_RESEARCH_REPORT.md",
    "archive/md_20261113/DEBUG_RESEARCH_VERIFICATION.md",
    "archive/md_20261113/OPTIMIZATION_AUDIT.md",
    "archive/md_20261113/tradebot0_arena_audit_and_remediation_plan.md",
    "archive/md_20261113/babeubugging.md",
    "archive/md_20261113/arena_report.md",
    "archive/md_20261113/macro_commander_omniroute_workflow_plan.md",
    "archive/md_20261113/omniroute_ai_agent_installation_playbook.md",
    "archive/md_20261113/omniroute_deployment_guide.md",
]
# 孤兒模組：零 import、零字串引用（alias，功能已由 src/data/persistence.py 提供）
OTHER_DELETE = [
    "src/data/storage.py",
]
DELETE_FILES = SCRATCH_DELETE + ARCHIVE_DELETE + OTHER_DELETE

# build/ 預期的 PyInstaller 中間產物（必須完全符合才整目錄刪）
BUILD_EXPECTED = {
    "TradeBot0_Arena/Analysis-00.toc",
    "TradeBot0_Arena/COLLECT-00.toc",
    "TradeBot0_Arena/EXE-00.toc",
    "TradeBot0_Arena/PKG-00.toc",
    "TradeBot0_Arena/PYZ-00.pyz",
    "TradeBot0_Arena/PYZ-00.toc",
    "TradeBot0_Arena/TradeBot0_Arena.exe",
    "TradeBot0_Arena/TradeBot0_Arena.pkg",
    "TradeBot0_Arena/base_library.zip",
    "TradeBot0_Arena/localpycs/pyimod01_archive.pyc",
    "TradeBot0_Arena/localpycs/pyimod02_importers.pyc",
    "TradeBot0_Arena/localpycs/pyimod03_ctypes.pyc",
    "TradeBot0_Arena/localpycs/pyimod04_pywin32.pyc",
    "TradeBot0_Arena/localpycs/struct.pyc",
    "TradeBot0_Arena/warn-TradeBot0_Arena.txt",
    "TradeBot0_Arena/xref-TradeBot0_Arena.html",
}

# ---- 工具 -----------------------------------------------------------------
SKIP_DIRS = {".venv", ".git", "__pycache__", "node_modules", "graphify-out",
             "build", "dist", ".mypy_cache", ".pytest_cache",
             # .cloud-attachments 是 IDE 匯入的對話紀錄（使用者資料），檔名出現在
             # 其中只是對話提及，不是程式引用，不列入引用檢查。
             ".cloud-attachments"}


def fail(msg):
    print("ABORT:", msg)
    sys.exit(1)


def read_text(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def repo_files():
    out = []
    for dirpath, dirnames, filenames in os.walk("."):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            out.append(os.path.join(dirpath, fn))
    return out


def grep_repo(needle, skip_paths):
    """回傳所有包含 needle 的檔案（相對路徑）。"""
    hits = []
    for p in repo_files():
        rp = os.path.normpath(p)
        if rp in skip_paths:
            continue
        try:
            if needle in read_text(p):
                hits.append(rp)
        except Exception:
            continue
    return hits


def rep(path, old, new):
    """old 必須恰好出現一次，否則中止。bytes 層級替換，保留原檔換行格式。"""
    with open(path, "rb") as f:
        data = f.read()
    crlf = b"\r\n" in data
    old_b = old.encode("utf-8")
    new_b = new.encode("utf-8")
    if crlf:
        old_b = old_b.replace(b"\n", b"\r\n")
        new_b = new_b.replace(b"\n", b"\r\n")
    n = data.count(old_b)
    if n != 1:
        fail(f"{path}: 預期替換出現 1 次，實際 {n} 次")
    with open(path, "wb") as f:
        f.write(data.replace(old_b, new_b, 1))
    print(f"EDITED: {path} (newline={'CRLF' if crlf else 'LF'})")


def main():
    if not os.path.exists("main.py"):
        fail("cwd 不是 TradeBot0 根目錄（找不到 main.py）")
    print("cwd:", os.getcwd())

    # ---- 1. 預驗證：每個待刪檔案都存在，且檔名在全 repo 零引用 ----
    # 排除：待刪檔案本身、patch 腳本本身、graphify 生成物（排除於 repo_files 外）、
    # archive 封存說明（它本身就是列出這些檔名的清單，稍後會更新）。
    skip_self = {os.path.normpath(p) for p in DELETE_FILES}
    skip_self.add(os.path.normpath("scratch/fix_item11_patch.py"))
    skip_self.add(os.path.normpath("archive/md_20261113/README.md"))
    for rel in DELETE_FILES:
        if not os.path.isfile(rel):
            # 前一次部分執行已刪掉，視為已完成（清單事前已對照盤點核對過）。
            print(f"SKIP already gone: {rel}")
            continue
        base = os.path.basename(rel)
        if rel.startswith("archive/"):
            # 封存檔：檢查對封存路徑本身的引用。檔名本身可能與運行期路徑同名
            #（例如 memory/arena_report.md 是 timemachine 即時生成的報告，與封存
            # 的舊快照是不同檔案），故不用檔名比對。
            needles = [f"archive/md_20261113/{base}",
                       f"archive\\md_20261113\\{base}"]
            hits = []
            for nd in needles:
                hits += grep_repo(nd, skip_self)
            if hits:
                fail(f"{rel} 仍有引用（封存路徑出現在 {sorted(set(hits))}），中止")
        else:
            # storage.py 唯一的檔名提及在 OptimizationFullGuide.md 的架構樹裡
            #（設計文件，非程式引用；本腳本會同步修正該行，故預驗證時排除它）。
            extra_skip = set()
            if rel == "src/data/storage.py":
                extra_skip.add(os.path.normpath("OptimizationFullGuide.md"))
            hits = grep_repo(base, skip_self | extra_skip)
            if hits:
                fail(f"{rel} 仍有引用（檔名 {base} 出現在 {hits}），中止")
        print(f"OK zero-ref: {rel}")
    # storage.py 額外檢查：模組路徑字串引用
    mod_hits = []
    for needle in ("src.data.storage", "src/data/storage", "from src.data import storage"):
        mod_hits += grep_repo(needle, skip_self | {os.path.normpath("src/data/storage.py")})
    if mod_hits:
        fail(f"src/data/storage.py 仍有模組路徑引用：{sorted(set(mod_hits))}，中止")
    print("OK storage.py: 無模組路徑引用")

    # ---- 2. 預驗證 build/ 內容完全符合預期 ----
    build_bytes = 0
    if not os.path.isdir("build"):
        print("SKIP already gone: build/")
    else:
        actual = set()
        for dirpath, dirnames, filenames in os.walk("build"):
            for fn in filenames:
                actual.add(os.path.relpath(os.path.join(dirpath, fn), "build").replace(os.sep, "/"))
        if actual != BUILD_EXPECTED:
            fail(f"build/ 內容與預期不符，多出：{sorted(actual - BUILD_EXPECTED)}，缺少：{sorted(BUILD_EXPECTED - actual)}")
        for dirpath, dirnames, filenames in os.walk("build"):
            for fn in filenames:
                build_bytes += os.path.getsize(os.path.join(dirpath, fn))
        print(f"OK build/: {len(actual)} 個檔案皆為預期的 PyInstaller 中間產物，共 {build_bytes} bytes")

    # ---- 3. 預驗證兩處 README 替換皆恰好一次 ----
    readme_old = "- 舊的審查／除錯／部署報告已封存至 `archive/md_20261113/`（可還原）；設計參考見 `OptimizationFullGuide.md`。"
    readme_new = "- 舊的審查／除錯／部署報告已於 2026-11-13 程式瘦身時移除，內容仍在 git 歷史（HEAD 5b6b7d5）可還原；設計參考見 `OptimizationFullGuide.md`。"
    archive_old = "## 還原方式\n\n把檔案移回專案根目錄（memory/arena_report.md 移回 memory/）即可。"
    archive_new = (
        "## 2026-11-13 程式瘦身（維修清單第 11 項）\n\n"
        "上面列出的 9 個舊報告已於 2026-11-13 移除（使用者指示：移除用不到的檔案與之前的除錯報告）。"
        "本資料夾只留本 README 作為紀錄。\n\n"
        "還原方式：這些檔案的內容仍在 git 歷史裡，HEAD commit 5b6b7d5 的原始位置"
        "（專案根目錄、memory/arena_report.md 在 memory/），用 `git show 5b6b7d5:<原路徑>` 可找回。"
    )
    for path, old in (("README.md", readme_old),
                      ("archive/md_20261113/README.md", archive_old)):
        txt = read_text(path)
        if txt.count(old) != 1:
            fail(f"{path}: 預期替換出現 1 次，實際 {txt.count(old)} 次")
    # OptimizationFullGuide.md 架構樹：storage.py 只是 persistence.py 的 alias，
    # 刪除後把該行改為真正的引擎 persistence.py（LF 檔）。
    guide_old = "│   ├── storage.py             # SQLite WAL persistence engine"
    guide_new = "│   ├── persistence.py         # SQLite WAL persistence engine (ArenaStorage)"
    guide_txt = read_text("OptimizationFullGuide.md")
    if guide_txt.count(guide_old) != 1:
        fail(f"OptimizationFullGuide.md: 預期替換出現 1 次，實際 {guide_txt.count(guide_old)} 次")
    print("OK README 替換預驗證通過")

    # ---- 4. 執行刪除（被其他行程鎖住的檔案重試 5 次，仍鎖住就跳過並記錄） ----
    import time
    freed = 0
    deleted = []
    locked = []
    for rel in DELETE_FILES:
        if not os.path.isfile(rel):
            continue
        sz = os.path.getsize(rel)
        ok = False
        for attempt in range(5):
            try:
                os.remove(rel)
                ok = True
                break
            except PermissionError:
                time.sleep(2)
        if not ok:
            locked.append(rel)
            print(f"LOCKED skip: {rel} (被其他行程佔用，稍後手動刪除)")
            continue
        freed += sz
        deleted.append((rel, sz))
        print(f"DELETED: {rel} ({sz} bytes)")
    if os.path.isdir("build"):
        try:
            shutil.rmtree("build")
            print(f"DELETED dir: build/ (16 files, {build_bytes} bytes)")
        except PermissionError:
            locked.append("build/")
            print("LOCKED skip: build/ (被其他行程佔用，稍後手動刪除)")
            build_bytes = 0
    else:
        print("SKIP already gone: build/")
        build_bytes = 0
    print(f"freed total: {freed + build_bytes} bytes ({len(deleted)} files + build/)")
    if locked:
        print(f"NOTE locked (not deleted): {locked}")

    # ---- 5. 執行 README 編輯 ----
    rep("README.md", readme_old, readme_new)
    rep("archive/md_20261113/README.md", archive_old, archive_new)
    rep("OptimizationFullGuide.md", guide_old, guide_new)

    print(f"DONE: deleted {len(deleted)} files + build/ dir, edited 3 files")
    if locked:
        print(f"REMAINING LOCKED (delete manually later): {locked}")
        sys.exit(1)


if __name__ == "__main__":
    main()
