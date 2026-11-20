from __future__ import annotations

import logging
import os
import pathlib
import sys
import threading
import time
from decimal import Decimal
from typing import Any, Dict, Optional

from src.data.live_engine import LiveArenaEngine
from src.intelligence.config_manager import ConfigManager
from src.intelligence.gateway_supervisor import GatewaySupervisor
from src.update_checker import check_for_updates as _run_update_check
from src.update_checker import get_manifest_url
from src.version import APP_VERSION

logger = logging.getLogger(__name__)

WINDOW_TITLE = f"TradeBot0 {APP_VERSION}"


def _get_native_hwnd(window: Any) -> Optional[int]:
    """Best-effort native window handle (WinForms HWND on Windows).

    Prefers the live handle pywebview already holds; returns None when the
    window has no native handle yet (headless tests, not-yet-shown window).
    """
    try:
        native = getattr(window, "native", None)
        if native is not None and getattr(native, "Handle", None) is not None:
            return int(native.Handle.ToInt64())
    except Exception as e:
        logger.debug("Failed to read native window handle: %s", e)
    return None


def _get_assets_dir() -> pathlib.Path:
    if hasattr(sys, "_MEIPASS"):
        return pathlib.Path(sys._MEIPASS) / "src" / "gui" / "assets"
    return pathlib.Path(__file__).parent / "assets"


_ASSETS_DIR = _get_assets_dir()


def _load_asset(filename: str) -> str:
    path = _ASSETS_DIR / filename
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    logger.error("Asset file not found: %s", path)
    return ""


def _build_html_template() -> str:
    html = _load_asset("index.html")
    css = _load_asset("app.css")
    js = _load_asset("app.js")
    if not html:
        logger.critical("Failed to load index.html from assets!")
        return "<html><body>Asset loading failed</body></html>"
    return html.replace("/* __APP_CSS__ */", css).replace("/* __APP_JS__ */", js)


HTML_TEMPLATE = _build_html_template()


def _copy_text_to_clipboard_windows(text: str) -> bool:
    """Best-effort copy of text to the Windows clipboard via ctypes.

    Returns False on non-Windows or any failure; never raises and never
    logs the text (it may be a password). The clipboard takes ownership
    of the allocated memory on success, so it is freed only on failure.
    """
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        # 64-bit Windows: ctypes defaults every foreign return type to
        # c_int, which truncates the 64-bit HGLOBAL handle; GlobalLock
        # then fails on the truncated handle and the copy silently
        # returns False (2026-11-13: the password-copy button never
        # worked for this reason). Declare the real signatures.
        kernel32.GlobalAlloc.restype = ctypes.c_void_p
        kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalUnlock.restype = wintypes.BOOL
        kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalFree.restype = ctypes.c_void_p
        kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
        user32.OpenClipboard.restype = wintypes.BOOL
        user32.OpenClipboard.argtypes = [wintypes.HWND]
        user32.EmptyClipboard.restype = wintypes.BOOL
        user32.EmptyClipboard.argtypes = []
        user32.SetClipboardData.restype = ctypes.c_void_p
        user32.SetClipboardData.argtypes = [wintypes.UINT, ctypes.c_void_p]
        user32.CloseClipboard.restype = wintypes.BOOL
        user32.CloseClipboard.argtypes = []
        CF_UNICODETEXT = 13
        GMEM_MOVEABLE = 0x0002
        data = text.encode("utf-16-le") + b"\x00\x00"
        hglobal = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not hglobal:
            return False
        owned_by_clipboard = False
        try:
            locked = kernel32.GlobalLock(hglobal)
            if not locked:
                return False
            try:
                ctypes.memmove(locked, data, len(data))
            finally:
                kernel32.GlobalUnlock(hglobal)
            opened = False
            for _ in range(5):
                if user32.OpenClipboard(None):
                    opened = True
                    break
                time.sleep(0.02)
            if not opened:
                return False
            try:
                user32.EmptyClipboard()
                if not user32.SetClipboardData(CF_UNICODETEXT, hglobal):
                    return False
                owned_by_clipboard = True
            finally:
                user32.CloseClipboard()
            return True
        finally:
            if not owned_by_clipboard:
                kernel32.GlobalFree(hglobal)
    except Exception as e:
        logger.debug("Clipboard copy failed: %s", e)
        return False


class _ArenaBridgeApi:
    """
    Native Python <-> WebView2 GPU Frontend Bridge.
    Exposes zero-latency state polling and interactive controls to the HiDPI UI.
    """

    def __init__(self, dashboard: "ArenaDashboard") -> None:
        self._dashboard = dashboard
        # Save & Launch stage reporting: the wizard polls this while the
        # synchronous save_and_launch_gateway call runs, so the user sees
        # which step is running instead of a frozen button. Percentages
        # are stage milestones, never measured time; 100% is set only
        # when the call is about to return ok.
        self._save_launch_lock = threading.Lock()
        self._save_launch_exec_lock = threading.Lock()
        self._save_launch_stage = {
            "status": "idle",
            "message": "",
            "progress": None,
            "phase": "",
        }

    def get_state(self) -> Dict[str, Any]:
        state = self._dashboard.engine.get_ui_state()
        self._inject_gateway_diagnosis(state)
        return state

    def get_state_delta(self, force_full: bool = False) -> Dict[str, Any]:
        state = self._dashboard.engine.get_ui_state_delta(force_full=force_full)
        self._inject_gateway_diagnosis(state)
        return state

    def _inject_gateway_diagnosis(self, state: Dict[str, Any]) -> None:
        """Adds the gateway diagnosis to the Intel Hub payload of a state
        dict the frontend polls (get_state / get_state_delta, every 1 s).
        Never raises; a state without an intel_hub payload is left alone.
        The delta publisher only ever omits candles/fills, so intel_hub
        is present on every poll."""
        try:
            diagnosis = self._dashboard.get_gateway_diagnosis()
            intel = state.get("intel_hub")
            if not isinstance(intel, dict):
                return
            omni = intel.get("omniroute")
            if not isinstance(omni, dict):
                return
            omni["diagnosis"] = diagnosis
        except Exception as e:
            logger.debug("Gateway diagnosis injection failed: %s", e)

    def evolve_now(self) -> Dict[str, Any]:
        """Runs a manual evolution on a background thread so the UI never blocks.

        The old version ran the whole genetic evolution synchronously on the
        bridge thread: the frontend waited on the call and the UI froze until
        evolution finished. Now it returns the current state immediately and
        the evolution runs in a daemon thread; the next state poll picks up
        the new generation. A second click while one is running is ignored.
        """
        with self._dashboard._evolution_lock:
            if not self._dashboard._evolution_running:
                self._dashboard._evolution_running = True
                try:
                    threading.Thread(target=self._run_manual_evolve, daemon=True).start()
                except Exception as e:
                    self._dashboard._evolution_running = False
                    logger.error("Failed to start manual evolution thread: %s", e)
            running_flag = self._dashboard._evolution_running
        state = self.get_state()
        state["evolution_running"] = running_flag
        return state

    def _run_manual_evolve(self) -> None:
        try:
            self._dashboard.engine.evolve_now(trigger="manual")
        except Exception as e:
            logger.error("Manual evolution failed: %s", e)
        finally:
            with self._dashboard._evolution_lock:
                self._dashboard._evolution_running = False

    def toggle_pause(self) -> Dict[str, Any]:
        self._dashboard.engine.paused = not self._dashboard.engine.paused
        return self.get_state()

    def toggle_auto_evolve(self) -> Dict[str, Any]:
        self._dashboard.engine.toggle_auto_evolve()
        return self.get_state()

    def set_evolve_interval(self, seconds: int) -> Dict[str, Any]:
        self._dashboard.engine.set_auto_evolve_interval(seconds)
        return self.get_state()

    def reset_arena(self) -> Dict[str, Any]:
        self._dashboard.reset_engine()
        return self.get_state()

    def start_live_trading(self) -> Dict[str, Any]:
        cfg = self._dashboard.config_manager.load_config()
        if not cfg.get("has_completed_onboarding") and not cfg.get("skip_ai_mode"):
            logger.warning("Rejecting start_live_trading: onboarding not completed.")
            return {"status": "blocked", "message": "Onboarding required"}
        res = self._dashboard.engine.start_live_trading()
        state = self.get_state()
        if isinstance(res, dict):
            state["start_result"] = res
        return state

    def refresh_intel_digest(self) -> Dict[str, Any]:
        self._dashboard.engine.trigger_intel_refresh_async()
        return self.get_state()

    def get_event_article(self, event_id: str) -> Dict[str, Any]:
        """Returns the ~1000-word article for one intel event (Phase A).

        First expand generates it via the ingest model and caches it on
        the event; later calls return the cache without another LLM call.
        Gateway or LLM failure returns {"ok": False, "reason": ...} --
        never a fabricated article. Never raises.
        """
        try:
            return self._dashboard.engine.macro_commander.get_event_article(event_id)
        except Exception as e:
            logger.error("Event article fetch failed for %s: %s", event_id, e)
            return {"ok": False, "event_id": event_id, "state": "failed", "reason": str(e) or e.__class__.__name__}

    def toggle_fullscreen(self) -> bool:
        if self._dashboard.window:
            self._dashboard.window.toggle_fullscreen()
            return True
        return False

    def cancel_shutdown_prompt(self) -> Dict[str, Any]:
        self._dashboard.closing_prompt_active = False
        return {"status": "cancelled"}

    def shutdown(self, save_progress: bool = True) -> Dict[str, Any]:
        logger.info("Shutdown requested from UI bridge (save_progress=%s)", save_progress)
        if save_progress:
            try:
                self._dashboard.engine.save_session_state()
            except Exception as e:
                logger.error("Error saving session state on shutdown: %s", e)
        self._dashboard.allow_exit = True
        try:
            self._dashboard.engine.stop()
        except Exception as e:
            logger.error("Error stopping engine on shutdown: %s", e)
        if self._dashboard.window:
            # Close on the calling thread: window.destroy() must run on the
            # UI thread, and the old background-thread destroy was a
            # use-after-free / deadlock risk on WinForms (item 7).
            self._dashboard.close_window()
        return {"status": "shutting_down", "saved": save_progress}

    def open_omniroute_console(self) -> Dict[str, Any]:
        """Launches the OmniRoute local web console dashboard in default system browser."""
        import webbrowser
        # Console URL follows the configured gateway port (item 10 A2).
        url = (
            f"http://{self._dashboard.gateway_supervisor.host}"
            f":{self._dashboard.gateway_supervisor.port}"
        )
        try:
            webbrowser.open(url)
            logger.info("Launched OmniRoute console in system browser: %s", url)
            return {"status": "ok", "url": url}
        except Exception as e:
            logger.error("Failed to open OmniRoute console: %s", e)
            return {"status": "error", "message": str(e)}

    def open_external_url(self, url: str) -> Dict[str, Any]:
        """Opens an approved provider key page in the system browser.

        AI panels (W2): the setup wizard's "Get a key" link. Only the
        Google Gemini API key page is allowed; anything else is refused
        and never opened. Never raises.
        """
        import webbrowser

        allowed = {
            "https://aistudio.google.com/apikey",
        }
        if url not in allowed:
            return {"status": "error", "message": "URL not allowed"}
        try:
            webbrowser.open(url)
            logger.info("Opened provider key page in system browser: %s", url)
            return {"status": "ok", "url": url}
        except Exception as e:
            logger.error("Failed to open provider key page: %s", e)
            return {"status": "error", "message": str(e)}

    def copy_omniroute_password(self) -> Dict[str, Any]:
        """Copies the OmniRoute admin password to the OS clipboard.

        The password value never enters the frontend (item 7): it is read
        from INITIAL_PASSWORD in ~/.omniroute/.env server-side, copied
        via the OS clipboard, and only the success status is returned
        so the frontend can show "copied!". The value is never logged.
        """
        try:
            env_map = self._dashboard.config_manager.read_omniroute_env()
        except Exception as e:
            logger.error("Failed to read omniroute env for password copy: %s", e)
            return {"status": "error", "message": "could not read password store"}
        password = (env_map.get("INITIAL_PASSWORD") or "").strip()
        if not password:
            return {"status": "error", "message": "password not configured"}
        try:
            ok = _copy_text_to_clipboard_windows(password)
        except Exception as e:
            logger.error("Failed to copy OmniRoute password to clipboard: %s", e)
            return {"status": "error", "message": str(e)}
        if not ok:
            return {"status": "error", "message": "clipboard unavailable"}
        return {"status": "ok"}

    def check_for_updates(self) -> Dict[str, Any]:
        """Checks whether a newer TradeBot0 release is available.

        Scaffolding (2026-11-13): the check runs only when a manifest
        URL is configured (env TRADEBOT0_UPDATE_URL). With no URL
        configured — the case today — this returns
        {"status": "not_configured"} and issues no network request.
        No download or install happens here; the frontend only reads
        the status. Never raises.
        """
        try:
            return _run_update_check()
        except Exception as e:
            logger.debug("Bridge update check failed: %s", e)
            return {
                "status": "check_failed",
                "current_version": APP_VERSION,
                "latest_version": None,
                "download_url": None,
            }

    def get_setup_status(self) -> Dict[str, Any]:
        """
        Returns initialization and credential setup status for the UI wizard.
        Fail-safe: never raises an unhandled exception.
        """
        try:
            cfg = self._dashboard.config_manager.load_config()
            configured = self._dashboard.config_manager.get_configured_providers()
            is_open = self._dashboard.gateway_supervisor.is_port_open(timeout=0.3)
            healthy = False
            if is_open:
                healthy, _ = self._dashboard.gateway_supervisor.probe_health(timeout=0.6)

            cli_avail = self._dashboard.gateway_supervisor.is_cli_available()

            # Never send any password value to the frontend: the old code
            # returned the admin password (default or configured) in plain
            # text to JavaScript. The UI only needs to know whether a custom
            # password has been configured in ~/.omniroute/.env (item 7).
            env_map = self._dashboard.config_manager.read_omniroute_env()
            pw_configured = bool(env_map.get("INITIAL_PASSWORD"))

            return {
                "status": "ok",
                "onboarding_completed": bool(cfg.get("has_completed_onboarding", False)),
                "skip_ai_mode": bool(cfg.get("skip_ai_mode", False)),
                "gateway_online": bool(healthy),
                "port_open": bool(is_open),
                "configured_providers": configured,
                "cli_available": bool(cli_avail),
                "gateway_port": int(cfg.get("gateway_port", 20128)),
                "omniroute_password_configured": pw_configured,
                "admin_password_required": bool((not cfg.get("skip_ai_mode", False)) and not pw_configured),
                "node_available": bool(self._dashboard.gateway_supervisor.node_available()),
                "omniroute_installed": bool(self._dashboard.gateway_supervisor.omniroute_installed()),
                "gateway_unavailable_reason": self._dashboard.gateway_supervisor.gateway_unavailable_reason(),
                "runtime_install_status": self._dashboard.gateway_supervisor.install_runtime_status(),
            }
        except Exception as e:
            logger.error("Error reading setup status: %s", e)
            return {
                "status": "error",
                "error": str(e),
                "onboarding_completed": False,
                "skip_ai_mode": False,
                "gateway_online": False,
                "port_open": False,
                "configured_providers": [],
                "cli_available": False,
                "gateway_port": 20128,
                "omniroute_password_configured": False,
                "admin_password_required": False,
                "node_available": False,
                "omniroute_installed": False,
                "gateway_unavailable_reason": None,
                "runtime_install_status": {"status": "idle", "message": "", "progress": None, "phase": ""},
            }

    def test_api_key(self, provider: str, key: str) -> Dict[str, Any]:
        """
        Live-probes an individual API key with defensive 3.5s timeout.
        Returns ok status, latency, and sanitized descriptive message.
        """
        try:
            return self._dashboard.gateway_supervisor.test_single_key(provider, key)
        except Exception as e:
            logger.error("Error testing API key (%s): %s", provider, e)
            return {"ok": False, "message": f"Verification failed: {e}", "latency_ms": 0}

    def _set_save_launch_stage(
        self, status: str, message: str,
        progress: Optional[int] = None, phase: str = "",
    ) -> None:
        """Records the current Save & Launch step for the wizard poll loop.

        Mirrors GatewaySupervisor._set_install_status: the stage dict is
        the single source of truth the frontend polls while the
        synchronous save_and_launch_gateway call runs (pywebview runs
        each JS bridge call on its own thread, so the poll is served
        concurrently). Progress values are stage milestones, never a
        measured percent; 100 is set only when the call is about to
        return ok.
        """
        with self._save_launch_lock:
            self._save_launch_stage = {
                "status": status,
                "message": message,
                "progress": progress,
                "phase": phase,
            }

    def get_save_launch_status(self) -> Dict[str, Any]:
        """Current Save & Launch stage for the wizard poll loop.

        Fail-safe: never raises. Returns a copy so the caller cannot
        mutate the stored stage.
        """
        try:
            with self._save_launch_lock:
                return dict(self._save_launch_stage)
        except Exception as e:
            logger.debug("Save launch status read failed: %s", e)
            return {"status": "idle", "message": "", "progress": None, "phase": ""}

    def save_and_launch_gateway(
        self, keys: Dict[str, str], admin_password: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Persists API keys into ~/.omniroute/.env and always launches the
        gateway: auto-launch is mandatory (offline mode was removed, so
        OmniRoute is required to use the app at all). Marks onboarding as
        completed in system_config.json.
        admin_password (item 10 A1): a user-chosen gateway admin password. It is
        required on first run and for installs that still rely on OmniRoute's
        built-in default password; the value is never logged or returned.
        """
        with self._save_launch_exec_lock:
            try:
                # Fresh stage for this run: a previous save's "done" must never
                # leak into the new run's progress bar.
                self._set_save_launch_stage("idle", "", None, "")

                # 0. Validate admin password (item 10 A1) without mutating .env yet,
                # so a failed SQLite password sync cannot leave .env and storage.sqlite
                # out of sync.
                _cm = self._dashboard.config_manager
                if admin_password is not None:
                    self._set_save_launch_stage("saving-password", "Saving password...", 10, "password")
                    _pw_ok, _pw_val_or_err = _cm.validate_admin_password(admin_password)
                    if not _pw_ok:
                        self._set_save_launch_stage("failed", _pw_val_or_err, 10, "password")
                        return {"status": "error", "ok": False, "message": _pw_val_or_err, "gateway_online": False}
                elif not _cm.is_admin_password_configured():
                    self._set_save_launch_stage("failed", "Please set an admin password for the local gateway console before launching the arena.", None, "password")
                    return {"status": "error", "ok": False, "message": "Please set an admin password for the local gateway console before launching the arena.", "gateway_online": False}

                # 1. Sync keys into ~/.omniroute/.env
                self._set_save_launch_stage("syncing-keys", "Connecting AI services...", 25, "keys")
                sync_res = self._dashboard.config_manager.sync_omniroute_keys(keys or {})
                if isinstance(sync_res, dict) and sync_res.get("ok") is False:
                    err_msg = str(sync_res.get("error") or "Failed to save API keys.")
                    self._set_save_launch_stage("failed", err_msg, 25, "keys")
                    return {"status": "error", "ok": False, "message": err_msg, "gateway_online": False}

                # 2. If a password was supplied, stop the watchdog & any self-spawned
                # gateway first (to avoid SQLite lock/cache staleness or a watchdog
                # respawn mid-update), apply the password directly into OmniRoute's
                # storage.sqlite via CLI, and only then persist INITIAL_PASSWORD to .env.
                if admin_password is not None:
                    _sup = self._dashboard.gateway_supervisor
                    try:
                        _sup.stop_watchdog()
                    except Exception as e:
                        logger.debug("Watchdog pause before password sync failed: %s", e)
                    with _sup._daemon_lock:
                        _needs_restart = bool(
                            (_sup.is_self_spawned and _sup.child_process is not None)
                            or _sup._daemon_starting
                        )
                    if _needs_restart:
                        self._set_save_launch_stage("restarting-gateway", "Restarting AI services...", 40, "gateway")
                        try:
                            _sup.shutdown()
                        except Exception as e:
                            logger.debug("Gateway restart after password change failed: %s", e)
                    _pw_sync = _sup.sync_admin_password(
                        admin_password,
                        data_dir=_cm.omni_env_file.parent,
                    )
                    if isinstance(_pw_sync, dict) and _pw_sync.get("ok") is False:
                        err_msg = str(_pw_sync.get("error") or "Failed to apply admin password to OmniRoute.")
                        self._set_save_launch_stage("failed", err_msg, 40, "password")
                        return {"status": "error", "ok": False, "message": err_msg, "gateway_online": False}
                    _pw_res = _cm.set_admin_password(admin_password)
                    if not _pw_res.get("ok"):
                        err_msg = _pw_res.get("error", "Could not write the admin password.")
                        self._set_save_launch_stage("failed", err_msg, 45, "password")
                        return {"status": "error", "ok": False, "message": err_msg, "gateway_online": False}

                # 2b. Update system config
                self._set_save_launch_stage("saving-config", "Saving setup...", 55, "config")
                configured = self._dashboard.config_manager.get_configured_providers()
                cfg_saved = self._dashboard.config_manager.save_config({
                    "has_completed_onboarding": True,
                    "skip_ai_mode": False,
                    "configured_providers": configured,
                    "last_setup_ts": time.time(),
                })
                if cfg_saved is False:
                    err_msg = "Failed to save system configuration."
                    self._set_save_launch_stage("failed", err_msg, 55, "config")
                    return {"status": "error", "ok": False, "message": err_msg, "gateway_online": False}

                # 3. Check gateway and spawn if requested
                is_open = self._dashboard.gateway_supervisor.is_port_open(timeout=0.3)
                healthy = False
                msg = "Credentials saved successfully."

                if is_open:
                    self._set_save_launch_stage("connecting-gateway", "Connecting to AI services...", 70, "gateway")
                    healthy, _ = self._dashboard.gateway_supervisor.probe_health(timeout=0.6)
                    if healthy:
                        msg = "AI services connected."
                else:
                    # Auto-launch is mandatory (offline mode removed): the gateway
                    # is always started when the port is not already open.
                    self._set_save_launch_stage("starting-gateway", "Starting AI services...", 70, "gateway")
                    spawn_ok, spawn_msg = self._dashboard.gateway_supervisor.start_daemon(max_wait_sec=30.0)
                    healthy = spawn_ok
                    # AI panels (W5): the success message is the plain
                    # "AI services connected."; the detailed spawn message
                    # is kept only for the failure path, where it explains
                    # what went wrong.
                    msg = "AI services connected." if spawn_ok else spawn_msg

                # 4. Start engine live loop if held in onboarding standby
                self._set_save_launch_stage("starting-engine", "Starting live engine...", 85, "engine")
                self._dashboard.start_engine_if_needed()

                # Gateway diagnosis workstream: the gateway is expected to be
                # running from here on; watch it and restart it if it dies.
                # armed=True when the gateway is healthy now (spawned or
                # already running); a failed spawn leaves the watchdog
                # unarmed, so it never restarts a gateway that never started.
                try:
                    self._dashboard.gateway_supervisor.start_watchdog(armed=bool(healthy))
                except Exception as e:
                    logger.debug("Gateway watchdog start failed: %s", e)

                # 100% only here: the procedure has actually finished. The
                # message carries the outcome (gateway healthy or not).
                self._set_save_launch_stage("done", msg, 100, "")
                return {
                    "status": "ok",
                    "ok": True,
                    "gateway_online": bool(healthy),
                    "configured_providers": configured,
                    "message": msg,
                }
            except Exception as e:
                logger.error("Error saving credentials & launching gateway: %s", e)
                self._set_save_launch_stage("failed", str(e), None, "")
                return {"status": "error", "ok": False, "message": str(e), "gateway_online": False}

    def install_gateway_runtime(self) -> Dict[str, Any]:
        """
        Starts the one-click Node.js + OmniRoute install in the background
        (item 10 B3). The wizard polls get_setup_status for progress.
        """
        try:
            return self._dashboard.gateway_supervisor.start_runtime_install()
        except Exception as e:
            logger.error("Error starting gateway runtime install: %s", e)
            return {"ok": False, "message": str(e)}

    def cancel_gateway_runtime_install(self) -> Dict[str, Any]:
        """
        Cancels a running one-click Node.js + OmniRoute install (wizard
        close warning). The supervisor stops the background worker and
        removes partial artifacts; a later install attempt starts clean.
        """
        try:
            return self._dashboard.gateway_supervisor.cancel_runtime_install()
        except Exception as e:
            logger.error("Error cancelling gateway runtime install: %s", e)
            return {"ok": False, "message": str(e)}

class ArenaDashboard:
    """
    Native Windows GPU-Accelerated HiDPI Live Multi-Strategy Trading Desk.
    Powered by Edge WebView2 DirectX 11 Compositor + LiveArenaEngine.
    """

    def __init__(self, initial_cash: Decimal = Decimal("100000.00")) -> None:
        self.initial_cash = initial_cash
        self.config_manager = ConfigManager()
        # Gateway host/port come from the user's own config (item 10 A2):
        # the console button and the supervisor must follow gateway_port
        # instead of the hardcoded 20128.
        try:
            _gw_cfg = self.config_manager.load_config()
            _gw_port = int(_gw_cfg.get("gateway_port", 20128) or 20128)
            _gw_host = str(_gw_cfg.get("gateway_host", "127.0.0.1") or "127.0.0.1")
            # Audit 3.21: auto-redeploy when all five are flat is an
            # explicit switch (default ON); load_config merges the
            # default for installs whose config predates the key.
            _auto_redeploy = bool(_gw_cfg.get("auto_redeploy_when_flat", True))
        except Exception:
            _gw_host, _gw_port, _auto_redeploy = "127.0.0.1", 20128, True
        _gw_base_url = None if os.getenv("LLM_BASE_URL") else f"http://{_gw_host}:{_gw_port}/v1"
        self.engine = LiveArenaEngine(symbol="ETH/USD", initial_cash=initial_cash, auto_redeploy_when_flat=_auto_redeploy, gateway_base_url=_gw_base_url)
        self.gateway_supervisor = GatewaySupervisor(host=_gw_host, port=_gw_port, omni_data_dir=self.config_manager.omni_env_file.parent)
        self.window = None
        self.allow_exit = False
        self.closing_prompt_active = False
        self._evolution_running = False
        self._evolution_lock = threading.Lock()
        self._reset_lock = threading.Lock()
        self._stop_lock = threading.Lock()
        self._bridge = _ArenaBridgeApi(self)

    def get_gateway_diagnosis(self) -> str:
        """Gateway failure diagnosis for the Intel Hub line (gateway
        diagnosis workstream). One of "ok", "quota_exhausted",
        "connection_problem", "restarting". Never raises.

        Precedence: a restart in flight beats everything; a dead
        gateway beats a quota signal (quota cannot be known while the
        gateway is down). "quota_exhausted" means every configured
        provider has failed with a quota/credit signal, or the user's
        own daily token budget is used up -- never a computed %.
        Before the watchdog's first probe there is no health signal, so
        a gateway that never started shows no line (the setup wizard
        owns that case).
        """
        try:
            wd = self.gateway_supervisor.watchdog_status()
        except Exception as e:
            logger.debug("Gateway watchdog status read failed: %s", e)
            wd = {"state": "idle", "healthy": None}
        if wd.get("state") == "restarting":
            return "restarting"
        if wd.get("healthy") is False:
            return "connection_problem"
        try:
            client = getattr(self.engine, "omniroute_client", None)
            if client is None:
                return "ok"
            budget_fn = getattr(client, "is_daily_budget_exhausted", None)
            if callable(budget_fn) and budget_fn() is True:
                return "quota_exhausted"
            exhausted_fn = getattr(client, "is_all_providers_quota_exhausted", None)
            if callable(exhausted_fn):
                configured = self.config_manager.get_configured_providers()
                if exhausted_fn(configured) is True:
                    return "quota_exhausted"
        except Exception as e:
            logger.debug("Gateway quota diagnosis failed: %s", e)
        return "ok"

    def reset_engine(self) -> None:
        """Rebuilds the engine, preserving the arena state a reset must not discard.

        Serialized with _reset_lock and fully configured on a local instance
        before atomically swapping self.engine so concurrent bridge polls never
        observe a half-configured engine.
        """
        from dataclasses import replace as _dc_replace

        with self._reset_lock:
            old_engine = self.engine
            old_engine.stop()
            if old_engine.worker_thread and old_engine.worker_thread.is_alive():
                old_engine.worker_thread.join(timeout=3.0)
                if old_engine.worker_thread.is_alive():
                    logger.warning("Previous engine worker thread still alive after reset timeout")

            with old_engine.lock:
                old_interval = old_engine.auto_evolve_interval_sec
                old_enabled = old_engine.auto_evolve_enabled
                old_cadence = old_engine.cadence_sec
                old_auto_redeploy = old_engine.auto_redeploy_when_flat
                old_paused = old_engine.paused
                old_pause_start_ts = getattr(old_engine, "_pause_start_ts", None)
                old_auto_evolve_disabled_ts = getattr(old_engine, "_auto_evolve_disabled_ts", None)
                old_gen = {c.portfolio_id: c.genome.generation for c in old_engine.competitors}
                old_genomes = {c.portfolio_id: c.genome for c in old_engine.competitors}
                old_fills = list(old_engine.fill_records)
                old_events = list(old_engine.evolution_events)
                old_last_evolve_ts = old_engine.last_evolve_ts
                old_live_start_ts = old_engine.live_start_ts
                old_closed_since_evolve = old_engine._closed_trades_since_evolve
                old_seq_offset = int(getattr(old_engine, "_live_fill_seq_offset", 0) or 0)
            try:
                old_engine.storage.clear_session_snapshot()
            except Exception as e:
                logger.warning("Failed to clear session snapshot during reset: %s", e)

            _gw_base_url = (
                None
                if os.getenv("LLM_BASE_URL")
                else f"http://{self.gateway_supervisor.host}:{self.gateway_supervisor.port}/v1"
            )
            new_engine = LiveArenaEngine(
                symbol="ETH/USD",
                initial_cash=self.initial_cash,
                auto_redeploy_when_flat=old_auto_redeploy,
                gateway_base_url=_gw_base_url,
            )
            new_engine.auto_evolve_interval_sec = old_interval
            new_engine.auto_evolve_enabled = old_enabled
            new_engine.cadence_sec = old_cadence
            for c in new_engine.competitors:
                prev_genome = old_genomes.get(c.portfolio_id)
                if prev_genome is not None:
                    c.reset_for_new_generation(prev_genome, preserve_portfolio=False)
                    c.portfolio.leverage = prev_genome.leverage if prev_genome.leverage_enabled else Decimal("1.0")
                    c.portfolio.leverage_enabled = prev_genome.leverage_enabled
                    new_engine.broker.register_portfolio(c.portfolio, max_position_ratio=c.max_position_ratio)
                else:
                    gen = old_gen.get(c.portfolio_id)
                    if gen is not None and gen != c.genome.generation:
                        c.genome = _dc_replace(c.genome, generation=gen)
            new_engine.fill_records = old_fills
            new_engine._live_fill_seq_offset = old_seq_offset
            new_engine.evolution_events = old_events
            new_engine.last_evolve_ts = old_last_evolve_ts
            new_engine.live_start_ts = old_live_start_ts
            new_engine._closed_trades_since_evolve = old_closed_since_evolve
            new_engine.paused = old_paused
            if old_paused and old_pause_start_ts is not None:
                new_engine._pause_start_ts = old_pause_start_ts
            if not old_enabled and old_auto_evolve_disabled_ts is not None:
                new_engine._auto_evolve_disabled_ts = old_auto_evolve_disabled_ts
            new_engine._preserved_from_reset = True
            self.engine = new_engine
            new_engine.start_live_loop(interval_sec=old_cadence)

    def start_engine_if_needed(self) -> None:
        if not self.engine.running:
            logger.info("Starting TradeBot0 LiveArenaEngine (ETH/USD) post-onboarding...")
            self.engine.start_live_loop(interval_sec=1.0)

    def _maybe_check_for_updates(self) -> None:
        """Fires the startup update check on a background thread, if configured.

        Guarded: with no manifest URL configured (the case today) this
        returns immediately and issues no request. When a URL is set, the
        check runs off the UI thread so a slow endpoint can never stall
        startup; the result is only logged for now — showing a prompt in
        the frontend is future work (see src/update_checker.py).
        """
        if not get_manifest_url():
            return

        def _check() -> None:
            try:
                result = _run_update_check()
                logger.info("Update check at startup: %s", result.get("status"))
            except Exception as e:
                logger.debug("Startup update check failed: %s", e)

        threading.Thread(target=_check, daemon=True).start()

    def stop(self) -> None:
        """Cleanly halts trading engine, persistence, and background daemon supervisor."""
        with self._stop_lock:
            try:
                self.gateway_supervisor.cancel_runtime_install()
            except Exception as e:
                logger.debug("Error cancelling gateway runtime install: %s", e)
            try:
                self.gateway_supervisor.stop_watchdog()
            except Exception as e:
                logger.debug("Error stopping gateway watchdog: %s", e)
            try:
                self.engine.stop()
            except Exception as e:
                logger.debug("Error stopping engine: %s", e)
            try:
                self.gateway_supervisor.shutdown()
            except Exception as e:
                logger.debug("Error shutting down gateway supervisor: %s", e)

    def close_window(self) -> None:
        """Closes the window from any thread.

        On Windows, posts WM_CLOSE to the native handle (PostMessage is
        thread-safe): the normal closing flow then runs on the UI thread.
        Falls back to destroy() when there is no native handle (headless /
        non-Windows). The old shutdown() path called window.destroy() from a
        background thread, which WinForms does not allow (item 7).
        """
        window = self.window
        if window is None:
            return
        if sys.platform == "win32":
            hwnd = _get_native_hwnd(window)
            if hwnd:
                try:
                    import ctypes
                    from ctypes import wintypes

                    user32 = ctypes.WinDLL("user32", use_last_error=True)
                    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
                    user32.PostMessageW.restype = wintypes.BOOL
                    posted = user32.PostMessageW(wintypes.HWND(hwnd), 0x0010, 0, 0)  # WM_CLOSE
                    if posted:
                        return
                    logger.debug("PostMessage WM_CLOSE failed, falling back to destroy()")
                except Exception as e:
                    logger.debug("PostMessage WM_CLOSE failed, falling back to destroy(): %s", e)
        try:
            window.destroy()
        except Exception as e:
            logger.debug("Window destroy failed: %s", e)

    def run(self) -> None:
        import webview

        # Auto-launch background OmniRoute daemon on every start once
        # onboarding is complete. There is no opt-out: offline mode was
        # removed, so OmniRoute is required to use the app at all.
        # The config is loaded exactly once: the old code loaded it twice in
        # run() (once here, once below before starting the engine) (item 7).
        cfg: Dict[str, Any] = {}
        try:
            cfg = self.config_manager.load_config()
            if (
                cfg.get("has_completed_onboarding")
                and not cfg.get("skip_ai_mode")
                # Item 10 A1: never auto-start a gateway whose console is still
                # protected only by OmniRoute's built-in default password; the
                # setup wizard forces the user to set one first.
                and self.config_manager.is_admin_password_configured()
            ):
                _gw_healthy = False
                if not self.gateway_supervisor.is_port_open(timeout=0.25):
                    logger.info("Auto-spawning background OmniRoute gateway daemon...")
                    _spawn_ok, _ = self.gateway_supervisor.start_daemon(max_wait_sec=30.0)
                    _gw_healthy = bool(_spawn_ok)
                else:
                    try:
                        _healthy, _ = self.gateway_supervisor.probe_health(timeout=0.6)
                        _gw_healthy = bool(_healthy)
                    except Exception as e:
                        logger.debug("Gateway health probe at startup failed: %s", e)
                        _gw_healthy = False
                # Gateway diagnosis workstream: watch the daemon while the
                # app runs and restart it if it dies. Only started when
                # the gateway is expected to be running (onboarding done,
                # password set, not pure-math mode).
                self.gateway_supervisor.start_watchdog(armed=_gw_healthy)
        except Exception as e:
            logger.warning("Auto-launch check encountered non-fatal error: %s", e)

        # Only start live engine if onboarding has completed or in pure math mode
        if cfg.get("has_completed_onboarding") or cfg.get("skip_ai_mode"):
            logger.info("Starting TradeBot0 LiveArenaEngine (ETH/USD)...")
            self.engine.start_live_loop(interval_sec=1.0)
        else:
            logger.info("Awaiting onboarding setup before starting LiveArenaEngine...")

        # Update check (scaffolding only): runs on a background thread and
        # only when a manifest URL is configured (TRADEBOT0_UPDATE_URL).
        # Nothing is configured today, so this is a no-op that issues no
        # network request. See src/update_checker.py for what still needs
        # wiring (frontend prompt, settings field, download flow).
        self._maybe_check_for_updates()

        logger.info("Initializing pywebview GPU Window...")
        window = webview.create_window(
            title=WINDOW_TITLE,
            html=HTML_TEMPLATE or _build_html_template(),
            js_api=self._bridge,
            width=1540,
            height=940,
            min_size=(960, 640),
            background_color="#08090C",
            resizable=True,
            maximized=True,
            text_select=False,
            on_top=False,
        )
        self.window = window

        def _activate_foreground_startup():
            """
            Brings window to the foremost layer on startup (pop to front)
            and automatically maximizes the window (non-fullscreen mode).
            Releases permanent topmost lock so other windows can freely overlay when clicked.
            """
            try:
                if hasattr(window, "maximize"):
                    window.maximize()
            except Exception as e:
                logger.debug("pywebview window.maximize error: %s", e)

            if sys.platform != "win32":
                return
            try:
                import ctypes
                from ctypes import wintypes

                user32 = ctypes.WinDLL("user32", use_last_error=True)
                user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
                user32.FindWindowW.restype = wintypes.HWND
                user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
                user32.ShowWindow.restype = wintypes.BOOL
                user32.GetForegroundWindow.argtypes = []
                user32.GetForegroundWindow.restype = wintypes.HWND
                user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
                user32.GetWindowThreadProcessId.restype = wintypes.DWORD
                user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
                user32.AttachThreadInput.restype = wintypes.BOOL
                user32.SetWindowPos.argtypes = [
                    wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                    ctypes.c_int, ctypes.c_int, wintypes.UINT,
                ]
                user32.SetWindowPos.restype = wintypes.BOOL
                user32.SetForegroundWindow.argtypes = [wintypes.HWND]
                user32.SetForegroundWindow.restype = wintypes.BOOL
                user32.BringWindowToTop.argtypes = [wintypes.HWND]
                user32.BringWindowToTop.restype = wintypes.BOOL

                # Native handle first (exact); title lookup only as a
                # last-resort fallback, and the title now comes from the
                # single WINDOW_TITLE constant so it cannot drift out of
                # sync with create_window (item 7).
                hwnd_int = _get_native_hwnd(window)
                hwnd = wintypes.HWND(hwnd_int) if hwnd_int else user32.FindWindowW(None, WINDOW_TITLE)

                if hwnd:
                    SW_MAXIMIZE = 3
                    HWND_TOPMOST = wintypes.HWND(-1)
                    HWND_NOTOPMOST = wintypes.HWND(-2)
                    SWP_NOSIZE = 0x0001
                    SWP_NOMOVE = 0x0002
                    SWP_SHOWWINDOW = 0x0040

                    # Standard window maximize (non-fullscreen mode, keeping taskbar and title controls)
                    user32.ShowWindow(hwnd, SW_MAXIMIZE)

                    # Seamless thread input attach for 100% reliable Windows foreground activation
                    attached = False
                    fg_thread = 0
                    win_thread = 0
                    try:
                        fg_hwnd = user32.GetForegroundWindow()
                        target_hwnd_val = int(hwnd_int) if hwnd_int else int(getattr(hwnd, "value", hwnd) or 0)
                        fg_hwnd_val = int(getattr(fg_hwnd, "value", fg_hwnd) or 0)
                        if fg_hwnd and fg_hwnd_val != target_hwnd_val:
                            fg_thread = user32.GetWindowThreadProcessId(fg_hwnd, None)
                            win_thread = user32.GetWindowThreadProcessId(hwnd, None)
                            if fg_thread and win_thread and fg_thread != win_thread:
                                attached = bool(user32.AttachThreadInput(fg_thread, win_thread, True))
                    except Exception as e:
                        logger.debug("AttachThreadInput failed during foreground activation: %s", e)
                        attached = False

                    try:
                        # 1. Pop to foremost layer on startup to bypass background restrictions
                        user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
                        # 2. Immediately release permanent topmost lock (not "always on top")
                        user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
                        # 3. Bring to front and focus
                        user32.SetForegroundWindow(hwnd)
                        user32.BringWindowToTop(hwnd)
                    finally:
                        if attached:
                            try:
                                user32.AttachThreadInput(fg_thread, win_thread, False)
                            except Exception as e:
                                logger.debug("AttachThreadInput detach failed: %s", e)
            except Exception as e:
                logger.debug("Foreground startup activation error: %s", e)

        def _on_window_shown(*args):
            logger.info("Window shown: activating foremost layer on startup & maximizing window (non-fullscreen)...")
            _activate_foreground_startup()

            def _delayed_activation():
                time.sleep(0.35)
                _activate_foreground_startup()

            threading.Thread(target=_delayed_activation, daemon=True).start()

        window.events.shown += _on_window_shown

        def _on_window_closing():
            if self.allow_exit:
                return True
            if self.closing_prompt_active:
                # Force close or secondary close request: auto-save and exit cleanly
                try:
                    self.engine.save_session_state()
                except Exception as e:
                    logger.debug("Auto save on secondary close: %s", e)
                self.allow_exit = True
                return True

            self.closing_prompt_active = True

            # Asynchronous invocation via background thread:
            # Calling evaluate_js synchronously on the WinForms UI thread during FormClosing
            # deadlocks on semaphore.acquire(), hanging the application and freeze-lagging Windows!
            def _prompt_async():
                try:
                    window.evaluate_js("window.promptShutdownSave()")
                except Exception as e:
                    logger.debug("Prompt shutdown JS failed: %s", e)

            threading.Thread(target=_prompt_async, daemon=True).start()
            return False

        def _on_window_closed():
            self.allow_exit = True
            try:
                self.stop()
            except Exception as e:
                logger.debug("Stop on window closed: %s", e)

        window.events.closing += _on_window_closing
        window.events.closed += _on_window_closed

        try:
            webview.start(debug=False)
        finally:
            logger.info("Shutting down TradeBot0 engine and background workers...")
            self.stop()
