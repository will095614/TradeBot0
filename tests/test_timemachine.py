from decimal import Decimal
import os
import pytest
from src.data.eth_feed import CandleBar
from src.data.timemachine import TimeMachineArena

def test_timemachine_simulation_with_synthetic_bars():
    arena = TimeMachineArena(symbol="ETH/USD", initial_cash=Decimal("500000.00"))
    
    # Create 30 synthetic candle bars with an upward trend then downward trend
    bars = []
    base_price = Decimal("2500.00")
    for i in range(40):
        if i < 20:
            price = base_price + Decimal(i * 15)  # Rising
            ema_fast = price - Decimal("5.00")
            ema_slow = price - Decimal("20.00")
            rsi = Decimal("55.00")
        else:
            price = base_price + Decimal(20 * 15) - Decimal((i - 20) * 20) # Falling
            ema_fast = price - Decimal("10.00")
            ema_slow = price + Decimal("5.00")
            rsi = Decimal("40.00")
            
        bar = CandleBar(
            timestamp=1000.0 + (i * 900),
            open_=price - Decimal("2.00"),
            high=price + Decimal("5.00"),
            low=price - Decimal("5.00"),
            close=price,
            volume=Decimal("150.0"),
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            rsi=rsi,
            atr=Decimal("25.00")
        )
        bars.append(bar)
        
    rankings = arena.run_simulation(bars)
    assert len(rankings) == 6
    for r in rankings:
        assert r.rank in [1, 2, 3, 4, 5, 6]
        assert r.equity > Decimal("0")
        
    # The report lands under ARENA_MEMORY_DIR (redirected to a tmp dir by conftest).
    mem_dir = os.environ.get("ARENA_MEMORY_DIR", "memory")
    assert os.path.exists(os.path.join(mem_dir, "arena_report.md"))


def test_backtest_opens_shorts_on_downtrend():
    """Audit 2.2: a SELL signal while flat must open a short.

    Before the fix run_simulation never passed side=SELL, so side
    defaulted to BUY and a SELL could only ever close -- the backtest
    (and therefore evolution) was long-only. The bar series below is
    built so the signals land exactly: bar 1-2 BUY (longs open),
    bar 3 SELL (longs close), bar 5 SELL while flat (shorts open),
    bar 9 SELL (shorts close). Aggressive's short branch is
    unconditional, so comp_agg must open a short; the close path is
    checked both ways and Aggressive ends flat.
    """
    from src.arena.order import ExecutionReason, OrderSide

    arena = TimeMachineArena(symbol="ETH/USD", initial_cash=Decimal("500000.00"))
    # (close, ema_fast, ema_slow, rsi) per bar; high/low = close +/- 5.
    spec = [
        (Decimal("2800.00"), Decimal("2805.00"), Decimal("2790.00"), Decimal("55.00")),  # 0 HOLD
        (Decimal("2820.00"), Decimal("2815.00"), Decimal("2800.00"), Decimal("55.00")),  # 1 BUY
        (Decimal("2840.00"), Decimal("2835.00"), Decimal("2820.00"), Decimal("55.00")),  # 2 BUY
        (Decimal("2820.00"), Decimal("2810.00"), Decimal("2830.00"), Decimal("55.00")),  # 3 SELL
        (Decimal("2810.00"), Decimal("2815.00"), Decimal("2800.00"), Decimal("75.00")),  # 4 HOLD
        (Decimal("2790.00"), Decimal("2780.00"), Decimal("2800.00"), Decimal("55.00")),  # 5 SELL
        (Decimal("2770.00"), Decimal("2760.00"), Decimal("2780.00"), Decimal("55.00")),  # 6 HOLD
        (Decimal("2750.00"), Decimal("2740.00"), Decimal("2760.00"), Decimal("55.00")),  # 7 HOLD
        (Decimal("2745.00"), Decimal("2750.00"), Decimal("2735.00"), Decimal("75.00")),  # 8 HOLD
        (Decimal("2730.00"), Decimal("2720.00"), Decimal("2740.00"), Decimal("55.00")),  # 9 SELL
    ]
    bars = [
        CandleBar(
            timestamp=1000.0 + (i * 900),
            open_=price - Decimal("2.00"),
            high=price + Decimal("5.00"),
            low=price - Decimal("5.00"),
            close=price,
            volume=Decimal("100.0"),
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            rsi=rsi,
            atr=Decimal("40.00"),
        )
        for i, (price, ema_fast, ema_slow, rsi) in enumerate(spec)
    ]
    rankings = arena.run_simulation(bars)
    assert len(rankings) == 6

    audit = arena.broker.execution_audit
    # At least one short fill on the synthetic downtrend (audit §7).
    short_entries = [
        f for f in audit
        if f.side == OrderSide.SELL and f.reason == ExecutionReason.SIGNAL_ENTRY
    ]
    assert short_entries, "no short opened on the downtrend"
    # Aggressive's short branch is unconditional: it must have opened.
    assert any(f.portfolio_id == "comp_agg" for f in short_entries)
    # The close path is intact both ways: bar 3 SELL closes the long,
    # bar 9 SELL closes the short (a BUY cover, not a second short).
    assert any(
        f.portfolio_id == "comp_agg" and f.side == OrderSide.SELL
        and f.reason == ExecutionReason.SIGNAL_EXIT for f in audit
    )
    assert any(
        f.portfolio_id == "comp_agg" and f.side == OrderSide.BUY
        and f.reason == ExecutionReason.SIGNAL_EXIT for f in audit
    )
    assert arena.comp_a.portfolio.position_qty == Decimal("0")


def test_timemachine_evolution_preserves_portfolio():
    arena = TimeMachineArena(symbol="ETH/USD", initial_cash=Decimal("500000.00"))
    
    # 25 synthetic candle bars
    bars = []
    base_price = Decimal("2500.00")
    for i in range(25):
        price = base_price + Decimal(i * 10)
        bar = CandleBar(
            timestamp=1000.0 + (i * 900),
            open_=price - Decimal("2.00"),
            high=price + Decimal("4.00"),
            low=price - Decimal("4.00"),
            close=price,
            volume=Decimal("100.0"),
            ema_fast=price - Decimal("5.00"),
            ema_slow=price - Decimal("15.00"),
            rsi=Decimal("56.00"),
            atr=Decimal("20.00")
        )
        bars.append(bar)
        
    rankings_g1 = arena.run_simulation(bars)
    assert len(rankings_g1) == 6
    
    # Evolve to Generation 2 with preserve_portfolio=True (Scheme 1)
    logs = arena.evolve_next_generation(rankings_g1, preserve_portfolio=True)
    assert len(logs) == 6
    
    # Check that generation advanced and portfolio positions/cash remain intact
    gen = max(c.genome.generation for c in arena.competitors)
    assert gen == 2
    for c in arena.competitors:
        assert c.portfolio.total_equity > Decimal("0")
        assert c.portfolio_id in arena.broker.competitor_caps


def test_r_multiple_dynamic_budget_sizing():
    from src.competitors.conservative import ConservativeCompetitor
    from src.arena.broker_sim import BrokerSim
    broker = BrokerSim(symbol="ETH/USD")
    comp = ConservativeCompetitor(initial_cash=Decimal("3000.00"))
    broker.register_portfolio(comp.portfolio, max_position_ratio=comp.max_position_ratio)
    
    # 1. Wide stop: stop loss is $200 away (risk_qty = 30 / 200 = 0.1500 ETH)
    entry = Decimal("3000.00")
    wide_stop = Decimal("2800.00")
    qty_wide = comp.compute_r_multiple_qty(entry, wide_stop, broker)
    
    # 2. Narrow stop: stop loss is $30 away (risk_qty = 30 / 30 = 1.0000 ETH, capped by 25% cap = 0.2500 ETH)
    narrow_stop = Decimal("2970.00")
    qty_narrow = comp.compute_r_multiple_qty(entry, narrow_stop, broker)
    
    # Wide stop must result in strictly smaller position than narrow stop
    assert qty_wide < qty_narrow
    assert qty_wide == Decimal("0.1500")
    assert qty_narrow == Decimal("0.2500")
    
    # Max loss at wide stop: (entry - stop) * qty <= risk_budget + buffer
    loss_at_wide_stop = (entry - wide_stop) * qty_wide
    risk_budget = comp.portfolio.total_equity * comp.genome.risk_per_trade_pct
    assert loss_at_wide_stop <= (risk_budget + Decimal("1.00"))


def test_monte_carlo_ev_gate_odds_evaluation():
    from src.data.timemachine import MonteCarloOddsEvaluator
    evaluator = MonteCarloOddsEvaluator(seed=19)
    
    # Reasonable scalper bracket: 1.5R target with realistic stop
    odds_pass = evaluator.evaluate_bracket(
        entry_price=Decimal("2500.00"),
        stop_loss=Decimal("2485.00"),
        take_profit=Decimal("2525.00"),
        atr=Decimal("4.00")
    )
    assert odds_pass.passed is True
    assert odds_pass.expected_r >= -0.05
    assert odds_pass.r_multiple > 1.0
    d = odds_pass.to_dict()
    assert "verdict" in d
    assert "expected_r" in d
    
    # Hostile / absurd bracket: stop is $5 away, but target is $200 away (40R in 30 minutes)
    odds_absurd = evaluator.evaluate_bracket(
        entry_price=Decimal("2500.00"),
        stop_loss=Decimal("2495.00"),
        take_profit=Decimal("2700.00"),
        atr=Decimal("2.00"),
        n_steps=30
    )
    assert odds_absurd.passed is False
    assert "Blocked" in odds_absurd.verdict




def test_orb_window_excludes_current_bar():
    """Item 2 regression: ORB range must come from closed bars only.

    Before the fix the current bar was included in the ORB window, so its
    own high became the range ceiling and a breakout could (almost) never
    trigger: 60 BUY bars produced 0 ORB fills.
    """
    arena = TimeMachineArena(symbol="ETH/USD", initial_cash=Decimal("500000.00"))
    bars = []
    for i in range(15):
        price = Decimal("2495.00")
        bars.append(CandleBar(
            timestamp=1000.0 + (i * 900),
            open_=price - Decimal("2.00"),
            high=Decimal("2500.00"),
            low=Decimal("2490.00"),
            close=price,
            volume=Decimal("100.0"),
            ema_fast=price + Decimal("1.00"),
            ema_slow=price - Decimal("5.00"),
            rsi=Decimal("55.00"),
            atr=Decimal("25.00")
        ))
    bars.append(CandleBar(
        timestamp=1000.0 + (15 * 900),
        open_=Decimal("2505.00"),
        high=Decimal("2515.00"),
        low=Decimal("2500.00"),
        close=Decimal("2510.00"),
        volume=Decimal("100.0"),
        ema_fast=Decimal("2508.00"),
        ema_slow=Decimal("2500.00"),
        rsi=Decimal("56.00"),
        atr=Decimal("25.00")
    ))
    rankings = arena.run_simulation(bars)
    assert len(rankings) == 6
    # The breakout bar closes above the prior 15-bar high (2500): ORB must fire.
    assert arena.comp_e.portfolio.position_qty > Decimal("0")


def test_zero_volume_bar_does_not_invent_volume():
    """F2: a volume=0 bar contributes weight 0 to the session VWAP.

    Bar 1 has typ 2500 on 100 volume; bar 2 has typ 2600 on 0 volume.
    The VWAP after bar 2 must stay 2500.00 -- the old fallback counted
    the zero-volume bar as 100.0 and dragged it to 2550.00.
    Observed through the mean_ref each competitor receives.
    """
    arena = TimeMachineArena(symbol="ETH/USD", initial_cash=Decimal("500000.00"))
    seen_vwap = []
    orig_evaluate = arena.comp_a.evaluate_signal

    def _spy(signal, market_price, indicators, broker, timestamp):
        seen_vwap.append(indicators["mean_ref"])
        return orig_evaluate(
            signal=signal, market_price=market_price, indicators=indicators,
            broker=broker, timestamp=timestamp,
        )

    arena.comp_a.evaluate_signal = _spy
    bars = [
        CandleBar(
            timestamp=1000.0, open_=Decimal("2498.00"), high=Decimal("2502.00"),
            low=Decimal("2498.00"), close=Decimal("2500.00"), volume=Decimal("100.0"),
            ema_fast=Decimal("2499.00"), ema_slow=Decimal("2495.00"),
            rsi=Decimal("55.00"), atr=Decimal("25.00"),
        ),
        CandleBar(
            timestamp=1900.0, open_=Decimal("2598.00"), high=Decimal("2602.00"),
            low=Decimal("2598.00"), close=Decimal("2600.00"), volume=Decimal("0"),
            ema_fast=Decimal("2599.00"), ema_slow=Decimal("2595.00"),
            rsi=Decimal("55.00"), atr=Decimal("25.00"),
        ),
    ]
    arena.run_simulation(bars)
    assert len(seen_vwap) == 2
    assert seen_vwap[0] == Decimal("2500.00")
    assert seen_vwap[1] == Decimal("2500.00")
# =========================================================== P1-A
# Multi-generation tournament + Monte Carlo without NumPy (A1).
# ===========================================================


def test_evolution_tournament_runs_multiple_generations():
    """P1 §2.8 (timemachine.py:140-158): run_evolution_tournament over
    3 generations produces a ranking each generation, advances the
    generation number by 1 per generation, and really changes genes
    (the rank-1 elite is preserved apart from its generation bump)."""
    from dataclasses import asdict

    arena = TimeMachineArena(symbol="ETH/USD", initial_cash=Decimal("500000.00"))
    bars = []
    base_price = Decimal("2500.00")
    for i in range(40):
        if i < 20:
            price = base_price + Decimal(i * 15)  # Rising
        else:
            price = base_price + Decimal(20 * 15) - Decimal((i - 20) * 20)  # Falling
        bars.append(CandleBar(
            timestamp=1000.0 + (i * 900),
            open_=price - Decimal("2.00"),
            high=price + Decimal("5.00"),
            low=price - Decimal("5.00"),
            close=price,
            volume=Decimal("150.0"),
            ema_fast=price - Decimal("5.00"),
            ema_slow=price - Decimal("20.00"),
            rsi=Decimal("55.00"),
            atr=Decimal("25.00"),
        ))
    before = {c.portfolio_id: asdict(c.genome) for c in arena.competitors}

    rankings = arena.run_evolution_tournament(bars, generations=3)

    assert len(rankings) == 6
    assert sorted(r.rank for r in rankings) == [1, 2, 3, 4, 5, 6]
    for r in rankings:
        assert r.equity > Decimal("0")
    # Two evolutions happened (gen 1 -> 3): every genome carries gen 3.
    assert all(c.genome.generation == 3 for c in arena.competitors)
    changed = 0
    for c in arena.competitors:
        old = before[c.portfolio_id]
        new = asdict(c.genome)
        moved = [k for k in old if k != "generation" and new[k] != old[k]]
        if c.portfolio_id == rankings[0].portfolio_id:
            # Rank-1 elite: preserved verbatim apart from the generation bump.
            assert moved == [], f"elite {c.portfolio_id} genes moved: {moved}"
        elif moved:
            changed += 1
    assert changed >= 4, f"expected >= 4 non-elite competitors to evolve, got {changed}"


def test_monte_carlo_without_numpy_reports_unknown(monkeypatch):
    """A1: with NumPy missing, the Monte Carlo evaluator ran zero paths,
    so it must report unknown (None) -- never the old invented fixed
    probabilities 0.35 / 0.45 / 0.20 / 0.48 -- and fail the EV gate.
    r_multiple / breakeven_prob are pure bracket geometry, so they stay numeric."""
    import src.data.timemachine as tm

    monkeypatch.setattr(tm, "np", None)
    evaluator = tm.MonteCarloOddsEvaluator(seed=19)
    odds = evaluator.evaluate_bracket(
        entry_price=Decimal("2500.00"),
        stop_loss=Decimal("2485.00"),
        take_profit=Decimal("2525.00"),
        atr=Decimal("4.00"),
    )
    assert odds.passed is False
    assert odds.target_prob is None
    assert odds.stop_prob is None
    assert odds.neither_prob is None
    assert odds.green_prob is None
    assert odds.expected_r is None
    assert odds.decided_win_rate is None
    assert "Unknown" in odds.verdict
    assert "NumPy" in odds.verdict
    d = odds.to_dict()  # must not raise on None values
    assert d["passed"] is False
    assert d["target_prob"] is None
    assert d["stop_prob"] is None
    assert d["neither_prob"] is None
    assert d["green_prob"] is None
    assert d["expected_r"] is None
    assert d["decided_win_rate"] is None
    assert d["r_multiple"] == 1.67  # (2525-2500)/(2500-2485) = 25/15
    assert d["breakeven_prob"] == 0.375  # 1 / (1 + 5/3)

# =========================================================== P2-A
# A2: the uncapped-runner 1.8R is a labelled model assumption.
# ===========================================================


def test_uncapped_runner_r_assumption_is_labelled():
    """A2: a bracket with no take-profit is evaluated as if its target
    sat at 1.8R -- a MODEL ASSUMPTION, not a measured exit. The value
    (1.8) is unchanged; what changes is that the assumption is now a
    named constant, flagged on the result, and footnoted in the backtest
    report instead of silently posing as bracket geometry."""
    from src.data.timemachine import MonteCarloOddsEvaluator, UNCAPPED_RUNNER_R_MULTIPLE

    assert UNCAPPED_RUNNER_R_MULTIPLE == 1.8
    evaluator = MonteCarloOddsEvaluator(seed=19)

    # Long runner, no TP: r_multiple is the assumed 1.8R, flagged as such.
    odds_long = evaluator.evaluate_bracket(
        entry_price=Decimal("2500.00"),
        stop_loss=Decimal("2485.00"),
        take_profit=None,
        atr=Decimal("4.00"),
    )
    assert odds_long.r_multiple == 1.8
    assert odds_long.r_multiple_is_assumption is True
    d_long = odds_long.to_dict()
    assert d_long["r_multiple"] == 1.8
    assert d_long["r_multiple_is_assumption"] is True

    # Short runner, no TP: same assumption, mirrored downward.
    odds_short = evaluator.evaluate_bracket(
        entry_price=Decimal("2500.00"),
        stop_loss=Decimal("2515.00"),
        take_profit=None,
        atr=Decimal("4.00"),
    )
    assert odds_short.r_multiple == 1.8
    assert odds_short.r_multiple_is_assumption is True

    # Capped bracket: the real TP drives r_multiple, no assumption flag.
    odds_capped = evaluator.evaluate_bracket(
        entry_price=Decimal("2500.00"),
        stop_loss=Decimal("2485.00"),
        take_profit=Decimal("2525.00"),
        atr=Decimal("4.00"),
    )
    assert odds_capped.r_multiple == pytest.approx(25 / 15)  # (2525-2500)/(2500-2485)
    assert odds_capped.r_multiple_is_assumption is False
    assert odds_capped.to_dict()["r_multiple_is_assumption"] is False

    # The backtest report footnotes the assumption where uncapped
    # runners appear ("Unbounded (Run)").
    arena = TimeMachineArena(symbol="ETH/USD", initial_cash=Decimal("500000.00"))
    bars = [
        CandleBar(
            timestamp=1000.0 + (i * 900), open_=Decimal("2500.00"),
            high=Decimal("2505.00"), low=Decimal("2495.00"),
            close=Decimal("2500.00"), volume=Decimal("100.0"),
            ema_fast=Decimal("2499.00"), ema_slow=Decimal("2495.00"),
            rsi=Decimal("55.00"), atr=Decimal("25.00"),
        )
        for i in range(2)
    ]
    arena.run_simulation(bars)
    mem_dir = os.environ.get("ARENA_MEMORY_DIR", "memory")
    report = open(os.path.join(mem_dir, "arena_report.md"), encoding="utf-8").read()
    assert "Unbounded (Run)" in report
    assert "1.8R" in report
    assert "model assumption" in report
