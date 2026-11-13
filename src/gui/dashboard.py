from __future__ import annotations

import logging
import pathlib
import sys
import threading
import time
from decimal import Decimal
from typing import Any, Dict, Optional

from src.data.live_engine import LiveArenaEngine
from src.intelligence.config_manager import ConfigManager
from src.intelligence.gateway_supervisor import GatewaySupervisor

logger = logging.getLogger(__name__)

WINDOW_TITLE = "TradeBot0 — ETH/USD Multi-Strategy Quant Arena"


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


class _ArenaBridgeApi:
    """
    Native Python <-> WebView2 GPU Frontend Bridge.
    Exposes zero-latency state polling and interactive controls to the HiDPI UI.
    """

    def __init__(self, dashboard: "ArenaDashboard") -> None:
        self._dashboard = dashboard

    def get_state(self) -> Dict[str, Any]:
        return self._dashboard.engine.get_ui_state()

    def get_state_delta(self, force_full: bool = False) -> Dict[str, Any]:
        return self._dashboard.engine.get_ui_state_delta(force_full=force_full)

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
                threading.Thread(target=self._run_manual_evolve, daemon=True).start()
        state = self._dashboard.engine.get_ui_state()
        state["evolution_running"] = self._dashboard._evolution_running
        return state

    def _run_manual_evolve(self) -> None:
        try:
            self._dashboard.engine.evolve_now(trigger="manual")
        except Exception as e:
            logger.error("Manual evolution failed: %s", e)
        finally:
            self._dashboard._evolution_running = False

    def toggle_pause(self) -> Dict[str, Any]:
        self._dashboard.engine.paused = not self._dashboard.engine.paused
        return self._dashboard.engine.get_ui_state()

    def toggle_auto_evolve(self) -> Dict[str, Any]:
        self._dashboard.engine.toggle_auto_evolve()
        return self._dashboard.engine.get_ui_state()

    def set_evolve_interval(self, seconds: int) -> Dict[str, Any]:
        self._dashboard.engine.set_auto_evolve_interval(seconds)
        return self._dashboard.engine.get_ui_state()

    def reset_arena(self) -> Dict[str, Any]:
        self._dashboard.reset_engine()
        return self._dashboard.engine.get_ui_state()

    def start_live_trading(self) -> Dict[str, Any]:
        cfg = self._dashboard.config_manager.load_config()
        if not cfg.get("has_completed_onboarding") and not cfg.get("skip_ai_mode"):
            logger.warning("Rejecting start_live_trading: onboarding not completed.")
            return {"status": "blocked", "message": "Onboarding required"}
        res = self._dashboard.engine.start_live_trading()
        state = self._dashboard.engine.get_ui_state()
        if isinstance(res, dict):
            state["start_result"] = res
        return state

    def refresh_intel_digest(self) -> Dict[str, Any]:
        threading.Thread(target=self._dashboard.engine.refresh_intel_digest, daemon=True).start()
        return self._dashboard.engine.get_ui_state()

    def toggle_fullscreen(self) -> bool:
        if self._dashboard.window:
            self._dashboard.window.toggle_fullscreen()
            return True
        return False

    def toggle_on_top(self) -> bool:
        """Flips always-on-top.

        The old version only set pywebview's `on_top` attribute, which does
        not reliably change the real window Z-order on Windows, so the button
        could report success without the window actually staying on top. Now
        the Win32 topmost flag is also set directly on the native handle
        (item 7).
        """
        if self._dashboard.window is None:
            return False
        new_val = not self.is_on_top()
        self._apply_on_top(new_val)
        self._dashboard._on_top = new_val
        return new_val

    def _apply_on_top(self, value: bool) -> None:
        window = self._dashboard.window
        if window is None:
            return
        try:
            window.on_top = value
        except Exception as e:
            logger.debug("pywebview on_top set failed: %s", e)
        if sys.platform == "win32":
            hwnd = _get_native_hwnd(window)
            if hwnd:
                try:
                    import ctypes
                    user32 = ctypes.windll.user32
                    HWND_TOPMOST = -1
                    HWND_NOTOPMOST = -2
                    SWP_NOSIZE = 0x0001
                    SWP_NOMOVE = 0x0002
                    SWP_SHOWWINDOW = 0x0040
                    user32.SetWindowPos(
                        hwnd,
                        HWND_TOPMOST if value else HWND_NOTOPMOST,
                        0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW,
                    )
                except Exception as e:
                    logger.debug("SetWindowPos topmost failed: %s", e)

    def is_on_top(self) -> bool:
        if self._dashboard.window:
            return bool(getattr(self._dashboard.window, "on_top", False)) or bool(self._dashboard._on_top)
        return bool(self._dashboard._on_top)

    def save_session_state(self) -> Dict[str, Any]:
        saved = self._dashboard.engine.save_session_state()
        return {"status": "ok", "saved": saved}

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
        url = "http://127.0.0.1:20128"
        try:
            webbrowser.open(url)
            logger.info("Launched OmniRoute console in system browser: %s", url)
            return {"status": "ok", "url": url}
        except Exception as e:
            logger.error("Failed to open OmniRoute console: %s", e)
            return {"status": "error", "message": str(e)}

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
                "gateway_auto_spawn": bool(cfg.get("gateway_auto_spawn", True)),
                "configured_providers": configured,
                "cli_available": bool(cli_avail),
                "gateway_port": int(cfg.get("gateway_port", 20128)),
                "omniroute_password_configured": pw_configured,
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
                "gateway_auto_spawn": True,
                "configured_providers": [],
                "cli_available": False,
                "gateway_port": 20128,
                "omniroute_password_configured": False,
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

    def save_and_launch_gateway(self, keys: Dict[str, str], auto_spawn: bool = True) -> Dict[str, Any]:
        """
        Persists API keys into ~/.omniroute/.env and launches gateway if requested.
        Marks onboarding as completed in system_config.json.
        """
        try:
            # 1. Sync keys into ~/.omniroute/.env
            sync_res = self._dashboard.config_manager.sync_omniroute_keys(keys or {})

            # 2. Update system config
            configured = self._dashboard.config_manager.get_configured_providers()
            self._dashboard.config_manager.save_config({
                "has_completed_onboarding": True,
                "skip_ai_mode": False,
                "gateway_auto_spawn": bool(auto_spawn),
                "configured_providers": configured,
                "last_setup_ts": time.time(),
            })

            # 3. Check gateway and spawn if requested
            is_open = self._dashboard.gateway_supervisor.is_port_open(timeout=0.3)
            healthy = False
            msg = "Credentials saved successfully."

            if is_open:
                healthy, _ = self._dashboard.gateway_supervisor.probe_health(timeout=0.6)
                if healthy:
                    msg = "Connected to active OmniRoute gateway."
            elif auto_spawn:
                spawn_ok, spawn_msg = self._dashboard.gateway_supervisor.start_daemon(max_wait_sec=30.0)
                healthy = spawn_ok
                msg = spawn_msg

            # 4. Start engine live loop if held in onboarding standby
            self._dashboard.start_engine_if_needed()

            return {
                "status": "ok",
                "ok": True,
                "gateway_online": bool(healthy),
                "configured_providers": configured,
                "message": msg,
            }
        except Exception as e:
            logger.error("Error saving credentials & launching gateway: %s", e)
            return {"status": "error", "ok": False, "message": str(e), "gateway_online": False}

    def skip_to_pure_math(self) -> Dict[str, Any]:
        """
        Bypasses external LLM gateway requirements entirely.
        TradeBot0 will operate 100% on local deterministic quantitative models.
        """
        try:
            self._dashboard.config_manager.save_config({
                "has_completed_onboarding": True,
                "skip_ai_mode": True,
                "last_setup_ts": time.time(),
            })
            self._dashboard.start_engine_if_needed()
            return {"status": "ok", "ok": True, "skip_ai_mode": True}
        except Exception as e:
            logger.error("Error setting pure math mode: %s", e)
            return {"status": "error", "ok": False, "message": str(e)}


class ArenaDashboard:
    """
    Native Windows GPU-Accelerated HiDPI Live Multi-Strategy Trading Desk.
    Powered by Edge WebView2 DirectX 11 Compositor + LiveArenaEngine.
    """

    def __init__(self, initial_cash: Decimal = Decimal("100000.00")) -> None:
        self.initial_cash = initial_cash
        self.engine = LiveArenaEngine(symbol="ETH/USD", initial_cash=initial_cash)
        self.config_manager = ConfigManager()
        self.gateway_supervisor = GatewaySupervisor()
        self.window = None
        self.allow_exit = False
        self.closing_prompt_active = False
        self._evolution_running = False
        self._evolution_lock = threading.Lock()
        self._on_top = False
        self._bridge = _ArenaBridgeApi(self)

    def reset_engine(self) -> None:
        """Rebuilds the engine, preserving the arena state a reset must not discard.

        The old version kept only three fields (evolve interval / enabled /
        cadence) and threw away the pause state, the generation, and the fill
        tape, then started the new engine trading immediately. Now the pause
        state, per-strategy generation, fill records, evolution events, evolve
        timer and closed-trade counter all survive the reset, and a paused
        arena stays paused: start_live_loop is paused-aware, so the loop
        thread runs but skips ticks until the user resumes (item 7).
        """
        from dataclasses import replace as _dc_replace

        old_interval = self.engine.auto_evolve_interval_sec
        old_enabled = self.engine.auto_evolve_enabled
        old_cadence = self.engine.cadence_sec
        old_paused = self.engine.paused
        old_gen = {c.portfolio_id: c.genome.generation for c in self.engine.competitors}
        old_fills = list(self.engine.fill_records)
        old_events = list(self.engine.evolution_events)
        old_last_evolve_ts = self.engine.last_evolve_ts
        old_live_start_ts = self.engine.live_start_ts
        old_closed_since_evolve = self.engine._closed_trades_since_evolve
        try:
            self.engine.storage.clear_session_snapshot()
        except Exception as e:
            logger.warning("Failed to clear session snapshot during reset: %s", e)
        self.engine.stop()
        if self.engine.worker_thread and self.engine.worker_thread.is_alive():
            self.engine.worker_thread.join(timeout=3.0)
            if self.engine.worker_thread.is_alive():
                logger.warning("Previous engine worker thread still alive after reset timeout")
        self.engine = LiveArenaEngine(symbol="ETH/USD", initial_cash=self.initial_cash)
        self.engine.auto_evolve_interval_sec = old_interval
        self.engine.auto_evolve_enabled = old_enabled
        self.engine.cadence_sec = old_cadence
        for c in self.engine.competitors:
            gen = old_gen.get(c.portfolio_id)
            if gen is not None and gen != c.genome.generation:
                c.genome = _dc_replace(c.genome, generation=gen)
        self.engine.fill_records = old_fills
        self.engine.evolution_events = old_events
        self.engine.last_evolve_ts = old_last_evolve_ts
        self.engine.live_start_ts = old_live_start_ts
        self.engine._closed_trades_since_evolve = old_closed_since_evolve
        self.engine.paused = old_paused
        self.engine.start_live_loop(interval_sec=old_cadence)

    def start_engine_if_needed(self) -> None:
        if not self.engine.running:
            logger.info("Starting TradeBot0 LiveArenaEngine (ETH/USD) post-onboarding...")
            self.engine.start_live_loop(interval_sec=1.0)

    def stop(self) -> None:
        """Cleanly halts trading engine, persistence, and background daemon supervisor."""
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
                    posted = ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
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

        # Auto-launch background OmniRoute daemon if enabled and onboarding is complete.
        # The config is loaded exactly once: the old code loaded it twice in
        # run() (once here, once below before starting the engine) (item 7).
        cfg: Dict[str, Any] = {}
        try:
            cfg = self.config_manager.load_config()
            if (
                cfg.get("has_completed_onboarding")
                and not cfg.get("skip_ai_mode")
                and cfg.get("gateway_auto_spawn", True)
            ):
                if not self.gateway_supervisor.is_port_open(timeout=0.25):
                    logger.info("Auto-spawning background OmniRoute gateway daemon...")
                    self.gateway_supervisor.start_daemon(max_wait_sec=30.0)
        except Exception as e:
            logger.warning("Auto-launch check encountered non-fatal error: %s", e)

        # Only start live engine if onboarding has completed or in pure math mode
        if cfg.get("has_completed_onboarding") or cfg.get("skip_ai_mode"):
            logger.info("Starting TradeBot0 LiveArenaEngine (ETH/USD)...")
            self.engine.start_live_loop(interval_sec=1.0)
        else:
            logger.info("Awaiting onboarding setup before starting LiveArenaEngine...")

        logger.info("Initializing pywebview GPU Window...")
        window = webview.create_window(
            title=WINDOW_TITLE,
            html=_build_html_template(),
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
                user32 = ctypes.windll.user32
                kernel32 = ctypes.windll.kernel32

                # Native handle first (exact); title lookup only as a
                # last-resort fallback, and the title now comes from the
                # single WINDOW_TITLE constant so it cannot drift out of
                # sync with create_window (item 7).
                hwnd = _get_native_hwnd(window)
                if not hwnd:
                    hwnd = user32.FindWindowW(None, WINDOW_TITLE)

                if hwnd:
                    SW_MAXIMIZE = 3
                    HWND_TOPMOST = -1
                    HWND_NOTOPMOST = -2
                    SWP_NOSIZE = 0x0001
                    SWP_NOMOVE = 0x0002
                    SWP_SHOWWINDOW = 0x0040

                    # Standard window maximize (non-fullscreen mode, keeping taskbar and title controls)
                    user32.ShowWindow(hwnd, SW_MAXIMIZE)

                    # Seamless thread input attach for 100% reliable Windows foreground activation
                    attached = False
                    try:
                        fg_hwnd = user32.GetForegroundWindow()
                        if fg_hwnd and fg_hwnd != hwnd:
                            fg_thread = user32.GetWindowThreadProcessId(fg_hwnd, None)
                            cur_thread = kernel32.GetCurrentThreadId()
                            if fg_thread and fg_thread != cur_thread:
                                attached = bool(user32.AttachThreadInput(fg_thread, cur_thread, True))
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
                                user32.AttachThreadInput(fg_thread, cur_thread, False)
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
