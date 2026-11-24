from __future__ import annotations

import base64
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
from src.intelligence.gemini_client import DEFAULT_GEMINI_BASE_URL, probe_gemini_api_key
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
            raw = native.Handle.ToInt64()
            if isinstance(raw, int) and not isinstance(raw, bool) and raw > 0:
                return raw
    except Exception as e:
        logger.debug("Failed to read native window handle: %s", e)
    return None


def _get_assets_dir() -> pathlib.Path:
    if hasattr(sys, "_MEIPASS"):
        return pathlib.Path(sys._MEIPASS) / "src" / "gui" / "assets"
    return pathlib.Path(__file__).parent / "assets"


_ASSETS_DIR = _get_assets_dir()
_ICON_LOCK = threading.Lock()
_ACTIVE_WINDOW_HICONS: Dict[int, int] = {}


def _get_app_icon_path() -> Optional[pathlib.Path]:
    """Return the multi-resolution TradeBot0 .ico path when bundled or on disk."""
    path = _ASSETS_DIR / "app_icon.ico"
    return path if path.is_file() else None


def _destroy_win32_hicons(handles: list[int]) -> None:
    """Release raw Win32 HICON handles via DestroyIcon without locking _ICON_LOCK."""
    to_free = [int(h) for h in handles if h]
    if sys.platform != "win32" or not to_free:
        return
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.DestroyIcon.argtypes = [wintypes.HICON]
        user32.DestroyIcon.restype = wintypes.BOOL
        for h in to_free:
            try:
                user32.DestroyIcon(wintypes.HICON(h))
            except Exception:
                pass
    except Exception as e:
        logger.debug("DestroyIcon cleanup failed: %s", e)


def _destroy_window_hicons(handles: Optional[list[int]] = None) -> None:
    """Release Win32 HICON handles tracked for the active window."""
    with _ICON_LOCK:
        if handles is None:
            to_free = list(_ACTIVE_WINDOW_HICONS.values())
            _ACTIVE_WINDOW_HICONS.clear()
        else:
            to_free = list(handles)
    _destroy_win32_hicons(to_free)


def _apply_window_icon(window: Any, icon_path: Optional[pathlib.Path] = None) -> bool:
    """Apply the multi-size TradeBot0 icon to a pywebview native Windows HWND."""
    if sys.platform != "win32" or window is None:
        return False
    ico = icon_path if icon_path is not None else _get_app_icon_path()
    if ico is None or not ico.is_file():
        return False

    applied = False
    try:
        native = getattr(window, "native", None)
        if native is not None and not getattr(native, "InvokeRequired", False):
            try:
                import clr

                clr.AddReference("System.Drawing")
                from System.Drawing import Icon as DotNetIcon

                native.Icon = DotNetIcon(str(ico))
                applied = True
            except Exception as e:
                logger.debug("WinForms native.Icon assignment skipped: %s", e)
    except Exception as e:
        logger.debug("WinForms native check failed: %s", e)

    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
        user32.FindWindowW.restype = wintypes.HWND
        user32.GetSystemMetrics.argtypes = [ctypes.c_int]
        user32.GetSystemMetrics.restype = ctypes.c_int
        user32.LoadImageW.argtypes = [
            wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
            ctypes.c_int, ctypes.c_int, wintypes.UINT,
        ]
        user32.LoadImageW.restype = wintypes.HANDLE
        user32.SendMessageW.argtypes = [
            wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
        ]
        user32.SendMessageW.restype = ctypes.c_ssize_t

        hwnd_int = _get_native_hwnd(window)
        hwnd = wintypes.HWND(hwnd_int) if hwnd_int else user32.FindWindowW(None, WINDOW_TITLE)
        if not hwnd:
            return applied

        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x0010
        WM_SETICON = 0x0080
        ICON_SMALL = 0
        ICON_BIG = 1
        cx_sm = int(user32.GetSystemMetrics(49) or 16)
        cy_sm = int(user32.GetSystemMetrics(50) or 16)
        cx_lg = int(user32.GetSystemMetrics(11) or 32)
        cy_lg = int(user32.GetSystemMetrics(12) or 32)

        ico_str = str(ico.resolve())
        h_sm = user32.LoadImageW(None, ico_str, IMAGE_ICON, cx_sm, cy_sm, LR_LOADFROMFILE)
        h_lg = user32.LoadImageW(None, ico_str, IMAGE_ICON, cx_lg, cy_lg, LR_LOADFROMFILE)

        new_slots: Dict[int, int] = {}
        if h_sm:
            new_slots[ICON_SMALL] = int(h_sm)
        if h_lg:
            new_slots[ICON_BIG] = int(h_lg)

        if new_slots:
            prev_replaced: list[int] = []
            try:
                with _ICON_LOCK:
                    for slot, handle_val in new_slots.items():
                        user32.SendMessageW(hwnd, WM_SETICON, slot, handle_val)
                        prev = _ACTIVE_WINDOW_HICONS.get(slot)
                        if prev and prev != handle_val:
                            prev_replaced.append(prev)
                        _ACTIVE_WINDOW_HICONS[slot] = handle_val
                        applied = True
            except Exception:
                _destroy_win32_hicons(list(new_slots.values()))
                raise
            if prev_replaced:
                _destroy_win32_hicons(prev_replaced)
    except Exception as e:
        logger.debug("Win32 WM_SETICON failed: %s", e)

    return applied


def _load_asset(filename: str) -> str:
    path = _ASSETS_DIR / filename
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    logger.error("Asset file not found: %s", path)
    return ""


def _load_binary_data_uri(filename: str, mime_type: str) -> Optional[str]:
    """Read a binary asset file as a base64 data URI, or None if missing."""
    path = _ASSETS_DIR / filename
    if not path.exists():
        logger.debug("Optional binary asset not found: %s", path)
        return None
    try:
        raw = path.read_bytes()
        encoded = base64.b64encode(raw).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"
    except Exception as e:
        logger.warning("Failed to encode asset %s: %s", path, e)
        return None


def _build_html_template() -> str:
    html = _load_asset("index.html")
    css = _load_asset("app.css")
    js = _load_asset("app.js")
    if not html:
        logger.critical("Failed to load index.html from assets!")
        return "<html><body>Asset loading failed</body></html>"
    grainient_uri = _load_binary_data_uri("grainient_obsidian.webp", "image/webp")
    if grainient_uri:
        css = css.replace("/* __GRAINIENT_OBSIDIAN_DATA_URI__ */", grainient_uri)
    else:
        css = (
            css.replace('url("/* __GRAINIENT_OBSIDIAN_DATA_URI__ */")', "none")
            .replace("url('/* __GRAINIENT_OBSIDIAN_DATA_URI__ */')", "none")
            .replace("/* __GRAINIENT_OBSIDIAN_DATA_URI__ */", "none")
        )
    app_icon_uri = _load_binary_data_uri("app_icon.png", "image/png")
    if app_icon_uri:
        html = html.replace("/* __APP_ICON_DATA_URI__ */", app_icon_uri)
    else:
        html = html.replace('<link rel="icon" type="image/png" href="/* __APP_ICON_DATA_URI__ */" />\n', "")
        html = html.replace('<link rel="icon" type="image/png" href="/* __APP_ICON_DATA_URI__ */" />', "")
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
        # synchronous save_and_launch call runs, so the user sees which step
        # is running instead of a frozen button. Percentages are stage
        # milestones, never measured time; 100% is set only when ok.
        self._save_launch_lock = threading.Lock()
        self._save_launch_exec_lock = threading.Lock()
        self._shutdown_lock = threading.Lock()
        self._shutdown_started = False
        self._save_launch_stage = {
            "status": "idle",
            "message": "",
            "progress": None,
            "phase": "",
        }

    def get_state(self) -> Dict[str, Any]:
        state = self._dashboard.engine.get_ui_state()
        self._inject_ai_diagnosis(state)
        return state

    def get_state_delta(self, force_full: bool = False) -> Dict[str, Any]:
        state = self._dashboard.engine.get_ui_state_delta(force_full=force_full)
        self._inject_ai_diagnosis(state)
        return state

    def _inject_ai_diagnosis(self, state: Dict[str, Any]) -> None:
        """Adds Gemini AI status diagnosis into state['intel_hub']['ai']['diagnosis']."""
        try:
            diagnosis = self._dashboard.get_ai_diagnosis()
            intel = state.get("intel_hub")
            if not isinstance(intel, dict):
                return
            ai_info = intel.get("ai")
            if not isinstance(ai_info, dict):
                return
            ai_info["diagnosis"] = diagnosis
        except Exception as e:
            logger.debug("AI diagnosis injection failed: %s", e)

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
        self._dashboard.engine.toggle_pause()
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
        AI or LLM failure returns {"ok": False, "reason": ...} --
        never a fabricated article. Never raises.
        """
        try:
            return self._dashboard.engine.macro_commander.get_event_article(event_id)
        except Exception as e:
            logger.error("Event article fetch failed for %s: %s", event_id, e)
            return {"ok": False, "event_id": event_id, "state": "failed", "reason": str(e) or e.__class__.__name__}

    def get_event_article_progress(self, event_id: str) -> Dict[str, Any]:
        """Returns live article generation percentage and stage for an event. Never raises."""
        try:
            return self._dashboard.engine.macro_commander.get_event_article_progress(str(event_id or ""))
        except Exception as e:
            logger.debug("Event article progress read failed for %s: %s", event_id, e)
            return {"ok": False, "event_id": str(event_id or ""), "state": "none", "progress": 0, "stage": ""}

    def toggle_fullscreen(self) -> bool:
        if self._dashboard.window:
            self._dashboard.window.toggle_fullscreen()
            return True
        return False

    def cancel_shutdown_prompt(self) -> Dict[str, Any]:
        self._dashboard.closing_prompt_active = False
        return {"status": "cancelled"}

    def shutdown(self, save_progress: bool = True) -> Dict[str, Any]:
        with self._shutdown_lock:
            if self._shutdown_started:
                return {"status": "shutting_down", "saved": save_progress}
            self._shutdown_started = True
        logger.info("Shutdown requested from UI bridge (save_progress=%s)", save_progress)
        self._dashboard.allow_exit = True
        self._dashboard.closing_prompt_active = False
        if save_progress:
            try:
                self._dashboard.engine.save_session_state()
            except Exception as e:
                logger.error("Error saving session state on shutdown: %s", e)
        try:
            self._dashboard.engine.stop()
        except Exception as e:
            logger.error("Error stopping engine on shutdown: %s", e)
        if self._dashboard.window:
            if _get_native_hwnd(self._dashboard.window) is not None:
                # Defer WM_CLOSE slightly on Windows so pywebview resolves the bridge
                # JS Promise before the native WebView2 control is disposed.
                def _deferred_close() -> None:
                    time.sleep(0.08)
                    self._dashboard.close_window()

                threading.Thread(target=_deferred_close, name="close-window-deferred", daemon=True).start()
            else:
                self._dashboard.close_window()
        return {"status": "shutting_down", "saved": save_progress}

    def open_external_url(self, url: str) -> Dict[str, Any]:
        """Opens an approved provider key page in the system browser.

        The setup wizard's "Get a key" link allows only the Google Gemini
        API key page; anything else is refused and never opened. Never raises.
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
        Returns initialization and Gemini key setup status for the UI wizard.
        Fail-safe: never raises an unhandled exception.
        """
        try:
            cfg = self._dashboard.config_manager.load_config()
            key_configured = bool(self._dashboard.config_manager.has_gemini_api_key())
            client = getattr(getattr(self._dashboard, "engine", None), "llm_client", None)
            ai_online = bool(getattr(client, "is_gateway_online", False))
            return {
                "status": "ok",
                "onboarding_completed": bool(cfg.get("has_completed_onboarding", False)),
                "skip_ai_mode": bool(cfg.get("skip_ai_mode", False)),
                "gemini_key_configured": key_configured,
                "ai_online": ai_online,
            }
        except Exception as e:
            logger.error("Error reading setup status: %s", e)
            return {
                "status": "error",
                "error": str(e),
                "onboarding_completed": False,
                "skip_ai_mode": False,
                "gemini_key_configured": False,
                "ai_online": False,
            }

    def test_api_key(self, provider: str = "gemini", key: Optional[str] = None) -> Dict[str, Any]:
        """Live-probes a Google Gemini API key via GET /v1beta/models/{model}."""
        try:
            actual_key = key if key is not None else ("" if str(provider or "").lower().strip() == "gemini" else str(provider))
            return probe_gemini_api_key(actual_key)
        except Exception as e:
            logger.error("Error testing API key: %s", e)
            return {"ok": False, "message": f"Verification failed: {e}", "latency_ms": 0}

    def _set_save_launch_stage(
        self, status: str, message: str,
        progress: Optional[int] = None, phase: str = "",
    ) -> None:
        """Records the current Save & Launch step for the wizard poll loop."""
        with self._save_launch_lock:
            self._save_launch_stage = {
                "status": status,
                "message": message,
                "progress": progress,
                "phase": phase,
            }

    def get_save_launch_status(self) -> Dict[str, Any]:
        """Current Save & Launch stage for the wizard poll loop. Never raises."""
        try:
            with self._save_launch_lock:
                return dict(self._save_launch_stage)
        except Exception as e:
            logger.debug("Save launch status read failed: %s", e)
            return {"status": "idle", "message": "", "progress": None, "phase": ""}

    def save_and_launch(self, keys: Any = None) -> Dict[str, Any]:
        """Persists the Gemini API key into system_config.json, hot-reloads the running
        client, verifies reachability, and starts the live trading engine.
        """
        with self._save_launch_exec_lock:
            try:
                self._set_save_launch_stage("idle", "", None, "")
                cm = self._dashboard.config_manager

                raw_key = ""
                if isinstance(keys, dict):
                    raw_key = str(keys.get("gemini") or "")
                elif isinstance(keys, str):
                    raw_key = keys
                cleaned_key = cm.sanitize_key(raw_key)

                # 1. Persist Gemini key when user typed one (blank preserves existing key)
                self._set_save_launch_stage("syncing-keys", "Saving Gemini API key...", 25, "keys")
                if cleaned_key:
                    key_res = cm.set_gemini_api_key(cleaned_key)
                    if isinstance(key_res, dict) and key_res.get("ok") is False:
                        err_msg = str(key_res.get("error") or "Failed to save Gemini API key.")
                        self._set_save_launch_stage("failed", err_msg, 25, "keys")
                        return {"status": "error", "ok": False, "message": err_msg, "ai_online": False}
                active_key = cm.get_gemini_api_key()

                # 2. Update system config
                self._set_save_launch_stage("saving-config", "Saving setup...", 55, "config")
                cfg_saved = cm.save_config({
                    "has_completed_onboarding": True,
                    "skip_ai_mode": False,
                    "last_setup_ts": time.time(),
                })
                if cfg_saved is False:
                    err_msg = "Failed to save system configuration."
                    self._set_save_launch_stage("failed", err_msg, 55, "config")
                    return {"status": "error", "ok": False, "message": err_msg, "ai_online": False}

                # 3. Hot-reload client key and perform lightweight probe
                self._set_save_launch_stage("verifying-ai", "Connecting to Gemini AI...", 75, "ai")
                ai_online = False
                engine = getattr(self._dashboard, "engine", None)
                if engine is not None and hasattr(engine, "update_gemini_api_key"):
                    engine.update_gemini_api_key(active_key)
                if active_key:
                    probe = probe_gemini_api_key(active_key, timeout=3.0)
                    ai_online = bool(probe.get("ok"))
                    client = getattr(engine, "llm_client", None)
                    if client is not None:
                        client.is_gateway_online = ai_online
                    msg = "Gemini AI connected." if ai_online else f"Saved. {probe.get('message', 'Gemini standby')}"
                else:
                    msg = "Setup saved (Pure Math standby mode)."

                # 4. Start engine live loop if held in onboarding standby
                self._set_save_launch_stage("starting-engine", "Starting live engine...", 90, "engine")
                self._dashboard.start_engine_if_needed()

                self._set_save_launch_stage("done", msg, 100, "")
                return {
                    "status": "ok",
                    "ok": True,
                    "ai_online": bool(ai_online),
                    "gemini_key_configured": bool(active_key),
                    "message": msg,
                }
            except Exception as e:
                logger.error("Error saving Gemini credentials & launching arena: %s", e)
                self._set_save_launch_stage("failed", str(e), None, "")
                return {"status": "error", "ok": False, "message": str(e), "ai_online": False}

def close_native_splash() -> bool:
    """Closes the PyInstaller native bootloader splash screen if active.

    Idempotent and safe when running from source (where `pyi_splash` does
    not exist) or after the splash has already been closed. Never raises.
    """
    try:
        import pyi_splash  # type: ignore[import-not-found]
        is_alive = getattr(pyi_splash, "is_alive", None)
        if not callable(is_alive) or is_alive():
            pyi_splash.close()
            return True
    except Exception:
        pass
    return False


class ArenaDashboard:
    """
    Native Windows GPU-Accelerated HiDPI Live Multi-Strategy Trading Desk.
    Powered by Edge WebView2 DirectX 11 Compositor + LiveArenaEngine.
    """

    def __init__(self, initial_cash: Decimal = Decimal("100000.00")) -> None:
        self.initial_cash = initial_cash
        self.config_manager = ConfigManager()
        try:
            self.config_manager.migrate_legacy_omniroute_once()
        except Exception as e:
            logger.debug("Legacy config migration check failed: %s", e)
        try:
            _cfg = self.config_manager.load_config()
            _auto_redeploy = bool(_cfg.get("auto_redeploy_when_flat", True))
        except Exception:
            _auto_redeploy = True
        _api_key = self.config_manager.get_gemini_api_key()
        self.engine = LiveArenaEngine(
            symbol="ETH/USD",
            initial_cash=initial_cash,
            auto_redeploy_when_flat=_auto_redeploy,
            llm_base_url=os.getenv("LLM_BASE_URL") or DEFAULT_GEMINI_BASE_URL,
            gemini_api_key=_api_key or None,
        )
        self.window = None
        self.allow_exit = False
        self.closing_prompt_active = False
        self._evolution_running = False
        self._evolution_lock = threading.Lock()
        self._reset_lock = threading.Lock()
        self._stop_lock = threading.Lock()
        self._stopped = False
        self._bridge = _ArenaBridgeApi(self)

    def get_ai_diagnosis(self) -> str:
        """Gemini AI failure diagnosis for the Intel Hub panel.
        Returns one of 'ok', 'quota_exhausted', 'connection_problem'. Never raises.
        """
        try:
            client = getattr(self.engine, "llm_client", None)
            if client is None:
                return "ok"
            budget_fn = getattr(client, "is_daily_budget_exhausted", None)
            if callable(budget_fn) and budget_fn() is True:
                return "quota_exhausted"
            has_q_fn = getattr(client, "has_quota_failures", None)
            if callable(has_q_fn) and has_q_fn() is True:
                return "quota_exhausted"
            last_fail = getattr(client, "last_failure", None)
            if isinstance(last_fail, dict) and last_fail.get("kind") in ("connection", "auth"):
                if not getattr(client, "is_gateway_online", False):
                    return "connection_problem"
        except Exception as e:
            logger.debug("AI diagnosis evaluation failed: %s", e)
        return "ok"

    def reset_engine(self) -> None:
        """Rebuilds the engine, preserving the arena state a reset must not discard.

        Serialized with _reset_lock and fully configured on a local instance
        before atomically swapping self.engine so concurrent bridge polls never
        observe a half-configured engine.
        """
        from dataclasses import replace as _dc_replace

        with self._reset_lock:
            if self._stopped:
                logger.info("Skipping reset_engine: dashboard is shutting down.")
                return
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
                old_tv_champ = dict(old_engine.tv_champion) if isinstance(getattr(old_engine, "tv_champion", None), dict) else {}
            try:
                old_engine.storage.clear_session_snapshot()
            except Exception as e:
                logger.warning("Failed to clear session snapshot during reset: %s", e)
            finally:
                try:
                    old_engine.storage.close()
                except Exception as e:
                    logger.debug("Failed to close previous engine storage during reset: %s", e)

            if self._stopped:
                return

            _api_key = self.config_manager.get_gemini_api_key()
            new_engine = LiveArenaEngine(
                symbol="ETH/USD",
                initial_cash=self.initial_cash,
                auto_redeploy_when_flat=old_auto_redeploy,
                llm_base_url=os.getenv("LLM_BASE_URL") or DEFAULT_GEMINI_BASE_URL,
                gemini_api_key=_api_key or None,
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
            max_carried_seq = max((int(getattr(f, "fill_seq", 0)) for f in old_fills), default=0)
            if max_carried_seq > 0:
                new_engine.broker.reset_seq(max_carried_seq)
            if old_tv_champ:
                import copy as _copy
                new_engine.tv_champion = _copy.deepcopy(old_tv_champ)
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
        """Cleanly halts trading engine and persistence (idempotent)."""
        with self._stop_lock:
            if self._stopped:
                return
            self._stopped = True
            try:
                self.engine.stop()
            except Exception as e:
                logger.debug("Error stopping engine: %s", e)
            _destroy_window_hicons()

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

        cfg: Dict[str, Any] = {}
        try:
            cfg = self.config_manager.load_config()
        except Exception as e:
            logger.warning("Startup config load failed: %s", e)

        # Start live engine directly if onboarding has completed or in pure math mode
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
            close_native_splash()
            _apply_window_icon(window)
            logger.info("Window shown: activating foremost layer on startup & maximizing window (non-fullscreen)...")
            _activate_foreground_startup()

            def _delayed_activation():
                time.sleep(0.35)
                if self._stopped or self.allow_exit:
                    return
                _apply_window_icon(window)
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
                if self.allow_exit or self._stopped:
                    return
                try:
                    window.evaluate_js("window.promptShutdownSave()")
                except Exception as e:
                    logger.debug("Prompt shutdown JS skipped/disposed: %s", e)

            threading.Thread(target=_prompt_async, daemon=True).start()
            return False

        def _on_window_closed():
            self.allow_exit = True
            self.closing_prompt_active = False
            # Avoid blocking the WinForms UI thread inside FormClosed; run() finally:
            # also calls self.stop() synchronously and blocks on _stop_lock until done.
            threading.Thread(target=self.stop, name="dashboard-stop", daemon=True).start()

        window.events.closing += _on_window_closing
        window.events.closed += _on_window_closed

        ico_path = _get_app_icon_path()
        if ico_path is not None:
            try:
                webview._state["icon"] = str(ico_path)
            except Exception as e:
                logger.debug("Failed to preset pywebview window icon: %s", e)

        try:
            webview.start(debug=False)
        finally:
            close_native_splash()
            logger.info("Shutting down TradeBot0 engine and background workers...")
            self.stop()
