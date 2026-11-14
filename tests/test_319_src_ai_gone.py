"""Audit 3.19: src/ai/ holds only stale .pyc files (no source).

Verified 2026-11-15: nothing imports src.ai (grep over src/, tests/,
main.py, build_exe.ps1, TradeBot0.iss -- only unrelated aiohttp hits),
git does not track it, and the PyInstaller spec collects only
webview/clr_loader/pythonnet/websockets + src/gui/assets data, so the
audit's "still gets bundled" claim is not supported by the build -- but
the directory is dead weight and was deleted. These tests pin that no
src/ai package or reference remains.
"""
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

_REFERENCE_RE = re.compile(r"(from\s+src\.ai\b|import\s+src\.ai\b|src[\\/]ai\b)")


def _scanned_files():
    for path in (PROJECT_ROOT / "src").rglob("*"):
        if path.is_file() and path.suffix in {".py", ".js", ".html", ".css"}:
            yield path
    for name in ("main.py", "TradeBot0.iss", "build_exe.ps1"):
        path = PROJECT_ROOT / name
        if path.is_file():
            yield path
    for path in PROJECT_ROOT.glob("*.spec"):
        yield path


def test_src_ai_directory_is_gone():
    assert not (PROJECT_ROOT / "src" / "ai").exists(), (
        "src/ai/ must not exist (audit 3.19: stale .pyc only, no source)"
    )


def test_no_src_ai_reference_remains():
    offenders = []
    for path in _scanned_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        if _REFERENCE_RE.search(text):
            offenders.append(str(path.relative_to(PROJECT_ROOT)))
    assert offenders == [], f"src/ai references remain in: {offenders}"
