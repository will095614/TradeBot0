"""Audit 3.21: auto-redeploy when all five are flat is behind an explicit
switch -- config key auto_redeploy_when_flat, default ON (current
behaviour preserved). With the switch OFF a flat arena stays flat;
with it ON the cadence redeploys, logging one line per flat episode.
"""
import logging
from decimal import Decimal

from src.data.live_engine import LiveArenaEngine
from src.intelligence.config_manager import DEFAULT_SYSTEM_CONFIG


def _flat_engine(**kwargs):
    return LiveArenaEngine(initial_cash=Decimal("100000.00"), **kwargs)


def test_config_default_is_on():
    assert DEFAULT_SYSTEM_CONFIG["auto_redeploy_when_flat"] is True


def test_switch_off_does_not_redeploy(monkeypatch):
    engine = _flat_engine(auto_redeploy_when_flat=False)
    calls = []
    monkeypatch.setattr(engine, "_ensure_active_live_positions", lambda p, t: calls.append((p, t)))
    assert engine._maybe_auto_redeploy(Decimal("3500.00"), 1000.0) is False
    assert calls == []


def test_switch_on_default_redeploys_when_flat(monkeypatch):
    engine = _flat_engine()  # default ON
    assert engine.auto_redeploy_when_flat is True
    calls = []
    monkeypatch.setattr(engine, "_ensure_active_live_positions", lambda p, t: calls.append((p, t)))
    assert engine._maybe_auto_redeploy(Decimal("3500.00"), 1000.0) is True
    assert calls == [(Decimal("3500.00"), 1000.0)]


def test_no_redeploy_when_any_position_open(monkeypatch):
    engine = _flat_engine()
    engine.comp_a.portfolio.position_qty = Decimal("5")
    calls = []
    monkeypatch.setattr(engine, "_ensure_active_live_positions", lambda p, t: calls.append((p, t)))
    assert engine._maybe_auto_redeploy(Decimal("3500.00"), 1000.0) is False
    assert calls == []


def test_redeploy_logs_once_per_flat_episode(monkeypatch, caplog):
    engine = _flat_engine()
    monkeypatch.setattr(engine, "_ensure_active_live_positions", lambda p, t: None)
    with caplog.at_level(logging.INFO):
        engine._maybe_auto_redeploy(Decimal("3500.00"), 1000.0)
        engine._maybe_auto_redeploy(Decimal("3500.00"), 1005.0)
        # A position opens, then closes again: a new episode logs again.
        engine.comp_a.portfolio.position_qty = Decimal("5")
        engine._maybe_auto_redeploy(Decimal("3500.00"), 1010.0)
        engine.comp_a.portfolio.position_qty = Decimal("0")
        engine._maybe_auto_redeploy(Decimal("3500.00"), 1015.0)
    hits = [r for r in caplog.records if "Auto-redeploy" in r.message]
    assert len(hits) == 2
