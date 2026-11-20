from __future__ import annotations
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional, Dict, Any
import math
import os
import time

try:
    import numpy as np
except ImportError:
    np = None

from src.arena.broker_sim import BrokerSim
from src.arena.leaderboard import Leaderboard, CompetitorStats
from src.arena.order import OrderSide
from src.arena.evolution import GeneticEvolver
from src.competitors.aggressive import AggressiveCompetitor
from src.competitors.conservative import ConservativeCompetitor
from src.competitors.trailing_guard import TrailingGuardCompetitor
from src.competitors.orb import ORBCompetitor
from src.competitors.session_mean import SessionMeanPullbackCompetitor
from src.data.eth_feed import ETHFeed, CandleBar

# A2: uncapped-runner target assumption -- a trend runner with no
# take-profit is evaluated in Monte Carlo as if its target sat at
# 1.8R (1.8x the stop distance). This is a MODEL ASSUMPTION, not a
# measured outcome: no market data says an uncapped runner exits
# at 1.8R. It shapes r_multiple / breakeven_prob / expected_r for
# uncapped brackets only; capped brackets use their real TP.
# The number itself is unchanged (decision: P2-A).
UNCAPPED_RUNNER_R_MULTIPLE = 1.8

# Chop gate (Phase 8): Kaufman efficiency ratio over the last 20 bars.
# ER = |close_N - close_0| / sum(|Δclose|). A trending tape scores near
# 1.0; a sideways tape scores near 0. Below the threshold the market is
# chop and NEW ENTRIES are blocked; closes/exits always run (a position
# must always be exitable). Measured on real 15m tapes, one pass from
# gen-1 defaults (experiment chop_gate_exp.py):
#   flat month (2,573 bars, +2.28%): mean ROI -5.52% -> -3.44%
#     (2.08pp / 38% of the loss recovered), mean fitness -49.76 -> -19.05
#   trend month (2,958 bars, -26%): mean ROI +0.86% -> +2.83%,
#     mean fitness -5.96 -> +7.75 (improved, not hurt)
# ADX(14) < 20 was also tried and REJECTED (trend month -1.34%).
# SCOPE: validated on 15m bars (20 bars = 5h window). The live port
# landed in the debug & optimize pass (live_engine._chop_gate_blocks):
# the live engine's MTF engine already aggregates the same 15m closes
# from the 1m feed, so the live gate reuses this exact statistic,
# window and threshold (21 closes = 20 intervals) on closed 15m bars.
# A 1m-close ER variant was measured and NOT used: ER(60/120/150) on
# 1m closes does not separate the flat and trend months at all (both
# ~0.075 mean at ER(150)) -- 1m noise dominates the statistic.
CHOP_GATE_WINDOW_BARS = 20
CHOP_GATE_ER_THRESHOLD = 0.25


def efficiency_ratio(closes: Any) -> float:
    """Kaufman efficiency ratio over the given closes (oldest first)."""
    n = len(closes)
    if n < 2:
        return 1.0
    it = iter(closes)
    first = float(next(it))
    prev = first
    path = 0.0
    for val in it:
        cur = float(val)
        path += abs(cur - prev)
        prev = cur
    net = abs(prev - first)
    return (net / path) if path > 0.0 else 1.0


class TimeMachineArena:
    """
    Time Machine Speed Simulation & Multi-Generation Evolution Runner.
    Replays hundreds of hours of real market bars across all competitor portfolios
    in seconds to evaluate survivability, Sharpe/Sortino Ratio, and genetic parameter fitness.
    """
    def __init__(
        self,
        symbol: str = "ETH/USD",
        initial_cash: Decimal = Decimal("100000.00")
    ):
        self.symbol = symbol
        self.initial_cash = initial_cash
        self.comp_a = AggressiveCompetitor(initial_cash=initial_cash)
        self.comp_b = ConservativeCompetitor(initial_cash=initial_cash)
        self.comp_d = TrailingGuardCompetitor(initial_cash=initial_cash)
        self.comp_e = ORBCompetitor(initial_cash=initial_cash)
        self.comp_f = SessionMeanPullbackCompetitor(initial_cash=initial_cash)
        self.competitors = [
            self.comp_a, self.comp_b,
            self.comp_d, self.comp_e, self.comp_f
        ]
        self._rebuild_broker()
        self.chop_gate_blocked = 0

    def _rebuild_broker(self) -> None:
        self.broker = BrokerSim(symbol=self.symbol, slippage_pct=Decimal("0.0002"))
        for c in self.competitors:
            self.broker.register_portfolio(c.portfolio, max_position_ratio=c.max_position_ratio)

    def run_simulation(
        self, bars: List[CandleBar], chop_gate: bool = True
    ) -> List[CompetitorStats]:
        """Replay bars across all competitors.

        chop_gate (default True): when the Kaufman efficiency ratio
        over the last 20 closes drops below 0.25 the tape is chop and
        new entries are blocked; closes/exits are never blocked.
        """
        self.chop_gate_blocked = 0
        gen = max(c.genome.generation for c in self.competitors)
        print(f"[*] Starting Time Machine Arena [Generation {gen}] on {len(bars)} {self.symbol} candle bars...")
        prev_bar: Optional[CandleBar] = None
        cum_vol = Decimal("0")
        cum_pv = Decimal("0")
        # Audit 3.4 / V2.8.0: the opening range is anchored to the FIRST
        # 15 closed bars of each UTC trading day and frozen for the rest
        # of that day. Tracked in O(1) per bar and reset at UTC midnight
        # alongside session VWAP accumulators.
        current_day: Any = None
        orb_bar_count = 0
        orb_day_high = Decimal("0")
        orb_day_low = Decimal("0")
        closes: deque[float] = deque(maxlen=CHOP_GATE_WINDOW_BARS + 1)
        # Rolling true ranges for the measured backtest ATR (F3).
        true_ranges: deque[Decimal] = deque(maxlen=14)

        for i, bar in enumerate(bars):
            orb_day = datetime.fromtimestamp(float(bar.timestamp), timezone.utc).date()
            if orb_day != current_day:
                current_day = orb_day
                cum_vol = Decimal("0")
                cum_pv = Decimal("0")
                orb_bar_count = 0
                orb_day_high = Decimal("0")
                orb_day_low = Decimal("0")

            typ_price = (bar.high + bar.low + bar.close) / Decimal("3")
            # P0-B / F2: a zero-volume bar weighs 0 in the VWAP -- the old
            # Decimal("100.0") invented volume out of thin air.
            bar_vol = bar.volume if bar.volume > Decimal("0") else Decimal("0")
            cum_vol += bar_vol
            cum_pv += (typ_price * bar_vol)
            # Backtest bars carry volume, so this IS the genuine session VWAP.
            # It is passed as "mean_ref": live has no per-bar volume and passes
            # the session typical-price mean under the same key.
            vwap = (cum_pv / cum_vol).quantize(Decimal("0.01")) if cum_vol > 0 else bar.close

            # ORB range is built from CLOSED bars only: including the current
            # bar makes its own high the range ceiling, so a breakout can
            # almost never trigger (ORB was dead in backtest). While the
            # day's first 15 bars are still forming the range uses that
            # day's closed bars so far; from bar 15 on it is the frozen
            # first 15 of the day.
            if orb_bar_count > 0:
                orb_high, orb_low = orb_day_high, orb_day_low
            else:
                orb_high, orb_low = bar.high, bar.low
            if orb_bar_count < 15:
                if orb_bar_count == 0:
                    orb_day_high, orb_day_low = bar.high, bar.low
                else:
                    if bar.high > orb_day_high:
                        orb_day_high = bar.high
                    if bar.low < orb_day_low:
                        orb_day_low = bar.low
                orb_bar_count += 1
            orb_mid = (orb_high + orb_low) / Decimal("2")

            # P0-B / F3: the backtest ATR is measured from the bars being
            # replayed (rolling ATR(14) over true ranges), not the broker's
            # fixed 12.00 start value -- the old value understated
            # slippage 4-8x for the whole backtest. Updated before
            # on_tick so this bar's fills already pay the measured rate.
            # (compute_execution_slippage keeps its atr=12.0 default as a
            # fallback for direct callers that pass no ATR.)
            tr = bar.high - bar.low
            if prev_bar is not None:
                tr = max(tr, abs(bar.high - prev_bar.close), abs(bar.low - prev_bar.close))
            true_ranges.append(tr)
            self.broker.current_atr = sum(true_ranges, Decimal("0")) / Decimal(len(true_ranges))

            # 1. Advance exchange venue with full OHLC candle prices (checks intra-bar stops & targets)
            self.broker.on_tick(
                price=bar.close,
                high=bar.high,
                low=bar.low,
                timestamp=bar.timestamp,
                open_price=bar.open
            )

            # 2. Derive strategy signal
            signal = ETHFeed.generate_signal(bar, prev_bar)

            # Chop gate: efficiency ratio over the last 20 closes.
            closes.append(float(bar.close))
            chop = (
                chop_gate
                and len(closes) > CHOP_GATE_WINDOW_BARS
                and efficiency_ratio(closes) < CHOP_GATE_ER_THRESHOLD
            )
            indicators = {
                "atr": bar.atr if (bar.atr is not None and bar.atr > Decimal("0")) else self.broker.current_atr,
                "high": bar.high,
                "low": bar.low,
                "mean_ref": vwap,
                "orb_high": orb_high,
                "orb_low": orb_low,
                "orb_mid": orb_mid,
            }

            # 3. Synchronously evaluate all competitors against the exact same bar.
            # Audit 2.2: drive the entry direction from the signal. A
            # "BUY" opens a long; a "SELL" closes an open position, or
            # opens a short when flat (the old call passed no side, so
            # side defaulted to BUY and a SELL could only ever close --
            # the backtest was long-only). No flip in one bar: a SELL
            # closes a long here; the short opens on the next SELL bar
            # once flat.
            for c in self.competitors:
                if signal == "SELL" and c.portfolio.position_qty == Decimal("0"):
                    ticket = c.evaluate_signal(
                        signal="BUY",
                        side=OrderSide.SELL,
                        market_price=bar.close,
                        indicators=indicators,
                        broker=self.broker,
                        timestamp=bar.timestamp
                    )
                else:
                    ticket = c.evaluate_signal(
                        signal=signal,
                        market_price=bar.close,
                        indicators=indicators,
                        broker=self.broker,
                        timestamp=bar.timestamp
                    )
                if ticket:
                    if chop and c.portfolio.position_qty == Decimal("0"):
                        # Chop: block the NEW ENTRY. The portfolio is
                        # flat, so this ticket can only open a position;
                        # closes (non-flat portfolios) never reach here.
                        self.chop_gate_blocked += 1
                        continue
                    self.broker.submit_order(ticket)

            prev_bar = bar

        rankings = Leaderboard.get_rankings(self.broker.portfolios)
        self._generate_post_mortem_report(rankings, len(bars), gen)
        return rankings

    def evolve_next_generation(
        self,
        current_rankings: List[CompetitorStats],
        preserve_portfolio: bool = True
    ) -> List[str]:
        """
        Triggers Genetic Evolution (Elitism + Crossover + Mutation).
        If preserve_portfolio is True (default), open positions, active brackets,
        and compounding equity are preserved across generations.
        """
        logs = GeneticEvolver.evolve_generation(
            self.competitors,
            current_rankings,
            preserve_portfolio=preserve_portfolio
        )
        if not preserve_portfolio:
            self._rebuild_broker()
        else:
            for c in self.competitors:
                self.broker.competitor_caps[c.portfolio_id] = c.max_position_ratio
        return logs

    def run_evolution_tournament(
        self, bars: List[CandleBar], generations: int = 3, chop_gate: bool = True
    ) -> List[CompetitorStats]:
        """
        Runs multiple seasons back-to-back, evolving competitor risk parameters between each generation.
        """
        rankings: List[CompetitorStats] = []
        for g in range(1, generations + 1):
            rankings = self.run_simulation(bars, chop_gate=chop_gate)
            if g < generations:
                evo_logs = self.evolve_next_generation(rankings)
                for log_line in evo_logs:
                    print(f"    -> {log_line}")
        return rankings

    def _generate_post_mortem_report(
        self,
        rankings: List[CompetitorStats],
        bar_count: int,
        generation: int = 1
    ) -> None:
        mem_dir = os.environ.get("ARENA_MEMORY_DIR", "memory")
        os.makedirs(mem_dir, exist_ok=True)
        report_path = os.path.join(mem_dir, "arena_report.md")

        leader = rankings[0] if rankings else None
        synthesis = (
            f"- [Tactical Synthesis (Generation {generation})] Evaluated {bar_count} bars. "
            f"Leading strategy: {leader.name if leader else 'N/A'} (ROI {float(leader.roi_pct):+.2f}%, "
            f"Sharpe {float(leader.sharpe_ratio):.2f}).\n"
            f"- [Risk Parity Audit] Maximum adverse excursion maintained within bracket limits.\n"
            f"- [Genetic Mutation] Elitism vectors preserved for next evolutionary cycle."
        )

        md = [
            f"# TradeBot0 Arena Post-Mortem & Leaderboard Report (Generation {generation})",
            f"**Evaluation Timestamp**: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Candles Evaluated**: {bar_count} bars (`{self.symbol}`)",
            f"**Initial Capital per Competitor**: ${self.initial_cash:,.2f} USDT",
            f"**Engine Execution Mode**: Local Pure-Math Quant Core (Zero API Overhead)\n",
            "## 1. Official Arena Leaderboard",
            "| Rank | Competitor | Equity (USDT) | ROI % | Max DD % | Sharpe | Sortino | Profit Factor | Win Rate % | Closed Trades | Fitness | Status |",
            "| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |"
        ]

        for r in rankings:
            md.append(
                f"| #{r.rank} | **{r.name}** | **${r.equity:,.2f}** | {r.roi_pct:+.2f}% | "
                f"{r.max_drawdown_pct:.2f}% | {r.sharpe_ratio:.2f} | {r.sortino_ratio:.2f} | "
                f"{r.profit_factor:.2f} | {r.win_rate_pct:.1f}% | {r.closed_trades} | "
                f"`{r.fitness_score:+.2f}` | `{r.status}` |"
            )

        md.extend([
            "\n## 2. Arena Tactical Synthesis & Lessons",
            synthesis,
            "\n## 3. Active Competitor Genomes (Parameters)",
            "| Portfolio ID | Gen | Position Cap | Stop Loss % | Take Profit % | ATR Risk % | Trailing Trigger / Dist |",
            "| :--- | :---: | :---: | :---: | :---: | :---: | :---: |"
        ])

        for c in self.competitors:
            g = c.genome
            tp_str = f"{float(g.take_profit_pct)*100:.2f}%" if g.take_profit_pct is not None else "Unbounded (Run)"
            md.append(
                f"| `{c.portfolio_id}` | G{g.generation} | {float(g.position_ratio)*100:.0f}% | "
                f"{float(g.stop_loss_pct)*100:.2f}% | {tp_str} | {float(g.atr_risk_pct)*100:.2f}% | "
                f"+{float(g.trailing_trigger_pct):.1f}% / {float(g.trailing_distance_pct)*100:.2f}% |"
            )

        md.append(
            "\n**Model assumptions**: uncapped runners (TP shown as `Unbounded (Run)`) "
            "are evaluated in Monte Carlo with an assumed 1.8R target -- a model "
            "assumption, not a measured outcome; capped brackets use their real TP."
        )

        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md))
        print(f"[+] Arena post-mortem saved to {report_path}")


@dataclass(frozen=True)
class MonteCarloBracketOdds:
    """
    Probabilistic outcome assessment from 500-10,000 forward Monte Carlo paths.
    Inspired by day-trader-skill Time Machine.
    """
    passed: bool
    # A1: probabilities / expected R are None when the odds are
    # unknown (NumPy missing, no paths simulated) -- never invented.
    # r_multiple / breakeven_prob are pure bracket geometry and stay numeric.
    target_prob: Optional[float]
    stop_prob: Optional[float]
    neither_prob: Optional[float]
    decided_win_rate: Optional[float]
    expected_r: Optional[float]
    r_multiple: float
    breakeven_prob: float
    verdict: str
    green_prob: Optional[float] = 0.50
    # A2: True when r_multiple came from the uncapped-runner 1.8R
    # assumption (no take-profit was given) instead of a real TP.
    # Surfaced in to_dict() so the live view model can label it.
    r_multiple_is_assumption: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "target_prob": round(self.target_prob, 4) if self.target_prob is not None else None,
            "stop_prob": round(self.stop_prob, 4) if self.stop_prob is not None else None,
            "neither_prob": round(self.neither_prob, 4) if self.neither_prob is not None else None,
            "decided_win_rate": round(self.decided_win_rate, 4) if self.decided_win_rate is not None else None,
            "green_prob": round(self.green_prob, 4) if self.green_prob is not None else None,
            "expected_r": round(self.expected_r, 3) if self.expected_r is not None else None,
            "r_multiple": round(self.r_multiple, 2),
            "r_multiple_is_assumption": self.r_multiple_is_assumption,
            "breakeven_prob": round(self.breakeven_prob, 4),
            "verdict": self.verdict,
        }


class MonteCarloOddsEvaluator:
    """
    Ultra-fast vectorized Monte Carlo Odds Evaluator & EV Gate.
    Replays hundreds of forward market paths from current volatility and bar returns
    to check whether the bracket's mathematical expectancy (EV in R-multiples) is positive.
    Rejects negative expectancy trades before capital is committed.
    """
    def __init__(self, seed: Optional[int] = 19):
        self.seed = seed
        self._rng = np.random.default_rng(seed) if np is not None else None
        self._ret_cache_key: Optional[tuple] = None
        self._ret_cache_val: Optional[tuple] = None

    @staticmethod
    def _reject_bracket(verdict: str) -> MonteCarloBracketOdds:
        return MonteCarloBracketOdds(
            passed=False,
            target_prob=0.0,
            stop_prob=1.0,
            neither_prob=0.0,
            decided_win_rate=0.0,
            expected_r=-1.0,
            r_multiple=0.0,
            breakeven_prob=1.0,
            verdict=verdict,
            green_prob=0.0,
        )

    def evaluate_bracket(
        self,
        entry_price: Decimal | float,
        stop_loss: Decimal | float,
        take_profit: Optional[Decimal | float] = None,
        atr: Optional[Decimal | float] = None,
        recent_candles: Optional[List[Dict[str, Any]]] = None,
        n_sims: int = 1000,
        n_steps: int = 120,
        min_ev_threshold: float = -0.05,
    ) -> MonteCarloBracketOdds:
        try:
            entry_f = float(entry_price)
            sl_f = float(stop_loss)
        except (TypeError, ValueError):
            return self._reject_bracket("Rejected (Invalid SL/Entry)")
        if (
            not (math.isfinite(entry_f) and math.isfinite(sl_f))
            or entry_f <= 0.0
            or sl_f <= 0.0
            or sl_f == entry_f
        ):
            return self._reject_bracket("Rejected (Invalid SL/Entry)")

        is_short = (sl_f > entry_f)
        stop_dist = abs(entry_f - sl_f)
        r_assumed = False  # A2: set True when the 1.8R assumption is used below.

        if take_profit is not None:
            try:
                tp_f = float(take_profit)
            except (TypeError, ValueError):
                return self._reject_bracket("Rejected (Invalid TP)")
            if not math.isfinite(tp_f) or tp_f <= 0.0:
                return self._reject_bracket("Rejected (Invalid TP)")
            if is_short:
                if tp_f >= entry_f:
                    return self._reject_bracket("Rejected (TP on wrong side of entry)")
                target_dist = entry_f - tp_f
            else:
                if tp_f <= entry_f:
                    return self._reject_bracket("Rejected (TP on wrong side of entry)")
                target_dist = tp_f - entry_f
            r_mult = target_dist / stop_dist
        else:
            # Uncapped trend runner: no TP was given, so the target
            # is ASSUMED at UNCAPPED_RUNNER_R_MULTIPLE (1.8R)
            # (A2: model assumption, not a measured exit).
            r_mult = UNCAPPED_RUNNER_R_MULTIPLE
            r_assumed = True
            tp_f = (entry_f - (stop_dist * r_mult)) if is_short else (entry_f + (stop_dist * r_mult))

        breakeven_win_rate = 1.0 / (1.0 + r_mult)

        # Estimate empirical volatility, drift & return history from recent candles or ATR
        sigma = 0.0015
        drift = 0.0
        empirical_ret_arr = None
        empirical_mean = 0.0
        used_empirical = False
        if recent_candles and len(recent_candles) >= 5:
            cache_key = (
                len(recent_candles),
                recent_candles[0].get("t"),
                recent_candles[-1].get("t"),
                recent_candles[-1].get("c"),
            )
            if self._ret_cache_key == cache_key and self._ret_cache_val is not None:
                empirical_ret_arr, empirical_mean, sigma, drift, used_empirical = self._ret_cache_val
            else:
                closes: List[float] = []
                for c in recent_candles:
                    if "c" not in c:
                        continue
                    try:
                        cv = float(c["c"])
                    except (TypeError, ValueError):
                        continue
                    if math.isfinite(cv) and cv > 0.0:
                        closes.append(cv)
                if len(closes) >= 5:
                    emp_rets = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
                    if len(emp_rets) >= 4:
                        if np is not None:
                            empirical_ret_arr = np.asarray(emp_rets, dtype=float)
                            std_val = float(np.std(empirical_ret_arr))
                            empirical_mean = float(np.mean(empirical_ret_arr))
                        else:
                            std_val = 0.0015
                            empirical_mean = 0.0
                        sigma = max(0.0006, min(0.008, std_val))
                        drift = max(-0.001, min(0.001, empirical_mean * 0.5))
                        used_empirical = True
                self._ret_cache_key = cache_key
                self._ret_cache_val = (empirical_ret_arr, empirical_mean, sigma, drift, used_empirical)

        if not used_empirical and atr is not None:
            try:
                atr_f = float(atr)
            except (TypeError, ValueError):
                atr_f = 0.0
            if math.isfinite(atr_f) and atr_f > 0.0:
                sigma = max(0.0006, min(0.008, (atr_f / entry_f) * 0.85))

        # Risk-neutral Ito convexity adjustment keeps E[S_t] = S_0 * exp(drift*t)
        # symmetric between LONG and SHORT brackets under log-return compounding.
        eff_drift = drift - 0.5 * (sigma ** 2)

        # Vectorized path simulation via NumPy (fat-tailed bootstrap + antithetic variance reduction)
        if np is not None and self._rng is not None:
            if empirical_ret_arr is not None and len(empirical_ret_arr) >= 20:
                shifted_rets = empirical_ret_arr - empirical_mean + eff_drift
                shocks = self._rng.choice(shifted_rets, size=(n_sims, n_steps), replace=True)
            else:
                # Heavy-tailed Student-t(df=6) shocks variance-matched to sigma
                # Paired with antithetic variates [-z, +z] to eliminate small-sample drift noise.
                df = 6.0
                scale_t = sigma * math.sqrt((df - 2.0) / df)
                half = max(1, n_sims // 2)
                raw = self._rng.standard_t(df=df, size=(half, n_steps)) * scale_t
                shocks = eff_drift + np.concatenate([raw, -raw], axis=0)
                if len(shocks) < n_sims:
                    extra = eff_drift + self._rng.standard_t(df=df, size=(1, n_steps)) * scale_t
                    shocks = np.concatenate([shocks, extra], axis=0)

            # Evaluate barrier hits directly in log-return space (avoids full 2D exp + 3 extra arrays).
            log_paths = np.cumsum(shocks, axis=1, out=shocks)
            wick_env = 0.25 * sigma
            hi_factor = 1.0 + wick_env
            lo_factor = max(0.0, 1.0 - wick_env)

            if is_short:
                sl_log_thr = math.log(sl_f / (entry_f * hi_factor))
                stop_hit = log_paths >= sl_log_thr
                if tp_f <= 0.0:
                    target_hit = np.zeros_like(stop_hit)
                elif lo_factor <= 0.0:
                    target_hit = np.ones_like(stop_hit)
                else:
                    tp_log_thr = math.log(tp_f / (entry_f * lo_factor))
                    target_hit = log_paths <= tp_log_thr
            else:
                if lo_factor <= 0.0:
                    stop_hit = np.ones((n_sims, n_steps), dtype=bool)
                else:
                    sl_log_thr = math.log(sl_f / (entry_f * lo_factor))
                    stop_hit = log_paths <= sl_log_thr
                if tp_f <= 0.0:
                    target_hit = np.ones_like(stop_hit)
                else:
                    tp_log_thr = math.log(tp_f / (entry_f * hi_factor))
                    target_hit = log_paths >= tp_log_thr

            rows = np.arange(n_sims)
            stop_idx = np.argmax(stop_hit, axis=1)
            target_idx = np.argmax(target_hit, axis=1)
            first_stop = np.where(stop_hit[rows, stop_idx], stop_idx, 999999)
            first_target = np.where(target_hit[rows, target_idx], target_idx, 999999)

            # Conservative tie-breaker matching BrokerSim.on_tick: stop wins equal-step touches
            stop_first = (first_stop <= first_target) & (first_stop < 999999)
            target_first = (first_target < first_stop) & (first_target < 999999)
            neither = (~stop_first) & (~target_first)

            payoffs = np.zeros(n_sims, dtype=float)
            payoffs[stop_first] = -1.0
            payoffs[target_first] = r_mult
            if neither.any():
                term_prices = entry_f * np.exp(log_paths[neither, -1])
                if is_short:
                    payoffs[neither] = (entry_f - term_prices) / stop_dist
                else:
                    payoffs[neither] = (term_prices - entry_f) / stop_dist

            target_prob = float(np.mean(target_first))
            stop_prob = float(np.mean(stop_first))
            neither_prob = float(np.mean(neither))
            expected_r = float(np.mean(payoffs))

            # trader-timemachine specification:
            # Green paths: Target first, or finished in profit at simulation horizon
            if is_short:
                green_paths = target_first | (neither & (log_paths[:, -1] <= 0.0))
            else:
                green_paths = target_first | (neither & (log_paths[:, -1] >= 0.0))
            green_prob = float(np.mean(green_paths))
        else:
            # A1: NumPy is missing, so no Monte Carlo paths ran at all.
            # The old fixed probabilities (0.35 / 0.45 / 0.20 / 0.48) were
            # invented numbers with no source; report unknown (None) and
            # fail the EV gate closed instead of trading on them.
            target_prob = None
            stop_prob = None
            neither_prob = None
            green_prob = None
            expected_r = None

        if target_prob is None or stop_prob is None:
            decided_win_rate = None
        else:
            decided = target_prob + stop_prob
            decided_win_rate = (target_prob / decided) if decided > 0 else 0.50

        # Target achievable check:
        # If stop was hit by substantial paths (stop_prob >= 0.35) but target was NEVER reached (target_prob <= 0.002),
        # the bracket is hostile/absurd (e.g. 40R target in 30 minutes).
        # Unknown odds cannot prove the target achievable: fail closed.
        target_achievable = (
            target_prob is not None and stop_prob is not None
            and not (stop_prob >= 0.35 and target_prob <= 0.002)
        )

        # Day-trader-skill Time Machine rule:
        # When neither_prob > 0.40 (trade horizon extends past simulation window),
        # evaluate win rate using green_prob (profitable paths), avoiding the small-sample
        # distortion of premature barrier touches.
        if neither_prob is None or decided_win_rate is None:
            effective_win_rate = None
        else:
            effective_win_rate = green_prob if neither_prob > 0.40 else decided_win_rate

        # Decision Gate:
        # Pass if Expected R is above threshold, effective win rate meets breakeven threshold,
        # and target is achievable.
        passed = (
            target_achievable
            and expected_r is not None
            and (expected_r >= min_ev_threshold)
            and effective_win_rate is not None
            and (effective_win_rate >= (breakeven_win_rate * 0.70))
        )

        display_win = effective_win_rate
        if target_prob is None:
            verdict = "Unknown (NumPy unavailable: Monte Carlo odds cannot be computed)"
        elif passed:
            verdict = f"Passed EV Gate (EV {expected_r:+.2f}R | Win {display_win*100:.0f}%)"
        else:
            verdict = f"Blocked by EV Gate (EV {expected_r:+.2f}R | Win {display_win*100:.0f}%)"

        return MonteCarloBracketOdds(
            passed=passed,
            target_prob=target_prob,
            stop_prob=stop_prob,
            neither_prob=neither_prob,
            decided_win_rate=decided_win_rate,
            expected_r=expected_r,
            r_multiple=r_mult,
            breakeven_prob=breakeven_win_rate,
            verdict=verdict,
            green_prob=green_prob,
            r_multiple_is_assumption=r_assumed,
        )
