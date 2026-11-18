from __future__ import annotations
from dataclasses import asdict, replace
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Any, Optional, Tuple, TYPE_CHECKING
import json
import logging
import os
import random
import sys
import time

from src.arena.leaderboard import CompetitorStats, Leaderboard
from src.competitors.base import CompetitorGenome

if TYPE_CHECKING:
    from src.competitors.base import BaseCompetitor

logger = logging.getLogger(__name__)


class GeneticEvolver:
    """
    Evolutionary Engine (Genetic Parameter Tournament).
    Implements Elitism (Top 2 survive) + Crossover & Bounded Gaussian Mutation (Bottom 2 evolve)
    and persists generational lineage into ECC structured memory (memory/arena_history.json).
    """
    # Fixed salt for deterministic evolution seeds. The seed for a generation
    # is SEED_SALT + generation * 97, so the same generation with the same
    # parents always mutates the same way and an evolution run is replayable.
    SEED_SALT: int = 20261113

    # Audit 3.11: the last evolution's records, shared with evolve_now so
    # the history can be saved outside the engine lock. Set only at the
    # end of evolve_generation; the None default keeps the read path safe
    # before any evolution has run (an early return with < 2 rankings
    # used to leave the attribute unset and raise AttributeError).
    _last_records: Optional[Tuple[int, List[Dict[str, Any]]]] = None

    @classmethod
    def _generation_seed(cls, next_gen: int, seed_entropy: int = 0) -> int:
        """Per-generation evolution seed (fixed salt + generation + optional market entropy)."""
        return cls.SEED_SALT + int(next_gen) * 97 + int(seed_entropy)

    @staticmethod
    def _clamp_decimal(val: Decimal, low: str, high: str, quant: str = "0.001") -> Decimal:
        clamped = max(Decimal(low), min(Decimal(high), val))
        return clamped.quantize(Decimal(quant), rounding=ROUND_HALF_UP)

    @classmethod
    def calculate_composite_fitness(cls, ranking: CompetitorStats) -> Decimal:
        """
        Single canonical fitness: delegates to Leaderboard.calculate_fitness,
        the same formula the leaderboard displays as fitness_score, so the
        evolution record's composite_fitness now agrees with prev_fitness.
        Fitness = 2.0*ROI + 1.5*Sharpe + 1.0*Sortino - 1.25*MaxDD
                  - 2.0*(MaxDD/15)^2 - 1.5*churn - 50 if circuit-tripped.
        The old evolution-only formula (normalized ROI/Sharpe, no Sortino,
        no trip penalty) is retired: it let a tripped competitor record a
        good composite fitness. Audit 3.9: parent selection now ranks by
        this fitness (see parent_order), not by total equity.
        """
        score = Leaderboard.calculate_fitness(
            float(ranking.roi_pct),
            float(ranking.max_drawdown_pct),
            ranking.sharpe_ratio,
            ranking.sortino_ratio,
            ranking.status == "CIRCUIT_TRIPPED",
            closed_trades=int(ranking.closed_trades),
        )
        return Decimal(str(score))

    @classmethod
    def crossover_and_mutate(
        cls,
        parent1: CompetitorGenome,
        parent2: CompetitorGenome,
        next_gen: int,
        seed_offset: int = 0,
        seed_entropy: int = 0,
    ) -> CompetitorGenome:
        rng = random.Random(cls._generation_seed(next_gen, seed_entropy) + seed_offset)

        def blend(d1: Decimal, d2: Decimal, jitter_pct: float = 0.12) -> Decimal:
            weight = Decimal(str(round(rng.uniform(0.35, 0.65), 2)))
            base = (d1 * weight) + (d2 * (Decimal("1") - weight))
            factor = Decimal(str(round(1.0 + rng.uniform(-jitter_pct, jitter_pct), 3)))
            return base * factor

        new_pos = cls._clamp_decimal(blend(parent1.position_ratio, parent2.position_ratio, 0.10), "0.20", "0.75", "0.01")
        new_sl = cls._clamp_decimal(blend(parent1.stop_loss_pct, parent2.stop_loss_pct, 0.15), "0.006", "0.035", "0.001")

        tp1 = parent1.take_profit_pct if parent1.take_profit_pct is not None else Decimal("0.028")
        tp2 = parent2.take_profit_pct if parent2.take_profit_pct is not None else Decimal("0.028")
        new_tp: Decimal | None = cls._clamp_decimal(blend(tp1, tp2, 0.15), "0.015", "0.065", "0.001")
        # Ensure Risk:Reward >= 1.5
        if new_tp is not None and new_tp < (new_sl * Decimal("1.5")):
            new_tp = (new_sl * Decimal("1.8")).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)

        new_atr_risk = cls._clamp_decimal(blend(parent1.atr_risk_pct, parent2.atr_risk_pct, 0.12), "0.008", "0.025", "0.001")
        new_atr_sl = cls._clamp_decimal(blend(parent1.atr_stop_mult, parent2.atr_stop_mult, 0.12), "1.0", "2.5", "0.1")
        new_atr_tp = cls._clamp_decimal(blend(parent1.atr_target_mult, parent2.atr_target_mult, 0.15), "2.0", "4.5", "0.1")
        # Ensure ATR Risk:Reward >= 1.5 (mirrors the TP rule above)
        if new_atr_tp < (new_atr_sl * Decimal("1.5")):
            new_atr_tp = cls._clamp_decimal(new_atr_sl * Decimal("1.8"), "2.0", "4.5", "0.1")
        new_trail_trig = cls._clamp_decimal(
            blend(parent1.trailing_trigger_pct, parent2.trailing_trigger_pct, 0.12), "1.2", "3.5", "0.1"
        )
        new_trail_dist = cls._clamp_decimal(
            blend(parent1.trailing_distance_pct, parent2.trailing_distance_pct, 0.15), "0.004", "0.012", "0.001"
        )
        new_risk_pct = cls._clamp_decimal(
            blend(parent1.risk_per_trade_pct, parent2.risk_per_trade_pct, 0.12), "0.008", "0.030", "0.001"
        )

        # Strategy-Specific Leverage Evolution
        if parent1.leverage_enabled or parent2.leverage_enabled:
            new_lev_enabled = rng.random() > 0.15
            lev1 = parent1.leverage if parent1.leverage_enabled else Decimal("1.5")
            lev2 = parent2.leverage if parent2.leverage_enabled else Decimal("1.5")
            new_lev = cls._clamp_decimal(blend(lev1, lev2, 0.15), "1.0", "5.0", "0.1")
        else:
            new_lev_enabled = rng.random() < 0.15
            new_lev = cls._clamp_decimal(blend(parent1.leverage, parent2.leverage, 0.10), "1.0", "3.0", "0.1")

        return CompetitorGenome(
            position_ratio=new_pos,
            risk_per_trade_pct=new_risk_pct,
            stop_loss_pct=new_sl,
            take_profit_pct=new_tp,
            atr_risk_pct=new_atr_risk,
            atr_stop_mult=new_atr_sl,
            atr_target_mult=new_atr_tp,
            trailing_trigger_pct=new_trail_trig,
            trailing_distance_pct=new_trail_dist,
            cooldown_bars=max(parent1.cooldown_bars, parent2.cooldown_bars),
            generation=next_gen,
            leverage_enabled=new_lev_enabled,
            leverage=new_lev,
            # News sensitivity is inherited unchanged (item 12C phase 1):
            # crossover blends genes, but this one is a fixed per-strategy
            # slot value, never a blended or mutated gene.
            news_sensitivity=parent1.news_sensitivity
        )

    # Genes eligible for runner-up fine-tuning: (field, low, high, quantum).
    # Bounds mirror the CompetitorGenome.__post_init__ validation ranges.
    _FINE_TUNE_GENES = [
        ("position_ratio", "0.20", "0.75", "0.01"),
        ("risk_per_trade_pct", "0.008", "0.030", "0.001"),
        ("stop_loss_pct", "0.006", "0.035", "0.001"),
        ("take_profit_pct", "0.015", "0.065", "0.001"),
        ("atr_risk_pct", "0.008", "0.025", "0.001"),
        ("atr_stop_mult", "1.0", "2.5", "0.1"),
        ("atr_target_mult", "2.0", "4.5", "0.1"),
        ("trailing_trigger_pct", "1.2", "3.5", "0.1"),
        ("trailing_distance_pct", "0.004", "0.012", "0.001"),
    ]

    @classmethod
    def _fine_tune_runner_up(
        cls,
        genome: CompetitorGenome,
        next_gen: int,
        seed: int
    ) -> tuple[CompetitorGenome, List[str]]:
        """Nudge 1-2 genes of the runner-up genome by +/-5% (real fine-tuning).

        Returns the new genome and the list of genes that actually changed.
        A gene whose 5% step quantizes away is nudged by one quantum step in
        the same direction instead, so a chosen gene always visibly moves.
        Ratio rules (TP >= 1.5x SL, ATR target >= 1.5x stop) are repaired the
        same way crossover does, so the result always passes validation.
        """
        rng = random.Random(seed)
        movable = [
            (name, low, high, quant)
            for (name, low, high, quant) in cls._FINE_TUNE_GENES
            if getattr(genome, name) is not None
        ]
        count = rng.choice([1, 2])
        chosen = rng.sample(movable, k=min(count, len(movable)))
        values: Dict[str, Any] = {
            name: getattr(genome, name) for (name, _, _, _) in cls._FINE_TUNE_GENES
        }
        tuned: List[str] = []
        for name, low, high, quant in chosen:
            old: Decimal = values[name]
            first = rng.choice([-1, 1])
            for direction in (first, -first):
                factor = Decimal("1.05") if direction > 0 else Decimal("0.95")
                new = cls._clamp_decimal(old * factor, low, high, quant)
                if new == old:
                    new = cls._clamp_decimal(old + Decimal(quant) * direction, low, high, quant)
                if new != old:
                    values[name] = new
                    tuned.append(name)
                    break
        tp = values["take_profit_pct"]
        if tp is not None and tp < values["stop_loss_pct"] * Decimal("1.5"):
            values["take_profit_pct"] = cls._clamp_decimal(
                values["stop_loss_pct"] * Decimal("1.8"), "0.015", "0.065", "0.001"
            )
            if "take_profit_pct" not in tuned:
                tuned.append("take_profit_pct")
        if values["atr_target_mult"] < values["atr_stop_mult"] * Decimal("1.5"):
            values["atr_target_mult"] = cls._clamp_decimal(
                values["atr_stop_mult"] * Decimal("1.8"), "2.0", "4.5", "0.1"
            )
            if "atr_target_mult" not in tuned:
                tuned.append("atr_target_mult")
        new_g = CompetitorGenome(
            position_ratio=values["position_ratio"],
            risk_per_trade_pct=values["risk_per_trade_pct"],
            stop_loss_pct=values["stop_loss_pct"],
            take_profit_pct=values["take_profit_pct"],
            atr_risk_pct=values["atr_risk_pct"],
            atr_stop_mult=values["atr_stop_mult"],
            atr_target_mult=values["atr_target_mult"],
            trailing_trigger_pct=values["trailing_trigger_pct"],
            trailing_distance_pct=values["trailing_distance_pct"],
            cooldown_bars=genome.cooldown_bars,
            generation=next_gen,
            leverage_enabled=genome.leverage_enabled,
            leverage=genome.leverage,
            # Not in _FINE_TUNE_GENES: the runner-up keeps its sensitivity.
            news_sensitivity=genome.news_sensitivity
        )
        return new_g, tuned

    @classmethod
    def parent_order(cls, rankings: List[CompetitorStats]) -> List[CompetitorStats]:
        """Parent-selection order for evolution (audit 3.9, fitness-first).

        Returns a NEW list sorted by composite fitness (descending), ties
        broken by total equity, then ROI, then smallest drawdown. Fitness
        already rewards ROI/Sharpe/Sortino and penalises drawdown (linear
        + quadratic) and circuit trips (-50), so a high-equity strategy
        that earned its lead with a huge drawdown or a tripped breaker no
        longer breeds as champion. The leaderboard display order is
        unchanged (still equity-first, as the user specified); this
        ordering is used ONLY to pick evolution parents.
        """
        return sorted(
            rankings,
            key=lambda r: (
                r.fitness_score,
                r.equity,
                float(r.roi_pct),
                -float(r.max_drawdown_pct),
            ),
            reverse=True,
        )

    UNCAPPED_RUNNER_IDS = ("comp_agg", "comp_trail")

    @classmethod
    def evolve_generation(
        cls,
        competitors: List[BaseCompetitor],
        rankings: List[CompetitorStats],
        preserve_portfolio: bool = True,
        save_history: bool = True,
        seed_entropy: int = 0,
    ) -> List[str]:
        """
        Evolves the competitor pool in-place for the next generation based on Arena rankings.
        Parents (champion + runner-up) are picked by composite fitness via
        parent_order; the incoming rankings keep their display (equity) order.
        Returns human-readable evolution log entries.
        """
        logs, _ = cls.evolve_generation_with_records(
            competitors,
            rankings,
            preserve_portfolio=preserve_portfolio,
            save_history=save_history,
            seed_entropy=seed_entropy,
        )
        return logs

    @classmethod
    def evolve_generation_with_records(
        cls,
        competitors: List[BaseCompetitor],
        rankings: List[CompetitorStats],
        preserve_portfolio: bool = True,
        save_history: bool = True,
        seed_entropy: int = 0,
    ) -> Tuple[List[str], Optional[Tuple[int, List[Dict[str, Any]]]]]:
        """Evolves the competitor pool and returns ``(logs, (next_gen, records))``
        directly so callers never have to rely solely on class state ``_last_records``.
        """
        comp_map: Dict[str, BaseCompetitor] = {c.portfolio_id: c for c in competitors}
        if len(rankings) < 2:
            return [], None

        # Audit 3.9: parents are picked by fitness, not by the equity
        # order of the display rankings. parent_order returns a new list;
        # the caller's rankings (and the leaderboard display) are untouched.
        parent_order = cls.parent_order(rankings)
        champion_stats = parent_order[0]
        runner_up_stats = parent_order[1]
        champ_comp = comp_map[champion_stats.portfolio_id]
        runner_comp = comp_map[runner_up_stats.portfolio_id]

        current_gen = max(c.genome.generation for c in competitors)
        next_gen = current_gen + 1
        gen_seed = cls._generation_seed(next_gen, seed_entropy=seed_entropy)

        logs: List[str] = []
        evolution_records: List[Dict[str, Any]] = []

        for idx, r in enumerate(parent_order):
            comp = comp_map[r.portfolio_id]
            old_g = comp.genome
            tuned_genes: List[str] = []

            if idx == 0:
                # Elite #1: Champion genome preserved with generation bump
                new_g = replace(old_g, generation=next_gen)
                action = "ELITE_CHAMPION_PRESERVED"
                logs.append(
                    f"[G{next_gen} ELITE #1] {comp.portfolio_id} retained winning genome "
                    f"(Fitness={r.fitness_score:+.2f}, ROI={r.roi_pct:+.2f}%)"
                )
            elif idx == 1:
                # Elite #2: Runner-up genome kept, with real adaptive fine-tuning:
                # 1-2 genes nudged by +/-5%. Ratio rules are repaired like crossover does.
                new_g, tuned_genes = cls._fine_tune_runner_up(old_g, next_gen, gen_seed + 1000003)
                action = "ELITE_RUNNER_UP_PRESERVED"
                logs.append(
                    f"[G{next_gen} ELITE #2] {comp.portfolio_id} fine-tuned runner-up genome "
                    f"({', '.join(tuned_genes) if tuned_genes else 'no gene moved'}; "
                    f"Fitness={r.fitness_score:+.2f}, ROI={r.roi_pct:+.2f}%)"
                )
            else:
                # Bottom performers: Crossover from Champion + Runner-up with Mutation
                new_g = cls.crossover_and_mutate(
                    champ_comp.genome,
                    runner_comp.genome,
                    next_gen=next_gen,
                    seed_offset=idx * 31,
                    seed_entropy=seed_entropy,
                )
                # Preserve uncapped runner specialization for Aggressive & Trailing Guard
                if comp.portfolio_id in cls.UNCAPPED_RUNNER_IDS:
                    pos_ratio = (
                        cls._clamp_decimal(new_g.position_ratio * Decimal("1.15"), "0.45", "0.75", "0.01")
                        if comp.portfolio_id == "comp_agg"
                        else new_g.position_ratio
                    )
                    new_g = replace(new_g, position_ratio=pos_ratio, take_profit_pct=None)
                action = "CROSSOVER_MUTATED"
                logs.append(
                    f"[G{next_gen} MUTATED] {comp.portfolio_id} evolved from #{champion_stats.rank}x#{runner_up_stats.rank}: "
                    f"Size={float(old_g.position_ratio)*100:.0f}%->{float(new_g.position_ratio)*100:.0f}%, "
                    f"SL={float(old_g.stop_loss_pct)*100:.1f}%->{float(new_g.stop_loss_pct)*100:.1f}%"
                )

            comp.reset_for_new_generation(new_g, preserve_portfolio=preserve_portfolio)
            comp_fitness = float(cls.calculate_composite_fitness(r))
            evolution_records.append({
                "portfolio_id": comp.portfolio_id,
                "prev_rank": r.rank,
                "prev_roi_pct": float(r.roi_pct),
                "prev_max_dd_pct": float(r.max_drawdown_pct),
                "prev_sharpe": r.sharpe_ratio,
                "prev_fitness": r.fitness_score,
                "composite_fitness": comp_fitness,
                "evolution_seed": gen_seed,
                "fine_tuned_genes": tuned_genes,
                "action": action,
                "new_generation": next_gen,
                "new_genome": {k: str(v) if isinstance(v, Decimal) else v for k, v in asdict(new_g).items()}
            })

        if save_history:
            cls.save_history(next_gen, evolution_records, evolution_seed=gen_seed)
        result_tuple = (next_gen, evolution_records)
        cls._last_records = result_tuple
        return logs, result_tuple

    @classmethod
    def save_history(cls, generation: int, records: List[Dict[str, Any]], evolution_seed: Optional[int] = None, storage: Optional[Any] = None) -> None:
        if getattr(sys, "frozen", False) and "ARENA_MEMORY_DIR" not in os.environ:
            appdata = os.environ.get("APPDATA")
            mem_dir = os.path.join(appdata, "TradeBot0", "memory") if appdata else os.path.join(os.path.expanduser("~"), ".tradebot0", "memory")
        else:
            mem_dir = os.environ.get("ARENA_MEMORY_DIR", "memory")
        os.makedirs(mem_dir, exist_ok=True)
        hist_path = os.path.join(mem_dir, "arena_history.json")
        history: List[Dict[str, Any]] = []
        if os.path.exists(hist_path):
            try:
                with open(hist_path, "r", encoding="utf-8") as f:
                    history = json.load(f)
            except Exception as e:
                logger.debug("Failed to load arena history, starting fresh: %s", e)
                history = []

        if evolution_seed is None:
            evolution_seed = records[0].get("evolution_seed") if records else None
        if evolution_seed is None:
            evolution_seed = cls._generation_seed(generation)
        history.append({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "generation": generation,
            "evolution_seed": int(evolution_seed),
            "competitors": records
        })
        if len(history) > 500:
            history = history[-500:]
        tmp_path = hist_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, hist_path)

        if records:
            # Audit 3.20: reuse a caller-owned storage when given (the
            # live engine passes self.storage); otherwise create one and
            # close it in the finally below -- previously a fresh
            # ArenaStorage was created per evolution and never closed.
            owned_storage = storage is None
            try:
                if owned_storage:
                    from src.data.persistence import ArenaStorage
                    storage = ArenaStorage()
                champ = records[0]
                storage.save_evolution_generation(
                    generation=generation,
                    champion_id=str(champ.get("portfolio_id", "")),
                    champion_name=str(champ.get("portfolio_id", "")),
                    champion_roi=float(champ.get("prev_roi_pct", 0.0)),
                    champion_sharpe=float(champ.get("prev_sharpe", 0.0)),
                    champion_max_dd=float(champ.get("prev_max_dd_pct", 0.0)),
                    elite_genome=champ.get("new_genome", {}),
                    evolution_seed=int(evolution_seed),
                )
            except Exception as e:
                logger.warning("Failed to persist evolution history to SQLite: %s", e)
            finally:
                if owned_storage and storage is not None:
                    storage.close()

    _save_evolution_history = save_history

