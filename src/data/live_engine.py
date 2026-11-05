from __future__ import annotations
import asyncio
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Any, Optional
import logging
import math
import threading
import time
import requests

from src.arena.broker_sim import BrokerSim
from src.arena.order import OrderTicket, OrderSide, OrderType, ExecutionReason, FillEvent, PositionSide
from src.arena.leaderboard import Leaderboard
from src.arena.evolution import GeneticEvolver
from src.competitors.aggressive import AggressiveCompetitor
from src.competitors.conservative import ConservativeCompetitor
from src.competitors.atr_dynamic import ATRDynamicCompetitor
from src.competitors.trailing_guard import TrailingGuardCompetitor
from src.competitors.orb import ORBCompetitor
from src.competitors.vwap import VWAPPullbackCompetitor
from src.data.eth_feed import ETHFeed, CandleBar
from src.data.timemachine import MonteCarloOddsEvaluator
from src.intelligence.omniroute_client import OmniRouteClient
from src.intelligence.macro_commander import MacroCommander, MacroRegimeState

logger = logging.getLogger(__name__)


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
    is_offline: bool = False


class LiveArenaEngine:
    """
    Real-Time Live Multi-Strategy Paper Trading Engine for ETH/USD.
    - Streams real-time live spot quotes from Coinbase / Binance / Kraken public REST APIs every 1.5s.
    - Bootstraps with the most recent 120 minutes of 1-minute live ETH/USD bars so indicators and
      active strategy positions are immediately hot on startup.
    - Operates 6 distinct real-time strategies simultaneously on every live tick.
    """
    def __init__(self, initial_cash: Decimal = Decimal("100000.00"), symbol: str = "ETH/USD"):
        self.symbol = symbol
        self.initial_cash = initial_cash
        self.lock = threading.RLock()
        self.market_online: bool = False
        self.is_bootstrapped: bool = False
        self.live_orders_enabled: bool = False
        self.live_trading_active: bool = False
        self.running = False
        self.paused = False
        self.interval_sec: float = 1.5
        self.worker_thread: Optional[threading.Thread] = None
        # Persistent structured fill tape (survives broker re-init on evolution)
        self.fill_records: List[FillEvent] = []
        self._audit_cursor: int = 0
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "TradeBot0-LiveArena/2.0"})
        self.preferred_quote_provider: str = "binance"
        self._quote_provider_cooldown: Dict[str, float] = {}

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
        self.live_logs: List[Dict[str, str]] = []
        self.latest_quote: Optional[LiveQuote] = None
        self.tick_count: int = 0
        self.live_atr: Decimal = Decimal("85.00")
        self.live_rsi: Decimal = Decimal("50.00")
        self.live_ema_fast: Decimal = Decimal("0.00")
        self.live_ema_slow: Decimal = Decimal("0.00")
        self.live_vwap: Decimal = Decimal("0.00")
        self.live_orb_high: Decimal = Decimal("0.00")
        self.live_orb_low: Decimal = Decimal("0.00")

        # 1-minute OHLC candles (bootstrap bars + live ticks aggregated) for charting & live RSI/ATR
        self.candles: List[Dict[str, float]] = []
        self.max_candles: int = 200
        self.live_start_ts: Optional[float] = None

        # Paced Candlestick Cadence Dispatcher (emits stable slices at 5s heartbeat: :00, :05, :10, :15...)
        self.cadence_sec: float = 5.0
        self.last_cadence_ts: float = 0.0
        self.last_cadence_slot: int = 0
        self.published_candles: List[Dict[str, float]] = []
        self.published_quote: Optional[LiveQuote] = None
        self._raw_quote_cache: Optional[LiveQuote] = None
        self._slice_ticks: List[LiveQuote] = []
        self.raw_fetch_thread: Optional[threading.Thread] = None

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

        # Macro Commander & OmniRoute Intelligence Layer (Strict Veto Option A)
        self.omniroute_client = OmniRouteClient()
        self.macro_commander = MacroCommander(self.omniroute_client)

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
        self.broker = BrokerSim(symbol=self.symbol, slippage_pct=Decimal("0.0001"))
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
            "comp_agg": "Momentum Breakout (3x Lev / 70% Cap)",
            "comp_cons": "Mean-Reversion Scalper (Spot 1x / 25% Cap)",
            "comp_atr": "ATR Volatility Adaptive (2x Lev Dynamic)",
            "comp_trail": "Trailing Ratchet Guard (2x Lev / 40% Cap)",
            "comp_orb": "Opening Range Breakout (2.5x Lev / 45% Cap)",
            "comp_vwap": "Institutional VWAP Pullback (Spot 1x / 50% Cap)",
        }
        return labels.get(pid, pid)

    @staticmethod
    def _get_entry_rule_desc(pid: str) -> str:
        rules = {
            "comp_agg": "Breakout > EMA-Fast (Long) or Breakdown < EMA-Slow (Short) | Wide SL, Uncapped Run",
            "comp_cons": "RSI bounce <= 48 (Long) or RSI fade >= 58 (Short) | Tight SL & Quick Scalp TP",
            "comp_atr": "ATR volatility-scaled Long & Short channels (1.5% risk / Dynamic SL & TP)",
            "comp_trail": "Trend-following Long/Short entry + automatic breakeven & peak/trough ratchet",
            "comp_orb": "Breakout > Range High (Long) / Breakdown < Range Low (Short) | Midpoint SL & 2.0R Target",
            "comp_vwap": "Pullback test & bounce at VWAP (Long) / Rejection at VWAP (Short) | 2.2R Target",
        }
        return rules.get(pid, "")

    def log_event(self, tag: str, message: str, level: str = "info") -> None:
        with self.lock:
            ts = time.strftime("%H:%M:%S")
            self.live_logs.insert(0, {"time": ts, "tag": tag, "message": message, "level": level})
            if len(self.live_logs) > 120:
                self.live_logs.pop()

    def _fetch_binance_quote(self) -> Optional[LiveQuote]:
        try:
            r_bin = self.session.get("https://api.binance.com/api/v3/ticker/24hr?symbol=ETHUSDT", timeout=1.2)
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
                    timestamp=time.time(),
                    is_offline=False
                )
        except Exception as e:
            logger.debug("Binance quote feed error: %s", e)
        return None

    def _fetch_kraken_quote(self) -> Optional[LiveQuote]:
        try:
            r_krk = self.session.get("https://api.kraken.com/0/public/Ticker?pair=ETHUSD", timeout=1.5)
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
                        timestamp=time.time(),
                        is_offline=False
                    )
        except Exception as e:
            logger.debug("Kraken quote feed error: %s", e)
        return None

    def _fetch_coinbase_quote(self) -> Optional[LiveQuote]:
        try:
            r_tick = self.session.get("https://api.exchange.coinbase.com/products/ETH-USD/ticker", timeout=1.2)
            r_stats = self.session.get("https://api.exchange.coinbase.com/products/ETH-USD/stats", timeout=1.2)
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
                    timestamp=time.time(),
                    is_offline=False
                )
        except Exception as e:
            logger.debug("Coinbase quote feed error: %s", e)
        return None

    def fetch_realtime_crypto_quote(self) -> LiveQuote:
        """
        Fetches real-time live ETH/USD spot quote with sub-second latency across
        Binance -> Kraken -> Coinbase with adaptive provider ranking & circuit breaking.
        """
        now = time.time()
        providers = ["binance", "kraken", "coinbase"]
        if self.preferred_quote_provider in providers:
            providers.remove(self.preferred_quote_provider)
            providers.insert(0, self.preferred_quote_provider)

        active_providers = [p for p in providers if self._quote_provider_cooldown.get(p, 0.0) <= now]
        candidate_providers = active_providers if active_providers else providers

        fetchers = {
            "binance": self._fetch_binance_quote,
            "kraken": self._fetch_kraken_quote,
            "coinbase": self._fetch_coinbase_quote,
        }

        for name in candidate_providers:
            fetcher = fetchers.get(name)
            if not fetcher:
                continue
            quote = fetcher()
            if quote is not None:
                self.preferred_quote_provider = name
                self._quote_provider_cooldown.pop(name, None)
                return quote
            self._quote_provider_cooldown[name] = now + 15.0

        # In-Memory Resilient Cache Fallback (survives transient network disconnects)
        if self.latest_quote is not None and not self.latest_quote.is_offline and self.latest_quote.price > Decimal("0.00"):
            return LiveQuote(
                price=self.latest_quote.price,
                bid=self.latest_quote.bid,
                ask=self.latest_quote.ask,
                high_24h=self.latest_quote.high_24h,
                low_24h=self.latest_quote.low_24h,
                volume_24h=self.latest_quote.volume_24h,
                change_24h_pct=self.latest_quote.change_24h_pct,
                source=f"{self.latest_quote.source} (Cache)",
                timestamp=time.time(),
                is_offline=False
            )

        # Cold-boot default baseline if completely offline on first start: marked offline to safely block mock fills
        return LiveQuote(
            price=Decimal("0.00"),
            bid=Decimal("0.00"),
            ask=Decimal("0.00"),
            high_24h=Decimal("0.00"),
            low_24h=Decimal("0.00"),
            volume_24h=Decimal("0.00"),
            change_24h_pct=Decimal("0.00"),
            source="Market Offline (No Feed)",
            timestamp=time.time(),
            is_offline=True
        )

    fetch_realtime_eth_quote = fetch_realtime_crypto_quote

    @staticmethod
    def _generate_fallback_bars(anchor_price: Decimal, count: int = 120) -> List[CandleBar]:
        """
        Synthesizes a continuous, realistic sequence of 1-minute historical candles
        anchored directly to the anchor_price if external web feeds are unreachable or slow.
        Ensures the tactical K-line viewport is densely populated with zero cold-boot blankness.
        """
        import random
        bars: List[CandleBar] = []
        now = time.time()
        start_ts = now - (count * 60)
        curr = float(anchor_price) * (1.0 - random.uniform(-0.003, 0.003))
        for i in range(count):
            ts = start_ts + (i * 60)
            drift = (float(anchor_price) - curr) / max(1, count - i)
            volatility = float(anchor_price) * 0.0006
            change = drift + random.gauss(0, volatility)
            open_p = curr
            close_p = open_p + change
            high_p = max(open_p, close_p) + abs(random.gauss(0, volatility * 0.45))
            low_p = min(open_p, close_p) - abs(random.gauss(0, volatility * 0.45))
            curr = close_p
            bars.append(CandleBar(
                timestamp=ts,
                open_=Decimal(f"{open_p:.2f}"),
                high=Decimal(f"{high_p:.2f}"),
                low=Decimal(f"{low_p:.2f}"),
                close=Decimal(f"{close_p:.2f}"),
                volume=Decimal(f"{random.uniform(2.5, 30.0):.2f}"),
                ema_fast=Decimal(f"{close_p:.2f}"),
                ema_slow=Decimal(f"{close_p:.2f}"),
                rsi=Decimal("50.00"),
                atr=Decimal("12.00")
            ))
        return bars

    def bootstrap_intraday_session(self) -> None:
        """
        Loads the last 120 minutes of real 1-minute ETH/USD candles to warm up live indicators
        and immediately deploy the 6 strategies into the current live market session.
        If external feeds fail or timeout, safely falls back to synthetic realistic continuous bars
        anchored to spot price so the K-line arena is never empty.
        """
        recent_bars = []
        try:
            bars = ETHFeed.fetch_historical_bars(ticker="ETH-USD", period="1d", interval="1m")
            recent_bars = bars[-120:] if len(bars) > 120 else bars
        except Exception as e:
            logger.debug("Intraday bars fetch failed: %s", e)

        # Fallback guarantee: if external feed timed out or failed, generate realistic 120m bars
        if not recent_bars:
            anchor = self.latest_quote.price if (self.latest_quote and self.latest_quote.price > Decimal("0")) else Decimal("2650.00")
            recent_bars = self._generate_fallback_bars(anchor, count=120)

        with self.lock:
            for i, bar in enumerate(recent_bars):
                self.live_ema_fast = bar.ema_fast or bar.close
                self.live_ema_slow = bar.ema_slow or bar.close
                self.live_rsi = bar.rsi or Decimal("50.00")
                self.live_atr = max(Decimal("5.00"), bar.atr or Decimal("12.00"))

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

            # Ensure all 6 distinct strategies are primed with historical simulation
            if recent_bars:
                last_b = recent_bars[-1]
                self.log_event(
                    "WARMUP_SYNC",
                    f"Replayed 120m intraday history ({len(recent_bars)} bars). Indicators & rankings primed. Waiting for UI reveal.",
                    "info"
                )

            self.published_candles = [dict(c) for c in self.candles]
            self.published_quote = self.latest_quote
            self._raw_quote_cache = self.latest_quote
            self.last_cadence_ts = time.time()
            self.last_cadence_slot = int(self.last_cadence_ts // self.cadence_sec) * int(self.cadence_sec)
            self.is_bootstrapped = True
            try:
                self.refresh_intel_digest()
            except Exception:
                pass

    def start_live_trading(self) -> None:
        """
        Activated only after the frontend verifies that the left K-line chart and right
        tactical tables are completely rendered and the initialization screen has faded out.
        """
        with self.lock:
            if not self.live_orders_enabled:
                self.live_orders_enabled = True
                self.log_event("ARENA_REVEALED", "Arena initialization verified. Live order placement activated.", "info")

    def refresh_intel_digest(self) -> Dict[str, Any]:
        """
        Triggers an AI-driven refresh of macro intelligence, synthesizing live/curated events
        through OmniRoute. Returns updated intel hub telemetry.
        """
        try:
            loop = None
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            if loop and loop.is_running():
                asyncio.create_task(self.macro_commander.refresh_digest_async())
            else:
                asyncio.run(self.macro_commander.refresh_digest_async())
        except Exception as e:
            logger.warning("Intel digest refresh error: %s", e)
        return self.macro_commander.get_intel_hub_telemetry()

    def _try_enter_bracket(
        self,
        competitor: Any,
        price: Decimal,
        sl: Decimal,
        tp: Optional[Decimal],
        ts: float,
        event_label: str,
        side: OrderSide = OrderSide.BUY,
        risk_budget: Optional[Decimal] = None
    ) -> bool:
        pid = competitor.portfolio_id

        # Strict Veto Gate (Macro Commander Option A)
        allowed, veto_reason = self.macro_commander.check_trade_veto(side, competitor.base_name)
        if not allowed:
            self.strategy_cooldown[pid] = ts + 20.0
            self.strategy_telemetry[pid]["intent"] = f"Macro Veto: {self.macro_commander.current_state.directional_bias}"
            self.log_event("VETO_MACRO", f"{competitor.base_name.split(' ')[0]} {side.value} vetoed: {veto_reason}", "loss")
            self.macro_commander.record_strategy_action(
                pid, competitor.base_name.split(' ')[0],
                f"{side.value} Blocked by Macro Veto ({self.macro_commander.current_state.directional_bias})",
                "loss"
            )
            return False

        # Macro Trend Take-Profit Expansion (R-Multiple expanded when riding macro regime)
        if tp is not None and self.macro_commander.current_state.risk_multiplier > 1.0:
            if side == OrderSide.BUY and self.macro_commander.current_state.directional_bias == "LONG_ONLY":
                r_dist = price - sl
                tp = (price + r_dist * Decimal(str(round(2.0 * self.macro_commander.current_state.risk_multiplier, 2)))).quantize(Decimal("0.01"))
            elif side == OrderSide.SELL and self.macro_commander.current_state.directional_bias == "SHORT_ONLY":
                r_dist = sl - price
                tp = (price - r_dist * Decimal(str(round(2.0 * self.macro_commander.current_state.risk_multiplier, 2)))).quantize(Decimal("0.01"))

        mc_odds = self.mc_evaluator.evaluate_bracket(price, sl, tp, atr=self.live_atr, recent_candles=self.candles)
        self.strategy_telemetry[pid]["mc_stats"] = mc_odds.to_dict()
        if not mc_odds.passed:
            self.strategy_cooldown[pid] = ts + 20.0
            display_win = mc_odds.green_prob if mc_odds.neither_prob > 0.40 else mc_odds.decided_win_rate
            self.strategy_telemetry[pid]["intent"] = f"EV Gate Blocked: Win {display_win*100:.0f}% (EV {mc_odds.expected_r:+.2f}R)"
            self.log_event("EV_GATE_BLOCK", f"{competitor.base_name.split(' ')[0]} blocked by TimeMachine EV Gate: {mc_odds.verdict}", "info")
            return False

        qty = competitor.compute_r_multiple_qty(price, sl, self.broker, risk_budget=risk_budget)
        if qty <= Decimal("0"):
            return False

        fill = self.broker.submit_order(OrderTicket(
            portfolio_id=pid, symbol=self.symbol, side=side,
            order_type=OrderType.MARKET, qty=qty, stop_loss=sl, take_profit=tp, timestamp=ts
        ))
        if fill:
            self.position_entry_ts[pid] = ts
            tp_str = f" | TP ${tp:,.2f}" if tp else ""
            pos_label = "SHORT" if side == OrderSide.SELL else "LONG"
            event_type = "sell" if side == OrderSide.SELL else "buy"
            self.log_event(event_label, f"{competitor.base_name.split(' ')[0]} opened {pos_label} {fill.qty} ETH @ ${fill.price:,.2f} (SL ${sl:,.2f}{tp_str} | EV {mc_odds.expected_r:+.2f}R)", event_type)
            self.macro_commander.record_strategy_action(
                pid, competitor.base_name.split(' ')[0],
                f"Opened {pos_label} {fill.qty} ETH @ ${fill.price:,.2f}",
                event_type
            )
            return True
        return False

    def _evaluate_live_strategies(self, price: Decimal, prev_price: Decimal, ts: float) -> None:
        """
        Executes differentiated real-time decision logic for each of the 6 strategies on every live tick/bar.
        Incorporates bidirectional Long & Short setups, anti-churn cooldowns, channel stagnation exits,
        and dynamic volatility adaptation.
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
                is_short = p.position_side == PositionSide.SHORT
                gain_pct = ((p.avg_entry_price - price) / p.avg_entry_price * Decimal("100")) if is_short else ((price - p.avg_entry_price) / p.avg_entry_price * Decimal("100"))
                if hold_sec >= 2400.0 and abs(gain_pct) < Decimal("0.10"):
                    exit_side = OrderSide.BUY if is_short else OrderSide.SELL
                    fill = self.broker.submit_order(OrderTicket(
                        portfolio_id=pid, symbol=self.symbol, side=exit_side,
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
                self._try_enter_bracket(self.comp_a, price, sl, tp, ts, "BREAKOUT_LONG", side=OrderSide.BUY)
            elif can_enter and (((not is_uptrend) and vel < Decimal("0") and self.live_rsi > Decimal("32")) or (vel < -self.live_atr * Decimal("0.25"))):
                sl = (price * (Decimal("1") + g_agg.stop_loss_pct)).quantize(Decimal("0.01"))
                tp = (price * (Decimal("1") - g_agg.take_profit_pct)).quantize(Decimal("0.01")) if g_agg.take_profit_pct else None
                self._try_enter_bracket(self.comp_a, price, sl, tp, ts, "BREAKDOWN_SHORT", side=OrderSide.SELL)

            if p_agg.position_qty == Decimal("0") and not self.strategy_telemetry["comp_agg"]["intent"].startswith("EV Gate"):
                self.strategy_telemetry["comp_agg"]["intent"] = f"Scanning breakout / breakdown near ${self.live_ema_fast:,.2f}"
        else:
            entry_p = p_agg.avg_entry_price
            if entry_p > Decimal("0"):
                if p_agg.position_side == PositionSide.SHORT:
                    gain_usd = entry_p - price
                    gain_pct = (gain_usd / entry_p) * Decimal("100")
                    if gain_pct >= Decimal("0.25") or (self.live_ema_fast > self.live_ema_slow and self.live_rsi > Decimal("52") and gain_usd >= (self.live_atr * Decimal("0.5"))):
                        fill = self.broker.submit_order(OrderTicket(
                            portfolio_id="comp_agg", symbol=self.symbol, side=OrderSide.BUY,
                            order_type=OrderType.MARKET, qty=p_agg.position_qty,
                            reason=ExecutionReason.TAKE_PROFIT, timestamp=ts
                        ))
                        if fill:
                            self.strategy_cooldown["comp_agg"] = ts + 60.0
                            self.position_entry_ts.pop("comp_agg", None)
                            self.log_event("MOMENTUM_TP", f"Aggressive locked short profit {fill.qty} ETH @ ${fill.price:,.2f} (+${fill.realized_pnl:+.2f})", "profit")
                    elif self.live_rsi < Decimal("26") and vel > Decimal("0"):
                        fill = self.broker.submit_order(OrderTicket(
                            portfolio_id="comp_agg", symbol=self.symbol, side=OrderSide.BUY,
                            order_type=OrderType.MARKET, qty=p_agg.position_qty, timestamp=ts
                        ))
                        if fill:
                            self.strategy_cooldown["comp_agg"] = ts + 60.0
                            self.position_entry_ts.pop("comp_agg", None)
                            self.log_event("MOMENTUM_EXIT", f"Aggressive covered short {fill.qty} ETH @ ${fill.price:,.2f} (PnL ${fill.realized_pnl:+.2f})", "profit" if fill.realized_pnl >= 0 else "loss")
                else:
                    gain_usd = price - entry_p
                    gain_pct = (gain_usd / entry_p) * Decimal("100")
                    if gain_pct >= Decimal("0.25") or (self.live_ema_fast < self.live_ema_slow and self.live_rsi < Decimal("48") and gain_usd >= (self.live_atr * Decimal("0.5"))):
                        fill = self.broker.submit_order(OrderTicket(
                            portfolio_id="comp_agg", symbol=self.symbol, side=OrderSide.SELL,
                            order_type=OrderType.MARKET, qty=p_agg.position_qty,
                            reason=ExecutionReason.TAKE_PROFIT, timestamp=ts
                        ))
                        if fill:
                            self.strategy_cooldown["comp_agg"] = ts + 60.0
                            self.position_entry_ts.pop("comp_agg", None)
                            self.log_event("MOMENTUM_TP", f"Aggressive locked long profit {fill.qty} ETH @ ${fill.price:,.2f} (+${fill.realized_pnl:+.2f})", "profit")
                    elif self.live_rsi > Decimal("74") and vel < Decimal("0"):
                        fill = self.broker.submit_order(OrderTicket(
                            portfolio_id="comp_agg", symbol=self.symbol, side=OrderSide.SELL,
                            order_type=OrderType.MARKET, qty=p_agg.position_qty, timestamp=ts
                        ))
                        if fill:
                            self.strategy_cooldown["comp_agg"] = ts + 60.0
                            self.position_entry_ts.pop("comp_agg", None)
                            self.log_event("MOMENTUM_EXIT", f"Aggressive closed long {fill.qty} ETH @ ${fill.price:,.2f} (PnL ${fill.realized_pnl:+.2f})", "profit" if fill.realized_pnl >= 0 else "loss")

        # --- 2. Conservative Mean-Reversion Scalper (comp_cons) ---
        p_cons = self.comp_b.portfolio
        g_cons = self.comp_b.genome
        if p_cons.position_qty == Decimal("0"):
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
                self._try_enter_bracket(self.comp_b, price, sl, tp, ts, "SCALP_SHORT", side=OrderSide.SELL)
        else:
            entry_p = p_cons.avg_entry_price
            if entry_p > Decimal("0"):
                if p_cons.position_side == PositionSide.SHORT:
                    gain_usd = entry_p - price
                    gain_pct = (gain_usd / entry_p) * Decimal("100")
                    if gain_pct >= Decimal("0.15") or (price <= self.live_ema_fast and gain_usd >= (self.live_atr * Decimal("0.5"))):
                        fill = self.broker.submit_order(OrderTicket(
                            portfolio_id="comp_cons", symbol=self.symbol, side=OrderSide.BUY,
                            order_type=OrderType.MARKET, qty=p_cons.position_qty,
                            reason=ExecutionReason.TAKE_PROFIT, timestamp=ts
                        ))
                        if fill:
                            self.strategy_cooldown["comp_cons"] = ts + 60.0
                            self.position_entry_ts.pop("comp_cons", None)
                            self.log_event("SCALP_TP", f"Conservative locked short profit {fill.qty} ETH @ ${fill.price:,.2f} (+${fill.realized_pnl:+.2f})", "profit")
                else:
                    gain_usd = price - entry_p
                    gain_pct = (gain_usd / entry_p) * Decimal("100")
                    if gain_pct >= Decimal("0.15") or (price >= self.live_ema_fast and gain_usd >= (self.live_atr * Decimal("0.5"))):
                        fill = self.broker.submit_order(OrderTicket(
                            portfolio_id="comp_cons", symbol=self.symbol, side=OrderSide.SELL,
                            order_type=OrderType.MARKET, qty=p_cons.position_qty,
                            reason=ExecutionReason.TAKE_PROFIT, timestamp=ts
                        ))
                        if fill:
                            self.strategy_cooldown["comp_cons"] = ts + 60.0
                            self.position_entry_ts.pop("comp_cons", None)
                            self.log_event("SCALP_TP", f"Conservative locked long profit {fill.qty} ETH @ ${fill.price:,.2f} (+${fill.realized_pnl:+.2f})", "profit")

        # --- 3. ATR Volatility Adaptive (comp_atr) ---
        p_atr = self.comp_c.portfolio
        g_atr = self.comp_c.genome
        if p_atr.position_qty == Decimal("0"):
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
                self._try_enter_bracket(self.comp_c, price, sl, tp, ts, "ATR_ADAPT_SHORT", side=OrderSide.SELL, risk_budget=risk_budget)
        else:
            entry_p = p_atr.avg_entry_price
            if entry_p > Decimal("0"):
                target_threshold = max(Decimal("8.00"), self.live_atr * Decimal("1.4"))
                if p_atr.position_side == PositionSide.SHORT:
                    gain_usd = entry_p - price
                    if gain_usd >= target_threshold:
                        fill = self.broker.submit_order(OrderTicket(
                            portfolio_id="comp_atr", symbol=self.symbol, side=OrderSide.BUY,
                            order_type=OrderType.MARKET, qty=p_atr.position_qty,
                            reason=ExecutionReason.TAKE_PROFIT, timestamp=ts
                        ))
                        if fill:
                            self.strategy_cooldown["comp_atr"] = ts + 60.0
                            self.position_entry_ts.pop("comp_atr", None)
                            self.log_event("ATR_TP", f"ATR Dynamic locked short target {fill.qty} ETH @ ${fill.price:,.2f} (+${fill.realized_pnl:+.2f})", "profit")
                else:
                    gain_usd = price - entry_p
                    if gain_usd >= target_threshold:
                        fill = self.broker.submit_order(OrderTicket(
                            portfolio_id="comp_atr", symbol=self.symbol, side=OrderSide.SELL,
                            order_type=OrderType.MARKET, qty=p_atr.position_qty,
                            reason=ExecutionReason.TAKE_PROFIT, timestamp=ts
                        ))
                        if fill:
                            self.strategy_cooldown["comp_atr"] = ts + 60.0
                            self.position_entry_ts.pop("comp_atr", None)
                            self.log_event("ATR_TP", f"ATR Dynamic locked long target {fill.qty} ETH @ ${fill.price:,.2f} (+${fill.realized_pnl:+.2f})", "profit")

        # --- 4. Trailing Profit Ratchet Guard (comp_trail) ---
        p_trail = self.comp_d.portfolio
        g_trail = self.comp_d.genome
        if p_trail.position_qty > Decimal("0"):
            entry_p = p_trail.avg_entry_price
            if entry_p > Decimal("0"):
                if p_trail.position_side == PositionSide.SHORT:
                    if self.comp_d.lowest_price_since_entry == Decimal("0") or price < self.comp_d.lowest_price_since_entry:
                        self.comp_d.lowest_price_since_entry = price
                    gain_pct = ((entry_p - self.comp_d.lowest_price_since_entry) / entry_p) * Decimal("100")
                    if gain_pct >= Decimal("0.12"):
                        self.comp_d.trailing_active = True
                        new_sl = (self.comp_d.lowest_price_since_entry * Decimal("1.0015")).quantize(Decimal("0.01"))
                        curr_stop = self.broker.active_stops.get("comp_trail")
                        if curr_stop and (curr_stop.price is None or new_sl < curr_stop.price):
                            self.broker.active_stops["comp_trail"] = OrderTicket(
                                portfolio_id="comp_trail", symbol=self.symbol, side=OrderSide.BUY,
                                order_type=OrderType.STOP_MARKET, qty=p_trail.position_qty,
                                price=new_sl, reason=ExecutionReason.TRAILING_STOP, timestamp=ts
                            )
                            self.log_event("TRAIL_RATCHET", f"Trailing Guard lowered stop -> ${new_sl:,.2f} (Trough ${self.comp_d.lowest_price_since_entry:,.2f})", "info")
                else:
                    if price > self.comp_d.highest_price_since_entry:
                        self.comp_d.highest_price_since_entry = price
                    gain_pct = ((self.comp_d.highest_price_since_entry - entry_p) / entry_p) * Decimal("100")
                    if gain_pct >= Decimal("0.12"):
                        self.comp_d.trailing_active = True
                        new_sl = (self.comp_d.highest_price_since_entry * Decimal("0.9985")).quantize(Decimal("0.01"))
                        curr_stop = self.broker.active_stops.get("comp_trail")
                        if curr_stop and (curr_stop.price is None or new_sl > curr_stop.price):
                            self.broker.active_stops["comp_trail"] = OrderTicket(
                                portfolio_id="comp_trail", symbol=self.symbol, side=OrderSide.SELL,
                                order_type=OrderType.STOP_MARKET, qty=p_trail.position_qty,
                                price=new_sl, reason=ExecutionReason.TRAILING_STOP, timestamp=ts
                            )
                            self.log_event("TRAIL_RATCHET", f"Trailing Guard raised stop -> ${new_sl:,.2f} (Peak ${self.comp_d.highest_price_since_entry:,.2f})", "info")
        else:
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
                    self.comp_d.trailing_active = False

        # --- 5. Opening Range Breakout (comp_orb) ---
        p_orb = self.comp_e.portfolio
        g_orb = self.comp_e.genome
        orb_high = self.live_orb_high if self.live_orb_high > Decimal("0") else (price * Decimal("1.002"))
        orb_low = self.live_orb_low if self.live_orb_low > Decimal("0") else (price * Decimal("0.998"))
        orb_mid = ((orb_high + orb_low) / Decimal("2")).quantize(Decimal("0.01"))

        if p_orb.position_qty == Decimal("0"):
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
                self._try_enter_bracket(self.comp_e, price, sl, tp, ts, "ORB_SHORT", side=OrderSide.SELL)

            if p_orb.position_qty == Decimal("0") and not self.strategy_telemetry["comp_orb"]["intent"].startswith("EV Gate"):
                self.strategy_telemetry["comp_orb"]["intent"] = f"Watching ORB High ${orb_high:,.2f} / Low ${orb_low:,.2f} (Mid ${orb_mid:,.2f})"
        else:
            entry_p = p_orb.avg_entry_price
            if entry_p > Decimal("0"):
                if p_orb.position_side == PositionSide.SHORT:
                    gain_usd = entry_p - price
                    gain_pct = (gain_usd / entry_p) * Decimal("100")
                    if gain_pct >= Decimal("0.35") or (price > orb_mid and gain_usd >= (self.live_atr * Decimal("0.5"))):
                        fill = self.broker.submit_order(OrderTicket(
                            portfolio_id="comp_orb", symbol=self.symbol, side=OrderSide.BUY,
                            order_type=OrderType.MARKET, qty=p_orb.position_qty,
                            reason=ExecutionReason.TAKE_PROFIT, timestamp=ts
                        ))
                        if fill:
                            self.strategy_cooldown["comp_orb"] = ts + 60.0
                            self.position_entry_ts.pop("comp_orb", None)
                            self.log_event("ORB_TP", f"ORB locked short target {fill.qty} ETH @ ${fill.price:,.2f} (+${fill.realized_pnl:+.2f})", "profit")
                else:
                    gain_usd = price - entry_p
                    gain_pct = (gain_usd / entry_p) * Decimal("100")
                    if gain_pct >= Decimal("0.35") or (price < orb_mid and gain_usd >= (self.live_atr * Decimal("0.5"))):
                        fill = self.broker.submit_order(OrderTicket(
                            portfolio_id="comp_orb", symbol=self.symbol, side=OrderSide.SELL,
                            order_type=OrderType.MARKET, qty=p_orb.position_qty,
                            reason=ExecutionReason.TAKE_PROFIT, timestamp=ts
                        ))
                        if fill:
                            self.strategy_cooldown["comp_orb"] = ts + 60.0
                            self.position_entry_ts.pop("comp_orb", None)
                            self.log_event("ORB_TP", f"ORB locked long target {fill.qty} ETH @ ${fill.price:,.2f} (+${fill.realized_pnl:+.2f})", "profit")

        # --- 6. Institutional VWAP Pullback (comp_vwap) ---
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

            if p_vwap.position_qty == Decimal("0") and not self.strategy_telemetry["comp_vwap"]["intent"].startswith("EV Gate"):
                self.strategy_telemetry["comp_vwap"]["intent"] = f"Awaiting VWAP bounce / rejection near ${vwap_ref:,.2f}"
        else:
            entry_p = p_vwap.avg_entry_price
            if entry_p > Decimal("0"):
                if p_vwap.position_side == PositionSide.SHORT:
                    gain_usd = entry_p - price
                    gain_pct = (gain_usd / entry_p) * Decimal("100")
                    if gain_pct >= Decimal("0.30") or (price <= (vwap_ref - self.live_atr * Decimal("1.5")) and gain_usd >= (self.live_atr * Decimal("0.6"))):
                        fill = self.broker.submit_order(OrderTicket(
                            portfolio_id="comp_vwap", symbol=self.symbol, side=OrderSide.BUY,
                            order_type=OrderType.MARKET, qty=p_vwap.position_qty,
                            reason=ExecutionReason.TAKE_PROFIT, timestamp=ts
                        ))
                        if fill:
                            self.strategy_cooldown["comp_vwap"] = ts + 60.0
                            self.position_entry_ts.pop("comp_vwap", None)
                            self.log_event("VWAP_TP", f"VWAP locked short profit {fill.qty} ETH @ ${fill.price:,.2f} (+${fill.realized_pnl:+.2f})", "profit")
                else:
                    gain_usd = price - entry_p
                    gain_pct = (gain_usd / entry_p) * Decimal("100")
                    if gain_pct >= Decimal("0.30") or (price >= (vwap_ref + self.live_atr * Decimal("1.5")) and gain_usd >= (self.live_atr * Decimal("0.6"))):
                        fill = self.broker.submit_order(OrderTicket(
                            portfolio_id="comp_vwap", symbol=self.symbol, side=OrderSide.SELL,
                            order_type=OrderType.MARKET, qty=p_vwap.position_qty,
                            reason=ExecutionReason.TAKE_PROFIT, timestamp=ts
                        ))
                        if fill:
                            self.strategy_cooldown["comp_vwap"] = ts + 60.0
                            self.position_entry_ts.pop("comp_vwap", None)
                            self.log_event("VWAP_TP", f"VWAP locked long profit {fill.qty} ETH @ ${fill.price:,.2f} (+${fill.realized_pnl:+.2f})", "profit")

        self._update_telemetry_snapshot(price)

    def _ensure_active_live_positions(self, price: Decimal, ts: float) -> None:
        """
        Ensures that on startup in Live Mode, any flat competitor deploys its initial strategy
        bracket at the current live market price with TimeMachine EV Gate and Dynamic R-Multiple sizing.
        Enters Long or Short according to market conditions and trend bias.
        """
        if price <= Decimal("0"):
            return

        is_uptrend = self.live_ema_fast >= self.live_ema_slow if self.live_ema_slow > Decimal("0") else True
        orb_high = self.live_orb_high if self.live_orb_high > Decimal("0") else (price * Decimal("1.002"))
        orb_low = self.live_orb_low if self.live_orb_low > Decimal("0") else (price * Decimal("0.998"))
        orb_mid = ((orb_high + orb_low) / Decimal("2")).quantize(Decimal("0.01"))
        vwap_ref = self.live_vwap if self.live_vwap > Decimal("0") else (self.live_ema_slow if self.live_ema_slow > Decimal("0") else price)

        # 1. Aggressive
        if self.comp_a.portfolio.position_qty == Decimal("0"):
            if is_uptrend:
                sl = (price * (Decimal("1") - self.comp_a.genome.stop_loss_pct)).quantize(Decimal("0.01"))
                tp = (price * (Decimal("1") + self.comp_a.genome.take_profit_pct)).quantize(Decimal("0.01")) if self.comp_a.genome.take_profit_pct else None
                self._try_enter_bracket(self.comp_a, price, sl, tp, ts, "BREAKOUT_LONG", side=OrderSide.BUY)
            else:
                sl = (price * (Decimal("1") + self.comp_a.genome.stop_loss_pct)).quantize(Decimal("0.01"))
                tp = (price * (Decimal("1") - self.comp_a.genome.take_profit_pct)).quantize(Decimal("0.01")) if self.comp_a.genome.take_profit_pct else None
                self._try_enter_bracket(self.comp_a, price, sl, tp, ts, "BREAKDOWN_SHORT", side=OrderSide.SELL)

        # 2. Conservative
        if self.comp_b.portfolio.position_qty == Decimal("0"):
            if self.live_rsi > Decimal("52.0"):
                sl = (price * Decimal("1.006")).quantize(Decimal("0.01"))
                tp = (price * Decimal("0.991")).quantize(Decimal("0.01"))
                self._try_enter_bracket(self.comp_b, price, sl, tp, ts, "SCALP_SHORT", side=OrderSide.SELL)
            else:
                sl = (price * Decimal("0.994")).quantize(Decimal("0.01"))
                tp = (price * Decimal("1.009")).quantize(Decimal("0.01"))
                self._try_enter_bracket(self.comp_b, price, sl, tp, ts, "SCALP_LONG", side=OrderSide.BUY)

        # 3. ATR Dynamic
        if self.comp_c.portfolio.position_qty == Decimal("0"):
            stop_dist = max(Decimal("50.00"), (self.live_atr * self.comp_c.genome.atr_stop_mult).quantize(Decimal("0.01")))
            target_dist = max(Decimal("100.00"), (self.live_atr * self.comp_c.genome.atr_target_mult).quantize(Decimal("0.01")))
            risk_budget = self.comp_c.portfolio.total_equity * self.comp_c.genome.atr_risk_pct
            if is_uptrend:
                sl = (price - stop_dist).quantize(Decimal("0.01"))
                tp = (price + target_dist).quantize(Decimal("0.01"))
                self._try_enter_bracket(self.comp_c, price, sl, tp, ts, "ATR_ADAPT_LONG", side=OrderSide.BUY, risk_budget=risk_budget)
            else:
                sl = (price + stop_dist).quantize(Decimal("0.01"))
                tp = (price - target_dist).quantize(Decimal("0.01"))
                self._try_enter_bracket(self.comp_c, price, sl, tp, ts, "ATR_ADAPT_SHORT", side=OrderSide.SELL, risk_budget=risk_budget)

        # 4. Trailing Guard
        if self.comp_d.portfolio.position_qty == Decimal("0"):
            if is_uptrend:
                sl = (price * Decimal("0.991")).quantize(Decimal("0.01"))
                if self._try_enter_bracket(self.comp_d, price, sl, None, ts, "TRAIL_LONG", side=OrderSide.BUY):
                    self.comp_d.highest_price_since_entry = price
                    self.comp_d.lowest_price_since_entry = price
            else:
                sl = (price * Decimal("1.009")).quantize(Decimal("0.01"))
                if self._try_enter_bracket(self.comp_d, price, sl, None, ts, "TRAIL_SHORT", side=OrderSide.SELL):
                    self.comp_d.highest_price_since_entry = price
                    self.comp_d.lowest_price_since_entry = price

        # 5. ORB Breakout
        if self.comp_e.portfolio.position_qty == Decimal("0"):
            if price >= orb_mid:
                sl = (price * Decimal("0.992")).quantize(Decimal("0.01"))
                tp = (price + (price - sl) * Decimal("2.0")).quantize(Decimal("0.01"))
                self._try_enter_bracket(self.comp_e, price, sl, tp, ts, "ORB_LONG", side=OrderSide.BUY)
            else:
                sl = (price * Decimal("1.008")).quantize(Decimal("0.01"))
                tp = (price - (sl - price) * Decimal("2.0")).quantize(Decimal("0.01"))
                self._try_enter_bracket(self.comp_e, price, sl, tp, ts, "ORB_SHORT", side=OrderSide.SELL)

        # 6. VWAP Pullback
        if self.comp_f.portfolio.position_qty == Decimal("0"):
            if price >= vwap_ref:
                sl = (price * Decimal("0.993")).quantize(Decimal("0.01"))
                tp = (price + (price - sl) * Decimal("2.2")).quantize(Decimal("0.01"))
                self._try_enter_bracket(self.comp_f, price, sl, tp, ts, "VWAP_LONG", side=OrderSide.BUY)
            else:
                sl = (price * Decimal("1.007")).quantize(Decimal("0.01"))
                tp = (price - (sl - price) * Decimal("2.2")).quantize(Decimal("0.01"))
                self._try_enter_bracket(self.comp_f, price, sl, tp, ts, "VWAP_SHORT", side=OrderSide.SELL)

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
                is_short = p.position_side == PositionSide.SHORT
                pos_dir = "SHORT" if is_short else "LONG"
                if is_short:
                    upnl_pct = ((p.avg_entry_price - price) / p.avg_entry_price * Decimal("100")) if p.avg_entry_price > 0 else Decimal("0")
                else:
                    upnl_pct = ((price - p.avg_entry_price) / p.avg_entry_price * Decimal("100")) if p.avg_entry_price > 0 else Decimal("0")

                if pid == "comp_agg":
                    intent = f"{pos_dir} {p.position_qty} ETH @ ${p.avg_entry_price:,.2f} | Uncapped Trend Run ({upnl_pct:+.2f}%)"
                elif pid == "comp_cons":
                    intent = f"SCALP {pos_dir} {p.position_qty} ETH @ ${p.avg_entry_price:,.2f} | Target ${tp_p:,.2f}" if tp_p else f"{pos_dir} {p.position_qty} ETH"
                elif pid == "comp_atr":
                    intent = f"ATR {pos_dir} {p.position_qty} ETH @ ${p.avg_entry_price:,.2f} | 1.5x/2.5x ATR Bracket"
                elif pid == "comp_orb":
                    intent = f"ORB {pos_dir} {p.position_qty} ETH @ ${p.avg_entry_price:,.2f} | 2.0R Target ${tp_p:,.2f}" if tp_p else f"{pos_dir} {p.position_qty} ETH"
                elif pid == "comp_vwap":
                    intent = f"VWAP {pos_dir} {p.position_qty} ETH @ ${p.avg_entry_price:,.2f} | 2.2R Target ${tp_p:,.2f}" if tp_p else f"{pos_dir} {p.position_qty} ETH"
                else:
                    ref_p = self.comp_d.lowest_price_since_entry if is_short else self.comp_d.highest_price_since_entry
                    ref_tag = "Trough" if is_short else "Peak"
                    intent = f"TRAILING {pos_dir} {p.position_qty} ETH | {ref_tag} ${ref_p:,.2f} | Ratchet SL ${sl_p:,.2f}" if sl_p else f"{pos_dir} {p.position_qty} ETH"
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

    def _quote_fetch_worker(self) -> None:
        """Hidden background thread: continuously queries public REST APIs without blocking UI cadence."""
        while self.running:
            if self.paused:
                time.sleep(0.25)
                continue
            try:
                raw = self.fetch_realtime_eth_quote()
                if raw and not raw.is_offline and raw.price > Decimal("0"):
                    with self.lock:
                        self._raw_quote_cache = raw
                        self._slice_ticks.append(raw)
                        self.market_online = True
                else:
                    with self.lock:
                        self.market_online = False
            except Exception as e:
                logger.debug("Background quote fetcher error: %s", e)
            time.sleep(1.0)

    def start_live_loop(self, interval_sec: float = 5.0) -> None:
        if self.running:
            return
        self.cadence_sec = max(1.0, float(interval_sec))
        self.running = True
        self.worker_thread = threading.Thread(target=self._live_loop, daemon=True)
        self.worker_thread.start()

    def stop_live_loop(self) -> None:
        self.running = False
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=3.0)
        self.worker_thread = None
        if self.raw_fetch_thread and self.raw_fetch_thread.is_alive():
            self.raw_fetch_thread.join(timeout=2.0)
        self.raw_fetch_thread = None

    def stop(self) -> None:
        self.stop_live_loop()

    def _live_loop(self) -> None:
        self.log_event("BOOT", "Connecting to real-time ETH/USD orderflow & warming 1m indicators...", "info")
        self.bootstrap_intraday_session()
        with self.lock:
            self.live_start_ts = time.time()
            self.last_evolve_ts = time.time()
            self.last_cadence_slot = int(time.time() // self.cadence_sec) * int(self.cadence_sec)

        # Start hidden raw quote fetcher in background
        self.raw_fetch_thread = threading.Thread(target=self._quote_fetch_worker, daemon=True)
        self.raw_fetch_thread.start()

        while self.running:
            if self.paused:
                time.sleep(0.25)
                continue

            now = time.time()
            current_slot = int(now // self.cadence_sec) * int(self.cadence_sec)

            if current_slot > self.last_cadence_slot:
                self.last_cadence_slot = current_slot
                try:
                    with self.lock:
                        raw = self._raw_quote_cache or self.latest_quote
                        ticks = list(self._slice_ticks)
                        self._slice_ticks.clear()

                        if raw and not raw.is_offline and raw.price > Decimal("0.00"):
                            self.market_online = True
                            prev_p = self.published_quote.price if (self.published_quote and self.published_quote.price > Decimal("0")) else raw.price

                            if ticks:
                                open_p = ticks[0].price
                                high_p = max(t.price for t in ticks)
                                low_p = min(t.price for t in ticks)
                                close_p = ticks[-1].price
                            else:
                                open_p = prev_p
                                high_p = max(raw.price, raw.ask)
                                low_p = min(raw.price, raw.bid)
                                close_p = raw.price

                            cadenced_quote = LiveQuote(
                                price=close_p,
                                bid=raw.bid,
                                ask=raw.ask,
                                high_24h=raw.high_24h,
                                low_24h=raw.low_24h,
                                volume_24h=raw.volume_24h,
                                change_24h_pct=raw.change_24h_pct,
                                source=raw.source,
                                timestamp=float(current_slot),
                                is_offline=False
                            )
                            self.latest_quote = cadenced_quote
                            self.published_quote = cadenced_quote
                            self.tick_count += 1

                            # Micro-bar aggregated 1-minute candle refresh [R1]
                            self._update_candle(
                                float(current_slot),
                                close=cadenced_quote.price,
                                high=high_p,
                                low=low_p,
                                open_=open_p
                            )
                            self._recompute_candle_indicators()

                            # Paced Cadence Dispatcher: Publish candle slices at stable 5s heartbeat (:00, :05, :10, :15...)
                            self.published_candles = [dict(c) for c in self.candles]
                            self.last_cadence_ts = float(current_slot)

                            # Update live exponential moving averages on each 5-second cadence beat
                            alpha_f = Decimal("0.15")
                            alpha_s = Decimal("0.04")
                            if self.live_ema_fast <= Decimal("0"):
                                self.live_ema_fast = cadenced_quote.price
                                self.live_ema_slow = cadenced_quote.price
                            else:
                                self.live_ema_fast = ((cadenced_quote.price * alpha_f) + (self.live_ema_fast * (Decimal("1") - alpha_f))).quantize(Decimal("0.01"))
                                self.live_ema_slow = ((cadenced_quote.price * alpha_s) + (self.live_ema_slow * (Decimal("1") - alpha_s))).quantize(Decimal("0.01"))

                            # Live orders & simulated matching activate ONLY on the 5-second boundary
                            if self.live_orders_enabled:
                                if not self.live_trading_active:
                                    self.live_trading_active = True
                                    self.live_start_ts = time.time()
                                    self.last_evolve_ts = time.time()
                                    self._ensure_active_live_positions(cadenced_quote.price, float(current_slot))
                                    self.log_event("LIVE_START", f"Arena revealed. Live order dispatch active @ ${cadenced_quote.price:,.2f}", "buy")

                                fills = self.broker.on_tick(
                                    price=cadenced_quote.price,
                                    high=max(high_p, cadenced_quote.price, cadenced_quote.ask),
                                    low=min(low_p, cadenced_quote.price, cadenced_quote.bid),
                                    timestamp=float(current_slot),
                                    open_price=prev_p
                                )
                                for f in fills:
                                    if f.side == OrderSide.SELL:
                                        self.strategy_cooldown[f.portfolio_id] = float(current_slot) + 60.0
                                        self.position_entry_ts.pop(f.portfolio_id, None)
                                    pnl_str = f" (PnL: ${f.realized_pnl:+.2f})" if f.side == OrderSide.SELL else ""
                                    self.log_event(
                                        f.reason.value,
                                        f"{f.portfolio_id.upper()} {f.side.value} {f.qty} ETH @ ${f.price:,.2f}{pnl_str}",
                                        "profit" if f.realized_pnl >= Decimal("0") else "loss"
                                    )
                                    strat_name = self.STRATEGY_SHORT.get(f.portfolio_id, f.portfolio_id)
                                    if f.side == OrderSide.SELL:
                                        self.macro_commander.record_strategy_action(
                                            f.portfolio_id,
                                            strat_name,
                                            f"Closed {f.qty} ETH @ ${f.price:,.2f} ({f.reason.value}{pnl_str})",
                                            "profit" if f.realized_pnl >= Decimal("0") else "loss"
                                        )

                                if not self.position_entry_ts and all(c.portfolio.position_qty == Decimal("0") for c in self.competitors):
                                    self._ensure_active_live_positions(cadenced_quote.price, float(current_slot))

                                # All 6 strategies evaluated strictly on the 5-second interval
                                self._evaluate_live_strategies(cadenced_quote.price, prev_p, float(current_slot))

                            self._record_series_point(cadenced_quote.price, float(current_slot))

                        if self.live_orders_enabled and self._auto_evolve_due():
                            self.evolve_now(trigger="auto")

                except Exception as e:
                    self.log_event("FEED_WARN", f"Retrying live quote stream: {e}", "loss")

            time.sleep(0.1)  # High-frequency sleep to hit exact 5-second wall clock slot without drift

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

    def set_cadence_interval(self, seconds: float) -> float:
        with self.lock:
            self.cadence_sec = max(1.0, min(10.0, float(seconds)))
            self.log_event("CONFIG", f"Candlestick output cadence set to {self.cadence_sec:.1f}s", "info")
            return self.cadence_sec

    def evolve_now(self, trigger: str = "manual") -> List[str]:
        records_to_save = None
        with self.lock:
            self._harvest_fills()
            rankings = Leaderboard.get_rankings(self.broker.portfolios)
            prev_gen = max(c.genome.generation for c in self.competitors)
            short = self.STRATEGY_SHORT
            kept = [short.get(r.portfolio_id, r.portfolio_id) for r in rankings[:2]]
            rebuilt = [short.get(r.portfolio_id, r.portfolio_id) for r in rankings[2:]]
            leader_roi = float(rankings[0].roi_pct) if rankings else 0.0

            logs = GeneticEvolver.evolve_generation(self.competitors, rankings, preserve_portfolio=True, save_history=False)
            records_to_save = GeneticEvolver._last_records
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
                self.log_event("STRATEGY_SYNTHESIS", f"Generation #{new_gen} online. Champion: {top.name} (ROI {float(top.roi_pct):+.2f}%, Sharpe {top.sharpe_ratio:+.2f})", "info")

            for line in logs:
                self.log_event("EVOLVE", line, "evolve")

        # Save history outside self.lock to prevent UI jitter
        if records_to_save and records_to_save[0] and records_to_save[1]:
            try:
                GeneticEvolver.save_history(records_to_save[0], records_to_save[1])
            except Exception as e:
                logger.warning("Failed to persist evolution history outside lock: %s", e)

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
        "SIGNAL_ENTRY": "Strategy Signal",
        "SIGNAL_EXIT": "Strategy Signal",
        "STOP_LOSS": "Stop Loss",
        "TAKE_PROFIT": "Take Profit",
        "TRAILING_STOP": "Trailing Stop",
        "CIRCUIT_BREAKER": "Circuit Breaker",
        "LIQUIDATION": "Margin Liquidation",
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
            is_short = p.position_side == PositionSide.SHORT
            upnl_pct = Decimal("0")
            if in_pos and p.avg_entry_price > Decimal("0") and spot > Decimal("0"):
                if is_short:
                    upnl_pct = (p.avg_entry_price - spot) / p.avg_entry_price * Decimal("100")
                else:
                    upnl_pct = (spot - p.avg_entry_price) / p.avg_entry_price * Decimal("100")
            tp_txt = f"{float(g.take_profit_pct) * 100:.1f}%" if g.take_profit_pct else "—"
            stop_ord = self.broker.active_stops.get(pid)
            tp_ord = self.broker.active_targets.get(pid)
            sl_p = fz(stop_ord.price) if (in_pos and stop_ord and stop_ord.price) else None
            tp_p = fz(tp_ord.price) if (in_pos and tp_ord and tp_ord.price) else None
            # Trailing Guard has no fixed TP: show a virtual ceiling (for Long) or virtual floor (for Short)
            # so the bracket bar stays meaningful even after the stop ratchets
            if in_pos and tp_p is None and sl_p is not None:
                entry_f = fz(p.avg_entry_price)
                if is_short:
                    ref = min(fz(spot), entry_f)
                    tp_p = round(max(1.0, ref - 2 * max(0.5, abs(sl_p - ref))), 2)
                else:
                    ref = max(fz(spot), entry_f)
                    tp_p = round(ref + 2 * max(0.5, abs(ref - sl_p)), 2)
            strategies.append({
                "id": pid,
                "rank": r.rank,
                "name": self.STRATEGY_DISPLAY.get(pid, c.base_name),
                "color": self.STRATEGY_COLORS.get(pid, "#ECF2F8"),
                "generation": g.generation,
                "leverage": fz(g.leverage),
                "leverage_enabled": bool(g.leverage_enabled),
                "leverage_label": f"{float(g.leverage):.1f}x Lev" if g.leverage_enabled else "Spot 1x",
                "genome": f"{'Lev ' + str(round(float(g.leverage), 1)) + 'x' if g.leverage_enabled else 'Spot 1x'} | Size {float(g.position_ratio) * 100:.0f}% | SL {float(g.stop_loss_pct) * 100:.2f}% | TP {tp_txt}",
                "equity": fz(r.equity),
                "cash": fz(p.cash),
                "margin_locked": fz(p.margin_locked),
                "roi_pct": fz(r.roi_pct),
                "unrealized_pnl": fz(p.unrealized_pnl),
                "unrealized_pct": fz(upnl_pct),
                "realized_pnl": fz(p.realized_pnl),
                "in_position": in_pos,
                "position_side": p.position_side.value,
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
            is_short_pos = getattr(f, "position_side", PositionSide.LONG) == PositionSide.SHORT
            if is_short_pos:
                is_entry = f.side == OrderSide.SELL
                action_label = "OPEN SHORT" if is_entry else "COVER SHORT"
            else:
                is_entry = f.side == OrderSide.BUY
                action_label = "OPEN LONG" if is_entry else "CLOSE LONG"
            base_reason = self.REASON_DISPLAY.get(f.reason.value, f.reason.value)
            entry_p_dec = getattr(f, "entry_price", None)
            reason_detail = base_reason

            fills_view.append({
                "seq": f.fill_seq,
                "time": time.strftime("%H:%M:%S", time.localtime(f.timestamp)),
                "strategy": self.STRATEGY_DISPLAY.get(pid, pid).split(" ")[0],
                "side": f.side.value,
                "action_label": action_label,
                "is_entry": is_entry,
                "qty": fz(f.qty),
                "price": fz(f.price),
                "entry_price": fz(entry_p_dec) if entry_p_dec else None,
                "pnl": fz(f.realized_pnl) if not is_entry else None,
                "reason": reason_detail,
                "is_live": is_live,
            })

        leader = strategies[0] if strategies else None
        quant_meta = {
            "source": "Local Pure-Math Quant Core",
            "is_online": self.market_online,
            "endpoint": "In-Memory Native Engine",
            "active_model": "Genetic Evolution + Monte Carlo EV",
            "quota_pct": 100.0,
            "tokens_used": 0,
            "tokens_saved": 0,
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
            "macro_commander": self.macro_commander.current_state.to_dict(),
            "intel_hub": self.macro_commander.get_intel_hub_telemetry(),
            "candles": [
                {
                    "t": c["t"],
                    "o": fz(c["o"]),
                    "h": fz(c["h"]),
                    "l": fz(c["l"]),
                    "c": fz(c["c"]),
                }
                for c in (self.published_candles if self.published_candles else self.candles)[-150:]
            ],
            "cadence_sec": self.cadence_sec,
            "tv_hub": {
                "champion": active_tv_champ,
                "next_rotation_sec": int(next_evolve_sec),
                "payloads": tv_payloads[:6],
                "webhook_endpoint": "Internal Signal Bus",
                "is_connected": False,
            },
            "quant_meta": quant_meta,
            "omni_meta": quant_meta,
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
                "market_online": self.market_online,
                "is_bootstrapped": self.is_bootstrapped,
                "live_orders_enabled": self.live_orders_enabled,
                "candle_count": len(self.candles),
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
                    "is_offline": q.is_offline if q else True,
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
            }
            state.update(self._build_view_model(rankings, gen))
            return state

