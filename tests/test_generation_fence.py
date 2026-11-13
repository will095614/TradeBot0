"""Item 9: generation fence + silent-except logging (TradeBot0 maintenance)."""
import logging
from decimal import Decimal
from pathlib import Path

from src.arena.evolution import GeneticEvolver
from src.arena.order import ExecutionReason, FillEvent, OrderSide, PositionSide
from src.data.live_engine import LiveArenaEngine


def _make_fill(seq=1):
    return FillEvent(
        order_id="test-fill-1",
        portfolio_id="comp_agg",
        symbol="ETH/USD",
        side=OrderSide.BUY,
        qty=Decimal("1.0"),
        price=Decimal("2000.00"),
        fee=Decimal("1.00"),
        timestamp=1700000000.0,
        realized_pnl=Decimal("0.00"),
        reason=ExecutionReason.SIGNAL,
        fill_seq=seq,
        entry_price=None,
        position_side=PositionSide.LONG,
    )


def test_stale_engine_save_session_state_refused(caplog):
    """A superseded engine (a newer one exists) must not overwrite the new
    generation's session snapshot; the current engine still saves fine."""
    engine1 = LiveArenaEngine(symbol="ETH/USD", initial_cash=Decimal("100000.00"))
    assert engine1.save_session_state() is True
    engine2 = LiveArenaEngine(symbol="ETH/USD", initial_cash=Decimal("100000.00"))
    with caplog.at_level(logging.WARNING):
        assert engine1.save_session_state() is False
    assert "Stale engine epoch" in caplog.text
    assert engine2.save_session_state() is True


def test_stale_engine_harvest_fills_refused():
    """Fills from a superseded engine must not reach the SQLite ledger."""
    engine1 = LiveArenaEngine(symbol="ETH/USD", initial_cash=Decimal("100000.00"))
    engine2 = LiveArenaEngine(symbol="ETH/USD", initial_cash=Decimal("100000.00"))
    engine1.broker.execution_audit.append(_make_fill(seq=1))
    engine1._audit_cursor = 0
    engine1._harvest_fills()
    assert engine1.fill_records == []
    assert engine1.storage.load_recent_fills(limit=10) == []
    # The current engine records the same fill normally.
    engine2.broker.execution_audit.append(_make_fill(seq=1))
    engine2._audit_cursor = 0
    engine2._harvest_fills()
    assert len(engine2.fill_records) == 1
    assert len(engine2.storage.load_recent_fills(limit=10)) == 1


def test_stale_engine_evolve_now_refused():
    """A superseded engine must not evolve or persist evolution history."""
    engine1 = LiveArenaEngine(symbol="ETH/USD", initial_cash=Decimal("100000.00"))
    engine2 = LiveArenaEngine(symbol="ETH/USD", initial_cash=Decimal("100000.00"))
    assert engine1.evolve_now(trigger="manual") == []
    assert engine1.storage.load_evolution_history(limit=10) == []
    logs = engine2.evolve_now(trigger="manual")
    assert logs
    assert len(engine2.storage.load_evolution_history(limit=10)) == 1


def test_stale_engine_state_publish_skipped():
    """A superseded engine must not publish a UI snapshot anymore."""
    engine1 = LiveArenaEngine(symbol="ETH/USD", initial_cash=Decimal("100000.00"))
    engine1._publish_state_snapshot()
    assert engine1._ui_state_snapshot is not None
    LiveArenaEngine(symbol="ETH/USD", initial_cash=Decimal("100000.00"))
    engine1._ui_state_snapshot = None
    engine1._publish_state_snapshot()
    assert engine1._ui_state_snapshot is None


def test_save_history_failure_is_logged_not_swallowed(caplog, monkeypatch):
    """save_history SQLite failure must log a warning, not `pass` silently."""
    import src.data.persistence as persistence

    def _boom(*args, **kwargs):
        raise RuntimeError("disk exploded")

    monkeypatch.setattr(persistence.ArenaStorage, "save_evolution_generation", _boom)
    records = [{
        "portfolio_id": "comp_cons",
        "prev_roi_pct": 1.0,
        "prev_sharpe": 1.0,
        "prev_max_dd_pct": 1.0,
        "new_genome": {},
    }]
    with caplog.at_level(logging.WARNING):
        GeneticEvolver.save_history(1, records)
    assert "Failed to persist evolution history to SQLite" in caplog.text


def _keyframes_block(css, name):
    # Brace-matched block: @keyframes rules are not terminated by the next
    # @keyframes (arenaFadeIn is the last one in the file), so scan braces.
    start = css.index(f"@keyframes {name}")
    brace = css.index("{", start)
    depth = 0
    for i in range(brace, len(css)):
        if css[i] == "{":
            depth += 1
        elif css[i] == "}":
            depth -= 1
            if depth == 0:
                return css[start:i + 1]
    return css[start:]


def test_splash_overlay_is_lightened_not_removed():
    """Splash stays (user design) but lighter: blur 1px, veil 0.30.
    arenaFadeIn has no blur and must stay untouched; toast blur stays 8px."""
    css_path = Path(__file__).resolve().parent.parent / "src" / "gui" / "assets" / "app.css"
    css = css_path.read_text(encoding="utf-8")
    splash = css.split(".splash-overlay {", 1)[1].split("}", 1)[0]
    assert "blur(1px)" in splash
    assert "rgba(2, 6, 15, 0.30)" in splash
    assert "blur(3px)" not in splash
    assert "blur" not in _keyframes_block(css, "arenaFadeIn")
    assert "blur(8px)" in _keyframes_block(css, "toastSpringIn")
    assert "blur(8px)" in _keyframes_block(css, "toastSpringOut")
