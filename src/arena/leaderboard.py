from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Optional
import math
import time
from src.arena.portfolio import Portfolio
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
        # up the Sharpe/Sortino factor.
        if len(equity_history) < 2:
            return PERIODS_PER_YEAR_15MIN_BARS  # Default: 15-min bars in a 365-day 24/7 crypto year
        dt_total = equity_history[-1][0] - equity_history[0][0]
        avg_dt = dt_total / max(1, len(equity_history) - 1)
        if avg_dt < 60.0:
            return PERIODS_PER_YEAR_15MIN_BARS
        seconds_per_year = 365.25 * 86400.0
        return max(252.0, min(PERIODS_PER_YEAR_15MIN_BARS, seconds_per_year / avg_dt))

    @classmethod
    def calculate_sharpe_and_sortino(
        cls, portfolio: Portfolio, risk_free_rate: float = 0.0
    ) -> tuple[float, Optional[float]]:
        history = portfolio.equity_history
        if len(history) < 3:
            return 0.0, 0.0

        # Audit §5.5: the old key included the latest equity value, which
        # moves on every tick, so the cache never hit and 6 x up-to-2000
        # point loops ran every second. The key is now fill-driven: only
        # a fill (entry or close) changes the return series in a way the
        # leaderboard must reflect immediately; ticks between fills only
        # append mark-to-market points. The trade-off is deliberate:
        # between fills the served metrics are the as-of-last-fill values
        # (they can lag a fast-moving short history; over a long history
        # one tick among up to 2000 points moves the 2dp-rounded values
        # negligibly). The history version covers reset/restore, which
        # reuse the same counters for a different history.
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

        # Single-pass Welford online mean/variance + Sortino downside accumulation
        # (avoids allocating returns/non_zero/downside_sq lists and halves Decimal->float casts).
        it = iter(history)
        prev_eq = float(next(it)[1])
        n = 0
        non_zero_count = 0
        mean_ret = 0.0
        m2 = 0.0
        downside_sq_sum = 0.0
        downside_count = 0

        for _, eq_dec in it:
            curr_eq = float(eq_dec)
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

        # If portfolio never traded or all returns are 0
        if non_zero_count < 2 or n < 2:
            result = (0.0, 0.0)
            portfolio._metrics_cache = (cache_key, result)  # type: ignore[attr-defined]
            portfolio._metrics_cache_time = time.monotonic()  # type: ignore[attr-defined]
            return result

        variance = m2 / (n - 1)
        std_dev = math.sqrt(variance) if variance > 0.0 else 0.0

        periods_per_year = cls._estimate_periods_per_year(history)
        ann_factor = math.sqrt(periods_per_year)

        sharpe = 0.0
        if std_dev > 1e-8:
            sharpe = ((mean_ret - risk_free_rate) / std_dev) * ann_factor
            sharpe = max(-25.0, min(25.0, round(sharpe, 2)))

        # Sortino uses downside deviation only (returns < risk_free_rate)
        if downside_count > 0:
            downside_dev = math.sqrt(downside_sq_sum / n)
            if downside_dev > 1e-8:
                sortino = ((mean_ret - risk_free_rate) / downside_dev) * ann_factor
                sortino = max(-25.0, min(25.0, round(sortino, 2)))
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
