from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict
import math
from src.arena.portfolio import Portfolio
from src.arena.order import OrderSide


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
    @staticmethod
    def _estimate_periods_per_year(equity_history: List[tuple[float, Decimal]]) -> float:
        # Standardize crypto intraday frequency (15-min bars: 365 * 24 * 4 = 35,040 periods/year)
        # Prevents high-frequency sub-second tick noise from blowing up annualization factor
        if len(equity_history) < 2:
            return 35040.0  # Default 15-min bars in a 365-day 24/7 crypto year
        dt_total = equity_history[-1][0] - equity_history[0][0]
        avg_dt = dt_total / max(1, len(equity_history) - 1)
        if avg_dt < 60.0:
            return 35040.0
        seconds_per_year = 365.25 * 86400.0
        return max(252.0, min(35040.0, seconds_per_year / avg_dt))

    @classmethod
    def calculate_sharpe_and_sortino(
        cls, portfolio: Portfolio, risk_free_rate: float = 0.0
    ) -> tuple[float, float]:
        history = portfolio.equity_history
        if len(history) < 3:
            return 0.0, 0.0

        cache_key = (len(history), history[-1][0], history[-1][1], risk_free_rate)
        cached = getattr(portfolio, "_metrics_cache", None)
        if cached is not None and cached[0] == cache_key:
            return cached[1]

        returns: List[float] = []
        for i in range(1, len(history)):
            prev_eq = float(history[i - 1][1])
            curr_eq = float(history[i][1])
            if prev_eq > 0:
                returns.append((curr_eq - prev_eq) / prev_eq)

        # If portfolio never traded or all returns are 0
        non_zero = [r for r in returns if abs(r) > 1e-9]
        if len(non_zero) < 2:
            return 0.0, 0.0

        n = len(returns)
        mean_ret = sum(returns) / n
        variance = sum((r - mean_ret) ** 2 for r in returns) / (n - 1)
        std_dev = math.sqrt(variance)

        periods_per_year = cls._estimate_periods_per_year(history)
        ann_factor = math.sqrt(periods_per_year)

        sharpe = 0.0
        if std_dev > 1e-8:
            sharpe = ((mean_ret - risk_free_rate) / std_dev) * ann_factor
            sharpe = max(-25.0, min(25.0, round(sharpe, 2)))

        # Sortino uses downside deviation only (returns < 0)
        downside_sq = [r ** 2 for r in returns if r < 0.0]
        if downside_sq:
            downside_dev = math.sqrt(sum(downside_sq) / n)
            if downside_dev > 1e-8:
                sortino = ((mean_ret - risk_free_rate) / downside_dev) * ann_factor
                sortino = max(-25.0, min(25.0, round(sortino, 2)))
            else:
                sortino = sharpe
        else:
            sortino = round(abs(sharpe) * 1.5, 2) if mean_ret > 0 else 0.0

        result = (sharpe, sortino)
        portfolio._metrics_cache = (cache_key, result)  # type: ignore[attr-defined]
        return result

    @staticmethod
    def calculate_win_rate(portfolio: Portfolio) -> Decimal:
        closed_fills = [t for t in portfolio.trade_history if t.is_closing_fill]
        if not closed_fills:
            return Decimal("0.00")
        wins = sum(1 for t in closed_fills if t.realized_pnl > Decimal("0"))
        win_rate = (Decimal(wins) / Decimal(len(closed_fills))) * Decimal("100")
        return win_rate.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def calculate_fitness(
        roi_pct: float,
        max_dd_pct: float,
        sharpe: float,
        sortino: float,
        is_tripped: bool,
        closed_trades: int = 0,
    ) -> float:
        """
        Composite Multi-Objective Fitness Function for Genetic Algorithm:
        Rewards risk-adjusted returns (ROI + Sharpe + Sortino) while penalizing
        quadratic drawdown excursions, overtrading churn, and circuit-breaker violations.
        """
        penalty = -50.0 if is_tripped else 0.0
        dd_linear = max_dd_pct * 1.25
        dd_quad = ((max_dd_pct / 15.0) ** 2) * 2.0
        churn_penalty = max(0.0, (closed_trades - 50) / 100.0) * 1.5
        score = (roi_pct * 2.0) + (sharpe * 1.5) + (sortino * 1.0) - dd_linear - dd_quad - churn_penalty + penalty
        return round(score, 2)

    @classmethod
    def get_rankings(cls, portfolios: Dict[str, Portfolio]) -> List[CompetitorStats]:
        stats_list: List[CompetitorStats] = []

        for p_id, p in portfolios.items():
            sharpe, sortino = cls.calculate_sharpe_and_sortino(p)
            win_rate = cls.calculate_win_rate(p)
            status = "CIRCUIT_TRIPPED" if p.is_circuit_breaker_tripped else "ACTIVE"
            closed_count = sum(1 for t in p.trade_history if t.is_closing_fill)
            fitness = cls.calculate_fitness(
                float(p.roi_pct),
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
                equity=p.total_equity,
                roi_pct=p.roi_pct,
                max_drawdown_pct=p.max_drawdown_pct,
                sharpe_ratio=sharpe,
                sortino_ratio=sortino,
                profit_factor=p.profit_factor,
                win_rate_pct=win_rate,
                total_trades=len(p.trade_history),
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
