from __future__ import annotations

from typing import Any

__all__ = ["ArenaDashboard"]


def __getattr__(name: str) -> Any:
    # Lazy export: avoids a circular import (src.data.live_engine -> src.gui.view_model -> src.gui -> dashboard -> live_engine)
    if name == "ArenaDashboard":
        from src.gui.dashboard import ArenaDashboard
        return ArenaDashboard
    raise AttributeError(f"module 'src.gui' has no attribute {name!r}")
