"""In-app update check — scaffolding (2026-11-13).

Checks a remote JSON manifest for a newer TradeBot0 release and reports
the result. This module is scaffolding only: it performs the check and
nothing else. There is no download, no install, and no automatic update.

Manifest format (plain HTTPS GET, no login required)::

    {
      "version": "2026.11.20",
      "download_url": "https://example.invalid/TradeBot0Setup.exe",
      "notes": "What changed in this release."
    }

The manifest URL comes from the environment variable
``TRADEBOT0_UPDATE_URL`` (or an explicit argument). With no URL
configured — the case today, as there is no domain and no release
hosted anywhere — :func:`check_for_updates` returns
``{"status": "not_configured", ...}`` and issues no network request.

Statuses returned by :func:`check_for_updates`:

- ``not_configured`` — no manifest URL is set; nothing was fetched.
- ``up_to_date`` — the manifest version is equal to or older than the
  running version.
- ``update_available`` — the manifest version is newer; ``download_url``
  and ``notes`` (when present) are included.
- ``check_failed`` — the request or the manifest could not be read
  (network error, non-2xx, bad JSON, missing ``version``). The failure
  is logged at debug level and never raised.

Still to wire up (future work, not in this change):

- Hosting: a place to serve the manifest JSON and the installer
  (the user's GitHub account is currently suspended, so GitHub
  Releases is unavailable; a static file host or the user's own
  server is needed first).
- Frontend: a prompt/banner in the UI when ``update_available`` is
  returned, plus a settings field to enter the manifest URL.
- Download flow: downloading the installer to a temp file, verifying
  it, and launching it — a running exe cannot replace itself on
  Windows, so the installer (or a small updater) must do the replace.
- Release process: bump ``APP_VERSION`` in ``src/version.py`` and
  ``MyAppVersion`` in ``TradeBot0.iss`` together, then publish the
  manifest with the new version and download URL.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, Optional

import requests

from src.version import APP_VERSION

logger = logging.getLogger(__name__)

UPDATE_MANIFEST_URL_ENV = "TRADEBOT0_UPDATE_URL"
DEFAULT_TIMEOUT_SEC = 5.0


def get_manifest_url(explicit_url: Optional[str] = None) -> str:
    """Returns the configured update-manifest URL, or "" when none is set.

    A non-blank explicit argument wins; otherwise the
    TRADEBOT0_UPDATE_URL environment variable is read. The result is
    stripped; an empty string means the update check is disabled.
    """
    if explicit_url and explicit_url.strip():
        return explicit_url.strip()
    return os.environ.get(UPDATE_MANIFEST_URL_ENV, "").strip()


def compare_versions(a: str, b: str) -> int:
    """Compares two version strings, returning -1, 0, or 1.

    Accepts date versions (``YYYY.MM.DD``), semver (``X.Y.Z``), and an
    optional ``v`` prefix. Segments are compared numerically; missing
    segments count as 0, so ``"1.2" == "1.2.0"`` and
    ``"2026.11.13" < "2026.11.20"``. Non-numeric segments count as 0.
    """
    def _parts(version: str) -> tuple:
        text = (version or "").strip()
        if text.startswith(("v", "V")):
            text = text[1:]
        parts = []
        for segment in text.split("."):
            match = re.match(r"(\d+)", segment)
            parts.append(int(match.group(1)) if match else 0)
        return tuple(parts)

    left = _parts(a)
    right = _parts(b)
    width = max(len(left), len(right))
    left = left + (0,) * (width - len(left))
    right = right + (0,) * (width - len(right))
    if left < right:
        return -1
    if left > right:
        return 1
    return 0


def check_for_updates(
    manifest_url: Optional[str] = None,
    current_version: str = APP_VERSION,
    timeout: float = DEFAULT_TIMEOUT_SEC,
) -> Dict[str, Any]:
    """Checks the update manifest for a newer release. Never raises.

    Returns a dict with ``status`` (``not_configured`` / ``up_to_date`` /
    ``update_available`` / ``check_failed``), ``current_version``,
    ``latest_version`` and ``download_url`` (None unless a newer release
    was found), plus ``notes`` when the manifest provides them.
    With no manifest URL configured this returns ``not_configured``
    without issuing any network request.
    """
    result: Dict[str, Any] = {
        "status": "not_configured",
        "current_version": current_version,
        "latest_version": None,
        "download_url": None,
    }
    url = get_manifest_url(manifest_url)
    if not url:
        return result
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        manifest = response.json()
        if not isinstance(manifest, dict):
            raise ValueError("update manifest is not a JSON object")
        latest = str(manifest.get("version") or "").strip()
        if not latest:
            raise ValueError("update manifest has no version")
    except Exception as exc:  # network, HTTP, JSON, or shape errors
        logger.debug("Update check failed: %s", exc)
        result["status"] = "check_failed"
        return result
    result["latest_version"] = latest
    download_url = manifest.get("download_url")
    result["download_url"] = str(download_url).strip() if download_url else None
    notes = manifest.get("notes")
    if notes:
        result["notes"] = str(notes)
    result["status"] = (
        "update_available"
        if compare_versions(latest, current_version) > 0
        else "up_to_date"
    )
    return result
