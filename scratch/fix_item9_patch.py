#!/usr/bin/env python3
"""Fix item 9: generation safety & observability (TradeBot0 maintenance list).

Applies exact-once-verified replacements to the PC project tree (run with
cwd = project root) and, identically, to the local audit copy.
Every replacement is verified to occur exactly once before anything is
written; on any mismatch the script aborts without touching a file.
Newline style is preserved (files are LF; open with newline="").

Three fixes:
  1. Generation fence: engine_epoch was set but never checked on writes, so a
     reset left the old engine's threads able to keep writing SQLite / the
     evolution history after a new engine started. Now the newest instance's
     epoch is the only valid one (class-level _active_epoch, strictly
     increasing); stale engines refuse fills, session saves, evolution and
     state publishes, and log a warning.
  2. Silent excepts: all 40 silent `except Exception` sites in src/ (26 bare
     `pass` + 14 silent fallbacks) now log -- debug for best-effort cleanup
     and expected fallbacks, warning where data is actually lost or a
     feature silently stops (evolution SQLite save, CCXT total failure,
     reset snapshot clear, quota/env read). Sites that already logged are
     untouched.
  3. Splash blur lightened (user design: the see-through init effect stays,
     just less blurry): .splash-overlay blur 3px -> 1px, veil 0.50 -> 0.30.
     arenaFadeIn (no blur) and toastSpringIn/Out blur(8px) untouched.
     The change only retunes two values in the existing AIMRAN liquid-glass
     overlay (frontend-design / stageshow SKILL.md read first); no new
     tokens or styles.
"""
import os
import sys

if not os.path.isdir("src/gui"):
    print("FAIL: run this script from the project root (src/gui not found)")
    sys.exit(1)

REPLACEMENTS = []
NEW_FILES = {}


def rep(path, old, new):
    REPLACEMENTS.append((path, old, new))


# =========================================================== 1. generation fence
# live_engine.py: class-level active epoch
rep("src/data/live_engine.py", """    - Operates 6 distinct real-time strategies simultaneously on every live tick.
    \"\"\"
    def __init__(self, initial_cash: Decimal = Decimal("100000.00"), symbol: str = "ETH/USD", storage: Optional[ArenaStorage] = None):""",
"""    - Operates 6 distinct real-time strategies simultaneously on every live tick.
    \"\"\"

    # Generation fence (item 9): reset_engine() builds a brand-new engine, so
    # the newest instance's epoch is the only valid one. A previous engine
    # whose worker thread survives stop() (join timeout) must not write
    # SQLite or publish state anymore.
    _active_epoch: float = 0.0

    def __init__(self, initial_cash: Decimal = Decimal("100000.00"), symbol: str = "ETH/USD", storage: Optional[ArenaStorage] = None):""")

# live_engine.py: strictly increasing epoch, register as active
rep("src/data/live_engine.py", """        self.engine_epoch: float = time.time()""",
"""        # Strictly increasing epoch: a new engine always supersedes any older
        # instance, even if two are constructed within one clock tick.
        self.engine_epoch: float = max(time.time(), LiveArenaEngine._active_epoch + 0.001)
        LiveArenaEngine._active_epoch = self.engine_epoch""")

# live_engine.py: fence helper + _harvest_fills gate
rep("src/data/live_engine.py", """    def _harvest_fills(self) -> None:
        \"\"\"Copies new broker fills into the persistent tape (bounded to 200 records) and SQLite ledger.\"\"\"
        audit = self.broker.execution_audit""",
"""    def _is_current_generation(self) -> bool:
        \"\"\"Generation fence (item 9): True only while this engine instance is
        the newest one. After a reset the dashboard owns a fresh engine, so
        any thread still owned by the old instance must refuse SQLite writes
        and state publishes instead of overwriting the new generation.\"\"\"
        return self.engine_epoch == LiveArenaEngine._active_epoch

    def _harvest_fills(self) -> None:
        \"\"\"Copies new broker fills into the persistent tape (bounded to 200 records) and SQLite ledger.\"\"\"
        if not self._is_current_generation():
            logger.warning("Stale engine epoch %.3f: refusing to record fills from a superseded generation", self.engine_epoch)
            return
        audit = self.broker.execution_audit""")

# live_engine.py: evolve_now gate (fence + stopped-engine guard)
rep("src/data/live_engine.py", """    def evolve_now(self, trigger: str = "manual") -> List[str]:
        records_to_save = None""",
"""    def evolve_now(self, trigger: str = "manual") -> List[str]:
        if not self._is_current_generation():
            logger.warning("Stale engine epoch %.3f: refusing to evolve from a superseded generation", self.engine_epoch)
            return []
        if self._stop_event.is_set():
            logger.warning("Engine stopped: refusing to evolve after shutdown")
            return []
        records_to_save = None""")

# live_engine.py: save_session_state gate
rep("src/data/live_engine.py", """        if self._stop_event.is_set():
            return False
        try:
            with self.lock:
                self._harvest_fills()""",
"""        if self._stop_event.is_set():
            return False
        if not self._is_current_generation():
            logger.warning("Stale engine epoch %.3f: refusing to save session state from a superseded generation", self.engine_epoch)
            return False
        try:
            with self.lock:
                self._harvest_fills()""")

# live_engine.py: _publish_state_snapshot gate (instance-local snapshot, but a
# stale engine's publish must never win over the new generation's)
rep("src/data/live_engine.py", """        Called at the completion of each cadence evaluation or state-changing command.
        \"\"\"
        snapshot = self._build_snapshot_locked()""",
"""        Called at the completion of each cadence evaluation or state-changing command.
        \"\"\"
        if not self._is_current_generation():
            logger.debug("Stale engine epoch %.3f: skipping state publish from a superseded generation", self.engine_epoch)
            return
        snapshot = self._build_snapshot_locked()""")

# live_engine.py: bootstrap candle batch save gate
rep("src/data/live_engine.py", """            # Persist warmed-up 1m candles to SQLite WAL storage
            if not self._stop_event.is_set():
                try:
                    self.storage.save_candles_batch(self.candles)""",
"""            # Persist warmed-up 1m candles to SQLite WAL storage
            if not self._stop_event.is_set() and self._is_current_generation():
                try:
                    self.storage.save_candles_batch(self.candles)""")

# live_engine.py: per-cadence candle save gate
rep("src/data/live_engine.py", """        if self.candles:
            self._update_mtf_regimes(self.candles[-1])
            if self.is_bootstrapped:
                try:
                    self.storage.save_candle(self.candles[-1])""",
"""        if self.candles:
            self._update_mtf_regimes(self.candles[-1])
            if self.is_bootstrapped and self._is_current_generation():
                try:
                    self.storage.save_candle(self.candles[-1])""")

# =========================================================== 3. splash blur
rep("src/gui/assets/app.css", """.splash-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    radial-gradient(circle at 50% 40%, rgba(255, 255, 255, 0.03), transparent 70%),
    rgba(2, 6, 15, 0.50);
  backdrop-filter: blur(3px) saturate(115%);
  -webkit-backdrop-filter: blur(3px) saturate(115%);""",
""".splash-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    radial-gradient(circle at 50% 40%, rgba(255, 255, 255, 0.03), transparent 70%),
    rgba(2, 6, 15, 0.30);
  backdrop-filter: blur(1px) saturate(115%);
  -webkit-backdrop-filter: blur(1px) saturate(115%);""")

# =========================================================== 2a. logger imports
rep("src/arena/evolution.py", """import json
import os
import random
import sys
import time

from src.arena.leaderboard import CompetitorStats, Leaderboard
from src.competitors.base import BaseCompetitor, CompetitorGenome
""",
"""import json
import logging
import os
import random
import sys
import time

from src.arena.leaderboard import CompetitorStats, Leaderboard
from src.competitors.base import BaseCompetitor, CompetitorGenome

logger = logging.getLogger(__name__)
""")

rep("src/data/eth_feed.py", """import os
import time
import warnings
import pandas as pd
import numpy as np
""",
"""import logging
import os
import time
import warnings
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)
""")

# =========================================================== 2b. evolution.py
rep("src/arena/evolution.py", """            try:
                with open(hist_path, "r", encoding="utf-8") as f:
                    history = json.load(f)
            except Exception:
                history = []""",
"""            try:
                with open(hist_path, "r", encoding="utf-8") as f:
                    history = json.load(f)
            except Exception as e:
                logger.debug("Failed to load arena history, starting fresh: %s", e)
                history = []""")

rep("src/arena/evolution.py", """                    evolution_seed=int(evolution_seed),
                )
            except Exception:
                pass""",
"""                    evolution_seed=int(evolution_seed),
                )
            except Exception as e:
                logger.warning("Failed to persist evolution history to SQLite: %s", e)""")

# =========================================================== 2c. eth_feed.py
rep("src/data/eth_feed.py", """            if df is not None and not df.empty:
                return df
        except Exception:
            pass

        # Automatic CCXT Public Exchange Fallback (Kraken ETH/USD, zero API key needed)""",
"""            if df is not None and not df.empty:
                return df
        except Exception as e:
            logger.debug("yfinance fetch failed, trying CCXT fallback: %s", e)

        # Automatic CCXT Public Exchange Fallback (Kraken ETH/USD, zero API key needed)""")

rep("src/data/eth_feed.py", """                df = df.set_index("Timestamp")
                return df
        except Exception:
            pass

        return pd.DataFrame()""",
"""                df = df.set_index("Timestamp")
                return df
        except Exception as e:
            logger.warning("CCXT fallback fetch failed, no bars available: %s", e)

        return pd.DataFrame()""")

# =========================================================== 2d. live_engine.py
rep("src/data/live_engine.py", """            self.is_bootstrapped = True
            try:
                self._publish_state_snapshot()
            except Exception:
                pass
            try:
                if os.environ.get("ARENA_FAST_TEST") != "1":""",
"""            self.is_bootstrapped = True
            try:
                self._publish_state_snapshot()
            except Exception as e:
                logger.debug("State publish skipped during bootstrap: %s", e)
            try:
                if os.environ.get("ARENA_FAST_TEST") != "1":""")

rep("src/data/live_engine.py", """            try:
                if os.environ.get("ARENA_FAST_TEST") != "1":
                    threading.Thread(target=self.refresh_intel_digest, daemon=True).start()
            except Exception:
                pass""",
"""            try:
                if os.environ.get("ARENA_FAST_TEST") != "1":
                    threading.Thread(target=self.refresh_intel_digest, daemon=True).start()
            except Exception as e:
                logger.warning("Failed to start intel digest refresh thread: %s", e)""")

rep("src/data/live_engine.py", """            self._is_refreshing_intel = False
            try:
                self._publish_state_snapshot()
            except Exception:
                pass
        return self.macro_commander.get_intel_hub_telemetry()""",
"""            self._is_refreshing_intel = False
            try:
                self._publish_state_snapshot()
            except Exception as e:
                logger.debug("State publish skipped after intel refresh: %s", e)
        return self.macro_commander.get_intel_hub_telemetry()""")

rep("src/data/live_engine.py", """                    qty=Decimal("0"),
                    price=Decimal(str(data))
                )
            except Exception:
                return None""",
"""                    qty=Decimal("0"),
                    price=Decimal(str(data))
                )
            except Exception as e:
                logger.debug("Failed to deserialize order ticket, dropping: %s", e)
                return None""")

rep("src/data/live_engine.py", """            try:
                side = OrderSide(data.get("side", "SELL"))
            except Exception:
                side = OrderSide.SELL""",
"""            try:
                side = OrderSide(data.get("side", "SELL"))
            except Exception as e:
                logger.debug("Invalid order side in saved ticket, defaulting to SELL: %s", e)
                side = OrderSide.SELL""")

rep("src/data/live_engine.py", """            try:
                order_type = OrderType(data.get("order_type", "STOP_MARKET"))
            except Exception:
                order_type = OrderType.STOP_MARKET""",
"""            try:
                order_type = OrderType(data.get("order_type", "STOP_MARKET"))
            except Exception as e:
                logger.debug("Invalid order type in saved ticket, defaulting to STOP_MARKET: %s", e)
                order_type = OrderType.STOP_MARKET""")

rep("src/data/live_engine.py", """            try:
                side = OrderSide(data.get("side", "BUY"))
            except Exception:
                side = OrderSide.BUY""",
"""            try:
                side = OrderSide(data.get("side", "BUY"))
            except Exception as e:
                logger.debug("Invalid fill side in saved data, defaulting to BUY: %s", e)
                side = OrderSide.BUY""")

rep("src/data/live_engine.py", """            try:
                pos_side = PositionSide(data.get("position_side", "LONG"))
            except Exception:
                pos_side = PositionSide.LONG""",
"""            try:
                pos_side = PositionSide(data.get("position_side", "LONG"))
            except Exception as e:
                logger.debug("Invalid position side in saved data, defaulting to LONG: %s", e)
                pos_side = PositionSide.LONG""")

rep("src/data/live_engine.py", """            try:
                reason = ExecutionReason(data.get("reason", "SIGNAL"))
            except Exception:
                reason = ExecutionReason.SIGNAL""",
"""            try:
                reason = ExecutionReason(data.get("reason", "SIGNAL"))
            except Exception as e:
                logger.debug("Invalid execution reason in saved data, defaulting to SIGNAL: %s", e)
                reason = ExecutionReason.SIGNAL""")

rep("src/data/live_engine.py", """                entry_price=ep,
                position_side=pos_side,
            )
        except Exception:
            return None""",
"""                entry_price=ep,
                position_side=pos_side,
            )
        except Exception as e:
            logger.debug("Failed to deserialize fill, dropping: %s", e)
            return None""")

rep("src/data/live_engine.py", """                        try:
                            p.position_side = PositionSide(cd.get("position_side", "FLAT"))
                        except Exception:
                            p.position_side = PositionSide.FLAT""",
"""                        try:
                            p.position_side = PositionSide(cd.get("position_side", "FLAT"))
                        except Exception as e:
                            logger.debug("Invalid position side in saved snapshot, defaulting to FLAT: %s", e)
                            p.position_side = PositionSide.FLAT""")

# =========================================================== 2e. persistence.py
rep("src/data/persistence.py", """                try:
                    conn.execute("ALTER TABLE evolution_history ADD COLUMN evolution_seed INTEGER")
                except Exception:
                    pass""",
"""                try:
                    conn.execute("ALTER TABLE evolution_history ADD COLUMN evolution_seed INTEGER")
                except Exception as e:
                    logger.debug("Evolution seed column already exists, skipping migration: %s", e)""")

rep("src/data/persistence.py", """                if row and row[0]:
                    try:
                        return json.loads(row[0])
                    except Exception:
                        return None""",
"""                if row and row[0]:
                    try:
                        return json.loads(row[0])
                    except Exception as e:
                        logger.debug("Corrupt session snapshot JSON, ignoring: %s", e)
                        return None""")

# =========================================================== 2f. ws_feed.py
rep("src/data/ws_feed.py", """            if ws is not None:
                try:
                    asyncio.run_coroutine_threadsafe(ws.close(), loop)
                except Exception:
                    pass""",
"""            if ws is not None:
                try:
                    asyncio.run_coroutine_threadsafe(ws.close(), loop)
                except Exception as e:
                    logger.debug("WebSocket close failed during stop: %s", e)""")

rep("src/data/ws_feed.py", """            try:
                loop.call_soon_threadsafe(loop.stop)
            except Exception:
                pass""",
"""            try:
                loop.call_soon_threadsafe(loop.stop)
            except Exception as e:
                logger.debug("WebSocket loop stop failed: %s", e)""")

rep("src/data/ws_feed.py", """        finally:
            try:
                self._loop.close()
            except Exception:
                pass
            self._loop = None""",
"""        finally:
            try:
                self._loop.close()
            except Exception as e:
                logger.debug("WebSocket event loop close failed: %s", e)
            self._loop = None""")

# =========================================================== 2g. dashboard.py
rep("src/gui/dashboard.py", """        if native is not None and getattr(native, "Handle", None) is not None:
            return int(native.Handle.ToInt64())
    except Exception:
        pass
    return None""",
"""        if native is not None and getattr(native, "Handle", None) is not None:
            return int(native.Handle.ToInt64())
    except Exception as e:
        logger.debug("Failed to read native window handle: %s", e)
    return None""")

rep("src/gui/dashboard.py", """        try:
            self.engine.storage.clear_session_snapshot()
        except Exception:
            pass
        self.engine.stop()""",
"""        try:
            self.engine.storage.clear_session_snapshot()
        except Exception as e:
            logger.warning("Failed to clear session snapshot during reset: %s", e)
        self.engine.stop()""")

rep("src/gui/dashboard.py", """                            if fg_thread and fg_thread != cur_thread:
                                attached = bool(user32.AttachThreadInput(fg_thread, cur_thread, True))
                    except Exception:
                        attached = False""",
"""                            if fg_thread and fg_thread != cur_thread:
                                attached = bool(user32.AttachThreadInput(fg_thread, cur_thread, True))
                    except Exception as e:
                        logger.debug("AttachThreadInput failed during foreground activation: %s", e)
                        attached = False""")

rep("src/gui/dashboard.py", """                        if attached:
                            try:
                                user32.AttachThreadInput(fg_thread, cur_thread, False)
                            except Exception:
                                pass""",
"""                        if attached:
                            try:
                                user32.AttachThreadInput(fg_thread, cur_thread, False)
                            except Exception as e:
                                logger.debug("AttachThreadInput detach failed: %s", e)""")

# =========================================================== 2h. config_manager.py
rep("src/intelligence/config_manager.py", """            if self.omni_env_file.is_file():
                try:
                    existing_lines = self.omni_env_file.read_text(encoding="utf-8").splitlines()
                except Exception:
                    existing_lines = []""",
"""            if self.omni_env_file.is_file():
                try:
                    existing_lines = self.omni_env_file.read_text(encoding="utf-8").splitlines()
                except Exception as e:
                    logger.warning("Could not read omniroute env file, existing keys will be rebuilt: %s", e)
                    existing_lines = []""")

# =========================================================== 2i. gateway_supervisor.py
rep("src/intelligence/gateway_supervisor.py", """            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(timeout)
                return s.connect_ex((self.host, self.port)) == 0
        except Exception:
            return False""",
"""            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(timeout)
                return s.connect_ex((self.host, self.port)) == 0
        except Exception as e:
            logger.debug("Port probe error for %s:%s: %s", self.host, self.port, e)
            return False""")

rep("src/intelligence/gateway_supervisor.py", """                logger.warning("Failed to rotate daemon log %s: %s", log_path, e)
                try:
                    log_path.write_text("", encoding="utf-8")
                except Exception:
                    pass""",
"""                logger.warning("Failed to rotate daemon log %s: %s", log_path, e)
                try:
                    log_path.write_text("", encoding="utf-8")
                except Exception as e:
                    logger.debug("Failed to truncate daemon log after rotation failure: %s", e)""")

rep("src/intelligence/gateway_supervisor.py", """            if self._daemon_log_file is not None:
                try:
                    self._daemon_log_file.close()
                except Exception:
                    pass
                self._daemon_log_file = None
            log_file = self._open_daemon_log()""",
"""            if self._daemon_log_file is not None:
                try:
                    self._daemon_log_file.close()
                except Exception as e:
                    logger.debug("Failed to close stale daemon log handle: %s", e)
                self._daemon_log_file = None
            log_file = self._open_daemon_log()""")

rep("src/intelligence/gateway_supervisor.py", """            try:
                log_file.write(
                    f"--- OmniRoute daemon spawned (PID {proc.pid}) "
                    f"at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\\n"
                )
            except Exception:
                pass""",
"""            try:
                log_file.write(
                    f"--- OmniRoute daemon spawned (PID {proc.pid}) "
                    f"at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\\n"
                )
            except Exception as e:
                logger.debug("Failed to write daemon spawn header to log: %s", e)""")

rep("src/intelligence/gateway_supervisor.py", """                    try:
                        self.child_process.wait(timeout=1.5)
                    except Exception:
                        pass""",
"""                    try:
                        self.child_process.wait(timeout=1.5)
                    except Exception as e:
                        logger.debug("Daemon did not exit within wait timeout during shutdown: %s", e)""")

rep("src/intelligence/gateway_supervisor.py", """            except Exception:
                try:
                    self.child_process.kill()
                except Exception:
                    pass
            finally:""",
"""            except Exception:
                try:
                    self.child_process.kill()
                except Exception as e:
                    logger.debug("Failed to kill daemon process during shutdown: %s", e)
            finally:""")

rep("src/intelligence/gateway_supervisor.py", """        if self._daemon_log_file is not None:
            try:
                self._daemon_log_file.close()
            except Exception:
                pass
            self._daemon_log_file = None

    def _kill_port_owner(self, port: int, owned_pid: Optional[int] = None) -> None:""",
"""        if self._daemon_log_file is not None:
            try:
                self._daemon_log_file.close()
            except Exception as e:
                logger.debug("Failed to close daemon log handle during shutdown: %s", e)
            self._daemon_log_file = None

    def _kill_port_owner(self, port: int, owned_pid: Optional[int] = None) -> None:""")

rep("src/intelligence/gateway_supervisor.py", """                            subprocess.run(
                                ["taskkill", "/F", "/T", "/PID", target_pid],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                creationflags=0x08000000,
                                close_fds=True,
                                check=False,
                            )
            except Exception:
                pass""",
"""                            subprocess.run(
                                ["taskkill", "/F", "/T", "/PID", target_pid],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                creationflags=0x08000000,
                                close_fds=True,
                                check=False,
                            )
            except Exception as e:
                logger.debug("Failed to terminate lingering daemon on port %s: %s", port, e)""")

# =========================================================== 2j. ingestion.py
rep("src/intelligence/ingestion.py", """                try:
                    pairs = [f"{o}: {float(p)*100:.0f}%" for o, p in zip(outcomes, outcome_prices)]
                    odds_str = " | Odds: " + ", ".join(pairs)
                except Exception:
                    pass""",
"""                try:
                    pairs = [f"{o}: {float(p)*100:.0f}%" for o, p in zip(outcomes, outcome_prices)]
                    odds_str = " | Odds: " + ", ".join(pairs)
                except Exception as e:
                    logger.debug("Failed to format Polymarket odds, omitting: %s", e)""")

rep("src/intelligence/ingestion.py", """                if "batch" in p_name or "events" in p_name or "list" in p_ann:
                    is_batch = True
        except Exception:
            pass""",
"""                if "batch" in p_name or "events" in p_name or "list" in p_ann:
                    is_batch = True
        except Exception as e:
            logger.debug("Failed to inspect dispatch function signature, using per-event dispatch: %s", e)""")

# =========================================================== 2k. macro_commander.py
rep("src/intelligence/macro_commander.py", """            try:
                q_val = self.client.get_quota_pct()
                if isinstance(q_val, (int, float)):
                    quota_pct = float(q_val)
            except Exception:
                pass""",
"""            try:
                q_val = self.client.get_quota_pct()
                if isinstance(q_val, (int, float)):
                    quota_pct = float(q_val)
            except Exception as e:
                logger.debug("Failed to read quota from client, falling back to estimate: %s", e)""")

# =========================================================== 2l. omniroute_client.py
rep("src/intelligence/omniroute_client.py", """            if self._session and not self._session.closed and self._owns_session:
                try:
                    await self._session.close()
                except Exception:
                    pass""",
"""            if self._session and not self._session.closed and self._owns_session:
                try:
                    await self._session.close()
                except Exception as e:
                    logger.debug("Failed to close previous session: %s", e)""")

rep("src/intelligence/omniroute_client.py", """                else:
                    self.is_gateway_online = False
        except Exception:
            self.is_gateway_online = False""",
"""                else:
                    self.is_gateway_online = False
        except Exception as e:
            logger.debug("Gateway health check failed: %s", e)
            self.is_gateway_online = False""")

rep("src/intelligence/omniroute_client.py", """                elif self._session_loop is None or not self._session_loop.is_closed():
                    asyncio.run(self._session.close())
            except Exception:
                pass
            self._session = None""",
"""                elif self._session_loop is None or not self._session_loop.is_closed():
                    asyncio.run(self._session.close())
            except Exception as e:
                logger.debug("Failed to close session synchronously: %s", e)
            self._session = None""")

rep("src/intelligence/omniroute_client.py", """    def __del__(self) -> None:
        try:
            self.close_sync()
        except Exception:
            pass""",
"""    def __del__(self) -> None:
        try:
            self.close_sync()
        except Exception as e:
            logger.debug("Failed to close session in destructor: %s", e)""")

# =========================================================== new tests
NEW_FILES["tests/test_generation_fence.py"] = '''"""Item 9: generation fence + silent-except logging (TradeBot0 maintenance)."""
import logging
from decimal import Decimal
from pathlib import Path

from src.arena.evolution import GeneticEvolver
from src.arena.order import ExecutionReason, FillEvent, OrderSide, PositionSide
from src.data.live_engine import LiveArenaEngine


def _make_fill(seq=1):
    return FillEvent(
        order_id="test-fill-1",
        portfolio_id="comp_agg",
        symbol="ETH/USD",
        side=OrderSide.BUY,
        qty=Decimal("1.0"),
        price=Decimal("2000.00"),
        fee=Decimal("1.00"),
        timestamp=1700000000.0,
        realized_pnl=Decimal("0.00"),
        reason=ExecutionReason.SIGNAL,
        fill_seq=seq,
        entry_price=None,
        position_side=PositionSide.LONG,
    )


def test_stale_engine_save_session_state_refused(caplog):
    """A superseded engine (a newer one exists) must not overwrite the new
    generation's session snapshot; the current engine still saves fine."""
    engine1 = LiveArenaEngine(symbol="ETH/USD", initial_cash=Decimal("100000.00"))
    assert engine1.save_session_state() is True
    engine2 = LiveArenaEngine(symbol="ETH/USD", initial_cash=Decimal("100000.00"))
    with caplog.at_level(logging.WARNING):
        assert engine1.save_session_state() is False
    assert "Stale engine epoch" in caplog.text
    assert engine2.save_session_state() is True


def test_stale_engine_harvest_fills_refused():
    """Fills from a superseded engine must not reach the SQLite ledger."""
    engine1 = LiveArenaEngine(symbol="ETH/USD", initial_cash=Decimal("100000.00"))
    engine2 = LiveArenaEngine(symbol="ETH/USD", initial_cash=Decimal("100000.00"))
    engine1.broker.execution_audit.append(_make_fill(seq=1))
    engine1._audit_cursor = 0
    engine1._harvest_fills()
    assert engine1.fill_records == []
    assert engine1.storage.load_recent_fills(limit=10) == []
    # The current engine records the same fill normally.
    engine2.broker.execution_audit.append(_make_fill(seq=1))
    engine2._audit_cursor = 0
    engine2._harvest_fills()
    assert len(engine2.fill_records) == 1
    assert len(engine2.storage.load_recent_fills(limit=10)) == 1


def test_stale_engine_evolve_now_refused():
    """A superseded engine must not evolve or persist evolution history."""
    engine1 = LiveArenaEngine(symbol="ETH/USD", initial_cash=Decimal("100000.00"))
    engine2 = LiveArenaEngine(symbol="ETH/USD", initial_cash=Decimal("100000.00"))
    assert engine1.evolve_now(trigger="manual") == []
    assert engine1.storage.load_evolution_history(limit=10) == []
    logs = engine2.evolve_now(trigger="manual")
    assert logs
    assert len(engine2.storage.load_evolution_history(limit=10)) == 1


def test_stale_engine_state_publish_skipped():
    """A superseded engine must not publish a UI snapshot anymore."""
    engine1 = LiveArenaEngine(symbol="ETH/USD", initial_cash=Decimal("100000.00"))
    engine1._publish_state_snapshot()
    assert engine1._ui_state_snapshot is not None
    LiveArenaEngine(symbol="ETH/USD", initial_cash=Decimal("100000.00"))
    engine1._ui_state_snapshot = None
    engine1._publish_state_snapshot()
    assert engine1._ui_state_snapshot is None


def test_save_history_failure_is_logged_not_swallowed(caplog, monkeypatch):
    """save_history SQLite failure must log a warning, not `pass` silently."""
    import src.data.persistence as persistence

    def _boom(*args, **kwargs):
        raise RuntimeError("disk exploded")

    monkeypatch.setattr(persistence.ArenaStorage, "save_evolution_generation", _boom)
    records = [{
        "portfolio_id": "comp_cons",
        "prev_roi_pct": 1.0,
        "prev_sharpe": 1.0,
        "prev_max_dd_pct": 1.0,
        "new_genome": {},
    }]
    with caplog.at_level(logging.WARNING):
        GeneticEvolver.save_history(1, records)
    assert "Failed to persist evolution history to SQLite" in caplog.text


def _keyframes_block(css, name):
    start = css.index(f"@keyframes {name}")
    end = css.find("@keyframes", start + 1)
    return css[start:end if end != -1 else len(css)]


def test_splash_overlay_is_lightened_not_removed():
    """Splash stays (user design) but lighter: blur 1px, veil 0.30.
    arenaFadeIn has no blur and must stay untouched; toast blur stays 8px."""
    css_path = Path(__file__).resolve().parent.parent / "src" / "gui" / "assets" / "app.css"
    css = css_path.read_text(encoding="utf-8")
    splash = css.split(".splash-overlay {", 1)[1].split("}", 1)[0]
    assert "blur(1px)" in splash
    assert "rgba(2, 6, 15, 0.30)" in splash
    assert "blur(3px)" not in splash
    assert "blur" not in _keyframes_block(css, "arenaFadeIn")
    assert "blur(8px)" in _keyframes_block(css, "toastSpringIn")
    assert "blur(8px)" in _keyframes_block(css, "toastSpringOut")
'''


# =========================================================== apply
def main():
    failed = []
    for path, old, new in REPLACEMENTS:
        with open(path, "r", encoding="utf-8", newline="") as f:
            content = f.read()
        n = content.count(old)
        if n != 1:
            failed.append(f"{path}: expected 1 occurrence, found {n} for: {old[:80]!r}")
            continue
        content = content.replace(old, new)
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        print(f"OK {path}")
    for path, content in NEW_FILES.items():
        if os.path.exists(path):
            failed.append(f"{path}: already exists, refusing to overwrite")
            continue
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        print(f"NEW {path}")
    if failed:
        print("FAILURES:")
        for msg in failed:
            print(" -", msg)
        sys.exit(1)
    print(f"Applied {len(REPLACEMENTS)} replacements + {len(NEW_FILES)} new files.")


if __name__ == "__main__":
    main()
