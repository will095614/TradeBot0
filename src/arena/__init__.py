from src.arena.order import OrderTicket, OrderSide, OrderType, OrderStatus, ExecutionReason, FillEvent
from src.arena.portfolio import Portfolio
from src.arena.broker_sim import BrokerSim
from src.arena.risk_guard import RiskGuard
from src.arena.leaderboard import Leaderboard, CompetitorStats

__all__ = [
    "OrderTicket",
    "OrderSide",
    "OrderType",
    "OrderStatus",
    "ExecutionReason",
    "FillEvent",
    "Portfolio",
    "BrokerSim",
    "RiskGuard",
    "Leaderboard",
    "CompetitorStats",
    "GeneticEvolver",
]


def __getattr__(name: str):
    # Lazy-load GeneticEvolver so importing src.competitors before src.arena
    # cannot trigger a circular import with src.competitors.base.
    if name == "GeneticEvolver":
        from src.arena.evolution import GeneticEvolver
        return GeneticEvolver
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
