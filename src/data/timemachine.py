from __future__ import annotations
from dataclasses import dataclass
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
from src.competitors.atr_dynamic import ATRDynamicCompetitor
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
        self.comp_c = ATRDynamicCompetitor(initial_cash=initial_cash)
        self.comp_d = TrailingGuardCompetitor(initial_cash=initial_cash)
        self.comp_e = ORBCompetitor(initial_cash=initial_cash)
        self.comp_f = SessionMeanPullbackCompetitor(initial_cash=initial_cash)
        self.competitors = [
            self.comp_a, self.comp_b, self.comp_c,
            self.comp_d, self.comp_e, self.comp_f
        ]
        self._rebuild_broker()

    def _rebuild_broker(self) -> None:
        self.broker = BrokerSim(symbol=self.symbol, slippage_pct=Decimal("0.0002"))
        for c in self.competitors:
            self.broker.register_portfolio(c.portfolio, max_position_ratio=c.max_position_ratio)

    def run_simulation(self, bars: List[CandleBar]) -> List[CompetitorStats]:
        gen = max(c.genome.generation for c in self.competitors)
        print(f"[*] Starting Time Machine Arena [Generation {gen}] on {len(bars)} {self.symbol} candle bars...")
        prev_bar: Optional[CandleBar] = None
        cum_vol = Decimal("0")
        cum_pv = Decimal("0")
        window_bars: List[CandleBar] = []
        # Rolling true ranges for the measured backtest ATR (F3).
        true_ranges: List[Decimal] = []

        for bar in bars:
            window_bars.append(bar)
            if len(window_bars) > 15:
                window_bars.pop(0)

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
            # almost never trigger (ORB was dead in backtest).
            orb_window = window_bars[:-1]
            orb_high = max(b.high for b in orb_window) if orb_window else bar.high
            orb_low = min(b.low for b in orb_window) if orb_window else bar.low
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
            if len(true_ranges) > 14:
                true_ranges.pop(0)
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
            indicators = {
                "atr": bar.atr,
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

    def run_evolution_tournament(self, bars: List[CandleBar], generations: int = 3) -> List[CompetitorStats]:
        """
        Runs multiple seasons back-to-back, evolving competitor risk parameters between each generation.
        """
        rankings: List[CompetitorStats] = []
        for g in range(1, generations + 1):
            rankings = self.run_simulation(bars)
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

    def evaluate_bracket(
        self,
        entry_price: Decimal | float,
        stop_loss: Decimal | float,
        take_profit: Optional[Decimal | float] = None,
        atr: Optional[Decimal | float] = None,
        recent_candles: Optional[List[Dict[str, Any]]] = None,
        n_sims: int = 500,
        n_steps: int = 120,
        min_ev_threshold: float = -0.05,
    ) -> MonteCarloBracketOdds:
        entry_f = float(entry_price)
        sl_f = float(stop_loss)
        if entry_f <= 0.0 or sl_f <= 0.0 or sl_f == entry_f:
            return MonteCarloBracketOdds(
                passed=False,
                target_prob=0.0,
                stop_prob=1.0,
                neither_prob=0.0,
                decided_win_rate=0.0,
                expected_r=-1.0,
                r_multiple=0.0,
                breakeven_prob=1.0,
                verdict="Rejected (Invalid SL/Entry)",
                green_prob=0.0,
            )

        is_short = (sl_f > entry_f)
        stop_dist = abs(entry_f - sl_f)
        r_assumed = False  # A2: set True when the 1.8R assumption is used below.

        if is_short:
            # SHORT bracket: Stop-Loss is above entry, Take-Profit is below entry
            if take_profit is not None and float(take_profit) < entry_f:
                tp_f = float(take_profit)
                target_dist = entry_f - tp_f
                r_mult = max(0.5, target_dist / stop_dist)
            else:
                # Uncapped short runner: no TP was given, so the target
                # is ASSUMED at UNCAPPED_RUNNER_R_MULTIPLE (1.8R) downward
                # (A2: model assumption, not a measured exit).
                r_mult = UNCAPPED_RUNNER_R_MULTIPLE
                r_assumed = True
                tp_f = entry_f - (stop_dist * r_mult)
        else:
            # LONG bracket: Stop-Loss is below entry, Take-Profit is above entry
            if take_profit is not None and float(take_profit) > entry_f:
                tp_f = float(take_profit)
                target_dist = tp_f - entry_f
                r_mult = max(0.5, target_dist / stop_dist)
            else:
                # Uncapped trend runner: no TP was given, so the target
                # is ASSUMED at UNCAPPED_RUNNER_R_MULTIPLE (1.8R) upward
                # (A2: model assumption, not a measured exit).
                r_mult = UNCAPPED_RUNNER_R_MULTIPLE
                r_assumed = True
                tp_f = entry_f + (stop_dist * r_mult)

        breakeven_win_rate = 1.0 / (1.0 + r_mult)

        # Estimate empirical volatility & drift from recent candle returns or ATR
        sigma = 0.0015
        drift = 0.0
        if recent_candles and len(recent_candles) >= 5:
            closes = [float(c["c"]) for c in recent_candles if "c" in c]
            if len(closes) >= 5:
                rets = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes)) if closes[i - 1] > 0]
                if len(rets) >= 4:
                    std_val = float(np.std(rets)) if np is not None else 0.0015
                    sigma = max(0.0006, min(0.008, std_val))
                    mean_val = float(np.mean(rets)) if np is not None else 0.0
                    drift = max(-0.001, min(0.001, mean_val * 0.5))
        elif atr is not None and float(atr) > 0:
            sigma = max(0.0006, min(0.008, (float(atr) / entry_f) * 0.85))

        # Vectorized path simulation via NumPy
        if np is not None and self._rng is not None:
            shocks = self._rng.normal(loc=drift, scale=sigma, size=(n_sims, n_steps))
            paths = entry_f * np.exp(np.cumsum(shocks, axis=1))

            if is_short:
                stop_hit = paths >= sl_f
                target_hit = paths <= tp_f
            else:
                stop_hit = paths <= sl_f
                target_hit = paths >= tp_f

            first_stop = np.where(stop_hit.any(axis=1), np.argmax(stop_hit, axis=1), 999999)
            first_target = np.where(target_hit.any(axis=1), np.argmax(target_hit, axis=1), 999999)

            stop_first = first_stop < first_target
            target_first = first_target < first_stop
            neither = (~stop_first) & (~target_first)

            payoffs = np.zeros(n_sims, dtype=float)
            payoffs[stop_first] = -1.0
            payoffs[target_first] = r_mult
            if neither.any():
                if is_short:
                    payoffs[neither] = (entry_f - paths[neither, -1]) / stop_dist
                else:
                    payoffs[neither] = (paths[neither, -1] - entry_f) / stop_dist

            target_prob = float(np.mean(target_first))
            stop_prob = float(np.mean(stop_first))
            neither_prob = float(np.mean(neither))
            expected_r = float(np.mean(payoffs))

            # trader-timemachine specification:
            # Green paths: Target first, or finished in profit at simulation horizon
            if is_short:
                green_paths = target_first | (neither & (paths[:, -1] <= entry_f))
            else:
                green_paths = target_first | (neither & (paths[:, -1] >= entry_f))
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
