#!/usr/bin/env python3
"""Fix item 12C: weighted sentiment + news sizing into orders (TradeBot0).

Applies exact-once-verified replacements to the PC project tree (run with
cwd = project root) and, identically, to the local audit copy.
Every replacement is verified to occur exactly once before anything is
written; on any mismatch the script aborts without touching a file.
Newline style is preserved (files are LF; open with newline="").

Design basis: ~/workspace/tradebot_audit/item12_design.md, section C
(C1-C5), as approved by the user 2026-11-13 (D1-D7 all at recommended
values; D4 sizing accepted, D5 per-strategy sensitivity accepted,
D7 backtest default 1.0 = not applied).

What this patch does:
  C1. MacroCommander.compute_weighted_sentiment(): deterministic
      tier/urgency/60-min-half-life weighted sentiment S, urgency U and
      coverage N; stored on the regime state and exposed via to_dict()
      (the view model already passes to_dict() through, so no
      view_model.py change is needed). The keyword fallback now decides
      direction from S/U/N (S > +/-0.45, U >= 7, N >= 2); HOLD_CASH is
      never set by the fallback (it needs live LLM confidence >= 0.8)
      and the fallback resets confidence to 0.50 ("no confidence"). The
      LLM prompt carries the same S/U/N as a reference value; the LLM's
      own judgement is not overridden.
  C2. CompetitorGenome gains news_sensitivity (0.0-1.0, validated in
      __post_init__): ORB 1.0, Aggressive 0.8, ATR 0.7, Trailing 0.5,
      Conservative 0.3, Session Mean 0.3. It is a property of the
      strategy slot: evolution preserves it (never mutates) and
      BaseCompetitor.reset_for_new_generation re-asserts the slot's
      value, so a genome crossed from another strategy's champion
      cannot change the slot's sensitivity. Snapshot save/restore
      carries it (old snapshots fall back to the slot value).
      MacroCommander.news_sizing_multiplier(sensitivity) implements
      sizing_mult = 1 + (rm-1) * ((c-0.5)/0.5) interpolated by
      sensitivity, clamped to [0.5, 1.5].
      compute_r_multiple_qty() gains sizing_multiplier (default 1.0);
      the risk budget is scaled by it (the position-ratio cap is NOT
      scaled: it stays the safety max). evaluate_signal() threads the
      factor through all 6 strategies (atr_dynamic's local risk_budget
      is scaled inside compute_r_multiple_qty, so no extra change
      there). Live engine computes the per-strategy factor once in
      _try_enter_bracket (TP stretch now uses it instead of the raw
      risk_multiplier) and passes it to evaluate_signal in
      _enter_via_strategy. Backtest never passes it, so it defaults to
      1.0 and backtest numbers are unchanged (D7).

Tests: new tests/test_weighted_sentiment.py + tests/test_news_sizing.py
(C4 assertions). Updated fixtures whose events the new 60-minute window
now treats as stale: test_item12a_omniroute._strong_bearish_events()
and test_intel_veto.test_fallback_thresholds_do_not_veto_on_single_word()
now stamp events fresh at run time (their intent is threshold behaviour,
not staleness).
"""
import os
import sys

if not os.path.isdir("src/gui"):
    print("FAIL: run this script from the project root (src/gui not found)")
    sys.exit(1)

REPLACEMENTS = []
NEW_FILES = {}


def rep(path, old, new):
    REPLACEMENTS.append((path, old, new))


# =========================================================== 1. base.py: genome field + validation
rep("src/competitors/base.py", '''from dataclasses import dataclass''',
'''from dataclasses import dataclass, replace''')

rep("src/competitors/base.py", '''    leverage_enabled: bool = False
    leverage: Decimal = Decimal("1.0")''',
'''    leverage_enabled: bool = False
    leverage: Decimal = Decimal("1.0")
    # News sensitivity (item 12C): how much macro news scales this
    # strategy's position size (0.0 = news-blind, 1.0 = full effect).
    # Fixed per strategy slot; evolution never mutates it. Kept last so
    # positional construction order of the other genes is unchanged.
    news_sensitivity: float = 0.5''')

rep("src/competitors/base.py", '''        _range("leverage", self.leverage, Decimal("1.0"), Decimal("5.0"))''',
'''        _range("leverage", self.leverage, Decimal("1.0"), Decimal("5.0"))
        if not 0.0 <= float(self.news_sensitivity) <= 1.0:
            raise ValueError(
                f"CompetitorGenome.news_sensitivity={self.news_sensitivity} out of range [0.0, 1.0]"
            )''')

# =========================================================== 2. base.py: compute_r_multiple_qty
rep("src/competitors/base.py", '''        broker: BrokerSim,
        risk_budget: Optional[Decimal] = None
    ) -> Decimal:''',
'''        broker: BrokerSim,
        risk_budget: Optional[Decimal] = None,
        sizing_multiplier: Decimal = Decimal("1.0"),
    ) -> Decimal:''')

rep("src/competitors/base.py", '''        budget = (
            risk_budget
            if risk_budget is not None
            else (self.portfolio.total_equity * self.genome.risk_per_trade_pct)
        )''',
'''        budget = (
            risk_budget
            if risk_budget is not None
            else (self.portfolio.total_equity * self.genome.risk_per_trade_pct)
        )
        # News sizing (item 12C): scale the risk budget by the news factor.
        # The position-ratio cap below is NOT scaled: it stays the safety
        # max, so an optimistic regime can never push size past the cap.
        sizing_multiplier = max(Decimal("0.5"), min(Decimal("1.5"), sizing_multiplier))
        budget = budget * sizing_multiplier''')

# =========================================================== 3. base.py: evaluate_signal signature
rep("src/competitors/base.py", '''        timestamp: float,
        side: OrderSide = OrderSide.BUY,
    ) -> Optional[OrderTicket]:''',
'''        timestamp: float,
        side: OrderSide = OrderSide.BUY,
        sizing_multiplier: Decimal = Decimal("1.0"),
    ) -> Optional[OrderTicket]:''')

# =========================================================== 4. base.py: slot sensitivity enforcement
rep("src/competitors/base.py", '''    All competitors share the identical market signal input but differ in risk, exit, and leverage genes.
    Supports genetic evolution across generations.
    """
    def __init__(''',
'''    All competitors share the identical market signal input but differ in risk, exit, and leverage genes.
    Supports genetic evolution across generations.
    """
    # News sensitivity for this strategy slot (item 12C, phase 1): fixed
    # per strategy, never mutated by evolution. Subclasses override.
    NEWS_SENSITIVITY: float = 0.5

    def __init__(''')

rep("src/competitors/base.py", '''    def reset_for_new_generation(self, new_genome: CompetitorGenome, preserve_portfolio: bool = True) -> None:
        self.genome = new_genome''',
'''    def reset_for_new_generation(self, new_genome: CompetitorGenome, preserve_portfolio: bool = True) -> None:
        # News sensitivity is a property of the strategy slot, not the
        # genome lineage: a genome crossed from another strategy's
        # champion must not change this slot's sensitivity (item 12C:
        # fixed per strategy in phase 1).
        try:
            sens = float(getattr(new_genome, "news_sensitivity", self.NEWS_SENSITIVITY))
        except (TypeError, ValueError):
            sens = float(self.NEWS_SENSITIVITY)
        if sens != float(self.NEWS_SENSITIVITY):
            new_genome = replace(new_genome, news_sensitivity=float(self.NEWS_SENSITIVITY))
        self.genome = new_genome''')

# =========================================================== 5. strategies: slot value + threading
# --- Aggressive (0.8) ---
rep("src/competitors/aggressive.py", '''    def __init__(self, portfolio_id: str = "comp_agg", initial_cash: Decimal = Decimal("100000.00")):''',
'''    # News sensitivity (item 12C): momentum eats macro-news sizing hard.
    NEWS_SENSITIVITY: float = 0.8

    def __init__(self, portfolio_id: str = "comp_agg", initial_cash: Decimal = Decimal("100000.00")):''')
rep("src/competitors/aggressive.py", '''            generation=1,
            leverage_enabled=True,
            leverage=Decimal("3.0")''',
'''            generation=1,
            leverage_enabled=True,
            leverage=Decimal("3.0"),
            news_sensitivity=0.8''')
rep("src/competitors/aggressive.py", '''        timestamp: float,
        side: OrderSide = OrderSide.BUY,
    ) -> Optional[OrderTicket]:''',
'''        timestamp: float,
        side: OrderSide = OrderSide.BUY,
        sizing_multiplier: Decimal = Decimal("1.0"),
    ) -> Optional[OrderTicket]:''')
rep("src/competitors/aggressive.py", '''            target_price = (
                (market_price * (Decimal("1") + self.genome.take_profit_pct)).quantize(Decimal("0.01"))
                if self.genome.take_profit_pct is not None
                else None
            )
            qty = self.compute_r_multiple_qty(market_price, stop_price, broker)''',
'''            target_price = (
                (market_price * (Decimal("1") + self.genome.take_profit_pct)).quantize(Decimal("0.01"))
                if self.genome.take_profit_pct is not None
                else None
            )
            qty = self.compute_r_multiple_qty(market_price, stop_price, broker, sizing_multiplier=sizing_multiplier)''')
rep("src/competitors/aggressive.py", '''            target_price = (
                (market_price * (Decimal("1") - self.genome.take_profit_pct)).quantize(Decimal("0.01"))
                if self.genome.take_profit_pct is not None
                else None
            )
            qty = self.compute_r_multiple_qty(market_price, stop_price, broker)''',
'''            target_price = (
                (market_price * (Decimal("1") - self.genome.take_profit_pct)).quantize(Decimal("0.01"))
                if self.genome.take_profit_pct is not None
                else None
            )
            qty = self.compute_r_multiple_qty(market_price, stop_price, broker, sizing_multiplier=sizing_multiplier)''')

# --- Conservative (0.3) ---
rep("src/competitors/conservative.py", '''    def __init__(self, portfolio_id: str = "comp_cons", initial_cash: Decimal = Decimal("100000.00")):''',
'''    # News sensitivity (item 12C): conservative barely moves on news.
    NEWS_SENSITIVITY: float = 0.3

    def __init__(self, portfolio_id: str = "comp_cons", initial_cash: Decimal = Decimal("100000.00")):''')
rep("src/competitors/conservative.py", '''            generation=1,
            leverage_enabled=False,
            leverage=Decimal("1.0")''',
'''            generation=1,
            leverage_enabled=False,
            leverage=Decimal("1.0"),
            news_sensitivity=0.3''')
rep("src/competitors/conservative.py", '''        timestamp: float,
        side: OrderSide = OrderSide.BUY,
    ) -> Optional[OrderTicket]:''',
'''        timestamp: float,
        side: OrderSide = OrderSide.BUY,
        sizing_multiplier: Decimal = Decimal("1.0"),
    ) -> Optional[OrderTicket]:''')
rep("src/competitors/conservative.py", '''            target_price = (market_price * (Decimal("1") + tp_pct)).quantize(Decimal("0.01"))

            qty = self.compute_r_multiple_qty(market_price, stop_price, broker)''',
'''            target_price = (market_price * (Decimal("1") + tp_pct)).quantize(Decimal("0.01"))

            qty = self.compute_r_multiple_qty(market_price, stop_price, broker, sizing_multiplier=sizing_multiplier)''')
rep("src/competitors/conservative.py", '''            target_price = (market_price * (Decimal("1") - tp_pct)).quantize(Decimal("0.01"))

            qty = self.compute_r_multiple_qty(market_price, stop_price, broker)''',
'''            target_price = (market_price * (Decimal("1") - tp_pct)).quantize(Decimal("0.01"))

            qty = self.compute_r_multiple_qty(market_price, stop_price, broker, sizing_multiplier=sizing_multiplier)''')

# --- ATR Dynamic (0.7) ---
rep("src/competitors/atr_dynamic.py", '''    def __init__(self, portfolio_id: str = "comp_atr", initial_cash: Decimal = Decimal("100000.00")):''',
'''    # News sensitivity (item 12C): volatility strategy, moderately news-aware.
    NEWS_SENSITIVITY: float = 0.7

    def __init__(self, portfolio_id: str = "comp_atr", initial_cash: Decimal = Decimal("100000.00")):''')
rep("src/competitors/atr_dynamic.py", '''            generation=1,
            leverage_enabled=True,
            leverage=Decimal("2.0")''',
'''            generation=1,
            leverage_enabled=True,
            leverage=Decimal("2.0"),
            news_sensitivity=0.7''')
rep("src/competitors/atr_dynamic.py", '''        timestamp: float,
        side: OrderSide = OrderSide.BUY,
    ) -> Optional[OrderTicket]:''',
'''        timestamp: float,
        side: OrderSide = OrderSide.BUY,
        sizing_multiplier: Decimal = Decimal("1.0"),
    ) -> Optional[OrderTicket]:''')
rep("src/competitors/atr_dynamic.py", '''            stop_price = (market_price - stop_dist).quantize(Decimal("0.01"))
            target_price = (market_price + target_dist).quantize(Decimal("0.01"))

            # Risk budget is struck on unleveraged equity; leverage never inflates it.
            risk_budget = self.portfolio.total_equity * self.genome.atr_risk_pct
            qty = self.compute_r_multiple_qty(market_price, stop_price, broker, risk_budget=risk_budget)''',
'''            stop_price = (market_price - stop_dist).quantize(Decimal("0.01"))
            target_price = (market_price + target_dist).quantize(Decimal("0.01"))

            # Risk budget is struck on unleveraged equity; leverage never inflates it.
            # The news factor scales it inside compute_r_multiple_qty (item 12C).
            risk_budget = self.portfolio.total_equity * self.genome.atr_risk_pct
            qty = self.compute_r_multiple_qty(market_price, stop_price, broker, risk_budget=risk_budget, sizing_multiplier=sizing_multiplier)''')
rep("src/competitors/atr_dynamic.py", '''            stop_price = (market_price + stop_dist).quantize(Decimal("0.01"))
            target_price = (market_price - target_dist).quantize(Decimal("0.01"))

            # Risk budget is struck on unleveraged equity; leverage never inflates it.
            risk_budget = self.portfolio.total_equity * self.genome.atr_risk_pct
            qty = self.compute_r_multiple_qty(market_price, stop_price, broker, risk_budget=risk_budget)''',
'''            stop_price = (market_price + stop_dist).quantize(Decimal("0.01"))
            target_price = (market_price - target_dist).quantize(Decimal("0.01"))

            # Risk budget is struck on unleveraged equity; leverage never inflates it.
            # The news factor scales it inside compute_r_multiple_qty (item 12C).
            risk_budget = self.portfolio.total_equity * self.genome.atr_risk_pct
            qty = self.compute_r_multiple_qty(market_price, stop_price, broker, risk_budget=risk_budget, sizing_multiplier=sizing_multiplier)''')

# --- Trailing Guard (0.5) ---
rep("src/competitors/trailing_guard.py", '''    def __init__(self, portfolio_id: str = "comp_trail", initial_cash: Decimal = Decimal("100000.00")):''',
'''    # News sensitivity (item 12C): trend follower, news impact is indirect.
    NEWS_SENSITIVITY: float = 0.5

    def __init__(self, portfolio_id: str = "comp_trail", initial_cash: Decimal = Decimal("100000.00")):''')
rep("src/competitors/trailing_guard.py", '''            generation=1,
            leverage_enabled=True,
            leverage=Decimal("2.0")''',
'''            generation=1,
            leverage_enabled=True,
            leverage=Decimal("2.0"),
            news_sensitivity=0.5''')
rep("src/competitors/trailing_guard.py", '''        timestamp: float,
        side: OrderSide = OrderSide.BUY,
    ) -> Optional[OrderTicket]:''',
'''        timestamp: float,
        side: OrderSide = OrderSide.BUY,
        sizing_multiplier: Decimal = Decimal("1.0"),
    ) -> Optional[OrderTicket]:''')
rep("src/competitors/trailing_guard.py", '''            self.highest_price_since_entry = market_price
            self.trailing_active = False

            stop_price = (market_price * (Decimal("1") - self.genome.stop_loss_pct)).quantize(Decimal("0.01"))
            qty = self.compute_r_multiple_qty(market_price, stop_price, broker)''',
'''            self.highest_price_since_entry = market_price
            self.trailing_active = False

            stop_price = (market_price * (Decimal("1") - self.genome.stop_loss_pct)).quantize(Decimal("0.01"))
            qty = self.compute_r_multiple_qty(market_price, stop_price, broker, sizing_multiplier=sizing_multiplier)''')
rep("src/competitors/trailing_guard.py", '''            self.lowest_price_since_entry = market_price
            self.trailing_active = False

            stop_price = (market_price * (Decimal("1") + self.genome.stop_loss_pct)).quantize(Decimal("0.01"))
            qty = self.compute_r_multiple_qty(market_price, stop_price, broker)''',
'''            self.lowest_price_since_entry = market_price
            self.trailing_active = False

            stop_price = (market_price * (Decimal("1") + self.genome.stop_loss_pct)).quantize(Decimal("0.01"))
            qty = self.compute_r_multiple_qty(market_price, stop_price, broker, sizing_multiplier=sizing_multiplier)''')

# --- ORB (1.0) ---
rep("src/competitors/orb.py", '''    def __init__(self, portfolio_id: str = "comp_orb", initial_cash: Decimal = Decimal("100000.00")):''',
'''    # News sensitivity (item 12C): breakout eats macro-news sizing in full.
    NEWS_SENSITIVITY: float = 1.0

    def __init__(self, portfolio_id: str = "comp_orb", initial_cash: Decimal = Decimal("100000.00")):''')
rep("src/competitors/orb.py", '''            generation=1,
            leverage_enabled=True,
            leverage=Decimal("2.5")''',
'''            generation=1,
            leverage_enabled=True,
            leverage=Decimal("2.5"),
            news_sensitivity=1.0''')
rep("src/competitors/orb.py", '''        timestamp: float,
        side: OrderSide = OrderSide.BUY,
    ) -> Optional[OrderTicket]:''',
'''        timestamp: float,
        side: OrderSide = OrderSide.BUY,
        sizing_multiplier: Decimal = Decimal("1.0"),
    ) -> Optional[OrderTicket]:''')
rep("src/competitors/orb.py", '''            target_price = (market_price + target_dist).quantize(Decimal("0.01"))

            qty = self.compute_r_multiple_qty(market_price, stop_price, broker)''',
'''            target_price = (market_price + target_dist).quantize(Decimal("0.01"))

            qty = self.compute_r_multiple_qty(market_price, stop_price, broker, sizing_multiplier=sizing_multiplier)''')
rep("src/competitors/orb.py", '''            target_price = (market_price - target_dist).quantize(Decimal("0.01"))

            qty = self.compute_r_multiple_qty(market_price, stop_price, broker)''',
'''            target_price = (market_price - target_dist).quantize(Decimal("0.01"))

            qty = self.compute_r_multiple_qty(market_price, stop_price, broker, sizing_multiplier=sizing_multiplier)''')

# --- Session Mean (0.3) ---
rep("src/competitors/session_mean.py", '''    def __init__(self, portfolio_id: str = "comp_vwap", initial_cash: Decimal = Decimal("100000.00")):''',
'''    # News sensitivity (item 12C): mean reversion often runs against the
    # news direction, so it barely moves on news.
    NEWS_SENSITIVITY: float = 0.3

    def __init__(self, portfolio_id: str = "comp_vwap", initial_cash: Decimal = Decimal("100000.00")):''')
rep("src/competitors/session_mean.py", '''            generation=1,
            leverage_enabled=False,
            leverage=Decimal("1.0")''',
'''            generation=1,
            leverage_enabled=False,
            leverage=Decimal("1.0"),
            news_sensitivity=0.3''')
rep("src/competitors/session_mean.py", '''        timestamp: float,
        side: OrderSide = OrderSide.BUY,
    ) -> Optional[OrderTicket]:''',
'''        timestamp: float,
        side: OrderSide = OrderSide.BUY,
        sizing_multiplier: Decimal = Decimal("1.0"),
    ) -> Optional[OrderTicket]:''')
rep("src/competitors/session_mean.py", '''            target_price = (market_price + target_dist).quantize(Decimal("0.01"))

            qty = self.compute_r_multiple_qty(market_price, stop_price, broker)''',
'''            target_price = (market_price + target_dist).quantize(Decimal("0.01"))

            qty = self.compute_r_multiple_qty(market_price, stop_price, broker, sizing_multiplier=sizing_multiplier)''')
rep("src/competitors/session_mean.py", '''            target_price = (market_price - target_dist).quantize(Decimal("0.01"))

            qty = self.compute_r_multiple_qty(market_price, stop_price, broker)''',
'''            target_price = (market_price - target_dist).quantize(Decimal("0.01"))

            qty = self.compute_r_multiple_qty(market_price, stop_price, broker, sizing_multiplier=sizing_multiplier)''')

# =========================================================== 6. evolution.py: preserve, never mutate
rep("src/arena/evolution.py", '''            leverage_enabled=new_lev_enabled,
            leverage=new_lev
        )

    # Genes eligible for runner-up fine-tuning: (field, low, high, quantum).''',
'''            leverage_enabled=new_lev_enabled,
            leverage=new_lev,
            # News sensitivity is inherited unchanged (item 12C phase 1):
            # crossover blends genes, but this one is a fixed per-strategy
            # slot value, never a blended or mutated gene.
            news_sensitivity=parent1.news_sensitivity
        )

    # Genes eligible for runner-up fine-tuning: (field, low, high, quantum).''')

rep("src/arena/evolution.py", '''            cooldown_bars=genome.cooldown_bars,
            generation=next_gen,
            leverage_enabled=genome.leverage_enabled,
            leverage=genome.leverage
        )
        return new_g, tuned''',
'''            cooldown_bars=genome.cooldown_bars,
            generation=next_gen,
            leverage_enabled=genome.leverage_enabled,
            leverage=genome.leverage,
            # Not in _FINE_TUNE_GENES: the runner-up keeps its sensitivity.
            news_sensitivity=genome.news_sensitivity
        )
        return new_g, tuned''')

rep("src/arena/evolution.py", '''                    cooldown_bars=old_g.cooldown_bars,
                    generation=next_gen,
                    leverage_enabled=old_g.leverage_enabled,
                    leverage=old_g.leverage
                )''',
'''                    cooldown_bars=old_g.cooldown_bars,
                    generation=next_gen,
                    leverage_enabled=old_g.leverage_enabled,
                    leverage=old_g.leverage,
                    news_sensitivity=old_g.news_sensitivity
                )''')

rep("src/arena/evolution.py", '''                        cooldown_bars=new_g.cooldown_bars,
                        generation=next_gen,
                        leverage_enabled=new_g.leverage_enabled,
                        leverage=new_g.leverage
                    )''',
'''                        cooldown_bars=new_g.cooldown_bars,
                        generation=next_gen,
                        leverage_enabled=new_g.leverage_enabled,
                        leverage=new_g.leverage,
                        news_sensitivity=new_g.news_sensitivity
                    )''')

# =========================================================== 7. macro_commander.py: weighted sentiment (C1)
rep("src/intelligence/macro_commander.py", '''import asyncio
from dataclasses import dataclass
import logging
import time''',
'''import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import time''')

rep("src/intelligence/macro_commander.py", '''FALLBACK_MAX_AGE_SEC = 1800.0''',
'''FALLBACK_MAX_AGE_SEC = 1800.0

# Weighted sentiment (item 12C / C1): tier weights, 60-minute half-life,
# 60-minute evidence window, at most the 30 freshest events.
TIER_WEIGHTS = {0: 1.5, 1: 1.2, 2: 1.0, 3: 0.7}
WEIGHTED_WINDOW_MIN = 60.0
WEIGHTED_MAX_EVENTS = 30
WEIGHTED_HALF_LIFE_MIN = 60.0


def _event_age_min(timestamp: str, now: float) -> float:
    """Minutes between an event's ISO8601 timestamp and `now`.

    Unparseable timestamps are treated as fresh (age 0): a malformed
    timestamp must not silently drop a real event from the weighted
    score. Future timestamps (clock skew) clamp to 0.
    """
    try:
        dt = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, (now - dt.timestamp()) / 60.0)
    except (TypeError, ValueError):
        return 0.0''')

rep("src/intelligence/macro_commander.py", '''    fallback: bool = False
    fallback_since_ts: float = 0.0''',
'''    fallback: bool = False
    fallback_since_ts: float = 0.0
    # Weighted sentiment (item 12C): deterministic tier/urgency/time-decay
    # scores from the latest synthesis; 0.0/0.0/0.0 means no usable evidence.
    weighted_sentiment: float = 0.0  # S in [-1, 1]
    weighted_urgency: float = 0.0  # U in [0, 10]
    weighted_coverage: float = 0.0  # N, decay-weighted event count''')

rep("src/intelligence/macro_commander.py", '''            "fallback": self.fallback,
            "fallback_since": time.strftime("%H:%M:%S", time.localtime(self.fallback_since_ts)) if self.fallback_since_ts else "",''',
'''            "fallback": self.fallback,
            "fallback_since": time.strftime("%H:%M:%S", time.localtime(self.fallback_since_ts)) if self.fallback_since_ts else "",
            "weighted_sentiment": round(self.weighted_sentiment, 3),
            "weighted_urgency": round(self.weighted_urgency, 2),
            "weighted_coverage": round(self.weighted_coverage, 2),''')

# Weighted formula + sizing factor, inserted ahead of synthesize_regime.
rep("src/intelligence/macro_commander.py", '''    async def synthesize_regime(self, recent_events: List[StructuredEvent]) -> MacroRegimeState:''',
'''    def compute_weighted_sentiment(
        self, events: List[StructuredEvent], now: Optional[float] = None
    ) -> Tuple[float, float, float]:
        """Deterministic tier/urgency/time-decay weighted sentiment (item 12C).

        Returns (S, U, N): weighted sentiment in [-1, 1], weighted urgency
        in [1, 10], decay-weighted event count. Only events from the last
        60 minutes count (at most the 30 freshest); with no usable evidence
        all three are 0.0. The LLM path uses these as a prompt reference;
        the keyword fallback uses them for direction (C1 thresholds).
        """
        now = time.time() if now is None else now
        scored = []
        for e in events:
            age_min = _event_age_min(e.timestamp, now)
            if age_min > WEIGHTED_WINDOW_MIN:
                continue
            try:
                tier_w = TIER_WEIGHTS.get(int(getattr(e, "tier", 2)), 1.0)
            except (TypeError, ValueError):
                tier_w = 1.0
            urg = max(1, min(10, int(e.urgency_score)))
            urg_w = 0.5 + urg / 10.0
            decay = 0.5 ** (age_min / WEIGHTED_HALF_LIFE_MIN)
            scored.append((tier_w * urg_w * decay, float(e.sentiment_score), float(urg), decay))
        if not scored:
            return 0.0, 0.0, 0.0
        # Freshest first (largest decay), keep at most 30.
        scored.sort(key=lambda item: -item[3])
        scored = scored[:WEIGHTED_MAX_EVENTS]
        total_w = sum(w for w, _, _, _ in scored)
        if total_w <= 0.0:
            return 0.0, 0.0, 0.0
        s = sum(w * sent for w, sent, _, _ in scored) / total_w
        u = sum(w * urg for w, _, urg, _ in scored) / total_w
        n = sum(d for _, _, _, d in scored)
        return max(-1.0, min(1.0, s)), max(0.0, min(10.0, u)), n

    def news_sizing_multiplier(self, news_sensitivity: float = 0.5) -> float:
        """Per-strategy news sizing factor (item 12C / C2).

        base = 1 + (risk_multiplier - 1) * ((confidence - 0.5) / 0.5):
        no confidence (0.5, e.g. keyword fallback) means news does not
        move size at all; full confidence means the full risk_multiplier.
        The per-strategy factor interpolates between 1.0 and base by the
        strategy's news_sensitivity (0.0 = news-blind, 1.0 = full effect).
        Callers pass competitor.genome.news_sensitivity. Result is clamped
        to [0.5, 1.5], the risk_multiplier range.
        """
        try:
            rm = max(0.5, min(1.5, float(self.current_state.risk_multiplier)))
            conf = max(0.5, min(1.0, float(self.current_state.confidence)))
            sens = max(0.0, min(1.0, float(news_sensitivity)))
        except (TypeError, ValueError):
            return 1.0
        base = 1.0 + (rm - 1.0) * ((conf - 0.5) / 0.5)
        mult = 1.0 + (base - 1.0) * sens
        return max(0.5, min(1.5, mult))

    async def synthesize_regime(self, recent_events: List[StructuredEvent]) -> MacroRegimeState:''')

# Empty digest: no evidence means zeroed weighted scores.
rep("src/intelligence/macro_commander.py", '''            if not recent_events:
                self.current_state.last_synthesis_ts = now
                self.current_state.status = "ONLINE" if self.client.is_gateway_online else "STANDBY"''',
'''            if not recent_events:
                self.current_state.last_synthesis_ts = now
                self.current_state.status = "ONLINE" if self.client.is_gateway_online else "STANDBY"
                self.current_state.weighted_sentiment = 0.0
                self.current_state.weighted_urgency = 0.0
                self.current_state.weighted_coverage = 0.0''')

# Compute + store the weighted scores ahead of the LLM call.
rep("src/intelligence/macro_commander.py", '''            intel_digest = "\\n".join(lines)

            system_prompt = (''',
'''            intel_digest = "\\n".join(lines)

            # Weighted reference (item 12C / C1): deterministic tier /
            # urgency / time-decay scores. The LLM still judges, but it
            # sees the same numbers the keyword fallback would use.
            w_s, w_u, w_n = self.compute_weighted_sentiment(recent_events, now)
            self.current_state.weighted_sentiment = w_s
            self.current_state.weighted_urgency = w_u
            self.current_state.weighted_coverage = w_n

            system_prompt = (''')

# Prompt carries the weighted reference.
rep("src/intelligence/macro_commander.py", '''            user_prompt = f"Analyze this live intelligence digest and declare the macro regime:\\n\\n{intel_digest}"''',
'''            user_prompt = (
                f"Analyze this live intelligence digest and declare the macro regime:\\n\\n{intel_digest}\\n\\n"
                f"Weighted reference (deterministic, tier/urgency/60-min half-life): "
                f"S={w_s:+.2f}, U={w_u:.1f}, N={w_n:.1f}. "
                f"Treat N<2 as insufficient evidence for a directional call; "
                f"HOLD_CASH needs S<-0.65, U>=9 and confidence>=0.8."
            )''')

# Fallback direction now comes from S/U/N (C1 thresholds).
rep("src/intelligence/macro_commander.py", '''            else:
                # Fallback: if LLM unreachable or unparseable, compute deterministic sentiment aggregate.
                # Conservative bar on purpose: without the LLM this is keyword
                # soup, so a single bearish word (sentiment -0.45) plus a
                # common urgency-7 word ("rate"/"sec"/"fed") must NOT flip the
                # whole arena into a directional veto. |avg_sent| >= 0.60
                # needs at least two net directional words and urgency >= 8
                # needs a genuinely severe keyword (item 6).
                avg_sent = sum(e.sentiment_score for e in recent_events) / len(recent_events)
                max_urg = max(e.urgency_score for e in recent_events)

                if avg_sent > 0.60 and max_urg >= 8:
                    self.current_state.regime = "BULLISH_SURGE"
                    self.current_state.directional_bias = "LONG_ONLY"
                    self.current_state.risk_multiplier = 1.25
                    self.current_state.active_headline = recent_events[-1].summary[:80]
                elif avg_sent < -0.60 and max_urg >= 8:
                    self.current_state.regime = "BEARISH_PANIC"
                    self.current_state.directional_bias = "SHORT_ONLY"
                    self.current_state.risk_multiplier = 0.75
                    self.current_state.active_headline = recent_events[-1].summary[:80]
                else:
                    self.current_state.regime = "NORMAL"
                    self.current_state.directional_bias = "BIDIRECTIONAL"
                    self.current_state.risk_multiplier = 1.0
                    self.current_state.active_headline = "全球訂單流維持宏觀均衡。實時智能情報監控運行中。"''',
'''            else:
                # Fallback (item 12C / C1): if the LLM is unreachable or
                # unparseable, direction comes from the weighted scores
                # (S/U/N) instead of the old unweighted average + max.
                # The bar is deliberately conservative: one extreme event
                # (N < 2) can never flip the arena, and HOLD_CASH is never
                # set here -- it needs live LLM confidence >= 0.8, which a
                # keyword fallback by definition does not have. Confidence
                # resets to 0.50 ("no confidence"), so news sizing (C2) is
                # neutral until the LLM is back.
                if w_s > 0.45 and w_u >= 7 and w_n >= 2:
                    self.current_state.regime = "BULLISH_SURGE"
                    self.current_state.directional_bias = "LONG_ONLY"
                    self.current_state.risk_multiplier = 1.25
                    self.current_state.active_headline = recent_events[-1].summary[:80]
                elif w_s < -0.45 and w_u >= 7 and w_n >= 2:
                    self.current_state.regime = "BEARISH_PANIC"
                    self.current_state.directional_bias = "SHORT_ONLY"
                    self.current_state.risk_multiplier = 0.75
                    self.current_state.active_headline = recent_events[-1].summary[:80]
                else:
                    self.current_state.regime = "NORMAL"
                    self.current_state.directional_bias = "BIDIRECTIONAL"
                    self.current_state.risk_multiplier = 1.0
                    self.current_state.active_headline = "全球訂單流維持宏觀均衡。實時智能情報監控運行中。"
                self.current_state.confidence = 0.50''')

# =========================================================== 8. live_engine.py: sizing wiring (C2)
rep("src/data/live_engine.py", '''    def _try_enter_ticket(self, competitor: Any, ticket: OrderTicket, price: Decimal, ts: float, event_label: str) -> bool:''',
'''    def _sizing_multiplier_for(self, competitor: Any) -> Decimal:
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

    def _try_enter_ticket(self, competitor: Any, ticket: OrderTicket, price: Decimal, ts: float, event_label: str) -> bool:''')

rep("src/data/live_engine.py", '''        ticket = competitor.evaluate_signal(
            signal=signal,
            market_price=price,
            indicators=self._live_indicators(price),
            broker=self.broker,
            timestamp=ts,
            side=side,
        )''',
'''        ticket = competitor.evaluate_signal(
            signal=signal,
            market_price=price,
            indicators=self._live_indicators(price),
            broker=self.broker,
            timestamp=ts,
            side=side,
            sizing_multiplier=self._sizing_multiplier_for(competitor),
        )''')

rep("src/data/live_engine.py", '''        # Macro Trend Take-Profit Expansion (R-Multiple expanded when riding macro regime)
        if tp is not None and self.macro_commander.current_state.risk_multiplier > 1.0:
            if side == OrderSide.BUY and self.macro_commander.current_state.directional_bias == "LONG_ONLY":
                r_dist = price - sl
                tp = (price + r_dist * Decimal(str(round(2.0 * self.macro_commander.current_state.risk_multiplier, 2)))).quantize(Decimal("0.01"))
            elif side == OrderSide.SELL and self.macro_commander.current_state.directional_bias == "SHORT_ONLY":
                r_dist = sl - price
                tp = (price - r_dist * Decimal(str(round(2.0 * self.macro_commander.current_state.risk_multiplier, 2)))).quantize(Decimal("0.01"))''',
'''        # Macro Trend Take-Profit Expansion (item 12C / C2): TP stretches by
        # the same per-strategy news sizing factor the position size uses,
        # so an optimistic-but-unconfident regime no longer stretches TP.
        sizing_mult = self._sizing_multiplier_for(competitor)
        if tp is not None and sizing_mult > Decimal("1.0"):
            if side == OrderSide.BUY and self.macro_commander.current_state.directional_bias == "LONG_ONLY":
                r_dist = price - sl
                tp = (price + r_dist * Decimal(str(round(2.0 * float(sizing_mult), 2)))).quantize(Decimal("0.01"))
            elif side == OrderSide.SELL and self.macro_commander.current_state.directional_bias == "SHORT_ONLY":
                r_dist = sl - price
                tp = (price - r_dist * Decimal(str(round(2.0 * float(sizing_mult), 2)))).quantize(Decimal("0.01"))''')

rep("src/data/live_engine.py", '''            qty = competitor.compute_r_multiple_qty(price, sl, self.broker, risk_budget=risk_budget)''',
'''            qty = competitor.compute_r_multiple_qty(price, sl, self.broker, risk_budget=risk_budget, sizing_multiplier=sizing_mult)''')

# Snapshot save/restore carries news_sensitivity (old snapshots fall back
# to the slot value via the competitor's NEWS_SENSITIVITY).
rep("src/data/live_engine.py", '''                            "leverage_enabled": g.leverage_enabled,
                            "leverage": str(g.leverage),
                        }''',
'''                            "leverage_enabled": g.leverage_enabled,
                            "leverage": str(g.leverage),
                            "news_sensitivity": g.news_sensitivity,
                        }''')

rep("src/data/live_engine.py", '''                                    leverage_enabled=bool(gd.get("leverage_enabled", False)),
                                    leverage=Decimal(str(gd.get("leverage", "1.0"))),
                                )''',
'''                                    leverage_enabled=bool(gd.get("leverage_enabled", False)),
                                    leverage=Decimal(str(gd.get("leverage", "1.0"))),
                                    news_sensitivity=float(gd.get("news_sensitivity", getattr(c, "NEWS_SENSITIVITY", 0.5))),
                                )''')

# =========================================================== 9. existing test fixtures: fresh timestamps
# The 60-minute evidence window (C1) treats the old fixed midnight
# timestamps as stale; these fixtures test thresholds, not staleness,
# so they stamp events fresh at run time.
rep("tests/test_item12a_omniroute.py", '''import asyncio
import io
import time
import urllib.error''',
'''import asyncio
import io
import time
import urllib.error
from datetime import datetime, timezone''')

rep("tests/test_item12a_omniroute.py", '''def _strong_bearish_events():
    return [
        StructuredEvent(timestamp="2026-11-13T00:00:00Z", source="Test", domain="macro", entities_tickers=["FED"], urgency_score=9, sentiment_score=-0.70, summary="Strong bearish 1"),
        StructuredEvent(timestamp="2026-11-13T00:00:00Z", source="Test", domain="macro", entities_tickers=["FED"], urgency_score=8, sentiment_score=-0.85, summary="Strong bearish 2"),
    ]''',
'''def _now_iso():
    # Weighted sentiment (item 12C) only counts events from the last 60
    # minutes, so threshold fixtures must be fresh at run time.
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _strong_bearish_events():
    return [
        StructuredEvent(timestamp=_now_iso(), source="Test", domain="macro", entities_tickers=["FED"], urgency_score=9, sentiment_score=-0.70, summary="Strong bearish 1"),
        StructuredEvent(timestamp=_now_iso(), source="Test", domain="macro", entities_tickers=["FED"], urgency_score=8, sentiment_score=-0.85, summary="Strong bearish 2"),
    ]''')

rep("tests/test_intel_veto.py", '''import asyncio
import socket
import subprocess
import sys
import time''',
'''import asyncio
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone''')

rep("tests/test_intel_veto.py", '''        weak = StructuredEvent(timestamp="2026-11-13T00:00:00Z", source="Test", domain="macro", entities_tickers=["FED"], urgency_score=7, sentiment_score=-0.45, summary="Weak signal")''',
'''        weak = StructuredEvent(timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), source="Test", domain="macro", entities_tickers=["FED"], urgency_score=7, sentiment_score=-0.45, summary="Weak signal")''')

rep("tests/test_intel_veto.py", '''            StructuredEvent(timestamp="2026-11-13T00:00:00Z", source="Test", domain="macro", entities_tickers=["FED"], urgency_score=9, sentiment_score=-0.70, summary="Strong bearish 1"),
            StructuredEvent(timestamp="2026-11-13T00:00:00Z", source="Test", domain="macro", entities_tickers=["FED"], urgency_score=8, sentiment_score=-0.85, summary="Strong bearish 2"),''',
'''            StructuredEvent(timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), source="Test", domain="macro", entities_tickers=["FED"], urgency_score=9, sentiment_score=-0.70, summary="Strong bearish 1"),
            StructuredEvent(timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), source="Test", domain="macro", entities_tickers=["FED"], urgency_score=8, sentiment_score=-0.85, summary="Strong bearish 2"),''')

# =========================================================== 10. new tests (C4)
NEW_FILES["tests/test_weighted_sentiment.py"] = '''"""Item 12C tests: weighted sentiment (C1) - tier weights, 60-minute
half-life decay, coverage gate, and the C1 direction thresholds."""
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

from src.intelligence.ingestion import StructuredEvent
from src.intelligence.macro_commander import MacroCommander


def _now_iso(age_min: float = 0.0) -> str:
    ts = datetime.now(timezone.utc) - timedelta(minutes=age_min)
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


def _ev(sent, urg, tier=2, age_min=0.0):
    return StructuredEvent(
        timestamp=_now_iso(age_min), source="Test", domain="macro",
        entities_tickers=["ETH"], urgency_score=urg, sentiment_score=sent,
        summary="s", tier=tier,
    )


def _offline_commander():
    mock_client = MagicMock()
    mock_client.is_gateway_online = False
    mock_client.chat_json = AsyncMock(return_value=None)
    return MacroCommander(mock_client)


def test_tier_weight_tier1_outweighs_tier3():
    c = _offline_commander()
    # Same urgency, opposite sentiment: tier 1 (w 1.2) beats tier 3 (w 0.7).
    s, u, n = c.compute_weighted_sentiment([
        _ev(+1.0, 5, tier=1), _ev(-1.0, 5, tier=3),
    ])
    assert abs(s - (1.2 - 0.7) / 1.9) < 0.01
    assert abs(u - 5.0) < 0.01
    assert abs(n - 2.0) < 0.01


def test_half_life_decay_60_min_is_half_weight():
    c = _offline_commander()
    # Fresh +1.0 vs 60-min-old -1.0: old event weighs half -> S = (1-0.5)/1.5.
    s, u, n = c.compute_weighted_sentiment([
        _ev(+1.0, 5, age_min=0.0), _ev(-1.0, 5, age_min=60.0),
    ])
    assert abs(s - (1.0 / 3.0)) < 0.02
    assert abs(n - 1.5) < 0.02


def test_events_older_than_60_min_excluded():
    c = _offline_commander()
    s, u, n = c.compute_weighted_sentiment([_ev(-1.0, 10, age_min=61.0)])
    assert (s, u, n) == (0.0, 0.0, 0.0)
    assert c.compute_weighted_sentiment([]) == (0.0, 0.0, 0.0)


def test_single_extreme_event_never_flips_direction():
    c = _offline_commander()
    state = asyncio.run(c.synthesize_regime([_ev(-1.0, 10)]))
    assert state.directional_bias == "BIDIRECTIONAL"
    assert state.regime == "NORMAL"
    assert state.weighted_coverage < 2.0


def test_direction_thresholds_long_and_short():
    c = _offline_commander()
    long_state = asyncio.run(c.synthesize_regime([_ev(0.5, 8), _ev(0.5, 8), _ev(0.5, 8)]))
    assert long_state.directional_bias == "LONG_ONLY"
    assert long_state.regime == "BULLISH_SURGE"
    assert abs(long_state.weighted_sentiment - 0.5) < 0.01
    assert abs(long_state.weighted_urgency - 8.0) < 0.01
    assert abs(long_state.weighted_coverage - 3.0) < 0.01
    short_state = asyncio.run(c.synthesize_regime([_ev(-0.5, 8), _ev(-0.5, 8), _ev(-0.5, 8)]))
    assert short_state.directional_bias == "SHORT_ONLY"
    assert short_state.regime == "BEARISH_PANIC"


def test_fallback_never_enters_hold_cash():
    c = _offline_commander()
    # S=-0.7, U=9 would be HOLD_CASH territory, but the keyword fallback
    # has no LLM confidence, so it must stop at SHORT_ONLY.
    state = asyncio.run(c.synthesize_regime([_ev(-0.7, 9), _ev(-0.7, 9)]))
    assert state.directional_bias == "SHORT_ONLY"
    assert state.confidence == 0.50


def test_llm_hold_cash_with_confidence_passes_through():
    mock_client = MagicMock()
    mock_client.is_gateway_online = True
    mock_client.chat_json = AsyncMock(return_value={
        "regime": "BEARISH_PANIC", "directional_bias": "HOLD_CASH",
        "risk_multiplier": 0.5, "active_headline": "Severe risk-off",
        "confidence": 0.9,
    })
    c = MacroCommander(mock_client)
    state = asyncio.run(c.synthesize_regime([_ev(-0.7, 9), _ev(-0.7, 9)]))
    assert state.directional_bias == "HOLD_CASH"
    assert state.confidence == 0.9


def test_weighted_scores_exposed_in_state_dict():
    c = _offline_commander()
    asyncio.run(c.synthesize_regime([_ev(0.5, 8), _ev(0.5, 8), _ev(0.5, 8)]))
    d = c.current_state.to_dict()
    assert abs(d["weighted_sentiment"] - 0.5) < 0.01
    assert abs(d["weighted_urgency"] - 8.0) < 0.01
    assert abs(d["weighted_coverage"] - 3.0) < 0.01
'''

NEW_FILES["tests/test_news_sizing.py"] = '''"""Item 12C tests: news sizing multiplier (C2) - confidence scaling,
per-strategy sensitivity, budget math, SL untouched, TP factor, and the
backtest default of 1.0."""
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from src.arena.broker_sim import BrokerSim
from src.arena.order import OrderSide
from src.competitors.aggressive import AggressiveCompetitor
from src.competitors.atr_dynamic import ATRDynamicCompetitor
from src.competitors.base import CompetitorGenome
from src.competitors.conservative import ConservativeCompetitor
from src.competitors.orb import ORBCompetitor
from src.data.live_engine import LiveArenaEngine
from src.intelligence.macro_commander import MacroCommander


def _commander(rm=1.0, conf=0.5):
    mock_client = MagicMock()
    mock_client.is_gateway_online = True
    c = MacroCommander(mock_client)
    c.current_state.risk_multiplier = rm
    c.current_state.confidence = conf
    return c


def _broker():
    return BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0.0"))


def test_no_confidence_means_no_sizing_effect():
    c = _commander(rm=1.5, conf=0.5)
    assert c.news_sizing_multiplier(1.0) == 1.0
    c2 = _commander(rm=0.5, conf=0.5)
    assert c2.news_sizing_multiplier(1.0) == 1.0
    assert c2.news_sizing_multiplier(0.3) == 1.0


def test_sizing_formula_exact_values():
    c = _commander(rm=1.5, conf=1.0)
    assert c.news_sizing_multiplier(1.0) == 1.5
    c2 = _commander(rm=0.5, conf=1.0)
    assert c2.news_sizing_multiplier(1.0) == 0.5
    c3 = _commander(rm=1.5, conf=0.8)
    assert abs(c3.news_sizing_multiplier(1.0) - 1.30) < 1e-9
    c4 = _commander(rm=0.5, conf=0.8)
    assert abs(c4.news_sizing_multiplier(1.0) - 0.70) < 1e-9


def test_per_strategy_sensitivity_scales_the_deviation():
    c = _commander(rm=1.5, conf=1.0)
    assert c.news_sizing_multiplier(1.0) == 1.5   # ORB eats the full move
    assert abs(c.news_sizing_multiplier(0.3) - 1.15) < 1e-9  # CONS eats 30%
    assert c.news_sizing_multiplier(0.0) == 1.0   # news-blind


def test_genome_news_sensitivity_defaults_and_validation():
    assert ORBCompetitor().genome.news_sensitivity == 1.0
    assert AggressiveCompetitor().genome.news_sensitivity == 0.8
    assert ATRDynamicCompetitor().genome.news_sensitivity == 0.7
    assert ConservativeCompetitor().genome.news_sensitivity == 0.3
    with pytest.raises(ValueError):
        CompetitorGenome(news_sensitivity=1.5)
    with pytest.raises(ValueError):
        CompetitorGenome(news_sensitivity=-0.1)


def test_compute_r_multiple_qty_scales_budget_and_clamps():
    comp = AggressiveCompetitor()
    broker = _broker()
    # No sizing: budget 2500, stop dist 87.50 -> 28.5714, capped at 28.0000.
    assert comp.compute_r_multiple_qty(Decimal("2500.00"), Decimal("2412.50"), broker) == Decimal("28.0000")
    # Sizing 0.5: budget 1250 -> 14.2857; stop-out loss stays within budget.
    qty = comp.compute_r_multiple_qty(Decimal("2500.00"), Decimal("2412.50"), broker, sizing_multiplier=Decimal("0.5"))
    assert qty == Decimal("14.2857")
    assert qty * Decimal("87.50") <= Decimal("1250.00")
    # Sizing below the 0.5 floor clamps to 0.5.
    assert comp.compute_r_multiple_qty(Decimal("2500.00"), Decimal("2412.50"), broker, sizing_multiplier=Decimal("0.1")) == Decimal("14.2857")


def test_evaluate_signal_sizing_shrinks_qty_not_sl():
    comp = AggressiveCompetitor()
    broker = _broker()
    broker.register_portfolio(comp.portfolio, max_position_ratio=comp.max_position_ratio)
    broker.on_tick(Decimal("2500.00"), timestamp=100.0)
    base = comp.evaluate_signal("BUY", Decimal("2500.00"), {"atr": Decimal("35.00")}, broker, 100.0)
    small = comp.evaluate_signal("BUY", Decimal("2500.00"), {"atr": Decimal("35.00")}, broker, 100.0, sizing_multiplier=Decimal("0.5"))
    assert base is not None and small is not None
    assert small.stop_loss == base.stop_loss  # SL is a risk floor, not a mood
    assert small.qty == Decimal("14.2857")
    assert small.qty < base.qty


def test_atr_risk_budget_scaled_by_sizing():
    comp = ATRDynamicCompetitor()
    broker = _broker()
    broker.register_portfolio(comp.portfolio, max_position_ratio=comp.max_position_ratio)
    broker.on_tick(Decimal("2500.00"), timestamp=100.0)
    ticket = comp.evaluate_signal("BUY", Decimal("2500.00"), {"atr": Decimal("35.00")}, broker, 100.0, sizing_multiplier=Decimal("0.5"))
    assert ticket is not None
    # atr budget 1500 * 0.5 = 750; stop dist 52.50 -> 14.2857 (cap 20).
    assert ticket.qty == Decimal("14.2857")


def test_backtest_default_sizing_is_one():
    comp = AggressiveCompetitor()
    broker = _broker()
    broker.register_portfolio(comp.portfolio, max_position_ratio=comp.max_position_ratio)
    broker.on_tick(Decimal("2500.00"), timestamp=100.0)
    default = comp.evaluate_signal("BUY", Decimal("2500.00"), {"atr": Decimal("35.00")}, broker, 100.0)
    explicit = comp.evaluate_signal("BUY", Decimal("2500.00"), {"atr": Decimal("35.00")}, broker, 100.0, sizing_multiplier=Decimal("1.0"))
    assert default is not None and explicit is not None
    assert default.qty == explicit.qty == Decimal("28.0000")


def _tp_engine(confidence):
    """Fresh engine with a passing MC gate and an optimistic macro state;
    returns the TP price armed by one LONG bracket entry."""
    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    engine.is_bootstrapped = True
    engine.live_orders_enabled = True
    engine.live_atr = Decimal("20.00")
    engine.candles = []
    engine.broker.on_tick(Decimal("2500.00"), timestamp=1000.0)
    mc = MagicMock()
    mc.passed = True
    mc.expected_r = Decimal("1.5")
    mc.green_prob = Decimal("0.6")
    mc.neither_prob = Decimal("0.1")
    mc.decided_win_rate = Decimal("0.6")
    mc.verdict = "PASS"
    mc.to_dict.return_value = {}
    engine.macro_commander.current_state.directional_bias = "LONG_ONLY"
    engine.macro_commander.current_state.risk_multiplier = 1.5
    engine.macro_commander.current_state.confidence = confidence
    with patch.object(engine, "is_entry_permitted_by_mtf", return_value=True), \\
            patch.object(engine.mc_evaluator, "evaluate_bracket", return_value=mc):
        ok = engine._try_enter_bracket(
            engine.comp_a, Decimal("2500.00"), Decimal("2412.50"),
            Decimal("2600.00"), 1000.0, "TEST", side=OrderSide.BUY,
        )
    assert ok is True
    return engine.broker.active_targets["comp_agg"].price


def test_tp_stretch_uses_sizing_mult_not_raw_rm():
    # Full confidence: AGG sensitivity 0.8 -> sizing 1.40 -> TP factor 2.80:
    # 2500 + 87.50 * 2.80 = 2745.00.
    assert _tp_engine(1.0) == Decimal("2745.00")
    # No confidence: sizing 1.0 -> no stretch, TP stays as given.
    assert _tp_engine(0.5) == Decimal("2600.00")
'''


# =========================================================== apply (verify ALL, then write)
def main():
    # Phase 1: verify every replacement matches exactly once, and no new
    # file already exists. Nothing is written until all checks pass, so a
    # bad anchor can never leave a half-applied patch behind.
    contents: dict = {}
    for path, old, new in REPLACEMENTS:
        if path not in contents:
            with open(path, "r", encoding="utf-8", newline="") as f:
                contents[path] = f.read()
        n = contents[path].count(old)
        if n != 1:
            print(f"FAIL {path}: expected 1 occurrence, found {n} for: {old[:80]!r}")
            sys.exit(1)
    for path in NEW_FILES:
        if os.path.exists(path):
            print(f"FAIL {path}: already exists, refusing to overwrite")
            sys.exit(1)
    # Phase 2: apply.
    for path, old, new in REPLACEMENTS:
        contents[path] = contents[path].replace(old, new)
        print(f"OK {path}")
    for path, content in contents.items():
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(content)
    for path, content in NEW_FILES.items():
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        print(f"NEW {path}")
    print(f"Applied {len(REPLACEMENTS)} replacements + {len(NEW_FILES)} new files.")


if __name__ == "__main__":
    main()
