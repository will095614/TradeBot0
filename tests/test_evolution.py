from decimal import Decimal
import os
import pytest
from src.arena.broker_sim import BrokerSim
from src.arena.order import OrderTicket, OrderSide, OrderType, ExecutionReason
from src.arena.portfolio import Portfolio
from src.arena.leaderboard import Leaderboard
from src.arena.evolution import GeneticEvolver
from src.competitors.aggressive import AggressiveCompetitor
from src.competitors.conservative import ConservativeCompetitor
from src.competitors.atr_dynamic import ATRDynamicCompetitor
from src.competitors.trailing_guard import TrailingGuardCompetitor


def test_exact_take_profit_and_win_rate_calculation():
    broker = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0.0"))
    p = Portfolio("p_tp", "TP Tester", initial_cash=Decimal("3000.00"))
    broker.register_portfolio(p, max_position_ratio=Decimal("0.50"))

    # Enter at $2500 with TP at $2600, SL at $2450
    broker.on_tick(price=Decimal("2500.00"), timestamp=1000.0)
    ticket = OrderTicket(
        portfolio_id="p_tp",
        symbol="ETH/USD",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        qty=Decimal("0.4000"),
        stop_loss=Decimal("2450.00"),
        take_profit=Decimal("2600.00"),
        timestamp=1000.0
    )
    buy_fill = broker.submit_order(ticket)
    assert buy_fill is not None

    # Candle spikes to high $2620 (piercing $2600 TP), even though close pulls back to $2510
    fills = broker.on_tick(
        price=Decimal("2510.00"),
        high=Decimal("2620.00"),
        low=Decimal("2495.00"),
        timestamp=1900.0,
        open_price=Decimal("2505.00")
    )
    assert len(fills) == 1
    tp_fill = fills[0]
    # Must fill at exact $2600.00 Take-Profit limit price, NOT $2510.00 close!
    assert tp_fill.price == Decimal("2600.00")
    assert tp_fill.reason == ExecutionReason.TAKE_PROFIT
    assert tp_fill.realized_pnl > Decimal("0")
    assert p.win_count == 1
    assert Leaderboard.calculate_win_rate(p) == Decimal("100.00")


def test_style_b_genetic_evolution_elitism_and_mutation():
    comp_a = AggressiveCompetitor()
    comp_b = ConservativeCompetitor()
    comp_c = ATRDynamicCompetitor()
    comp_d = TrailingGuardCompetitor()
    competitors = [comp_a, comp_b, comp_c, comp_d]

    broker = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0.0"))
    for c in competitors:
        broker.register_portfolio(c.portfolio, max_position_ratio=c.max_position_ratio)

    # Simulate different equity outcomes
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

    old_trail_sl = comp_d.genome.stop_loss_pct
    # Test Scheme 1: Compounded portfolio equity preserved across generations
    logs = GeneticEvolver.evolve_generation(competitors, rankings, preserve_portfolio=True)
    assert len(logs) == 4
    for c in competitors:
        assert c.genome.generation == 2
    assert comp_d.portfolio.total_equity == Decimal("518000.00")
    assert comp_b.portfolio.total_equity == Decimal("505000.00")
    # Champion elite stop loss must be preserved
    assert comp_d.genome.stop_loss_pct == old_trail_sl

    # Test clean reset mode when preserve_portfolio=False
    GeneticEvolver.evolve_generation(competitors, rankings, preserve_portfolio=False)
    for c in competitors:
        assert c.portfolio.total_equity == Decimal("100000.00")
    assert os.path.exists(os.path.join("memory", "arena_history.json"))


def test_evolution_save_history_decoupled_from_lock():
    comp_a = AggressiveCompetitor()
    comp_b = ConservativeCompetitor()
    comp_c = ATRDynamicCompetitor()
    comp_d = TrailingGuardCompetitor()
    competitors = [comp_a, comp_b, comp_c, comp_d]

    broker = BrokerSim(symbol="ETH/USD", slippage_pct=Decimal("0.0"))
    for c in competitors:
        broker.register_portfolio(c.portfolio, max_position_ratio=c.max_position_ratio)
    rankings = Leaderboard.get_rankings(broker.portfolios)

    # Calling with save_history=False produces records without disk I/O
    logs = GeneticEvolver.evolve_generation(competitors, rankings, preserve_portfolio=True, save_history=False)
    assert len(logs) == 4
    last_records = GeneticEvolver._last_records
    assert last_records is not None
    assert last_records[0] == 2  # next generation
    assert len(last_records[1]) == 4

    # Explicit save_history call outside locks succeeds
    GeneticEvolver.save_history(last_records[0], last_records[1])
    assert os.path.exists(os.path.join("memory", "arena_history.json"))



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
