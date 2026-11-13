"""Item 4 patch: dead-champion fix + unify fitness formulas.

- Dead champion: reset_for_new_generation (preserve path) now clears the
  circuit breaker AND the drawdown clock for tripped competitors, so a
  tripped strategy gets a clean evaluation window next generation instead of
  staying dead forever while its equity-ranked genome is kept as ELITE.
  Resetting the flag alone would not stick: max_drawdown_pct is sticky, so
  broker_sim / risk_guard would re-trip it on the next bar/order.
- Fitness: GeneticEvolver.calculate_composite_fitness now delegates to the
  single canonical Leaderboard.calculate_fitness (the display formula, with
  Sortino and the -50 trip penalty). The old evolution-only formula
  (normalized ROI/Sharpe, no Sortino, no trip penalty) is retired.

Usage: python fix_item4_patch.py [project_root]
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


# ---------------------------------------------------------------- base.py: revive tripped competitors at generation boundary
rep("src/competitors/base.py",
    """        else:
            self.portfolio.name = self.name
            self.portfolio.leverage = eff_lev
            self.portfolio.leverage_enabled = new_genome.leverage_enabled""",
    """        else:
            self.portfolio.name = self.name
            self.portfolio.leverage = eff_lev
            self.portfolio.leverage_enabled = new_genome.leverage_enabled
            if self.portfolio.is_circuit_breaker_tripped:
                # Generation boundary = fresh risk clock. Resetting the flag
                # alone is not enough: max_drawdown_pct is sticky, so the
                # next bar (broker_sim) or order (risk_guard) would re-trip
                # the breaker immediately and the strategy would stay dead
                # forever while its equity-ranked genome is kept as ELITE.
                # Clear the drawdown clock as well so the strategy gets one
                # clean evaluation window next generation.
                self.portfolio.is_circuit_breaker_tripped = False
                self.portfolio.max_drawdown_pct = Decimal("0.00")
                self.portfolio.peak_equity = self.portfolio.total_equity""")

# ---------------------------------------------------------------- evolution.py: single canonical fitness
rep("src/arena/evolution.py",
    "from src.arena.leaderboard import CompetitorStats",
    "from src.arena.leaderboard import CompetitorStats, Leaderboard")

rep("src/arena/evolution.py",
    '''    @classmethod
    def calculate_composite_fitness(cls, ranking: CompetitorStats) -> Decimal:
        """
        Risk-Adjusted Multi-Objective Fitness Function (Phase 5):
        Fitness = 0.40 * ROI_norm + 0.35 * Sharpe_norm - 0.20 * MaxDD_penalty - 0.05 * Churn_penalty
        """
        roi = float(ranking.roi_pct)
        sharpe = float(ranking.sharpe_ratio)
        max_dd = float(ranking.max_drawdown_pct)
        trades = int(ranking.closed_trades)

        roi_component = min(3.0, max(-1.0, roi / 10.0)) * 0.40
        sharpe_component = min(3.0, max(-1.0, sharpe / 2.0)) * 0.35
        dd_penalty = ((max_dd / 15.0) ** 2) * 0.20
        churn_penalty = max(0.0, (trades - 50) / 100.0) * 0.05

        composite = roi_component + sharpe_component - dd_penalty - churn_penalty
        return Decimal(str(round(composite, 4)))''',
    '''    @classmethod
    def calculate_composite_fitness(cls, ranking: CompetitorStats) -> Decimal:
        """
        Single canonical fitness: delegates to Leaderboard.calculate_fitness,
        the same formula the leaderboard displays as fitness_score, so the
        evolution record's composite_fitness now agrees with prev_fitness.
        Fitness = 2.0*ROI + 1.5*Sharpe + 1.0*Sortino - 1.25*MaxDD
                  - 2.0*(MaxDD/15)^2 - 1.5*churn - 50 if circuit-tripped.
        The old evolution-only formula (normalized ROI/Sharpe, no Sortino,
        no trip penalty) is retired: it let a tripped competitor record a
        good composite fitness. Parent selection is unchanged: it ranks by
        total equity, not by fitness.
        """
        score = Leaderboard.calculate_fitness(
            float(ranking.roi_pct),
            float(ranking.max_drawdown_pct),
            ranking.sharpe_ratio,
            ranking.sortino_ratio,
            ranking.status == "CIRCUIT_TRIPPED",
            closed_trades=int(ranking.closed_trades),
        )
        return Decimal(str(score))''')

# ---------------------------------------------------------------- phase5 test: fixtures need the unified formula's inputs
rep("tests/test_performance_and_optimizations.py",
    """    steady_champ = SimpleNamespace(
        roi_pct=Decimal("8.5"),
        sharpe_ratio=2.4,
        max_drawdown_pct=Decimal("2.0"),
        closed_trades=18,
    )""",
    """    steady_champ = SimpleNamespace(
        roi_pct=Decimal("8.5"),
        sharpe_ratio=2.4,
        sortino_ratio=3.0,
        max_drawdown_pct=Decimal("2.0"),
        closed_trades=18,
        status="ACTIVE",
    )""")

rep("tests/test_performance_and_optimizations.py",
    """    reckless_gambler = SimpleNamespace(
        roi_pct=Decimal("9.0"),
        sharpe_ratio=0.4,
        max_drawdown_pct=Decimal("18.5"),
        closed_trades=110,
    )""",
    """    reckless_gambler = SimpleNamespace(
        roi_pct=Decimal("9.0"),
        sharpe_ratio=0.4,
        sortino_ratio=0.5,
        max_drawdown_pct=Decimal("18.5"),
        closed_trades=110,
        status="ACTIVE",
    )""")

# ---------------------------------------------------------------- new tests (appended to test_evolution.py)
NEW_TESTS = '''

def test_tripped_champion_revives_next_generation():
    """Dead champion (item 4): a tripped #1 by equity must trade again after
    evolution instead of staying dead forever as ELITE."""
    from src.arena.risk_guard import RiskGuard

    comp_a = AggressiveCompetitor()
    comp_b = ConservativeCompetitor()
    comp_c = ATRDynamicCompetitor()
    comp_d = TrailingGuardCompetitor()
    competitors = [comp_a, comp_b, comp_c, comp_d]

    broker = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0.0"))
    for c in competitors:
        broker.register_portfolio(c.portfolio, max_position_ratio=c.max_position_ratio)

    # Champion by equity, but circuit breaker tripped after a 16% drawdown
    # (peak 610k vs current 518k).
    comp_d.portfolio.cash = Decimal("518000.00")
    comp_d.portfolio.update_market_price(Decimal("2500.00"), timestamp=1000.0)
    comp_d.portfolio.peak_equity = Decimal("610000.00")
    comp_d.portfolio.max_drawdown_pct = Decimal("16.00")
    comp_d.portfolio.is_circuit_breaker_tripped = True
    comp_b.portfolio.cash = Decimal("505000.00")
    comp_b.portfolio.update_market_price(Decimal("2500.00"), timestamp=1000.0)
    comp_c.portfolio.cash = Decimal("496000.00")
    comp_c.portfolio.update_market_price(Decimal("2500.00"), timestamp=1000.0)
    comp_a.portfolio.cash = Decimal("479000.00")
    comp_a.portfolio.update_market_price(Decimal("2500.00"), timestamp=1000.0)

    rankings = Leaderboard.get_rankings(broker.portfolios)
    assert rankings[0].portfolio_id == "comp_trail"
    assert rankings[0].status == "CIRCUIT_TRIPPED"

    # While tripped, the champion cannot open new positions.
    ticket = OrderTicket(
        portfolio_id="comp_trail",
        symbol="ETH/USD",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        qty=Decimal("1.0000"),
        timestamp=1000.0,
    )
    ok, _reason = RiskGuard.validate_order(
        ticket, comp_d.portfolio, comp_d.max_position_ratio, Decimal("2500.00")
    )
    assert ok is False

    old_trail_sl = comp_d.genome.stop_loss_pct
    logs = GeneticEvolver.evolve_generation(
        competitors, rankings, preserve_portfolio=True, save_history=False
    )
    assert len(logs) == 4
    # Revived as ELITE (genome kept), breaker cleared, drawdown clock reset,
    # equity untouched.
    assert comp_d.genome.stop_loss_pct == old_trail_sl
    assert comp_d.genome.generation == 2
    assert comp_d.portfolio.is_circuit_breaker_tripped is False
    assert comp_d.portfolio.max_drawdown_pct == Decimal("0.00")
    assert comp_d.portfolio.peak_equity == comp_d.portfolio.total_equity
    assert comp_d.portfolio.total_equity == Decimal("518000.00")

    # The reset sticks: one more price update at the same level must not
    # re-trip the breaker, and new orders validate again.
    comp_d.portfolio.update_market_price(Decimal("2500.00"), timestamp=2000.0)
    assert comp_d.portfolio.max_drawdown_pct == Decimal("0.00")
    assert comp_d.portfolio.is_circuit_breaker_tripped is False
    ok, _reason = RiskGuard.validate_order(
        ticket, comp_d.portfolio, comp_d.max_position_ratio, Decimal("2500.00")
    )
    assert ok is True


def test_composite_fitness_matches_leaderboard_fitness():
    """Fitness unification (item 4): evolution's composite fitness is now the
    same number the leaderboard displays, including the -50 trip penalty."""
    from dataclasses import replace
    from src.arena.leaderboard import CompetitorStats

    stats = CompetitorStats(
        rank=1,
        portfolio_id="comp_test",
        name="Test",
        equity=Decimal("108500.00"),
        roi_pct=Decimal("8.50"),
        max_drawdown_pct=Decimal("2.00"),
        sharpe_ratio=2.4,
        sortino_ratio=3.0,
        profit_factor=1.8,
        win_rate_pct=Decimal("60.00"),
        total_trades=18,
        closed_trades=18,
        current_qty=Decimal("0"),
        cash=Decimal("108500.00"),
        fitness_score=0.0,
        status="ACTIVE",
    )
    # 8.5*2 + 2.4*1.5 + 3.0 - 2.0*1.25 - ((2/15)^2)*2 = 21.06
    assert GeneticEvolver.calculate_composite_fitness(stats) == Decimal("21.06")
    assert GeneticEvolver.calculate_composite_fitness(stats) == Decimal(str(
        Leaderboard.calculate_fitness(8.5, 2.0, 2.4, 3.0, False, closed_trades=18)
    ))
    tripped = replace(stats, status="CIRCUIT_TRIPPED")
    assert GeneticEvolver.calculate_composite_fitness(tripped) == Decimal("21.06") - Decimal("50")
'''

app("tests/test_evolution.py", "def test_tripped_champion_revives_next_generation", NEW_TESTS)


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
    print("ITEM4 PATCH OK")


if __name__ == "__main__":
    main()
