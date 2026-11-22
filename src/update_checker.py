"""In-app update check — scaffolding (2026-11-13).

Checks a remote JSON manifest for a newer TradeBot0 release and reports
the result. This module is scaffolding only: it performs the check and
nothing else. There is no download, no install, and no automatic update.

Manifest format (plain HTTPS GET, no login required)::

    {
      "version": "V2.7.0",
      "download_url": "https://example.invalid/TradeBot0Setup.exe",
      "notes": "What changed in this release."
    }

A date-stamped version (``YYYY.MM.DD``) is the superseded scheme from
before the V2.5.3 switch; it always compares older than a ``VX.Y.Z``
version (see :func:`compare_versions`), so a stale date manifest
never offers a bogus update to a V-release app.

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
from urllib.parse import urlparse

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


def _is_date_version(parts: tuple) -> bool:
    """True when a parsed version is a date version (``YYYY.MM.DD``).

    A date version is recognised by a 4-digit year as its first
    segment (1900-2099). The ``v``/``V`` prefix is stripped before
    this check, so ``"v2026.11.13"`` is a date version too.
    """
    return bool(parts) and 1900 <= parts[0] <= 2099


def compare_versions(a: str, b: str) -> int:
    """Compares two version strings, returning -1, 0, or 1.

    Accepts date versions (``YYYY.MM.DD``), semver (``X.Y.Z``), and an
    optional ``v`` prefix. Within one scheme, segments are compared
    numerically; missing segments count as 0, so ``"1.2" == "1.2.0"``
    and ``"2026.11.13" < "2026.11.20"``. Non-numeric segments count
    as 0.

    Across schemes, a date version always compares OLDER than a
    semver: the project switched from date versions to the ``VX.Y.Z``
    scheme at V2.5.3, so ``"2026.11.20"`` belongs to the superseded
    scheme. (Audit 3.14: the old purely-numeric comparison ordered
    them the other way -- 2026 > 2 in the first segment -- so a stale
    date-stamped manifest looked newer than any V release.)
    """
    def _parse(version: str) -> tuple[tuple[int, ...], Optional[str]]:
        text = (version or "").strip()
        if text.startswith(("v", "V")):
            text = text[1:]
        # Strip optional build metadata (+...) and split optional -prerelease suffix.
        text = text.split("+", 1)[0]
        core, _, prerelease = text.partition("-")
        parts = []
        for segment in core.split("."):
            match = re.match(r"(\d+)", segment)
            parts.append(int(match.group(1)) if match else 0)
        return tuple(parts), (prerelease.strip().lower() or None)

    left, left_pre = _parse(a)
    right, right_pre = _parse(b)
    if _is_date_version(left) != _is_date_version(right):
        return -1 if _is_date_version(left) else 1
    width = max(len(left), len(right))
    left = left + (0,) * (width - len(left))
    right = right + (0,) * (width - len(right))
    if left < right:
        return -1
    if left > right:
        return 1
    # Core versions are equal: stable release > pre-release (SemVer 2.0.0 §11).
    if left_pre is None and right_pre is None:
        return 0
    if left_pre is None:
        return 1
    if right_pre is None:
        return -1
    if left_pre < right_pre:
        return -1
    if left_pre > right_pre:
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
    parsed_url = urlparse(url)
    if parsed_url.scheme.lower() != "https" or not parsed_url.netloc:
        logger.debug("Update check rejected non-HTTPS manifest URL: %r", url)
        result["status"] = "check_failed"
        return result
    response = None
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        # Reject HTTPS -> HTTP downgrade redirects (final URL and any redirect hops).
        hops = list(getattr(response, "history", None) or ()) + [response]
        for hop in hops:
            hop_url = getattr(hop, "url", None)
            if isinstance(hop_url, str) and hop_url.strip():
                hop_parsed = urlparse(hop_url.strip())
                if hop_parsed.scheme.lower() != "https" or not hop_parsed.netloc:
                    raise ValueError(f"update check redirected to non-HTTPS URL: {hop_url!r}")
        manifest = response.json()
        if not isinstance(manifest, dict):
            raise ValueError("update manifest is not a JSON object")
        raw_version = manifest.get("version")
        if not isinstance(raw_version, str):
            raise ValueError("update manifest version must be a string")
        latest = raw_version.strip()
        if not latest:
            raise ValueError("update manifest has no version")
    except Exception as exc:  # network, HTTP, JSON, or shape errors
        logger.debug("Update check failed: %s", exc)
        result["status"] = "check_failed"
        return result
    finally:
        if response is not None:
            try:
                response.close()
            except Exception:
                pass
    result["latest_version"] = latest
    status = (
        "update_available"
        if compare_versions(latest, current_version) > 0
        else "up_to_date"
    )
    result["status"] = status
    raw_dl = manifest.get("download_url")
    dl_str = str(raw_dl).strip() if raw_dl else ""
    if status == "update_available" and dl_str:
        dl_parsed = urlparse(dl_str)
        result["download_url"] = dl_str if (dl_parsed.scheme.lower() == "https" and dl_parsed.netloc) else None
    else:
        result["download_url"] = None
    notes = manifest.get("notes")
    if notes:
        result["notes"] = str(notes)
    return result
