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
import tempfile
import threading
import time
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
    # Audit 3.21: redeploy when all five strategies are flat. Default ON
    # preserves current behaviour; OFF leaves a flat arena flat.
    "auto_redeploy_when_flat": True,
}

PROVIDER_ENV_MAP: Dict[str, str] = {
    "deepseek": "DEEPSEEK_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "groq": "GROQ_API_KEY",
    "nvidia": "NVIDIA_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}

_OMNI_ENV_QUOTED_RE = re.compile(r"""^(['"])([\s\S]*)\1\s*(?:#.*)?$""")
_OMNI_ENV_INLINE_COMMENT_RE = re.compile(r"\s+#.*$")


def parse_omni_env_line(raw_line: str) -> Optional[Tuple[str, str]]:
    """Parses one .env line mirroring OmniRoute's parseEnvValue.mjs semantics.

    - Matching outer single/double quotes return the inner text verbatim (no
      backslash unescaping, optional trailing ` # comment` stripped).
    - Unquoted values strip trailing inline ` # comment` and outer whitespace.
    """
    line = (raw_line or "").lstrip("\ufeff").strip()
    if not line or line.startswith("#") or "=" not in line:
        return None
    key, raw_val = line.split("=", 1)
    key = key.strip()
    if not key:
        return None
    val = raw_val.strip()
    m = _OMNI_ENV_QUOTED_RE.match(val)
    if m:
        return key, m.group(2)
    return key, _OMNI_ENV_INLINE_COMMENT_RE.sub("", val).strip()


def format_omni_env_value(val: str) -> str:
    """Formats a .env value so OmniRoute's parser round-trips it verbatim.

    Plain values stay unquoted (e.g. `INITIAL_PASSWORD=TestAdmin123`).
    Values containing whitespace, `#`, or leading/trailing quote characters are
    wrapped in matching quotes so inline-comment stripping never truncates them.
    """
    if not val:
        return ""
    needs_quotes = (
        any(ch.isspace() for ch in val)
        or "#" in val
        or val[0] in ("'", '"')
        or val[-1] in ("'", '"')
    )
    if not needs_quotes:
        return val
    if '"' not in val:
        return f'"{val}"'
    if "'" not in val:
        return f"'{val}'"
    return f'"{val}"'


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
        self._io_lock = threading.RLock()
        self._omni_env_cache_key: Optional[Tuple[int, int]] = None
        self._omni_env_cache: Dict[str, str] = {}
        self._config_cache_key: Optional[Tuple[int, int]] = None
        self._config_cache: Optional[Dict[str, Any]] = None

    @staticmethod
    def _atomic_write_text(target: Path, content: str) -> None:
        """Writes content via a unique temp file + fsync + os.replace with brief Windows retry."""
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp_path: Optional[str] = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=str(target.parent),
                prefix=f"{target.name}.",
                suffix=".tmp",
                delete=False,
            ) as f:
                tmp_path = f.name
                f.write(content)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except OSError:
                    pass
            last_err: Optional[Exception] = None
            for attempt in range(4):
                try:
                    os.replace(tmp_path, str(target))
                    tmp_path = None
                    return
                except PermissionError as pe:
                    last_err = pe
                    time.sleep(0.025 * (attempt + 1))
            if last_err is not None:
                raise last_err
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    @staticmethod
    def _strip_outer_quotes(val: str) -> str:
        s = val.strip()
        if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
            return s[1:-1]
        return s

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
        Safely loads system_config.json under _io_lock with (mtime_ns, size) caching.
        If the file is missing, corrupted, or unreadable, returns a valid default
        configuration without crashing.
        """
        with self._io_lock:
            try:
                st = self.config_file.stat()
                key = (st.st_mtime_ns, st.st_size)
            except OSError:
                self._config_cache_key = None
                self._config_cache = None
                return dict(DEFAULT_SYSTEM_CONFIG)

            if key == self._config_cache_key and self._config_cache is not None:
                return dict(self._config_cache)

            for attempt in range(3):
                try:
                    content = self.config_file.read_text(encoding="utf-8")
                    data = json.loads(content)
                    if not isinstance(data, dict):
                        logger.warning("system_config.json is not a JSON object. Using defaults.")
                        return dict(DEFAULT_SYSTEM_CONFIG)
                    config = dict(DEFAULT_SYSTEM_CONFIG)
                    config.update(data)
                    self._config_cache_key = key
                    self._config_cache = config
                    return dict(config)
                except PermissionError as pe:
                    if attempt < 2:
                        time.sleep(0.02 * (attempt + 1))
                        continue
                    logger.warning("Failed to read system_config.json (%s). Using cached/defaults.", pe)
                    return dict(self._config_cache) if self._config_cache is not None else dict(DEFAULT_SYSTEM_CONFIG)
                except Exception as e:
                    logger.warning("Failed to parse system_config.json (%s). Using defaults.", e)
                    return dict(DEFAULT_SYSTEM_CONFIG)
            return dict(DEFAULT_SYSTEM_CONFIG)

    def save_config(self, updates: Dict[str, Any]) -> bool:
        """
        Atomically updates and saves configuration using a unique temporary file.
        Prevents half-written or corrupted state if application terminates unexpectedly.
        """
        try:
            with self._io_lock:
                current = self.load_config()
                current.update(updates)
                content = json.dumps(current, indent=2, ensure_ascii=False)
                self._atomic_write_text(self.config_file, content)
                self._config_cache_key = None
                self._config_cache = None
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
        with self._io_lock:
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
            read_ok = False
            for attempt in range(3):
                try:
                    lines = self.omni_env_file.read_text(encoding="utf-8-sig", errors="replace").splitlines()
                    for line in lines:
                        parsed = parse_omni_env_line(line)
                        if parsed is None:
                            continue
                        k, v = parsed
                        # First-wins mirrors OmniRoute's env loader (if process.env[k] === undefined).
                        if k not in result:
                            result[k] = v
                    read_ok = True
                    break
                except PermissionError as pe:
                    if attempt < 2:
                        time.sleep(0.02 * (attempt + 1))
                        result.clear()
                        continue
                    logger.warning("Could not read omniroute env file: %s", pe)
                    return dict(self._omni_env_cache) if self._omni_env_cache else {}
                except Exception as e:
                    logger.warning("Could not read omniroute env file: %s", e)
                    return {}
            if not read_ok:
                return dict(self._omni_env_cache) if self._omni_env_cache else {}
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
            with self._io_lock:
                self.omni_env_file.parent.mkdir(parents=True, exist_ok=True)
                existing_lines: List[str] = []
                if self.omni_env_file.is_file():
                    try:
                        existing_lines = self.omni_env_file.read_text(encoding="utf-8-sig", errors="replace").splitlines()
                    except Exception as e:
                        logger.error("Refusing to overwrite unreadable omniroute env file: %s", e)
                        return {"ok": False, "error": f"Could not read existing .env safely: {e}"}

                # Build updated line list while preserving ordering and dropping duplicate keys.
                updated_vars: Dict[str, str] = dict(updates)
                written_keys: set = set()
                new_lines: List[str] = []

                for line in existing_lines:
                    stripped = line.lstrip("\ufeff").strip()
                    if stripped and not stripped.startswith("#") and "=" in stripped:
                        var_name, _ = stripped.split("=", 1)
                        var_name = var_name.strip()
                        if var_name in updated_vars:
                            new_lines.append(f"{var_name}={format_omni_env_value(updated_vars.pop(var_name))}")
                            written_keys.add(var_name)
                            continue
                        if var_name in written_keys:
                            continue
                    new_lines.append(line)

                for k, v in updated_vars.items():
                    new_lines.append(f"{k}={format_omni_env_value(v)}")

                self._atomic_write_text(self.omni_env_file, "\n".join(new_lines) + "\n")

                # Drop cache so the next read sees the new content.
                self._omni_env_cache_key = None
                self._omni_env_cache = {}

                # Synchronize provider API keys into current process environment;
                # keep INITIAL_PASSWORD out of process env so child tools never inherit it.
                for env_name, env_val in updates.items():
                    if env_name != "INITIAL_PASSWORD":
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

        if not sanitized_keys:
            return {"ok": True, "updated_count": 0}

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

    def validate_admin_password(self, password: Any) -> Tuple[bool, str]:
        """Validates an admin password without writing to disk.

        Returns (True, cleaned_password) or (False, error_message).
        """
        if not isinstance(password, str):
            return False, "Admin password must be text."
        pw = password.strip()
        if len(pw) < self.ADMIN_PASSWORD_MIN_LENGTH:
            return False, f"Admin password must be at least {self.ADMIN_PASSWORD_MIN_LENGTH} characters."
        if re.search(r"[\r\n\t\x00-\x1f]", pw):
            return False, "Admin password contains invalid characters."
        return True, pw

    def set_admin_password(self, password: Any) -> Dict[str, Any]:
        """
        Writes a user-chosen admin password (INITIAL_PASSWORD) into
        ~/.omniroute/.env, preserving all other variables. The password value
        is never logged or returned. Minimum 8 characters; no control
        characters. Returns {"ok": True} or {"ok": False, "error": ...}.
        """
        ok, pw_or_err = self.validate_admin_password(password)
        if not ok:
            return {"ok": False, "error": pw_or_err}
        res = self._write_omni_env_vars({"INITIAL_PASSWORD": pw_or_err})
        if not res.get("ok"):
            return {"ok": False, "error": res.get("error", "Could not write the admin password.")}
        return {"ok": True}

