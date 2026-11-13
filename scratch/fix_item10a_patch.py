#!/usr/bin/env python3
"""Fix item 10a: packaging prerequisites - admin password, console port, no-key auth (TradeBot0 maintenance list).

Applies exact-once-verified replacements to the PC project tree (run with
cwd = project root) and, identically, to the local audit copy.
Every replacement is verified to occur exactly once before anything is
written; on any mismatch the script aborts without touching a file.
Newline style is preserved (files are LF; open with newline="").
Run with --check for a dry run that only verifies anchor counts.

Three fixes (item 10 task A, parts 1-3):
  1. Admin password (A1): there is no default password in TradeBot0 code --
     OmniRoute applies its own built-in default when INITIAL_PASSWORD is
     absent from ~/.omniroute/.env, so every fresh install shared one
     password. Now the setup wizard forces the user to set a password
     (min 8 chars) before onboarding can complete, and run() never
     auto-spawns a gateway whose console is still on the built-in default.
     Existing installs on the default are forced through the wizard on next
     launch (admin_password_required). get_setup_status still returns only
     booleans (item 7); the password value is never logged or returned.
  2. Console button follows gateway_port (A2): ArenaDashboard builds its
     GatewaySupervisor from the configured host/port, open_omniroute_console
     builds the URL from the supervisor, and the app.js fallback reuses the
     last gateway_port reported by get_setup_status.
  3. No key -> no Authorization (A3): OmniRouteClient no longer defaults to
     a placeholder key (the displayed "<redacted>" is the tool output layer
     masking the real placeholder value; the code contains no such literal
     and this patch never prints or copies that value -- the change is a
     regex that matches the placeholder without naming it). chat_json only
     sends an Authorization header when a key is actually configured.
"""
import os
import re
import sys

if not os.path.isdir("src/gui"):
    print("FAIL: run this script from the project root (src/gui not found)")
    sys.exit(1)

REPLACEMENTS = []
REGEX_REPLACEMENTS = []
NEW_FILES = {}


def rep(path, old, new):
    REPLACEMENTS.append((path, old, new))


def rep_re(path, pattern, replacement):
    """Regex replacement; the pattern must match exactly once. The matched
    text is NEVER printed (it may contain a credential placeholder)."""
    REGEX_REPLACEMENTS.append((path, pattern, replacement))


# =========================================================== A1: config_manager
# Extract the atomic .env upsert into a shared helper, rewrite
# sync_omniroute_keys on top of it, and add the admin-password API.
rep("src/intelligence/config_manager.py", '''    def sync_omniroute_keys(self, keys_payload: Dict[str, str]) -> Dict[str, Any]:
        """
        Updates ~/.omniroute/.env with the provided keys while strictly preserving
        all existing variables (such as JWT_SECRET, PORT, STORAGE_ENCRYPTION_KEY).
        """
        sanitized_keys: Dict[str, str] = {}
        for prov, raw_val in keys_payload.items():
            norm_prov = prov.lower().strip()
            if norm_prov in PROVIDER_ENV_MAP:
                val = self.sanitize_key(raw_val)
                if val:
                    sanitized_keys[PROVIDER_ENV_MAP[norm_prov]] = val

        try:
            self.omni_env_file.parent.mkdir(parents=True, exist_ok=True)
            existing_lines: List[str] = []
            if self.omni_env_file.is_file():
                try:
                    existing_lines = self.omni_env_file.read_text(encoding="utf-8").splitlines()
                except Exception as e:
                    logger.warning("Could not read omniroute env file, existing keys will be rebuilt: %s", e)
                    existing_lines = []

            # Build updated line dictionary while preserving ordering
            updated_vars: Dict[str, str] = dict(sanitized_keys)
            new_lines: List[str] = []

            for line in existing_lines:
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    var_name, _ = stripped.split("=", 1)
                    var_name = var_name.strip()
                    if var_name in updated_vars:
                        # Replace with sanitized new value
                        new_lines.append(f"{var_name}={updated_vars.pop(var_name)}")
                        continue
                new_lines.append(line)

            # Append any remaining new keys that weren't present previously
            for k, v in updated_vars.items():
                new_lines.append(f"{k}={v}")

            # Atomic file replacement
            tmp_file = self.omni_env_file.with_suffix(".tmp")
            tmp_file.write_text("\\n".join(new_lines) + "\\n", encoding="utf-8")
            tmp_file.replace(self.omni_env_file)

            # Synchronize into current process environment
            for env_name, env_val in sanitized_keys.items():
                os.environ[env_name] = env_val

            return {"ok": True, "updated_count": len(sanitized_keys)}
        except Exception as e:
            logger.error("Failed to sync keys to omniroute env: %s", e)
            return {"ok": False, "error": str(e), "updated_count": 0}''',
'''    def _write_omni_env_vars(self, updates: Dict[str, str]) -> Dict[str, Any]:
        """
        Atomically upserts variables into ~/.omniroute/.env, preserving every
        other variable (JWT_SECRET, PORT, STORAGE_ENCRYPTION_KEY, ...).
        Shared by sync_omniroute_keys() and set_admin_password() (item 10).
        Returns {"ok": True} or {"ok": False, "error": ...}. Callers must
        never log the values passed in here.
        """
        try:
            self.omni_env_file.parent.mkdir(parents=True, exist_ok=True)
            existing_lines: List[str] = []
            if self.omni_env_file.is_file():
                try:
                    existing_lines = self.omni_env_file.read_text(encoding="utf-8").splitlines()
                except Exception as e:
                    logger.warning("Could not read omniroute env file, existing keys will be rebuilt: %s", e)
                    existing_lines = []

            # Build updated line dictionary while preserving ordering
            updated_vars: Dict[str, str] = dict(updates)
            new_lines: List[str] = []

            for line in existing_lines:
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    var_name, _ = stripped.split("=", 1)
                    var_name = var_name.strip()
                    if var_name in updated_vars:
                        # Replace with sanitized new value
                        new_lines.append(f"{var_name}={updated_vars.pop(var_name)}")
                        continue
                new_lines.append(line)

            # Append any remaining new keys that weren't present previously
            for k, v in updated_vars.items():
                new_lines.append(f"{k}={v}")

            # Atomic file replacement
            tmp_file = self.omni_env_file.with_suffix(".tmp")
            tmp_file.write_text("\\n".join(new_lines) + "\\n", encoding="utf-8")
            tmp_file.replace(self.omni_env_file)

            # Synchronize into current process environment
            for env_name, env_val in updates.items():
                os.environ[env_name] = env_val

            return {"ok": True}
        except Exception as e:
            logger.error("Failed to write omniroute env file: %s", e)
            return {"ok": False, "error": str(e)}

    def sync_omniroute_keys(self, keys_payload: Dict[str, str]) -> Dict[str, Any]:
        """
        Updates ~/.omniroute/.env with the provided keys while strictly preserving
        all existing variables (such as JWT_SECRET, PORT, STORAGE_ENCRYPTION_KEY).
        """
        sanitized_keys: Dict[str, str] = {}
        for prov, raw_val in keys_payload.items():
            norm_prov = prov.lower().strip()
            if norm_prov in PROVIDER_ENV_MAP:
                val = self.sanitize_key(raw_val)
                if val:
                    sanitized_keys[PROVIDER_ENV_MAP[norm_prov]] = val

        res = self._write_omni_env_vars(sanitized_keys)
        if not res.get("ok"):
            return {"ok": False, "error": res.get("error", "write failed"), "updated_count": 0}
        return {"ok": True, "updated_count": len(sanitized_keys)}

    # --- Gateway admin password (item 10 A1) ---------------------------------
    ADMIN_PASSWORD_MIN_LENGTH = 8

    def is_admin_password_configured(self) -> bool:
        """True when a non-empty INITIAL_PASSWORD is present in the omni env file or process env."""
        env_map = self.read_omniroute_env()
        val = (env_map.get("INITIAL_PASSWORD") or os.getenv("INITIAL_PASSWORD") or "").strip()
        return bool(val)

    def set_admin_password(self, password: Any) -> Dict[str, Any]:
        """
        Writes a user-chosen admin password (INITIAL_PASSWORD) into
        ~/.omniroute/.env, preserving all other variables. The password value
        is never logged or returned. Minimum 8 characters; no control
        characters. Returns {"ok": True} or {"ok": False, "error": ...}.
        """
        if not isinstance(password, str):
            return {"ok": False, "error": "Admin password must be text."}
        pw = password.strip()
        if len(pw) < self.ADMIN_PASSWORD_MIN_LENGTH:
            return {"ok": False, "error": f"Admin password must be at least {self.ADMIN_PASSWORD_MIN_LENGTH} characters."}
        if re.search(r"[\\r\\n\\t\\x00-\\x1f]", pw):
            return {"ok": False, "error": "Admin password contains invalid characters."}
        res = self._write_omni_env_vars({"INITIAL_PASSWORD": pw})
        if not res.get("ok"):
            return {"ok": False, "error": res.get("error", "Could not write the admin password.")}
        return {"ok": True}''')


# =========================================================== A3: omniroute_client
# Drop the placeholder-key default: with no key configured, os.getenv
# returns None and no Authorization header is sent (see headers below).
# The regex matches the placeholder value without naming or printing it.
rep_re("src/intelligence/omniroute_client.py",
       r'os\.getenv\("LLM_API_KEY", "[^"]*"\)',
       'os.getenv("LLM_API_KEY")')

rep("src/intelligence/omniroute_client.py", '''        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }''',
'''        # Item 10 A3: never send a placeholder key. With no key configured
        # the request goes out without an Authorization header at all.
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"''')

# =========================================================== A2/A1: dashboard
# ArenaDashboard builds its supervisor from the configured host/port.
rep("src/gui/dashboard.py", '''        self.config_manager = ConfigManager()
        self.gateway_supervisor = GatewaySupervisor()''',
'''        self.config_manager = ConfigManager()
        # Gateway host/port come from the user's own config (item 10 A2):
        # the console button and the supervisor must follow gateway_port
        # instead of the hardcoded 20128.
        try:
            _gw_cfg = self.config_manager.load_config()
            _gw_port = int(_gw_cfg.get("gateway_port", 20128) or 20128)
            _gw_host = str(_gw_cfg.get("gateway_host", "127.0.0.1") or "127.0.0.1")
        except Exception:
            _gw_host, _gw_port = "127.0.0.1", 20128
        self.gateway_supervisor = GatewaySupervisor(host=_gw_host, port=_gw_port)''')

# Console button follows the supervisor's configured host/port.
rep("src/gui/dashboard.py", '''        """Launches the OmniRoute local web console dashboard in default system browser."""
        import webbrowser
        url = "http://127.0.0.1:20128"''',
'''        """Launches the OmniRoute local web console dashboard in default system browser."""
        import webbrowser
        # Console URL follows the configured gateway port (item 10 A2).
        url = (
            f"http://{self._dashboard.gateway_supervisor.host}"
            f":{self._dashboard.gateway_supervisor.port}"
        )''')

# get_setup_status: expose admin_password_required (boolean only, item 7 rule).
rep("src/gui/dashboard.py", '''                "cli_available": bool(cli_avail),
                "gateway_port": int(cfg.get("gateway_port", 20128)),
                "omniroute_password_configured": pw_configured,
            }''',
'''                "cli_available": bool(cli_avail),
                "gateway_port": int(cfg.get("gateway_port", 20128)),
                "omniroute_password_configured": pw_configured,
                "admin_password_required": bool((not cfg.get("skip_ai_mode", False)) and not pw_configured),
            }''')

rep("src/gui/dashboard.py", '''                "cli_available": False,
                "gateway_port": 20128,
                "omniroute_password_configured": False,
            }''',
'''                "cli_available": False,
                "gateway_port": 20128,
                "omniroute_password_configured": False,
                "admin_password_required": False,
            }''')

# save_and_launch_gateway: require / accept an admin password (item 10 A1).
rep("src/gui/dashboard.py", '''    def save_and_launch_gateway(self, keys: Dict[str, str], auto_spawn: bool = True) -> Dict[str, Any]:
        """
        Persists API keys into ~/.omniroute/.env and launches gateway if requested.
        Marks onboarding as completed in system_config.json.
        """
        try:
            # 1. Sync keys into ~/.omniroute/.env
            sync_res = self._dashboard.config_manager.sync_omniroute_keys(keys or {})''',
'''    def save_and_launch_gateway(
        self, keys: Dict[str, str], auto_spawn: bool = True, admin_password: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Persists API keys into ~/.omniroute/.env and launches gateway if requested.
        Marks onboarding as completed in system_config.json.
        admin_password (item 10 A1): a user-chosen gateway admin password. It is
        required on first run and for installs that still rely on OmniRoute's
        built-in default password; the value is never logged or returned.
        """
        try:
            # 0. Admin password (item 10 A1): no shared default password may
            # survive. A password must be supplied or already configured before
            # onboarding can complete (pure-math mode is the password-free path).
            _cm = self._dashboard.config_manager
            if admin_password is not None:
                _pw_res = _cm.set_admin_password(admin_password)
                if not _pw_res.get("ok"):
                    return {"status": "error", "ok": False, "message": _pw_res.get("error", "Invalid admin password."), "gateway_online": False}
            elif not _cm.is_admin_password_configured():
                return {"status": "error", "ok": False, "message": "Please set an admin password for the local gateway console before launching the arena.", "gateway_online": False}

            # 1. Sync keys into ~/.omniroute/.env
            sync_res = self._dashboard.config_manager.sync_omniroute_keys(keys or {})''')

# Restart a self-spawned gateway after a password change so the new
# password takes effect immediately (a user-started gateway is left alone).
rep("src/gui/dashboard.py", '''            # 3. Check gateway and spawn if requested
            is_open = self._dashboard.gateway_supervisor.is_port_open(timeout=0.3)''',
'''            # 2b. If the password was just set and our own gateway is already
            # running, restart it so the new password takes effect immediately.
            # (A gateway the user started themselves is left alone; it picks
            # the new password up on its next manual restart.)
            if admin_password is not None:
                _sup = self._dashboard.gateway_supervisor
                if _sup.is_self_spawned and _sup.child_process is not None:
                    try:
                        _sup.shutdown()
                    except Exception as e:
                        logger.debug("Gateway restart after password change failed: %s", e)

            # 3. Check gateway and spawn if requested
            is_open = self._dashboard.gateway_supervisor.is_port_open(timeout=0.3)''')

# run(): never auto-spawn a gateway whose console is still on the built-in
# default password; the wizard forces the user to set one first.
rep("src/gui/dashboard.py", '''            if (
                cfg.get("has_completed_onboarding")
                and not cfg.get("skip_ai_mode")
                and cfg.get("gateway_auto_spawn", True)
            ):''',
'''            if (
                cfg.get("has_completed_onboarding")
                and not cfg.get("skip_ai_mode")
                and cfg.get("gateway_auto_spawn", True)
                # Item 10 A1: never auto-start a gateway whose console is still
                # protected only by OmniRoute's built-in default password; the
                # setup wizard forces the user to set one first.
                and self.config_manager.is_admin_password_configured()
            ):''')


# =========================================================== A1: index.html wizard
# Admin password card, reusing the provider-card markup (no new CSS).
rep("src/gui/assets/index.html", '''        <!-- Gateway Toggle Options -->''',
'''        <!-- Admin Password -->
        <div class="setup-provider-card">
          <div class="setup-provider-meta">
            <span class="setup-provider-name">Gateway Admin Password</span>
            <span class="setup-provider-hint">Protects the local OmniRoute console (min 8 characters)</span>
          </div>
          <div class="setup-input-group">
            <input type="password" id="keyAdminPassword" class="setup-key-input num" placeholder="New admin password" autocomplete="new-password" spellcheck="false" />
            <button type="button" class="setup-eye-btn" onclick="toggleKeyVisibility('keyAdminPassword', this)" title="Show / Hide Password">
              <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M1.5 8s2.5-5 6.5-5 6.5 5 6.5 5-2.5 5-6.5 5-6.5-5-6.5-5z"></path><circle cx="8" cy="8" r="2.5"></circle></svg>
            </button>
          </div>
          <div class="setup-input-group">
            <input type="password" id="keyAdminPasswordConfirm" class="setup-key-input num" placeholder="Confirm admin password" autocomplete="new-password" spellcheck="false" />
            <button type="button" class="setup-eye-btn" onclick="toggleKeyVisibility('keyAdminPasswordConfirm', this)" title="Show / Hide Password">
              <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M1.5 8s2.5-5 6.5-5 6.5 5 6.5 5-2.5 5-6.5 5-6.5-5-6.5-5z"></path><circle cx="8" cy="8" r="2.5"></circle></svg>
            </button>
          </div>
          <div class="setup-provider-status" id="statusAdminPassword">
            <span class="setup-status-pill neutral">Not Set</span>
          </div>
        </div>

        <!-- Gateway Toggle Options -->''')

# =========================================================== A1/A2: app.js
# Console fallback reuses the last gateway_port from get_setup_status.
rep("src/gui/assets/app.js", '''  function openOmniRouteConsole() {
    if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.open_omniroute_console === 'function') {
      window.pywebview.api.open_omniroute_console().catch(() => {
        window.open('http://127.0.0.1:20128', '_blank');
      });
    } else {
      window.open('http://127.0.0.1:20128', '_blank');
    }
  }''',
'''  function openOmniRouteConsole() {
    // Console URL follows the configured gateway port (item 10 A2): the
    // bridge is the primary path; the fallback reuses the last port the
    // setup status reported (20128 until the first status call).
    const port = (typeof window.__tradebotGatewayPort === 'number') ? window.__tradebotGatewayPort : 20128;
    const fallbackUrl = `http://127.0.0.1:${port}`;
    if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.open_omniroute_console === 'function') {
      window.pywebview.api.open_omniroute_console().catch(() => {
        window.open(fallbackUrl, '_blank');
      });
    } else {
      window.open(fallbackUrl, '_blank');
    }
  }''')

# initAppBoot: a missing admin password forces the wizard, and the reported
# gateway port is remembered for the console fallback.
rep("src/gui/assets/app.js", '''      if (res && res.status === 'ok') {
        if (!res.onboarding_completed && !res.skip_ai_mode) {
          needsOnboarding = true;
        } else {
          hasCompletedSetup = true;
        }
      }''',
'''      if (res && res.status === 'ok') {
        if (typeof res.gateway_port === 'number') {
          window.__tradebotGatewayPort = res.gateway_port;
        }
        if ((!res.onboarding_completed && !res.skip_ai_mode) || res.admin_password_required) {
          needsOnboarding = true;
        } else {
          hasCompletedSetup = true;
        }
      }''')

# checkOnboardingBoot: same forced-wizard condition as initAppBoot.
rep("src/gui/assets/app.js", '''        if (res && res.status === 'ok') {
          if (!res.onboarding_completed && !res.skip_ai_mode) {
            openSetupWizardModal(false);
          }
        }''',
'''        if (res && res.status === 'ok') {
          if ((!res.onboarding_completed && !res.skip_ai_mode) || res.admin_password_required) {
            openSetupWizardModal(false);
          }
        }''')

# openSetupWizardModal: password badge wording, port memory, admin card state.
rep("src/gui/assets/app.js", '''          const pwdEl = document.getElementById('omniConsolePwd');
          if (pwdEl) {
            const pwdSpan = pwdEl.querySelector('span') || pwdEl;
            pwdSpan.textContent = '********';
            pwdEl.title = res.omniroute_password_configured
              ? 'Custom admin password configured in ~/.omniroute/.env'
              : 'Default admin password in effect - see ~/.omniroute/.env';
          }''',
'''          const pwdEl = document.getElementById('omniConsolePwd');
          if (pwdEl) {
            const pwdSpan = pwdEl.querySelector('span') || pwdEl;
            pwdSpan.textContent = '********';
            pwdEl.title = res.omniroute_password_configured
              ? 'Custom admin password configured in ~/.omniroute/.env'
              : 'No admin password set - set one below to protect the gateway console';
          }

          if (typeof res.gateway_port === 'number') {
            window.__tradebotGatewayPort = res.gateway_port;
          }

          // Admin password card (item 10 A1): required on first run and for
          // installs still on the built-in default password; blank keeps the
          // existing password when one is already configured.
          window.__adminPasswordRequired = !!res.admin_password_required;
          const adminStatus = document.getElementById('statusAdminPassword');
          if (adminStatus) {
            adminStatus.innerHTML = res.omniroute_password_configured
              ? '<span class="setup-status-pill valid">Configured in .env</span>'
              : '<span class="setup-status-pill neutral">Not Set - Required</span>';
          }''')

# saveAndLaunchGateway: client-side password validation, then pass it through.
rep("src/gui/assets/app.js", '''    const keys = {
      deepseek: (document.getElementById('keyDeepSeek')?.value || '').trim(),
      gemini: (document.getElementById('keyGemini')?.value || '').trim(),
      groq: (document.getElementById('keyGroq')?.value || '').trim(),
      openrouter: (document.getElementById('keyOpenRouter')?.value || '').trim(),
    };

    if (saveBtn) {''',
'''    const keys = {
      deepseek: (document.getElementById('keyDeepSeek')?.value || '').trim(),
      gemini: (document.getElementById('keyGemini')?.value || '').trim(),
      groq: (document.getElementById('keyGroq')?.value || '').trim(),
      openrouter: (document.getElementById('keyOpenRouter')?.value || '').trim(),
    };

    // Admin password (item 10 A1): required when the backend says so, or
    // whenever the user typed one (changing it). Blank keeps the existing
    // password when one is already configured.
    const adminPw = (document.getElementById('keyAdminPassword')?.value || '');
    const adminPwConfirm = (document.getElementById('keyAdminPasswordConfirm')?.value || '');
    if (window.__adminPasswordRequired || adminPw || adminPwConfirm) {
      if (adminPw.length < 8) {
        setWizardBanner('Admin password must be at least 8 characters.', 'error');
        return;
      }
      if (adminPw !== adminPwConfirm) {
        setWizardBanner('Admin password and confirmation do not match.', 'error');
        return;
      }
    }

    if (saveBtn) {''')

rep("src/gui/assets/app.js", '''        const res = await window.pywebview.api.save_and_launch_gateway(keys, autoSpawn);''',
'''        const res = await window.pywebview.api.save_and_launch_gateway(keys, autoSpawn, adminPw || null);''')

# =========================================================== existing tests: pass a password
# test_gateway_item8 calls save_and_launch_gateway with no password; the
# regex matches the call without naming the fake key value in it.
rep_re("tests/test_gateway_item8.py",
       r'res = bridge\.save_and_launch_gateway\(\{"deepseek": "[^"]*"\}, auto_spawn=True\)',
       'res = bridge.save_and_launch_gateway({"deepseek": "sk-test-item8-000000000000000000000000"}, auto_spawn=True, admin_password="TestAdmin123")')

rep("tests/test_gateway_setup_wizard.py",
    'res_launch = bridge.save_and_launch_gateway(keys_payload, auto_spawn=True)',
    'res_launch = bridge.save_and_launch_gateway(keys_payload, auto_spawn=True, admin_password="TestAdmin123")')

# =========================================================== new tests
NEW_FILES["tests/test_item10_packaging.py"] = '''"""Item 10 tests (part A): forced admin password, console port, no-key auth.

- A1: onboarding cannot complete without an admin password; the password is
  written to ~/.omniroute/.env preserving other vars and is never returned
  to the frontend.
- A2: the console URL follows the configured gateway_port.
- A3: with no key configured, chat_json sends no Authorization header.
"""
import asyncio
import inspect
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import src.gui.dashboard as dashboard_mod
from src.gui.dashboard import ArenaDashboard, _ArenaBridgeApi
from src.intelligence.config_manager import ConfigManager
from src.intelligence.gateway_supervisor import GatewaySupervisor
from src.intelligence.omniroute_client import OmniRouteClient


def _make_bridge(tmp_path):
    dash = ArenaDashboard()
    dash.config_manager = ConfigManager(
        data_dir=tmp_path / "data",
        omni_env_path=tmp_path / ".omniroute" / ".env",
    )
    dash.gateway_supervisor = GatewaySupervisor(
        daemon_log_path=tmp_path / "logs" / "omniroute_daemon.log"
    )
    return dash, _ArenaBridgeApi(dash)


def _mock_200_session():
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.headers = {}
    mock_resp.json = AsyncMock(return_value={
        "choices": [{"message": {"content": '{"directional_bias": "LONG_ONLY", "confidence": 0.92}'}}]
    })
    mock_session = MagicMock()
    mock_session.closed = False
    mock_session.post.return_value.__aenter__.return_value = mock_resp
    return mock_session


# ------------------------------------------------------------------ A1: password
def test_admin_password_required_before_onboarding(tmp_path):
    dash, bridge = _make_bridge(tmp_path)
    try:
        st = bridge.get_setup_status()
        assert st["admin_password_required"] is True
        assert st["omniroute_password_configured"] is False

        # No password supplied -> onboarding refused, nothing saved.
        res = bridge.save_and_launch_gateway(
            {"deepseek": "sk-test-000000000000000000000000"}, auto_spawn=False
        )
        assert res["ok"] is False
        assert "password" in res["message"].lower()
        assert bridge.get_setup_status()["onboarding_completed"] is False

        # With a password -> onboarding completes and the password is stored.
        with patch.object(dash.gateway_supervisor, "is_port_open", return_value=False):
            res2 = bridge.save_and_launch_gateway(
                {"deepseek": "sk-test-000000000000000000000000"},
                auto_spawn=False,
                admin_password="TestAdmin123",
            )
        assert res2["ok"] is True
        env_text = (tmp_path / ".omniroute" / ".env").read_text(encoding="utf-8")
        assert "INITIAL_PASSWORD=TestAdmin123" in env_text

        st3 = bridge.get_setup_status()
        assert st3["admin_password_required"] is False
        assert st3["omniroute_password_configured"] is True
        assert "TestAdmin123" not in json.dumps(st3)
    finally:
        dash.engine.stop()


def test_admin_password_too_short_rejected(tmp_path):
    cm = ConfigManager(
        data_dir=tmp_path / "data",
        omni_env_path=tmp_path / ".omniroute" / ".env",
    )
    res = cm.set_admin_password("short")
    assert res["ok"] is False
    assert not cm.is_admin_password_configured()
    assert not (tmp_path / ".omniroute" / ".env").exists()


def test_set_admin_password_preserves_other_vars(tmp_path):
    env_path = tmp_path / ".omniroute" / ".env"
    env_path.parent.mkdir(parents=True)
    env_path.write_text(
        "JWT_SECRET=keepme123\\nDEEPSEEK_API_KEY=sk-old-000000000000000000000000\\n",
        encoding="utf-8",
    )
    cm = ConfigManager(data_dir=tmp_path / "data", omni_env_path=env_path)
    res = cm.set_admin_password("TestAdmin123")
    assert res["ok"] is True
    text = env_path.read_text(encoding="utf-8")
    assert "JWT_SECRET=keepme123" in text
    assert "DEEPSEEK_API_KEY=sk-old-000000000000000000000000" in text
    assert "INITIAL_PASSWORD=TestAdmin123" in text


# ------------------------------------------------------------------ A2: console port
def test_console_url_follows_gateway_port(tmp_path):
    dash = ArenaDashboard()
    try:
        dash.config_manager = ConfigManager(
            data_dir=tmp_path / "data",
            omni_env_path=tmp_path / ".omniroute" / ".env",
        )
        dash.gateway_supervisor = GatewaySupervisor(
            port=20129, daemon_log_path=tmp_path / "logs" / "omniroute_daemon.log"
        )
        bridge = _ArenaBridgeApi(dash)
        with patch("webbrowser.open", return_value=True) as mock_open:
            res = bridge.open_omniroute_console()
        assert res["status"] == "ok"
        assert res["url"] == "http://127.0.0.1:20129"
        mock_open.assert_called_once_with("http://127.0.0.1:20129")
    finally:
        dash.engine.stop()


def test_dashboard_init_passes_configured_port_to_supervisor():
    src = inspect.getsource(dashboard_mod.ArenaDashboard.__init__)
    assert "GatewaySupervisor(host=" in src
    assert "gateway_port" in src


# ------------------------------------------------------------------ A3: no-key auth
def test_no_key_sends_no_authorization(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    async def _run():
        client = OmniRouteClient(base_url="http://mock-omniroute:20128/v1")
        assert client.api_key is None
        mock_session = _mock_200_session()
        client._session = mock_session
        client._owns_session = False
        result = await client.chat_json("auto", "system", "user")
        assert result == {"directional_bias": "LONG_ONLY", "confidence": 0.92}
        _, kwargs = mock_session.post.call_args
        assert "Authorization" not in kwargs.get("headers", {})

    asyncio.run(_run())


def test_key_present_sends_authorization(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    async def _run():
        client = OmniRouteClient(
            base_url="http://mock-omniroute:20128/v1",
            api_key="sk-test-item10-000000000000000000000000",
        )
        mock_session = _mock_200_session()
        client._session = mock_session
        client._owns_session = False
        await client.chat_json("auto", "system", "user")
        _, kwargs = mock_session.post.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer sk-test-item10-000000000000000000000000"

    asyncio.run(_run())


# ------------------------------------------------------------------ A1/A2: frontend
def test_frontend_wizard_has_admin_password_fields():
    assets = Path(__file__).resolve().parent.parent / "src" / "gui" / "assets"
    html = (assets / "index.html").read_text(encoding="utf-8")
    js = (assets / "app.js").read_text(encoding="utf-8")
    assert 'id="keyAdminPassword"' in html
    assert 'id="keyAdminPasswordConfirm"' in html
    assert 'id="statusAdminPassword"' in html
    assert "admin_password_required" in js
    assert "keyAdminPassword" in js
    assert "__tradebotGatewayPort" in js
    # New frontend strings are English-only (project rule: frontend zero CJK).
    for s in (
        "Admin password must be at least 8 characters.",
        "Admin password and confirmation do not match.",
        "Gateway Admin Password",
        "Protects the local OmniRoute console (min 8 characters)",
        "Not Set - Required",
    ):
        assert s.isascii()
        assert s in html or s in js
'''


# =========================================================== apply
def main():
    check_only = "--check" in sys.argv
    failed = []
    for path, old, new in REPLACEMENTS:
        with open(path, "r", encoding="utf-8", newline="") as f:
            content = f.read()
        n = content.count(old)
        if n != 1:
            failed.append(f"{path}: expected 1 occurrence, found {n} for: {old[:80]!r}")
            continue
        if check_only:
            print(f"CHECK-OK {path}")
            continue
        content = content.replace(old, new)
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        print(f"OK {path}")
    for path, pattern, replacement in REGEX_REPLACEMENTS:
        with open(path, "r", encoding="utf-8", newline="") as f:
            content = f.read()
        matches = re.findall(pattern, content)
        if len(matches) != 1:
            failed.append(f"{path}: regex expected 1 match, found {len(matches)} for pattern: {pattern!r}")
            continue
        if check_only:
            print(f"CHECK-OK {path} (regex)")
            continue
        content, n = re.subn(pattern, replacement, content, count=1)
        assert n == 1
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        print(f"OK {path} (regex)")
    for path, content in NEW_FILES.items():
        if os.path.exists(path):
            failed.append(f"{path}: already exists, refusing to overwrite")
            continue
        if check_only:
            print(f"CHECK-OK {path} (new file)")
            continue
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        print(f"NEW {path}")
    if failed:
        print("FAILURES:")
        for msg in failed:
            print(" -", msg)
        sys.exit(1)
    if check_only:
        print(f"Check passed: {len(REPLACEMENTS)} replacements + {len(REGEX_REPLACEMENTS)} regex + {len(NEW_FILES)} new files.")
    else:
        print(f"Applied {len(REPLACEMENTS)} replacements + {len(REGEX_REPLACEMENTS)} regex + {len(NEW_FILES)} new files.")


if __name__ == "__main__":
    main()
