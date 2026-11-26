"""Update-checker scaffolding tests (2026-11-13): all mocked, zero network.

Covers version comparison, manifest parsing, the not-configured
no-op (requests.get must not be called), and failure handling.
No real URL is ever used; the only URL strings in this file are the
unresolvable .invalid placeholder inside mocked responses.
"""
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.gui.dashboard import ArenaDashboard, _ArenaBridgeApi
from src.update_checker import check_for_updates, compare_versions, get_manifest_url
from src.version import APP_NAME, APP_VERSION


def _mock_response(payload, status_ok=True):
    resp = MagicMock()
    resp.json.return_value = payload
    if status_ok:
        resp.raise_for_status.return_value = None
    else:
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError("404")
    return resp


# ------------------------------------------------------------ version compare
@pytest.mark.parametrize("a,b,expected", [
    ("2026.11.13", "2026.11.13", 0),
    ("2026.11.13", "2026.11.20", -1),
    ("2026.11.20", "2026.11.13", 1),
    ("2026.11.13", "2026.12.01", -1),
    ("2026.11.13", "2027.01.01", -1),
    ("v2026.11.13", "2026.11.13", 0),
    ("V2026.11.13", "2026.11.13", 0),
    ("1.2.3", "1.2.10", -1),
    ("1.2.10", "1.2.3", 1),
    ("1.2", "1.2.0", 0),
    ("1.2", "1.2.1", -1),
    ("2.0.0", "1.9.9", 1),
    ("V2.8.6", "V2.8.7", -1),
    ("V2.8.6", "V2.8.6", 0),
    # Audit 3.14: date versions are the superseded scheme and always
    # compare older than a semver, in either direction.
    ("V2.6.0", "2026.11.20", 1),
    ("2026.11.20", "V2.6.0", -1),
    ("V2.7.0", "2026.12.01", 1),
    ("2026.12.01", "V2.7.0", -1),
    ("v2026.11.13", "V2.6.0", -1),
    ("2.6.0", "2026.11.20", 1),
])
def test_compare_versions(a, b, expected):
    assert compare_versions(a, b) == expected


def test_version_single_source():
    assert APP_NAME == "TradeBot0"
    assert APP_VERSION == "V3.2.1"


def test_iss_version_matches_version_py():
    iss_path = Path(__file__).resolve().parent.parent / "TradeBot0.iss"
    text = iss_path.read_text(encoding="utf-8")
    assert f'#define MyAppVersion "{APP_VERSION}"' in text


# ------------------------------------------------------------ manifest URL
def test_get_manifest_url_prefers_explicit_arg(monkeypatch):
    monkeypatch.setenv("TRADEBOT0_UPDATE_URL", "https://example.invalid/env.json")
    assert get_manifest_url("https://example.invalid/arg.json") == "https://example.invalid/arg.json"
    assert get_manifest_url() == "https://example.invalid/env.json"
    # A blank explicit argument falls back to the environment variable.
    assert get_manifest_url("  ") == "https://example.invalid/env.json"


def test_get_manifest_url_empty_when_unset(monkeypatch):
    monkeypatch.delenv("TRADEBOT0_UPDATE_URL", raising=False)
    assert get_manifest_url() == ""


# ------------------------------------------------------------ check_for_updates
def test_not_configured_makes_no_request(monkeypatch):
    monkeypatch.delenv("TRADEBOT0_UPDATE_URL", raising=False)
    with patch("src.update_checker.requests.get") as mock_get:
        result = check_for_updates()
    mock_get.assert_not_called()
    assert result["status"] == "not_configured"
    assert result["current_version"] == APP_VERSION
    assert result["latest_version"] is None
    assert result["download_url"] is None


def test_update_available_with_manifest(monkeypatch):
    monkeypatch.delenv("TRADEBOT0_UPDATE_URL", raising=False)
    payload = {
        "version": "V9.9.0",
        "download_url": "https://example.invalid/TradeBot0Setup.exe",
        "notes": "Bug fixes.",
    }
    with patch("src.update_checker.requests.get", return_value=_mock_response(payload)) as mock_get:
        result = check_for_updates(manifest_url="https://example.invalid/manifest.json")
    mock_get.assert_called_once_with("https://example.invalid/manifest.json", timeout=5.0)
    assert result["status"] == "update_available"
    assert result["latest_version"] == "V9.9.0"
    assert result["download_url"] == "https://example.invalid/TradeBot0Setup.exe"
    assert result["notes"] == "Bug fixes."
    assert result["current_version"] == APP_VERSION


def test_date_manifest_is_not_newer_than_v_release():
    # Audit 3.14: "2026.11.20" is the superseded date scheme, so it
    # must not offer an update to an app running V2.8.6.
    payload = {"version": "2026.11.20", "download_url": "https://example.invalid/TradeBot0Setup.exe"}
    with patch("src.update_checker.requests.get", return_value=_mock_response(payload)):
        result = check_for_updates(manifest_url="https://example.invalid/manifest.json")
    assert result["status"] == "up_to_date"
    assert result["latest_version"] == "2026.11.20"
    # NOTE: the checker echoes the manifest's download_url even when
    # up_to_date (its docstring claims otherwise -- observed, not part
    # of 3.14, so not asserted here and not changed here).


def test_up_to_date_same_version():
    payload = {"version": APP_VERSION, "download_url": "https://example.invalid/TradeBot0Setup.exe"}
    with patch("src.update_checker.requests.get", return_value=_mock_response(payload)):
        result = check_for_updates(manifest_url="https://example.invalid/manifest.json")
    assert result["status"] == "up_to_date"
    assert result["latest_version"] == APP_VERSION


def test_up_to_date_older_manifest():
    # V1.0.0 is a numbering reset (2026-11-18, first public release):
    # old 2.x versions compare numerically newer than 1.0.0, so the
    # older-manifest fixture uses V0.9.0 instead of V2.5.3.
    payload = {"version": "V0.9.0"}
    with patch("src.update_checker.requests.get", return_value=_mock_response(payload)):
        result = check_for_updates(manifest_url="https://example.invalid/manifest.json")
    assert result["status"] == "up_to_date"
    assert result["download_url"] is None  # no download offered when not newer
    assert "notes" not in result


def test_check_failed_on_network_error():
    with patch("src.update_checker.requests.get", side_effect=requests.exceptions.ConnectionError("down")):
        result = check_for_updates(manifest_url="https://example.invalid/manifest.json")
    assert result["status"] == "check_failed"
    assert result["latest_version"] is None


def test_check_failed_on_http_error():
    with patch("src.update_checker.requests.get", return_value=_mock_response({}, status_ok=False)):
        result = check_for_updates(manifest_url="https://example.invalid/manifest.json")
    assert result["status"] == "check_failed"


def test_check_failed_on_bad_manifest():
    for bad in ({}, {"notes": "no version"}, ["2026.11.20"], "not json"):
        with patch("src.update_checker.requests.get", return_value=_mock_response(bad)):
            result = check_for_updates(manifest_url="https://example.invalid/manifest.json")
        assert result["status"] == "check_failed", f"payload {bad!r} should fail"


def test_check_failed_on_invalid_json():
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.side_effect = ValueError("bad json")
    with patch("src.update_checker.requests.get", return_value=resp):
        result = check_for_updates(manifest_url="https://example.invalid/manifest.json")
    assert result["status"] == "check_failed"


# ------------------------------------------------------------ bridge + startup hook
def test_bridge_check_for_updates_passthrough(monkeypatch):
    monkeypatch.delenv("TRADEBOT0_UPDATE_URL", raising=False)
    dash = ArenaDashboard()
    bridge = _ArenaBridgeApi(dash)
    canned = {
        "status": "update_available",
        "current_version": "2026.11.13",
        "latest_version": "2026.11.20",
        "download_url": "https://example.invalid/x.exe",
    }
    with patch("src.gui.dashboard._run_update_check", return_value=canned):
        assert bridge.check_for_updates() == canned


def test_bridge_check_for_updates_not_configured(monkeypatch):
    monkeypatch.delenv("TRADEBOT0_UPDATE_URL", raising=False)
    dash = ArenaDashboard()
    bridge = _ArenaBridgeApi(dash)
    with patch("src.update_checker.requests.get") as mock_get:
        result = bridge.check_for_updates()
    mock_get.assert_not_called()
    assert result["status"] == "not_configured"


def test_startup_hook_is_noop_without_url(monkeypatch):
    monkeypatch.delenv("TRADEBOT0_UPDATE_URL", raising=False)
    dash = ArenaDashboard()
    with patch("src.gui.dashboard._run_update_check") as mock_check:
        dash._maybe_check_for_updates()
    mock_check.assert_not_called()


def test_startup_hook_runs_in_background_when_configured(monkeypatch):
    monkeypatch.setenv("TRADEBOT0_UPDATE_URL", "https://example.invalid/manifest.json")
    dash = ArenaDashboard()
    with patch("src.gui.dashboard._run_update_check", return_value={"status": "up_to_date"}) as mock_check:
        dash._maybe_check_for_updates()
        # The check runs on a background thread: poll briefly for the call.
        for _ in range(50):
            if mock_check.call_count:
                break
            time.sleep(0.02)
        mock_check.assert_called_once()
