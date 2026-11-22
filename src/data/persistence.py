"""
src/data/persistence.py - Native SQLite WAL Local Engine Storage
Implements Phase 2 (P1): Deterministic State Persistence in Write-Ahead Logging (WAL) mode.
"""
from __future__ import annotations

import functools
import json
import logging
import math
import os
import sqlite3
import sys
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _sanitize_json_value(obj: Any) -> Any:
    """Recursively replaces non-finite floats (NaN/Inf) with None so JSON stays strict RFC 8259."""
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: _sanitize_json_value(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_json_value(v) for v in obj]
    if isinstance(obj, tuple):
        return [_sanitize_json_value(v) for v in obj]
    return obj


def _retry_on_db_error(fn):
    """Retry a storage call once after backing off on transient lock errors or
    resetting a broken connection.

    See the module note on the persistent connection: the only new
    failure mode versus per-call connections is a stale handle, and
    one reset + retry recovers from it exactly as a fresh connect
    used to. Genuine errors (bad SQL, disk full) simply raise again
    on the retry.
    """

    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        try:
            return fn(self, *args, **kwargs)
        except (sqlite3.IntegrityError, sqlite3.InterfaceError):
            raise
        except sqlite3.OperationalError as exc:
            msg = str(exc).lower()
            if "locked" in msg or "busy" in msg:
                # Transient WAL contention: wait briefly instead of running a
                # disruptive wal_checkpoint(TRUNCATE) + reconnect storm.
                time.sleep(0.05)
                return fn(self, *args, **kwargs)
            with self._db_lock:
                self._reset_connection()
            return fn(self, *args, **kwargs)
        except sqlite3.Error:
            with self._db_lock:
                self._reset_connection()
            return fn(self, *args, **kwargs)

    return wrapper


class ArenaStorage:
    """
    Zero-dependency embedded SQLite WAL persistence engine for TradeBot0.
    Provides sub-millisecond writes and instant cold-start candle/ledger hydration.
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        if db_path is None:
            env_dir = os.environ.get("ARENA_MEMORY_DIR")
            if env_dir:
                base_dir = env_dir
            elif getattr(sys, "frozen", False):
                appdata = os.environ.get("APPDATA")
                base_dir = os.path.join(appdata, "TradeBot0", "data") if appdata else os.path.join(os.path.expanduser("~"), ".tradebot0", "data")
            else:
                base_dir = "data"
            db_path = os.path.join(base_dir, "arena_history.db")
        parent_dir = os.path.dirname(os.path.abspath(db_path))
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        self.db_path: str = db_path
        self._db_lock = threading.RLock()
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Return the single persistent connection for this storage.

        Phase 2: opening a fresh connection per write cost ~8 ms per
        tick (connect + 3 PRAGMAs + commit + close + WAL checkpoint on
        last-close), ~65% of the whole tick. One lazily created
        connection per instance removes that cost; the per-write
        commit is unchanged, so crash safety is identical to before
        (WAL + synchronous=NORMAL, commit per candle).
        check_same_thread=False is required because one storage
        instance is shared by the live-loop, bootstrap, harvest and
        digest threads -- but every caller holds self._db_lock, so
        the connection is still used by only one thread at a time.
        """
        with self._db_lock:
            if self._conn is None:
                conn = sqlite3.connect(self.db_path, timeout=5.0, check_same_thread=False)
                try:
                    conn.execute("PRAGMA busy_timeout=5000;")
                    conn.execute("PRAGMA journal_mode=WAL;")
                    conn.execute("PRAGMA synchronous=NORMAL;")
                    conn.execute("PRAGMA temp_store=MEMORY;")
                except Exception:
                    conn.close()
                    raise
                self._conn = conn
            return self._conn

    def _reset_connection(self) -> None:
        """Drop the persistent connection (checkpointing the WAL first).

        Best effort: a checkpoint can fail while another connection
        still holds the database; the data is safe either way because
        every write already committed. The next call reopens lazily.
        """
        with self._db_lock:
            conn, self._conn = self._conn, None
            if conn is not None:
                try:
                    conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                except Exception as e:
                    logger.debug("Best-effort WAL checkpoint failed on connection reset: %s", e)
                try:
                    conn.close()
                except Exception as e:
                    logger.debug("SQLite close failed during connection reset: %s", e)

    def close(self) -> None:
        """Release the persistent connection; the storage stays usable
        (the next call reopens lazily), so an engine restarted after
        stop() is unaffected."""
        self._reset_connection()

    @_retry_on_db_error
    def _init_db(self) -> None:
        with self._db_lock:
            with self._get_connection() as conn:
                conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS candles_1m (
                        timestamp INTEGER PRIMARY KEY,
                        open REAL NOT NULL,
                        high REAL NOT NULL,
                        low REAL NOT NULL,
                        close REAL NOT NULL,
                        volume REAL NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS execution_ledger (
                        fill_seq INTEGER PRIMARY KEY,
                        timestamp REAL NOT NULL,
                        portfolio_id TEXT NOT NULL,
                        strategy TEXT NOT NULL,
                        symbol TEXT NOT NULL,
                        side TEXT NOT NULL,
                        action_label TEXT NOT NULL,
                        qty REAL NOT NULL,
                        price REAL NOT NULL,
                        entry_price REAL,
                        realized_pnl REAL,
                        fee REAL NOT NULL,
                        reason TEXT NOT NULL,
                        is_live INTEGER NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS evolution_history (
                        generation INTEGER PRIMARY KEY,
                        timestamp REAL NOT NULL,
                        champion_id TEXT NOT NULL,
                        champion_name TEXT NOT NULL,
                        champion_roi REAL NOT NULL,
                        champion_sharpe REAL NOT NULL,
                        champion_max_dd REAL NOT NULL,
                        elite_genome TEXT NOT NULL,
                        evolution_seed INTEGER
                    );

                    CREATE TABLE IF NOT EXISTS session_snapshot (
                        key TEXT PRIMARY KEY,
                        timestamp REAL NOT NULL,
                        data TEXT NOT NULL
                    );

                    CREATE INDEX IF NOT EXISTS idx_ledger_ts ON execution_ledger(timestamp);
                    """
                )
                # Schema migration for pre-existing DBs: check PRAGMA table_info
                # instead of swallowing arbitrary OperationalErrors on ALTER TABLE.
                cols = {row[1] for row in conn.execute("PRAGMA table_info(evolution_history)").fetchall()}
                if "evolution_seed" not in cols:
                    conn.execute("ALTER TABLE evolution_history ADD COLUMN evolution_seed INTEGER")

    @staticmethod
    def _candle_row(c: Dict[str, Any]) -> Optional[tuple]:
        try:
            t_f = float(c["t"])
            o = float(c["o"])
            h = float(c["h"])
            lo = float(c["l"])
            cl = float(c["c"])
            v = float(c.get("v", 0.0))
        except (KeyError, TypeError, ValueError):
            return None
        if not (math.isfinite(t_f) and math.isfinite(o) and math.isfinite(h) and math.isfinite(lo) and math.isfinite(cl)):
            return None
        if o <= 0.0 or h <= 0.0 or lo <= 0.0 or cl <= 0.0:
            return None
        if not math.isfinite(v) or v < 0.0:
            v = 0.0
        return (int(t_f), o, h, lo, cl, v)

    @_retry_on_db_error
    def save_candle(self, c: Dict[str, Any]) -> None:
        row = self._candle_row(c)
        if row is None:
            return
        with self._db_lock:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO candles_1m (timestamp, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    row,
                )

    @_retry_on_db_error
    def save_candles_batch(self, candles: List[Dict[str, Any]]) -> None:
        if not candles:
            return
        rows = [r for r in (self._candle_row(c) for c in candles) if r is not None]
        if not rows:
            return
        with self._db_lock:
            with self._get_connection() as conn:
                conn.executemany(
                    """
                    INSERT OR REPLACE INTO candles_1m (timestamp, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )

    @_retry_on_db_error
    def load_latest_candles(self, limit: int = 150) -> List[Dict[str, Any]]:
        with self._db_lock:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT timestamp, open, high, low, close, volume
                    FROM candles_1m
                    ORDER BY timestamp DESC
                    LIMIT ?
                    """,
                    (int(limit),),
                )
                rows = cursor.fetchall()
                return [
                    {
                        "t": float(r[0]),
                        "o": float(r[1]),
                        "h": float(r[2]),
                        "l": float(r[3]),
                        "c": float(r[4]),
                        "v": float(r[5]),
                    }
                    for r in reversed(rows)
                ]

    @staticmethod
    def _fill_row(f: Dict[str, Any], default_ts: float) -> Optional[tuple]:
        try:
            seq = int(f.get("seq", 0))
            ts = float(f.get("timestamp", default_ts))
            qty = float(f.get("qty", 0.0))
            price = float(f.get("price", 0.0))
            fee = float(f.get("fee", 0.0))
        except (TypeError, ValueError):
            return None
        if not (math.isfinite(ts) and math.isfinite(qty) and math.isfinite(price)):
            return None
        if qty < 0.0 or price < 0.0:
            return None
        if not math.isfinite(fee) or fee < 0.0:
            fee = 0.0
        entry_p = None
        if f.get("entry_price") is not None:
            try:
                ep = float(f["entry_price"])
                if math.isfinite(ep) and ep > 0.0:
                    entry_p = ep
            except (TypeError, ValueError):
                entry_p = None
        pnl = None
        if f.get("pnl") is not None:
            try:
                pv = float(f["pnl"])
                if math.isfinite(pv):
                    pnl = pv
            except (TypeError, ValueError):
                pnl = None
        return (
            seq,
            ts,
            str(f.get("portfolio_id", "")),
            str(f.get("strategy", "")),
            str(f.get("symbol", "ETH/USD")),
            str(f.get("side", "")),
            str(f.get("action_label", "")),
            qty,
            price,
            entry_p,
            pnl,
            fee,
            str(f.get("reason", "")),
            1 if f.get("is_live") else 0,
        )

    @_retry_on_db_error
    def record_fill(self, fill_data: Dict[str, Any]) -> None:
        row = self._fill_row(fill_data, time.time())
        if row is None:
            return
        with self._db_lock:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO execution_ledger (
                        fill_seq, timestamp, portfolio_id, strategy, symbol,
                        side, action_label, qty, price, entry_price, realized_pnl, fee, reason, is_live
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    row,
                )

    @_retry_on_db_error
    def record_fills_batch(self, fills: List[Dict[str, Any]]) -> None:
        if not fills:
            return
        now = time.time()
        rows = [r for r in (self._fill_row(f, now) for f in fills) if r is not None]
        if not rows:
            return
        with self._db_lock:
            with self._get_connection() as conn:
                conn.executemany(
                    """
                    INSERT OR REPLACE INTO execution_ledger (
                        fill_seq, timestamp, portfolio_id, strategy, symbol,
                        side, action_label, qty, price, entry_price, realized_pnl, fee, reason, is_live
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )

    @_retry_on_db_error
    def prune_old_candles(self, max_age_sec: float = 30 * 86400.0) -> int:
        """Delete 1-minute candles older than max_age_sec to bound SQLite growth."""
        cutoff = int(time.time() - max(60.0, float(max_age_sec)))
        with self._db_lock:
            with self._get_connection() as conn:
                cur = conn.execute("DELETE FROM candles_1m WHERE timestamp < ?", (cutoff,))
                return int(cur.rowcount or 0)

    @_retry_on_db_error
    def load_recent_fills(self, limit: int = 60) -> List[Dict[str, Any]]:
        with self._db_lock:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT fill_seq, timestamp, portfolio_id, strategy, symbol,
                           side, action_label, qty, price, entry_price, realized_pnl, fee, reason, is_live
                    FROM execution_ledger
                    ORDER BY fill_seq DESC
                    LIMIT ?
                    """,
                    (int(limit),),
                )
                rows = cursor.fetchall()
                return [
                    {
                        "seq": int(r[0]),
                        "timestamp": float(r[1]),
                        "portfolio_id": str(r[2]),
                        "strategy": str(r[3]),
                        "symbol": str(r[4]),
                        "side": str(r[5]),
                        "action_label": str(r[6]),
                        "qty": float(r[7]),
                        "price": float(r[8]),
                        "entry_price": float(r[9]) if r[9] is not None else None,
                        "pnl": float(r[10]) if r[10] is not None else None,
                        "fee": float(r[11]),
                        "reason": str(r[12]),
                        "is_live": bool(r[13]),
                    }
                    for r in rows
                ]

    @_retry_on_db_error
    def save_evolution_generation(
        self,
        generation: int,
        champion_id: str,
        champion_name: str,
        champion_roi: float,
        champion_sharpe: float,
        champion_max_dd: float,
        elite_genome: Any,
        evolution_seed: Optional[int] = None,
    ) -> None:
        genome_str = (
            elite_genome
            if isinstance(elite_genome, str)
            else json.dumps(_sanitize_json_value(elite_genome), default=str, allow_nan=False)
        )
        safe_roi = float(champion_roi) if math.isfinite(float(champion_roi)) else 0.0
        safe_sharpe = float(champion_sharpe) if math.isfinite(float(champion_sharpe)) else 0.0
        safe_dd = float(champion_max_dd) if math.isfinite(float(champion_max_dd)) else 0.0
        with self._db_lock:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO evolution_history (
                        generation, timestamp, champion_id, champion_name,
                        champion_roi, champion_sharpe, champion_max_dd, elite_genome,
                        evolution_seed
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        int(generation),
                        time.time(),
                        str(champion_id),
                        str(champion_name),
                        safe_roi,
                        safe_sharpe,
                        safe_dd,
                        genome_str,
                        int(evolution_seed) if evolution_seed is not None else None,
                    ),
                )

    @_retry_on_db_error
    def load_evolution_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._db_lock:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT generation, timestamp, champion_id, champion_name,
                           champion_roi, champion_sharpe, champion_max_dd, elite_genome,
                           evolution_seed
                    FROM evolution_history
                    ORDER BY generation DESC
                    LIMIT ?
                    """,
                    (int(limit),),
                )
                rows = cursor.fetchall()
                return [
                    {
                        "generation": int(r[0]),
                        "timestamp": float(r[1]),
                        "champion_id": str(r[2]),
                        "champion_name": str(r[3]),
                        "champion_roi": float(r[4]),
                        "champion_sharpe": float(r[5]),
                        "champion_max_dd": float(r[6]),
                        "elite_genome": str(r[7]),
                        "evolution_seed": (int(r[8]) if r[8] is not None else None),
                    }
                    for r in reversed(rows)
                ]

    @_retry_on_db_error
    def save_session_snapshot(self, snapshot: Dict[str, Any]) -> None:
        """Persist full arena session snapshot (competitors, cash, positions, genomes, generation)."""
        data_str = json.dumps(_sanitize_json_value(snapshot), default=str, allow_nan=False)
        with self._db_lock:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO session_snapshot (key, timestamp, data)
                    VALUES ('latest_session', ?, ?)
                    """,
                    (time.time(), data_str),
                )

    @_retry_on_db_error
    def load_session_snapshot(self) -> Optional[Dict[str, Any]]:
        """Retrieve most recent saved session snapshot if present."""
        with self._db_lock:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT data FROM session_snapshot WHERE key = 'latest_session'"
                )
                row = cursor.fetchone()
                if row and row[0]:
                    try:
                        return json.loads(row[0])
                    except Exception as e:
                        logger.debug("Corrupt session snapshot JSON, ignoring: %s", e)
                        return None
                return None

    @_retry_on_db_error
    def clear_session_snapshot(self) -> None:
        """Clear active saved session snapshot on hard reset."""
        with self._db_lock:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM session_snapshot WHERE key = 'latest_session'")


