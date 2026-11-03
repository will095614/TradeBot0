from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN
from typing import Dict, List, Any, Optional
import math
import threading
import time
import requests

from src.arena.broker_sim import BrokerSim
from src.arena.order import OrderTicket, OrderSide, OrderType, ExecutionReason, FillEvent
from src.arena.leaderboard import Leaderboard
from src.arena.evolution import GeneticEvolver
from src.ai.omniroute_client import OmniRouteGateway
from src.competitors.aggressive import AggressiveCompetitor
from src.competitors.conservative import ConservativeCompetitor
from src.competitors.atr_dynamic import ATRDynamicCompetitor
from src.competitors.trailing_guard import TrailingGuardCompetitor
from src.competitors.orb import ORBCompetitor
from src.competitors.vwap import VWAPPullbackCompetitor
from src.data.eth_feed import ETHFeed, CandleBar
from src.data.timemachine import MonteCarloOddsEvaluator, MonteCarloBracketOdds


@dataclass
class LiveQuote:
    price: Decimal
    bid: Decimal
    ask: Decimal
    high_24h: Decimal
    low_24h: Decimal
    volume_24h: Decimal
    change_24h_pct: Decimal
    source: str
    timestamp: float


class LiveArenaEngine:
    """
    Real-Time Live Multi-Strategy Paper Trading Engine for ETH/USD.
    - Streams real-time live spot quotes from Coinbase / Binance / Kraken public REST APIs every 1.5s.
    - Bootstraps with the most recent 60 minutes of 1-minute live ETH/USD bars so indicators and
      active strategy positions are immediately hot on startup.
    - Operates 4 distinct real-time strategies (Aggressive Breakout, Conservative Scalper,
      ATR Volatility Adaptive, Trailing Profit Ratchet) simultaneously on every live tick.
    """
    def __init__(self, initial_cash: Decimal = Decimal("500000.00"), symbol: str = "ETH/USD"):
        self.symbol = symbol
        self.initial_cash = initial_cash
        self.lock = threading.RLock()
        self.omniroute = OmniRouteGateway()
        self.running = False
        self.paused = False
        self.interval_sec: float = 1.5
        self.worker_thread: Optional[threading.Thread] = None
        # Persistent structured fill tape (survives broker re-init on evolution)
        self.fill_records: List[FillEvent] = []
        self._audit_cursor: int = 0
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "TradeBot0-LiveArena/2.0"})

        self.comp_a = AggressiveCompetitor(initial_cash=initial_cash)
        self.comp_b = ConservativeCompetitor(initial_cash=initial_cash)
        self.comp_c = ATRDynamicCompetitor(initial_cash=initial_cash)
        self.comp_d = TrailingGuardCompetitor(initial_cash=initial_cash)
        self.comp_e = ORBCompetitor(initial_cash=initial_cash)
        self.comp_f = VWAPPullbackCompetitor(initial_cash=initial_cash)
        self.competitors = [
            self.comp_a, self.comp_b, self.comp_c,
            self.comp_d, self.comp_e, self.comp_f
        ]

        # Strategy live telemetry descriptions (what each strategy is doing right now)
        self.strategy_telemetry: Dict[str, Dict[str, Any]] = {}
        self.tick_timestamps: List[str] = []
        self.eth_price_series: List[float] = []
        self.ema_fast_series: List[float] = []
        self.ema_slow_series: List[float] = []
        self.equity_series: Dict[str, List[float]] = {
            "comp_agg": [],
            "comp_cons": [],
            "comp_atr": [],
            "comp_trail": [],
            "comp_orb": [],
            "comp_vwap": [],
        }
        self.live_logs: List[Dict[str, str]] = []
        self.latest_quote: Optional[LiveQuote] = None
        self.tick_count: int = 0
        self.live_atr: Decimal = Decimal("4.50")
        self.live_rsi: Decimal = Decimal("50.00")
        self.live_ema_fast: Decimal = Decimal("0.00")
        self.live_ema_slow: Decimal = Decimal("0.00")
        self.live_vwap: Decimal = Decimal("0.00")
        self.live_orb_high: Decimal = Decimal("0.00")
        self.live_orb_low: Decimal = Decimal("0.00")

        # 1-minute OHLC candles (bootstrap bars + live ticks aggregated) for charting & live RSI/ATR
        self.candles: List[Dict[str, float]] = []
        self.max_candles: int = 200
        # Equity curve keeps ~1 hour of live ticks (one full generation) with epoch timestamps
        self.equity_ts: List[float] = []
        self.max_equity_pts: int = 3000
        self.live_start_ts: Optional[float] = None

        # Style-B automatic hourly evolution
        self.auto_evolve_enabled: bool = True
        self.auto_evolve_interval_sec: int = 21600  # Default 6 hours (21600s)
        self.last_evolve_ts: float = time.time()
        self.evolution_events: List[Dict[str, Any]] = []

        # TradingView Paper Trading Auto-Pilot Dispatcher
        self.tv_champion: Dict[str, Any] = {
            "strategy_id": "comp_agg",
            "name": "Aggressive Momentum",
            "generation": 1,
            "roi_pct": 0.0,
            "fitness": 0.0,
            "status": "Gen #1 Running (Live Candidate #1)",
        }
        self.tv_dispatch_log: List[Dict[str, Any]] = []

        # Anti-churn cooldown & hold-duration tracking
        self.strategy_cooldown: Dict[str, float] = {}
        self.position_entry_ts: Dict[str, float] = {}

        # TimeMachine Monte Carlo Odds Evaluator & EV Gate (day-trader-skill)
        self.mc_evaluator = MonteCarloOddsEvaluator(seed=19)

        self._init_broker()

    def _harvest_fills(self) -> None:
        """Copies new broker fills into the persistent tape (bounded to 200 records)."""
        audit = self.broker.execution_audit
        if self._audit_cursor < len(audit):
            self.fill_records.extend(audit[self._audit_cursor:])
            self._audit_cursor = len(audit)
            if len(self.fill_records) > 200:
                self.fill_records = self.fill_records[-200:]
            if self._audit_cursor > 500:
                self.broker.execution_audit = self.broker.execution_audit[self._audit_cursor:]
                self._audit_cursor = 0

    def _init_broker(self) -> None:
        self.broker = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0.0001"))
        self._audit_cursor = 0
        for c in self.competitors:
            self.broker.register_portfolio(c.portfolio, max_position_ratio=c.max_position_ratio)
            self.strategy_telemetry[c.portfolio_id] = {
                "strategy_type": self._get_strategy_label(c.portfolio_id),
                "intent": "Warming up live orderflow indicators...",
                "entry_rule": self._get_entry_rule_desc(c.portfolio_id),
                "stop_price": None,
                "target_price": None,
                "mc_stats": {},
            }

    @staticmethod
    def _get_strategy_label(pid: str) -> str:
        labels = {
            "comp_agg": "Momentum Breakout (70% Cap)",
            "comp_cons": "Mean-Reversion Scalper (25% Cap)",
            "comp_atr": "ATR Volatility Adaptive (Dynamic)",
            "comp_trail": "Trailing Ratchet Guard (40% Cap)",
            "comp_orb": "Opening Range Breakout (45% Cap)",
            "comp_vwap": "Institutional VWAP Pullback (50% Cap)",
        }
        return labels.get(pid, pid)

    @staticmethod
    def _get_entry_rule_desc(pid: str) -> str:
        rules = {
            "comp_agg": "Breakout > EMA-Fast + positive tick velocity | Wide SL, Uncapped Run",
            "comp_cons": "Pullback dip bounce (RSI < 52 or lower band) | Tight SL & Quick Scalp TP",
            "comp_atr": "Volatility-scaled size (1.5% risk / 1.5x ATR SL / 2.5x ATR TP)",
            "comp_trail": "Trend alignment entry + automatic breakeven & 0.25% live peak ratchet",
            "comp_orb": "Breakout > 15m Range High | Dynamic Midpoint SL & 2.0R Target",
            "comp_vwap": "Pullback test of Session VWAP + Rebound | Tight VWAP SL & 2.2R Target",
        }
        return rules.get(pid, "")

    def log_event(self, tag: str, message: str, level: str = "info") -> None:
        with self.lock:
            ts = time.strftime("%H:%M:%S")
            self.live_logs.insert(0, {"time": ts, "tag": tag, "message": message, "level": level})
            if len(self.live_logs) > 120:
                self.live_logs.pop()

    def fetch_realtime_eth_quote(self) -> LiveQuote:
        """
        Fetches real-time live ETH/USD spot quote with sub-second latency across
        Coinbase Exchange -> Binance -> Kraken public endpoints.
        """
        # 1. Binance 24hr Live Ticker (Ultra-fast ~120ms sub-second latency)
        try:
            r_bin = self.session.get("https://api.binance.com/api/v3/ticker/24hr?symbol=ETHUSDT", timeout=1.8)
            if r_bin.status_code == 200:
                b = r_bin.json()
                return LiveQuote(
                    price=Decimal(str(b["lastPrice"])).quantize(Decimal("0.01")),
                    bid=Decimal(str(b["bidPrice"])).quantize(Decimal("0.01")),
                    ask=Decimal(str(b["askPrice"])).quantize(Decimal("0.01")),
                    high_24h=Decimal(str(b["highPrice"])).quantize(Decimal("0.01")),
                    low_24h=Decimal(str(b["lowPrice"])).quantize(Decimal("0.01")),
                    volume_24h=Decimal(str(b["volume"])).quantize(Decimal("0.01")),
                    change_24h_pct=Decimal(str(b["priceChangePercent"])).quantize(Decimal("0.01")),
                    source="Binance Live",
                    timestamp=time.time()
                )
        except Exception:
            pass

        # 2. Kraken Live Ticker Fallback
        try:
            r_krk = self.session.get("https://api.kraken.com/0/public/Ticker?pair=ETHUSD", timeout=2.0)
            if r_krk.status_code == 200:
                k_res = r_krk.json().get("result", {})
                if k_res:
                    pair_key = next(iter(k_res.keys()))
                    k = k_res[pair_key]
                    price = Decimal(str(k["c"][0])).quantize(Decimal("0.01"))
                    open_p = Decimal(str(k["o"]))
                    chg = (((price - open_p) / open_p) * Decimal("100")).quantize(Decimal("0.01")) if open_p > 0 else Decimal("0.00")
                    return LiveQuote(
                        price=price,
                        bid=Decimal(str(k["b"][0])).quantize(Decimal("0.01")),
                        ask=Decimal(str(k["a"][0])).quantize(Decimal("0.01")),
                        high_24h=Decimal(str(k["h"][1])).quantize(Decimal("0.01")),
                        low_24h=Decimal(str(k["l"][1])).quantize(Decimal("0.01")),
                        volume_24h=Decimal(str(k["v"][1])).quantize(Decimal("0.01")),
                        change_24h_pct=chg,
                        source="Kraken Live",
                        timestamp=time.time()
                    )
        except Exception:
            pass

        # 3. Coinbase Exchange Live Ticker Fallback
        try:
            r_tick = self.session.get("https://api.exchange.coinbase.com/products/ETH-USD/ticker", timeout=1.8)
            r_stats = self.session.get("https://api.exchange.coinbase.com/products/ETH-USD/stats", timeout=1.8)
            if r_tick.status_code == 200:
                t_data = r_tick.json()
                price = Decimal(str(t_data["price"])).quantize(Decimal("0.01"))
                bid = Decimal(str(t_data.get("bid", price))).quantize(Decimal("0.01"))
                ask = Decimal(str(t_data.get("ask", price))).quantize(Decimal("0.01"))
                vol = Decimal(str(t_data.get("volume", "0"))).quantize(Decimal("0.01"))
                high_24 = price
                low_24 = price
                chg_pct = Decimal("0.00")
                if r_stats.status_code == 200:
                    s_data = r_stats.json()
                    open_24 = Decimal(str(s_data.get("open", price)))
                    high_24 = Decimal(str(s_data.get("high", price))).quantize(Decimal("0.01"))
                    low_24 = Decimal(str(s_data.get("low", price))).quantize(Decimal("0.01"))
                    if open_24 > Decimal("0"):
                        chg_pct = (((price - open_24) / open_24) * Decimal("100")).quantize(Decimal("0.01"))
                return LiveQuote(
                    price=price,
                    bid=bid,
                    ask=ask,
                    high_24h=high_24,
                    low_24h=low_24,
                    volume_24h=vol,
                    change_24h_pct=chg_pct,
                    source="Coinbase Live",
                    timestamp=time.time()
                )
        except Exception:
            pass

        # 4. In-Memory Resilient Cache Fallback (survives transient network disconnects)
        if self.latest_quote is not None:
            return LiveQuote(
                price=self.latest_quote.price,
                bid=self.latest_quote.bid,
                ask=self.latest_quote.ask,
                high_24h=self.latest_quote.high_24h,
                low_24h=self.latest_quote.low_24h,
                volume_24h=self.latest_quote.volume_24h,
                change_24h_pct=self.latest_quote.change_24h_pct,
                source=f"{self.latest_quote.source} (Cache)",
                timestamp=time.time()
            )

        # 5. Cold-boot default baseline if completely offline on first start
        return LiveQuote(
            price=Decimal("2250.00"),
            bid=Decimal("2249.80"),
            ask=Decimal("2250.20"),
            high_24h=Decimal("2280.00"),
            low_24h=Decimal("2220.00"),
            volume_24h=Decimal("125000.00"),
            change_24h_pct=Decimal("0.00"),
            source="Offline Default",
            timestamp=time.time()
        )

    def bootstrap_intraday_session(self) -> None:
        """
        Loads the last 120 minutes of real 1-minute ETH/USD candles to warm up live indicators
        and immediately deploy the 4 strategies into the current live market session.
        """
        try:
            bars = ETHFeed.fetch_historical_bars(ticker="ETH-USD", period="1d", interval="1m")
            recent_bars = bars[-120:] if len(bars) > 120 else bars
        except Exception:
            recent_bars = []

        with self.lock:
            for i, bar in enumerate(recent_bars):
                self.live_ema_fast = bar.ema_fast or bar.close
                self.live_ema_slow = bar.ema_slow or bar.close
                self.live_rsi = bar.rsi or Decimal("50.00")
                self.live_atr = max(Decimal("1.50"), bar.atr or Decimal("3.50"))

                fills = self.broker.on_tick(
                    price=bar.close,
                    high=bar.high,
                    low=bar.low,
                    timestamp=bar.timestamp,
                    open_price=bar.open
                )
                for f in fills:
                    if f.side == OrderSide.SELL:
                        self.strategy_cooldown[f.portfolio_id] = bar.timestamp + 60.0
                        self.position_entry_ts.pop(f.portfolio_id, None)
                    pnl_str = f" | PnL: ${f.realized_pnl:+.2f}" if f.side == OrderSide.SELL else ""
                    self.log_event(
                        f.reason.value,
                        f"{f.portfolio_id.upper()} {f.side.value} {f.qty} ETH @ ${f.price:,.2f}{pnl_str}",
                        "profit" if f.realized_pnl >= Decimal("0") else "loss"
                    )

                prev_p = recent_bars[i - 1].close if i > 0 else bar.open
                self._evaluate_live_strategies(bar.close, prev_p, bar.timestamp)
                self._update_candle(float(bar.timestamp), bar.close, bar.high, bar.low, bar.open)
                self._record_series_point(bar.close, bar.timestamp)

            # Rolling ORB range (first 15m or recent 15 bars)
            if len(recent_bars) >= 15:
                first_15 = recent_bars[:15]
                self.live_orb_high = max(b.high for b in first_15)
                self.live_orb_low = min(b.low for b in first_15)
            elif recent_bars:
                self.live_orb_high = max(b.high for b in recent_bars)
                self.live_orb_low = min(b.low for b in recent_bars)

            # Rolling VWAP
            cum_vol = sum(b.volume for b in recent_bars if b.volume > 0)
            cum_pv = sum(((b.high + b.low + b.close) / Decimal("3")) * b.volume for b in recent_bars if b.volume > 0)
            if cum_vol > Decimal("0"):
                self.live_vwap = (cum_pv / cum_vol).quantize(Decimal("0.01"))

            # Ensure all 6 distinct strategies have active or primed live setups right now
            if recent_bars:
                last_b = recent_bars[-1]
                self._ensure_active_live_positions(last_b.close, time.time())
                self.log_event(
                    "LIVE_SYNC",
                    f"Synced 1m intraday orderflow ({len(recent_bars)} bars). Live ETH/USD @ ${last_b.close:,.2f}",
                    "info"
                )

    def _evaluate_live_strategies(self, price: Decimal, prev_price: Decimal, ts: float) -> None:
        """
        Executes differentiated real-time decision logic for each of the 4 strategies on every live tick/bar.
        Incorporates anti-churn cooldowns, channel stagnation exits, and dynamic volatility adaptation.
        """
        vel = price - prev_price
        is_uptrend = self.live_ema_fast >= self.live_ema_slow

        # --- Channel Stagnation Timeout Guard (frees locked capital if dead flat > 40 min) ---
        for c in self.competitors:
            pid = c.portfolio_id
            p = c.portfolio
            if p.position_qty > Decimal("0") and p.avg_entry_price > Decimal("0"):
                entry_ts = self.position_entry_ts.get(pid, ts)
                hold_sec = ts - entry_ts
                gain_pct = ((price - p.avg_entry_price) / p.avg_entry_price) * Decimal("100")
                if hold_sec >= 2400.0 and abs(gain_pct) < Decimal("0.10"):
                    fill = self.broker.submit_order(OrderTicket(
                        portfolio_id=pid, symbol="ETH/USD", side=OrderSide.SELL,
                        order_type=OrderType.MARKET, qty=p.position_qty,
                        reason=ExecutionReason.SIGNAL, timestamp=ts
                    ))
                    if fill:
                        self.strategy_cooldown[pid] = ts + 60.0
                        self.position_entry_ts.pop(pid, None)
                        self.log_event("STAGNATION_EXIT", f"{c.base_name.split(' ')[0]} closed after 40m stagnation timeout", "info")

        # --- 1. Aggressive Momentum Breakout (comp_agg) ---
        p_agg = self.comp_a.portfolio
        g_agg = self.comp_a.genome
        if p_agg.position_qty == Decimal("0"):
            can_enter = ts >= self.strategy_cooldown.get("comp_agg", 0.0)
            if can_enter and ((is_uptrend and vel > Decimal("0") and self.live_rsi < Decimal("68")) or (vel > self.live_atr * Decimal("0.25"))):
                sl = (price * (Decimal("1") - g_agg.stop_loss_pct)).quantize(Decimal("0.01"))
                tp = (price * (Decimal("1") + g_agg.take_profit_pct)).quantize(Decimal("0.01")) if g_agg.take_profit_pct else None
                mc_odds = self.mc_evaluator.evaluate_bracket(price, sl, tp, atr=self.live_atr, recent_candles=self.candles)
                self.strategy_telemetry["comp_agg"]["mc_stats"] = mc_odds.to_dict()
                if not mc_odds.passed:
                    self.strategy_cooldown["comp_agg"] = ts + 20.0
                    self.strategy_telemetry["comp_agg"]["intent"] = f"EV Gate Blocked: Win {mc_odds.target_prob*100:.0f}% (EV {mc_odds.expected_r:+.2f}R)"
                    self.log_event("EV_GATE_BLOCK", f"Aggressive blocked by TimeMachine EV Gate: {mc_odds.verdict}", "info")
                else:
                    qty = self.comp_a.compute_r_multiple_qty(price, sl, self.broker)
                    if qty > Decimal("0"):
                        fill = self.broker.submit_order(OrderTicket(
                            portfolio_id="comp_agg", symbol="ETH/USD", side=OrderSide.BUY,
                            order_type=OrderType.MARKET, qty=qty, stop_loss=sl, take_profit=tp, timestamp=ts
                        ))
                        if fill:
                            self.position_entry_ts["comp_agg"] = ts
                            self.log_event("BREAKOUT_BUY", f"Aggressive entered {fill.qty} ETH @ ${fill.price:,.2f} (SL ${sl:,.2f} | EV {mc_odds.expected_r:+.2f}R)", "buy")
            if p_agg.position_qty == Decimal("0") and not self.strategy_telemetry["comp_agg"]["intent"].startswith("EV Gate"):
                self.strategy_telemetry["comp_agg"]["intent"] = f"Scanning breakout > ${self.live_ema_fast:,.2f}"
        else:
            entry_p = p_agg.avg_entry_price
            if entry_p > Decimal("0"):
                gain_usd = price - entry_p
                gain_pct = (gain_usd / entry_p) * Decimal("100")
                # Momentum micro-take-profit or trend stall exit
                if gain_pct >= Decimal("0.25") or (self.live_ema_fast < self.live_ema_slow and self.live_rsi < Decimal("48") and gain_usd >= Decimal("1.20")):
                    fill = self.broker.submit_order(OrderTicket(
                        portfolio_id="comp_agg", symbol="ETH/USD", side=OrderSide.SELL,
                        order_type=OrderType.MARKET, qty=p_agg.position_qty,
                        reason=ExecutionReason.TAKE_PROFIT, timestamp=ts
                    ))
                    if fill:
                        self.strategy_cooldown["comp_agg"] = ts + 60.0
                        self.position_entry_ts.pop("comp_agg", None)
                        self.log_event("MOMENTUM_TP", f"Aggressive locked profit {fill.qty} ETH @ ${fill.price:,.2f} (+${fill.realized_pnl:+.2f})", "profit")
                elif self.live_rsi > Decimal("74") and vel < Decimal("0"):
                    fill = self.broker.submit_order(OrderTicket(
                        portfolio_id="comp_agg", symbol="ETH/USD", side=OrderSide.SELL,
                        order_type=OrderType.MARKET, qty=p_agg.position_qty, timestamp=ts
                    ))
                    if fill:
                        self.strategy_cooldown["comp_agg"] = ts + 60.0
                        self.position_entry_ts.pop("comp_agg", None)
                        self.log_event("MOMENTUM_EXIT", f"Aggressive closed {fill.qty} ETH @ ${fill.price:,.2f} (PnL ${fill.realized_pnl:+.2f})", "profit" if fill.realized_pnl >= 0 else "loss")

        # --- 2. Conservative Mean-Reversion Scalper (comp_cons) ---
        p_cons = self.comp_b.portfolio
        g_cons = self.comp_b.genome
        if p_cons.position_qty == Decimal("0"):
            can_enter = ts >= self.strategy_cooldown.get("comp_cons", 0.0)
            if can_enter and self.live_rsi <= Decimal("53.5") and vel >= Decimal("0"):
                sl_pct = min(Decimal("0.006"), g_cons.stop_loss_pct)   # Tight 0.6% scalp SL
                tp_pct = min(Decimal("0.009"), g_cons.take_profit_pct or Decimal("0.009"))  # Quick 0.9% scalp TP
                sl = (price * (Decimal("1") - sl_pct)).quantize(Decimal("0.01"))
                tp = (price * (Decimal("1") + tp_pct)).quantize(Decimal("0.01"))
                mc_odds = self.mc_evaluator.evaluate_bracket(price, sl, tp, atr=self.live_atr, recent_candles=self.candles)
                self.strategy_telemetry["comp_cons"]["mc_stats"] = mc_odds.to_dict()
                if not mc_odds.passed:
                    self.strategy_cooldown["comp_cons"] = ts + 20.0
                    self.strategy_telemetry["comp_cons"]["intent"] = f"EV Gate Blocked: Win {mc_odds.target_prob*100:.0f}% (EV {mc_odds.expected_r:+.2f}R)"
                    self.log_event("EV_GATE_BLOCK", f"Conservative blocked by TimeMachine EV Gate: {mc_odds.verdict}", "info")
                else:
                    qty = self.comp_b.compute_r_multiple_qty(price, sl, self.broker)
                    if qty > Decimal("0"):
                        fill = self.broker.submit_order(OrderTicket(
                            portfolio_id="comp_cons", symbol="ETH/USD", side=OrderSide.BUY,
                            order_type=OrderType.MARKET, qty=qty, stop_loss=sl, take_profit=tp, timestamp=ts
                        ))
                        if fill:
                            self.position_entry_ts["comp_cons"] = ts
                            self.log_event("SCALP_BUY", f"Conservative scalped {fill.qty} ETH @ ${fill.price:,.2f} (TP ${tp:,.2f} | EV {mc_odds.expected_r:+.2f}R)", "buy")
        else:
            entry_p = p_cons.avg_entry_price
            if entry_p > Decimal("0"):
                gain_usd = price - entry_p
                gain_pct = (gain_usd / entry_p) * Decimal("100")
                if gain_pct >= Decimal("0.15") or (price >= self.live_ema_fast and gain_usd >= Decimal("1.50")):
                    fill = self.broker.submit_order(OrderTicket(
                        portfolio_id="comp_cons", symbol="ETH/USD", side=OrderSide.SELL,
                        order_type=OrderType.MARKET, qty=p_cons.position_qty,
                        reason=ExecutionReason.TAKE_PROFIT, timestamp=ts
                    ))
                    if fill:
                        self.strategy_cooldown["comp_cons"] = ts + 60.0
                        self.position_entry_ts.pop("comp_cons", None)
                        self.log_event("SCALP_TP", f"Conservative locked profit {fill.qty} ETH @ ${fill.price:,.2f} (+${fill.realized_pnl:+.2f})", "profit")

        # --- 3. ATR Volatility Adaptive (comp_atr) ---
        p_atr = self.comp_c.portfolio
        g_atr = self.comp_c.genome
        if p_atr.position_qty == Decimal("0"):
            can_enter = ts >= self.strategy_cooldown.get("comp_atr", 0.0)
            if can_enter and ((price >= self.live_ema_fast and vel > Decimal("0")) or self.live_rsi < Decimal("42")):
                stop_dist = max(Decimal("1.80"), (self.live_atr * g_atr.atr_stop_mult).quantize(Decimal("0.01")))
                target_dist = max(Decimal("2.60"), (self.live_atr * g_atr.atr_target_mult).quantize(Decimal("0.01")))
                sl = (price - stop_dist).quantize(Decimal("0.01"))
                tp = (price + target_dist).quantize(Decimal("0.01"))
                mc_odds = self.mc_evaluator.evaluate_bracket(price, sl, tp, atr=self.live_atr, recent_candles=self.candles)
                self.strategy_telemetry["comp_atr"]["mc_stats"] = mc_odds.to_dict()
                if not mc_odds.passed:
                    self.strategy_cooldown["comp_atr"] = ts + 20.0
                    self.strategy_telemetry["comp_atr"]["intent"] = f"EV Gate Blocked: Win {mc_odds.target_prob*100:.0f}% (EV {mc_odds.expected_r:+.2f}R)"
                    self.log_event("EV_GATE_BLOCK", f"ATR Dynamic blocked by TimeMachine EV Gate: {mc_odds.verdict}", "info")
                else:
                    risk_budget = p_atr.total_equity * g_atr.atr_risk_pct
                    qty = self.comp_c.compute_r_multiple_qty(price, sl, self.broker, risk_budget=risk_budget)
                    if qty > Decimal("0"):
                        fill = self.broker.submit_order(OrderTicket(
                            portfolio_id="comp_atr", symbol="ETH/USD", side=OrderSide.BUY,
                            order_type=OrderType.MARKET, qty=qty, stop_loss=sl, take_profit=tp, timestamp=ts
                        ))
                        if fill:
                            self.position_entry_ts["comp_atr"] = ts
                            self.log_event("ATR_ADAPT_BUY", f"ATR Dynamic sized {fill.qty} ETH @ ${fill.price:,.2f} (ATR=${self.live_atr} | EV {mc_odds.expected_r:+.2f}R)", "buy")
        else:
            entry_p = p_atr.avg_entry_price
            if entry_p > Decimal("0"):
                gain_usd = price - entry_p
                target_threshold = max(Decimal("2.20"), self.live_atr * Decimal("1.4"))
                if gain_usd >= target_threshold:
                    fill = self.broker.submit_order(OrderTicket(
                        portfolio_id="comp_atr", symbol="ETH/USD", side=OrderSide.SELL,
                        order_type=OrderType.MARKET, qty=p_atr.position_qty,
                        reason=ExecutionReason.TAKE_PROFIT, timestamp=ts
                    ))
                    if fill:
                        self.strategy_cooldown["comp_atr"] = ts + 60.0
                        self.position_entry_ts.pop("comp_atr", None)
                        self.log_event("ATR_TP", f"ATR Dynamic locked target {fill.qty} ETH @ ${fill.price:,.2f} (+${fill.realized_pnl:+.2f})", "profit")

        # --- 4. Trailing Profit Ratchet Guard (comp_trail) ---
        p_trail = self.comp_d.portfolio
        g_trail = self.comp_d.genome
        if p_trail.position_qty > Decimal("0"):
            if price > self.comp_d.highest_price_since_entry:
                self.comp_d.highest_price_since_entry = price
            entry_p = p_trail.avg_entry_price
            if entry_p > Decimal("0"):
                gain_pct = ((self.comp_d.highest_price_since_entry - entry_p) / entry_p) * Decimal("100")
                # Live micro-ratchet: activate trailing stop once gain >= +0.12%
                if gain_pct >= Decimal("0.12"):
                    self.comp_d.trailing_active = True
                    new_sl = (self.comp_d.highest_price_since_entry * Decimal("0.9985")).quantize(Decimal("0.01"))
                    curr_stop = self.broker.active_stops.get("comp_trail")
                    if curr_stop and (curr_stop.price is None or new_sl > curr_stop.price):
                        self.broker.active_stops["comp_trail"] = OrderTicket(
                            portfolio_id="comp_trail", symbol="ETH/USD", side=OrderSide.SELL,
                            order_type=OrderType.STOP_MARKET, qty=p_trail.position_qty,
                            price=new_sl, reason=ExecutionReason.TRAILING_STOP, timestamp=ts
                        )
                        self.log_event("TRAIL_RATCHET", f"Trailing Guard raised stop -> ${new_sl:,.2f} (Peak ${self.comp_d.highest_price_since_entry:,.2f})", "info")
        else:
            can_enter = ts >= self.strategy_cooldown.get("comp_trail", 0.0)
            if can_enter and vel >= Decimal("0") and self.live_rsi < Decimal("66"):
                sl = (price * Decimal("0.991")).quantize(Decimal("0.01"))  # 0.9% initial guard
                mc_odds = self.mc_evaluator.evaluate_bracket(price, sl, None, atr=self.live_atr, recent_candles=self.candles)
                self.strategy_telemetry["comp_trail"]["mc_stats"] = mc_odds.to_dict()
                if not mc_odds.passed:
                    self.strategy_cooldown["comp_trail"] = ts + 20.0
                    self.strategy_telemetry["comp_trail"]["intent"] = f"EV Gate Blocked: Win {mc_odds.target_prob*100:.0f}% (EV {mc_odds.expected_r:+.2f}R)"
                    self.log_event("EV_GATE_BLOCK", f"Trailing Guard blocked by TimeMachine EV Gate: {mc_odds.verdict}", "info")
                else:
                    qty = self.comp_d.compute_r_multiple_qty(price, sl, self.broker)
                    if qty > Decimal("0"):
                        self.comp_d.highest_price_since_entry = price
                        self.comp_d.trailing_active = False
                        fill = self.broker.submit_order(OrderTicket(
                            portfolio_id="comp_trail", symbol="ETH/USD", side=OrderSide.BUY,
                            order_type=OrderType.MARKET, qty=qty, stop_loss=sl, take_profit=None, timestamp=ts
                        ))
                        if fill:
                            self.position_entry_ts["comp_trail"] = ts
                            self.log_event("TRAIL_ENTRY", f"Trailing Guard entered {fill.qty} ETH @ ${fill.price:,.2f} (Init SL ${sl:,.2f} | EV {mc_odds.expected_r:+.2f}R)", "buy")

        # --- 5. Opening Range Breakout (comp_orb) ---
        p_orb = self.comp_e.portfolio
        g_orb = self.comp_e.genome
        orb_high = self.live_orb_high if self.live_orb_high > Decimal("0") else (price * Decimal("1.002"))
        orb_low = self.live_orb_low if self.live_orb_low > Decimal("0") else (price * Decimal("0.998"))
        orb_mid = ((orb_high + orb_low) / Decimal("2")).quantize(Decimal("0.01"))

        if p_orb.position_qty == Decimal("0"):
            can_enter = ts >= self.strategy_cooldown.get("comp_orb", 0.0)
            is_breakout = (price >= orb_high and vel >= Decimal("0")) or (price > orb_mid and is_uptrend and vel > self.live_atr * Decimal("0.2"))
            if can_enter and is_breakout and self.live_rsi < Decimal("72"):
                sl = max(orb_mid, (price - max(Decimal("2.50"), self.live_atr * Decimal("1.2"))).quantize(Decimal("0.01")))
                if sl >= price:
                    sl = (price * Decimal("0.992")).quantize(Decimal("0.01"))
                r_dist = price - sl
                tp = (price + r_dist * Decimal("2.0")).quantize(Decimal("0.01"))
                mc_odds = self.mc_evaluator.evaluate_bracket(price, sl, tp, atr=self.live_atr, recent_candles=self.candles)
                self.strategy_telemetry["comp_orb"]["mc_stats"] = mc_odds.to_dict()
                if not mc_odds.passed:
                    self.strategy_cooldown["comp_orb"] = ts + 20.0
                    self.strategy_telemetry["comp_orb"]["intent"] = f"EV Gate Blocked: Win {mc_odds.target_prob*100:.0f}% (EV {mc_odds.expected_r:+.2f}R)"
                    self.log_event("EV_GATE_BLOCK", f"ORB blocked by TimeMachine EV Gate: {mc_odds.verdict}", "info")
                else:
                    qty = self.comp_e.compute_r_multiple_qty(price, sl, self.broker)
                    if qty > Decimal("0"):
                        fill = self.broker.submit_order(OrderTicket(
                            portfolio_id="comp_orb", symbol="ETH/USD", side=OrderSide.BUY,
                            order_type=OrderType.MARKET, qty=qty, stop_loss=sl, take_profit=tp, timestamp=ts
                        ))
                        if fill:
                            self.position_entry_ts["comp_orb"] = ts
                            self.log_event("ORB_BREAKOUT", f"ORB entered {fill.qty} ETH @ ${fill.price:,.2f} (SL ${sl:,.2f} | TP ${tp:,.2f})", "buy")
            if p_orb.position_qty == Decimal("0") and not self.strategy_telemetry["comp_orb"]["intent"].startswith("EV Gate"):
                self.strategy_telemetry["comp_orb"]["intent"] = f"Watching ORB High ${orb_high:,.2f} (Mid ${orb_mid:,.2f})"
        else:
            entry_p = p_orb.avg_entry_price
            if entry_p > Decimal("0"):
                gain_usd = price - entry_p
                gain_pct = (gain_usd / entry_p) * Decimal("100")
                if gain_pct >= Decimal("0.35") or (price < orb_mid and gain_usd >= Decimal("1.50")):
                    fill = self.broker.submit_order(OrderTicket(
                        portfolio_id="comp_orb", symbol="ETH/USD", side=OrderSide.SELL,
                        order_type=OrderType.MARKET, qty=p_orb.position_qty,
                        reason=ExecutionReason.TAKE_PROFIT, timestamp=ts
                    ))
                    if fill:
                        self.strategy_cooldown["comp_orb"] = ts + 60.0
                        self.position_entry_ts.pop("comp_orb", None)
                        self.log_event("ORB_TP", f"ORB locked target {fill.qty} ETH @ ${fill.price:,.2f} (+${fill.realized_pnl:+.2f})", "profit")

        # --- 6. Institutional VWAP Pullback (comp_vwap) ---
        p_vwap = self.comp_f.portfolio
        g_vwap = self.comp_f.genome
        vwap_ref = self.live_vwap if self.live_vwap > Decimal("0") else (self.live_ema_slow if self.live_ema_slow > Decimal("0") else price)

        if p_vwap.position_qty == Decimal("0"):
            can_enter = ts >= self.strategy_cooldown.get("comp_vwap", 0.0)
            near_vwap = abs(price - vwap_ref) <= (self.live_atr * Decimal("0.85"))
            is_rebound = vel >= Decimal("0") and self.live_rsi >= Decimal("42")
            if can_enter and near_vwap and is_rebound:
                sl = (vwap_ref - max(Decimal("1.80"), self.live_atr * Decimal("0.6"))).quantize(Decimal("0.01"))
                if sl >= price:
                    sl = (price * Decimal("0.993")).quantize(Decimal("0.01"))
                r_dist = price - sl
                tp = (price + r_dist * Decimal("2.2")).quantize(Decimal("0.01"))
                mc_odds = self.mc_evaluator.evaluate_bracket(price, sl, tp, atr=self.live_atr, recent_candles=self.candles)
                self.strategy_telemetry["comp_vwap"]["mc_stats"] = mc_odds.to_dict()
                if not mc_odds.passed:
                    self.strategy_cooldown["comp_vwap"] = ts + 20.0
                    self.strategy_telemetry["comp_vwap"]["intent"] = f"EV Gate Blocked: Win {mc_odds.target_prob*100:.0f}% (EV {mc_odds.expected_r:+.2f}R)"
                    self.log_event("EV_GATE_BLOCK", f"VWAP blocked by TimeMachine EV Gate: {mc_odds.verdict}", "info")
                else:
                    qty = self.comp_f.compute_r_multiple_qty(price, sl, self.broker)
                    if qty > Decimal("0"):
                        fill = self.broker.submit_order(OrderTicket(
                            portfolio_id="comp_vwap", symbol="ETH/USD", side=OrderSide.BUY,
                            order_type=OrderType.MARKET, qty=qty, stop_loss=sl, take_profit=tp, timestamp=ts
                        ))
                        if fill:
                            self.position_entry_ts["comp_vwap"] = ts
                            self.log_event("VWAP_BUY", f"VWAP entered {fill.qty} ETH @ ${fill.price:,.2f} (VWAP ${vwap_ref:,.2f} | EV {mc_odds.expected_r:+.2f}R)", "buy")
            if p_vwap.position_qty == Decimal("0") and not self.strategy_telemetry["comp_vwap"]["intent"].startswith("EV Gate"):
                self.strategy_telemetry["comp_vwap"]["intent"] = f"Awaiting VWAP pullback near ${vwap_ref:,.2f}"
        else:
            entry_p = p_vwap.avg_entry_price
            if entry_p > Decimal("0"):
                gain_usd = price - entry_p
                gain_pct = (gain_usd / entry_p) * Decimal("100")
                if gain_pct >= Decimal("0.30") or (price >= (vwap_ref + self.live_atr * Decimal("1.5")) and gain_usd >= Decimal("1.80")):
                    fill = self.broker.submit_order(OrderTicket(
                        portfolio_id="comp_vwap", symbol="ETH/USD", side=OrderSide.SELL,
                        order_type=OrderType.MARKET, qty=p_vwap.position_qty,
                        reason=ExecutionReason.TAKE_PROFIT, timestamp=ts
                    ))
                    if fill:
                        self.strategy_cooldown["comp_vwap"] = ts + 60.0
                        self.position_entry_ts.pop("comp_vwap", None)
                        self.log_event("VWAP_TP", f"VWAP locked profit {fill.qty} ETH @ ${fill.price:,.2f} (+${fill.realized_pnl:+.2f})", "profit")

        self._update_telemetry_snapshot(price)

    def _ensure_active_live_positions(self, price: Decimal, ts: float) -> None:
        """
        Ensures that on startup in Live Mode, any flat competitor deploys its initial strategy
        bracket at the current live market price so the user immediately sees all 4 distinct
        risk profiles operating simultaneously in real time.
        Uses TimeMachine EV Gate and Dynamic R-Multiple position sizing.
        """
        if price <= Decimal("0"):
            return

        # 1. Aggressive
        if self.comp_a.portfolio.position_qty == Decimal("0"):
            sl = (price * (Decimal("1") - self.comp_a.genome.stop_loss_pct)).quantize(Decimal("0.01"))
            tp = (price * (Decimal("1") + self.comp_a.genome.take_profit_pct)).quantize(Decimal("0.01")) if self.comp_a.genome.take_profit_pct else None
            mc_odds = self.mc_evaluator.evaluate_bracket(price, sl, tp, atr=self.live_atr, recent_candles=self.candles)
            self.strategy_telemetry["comp_agg"]["mc_stats"] = mc_odds.to_dict()
            if not mc_odds.passed:
                self.strategy_cooldown["comp_agg"] = ts + 20.0
                self.strategy_telemetry["comp_agg"]["intent"] = f"EV Gate Blocked: Win {mc_odds.target_prob*100:.0f}% (EV {mc_odds.expected_r:+.2f}R)"
                self.log_event("EV_GATE_BLOCK", f"Aggressive blocked on startup by TimeMachine EV Gate: {mc_odds.verdict}", "info")
            else:
                qty = self.comp_a.compute_r_multiple_qty(price, sl, self.broker)
                if qty > Decimal("0"):
                    fill = self.broker.submit_order(OrderTicket("comp_agg", "ETH/USD", OrderSide.BUY, OrderType.MARKET, qty, stop_loss=sl, take_profit=tp, timestamp=ts))
                    if fill:
                        self.position_entry_ts["comp_agg"] = ts

        # 2. Conservative
        if self.comp_b.portfolio.position_qty == Decimal("0"):
            sl = (price * Decimal("0.994")).quantize(Decimal("0.01"))
            tp = (price * Decimal("1.009")).quantize(Decimal("0.01"))
            mc_odds = self.mc_evaluator.evaluate_bracket(price, sl, tp, atr=self.live_atr, recent_candles=self.candles)
            self.strategy_telemetry["comp_cons"]["mc_stats"] = mc_odds.to_dict()
            if not mc_odds.passed:
                self.strategy_cooldown["comp_cons"] = ts + 20.0
                self.strategy_telemetry["comp_cons"]["intent"] = f"EV Gate Blocked: Win {mc_odds.target_prob*100:.0f}% (EV {mc_odds.expected_r:+.2f}R)"
                self.log_event("EV_GATE_BLOCK", f"Conservative blocked on startup by TimeMachine EV Gate: {mc_odds.verdict}", "info")
            else:
                qty = self.comp_b.compute_r_multiple_qty(price, sl, self.broker)
                if qty > Decimal("0"):
                    fill = self.broker.submit_order(OrderTicket("comp_cons", "ETH/USD", OrderSide.BUY, OrderType.MARKET, qty, stop_loss=sl, take_profit=tp, timestamp=ts))
                    if fill:
                        self.position_entry_ts["comp_cons"] = ts

        # 3. ATR Dynamic
        if self.comp_c.portfolio.position_qty == Decimal("0"):
            stop_dist = max(Decimal("1.80"), (self.live_atr * self.comp_c.genome.atr_stop_mult).quantize(Decimal("0.01")))
            target_dist = max(Decimal("2.60"), (self.live_atr * self.comp_c.genome.atr_target_mult).quantize(Decimal("0.01")))
            sl = (price - stop_dist).quantize(Decimal("0.01"))
            tp = (price + target_dist).quantize(Decimal("0.01"))
            mc_odds = self.mc_evaluator.evaluate_bracket(price, sl, tp, atr=self.live_atr, recent_candles=self.candles)
            self.strategy_telemetry["comp_atr"]["mc_stats"] = mc_odds.to_dict()
            if not mc_odds.passed:
                self.strategy_cooldown["comp_atr"] = ts + 20.0
                self.strategy_telemetry["comp_atr"]["intent"] = f"EV Gate Blocked: Win {mc_odds.target_prob*100:.0f}% (EV {mc_odds.expected_r:+.2f}R)"
                self.log_event("EV_GATE_BLOCK", f"ATR Dynamic blocked on startup by TimeMachine EV Gate: {mc_odds.verdict}", "info")
            else:
                risk_budget = self.comp_c.portfolio.total_equity * self.comp_c.genome.atr_risk_pct
                qty = self.comp_c.compute_r_multiple_qty(price, sl, self.broker, risk_budget=risk_budget)
                if qty > Decimal("0"):
                    fill = self.broker.submit_order(OrderTicket("comp_atr", "ETH/USD", OrderSide.BUY, OrderType.MARKET, qty, stop_loss=sl, take_profit=tp, timestamp=ts))
                    if fill:
                        self.position_entry_ts["comp_atr"] = ts

        # 4. Trailing Guard
        if self.comp_d.portfolio.position_qty == Decimal("0"):
            sl = (price * Decimal("0.991")).quantize(Decimal("0.01"))
            mc_odds = self.mc_evaluator.evaluate_bracket(price, sl, None, atr=self.live_atr, recent_candles=self.candles)
            self.strategy_telemetry["comp_trail"]["mc_stats"] = mc_odds.to_dict()
            if not mc_odds.passed:
                self.strategy_cooldown["comp_trail"] = ts + 20.0
                self.strategy_telemetry["comp_trail"]["intent"] = f"EV Gate Blocked: Win {mc_odds.target_prob*100:.0f}% (EV {mc_odds.expected_r:+.2f}R)"
                self.log_event("EV_GATE_BLOCK", f"Trailing Guard blocked on startup by TimeMachine EV Gate: {mc_odds.verdict}", "info")
            else:
                qty = self.comp_d.compute_r_multiple_qty(price, sl, self.broker)
                if qty > Decimal("0"):
                    self.comp_d.highest_price_since_entry = price
                    fill = self.broker.submit_order(OrderTicket("comp_trail", "ETH/USD", OrderSide.BUY, OrderType.MARKET, qty, stop_loss=sl, take_profit=None, timestamp=ts))
                    if fill:
                        self.position_entry_ts["comp_trail"] = ts

        # 5. ORB Breakout
        if self.comp_e.portfolio.position_qty == Decimal("0"):
            sl = (price * Decimal("0.992")).quantize(Decimal("0.01"))
            tp = (price + (price - sl) * Decimal("2.0")).quantize(Decimal("0.01"))
            mc_odds = self.mc_evaluator.evaluate_bracket(price, sl, tp, atr=self.live_atr, recent_candles=self.candles)
            self.strategy_telemetry["comp_orb"]["mc_stats"] = mc_odds.to_dict()
            if not mc_odds.passed:
                self.strategy_cooldown["comp_orb"] = ts + 20.0
                self.strategy_telemetry["comp_orb"]["intent"] = f"EV Gate Blocked: Win {mc_odds.target_prob*100:.0f}% (EV {mc_odds.expected_r:+.2f}R)"
                self.log_event("EV_GATE_BLOCK", f"ORB Breakout blocked on startup by TimeMachine EV Gate: {mc_odds.verdict}", "info")
            else:
                qty = self.comp_e.compute_r_multiple_qty(price, sl, self.broker)
                if qty > Decimal("0"):
                    fill = self.broker.submit_order(OrderTicket("comp_orb", "ETH/USD", OrderSide.BUY, OrderType.MARKET, qty, stop_loss=sl, take_profit=tp, timestamp=ts))
                    if fill:
                        self.position_entry_ts["comp_orb"] = ts

        # 6. VWAP Pullback
        if self.comp_f.portfolio.position_qty == Decimal("0"):
            sl = (price * Decimal("0.993")).quantize(Decimal("0.01"))
            tp = (price + (price - sl) * Decimal("2.2")).quantize(Decimal("0.01"))
            mc_odds = self.mc_evaluator.evaluate_bracket(price, sl, tp, atr=self.live_atr, recent_candles=self.candles)
            self.strategy_telemetry["comp_vwap"]["mc_stats"] = mc_odds.to_dict()
            if not mc_odds.passed:
                self.strategy_cooldown["comp_vwap"] = ts + 20.0
                self.strategy_telemetry["comp_vwap"]["intent"] = f"EV Gate Blocked: Win {mc_odds.target_prob*100:.0f}% (EV {mc_odds.expected_r:+.2f}R)"
                self.log_event("EV_GATE_BLOCK", f"VWAP Pullback blocked on startup by TimeMachine EV Gate: {mc_odds.verdict}", "info")
            else:
                qty = self.comp_f.compute_r_multiple_qty(price, sl, self.broker)
                if qty > Decimal("0"):
                    fill = self.broker.submit_order(OrderTicket("comp_vwap", "ETH/USD", OrderSide.BUY, OrderType.MARKET, qty, stop_loss=sl, take_profit=tp, timestamp=ts))
                    if fill:
                        self.position_entry_ts["comp_vwap"] = ts

        self._update_telemetry_snapshot(price)

    def _update_telemetry_snapshot(self, price: Decimal) -> None:
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
                upnl = p.unrealized_pnl
                upnl_pct = ((price - p.avg_entry_price) / p.avg_entry_price * Decimal("100")) if p.avg_entry_price > 0 else Decimal("0")
                if pid == "comp_agg":
                    intent = f"LONG {p.position_qty} ETH @ ${p.avg_entry_price:,.2f} | Uncapped Trend Run ({upnl_pct:+.2f}%)"
                elif pid == "comp_cons":
                    intent = f"SCALP LONG {p.position_qty} ETH @ ${p.avg_entry_price:,.2f} | Target ${tp_p:,.2f}" if tp_p else f"LONG {p.position_qty} ETH"
                elif pid == "comp_atr":
                    intent = f"ATR-SCALED {p.position_qty} ETH @ ${p.avg_entry_price:,.2f} | 1.5x/2.5x ATR Bracket"
                elif pid == "comp_orb":
                    intent = f"ORB BREAKOUT {p.position_qty} ETH @ ${p.avg_entry_price:,.2f} | 2.0R Target ${tp_p:,.2f}" if tp_p else f"LONG {p.position_qty} ETH"
                elif pid == "comp_vwap":
                    intent = f"VWAP PULLBACK {p.position_qty} ETH @ ${p.avg_entry_price:,.2f} | 2.2R Target ${tp_p:,.2f}" if tp_p else f"LONG {p.position_qty} ETH"
                else:
                    peak = self.comp_d.highest_price_since_entry
                    intent = f"TRAILING {p.position_qty} ETH | Peak ${peak:,.2f} | Ratchet SL ${sl_p:,.2f}" if sl_p else f"LONG {p.position_qty} ETH"
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

    def _update_candle(
        self,
        ts: float,
        close: Decimal,
        high: Optional[Decimal] = None,
        low: Optional[Decimal] = None,
        open_: Optional[Decimal] = None,
    ) -> None:
        """Aggregates a bar or tick into the 1-minute candle it belongs to."""
        minute = float(int(ts // 60) * 60)
        c = float(close)
        h = float(high) if high is not None else c
        lo = float(low) if low is not None else c
        if self.candles and self.candles[-1]["t"] == minute:
            cur = self.candles[-1]
            cur["h"] = max(cur["h"], h)
            cur["l"] = min(cur["l"], lo)
            cur["c"] = c
        elif not self.candles or minute > self.candles[-1]["t"]:
            o = float(open_) if open_ is not None else (self.candles[-1]["c"] if self.candles else c)
            self.candles.append({"t": minute, "o": o, "h": max(h, o), "l": min(lo, o), "c": c})
            if len(self.candles) > self.max_candles:
                self.candles = self.candles[-self.max_candles:]

    def _recompute_candle_indicators(self, period: int = 14) -> None:
        """Wilder RSI(14) and ATR(14) on 1-minute candles, so live indicators keep moving."""
        cs = self.candles
        if len(cs) < period + 1:
            return
        closes = [x["c"] for x in cs]
        avg_g = sum(max(0.0, closes[i] - closes[i - 1]) for i in range(1, period + 1)) / period
        avg_l = sum(max(0.0, closes[i - 1] - closes[i]) for i in range(1, period + 1)) / period
        for i in range(period + 1, len(closes)):
            d = closes[i] - closes[i - 1]
            avg_g = (avg_g * (period - 1) + max(0.0, d)) / period
            avg_l = (avg_l * (period - 1) + max(0.0, -d)) / period
        if avg_l == 0 and avg_g == 0:
            rsi = 50.0
        elif avg_l == 0:
            rsi = 100.0
        elif avg_g == 0:
            rsi = 0.0
        else:
            rs = avg_g / avg_l
            rsi = 100.0 - (100.0 / (1.0 + rs))

        trs = [
            max(cs[i]["h"] - cs[i]["l"], abs(cs[i]["h"] - cs[i - 1]["c"]), abs(cs[i]["l"] - cs[i - 1]["c"]))
            for i in range(1, len(cs))
        ]
        atr = sum(trs[:period]) / period
        for tr in trs[period:]:
            atr = (atr * (period - 1) + tr) / period

        self.live_rsi = Decimal(str(round(rsi, 2)))
        self.live_atr = max(Decimal("1.50"), Decimal(str(round(atr, 2))))

        if len(cs) >= 15:
            first_15 = cs[:15]
            self.live_orb_high = Decimal(str(round(max(x["h"] for x in first_15), 2)))
            self.live_orb_low = Decimal(str(round(min(x["l"] for x in first_15), 2)))
        elif cs:
            self.live_orb_high = Decimal(str(round(max(x["h"] for x in cs), 2)))
            self.live_orb_low = Decimal(str(round(min(x["l"] for x in cs), 2)))

        if cs:
            cum_p = sum((x["h"] + x["l"] + x["c"]) / 3.0 for x in cs)
            self.live_vwap = Decimal(str(round(cum_p / len(cs), 2)))

    def _record_series_point(self, price: Decimal, ts: float) -> None:
        self._harvest_fills()
        t_label = time.strftime("%H:%M:%S", time.localtime(ts))
        self.tick_timestamps.append(t_label)
        self.eth_price_series.append(float(price))
        self.ema_fast_series.append(float(self.live_ema_fast))
        self.ema_slow_series.append(float(self.live_ema_slow))

        # Keep rolling window of 180 tick points for the raw tick series
        max_pts = 180
        if len(self.tick_timestamps) > max_pts:
            self.tick_timestamps = self.tick_timestamps[-max_pts:]
            self.eth_price_series = self.eth_price_series[-max_pts:]
            self.ema_fast_series = self.ema_fast_series[-max_pts:]
            self.ema_slow_series = self.ema_slow_series[-max_pts:]

        # Equity curve: longer window so a whole generation (1 hour) stays visible
        self.equity_ts.append(float(ts))
        for c in self.competitors:
            self.equity_series[c.portfolio_id].append(float(c.portfolio.total_equity))
        if len(self.equity_ts) > self.max_equity_pts:
            self.equity_ts = self.equity_ts[-self.max_equity_pts:]
            for pid in self.equity_series:
                self.equity_series[pid] = self.equity_series[pid][-self.max_equity_pts:]

    def start_live_loop(self, interval_sec: float = 1.5) -> None:
        if self.running:
            return
        self.interval_sec = max(0.5, float(interval_sec))
        self.running = True
        self.worker_thread = threading.Thread(target=self._live_loop, daemon=True)
        self.worker_thread.start()

    def stop_live_loop(self) -> None:
        self.running = False
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=3.0)
        self.worker_thread = None

    def stop(self) -> None:
        self.stop_live_loop()

    def _live_loop(self) -> None:
        self.log_event("BOOT", "Connecting to real-time ETH/USD orderflow & warming 1m indicators...", "info")
        self.bootstrap_intraday_session()
        with self.lock:
            self.live_start_ts = time.time()
            self.last_evolve_ts = time.time()  # the hourly countdown starts when live trading starts

        while self.running:
            if self.paused:
                time.sleep(0.25)
                continue
            try:
                quote = self.fetch_realtime_eth_quote()
                with self.lock:
                    prev_p = self.latest_quote.price if self.latest_quote else quote.price
                    self.latest_quote = quote
                    self.tick_count += 1

                    # Live 1-minute candle + RSI(14)/ATR(14) refresh on every tick
                    self._update_candle(quote.timestamp, quote.price)
                    self._recompute_candle_indicators()

                    # Update live exponential moving averages & micro-RSI on each real-time tick
                    alpha_f = Decimal("0.15")
                    alpha_s = Decimal("0.04")
                    if self.live_ema_fast <= Decimal("0"):
                        self.live_ema_fast = quote.price
                        self.live_ema_slow = quote.price
                    else:
                        self.live_ema_fast = ((quote.price * alpha_f) + (self.live_ema_fast * (Decimal("1") - alpha_f))).quantize(Decimal("0.01"))
                        self.live_ema_slow = ((quote.price * alpha_s) + (self.live_ema_slow * (Decimal("1") - alpha_s))).quantize(Decimal("0.01"))

                    fills = self.broker.on_tick(
                        price=quote.price,
                        high=max(quote.price, quote.ask),
                        low=min(quote.price, quote.bid),
                        timestamp=quote.timestamp,
                        open_price=prev_p
                    )
                    for f in fills:
                        if f.side == OrderSide.SELL:
                            self.strategy_cooldown[f.portfolio_id] = quote.timestamp + 60.0
                            self.position_entry_ts.pop(f.portfolio_id, None)
                        pnl_str = f" (PnL: ${f.realized_pnl:+.2f})" if f.side == OrderSide.SELL else ""
                        self.log_event(
                            f.reason.value,
                            f"{f.portfolio_id.upper()} {f.side.value} {f.qty} ETH @ ${f.price:,.2f}{pnl_str}",
                            "profit" if f.realized_pnl >= Decimal("0") else "loss"
                        )

                    # Ensure active initial positions if bootstrap was empty and all strategies are flat
                    if not self.position_entry_ts and all(c.portfolio.position_qty == Decimal("0") for c in self.competitors):
                        self._ensure_active_live_positions(quote.price, quote.timestamp)

                    self._evaluate_live_strategies(quote.price, prev_p, quote.timestamp)
                    self._record_series_point(quote.price, quote.timestamp)

                if self._auto_evolve_due():
                    self.evolve_now(trigger="auto")

            except Exception as e:
                self.log_event("FEED_WARN", f"Retrying live quote stream: {e}", "loss")

            time.sleep(self.interval_sec)

    def _auto_evolve_due(self, now: Optional[float] = None) -> bool:
        now = time.time() if now is None else now
        return (
            self.auto_evolve_enabled
            and self.latest_quote is not None
            and now - self.last_evolve_ts >= self.auto_evolve_interval_sec
        )

    def toggle_auto_evolve(self) -> bool:
        with self.lock:
            self.auto_evolve_enabled = not self.auto_evolve_enabled
            hours = self.auto_evolve_interval_sec / 3600.0
            hrs_text = f"{hours:g}h" if hours >= 1 else f"{self.auto_evolve_interval_sec // 60}m"
            status_text = f"Enabled (Every {hrs_text})" if self.auto_evolve_enabled else "Disabled (Manual only)"
            self.log_event("CONFIG", f"Auto Evolution: {status_text}", "info")
            return self.auto_evolve_enabled

    def set_auto_evolve_interval(self, seconds: int) -> int:
        with self.lock:
            self.auto_evolve_interval_sec = max(60, int(seconds))
            hours = self.auto_evolve_interval_sec / 3600.0
            hrs_text = f"{hours:g}h" if hours >= 1 else f"{self.auto_evolve_interval_sec // 60}m"
            self.log_event("CONFIG", f"Auto Evolution Interval set to {hrs_text} ({self.auto_evolve_interval_sec}s)", "info")
            return self.auto_evolve_interval_sec

    def evolve_now(self, trigger: str = "manual") -> List[str]:
        with self.lock:
            self._harvest_fills()
            rankings = Leaderboard.get_rankings(self.broker.portfolios)
            prev_gen = max(c.genome.generation for c in self.competitors)
            short = self.STRATEGY_SHORT
            kept = [short.get(r.portfolio_id, r.portfolio_id) for r in rankings[:2]]
            rebuilt = [short.get(r.portfolio_id, r.portfolio_id) for r in rankings[2:]]
            leader_roi = float(rankings[0].roi_pct) if rankings else 0.0

            logs = GeneticEvolver.evolve_generation(self.competitors, rankings, preserve_portfolio=True)
            # Update broker position caps with evolved genomes while preserving open positions & active brackets
            for c in self.competitors:
                self.broker.competitor_caps[c.portfolio_id] = c.max_position_ratio

            now = time.time()
            self.last_evolve_ts = now
            new_gen = max(c.genome.generation for c in self.competitors)
            summary = (
                f"Preserved {', '.join(kept)}; Mutated {', '.join(rebuilt)} from Top 2"
                if rebuilt else "Genome Updated"
            )
            self.evolution_events.append({
                "ts": now,
                "time": time.strftime("%H:%M", time.localtime(now)),
                "from_gen": prev_gen,
                "to_gen": new_gen,
                "trigger": trigger,
                "leader_roi_pct": round(leader_roi, 2),
                "summary": summary,
            })
            self.evolution_events = self.evolution_events[-24:]

            # TradingView Auto-Pilot: lock the previous hour's champion strategy
            if rankings:
                top = rankings[0]
                self.tv_champion = {
                    "strategy_id": top.portfolio_id,
                    "name": self.STRATEGY_DISPLAY.get(top.portfolio_id, top.name),
                    "generation": prev_gen,
                    "roi_pct": round(float(top.roi_pct), 2),
                    "fitness": round(float(top.fitness_score), 2),
                    "status": f"Gen #{prev_gen} Champion (Win Rate {float(top.win_rate_pct):.0f}%)",
                }
                self.log_event("TV_AUTOPILOT", f"TradingView Auto-Pilot: Locked previous hour champion '{self.tv_champion['name']}'", "info")

            # OmniRoute Intelligent Strategic Post-Mortem Synthesis
            try:
                omni_report = self.omniroute.synthesize_post_mortem(
                    rankings=rankings,
                    generation=prev_gen,
                    bar_count=len(self.candles),
                    tier="fast"
                )
                if omni_report:
                    first_line = omni_report.splitlines()[0]
                    self.log_event("OMNIROUTE", f"{first_line}", "info")
            except Exception:
                pass

            for line in logs:
                self.log_event("EVOLVE", line, "evolve")
            return logs

    # High-contrast vibrant electric palette: vivid pop on ultra-deep dark #08090C
    STRATEGY_COLORS: Dict[str, str] = {
        "comp_agg": "#FF334B",    # Neon Coral (Aggressive Momentum)
        "comp_cons": "#38BDF8",   # Electric Sky Cyan (Conservative Scalper)
        "comp_atr": "#FFB800",    # Electric Amber Gold (ATR Dynamic)
        "comp_trail": "#00E676",  # Neon Emerald Green (Trailing Guard)
        "comp_orb": "#A855F7",    # Electric Violet (ORB Breakout)
        "comp_vwap": "#14F195",   # Mint Teal (Institutional VWAP)
    }
    STRATEGY_SHORT: Dict[str, str] = {
        "comp_agg": "AGG",
        "comp_cons": "CONS",
        "comp_atr": "ATR",
        "comp_trail": "TRAIL",
        "comp_orb": "ORB",
        "comp_vwap": "VWAP",
    }
    STRATEGY_DISPLAY: Dict[str, str] = {
        "comp_agg": "Aggressive Momentum",
        "comp_cons": "Conservative Scalper",
        "comp_atr": "ATR Dynamic",
        "comp_trail": "Trailing Guard",
        "comp_orb": "ORB Breakout (15m)",
        "comp_vwap": "Institutional VWAP",
    }
    REASON_DISPLAY: Dict[str, str] = {
        "SIGNAL": "Strategy Signal",
        "STOP_LOSS": "Stop Loss",
        "TAKE_PROFIT": "Take Profit",
        "TRAILING_STOP": "Trailing Stop",
        "CIRCUIT_BREAKER": "Circuit Breaker",
    }

    @staticmethod
    def _finite(val: Any, default: float = 0.0) -> float:
        """JSON-safe float (WebView JSON.parse rejects NaN / Infinity)."""
        try:
            f = float(val)
        except (TypeError, ValueError):
            return default
        return f if math.isfinite(f) else default

    def _build_view_model(self, rankings: List[Any], gen: int) -> Dict[str, Any]:
        fz = self._finite
        q = self.latest_quote
        spot = q.price if q else self.broker.current_price

        strategies: List[Dict[str, Any]] = []
        for r in rankings:
            c = next(comp for comp in self.competitors if comp.portfolio_id == r.portfolio_id)
            p = c.portfolio
            g = c.genome
            pid = r.portfolio_id
            tel = self.strategy_telemetry.get(pid, {})
            mc_st = tel.get("mc_stats", {})
            in_pos = p.position_qty > Decimal("0")
            upnl_pct = Decimal("0")
            if in_pos and p.avg_entry_price > Decimal("0") and spot > Decimal("0"):
                upnl_pct = (spot - p.avg_entry_price) / p.avg_entry_price * Decimal("100")
            tp_txt = f"{float(g.take_profit_pct) * 100:.1f}%" if g.take_profit_pct else "∞"
            stop_ord = self.broker.active_stops.get(pid)
            tp_ord = self.broker.active_targets.get(pid)
            sl_p = fz(stop_ord.price) if (in_pos and stop_ord and stop_ord.price) else None
            tp_p = fz(tp_ord.price) if (in_pos and tp_ord and tp_ord.price) else None
            # Trailing Guard has no fixed TP: show a virtual ceiling (2x current stop distance above
            # max(entry, spot)) so the bracket bar stays meaningful even after the stop ratchets above entry
            if in_pos and tp_p is None and sl_p is not None:
                entry_f = fz(p.avg_entry_price)
                ref = max(fz(spot), entry_f)
                tp_p = round(ref + 2 * max(0.5, abs(ref - sl_p)), 2)
            strategies.append({
                "id": pid,
                "rank": r.rank,
                "name": self.STRATEGY_DISPLAY.get(pid, c.base_name),
                "color": self.STRATEGY_COLORS.get(pid, "#ECF2F8"),
                "generation": g.generation,
                "genome": f"Size {float(g.position_ratio) * 100:.0f}% | SL {float(g.stop_loss_pct) * 100:.2f}% | TP {tp_txt}",
                "equity": fz(r.equity),
                "cash": fz(p.cash),
                "roi_pct": fz(r.roi_pct),
                "unrealized_pnl": fz(p.unrealized_pnl),
                "unrealized_pct": fz(upnl_pct),
                "realized_pnl": fz(p.realized_pnl),
                "in_position": in_pos,
                "qty": fz(p.position_qty),
                "entry_price": fz(p.avg_entry_price) if in_pos else None,
                "stop_loss": sl_p,
                "take_profit": tp_p,
                "win_rate_pct": fz(r.win_rate_pct),
                "closed_trades": int(r.closed_trades),
                "max_dd_pct": fz(r.max_drawdown_pct),
                "sharpe": fz(r.sharpe_ratio),
                "fitness": fz(r.fitness_score),
                "intent": tel.get("intent", ""),
                "mc_verdict": mc_st.get("verdict", "EV Gate Active"),
                "expected_r": mc_st.get("expected_r", 0.0),
                "target_prob": mc_st.get("target_prob", 0.50),
                "stop_prob": mc_st.get("stop_prob", 0.40),
                "r_multiple": mc_st.get("r_multiple", 1.8),
                "ev_passed": mc_st.get("passed", True),
            })

        fills_view: List[Dict[str, Any]] = []
        live_start = self.live_start_ts or 0.0
        for f in reversed(self.fill_records[-60:]):
            pid = f.portfolio_id
            is_live = bool(live_start > 0 and f.timestamp >= (live_start - 2.0))
            is_buy = f.side == OrderSide.BUY
            action_tag = "OPEN" if is_buy else "CLOSE"
            action_label = f"{action_tag} {f.side.value}"
            base_reason = self.REASON_DISPLAY.get(f.reason.value, f.reason.value)
            entry_p_dec = getattr(f, "entry_price", None)
            reason_detail = base_reason

            fills_view.append({
                "seq": f.fill_seq,
                "time": time.strftime("%H:%M:%S", time.localtime(f.timestamp)),
                "strategy": self.STRATEGY_DISPLAY.get(pid, pid).split(" ")[0],
                "side": f.side.value,
                "action_label": action_label,
                "is_entry": is_buy,
                "qty": fz(f.qty),
                "price": fz(f.price),
                "entry_price": fz(entry_p_dec) if entry_p_dec else None,
                "pnl": fz(f.realized_pnl) if f.side == OrderSide.SELL else None,
                "reason": reason_detail,
                "is_live": is_live,
            })

        leader = strategies[0] if strategies else None
        is_online = self.omniroute.metrics.gateway_online
        omni_source = f"OmniRoute Gateway ({self.omniroute.fast_model})" if is_online else "Local Quant Engine (0 Token Offline)"
        omni_meta = {
            "source": omni_source,
            "is_online": is_online,
            "endpoint": self.omniroute.base_url,
            "active_model": f"{self.omniroute.fast_model} (Tactical Reasoning)" if is_online else "Pure Offline Math Engine (No External API)",
            "quota_pct": self.omniroute.metrics.quota_remaining_pct,
            "tokens_used": self.omniroute.metrics.tokens_used,
            "tokens_saved": self.omniroute.metrics.tokens_saved,
        }
        omni_summary = (
            f"Leader: {leader['name']} ROI {leader['roi_pct']:+.2f}% | "
            f"RSI {fz(self.live_rsi):.1f} | ATR ${fz(self.live_atr):.2f} | "
            f"EMA {fz(self.live_ema_fast):,.2f}/{fz(self.live_ema_slow):,.2f}"
        ) if leader else "Synchronizing live orderflow..."

        now = time.time()
        elapsed_since_evolve = max(0.0, now - self.last_evolve_ts)
        next_evolve_sec = max(0.0, float(self.auto_evolve_interval_sec) - elapsed_since_evolve)

        # Champion Strategy for TradingView Auto-Pilot
        if rankings and (self.tv_champion.get("generation") == 1 or not self.tv_champion.get("strategy_id")):
            top = rankings[0]
            active_tv_champ = {
                "strategy_id": top.portfolio_id,
                "name": self.STRATEGY_DISPLAY.get(top.portfolio_id, top.name),
                "generation": gen,
                "roi_pct": fz(top.roi_pct),
                "fitness": fz(top.fitness_score),
                "win_rate_pct": fz(top.win_rate_pct),
                "closed_trades": int(top.closed_trades),
                "status": "Hourly Leader (Active Dispatch)",
            }
        else:
            active_tv_champ = self.tv_champion

        champ_id = active_tv_champ.get("strategy_id", "comp_agg")
        tv_payloads = []
        for f in reversed(self.fill_records[-60:]):
            if f.portfolio_id == champ_id:
                tv_payloads.append({
                    "time": time.strftime("%H:%M:%S", time.localtime(f.timestamp)),
                    "ticker": "ETHUSD",
                    "action": f.side.value,
                    "qty": fz(f.qty),
                    "price": fz(f.price),
                    "pnl": fz(f.realized_pnl) if f.side == OrderSide.SELL else None,
                    "status": "SIM_EXECUTED",
                })

        return {
            "paused": self.paused,
            "auto_evolve_enabled": self.auto_evolve_enabled,
            "auto_evolve_interval_sec": self.auto_evolve_interval_sec,
            "next_evolve_sec": int(next_evolve_sec),
            "evolution_events": self.evolution_events,
            "candles": [
                {
                    "t": c["t"],
                    "o": fz(c["o"]),
                    "h": fz(c["h"]),
                    "l": fz(c["l"]),
                    "c": fz(c["c"]),
                }
                for c in self.candles[-150:]
            ],
            "tv_hub": {
                "champion": active_tv_champ,
                "next_rotation_sec": int(next_evolve_sec),
                "payloads": tv_payloads[:6],
                "webhook_endpoint": "http://localhost:20128/tradingview/webhook",
                "is_connected": False,
            },
            "omni_meta": omni_meta,
            "omni_summary": omni_summary,
            "strategies": strategies,
            "fills": fills_view,
            "price_history": [fz(v) for v in self.eth_price_series],
            "ema_fast_history": [fz(v) for v in self.ema_fast_series],
            "ema_slow_history": [fz(v) for v in self.ema_slow_series],
        }

    def get_ui_state(self) -> Dict[str, Any]:
        with self.lock:
            self._harvest_fills()
            rankings = Leaderboard.get_rankings(self.broker.portfolios)
            q = self.latest_quote
            gen = max(c.genome.generation for c in self.competitors)

            state = {
                "generation": gen,
                "tick_count": self.tick_count,
                "running": self.running,
                "quote": {
                    "price": float(q.price) if q else 0.0,
                    "bid": float(q.bid) if q else 0.0,
                    "ask": float(q.ask) if q else 0.0,
                    "high_24h": float(q.high_24h) if q else 0.0,
                    "low_24h": float(q.low_24h) if q else 0.0,
                    "volume_24h": float(q.volume_24h) if q else 0.0,
                    "change_24h_pct": float(q.change_24h_pct) if q else 0.0,
                    "source": q.source if q else "Connecting...",
                    "timestamp": time.strftime("%H:%M:%S", time.localtime(q.timestamp)) if q else "",
                },
                "indicators": {
                    "ema_fast": float(self.live_ema_fast),
                    "ema_slow": float(self.live_ema_slow),
                    "vwap": float(self.live_vwap),
                    "orb_high": float(self.live_orb_high),
                    "orb_low": float(self.live_orb_low),
                    "rsi": float(self.live_rsi),
                    "atr": float(self.live_atr),
                },
                "quota": {
                    "remaining_pct": self.omniroute.metrics.quota_remaining_pct,
                    "saved_tokens": self.omniroute.metrics.tokens_saved,
                },
            }
            state.update(self._build_view_model(rankings, gen))
            return state

