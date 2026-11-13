"""TradeBot0 maintenance item 2 patch: backtest / live unification.

Main line: live entries route through each strategy's evaluate_signal
(with a new `side` parameter for short entries); ORB window excludes the
current bar; the live "VWAP" is renamed to session typical-price mean
(it was an unweighted mean of typical prices, not volume-weighted VWAP).

Safety: Phase 1 verifies EVERY replacement occurs exactly the expected
number of times (and the rename source exists / target does not) BEFORE
any file is written. Any mismatch aborts with no writes.
Line endings: each target file keeps its own newline style (CRLF or LF).

Usage:
  python fix_item2_patch.py [project_root]     # default C:\\Users\\will0\\TradeBot0
"""
import os
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"C:\Users\will0\TradeBot0")

OPS = []          # (rel path, old, new, expected_count)
RENAME_SRC = "src/competitors/vwap.py"
RENAME_DST = "src/competitors/session_mean.py"
RENAME_OPS = []   # (old, new, expected_count) applied to vwap.py content
APPENDS = []      # (rel path, text) appended at end of file


def _read(path):
    raw = Path(path).read_bytes()
    nl = "\r\n" if b"\r\n" in raw else "\n"
    return raw.decode("utf-8"), nl


def _norm(text, nl):
    return text.replace("\n", nl) if nl == "\r\n" else text


def op(rel, old, new, expected=1):
    OPS.append((rel, old, new, expected))


def rop(old, new, expected=1):
    RENAME_OPS.append((old, new, expected))


# ---------------------------------------------------------------- base.py
op("src/competitors/base.py",
   "from src.arena.order import OrderTicket",
   "from src.arena.order import OrderTicket, OrderSide, OrderType, PositionSide, ExecutionReason")

op("src/competitors/base.py",
   '''    @abstractmethod
    def evaluate_signal(
        self,
        signal: str,  # "BUY", "SELL", or "HOLD"
        market_price: Decimal,
        indicators: Dict[str, Any],
        broker: BrokerSim,
        timestamp: float
    ) -> Optional[OrderTicket]:
        """
        Translates a raw strategy signal into a sized, risk-managed OrderTicket.
        """
        pass''',
   '''    @abstractmethod
    def evaluate_signal(
        self,
        signal: str,  # "BUY", "SELL", or "HOLD"
        market_price: Decimal,
        indicators: Dict[str, Any],
        broker: BrokerSim,
        timestamp: float,
        side: OrderSide = OrderSide.BUY,
    ) -> Optional[OrderTicket]:
        """
        Translates a raw strategy signal into a sized, risk-managed OrderTicket.

        Single entry/exit contract shared by backtest (TimeMachine) and live
        (LiveArenaEngine): the strategy owns bracket math (SL / TP / sizing)
        from its genome; the caller owns signal generation and live-only gates
        (MTF, macro veto, MC EV gate, cooldown).
        - signal "BUY": entry intent in the direction of `side`
          (BUY = open long, SELL = open short).
        - signal "SELL": close the existing position, if any (opposite side
          of the current position; BUY to cover a short, SELL to exit a long).
        - signal "HOLD": no new ticket (trailing management still runs where
          implemented).
        """
        pass''')

op("src/competitors/base.py",
   "    def compute_safe_buy_qty(",
   '''    def _close_ticket(self, broker: BrokerSim, timestamp: float) -> Optional[OrderTicket]:
        """Market ticket closing the full open position, if any.

        Side is the opposite of the current position (BUY covers a short,
        SELL exits a long), so a SELL signal closes either direction.
        """
        if self.portfolio.position_qty <= Decimal("0"):
            return None
        close_side = OrderSide.BUY if self.portfolio.position_side == PositionSide.SHORT else OrderSide.SELL
        return OrderTicket(
            portfolio_id=self.portfolio_id,
            symbol=broker.symbol,
            side=close_side,
            order_type=OrderType.MARKET,
            qty=self.portfolio.position_qty,
            reason=ExecutionReason.SIGNAL_EXIT,
            timestamp=timestamp
        )

    def compute_safe_buy_qty(''')

# ------------------------------------------------- strategy signatures
# The 9-line evaluate_signal signature block is identical in all six
# strategy files; each op targets one file, so count == 1 per file.
SIG_OLD = '''    def evaluate_signal(
        self,
        signal: str,
        market_price: Decimal,
        indicators: Dict[str, Any],
        broker: BrokerSim,
        timestamp: float
    ) -> Optional[OrderTicket]:'''
SIG_NEW = '''    def evaluate_signal(
        self,
        signal: str,
        market_price: Decimal,
        indicators: Dict[str, Any],
        broker: BrokerSim,
        timestamp: float,
        side: OrderSide = OrderSide.BUY,
    ) -> Optional[OrderTicket]:'''
for _f in ("aggressive", "conservative", "atr_dynamic", "trailing_guard", "orb"):
    op(f"src/competitors/{_f}.py", SIG_OLD, SIG_NEW)

# The long-entry condition line is identical in all six strategy files.
BUYCOND_OLD = '        if signal == "BUY" and self.portfolio.position_qty == Decimal("0"):'
BUYCOND_NEW = '        if signal == "BUY" and side == OrderSide.BUY and self.portfolio.position_qty == Decimal("0"):'
for _f in ("aggressive", "conservative", "atr_dynamic", "orb"):
    op(f"src/competitors/{_f}.py", BUYCOND_OLD, BUYCOND_NEW)
# NOTE: trailing_guard is excluded here: its opening block is replaced as a
# whole below (condition change + short branch in one op).

# The SELL (close-long) block is identical in 5 strategy files
# (trailing_guard has its own, handled separately below).
SELL_OLD = '''        elif signal == "SELL" and self.portfolio.position_qty > Decimal("0"):
            return OrderTicket(
                portfolio_id=self.portfolio_id,
                symbol=broker.symbol,
                side=OrderSide.SELL,
                order_type=OrderType.MARKET,
                qty=self.portfolio.position_qty,
                reason=ExecutionReason.SIGNAL_EXIT,
                timestamp=timestamp
            )

        return None'''


def _short_branch_and_close(mirror_body):
    return ('''        elif signal == "BUY" and side == OrderSide.SELL and self.portfolio.position_qty == Decimal("0"):
''' + mirror_body + '''
        elif signal == "SELL":
            return self._close_ticket(broker, timestamp)

        return None''')


# ------------------------------------------------- aggressive (short mirror)
op("src/competitors/aggressive.py", SELL_OLD, _short_branch_and_close(
   '''            stop_price = (market_price * (Decimal("1") + self.genome.stop_loss_pct)).quantize(Decimal("0.01"))
            target_price = (
                (market_price * (Decimal("1") - self.genome.take_profit_pct)).quantize(Decimal("0.01"))
                if self.genome.take_profit_pct is not None
                else None
            )
            qty = self.compute_r_multiple_qty(market_price, stop_price, broker)
            if qty <= Decimal("0"):
                return None

            return OrderTicket(
                portfolio_id=self.portfolio_id,
                symbol=broker.symbol,
                side=OrderSide.SELL,
                order_type=OrderType.MARKET,
                qty=qty,
                stop_loss=stop_price,
                take_profit=target_price,
                reason=ExecutionReason.SIGNAL_ENTRY,
                timestamp=timestamp
            )'''))

# ----------------------------------------------- conservative (short mirror)
op("src/competitors/conservative.py", SELL_OLD, _short_branch_and_close(
   '''            stop_price = (market_price * (Decimal("1") + self.genome.stop_loss_pct)).quantize(Decimal("0.01"))
            tp_pct = self.genome.take_profit_pct if self.genome.take_profit_pct is not None else Decimal("0.018")
            target_price = (market_price * (Decimal("1") - tp_pct)).quantize(Decimal("0.01"))

            qty = self.compute_r_multiple_qty(market_price, stop_price, broker)
            if qty <= Decimal("0"):
                return None

            return OrderTicket(
                portfolio_id=self.portfolio_id,
                symbol=broker.symbol,
                side=OrderSide.SELL,
                order_type=OrderType.MARKET,
                qty=qty,
                stop_loss=stop_price,
                take_profit=target_price,
                reason=ExecutionReason.SIGNAL_ENTRY,
                timestamp=timestamp
            )'''))

# ------------------------------------------------- atr_dynamic (short mirror)
op("src/competitors/atr_dynamic.py", SELL_OLD, _short_branch_and_close(
   '''            atr_val = indicators.get("atr", market_price * Decimal("0.015"))
            if atr_val is None:
                atr_val = market_price * Decimal("0.015")
            elif not isinstance(atr_val, Decimal):
                atr_val = Decimal(str(atr_val))
            if atr_val <= Decimal("0"):
                atr_val = market_price * Decimal("0.015")

            stop_dist = (atr_val * self.genome.atr_stop_mult).quantize(Decimal("0.01"))
            target_dist = (atr_val * self.genome.atr_target_mult).quantize(Decimal("0.01"))

            stop_price = (market_price + stop_dist).quantize(Decimal("0.01"))
            target_price = (market_price - target_dist).quantize(Decimal("0.01"))

            # Risk budget is struck on unleveraged equity; leverage never inflates it.
            risk_budget = self.portfolio.total_equity * self.genome.atr_risk_pct
            qty = self.compute_r_multiple_qty(market_price, stop_price, broker, risk_budget=risk_budget)
            if qty <= Decimal("0"):
                return None

            return OrderTicket(
                portfolio_id=self.portfolio_id,
                symbol=broker.symbol,
                side=OrderSide.SELL,
                order_type=OrderType.MARKET,
                qty=qty,
                stop_loss=stop_price,
                take_profit=target_price,
                reason=ExecutionReason.SIGNAL_ENTRY,
                timestamp=timestamp
            )'''))

# ------------------------------------------------------------- orb (short mirror)
op("src/competitors/orb.py", SELL_OLD, _short_branch_and_close(
   '''            orb_high = indicators.get("orb_high")
            orb_low = indicators.get("orb_low")

            if orb_high is not None and orb_low is not None:
                orb_h = Decimal(str(orb_high))
                orb_l = Decimal(str(orb_low))
                orb_mid = (orb_h + orb_l) / Decimal("2")
                # Breakdown condition: must pierce or trade below the range floor
                if market_price > orb_l:
                    return None
                stop_dist = max(Decimal("10.00"), orb_mid - market_price)
            else:
                stop_dist = max(Decimal("10.00"), market_price * self.genome.stop_loss_pct)

            stop_price = max(Decimal("0.01"), (market_price + stop_dist).quantize(Decimal("0.01")))
            target_dist = stop_dist * Decimal("2.0")  # Strict 2.0R Target
            target_price = (market_price - target_dist).quantize(Decimal("0.01"))

            qty = self.compute_r_multiple_qty(market_price, stop_price, broker)
            if qty <= Decimal("0"):
                return None

            return OrderTicket(
                portfolio_id=self.portfolio_id,
                symbol=broker.symbol,
                side=OrderSide.SELL,
                order_type=OrderType.MARKET,
                qty=qty,
                stop_loss=stop_price,
                take_profit=target_price,
                reason=ExecutionReason.SIGNAL_ENTRY,
                timestamp=timestamp
            )'''))

# --------------------------------------------------- trailing_guard (own shape)
op("src/competitors/trailing_guard.py",
   '''            if signal == "SELL":
                self.highest_price_since_entry = Decimal("0")
                self.trailing_active = False
                return OrderTicket(
                    portfolio_id=self.portfolio_id,
                    symbol=broker.symbol,
                    side=OrderSide.SELL,
                    order_type=OrderType.MARKET,
                    qty=self.portfolio.position_qty,
                    reason=ExecutionReason.SIGNAL_EXIT,
                    timestamp=timestamp
                )''',
   '''            if signal == "SELL":
                self.highest_price_since_entry = Decimal("0")
                self.lowest_price_since_entry = Decimal("0")
                self.trailing_active = False
                return self._close_ticket(broker, timestamp)''')

op("src/competitors/trailing_guard.py",
   '''        # Opening new position
        if signal == "BUY" and self.portfolio.position_qty == Decimal("0"):
            self.highest_price_since_entry = market_price
            self.trailing_active = False

            stop_price = (market_price * (Decimal("1") - self.genome.stop_loss_pct)).quantize(Decimal("0.01"))
            qty = self.compute_r_multiple_qty(market_price, stop_price, broker)
            if qty <= Decimal("0"):
                return None

            return OrderTicket(
                portfolio_id=self.portfolio_id,
                symbol=broker.symbol,
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                qty=qty,
                stop_loss=stop_price,
                take_profit=None,
                reason=ExecutionReason.SIGNAL_ENTRY,
                timestamp=timestamp
            )

        return None''',
   '''        # Opening new position
        if signal == "BUY" and side == OrderSide.BUY and self.portfolio.position_qty == Decimal("0"):
            self.highest_price_since_entry = market_price
            self.trailing_active = False

            stop_price = (market_price * (Decimal("1") - self.genome.stop_loss_pct)).quantize(Decimal("0.01"))
            qty = self.compute_r_multiple_qty(market_price, stop_price, broker)
            if qty <= Decimal("0"):
                return None

            return OrderTicket(
                portfolio_id=self.portfolio_id,
                symbol=broker.symbol,
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                qty=qty,
                stop_loss=stop_price,
                take_profit=None,
                reason=ExecutionReason.SIGNAL_ENTRY,
                timestamp=timestamp
            )

        elif signal == "BUY" and side == OrderSide.SELL and self.portfolio.position_qty == Decimal("0"):
            self.lowest_price_since_entry = market_price
            self.trailing_active = False

            stop_price = (market_price * (Decimal("1") + self.genome.stop_loss_pct)).quantize(Decimal("0.01"))
            qty = self.compute_r_multiple_qty(market_price, stop_price, broker)
            if qty <= Decimal("0"):
                return None

            return OrderTicket(
                portfolio_id=self.portfolio_id,
                symbol=broker.symbol,
                side=OrderSide.SELL,
                order_type=OrderType.MARKET,
                qty=qty,
                stop_loss=stop_price,
                take_profit=None,
                reason=ExecutionReason.SIGNAL_ENTRY,
                timestamp=timestamp
            )

        return None''')

# ------------------------------------------- session_mean (rename of vwap.py)
# Applied to src/competitors/vwap.py content, written to session_mean.py.
rop("class VWAPPullbackCompetitor(BaseCompetitor):",
    "class SessionMeanPullbackCompetitor(BaseCompetitor):")
rop('''    """
    Profile F: Institutional VWAP Pullback (Volume-Weighted Average Price)
    - Origin: Wall Street Institutional Benchmark Trading
    - Setup: Tracks cumulative intraday Volume-Weighted Average Price (VWAP).
    - Leverage: Spot 1x (Leverage Disabled / Institutional Balance Sheet Mode)
    - Trigger: In an uptrend (Price > VWAP), waits for a shallow pullback into the VWAP
      accumulation band (within 0.25%) and enters on rebound confirmation.
    - Risk & Exit: Tight institutional stop just under VWAP (~1.2%), target set to 2.2R (~2.6%).
    - Dynamic Sizing: Quant dynamic R-Multiple sizing up to 50% position cap.
    """''',
    '''    """
    Profile F: Session Mean Pullback (NOT volume-weighted VWAP)
    - Origin: Wall Street Institutional Benchmark Trading
    - Setup: Tracks the session typical-price mean (mean of (H+L+C)/3 over the
      last 200 1-minute bars). It is deliberately NOT called VWAP: live 1-minute
      candles carry no per-bar volume, so a true volume-weighted VWAP cannot be
      computed live. Backtest bars do carry volume, so the backtest reference
      passed in as "mean_ref" is the genuine session VWAP; live passes the
      typical-price mean under the same key.
    - Leverage: Spot 1x (Leverage Disabled / Institutional Balance Sheet Mode)
    - Trigger: In an uptrend (Price > mean), waits for a shallow pullback into the
      mean accumulation band (within 0.85x ATR) and enters on rebound confirmation.
    - Risk & Exit: Tight institutional stop just under the mean (~1.2%), target set to 2.2R (~2.6%).
    - Dynamic Sizing: Quant dynamic R-Multiple sizing up to 50% position cap.
    """''')
rop('name="VWAP Pullback (Spot 1x / Institutional 2.2R)"',
    'name="Session Mean Pullback (Spot 1x / 2.2R)"')
rop(SIG_OLD, SIG_NEW)
rop(BUYCOND_OLD, BUYCOND_NEW)
rop('            vwap_val = indicators.get("vwap")',
    '            mean_ref = indicators.get("mean_ref")')
rop('            if vwap_val is not None:',
    '            if mean_ref is not None:')
rop('                vwap_dec = Decimal(str(vwap_val))',
    '                mean_dec = Decimal(str(mean_ref))')
rop('                # Pullback zone: within 0.85x ATR of institutional VWAP',
    '                # Pullback zone: within 0.85x ATR of the session mean')
rop('                if abs(market_price - vwap_dec) > (atr_dec * Decimal("0.85")):',
    '                if abs(market_price - mean_dec) > (atr_dec * Decimal("0.85")):')
rop('                stop_price = max(Decimal("0.01"), (vwap_dec - max(Decimal("10.00"), atr_dec * Decimal("0.5"))).quantize(Decimal("0.01")))',
    '                stop_price = max(Decimal("0.01"), (mean_dec - max(Decimal("10.00"), atr_dec * Decimal("0.5"))).quantize(Decimal("0.01")))')
rop(SELL_OLD, _short_branch_and_close(
   '''            mean_ref = indicators.get("mean_ref")
            atr_val = indicators.get("atr", Decimal("20.00"))
            atr_dec = Decimal(str(atr_val)) if atr_val is not None else Decimal("20.00")

            if mean_ref is not None:
                mean_dec = Decimal(str(mean_ref))
                # Pullback zone: within 0.85x ATR of the session mean
                if abs(market_price - mean_dec) > (atr_dec * Decimal("0.85")):
                    return None
                stop_price = (mean_dec + max(Decimal("10.00"), atr_dec * Decimal("0.5"))).quantize(Decimal("0.01"))
                if stop_price <= market_price:
                    stop_price = (market_price * Decimal("1.007")).quantize(Decimal("0.01"))
                stop_dist = max(Decimal("10.00"), stop_price - market_price)
            else:
                stop_dist = max(Decimal("10.00"), market_price * self.genome.stop_loss_pct)
                stop_price = max(Decimal("0.01"), (market_price + stop_dist).quantize(Decimal("0.01")))

            target_dist = stop_dist * Decimal("2.2")  # 2.2R Institutional Reward
            target_price = (market_price - target_dist).quantize(Decimal("0.01"))

            qty = self.compute_r_multiple_qty(market_price, stop_price, broker)
            if qty <= Decimal("0"):
                return None

            return OrderTicket(
                portfolio_id=self.portfolio_id,
                symbol=broker.symbol,
                side=OrderSide.SELL,
                order_type=OrderType.MARKET,
                qty=qty,
                stop_loss=stop_price,
                take_profit=target_price,
                reason=ExecutionReason.SIGNAL_ENTRY,
                timestamp=timestamp
            )'''))

op("src/competitors/__init__.py",
   "from src.competitors.vwap import VWAPPullbackCompetitor",
   "from src.competitors.session_mean import SessionMeanPullbackCompetitor")

# ---------------------------------------------------------------- timemachine
op("src/data/timemachine.py",
   "from src.competitors.vwap import VWAPPullbackCompetitor",
   "from src.competitors.session_mean import SessionMeanPullbackCompetitor")
op("src/data/timemachine.py",
   "        self.comp_f = VWAPPullbackCompetitor(initial_cash=initial_cash)",
   "        self.comp_f = SessionMeanPullbackCompetitor(initial_cash=initial_cash)")
op("src/data/timemachine.py",
   '''            typ_price = (bar.high + bar.low + bar.close) / Decimal("3")
            bar_vol = bar.volume if bar.volume > Decimal("0") else Decimal("100.0")
            cum_vol += bar_vol
            cum_pv += (typ_price * bar_vol)
            vwap = (cum_pv / cum_vol).quantize(Decimal("0.01")) if cum_vol > 0 else bar.close

            orb_high = max(b.high for b in window_bars)
            orb_low = min(b.low for b in window_bars)
            orb_mid = (orb_high + orb_low) / Decimal("2")''',
   '''            typ_price = (bar.high + bar.low + bar.close) / Decimal("3")
            bar_vol = bar.volume if bar.volume > Decimal("0") else Decimal("100.0")
            cum_vol += bar_vol
            cum_pv += (typ_price * bar_vol)
            # Backtest bars carry volume, so this IS the genuine session VWAP.
            # It is passed as "mean_ref": live has no per-bar volume and passes
            # the session typical-price mean under the same key.
            vwap = (cum_pv / cum_vol).quantize(Decimal("0.01")) if cum_vol > 0 else bar.close

            # ORB range is built from CLOSED bars only: including the current
            # bar makes its own high the range ceiling, so a breakout can
            # almost never trigger (ORB was dead in backtest).
            orb_window = window_bars[:-1]
            orb_high = max(b.high for b in orb_window) if orb_window else bar.high
            orb_low = min(b.low for b in orb_window) if orb_window else bar.low
            orb_mid = (orb_high + orb_low) / Decimal("2")''')
op("src/data/timemachine.py",
   '''                "vwap": vwap,''',
   '''                "mean_ref": vwap,''')

# --------------------------------------------------------------- live_engine
LE = "src/data/live_engine.py"
op(LE, "from dataclasses import dataclass",
       "from dataclasses import dataclass, replace")
op(LE, "from src.competitors.vwap import VWAPPullbackCompetitor",
       "from src.competitors.session_mean import SessionMeanPullbackCompetitor")
op(LE, "        self.comp_f = VWAPPullbackCompetitor(initial_cash=initial_cash)",
       "        self.comp_f = SessionMeanPullbackCompetitor(initial_cash=initial_cash)")
op(LE, '        self.live_vwap: Decimal = Decimal("0.00")',
       '        self.live_typical_mean: Decimal = Decimal("0.00")')

# labels (user-visible VWAP -> session mean; portfolio id comp_vwap stays)
op(LE, '"comp_vwap": "Institutional VWAP Pullback (Spot 1x / 50% Cap)",',
       '"comp_vwap": "Session Mean Pullback (Spot 1x / 50% Cap)",')
op(LE, '"comp_vwap": "Pullback test & bounce at VWAP (Long) / Rejection at VWAP (Short) | 2.2R Target",',
       '"comp_vwap": "Pullback test & bounce at session mean (Long) / Rejection at session mean (Short) | 2.2R Target",')
op(LE, '"comp_vwap": "#14F195",   # Mint Teal (Institutional VWAP)',
       '"comp_vwap": "#14F195",   # Mint Teal (Session Mean)')
op(LE, '''        "comp_vwap": "VWAP",''',
       '''        "comp_vwap": "MEAN",''')
op(LE, '''        "comp_vwap": "Institutional VWAP",''',
       '''        "comp_vwap": "Session Mean",''')
op(LE, '''                    intent = f"VWAP {pos_dir} {p.position_qty} ETH @ ${p.avg_entry_price:,.2f} | 2.2R Target ${tp_p:,.2f}" if tp_p else f"{pos_dir} {p.position_qty} ETH"''',
       '''                    intent = f"MEAN {pos_dir} {p.position_qty} ETH @ ${p.avg_entry_price:,.2f} | 2.2R Target ${tp_p:,.2f}" if tp_p else f"{pos_dir} {p.position_qty} ETH"''')

# _try_enter_bracket gains an optional pre-built ticket; gates stay identical.
op(LE,
   '''        side: OrderSide = OrderSide.BUY,
        risk_budget: Optional[Decimal] = None
    ) -> bool:
        pid = competitor.portfolio_id''',
   '''        side: OrderSide = OrderSide.BUY,
        risk_budget: Optional[Decimal] = None,
        ticket: Optional[OrderTicket] = None
    ) -> bool:
        pid = competitor.portfolio_id

        # Ticket path (live entries routed through evaluate_signal): the
        # strategy already built SL / TP / qty; the gates below run on it.
        if ticket is not None:
            side = ticket.side
            sl = ticket.stop_loss
            tp = ticket.take_profit''')
op(LE,
   '''        qty = competitor.compute_r_multiple_qty(price, sl, self.broker, risk_budget=risk_budget)
        if qty <= Decimal("0"):
            return False

        fill = self.broker.submit_order(OrderTicket(
            portfolio_id=pid, symbol=self.symbol, side=side,
            order_type=OrderType.MARKET, qty=qty, stop_loss=sl, take_profit=tp, timestamp=ts
        ))''',
   '''        if ticket is not None:
            if ticket.qty <= Decimal("0"):
                return False
            if tp != ticket.take_profit:
                ticket = replace(ticket, take_profit=tp)
        else:
            qty = competitor.compute_r_multiple_qty(price, sl, self.broker, risk_budget=risk_budget)
            if qty <= Decimal("0"):
                return False
            ticket = OrderTicket(
                portfolio_id=pid, symbol=self.symbol, side=side,
                order_type=OrderType.MARKET, qty=qty, stop_loss=sl, take_profit=tp, timestamp=ts
            )

        fill = self.broker.submit_order(ticket)''')

# New helpers, inserted right before _try_enter_bracket.
op(LE,
   '''    def _try_enter_bracket(''',
   '''    def _live_indicators(self, price: Decimal) -> Dict[str, Any]:
        """Indicator snapshot handed to evaluate_signal for live entries.

        "mean_ref" is the session typical-price mean (NOT volume-weighted
        VWAP: live 1-minute candles carry no per-bar volume). Backtest passes
        its genuine session VWAP under the same key.
        """
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

    def _try_enter_ticket(self, competitor: Any, ticket: OrderTicket, price: Decimal, ts: float, event_label: str) -> bool:
        """Submit a strategy-built ticket through the live-only gates.

        Thin wrapper over _try_enter_bracket: MTF, macro veto, MC EV gate,
        cooldown and bracket management all live there.
        """
        return self._try_enter_bracket(competitor, price, ticket.stop_loss, ticket.take_profit, ts, event_label, side=ticket.side, ticket=ticket)

    def _enter_via_strategy(
        self,
        competitor: Any,
        price: Decimal,
        ts: float,
        event_label: str,
        side: OrderSide = OrderSide.BUY,
        signal: str = "BUY",
    ) -> bool:
        """Route one live entry through the strategy's own evaluate_signal.

        The live per-strategy condition that called this is the live signal
        generator (the live analogue of ETHFeed.generate_signal in backtest);
        the strategy owns the bracket (SL / TP / sizing) from its genome, and
        _try_enter_bracket still applies the live-only gates. Cooldown is
        enforced here so callers only express the entry condition.
        """
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
        )
        if ticket is None:
            return False
        return self._try_enter_ticket(competitor, ticket, price, ts, event_label)

    def _try_enter_bracket(''')

# Bootstrap: warmup uses the same unweighted typical-price mean definition
# as the live loop (the old volume-weighted value was overwritten on the
# first live cadence anyway).
op(LE,
   '''            # Rolling VWAP
            cum_vol = sum(b.volume for b in recent_bars if b.volume > 0)
            cum_pv = sum(((b.high + b.low + b.close) / Decimal("3")) * b.volume for b in recent_bars if b.volume > 0)
            if cum_vol > Decimal("0"):
                self.live_vwap = (cum_pv / cum_vol).quantize(Decimal("0.01"))''',
   '''            # Rolling session typical-price mean (NOT volume-weighted VWAP:
            # the live loop recomputes the same unweighted mean every cadence,
            # so warmup uses the identical definition).
            if recent_bars:
                self.live_typical_mean = (
                    sum(((b.high + b.low + b.close) / Decimal("3")) for b in recent_bars) / Decimal(len(recent_bars))
                ).quantize(Decimal("0.01"))''')

# Live recompute: same unweighted formula, honest name + comment.
op(LE,
   '''        if cs:
            cum_p = sum((x["h"] + x["l"] + x["c"]) / 3.0 for x in cs)
            self.live_vwap = Decimal(str(round(cum_p / len(cs), 2)))''',
   '''        if cs:
            # Session typical-price mean over the last <=200 1m candles.
            # Deliberately NOT called VWAP: these candles carry no volume,
            # so no volume weighting is possible here.
            cum_p = sum((x["h"] + x["l"] + x["c"]) / 3.0 for x in cs)
            self.live_typical_mean = Decimal(str(round(cum_p / len(cs), 2)))''')

# UI state indicator key.
op(LE,
   '''                "vwap": float(self.live_vwap),''',
   '''                "typical_mean": float(self.live_typical_mean),''')

# Trailing ratchet: hardcoded 0.12% / 0.15% -> genome parameters.
op(LE, 'Decimal("0.12")', 'g_trail.trailing_trigger_pct', expected=2)
op(LE, 'Decimal("1.0015")', '(Decimal("1") + g_trail.trailing_distance_pct)')
op(LE, 'Decimal("0.9985")', '(Decimal("1") - g_trail.trailing_distance_pct)')

# Section 6 exit log tags.
op(LE, '"VWAP_TP"', '"MEAN_TP"', expected=2)

# _ensure_active_live_positions section 6: comment + fallback ref + labels.
op(LE, "        # 6. VWAP Pullback",
       "        # 6. Session Mean Pullback")
op(LE,
   '''        orb_mid = ((orb_high + orb_low) / Decimal("2")).quantize(Decimal("0.01"))
        vwap_ref = self.live_vwap if self.live_vwap > Decimal("0") else (self.live_ema_slow if self.live_ema_slow > Decimal("0") else price)''',
   '''        orb_mid = ((orb_high + orb_low) / Decimal("2")).quantize(Decimal("0.01"))
        mean_ref = self.live_typical_mean if self.live_typical_mean > Decimal("0") else (self.live_ema_slow if self.live_ema_slow > Decimal("0") else price)''')
op(LE,
   '''            if price >= vwap_ref:
                sl = (price * Decimal("0.993")).quantize(Decimal("0.01"))
                tp = (price + (price - sl) * Decimal("2.2")).quantize(Decimal("0.01"))
                self._try_enter_bracket(self.comp_f, price, sl, tp, ts, "VWAP_LONG", side=OrderSide.BUY)''',
   '''            if price >= mean_ref:
                sl = (price * Decimal("0.993")).quantize(Decimal("0.01"))
                tp = (price + (price - sl) * Decimal("2.2")).quantize(Decimal("0.01"))
                self._try_enter_bracket(self.comp_f, price, sl, tp, ts, "MEAN_LONG", side=OrderSide.BUY)''')
op(LE,
   '''                sl = (price * Decimal("1.007")).quantize(Decimal("0.01"))
                tp = (price - (sl - price) * Decimal("2.2")).quantize(Decimal("0.01"))
                self._try_enter_bracket(self.comp_f, price, sl, tp, ts, "VWAP_SHORT", side=OrderSide.SELL)''',
   '''                sl = (price * Decimal("1.007")).quantize(Decimal("0.01"))
                tp = (price - (sl - price) * Decimal("2.2")).quantize(Decimal("0.01"))
                self._try_enter_bracket(self.comp_f, price, sl, tp, ts, "MEAN_SHORT", side=OrderSide.SELL)''')

# Section 6 exit branches: vwap_ref -> mean_ref (unique full-line anchors).
op(LE,
   '''                    if gain_pct >= Decimal("0.30") or (price <= (vwap_ref - self.live_atr * Decimal("1.5")) and gain_usd >= (self.live_atr * Decimal("0.6"))):''',
   '''                    if gain_pct >= Decimal("0.30") or (price <= (mean_ref - self.live_atr * Decimal("1.5")) and gain_usd >= (self.live_atr * Decimal("0.6"))):''')
op(LE,
   '''                    if gain_pct >= Decimal("0.30") or (price >= (vwap_ref + self.live_atr * Decimal("1.5")) and gain_usd >= (self.live_atr * Decimal("0.6"))):''',
   '''                    if gain_pct >= Decimal("0.30") or (price >= (mean_ref + self.live_atr * Decimal("1.5")) and gain_usd >= (self.live_atr * Decimal("0.6"))):''')

# macro_commander display map.
op("src/intelligence/macro_commander.py",
   '''        "comp_vwap": "Strategy 6 (VWAP)",''',
   '''        "comp_vwap": "Strategy 6 (Mean)",''')

# --------------------------------------- live entries via evaluate_signal
# 1. Aggressive: bracket (genome SL/TP) was already identical; only routing changes.
op(LE,
   '''        if p_agg.position_qty == Decimal("0"):
            can_enter = ts >= self.strategy_cooldown.get("comp_agg", 0.0)
            if can_enter and ((is_uptrend and vel > Decimal("0") and self.live_rsi < Decimal("68")) or (vel > self.live_atr * Decimal("0.25"))):
                sl = (price * (Decimal("1") - g_agg.stop_loss_pct)).quantize(Decimal("0.01"))
                tp = (price * (Decimal("1") + g_agg.take_profit_pct)).quantize(Decimal("0.01")) if g_agg.take_profit_pct else None
                self._try_enter_bracket(self.comp_a, price, sl, tp, ts, "BREAKOUT_LONG", side=OrderSide.BUY)
            elif can_enter and (((not is_uptrend) and vel < Decimal("0") and self.live_rsi > Decimal("32")) or (vel < -self.live_atr * Decimal("0.25"))):
                sl = (price * (Decimal("1") + g_agg.stop_loss_pct)).quantize(Decimal("0.01"))
                tp = (price * (Decimal("1") - g_agg.take_profit_pct)).quantize(Decimal("0.01")) if g_agg.take_profit_pct else None
                self._try_enter_bracket(self.comp_a, price, sl, tp, ts, "BREAKDOWN_SHORT", side=OrderSide.SELL)''',
   '''        if p_agg.position_qty == Decimal("0"):
            if (is_uptrend and vel > Decimal("0") and self.live_rsi < Decimal("68")) or (vel > self.live_atr * Decimal("0.25")):
                self._enter_via_strategy(self.comp_a, price, ts, "BREAKOUT_LONG", side=OrderSide.BUY)
            elif ((not is_uptrend) and vel < Decimal("0") and self.live_rsi > Decimal("32")) or (vel < -self.live_atr * Decimal("0.25")):
                self._enter_via_strategy(self.comp_a, price, ts, "BREAKDOWN_SHORT", side=OrderSide.SELL)''')

# 2. Conservative: live 0.6%/0.9% caps are gone; genome 1.0%/1.8% governs now.
op(LE,
   '''        if p_cons.position_qty == Decimal("0"):
            can_enter = ts >= self.strategy_cooldown.get("comp_cons", 0.0)
            sl_pct = min(Decimal("0.006"), g_cons.stop_loss_pct)
            tp_pct = min(Decimal("0.009"), g_cons.take_profit_pct or Decimal("0.009"))
            if can_enter and self.live_rsi <= Decimal("52.0") and vel >= Decimal("0"):
                sl = (price * (Decimal("1") - sl_pct)).quantize(Decimal("0.01"))
                tp = (price * (Decimal("1") + tp_pct)).quantize(Decimal("0.01"))
                self._try_enter_bracket(self.comp_b, price, sl, tp, ts, "SCALP_LONG", side=OrderSide.BUY)
            elif can_enter and self.live_rsi >= Decimal("58.0") and vel <= Decimal("0"):
                sl = (price * (Decimal("1") + sl_pct)).quantize(Decimal("0.01"))
                tp = (price * (Decimal("1") - tp_pct)).quantize(Decimal("0.01"))
                self._try_enter_bracket(self.comp_b, price, sl, tp, ts, "SCALP_SHORT", side=OrderSide.SELL)''',
   '''        if p_cons.position_qty == Decimal("0"):
            # Bracket now comes from the strategy's own evaluate_signal
            # (genome SL 1.0% / TP 1.8%); the live 0.6% / 0.9% caps are gone
            # so backtest and live finally trade the same bracket.
            if self.live_rsi <= Decimal("52.0") and vel >= Decimal("0"):
                self._enter_via_strategy(self.comp_b, price, ts, "SCALP_LONG", side=OrderSide.BUY)
            elif self.live_rsi >= Decimal("58.0") and vel <= Decimal("0"):
                self._enter_via_strategy(self.comp_b, price, ts, "SCALP_SHORT", side=OrderSide.SELL)''')

# 3. ATR: live $5/$10 floors are gone; strategy ATR math governs now.
op(LE,
   '''        if p_atr.position_qty == Decimal("0"):
            can_enter = ts >= self.strategy_cooldown.get("comp_atr", 0.0)
            stop_dist = max(Decimal("5.00"), (self.live_atr * g_atr.atr_stop_mult).quantize(Decimal("0.01")))
            target_dist = max(Decimal("10.00"), (self.live_atr * g_atr.atr_target_mult).quantize(Decimal("0.01")))
            risk_budget = p_atr.total_equity * g_atr.atr_risk_pct
            if can_enter and ((price >= self.live_ema_fast and vel > Decimal("0")) or self.live_rsi < Decimal("42")):
                sl = (price - stop_dist).quantize(Decimal("0.01"))
                tp = (price + target_dist).quantize(Decimal("0.01"))
                self._try_enter_bracket(self.comp_c, price, sl, tp, ts, "ATR_ADAPT_LONG", side=OrderSide.BUY, risk_budget=risk_budget)
            elif can_enter and ((price <= self.live_ema_fast and vel < Decimal("0")) or self.live_rsi > Decimal("58")):
                sl = (price + stop_dist).quantize(Decimal("0.01"))
                tp = (price - target_dist).quantize(Decimal("0.01"))
                self._try_enter_bracket(self.comp_c, price, sl, tp, ts, "ATR_ADAPT_SHORT", side=OrderSide.SELL, risk_budget=risk_budget)''',
   '''        if p_atr.position_qty == Decimal("0"):
            # Bracket (ATR stop/target + risk budget) now comes from the
            # strategy's own evaluate_signal; the live $5/$10 floors are gone.
            if (price >= self.live_ema_fast and vel > Decimal("0")) or self.live_rsi < Decimal("42"):
                self._enter_via_strategy(self.comp_c, price, ts, "ATR_ADAPT_LONG", side=OrderSide.BUY)
            elif (price <= self.live_ema_fast and vel < Decimal("0")) or self.live_rsi > Decimal("58"):
                self._enter_via_strategy(self.comp_c, price, ts, "ATR_ADAPT_SHORT", side=OrderSide.SELL)''')

# 4. Trailing Guard entry: live 0.9% guard is gone; genome SL 1.5% governs.
# (The ratchet itself stays inline -- it is short-aware, unlike the
# strategy's long-only ratchet -- but now uses genome trigger/distance.)
op(LE,
   '''        else:
            can_enter = ts >= self.strategy_cooldown.get("comp_trail", 0.0)
            if can_enter and vel >= Decimal("0") and self.live_rsi < Decimal("66") and (is_uptrend or self.live_rsi <= Decimal("50")):
                sl = (price * Decimal("0.991")).quantize(Decimal("0.01"))  # 0.9% initial guard
                if self._try_enter_bracket(self.comp_d, price, sl, None, ts, "TRAIL_LONG", side=OrderSide.BUY):
                    self.comp_d.highest_price_since_entry = price
                    self.comp_d.lowest_price_since_entry = price
                    self.comp_d.trailing_active = False
            elif can_enter and vel <= Decimal("0") and self.live_rsi > Decimal("34") and ((not is_uptrend) or self.live_rsi >= Decimal("50")):
                sl = (price * Decimal("1.009")).quantize(Decimal("0.01"))  # 0.9% initial guard
                if self._try_enter_bracket(self.comp_d, price, sl, None, ts, "TRAIL_SHORT", side=OrderSide.SELL):
                    self.comp_d.highest_price_since_entry = price
                    self.comp_d.lowest_price_since_entry = price
                    self.comp_d.trailing_active = False''',
   '''        else:
            # Entry bracket (genome SL 1.5%, uncapped) now comes from the
            # strategy's own evaluate_signal; the live 0.9% guard is gone.
            # evaluate_signal also arms highest/lowest on entry.
            if vel >= Decimal("0") and self.live_rsi < Decimal("66") and (is_uptrend or self.live_rsi <= Decimal("50")):
                self._enter_via_strategy(self.comp_d, price, ts, "TRAIL_LONG", side=OrderSide.BUY)
            elif vel <= Decimal("0") and self.live_rsi > Decimal("34") and ((not is_uptrend) or self.live_rsi >= Decimal("50")):
                self._enter_via_strategy(self.comp_d, price, ts, "TRAIL_SHORT", side=OrderSide.SELL)''')

# 5. ORB: the strategy re-checks the strict ceiling/floor pierce, so the
# looser mid-range trigger below can only produce a ticket on a real breakout.
op(LE,
   '''        if p_orb.position_qty == Decimal("0"):
            can_enter = ts >= self.strategy_cooldown.get("comp_orb", 0.0)
            is_breakout = (price >= orb_high and vel >= Decimal("0")) or (price > orb_mid and is_uptrend and vel > self.live_atr * Decimal("0.2"))
            is_breakdown = (price <= orb_low and vel <= Decimal("0")) or (price < orb_mid and (not is_uptrend) and vel < -self.live_atr * Decimal("0.2"))
            if can_enter and is_breakout and self.live_rsi < Decimal("72"):
                sl = max(orb_mid, (price - max(Decimal("50.00"), self.live_atr * Decimal("1.2"))).quantize(Decimal("0.01")))
                if sl >= price:
                    sl = (price * Decimal("0.992")).quantize(Decimal("0.01"))
                r_dist = price - sl
                tp = (price + r_dist * Decimal("2.0")).quantize(Decimal("0.01"))
                self._try_enter_bracket(self.comp_e, price, sl, tp, ts, "ORB_LONG", side=OrderSide.BUY)
            elif can_enter and is_breakdown and self.live_rsi > Decimal("28"):
                sl = min(orb_mid, (price + max(Decimal("50.00"), self.live_atr * Decimal("1.2"))).quantize(Decimal("0.01")))
                if sl <= price:
                    sl = (price * Decimal("1.008")).quantize(Decimal("0.01"))
                r_dist = sl - price
                tp = (price - r_dist * Decimal("2.0")).quantize(Decimal("0.01"))
                self._try_enter_bracket(self.comp_e, price, sl, tp, ts, "ORB_SHORT", side=OrderSide.SELL)''',
   '''        if p_orb.position_qty == Decimal("0"):
            is_breakout = (price >= orb_high and vel >= Decimal("0")) or (price > orb_mid and is_uptrend and vel > self.live_atr * Decimal("0.2"))
            is_breakdown = (price <= orb_low and vel <= Decimal("0")) or (price < orb_mid and (not is_uptrend) and vel < -self.live_atr * Decimal("0.2"))
            # Bracket (midpoint SL, 2.0R) now comes from the strategy's own
            # evaluate_signal; the live $50/ATR*1.2 SL floor is gone.
            if is_breakout and self.live_rsi < Decimal("72"):
                self._enter_via_strategy(self.comp_e, price, ts, "ORB_LONG", side=OrderSide.BUY)
            elif is_breakdown and self.live_rsi > Decimal("28"):
                self._enter_via_strategy(self.comp_e, price, ts, "ORB_SHORT", side=OrderSide.SELL)''')

# 6. Session Mean Pullback entry.
op(LE,
   '''        # --- 6. Institutional VWAP Pullback (comp_vwap) ---
        p_vwap = self.comp_f.portfolio
        g_vwap = self.comp_f.genome
        vwap_ref = self.live_vwap if self.live_vwap > Decimal("0") else (self.live_ema_slow if self.live_ema_slow > Decimal("0") else price)

        if p_vwap.position_qty == Decimal("0"):
            can_enter = ts >= self.strategy_cooldown.get("comp_vwap", 0.0)
            near_vwap = abs(price - vwap_ref) <= (self.live_atr * Decimal("0.85"))
            is_rebound = vel >= Decimal("0") and self.live_rsi >= Decimal("42") and price >= (vwap_ref - self.live_atr * Decimal("0.5"))
            is_rejection = vel <= Decimal("0") and self.live_rsi <= Decimal("58") and price <= (vwap_ref + self.live_atr * Decimal("0.5"))
            if can_enter and near_vwap and is_rebound:
                sl = (vwap_ref - max(Decimal("5.00"), self.live_atr * Decimal("0.6"))).quantize(Decimal("0.01"))
                if sl >= price:
                    sl = (price * Decimal("0.993")).quantize(Decimal("0.01"))
                r_dist = price - sl
                tp = (price + r_dist * Decimal("2.2")).quantize(Decimal("0.01"))
                self._try_enter_bracket(self.comp_f, price, sl, tp, ts, "VWAP_LONG", side=OrderSide.BUY)
            elif can_enter and near_vwap and is_rejection:
                sl = (vwap_ref + max(Decimal("5.00"), self.live_atr * Decimal("0.6"))).quantize(Decimal("0.01"))
                if sl <= price:
                    sl = (price * Decimal("1.007")).quantize(Decimal("0.01"))
                r_dist = sl - price
                tp = (price - r_dist * Decimal("2.2")).quantize(Decimal("0.01"))
                self._try_enter_bracket(self.comp_f, price, sl, tp, ts, "VWAP_SHORT", side=OrderSide.SELL)

            if p_vwap.position_qty == Decimal("0") and not self.strategy_telemetry["comp_vwap"]["intent"].startswith(("EV Gate", "Macro Veto")):
                self.strategy_telemetry["comp_vwap"]["intent"] = f"Awaiting VWAP bounce / rejection near ${vwap_ref:,.2f}"''',
   '''        # --- 6. Session Mean Pullback (comp_vwap) ---
        # NOTE: the reference is the session typical-price mean, NOT a
        # volume-weighted VWAP (live 1m candles carry no volume).
        p_vwap = self.comp_f.portfolio
        g_vwap = self.comp_f.genome
        mean_ref = self.live_typical_mean if self.live_typical_mean > Decimal("0") else (self.live_ema_slow if self.live_ema_slow > Decimal("0") else price)

        if p_vwap.position_qty == Decimal("0"):
            near_mean = abs(price - mean_ref) <= (self.live_atr * Decimal("0.85"))
            is_rebound = vel >= Decimal("0") and self.live_rsi >= Decimal("42") and price >= (mean_ref - self.live_atr * Decimal("0.5"))
            is_rejection = vel <= Decimal("0") and self.live_rsi <= Decimal("58") and price <= (mean_ref + self.live_atr * Decimal("0.5"))
            # Bracket (mean-anchored SL, 2.2R) now comes from the strategy's
            # own evaluate_signal; the live $5/ATR*0.6 SL rule is gone.
            if near_mean and is_rebound:
                self._enter_via_strategy(self.comp_f, price, ts, "MEAN_LONG", side=OrderSide.BUY)
            elif near_mean and is_rejection:
                self._enter_via_strategy(self.comp_f, price, ts, "MEAN_SHORT", side=OrderSide.SELL)

            if p_vwap.position_qty == Decimal("0") and not self.strategy_telemetry["comp_vwap"]["intent"].startswith(("EV Gate", "Macro Veto")):
                self.strategy_telemetry["comp_vwap"]["intent"] = f"Awaiting session-mean bounce / rejection near ${mean_ref:,.2f}"''')

# ------------------------------------------------------------------ frontend
op("src/gui/assets/index.html",
   '''<span class="legend-item"><i class="legend-swatch" style="background:var(--c-vwap)"></i>VWAP</span>''',
   '''<span class="legend-item"><i class="legend-swatch" style="background:var(--c-mean)"></i>MEAN</span>''')
op("src/gui/assets/index.html",
   '''<span class="legend-item" title="Institutional VWAP Pullback"><i class="legend-dot" style="background:var(--c-vwap)"></i>VWAP</span>''',
   '''<span class="legend-item" title="Session Mean Pullback"><i class="legend-dot" style="background:var(--c-mean)"></i>MEAN</span>''')
op("src/gui/assets/app.css",
   '''  --c-vwap:             #60A5FA; /* Sapphire Ice */''',
   '''  --c-mean:             #60A5FA; /* Sapphire Ice */''')

# ---------------------------------------------------------------------- tests
op("tests/test_competitors.py",
   "from src.competitors.vwap import VWAPPullbackCompetitor",
   "from src.competitors.session_mean import SessionMeanPullbackCompetitor")
op("tests/test_competitors.py",
   "    comp_f = VWAPPullbackCompetitor()",
   "    comp_f = SessionMeanPullbackCompetitor()")
op("tests/test_competitors.py",
   '''        "vwap": Decimal("2500.00")''',
   '''        "mean_ref": Decimal("2500.00")''')
op("tests/test_competitors.py",
   "    # F (VWAP Pullback Spot 1x ~50% of 100,000 = $50,000 / 2500 = 20 BTC)",
   "    # F (Session Mean Pullback Spot 1x ~50% of 100,000 = $50,000 / 2500 = 20 BTC)")
op("tests/test_competitors.py",
   "def test_vwap_competitor_pullback_and_r_multiple():",
   "def test_session_mean_competitor_pullback_and_r_multiple():")
op("tests/test_competitors.py",
   "    comp = VWAPPullbackCompetitor()",
   "    comp = SessionMeanPullbackCompetitor()")
op("tests/test_competitors.py",
   '''    vwap = Decimal("2500.00")''',
   '''    mean_ref = Decimal("2500.00")''')
op("tests/test_competitors.py",
   '''        indicators={"vwap": vwap, "atr": atr, "rsi": Decimal("50.00")},''',
   '''        indicators={"mean_ref": mean_ref, "atr": atr, "rsi": Decimal("50.00")},''')
op("tests/test_competitors.py",
   '''        indicators={"vwap": vwap, "atr": atr, "rsi": Decimal("48.00")},''',
   '''        indicators={"mean_ref": mean_ref, "atr": atr, "rsi": Decimal("48.00")},''')
op("tests/test_competitors.py",
   "    # 1. Price too far above VWAP (> 0.85 * 20 = 17 away): should NOT trigger pullback buy",
   "    # 1. Price too far above the session mean (> 0.85 * 20 = 17 away): should NOT trigger pullback buy")
op("tests/test_competitors.py",
   "    # 2. Price pulls back near VWAP (within 17): triggers pullback BUY",
   "    # 2. Price pulls back near the session mean (within 17): triggers pullback BUY")
op("tests/test_risk_semantics.py",
   "from src.competitors.vwap import VWAPPullbackCompetitor",
   "from src.competitors.session_mean import SessionMeanPullbackCompetitor")
op("tests/test_risk_semantics.py",
   "                TrailingGuardCompetitor, ORBCompetitor, VWAPPullbackCompetitor):",
   "                TrailingGuardCompetitor, ORBCompetitor, SessionMeanPullbackCompetitor):")

APPENDS.append(("tests/test_competitors.py", '''

def test_evaluate_signal_short_entries_mirror_long_brackets():
    """Item 2: evaluate_signal supports short entries (new `side` param).

    Live routes short entries through evaluate_signal, so the mirrored
    bracket must be the exact mirror of the long bracket, and a SELL
    signal must close a short with a BUY ticket.
    """
    broker = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0.0"))
    comp = AggressiveCompetitor()
    broker.register_portfolio(comp.portfolio, max_position_ratio=comp.max_position_ratio)
    broker.on_tick(Decimal("2500.00"), timestamp=100.0)

    ticket = comp.evaluate_signal(
        signal="BUY",
        market_price=Decimal("2500.00"),
        indicators={"atr": Decimal("35.00")},
        broker=broker,
        timestamp=100.0,
        side=OrderSide.SELL,
    )
    assert ticket is not None
    assert ticket.side == OrderSide.SELL
    # Aggressive genome SL 3.5%: short stop sits above entry, no TP (uncapped).
    assert ticket.stop_loss == Decimal("2587.50")
    assert ticket.take_profit is None
    fill = broker.submit_order(ticket)
    assert fill is not None
    assert comp.portfolio.position_side.value == "SHORT"

    close_ticket = comp.evaluate_signal(
        signal="SELL",
        market_price=Decimal("2500.00"),
        indicators={},
        broker=broker,
        timestamp=110.0,
    )
    assert close_ticket is not None
    assert close_ticket.side == OrderSide.BUY
    assert close_ticket.qty == comp.portfolio.position_qty
'''))

APPENDS.append(("tests/test_timemachine.py", '''

def test_orb_window_excludes_current_bar():
    """Item 2 regression: ORB range must come from closed bars only.

    Before the fix the current bar was included in the ORB window, so its
    own high became the range ceiling and a breakout could (almost) never
    trigger: 60 BUY bars produced 0 ORB fills.
    """
    arena = TimeMachineArena(symbol="ETH/USD", initial_cash=Decimal("500000.00"))
    bars = []
    for i in range(15):
        price = Decimal("2495.00")
        bars.append(CandleBar(
            timestamp=1000.0 + (i * 900),
            open_=price - Decimal("2.00"),
            high=Decimal("2500.00"),
            low=Decimal("2490.00"),
            close=price,
            volume=Decimal("100.0"),
            ema_fast=price + Decimal("1.00"),
            ema_slow=price - Decimal("5.00"),
            rsi=Decimal("55.00"),
            atr=Decimal("25.00")
        ))
    bars.append(CandleBar(
        timestamp=1000.0 + (15 * 900),
        open_=Decimal("2505.00"),
        high=Decimal("2515.00"),
        low=Decimal("2500.00"),
        close=Decimal("2510.00"),
        volume=Decimal("100.0"),
        ema_fast=Decimal("2508.00"),
        ema_slow=Decimal("2500.00"),
        rsi=Decimal("56.00"),
        atr=Decimal("25.00")
    ))
    rankings = arena.run_simulation(bars)
    assert len(rankings) == 6
    # The breakout bar closes above the prior 15-bar high (2500): ORB must fire.
    assert arena.comp_e.portfolio.position_qty > Decimal("0")
'''))


def main():
    # ---- Phase 1: verify every replacement before writing anything. ----
    for rel, old, new, expected in OPS:
        text, nl = _read(ROOT / rel)
        n = text.count(_norm(old, nl))
        assert n == expected, f"VERIFY FAIL {rel}: expected {expected}, found {n}: {old[:80]!r}"
    src_path = ROOT / RENAME_SRC
    dst_path = ROOT / RENAME_DST
    assert src_path.exists(), f"VERIFY FAIL: missing {RENAME_SRC}"
    assert not dst_path.exists(), f"VERIFY FAIL: {RENAME_DST} already exists"
    vwap_text, vwap_nl = _read(src_path)
    for old, new, expected in RENAME_OPS:
        n = vwap_text.count(_norm(old, vwap_nl))
        assert n == expected, f"VERIFY FAIL {RENAME_SRC}: expected {expected}, found {n}: {old[:80]!r}"
    for rel, text_add in APPENDS:
        text, nl = _read(ROOT / rel)
        marker = "test_orb_window_excludes_current_bar" if "timemachine" in rel else "test_evaluate_signal_short_entries_mirror_long_brackets"
        assert marker not in text, f"VERIFY FAIL {rel}: already contains {marker}"
    print(f"Phase 1 verification passed ({len(OPS)} replacements + {len(RENAME_OPS)} rename ops + {len(APPENDS)} appends).")

    # ---- Phase 2: apply. ----
    for rel, old, new, expected in OPS:
        p = ROOT / rel
        text, nl = _read(p)
        p.write_bytes(text.replace(_norm(old, nl), _norm(new, nl)).encode("utf-8"))
        print(f"patched {rel}")
    new_text = vwap_text
    for old, new, expected in RENAME_OPS:
        new_text = new_text.replace(_norm(old, vwap_nl), _norm(new, vwap_nl))
    dst_path.write_bytes(new_text.encode("utf-8"))
    os.remove(src_path)
    for pyc in (ROOT / "src/competitors/__pycache__").glob("vwap.*"):
        os.remove(pyc)
        print(f"removed stale {pyc}")
    print(f"renamed {RENAME_SRC} -> {RENAME_DST}")
    for rel, text_add in APPENDS:
        p = ROOT / rel
        text, nl = _read(p)
        if not text.endswith(nl):
            text += nl
        p.write_bytes((text + _norm(text_add, nl)).encode("utf-8"))
        print(f"appended to {rel}")

    # ---- Phase 3: post-conditions. ----
    le = (ROOT / "src/data/live_engine.py").read_bytes().decode("utf-8")
    assert "live_vwap" not in le, "post-check: live_vwap still in live_engine.py"
    assert '"vwap"' not in le, "post-check: \"vwap\" key still in live_engine.py"
    tm = (ROOT / "src/data/timemachine.py").read_bytes().decode("utf-8")
    assert '"vwap"' not in tm, "post-check: \"vwap\" key still in timemachine.py"
    sm = (ROOT / RENAME_DST).read_bytes().decode("utf-8")
    assert '"vwap"' not in sm, "post-check: \"vwap\" key still in session_mean.py"
    assert not (ROOT / RENAME_SRC).exists(), "post-check: vwap.py still exists"
    leftovers = []
    for py in list((ROOT / "src").rglob("*.py")) + list((ROOT / "tests").glob("*.py")):
        if "__pycache__" in py.parts:
            continue
        if "VWAPPullbackCompetitor" in py.read_bytes().decode("utf-8"):
            leftovers.append(str(py))
    assert not leftovers, f"post-check: VWAPPullbackCompetitor still referenced in {leftovers}"
    print("ALL PATCHES APPLIED")


if __name__ == "__main__":
    main()
