"""TradeBot0 Phase 3 soak harness: long-duration / accelerated simulation.

Simulates many hours of live-engine ticks headless with synthetic prices
(mocked feeds, ZERO network) and watches for slow failures: memory growth,
multi-generation evolution, circuit-breaker trips + recovery, and log spam.

Usage (on the PC, from the project root, .venv python):
    .venv\\Scripts\\python.exe scripts\\soak_engine.py [--ticks 30000]
        [--wall-cap-sec 900] [--seed 20261113]
        [--out scratch\\soak_phase3_out.json] [--tmp-dir scratch\\soak_tmp_p3]

What it simulates (defaults):
- 15,000 ticks at 1 sim-second per tick = 15,000 sim-seconds (~4.2 sim-hours)
  of the real per-cadence slice body (same slice as the Phase 0/2 tick probes:
  _update_candle, indicators, EMA, broker.on_tick + fill handling,
  _ensure_active_live_positions, _evaluate_live_strategies (6 strategies),
  _record_series_point, _publish_state_snapshot), plus the real
  auto-evolution trigger check (_auto_evolve_reason) every tick.
- Price: deterministic seeded sine + noise (amplitude $120, period 90 ticks,
  uniform noise +/-$6), so TP/SL brackets fire regularly and closed trades
  accumulate toward the 30-trade evolution trigger (with the real 30-minute
  debounce, i.e. >= 1800 ticks between trade-triggered evolutions).
- Then, in order: a forced time-triggered evolution (last_evolve_ts wound
  back past the 6 h cap), a circuit-breaker scenario on a fresh engine
  (naked long + engineered -35% crash -> trip, force-close, blocked
  re-entry, evolve reset, trading resumes), and a save/restore consistency
  check (session snapshot round-trip + arena_history.json vs SQLite
  evolution_history agreement).

Isolation: all state lives under --tmp-dir (SQLite DB + ARENA_MEMORY_DIR);
the user's live data/ and memory/ are never touched. The intel digest
thread is suppressed (ARENA_FAST_TEST=1): it needs a live gateway/LLM and
is out of scope for this hermetic soak.

Wall-clock cap: the loop checks the clock every 200 ticks and stops
gracefully with truncated=true if --wall-cap-sec is exceeded, so a run
never hangs the machine. Expected wall time for the defaults is a few
minutes (tick cost ~1-3 ms with tracemalloc on).
"""
import argparse
import datetime
import json
import math
import os
import random
import shutil
import sqlite3
import sys
import time
import tracemalloc
from collections import Counter
from decimal import Decimal

# --- isolation MUST be set before importing src modules -------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

DEFAULT_TMP = os.path.join("scratch", "soak_tmp_p3")
DEFAULT_OUT = os.path.join("scratch", "soak_phase3_out.json")


def _parse_args():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ticks", type=int, default=15000)
    ap.add_argument("--wall-cap-sec", type=float, default=2400.0)
    ap.add_argument("--seed", type=int, default=20261113)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--tmp-dir", default=DEFAULT_TMP)
    return ap.parse_args()


# Import-safe: argument parsing and run isolation live in main(), so the
# helpers (synth_price, do_slice, genome_valid, ...) can be imported by
# tests/test_phase3_soak.py without side effects. Module-level defaults:
ARGS = None
TMP_DIR = None
MEM_DIR = None
DB_PATH = None
SEED = 20261113

import ctypes
from ctypes import wintypes

from src.arena.order import ExecutionReason, OrderSide, OrderTicket, OrderType, PositionSide
from src.data.eth_feed import CandleBar, ETHFeed
from src.data.live_engine import LiveArenaEngine, LiveQuote
from src.data.persistence import ArenaStorage


class _PMC(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t)]


def _win_mem():
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(_PMC), wintypes.DWORD]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    pmc = _PMC()
    pmc.cb = ctypes.sizeof(pmc)
    h = ctypes.windll.kernel32.GetCurrentProcess()
    if not psapi.GetProcessMemoryInfo(h, ctypes.byref(pmc), pmc.cb):
        raise RuntimeError("GetProcessMemoryInfo failed: %d" % ctypes.get_last_error())
    return pmc.WorkingSetSize / 1e6, pmc.PeakWorkingSetSize / 1e6


def rss_mb():
    ws, _ = _win_mem()
    return ws


BASE_PRICE = Decimal("3500.00")


def synth_bars(n=120, start_ts=None, seed=SEED):
    rng = random.Random(seed)
    if start_ts is None:
        start_ts = (int(time.time()) // 60) * 60 - n * 60
    bars = []
    p = BASE_PRICE
    for i in range(n):
        o = p
        drift = Decimal(str(rng.uniform(-4.0, 4.0))).quantize(Decimal("0.01"))
        c = (o + drift).quantize(Decimal("0.01"))
        h = max(o, c) + Decimal(str(rng.uniform(0.0, 2.0))).quantize(Decimal("0.01"))
        lo = min(o, c) - Decimal(str(rng.uniform(0.0, 2.0))).quantize(Decimal("0.01"))
        bars.append(CandleBar(
            timestamp=float(start_ts + i * 60), open_=o, high=h, low=lo, close=c,
            volume=Decimal("15.0"), ema_fast=c, ema_slow=c,
            rsi=Decimal("50.00"), atr=Decimal("12.00"),
        ))
        p = c
    return bars


def synth_price(i, rng):
    """Deterministic volatile price: sine (amp $120, period 90 ticks) + noise."""
    sine = 120.0 * math.sin(2.0 * math.pi * i / 90.0)
    noise = rng.uniform(-6.0, 6.0)
    return (BASE_PRICE + Decimal(str(round(sine + noise, 2)))).quantize(Decimal("0.01"))


def make_quote(price, ts):
    return LiveQuote(
        price=price, bid=price - Decimal("0.50"), ask=price + Decimal("0.50"),
        high_24h=price + Decimal("50"), low_24h=price - Decimal("50"),
        volume_24h=Decimal("12000"), change_24h_pct=Decimal("0.5"),
        source="soak-synthetic", timestamp=float(ts), is_offline=False,
    )


def do_slice(eng, price, prev_price, slot):
    """One cadence slice, replicating _live_loop's per-slot body (Phase 0/2 probe)."""
    with eng.lock:
        q = make_quote(price, slot)
        ticks_open = prev_price
        high_p = max(price, prev_price) + Decimal("0.50")
        low_p = min(price, prev_price) - Decimal("0.50")
        eng.latest_quote = q
        eng.published_quote = q
        eng.tick_count += 1
        eng._update_candle(
            float(slot), close=price, high=high_p, low=low_p, open_=ticks_open,
        )
        eng._recompute_candle_indicators()
        eng.published_candles = [dict(c) for c in eng.candles]
        eng.last_cadence_ts = float(slot)
        alpha_f = Decimal("0.15")
        alpha_s = Decimal("0.04")
        if eng.live_ema_fast <= Decimal("0"):
            eng.live_ema_fast = price
            eng.live_ema_slow = price
        else:
            eng.live_ema_fast = ((price * alpha_f) + (eng.live_ema_fast * (Decimal("1") - alpha_f))).quantize(Decimal("0.01"))
            eng.live_ema_slow = ((price * alpha_s) + (eng.live_ema_slow * (Decimal("1") - alpha_s))).quantize(Decimal("0.01"))
        if eng.live_orders_enabled:
            if not eng.live_trading_active:
                eng.live_trading_active = True
                if not eng.live_start_ts:
                    eng.live_start_ts = float(slot)
                eng.last_evolve_ts = float(slot)
                eng._ensure_active_live_positions(price, float(slot))
                eng._harvest_fills()
            fills = eng.broker.on_tick(
                price=price,
                high=max(high_p, price, q.ask),
                low=min(low_p, price, q.bid),
                timestamp=float(slot),
                open_price=prev_price,
            )
            for f in fills:
                if f.is_closing_fill:
                    eng.strategy_cooldown[f.portfolio_id] = float(slot) + 60.0
                    eng.position_entry_ts.pop(f.portfolio_id, None)
                eng.log_event(
                    f.reason.value,
                    f"{f.portfolio_id.upper()} {f.side.value} {f.qty} ETH @ ${f.price:,.2f}",
                    "profit" if f.realized_pnl >= Decimal("0") else "loss",
                )
                if f.is_closing_fill:
                    close_verb = "Covered SHORT" if f.position_side == PositionSide.SHORT else "Closed LONG"
                    eng.macro_commander.record_strategy_action(
                        f.portfolio_id,
                        eng.STRATEGY_SHORT.get(f.portfolio_id, f.portfolio_id),
                        f"{close_verb} {f.qty} ETH @ ${f.price:,.2f}",
                        "profit" if f.realized_pnl >= Decimal("0") else "loss",
                    )
            if not eng.position_entry_ts and all(
                c.portfolio.position_qty == Decimal("0") for c in eng.competitors
            ):
                eng._ensure_active_live_positions(price, float(slot))
            eng._evaluate_live_strategies(price, prev_price, float(slot))
        eng._record_series_point(price, float(slot))
        eng._publish_state_snapshot()


def genome_valid(c):
    """Genome sanity: finite, in-range values; returns list of problems (empty = valid)."""
    g = c.genome
    problems = []
    try:
        if not (Decimal("0") < g.position_ratio < Decimal("1")):
            problems.append(f"position_ratio={g.position_ratio}")
        if not (g.risk_per_trade_pct > 0):
            problems.append(f"risk_per_trade_pct={g.risk_per_trade_pct}")
        if not (g.stop_loss_pct > 0):
            problems.append(f"stop_loss_pct={g.stop_loss_pct}")
        if g.take_profit_pct is not None and not (g.take_profit_pct > 0):
            problems.append(f"take_profit_pct={g.take_profit_pct}")
        if not (g.atr_stop_mult > 0 and g.atr_target_mult > 0):
            problems.append("atr mults<=0")
        if g.cooldown_bars < 0:
            problems.append(f"cooldown_bars={g.cooldown_bars}")
        if g.leverage_enabled and not (g.leverage >= Decimal("1")):
            problems.append(f"leverage={g.leverage}")
    except Exception as e:  # noqa: BLE001 - validity probe must not crash the soak
        problems.append(f"exception:{e}")
    return problems


def structure_sizes(eng):
    return {
        "trade_history_len": {c.portfolio_id: len(c.portfolio.trade_history) for c in eng.competitors},
        "trade_history_total": sum(len(c.portfolio.trade_history) for c in eng.competitors),
        "equity_history_len": {c.portfolio_id: len(c.portfolio.equity_history) for c in eng.competitors},
        "fill_records": len(eng.fill_records),
        "broker_execution_audit": len(eng.broker.execution_audit),
        "broker_rejection_audit": len(eng.broker.rejection_audit),
        "live_logs": len(eng.live_logs),
        "candles": len(eng.candles),
        "candles_5m": len(eng.candles_5m),
        "candles_15m": len(eng.candles_15m),
        "candles_1h": len(eng.candles_1h),
        "evolution_events": len(eng.evolution_events),
        "tick_series": len(eng.eth_price_series),
        "slice_ticks": len(eng._slice_ticks),
        "strategy_cooldown": len(eng.strategy_cooldown),
        "position_entry_ts": len(eng.position_entry_ts),
    }


def closing_fills_since(storage, last_seq):
    """Closing fills (action_label CLOSE LONG / COVER SHORT) in the SQLite
    ledger with fill_seq > last_seq, per portfolio. The in-memory tape is
    capped at 200 records, so the ledger is the reliable count."""
    try:
        conn = sqlite3.connect(storage.db_path)
        rows = conn.execute(
            "SELECT portfolio_id, COUNT(*) FROM execution_ledger "
            "WHERE fill_seq > ? AND action_label IN ('CLOSE LONG', 'COVER SHORT') "
            "GROUP BY portfolio_id", (int(last_seq),)).fetchall()
        max_seq = conn.execute("SELECT MAX(fill_seq) FROM execution_ledger").fetchone()[0]
        conn.close()
        return {r[0]: r[1] for r in rows}, (int(max_seq) if max_seq is not None else int(last_seq))
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}, int(last_seq)


def db_stats(db_path):
    out = {"db_file_mb": round(os.path.getsize(db_path) / 1e6, 3) if os.path.exists(db_path) else None}
    try:
        conn = sqlite3.connect(db_path)
        for tbl in ("candles_1m", "execution_ledger", "evolution_history"):
            try:
                out[f"rows_{tbl}"] = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
            except Exception as e:  # noqa: BLE001 - table may not exist yet
                out[f"rows_{tbl}"] = f"n/a:{e}"
        conn.close()
    except Exception as e:  # noqa: BLE001
        out["error"] = str(e)
    return out


def main():
    global ARGS, TMP_DIR, MEM_DIR, DB_PATH, SEED
    ARGS = _parse_args()
    SEED = ARGS.seed
    # Fresh unique tmp dir per run: a crashed earlier run's leftovers
    # (notably arena_history.json) must never leak into this run's counts.
    # Second-resolution timestamps collide when a run is retried within the
    # same second (the pilot's arena_history.json showed a doubled
    # [2,3,4,2,3,4] generation list from two writers sharing one dir), so
    # the stamp carries microseconds plus the PID.
    TMP_DIR = (ARGS.tmp_dir + "_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
               + f"_pid{os.getpid()}")
    MEM_DIR = os.path.join(TMP_DIR, "memory")
    DB_PATH = os.path.join(TMP_DIR, "arena_history.db")
    os.makedirs(MEM_DIR, exist_ok=True)
    os.environ["ARENA_MEMORY_DIR"] = os.path.abspath(MEM_DIR)
    os.environ["ARENA_FAST_TEST"] = "1"
    result = {
        "soak": "scripts/soak_engine.py (Phase 3)",
        "seed": SEED,
        "ticks_requested": ARGS.ticks,
        "wall_cap_sec": ARGS.wall_cap_sec,
        "sim_seconds_per_tick": 1.0,
        "harness": "synthetic sine+noise prices, mocked feeds, zero network",
        "truncated": False,
        "exceptions": [],
    }
    t_run0 = time.perf_counter()
    result["rss_after_import_mb"] = round(rss_mb(), 2)

    # --- engine construction (temp storage, never touches real data/) ---
    os.makedirs(TMP_DIR, exist_ok=True)
    storage = ArenaStorage(db_path=DB_PATH)
    eng = LiveArenaEngine(storage=storage, initial_cash=Decimal("500000.00"), symbol="ETH/USD")
    result["rss_after_engine_construct_mb"] = round(rss_mb(), 2)

    # --- bootstrap with mocked bars (no network) ---
    bars = synth_bars(120, seed=SEED)
    orig_fetch = ETHFeed.fetch_historical_bars
    ETHFeed.fetch_historical_bars = classmethod(lambda cls, **kw: list(bars))
    try:
        eng.auto_evolve_enabled = True  # real defaults: 6h / 30 trades / 30min debounce
        eng.intel_refresh_interval_sec = 3600.0 * 24
        eng.last_intel_refresh_ts = time.time()
        eng.bootstrap_intraday_session()
    finally:
        ETHFeed.fetch_historical_bars = orig_fetch
    result["bootstrap_candles"] = len(eng.candles)
    result["is_bootstrapped"] = bool(eng.is_bootstrapped)
    result["rss_after_bootstrap_mb"] = round(rss_mb(), 2)

    # --- log-spam counting: wrap log_event (counts every call by tag) ---
    log_counts = Counter()
    log_total = {"n": 0}
    _orig_log_event = eng.log_event

    def _counting_log_event(tag, message, level="info"):
        log_counts[tag] += 1
        log_total["n"] += 1
        return _orig_log_event(tag, message, level)

    eng.log_event = _counting_log_event

    # --- main soak loop ---
    eng.live_orders_enabled = True
    rng = random.Random(SEED + 1)
    price = bars[-1].close
    t0_sim = time.time()  # sim clock starts at real now so evolve_now's
    # time.time() last_evolve_ts stays consistent with the sim clock.
    slot0 = int(t0_sim)
    tracemalloc.start()
    snap_start = tracemalloc.take_snapshot()
    samples = []
    evolutions = []
    last_seq = 0
    fills_before_evolve = len(eng.fill_records)
    sample_every = 1000
    tick_lat_samples = []
    gen_at_start = max(c.genome.generation for c in eng.competitors)

    def _sample(tick_i, note=""):
        cur, peak = tracemalloc.get_traced_memory()
        hist_path = os.path.join(MEM_DIR, "arena_history.json")
        hist_entries = 0
        if os.path.exists(hist_path):
            with open(hist_path, encoding="utf-8") as hf:
                hist_entries = len(json.load(hf))
        samples.append({
            "tick": tick_i, "sim_seconds": tick_i,
            "wall_sec": round(time.perf_counter() - t_run0, 1),
            "rss_mb": round(rss_mb(), 2),
            "tracemalloc_current_mb": round(cur / 1e6, 3),
            "tracemalloc_peak_mb": round(peak / 1e6, 3),
            "structures": structure_sizes(eng),
            "db": db_stats(DB_PATH),
            "db_memory": db_stats(os.path.join(MEM_DIR, "arena_history.db")),
            "arena_history_json_entries": hist_entries,
            "note": note,
        })

    _sample(0, "soak start")
    n_ticks_done = 0
    try:
        for i in range(ARGS.ticks):
            prev = price
            price = synth_price(i, rng)
            slot = slot0 + i
            s0 = time.perf_counter_ns()
            do_slice(eng, price, prev, slot)
            tick_lat_samples.append((time.perf_counter_ns() - s0) / 1e9)
            # Real auto-evolve trigger check, exactly like _live_loop.
            reason = eng._auto_evolve_reason(now=float(slot))
            if reason is not None:
                gen_before = max(c.genome.generation for c in eng.competitors)
                champ_before = eng.tv_champion.get("strategy_id")
                closes_in_window, last_seq = closing_fills_since(storage, last_seq)
                n_fills_window = len(eng.fill_records) - fills_before_evolve
                logs = eng.evolve_now(trigger=f"auto:{reason}")
                # Align last_evolve_ts back to the accelerated sim clock (evolve_now stamps wall time).
                eng.last_evolve_ts = float(slot)
                gen_after = max(c.genome.generation for c in eng.competitors)
                problems = {c.portfolio_id: genome_valid(c) for c in eng.competitors}
                problems = {k: v for k, v in problems.items() if v}
                evolutions.append({
                    "tick": i, "sim_seconds": i, "trigger": reason,
                    "gen_before": gen_before, "gen_after": gen_after,
                    "champion_before": champ_before,
                    "champion_after": eng.tv_champion.get("strategy_id"),
                    "closes_in_window_by_strategy": closes_in_window,
                    "closes_in_window_total": sum(closes_in_window.values()),
                    "fills_in_window": n_fills_window,
                    "genome_problems": problems,
                    "evolve_logs": len(logs),
                })
                fills_before_evolve = len(eng.fill_records)
            # Closing-fill counts per strategy come from the SQLite ledger
            # (closing_fills_since, at each evolution); see evolutions[].
            n_ticks_done = i + 1
            if (i + 1) % sample_every == 0:
                _sample(i + 1)
            if (i + 1) % 200 == 0 and (time.perf_counter() - t_run0) > ARGS.wall_cap_sec:
                result["truncated"] = True
                result["truncated_at_tick"] = i + 1
                break
    except Exception:
        import traceback
        result["exceptions"].append(traceback.format_exc())
        result["crashed_at_tick"] = n_ticks_done
    _sample(n_ticks_done, "soak end")

    # Closing-fill counts per strategy over the whole soak (from the tape tail
    # is lossy because fill_records is capped at 200, so use SQLite ledger).
    try:
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute(
            "SELECT portfolio_id, COUNT(*) FROM execution_ledger WHERE action_label IN "
            "('CLOSE LONG','COVER SHORT') GROUP BY portfolio_id").fetchall()
        result["sqlite_closing_fills_by_strategy"] = {r[0]: r[1] for r in rows}
        result["sqlite_total_fills"] = conn.execute("SELECT COUNT(*) FROM execution_ledger").fetchone()[0]
        conn.close()
    except Exception as e:  # noqa: BLE001
        result["sqlite_closing_fills_error"] = str(e)

    snap_end = tracemalloc.take_snapshot()
    top_diff = snap_end.compare_to(snap_start, "lineno")[:10]
    cur, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    # Clean latency at end-of-soak state (tracemalloc off): the traced mean
    # above is inflated by tracing itself (Phase 0 measured ~2x on calm
    # ticks; the Sharpe loop inflates far more). 300 slices, no evolve check.
    clean_lat = []
    clean_base = n_ticks_done
    for j in range(300):
        prev = price
        price = synth_price(clean_base + 100000 + j, rng)
        slot = slot0 + clean_base + 100000 + j
        s0 = time.perf_counter_ns()
        do_slice(eng, price, prev, slot)
        clean_lat.append((time.perf_counter_ns() - s0) / 1e6)
    result["clean_latency_extra_ticks"] = 300
    clean_lat.sort()
    n_cl = len(clean_lat)
    result["clean_tick_latency_ms_end_state"] = {
        "n": n_cl,
        "mean": round(sum(clean_lat) / n_cl, 3),
        "p50": round(clean_lat[n_cl // 2], 3),
        "p95": round(clean_lat[int(0.95 * n_cl)], 3),
        "max": round(clean_lat[-1], 3),
    }
    tick_lat_samples.sort()
    n_lat = len(tick_lat_samples)

    def _q(p):
        return round(tick_lat_samples[min(n_lat - 1, max(0, int(p * n_lat)))] * 1000.0, 3) if n_lat else None

    result["ticks_done"] = n_ticks_done
    result["sim_hours"] = round(n_ticks_done / 3600.0, 2)
    result["wall_sec"] = round(time.perf_counter() - t_run0, 1)
    result["tick_latency_ms_traced"] = {"n": n_lat, "mean": round(sum(tick_lat_samples) / n_lat * 1000.0, 3) if n_lat else None, "p50": _q(0.50), "p95": _q(0.95), "max": _q(1.0)} if n_lat else {}
    result["tracemalloc_end_current_mb"] = round(cur / 1e6, 3)
    result["tracemalloc_end_peak_mb"] = round(peak / 1e6, 3)
    result["tracemalloc_top_growth"] = [str(s) for s in top_diff]
    result["samples"] = samples
    result["evolutions"] = evolutions
    result["gen_at_start"] = gen_at_start
    result["gen_at_end"] = max(c.genome.generation for c in eng.competitors)
    result["champions_seen"] = sorted({e["champion_after"] for e in evolutions if e.get("champion_after")})
    result["log_event_total"] = log_total["n"]
    result["log_event_by_tag"] = dict(log_counts)
    result["log_event_per_sim_hour"] = round(log_total["n"] / max(n_ticks_done / 3600.0, 1e-9), 1) if n_ticks_done else None
    result["live_logs_len_end"] = len(eng.live_logs)
    result["structures_end"] = structure_sizes(eng)
    result["db_end"] = db_stats(DB_PATH)
    result["fills_total_tape"] = len(eng.fill_records)
    result["tick_count"] = eng.tick_count
    result["open_positions_end"] = sum(1 for c in eng.competitors if c.portfolio.position_qty != Decimal("0"))
    result["strategies_end"] = [
        {"id": c.portfolio_id, "gen": c.genome.generation,
         "equity": float(c.portfolio.total_equity),
         "closed": c.portfolio.closed_trades_count,
         "breaker_tripped": bool(c.portfolio.is_circuit_breaker_tripped),
         "max_dd_pct": float(c.portfolio.max_drawdown_pct),
         "trade_history_len": len(c.portfolio.trade_history)}
        for c in eng.competitors
    ]
    # Natural breaker trips during the main soak (CIRCUIT_BREAKER fills).
    cb_fills = [f for f in eng.fill_records if getattr(f, "reason", None) is not None and f.reason.value == "CIRCUIT_BREAKER"]
    result["natural_circuit_breaker_fills_in_tape_tail"] = len(cb_fills)

    # --- forced time-triggered evolution ----------------------------------
    time_trig = {}
    try:
        sim_now = float(slot0 + n_ticks_done)
        eng.last_evolve_ts = sim_now - (eng.auto_evolve_interval_sec + 1)
        reason = eng._auto_evolve_reason(now=sim_now)
        time_trig["reason_before_forcing"] = reason
        gen_before = max(c.genome.generation for c in eng.competitors)
        if reason == "time":
            eng.evolve_now(trigger="auto:time")
            time_trig["gen_before"] = gen_before
            time_trig["gen_after"] = max(c.genome.generation for c in eng.competitors)
            time_trig["evolved"] = time_trig["gen_after"] == gen_before + 1
        else:
            time_trig["evolved"] = False
    except Exception:
        import traceback
        time_trig["error"] = traceback.format_exc()
    result["time_trigger_test"] = time_trig
    result["gen_after_time_trigger"] = max(c.genome.generation for c in eng.competitors)

    # --- save / restore consistency ---------------------------------------
    save_restore = {}
    try:
        save_restore["save_ok"] = bool(eng.save_session_state())
        storage2 = ArenaStorage(db_path=DB_PATH)
        eng2r = LiveArenaEngine(storage=storage2, initial_cash=Decimal("500000.00"), symbol="ETH/USD")
        save_restore["restore_ok"] = bool(eng2r.restore_session_state())
        if save_restore["restore_ok"]:
            mismatches = []
            for c_old, c_new in zip(eng.competitors, eng2r.competitors):
                g_old, g_new = c_old.genome, c_new.genome
                for field in ("position_ratio", "risk_per_trade_pct", "stop_loss_pct",
                              "take_profit_pct", "generation"):
                    if str(getattr(g_old, field)) != str(getattr(g_new, field)):
                        mismatches.append(f"{c_old.portfolio_id}.{field}: {getattr(g_old, field)} != {getattr(g_new, field)}")
                if str(c_old.portfolio.cash) != str(c_new.portfolio.cash):
                    mismatches.append(f"{c_old.portfolio_id}.cash differs")
                if str(c_old.portfolio.position_qty) != str(c_new.portfolio.position_qty):
                    mismatches.append(f"{c_old.portfolio_id}.position_qty differs")
            save_restore["mismatches"] = mismatches
            save_restore["gen_restored"] = max(c.genome.generation for c in eng2r.competitors)
        try:
            eng2r.stop()
        except Exception:
            pass
    except Exception:
        import traceback
        save_restore["error"] = traceback.format_exc()
    result["save_restore"] = save_restore

    # --- JSON vs SQLite evolution-history agreement -----------------------
    agreement = {}
    try:
        hist_path = os.path.join(MEM_DIR, "arena_history.json")
        if os.path.exists(hist_path):
            with open(hist_path, encoding="utf-8") as hf:
                json_gens = [e.get("generation") for e in json.load(hf)]
        else:
            json_gens = []
        mem_storage = ArenaStorage(db_path=DB_PATH)
        sql_gens = [r["generation"] for r in mem_storage.load_evolution_history(limit=500)]
        try:
            mem_storage.close()
        except Exception:
            pass
        agreement["json_generations"] = json_gens
        agreement["sqlite_generations"] = sorted(sql_gens)
        agreement["agree"] = sorted(json_gens) == sorted(sql_gens)
        agreement["json_entries"] = len(json_gens)
        agreement["sqlite_entries"] = len(sql_gens)
    except Exception:
        import traceback
        agreement["error"] = traceback.format_exc()
    result["history_agreement"] = agreement

    # --- circuit-breaker scenario (fresh engine) --------------------------
    breaker = {}
    eng_b = None
    try:
        storage_b = ArenaStorage(db_path=os.path.join(TMP_DIR, "breaker.db"))
        eng_b = LiveArenaEngine(storage=storage_b, initial_cash=Decimal("500000.00"), symbol="ETH/USD")
        bars_b = synth_bars(120, seed=SEED)
        ETHFeed.fetch_historical_bars = classmethod(lambda cls, **kw: list(bars_b))
        try:
            eng_b.auto_evolve_enabled = True
            eng_b.intel_refresh_interval_sec = 3600.0 * 24
            eng_b.last_intel_refresh_ts = time.time()
            eng_b.bootstrap_intraday_session()
        finally:
            ETHFeed.fetch_historical_bars = orig_fetch
        eng_b.live_orders_enabled = True
        comp = eng_b.comp_a  # Aggressive, position_ratio 0.70 (largest cap)
        p = comp.portfolio
        entry_price = Decimal("3500.00")
        # Naked long, no TP/SL bracket: only the breaker can exit it.
        ticket = OrderTicket(portfolio_id=comp.portfolio_id, symbol="ETH/USD",
                             side=OrderSide.BUY, order_type=OrderType.MARKET,
                             qty=Decimal("90"), price=entry_price,
                             reason=ExecutionReason.SIGNAL_ENTRY,
                             timestamp=time.time())
        fill = eng_b.broker.submit_order(ticket)
        breaker["naked_entry_fill"] = fill is not None
        breaker["entry_qty"] = float(p.position_qty)
        breaker["entry_price"] = float(p.avg_entry_price)
        # Engineered crash: -35% over 25 ticks, wide high/low so the
        # intra-bar drawdown path (update_market_price low) is exercised.
        crash_ticks = 0
        prev = entry_price
        for k in range(1, 26):
            crash_price = (entry_price * (Decimal("1") - Decimal("0.35") * Decimal(k) / Decimal("25"))).quantize(Decimal("0.01"))
            with eng_b.lock:
                eng_b.broker.on_tick(price=crash_price, high=prev, low=crash_price,
                                     timestamp=time.time(), open_price=prev)
                eng_b._harvest_fills()
            prev = crash_price
            crash_ticks += 1
            if p.is_circuit_breaker_tripped:
                break
        breaker["crash_ticks_to_trip"] = crash_ticks
        breaker["tripped"] = bool(p.is_circuit_breaker_tripped)
        breaker["max_dd_pct_at_trip"] = float(p.max_drawdown_pct)
        breaker["position_qty_after_trip"] = float(p.position_qty)
        cb = [f for f in eng_b.fill_records if f.reason.value == "CIRCUIT_BREAKER"]
        breaker["circuit_breaker_fills"] = len(cb)
        # Blocked re-entry while tripped (RiskGuard rejects new opens).
        ticket2 = OrderTicket(portfolio_id=comp.portfolio_id, symbol="ETH/USD",
                              side=OrderSide.BUY, order_type=OrderType.MARKET,
                              qty=Decimal("1"), price=Decimal("2300.00"),
                              reason=ExecutionReason.SIGNAL_ENTRY,
                              timestamp=time.time())
        breaker["reentry_while_tripped_fill"] = eng_b.broker.submit_order(ticket2) is not None
        breaker["reentry_while_tripped_blocked"] = breaker["reentry_while_tripped_fill"] is False
        # Evolve: the generation boundary must reset the breaker (Phase 1/item 4).
        gen_b_before = max(c.genome.generation for c in eng_b.competitors)
        eng_b.evolve_now(trigger="soak:breaker-reset")
        breaker["gen_before_reset"] = gen_b_before
        breaker["gen_after_reset"] = max(c.genome.generation for c in eng_b.competitors)
        breaker["tripped_after_evolve"] = bool(p.is_circuit_breaker_tripped)
        breaker["max_dd_after_evolve"] = float(p.max_drawdown_pct)
        breaker["peak_eq_after_evolve"] = float(p.peak_equity)
        breaker["total_eq_after_evolve"] = float(p.total_equity)
        breaker["peak_reset_to_equity"] = breaker["peak_eq_after_evolve"] == breaker["total_eq_after_evolve"]
        # Trading resumes: a fresh market buy now fills, and normal ticks run.
        ticket3 = OrderTicket(portfolio_id=comp.portfolio_id, symbol="ETH/USD",
                              side=OrderSide.BUY, order_type=OrderType.MARKET,
                              qty=Decimal("1"), price=Decimal("2300.00"),
                              reason=ExecutionReason.SIGNAL_ENTRY,
                              timestamp=time.time())
        breaker["reentry_after_evolve_fill"] = eng_b.broker.submit_order(ticket3) is not None
        fills_after = len(eng_b.fill_records)
        prev2 = Decimal("2300.00")
        rng_resume = random.Random(SEED + 99)
        for k in range(10):
            px = prev2 + Decimal(str(rng_resume.uniform(-5, 5))).quantize(Decimal("0.01"))
            with eng_b.lock:
                eng_b.broker.on_tick(price=px, high=max(px, prev2), low=min(px, prev2),
                                     timestamp=time.time(), open_price=prev2)
                eng_b._harvest_fills()
            prev2 = px
        breaker["ticks_after_resume_ok"] = True
        breaker["fills_after_resume"] = len(eng_b.fill_records) - fills_after
        breaker["position_qty_after_resume"] = float(p.position_qty)
    except Exception:
        import traceback
        breaker["error"] = traceback.format_exc()
    finally:
        if eng_b is not None:
            try:
                eng_b.stop()
            except Exception:
                pass
    result["breaker_scenario"] = breaker

    # --- finalize ---
    try:
        eng.stop()
    except Exception:
        pass
    result["rss_end_mb"] = round(rss_mb(), 2)
    result["peak_rss_mb"] = round(_win_mem()[1], 2)
    out_parent = os.path.dirname(os.path.abspath(ARGS.out))
    if out_parent:
        os.makedirs(out_parent, exist_ok=True)
    with open(ARGS.out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)
    print(json.dumps({k: v for k, v in result.items() if k not in ("samples", "tracemalloc_top_growth")}, indent=2, ensure_ascii=False, default=str))
    print("SAMPLES:", len(samples), "EVOLUTIONS:", len(evolutions))
    print("SOAK_DONE")
    cleaned = False
    for _ in range(10):
        shutil.rmtree(TMP_DIR, ignore_errors=True)
        if not os.path.exists(TMP_DIR):
            cleaned = True
            break
        time.sleep(0.5)
    print("TMP_CLEANED:", cleaned)


if __name__ == "__main__":
    main()
