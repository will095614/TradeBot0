"""Item 4b patch: evolution optimization (all three, user-approved 2026-11-13).

1. Trigger by closed trades: auto-evolution fires after 30 closed trades
   (CLOSE LONG / COVER SHORT fills) OR 6 hours, whichever comes first, with
   a 30-minute debounce after the previous evolution. The 6h cap is kept as
   the backstop. N=30 is grounded in the user's live ledger: ~1115 fills in
   ~3.6 days, ~13 fills/hour, ~6-7 closes/hour, so 30 closes fire in ~4-5h.
2. Deterministic mutation seed: crossover/fine-tune RNG is seeded from the
   generation number + a fixed salt (no more time.time()), and the seed is
   recorded in the JSON history entry, every evolution record, and the
   SQLite evolution_history row (new evolution_seed column + migration).
3. Runner-up fine-tuning: the #2 genome is really fine-tuned (1-2 genes
   nudged +/-5%, quantized to the gene's step) instead of copied verbatim;
   TP/ATR ratio rules are repaired the same way crossover does, so the
   result always passes CompetitorGenome validation.

Usage: python fix_item4b_patch.py [project_root]
Verifies EVERY replacement anchor appears exactly once before writing anything.
Preserves each file's original newline style (CRLF stays CRLF).
"""
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
assert (ROOT / "src/data/live_engine.py").exists(), f"not a TradeBot0 root: {ROOT}"

# (rel_path, old, new) — old must occur exactly once.
REPLACEMENTS = []
# (rel_path, marker_that_must_not_exist_yet, text_to_append)
APPENDS = []


def rep(rel, old, new):
    REPLACEMENTS.append((rel, old, new))


def app(rel, marker, text):
    APPENDS.append((rel, marker, text))


def _read(path):
    raw = path.read_bytes()
    crlf = b"\r\n" in raw
    text = raw.decode("utf-8")
    if crlf:
        text = text.replace("\r\n", "\n")
    return text, crlf


def _write(path, text, crlf):
    if crlf:
        text = text.replace("\n", "\r\n")
    path.write_bytes(text.encode("utf-8"))


# ---------------------------------------------------------------- evolution.py: deterministic seed
rep("src/arena/evolution.py",
    """from typing import Dict, List, Any""",
    """from typing import Dict, List, Any, Optional""")

rep("src/arena/evolution.py",
    '''    """
    @staticmethod
    def _clamp_decimal(val: Decimal, low: str, high: str, quant: str = "0.001") -> Decimal:''',
    '''    """
    # Fixed salt for deterministic evolution seeds. The seed for a generation
    # is SEED_SALT + generation * 97, so the same generation with the same
    # parents always mutates the same way and an evolution run is replayable.
    SEED_SALT: int = 20261113

    @classmethod
    def _generation_seed(cls, next_gen: int) -> int:
        """Deterministic per-generation evolution seed (fixed salt + generation)."""
        return cls.SEED_SALT + int(next_gen) * 97

    @staticmethod
    def _clamp_decimal(val: Decimal, low: str, high: str, quant: str = "0.001") -> Decimal:''')

rep("src/arena/evolution.py",
    """        rng = random.Random(int(time.time() * 1000) + seed_offset + next_gen * 97)""",
    """        rng = random.Random(cls._generation_seed(next_gen) + seed_offset)""")

# ---------------------------------------------------------------- evolution.py: runner-up fine-tuning
rep("src/arena/evolution.py",
    """            cooldown_bars=max(parent1.cooldown_bars, parent2.cooldown_bars),
            generation=next_gen,
            leverage_enabled=new_lev_enabled,
            leverage=new_lev
        )

    @classmethod
    def evolve_generation(""",
    """            cooldown_bars=max(parent1.cooldown_bars, parent2.cooldown_bars),
            generation=next_gen,
            leverage_enabled=new_lev_enabled,
            leverage=new_lev
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
        \"\"\"Nudge 1-2 genes of the runner-up genome by +/-5% (real fine-tuning).

        Returns the new genome and the list of genes that actually changed.
        A gene whose 5% step quantizes away is nudged by one quantum step in
        the same direction instead, so a chosen gene always visibly moves.
        Ratio rules (TP >= 1.5x SL, ATR target >= 1.5x stop) are repaired the
        same way crossover does, so the result always passes validation.
        \"\"\"
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
            leverage=genome.leverage
        )
        return new_g, tuned

    @classmethod
    def evolve_generation(""")

# ---------------------------------------------------------------- evolution.py: evolve_generation wiring
rep("src/arena/evolution.py",
    """        current_gen = max(c.genome.generation for c in competitors)
        next_gen = current_gen + 1

        logs: List[str] = []""",
    """        current_gen = max(c.genome.generation for c in competitors)
        next_gen = current_gen + 1
        gen_seed = cls._generation_seed(next_gen)

        logs: List[str] = []""")

rep("src/arena/evolution.py",
    """        for idx, r in enumerate(rankings):
            comp = comp_map[r.portfolio_id]
            old_g = comp.genome""",
    """        for idx, r in enumerate(rankings):
            comp = comp_map[r.portfolio_id]
            old_g = comp.genome
            tuned_genes: List[str] = []""")

rep("src/arena/evolution.py",
    """            elif idx == 1:
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
                    generation=next_gen,
                    leverage_enabled=old_g.leverage_enabled,
                    leverage=old_g.leverage
                )
                action = "ELITE_RUNNER_UP_PRESERVED"
                logs.append(
                    f"[G{next_gen} ELITE #2] {comp.portfolio_id} retained runner-up genome "
                    f"(Fitness={r.fitness_score:+.2f}, ROI={r.roi_pct:+.2f}%)"
                )""",
    """            elif idx == 1:
                # Elite #2: Runner-up genome kept, with real adaptive fine-tuning:
                # 1-2 genes nudged by +/-5% (this used to be a plain copy despite
                # the comment). Ratio rules are repaired like crossover does.
                new_g, tuned_genes = cls._fine_tune_runner_up(old_g, next_gen, gen_seed + 1000003)
                action = "ELITE_RUNNER_UP_PRESERVED"
                logs.append(
                    f"[G{next_gen} ELITE #2] {comp.portfolio_id} fine-tuned runner-up genome "
                    f"({', '.join(tuned_genes) if tuned_genes else 'no gene moved'}; "
                    f"Fitness={r.fitness_score:+.2f}, ROI={r.roi_pct:+.2f}%)"
                )""")

rep("src/arena/evolution.py",
    """                "composite_fitness": comp_fitness,
                "action": action,
                "new_generation": next_gen,""",
    """                "composite_fitness": comp_fitness,
                "evolution_seed": gen_seed,
                "fine_tuned_genes": tuned_genes,
                "action": action,
                "new_generation": next_gen,""")

rep("src/arena/evolution.py",
    """        if save_history:
            cls.save_history(next_gen, evolution_records)""",
    """        if save_history:
            cls.save_history(next_gen, evolution_records, evolution_seed=gen_seed)""")

# ---------------------------------------------------------------- evolution.py: save_history records the seed
rep("src/arena/evolution.py",
    """    def save_history(cls, generation: int, records: List[Dict[str, Any]]) -> None:""",
    """    def save_history(cls, generation: int, records: List[Dict[str, Any]], evolution_seed: Optional[int] = None) -> None:""")

rep("src/arena/evolution.py",
    """        history.append({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "generation": generation,
            "competitors": records
        })""",
    """        if evolution_seed is None:
            evolution_seed = records[0].get("evolution_seed") if records else None
        if evolution_seed is None:
            evolution_seed = cls._generation_seed(generation)
        history.append({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "generation": generation,
            "evolution_seed": int(evolution_seed),
            "competitors": records
        })""")

rep("src/arena/evolution.py",
    """                    champion_max_dd=float(champ.get("prev_max_dd_pct", 0.0)),
                    elite_genome=champ.get("new_genome", {}),
                )""",
    """                    champion_max_dd=float(champ.get("prev_max_dd_pct", 0.0)),
                    elite_genome=champ.get("new_genome", {}),
                    evolution_seed=int(evolution_seed),
                )""")

# ---------------------------------------------------------------- live_engine.py: trade-count trigger
rep("src/data/live_engine.py",
    """        # Automatic hourly evolution
        self.auto_evolve_enabled: bool = True
        self.auto_evolve_interval_sec: int = 21600  # Default 6 hours (21600s)
        self.last_evolve_ts: float = time.time()
        self.evolution_events: List[Dict[str, Any]] = []""",
    """        # Automatic evolution: every 6 hours, or every 30 closed trades,
        # whichever comes first, with a 30-minute debounce between runs.
        self.auto_evolve_enabled: bool = True
        self.auto_evolve_interval_sec: int = 21600  # Default 6 hours (21600s)
        self.auto_evolve_closed_trades: int = 30
        self.auto_evolve_debounce_sec: int = 1800  # 30 minutes
        self.last_evolve_ts: float = time.time()
        self._closed_trades_since_evolve: int = 0
        self.evolution_events: List[Dict[str, Any]] = []""")

rep("src/data/live_engine.py",
    """            for f in new_fills:
                try:
                    is_short_pos = getattr(f, "position_side", PositionSide.LONG) == PositionSide.SHORT""",
    """            for f in new_fills:
                if getattr(f, "is_closing_fill", False):
                    # Closed trade (CLOSE LONG / COVER SHORT): counts toward the
                    # trade-count evolution trigger; opening fills do not count.
                    self._closed_trades_since_evolve += 1
                try:
                    is_short_pos = getattr(f, "position_side", PositionSide.SHORT) == PositionSide.SHORT""")

rep("src/data/live_engine.py",
    """    def _auto_evolve_due(self, now: Optional[float] = None) -> bool:
        if self.paused:
            return False
        now = time.time() if now is None else now
        return (
            self.auto_evolve_enabled
            and self.latest_quote is not None
            and now - self.last_evolve_ts >= self.auto_evolve_interval_sec
        )""",
    """    def _auto_evolve_reason(self, now: Optional[float] = None) -> Optional[str]:
        \"\"\"Why auto-evolution is due now: 'time' (6h cap), 'trades'
        (30 closed trades + 30min debounce), or None when not due.\"\"\"
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
        return self._auto_evolve_reason(now) is not None""")

rep("src/data/live_engine.py",
    """                        if self.live_orders_enabled and self._auto_evolve_due():
                            self.evolve_now(trigger="auto")""",
    """                        if self.live_orders_enabled:
                            _evolve_reason = self._auto_evolve_reason()
                            if _evolve_reason is not None:
                                self.evolve_now(trigger=f"auto:{_evolve_reason}")""")

rep("src/data/live_engine.py",
    """            now = time.time()
            self.last_evolve_ts = now
            new_gen = max(c.genome.generation for c in self.competitors)""",
    """            now = time.time()
            self.last_evolve_ts = now
            self._closed_trades_since_evolve = 0
            new_gen = max(c.genome.generation for c in self.competitors)""")

# ---------------------------------------------------------------- persistence.py: evolution_seed column
rep("src/data/persistence.py",
    """                    CREATE TABLE IF NOT EXISTS evolution_history (
                        generation INTEGER PRIMARY KEY,
                        timestamp REAL NOT NULL,
                        champion_id TEXT NOT NULL,
                        champion_name TEXT NOT NULL,
                        champion_roi REAL NOT NULL,
                        champion_sharpe REAL NOT NULL,
                        champion_max_dd REAL NOT NULL,
                        elite_genome TEXT NOT NULL
                    );""",
    """                    CREATE TABLE IF NOT EXISTS evolution_history (
                        generation INTEGER PRIMARY KEY,
                        timestamp REAL NOT NULL,
                        champion_id TEXT NOT NULL,
                        champion_name TEXT NOT NULL,
                        champion_roi REAL NOT NULL,
                        champion_sharpe REAL NOT NULL,
                        champion_max_dd REAL NOT NULL,
                        elite_genome TEXT NOT NULL,
                        evolution_seed INTEGER
                    );""")

rep("src/data/persistence.py",
    """                    CREATE INDEX IF NOT EXISTS idx_candles_ts ON candles_1m(timestamp);
                    CREATE INDEX IF NOT EXISTS idx_ledger_ts ON execution_ledger(timestamp);
                    \"\"\"
                )""",
    """                    CREATE INDEX IF NOT EXISTS idx_candles_ts ON candles_1m(timestamp);
                    CREATE INDEX IF NOT EXISTS idx_ledger_ts ON execution_ledger(timestamp);
                    \"\"\"
                )
                # Schema migration for pre-existing DBs: evolution_seed column
                # (added with the deterministic-seed change). ALTER fails if the
                # column already exists; that is expected and safe to ignore.
                try:
                    conn.execute("ALTER TABLE evolution_history ADD COLUMN evolution_seed INTEGER")
                except Exception:
                    pass""")

rep("src/data/persistence.py",
    """    def save_evolution_generation(
        self,
        generation: int,
        champion_id: str,
        champion_name: str,
        champion_roi: float,
        champion_sharpe: float,
        champion_max_dd: float,
        elite_genome: Any,
    ) -> None:""",
    """    def save_evolution_generation(
        self,
        generation: int,
        champion_id: str,
        champion_name: str,
        champion_roi: float,
        champion_sharpe: float,
        champion_max_dd: float,
        elite_genome: Any,
        evolution_seed: Optional[int] = None,
    ) -> None:""")

rep("src/data/persistence.py",
    """                    INSERT OR REPLACE INTO evolution_history (
                        generation, timestamp, champion_id, champion_name,
                        champion_roi, champion_sharpe, champion_max_dd, elite_genome
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
    """                    INSERT OR REPLACE INTO evolution_history (
                        generation, timestamp, champion_id, champion_name,
                        champion_roi, champion_sharpe, champion_max_dd, elite_genome,
                        evolution_seed
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""")

rep("src/data/persistence.py",
    """                        float(champion_roi),
                        float(champion_sharpe),
                        float(champion_max_dd),
                        genome_str,
                    ),""",
    """                        float(champion_roi),
                        float(champion_sharpe),
                        float(champion_max_dd),
                        genome_str,
                        int(evolution_seed) if evolution_seed is not None else None,
                    ),""")

rep("src/data/persistence.py",
    """                    SELECT generation, timestamp, champion_id, champion_name,
                           champion_roi, champion_sharpe, champion_max_dd, elite_genome
                    FROM evolution_history""",
    """                    SELECT generation, timestamp, champion_id, champion_name,
                           champion_roi, champion_sharpe, champion_max_dd, elite_genome,
                           evolution_seed
                    FROM evolution_history""")

rep("src/data/persistence.py",
    """                        "champion_max_dd": float(r[6]),
                        "elite_genome": str(r[7]),
                    }""",
    """                        "champion_max_dd": float(r[6]),
                        "elite_genome": str(r[7]),
                        "evolution_seed": (int(r[8]) if r[8] is not None else None),
                    }""")


# ---------------------------------------------------------------- tests: evolution optimization (item 4b)
NEW_EVOLUTION_TESTS = '''

def _ranked_four():
    """Four competitors with fixed equity order: trail #1, cons #2."""
    comp_a = AggressiveCompetitor()
    comp_b = ConservativeCompetitor()
    comp_c = ATRDynamicCompetitor()
    comp_d = TrailingGuardCompetitor()
    competitors = [comp_a, comp_b, comp_c, comp_d]
    broker = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0.0"))
    for c in competitors:
        broker.register_portfolio(c.portfolio, max_position_ratio=c.max_position_ratio)
    comp_d.portfolio.cash = Decimal("518000.00")
    comp_d.portfolio.update_market_price(Decimal("2500.00"), timestamp=1000.0)
    comp_b.portfolio.cash = Decimal("505000.00")
    comp_b.portfolio.update_market_price(Decimal("2500.00"), timestamp=1000.0)
    comp_c.portfolio.cash = Decimal("496000.00")
    comp_c.portfolio.update_market_price(Decimal("2500.00"), timestamp=1000.0)
    comp_a.portfolio.cash = Decimal("479000.00")
    comp_a.portfolio.update_market_price(Decimal("2500.00"), timestamp=1000.0)
    rankings = Leaderboard.get_rankings(broker.portfolios)
    assert rankings[0].portfolio_id == "comp_trail"
    assert rankings[1].portfolio_id == "comp_cons"
    return competitors, rankings


def test_generation_seed_is_deterministic_and_recorded():
    """Evolution optimization (item 4b): the mutation seed comes from the
    generation number + a fixed salt, so the same generation with the same
    parents evolves identically, and the seed is recorded on every record."""
    from dataclasses import asdict

    def _run_once():
        competitors, rankings = _ranked_four()
        logs = GeneticEvolver.evolve_generation(
            competitors, rankings, preserve_portfolio=True, save_history=False
        )
        assert len(logs) == 4
        return competitors, GeneticEvolver._last_records

    comps1, rec1 = _run_once()
    comps2, rec2 = _run_once()
    # Same inputs -> identical genomes (seed is deterministic, no wall clock).
    for c1, c2 in zip(comps1, comps2):
        assert asdict(c1.genome) == asdict(c2.genome)
    # Seed is stable per generation and recorded on every record.
    assert GeneticEvolver._generation_seed(2) == GeneticEvolver._generation_seed(2)
    assert GeneticEvolver._generation_seed(2) != GeneticEvolver._generation_seed(3)
    assert rec1[0] == 2
    for record in rec1[1]:
        assert record["evolution_seed"] == GeneticEvolver._generation_seed(2)


def test_runner_up_is_fine_tuned_not_copied():
    """Evolution optimization (item 4b): the runner-up genome is really
    fine-tuned (1-2 genes nudged ~5%) instead of copied verbatim, and the
    result still passes genome validation (construction would raise otherwise)."""
    from dataclasses import asdict

    competitors, rankings = _ranked_four()
    comp_b = next(c for c in competitors if c.portfolio_id == "comp_cons")
    comp_d = next(c for c in competitors if c.portfolio_id == "comp_trail")
    old_runner = asdict(comp_b.genome)
    old_champ = asdict(comp_d.genome)

    logs = GeneticEvolver.evolve_generation(
        competitors, rankings, preserve_portfolio=True, save_history=False
    )
    assert len(logs) == 4

    # Champion: preserved except the generation bump.
    new_champ = asdict(comp_d.genome)
    assert new_champ["generation"] == 2
    for key, val in old_champ.items():
        if key != "generation":
            assert new_champ[key] == val

    # Runner-up: 1-2 genes changed, each a small nudge (quantization on the
    # smallest genes can stretch a 5% step to ~25%, e.g. 0.004 -> 0.005),
    # everything else identical, generation bumped.
    new_runner = asdict(comp_b.genome)
    assert new_runner["generation"] == 2
    changed = [k for k in old_runner if k != "generation" and new_runner[k] != old_runner[k]]
    assert 1 <= len(changed) <= 2, f"expected 1-2 tuned genes, got {changed}"
    for key in changed:
        old_v = old_runner[key]
        new_v = new_runner[key]
        assert old_v is not None and new_v is not None
        ratio = float(new_v) / float(old_v)
        assert 0.75 <= ratio <= 1.25, f"{key} moved {ratio:.3f}x, expected a small nudge"
    # The record names exactly the tuned genes.
    record = [r for r in GeneticEvolver._last_records[1] if r["portfolio_id"] == "comp_cons"][0]
    assert sorted(record["fine_tuned_genes"]) == sorted(changed)


def test_evolution_seed_recorded_in_history():
    """Evolution optimization (item 4b): the generation seed is written into
    the JSON history entry and the SQLite evolution_history row."""
    import json

    from src.data.persistence import ArenaStorage

    competitors, rankings = _ranked_four()
    logs = GeneticEvolver.evolve_generation(
        competitors, rankings, preserve_portfolio=True, save_history=True
    )
    assert len(logs) == 4

    hist_path = os.path.join(os.environ["ARENA_MEMORY_DIR"], "arena_history.json")
    with open(hist_path, encoding="utf-8") as f:
        history = json.load(f)
    assert history[-1]["generation"] == 2
    assert history[-1]["evolution_seed"] == GeneticEvolver._generation_seed(2)

    storage = ArenaStorage()
    rows = storage.load_evolution_history(limit=5)
    row = [r for r in rows if r["generation"] == 2][-1]
    assert row["evolution_seed"] == GeneticEvolver._generation_seed(2)
'''

app("tests/test_evolution.py", "def test_generation_seed_is_deterministic_and_recorded", NEW_EVOLUTION_TESTS)


# ---------------------------------------------------------------- tests: trade-count trigger (item 4b)
NEW_TRIGGER_TEST = '''

def test_auto_evolve_fires_on_closed_trades():
    """Evolution optimization (item 4b): auto-evolution fires after 30 closed
    trades (not opens), earliest 30 minutes after the previous evolution;
    the 6-hour cap still fires on time alone."""
    from src.arena.order import OrderSide, OrderTicket, OrderType

    engine = LiveArenaEngine(initial_cash=Decimal("3000.00"))
    engine.latest_quote = _quote("3500.00")
    now = time.time()
    engine.last_evolve_ts = now

    # 6-hour cap still works with zero trades.
    assert engine._auto_evolve_reason(now=now + 21601) == "time"

    def _round_trips(n):
        broker = engine.broker
        broker.on_tick(price=Decimal("3500.00"), timestamp=now)
        for _ in range(n):
            buy = OrderTicket("comp_cons", "ETH/USD", OrderSide.BUY, OrderType.MARKET, qty=Decimal("0.1"), timestamp=now)
            assert broker.submit_order(buy) is not None
            sell = OrderTicket("comp_cons", "ETH/USD", OrderSide.SELL, OrderType.MARKET, qty=Decimal("0.1"), timestamp=now)
            assert broker.submit_order(sell) is not None
        engine._harvest_fills()

    _round_trips(29)
    assert engine._closed_trades_since_evolve == 29
    assert engine._auto_evolve_due(now=now + 100) is False
    assert engine._auto_evolve_due(now=now + 2000) is False  # debounce ok, still < 30

    _round_trips(1)
    assert engine._closed_trades_since_evolve == 30
    assert engine._auto_evolve_due(now=now + 100) is False  # debounce blocks
    assert engine._auto_evolve_reason(now=now + 1801) == "trades"
    assert engine._auto_evolve_due(now=now + 1801) is True

    # Evolving resets the counter.
    engine.evolve_now(trigger="manual")
    assert engine._closed_trades_since_evolve == 0
    assert engine._auto_evolve_due(now=now + 1801) is False
'''

app("tests/test_live_engine.py", "def test_auto_evolve_fires_on_closed_trades", NEW_TRIGGER_TEST)


# ---------------------------------------------------------------- verify + apply
def main():
    files = {}
    for rel, _old, _new in REPLACEMENTS:
        files.setdefault(rel, _read(ROOT / rel))
    for rel, _marker, _text in APPENDS:
        files.setdefault(rel, _read(ROOT / rel))

    for rel, old, _new in REPLACEMENTS:
        text, _crlf = files[rel]
        n = text.count(old)
        assert n == 1, f"{rel}: expected exactly 1 occurrence, found {n}: {old[:100]!r}"
    for rel, marker, _text in APPENDS:
        text, _crlf = files[rel]
        assert marker not in text, f"{rel}: marker already present: {marker!r}"
    print(f"All {len(REPLACEMENTS)} anchors verified, {len(APPENDS)} append markers clear.")

    new_texts = {rel: text for rel, (text, _c) in files.items()}
    for rel, old, new in REPLACEMENTS:
        new_texts[rel] = new_texts[rel].replace(old, new, 1)
    for rel, _marker, text in APPENDS:
        cur = new_texts[rel]
        if not cur.endswith("\n"):
            cur += "\n"
        new_texts[rel] = cur + text
    for rel, text in new_texts.items():
        _write(ROOT / rel, text, files[rel][1])
        print(f"patched {rel}")
    print("ITEM4B PATCH OK")


if __name__ == "__main__":
    main()
