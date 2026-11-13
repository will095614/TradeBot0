"""
src/data/persistence.py - Native SQLite WAL Local Engine Storage
Implements Phase 2 (P1): Deterministic State Persistence in Write-Ahead Logging (WAL) mode.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import sys
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


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
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA temp_store=MEMORY;")
        return conn

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

                    CREATE INDEX IF NOT EXISTS idx_candles_ts ON candles_1m(timestamp);
                    CREATE INDEX IF NOT EXISTS idx_ledger_ts ON execution_ledger(timestamp);
                    """
                )
                # Schema migration for pre-existing DBs: evolution_seed column
                # (added with the deterministic-seed change). ALTER fails if the
                # column already exists; that is expected and safe to ignore.
                try:
                    conn.execute("ALTER TABLE evolution_history ADD COLUMN evolution_seed INTEGER")
                except Exception as e:
                    logger.debug("Evolution seed column already exists, skipping migration: %s", e)

    def save_candle(self, c: Dict[str, Any]) -> None:
        with self._db_lock:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO candles_1m (timestamp, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        int(c["t"]),
                        float(c["o"]),
                        float(c["h"]),
                        float(c["l"]),
                        float(c["c"]),
                        float(c.get("v", 0.0)),
                    ),
                )

    def save_candles_batch(self, candles: List[Dict[str, Any]]) -> None:
        if not candles:
            return
        rows = [
            (
                int(c["t"]),
                float(c["o"]),
                float(c["h"]),
                float(c["l"]),
                float(c["c"]),
                float(c.get("v", 0.0)),
            )
            for c in candles
        ]
        with self._db_lock:
            with self._get_connection() as conn:
                conn.executemany(
                    """
                    INSERT OR REPLACE INTO candles_1m (timestamp, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )

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

    def record_fill(self, fill_data: Dict[str, Any]) -> None:
        with self._db_lock:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO execution_ledger (
                        fill_seq, timestamp, portfolio_id, strategy, symbol,
                        side, action_label, qty, price, entry_price, realized_pnl, fee, reason, is_live
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        int(fill_data.get("seq", 0)),
                        float(fill_data.get("timestamp", time.time())),
                        str(fill_data.get("portfolio_id", "")),
                        str(fill_data.get("strategy", "")),
                        str(fill_data.get("symbol", "ETH/USD")),
                        str(fill_data.get("side", "")),
                        str(fill_data.get("action_label", "")),
                        float(fill_data.get("qty", 0.0)),
                        float(fill_data.get("price", 0.0)),
                        float(fill_data["entry_price"]) if fill_data.get("entry_price") is not None else None,
                        float(fill_data["pnl"]) if fill_data.get("pnl") is not None else None,
                        float(fill_data.get("fee", 0.0)),
                        str(fill_data.get("reason", "")),
                        1 if fill_data.get("is_live") else 0,
                    ),
                )

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
        genome_str = elite_genome if isinstance(elite_genome, str) else json.dumps(elite_genome, default=str)
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
                        float(champion_roi),
                        float(champion_sharpe),
                        float(champion_max_dd),
                        genome_str,
                        int(evolution_seed) if evolution_seed is not None else None,
                    ),
                )

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

    def save_session_snapshot(self, snapshot: Dict[str, Any]) -> None:
        """Persist full arena session snapshot (competitors, cash, positions, genomes, generation)."""
        data_str = json.dumps(snapshot, default=str)
        with self._db_lock:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO session_snapshot (key, timestamp, data)
                    VALUES ('latest_session', ?, ?)
                    """,
                    (time.time(), data_str),
                )

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

    def clear_session_snapshot(self) -> None:
        """Clear active saved session snapshot on hard reset."""
        with self._db_lock:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM session_snapshot WHERE key = 'latest_session'")


