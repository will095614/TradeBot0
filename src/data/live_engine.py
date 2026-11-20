from __future__ import annotations

import asyncio
import copy
from decimal import Decimal
import logging
import math
import os
import threading
import time
from typing import Any, Dict, List, Optional

import requests

from src.arena.broker_sim import BrokerSim
from src.arena.evolution import GeneticEvolver
from src.arena.leaderboard import Leaderboard
from src.arena.order import ExecutionReason, FillEvent, OrderSide, OrderTicket, OrderType, PositionSide
from src.competitors.aggressive import AggressiveCompetitor
from src.competitors.conservative import ConservativeCompetitor
from src.competitors.orb import ORBCompetitor
from src.competitors.session_mean import SessionMeanPullbackCompetitor
from src.competitors.trailing_guard import TrailingGuardCompetitor
from src.data.eth_feed import CandleBar, ETHFeed
from src.data.indicator_engine import IndicatorEngineMixin, MTF_SEED_STALE_SEC
from src.data.live_strategy_runner import LiveStrategyRunnerMixin
from src.data.mtf_engine import MultiTimeframeEngine
from src.data.persistence import ArenaStorage
from src.data.quote_feeds import (
    QUOTE_STALE_SEC,
    LiveQuote,
    QuoteFeedsMixin,
    parse_symbol_pairs,
)
from src.data.quote_manager import QuoteManager
from src.data.session_codec import SessionCodecMixin
from src.data.timemachine import (
    CHOP_GATE_ER_THRESHOLD,
    CHOP_GATE_WINDOW_BARS,
    MonteCarloOddsEvaluator,
    efficiency_ratio,
)
from src.data.ws_feed import StreamingCryptoFeed
from src.gui.view_model import ViewModelPublisher, build_engine_view_model
from src.intelligence.macro_commander import MacroCommander, MacroRegimeState
from src.intelligence.omniroute_client import OmniRouteClient

logger = logging.getLogger(__name__)

# A SQLite candle cache is fresh only while its newest 1-minute bar is
# recent. 600s = 10 bars of slack for a brief feed gap: a cache older
# than that belongs to a dead session, and warming indicators (RSI / ATR
# / ORB / session mean) from it would misprice the live open.
CANDLE_CACHE_STALE_SEC = 600.0

# Chop-gate cold-start seeding (V2.8.0): load up to 360 1m bars so the
# newest 120 warm indicators while the up-to-240 older bars seed the MTF
# 15m close history immediately at startup.
CHOP_GATE_SEED_TOTAL_BARS = 360
CHOP_GATE_SEED_WARMUP_BARS = 120


class LiveArenaEngine(
    QuoteFeedsMixin,
    IndicatorEngineMixin,
    LiveStrategyRunnerMixin,
    SessionCodecMixin,
):
    """
    Real-Time Live Multi-Strategy Paper Trading Engine (default ETH/USD).
    Orchestrates live quote intake, 1.0s heartbeat cadence matching, evolutionary
    cycles, and lock-free UI snapshot delivery across specialized mixins.
    """

    # Strictly increasing epoch across engine resets (generation fence).
    _active_epoch: float = 0.0

    def __init__(
        self,
        initial_cash: Decimal = Decimal("100000.00"),
        symbol: str = "ETH/USD",
        storage: Optional[ArenaStorage] = None,
        auto_redeploy_when_flat: bool = True,
    ):
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

        # Strictly increasing epoch: a new engine always supersedes any older instance.
        with SessionCodecMixin._persistence_epoch_lock:
            self.engine_epoch: float = max(time.time(), LiveArenaEngine._active_epoch + 0.001)
            LiveArenaEngine._active_epoch = self.engine_epoch
        self.running = False
        self._stop_event = threading.Event()
        self._paused: bool = False
        self._pause_start_ts: Optional[float] = None
        self._auto_evolve_disabled_ts: Optional[float] = None
        self.interval_sec: float = 1.5
        self.worker_thread: Optional[threading.Thread] = None

        # Persistent structured fill tape (bounded in RAM; offset tracks evicted live fills)
        self.fill_records: List[FillEvent] = []
        self._live_fill_seq_offset: int = 0
        self._audit_cursor: int = 0
        self._defer_sql_flush: bool = False
        self._pending_sql_candles: List[Dict[str, Any]] = []
        self._pending_sql_fills: List[Dict[str, Any]] = []

        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "TradeBot0-LiveArena/2.0"})
        self.preferred_quote_provider: str = "binance"
        self._quote_provider_cooldown: Dict[str, float] = {}

        self.comp_a = AggressiveCompetitor(initial_cash=initial_cash)
        self.comp_b = ConservativeCompetitor(initial_cash=initial_cash)
        self.comp_d = TrailingGuardCompetitor(initial_cash=initial_cash)
        self.comp_e = ORBCompetitor(initial_cash=initial_cash)
        self.comp_f = SessionMeanPullbackCompetitor(initial_cash=initial_cash)
        self.competitors = [
            self.comp_a,
            self.comp_b,
            self.comp_d,
            self.comp_e,
            self.comp_f,
        ]

        # Strategy live telemetry descriptions
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
        self._orb_range_frozen: bool = False
        self._orb_session_day = None

        # 1-minute OHLC candles for charting & live RSI/ATR
        self.candles: List[Dict[str, float]] = []
        self.max_candles: int = 200
        self._last_saved_candle_t: Optional[float] = None
        self.live_start_ts: Optional[float] = None

        # Paced Candlestick Cadence Dispatcher (1.0s default heartbeat)
        self.cadence_sec: float = 1.0
        self.last_cadence_ts: float = 0.0
        self.last_cadence_slot: float = 0.0
        self.published_candles: List[Dict[str, float]] = []
        self.published_quote: Optional[LiveQuote] = None
        self._raw_quote_cache: Optional[LiveQuote] = None
        self._slice_ticks: List[LiveQuote] = []
        self.raw_fetch_thread: Optional[threading.Thread] = None

        # Automatic evolution: every 6 hours, or every 30 closed trades (30m debounce).
        self.auto_evolve_enabled: bool = True
        self.auto_redeploy_when_flat: bool = auto_redeploy_when_flat
        self._auto_redeploy_logged: bool = False
        self.auto_evolve_interval_sec: int = 21600
        self.auto_evolve_closed_trades: int = 30
        self.auto_evolve_debounce_sec: int = 1800
        self.last_evolve_ts: float = time.time()
        self.autosave_interval_sec: float = 60.0
        self._last_autosave_ts: float = time.time()
        self._autosave_pending: bool = False
        self._closed_trades_since_evolve: int = 0
        self.live_chop_gate_blocked: int = 0
        self.evolution_events: List[Dict[str, Any]] = []

        self.tv_champion: Dict[str, Any] = {
            "strategy_id": "comp_agg",
            "name": "Aggressive Momentum",
            "generation": 1,
            "roi_pct": 0.0,
            "fitness": 0.0,
            "status": "Gen #1 Running (Live Candidate #1)",
        }

        self.strategy_cooldown: Dict[str, float] = {}
        self.position_entry_ts: Dict[str, float] = {}

        self.mc_evaluator = MonteCarloOddsEvaluator(seed=19)

        self.omniroute_client = OmniRouteClient()
        self.macro_commander = MacroCommander(self.omniroute_client)
        self.intel_refresh_interval_sec: float = 300.0
        self.last_intel_refresh_ts: float = time.time()
        self._is_refreshing_intel: bool = False
        self._intel_refresh_lock = threading.Lock()

        self.quote_manager = QuoteManager(
            session=self.session,
            on_ws_quote=self._handle_ws_quote,
            symbol=symbol,
        )
        self.ws_feed: StreamingCryptoFeed = self.quote_manager.ws_feed

        self.storage = storage if storage is not None else ArenaStorage()

        self.mtf_engine = MultiTimeframeEngine()
        self.candles_5m: List[Dict[str, float]] = self.mtf_engine.candles_5m
        self.candles_15m: List[Dict[str, float]] = self.mtf_engine.candles_15m
        self.candles_1h: List[Dict[str, float]] = self.mtf_engine.candles_1h
        self.htf_ema_50: float = 0.0
        self.htf_ema_200: float = 0.0
        self.htf_bias: str = "NEUTRAL"

        self.view_publisher = ViewModelPublisher()

        self._init_broker()

    def _fetch_historical_bars(self, ticker: str, period: str, interval: str) -> List[CandleBar]:
        """Delegates to ETHFeed so monkeypatching src.data.live_engine.ETHFeed intercepts all mixins."""
        return ETHFeed.fetch_historical_bars(ticker=ticker, period=period, interval=interval)

    def _handle_ws_quote(self, quote: LiveQuote) -> None:
        """Callback invoked by StreamingCryptoFeed when a real-time WebSocket tick arrives."""
        with self.lock:
            self.latest_quote = quote
            self._raw_quote_cache = quote
            self._slice_ticks.append(quote)
            if len(self._slice_ticks) > 1200:
                del self._slice_ticks[:-1200]

    def _is_current_generation(self) -> bool:
        """Generation fence: True only while this engine instance is the active generation."""
        return self.engine_epoch == LiveArenaEngine._active_epoch

    def _harvest_fills(self) -> None:
        """Copies new broker fills into the persistent tape (bounded to 200 records) and queues/persists SQLite rows."""
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
                    self._closed_trades_since_evolve += 1
                try:
                    is_short_pos = getattr(f, "position_side", PositionSide.SHORT) == PositionSide.SHORT
                    is_entry = (f.side == OrderSide.SELL) if is_short_pos else (f.side == OrderSide.BUY)
                    if is_short_pos:
                        action_label = "OPEN SHORT" if is_entry else "COVER SHORT"
                    else:
                        action_label = "OPEN LONG" if is_entry else "CLOSE LONG"
                    entry_p = getattr(f, "entry_price", None)
                    payload = {
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
                    }
                    if getattr(self, "_defer_sql_flush", False):
                        self._pending_sql_fills.append(payload)
                    else:
                        self.storage.record_fill(payload)
                except Exception as e:
                    logger.debug("SQLite fill record skipped: %s", e)
            if len(self.fill_records) > 200:
                evicted = self.fill_records[:-200]
                self._live_fill_seq_offset += sum(
                    1
                    for ef in evicted
                    if bool(self.live_start_ts and float(getattr(ef, "timestamp", 0.0)) >= self.live_start_ts - 2.0)
                )
                self.fill_records = self.fill_records[-200:]
            if self._audit_cursor > 500:
                self.broker.execution_audit = self.broker.execution_audit[self._audit_cursor:]
                self._audit_cursor = 0

    def _flush_sql_queues(self) -> None:
        """Flushes deferred SQLite candle and fill writes outside self.lock."""
        with self.lock:
            candles = list(self._pending_sql_candles)
            fills = list(self._pending_sql_fills)
            self._pending_sql_candles.clear()
            self._pending_sql_fills.clear()
        if not self._is_current_generation():
            return
        if candles:
            try:
                self.storage.save_candles_batch(candles)
            except Exception as e:
                logger.debug("SQLite candle batch save skipped: %s", e)
        if fills:
            try:
                self.storage.record_fills_batch(fills)
            except Exception as e:
                logger.debug("SQLite fill batch record skipped: %s", e)

    def _init_broker(self) -> None:
        self.broker = BrokerSim(symbol=self.symbol, slippage_pct=Decimal("0.0001"))
        self._audit_cursor = 0
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

    def bootstrap_intraday_session(self) -> None:
        """
        Loads the last 120 minutes of 1-minute bars to warm indicators and prime the arena.
        Falls back to fresh SQLite candle cache when available; never fabricates synthetic bars.
        """
        if self._stop_event.is_set():
            return
        pairs = parse_symbol_pairs(self.symbol)
        asset = pairs["base"]
        recent_bars: List[CandleBar] = []
        seed_bars: List[Dict[str, Any]] = []
        cached_candles: List[Dict[str, Any]] = []
        is_fresh_cache = False
        try:
            cached_candles = self.storage.load_latest_candles(CHOP_GATE_SEED_TOTAL_BARS)
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
                    for c in cached_candles[-CHOP_GATE_SEED_WARMUP_BARS:]
                ]
                seed_bars = [
                    {
                        "t": float(c["t"]),
                        "o": float(c["o"]),
                        "h": float(c["h"]),
                        "l": float(c["l"]),
                        "c": float(c["c"]),
                        "v": float(c.get("v", 0.0)),
                    }
                    for c in cached_candles[:-CHOP_GATE_SEED_WARMUP_BARS]
                ]
        except Exception as e:
            logger.debug("SQLite candle cache hydration skipped: %s", e)

        if self._stop_event.is_set():
            return

        if not recent_bars:
            try:
                bars = self._fetch_historical_bars(ticker=pairs["yahoo"], period="1d", interval="1m")
                recent_bars = bars[-CHOP_GATE_SEED_WARMUP_BARS:] if len(bars) > CHOP_GATE_SEED_WARMUP_BARS else bars
                seed_bars = [
                    {
                        "t": float(b.timestamp),
                        "o": float(b.open),
                        "h": float(b.high),
                        "l": float(b.low),
                        "c": float(b.close),
                        "v": float(b.volume),
                    }
                    for b in bars[:-CHOP_GATE_SEED_WARMUP_BARS]
                ]
            except Exception as e:
                logger.debug("Intraday bars fetch failed: %s", e)

        if self._stop_event.is_set():
            return

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
            logger.info("Bootstrap: no real intraday bars available; waiting for live feed.")

        candles_to_save: List[Dict[str, float]] = []
        should_try_restore = False

        with self.lock:
            if self._stop_event.is_set():
                return

            if recent_bars:
                seeded = self._seed_chop_gate_buckets(seed_bars, float(recent_bars[0].timestamp))
                if seeded:
                    logger.info("Chop gate seeded: %d 1m bars -> %d 15m buckets.", seeded, len(self.candles_15m))

            ema_fast_val: Optional[Decimal] = None
            ema_slow_val: Optional[Decimal] = None
            alpha_f = Decimal("0.2")      # EMA(9)
            alpha_s = Decimal("0.0909")   # EMA(21)
            for bar in recent_bars:
                if self._stop_event.is_set():
                    return
                has_bar_ema = (
                    bar.ema_fast is not None
                    and bar.ema_slow is not None
                    and not (bar.ema_fast == bar.close and bar.ema_slow == bar.close)
                )
                if has_bar_ema:
                    ema_fast_val = bar.ema_fast
                    ema_slow_val = bar.ema_slow
                else:
                    if ema_fast_val is None:
                        ema_fast_val = bar.close
                        ema_slow_val = bar.close
                    else:
                        ema_fast_val = ((bar.close * alpha_f) + (ema_fast_val * (Decimal("1") - alpha_f))).quantize(Decimal("0.01"))
                        ema_slow_val = ((bar.close * alpha_s) + (ema_slow_val * (Decimal("1") - alpha_s))).quantize(Decimal("0.01"))
                self.live_ema_fast = ema_fast_val
                self.live_ema_slow = ema_slow_val
                self.live_rsi = bar.rsi or Decimal("50.00")
                self.live_atr = max(Decimal("5.00"), bar.atr or Decimal("12.00"))
                self.broker.current_atr = self.live_atr

                self._update_candle(float(bar.timestamp), bar.close, bar.high, bar.low, bar.open)
                self._record_series_point(bar.close, bar.timestamp)

            self._recompute_orb_range(self.candles)

            if recent_bars:
                self.live_typical_mean = (
                    sum(((b.high + b.low + b.close) / Decimal("3")) for b in recent_bars) / Decimal(len(recent_bars))
                ).quantize(Decimal("0.01"))

            if not self._stop_event.is_set() and self._is_current_generation() and self.candles:
                candles_to_save = [dict(c) for c in self.candles]

            if recent_bars:
                self.log_event(
                    "WARMUP_SYNC",
                    f"Replayed 120m intraday history ({len(recent_bars)} bars). Indicators & rankings primed. Waiting for UI reveal.",
                    "info",
                )

            if not self._has_restored_session:
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
                self.comp_d.highest_price_since_entry = Decimal("0")
                self.comp_d.lowest_price_since_entry = Decimal("0")
                self.comp_d.trailing_active = False
                if hasattr(self, "broker"):
                    self.broker.active_stops.clear()
                    self.broker.active_targets.clear()
                    self.broker.pending_orders.clear()
                    self.broker.execution_audit.clear()
                    self.broker.rejection_audit.clear()
                self._audit_cursor = 0
                self._closed_trades_since_evolve = 0
                self.live_chop_gate_blocked = 0
                self.fill_records.clear()
                self._live_fill_seq_offset = 0
                self.live_logs = [log for log in self.live_logs if log.get("tag") not in ("BUY", "SELL", "STOP_LOSS", "TAKE_PROFIT")]
                self.strategy_cooldown.clear()
                self.position_entry_ts.clear()
                should_try_restore = (os.environ.get("ARENA_FAST_TEST") != "1")
            else:
                if recent_bars:
                    last_price = recent_bars[-1].close
                    for comp in self.competitors:
                        if comp.portfolio.position_qty > Decimal("0"):
                            comp.portfolio.current_market_price = last_price

        if candles_to_save and not self._stop_event.is_set() and self._is_current_generation():
            try:
                self.storage.save_candles_batch(candles_to_save)
            except Exception as e:
                logger.debug("SQLite candle batch save skipped: %s", e)

        if should_try_restore and not self._stop_event.is_set():
            try:
                if self.restore_session_state():
                    self._has_restored_session = True
            except Exception as e:
                logger.debug("Auto restore session state skipped: %s", e)

        with self.lock:
            if self._stop_event.is_set():
                return
            if self._has_restored_session and recent_bars:
                last_price = recent_bars[-1].close
                for comp in self.competitors:
                    if comp.portfolio.position_qty > Decimal("0"):
                        comp.portfolio.current_market_price = last_price

            if not self.live_orders_enabled:
                self.live_trading_active = False
                self.live_start_ts = None

            self.published_candles = [dict(c) for c in self.candles]
            self.published_quote = self.latest_quote
            self._raw_quote_cache = self.latest_quote
            self.last_cadence_ts = time.time()
            self.last_cadence_slot = math.floor(self.last_cadence_ts / self.cadence_sec) * self.cadence_sec
            self.macro_commander.ensure_traditional_chinese_seed_events()
            self.is_bootstrapped = True
            try:
                self._publish_state_snapshot()
            except Exception as e:
                logger.debug("State publish skipped during bootstrap: %s", e)
            try:
                if os.environ.get("ARENA_FAST_TEST") != "1":
                    threading.Thread(target=self.refresh_intel_digest, daemon=True).start()
                    threading.Thread(target=self._seed_mtf_1h_history, daemon=True).start()
            except Exception as e:
                logger.warning("Failed to start intel digest refresh thread: %s", e)

    def start_live_trading(self) -> Dict[str, Any]:
        """Activated once frontend reveal finishes and layout is verified ready."""
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
                if hasattr(self, "broker"):
                    self.broker.execution_audit.clear()
                    self.broker.rejection_audit.clear()
                self._audit_cursor = 0
                self.fill_records.clear()
                self._live_fill_seq_offset = 0

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
                self.log_event("ARENA_REVEALED", "Arena initialization verified. Live order placement active, awaiting live price ticks...", "info")
                self._publish_state_snapshot()
                return {"accepted": True, "reason": "Live trading active, awaiting online quote", "restored": False}

            self._publish_state_snapshot()
            return {"accepted": True, "reason": "Live trading active with restored positions", "restored": True}

    def refresh_intel_digest(self) -> Dict[str, Any]:
        """Triggers an AI-driven macro intelligence refresh via OmniRoute."""
        if self._stop_event.is_set() or not self._is_current_generation():
            return self.macro_commander.get_intel_hub_telemetry()
        with self._intel_refresh_lock:
            if self._is_refreshing_intel:
                return self.macro_commander.get_intel_hub_telemetry()
            self._is_refreshing_intel = True
        self.last_intel_refresh_ts = time.time()
        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                loop.create_task(self.macro_commander.refresh_digest_async())
            else:
                self.macro_commander.run_digest_sync()
        except Exception as e:
            logger.warning("Intel digest refresh error: %s", e)
        finally:
            with self._intel_refresh_lock:
                self._is_refreshing_intel = False
            if not self._stop_event.is_set() and self._is_current_generation():
                try:
                    self._publish_state_snapshot()
                except Exception as e:
                    logger.debug("State publish skipped after intel refresh: %s", e)
        return self.macro_commander.get_intel_hub_telemetry()

    def _record_series_point(self, price: Decimal, ts: float) -> None:
        self._harvest_fills()
        t_label = time.strftime("%H:%M:%S", time.localtime(ts))
        self.tick_timestamps.append(t_label)
        self.eth_price_series.append(float(price))
        self.ema_fast_series.append(float(self.live_ema_fast))
        self.ema_slow_series.append(float(self.live_ema_slow))

        max_pts = 180
        if len(self.tick_timestamps) > max_pts:
            self.tick_timestamps = self.tick_timestamps[-max_pts:]
            self.eth_price_series = self.eth_price_series[-max_pts:]
            self.ema_fast_series = self.ema_fast_series[-max_pts:]
            self.ema_slow_series = self.ema_slow_series[-max_pts:]

    def _quote_fetch_worker(self) -> None:
        """Hidden background thread querying public REST APIs without blocking UI cadence."""
        while self.running and not self._stop_event.is_set():
            if self.paused:
                time.sleep(0.25)
                continue
            try:
                if not self.ws_feed.is_fresh():
                    fetch_started = time.time()
                    raw = self.fetch_realtime_crypto_quote()
                    if raw and not raw.is_offline and raw.price > Decimal("0"):
                        with self.lock:
                            cur = self._raw_quote_cache
                            if cur is None or (raw.timestamp >= cur.timestamp and cur.timestamp <= fetch_started + 0.05):
                                self._raw_quote_cache = raw
                                self._slice_ticks.append(raw)
                                if len(self._slice_ticks) > 1200:
                                    del self._slice_ticks[:-1200]
            except Exception as e:
                logger.debug("Background quote fetcher error: %s", e)
            for _ in range(10):
                if not self.running or self._stop_event.is_set():
                    break
                time.sleep(0.1)

    def start_live_loop(self, interval_sec: float = 1.0) -> None:
        if self.running:
            return
        if self.worker_thread is not None and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=3.0)
            if self.worker_thread.is_alive():
                logger.warning("Previous live loop thread still alive; refusing to start a second one")
                return
        if self.raw_fetch_thread is not None and self.raw_fetch_thread.is_alive():
            self.raw_fetch_thread.join(timeout=3.0)
            if self.raw_fetch_thread.is_alive():
                logger.warning("Previous quote fetch thread still alive; refusing to start a second one")
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
        try:
            self.session.close()
        except Exception as e:
            logger.debug("Quote session close failed during stop: %s", e)
        try:
            self.storage.close()
        except Exception as e:
            logger.debug("Storage close failed during stop: %s", e)

    def stop(self) -> None:
        self.stop_live_loop()

    def _live_loop(self) -> None:
        pairs = parse_symbol_pairs(self.symbol)
        asset = pairs["base"]
        self.log_event("BOOT", f"Connecting to real-time {pairs['symbol']} orderflow & warming 1m indicators...", "info")
        self.ws_feed.start()
        self.bootstrap_intraday_session()
        if not self.running or self._stop_event.is_set():
            return

        with self.lock:
            now_init = time.time()
            if self.live_orders_enabled and self.live_start_ts is None:
                self.live_start_ts = now_init
            if self.last_evolve_ts <= 0.0:
                self.last_evolve_ts = now_init
            self._last_autosave_ts = now_init
            self.last_cadence_slot = math.floor(now_init / self.cadence_sec) * self.cadence_sec

        self.raw_fetch_thread = threading.Thread(target=self._quote_fetch_worker, daemon=True)
        self.raw_fetch_thread.start()

        try:
            while self.running and not self._stop_event.is_set():
                if self.paused:
                    time.sleep(0.25)
                    continue

                now = time.time()
                current_slot = math.floor(now / self.cadence_sec) * self.cadence_sec

                if current_slot > self.last_cadence_slot:
                    self.last_cadence_slot = current_slot
                    _evolve_reason: Optional[str] = None
                    _should_refresh_intel = False
                    try:
                        with self.lock:
                            self._defer_sql_flush = True
                            try:
                                raw = self._raw_quote_cache or self.latest_quote
                                ticks = list(self._slice_ticks)
                                self._slice_ticks.clear()

                                if self._is_quote_fresh(raw, now):
                                    if not self.market_online:
                                        self.market_online = True
                                        self.log_event("FEED_ONLINE", "Market feed reconnected: trading resumed.", "success")
                                    prev_p = (
                                        self.published_quote.price
                                        if (self.published_quote and self.published_quote.price > Decimal("0"))
                                        else raw.price
                                    )

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
                                        is_offline=False,
                                    )
                                    self.latest_quote = cadenced_quote
                                    self.published_quote = cadenced_quote
                                    self.tick_count += 1

                                    # Micro-bar aggregated 1-minute candle refresh
                                    self._update_candle(
                                        float(current_slot),
                                        close=cadenced_quote.price,
                                        high=high_p,
                                        low=low_p,
                                        open_=open_p,
                                    )
                                    self._recompute_candle_indicators()

                                    # Publish candle slices on the 1.0-second cadence heartbeat
                                    self.published_candles = [dict(c) for c in self.candles]
                                    self.last_cadence_ts = float(current_slot)

                                    # Update live exponential moving averages on each cadence beat
                                    alpha_f = Decimal("0.15")
                                    alpha_s = Decimal("0.04")
                                    if self.live_ema_fast <= Decimal("0"):
                                        self.live_ema_fast = cadenced_quote.price
                                        self.live_ema_slow = cadenced_quote.price
                                    else:
                                        self.live_ema_fast = ((cadenced_quote.price * alpha_f) + (self.live_ema_fast * (Decimal("1") - alpha_f))).quantize(Decimal("0.01"))
                                        self.live_ema_slow = ((cadenced_quote.price * alpha_s) + (self.live_ema_slow * (Decimal("1") - alpha_s))).quantize(Decimal("0.01"))

                                    # Live orders & simulated matching activate on each cadence boundary
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
                                            open_price=prev_p,
                                        )
                                        for f in fills:
                                            if f.is_closing_fill:
                                                self.strategy_cooldown[f.portfolio_id] = float(current_slot) + 60.0
                                                self.position_entry_ts.pop(f.portfolio_id, None)
                                            pnl_str = f" (PnL: ${f.realized_pnl:+.2f})" if f.is_closing_fill else ""
                                            self.log_event(
                                                f.reason.value,
                                                f"{f.portfolio_id.upper()} {f.side.value} {f.qty} {asset} @ ${f.price:,.2f}{pnl_str}",
                                                "profit" if f.realized_pnl >= Decimal("0") else "loss",
                                            )
                                            strat_name = self.STRATEGY_SHORT.get(f.portfolio_id, f.portfolio_id)
                                            if f.is_closing_fill:
                                                close_verb = "Covered SHORT" if f.position_side == PositionSide.SHORT else "Closed LONG"
                                                self.macro_commander.record_strategy_action(
                                                    f.portfolio_id,
                                                    strat_name,
                                                    f"{close_verb} {f.qty} {asset} @ ${f.price:,.2f} ({f.reason.value}{pnl_str})",
                                                    "profit" if f.realized_pnl >= Decimal("0") else "loss",
                                                )

                                        self._maybe_auto_redeploy(cadenced_quote.price, float(current_slot))
                                        self._evaluate_live_strategies(cadenced_quote.price, prev_p, float(current_slot))

                                    self._record_series_point(cadenced_quote.price, float(current_slot))
                                elif self.market_online:
                                    self.market_online = False
                                    self.log_event("FEED_OFFLINE", "Market feed offline: trading paused, waiting to reconnect...", "loss")

                                if self.live_orders_enabled:
                                    _evolve_reason = self._auto_evolve_reason()

                                if _evolve_reason is None:
                                    self._publish_state_snapshot()

                                _should_refresh_intel = (
                                    (now - self.last_intel_refresh_ts)
                                    >= self.macro_commander.digest_interval_sec(self.intel_refresh_interval_sec)
                                    and not self._is_refreshing_intel
                                    and os.environ.get("ARENA_FAST_TEST") != "1"
                                )
                            finally:
                                self._defer_sql_flush = False

                        # Flush deferred SQLite writes and auto-evolution outside self.lock (§3.2).
                        self._flush_sql_queues()
                        if _evolve_reason is not None:
                            self.evolve_now(trigger=f"auto:{_evolve_reason}")
                            self._publish_state_snapshot()
                        if _should_refresh_intel:
                            threading.Thread(target=self.refresh_intel_digest, daemon=True).start()

                    except Exception as e:
                        self.log_event("FEED_WARN", f"Retrying live quote stream: {e}", "loss")

                self._maybe_autosave(now)
                time.sleep(0.1)  # High-frequency poll to align cleanly with the cadence slot without drift
        finally:
            try:
                self._flush_sql_queues()
            except Exception as e:
                logger.debug("Final SQL flush skipped during loop exit: %s", e)

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
                    for pid in list(self.position_entry_ts):
                        self.position_entry_ts[pid] += paused_dur
                    self._pause_start_ts = None
                    self._slice_ticks.clear()
                self.log_event("ENGINE", "Simulation & Evolution Timer RESUMED", "info")
        self._publish_state_snapshot()

    def toggle_pause(self) -> bool:
        self.paused = not self.paused
        return self.paused

    def _auto_evolve_reason(self, now: Optional[float] = None) -> Optional[str]:
        """Why auto-evolution is due now: 'time' (6h cap), 'trades' (30 closed + 30m debounce), or None."""
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
            parent_order = GeneticEvolver.parent_order(rankings)
            kept = [short.get(r.portfolio_id, r.portfolio_id) for r in parent_order[:2]]
            rebuilt = [short.get(r.portfolio_id, r.portfolio_id) for r in parent_order[2:]]
            leader_roi = float(rankings[0].roi_pct) if rankings else 0.0

            entropy = sum(int(c.portfolio.total_equity * 100) for c in self.competitors) + sum(
                c.portfolio.total_fills for c in self.competitors
            )
            logs, records_to_save = GeneticEvolver.evolve_generation_with_records(
                self.competitors,
                rankings,
                preserve_portfolio=True,
                save_history=False,
                seed_entropy=entropy,
            )
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

        if records_to_save and records_to_save[0] and records_to_save[1]:
            try:
                GeneticEvolver.save_history(records_to_save[0], records_to_save[1], storage=self.storage)
            except Exception as e:
                logger.warning("Failed to persist evolution history outside lock: %s", e)

        self._autosave_pending = True
        return logs

    STRATEGY_COLORS: Dict[str, str] = {
        "comp_agg": "#FF334B",
        "comp_cons": "#38BDF8",
        "comp_trail": "#00E676",
        "comp_orb": "#A855F7",
        "comp_vwap": "#FFD60A",
    }
    STRATEGY_SHORT: Dict[str, str] = {
        "comp_agg": "AGG",
        "comp_cons": "CONS",
        "comp_trail": "TRAIL",
        "comp_orb": "ORB",
        "comp_vwap": "MEAN",
    }
    STRATEGY_DISPLAY: Dict[str, str] = {
        "comp_agg": "Aggressive Momentum",
        "comp_cons": "Conservative Scalper",
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
        """Atomically publishes double-buffered UI snapshot for lock-free IPC consumption."""
        if not self._is_current_generation():
            logger.debug("Stale engine epoch %.3f: skipping state publish from a superseded generation", self.engine_epoch)
            return
        with self.lock:
            snapshot = self._build_snapshot_locked()
        with self._snapshot_lock:
            self._ui_state_snapshot = snapshot

    def get_ui_state(self) -> Dict[str, Any]:
        """Retrieves current UI state from the lock-free double-buffered snapshot."""
        with self._snapshot_lock:
            snap = self._ui_state_snapshot
        if snap is not None:
            return copy.deepcopy(snap)
        with self.lock:
            return copy.deepcopy(self._build_snapshot_locked())

    def get_ui_state_delta(self, force_full: bool = False) -> Dict[str, Any]:
        """Diff-based IPC state delta publisher from the immutable snapshot."""
        with self._snapshot_lock:
            snap = self._ui_state_snapshot
        if snap is None:
            with self.lock:
                snap = self._build_snapshot_locked()
        return self.view_publisher.compute_delta_from_snapshot(snap, force_full=force_full)
