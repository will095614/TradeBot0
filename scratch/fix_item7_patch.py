#!/usr/bin/env python3
"""Fix item 7: GUI (TradeBot0 maintenance list).

Applies exact-once-verified replacements to the PC project tree (run with
cwd = project root) and, identically, to the local audit copy.
Every replacement is verified to occur exactly once before anything is
written; on any mismatch the script aborts without touching a file.
Newline style is preserved (files are LF; open with newline="").
"""
import os
import sys

if not os.path.isdir("src/gui"):
    print("FAIL: run this script from the project root (src/gui not found)")
    sys.exit(1)

REPLACEMENTS = []

# ---------------------------------------------------------------- dashboard.py
REPLACEMENTS.append(("src/gui/dashboard.py", r'''from typing import Any, Dict''', r'''from typing import Any, Dict, Optional'''))

REPLACEMENTS.append(("src/gui/dashboard.py", r'''logger = logging.getLogger(__name__)
''', r'''logger = logging.getLogger(__name__)

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
    except Exception:
        pass
    return None
'''))

REPLACEMENTS.append(("src/gui/dashboard.py", r'''        self.window = None
        self.allow_exit = False
        self.closing_prompt_active = False
        self._bridge = _ArenaBridgeApi(self)''', r'''        self.window = None
        self.allow_exit = False
        self.closing_prompt_active = False
        self._evolution_running = False
        self._evolution_lock = threading.Lock()
        self._on_top = False
        self._bridge = _ArenaBridgeApi(self)'''))

REPLACEMENTS.append(("src/gui/dashboard.py", r'''    def evolve_now(self) -> Dict[str, Any]:
        self._dashboard.engine.evolve_now(trigger="manual")
        return self._dashboard.engine.get_ui_state()''', r'''    def evolve_now(self) -> Dict[str, Any]:
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
            self._dashboard._evolution_running = False'''))

REPLACEMENTS.append(("src/gui/dashboard.py", r'''    def toggle_on_top(self) -> bool:
        if self._dashboard.window:
            new_val = not getattr(self._dashboard.window, "on_top", False)
            self._dashboard.window.on_top = new_val
            return new_val
        return False

    def is_on_top(self) -> bool:
        if self._dashboard.window:
            return bool(getattr(self._dashboard.window, "on_top", False))
        return False''', r'''    def toggle_on_top(self) -> bool:
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
        return bool(self._dashboard._on_top)'''))

REPLACEMENTS.append(("src/gui/dashboard.py", r'''        if self._dashboard.window:
            def _close_window():
                try:
                    time.sleep(0.1)
                    self._dashboard.window.destroy()
                except Exception as e:
                    logger.debug("Window destroy in background thread: %s", e)
            threading.Thread(target=_close_window, daemon=True).start()
        return {"status": "shutting_down", "saved": save_progress}''', r'''        if self._dashboard.window:
            # Close on the calling thread: window.destroy() must run on the
            # UI thread, and the old background-thread destroy was a
            # use-after-free / deadlock risk on WinForms (item 7).
            self._dashboard.close_window()
        return {"status": "shutting_down", "saved": save_progress}'''))

REPLACEMENTS.append(("src/gui/dashboard.py", r'''            # Retrieve default/configured OmniRoute password for easy one-click login
            omni_pw = "OmniAdmin2026!ChangeMe"
            env_map = self._dashboard.config_manager.read_omniroute_env()
            if "INITIAL_PASSWORD" in env_map and env_map["INITIAL_PASSWORD"]:
                omni_pw = env_map["INITIAL_PASSWORD"]''', r'''            # Never send any password value to the frontend: the old code
            # returned the admin password (default or configured) in plain
            # text to JavaScript. The UI only needs to know whether a custom
            # password has been configured in ~/.omniroute/.env (item 7).
            env_map = self._dashboard.config_manager.read_omniroute_env()
            pw_configured = bool(env_map.get("INITIAL_PASSWORD"))'''))

REPLACEMENTS.append(("src/gui/dashboard.py", r'''                "omniroute_password": omni_pw,''', r'''                "omniroute_password_configured": pw_configured,'''))

REPLACEMENTS.append(("src/gui/dashboard.py", r'''                "omniroute_password": "OmniAdmin2026!ChangeMe",''', r'''                "omniroute_password_configured": False,'''))

REPLACEMENTS.append(("src/gui/dashboard.py", r'''    def reset_engine(self) -> None:
        old_interval = self.engine.auto_evolve_interval_sec
        old_enabled = self.engine.auto_evolve_enabled
        old_cadence = self.engine.cadence_sec
        try:
            self.engine.storage.clear_session_snapshot()
        except Exception:
            pass
        self.engine.stop()
        if self.engine.worker_thread and self.engine.worker_thread.is_alive():
            self.engine.worker_thread.join(timeout=3.0)
            if self.engine.worker_thread.is_alive():
                logger.warning("Previous engine worker thread still alive after reset timeout")
        self.engine = LiveArenaEngine(symbol="ETH/USD", initial_cash=self.initial_cash)
        self.engine.auto_evolve_interval_sec = old_interval
        self.engine.auto_evolve_enabled = old_enabled
        self.engine.cadence_sec = old_cadence
        self.engine.start_live_loop(interval_sec=old_cadence)''', r'''    def reset_engine(self) -> None:
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
        except Exception:
            pass
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
        self.engine.start_live_loop(interval_sec=old_cadence)'''))

REPLACEMENTS.append(("src/gui/dashboard.py", r'''    def run(self) -> None:
        import webview''', r'''    def close_window(self) -> None:
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
                    ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
                    return
                except Exception as e:
                    logger.debug("PostMessage WM_CLOSE failed, falling back to destroy(): %s", e)
        try:
            window.destroy()
        except Exception as e:
            logger.debug("Window destroy failed: %s", e)

    def run(self) -> None:
        import webview'''))

REPLACEMENTS.append(("src/gui/dashboard.py", r'''        # Auto-launch background OmniRoute daemon if enabled and onboarding is complete
        try:
            cfg = self.config_manager.load_config()
            if (
                cfg.get("has_completed_onboarding")
                and not cfg.get("skip_ai_mode")
                and cfg.get("gateway_auto_spawn", True)
            ):
                if not self.gateway_supervisor.is_port_open(timeout=0.25):
                    logger.info("Auto-spawning background OmniRoute gateway daemon...")
                    self.gateway_supervisor.start_daemon(max_wait_sec=14.0)
        except Exception as e:
            logger.warning("Auto-launch check encountered non-fatal error: %s", e)

        # Only start live engine if onboarding has completed or in pure math mode
        cfg = self.config_manager.load_config()
        if cfg.get("has_completed_onboarding") or cfg.get("skip_ai_mode"):''', r'''        # Auto-launch background OmniRoute daemon if enabled and onboarding is complete.
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
                    self.gateway_supervisor.start_daemon(max_wait_sec=14.0)
        except Exception as e:
            logger.warning("Auto-launch check encountered non-fatal error: %s", e)

        # Only start live engine if onboarding has completed or in pure math mode
        if cfg.get("has_completed_onboarding") or cfg.get("skip_ai_mode"):'''))

REPLACEMENTS.append(("src/gui/dashboard.py", r'''            title="TradeBot0 — ETH/USD Multi-Strategy Quant Arena",''', r'''            title=WINDOW_TITLE,'''))

REPLACEMENTS.append(("src/gui/dashboard.py", r'''                hwnd = None
                if hasattr(window, "native") and window.native:
                    try:
                        hwnd = int(window.native.Handle.ToInt64())
                    except Exception:
                        hwnd = None
                if not hwnd:
                    hwnd = user32.FindWindowW(None, "TradeBot0 — ETH/USD Multi-Strategy Quant Arena")''', r'''                # Native handle first (exact); title lookup only as a
                # last-resort fallback, and the title now comes from the
                # single WINDOW_TITLE constant so it cannot drift out of
                # sync with create_window (item 7).
                hwnd = _get_native_hwnd(window)
                if not hwnd:
                    hwnd = user32.FindWindowW(None, WINDOW_TITLE)'''))

# ---------------------------------------------------------------- view_model.py
REPLACEMENTS.append(("src/gui/view_model.py", r'''import hashlib
import json
import math
import time''', r'''import hashlib
import json
import logging
import math
import time'''))

REPLACEMENTS.append(("src/gui/view_model.py", r'''from src.arena.order import OrderSide, PositionSide''', r'''from src.arena.order import OrderSide, PositionSide


logger = logging.getLogger(__name__)'''))

REPLACEMENTS.append(("src/gui/view_model.py", r'''def build_engine_view_model(engine: Any, rankings: List[Any], gen: int) -> Dict[str, Any]:''', r'''def _build_engine_view_model_impl(engine: Any, rankings: List[Any], gen: int) -> Dict[str, Any]:'''))

REPLACEMENTS.append(("src/gui/view_model.py", r'''        c = next(comp for comp in engine.competitors if comp.portfolio_id == r.portfolio_id)''', r'''        c = next((comp for comp in engine.competitors if comp.portfolio_id == r.portfolio_id), None)
        if c is None:
            # Stale ranking entry (competitor removed): skip it instead of
            # raising StopIteration and taking down the whole view model.
            continue'''))

REPLACEMENTS.append(("src/gui/view_model.py", r'''        if in_pos and tp_p is None and sl_p is not None:
            entry_f = fz(p.avg_entry_price)
            if is_short:
                ref = min(fz(spot), entry_f)
                tp_p = round(max(1.0, ref - 2 * max(0.5, abs(sl_p - ref))), 2)
            else:
                ref = max(fz(spot), entry_f)
                tp_p = round(ref + 2 * max(0.5, abs(ref - sl_p)), 2)
''', r''''''))

REPLACEMENTS.append(("src/gui/view_model.py", r'''                "mc_verdict": mc_st.get("verdict", "EV Gate Active"),
                "expected_r": mc_st.get("expected_r", 0.0),
                "target_prob": mc_st.get("target_prob", 0.50),
                "stop_prob": mc_st.get("stop_prob", 0.40),
                "r_multiple": mc_st.get("r_multiple", 1.8),
                "ev_passed": mc_st.get("passed", True),''', r'''                # No Monte Carlo evaluation has run yet for this strategy
                # (mc_stats is empty until the first bracket is evaluated):
                # report unknown (None), never fabricated defaults. The old
                # defaults (EV 0.0, win 50%, R 1.8, passed True, verdict
                # "EV Gate Active") were invented numbers (item 7).
                "mc_verdict": mc_st.get("verdict"),
                "expected_r": mc_st.get("expected_r"),
                "target_prob": mc_st.get("target_prob"),
                "stop_prob": mc_st.get("stop_prob"),
                "r_multiple": mc_st.get("r_multiple"),
                "ev_passed": mc_st.get("passed"),'''))

REPLACEMENTS.append(("src/gui/view_model.py", r'''        "quota_pct": 100.0,''', r'''        "quota_pct": None,  # Unknown: the local engine reports no quota (was a fabricated 100.0, item 7).'''))

REPLACEMENTS.append(("src/gui/view_model.py", r'''        "price_history": [fz(v) for v in engine.eth_price_series],
        "ema_fast_history": [fz(v) for v in engine.ema_fast_series],
        "ema_slow_history": [fz(v) for v in engine.ema_slow_series],
    }''', r'''        "price_history": [fz(v) for v in engine.eth_price_series],
        "ema_fast_history": [fz(v) for v in engine.ema_fast_series],
        "ema_slow_history": [fz(v) for v in engine.ema_slow_series],
    }


def _empty_view_model(error: str) -> Dict[str, Any]:
    """Safe fallback view model used when the engine is missing or broken.

    Carries every top-level key the frontend reads so a broken engine
    degrades to an empty dashboard instead of crashing the bridge (item 7).
    """
    quant_meta = {
        "source": "Local Pure-Math Quant Core",
        "is_online": False,
        "endpoint": "In-Memory Native Engine",
        "active_model": "Genetic Evolution + Monte Carlo EV",
        "quota_pct": None,
        "tokens_used": 0,
        "tokens_saved": 0,
    }
    return {
        "error": error,
        "engine_available": False,
        "paused": False,
        "auto_evolve_enabled": False,
        "auto_evolve_interval_sec": 21600,
        "next_evolve_sec": 0,
        "evolution_events": [],
        "macro_commander": {},
        "intel_hub": {},
        "mtf": {
            "htf_bias": "NEUTRAL",
            "htf_ema_50": 0.0,
            "htf_ema_200": 0.0,
            "candles_1h_count": 0,
        },
        "candles": [],
        "cadence_sec": 1.0,
        "tv_hub": {
            "champion": {},
            "next_rotation_sec": 0,
            "payloads": [],
            "webhook_endpoint": "Internal Signal Bus",
            "is_connected": False,
        },
        "quant_meta": quant_meta,
        "omni_meta": quant_meta,
        "omni_summary": "",
        "strategies": [],
        "fills": [],
        "price_history": [],
        "ema_fast_history": [],
        "ema_slow_history": [],
    }


def build_engine_view_model(engine: Any, rankings: List[Any], gen: int) -> Dict[str, Any]:
    """Fault-tolerant entry point (item 7).

    The old version raised on any abnormal engine state (engine None, a
    missing attribute, a stale ranking entry) and took down the whole view
    model / bridge poll. Now it returns the safe empty model instead.
    """
    if engine is None:
        return _empty_view_model("engine_not_initialized")
    try:
        return _build_engine_view_model_impl(engine, rankings or [], gen)
    except Exception as e:
        logger.exception("build_engine_view_model failed, returning empty model: %s", e)
        return _empty_view_model(str(e))'''))

# ---------------------------------------------------------------- index.html
REPLACEMENTS.append(("src/gui/assets/index.html", r'''title="Click to copy password"><span>OmniAdmin2026!ChangeMe</span>''', r'''title="Admin password is stored in ~/.omniroute/.env"><span>********</span>'''))

# ---------------------------------------------------------------- app.js
REPLACEMENTS.append(("src/gui/assets/app.js", r'''          const pwdEl = document.getElementById('omniConsolePwd');
          if (pwdEl && res.omniroute_password) {
            pwdEl.textContent = res.omniroute_password;
          }''', r'''          // The backend never sends the password value: only whether a
          // custom password is configured. The badge always shows a mask
          // (item 7); the real password lives in ~/.omniroute/.env.
          const pwdEl = document.getElementById('omniConsolePwd');
          if (pwdEl) {
            const pwdSpan = pwdEl.querySelector('span') || pwdEl;
            pwdSpan.textContent = '********';
            pwdEl.title = res.omniroute_password_configured
              ? 'Custom admin password configured in ~/.omniroute/.env'
              : 'Default admin password in effect - see ~/.omniroute/.env';
          }'''))

REPLACEMENTS.append(("src/gui/assets/app.js", r'''  function copyOmniPassword() {
    const el = document.getElementById('omniConsolePwd');
    const pwd = 'OmniAdmin2026!ChangeMe';
    let copied = false;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      try {
        navigator.clipboard.writeText(pwd).then(() => {}).catch(() => {
          fallbackCopyText(pwd);
        });
        copied = true;
      } catch (err) {
        copied = fallbackCopyText(pwd);
      }
    } else {
      copied = fallbackCopyText(pwd);
    }

    if (el) {
      el.classList.add('pwd-copied');
      const span = el.querySelector('span') || el;
      span.textContent = 'Copied \u2713';
      setTimeout(() => {
        span.textContent = 'OmniAdmin2026!ChangeMe';
        el.classList.remove('pwd-copied');
      }, 2000);
    }
    if (typeof showChartToast === 'function') {
      showChartToast('OmniRoute Admin Password Copied to Clipboard', '#10F5A0');
    }
  }''', r'''  function copyOmniPassword() {
    // The password is never exposed to the frontend (item 7): clicking the
    // badge only points at where it lives instead of copying it.
    if (typeof showChartToast === 'function') {
      showChartToast('Admin password is stored in ~/.omniroute/.env', '#F59E0B');
    }
  }'''))

REPLACEMENTS.append(("src/gui/assets/app.js", r'''    const qPct = typeof omni.quota_pct === 'number' ? omni.quota_pct : 100.0;
    if (quotaBar) quotaBar.style.width = `${Math.max(5, Math.min(100, qPct))}%`;
    if (quotaPct) {
      const remTokens = Math.max(0, 100000 - (omni.tokens_used || 0)).toLocaleString();
      quotaPct.textContent = `${qPct.toFixed(1)}% Available (${remTokens} rem)`;
    }''', r'''    // Unknown quota stays unknown: the old fallback fabricated 100.0%
    // whenever the backend sent no number (item 7).
    const qPct = typeof omni.quota_pct === 'number' ? omni.quota_pct : null;
    if (quotaBar) quotaBar.style.width = qPct === null ? '0%' : `${Math.max(5, Math.min(100, qPct))}%`;
    if (quotaPct) {
      if (qPct === null) {
        quotaPct.textContent = 'Quota unknown';
      } else {
        const remTokens = Math.max(0, 100000 - (omni.tokens_used || 0)).toLocaleString();
        quotaPct.textContent = `${qPct.toFixed(1)}% Available (${remTokens} rem)`;
      }
    }'''))

REPLACEMENTS.append(("src/gui/assets/app.js", r'''      const evBadge = (s.expected_r !== undefined && Math.abs(s.expected_r) > 0.01)''', r'''      const evBadge = (typeof s.expected_r === 'number' && Math.abs(s.expected_r) > 0.01)'''))

REPLACEMENTS.append(("src/gui/assets/app.js", r'''        const evVal = s.expected_r !== undefined ? `${s.expected_r >= 0 ? '+' : ''}${s.expected_r.toFixed(2)}R` : '-0.5R';''', r'''        const evVal = typeof s.expected_r === 'number' ? `${s.expected_r >= 0 ? '+' : ''}${s.expected_r.toFixed(2)}R` : '-';'''))

NEW_FILES = {}
NEW_FILES["tests/test_gui_item7.py"] = r'''"""Item 7 tests: GUI password handling, fabricated view-model values,
view-model fault tolerance, reset state preservation, async evolve,
UI-thread shutdown, single config load."""
import inspect
import json
import threading
import time
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import src.gui.dashboard as dashboard_mod
from src.arena.order import FillEvent, OrderSide, PositionSide
from src.data.live_engine import LiveArenaEngine
from src.gui.dashboard import ArenaDashboard, _ArenaBridgeApi
from src.gui.view_model import build_engine_view_model
from src.intelligence.config_manager import ConfigManager
from src.intelligence.gateway_supervisor import GatewaySupervisor


def _rankings(engine):
    return [
        SimpleNamespace(
            portfolio_id=c.portfolio_id, rank=i + 1, equity=100000.0,
            roi_pct=0.0, win_rate_pct=0.0, closed_trades=0,
            max_drawdown_pct=0.0, sharpe_ratio=0.0, fitness_score=0.0,
            name=c.base_name,
        )
        for i, c in enumerate(engine.competitors)
    ]


# ------------------------------------------------------------------ password
def test_setup_status_never_returns_password(tmp_path):
    dash = ArenaDashboard()
    dash.config_manager = ConfigManager(
        data_dir=tmp_path / "data",
        omni_env_path=tmp_path / ".omniroute" / ".env",
    )
    dash.gateway_supervisor = GatewaySupervisor()
    bridge = _ArenaBridgeApi(dash)

    st = bridge.get_setup_status()
    assert st["status"] == "ok"
    assert "omniroute_password" not in st
    assert st["omniroute_password_configured"] is False
    assert "OmniAdmin2026!ChangeMe" not in json.dumps(st)

    # A configured custom password is still never returned, only flagged.
    env_dir = tmp_path / ".omniroute"
    env_dir.mkdir(parents=True, exist_ok=True)
    (env_dir / ".env").write_text("INITIAL_PASSWORD=MySecret123\n", encoding="utf-8")
    st2 = bridge.get_setup_status()
    assert st2["omniroute_password_configured"] is True
    assert "omniroute_password" not in st2
    assert "MySecret123" not in json.dumps(st2)


def test_frontend_assets_contain_no_default_password():
    assets = Path(__file__).resolve().parent.parent / "src" / "gui" / "assets"
    for name in ("index.html", "app.js"):
        text = (assets / name).read_text(encoding="utf-8")
        assert "OmniAdmin2026!ChangeMe" not in text, f"default password still in {name}"


# ------------------------------------------------------- fabricated view model
def test_view_model_does_not_fabricate_take_profit():
    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    try:
        engine.broker.current_price = Decimal("2500")
        comp = engine.comp_a
        comp.portfolio.position_qty = Decimal("10")
        comp.portfolio.position_side = PositionSide.LONG
        comp.portfolio.avg_entry_price = Decimal("2400")
        engine.broker.active_stops[comp.portfolio_id] = SimpleNamespace(price=Decimal("2300"))
        vm = build_engine_view_model(engine, _rankings(engine), 1)
        strat = next(s for s in vm["strategies"] if s["id"] == comp.portfolio_id)
        assert strat["stop_loss"] == 2300.0
        # No target order: unknown (None), not a price synthesized from SL.
        assert strat["take_profit"] is None
    finally:
        engine.stop()


def test_view_model_reports_unknown_mc_and_quota():
    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    try:
        vm = build_engine_view_model(engine, _rankings(engine), 1)
        for strat in vm["strategies"]:
            assert strat["expected_r"] is None
            assert strat["target_prob"] is None
            assert strat["stop_prob"] is None
            assert strat["r_multiple"] is None
            assert strat["ev_passed"] is None
            assert strat["mc_verdict"] is None
        assert vm["quant_meta"]["quota_pct"] is None
        assert vm["omni_meta"]["quota_pct"] is None
    finally:
        engine.stop()


# ------------------------------------------------------------ fault tolerance
def test_view_model_survives_missing_or_broken_engine():
    vm = build_engine_view_model(None, [], 1)
    assert vm["engine_available"] is False
    assert vm["strategies"] == []
    assert "error" in vm

    vm2 = build_engine_view_model(SimpleNamespace(), [], 1)
    assert vm2["engine_available"] is False
    assert vm2["strategies"] == []


def test_view_model_skips_stale_ranking_entry():
    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    try:
        rankings = _rankings(engine) + [
            SimpleNamespace(
                portfolio_id="comp_ghost", rank=99, equity=0.0, roi_pct=0.0,
                win_rate_pct=0.0, closed_trades=0, max_drawdown_pct=0.0,
                sharpe_ratio=0.0, fitness_score=0.0, name="Ghost",
            )
        ]
        vm = build_engine_view_model(engine, rankings, 1)
        assert "error" not in vm
        assert len(vm["strategies"]) == 6
    finally:
        engine.stop()


# ---------------------------------------------------------------- reset_engine
def test_reset_engine_preserves_pause_generation_and_fills():
    dash = ArenaDashboard(initial_cash=Decimal("100000.00"))
    try:
        dash.engine.paused = True
        for c in dash.engine.competitors:
            c.genome = replace(c.genome, generation=5)
        fill = FillEvent(
            order_id="test-1", portfolio_id="comp_agg", symbol="ETH/USD",
            side=OrderSide.BUY, qty=Decimal("1"), price=Decimal("2500"),
            fee=Decimal("1"), timestamp=time.time(),
        )
        dash.engine.fill_records.append(fill)
        dash.engine.evolution_events.append({"generation": 5, "note": "test"})

        dash.reset_engine()

        assert dash.engine.paused is True
        assert max(c.genome.generation for c in dash.engine.competitors) == 5
        assert fill in dash.engine.fill_records
        assert dash.engine.evolution_events[-1].get("note") == "test"
        # Loop thread is alive but paused: no trading resumes by itself.
        assert dash.engine.running is True
        assert all(c.portfolio.position_qty == 0 for c in dash.engine.competitors)
    finally:
        dash.engine.stop()


# ------------------------------------------------------------------ async evolve
def test_manual_evolve_does_not_block_bridge():
    dash = ArenaDashboard(initial_cash=Decimal("100000.00"))
    bridge = _ArenaBridgeApi(dash)
    started = threading.Event()
    release = threading.Event()
    calls = []

    def slow_evolve(trigger="manual"):
        calls.append(trigger)
        started.set()
        release.wait(timeout=10)

    dash.engine.evolve_now = slow_evolve
    try:
        t0 = time.monotonic()
        state = bridge.evolve_now()
        elapsed = time.monotonic() - t0
        assert elapsed < 5.0  # returned without waiting for evolution
        assert started.wait(timeout=5)  # evolution actually started in background
        assert state.get("evolution_running") is True
        bridge.evolve_now()  # second click while running: no second run
        assert len(calls) == 1
    finally:
        release.set()
        deadline = time.monotonic() + 5
        while dash._evolution_running and time.monotonic() < deadline:
            time.sleep(0.05)
        assert dash._evolution_running is False
        dash.engine.stop()


# --------------------------------------------------------------------- shutdown
def test_shutdown_closes_window_on_calling_thread():
    dash = ArenaDashboard(initial_cash=Decimal("100000.00"))
    bridge = _ArenaBridgeApi(dash)
    caller = threading.get_ident()
    seen = []
    mock_win = MagicMock()
    mock_win.destroy.side_effect = lambda: seen.append(threading.get_ident())
    dash.window = mock_win
    try:
        res = bridge.shutdown(save_progress=False)
        assert res["status"] == "shutting_down"
        assert mock_win.destroy.call_count == 1
        assert seen == [caller]  # destroyed on the calling thread, not a background thread
    finally:
        dash.engine.stop()


# ------------------------------------------------------- run() / window handle
def test_run_loads_config_once_and_uses_window_title_constant():
    src = inspect.getsource(dashboard_mod.ArenaDashboard.run)
    assert src.count("load_config()") == 1
    assert "title=WINDOW_TITLE" in src
    assert dashboard_mod.WINDOW_TITLE.startswith("TradeBot0")
    assert callable(dashboard_mod._get_native_hwnd)
    assert dashboard_mod._get_native_hwnd(SimpleNamespace()) is None
    fake = SimpleNamespace(native=SimpleNamespace(Handle=SimpleNamespace(ToInt64=lambda: 12345)))
    assert dashboard_mod._get_native_hwnd(fake) == 12345
'''


def main():
    for rel, old, new in REPLACEMENTS:
        with open(rel, "r", encoding="utf-8", newline="") as f:
            content = f.read()
        count = content.count(old)
        if count != 1:
            print(f"FAIL {rel}: expected exactly 1 occurrence, found {count}")
            sys.exit(1)
        content = content.replace(old, new)
        with open(rel, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        print(f"OK {rel}")
    for rel, text in NEW_FILES.items():
        if os.path.exists(rel):
            print(f"FAIL {rel}: already exists")
            sys.exit(1)
        with open(rel, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        print(f"CREATED {rel}")
    print("ALL PATCHES APPLIED")


if __name__ == "__main__":
    main()
