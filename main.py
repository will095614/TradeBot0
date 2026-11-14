import logging
import sys
from decimal import Decimal
from src.gui.dashboard import ArenaDashboard
from src.data.timemachine import TimeMachineArena
from src.data.eth_feed import ETHFeed

from src.logging_setup import configure_logging

# Audit 3.10: the release build is windowed (PyInstaller console=False), so
# sys.stdout is None and a bare StreamHandler discards every log record.
# configure_logging always writes a rotating file log and keeps the console
# stream only when a real stdout exists.
configure_logging()
logger = logging.getLogger("TradeBot0")


def check_and_ensure_environment() -> bool:
    """
    Guarantees cross-Windows compatibility (Windows 7, 10, 11) for any user:
    1. Checks for Microsoft Edge WebView2 runtime.
    2. If missing, prompts the user with a native Win32 dialog offering one-click download/install
       via Microsoft's official Evergreen Bootstrapper.
    """
    if sys.platform != "win32":
        return True

    has_webview2 = False
    try:
        import winreg
        keys = [
            r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
            r"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
            r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{2CD8A007-E189-40E2-A670-D1E4E374AD5B}",
            r"SOFTWARE\Microsoft\EdgeUpdate\Clients\{2CD8A007-E189-40E2-A670-D1E4E374AD5B}",
        ]
        for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            for kpath in keys:
                try:
                    with winreg.OpenKey(root, kpath) as reg_key:
                        val, _ = winreg.QueryValueEx(reg_key, "pv")
                        if val and val != "0.0.0.0":
                            has_webview2 = True
                            break
                except Exception:
                    pass
            if has_webview2:
                break
    except Exception:
        has_webview2 = True

    if not has_webview2:
        import ctypes
        import webbrowser
        MB_YESNO = 0x04
        MB_ICONEXCLAMATION = 0x30
        IDYES = 6
        title = "TradeBot0 - Required Component Notice"
        msg = (
            "TradeBot0 requires the Microsoft Edge WebView2 Runtime to display its hardware-accelerated quant arena.\n\n"
            "This component was not detected on this system (common on Windows 7 or older Windows 10 editions).\n\n"
            "Would you like to open Microsoft's official download page to install the WebView2 Evergreen Bootstrapper now?"
        )
        res = ctypes.windll.user32.MessageBoxW(0, msg, title, MB_YESNO | MB_ICONEXCLAMATION)
        if res == IDYES:
            webbrowser.open("https://go.microsoft.com/fwlink/p/?LinkId=2124703")
        return False

    return True


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

        print(f"=== TradeBot0 CLI Time Machine & Evolution Arena (Generations: {generations}) ===")
        bars = ETHFeed.fetch_historical_bars(ticker="ETH-USD", period="1mo", interval="15m")
        arena = TimeMachineArena(symbol="ETH/USD", initial_cash=Decimal("100000.00"))

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
        if not check_and_ensure_environment():
            return
        app = ArenaDashboard(initial_cash=Decimal("100000.00"))
        import atexit
        import time
        atexit.register(app.stop)
        try:
            app.run()
        finally:
            logger.info("Exiting TradeBot0 process cleanly...")
            try:
                app.stop()
            except Exception:
                pass
            import gc
            import os
            import logging
            logging.shutdown()
            gc.collect()
            try:
                os.chdir(os.path.expanduser("~"))
            except Exception:
                pass
            time.sleep(0.4)


if __name__ == "__main__":
    main()
