from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Optional
import math
import time
try:
    import numpy as _np
except Exception:  # pragma: no cover
    _np = None  # type: ignore[assignment]
from src.arena.portfolio import Portfolio, _SliceableDeque
from src.arena.order import OrderSide

# A3: annualization convention -- 35040 periods/year = 365 days x 96
# 15-minute bars per day (24h crypto market). This is a fixed modelling
# convention, NOT a measured sampling frequency: live equity_history is
# sampled every ~5s, but sub-60s histories are still annualized at this
# 15-minute-bar rate so high-frequency tick noise cannot inflate the
# annualization factor. The number itself is unchanged (decision: P2-A).
PERIODS_PER_YEAR_15MIN_BARS = 35040.0


@dataclass
class CompetitorStats:
    rank: int
    portfolio_id: str
    name: str
    equity: Decimal
    roi_pct: Decimal
    max_drawdown_pct: Decimal
    sharpe_ratio: float
    sortino_ratio: float
    profit_factor: float
    win_rate_pct: Decimal
    total_trades: int
    closed_trades: int
    current_qty: Decimal
    cash: Decimal
    fitness_score: float
    status: str


class Leaderboard:
    """
    Real-time Multi-Portfolio Ranking Engine.
    Evaluates competitors using risk-adjusted metrics (Sharpe, Sortino, Profit Factor, Drawdown)
    and computes a unified Evolutionary Fitness Score for genetic selection.
    """
    # Audit 2.8: the fill-driven cache key (below) is right for
    # performance, but without a TTL the served metrics freeze at the
    # last fill while the equity history keeps moving. A read older
    # than the TTL recomputes, so the lag is bounded at 60s.
    METRICS_CACHE_TTL_SEC = 60.0
    @staticmethod
    def _estimate_periods_per_year(equity_history: List[tuple[float, Decimal]]) -> float:
        # Annualize at the 15-minute-bar convention (see the named
        # constant PERIODS_PER_YEAR_15MIN_BARS above): sub-60s histories
        # would otherwise annualize at their tick frequency and blow
        # up the Sharpe/Sortino factor. Use the median of sampled
        # consecutive timestamp deltas so offline/pause gaps do not
        # stretch avg_dt and halve Sharpe/Sortino after a restart.
        n_pts = len(equity_history)
        if n_pts < 2:
            return PERIODS_PER_YEAR_15MIN_BARS
        max_samples = 64
        step = max(1, (n_pts - 1) // max_samples)
        deltas: List[float] = []
        if isinstance(equity_history, _SliceableDeque):
            # Single sequential pass avoids O(N) deque random indexing per sample.
            it = iter(equity_history)
            prev_t = next(it)[0]
            next_sample = 0
            for idx, (curr_t, _) in enumerate(it):
                if idx == next_sample:
                    dt = curr_t - prev_t
                    if math.isfinite(dt) and dt > 0.0:
                        deltas.append(dt)
                    next_sample += step
                prev_t = curr_t
        else:
            for idx in range(0, n_pts - 1, step):
                dt = equity_history[idx + 1][0] - equity_history[idx][0]
                if math.isfinite(dt) and dt > 0.0:
                    deltas.append(dt)
        if not deltas:
            return PERIODS_PER_YEAR_15MIN_BARS
        deltas.sort()
        median_dt = deltas[len(deltas) // 2]
        if median_dt < 60.0:
            return PERIODS_PER_YEAR_15MIN_BARS
        seconds_per_year = 365.25 * 86400.0
        return max(252.0, min(PERIODS_PER_YEAR_15MIN_BARS, seconds_per_year / median_dt))

    @classmethod
    def calculate_sharpe_and_sortino(
        cls, portfolio: Portfolio, risk_free_rate: float = 0.0
    ) -> tuple[float, Optional[float]]:
        history = portfolio.equity_history
        if len(history) < 3:
            return 0.0, 0.0

        cache_key = (
            portfolio.total_fills,
            portfolio.closed_trades_count,
            getattr(portfolio, "_equity_history_version", 0),
            risk_free_rate,
        )
        cached = getattr(portfolio, "_metrics_cache", None)
        if cached is not None and cached[0] == cache_key:
            cached_time = getattr(portfolio, "_metrics_cache_time", 0.0)
            if time.monotonic() - cached_time < cls.METRICS_CACHE_TTL_SEC:
                return cached[1]
            # TTL expired: fall through and recompute below.

        eq_floats = getattr(portfolio, "_equity_floats", None)
        floats_in_sync = (
            isinstance(history, _SliceableDeque)
            and eq_floats is not None
            and len(eq_floats) == len(history)
            and getattr(portfolio, "_equity_floats_sync_gen", -1) == getattr(history, "_mut_gen", -2)
        )
        if _np is not None and floats_in_sync:
            arr = _np.fromiter(eq_floats, dtype=_np.float64, count=len(eq_floats))
            finite_mask = _np.isfinite(arr)
            if not _np.all(finite_mask):
                arr = arr[finite_mask]
            if arr.size < 3:
                return 0.0, 0.0
            prev = arr[:-1]
            valid = prev > 0.0
            rets = (arr[1:][valid] - prev[valid]) / prev[valid]
            n = int(rets.size)
            non_zero_count = int(_np.count_nonzero(_np.abs(rets) > 1e-9)) if n else 0
            if non_zero_count < 2 or n < 2:
                result = (0.0, 0.0)
                if portfolio.position_qty <= Decimal("0"):
                    portfolio._metrics_cache = (cache_key, result)  # type: ignore[attr-defined]
                    portfolio._metrics_cache_time = time.monotonic()  # type: ignore[attr-defined]
                return result
            mean_ret = float(rets.mean())
            std_dev = float(rets.std(ddof=1))
            down_mask = rets < risk_free_rate
            downside_count = int(_np.count_nonzero(down_mask))
            downside_sq_sum = float(_np.sum((rets[down_mask] - risk_free_rate) ** 2)) if downside_count > 0 else 0.0
        else:
            # Single-pass Welford online mean/variance + Sortino downside accumulation
            it = iter(history)
            prev_eq = float("nan")
            for _, eq_dec in it:
                val = float(eq_dec)
                if math.isfinite(val):
                    prev_eq = val
                    break
            if not math.isfinite(prev_eq):
                return 0.0, 0.0
            n = 0
            non_zero_count = 0
            mean_ret = 0.0
            m2 = 0.0
            downside_sq_sum = 0.0
            downside_count = 0

            for _, eq_dec in it:
                curr_eq = float(eq_dec)
                if not math.isfinite(curr_eq):
                    continue
                if prev_eq > 0.0:
                    r = (curr_eq - prev_eq) / prev_eq
                    n += 1
                    if abs(r) > 1e-9:
                        non_zero_count += 1
                    delta = r - mean_ret
                    mean_ret += delta / n
                    m2 += delta * (r - mean_ret)
                    if r < risk_free_rate:
                        diff = r - risk_free_rate
                        downside_sq_sum += diff * diff
                        downside_count += 1
                prev_eq = curr_eq

            if non_zero_count < 2 or n < 2:
                result = (0.0, 0.0)
                if portfolio.position_qty <= Decimal("0"):
                    portfolio._metrics_cache = (cache_key, result)  # type: ignore[attr-defined]
                    portfolio._metrics_cache_time = time.monotonic()  # type: ignore[attr-defined]
                return result

            variance = m2 / (n - 1)
            std_dev = math.sqrt(variance) if (math.isfinite(variance) and variance > 0.0) else 0.0

        periods_per_year = cls._estimate_periods_per_year(history)
        ann_factor = math.sqrt(periods_per_year)

        sharpe = 0.0
        if math.isfinite(std_dev) and std_dev > 1e-8 and math.isfinite(mean_ret):
            raw_sharpe = ((mean_ret - risk_free_rate) / std_dev) * ann_factor
            if math.isfinite(raw_sharpe):
                sharpe = max(-25.0, min(25.0, round(raw_sharpe, 2)))

        # Sortino uses downside deviation only (returns < risk_free_rate)
        if downside_count > 0:
            downside_dev = math.sqrt(downside_sq_sum / n) if (math.isfinite(downside_sq_sum) and downside_sq_sum >= 0.0) else 0.0
            if math.isfinite(downside_dev) and downside_dev > 1e-8 and math.isfinite(mean_ret):
                raw_sortino = ((mean_ret - risk_free_rate) / downside_dev) * ann_factor
                sortino = max(-25.0, min(25.0, round(raw_sortino, 2))) if math.isfinite(raw_sortino) else sharpe
            else:
                sortino = sharpe
        else:
            # P0-B / F1: no downside returns means the downside deviation
            # is undefined, not abs(sharpe) * 1.5 -- that 1.5 multiplier
            # had no source and invented a Sortino for never-losing
            # histories. Callers treat None as "undefined" (fitness
            # counts it as 0; the rankings table shows 0.0).
            sortino = None

        result = (sharpe, sortino)
        portfolio._metrics_cache = (cache_key, result)  # type: ignore[attr-defined]
        portfolio._metrics_cache_time = time.monotonic()  # type: ignore[attr-defined]
        return result

    @staticmethod
    def calculate_win_rate(portfolio: Portfolio) -> Decimal:
        # Audit 3.7: derive from the lifetime counters, not trade_history.
        # The snapshot keeps only the last 50 fills but the full counters,
        # so counting the history understated the win rate after a restore
        # (and the churn penalty in calculate_fitness, which takes the
        # closed-trades count from get_rankings). Breakeven closes
        # (realized_pnl == 0) increment neither counter, so they are
        # excluded from the denominator: wins / decided trades.
        total = portfolio.win_count + portfolio.loss_count
        if total == 0:
            return Decimal("0.00")
        win_rate = (Decimal(portfolio.win_count) / Decimal(total)) * Decimal("100")
        return win_rate.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def calculate_fitness(
        roi_pct: float,
        max_dd_pct: float,
        sharpe: float,
        sortino: Optional[float],
        is_tripped: bool,
        closed_trades: int = 0,
    ) -> float:
        """
        Composite Multi-Objective Fitness Function for Genetic Algorithm:
        Rewards risk-adjusted returns (ROI + Sharpe + Sortino) while penalizing
        quadratic drawdown excursions, overtrading churn, and circuit-breaker violations.
        """
        # An undefined Sortino (no downside returns, F1) contributes 0 to
        # fitness instead of an invented abs(sharpe) * 1.5.
        sortino_value = 0.0 if sortino is None else sortino
        penalty = -50.0 if is_tripped else 0.0
        dd_linear = max_dd_pct * 1.25
        dd_quad = ((max_dd_pct / 15.0) ** 2) * 2.0
        churn_penalty = max(0.0, (closed_trades - 50) / 100.0) * 1.5
        score = (roi_pct * 2.0) + (sharpe * 1.5) + (sortino_value * 1.0) - dd_linear - dd_quad - churn_penalty + penalty
        return round(score, 2)

    @classmethod
    def get_rankings(cls, portfolios: Dict[str, Portfolio]) -> List[CompetitorStats]:
        stats_list: List[CompetitorStats] = []

        for p_id, p in portfolios.items():
            sharpe, sortino = cls.calculate_sharpe_and_sortino(p)
            win_rate = cls.calculate_win_rate(p)
            status = "CIRCUIT_TRIPPED" if p.is_circuit_breaker_tripped else "ACTIVE"
            # Audit 3.7: lifetime closed trades from the counters, not
            # the truncated history (see calculate_win_rate).
            closed_count = p.closed_trades_count
            eq = p.total_equity
            roi = (
                (((eq - p.initial_cash) / p.initial_cash) * Decimal("100")).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                if p.initial_cash > Decimal("0")
                else Decimal("0.00")
            )
            fitness = cls.calculate_fitness(
                float(roi),
                float(p.max_drawdown_pct),
                sharpe,
                sortino,
                p.is_circuit_breaker_tripped,
                closed_trades=closed_count,
            )

            stats = CompetitorStats(
                rank=0,
                portfolio_id=p_id,
                name=p.name,
                equity=eq,
                roi_pct=roi,
                max_drawdown_pct=p.max_drawdown_pct,
                sharpe_ratio=sharpe,
                # Display fallback for an undefined Sortino (F1); the
                # fitness above already received the None.
                sortino_ratio=sortino if sortino is not None else 0.0,
                profit_factor=p.profit_factor,
                win_rate_pct=win_rate,
                total_trades=p.total_fills,
                closed_trades=closed_count,
                current_qty=p.position_qty,
                cash=p.cash,
                fitness_score=fitness,
                status=status
            )
            stats_list.append(stats)

        # Sort strictly by Total Equity (Descending) -> Active Status -> Fitness Score -> ROI %
        stats_list.sort(
            key=lambda s: (
                s.equity,
                s.status == "ACTIVE",
                s.fitness_score,
                float(s.roi_pct),
                -float(s.max_drawdown_pct)
            ),
            reverse=True
        )

        for idx, s in enumerate(stats_list, start=1):
            s.rank = idx

        return stats_list
