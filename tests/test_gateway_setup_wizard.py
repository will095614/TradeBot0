"""
tests/test_gateway_setup_wizard.py - Gemini Setup Wizard & ConfigManager Verification
Simulates progressive failure modes, invalid/corrupt inputs, network timeouts,
close confirmation, compact non-scrolling modal rules, and valid recovery.
"""
import io
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.gui.dashboard import ArenaDashboard, _ArenaBridgeApi
from src.intelligence.config_manager import ConfigManager, DEFAULT_SYSTEM_CONFIG
from src.intelligence.gemini_client import probe_gemini_api_key

_ASSETS = Path(__file__).resolve().parent.parent / "src" / "gui" / "assets"


# =============================================================================
# 1. ConfigManager Resilient Input & Persistence Tests
# =============================================================================

def test_config_manager_input_sanitization():
    """Verifies strict input sanitization stripping quotes, whitespace, and control chars."""
    assert ConfigManager.sanitize_key("") == ""
    assert ConfigManager.sanitize_key(None) == ""
    assert ConfigManager.sanitize_key("   ") == ""
    assert ConfigManager.sanitize_key("  'sk-123456789'  ") == "sk-123456789"
    assert ConfigManager.sanitize_key('  "AIzaSy-987654321"  ') == "AIzaSy-987654321"
    assert ConfigManager.sanitize_key("sk-test\r\n\tcontrol\x00key") == "sk-testcontrolkey"


def test_config_manager_atomic_recovery_from_corruption(tmp_path: Path):
    """Verifies that corrupted, empty, or non-dict system_config.json safely falls back to defaults."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    cfg_file = data_dir / "system_config.json"

    cfg_file.write_text("{ unclosed invalid json ...", encoding="utf-8")
    cm = ConfigManager(data_dir=data_dir)
    assert cm.load_config() == DEFAULT_SYSTEM_CONFIG

    cfg_file.write_text("[1, 2, 3]", encoding="utf-8")
    assert cm.load_config() == DEFAULT_SYSTEM_CONFIG

    cfg_file.write_text("", encoding="utf-8")
    assert cm.load_config() == DEFAULT_SYSTEM_CONFIG

    ok = cm.save_config({"has_completed_onboarding": True, "custom_field": "val"})
    assert ok is True
    res4 = cm.load_config()
    assert res4["has_completed_onboarding"] is True
    assert res4["custom_field"] == "val"
    assert "gemini_api_key" in res4


def test_config_manager_gemini_key_persistence(tmp_path: Path, monkeypatch):
    """Verifies set_gemini_api_key persists cleaned keys into system_config.json."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    cm = ConfigManager(data_dir=tmp_path / "data")
    res = cm.set_gemini_api_key('  "AIzaSyNewGeminiKey8888"  ')
    assert res["ok"] is True
    assert res["configured"] is True
    assert cm.has_gemini_api_key() is True
    assert cm.get_gemini_api_key() == "AIzaSyNewGeminiKey8888"


# =============================================================================
# 2. Direct Gemini Key Probe Validation Tests
# =============================================================================

def test_gemini_key_probe_validation_defensive():
    """Verifies immediate rejection of invalid length or empty keys without network roundtrips."""
    r1 = probe_gemini_api_key("")
    assert r1["ok"] is False
    assert "empty" in r1["message"].lower()

    r2 = probe_gemini_api_key("short")
    assert r2["ok"] is False
    assert "short" in r2["message"].lower()


@patch("urllib.request.urlopen")
def test_gemini_key_probe_http_responses(mock_urlopen):
    """Simulates HTTP 200, 401 Unauthorized, 429 Rate Limit, and timeout exceptions."""
    mock_resp_200 = MagicMock()
    mock_resp_200.status = 200
    mock_resp_200.__enter__.return_value = mock_resp_200
    mock_urlopen.return_value = mock_resp_200

    res_ok = probe_gemini_api_key("AIzaSyValidKey1234567890")
    assert res_ok["ok"] is True
    assert "Verified" in res_ok["message"]

    mock_urlopen.side_effect = urllib.error.HTTPError(
        url="https://generativelanguage.googleapis.com/v1beta/models",
        code=401,
        msg="Unauthorized",
        hdrs={},
        fp=io.BytesIO(b'{"error":"invalid key"}'),
    )
    res_401 = probe_gemini_api_key("AIzaSyInvalidKey1234567890")
    assert res_401["ok"] is False
    assert "401" in res_401["message"]

    mock_urlopen.side_effect = urllib.error.HTTPError(
        url="https://generativelanguage.googleapis.com/v1beta/models",
        code=429,
        msg="Too Many Requests",
        hdrs={},
        fp=io.BytesIO(b'{"error":"rate limited"}'),
    )
    res_429 = probe_gemini_api_key("AIzaSyRateLimitedKey12345")
    assert res_429["ok"] is False
    assert "429" in res_429["message"]
    assert "unconfirmed" in res_429["message"].lower()

    mock_urlopen.side_effect = TimeoutError("Connection timed out")
    res_timeout = probe_gemini_api_key("AIzaSyTimeoutKey1234567890")
    assert res_timeout["ok"] is False
    assert "timed out" in res_timeout["message"].lower() or "offline" in res_timeout["message"].lower()


# =============================================================================
# 3. Stepwise Erroneous-Then-Valid Simulation Tests
# =============================================================================

def test_bridge_stepwise_simulation_erroneous_then_valid(tmp_path: Path, monkeypatch):
    """Attempts invalid entries first, checks feedback, then saves a valid Gemini key."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    dash = ArenaDashboard()
    dash.config_manager = ConfigManager(data_dir=tmp_path / "data")
    bridge = _ArenaBridgeApi(dash)
    try:
        st0 = bridge.get_setup_status()
        assert st0["status"] == "ok"
        assert st0["onboarding_completed"] is False
        assert st0["skip_ai_mode"] is False

        r_err1 = bridge.test_api_key("gemini", "")
        assert r_err1["ok"] is False
        assert "empty" in r_err1["message"].lower()

        r_err2 = bridge.test_api_key("gemini", "AIza")
        assert r_err2["ok"] is False

        with patch("src.gui.dashboard.probe_gemini_api_key", return_value={"ok": True, "message": "Verified (95ms)", "latency_ms": 95}):
            r_ok = bridge.test_api_key("gemini", "AIzaSy-correct-gemini-key-33333333")
            assert r_ok["ok"] is True

            res_launch = bridge.save_and_launch({"gemini": "AIzaSy-correct-gemini-key-33333333"})
            assert res_launch["status"] == "ok"
            assert res_launch["ok"] is True
            assert res_launch["ai_online"] is True

        st_final = bridge.get_setup_status()
        assert st_final["onboarding_completed"] is True
        assert st_final["gemini_key_configured"] is True
        assert dash.config_manager.get_gemini_api_key() == "AIzaSy-correct-gemini-key-33333333"
    finally:
        dash.engine.stop()


def test_blank_save_allows_standby_mode(tmp_path: Path, monkeypatch):
    """Saving with zero keys enters Pure Math standby cleanly."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    dash = ArenaDashboard()
    dash.config_manager = ConfigManager(data_dir=tmp_path / "data")
    bridge = _ArenaBridgeApi(dash)
    try:
        res = bridge.save_and_launch({})
        assert res["ok"] is True
        st = bridge.get_setup_status()
        assert st["onboarding_completed"] is True
        assert st["gemini_key_configured"] is False
    finally:
        dash.engine.stop()


# =============================================================================
# 4. Wizard Close Confirmation & Non-Scrolling Layout Contracts
# =============================================================================

def test_wizard_close_confirm_dialog():
    """Wizard close confirmation warns that the typed API key will not be saved."""
    html = (_ASSETS / "index.html").read_text(encoding="utf-8")
    js = (_ASSETS / "app.js").read_text(encoding="utf-8")

    assert 'id="wizardCloseConfirmModal"' in html
    assert "Your API key will not be saved." in html
    assert "function requestCloseSetupWizardModal(" in js
    assert 'onclick="requestCloseSetupWizardModal()"' in html


def test_wizard_vertical_content_sized_layout():
    """Setup wizard keeps non-scrolling vertical layout and omits deleted gateway UI."""
    html = (_ASSETS / "index.html").read_text(encoding="utf-8")
    css = (_ASSETS / "app.css").read_text(encoding="utf-8")

    for removed_id in (
        'id="envNodePill"',
        'id="envOmniRoutePill"',
        'id="gatewayRuntimeActionWrap"',
        'id="setupInstallProgressWrap"',
        'id="gatewayUnavailableNote"',
    ):
        assert removed_id not in html

    modal_rule = css.split(".setup-wizard-modal {", 1)[1].split("}", 1)[0]
    assert "overflow-y: hidden;" in modal_rule
    assert "@media (max-height: 720px)" in css


# =============================================================================
# 5. Strict UI Cleanliness & Zero Art Jargon Verification
# =============================================================================

def test_ui_assets_art_jargon_and_cjk_cleanliness():
    """Enforces zero forbidden art jargon and zero CJK characters in frontend assets."""
    files = ["index.html", "app.css", "app.js"]
    art_jargon_terms = ["spatial glass", "type a design", "style b tournament"]

    for fname in files:
        path = _ASSETS / fname
        assert path.is_file(), f"Asset {fname} must exist"
        content = path.read_text(encoding="utf-8")

        cjk_chars = [c for c in content if "\u4e00" <= c <= "\u9fff"]
        assert len(cjk_chars) == 0, f"Found {len(cjk_chars)} CJK characters in {fname}: {cjk_chars[:10]}"

        content_lower = content.lower()
        for term in art_jargon_terms:
            assert term not in content_lower, f"Forbidden art jargon '{term}' detected in {fname}"
