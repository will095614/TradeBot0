"""Audit 3.13: QuoteManager advertised a REST cascade it did not implement.

The class carried preferred_provider / provider_cooldown state and a
docstring promising a "Binance -> Kraken -> Coinbase" cascade, but it
only wraps the WebSocket feed -- the real cascade lives in
LiveArenaEngine.fetch_realtime_crypto_quote. The fix deletes the dead
state and corrects the docstrings; the WS quote path must keep working.
"""
from pathlib import Path

from src.data.quote_manager import QuoteManager


def test_dead_cascade_state_is_gone():
    source = (
        Path(__file__).resolve().parent.parent / "src" / "data" / "quote_manager.py"
    ).read_text(encoding="utf-8")
    assert "preferred_provider" not in source
    assert "provider_cooldown" not in source
    # The old advertising claims must be gone (the new docstring may
    # still name the cascade, but only to point at the real location).
    assert "3-provider HTTP REST" not in source
    assert "circuit-breaker cascade" not in source
    assert "self-healing REST circuit breaker" not in source

    qm = QuoteManager()
    assert not hasattr(qm, "preferred_provider")
    assert not hasattr(qm, "provider_cooldown")


def test_ws_quote_path_still_works(monkeypatch):
    qm = QuoteManager()
    sentinel = object()
    qm.ws_feed.latest_ws_quote = sentinel
    monkeypatch.setattr(qm.ws_feed, "is_fresh", lambda now=None: True)
    assert qm.get_fresh_ws_quote() is sentinel
    monkeypatch.setattr(qm.ws_feed, "is_fresh", lambda now=None: False)
    assert qm.get_fresh_ws_quote() is None
