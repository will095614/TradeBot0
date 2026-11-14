from __future__ import annotations
import asyncio
import copy
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Dict, List, Any, Optional
import logging
import math
import os
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
from src.competitors.session_mean import SessionMeanPullbackCompetitor
from src.data.eth_feed import ETHFeed, CandleBar
from src.data.mtf_engine import MultiTimeframeEngine
from src.data.persistence import ArenaStorage
from src.data.quote_manager import QuoteManager
from src.data.timemachine import MonteCarloOddsEvaluator
from src.data.ws_feed import StreamingCryptoFeed
from src.gui.view_model import ViewModelPublisher, build_engine_view_model
from src.intelligence.omniroute_client import OmniRouteClient
from src.intelligence.macro_commander import MacroCommander, MacroRegimeState

logger = logging.getLogger(__name__)

# A quote older than this is stale and never tradable. On disconnect the
# engine pauses and waits for a fresh quote instead of trading on a cached
# price (offline mode removed, item 3).
QUOTE_STALE_SEC = 5.0

# A SQLite candle cache is fresh only while its newest 1-minute bar is
# recent. 600s = 10 bars of slack for a brief feed gap: a cache older
# than that belongs to a dead session, and warming indicators (RSI / ATR
# / ORB / session mean) from it would misprice the live open. The 5s
# quote freshness above is for tradable quotes, not warm-up candles,
# so it does not apply here. Both bootstrap cache branches share this
# one threshold (the first branch already used the literal 600.0).
CANDLE_CACHE_STALE_SEC = 600.0


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

    # Generation fence (item 9): reset_engine() builds a brand-new engine, so
    # the newest instance's epoch is the only valid one. A previous engine
    # whose worker thread survives stop() (join timeout) must not write
    # SQLite or publish state anymore.
    _active_epoch: float = 0.0

    def __init__(self, initial_cash: Decimal = Decimal("100000.00"), symbol: str = "ETH/USD", storage: Optional[ArenaStorage] = None):
        self.symbol = symbol
        self.initial_cash = initial_cash
        self.lock = threading.RLock()
        self._snapshot_lock = threading.Lock()
        self._ui_state_snapshot: Optional[Dict[str, Any]] = None
        self.market_online: bool = False
        self.is_bootstrapped: bool = False
        self.live_orders_enabled: bool = False
        self.live_trading_active: bool = False
        self._has_restored_session: bool = False
        # Strictly increasing epoch: a new engine always supersedes any older
        # instance, even if two are constructed within one clock tick.
        self.engine_epoch: float = max(time.time(), LiveArenaEngine._active_epoch + 0.001)
        LiveArenaEngine._active_epoch = self.engine_epoch
        self.running = False
        self._stop_event = threading.Event()
        self._paused: bool = False
        self._pause_start_ts: Optional[float] = None
        self._auto_evolve_disabled_ts: Optional[float] = None
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
        self.comp_f = SessionMeanPullbackCompetitor(initial_cash=initial_cash)
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
        self.live_typical_mean: Decimal = Decimal("0.00")
        self.live_orb_high: Decimal = Decimal("0.00")
        self.live_orb_low: Decimal = Decimal("0.00")

        # 1-minute OHLC candles (bootstrap bars + live ticks aggregated) for charting & live RSI/ATR
        self.candles: List[Dict[str, float]] = []
        self.max_candles: int = 200
        self.live_start_ts: Optional[float] = None

        # Paced Candlestick Cadence Dispatcher (emits stable slices at 1s real-time heartbeat)
        self.cadence_sec: float = 1.0
        self.last_cadence_ts: float = 0.0
        self.last_cadence_slot: int = 0
        self.published_candles: List[Dict[str, float]] = []
        self.published_quote: Optional[LiveQuote] = None
        # Last FRESH quote only. It is never served once stale: the live loop
        # gates on _is_quote_fresh() and pauses when the feed goes down.
        self._raw_quote_cache: Optional[LiveQuote] = None
        self._slice_ticks: List[LiveQuote] = []
        self.raw_fetch_thread: Optional[threading.Thread] = None

        # Automatic evolution: every 6 hours, or every 30 closed trades,
        # whichever comes first, with a 30-minute debounce between runs.
        self.auto_evolve_enabled: bool = True
        self.auto_evolve_interval_sec: int = 21600  # Default 6 hours (21600s)
        self.auto_evolve_closed_trades: int = 30
        self.auto_evolve_debounce_sec: int = 1800  # 30 minutes
        self.last_evolve_ts: float = time.time()
        self._closed_trades_since_evolve: int = 0
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

        # Anti-churn cooldown & hold-duration tracking
        self.strategy_cooldown: Dict[str, float] = {}
        self.position_entry_ts: Dict[str, float] = {}

        # TimeMachine Monte Carlo Odds Evaluator & EV Gate (day-trader-skill)
        self.mc_evaluator = MonteCarloOddsEvaluator(seed=19)

        # Macro Commander & OmniRoute Intelligence Layer (Strict Veto Option A)
        self.omniroute_client = OmniRouteClient()
        self.macro_commander = MacroCommander(self.omniroute_client)
        self.intel_refresh_interval_sec: float = 300.0  # 5 minutes automated background digest cycle
        self.last_intel_refresh_ts: float = time.time()
        self._is_refreshing_intel: bool = False
        self._intel_refresh_lock = threading.Lock()

        # Phase 1: Low-Latency WebSocket Streaming & Quote Manager (single shared WS socket)
        self.quote_manager = QuoteManager(session=self.session, on_ws_quote=self._handle_ws_quote)
        self.ws_feed: StreamingCryptoFeed = self.quote_manager.ws_feed

        # Phase 2: Native SQLite WAL Embedded Persistence
        self.storage = storage if storage is not None else ArenaStorage()

        # Phase 4: Multi-Timeframe (MTF) Trend Confluence Engine
        self.mtf_engine = MultiTimeframeEngine()
        self.candles_5m: List[Dict[str, float]] = self.mtf_engine.candles_5m
        self.candles_15m: List[Dict[str, float]] = self.mtf_engine.candles_15m
        self.candles_1h: List[Dict[str, float]] = self.mtf_engine.candles_1h
        self.htf_ema_50: float = 0.0
        self.htf_ema_200: float = 0.0
        self.htf_bias: str = "NEUTRAL"

        # Phase 6: Diff-Based ViewModel Publisher
        self.view_publisher = ViewModelPublisher()

        self._init_broker()

    def _handle_ws_quote(self, quote: LiveQuote) -> None:
        """Callback invoked by StreamingCryptoFeed when a real-time WebSocket tick arrives."""
        with self.lock:
            self.latest_quote = quote
            self._raw_quote_cache = quote
            self._slice_ticks.append(quote)
            # Bound the backlog: while paused the live loop never drains
            # this list, so an unattended WS stream would grow it forever
            # (a cadence consumes at most seconds of ticks; 1200 is ~10
            # minutes at full ticker rate).
            if len(self._slice_ticks) > 1200:
                del self._slice_ticks[:-1200]
            self.market_online = True

    def _is_current_generation(self) -> bool:
        """Generation fence (item 9): True only while this engine instance is
        the newest one. After a reset the dashboard owns a fresh engine, so
        any thread still owned by the old instance must refuse SQLite writes
        and state publishes instead of overwriting the new generation."""
        return self.engine_epoch == LiveArenaEngine._active_epoch

    def _harvest_fills(self) -> None:
        """Copies new broker fills into the persistent tape (bounded to 200 records) and SQLite ledger."""
        if not self._is_current_generation():
            logger.warning("Stale engine epoch %.3f: refusing to record fills from a superseded generation", self.engine_epoch)
            return
        audit = self.broker.execution_audit
        if self._audit_cursor > len(audit):
            self._audit_cursor = 0
        if self._audit_cursor < len(audit):
            new_fills = audit[self._audit_cursor:]
            self.fill_records.extend(new_fills)
            self._audit_cursor = len(audit)
            for f in new_fills:
                if getattr(f, "is_closing_fill", False):
                    # Closed trade (CLOSE LONG / COVER SHORT): counts toward the
                    # trade-count evolution trigger; opening fills do not count.
                    self._closed_trades_since_evolve += 1
                try:
                    is_short_pos = getattr(f, "position_side", PositionSide.SHORT) == PositionSide.SHORT
                    is_entry = (f.side == OrderSide.SELL) if is_short_pos else (f.side == OrderSide.BUY)
                    if is_short_pos:
                        action_label = "OPEN SHORT" if is_entry else "COVER SHORT"
                    else:
                        action_label = "OPEN LONG" if is_entry else "CLOSE LONG"
                    entry_p = getattr(f, "entry_price", None)
                    self.storage.record_fill({
                        "seq": f.fill_seq,
                        "timestamp": f.timestamp,
                        "portfolio_id": f.portfolio_id,
                        "strategy": self.STRATEGY_SHORT.get(f.portfolio_id, f.portfolio_id),
                        "symbol": self.symbol,
                        "side": f.side.value,
                        "action_label": action_label,
                        "qty": float(f.qty),
                        "price": float(f.price),
                        "entry_price": float(entry_p) if entry_p else None,
                        "pnl": float(f.realized_pnl) if not is_entry else None,
                        "fee": float(getattr(f, "fee", 0) or 0),
                        "reason": f.reason.value,
                        "is_live": bool(self.live_start_ts and f.timestamp >= self.live_start_ts - 2.0),
                    })
                except Exception as e:
                    logger.debug("SQLite fill record skipped: %s", e)
            if len(self.fill_records) > 200:
                self.fill_records = self.fill_records[-200:]
            if self._audit_cursor > 500:
                self.broker.execution_audit = self.broker.execution_audit[self._audit_cursor:]
                self._audit_cursor = 0

    def _init_broker(self) -> None:
        self.broker = BrokerSim(symbol=self.symbol, slippage_pct=Decimal("0.0001"))
        self._audit_cursor = 0
        # Seed the fill sequence past the SQLite ledger's max so fill_seq never
        # reuses a number across restarts (INSERT OR REPLACE would overwrite
        # an earlier fill). Monotonic floor: reset_seq() never lowers it.
        try:
            recent = self.storage.load_recent_fills(limit=1)
            if recent:
                self.broker.reset_seq(int(recent[0].get("seq", 0)))
        except Exception as e:
            logger.debug("Fill-seq seeding skipped: %s", e)
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

        # Check and restore previous session state if available and not in fast-test mode
        if os.environ.get("ARENA_FAST_TEST") != "1":
            try:
                if self.restore_session_state():
                    self._has_restored_session = True
            except Exception as e:
                logger.debug("Auto restore session state skipped: %s", e)

    @staticmethod
    def _get_strategy_label(pid: str) -> str:
        labels = {
            "comp_agg": "Momentum Breakout (3x Lev / 70% Cap)",
            "comp_cons": "Mean-Reversion Scalper (Spot 1x / 25% Cap)",
            "comp_atr": "ATR Volatility Adaptive (2x Lev Dynamic)",
            "comp_trail": "Trailing Ratchet Guard (2x Lev / 40% Cap)",
            "comp_orb": "Opening Range Breakout (2.5x Lev / 45% Cap)",
            "comp_vwap": "Session Mean Pullback (Spot 1x / 50% Cap)",
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
            "comp_vwap": "Pullback test & bounce at session mean (Long) / Rejection at session mean (Short) | 2.2R Target",
        }
        return rules.get(pid, "")

    def log_event(self, tag: str, message: str, level: str = "info") -> None:
        with self.lock:
            ts = time.strftime("%H:%M:%S")
            self.live_logs.insert(0, {"time": ts, "tag": tag, "message": message, "level": level})
            if len(self.live_logs) > 120:
                self.live_logs.pop()

    # Quote chain policy (user decision 2026-11-13): every external source
    # is best-effort — try it, and a blocked one is fine, because different
    # users sit behind different network filters. Each fetcher below catches
    # all exceptions (incl. SSLError from DNS-filter landing pages) and
    # returns None; the caller walks Binance -> Kraken -> Coinbase and uses
    # the first live quote. No single source may take down the quote path.
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
        WebSocket Push -> Binance -> Kraken -> Coinbase with adaptive provider ranking & circuit breaking.
        There is deliberately NO cached-price fallback: when every live source
        fails, the honest offline sentinel is returned and the engine pauses
        trading until a fresh quote arrives (offline mode removed, item 3).
        """
        now = time.time()
        if (
            self.ws_feed.connected
            and (now - self.ws_feed.last_msg_ts) < 3.0
            and self.latest_quote is not None
            and not self.latest_quote.is_offline
        ):
            return self.latest_quote

        providers = ["binance", "kraken", "coinbase"]
        if self.preferred_quote_provider in providers:
            providers.remove(self.preferred_quote_provider)
            providers.insert(0, self.preferred_quote_provider)

        active_providers = [p for p in providers if self._quote_provider_cooldown.get(p, 0.0) <= now]
        # Providers in cooldown are skipped. When ALL of them are cooling down
        # the backoff is respected, not bypassed: no fetch is attempted and the
        # offline sentinel is returned until a cooldown expires.
        if not active_providers:
            return self._offline_quote()

        fetchers = {
            "binance": self._fetch_binance_quote,
            "kraken": self._fetch_kraken_quote,
            "coinbase": self._fetch_coinbase_quote,
        }

        for name in active_providers:
            fetcher = fetchers.get(name)
            if not fetcher:
                continue
            quote = fetcher()
            if quote is not None:
                self.preferred_quote_provider = name
                self._quote_provider_cooldown.pop(name, None)
                return quote
            self._quote_provider_cooldown[name] = now + 15.0

        # Every live source failed: report offline. The engine pauses trading
        # and waits for the next retry instead of trading on a stale price.

        return self._offline_quote()

    @staticmethod
    def _offline_quote() -> LiveQuote:
        """Honest no-feed sentinel: price 0.00, flagged offline, never tradable."""
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

    def _is_quote_fresh(self, quote: Optional[LiveQuote], now: Optional[float] = None) -> bool:
        """A quote is tradable only while fresh. A stale cached quote is never
        traded as if live: on disconnect the engine pauses until a fresh
        quote arrives (offline mode removed, item 3)."""
        if quote is None or quote.is_offline or quote.price <= Decimal("0.00"):
            return False
        current = time.time() if now is None else now
        return (current - float(quote.timestamp)) <= QUOTE_STALE_SEC

    fetch_realtime_eth_quote = fetch_realtime_crypto_quote

    def bootstrap_intraday_session(self) -> None:
        """
        Loads the last 120 minutes of real 1-minute ETH/USD candles to warm up live indicators
        and immediately deploy the 6 strategies into the current live market session.
        First attempts cold-start hydration from SQLite WAL storage; if empty, queries live
        feed. If no real bars are available (offline), no bars are fabricated:
        the engine starts with an empty chart and waits for live quotes.
        """
        if self._stop_event.is_set():
            return
        recent_bars: List[CandleBar] = []
        cached_candles: List[Dict[str, Any]] = []
        is_fresh_cache = False
        try:
            cached_candles = self.storage.load_latest_candles(120)
            is_fresh_cache = bool(cached_candles) and (time.time() - float(cached_candles[-1]["t"])) < CANDLE_CACHE_STALE_SEC
            if len(cached_candles) >= 30 and is_fresh_cache:
                recent_bars = [
                    CandleBar(
                        timestamp=float(c["t"]),
                        open_=Decimal(str(c["o"])),
                        high=Decimal(str(c["h"])),
                        low=Decimal(str(c["l"])),
                        close=Decimal(str(c["c"])),
                        volume=Decimal(str(c.get("v", 15.0))),
                        ema_fast=Decimal(str(c["c"])),
                        ema_slow=Decimal(str(c["c"])),
                        rsi=Decimal("50.00"),
                        atr=Decimal("12.00"),
                    )
                    for c in cached_candles
                ]
        except Exception as e:
            logger.debug("SQLite candle cache hydration skipped: %s", e)

        if self._stop_event.is_set():
            return

        if not recent_bars:
            try:
                bars = ETHFeed.fetch_historical_bars(ticker="ETH-USD", period="1d", interval="1m")
                recent_bars = bars[-120:] if len(bars) > 120 else bars
            except Exception as e:
                logger.debug("Intraday bars fetch failed: %s", e)

        if self._stop_event.is_set():
            return

        # Prefer persisted SQLite cache (real data only) when the live feed is unreachable.
        # Same freshness rule as the first branch: a stale cache must never
        # become the opening bars, even as a fallback (P1: the old code
        # hydrated it unconditionally here).
        if not recent_bars and cached_candles and is_fresh_cache:
            recent_bars = [
                CandleBar(
                    timestamp=float(c["t"]),
                    open_=Decimal(str(c["o"])),
                    high=Decimal(str(c["h"])),
                    low=Decimal(str(c["l"])),
                    close=Decimal(str(c["c"])),
                    volume=Decimal(str(c.get("v", 15.0))),
                    ema_fast=Decimal(str(c["c"])),
                    ema_slow=Decimal(str(c["c"])),
                    rsi=Decimal("50.00"),
                    atr=Decimal("12.00"),
                )
                for c in cached_candles[-120:]
            ]

        if not recent_bars:
            # No real bars available (offline): do NOT fabricate candles.
            # The engine starts with an empty chart and waits for live quotes;
            # indicators stay at defaults until the feed reconnects.
            logger.info("Bootstrap: no real intraday bars available; waiting for live feed.")

        with self.lock:
            if self._stop_event.is_set():
                return

            for i, bar in enumerate(recent_bars):
                if self._stop_event.is_set():
                    return
                self.live_ema_fast = bar.ema_fast or bar.close
                self.live_ema_slow = bar.ema_slow or bar.close
                self.live_rsi = bar.rsi or Decimal("50.00")
                self.live_atr = max(Decimal("5.00"), bar.atr or Decimal("12.00"))
                self.broker.current_atr = self.live_atr

                # Historical warm-up simulation: only run simulated broker ticks if we do not already have a restored session
                if not self._has_restored_session:
                    fills = self.broker.on_tick(
                        price=bar.close,
                        high=bar.high,
                        low=bar.low,
                        timestamp=bar.timestamp,
                        open_price=bar.open
                    )
                    for f in fills:
                        if f.is_closing_fill:
                            self.strategy_cooldown[f.portfolio_id] = bar.timestamp + 60.0
                            self.position_entry_ts.pop(f.portfolio_id, None)
                        pnl_str = f" | PnL: ${f.realized_pnl:+.2f}" if f.is_closing_fill else ""
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

            # Rolling session typical-price mean (NOT volume-weighted VWAP:
            # the live loop recomputes the same unweighted mean every cadence,
            # so warmup uses the identical definition).
            if recent_bars:
                self.live_typical_mean = (
                    sum(((b.high + b.low + b.close) / Decimal("3")) for b in recent_bars) / Decimal(len(recent_bars))
                ).quantize(Decimal("0.01"))

            # Persist warmed-up 1m candles to SQLite WAL storage
            if not self._stop_event.is_set() and self._is_current_generation():
                try:
                    self.storage.save_candles_batch(self.candles)
                except Exception as e:
                    logger.debug("SQLite candle batch save skipped: %s", e)

            # Ensure all 6 distinct strategies are primed with historical simulation
            if recent_bars:
                last_b = recent_bars[-1]
                self.log_event(
                    "WARMUP_SYNC",
                    f"Replayed 120m intraday history ({len(recent_bars)} bars). Indicators & rankings primed. Waiting for UI reveal.",
                    "info"
                )

            # Clean up warmup simulation or auto-restore
            if not self._has_restored_session:
                # Purge any warmup-simulated positions so all competitor portfolios are pristine and FLAT
                for comp in self.competitors:
                    comp.portfolio.reset(self.initial_cash)
                    self.strategy_telemetry[comp.portfolio_id] = {
                        "strategy_type": self._get_strategy_label(comp.portfolio_id),
                        "intent": "Scanning orderflow & waiting for live reveal...",
                        "entry_rule": self._get_entry_rule_desc(comp.portfolio_id),
                        "stop_price": None,
                        "target_price": None,
                        "mc_stats": {},
                    }
                if hasattr(self, "broker"):
                    self.broker.active_stops.clear()
                    self.broker.active_targets.clear()
                    self.broker.execution_audit.clear()
                    self.broker.rejection_audit.clear()
                self._audit_cursor = 0
                self.fill_records.clear()
                self.live_logs = [log for log in self.live_logs if log.get("tag") not in ("BUY", "SELL", "STOP_LOSS", "TAKE_PROFIT")]
                self.strategy_cooldown.clear()
                self.position_entry_ts.clear()

                # Attempt auto-restore on real startup if snapshot exists and not in fast test mode
                if os.environ.get("ARENA_FAST_TEST") != "1":
                    try:
                        if self.restore_session_state():
                            self._has_restored_session = True
                    except Exception as e:
                        logger.debug("Auto restore session state skipped: %s", e)
            else:
                # Restored session already active: sync current market price to latest bar close
                if recent_bars:
                    last_price = recent_bars[-1].close
                    for comp in self.competitors:
                        if comp.portfolio.position_qty > Decimal("0"):
                            comp.portfolio.current_market_price = last_price

            if not self.live_orders_enabled:
                self.live_orders_enabled = False
                self.live_trading_active = False
                self.live_start_ts = None

            self.published_candles = [dict(c) for c in self.candles]
            self.published_quote = self.latest_quote
            self._raw_quote_cache = self.latest_quote
            self.last_cadence_ts = time.time()
            self.last_cadence_slot = int(self.last_cadence_ts // self.cadence_sec) * int(self.cadence_sec)
            self.macro_commander.ensure_traditional_chinese_seed_events()
            self.is_bootstrapped = True
            try:
                self._publish_state_snapshot()
            except Exception as e:
                logger.debug("State publish skipped during bootstrap: %s", e)
            try:
                if os.environ.get("ARENA_FAST_TEST") != "1":
                    threading.Thread(target=self.refresh_intel_digest, daemon=True).start()
            except Exception as e:
                logger.warning("Failed to start intel digest refresh thread: %s", e)

    def start_live_trading(self) -> Dict[str, Any]:
        """
        Activated only after the frontend verifies that the left K-line chart and right
        tactical tables are completely rendered and the initialization screen has faded out.
        """
        with self.lock:
            if not self.is_bootstrapped:
                logger.warning("start_live_trading rejected: engine is not bootstrapped yet.")
                return {"accepted": False, "reason": "Engine still bootstrapping"}

            has_restored_positions = any(c.portfolio.position_qty > Decimal("0") for c in self.competitors)

            if self.live_orders_enabled and has_restored_positions:
                self.live_trading_active = True
                if not self.live_start_ts:
                    self.live_start_ts = time.time()
                self._publish_state_snapshot()
                return {"accepted": True, "reason": "Live trading active with restored positions", "restored": True}

            self.live_orders_enabled = True
            self.live_trading_active = True
            if not self.live_start_ts:
                self.live_start_ts = time.time()

            if not has_restored_positions:
                # Clean slate: portfolios are flat
                if hasattr(self, "broker"):
                    self.broker.execution_audit.clear()
                    self.broker.rejection_audit.clear()
                self._audit_cursor = 0
                self.fill_records.clear()

                is_quote_online = bool(
                    self.latest_quote
                    and not getattr(self.latest_quote, "is_offline", False)
                    and self.latest_quote.price > Decimal("0")
                )

                if is_quote_online:
                    quote_p = self.latest_quote.price
                    self._ensure_active_live_positions(quote_p, self.live_start_ts)
                    self._harvest_fills()
                    self.log_event("ARENA_REVEALED", f"Arena initialization verified. Live order placement activated @ ${quote_p:,.2f}", "info")
                    self._publish_state_snapshot()
                    return {"accepted": True, "reason": "Live trading active", "restored": False}
                else:
                    self.log_event("ARENA_REVEALED", "Arena initialization verified. Live order placement active, awaiting live price ticks...", "info")
                    self._publish_state_snapshot()
                    return {"accepted": True, "reason": "Live trading active, awaiting online quote", "restored": False}
            else:
                self._publish_state_snapshot()
                return {"accepted": True, "reason": "Live trading active with restored positions", "restored": True}

    def refresh_intel_digest(self) -> Dict[str, Any]:
        """
        Triggers an AI-driven refresh of macro intelligence, synthesizing live/curated events
        through OmniRoute. Returns updated intel hub telemetry.
        """
        with self._intel_refresh_lock:
            if self._is_refreshing_intel:
                return self.macro_commander.get_intel_hub_telemetry()
            self._is_refreshing_intel = True
        self.last_intel_refresh_ts = time.time()
        try:
            loop = None
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                loop.create_task(self.macro_commander.refresh_digest_async())
            else:
                asyncio.run(self.macro_commander.refresh_digest_async())
        except Exception as e:
            logger.warning("Intel digest refresh error: %s", e)
        finally:
            with self._intel_refresh_lock:
                self._is_refreshing_intel = False
            try:
                self._publish_state_snapshot()
            except Exception as e:
                logger.debug("State publish skipped after intel refresh: %s", e)
        return self.macro_commander.get_intel_hub_telemetry()

    @staticmethod
    def _calc_ema(closes: List[float], period: int) -> float:
        return MultiTimeframeEngine.calc_ema(closes, period)

    def _update_mtf_regimes(self, new_1m_bar: Dict[str, Any]) -> None:
        """
        Aggregates 1m bars into 5m, 15m, and 1h buckets and updates Higher-Timeframe (HTF)
        EMA-50 / EMA-200 directional confluence.
        """
        self.mtf_engine.candles_5m = self.candles_5m
        self.mtf_engine.candles_15m = self.candles_15m
        self.mtf_engine.candles_1h = self.candles_1h
        self.mtf_engine.update_from_1m_bar(new_1m_bar)
        self.candles_5m = self.mtf_engine.candles_5m
        self.candles_15m = self.mtf_engine.candles_15m
        self.candles_1h = self.mtf_engine.candles_1h
        self.htf_ema_50 = self.mtf_engine.htf_ema_50
        self.htf_ema_200 = self.mtf_engine.htf_ema_200
        self.htf_bias = self.mtf_engine.htf_bias

    def is_entry_permitted_by_mtf(self, side: OrderSide) -> bool:
        """
        Blocks Long entries if 1h regime is strictly BEARISH,
        and blocks Short entries if 1h regime is strictly BULLISH.
        """
        if self.htf_bias == "BEARISH" and side == OrderSide.BUY:
            return False
        if self.htf_bias == "BULLISH" and side == OrderSide.SELL:
            return False
        return True

    def _live_indicators(self, price: Decimal) -> Dict[str, Any]:
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

    def _sizing_multiplier_for(self, competitor: Any) -> Decimal:
        """Per-strategy news sizing factor for one entry (item 12C / C2).

        The same factor the strategy's evaluate_signal receives, so the TP
        stretch below and the position size use one consistent number.
        Unknown competitors (mocks without a genome) read as 0.5.
        """
        sens = getattr(getattr(competitor, "genome", None), "news_sensitivity", 0.5)
        try:
            sens_f = float(sens)
        except (TypeError, ValueError):
            sens_f = 0.5
        return Decimal(str(self.macro_commander.news_sizing_multiplier(sens_f)))

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
        ticket: Optional[OrderTicket] = None
    ) -> bool:
        pid = competitor.portfolio_id

        # Ticket path (live entries routed through evaluate_signal): the
        # strategy already built SL / TP / qty; the gates below run on it.
        if ticket is not None:
            side = ticket.side
            sl = ticket.stop_loss
            tp = ticket.take_profit

        # Close ticket (SIGNAL_EXIT): exits an existing position. Entry-only
        # gates (MTF, macro veto, MC EV gate) do not apply to a risk-reducing
        # close, and there is no SL/TP bracket to evaluate (the MC gate would
        # crash on stop_loss=None). Route it straight to the broker so a
        # position can always be exited, even under HOLD_CASH (item 6).
        if ticket is not None and ticket.reason == ExecutionReason.SIGNAL_EXIT:
            if ticket.qty <= Decimal("0"):
                return False
            fill = self.broker.submit_order(ticket)
            if fill:
                self.strategy_cooldown[pid] = ts + 60.0
                self.position_entry_ts.pop(pid, None)
                self.log_event(event_label, f"{competitor.base_name.split(' ')[0]} closed {fill.qty} ETH @ ${fill.price:,.2f} (PnL ${fill.realized_pnl:+.2f})", "profit" if fill.realized_pnl >= 0 else "loss")
                return True
            return False

        # Phase 4: Multi-Timeframe (1h) Trend Confluence Gatekeeper
        if not self.is_entry_permitted_by_mtf(side):
            self.strategy_cooldown[pid] = ts + 20.0
            self.strategy_telemetry[pid]["intent"] = f"MTF Veto: 1h {self.htf_bias}"
            self.log_event("VETO_MTF", f"{competitor.base_name.split(' ')[0]} {side.value} blocked by 1h {self.htf_bias} regime", "loss")
            return False

        # Strict Veto Gate (Macro Commander Option A). Only opening orders
        # reach this point (close tickets take the fast-path above), so the
        # veto is explicitly told this is an open (item 6).
        allowed, veto_reason = self.macro_commander.check_trade_veto(side, competitor.base_name, is_close=False)
        if not allowed:
            self.strategy_cooldown[pid] = ts + 20.0
            self.strategy_telemetry[pid]["intent"] = f"Macro Veto: {self.macro_commander.current_state.directional_bias}"
            self.log_event("VETO_MACRO", f"{competitor.base_name.split(' ')[0]} {side.value} vetoed: {veto_reason}", "loss")
            self.macro_commander.record_strategy_action(
                pid, competitor.base_name.split(' ')[0],
                f"{side.value} Blocked by Macro Veto ({self.macro_commander.current_state.directional_bias})",
                "loss",
                is_macro_action=True,
            )
            return False

        # Macro Trend Take-Profit Expansion (item 12C / C2): TP stretches by
        # the same per-strategy news sizing factor the position size uses,
        # so an optimistic-but-unconfident regime no longer stretches TP.
        sizing_mult = self._sizing_multiplier_for(competitor)
        if tp is not None and sizing_mult > Decimal("1.0"):
            if side == OrderSide.BUY and self.macro_commander.current_state.directional_bias == "LONG_ONLY":
                r_dist = price - sl
                tp = (price + r_dist * Decimal(str(round(2.0 * float(sizing_mult), 2)))).quantize(Decimal("0.01"))
            elif side == OrderSide.SELL and self.macro_commander.current_state.directional_bias == "SHORT_ONLY":
                r_dist = sl - price
                tp = (price - r_dist * Decimal(str(round(2.0 * float(sizing_mult), 2)))).quantize(Decimal("0.01"))

        mc_odds = self.mc_evaluator.evaluate_bracket(price, sl, tp, atr=self.live_atr, recent_candles=self.candles)
        self.strategy_telemetry[pid]["mc_stats"] = mc_odds.to_dict()
        if not mc_odds.passed:
            self.strategy_cooldown[pid] = ts + 20.0
            # A1: with NumPy missing the odds are unknown (None), not numbers;
            # comparing None would raise here, so report "unknown" instead.
            if mc_odds.neither_prob is None or mc_odds.green_prob is None or mc_odds.decided_win_rate is None:
                win_txt = "unknown"
            else:
                display_win = mc_odds.green_prob if mc_odds.neither_prob > 0.40 else mc_odds.decided_win_rate
                win_txt = f"{display_win*100:.0f}%"
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
                portfolio_id=pid, symbol=self.symbol, side=side,
                order_type=OrderType.MARKET, qty=qty, stop_loss=sl, take_profit=tp, timestamp=ts
            )

        fill = self.broker.submit_order(ticket)
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
        # Rejected by the broker (RiskGuard): do not retry every cadence
        # -- that would spam rejection_audit forever. Same 20 s breather
        # as the MTF / macro-veto / EV-gate rejections above.
        self.strategy_cooldown[pid] = ts + 20.0
        return False

    def _evaluate_live_strategies(self, price: Decimal, prev_price: Decimal, ts: float) -> None:
        """
        Executes differentiated real-time decision logic for each of the 6 strategies on every live tick/bar.
        Incorporates bidirectional Long & Short setups, anti-churn cooldowns, channel stagnation exits,
        and dynamic volatility adaptation.

        Exits: profit-taking is owned by the genome brackets
        (BrokerSim.active_targets, evaluated by on_tick every cadence);
        the per-strategy blocks below close only on signal reversals.
        (Audit 2.1: the hardcoded +0.25%/+0.15%/+0.35%/+0.30% and ATR
        max($8, 1.4xATR) profit caps were removed -- they fired long
        before the genome TP and made evolution tune a TP that never ran.)
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
            if (is_uptrend and vel > Decimal("0") and self.live_rsi < Decimal("68")) or (vel > self.live_atr * Decimal("0.25")):
                self._enter_via_strategy(self.comp_a, price, ts, "BREAKOUT_LONG", side=OrderSide.BUY)
            elif ((not is_uptrend) and vel < Decimal("0") and self.live_rsi > Decimal("32")) or (vel < -self.live_atr * Decimal("0.25")):
                self._enter_via_strategy(self.comp_a, price, ts, "BREAKDOWN_SHORT", side=OrderSide.SELL)

            if p_agg.position_qty == Decimal("0") and not self.strategy_telemetry["comp_agg"]["intent"].startswith(("EV Gate", "Macro Veto")):
                self.strategy_telemetry["comp_agg"]["intent"] = f"Scanning breakout / breakdown near ${self.live_ema_fast:,.2f}"
        else:
            entry_p = p_agg.avg_entry_price
            if entry_p > Decimal("0"):
                if p_agg.position_side == PositionSide.SHORT:
                    gain_usd = entry_p - price
                    if self.live_ema_fast > self.live_ema_slow and self.live_rsi > Decimal("52") and gain_usd >= (self.live_atr * Decimal("0.5")):
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
                    if self.live_ema_fast < self.live_ema_slow and self.live_rsi < Decimal("48") and gain_usd >= (self.live_atr * Decimal("0.5")):
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
            # Bracket now comes from the strategy's own evaluate_signal
            # (genome SL 1.0% / TP 1.8%); the live 0.6% / 0.9% caps are gone
            # so backtest and live finally trade the same bracket.
            if self.live_rsi <= Decimal("52.0") and vel >= Decimal("0"):
                self._enter_via_strategy(self.comp_b, price, ts, "SCALP_LONG", side=OrderSide.BUY)
            elif self.live_rsi >= Decimal("58.0") and vel <= Decimal("0"):
                self._enter_via_strategy(self.comp_b, price, ts, "SCALP_SHORT", side=OrderSide.SELL)
        else:
            entry_p = p_cons.avg_entry_price
            if entry_p > Decimal("0"):
                if p_cons.position_side == PositionSide.SHORT:
                    gain_usd = entry_p - price
                    if price <= self.live_ema_fast and gain_usd >= (self.live_atr * Decimal("0.5")):
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
                    if price >= self.live_ema_fast and gain_usd >= (self.live_atr * Decimal("0.5")):
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
            # Bracket (ATR stop/target + risk budget) now comes from the
            # strategy's own evaluate_signal; the live $5/$10 floors are gone.
            if (price >= self.live_ema_fast and vel > Decimal("0")) or self.live_rsi < Decimal("42"):
                self._enter_via_strategy(self.comp_c, price, ts, "ATR_ADAPT_LONG", side=OrderSide.BUY)
            elif (price <= self.live_ema_fast and vel < Decimal("0")) or self.live_rsi > Decimal("58"):
                self._enter_via_strategy(self.comp_c, price, ts, "ATR_ADAPT_SHORT", side=OrderSide.SELL)
        # No per-tick exit block (audit 2.1): ATR exits via its genome
        # bracket (SL 1.5xATR / TP 2.5xATR) through broker.on_tick. The old
        # max($8, 1.4xATR) cap fired before the genome TP (1.4xATR <
        # 2.5xATR) and was a duplicate exit path with no signal content,
        # so it is deleted rather than kept.

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
                    if gain_pct >= g_trail.trailing_trigger_pct:
                        self.comp_d.trailing_active = True
                        new_sl = (self.comp_d.lowest_price_since_entry * (Decimal("1") + g_trail.trailing_distance_pct)).quantize(Decimal("0.01"))
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
                    if gain_pct >= g_trail.trailing_trigger_pct:
                        self.comp_d.trailing_active = True
                        new_sl = (self.comp_d.highest_price_since_entry * (Decimal("1") - g_trail.trailing_distance_pct)).quantize(Decimal("0.01"))
                        curr_stop = self.broker.active_stops.get("comp_trail")
                        if curr_stop and (curr_stop.price is None or new_sl > curr_stop.price):
                            self.broker.active_stops["comp_trail"] = OrderTicket(
                                portfolio_id="comp_trail", symbol=self.symbol, side=OrderSide.SELL,
                                order_type=OrderType.STOP_MARKET, qty=p_trail.position_qty,
                                price=new_sl, reason=ExecutionReason.TRAILING_STOP, timestamp=ts
                            )
                            self.log_event("TRAIL_RATCHET", f"Trailing Guard raised stop -> ${new_sl:,.2f} (Peak ${self.comp_d.highest_price_since_entry:,.2f})", "info")
        else:
            # Entry bracket (genome SL 1.5%, uncapped) now comes from the
            # strategy's own evaluate_signal; the live 0.9% guard is gone.
            # evaluate_signal also arms highest/lowest on entry.
            if vel >= Decimal("0") and self.live_rsi < Decimal("66") and (is_uptrend or self.live_rsi <= Decimal("50")):
                self._enter_via_strategy(self.comp_d, price, ts, "TRAIL_LONG", side=OrderSide.BUY)
            elif vel <= Decimal("0") and self.live_rsi > Decimal("34") and ((not is_uptrend) or self.live_rsi >= Decimal("50")):
                self._enter_via_strategy(self.comp_d, price, ts, "TRAIL_SHORT", side=OrderSide.SELL)

        # --- 5. Opening Range Breakout (comp_orb) ---
        p_orb = self.comp_e.portfolio
        g_orb = self.comp_e.genome
        orb_high = self.live_orb_high if self.live_orb_high > Decimal("0") else (price * Decimal("1.002"))
        orb_low = self.live_orb_low if self.live_orb_low > Decimal("0") else (price * Decimal("0.998"))
        orb_mid = ((orb_high + orb_low) / Decimal("2")).quantize(Decimal("0.01"))

        if p_orb.position_qty == Decimal("0"):
            is_breakout = (price >= orb_high and vel >= Decimal("0")) or (price > orb_mid and is_uptrend and vel > self.live_atr * Decimal("0.2"))
            is_breakdown = (price <= orb_low and vel <= Decimal("0")) or (price < orb_mid and (not is_uptrend) and vel < -self.live_atr * Decimal("0.2"))
            # Bracket (midpoint SL, 2.0R) now comes from the strategy's own
            # evaluate_signal; the live $50/ATR*1.2 SL floor is gone.
            if is_breakout and self.live_rsi < Decimal("72"):
                self._enter_via_strategy(self.comp_e, price, ts, "ORB_LONG", side=OrderSide.BUY)
            elif is_breakdown and self.live_rsi > Decimal("28"):
                self._enter_via_strategy(self.comp_e, price, ts, "ORB_SHORT", side=OrderSide.SELL)

            if p_orb.position_qty == Decimal("0") and not self.strategy_telemetry["comp_orb"]["intent"].startswith(("EV Gate", "Macro Veto")):
                self.strategy_telemetry["comp_orb"]["intent"] = f"Watching ORB High ${orb_high:,.2f} / Low ${orb_low:,.2f} (Mid ${orb_mid:,.2f})"
        else:
            entry_p = p_orb.avg_entry_price
            if entry_p > Decimal("0"):
                if p_orb.position_side == PositionSide.SHORT:
                    gain_usd = entry_p - price
                    if price > orb_mid and gain_usd >= (self.live_atr * Decimal("0.5")):
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
                    if price < orb_mid and gain_usd >= (self.live_atr * Decimal("0.5")):
                        fill = self.broker.submit_order(OrderTicket(
                            portfolio_id="comp_orb", symbol=self.symbol, side=OrderSide.SELL,
                            order_type=OrderType.MARKET, qty=p_orb.position_qty,
                            reason=ExecutionReason.TAKE_PROFIT, timestamp=ts
                        ))
                        if fill:
                            self.strategy_cooldown["comp_orb"] = ts + 60.0
                            self.position_entry_ts.pop("comp_orb", None)
                            self.log_event("ORB_TP", f"ORB locked long target {fill.qty} ETH @ ${fill.price:,.2f} (+${fill.realized_pnl:+.2f})", "profit")

        # --- 6. Session Mean Pullback (comp_vwap) ---
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
                self.strategy_telemetry["comp_vwap"]["intent"] = f"Awaiting session-mean bounce / rejection near ${mean_ref:,.2f}"
        else:
            entry_p = p_vwap.avg_entry_price
            if entry_p > Decimal("0"):
                if p_vwap.position_side == PositionSide.SHORT:
                    gain_usd = entry_p - price
                    if price <= (mean_ref - self.live_atr * Decimal("1.5")) and gain_usd >= (self.live_atr * Decimal("0.6")):
                        fill = self.broker.submit_order(OrderTicket(
                            portfolio_id="comp_vwap", symbol=self.symbol, side=OrderSide.BUY,
                            order_type=OrderType.MARKET, qty=p_vwap.position_qty,
                            reason=ExecutionReason.TAKE_PROFIT, timestamp=ts
                        ))
                        if fill:
                            self.strategy_cooldown["comp_vwap"] = ts + 60.0
                            self.position_entry_ts.pop("comp_vwap", None)
                            self.log_event("MEAN_TP", f"VWAP locked short profit {fill.qty} ETH @ ${fill.price:,.2f} (+${fill.realized_pnl:+.2f})", "profit")
                else:
                    gain_usd = price - entry_p
                    if price >= (mean_ref + self.live_atr * Decimal("1.5")) and gain_usd >= (self.live_atr * Decimal("0.6")):
                        fill = self.broker.submit_order(OrderTicket(
                            portfolio_id="comp_vwap", symbol=self.symbol, side=OrderSide.SELL,
                            order_type=OrderType.MARKET, qty=p_vwap.position_qty,
                            reason=ExecutionReason.TAKE_PROFIT, timestamp=ts
                        ))
                        if fill:
                            self.strategy_cooldown["comp_vwap"] = ts + 60.0
                            self.position_entry_ts.pop("comp_vwap", None)
                            self.log_event("MEAN_TP", f"VWAP locked long profit {fill.qty} ETH @ ${fill.price:,.2f} (+${fill.realized_pnl:+.2f})", "profit")

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
        mean_ref = self.live_typical_mean if self.live_typical_mean > Decimal("0") else (self.live_ema_slow if self.live_ema_slow > Decimal("0") else price)

        # 1. Aggressive
        if self.comp_a.portfolio.position_qty == Decimal("0") and ts >= self.strategy_cooldown.get("comp_agg", 0.0):
            if is_uptrend:
                sl = (price * (Decimal("1") - self.comp_a.genome.stop_loss_pct)).quantize(Decimal("0.01"))
                tp = (price * (Decimal("1") + self.comp_a.genome.take_profit_pct)).quantize(Decimal("0.01")) if self.comp_a.genome.take_profit_pct else None
                self._try_enter_bracket(self.comp_a, price, sl, tp, ts, "BREAKOUT_LONG", side=OrderSide.BUY)
            else:
                sl = (price * (Decimal("1") + self.comp_a.genome.stop_loss_pct)).quantize(Decimal("0.01"))
                tp = (price * (Decimal("1") - self.comp_a.genome.take_profit_pct)).quantize(Decimal("0.01")) if self.comp_a.genome.take_profit_pct else None
                self._try_enter_bracket(self.comp_a, price, sl, tp, ts, "BREAKDOWN_SHORT", side=OrderSide.SELL)

        # 2. Conservative
        if self.comp_b.portfolio.position_qty == Decimal("0") and ts >= self.strategy_cooldown.get("comp_cons", 0.0):
            if self.live_rsi > Decimal("52.0"):
                sl = (price * Decimal("1.006")).quantize(Decimal("0.01"))
                tp = (price * Decimal("0.991")).quantize(Decimal("0.01"))
                self._try_enter_bracket(self.comp_b, price, sl, tp, ts, "SCALP_SHORT", side=OrderSide.SELL)
            else:
                sl = (price * Decimal("0.994")).quantize(Decimal("0.01"))
                tp = (price * Decimal("1.009")).quantize(Decimal("0.01"))
                self._try_enter_bracket(self.comp_b, price, sl, tp, ts, "SCALP_LONG", side=OrderSide.BUY)

        # 3. ATR Dynamic
        if self.comp_c.portfolio.position_qty == Decimal("0") and ts >= self.strategy_cooldown.get("comp_atr", 0.0):
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
        if self.comp_d.portfolio.position_qty == Decimal("0") and ts >= self.strategy_cooldown.get("comp_trail", 0.0):
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
        if self.comp_e.portfolio.position_qty == Decimal("0") and ts >= self.strategy_cooldown.get("comp_orb", 0.0):
            if price >= orb_mid:
                sl = (price * Decimal("0.992")).quantize(Decimal("0.01"))
                tp = (price + (price - sl) * Decimal("2.0")).quantize(Decimal("0.01"))
                self._try_enter_bracket(self.comp_e, price, sl, tp, ts, "ORB_LONG", side=OrderSide.BUY)
            else:
                sl = (price * Decimal("1.008")).quantize(Decimal("0.01"))
                tp = (price - (sl - price) * Decimal("2.0")).quantize(Decimal("0.01"))
                self._try_enter_bracket(self.comp_e, price, sl, tp, ts, "ORB_SHORT", side=OrderSide.SELL)

        # 6. Session Mean Pullback
        if self.comp_f.portfolio.position_qty == Decimal("0") and ts >= self.strategy_cooldown.get("comp_vwap", 0.0):
            if price >= mean_ref:
                sl = (price * Decimal("0.993")).quantize(Decimal("0.01"))
                tp = (price + (price - sl) * Decimal("2.2")).quantize(Decimal("0.01"))
                self._try_enter_bracket(self.comp_f, price, sl, tp, ts, "MEAN_LONG", side=OrderSide.BUY)
            else:
                sl = (price * Decimal("1.007")).quantize(Decimal("0.01"))
                tp = (price - (sl - price) * Decimal("2.2")).quantize(Decimal("0.01"))
                self._try_enter_bracket(self.comp_f, price, sl, tp, ts, "MEAN_SHORT", side=OrderSide.SELL)

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
                    intent = f"MEAN {pos_dir} {p.position_qty} ETH @ ${p.avg_entry_price:,.2f} | 2.2R Target ${tp_p:,.2f}" if tp_p else f"{pos_dir} {p.position_qty} ETH"
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
        """Aggregates a bar or tick into the 1-minute candle it belongs to, updates MTF regimes, and persists."""
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

        if self.candles:
            self._update_mtf_regimes(self.candles[-1])
            if self.is_bootstrapped and self._is_current_generation():
                try:
                    self.storage.save_candle(self.candles[-1])
                except Exception as e:
                    logger.debug("SQLite candle save skipped: %s", e)

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
        self.broker.current_atr = self.live_atr

        if len(cs) >= 15:
            first_15 = cs[:15]
            self.live_orb_high = Decimal(str(round(max(x["h"] for x in first_15), 2)))
            self.live_orb_low = Decimal(str(round(min(x["l"] for x in first_15), 2)))
        elif cs:
            self.live_orb_high = Decimal(str(round(max(x["h"] for x in cs), 2)))
            self.live_orb_low = Decimal(str(round(min(x["l"] for x in cs), 2)))

        if cs:
            # Session typical-price mean over the last <=200 1m candles.
            # Deliberately NOT called VWAP: these candles carry no volume,
            # so no volume weighting is possible here.
            cum_p = sum((x["h"] + x["l"] + x["c"]) / 3.0 for x in cs)
            self.live_typical_mean = Decimal(str(round(cum_p / len(cs), 2)))

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
        while self.running and not self._stop_event.is_set():
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
            for _ in range(10):
                if not self.running or self._stop_event.is_set():
                    break
                time.sleep(0.1)

    def start_live_loop(self, interval_sec: float = 1.0) -> None:
        if self.running:
            return
        # A previous worker thread that has not exited yet (stop() only
        # joins up to 3 s) must never be joined by a second live loop on
        # the same engine: the old thread would see running=True again
        # and resume ticking alongside the new one.
        if self.worker_thread is not None and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=3.0)
            if self.worker_thread.is_alive():
                logger.warning("Previous live loop thread still alive; refusing to start a second one")
                return
        self.cadence_sec = max(1.0, min(10.0, float(interval_sec)))
        self._stop_event.clear()
        self.running = True
        self.worker_thread = threading.Thread(target=self._live_loop, daemon=True)
        self.worker_thread.start()

    def stop_live_loop(self, timeout: float = 3.0) -> None:
        self.running = False
        self._stop_event.set()
        self.ws_feed.stop()
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=timeout)
        if self.worker_thread and not self.worker_thread.is_alive():
            self.worker_thread = None
        if self.raw_fetch_thread and self.raw_fetch_thread.is_alive():
            self.raw_fetch_thread.join(timeout=timeout)
        if self.raw_fetch_thread and not self.raw_fetch_thread.is_alive():
            self.raw_fetch_thread = None
        # Release the quote session's keep-alive pool: every reset_engine
        # builds a new engine (and a new Session), so an unclosed session
        # leaks pooled connections until GC. The session stays usable
        # afterwards (requests re-opens pools lazily) if this engine is
        # ever started again.
        try:
            self.session.close()
        except Exception as e:
            logger.debug("Quote session close failed during stop: %s", e)
        # Release the persistent SQLite connection too: every
        # reset_engine builds a new engine (and a new ArenaStorage),
        # so an unclosed connection would hold the database file
        # handle until GC. The storage reopens lazily on next use,
        # so restarting this same engine after stop() still works.
        try:
            self.storage.close()
        except Exception as e:
            logger.debug("Storage close failed during stop: %s", e)

    def stop(self) -> None:
        self.stop_live_loop()

    def _live_loop(self) -> None:
        self.log_event("BOOT", "Connecting to real-time ETH/USD orderflow & warming 1m indicators...", "info")
        self.ws_feed.start()
        self.bootstrap_intraday_session()
        if not self.running or self._stop_event.is_set():
            return

        with self.lock:
            if self.live_orders_enabled and self.live_start_ts is None:
                self.live_start_ts = time.time()
            self.last_evolve_ts = time.time()
            self.last_cadence_slot = int(time.time() // self.cadence_sec) * int(self.cadence_sec)

        # Start hidden raw quote fetcher in background
        self.raw_fetch_thread = threading.Thread(target=self._quote_fetch_worker, daemon=True)
        self.raw_fetch_thread.start()

        while self.running and not self._stop_event.is_set():
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

                        if self._is_quote_fresh(raw, now):
                            if not self.market_online:
                                self.market_online = True
                                self.log_event("FEED_ONLINE", "Market feed reconnected: trading resumed.", "success")
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
                                    if not self.live_start_ts:
                                        self.live_start_ts = time.time()
                                    self.last_evolve_ts = time.time()
                                    self._ensure_active_live_positions(cadenced_quote.price, float(current_slot))
                                    self._harvest_fills()
                                    self.log_event("LIVE_START", f"Arena revealed. Live order dispatch active @ ${cadenced_quote.price:,.2f}", "buy")

                                fills = self.broker.on_tick(
                                    price=cadenced_quote.price,
                                    high=max(high_p, cadenced_quote.price, cadenced_quote.ask),
                                    low=min(low_p, cadenced_quote.price, cadenced_quote.bid),
                                    timestamp=float(current_slot),
                                    open_price=prev_p
                                )
                                for f in fills:
                                    if f.is_closing_fill:
                                        self.strategy_cooldown[f.portfolio_id] = float(current_slot) + 60.0
                                        self.position_entry_ts.pop(f.portfolio_id, None)
                                    pnl_str = f" (PnL: ${f.realized_pnl:+.2f})" if f.is_closing_fill else ""
                                    self.log_event(
                                        f.reason.value,
                                        f"{f.portfolio_id.upper()} {f.side.value} {f.qty} ETH @ ${f.price:,.2f}{pnl_str}",
                                        "profit" if f.realized_pnl >= Decimal("0") else "loss"
                                    )
                                    strat_name = self.STRATEGY_SHORT.get(f.portfolio_id, f.portfolio_id)
                                    if f.is_closing_fill:
                                        close_verb = "Covered SHORT" if f.position_side == PositionSide.SHORT else "Closed LONG"
                                        self.macro_commander.record_strategy_action(
                                            f.portfolio_id,
                                            strat_name,
                                            f"{close_verb} {f.qty} ETH @ ${f.price:,.2f} ({f.reason.value}{pnl_str})",
                                            "profit" if f.realized_pnl >= Decimal("0") else "loss"
                                        )

                                if not self.position_entry_ts and all(c.portfolio.position_qty == Decimal("0") for c in self.competitors):
                                    self._ensure_active_live_positions(cadenced_quote.price, float(current_slot))

                                # All 6 strategies evaluated strictly on the 5-second interval
                                self._evaluate_live_strategies(cadenced_quote.price, prev_p, float(current_slot))

                            self._record_series_point(cadenced_quote.price, float(current_slot))
                        elif self.market_online:
                            self.market_online = False
                            self.log_event("FEED_OFFLINE", "Market feed offline: trading paused, waiting to reconnect...", "loss")

                        if self.live_orders_enabled:
                            _evolve_reason = self._auto_evolve_reason()
                            if _evolve_reason is not None:
                                self.evolve_now(trigger=f"auto:{_evolve_reason}")

                        # Publish updated double-buffered state snapshot for lock-free UI IPC consumption
                        self._publish_state_snapshot()

                        # Automated periodic background intelligence digest refresh (every 5m / 300s;
                        # slowed to >= 900s while the daily token quota is exceeded, item 12 / A4-4)
                        if (now - self.last_intel_refresh_ts) >= self.macro_commander.digest_interval_sec(self.intel_refresh_interval_sec) and not self._is_refreshing_intel:
                            if os.environ.get("ARENA_FAST_TEST") != "1":
                                threading.Thread(target=self.refresh_intel_digest, daemon=True).start()

                except Exception as e:
                    self.log_event("FEED_WARN", f"Retrying live quote stream: {e}", "loss")

            time.sleep(0.1)  # High-frequency sleep to hit exact 5-second wall clock slot without drift

    @property
    def paused(self) -> bool:
        return self._paused

    @paused.setter
    def paused(self, value: bool) -> None:
        val = bool(value)
        if getattr(self, "_paused", False) == val:
            return
        now = time.time()
        with self.lock:
            self._paused = val
            if val:
                self._pause_start_ts = now
                self.log_event("ENGINE", "Simulation & Evolution Timer PAUSED", "info")
            else:
                if getattr(self, "_pause_start_ts", None) is not None:
                    paused_dur = max(0.0, now - self._pause_start_ts)
                    self.last_evolve_ts += paused_dur
                    self._pause_start_ts = None
                    # Ticks that arrived while paused are stale: they must
                    # not be aggregated into the first post-resume candle.
                    self._slice_ticks.clear()
                self.log_event("ENGINE", "Simulation & Evolution Timer RESUMED", "info")
        self._publish_state_snapshot()

    def toggle_pause(self) -> bool:
        self.paused = not self.paused
        return self.paused

    def _auto_evolve_reason(self, now: Optional[float] = None) -> Optional[str]:
        """Why auto-evolution is due now: 'time' (6h cap), 'trades'
        (30 closed trades + 30min debounce), or None when not due."""
        if self.paused:
            return None
        now = time.time() if now is None else now
        if not self.auto_evolve_enabled or self.latest_quote is None:
            return None
        elapsed = now - self.last_evolve_ts
        if elapsed >= self.auto_evolve_interval_sec:
            return "time"
        if (
            elapsed >= self.auto_evolve_debounce_sec
            and self._closed_trades_since_evolve >= self.auto_evolve_closed_trades
        ):
            return "trades"
        return None

    def _auto_evolve_due(self, now: Optional[float] = None) -> bool:
        return self._auto_evolve_reason(now) is not None

    def toggle_auto_evolve(self) -> bool:
        with self.lock:
            self.auto_evolve_enabled = not self.auto_evolve_enabled
            now = time.time()
            if not self.auto_evolve_enabled:
                self._auto_evolve_disabled_ts = now
            else:
                if getattr(self, "_auto_evolve_disabled_ts", None) is not None:
                    disabled_dur = max(0.0, now - self._auto_evolve_disabled_ts)
                    self.last_evolve_ts += disabled_dur
                    self._auto_evolve_disabled_ts = None
            hours = self.auto_evolve_interval_sec / 3600.0
            hrs_text = f"{hours:g}h" if hours >= 1 else f"{self.auto_evolve_interval_sec // 60}m"
            status_text = f"Enabled (Every {hrs_text})" if self.auto_evolve_enabled else "Disabled (Manual only)"
            self.log_event("CONFIG", f"Auto Evolution: {status_text}", "info")
        self._publish_state_snapshot()
        return self.auto_evolve_enabled

    def set_auto_evolve_interval(self, seconds: int) -> int:
        with self.lock:
            self.auto_evolve_interval_sec = max(60, int(seconds))
            hours = self.auto_evolve_interval_sec / 3600.0
            hrs_text = f"{hours:g}h" if hours >= 1 else f"{self.auto_evolve_interval_sec // 60}m"
            self.log_event("CONFIG", f"Auto Evolution Interval set to {hrs_text} ({self.auto_evolve_interval_sec}s)", "info")
        self._publish_state_snapshot()
        return self.auto_evolve_interval_sec

    def set_cadence_interval(self, seconds: float) -> float:
        with self.lock:
            self.cadence_sec = max(1.0, min(10.0, float(seconds)))
            self.log_event("CONFIG", f"Candlestick output cadence set to {self.cadence_sec:.1f}s", "info")
        self._publish_state_snapshot()
        return self.cadence_sec

    def set_intel_refresh_interval(self, seconds: float) -> float:
        with self.lock:
            self.intel_refresh_interval_sec = max(30.0, float(seconds))
            self.log_event("CONFIG", f"Macro intelligence refresh interval set to {self.intel_refresh_interval_sec:.0f}s", "info")
        self._publish_state_snapshot()
        return self.intel_refresh_interval_sec

    def evolve_now(self, trigger: str = "manual") -> List[str]:
        if not self._is_current_generation():
            logger.warning("Stale engine epoch %.3f: refusing to evolve from a superseded generation", self.engine_epoch)
            return []
        if self._stop_event.is_set():
            logger.warning("Engine stopped: refusing to evolve after shutdown")
            return []
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
            self._closed_trades_since_evolve = 0
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

    # High-contrast vibrant Stageshow palette: vivid pop on ultra-deep obsidian #060709
    STRATEGY_COLORS: Dict[str, str] = {
        "comp_agg": "#FF334B",    # Neon Coral (Aggressive Momentum)
        "comp_cons": "#38BDF8",   # Electric Sky Cyan (Conservative Scalper)
        "comp_atr": "#FFB800",    # Electric Amber Gold (ATR Dynamic)
        "comp_trail": "#00E676",  # Neon Emerald Green (Trailing Guard)
        "comp_orb": "#A855F7",    # Electric Violet (ORB Breakout)
        "comp_vwap": "#14F195",   # Mint Teal (Session Mean)
    }
    STRATEGY_SHORT: Dict[str, str] = {
        "comp_agg": "AGG",
        "comp_cons": "CONS",
        "comp_atr": "ATR",
        "comp_trail": "TRAIL",
        "comp_orb": "ORB",
        "comp_vwap": "MEAN",
    }
    STRATEGY_DISPLAY: Dict[str, str] = {
        "comp_agg": "Aggressive Momentum",
        "comp_cons": "Conservative Scalper",
        "comp_atr": "ATR Dynamic",
        "comp_trail": "Trailing Guard",
        "comp_orb": "ORB Breakout (15m)",
        "comp_vwap": "Session Mean",
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
        """Delegates JSON view-model extraction to the modular ViewModelPublisher."""
        return build_engine_view_model(self, rankings, gen)

    def _build_snapshot_locked(self) -> Dict[str, Any]:
        """Constructs full UI state dictionary while holding engine lock."""
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
                "typical_mean": float(self.live_typical_mean),
                "orb_high": float(self.live_orb_high),
                "orb_low": float(self.live_orb_low),
                "rsi": float(self.live_rsi),
                "atr": float(self.live_atr),
            },
        }
        state.update(self._build_view_model(rankings, gen))
        return state

    def _publish_state_snapshot(self) -> None:
        """
        Atomically publishes double-buffered UI snapshot for lock-free IPC consumption.
        Called at the completion of each cadence evaluation or state-changing command.
        """
        if not self._is_current_generation():
            logger.debug("Stale engine epoch %.3f: skipping state publish from a superseded generation", self.engine_epoch)
            return
        snapshot = self._build_snapshot_locked()
        with self._snapshot_lock:
            self._ui_state_snapshot = snapshot

    def get_ui_state(self) -> Dict[str, Any]:
        """
        Retrieves current UI state. If a double-buffered snapshot is available,
        returns a defensive copy immediately without acquiring `self.lock`, avoiding IPC thread stalls
        and preventing callers from mutating internal engine state.
        """
        with self._snapshot_lock:
            snap = self._ui_state_snapshot
        if snap is not None:
            return copy.deepcopy(snap)
        with self.lock:
            return copy.deepcopy(self._build_snapshot_locked())

    def get_ui_state_delta(self, force_full: bool = False) -> Dict[str, Any]:
        """
        Phase 6: Diff-based IPC state delta publisher with lock-free double buffering.
        Omits unchanged `candles` and `fills` arrays on consecutive polls.
        """
        full_state = self.get_ui_state()
        return self.view_publisher.compute_delta_payload(full_state, force_full=force_full)

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
        }

    @staticmethod
    def _deserialize_ticket(data: Any) -> Optional[Any]:
        from src.arena.broker_sim import OrderTicket, OrderSide, OrderType
        if data is None:
            return None
        if isinstance(data, OrderTicket):
            return data
        if isinstance(data, (int, float, Decimal, str)):
            # A bare number carries no quantity, so it would deserialize
            # to a qty=0 ticket; a zero-size ticket must never be mounted
            # as a live stop/target in the broker (P0 fix: restore used
            # to mount it because OrderTicket has no __bool__).
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
                # Garbage numbers in one saved ticket must not abort the
                # whole session restore (F3): drop this ticket only.
                logger.debug("Dropping ticket with unparseable numbers: %s (%s)", data, e)
                return None
            if qty_val <= Decimal("0"):
                # A zero/negative-size ticket is not a valid bracket: drop
                # it instead of letting restore mount it as a live stop.
                logger.debug("Dropping deserialized ticket with non-positive qty: %s", data)
                return None
            return OrderTicket(
                portfolio_id=str(data.get("portfolio_id", "")),
                symbol=str(data.get("symbol", "ETH/USD")),
                side=side,
                order_type=order_type,
                qty=qty_val,
                price=price_val,
                stop_loss=sl_val,
                take_profit=tp_val
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
        from src.arena.order import FillEvent, OrderSide, PositionSide, ExecutionReason
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
        """
        Saves current arena session state (competitors' portfolio, cash, positions,
        active brackets, genetic generation) to SQLite WAL storage.
        """
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
                    comp_states.append({
                        "portfolio_id": c.portfolio_id,
                        "name": c.name,
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
                        "peak_equity": str(p.peak_equity),
                        "max_drawdown_pct": str(p.max_drawdown_pct),
                        "is_circuit_breaker_tripped": p.is_circuit_breaker_tripped,
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
                        }
                    })

                snapshot = {
                    "schema_version": 2,
                    "saved_at": time.time(),
                    "generation": gen,
                    "live_start_ts": self.live_start_ts,
                    "strategy_telemetry": dict(self.strategy_telemetry),
                    "fill_records": [self._serialize_fill(f) for f in self.fill_records[-100:] if f is not None],
                    "broker_execution_audit": [self._serialize_fill(f) for f in self.broker.execution_audit[-100:] if f is not None] if hasattr(self, "broker") else [],
                    "auto_evolve_interval_sec": self.auto_evolve_interval_sec,
                    "auto_evolve_enabled": self.auto_evolve_enabled,
                    "cadence_sec": self.cadence_sec,
                    "live_orders_enabled": self.live_orders_enabled,
                    "active_stops": {pid: self._serialize_ticket(ticket) for pid, ticket in self.broker.active_stops.items() if ticket is not None},
                    "active_targets": {pid: self._serialize_ticket(ticket) for pid, ticket in self.broker.active_targets.items() if ticket is not None},
                    "position_entry_ts": dict(self.position_entry_ts),
                    "competitors": comp_states,
                }
                self.storage.save_session_snapshot(snapshot)
                self.log_event("SESSION_SAVED", f"Saved session state at Generation #{gen} to persistent storage.", "success")
                logger.info("Arena session snapshot saved successfully at Generation #%d", gen)
                return True
        except Exception as e:
            logger.error("Failed to save arena session state: %s", e)
            return False

    def restore_session_state(self, snapshot: Optional[Dict[str, Any]] = None) -> bool:
        """
        Restores arena session state from saved snapshot.
        """
        try:
            if snapshot is None:
                snapshot = self.storage.load_session_snapshot()
            if not snapshot or "competitors" not in snapshot:
                return False

            with self.lock:
                from src.competitors.base import CompetitorGenome
                from src.arena.portfolio import PositionSide

                comp_map = {c["portfolio_id"]: c for c in snapshot.get("competitors", [])}
                for c in self.competitors:
                    if c.portfolio_id in comp_map:
                        cd = comp_map[c.portfolio_id]
                        gd = cd.get("genome", {})
                        if gd:
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
                            except ValueError as e:
                                # Stored genome fails validation (e.g. written by an older
                                # version): keep the strategy default genome instead of
                                # breaking the whole restore.
                                self.log_event("RESTORE_WARN", f"{c.portfolio_id} stored genome invalid ({e}); keeping default genome", "loss")
                                new_genome = None
                            if new_genome is not None:
                                c.genome = new_genome
                                c.max_position_ratio = new_genome.position_ratio
                                gen_tag = f" [G{new_genome.generation}]" if new_genome.generation > 1 else ""
                                c.name = f"{c.base_name}{gen_tag}"

                        p = c.portfolio
                        p.name = c.name
                        p.cash = Decimal(str(cd.get("cash", p.cash)))
                        p.position_qty = Decimal(str(cd.get("position_qty", "0")))
                        try:
                            p.position_side = PositionSide(cd.get("position_side", "FLAT"))
                        except Exception as e:
                            logger.debug("Invalid position side in saved snapshot, defaulting to FLAT: %s", e)
                            p.position_side = PositionSide.FLAT
                        p.avg_entry_price = Decimal(str(cd.get("avg_entry_price", "0")))
                        p.open_position_entry_fee = Decimal(str(cd.get("open_position_entry_fee", "0.00")))
                        if "margin_locked" in cd:
                            p.margin_locked = Decimal(str(cd["margin_locked"]))
                        elif p.position_qty > Decimal("0") and p.avg_entry_price > Decimal("0"):
                            cost = (p.position_qty * p.avg_entry_price).quantize(Decimal("0.01"))
                            eff_lev = c.genome.leverage if (c.genome.leverage_enabled and c.genome.leverage > Decimal("0")) else Decimal("1.0")
                            p.margin_locked = (cost / eff_lev).quantize(Decimal("0.01"))
                        else:
                            p.margin_locked = Decimal("0.00")

                        p.current_market_price = Decimal(str(cd.get("current_market_price", p.avg_entry_price)))
                        p.realized_pnl = Decimal(str(cd.get("realized_pnl", "0")))
                        p.total_fees_paid = Decimal(str(cd.get("total_fees_paid", "0")))
                        p.gross_profit = Decimal(str(cd.get("gross_profit", "0")))
                        p.gross_loss = Decimal(str(cd.get("gross_loss", "0")))
                        p.win_count = int(cd.get("win_count", 0))
                        p.loss_count = int(cd.get("loss_count", 0))
                        p.peak_equity = Decimal(str(cd.get("peak_equity", p.cash)))
                        p.max_drawdown_pct = Decimal(str(cd.get("max_drawdown_pct", "0.00")))
                        p.is_circuit_breaker_tripped = bool(cd.get("is_circuit_breaker_tripped", False))

                        if "trade_history" in cd and isinstance(cd["trade_history"], list):
                            p.trade_history = [f for f in (self._deserialize_fill(d) for d in cd["trade_history"]) if f is not None]
                        if "equity_history" in cd and isinstance(cd["equity_history"], list):
                            p.equity_history = [
                                (float(pt[0]), Decimal(str(pt[1])))
                                for pt in cd["equity_history"]
                                if isinstance(pt, (list, tuple)) and len(pt) >= 2
                            ]

                        self.broker.competitor_caps[c.portfolio_id] = c.max_position_ratio

                if "active_stops" in snapshot and isinstance(snapshot["active_stops"], dict):
                    self.broker.active_stops = {}
                    for pid, s_data in snapshot["active_stops"].items():
                        t = self._deserialize_ticket(s_data)
                        if t:
                            self.broker.active_stops[pid] = t
                if "active_targets" in snapshot and isinstance(snapshot["active_targets"], dict):
                    self.broker.active_targets = {}
                    for pid, t_data in snapshot["active_targets"].items():
                        t = self._deserialize_ticket(t_data)
                        if t:
                            self.broker.active_targets[pid] = t
                if "position_entry_ts" in snapshot:
                    try:
                        self.position_entry_ts = {pid: float(ts) for pid, ts in snapshot["position_entry_ts"].items()}
                    except (TypeError, ValueError, AttributeError) as e:
                        logger.debug("Invalid position_entry_ts in saved snapshot, ignoring: %s", e)
                if "strategy_telemetry" in snapshot and isinstance(snapshot["strategy_telemetry"], dict):
                    self.strategy_telemetry.update(snapshot["strategy_telemetry"])
                if "fill_records" in snapshot and isinstance(snapshot["fill_records"], list):
                    self.fill_records = [f for f in (self._deserialize_fill(d) for d in snapshot["fill_records"]) if f is not None]
                if "broker_execution_audit" in snapshot and isinstance(snapshot["broker_execution_audit"], list) and hasattr(self, "broker"):
                    self.broker.execution_audit = [f for f in (self._deserialize_fill(d) for d in snapshot["broker_execution_audit"]) if f is not None]
                    self._audit_cursor = len(self.broker.execution_audit)
                    max_seq = max((int(getattr(f, "fill_seq", 0)) for f in self.broker.execution_audit), default=0)
                    self.broker.reset_seq(max_seq)
                if "auto_evolve_interval_sec" in snapshot:
                    self.auto_evolve_interval_sec = int(snapshot["auto_evolve_interval_sec"])
                if "auto_evolve_enabled" in snapshot:
                    self.auto_evolve_enabled = bool(snapshot["auto_evolve_enabled"])
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


