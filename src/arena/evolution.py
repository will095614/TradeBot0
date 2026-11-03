from __future__ import annotations
from dataclasses import asdict
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Any
import json
import os
import random
import time

from src.arena.leaderboard import CompetitorStats
from src.competitors.base import BaseCompetitor, CompetitorGenome


class GeneticEvolver:
    """
    Style B Evolutionary Engine (Genetic Parameter Tournament).
    Implements Elitism (Top 2 survive) + Crossover & Bounded Gaussian Mutation (Bottom 2 evolve)
    and persists generational lineage into ECC structured memory (memory/arena_history.json).
    """
    @staticmethod
    def _clamp_decimal(val: Decimal, low: str, high: str, quant: str = "0.001") -> Decimal:
        clamped = max(Decimal(low), min(Decimal(high), val))
        return clamped.quantize(Decimal(quant), rounding=ROUND_HALF_UP)

    @classmethod
    def crossover_and_mutate(
        cls,
        parent1: CompetitorGenome,
        parent2: CompetitorGenome,
        next_gen: int,
        seed_offset: int = 0
    ) -> CompetitorGenome:
        rng = random.Random(int(time.time() * 1000) + seed_offset + next_gen * 97)

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
        new_trail_trig = cls._clamp_decimal(
            blend(parent1.trailing_trigger_pct, parent2.trailing_trigger_pct, 0.12), "1.2", "3.5", "0.1"
        )
        new_trail_dist = cls._clamp_decimal(
            blend(parent1.trailing_distance_pct, parent2.trailing_distance_pct, 0.15), "0.004", "0.012", "0.001"
        )
        new_risk_pct = cls._clamp_decimal(
            blend(parent1.risk_per_trade_pct, parent2.risk_per_trade_pct, 0.12), "0.008", "0.030", "0.001"
        )

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
            generation=next_gen
        )

    @classmethod
    def evolve_generation(
        cls,
        competitors: List[BaseCompetitor],
        rankings: List[CompetitorStats],
        preserve_portfolio: bool = True
    ) -> List[str]:
        """
        Evolves the competitor pool in-place for the next generation based on Arena rankings.
        Returns human-readable evolution log entries.
        """
        comp_map: Dict[str, BaseCompetitor] = {c.portfolio_id: c for c in competitors}
        if len(rankings) < 2:
            return []

        champion_stats = rankings[0]
        runner_up_stats = rankings[1]
        champ_comp = comp_map[champion_stats.portfolio_id]
        runner_comp = comp_map[runner_up_stats.portfolio_id]

        current_gen = max(c.genome.generation for c in competitors)
        next_gen = current_gen + 1

        logs: List[str] = []
        evolution_records: List[Dict[str, Any]] = []

        for idx, r in enumerate(rankings):
            comp = comp_map[r.portfolio_id]
            old_g = comp.genome

            if idx == 0:
                # Elite #1: Champion genome preserved with generation bump
                new_g = CompetitorGenome(
                    position_ratio=old_g.position_ratio,
                    risk_per_trade_pct=old_g.risk_per_trade_pct,
                    stop_loss_pct=old_g.stop_loss_pct,
                    take_profit_pct=old_g.take_profit_pct,
                    atr_risk_pct=old_g.atr_risk_pct,
                    atr_stop_mult=old_g.atr_stop_mult,
                    atr_target_mult=old_g.atr_target_mult,
                    trailing_trigger_pct=old_g.trailing_trigger_pct,
                    trailing_distance_pct=old_g.trailing_distance_pct,
                    cooldown_bars=old_g.cooldown_bars,
                    generation=next_gen
                )
                action = "ELITE_CHAMPION_PRESERVED"
                logs.append(
                    f"[G{next_gen} ELITE #1] {comp.portfolio_id} retained winning genome "
                    f"(Fitness={r.fitness_score:+.2f}, ROI={r.roi_pct:+.2f}%)"
                )
            elif idx == 1:
                # Elite #2: Runner-up genome preserved with adaptive fine-tuning
                new_g = CompetitorGenome(
                    position_ratio=old_g.position_ratio,
                    risk_per_trade_pct=old_g.risk_per_trade_pct,
                    stop_loss_pct=old_g.stop_loss_pct,
                    take_profit_pct=old_g.take_profit_pct,
                    atr_risk_pct=old_g.atr_risk_pct,
                    atr_stop_mult=old_g.atr_stop_mult,
                    atr_target_mult=old_g.atr_target_mult,
                    trailing_trigger_pct=old_g.trailing_trigger_pct,
                    trailing_distance_pct=old_g.trailing_distance_pct,
                    cooldown_bars=old_g.cooldown_bars,
                    generation=next_gen
                )
                action = "ELITE_RUNNER_UP_PRESERVED"
                logs.append(
                    f"[G{next_gen} ELITE #2] {comp.portfolio_id} retained runner-up genome "
                    f"(Fitness={r.fitness_score:+.2f}, ROI={r.roi_pct:+.2f}%)"
                )
            else:
                # Bottom performers: Crossover from Champion + Runner-up with Mutation
                new_g = cls.crossover_and_mutate(
                    champ_comp.genome,
                    runner_comp.genome,
                    next_gen=next_gen,
                    seed_offset=idx * 31
                )
                # Preserve archetype specialization (e.g. Aggressive keeps take_profit_pct=None)
                if comp.portfolio_id == "comp_agg":
                    new_g = CompetitorGenome(
                        position_ratio=cls._clamp_decimal(new_g.position_ratio * Decimal("1.15"), "0.45", "0.75", "0.01"),
                        stop_loss_pct=new_g.stop_loss_pct,
                        take_profit_pct=None,
                        atr_risk_pct=new_g.atr_risk_pct,
                        atr_stop_mult=new_g.atr_stop_mult,
                        atr_target_mult=new_g.atr_target_mult,
                        trailing_trigger_pct=new_g.trailing_trigger_pct,
                        trailing_distance_pct=new_g.trailing_distance_pct,
                        cooldown_bars=new_g.cooldown_bars,
                        generation=next_gen
                    )
                action = "CROSSOVER_MUTATED"
                logs.append(
                    f"[G{next_gen} MUTATED] {comp.portfolio_id} evolved from #{champion_stats.rank}x#{runner_up_stats.rank}: "
                    f"Size={float(old_g.position_ratio)*100:.0f}%->{float(new_g.position_ratio)*100:.0f}%, "
                    f"SL={float(old_g.stop_loss_pct)*100:.1f}%->{float(new_g.stop_loss_pct)*100:.1f}%"
                )

            comp.reset_for_new_generation(new_g, preserve_portfolio=preserve_portfolio)
            evolution_records.append({
                "portfolio_id": comp.portfolio_id,
                "prev_rank": r.rank,
                "prev_roi_pct": float(r.roi_pct),
                "prev_max_dd_pct": float(r.max_drawdown_pct),
                "prev_sharpe": r.sharpe_ratio,
                "prev_fitness": r.fitness_score,
                "action": action,
                "new_generation": next_gen,
                "new_genome": {k: str(v) if isinstance(v, Decimal) else v for k, v in asdict(new_g).items()}
            })

        cls._save_evolution_history(next_gen, evolution_records)
        return logs

    @staticmethod
    def _save_evolution_history(generation: int, records: List[Dict[str, Any]]) -> None:
        mem_dir = os.environ.get("ARENA_MEMORY_DIR", "memory")
        os.makedirs(mem_dir, exist_ok=True)
        hist_path = os.path.join(mem_dir, "arena_history.json")
        history: List[Dict[str, Any]] = []
        if os.path.exists(hist_path):
            try:
                with open(hist_path, "r", encoding="utf-8") as f:
                    history = json.load(f)
            except Exception:
                history = []

        history.append({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "generation": generation,
            "competitors": records
        })
        if len(history) > 500:
            history = history[-500:]
        with open(hist_path, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)

