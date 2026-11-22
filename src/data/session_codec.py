"""
src/data/session_codec.py - Session Snapshot Serialization, Autosave & Restore.
"""
from __future__ import annotations

import copy
from datetime import date
from decimal import Decimal
import logging
import math
import threading
import time
from typing import Any, Dict, Optional

from src.arena.order import ExecutionReason, FillEvent, OrderSide, OrderTicket, OrderType, PositionSide
from src.competitors.base import CompetitorGenome

logger = logging.getLogger(__name__)


def _parse_finite_dec(raw: Any, default: Decimal, *, min_val: Optional[Decimal] = None) -> Decimal:
    try:
        val = Decimal(str(raw))
    except Exception as exc:
        raise ValueError(f"Non-decimal value: {raw!r}") from exc
    if not val.is_finite():
        raise ValueError(f"Non-finite decimal value: {raw!r}")
    if min_val is not None and val < min_val:
        return default
    return val


class SessionCodecMixin:
    """Serializes and restores live engine portfolios, active brackets, fills, and genomes."""

    _persistence_epoch_lock = threading.Lock()

    @staticmethod
    def _serialize_ticket(ticket: Any) -> Optional[Dict[str, Any]]:
        if ticket is None:
            return None
        if isinstance(ticket, (int, float, Decimal, str)):
            return {"price": str(ticket)}
        return {
            "portfolio_id": getattr(ticket, "portfolio_id", ""),
            "symbol": getattr(ticket, "symbol", "ETH/USD"),
            "side": getattr(ticket.side, "value", str(ticket.side)) if hasattr(ticket, "side") else "SELL",
            "order_type": getattr(ticket.order_type, "value", str(ticket.order_type)) if hasattr(ticket, "order_type") else "STOP_MARKET",
            "qty": str(getattr(ticket, "qty", "0")),
            "price": str(getattr(ticket, "price", "0")) if getattr(ticket, "price", None) is not None else None,
            "stop_loss": str(getattr(ticket, "stop_loss", "0")) if getattr(ticket, "stop_loss", None) is not None else None,
            "take_profit": str(getattr(ticket, "take_profit", "0")) if getattr(ticket, "take_profit", None) is not None else None,
            "reason": getattr(ticket.reason, "value", str(ticket.reason)) if hasattr(ticket, "reason") else "SIGNAL",
            "timestamp": float(getattr(ticket, "timestamp", 0.0)),
        }

    @staticmethod
    def _deserialize_ticket(data: Any) -> Optional[Any]:
        if data is None:
            return None
        if isinstance(data, OrderTicket):
            return data
        if isinstance(data, (int, float, Decimal, str)):
            logger.debug("Dropping scalar ticket without quantity: %s", data)
            return None
        if isinstance(data, dict):
            try:
                side = OrderSide(data.get("side", "SELL"))
            except Exception as e:
                logger.debug("Invalid order side in saved ticket, defaulting to SELL: %s", e)
                side = OrderSide.SELL
            try:
                order_type = OrderType(data.get("order_type", "STOP_MARKET"))
            except Exception as e:
                logger.debug("Invalid order type in saved ticket, defaulting to STOP_MARKET: %s", e)
                order_type = OrderType.STOP_MARKET
            try:
                price_val = Decimal(str(data["price"])) if data.get("price") is not None else None
                sl_val = Decimal(str(data["stop_loss"])) if data.get("stop_loss") is not None else None
                tp_val = Decimal(str(data["take_profit"])) if data.get("take_profit") is not None else None
                qty_val = Decimal(str(data.get("qty", "0")))
            except Exception as e:
                logger.debug("Dropping ticket with unparseable numbers: %s (%s)", data, e)
                return None
            if qty_val <= Decimal("0"):
                logger.debug("Dropping deserialized ticket with non-positive qty: %s", data)
                return None
            try:
                reason = ExecutionReason(data.get("reason", "SIGNAL"))
            except Exception as e:
                logger.debug("Invalid reason in saved ticket, defaulting to SIGNAL: %s", e)
                reason = ExecutionReason.SIGNAL
            try:
                ts_val = float(data["timestamp"]) if data.get("timestamp") is not None else None
            except Exception as e:
                logger.debug("Invalid timestamp in saved ticket, defaulting to now: %s", e)
                ts_val = None
            return OrderTicket(
                portfolio_id=str(data.get("portfolio_id", "")),
                symbol=str(data.get("symbol", "ETH/USD")),
                side=side,
                order_type=order_type,
                qty=qty_val,
                price=price_val,
                stop_loss=sl_val,
                take_profit=tp_val,
                reason=reason,
                timestamp=ts_val if ts_val is not None else time.time(),
            )
        return None

    @staticmethod
    def _serialize_fill(f: Any) -> Optional[Dict[str, Any]]:
        if f is None:
            return None
        return {
            "order_id": getattr(f, "order_id", ""),
            "portfolio_id": getattr(f, "portfolio_id", ""),
            "symbol": getattr(f, "symbol", "ETH/USD"),
            "side": getattr(f.side, "value", str(f.side)) if hasattr(f, "side") else "BUY",
            "qty": str(getattr(f, "qty", "0")),
            "price": str(getattr(f, "price", "0")),
            "fee": str(getattr(f, "fee", "0")),
            "timestamp": float(getattr(f, "timestamp", 0.0)),
            "realized_pnl": str(getattr(f, "realized_pnl", "0.00")),
            "reason": getattr(f.reason, "value", str(f.reason)) if hasattr(f, "reason") else "SIGNAL",
            "fill_seq": int(getattr(f, "fill_seq", 0)),
            "entry_price": str(f.entry_price) if getattr(f, "entry_price", None) is not None else None,
            "position_side": getattr(f.position_side, "value", str(f.position_side)) if hasattr(f, "position_side") else "LONG",
        }

    @staticmethod
    def _deserialize_fill(data: Any) -> Optional[Any]:
        if not isinstance(data, dict):
            return None
        try:
            try:
                side = OrderSide(data.get("side", "BUY"))
            except Exception as e:
                logger.debug("Invalid fill side in saved data, defaulting to BUY: %s", e)
                side = OrderSide.BUY
            try:
                pos_side = PositionSide(data.get("position_side", "LONG"))
            except Exception as e:
                logger.debug("Invalid position side in saved data, defaulting to LONG: %s", e)
                pos_side = PositionSide.LONG
            try:
                reason = ExecutionReason(data.get("reason", "SIGNAL"))
            except Exception as e:
                logger.debug("Invalid execution reason in saved data, defaulting to SIGNAL: %s", e)
                reason = ExecutionReason.SIGNAL
            ep_raw = data.get("entry_price")
            ep = Decimal(str(ep_raw)) if ep_raw is not None else None
            return FillEvent(
                order_id=str(data.get("order_id", "")),
                portfolio_id=str(data.get("portfolio_id", "")),
                symbol=str(data.get("symbol", "ETH/USD")),
                side=side,
                qty=Decimal(str(data.get("qty", "0"))),
                price=Decimal(str(data.get("price", "0"))),
                fee=Decimal(str(data.get("fee", "0"))),
                timestamp=float(data.get("timestamp", 0.0)),
                realized_pnl=Decimal(str(data.get("realized_pnl", "0.00"))),
                reason=reason,
                fill_seq=int(data.get("fill_seq", 0)),
                entry_price=ep,
                position_side=pos_side,
            )
        except Exception as e:
            logger.debug("Failed to deserialize fill, dropping: %s", e)
            return None

    def save_session_state(self) -> bool:
        """Saves arena session state to SQLite WAL storage."""
        if self._stop_event.is_set():
            return False
        if not self._is_current_generation():
            logger.warning("Stale engine epoch %.3f: refusing to save session state from a superseded generation", self.engine_epoch)
            return False
        try:
            with self.lock:
                self._harvest_fills()
                gen = max((c.genome.generation for c in self.competitors), default=1)
                comp_states = []
                for c in self.competitors:
                    p = c.portfolio
                    g = c.genome
                    comp_entry: Dict[str, Any] = {
                        "portfolio_id": c.portfolio_id,
                        "name": c.name,
                        "initial_cash": str(p.initial_cash),
                        "cash": str(p.cash),
                        "position_qty": str(p.position_qty),
                        "position_side": p.position_side.value,
                        "avg_entry_price": str(p.avg_entry_price),
                        "open_position_entry_fee": str(p.open_position_entry_fee),
                        "margin_locked": str(p.margin_locked),
                        "current_market_price": str(p.current_market_price),
                        "realized_pnl": str(p.realized_pnl),
                        "total_fees_paid": str(p.total_fees_paid),
                        "gross_profit": str(p.gross_profit),
                        "gross_loss": str(p.gross_loss),
                        "win_count": p.win_count,
                        "loss_count": p.loss_count,
                        "breakeven_count": p.breakeven_count,
                        "peak_equity": str(p.peak_equity),
                        "max_drawdown_pct": str(p.max_drawdown_pct),
                        "is_circuit_breaker_tripped": p.is_circuit_breaker_tripped,
                        "trade_history_total": max(p.total_fills, len(p.trade_history)),
                        "trade_history_truncated": max(p.total_fills, len(p.trade_history)) > 50,
                        "total_fills": p.total_fills,
                        "trade_history": [self._serialize_fill(f) for f in p.trade_history[-50:] if f is not None],
                        "equity_history": [[float(ts), str(eq)] for ts, eq in p.equity_history[-100:]],
                        "genome": {
                            "position_ratio": str(g.position_ratio),
                            "risk_per_trade_pct": str(g.risk_per_trade_pct),
                            "stop_loss_pct": str(g.stop_loss_pct),
                            "take_profit_pct": str(g.take_profit_pct) if g.take_profit_pct is not None else None,
                            "atr_risk_pct": str(g.atr_risk_pct),
                            "atr_stop_mult": str(g.atr_stop_mult),
                            "atr_target_mult": str(g.atr_target_mult),
                            "trailing_trigger_pct": str(g.trailing_trigger_pct),
                            "trailing_distance_pct": str(g.trailing_distance_pct),
                            "cooldown_bars": g.cooldown_bars,
                            "generation": g.generation,
                            "leverage_enabled": g.leverage_enabled,
                            "leverage": str(g.leverage),
                            "news_sensitivity": g.news_sensitivity,
                        },
                    }
                    if hasattr(c, "trailing_active"):
                        comp_entry["trailing_state"] = {
                            "highest_price_since_entry": str(getattr(c, "highest_price_since_entry", Decimal("0"))),
                            "lowest_price_since_entry": str(getattr(c, "lowest_price_since_entry", Decimal("0"))),
                            "trailing_active": bool(getattr(c, "trailing_active", False)),
                        }
                    comp_states.append(comp_entry)

                evicted_live_on_save = 0
                if len(self.fill_records) > 200 and self.live_start_ts:
                    evicted_live_on_save = sum(
                        1
                        for ef in self.fill_records[:-200]
                        if float(getattr(ef, "timestamp", 0.0)) >= self.live_start_ts - 5.0
                    )

                snapshot = {
                    "schema_version": 2,
                    "symbol": self.symbol,
                    "saved_at": time.time(),
                    "generation": gen,
                    "live_start_ts": self.live_start_ts,
                    "live_fill_seq_offset": int(getattr(self, "_live_fill_seq_offset", 0)) + evicted_live_on_save,
                    "closed_trades_since_evolve": int(getattr(self, "_closed_trades_since_evolve", 0)),
                    "last_evolve_ts": float(getattr(self, "last_evolve_ts", 0.0)),
                    "auto_evolve_disabled_ts": getattr(self, "_auto_evolve_disabled_ts", None),
                    "evolution_events": [dict(e) for e in getattr(self, "evolution_events", [])[-24:]],
                    "tv_champion": copy.deepcopy(getattr(self, "tv_champion", {})),
                    "strategy_telemetry": copy.deepcopy(self.strategy_telemetry),
                    "fill_records": [self._serialize_fill(f) for f in self.fill_records[-200:] if f is not None],
                    "broker_execution_audit": [self._serialize_fill(f) for f in self.broker.execution_audit[-200:] if f is not None] if hasattr(self, "broker") else [],
                    "auto_evolve_interval_sec": self.auto_evolve_interval_sec,
                    "auto_evolve_enabled": self.auto_evolve_enabled,
                    "cadence_sec": self.cadence_sec,
                    "live_orders_enabled": self.live_orders_enabled,
                    "active_stops": {pid: self._serialize_ticket(ticket) for pid, ticket in self.broker.active_stops.items() if ticket is not None},
                    "active_targets": {pid: self._serialize_ticket(ticket) for pid, ticket in self.broker.active_targets.items() if ticket is not None},
                    "pending_orders": {
                        oid: self._serialize_ticket(ticket)
                        for oid, ticket in getattr(self.broker, "pending_orders", {}).items()
                        if ticket is not None
                    },
                    "orb_state": {
                        "high": str(getattr(self, "live_orb_high", Decimal("0.00"))),
                        "low": str(getattr(self, "live_orb_low", Decimal("0.00"))),
                        "frozen": bool(getattr(self, "_orb_range_frozen", False)),
                        "day": (
                            self._orb_session_day.isoformat()
                            if getattr(self, "_orb_session_day", None) is not None
                            else None
                        ),
                    },
                    "position_entry_ts": dict(self.position_entry_ts),
                    "competitors": comp_states,
                }
            with SessionCodecMixin._persistence_epoch_lock:
                if self._stop_event.is_set() or not self._is_current_generation():
                    return False
                self.storage.save_session_snapshot(snapshot)
            self.log_event("SESSION_SAVED", f"Saved session state at Generation #{gen} to persistent storage.", "success")
            logger.info("Arena session snapshot saved successfully at Generation #%d", gen)
            return True
        except Exception as e:
            logger.error("Failed to save arena session state: %s", e)
            return False

    def _maybe_autosave(self, now: Optional[float] = None) -> bool:
        if self._stop_event.is_set() or not self._is_current_generation():
            return False
        now = time.time() if now is None else now
        if now < getattr(self, "_autosave_retry_after", 0.0):
            return False
        if not self._autosave_pending and (now - self._last_autosave_ts) < self.autosave_interval_sec:
            return False
        ok = self.save_session_state()
        if ok:
            self._last_autosave_ts = now
            self._autosave_pending = False
            self._autosave_retry_after = 0.0
        else:
            # Back off 10s on failure so _live_loop (10 Hz) cannot enter a tight error storm.
            self._autosave_retry_after = now + 10.0
        return ok

    def restore_session_state(self, snapshot: Optional[Dict[str, Any]] = None) -> bool:
        """Restores arena session state from saved snapshot atomically (staging before mutating)."""
        try:
            if snapshot is None:
                snapshot = self.storage.load_session_snapshot()
            if not snapshot or "competitors" not in snapshot:
                return False

            saved_sym = snapshot.get("symbol")
            if saved_sym is not None and str(saved_sym).strip().upper() != str(self.symbol).strip().upper():
                logger.warning(
                    "Skipping session snapshot for symbol %s (engine running %s)",
                    saved_sym,
                    self.symbol,
                )
                return False

            with self.lock:
                comp_map = {
                    c["portfolio_id"]: c
                    for c in snapshot.get("competitors", [])
                    if isinstance(c, dict) and "portfolio_id" in c
                }

                # Stage and validate all competitor fields before mutating any Portfolio so
                # a corrupt entry cannot leave earlier competitors half-restored.
                staged: list[tuple[Any, Dict[str, Any]]] = []
                genome_warnings: list[str] = []
                for c in self.competitors:
                    if c.portfolio_id not in comp_map:
                        continue
                    cd = comp_map[c.portfolio_id]
                    p = c.portfolio
                    new_genome = None
                    gd = cd.get("genome", {})
                    if isinstance(gd, dict) and gd:
                        try:
                            new_genome = CompetitorGenome(
                                position_ratio=Decimal(str(gd.get("position_ratio", "0.40"))),
                                risk_per_trade_pct=Decimal(str(gd.get("risk_per_trade_pct", "0.015"))),
                                stop_loss_pct=Decimal(str(gd.get("stop_loss_pct", "0.015"))),
                                take_profit_pct=Decimal(str(gd["take_profit_pct"])) if gd.get("take_profit_pct") is not None else None,
                                atr_risk_pct=Decimal(str(gd.get("atr_risk_pct", "0.015"))),
                                atr_stop_mult=Decimal(str(gd.get("atr_stop_mult", "1.5"))),
                                atr_target_mult=Decimal(str(gd.get("atr_target_mult", "2.5"))),
                                trailing_trigger_pct=Decimal(str(gd.get("trailing_trigger_pct", "2.0"))),
                                trailing_distance_pct=Decimal(str(gd.get("trailing_distance_pct", "0.006"))),
                                cooldown_bars=int(gd.get("cooldown_bars", 0)),
                                generation=int(gd.get("generation", 1)),
                                leverage_enabled=bool(gd.get("leverage_enabled", False)),
                                leverage=Decimal(str(gd.get("leverage", "1.0"))),
                                news_sensitivity=float(gd.get("news_sensitivity", getattr(c, "NEWS_SENSITIVITY", 0.5))),
                            )
                        except (ValueError, TypeError, ArithmeticError) as e:
                            genome_warnings.append(f"{c.portfolio_id} stored genome invalid ({e}); keeping default genome")
                            new_genome = None

                    eff_genome = new_genome if new_genome is not None else c.genome
                    init_c = p.initial_cash
                    if "initial_cash" in cd:
                        cand_init = _parse_finite_dec(cd["initial_cash"], p.initial_cash)
                        if cand_init > Decimal("0"):
                            init_c = cand_init
                    cash = _parse_finite_dec(cd.get("cash", p.cash), p.cash)
                    pos_qty = _parse_finite_dec(cd.get("position_qty", "0"), Decimal("0"))
                    try:
                        pos_side = PositionSide(cd.get("position_side", "FLAT"))
                    except Exception as e:
                        logger.debug("Invalid position side in saved snapshot, defaulting to FLAT: %s", e)
                        pos_side = PositionSide.FLAT
                    avg_entry = _parse_finite_dec(cd.get("avg_entry_price", "0"), Decimal("0"), min_val=Decimal("0"))
                    open_fee = _parse_finite_dec(cd.get("open_position_entry_fee", "0.00"), Decimal("0.00"), min_val=Decimal("0"))
                    if pos_qty <= Decimal("0"):
                        pos_qty = Decimal("0.0000")
                        pos_side = PositionSide.FLAT
                        avg_entry = Decimal("0.00")
                        open_fee = Decimal("0.00")
                        margin_locked = Decimal("0.00")
                        pos_leveraged = False
                    else:
                        if pos_side == PositionSide.FLAT:
                            pos_side = PositionSide.LONG
                        if "margin_locked" in cd:
                            margin_locked = _parse_finite_dec(cd["margin_locked"], Decimal("0.00"), min_val=Decimal("0"))
                        elif avg_entry > Decimal("0"):
                            cost = (pos_qty * avg_entry).quantize(Decimal("0.01"))
                            eff_lev = eff_genome.leverage if (eff_genome.leverage_enabled and eff_genome.leverage > Decimal("0")) else Decimal("1.0")
                            margin_locked = (cost / eff_lev).quantize(Decimal("0.01"))
                        else:
                            margin_locked = Decimal("0.00")
                        entry_notional = (pos_qty * avg_entry).quantize(Decimal("0.01"))
                        pos_leveraged = (pos_side == PositionSide.SHORT) or (
                            entry_notional > Decimal("0") and margin_locked < (entry_notional - Decimal("0.05"))
                        )

                    trailing_parsed = None
                    if hasattr(c, "trailing_active"):
                        ts_dict = cd.get("trailing_state")
                        if isinstance(ts_dict, dict) and pos_qty > Decimal("0"):
                            trailing_parsed = (
                                _parse_finite_dec(ts_dict.get("highest_price_since_entry", "0"), Decimal("0"), min_val=Decimal("0")),
                                _parse_finite_dec(ts_dict.get("lowest_price_since_entry", "0"), Decimal("0"), min_val=Decimal("0")),
                                bool(ts_dict.get("trailing_active", False)),
                            )
                        else:
                            trailing_parsed = (Decimal("0"), Decimal("0"), False)

                    curr_mkt = _parse_finite_dec(cd.get("current_market_price", avg_entry), Decimal("0"), min_val=Decimal("0"))
                    realized_pnl = _parse_finite_dec(cd.get("realized_pnl", "0"), Decimal("0"))
                    total_fees = _parse_finite_dec(cd.get("total_fees_paid", "0"), Decimal("0"), min_val=Decimal("0"))
                    gross_profit = _parse_finite_dec(cd.get("gross_profit", "0"), Decimal("0"), min_val=Decimal("0"))
                    gross_loss = _parse_finite_dec(cd.get("gross_loss", "0"), Decimal("0"), min_val=Decimal("0"))
                    win_count = max(0, int(cd.get("win_count", 0)))
                    loss_count = max(0, int(cd.get("loss_count", 0)))
                    breakeven_count = max(0, int(cd.get("breakeven_count", 0)))
                    total_fills = max(0, int(cd.get("total_fills", 0))) if "total_fills" in cd else None
                    peak_eq = _parse_finite_dec(cd.get("peak_equity", cash), cash)
                    max_dd = _parse_finite_dec(cd.get("max_drawdown_pct", "0.00"), Decimal("0.00"), min_val=Decimal("0"))
                    cb_tripped = bool(cd.get("is_circuit_breaker_tripped", False))

                    trade_hist = None
                    if "trade_history" in cd and isinstance(cd["trade_history"], list):
                        trade_hist = [f for f in (self._deserialize_fill(d) for d in cd["trade_history"]) if f is not None]
                    eq_hist = None
                    if "equity_history" in cd and isinstance(cd["equity_history"], list):
                        eq_pts = []
                        for pt in cd["equity_history"]:
                            if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                                try:
                                    pt_t = float(pt[0])
                                    pt_eq = Decimal(str(pt[1]))
                                    if math.isfinite(pt_t) and pt_eq.is_finite():
                                        eq_pts.append((pt_t, pt_eq))
                                except Exception:
                                    continue
                        eq_hist = eq_pts

                    staged.append((c, {
                        "genome": new_genome,
                        "initial_cash": init_c,
                        "cash": cash,
                        "position_qty": pos_qty,
                        "position_side": pos_side,
                        "avg_entry_price": avg_entry,
                        "open_position_entry_fee": open_fee,
                        "margin_locked": margin_locked,
                        "position_is_leveraged": pos_leveraged,
                        "trailing": trailing_parsed,
                        "current_market_price": curr_mkt,
                        "realized_pnl": realized_pnl,
                        "total_fees_paid": total_fees,
                        "gross_profit": gross_profit,
                        "gross_loss": gross_loss,
                        "win_count": win_count,
                        "loss_count": loss_count,
                        "breakeven_count": breakeven_count,
                        "total_fills": total_fills,
                        "peak_equity": peak_eq,
                        "max_drawdown_pct": max_dd,
                        "cb_tripped": cb_tripped,
                        "trade_history": trade_hist,
                        "equity_history": eq_hist,
                    }))

                # Commit staged competitor state atomically now that validation succeeded.
                for warn_msg in genome_warnings:
                    self.log_event("RESTORE_WARN", warn_msg, "loss")

                for c, s in staged:
                    new_genome = s["genome"]
                    if new_genome is not None:
                        c.genome = new_genome
                        c.max_position_ratio = new_genome.position_ratio
                        gen_tag = f" [G{new_genome.generation}]" if new_genome.generation > 1 else ""
                        c.name = f"{c.base_name}{gen_tag}"
                        eff_lev = new_genome.leverage if new_genome.leverage_enabled else Decimal("1.0")
                        c.portfolio.leverage = eff_lev
                        c.portfolio.leverage_enabled = new_genome.leverage_enabled

                    p = c.portfolio
                    p.name = c.name
                    p.initial_cash = s["initial_cash"]
                    p.cash = s["cash"]
                    p.position_qty = s["position_qty"]
                    p.position_side = s["position_side"]
                    p.avg_entry_price = s["avg_entry_price"]
                    p.open_position_entry_fee = s["open_position_entry_fee"]
                    p.margin_locked = s["margin_locked"]
                    p.position_is_leveraged = s["position_is_leveraged"]

                    if s["trailing"] is not None:
                        c.highest_price_since_entry, c.lowest_price_since_entry, c.trailing_active = s["trailing"]

                    p.current_market_price = s["current_market_price"]
                    p.realized_pnl = s["realized_pnl"]
                    p.total_fees_paid = s["total_fees_paid"]
                    p.gross_profit = s["gross_profit"]
                    p.gross_loss = s["gross_loss"]
                    p.win_count = s["win_count"]
                    p.loss_count = s["loss_count"]
                    p.breakeven_count = s["breakeven_count"]
                    p.peak_equity = s["peak_equity"]
                    p.max_drawdown_pct = s["max_drawdown_pct"]
                    p.is_circuit_breaker_tripped = s["cb_tripped"]

                    if s["trade_history"] is not None:
                        p.trade_history = s["trade_history"]
                    if s["total_fills"] is not None:
                        p.total_fills = s["total_fills"]
                    else:
                        p.total_fills = len(p.trade_history)
                    if s["equity_history"] is not None:
                        p.replace_equity_history(s["equity_history"])

                    self.broker.competitor_caps[c.portfolio_id] = c.max_position_ratio

                open_pids = {c.portfolio_id for c in self.competitors if c.portfolio.position_qty > Decimal("0")}
                if "active_stops" in snapshot and isinstance(snapshot["active_stops"], dict):
                    self.broker.active_stops = {}
                    for pid, s_data in snapshot["active_stops"].items():
                        if pid in comp_map and pid not in open_pids:
                            continue
                        t = self._deserialize_ticket(s_data)
                        if t:
                            self.broker.active_stops[pid] = t
                if "active_targets" in snapshot and isinstance(snapshot["active_targets"], dict):
                    self.broker.active_targets = {}
                    for pid, t_data in snapshot["active_targets"].items():
                        if pid in comp_map and pid not in open_pids:
                            continue
                        t = self._deserialize_ticket(t_data)
                        if t:
                            self.broker.active_targets[pid] = t
                if hasattr(self, "broker"):
                    self.broker.pending_orders = {}
                    if "pending_orders" in snapshot and isinstance(snapshot["pending_orders"], dict):
                        for oid, p_data in snapshot["pending_orders"].items():
                            t = self._deserialize_ticket(p_data)
                            if t:
                                self.broker.pending_orders[str(oid)] = t
                if "orb_state" in snapshot and isinstance(snapshot["orb_state"], dict):
                    orb = snapshot["orb_state"]
                    try:
                        oh = _parse_finite_dec(orb.get("high", "0"), Decimal("0.00"), min_val=Decimal("0"))
                        ol = _parse_finite_dec(orb.get("low", "0"), Decimal("0.00"), min_val=Decimal("0"))
                        if oh > Decimal("0") and ol > Decimal("0") and oh >= ol:
                            self.live_orb_high = oh
                            self.live_orb_low = ol
                            self._orb_range_frozen = bool(orb.get("frozen", False))
                            raw_day = orb.get("day")
                            if isinstance(raw_day, str) and raw_day:
                                self._orb_session_day = date.fromisoformat(raw_day)
                                self._orb_session_day_idx = None
                    except Exception as e:
                        logger.debug("Invalid orb_state in saved snapshot, ignoring: %s", e)
                if "position_entry_ts" in snapshot:
                    try:
                        self.position_entry_ts = {
                            pid: float(ts)
                            for pid, ts in snapshot["position_entry_ts"].items()
                            if not (pid in comp_map and pid not in open_pids)
                        }
                    except (TypeError, ValueError, AttributeError) as e:
                        logger.debug("Invalid position_entry_ts in saved snapshot, ignoring: %s", e)
                if "closed_trades_since_evolve" in snapshot:
                    try:
                        self._closed_trades_since_evolve = max(0, int(snapshot["closed_trades_since_evolve"]))
                    except (TypeError, ValueError):
                        pass
                if "last_evolve_ts" in snapshot:
                    try:
                        saved_evolve_ts = float(snapshot["last_evolve_ts"])
                        if saved_evolve_ts > 0.0:
                            self.last_evolve_ts = saved_evolve_ts
                    except (TypeError, ValueError):
                        pass
                if "evolution_events" in snapshot and isinstance(snapshot["evolution_events"], list):
                    self.evolution_events = [dict(e) for e in snapshot["evolution_events"][-24:] if isinstance(e, dict)]
                if "tv_champion" in snapshot and isinstance(snapshot["tv_champion"], dict) and snapshot["tv_champion"]:
                    self.tv_champion = copy.deepcopy(snapshot["tv_champion"])
                if "strategy_telemetry" in snapshot and isinstance(snapshot["strategy_telemetry"], dict):
                    roster = {c.portfolio_id for c in self.competitors}
                    self.strategy_telemetry.update({k: copy.deepcopy(v) for k, v in snapshot["strategy_telemetry"].items() if k in roster})
                if "fill_records" in snapshot and isinstance(snapshot["fill_records"], list):
                    self.fill_records = [f for f in (self._deserialize_fill(d) for d in snapshot["fill_records"]) if f is not None]
                if hasattr(self, "broker"):
                    if "broker_execution_audit" in snapshot and isinstance(snapshot["broker_execution_audit"], list):
                        self.broker.execution_audit = [f for f in (self._deserialize_fill(d) for d in snapshot["broker_execution_audit"]) if f is not None]
                        self._audit_cursor = len(self.broker.execution_audit)
                    max_seq = max(
                        (
                            int(getattr(f, "fill_seq", 0))
                            for f in (
                                list(self.broker.execution_audit)
                                + list(self.fill_records)
                                + [tf for c in self.competitors for tf in c.portfolio.trade_history]
                            )
                        ),
                        default=0,
                    )
                    if max_seq > 0:
                        self.broker.reset_seq(max_seq)
                    for c in self.competitors:
                        if c.portfolio.current_market_price > Decimal("0"):
                            self.broker.current_price = c.portfolio.current_market_price
                            break
                if "live_fill_seq_offset" in snapshot:
                    self._live_fill_seq_offset = int(snapshot.get("live_fill_seq_offset", 0) or 0)
                if "auto_evolve_interval_sec" in snapshot:
                    self.auto_evolve_interval_sec = int(snapshot["auto_evolve_interval_sec"])
                if "auto_evolve_enabled" in snapshot:
                    self.auto_evolve_enabled = bool(snapshot["auto_evolve_enabled"])
                if "auto_evolve_disabled_ts" in snapshot:
                    raw_dis = snapshot.get("auto_evolve_disabled_ts")
                    try:
                        self._auto_evolve_disabled_ts = float(raw_dis) if (raw_dis is not None and not self.auto_evolve_enabled) else None
                    except (TypeError, ValueError):
                        self._auto_evolve_disabled_ts = None
                elif self.auto_evolve_enabled:
                    self._auto_evolve_disabled_ts = None
                if "cadence_sec" in snapshot:
                    self.cadence_sec = max(1.0, min(10.0, float(snapshot["cadence_sec"])))
                if "live_orders_enabled" in snapshot:
                    self.live_orders_enabled = bool(snapshot["live_orders_enabled"])
                    self.live_trading_active = self.live_orders_enabled
                if "live_start_ts" in snapshot:
                    self.live_start_ts = snapshot.get("live_start_ts")

                self._has_restored_session = True
                gen = snapshot.get("generation", 1)
                self.log_event("SESSION_RESTORE", f"Restored previous session state at Generation #{gen}.", "success")
                logger.info("Arena session snapshot successfully restored at Generation #%d", gen)
                return True
        except Exception as e:
            logger.error("Failed to restore arena session state: %s", e)
            return False
