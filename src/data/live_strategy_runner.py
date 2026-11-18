"""
src/data/live_strategy_runner.py - Live Strategy Evaluation, 4-Layer Gate Pipeline & Telemetry.
"""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
import logging
from typing import Any, Dict, Optional

from src.arena.order import ExecutionReason, OrderSide, OrderTicket, OrderType, PositionSide
from src.data.quote_feeds import parse_symbol_pairs

logger = logging.getLogger(__name__)


class LiveStrategyRunnerMixin:
    """Evaluates the 5 live strategies through Chop, MTF, Macro Veto, and Monte Carlo EV gates."""

    def _base_asset(self) -> str:
        return parse_symbol_pairs(getattr(self, "symbol", "ETH/USD"))["base"]

    def _live_indicators(self, price: Decimal) -> Dict[str, Any]:
        """Indicator snapshot handed to evaluate_signal for live entries."""
        mean_ref = self.live_typical_mean
        if mean_ref <= Decimal("0"):
            mean_ref = self.live_ema_slow if self.live_ema_slow > Decimal("0") else price
        orb_high = self.live_orb_high if self.live_orb_high > Decimal("0") else (price * Decimal("1.002"))
        orb_low = self.live_orb_low if self.live_orb_low > Decimal("0") else (price * Decimal("0.998"))
        return {
            "atr": self.live_atr,
            "mean_ref": mean_ref,
            "orb_high": orb_high,
            "orb_low": orb_low,
        }

    def _sizing_multiplier_for(self, competitor: Any) -> Decimal:
        sens = getattr(getattr(competitor, "genome", None), "news_sensitivity", 0.5)
        try:
            sens_f = float(sens)
        except (TypeError, ValueError):
            sens_f = 0.5
        return Decimal(str(self.macro_commander.news_sizing_multiplier(sens_f)))

    def _try_enter_ticket(self, competitor: Any, ticket: OrderTicket, price: Decimal, ts: float, event_label: str) -> bool:
        return self._try_enter_bracket(
            competitor, price, ticket.stop_loss, ticket.take_profit, ts, event_label, side=ticket.side, ticket=ticket
        )

    def _enter_via_strategy(
        self,
        competitor: Any,
        price: Decimal,
        ts: float,
        event_label: str,
        side: OrderSide = OrderSide.BUY,
        signal: str = "BUY",
    ) -> bool:
        pid = competitor.portfolio_id
        if ts < self.strategy_cooldown.get(pid, 0.0):
            return False
        ticket = competitor.evaluate_signal(
            signal=signal,
            market_price=price,
            indicators=self._live_indicators(price),
            broker=self.broker,
            timestamp=ts,
            side=side,
            sizing_multiplier=self._sizing_multiplier_for(competitor),
        )
        if ticket is None:
            return False
        return self._try_enter_ticket(competitor, ticket, price, ts, event_label)

    def _try_enter_bracket(
        self,
        competitor: Any,
        price: Decimal,
        sl: Decimal,
        tp: Optional[Decimal],
        ts: float,
        event_label: str,
        side: OrderSide = OrderSide.BUY,
        risk_budget: Optional[Decimal] = None,
        ticket: Optional[OrderTicket] = None,
    ) -> bool:
        pid = competitor.portfolio_id
        asset = self._base_asset()

        if ticket is not None:
            side = ticket.side
            sl = ticket.stop_loss
            tp = ticket.take_profit

        # Close fast-path: risk-reducing exits bypass entry gates & vetoes.
        if ticket is not None and ticket.reason == ExecutionReason.SIGNAL_EXIT:
            if ticket.qty <= Decimal("0"):
                return False
            fill = self.broker.submit_order(ticket)
            if fill:
                self.strategy_cooldown[pid] = ts + 60.0
                self.position_entry_ts.pop(pid, None)
                self.log_event(
                    event_label,
                    f"{competitor.base_name.split(' ')[0]} closed {fill.qty} {asset} @ ${fill.price:,.2f} (PnL ${fill.realized_pnl:+.2f})",
                    "profit" if fill.realized_pnl >= 0 else "loss",
                )
                return True
            return False

        # Gate 1: 15m Chop Gate (ER < 0.25)
        if self._chop_gate_blocks():
            self.live_chop_gate_blocked += 1
            self.strategy_cooldown[pid] = ts + 20.0
            self.strategy_telemetry[pid]["intent"] = "Chop Gate: 15m ER < 0.25"
            self.log_event("VETO_CHOP", f"{competitor.base_name.split(' ')[0]} {side.value} blocked by chop gate (15m ER < 0.25)", "info")
            return False

        # Gate 2: Multi-Timeframe (1h) Trend Confluence
        if not self.is_entry_permitted_by_mtf(side):
            self.strategy_cooldown[pid] = ts + 20.0
            self.strategy_telemetry[pid]["intent"] = f"MTF Veto: 1h {self.htf_bias}"
            self.log_event("VETO_MTF", f"{competitor.base_name.split(' ')[0]} {side.value} blocked by 1h {self.htf_bias} regime", "loss")
            return False

        # Gate 3: Macro Commander Directional Veto
        allowed, veto_reason = self.macro_commander.check_trade_veto(side, competitor.base_name, is_close=False)
        if not allowed:
            self.strategy_cooldown[pid] = ts + 20.0
            self.strategy_telemetry[pid]["intent"] = f"Macro Veto: {self.macro_commander.current_state.directional_bias}"
            self.log_event("VETO_MACRO", f"{competitor.base_name.split(' ')[0]} {side.value} vetoed: {veto_reason}", "loss")
            self.macro_commander.record_strategy_action(
                pid,
                competitor.base_name.split(" ")[0],
                f"{side.value} Blocked by Macro Veto ({self.macro_commander.current_state.directional_bias})",
                "loss",
                is_macro_action=True,
            )
            return False

        # Macro Trend TP Expansion: scale at least the ticket's actual target distance
        # (never shrinking >2R setups down to 2.0R while stretching <=2R setups to >=2R * mult).
        sizing_mult = self._sizing_multiplier_for(competitor)
        if tp is not None and sizing_mult > Decimal("1.0"):
            risk_dist = abs(price - sl)
            if side == OrderSide.BUY and self.macro_commander.current_state.directional_bias == "LONG_ONLY":
                base_dist = max(max(Decimal("0"), tp - price), risk_dist * Decimal("2.0"))
                tp = (price + base_dist * sizing_mult).quantize(Decimal("0.01"))
            elif side == OrderSide.SELL and self.macro_commander.current_state.directional_bias == "SHORT_ONLY":
                base_dist = max(max(Decimal("0"), price - tp), risk_dist * Decimal("2.0"))
                tp = (price - base_dist * sizing_mult).quantize(Decimal("0.01"))

        # Gate 4: TimeMachine Monte Carlo EV Gate
        mc_odds = self.mc_evaluator.evaluate_bracket(price, sl, tp, atr=self.live_atr, recent_candles=self.candles)
        self.strategy_telemetry[pid]["mc_stats"] = mc_odds.to_dict()
        if not mc_odds.passed:
            self.strategy_cooldown[pid] = ts + 20.0
            if mc_odds.neither_prob is None or mc_odds.green_prob is None or mc_odds.decided_win_rate is None:
                win_txt = "unknown"
            else:
                display_win = mc_odds.green_prob if mc_odds.neither_prob > 0.40 else mc_odds.decided_win_rate
                win_txt = f"{display_win * 100:.0f}%"
            ev_txt = f"{mc_odds.expected_r:+.2f}R" if mc_odds.expected_r is not None else "unknown"
            self.strategy_telemetry[pid]["intent"] = f"EV Gate Blocked: Win {win_txt} (EV {ev_txt})"
            self.log_event("EV_GATE_BLOCK", f"{competitor.base_name.split(' ')[0]} blocked by TimeMachine EV Gate: {mc_odds.verdict}", "info")
            return False

        if ticket is not None:
            if ticket.qty <= Decimal("0"):
                return False
            if tp != ticket.take_profit:
                ticket = replace(ticket, take_profit=tp)
        else:
            qty = competitor.compute_r_multiple_qty(price, sl, self.broker, risk_budget=risk_budget, sizing_multiplier=sizing_mult)
            if qty <= Decimal("0"):
                return False
            ticket = OrderTicket(
                portfolio_id=pid,
                symbol=self.symbol,
                side=side,
                order_type=OrderType.MARKET,
                qty=qty,
                stop_loss=sl,
                take_profit=tp,
                timestamp=ts,
            )

        fill = self.broker.submit_order(ticket)
        if fill:
            self.position_entry_ts[pid] = ts
            tp_str = f" | TP ${tp:,.2f}" if tp else ""
            pos_label = "SHORT" if side == OrderSide.SELL else "LONG"
            event_type = "sell" if side == OrderSide.SELL else "buy"
            self.log_event(
                event_label,
                f"{competitor.base_name.split(' ')[0]} opened {pos_label} {fill.qty} {asset} @ ${fill.price:,.2f} (SL ${sl:,.2f}{tp_str} | EV {mc_odds.expected_r:+.2f}R)",
                event_type,
            )
            self.macro_commander.record_strategy_action(
                pid,
                competitor.base_name.split(" ")[0],
                f"Opened {pos_label} {fill.qty} {asset} @ ${fill.price:,.2f}",
                event_type,
            )
            return True
        self.strategy_cooldown[pid] = ts + 20.0
        return False

    def _update_live_trailing_stop(self, price: Decimal, ts: float) -> None:
        """Ratchets Trailing Guard stop for open LONG or SHORT positions (parity with TrailingGuardCompetitor)."""
        p_trail = self.comp_d.portfolio
        g_trail = self.comp_d.genome
        entry_p = p_trail.avg_entry_price
        if entry_p <= Decimal("0"):
            return
        curr_stop = self.broker.active_stops.get("comp_trail")

        if p_trail.position_side == PositionSide.SHORT:
            if self.comp_d.lowest_price_since_entry == Decimal("0") or price < self.comp_d.lowest_price_since_entry:
                self.comp_d.lowest_price_since_entry = price
            gain_pct = ((entry_p - self.comp_d.lowest_price_since_entry) / entry_p) * Decimal("100")
            if gain_pct >= g_trail.trailing_trigger_pct:
                self.comp_d.trailing_active = True
            if self.comp_d.trailing_active:
                new_sl = (self.comp_d.lowest_price_since_entry * (Decimal("1") + g_trail.trailing_distance_pct)).quantize(Decimal("0.01"))
                if curr_stop and (curr_stop.price is None or new_sl < curr_stop.price):
                    self.broker.active_stops["comp_trail"] = OrderTicket(
                        portfolio_id="comp_trail", symbol=self.symbol, side=OrderSide.BUY,
                        order_type=OrderType.STOP_MARKET, qty=p_trail.position_qty,
                        price=new_sl, reason=ExecutionReason.TRAILING_STOP, timestamp=ts,
                    )
                    self.log_event("TRAIL_RATCHET", f"Trailing Guard lowered stop -> ${new_sl:,.2f} (Trough ${self.comp_d.lowest_price_since_entry:,.2f})", "info")
            elif gain_pct >= Decimal("1.0"):
                be_sl = (entry_p * Decimal("0.9995")).quantize(Decimal("0.01"))
                if curr_stop and (curr_stop.price is None or be_sl < curr_stop.price):
                    self.broker.active_stops["comp_trail"] = OrderTicket(
                        portfolio_id="comp_trail", symbol=self.symbol, side=OrderSide.BUY,
                        order_type=OrderType.STOP_MARKET, qty=p_trail.position_qty,
                        price=be_sl, reason=ExecutionReason.TRAILING_STOP, timestamp=ts,
                    )
        else:
            if price > self.comp_d.highest_price_since_entry:
                self.comp_d.highest_price_since_entry = price
            gain_pct = ((self.comp_d.highest_price_since_entry - entry_p) / entry_p) * Decimal("100")
            if gain_pct >= g_trail.trailing_trigger_pct:
                self.comp_d.trailing_active = True
            if self.comp_d.trailing_active:
                new_sl = (self.comp_d.highest_price_since_entry * (Decimal("1") - g_trail.trailing_distance_pct)).quantize(Decimal("0.01"))
                if curr_stop and (curr_stop.price is None or new_sl > curr_stop.price):
                    self.broker.active_stops["comp_trail"] = OrderTicket(
                        portfolio_id="comp_trail", symbol=self.symbol, side=OrderSide.SELL,
                        order_type=OrderType.STOP_MARKET, qty=p_trail.position_qty,
                        price=new_sl, reason=ExecutionReason.TRAILING_STOP, timestamp=ts,
                    )
                    self.log_event("TRAIL_RATCHET", f"Trailing Guard raised stop -> ${new_sl:,.2f} (Peak ${self.comp_d.highest_price_since_entry:,.2f})", "info")
            elif gain_pct >= Decimal("1.0"):
                be_sl = (entry_p * Decimal("1.0005")).quantize(Decimal("0.01"))
                if curr_stop and (curr_stop.price is None or be_sl > curr_stop.price):
                    self.broker.active_stops["comp_trail"] = OrderTicket(
                        portfolio_id="comp_trail", symbol=self.symbol, side=OrderSide.SELL,
                        order_type=OrderType.STOP_MARKET, qty=p_trail.position_qty,
                        price=be_sl, reason=ExecutionReason.TRAILING_STOP, timestamp=ts,
                    )

    def _evaluate_live_strategies(self, price: Decimal, prev_price: Decimal, ts: float) -> None:
        """Evaluates all 5 live strategies on each cadence tick."""
        vel = price - prev_price
        is_uptrend = self.live_ema_fast >= self.live_ema_slow
        asset = self._base_asset()

        # Channel stagnation timeout guard (>40m dead flat)
        for c in self.competitors:
            pid = c.portfolio_id
            p = c.portfolio
            if p.position_qty > Decimal("0") and p.avg_entry_price > Decimal("0"):
                entry_ts = self.position_entry_ts.get(pid, ts)
                hold_sec = ts - entry_ts
                is_short = p.position_side == PositionSide.SHORT
                gain_pct = ((p.avg_entry_price - price) / p.avg_entry_price * Decimal("100")) if is_short else ((price - p.avg_entry_price) / p.avg_entry_price * Decimal("100"))
                if hold_sec >= 2400.0 and abs(gain_pct) < Decimal("0.10"):
                    exit_side = OrderSide.BUY if is_short else OrderSide.SELL
                    fill = self.broker.submit_order(OrderTicket(
                        portfolio_id=pid, symbol=self.symbol, side=exit_side,
                        order_type=OrderType.MARKET, qty=p.position_qty,
                        reason=ExecutionReason.SIGNAL, timestamp=ts,
                    ))
                    if fill:
                        self.strategy_cooldown[pid] = ts + 60.0
                        self.position_entry_ts.pop(pid, None)
                        self.log_event("STAGNATION_EXIT", f"{c.base_name.split(' ')[0]} closed after 40m stagnation timeout", "info")

        # 1. Aggressive Momentum Breakout
        p_agg = self.comp_a.portfolio
        if p_agg.position_qty == Decimal("0"):
            if (is_uptrend and vel > Decimal("0") and self.live_rsi < Decimal("68")) or (vel > self.live_atr * Decimal("0.25")):
                self._enter_via_strategy(self.comp_a, price, ts, "BREAKOUT_LONG", side=OrderSide.BUY)
            elif ((not is_uptrend) and vel < Decimal("0") and self.live_rsi > Decimal("32")) or (vel < -self.live_atr * Decimal("0.25")):
                self._enter_via_strategy(self.comp_a, price, ts, "BREAKDOWN_SHORT", side=OrderSide.SELL)
            if p_agg.position_qty == Decimal("0") and not self.strategy_telemetry["comp_agg"]["intent"].startswith(("EV Gate", "Macro Veto")):
                self.strategy_telemetry["comp_agg"]["intent"] = f"Scanning breakout / breakdown near ${self.live_ema_fast:,.2f}"
        elif p_agg.avg_entry_price > Decimal("0"):
            entry_p = p_agg.avg_entry_price
            if p_agg.position_side == PositionSide.SHORT:
                gain_usd = entry_p - price
                if self.live_ema_fast > self.live_ema_slow and self.live_rsi > Decimal("52") and gain_usd >= (self.live_atr * Decimal("0.5")):
                    fill = self.broker.submit_order(OrderTicket(portfolio_id="comp_agg", symbol=self.symbol, side=OrderSide.BUY, order_type=OrderType.MARKET, qty=p_agg.position_qty, reason=ExecutionReason.TAKE_PROFIT, timestamp=ts))
                    if fill:
                        self.strategy_cooldown["comp_agg"] = ts + 60.0
                        self.position_entry_ts.pop("comp_agg", None)
                        self.log_event("MOMENTUM_TP", f"Aggressive locked short profit {fill.qty} {asset} @ ${fill.price:,.2f} (+${fill.realized_pnl:+.2f})", "profit")
                elif self.live_rsi < Decimal("26") and vel > Decimal("0"):
                    fill = self.broker.submit_order(OrderTicket(portfolio_id="comp_agg", symbol=self.symbol, side=OrderSide.BUY, order_type=OrderType.MARKET, qty=p_agg.position_qty, timestamp=ts))
                    if fill:
                        self.strategy_cooldown["comp_agg"] = ts + 60.0
                        self.position_entry_ts.pop("comp_agg", None)
                        self.log_event("MOMENTUM_EXIT", f"Aggressive covered short {fill.qty} {asset} @ ${fill.price:,.2f} (PnL ${fill.realized_pnl:+.2f})", "profit" if fill.realized_pnl >= 0 else "loss")
            else:
                gain_usd = price - entry_p
                if self.live_ema_fast < self.live_ema_slow and self.live_rsi < Decimal("48") and gain_usd >= (self.live_atr * Decimal("0.5")):
                    fill = self.broker.submit_order(OrderTicket(portfolio_id="comp_agg", symbol=self.symbol, side=OrderSide.SELL, order_type=OrderType.MARKET, qty=p_agg.position_qty, reason=ExecutionReason.TAKE_PROFIT, timestamp=ts))
                    if fill:
                        self.strategy_cooldown["comp_agg"] = ts + 60.0
                        self.position_entry_ts.pop("comp_agg", None)
                        self.log_event("MOMENTUM_TP", f"Aggressive locked long profit {fill.qty} {asset} @ ${fill.price:,.2f} (+${fill.realized_pnl:+.2f})", "profit")
                elif self.live_rsi > Decimal("74") and vel < Decimal("0"):
                    fill = self.broker.submit_order(OrderTicket(portfolio_id="comp_agg", symbol=self.symbol, side=OrderSide.SELL, order_type=OrderType.MARKET, qty=p_agg.position_qty, timestamp=ts))
                    if fill:
                        self.strategy_cooldown["comp_agg"] = ts + 60.0
                        self.position_entry_ts.pop("comp_agg", None)
                        self.log_event("MOMENTUM_EXIT", f"Aggressive closed long {fill.qty} {asset} @ ${fill.price:,.2f} (PnL ${fill.realized_pnl:+.2f})", "profit" if fill.realized_pnl >= 0 else "loss")

        # 2. Conservative Mean-Reversion Scalper
        p_cons = self.comp_b.portfolio
        if p_cons.position_qty == Decimal("0"):
            if self.live_rsi <= Decimal("52.0") and vel >= Decimal("0"):
                self._enter_via_strategy(self.comp_b, price, ts, "SCALP_LONG", side=OrderSide.BUY)
            elif self.live_rsi >= Decimal("58.0") and vel <= Decimal("0"):
                self._enter_via_strategy(self.comp_b, price, ts, "SCALP_SHORT", side=OrderSide.SELL)
        elif p_cons.avg_entry_price > Decimal("0"):
            entry_p = p_cons.avg_entry_price
            if p_cons.position_side == PositionSide.SHORT:
                if price <= self.live_ema_fast and (entry_p - price) >= (self.live_atr * Decimal("0.5")):
                    fill = self.broker.submit_order(OrderTicket(portfolio_id="comp_cons", symbol=self.symbol, side=OrderSide.BUY, order_type=OrderType.MARKET, qty=p_cons.position_qty, reason=ExecutionReason.TAKE_PROFIT, timestamp=ts))
                    if fill:
                        self.strategy_cooldown["comp_cons"] = ts + 60.0
                        self.position_entry_ts.pop("comp_cons", None)
                        self.log_event("SCALP_TP", f"Conservative locked short profit {fill.qty} {asset} @ ${fill.price:,.2f} (+${fill.realized_pnl:+.2f})", "profit")
            else:
                if price >= self.live_ema_fast and (price - entry_p) >= (self.live_atr * Decimal("0.5")):
                    fill = self.broker.submit_order(OrderTicket(portfolio_id="comp_cons", symbol=self.symbol, side=OrderSide.SELL, order_type=OrderType.MARKET, qty=p_cons.position_qty, reason=ExecutionReason.TAKE_PROFIT, timestamp=ts))
                    if fill:
                        self.strategy_cooldown["comp_cons"] = ts + 60.0
                        self.position_entry_ts.pop("comp_cons", None)
                        self.log_event("SCALP_TP", f"Conservative locked long profit {fill.qty} {asset} @ ${fill.price:,.2f} (+${fill.realized_pnl:+.2f})", "profit")

        # 3. Trailing Profit Ratchet Guard
        if self.comp_d.portfolio.position_qty > Decimal("0"):
            self._update_live_trailing_stop(price, ts)
        else:
            if vel >= Decimal("0") and self.live_rsi < Decimal("66") and (is_uptrend or self.live_rsi <= Decimal("50")):
                self._enter_via_strategy(self.comp_d, price, ts, "TRAIL_LONG", side=OrderSide.BUY)
            elif vel <= Decimal("0") and self.live_rsi > Decimal("34") and ((not is_uptrend) or self.live_rsi >= Decimal("50")):
                self._enter_via_strategy(self.comp_d, price, ts, "TRAIL_SHORT", side=OrderSide.SELL)

        # 4. Opening Range Breakout
        p_orb = self.comp_e.portfolio
        orb_high = self.live_orb_high if self.live_orb_high > Decimal("0") else (price * Decimal("1.002"))
        orb_low = self.live_orb_low if self.live_orb_low > Decimal("0") else (price * Decimal("0.998"))
        orb_mid = ((orb_high + orb_low) / Decimal("2")).quantize(Decimal("0.01"))
        if p_orb.position_qty == Decimal("0"):
            is_breakout = (price >= orb_high and vel >= Decimal("0")) or (price > orb_mid and is_uptrend and vel > self.live_atr * Decimal("0.2"))
            is_breakdown = (price <= orb_low and vel <= Decimal("0")) or (price < orb_mid and (not is_uptrend) and vel < -self.live_atr * Decimal("0.2"))
            if is_breakout and self.live_rsi < Decimal("72"):
                self._enter_via_strategy(self.comp_e, price, ts, "ORB_LONG", side=OrderSide.BUY)
            elif is_breakdown and self.live_rsi > Decimal("28"):
                self._enter_via_strategy(self.comp_e, price, ts, "ORB_SHORT", side=OrderSide.SELL)
            if p_orb.position_qty == Decimal("0") and not self.strategy_telemetry["comp_orb"]["intent"].startswith(("EV Gate", "Macro Veto")):
                self.strategy_telemetry["comp_orb"]["intent"] = f"Watching ORB High ${orb_high:,.2f} / Low ${orb_low:,.2f} (Mid ${orb_mid:,.2f})"
        elif p_orb.avg_entry_price > Decimal("0"):
            entry_p = p_orb.avg_entry_price
            if p_orb.position_side == PositionSide.SHORT:
                if price > orb_mid and (entry_p - price) >= (self.live_atr * Decimal("0.5")):
                    fill = self.broker.submit_order(OrderTicket(portfolio_id="comp_orb", symbol=self.symbol, side=OrderSide.BUY, order_type=OrderType.MARKET, qty=p_orb.position_qty, reason=ExecutionReason.TAKE_PROFIT, timestamp=ts))
                    if fill:
                        self.strategy_cooldown["comp_orb"] = ts + 60.0
                        self.position_entry_ts.pop("comp_orb", None)
                        self.log_event("ORB_TP", f"ORB locked short target {fill.qty} {asset} @ ${fill.price:,.2f} (+${fill.realized_pnl:+.2f})", "profit")
            else:
                if price < orb_mid and (price - entry_p) >= (self.live_atr * Decimal("0.5")):
                    fill = self.broker.submit_order(OrderTicket(portfolio_id="comp_orb", symbol=self.symbol, side=OrderSide.SELL, order_type=OrderType.MARKET, qty=p_orb.position_qty, reason=ExecutionReason.TAKE_PROFIT, timestamp=ts))
                    if fill:
                        self.strategy_cooldown["comp_orb"] = ts + 60.0
                        self.position_entry_ts.pop("comp_orb", None)
                        self.log_event("ORB_TP", f"ORB locked long target {fill.qty} {asset} @ ${fill.price:,.2f} (+${fill.realized_pnl:+.2f})", "profit")

        # 5. Session Mean Pullback
        p_vwap = self.comp_f.portfolio
        mean_ref = self.live_typical_mean if self.live_typical_mean > Decimal("0") else (self.live_ema_slow if self.live_ema_slow > Decimal("0") else price)
        if p_vwap.position_qty == Decimal("0"):
            near_mean = abs(price - mean_ref) <= (self.live_atr * Decimal("0.85"))
            is_rebound = vel >= Decimal("0") and self.live_rsi >= Decimal("42") and price >= (mean_ref - self.live_atr * Decimal("0.5"))
            is_rejection = vel <= Decimal("0") and self.live_rsi <= Decimal("58") and price <= (mean_ref + self.live_atr * Decimal("0.5"))
            if near_mean and is_rebound:
                self._enter_via_strategy(self.comp_f, price, ts, "MEAN_LONG", side=OrderSide.BUY)
            elif near_mean and is_rejection:
                self._enter_via_strategy(self.comp_f, price, ts, "MEAN_SHORT", side=OrderSide.SELL)
            if p_vwap.position_qty == Decimal("0") and not self.strategy_telemetry["comp_vwap"]["intent"].startswith(("EV Gate", "Macro Veto")):
                self.strategy_telemetry["comp_vwap"]["intent"] = f"Awaiting session-mean bounce / rejection near ${mean_ref:,.2f}"
        elif p_vwap.avg_entry_price > Decimal("0"):
            entry_p = p_vwap.avg_entry_price
            if p_vwap.position_side == PositionSide.SHORT:
                if price <= (mean_ref - self.live_atr * Decimal("1.5")) and (entry_p - price) >= (self.live_atr * Decimal("0.6")):
                    fill = self.broker.submit_order(OrderTicket(portfolio_id="comp_vwap", symbol=self.symbol, side=OrderSide.BUY, order_type=OrderType.MARKET, qty=p_vwap.position_qty, reason=ExecutionReason.TAKE_PROFIT, timestamp=ts))
                    if fill:
                        self.strategy_cooldown["comp_vwap"] = ts + 60.0
                        self.position_entry_ts.pop("comp_vwap", None)
                        self.log_event("MEAN_TP", f"Session Mean locked short profit {fill.qty} {asset} @ ${fill.price:,.2f} (+${fill.realized_pnl:+.2f})", "profit")
            else:
                if price >= (mean_ref + self.live_atr * Decimal("1.5")) and (price - entry_p) >= (self.live_atr * Decimal("0.6")):
                    fill = self.broker.submit_order(OrderTicket(portfolio_id="comp_vwap", symbol=self.symbol, side=OrderSide.SELL, order_type=OrderType.MARKET, qty=p_vwap.position_qty, reason=ExecutionReason.TAKE_PROFIT, timestamp=ts))
                    if fill:
                        self.strategy_cooldown["comp_vwap"] = ts + 60.0
                        self.position_entry_ts.pop("comp_vwap", None)
                        self.log_event("MEAN_TP", f"Session Mean locked long profit {fill.qty} {asset} @ ${fill.price:,.2f} (+${fill.realized_pnl:+.2f})", "profit")

        self._update_telemetry_snapshot(price)

    def _maybe_auto_redeploy(self, price: Decimal, ts: float) -> bool:
        if not self.auto_redeploy_when_flat:
            self._auto_redeploy_logged = False
            return False
        if self.position_entry_ts or not all(c.portfolio.position_qty == Decimal("0") for c in self.competitors):
            self._auto_redeploy_logged = False
            return False
        if not self._auto_redeploy_logged:
            logger.info("Auto-redeploy: all five strategies flat -- re-entering via _ensure_active_live_positions (auto_redeploy_when_flat=True)")
            self._auto_redeploy_logged = True
        self._ensure_active_live_positions(price, ts)
        return True

    def _ensure_active_live_positions(self, price: Decimal, ts: float) -> None:
        if price <= Decimal("0"):
            return
        is_uptrend = self.live_ema_fast >= self.live_ema_slow if self.live_ema_slow > Decimal("0") else True
        orb_high = self.live_orb_high if self.live_orb_high > Decimal("0") else (price * Decimal("1.002"))
        orb_low = self.live_orb_low if self.live_orb_low > Decimal("0") else (price * Decimal("0.998"))
        orb_mid = ((orb_high + orb_low) / Decimal("2")).quantize(Decimal("0.01"))
        mean_ref = self.live_typical_mean if self.live_typical_mean > Decimal("0") else (self.live_ema_slow if self.live_ema_slow > Decimal("0") else price)

        if self.comp_a.portfolio.position_qty == Decimal("0") and ts >= self.strategy_cooldown.get("comp_agg", 0.0):
            if is_uptrend:
                self._enter_via_strategy(self.comp_a, price, ts, "BREAKOUT_LONG", side=OrderSide.BUY)
            else:
                self._enter_via_strategy(self.comp_a, price, ts, "BREAKDOWN_SHORT", side=OrderSide.SELL)

        if self.comp_b.portfolio.position_qty == Decimal("0") and ts >= self.strategy_cooldown.get("comp_cons", 0.0):
            if self.live_rsi > Decimal("52.0"):
                self._enter_via_strategy(self.comp_b, price, ts, "SCALP_SHORT", side=OrderSide.SELL)
            else:
                self._enter_via_strategy(self.comp_b, price, ts, "SCALP_LONG", side=OrderSide.BUY)

        if self.comp_d.portfolio.position_qty == Decimal("0") and ts >= self.strategy_cooldown.get("comp_trail", 0.0):
            if is_uptrend:
                self._enter_via_strategy(self.comp_d, price, ts, "TRAIL_LONG", side=OrderSide.BUY)
            else:
                self._enter_via_strategy(self.comp_d, price, ts, "TRAIL_SHORT", side=OrderSide.SELL)

        if self.comp_e.portfolio.position_qty == Decimal("0") and ts >= self.strategy_cooldown.get("comp_orb", 0.0):
            if price >= orb_mid:
                self._enter_via_strategy(self.comp_e, price, ts, "ORB_LONG", side=OrderSide.BUY)
            else:
                self._enter_via_strategy(self.comp_e, price, ts, "ORB_SHORT", side=OrderSide.SELL)

        if self.comp_f.portfolio.position_qty == Decimal("0") and ts >= self.strategy_cooldown.get("comp_vwap", 0.0):
            if price >= mean_ref:
                self._enter_via_strategy(self.comp_f, price, ts, "MEAN_LONG", side=OrderSide.BUY)
            else:
                self._enter_via_strategy(self.comp_f, price, ts, "MEAN_SHORT", side=OrderSide.SELL)

        self._update_telemetry_snapshot(price)

    def _update_telemetry_snapshot(self, price: Decimal) -> None:
        asset = self._base_asset()
        for c in self.competitors:
            pid = c.portfolio_id
            p = c.portfolio
            stop_ord = self.broker.active_stops.get(pid)
            tp_ord = self.broker.active_targets.get(pid)
            sl_p = float(stop_ord.price) if (stop_ord and stop_ord.price) else None
            tp_p = float(tp_ord.price) if (tp_ord and tp_ord.price) else None

            prev_tel = self.strategy_telemetry.get(pid, {})
            mc_st = prev_tel.get("mc_stats", {})

            if p.position_qty > Decimal("0"):
                is_short = p.position_side == PositionSide.SHORT
                pos_dir = "SHORT" if is_short else "LONG"
                if is_short:
                    upnl_pct = ((p.avg_entry_price - price) / p.avg_entry_price * Decimal("100")) if p.avg_entry_price > 0 else Decimal("0")
                else:
                    upnl_pct = ((price - p.avg_entry_price) / p.avg_entry_price * Decimal("100")) if p.avg_entry_price > 0 else Decimal("0")

                if pid == "comp_agg":
                    intent = f"{pos_dir} {p.position_qty} {asset} @ ${p.avg_entry_price:,.2f} | Uncapped Trend Run ({upnl_pct:+.2f}%)"
                elif pid == "comp_cons":
                    intent = f"SCALP {pos_dir} {p.position_qty} {asset} @ ${p.avg_entry_price:,.2f} | Target ${tp_p:,.2f}" if tp_p else f"{pos_dir} {p.position_qty} {asset}"
                elif pid == "comp_orb":
                    intent = f"ORB {pos_dir} {p.position_qty} {asset} @ ${p.avg_entry_price:,.2f} | 2.0R Target ${tp_p:,.2f}" if tp_p else f"{pos_dir} {p.position_qty} {asset}"
                elif pid == "comp_vwap":
                    intent = f"MEAN {pos_dir} {p.position_qty} {asset} @ ${p.avg_entry_price:,.2f} | 2.2R Target ${tp_p:,.2f}" if tp_p else f"{pos_dir} {p.position_qty} {asset}"
                else:
                    ref_p = self.comp_d.lowest_price_since_entry if is_short else self.comp_d.highest_price_since_entry
                    ref_tag = "Trough" if is_short else "Peak"
                    intent = f"TRAILING {pos_dir} {p.position_qty} {asset} | {ref_tag} ${ref_p:,.2f} | Ratchet SL ${sl_p:,.2f}" if sl_p else f"{pos_dir} {p.position_qty} {asset}"
            else:
                intent = prev_tel.get("intent") or f"SCANNING LIVE BOOK (Cash: ${p.cash:,.2f})"

            self.strategy_telemetry[pid] = {
                "strategy_type": self._get_strategy_label(pid),
                "intent": intent,
                "entry_rule": self._get_entry_rule_desc(pid),
                "stop_price": sl_p,
                "target_price": tp_p,
                "entry_price": float(p.avg_entry_price) if p.position_qty > 0 else None,
                "mc_stats": mc_st,
            }
