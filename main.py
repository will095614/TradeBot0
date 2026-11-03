import logging
import sys
from decimal import Decimal
from src.gui.dashboard import ArenaDashboard
from src.data.timemachine import TimeMachineArena
from src.data.eth_feed import ETHFeed

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("TradeBot0")


def main() -> None:
    if "--self-test" in sys.argv:
        import ctypes
        import ssl
        import sqlite3
        import lzma
        import bz2
        import pandas as pd
        import webview
        import json
        from src.data.live_engine import LiveArenaEngine
        app = ArenaDashboard(initial_cash=Decimal("100000.00"))
        json.dumps(app.engine.get_ui_state(), allow_nan=False)
        print("SELF_TEST_OK")
        return

    if "--cli" in sys.argv:
        generations = 1
        if "--evolve" in sys.argv:
            idx = sys.argv.index("--evolve")
            if idx + 1 < len(sys.argv) and sys.argv[idx + 1].isdigit():
                generations = max(1, int(sys.argv[idx + 1]))
            else:
                generations = 3

        print(f"=== TradeBot0 CLI Time Machine & Style-B Evolution Arena (Generations: {generations}) ===")
        bars = ETHFeed.fetch_historical_bars(ticker="BTC-USD", period="1mo", interval="15m")
        arena = TimeMachineArena(symbol="BTC/USD", initial_cash=Decimal("100000.00"))

        if generations > 1:
            rankings = arena.run_evolution_tournament(bars, generations=generations)
        else:
            rankings = arena.run_simulation(bars)

        print("\nOfficial Final Leaderboard:")
        for r in rankings:
            print(
                f"#{r.rank} {r.name:<48} | Equity=${r.equity:,.2f} | ROI={r.roi_pct:+.2f}% | "
                f"MaxDD={r.max_drawdown_pct:.2f}% | Win={r.win_rate_pct:.1f}% ({r.closed_trades}) | "
                f"Sharpe={r.sharpe_ratio:.2f} | Sortino={r.sortino_ratio:.2f} | Fitness={r.fitness_score:+.2f}"
            )
    else:
        app = ArenaDashboard(initial_cash=Decimal("100000.00"))
        app.run()


if __name__ == "__main__":
    main()
