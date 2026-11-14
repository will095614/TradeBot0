"""
src/intelligence/config_manager.py - Resilient System Configuration & Key Store
Manages local TradeBot0 configuration and OmniRoute credential synchronization
with atomic file operations, defensive deserialization, and strict input sanitization.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("tradebot0.config_manager")

# NOTE: there is deliberately no "gateway_auto_spawn" option. Offline mode
# was removed, so OmniRoute is required to use the app at all and the
# gateway always auto-launches. A stored False from an older install is
# inert: nothing reads it anymore.
DEFAULT_SYSTEM_CONFIG: Dict[str, Any] = {
    "has_completed_onboarding": False,
    "skip_ai_mode": False,
    "gateway_port": 20128,
    "gateway_host": "127.0.0.1",
    "configured_providers": [],
    "last_setup_ts": 0.0,
    # Audit 3.21: redeploy when all six strategies are flat. Default ON
    # preserves current behaviour; OFF leaves a flat arena flat.
    "auto_redeploy_when_flat": True,
}

PROVIDER_ENV_MAP: Dict[str, str] = {
    "deepseek": "DEEPSEEK_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "groq": "GROQ_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}


class ConfigManager:
    """
    Defensive configuration manager. Handles atomic writes, fallback on corruption,
    and credential persistence for local AI gateways without external dependencies.
    """

    def __init__(self, data_dir: Optional[Path] = None, omni_env_path: Optional[Path] = None) -> None:
        if data_dir is not None:
            self.data_dir = Path(data_dir)
        elif getattr(sys, "frozen", False):
            # Production standalone executable: use user AppData for universal write access
            appdata = os.environ.get("APPDATA")
            base = Path(appdata) / "TradeBot0" if appdata else Path.home() / ".tradebot0"
            self.data_dir = base / "data"
        else:
            self.data_dir = Path(__file__).resolve().parent.parent.parent / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.data_dir / "system_config.json"

        if omni_env_path is not None:
            self.omni_env_file = Path(omni_env_path)
        else:
            home = Path.home()
            self.omni_env_file = home / ".omniroute" / ".env"

        # Audit §5.4: cache of the parsed omni env file, keyed by
        # (mtime_ns, size). The per-second gateway-diagnosis poll must
        # not re-open and re-parse this file 86,400 times a day.
        self._omni_env_cache_key: Optional[Tuple[int, int]] = None
        self._omni_env_cache: Dict[str, str] = {}

    @staticmethod
    def sanitize_key(raw_key: Any) -> str:
        """Strips whitespace, surrounding quotes, and control characters from user input."""
        if not raw_key or not isinstance(raw_key, str):
            return ""
        s = raw_key.strip().strip("'\"").strip()
        # Remove any newlines or dangerous control characters
        s = re.sub(r"[\r\n\t\x00-\x1f]", "", s)
        return s

    def load_config(self) -> Dict[str, Any]:
        """
        Safely loads system_config.json. If the file is missing, corrupted,
        or unreadable, returns a valid default configuration without crashing.
        """
        if not self.config_file.is_file():
            return dict(DEFAULT_SYSTEM_CONFIG)

        try:
            content = self.config_file.read_text(encoding="utf-8")
            data = json.loads(content)
            if not isinstance(data, dict):
                logger.warning("system_config.json is not a JSON object. Using defaults.")
                return dict(DEFAULT_SYSTEM_CONFIG)

            # Ensure all required keys exist
            config = dict(DEFAULT_SYSTEM_CONFIG)
            config.update(data)
            return config
        except Exception as e:
            logger.warning("Failed to parse system_config.json (%s). Using defaults.", e)
            return dict(DEFAULT_SYSTEM_CONFIG)

    def save_config(self, updates: Dict[str, Any]) -> bool:
        """
        Atomically updates and saves configuration using a temporary file.
        Prevents half-written or corrupted state if application terminates unexpectedly.
        """
        try:
            current = self.load_config()
            current.update(updates)

            tmp_file = self.config_file.with_suffix(".tmp")
            content = json.dumps(current, indent=2, ensure_ascii=False)
            tmp_file.write_text(content, encoding="utf-8")
            tmp_file.replace(self.config_file)
            return True
        except Exception as e:
            logger.error("Failed to save system config: %s", e)
            return False

    def get_configured_providers(self) -> List[str]:
        """Returns list of providers that currently have non-empty API keys stored."""
        env_keys = self.read_omniroute_env()
        configured: List[str] = []
        for prov, env_var in PROVIDER_ENV_MAP.items():
            val = env_keys.get(env_var, "").strip() or os.getenv(env_var, "").strip()
            if val and len(val) >= 4:
                configured.append(prov)
        return configured

    def read_omniroute_env(self) -> Dict[str, str]:
        """Safely parses ~/.omniroute/.env file into key-value pairs.

        Audit §5.4: the parsed file is cached by (mtime_ns, size), so
        the per-second gateway-diagnosis poll does not re-open and
        re-parse it 86,400 times a day. A copy is returned, so mutating
        the result cannot poison the cache. The cache is dropped on any
        mtime/size change and after our own writes (_write_omni_env_vars).
        """
        try:
            st = self.omni_env_file.stat()
            key = (st.st_mtime_ns, st.st_size)
        except OSError:
            self._omni_env_cache_key = None
            self._omni_env_cache = {}
            return {}
        if key == self._omni_env_cache_key:
            return dict(self._omni_env_cache)
        result: Dict[str, str] = {}
        try:
            lines = self.omni_env_file.read_text(encoding="utf-8").splitlines()
            for line in lines:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    result[k.strip()] = v.strip().strip("'\"")
        except Exception as e:
            logger.warning("Could not read omniroute env file: %s", e)
            return {}
        self._omni_env_cache_key = key
        self._omni_env_cache = result
        return dict(result)

    def _write_omni_env_vars(self, updates: Dict[str, str]) -> Dict[str, Any]:
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
            tmp_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            tmp_file.replace(self.omni_env_file)

            # Audit §5.4: our own write changes the file; drop the cache
            # so the next read sees the new content even if the mtime
            # granularity ever collides.
            self._omni_env_cache_key = None
            self._omni_env_cache = {}

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
        """True when a non-empty INITIAL_PASSWORD is persisted in the omni env file.
        The file is the source of truth the gateway reads; the process env is
        not consulted, so a password set earlier in this process (for a
        spawned daemon, or by another test) cannot masquerade as a persisted
        password for a fresh install."""
        env_map = self.read_omniroute_env()
        return bool((env_map.get("INITIAL_PASSWORD") or "").strip())

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
        if re.search(r"[\r\n\t\x00-\x1f]", pw):
            return {"ok": False, "error": "Admin password contains invalid characters."}
        res = self._write_omni_env_vars({"INITIAL_PASSWORD": pw})
        if not res.get("ok"):
            return {"ok": False, "error": res.get("error", "Could not write the admin password.")}
        return {"ok": True}

