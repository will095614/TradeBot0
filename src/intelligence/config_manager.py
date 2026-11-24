"""
src/intelligence/config_manager.py - Resilient System Configuration & Key Store
Manages local TradeBot0 configuration and Google Gemini API credentials
with atomic file operations, defensive deserialization, and strict input sanitization.
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("tradebot0.config_manager")

ALLOWED_GEMINI_MODELS = (
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
)
DEFAULT_GEMINI_MODEL = "gemini-3.1-flash-lite"

DEFAULT_SYSTEM_CONFIG: Dict[str, Any] = {
    "has_completed_onboarding": False,
    "skip_ai_mode": False,
    "gemini_api_key": "",
    "gemini_model": DEFAULT_GEMINI_MODEL,
    "preload_intel_articles": True,
    "last_setup_ts": 0.0,
    "legacy_omniroute_migrated": False,
    "legacy_runtime_cleaned": False,
    # Audit 3.21: redeploy when all five strategies are flat. Default ON
    # preserves current behaviour; OFF leaves a flat arena flat.
    "auto_redeploy_when_flat": True,
}

_ENV_QUOTED_RE = re.compile(r"""^(['"])([\s\S]*)\1\s*(?:#.*)?$""")
_ENV_INLINE_COMMENT_RE = re.compile(r"\s+#.*$")


def _extract_env_var_from_file(env_path: Path, target_key: str) -> str:
    """Reads a single variable from a legacy .env file without modifying or logging it."""
    if not env_path or not env_path.is_file():
        return ""
    try:
        lines = env_path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    except OSError:
        return ""
    for raw_line in lines:
        line = (raw_line or "").lstrip("\ufeff").strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, raw_val = line.split("=", 1)
        if k.strip() != target_key:
            continue
        val = raw_val.strip()
        m = _ENV_QUOTED_RE.match(val)
        if m:
            return m.group(2)
        return _ENV_INLINE_COMMENT_RE.sub("", val).strip()
    return ""


class ConfigManager:
    """
    Defensive configuration manager. Handles atomic writes, fallback on corruption,
    and Gemini API key persistence without external dependencies.
    """

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        self._custom_data_dir = data_dir is not None
        if data_dir is not None:
            self.data_dir = Path(data_dir)
        elif getattr(sys, "frozen", False):
            appdata = os.environ.get("APPDATA")
            base = Path(appdata) / "TradeBot0" if appdata else Path.home() / ".tradebot0"
            self.data_dir = base / "data"
        else:
            self.data_dir = Path(__file__).resolve().parent.parent.parent / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.data_dir / "system_config.json"

        self._io_lock = threading.RLock()
        self._config_cache_key: Optional[tuple[int, int]] = None
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

    def get_gemini_api_key(self) -> str:
        """Returns sanitized Gemini API key from system_config.json or GEMINI_API_KEY env."""
        cfg = self.load_config()
        stored = self.sanitize_key(cfg.get("gemini_api_key", ""))
        if stored:
            return stored
        return self.sanitize_key(os.getenv("GEMINI_API_KEY", ""))

    def has_gemini_api_key(self) -> bool:
        """True when a plausible non-empty Gemini API key is configured."""
        return len(self.get_gemini_api_key()) >= 4

    def set_gemini_api_key(self, raw_key: Any) -> Dict[str, Any]:
        """Sanitizes and persists the Gemini API key in system_config.json and process env."""
        cleaned = self.sanitize_key(raw_key if isinstance(raw_key, str) else "")
        ok = self.save_config({"gemini_api_key": cleaned})
        if not ok:
            return {"ok": False, "error": "Failed to persist Gemini API key.", "configured": False}
        if cleaned:
            os.environ["GEMINI_API_KEY"] = cleaned
        else:
            os.environ.pop("GEMINI_API_KEY", None)
        return {"ok": True, "configured": len(cleaned) >= 4}

    def migrate_legacy_omniroute_once(
        self,
        legacy_env_path: Optional[Path] = None,
        legacy_runtime_dir: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """One-time upgrade helper for V2.x -> V3.0.0 installs.

        Imports GEMINI_API_KEY from ~/.omniroute/.env if system_config.json has none yet
        (without touching or deleting ~/.omniroute), and removes the orphaned local
        %LOCALAPPDATA%\\TradeBot0\\runtime folder once.
        """
        if legacy_env_path is None and legacy_runtime_dir is None and os.environ.get("PYTEST_CURRENT_TEST"):
            return {"imported_key": False, "cleaned_runtime": False}

        cfg = self.load_config()
        updates: Dict[str, Any] = {}
        imported = False
        cleaned_runtime = False

        if not cfg.get("legacy_omniroute_migrated", False):
            env_path = (
                Path(legacy_env_path)
                if legacy_env_path is not None
                else (None if self._custom_data_dir else (Path.home() / ".omniroute" / ".env"))
            )
            if env_path is not None and not self.sanitize_key(cfg.get("gemini_api_key", "")):
                legacy_key = self.sanitize_key(_extract_env_var_from_file(env_path, "GEMINI_API_KEY"))
                if legacy_key:
                    updates["gemini_api_key"] = legacy_key
                    os.environ["GEMINI_API_KEY"] = legacy_key
                    imported = True
                    logger.info("Imported legacy GEMINI_API_KEY into system_config.json")
            updates["legacy_omniroute_migrated"] = True

        if not cfg.get("legacy_runtime_cleaned", False):
            rt_dir: Optional[Path] = None
            if legacy_runtime_dir is not None:
                rt_dir = Path(legacy_runtime_dir)
            elif not self._custom_data_dir and getattr(sys, "frozen", False):
                local_app = os.environ.get("LOCALAPPDATA")
                if local_app:
                    rt_dir = Path(local_app) / "TradeBot0" / "runtime"
            if rt_dir is not None and rt_dir.exists() and rt_dir.is_dir():
                try:
                    shutil.rmtree(rt_dir, ignore_errors=True)
                    cleaned_runtime = not rt_dir.exists()
                    logger.info("Cleaned legacy AI runtime directory: %s (removed=%s)", rt_dir, cleaned_runtime)
                except Exception as exc:
                    logger.debug("Legacy runtime cleanup skipped (%s): %s", rt_dir, exc)
            updates["legacy_runtime_cleaned"] = True

        if updates:
            # Strip dead V2.x gateway keys opportunistically if present
            for stale_key in ("gateway_port", "gateway_host", "configured_providers"):
                if stale_key in cfg:
                    cfg.pop(stale_key, None)
            cfg.update(updates)
            with self._io_lock:
                content = json.dumps(cfg, indent=2, ensure_ascii=False)
                self._atomic_write_text(self.config_file, content)
                self._config_cache_key = None
                self._config_cache = None

        return {"imported_key": imported, "cleaned_runtime": cleaned_runtime}

    @staticmethod
    def sanitize_model_name(raw_model: Any) -> str:
        candidate = str(raw_model or "").strip()
        if candidate.lower().startswith("gemini/"):
            candidate = candidate[len("gemini/"):].strip()
        return candidate

    def get_gemini_model(self) -> str:
        """Returns the persisted Gemini model ID, falling back to DEFAULT_GEMINI_MODEL."""
        cfg = self.load_config()
        candidate = self.sanitize_model_name(cfg.get("gemini_model", DEFAULT_GEMINI_MODEL))
        return candidate if candidate in ALLOWED_GEMINI_MODELS else DEFAULT_GEMINI_MODEL

    def set_gemini_model(self, raw_model: Any) -> Dict[str, Any]:
        """Validates and persists the selected Gemini model ID."""
        candidate = self.sanitize_model_name(raw_model)
        if candidate not in ALLOWED_GEMINI_MODELS:
            return {
                "ok": False,
                "error": f"Unsupported Gemini model: {raw_model!r}",
                "allowed_models": list(ALLOWED_GEMINI_MODELS),
            }
        if not self.save_config({"gemini_model": candidate}):
            return {"ok": False, "error": "Failed to persist Gemini model preference."}
        return {"ok": True, "gemini_model": candidate}

    def get_preload_intel_articles(self) -> bool:
        """Returns whether background article preloading is enabled."""
        cfg = self.load_config()
        val = cfg.get("preload_intel_articles", True)
        return True if val is None else bool(val)

    def set_preload_intel_articles(self, enabled: Any) -> Dict[str, Any]:
        """Persists the background article preload preference."""
        flag = bool(enabled)
        if not self.save_config({"preload_intel_articles": flag}):
            return {"ok": False, "error": "Failed to persist article preload preference."}
        return {"ok": True, "preload_intel_articles": flag}
