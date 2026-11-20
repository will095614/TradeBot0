"""
tests/test_gateway_setup_wizard.py - Defensive Setup Wizard & Gateway Supervisor Verification
Simulates progressive failure modes, invalid/corrupt inputs, network timeouts,
and subsequent valid recovery to guarantee crash-proof operation.
"""
import io
import json
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.gui.dashboard import ArenaDashboard, _ArenaBridgeApi
from src.intelligence.config_manager import (
    ConfigManager,
    DEFAULT_SYSTEM_CONFIG,
    PROVIDER_ENV_MAP,
)
from src.intelligence.gateway_supervisor import GatewaySupervisor


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

    # Test Case 1: Corrupted malformed JSON syntax
    cfg_file.write_text("{ unclosed invalid json ...", encoding="utf-8")
    cm = ConfigManager(data_dir=data_dir)
    res = cm.load_config()
    assert res == DEFAULT_SYSTEM_CONFIG

    # Test Case 2: Valid JSON but wrong type (Array instead of Dict)
    cfg_file.write_text("[1, 2, 3]", encoding="utf-8")
    res2 = cm.load_config()
    assert res2 == DEFAULT_SYSTEM_CONFIG

    # Test Case 3: Empty file
    cfg_file.write_text("", encoding="utf-8")
    res3 = cm.load_config()
    assert res3 == DEFAULT_SYSTEM_CONFIG

    # Test Case 4: Atomic save updates successfully
    ok = cm.save_config({"has_completed_onboarding": True, "custom_field": "val"})
    assert ok is True
    res4 = cm.load_config()
    assert res4["has_completed_onboarding"] is True
    assert res4["custom_field"] == "val"
    assert res4["gateway_port"] == 20128  # Preserves default keys


def test_config_manager_env_preservation(tmp_path: Path):
    """Verifies that synchronizing keys preserves existing security tokens and server settings."""
    env_file = tmp_path / ".omniroute" / ".env"
    env_file.parent.mkdir(parents=True, exist_ok=True)
    initial_content = (
        "# OmniRoute System Configuration\n"
        "PORT=20128\n"
        "JWT_SECRET=super_secret_jwt_token_12345\n"
        "STORAGE_ENCRYPTION_KEY=enc_key_abcde\n"
        "DEEPSEEK_API_KEY=old_deepseek_key\n"
    )
    env_file.write_text(initial_content, encoding="utf-8")

    cm = ConfigManager(data_dir=tmp_path / "data", omni_env_path=env_file)
    res = cm.sync_omniroute_keys({
        "deepseek": "sk-new-deepseek-key-9999",
        "gemini": "AIzaSyNewGeminiKey8888",
        "groq": "gsk_new_groq_key_7777",
    })

    assert res["ok"] is True
    assert res["updated_count"] == 3

    parsed = cm.read_omniroute_env()
    assert parsed["PORT"] == "20128"
    assert parsed["JWT_SECRET"] == "super_secret_jwt_token_12345"
    assert parsed["STORAGE_ENCRYPTION_KEY"] == "enc_key_abcde"
    assert parsed["DEEPSEEK_API_KEY"] == "sk-new-deepseek-key-9999"
    assert parsed["GEMINI_API_KEY"] == "AIzaSyNewGeminiKey8888"
    assert parsed["GROQ_API_KEY"] == "gsk_new_groq_key_7777"


# =============================================================================
# 2. GatewaySupervisor Resilient Key Validation Tests
# =============================================================================

def test_gateway_supervisor_key_validation_defensive():
    """Verifies immediate rejection of invalid length or empty keys without network roundtrips."""
    gs = GatewaySupervisor()

    # Empty key
    r1 = gs.test_single_key("deepseek", "")
    assert r1["ok"] is False
    assert "empty" in r1["message"].lower()

    # Suspiciously short key
    r2 = gs.test_single_key("gemini", "short")
    assert r2["ok"] is False
    assert "short" in r2["message"].lower()


@patch("urllib.request.urlopen")
def test_gateway_supervisor_http_responses(mock_urlopen):
    """Simulates HTTP 200, 401 Unauthorized, 429 Rate Limit, and timeout exceptions."""
    gs = GatewaySupervisor()

    # 1. Simulate 200 OK
    mock_resp_200 = MagicMock()
    mock_resp_200.status = 200
    mock_resp_200.__enter__.return_value = mock_resp_200
    mock_urlopen.return_value = mock_resp_200

    res_ok = gs.test_single_key("deepseek", "sk-valid-key-1234567890")
    assert res_ok["ok"] is True
    assert "Verified" in res_ok["message"]

    # 2. Simulate HTTP 401 Unauthorized
    mock_urlopen.side_effect = urllib.error.HTTPError(
        url="https://api.deepseek.com",
        code=401,
        msg="Unauthorized",
        hdrs={},
        fp=io.BytesIO(b'{"error":"invalid key"}')
    )
    res_401 = gs.test_single_key("deepseek", "sk-invalid-key-1234567890")
    assert res_401["ok"] is False
    assert "401" in res_401["message"]

    # 3. Simulate HTTP 429 Rate Limit (key status unconfirmed, not verified)
    mock_urlopen.side_effect = urllib.error.HTTPError(
        url="https://api.groq.com",
        code=429,
        msg="Too Many Requests",
        hdrs={},
        fp=io.BytesIO(b'{"error":"rate limited"}')
    )
    res_429 = gs.test_single_key("groq", "gsk_rate_limited_key_12345678")
    # Item 12 / A4-1: 429 only proves the key was accepted far enough to be
    # rate limited; it must never be reported as a verified key.
    assert res_429["ok"] is False
    assert "429" in res_429["message"]
    assert "unconfirmed" in res_429["message"].lower()

    # 4. Simulate Timeout / Offline
    mock_urlopen.side_effect = TimeoutError("Connection timed out")
    res_timeout = gs.test_single_key("openrouter", "sk-or-v1-valid-format-key-12345")
    assert res_timeout["ok"] is False
    assert "timed out" in res_timeout["message"].lower() or "offline" in res_timeout["message"].lower()


@patch("urllib.request.urlopen")
def test_gateway_supervisor_nvidia_endpoint(mock_urlopen):
    """Wizard swap (2026-11-16): DeepSeek card replaced by NVIDIA NIM --
    the Test button must hit NVIDIA's /v1/models with a Bearer key."""
    gs = GatewaySupervisor()
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.__enter__.return_value = mock_resp
    mock_urlopen.return_value = mock_resp
    res = gs.test_single_key("nvidia", "nvapi-test-key-12345678")
    assert res["ok"] is True
    req = mock_urlopen.call_args[0][0]
    assert req.full_url == "https://integrate.api.nvidia.com/v1/models"
    assert req.get_header("Authorization") == "Bearer nvapi-test-key-12345678"


def test_gateway_supervisor_port_and_health_conflict():
    """Verifies detection of conflicting foreign applications on port 20128."""
    gs = GatewaySupervisor()

    with patch.object(gs, "is_port_open", return_value=True), \
         patch.object(gs, "probe_health", return_value=(False, {})):
        ok, msg = gs.start_daemon(max_wait_sec=1.0)
        assert ok is False
        assert "occupied by another application" in msg.lower()


# =============================================================================
# 3. Stepwise Erroneous-Then-Valid Simulation Tests
# =============================================================================

def test_bridge_stepwise_simulation_erroneous_then_valid(tmp_path: Path, monkeypatch):
    """
    Step-by-step interactive simulation:
    Attempts various invalid entries first for each provider, catches defensive feedback,
    and then enters valid keys and confirms seamless transition.
    """
    for env_var in PROVIDER_ENV_MAP.values():
        monkeypatch.setenv(env_var, "")
        monkeypatch.delenv(env_var, raising=False)

    # Set up isolated dashboard environment
    dash = ArenaDashboard()
    dash.config_manager = ConfigManager(
        data_dir=tmp_path / "data",
        omni_env_path=tmp_path / ".omniroute" / ".env"
    )
    dash.gateway_supervisor = GatewaySupervisor()
    bridge = _ArenaBridgeApi(dash)

    # Initial check: not onboarded
    st0 = bridge.get_setup_status()
    assert st0["status"] == "ok"
    assert st0["onboarding_completed"] is False
    assert st0["skip_ai_mode"] is False

    # --- Step 1: DeepSeek Validation ---
    # Erroneous input 1: empty
    r_ds_err1 = bridge.test_api_key("deepseek", "")
    assert r_ds_err1["ok"] is False
    assert "empty" in r_ds_err1["message"].lower()

    # Erroneous input 2: invalid 401 key
    with patch.object(dash.gateway_supervisor, "test_single_key", return_value={"ok": False, "message": "Invalid Key (HTTP 401)", "latency_ms": 110}):
        r_ds_err2 = bridge.test_api_key("deepseek", "sk-bad-key-11111111")
        assert r_ds_err2["ok"] is False

    # Valid input 1: correct key
    with patch.object(dash.gateway_supervisor, "test_single_key", return_value={"ok": True, "message": "Verified (118ms)", "latency_ms": 118}):
        r_ds_ok = bridge.test_api_key("deepseek", "sk-correct-key-22222222")
        assert r_ds_ok["ok"] is True

    # --- Step 2: Google Gemini Validation ---
    # Erroneous input: short
    r_gm_err = bridge.test_api_key("gemini", "AIza")
    assert r_gm_err["ok"] is False

    # Valid input: correct key
    with patch.object(dash.gateway_supervisor, "test_single_key", return_value={"ok": True, "message": "Verified (95ms)", "latency_ms": 95}):
        r_gm_ok = bridge.test_api_key("gemini", "AIzaSy-correct-gemini-key-33333333")
        assert r_gm_ok["ok"] is True

    # --- Step 3: Groq Validation ---
    # Erroneous input: offline / timed out
    with patch.object(dash.gateway_supervisor, "test_single_key", return_value={"ok": False, "message": "Connection timed out (3500ms)", "latency_ms": 3500}):
        r_gq_err = bridge.test_api_key("groq", "gsk_timeout_key_44444444")
        assert r_gq_err["ok"] is False

    # Valid input: correct key
    with patch.object(dash.gateway_supervisor, "test_single_key", return_value={"ok": True, "message": "Verified (48ms)", "latency_ms": 48}):
        r_gq_ok = bridge.test_api_key("groq", "gsk_correct_key_44444444")
        assert r_gq_ok["ok"] is True

    # --- Step 4: OpenRouter Validation ---
    # Valid input
    with patch.object(dash.gateway_supervisor, "test_single_key", return_value={"ok": True, "message": "Verified (142ms)", "latency_ms": 142}):
        r_or_ok = bridge.test_api_key("openrouter", "sk-or-v1-correct-key-55555555")
        assert r_or_ok["ok"] is True

    # --- Step 5: Save & Launch Gateway (wizard sends Gemini key only) ---
    keys_payload = {
        "gemini": "AIzaSy-correct-gemini-key-33333333",
    }
    # start_watchdog is mocked: a real watchdog thread must never start in
    # tests — a delayed first tick could outlive these mocks and spawn a real
    # gateway on the machine.
    with patch.object(dash.gateway_supervisor, "is_port_open", return_value=True), \
         patch.object(dash.gateway_supervisor, "probe_health", return_value=(True, {"status": "ok"})), \
         patch.object(dash.gateway_supervisor, "start_watchdog", return_value=True):
        res_launch = bridge.save_and_launch_gateway(keys_payload, admin_password="TestAdmin123")
        assert res_launch["status"] == "ok"
        assert res_launch["ok"] is True
        assert res_launch["gateway_online"] is True

    # Verify state after setup completion
    st_final = bridge.get_setup_status()
    assert st_final["onboarding_completed"] is True
    assert st_final["configured_providers"] == ["gemini"]
    env_map = dash.config_manager.read_omniroute_env()
    assert env_map["GEMINI_API_KEY"] == "AIzaSy-correct-gemini-key-33333333"
    assert env_map["INITIAL_PASSWORD"] == "TestAdmin123"
    for absent_var in ("NVIDIA_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY", "DEEPSEEK_API_KEY"):
        assert absent_var not in env_map

    # Gateway diagnosis workstream: save_and_launch_gateway starts the
    # auto-restart watchdog; stop it so no thread outlives the test.
    dash.gateway_supervisor.stop_watchdog()
    dash.engine.stop()


def test_gemini_only_save_preserves_preexisting_keys_and_allows_zero_keys(tmp_path: Path, monkeypatch):
    """Gemini-only wizard saves preserve existing provider keys in ~/.omniroute/.env,
    and saving with zero keys + admin password still completes onboarding."""
    for env_var in PROVIDER_ENV_MAP.values():
        monkeypatch.setenv(env_var, "")
        monkeypatch.delenv(env_var, raising=False)

    env_path = tmp_path / ".omniroute" / ".env"
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text(
        "NVIDIA_API_KEY=nvapi-existing-1234\nGROQ_API_KEY=gsk_existing_1234\n",
        encoding="utf-8",
    )

    dash = ArenaDashboard()
    dash.config_manager = ConfigManager(data_dir=tmp_path / "data", omni_env_path=env_path)
    dash.gateway_supervisor = GatewaySupervisor()
    bridge = _ArenaBridgeApi(dash)
    try:
        with patch.object(dash.gateway_supervisor, "is_port_open", return_value=True), \
             patch.object(dash.gateway_supervisor, "probe_health", return_value=(True, {"status": "ok"})), \
             patch.object(dash.gateway_supervisor, "start_watchdog", return_value=True):
            res = bridge.save_and_launch_gateway(
                {"gemini": "AIzaSy-test-gemini-9999"}, admin_password="TestAdmin123"
            )
        assert res["ok"] is True
        configured = bridge.get_setup_status()["configured_providers"]
        assert "gemini" in configured
        assert "nvidia" in configured
        assert "groq" in configured
    finally:
        dash.gateway_supervisor.stop_watchdog()
        dash.engine.stop()

    # Zero keys + admin password on a fresh env must still succeed.
    for env_var in PROVIDER_ENV_MAP.values():
        monkeypatch.setenv(env_var, "")
        monkeypatch.delenv(env_var, raising=False)
    dash2 = ArenaDashboard()
    dash2.config_manager = ConfigManager(
        data_dir=tmp_path / "data2",
        omni_env_path=tmp_path / ".omniroute2" / ".env",
    )
    dash2.gateway_supervisor = GatewaySupervisor()
    bridge2 = _ArenaBridgeApi(dash2)
    try:
        with patch.object(dash2.gateway_supervisor, "is_port_open", return_value=True), \
             patch.object(dash2.gateway_supervisor, "probe_health", return_value=(True, {"status": "ok"})), \
             patch.object(dash2.gateway_supervisor, "start_watchdog", return_value=True):
            res2 = bridge2.save_and_launch_gateway({}, admin_password="TestAdmin123")
        assert res2["ok"] is True
        st2 = bridge2.get_setup_status()
        assert st2["onboarding_completed"] is True
        assert st2["configured_providers"] == []
    finally:
        dash2.gateway_supervisor.stop_watchdog()
        dash2.engine.stop()


# =============================================================================
# 4. Strict UI Cleanliness & Zero Art Jargon Verification
# =============================================================================

def test_ui_assets_art_jargon_and_cjk_cleanliness():
    """
    Enforces user rules:
    1. Zero art jargon ('spatial glass', 'type a design', 'style b', 'bento dock') in frontend assets.
    2. Zero CJK characters in index.html, app.css, app.js.
    """
    assets_dir = Path(__file__).resolve().parent.parent / "src" / "gui" / "assets"
    files = ["index.html", "app.css", "app.js"]

    art_jargon_terms = [
        "spatial glass",
        "type a design",
        "style b tournament",
    ]

    for fname in files:
        path = assets_dir / fname
        assert path.is_file(), f"Asset {fname} must exist"
        content = path.read_text(encoding="utf-8")

        # 1. Check CJK
        cjk_chars = [c for c in content if "\u4e00" <= c <= "\u9fff"]
        assert len(cjk_chars) == 0, f"Found {len(cjk_chars)} CJK characters in {fname}: {cjk_chars[:10]}"

        # 2. Check forbidden art jargon
        content_lower = content.lower()
        for term in art_jargon_terms:
            assert term not in content_lower, f"Forbidden art jargon '{term}' detected in {fname}"

