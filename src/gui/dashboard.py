from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict, Optional

from src.data.live_engine import LiveArenaEngine

logger = logging.getLogger(__name__)


class _ArenaBridgeApi:
    """
    Native Python <-> WebView2 GPU Frontend Bridge.
    Exposes zero-latency state polling and interactive controls to the HiDPI UI.
    """

    def __init__(self, dashboard: "ArenaDashboard") -> None:
        self._dashboard = dashboard

    def get_state(self) -> Dict[str, Any]:
        return self._dashboard.engine.get_ui_state()

    def evolve_now(self) -> Dict[str, Any]:
        self._dashboard.engine.evolve_now(trigger="manual")
        return self._dashboard.engine.get_ui_state()

    def toggle_pause(self) -> Dict[str, Any]:
        self._dashboard.engine.paused = not self._dashboard.engine.paused
        return self._dashboard.engine.get_ui_state()

    def toggle_auto_evolve(self) -> Dict[str, Any]:
        self._dashboard.engine.toggle_auto_evolve()
        return self._dashboard.engine.get_ui_state()

    def set_evolve_interval(self, seconds: int) -> Dict[str, Any]:
        self._dashboard.engine.set_auto_evolve_interval(seconds)
        return self._dashboard.engine.get_ui_state()

    def reset_arena(self) -> Dict[str, Any]:
        self._dashboard.reset_engine()
        return self._dashboard.engine.get_ui_state()

    def toggle_fullscreen(self) -> bool:
        if self._dashboard.window:
            self._dashboard.window.toggle_fullscreen()
            return True
        return False


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>TradeBot0 - ETH/USD Multi-Strategy Quant Arena</title>
<style>
  :root {
    /* Ultra-Deep High-Contrast OLED Obsidian Dark Palette */
    --bg-canvas: #07090E;
    --bg-surface: #0C1018;
    --bg-elevated: #131824;
    --bg-elevated-hover: #1A2234;
    --bg-input: #090C12;
    
    --border-subtle: rgba(255, 255, 255, 0.08);
    --border-medium: rgba(255, 255, 255, 0.16);
    --border-focus: #38BDF8;
    
    /* Institutional Accent: Electric Cyan (Aerospace & Terminal Grade) */
    --accent: #38BDF8;
    --accent-hover: #0EA5E9;
    --accent-dim: rgba(56, 189, 248, 0.12);
    --accent-border: rgba(56, 189, 248, 0.35);
    --terracotta: #38BDF8; /* Backwards-compatible alias */
    --terracotta-hover: #0EA5E9;
    --terracotta-dim: rgba(56, 189, 248, 0.12);
    --terracotta-border: rgba(56, 189, 248, 0.35);

    /* Text & Ink: High-Contrast Pure White & Crisp Silvers */
    --text-primary: #FFFFFF;
    --text-secondary: #CBD5E1;
    --text-muted: #8290A5;

    /* Semantic Tones: High-Luminosity Neon Emerald & Fiery Crimson */
    --up: #00E676;
    --up-dim: rgba(0, 230, 118, 0.15);
    --down: #FF334B;
    --down-dim: rgba(255, 51, 75, 0.15);
    
    /* 6 Strategy Competitors: High Saturation & Vivid Electric Glow */
    --c-agg: #FF334B;   /* Neon Coral (Aggressive Breakout) */
    --c-cons: #38BDF8;  /* Electric Sky Cyan (Conservative Scalper) */
    --c-atr: #FFB800;   /* Electric Amber Gold (ATR Dynamic) */
    --c-trail: #00E676; /* Vivid Electric Emerald (Trailing Guard) */
    --c-orb: #A855F7;   /* Electric Violet (ORB Breakout) */
    --c-vwap: #14F195;  /* Mint Teal (Institutional VWAP) */

    /* Typography: Modern Quantitative Grotesk & Monospace */
    --font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI Variable Text', 'Segoe UI', 'Inter', system-ui, sans-serif;
    --font-mono: 'Cascadia Code', 'JetBrains Mono', 'Consolas', monospace;
    --font-serif: -apple-system, BlinkMacSystemFont, 'Segoe UI Variable Text', 'Segoe UI', 'Inter', system-ui, sans-serif;
  }

  * {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
    user-select: none;
  }

  html, body {
    width: 100vw;
    height: 100vh;
    overflow: hidden;
    background-color: var(--bg-canvas);
    color: var(--text-primary);
    font-family: var(--font-sans);
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    text-rendering: optimizeLegibility;
  }

  .num {
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
    letter-spacing: -0.015em;
  }

  .serif {
    font-family: var(--font-sans);
    letter-spacing: -0.015em;
  }

  /* App Shell: Fluid 100vh Layout */
  .app-shell {
    display: grid;
    grid-template-rows: auto 1fr;
    width: 100vw;
    height: 100vh;
    gap: 8px;
    padding: 8px 10px;
  }

  /* Top Command & Ticker Ribbon */
  .top-ribbon {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    padding: 9px 14px;
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: 7px;
  }

  .brand-cluster {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .brand-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 3px 8px;
    border-radius: 5px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    background: var(--terracotta-dim);
    color: var(--terracotta);
    border: 1px solid var(--terracotta-border);
  }

  .pulse-dot {
    width: 6.5px;
    height: 6.5px;
    border-radius: 50%;
    background: currentColor;
    box-shadow: 0 0 6px currentColor;
    animation: pulseAnim 1.6s infinite ease-in-out;
  }

  @keyframes pulseAnim {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.35; transform: scale(0.85); }
  }

  .title-group {
    display: flex;
    flex-direction: column;
  }

  .title-group h1 {
    font-size: 16px;
    font-weight: 700;
    color: var(--text-primary);
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .title-sub {
    font-size: 10.5px;
    color: var(--text-secondary);
  }

  .ticker-strip {
    display: flex;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
  }

  .stat-block {
    display: flex;
    flex-direction: column;
    gap: 1px;
  }

  .stat-lbl {
    font-size: 9.5px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
  }

  .stat-val {
    font-size: 13.5px;
    font-weight: 600;
    color: var(--text-primary);
  }

  .spot-hero {
    font-size: 21px;
    font-weight: 700;
    line-height: 1.05;
  }

  .up { color: var(--up); }
  .down { color: var(--down); }

  /* Auto Evolution Widget with Dynamic Interval Switcher */
  .auto-evolve-pill {
    display: flex;
    align-items: center;
    gap: 7px;
    padding: 3px 8px;
    background: var(--bg-elevated);
    border: 1px solid var(--border-subtle);
    border-radius: 6px;
    font-size: 11px;
    white-space: nowrap;
  }

  .interval-select {
    background: var(--accent-dim);
    border: 1px solid var(--accent-border);
    border-radius: 4px;
    color: var(--accent);
    font-family: inherit;
    font-size: 11px;
    font-weight: 700;
    padding: 1.5px 6px;
    cursor: pointer;
    outline: none;
    transition: all 0.15s ease;
  }

  .interval-select:hover, .interval-select:focus {
    border-color: var(--accent);
    background: rgba(56, 189, 248, 0.2);
    box-shadow: 0 0 8px rgba(56, 189, 248, 0.25);
  }

  .interval-select option {
    background: var(--bg-surface);
    color: var(--text-primary);
    padding: 4px 8px;
  }

  .auto-evolve-btn {
    background: transparent;
    border: none;
    cursor: pointer;
    color: var(--accent);
    font-weight: 700;
    padding: 0;
    text-decoration: underline;
    text-underline-offset: 2px;
  }

  .action-cluster {
    display: flex;
    align-items: center;
    gap: 7px;
    flex-wrap: wrap;
  }

  .btn {
    appearance: none;
    border: 1px solid var(--border-medium);
    background: var(--bg-elevated);
    color: var(--text-primary);
    font-family: var(--font-sans);
    font-size: 11px;
    font-weight: 600;
    padding: 5.5px 12px;
    border-radius: 5px;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 5px;
    transition: all 0.14s ease;
  }

  .btn:hover {
    background: var(--bg-elevated-hover);
    border-color: var(--border-focus);
    transform: translateY(-1px);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4);
  }

  .btn:active {
    transform: translateY(0);
  }

  .btn-primary, .btn-terracotta {
    background: linear-gradient(180deg, #0284C7 0%, #0369A1 100%);
    border-color: rgba(56, 189, 248, 0.45);
    color: #FFFFFF;
    font-weight: 700;
    box-shadow: 0 2px 8px rgba(2, 132, 199, 0.3);
  }

  .btn-primary:hover, .btn-terracotta:hover {
    background: linear-gradient(180deg, #0EA5E9 0%, #0284C7 100%);
    border-color: #38BDF8;
    box-shadow: 0 4px 14px rgba(56, 189, 248, 0.45);
  }

  /* Main Workspace Split */
  .workspace-grid {
    display: grid;
    grid-template-columns: minmax(0, 1.4fr) minmax(430px, 1fr);
    gap: 8px;
    min-height: 0;
    width: 100%;
    height: 100%;
  }

  @media (max-width: 1120px) {
    html, body { overflow-y: auto; }
    .app-shell { height: auto; min-height: 100vh; }
    .workspace-grid { grid-template-columns: 1fr; }
  }

  .left-column {
    display: flex;
    flex-direction: column;
    min-height: 0;
    min-width: 0;
    height: 100%;
  }

  .left-column > .panel {
    flex: 1;
    height: 100%;
  }

  .right-column {
    display: grid;
    grid-template-rows: auto minmax(120px, 1fr);
    gap: 7px;
    min-height: 0;
    min-width: 0;
  }

  /* Top-Right Enhanced Quant Arena Hub - Zero-Scroll High-Density Layout */
  .top-right-body {
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: flex-start;
    gap: 3px;
    padding: 4px 6px;
    min-height: 0;
    overflow-y: auto;
  }

  .tactical-hud {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 3px;
    flex-shrink: 0;
  }

  @media (max-width: 980px) {
    .tactical-hud { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  }

  /* Micro-Animations & Glow FX */
  @keyframes radarRipple {
    0% { transform: scale(0.6); opacity: 0.9; }
    70% { transform: scale(1.8); opacity: 0; }
    100% { transform: scale(2.2); opacity: 0; }
  }

  @keyframes tickUpGlow {
    0% { color: var(--up); text-shadow: 0 0 16px rgba(0, 230, 118, 0.85); transform: scale(1.025); }
    100% { transform: scale(1); }
  }

  @keyframes tickDownGlow {
    0% { color: var(--down); text-shadow: 0 0 16px rgba(255, 51, 75, 0.85); transform: scale(1.025); }
    100% { transform: scale(1); }
  }

  .spot-hero.tick-up {
    animation: tickUpGlow 0.85s cubic-bezier(0.2, 0.8, 0.2, 1);
  }

  .spot-hero.tick-down {
    animation: tickDownGlow 0.85s cubic-bezier(0.2, 0.8, 0.2, 1);
  }

  @keyframes markerPulse {
    0% { transform: translate(-50%, -50%) scale(1); box-shadow: 0 0 0 0 rgba(255, 255, 255, 0.85); }
    70% { transform: translate(-50%, -50%) scale(1.2); box-shadow: 0 0 0 5px rgba(255, 255, 255, 0); }
    100% { transform: translate(-50%, -50%) scale(1); box-shadow: 0 0 0 0 rgba(255, 255, 255, 0); }
  }

  @keyframes newFillFlash {
    0% { background: rgba(0, 230, 118, 0.22); transform: translateY(-3px); }
    100% { background: transparent; transform: translateY(0); }
  }

  @keyframes idleBlink {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.35; transform: scale(0.8); }
  }

  .hud-card {
    background: var(--bg-elevated);
    border: 1px solid var(--border-subtle);
    border-radius: 5px;
    padding: 4px 7px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 1.5px;
    min-width: 0;
    transition: transform 0.2s cubic-bezier(0.2, 0.8, 0.2, 1), border-color 0.2s ease, box-shadow 0.2s ease;
  }

  .hud-card:hover {
    transform: translateY(-1.5px);
    border-color: var(--border-medium);
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.45);
  }

  .hud-title {
    font-size: 8.5px;
    font-weight: 600;
    letter-spacing: 0.02em;
    color: var(--text-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .hud-value {
    font-size: 11.5px;
    font-weight: 700;
    color: var(--text-primary);
    line-height: 1.2;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .hud-sub {
    font-size: 8px;
    color: var(--text-secondary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .leaderboard-wrap {
    background: var(--bg-elevated);
    border: 1px solid var(--border-subtle);
    border-radius: 5px;
    padding: 4px 7px;
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-height: 0;
    flex-shrink: 0;
    transition: border-color 0.2s ease;
  }

  .leaderboard-wrap:hover {
    border-color: var(--border-medium);
  }

  .leaderboard-wrap table {
    font-size: 9.5px;
  }

  .leaderboard-wrap th {
    font-size: 8.5px;
    padding: 3px 5px;
    letter-spacing: 0.02em;
    font-weight: 600;
    color: var(--text-muted);
  }

  .leaderboard-wrap td {
    padding: 2.5px 5px;
    font-size: 9.5px;
    line-height: 1.25;
    transition: background 0.15s ease;
  }

  .leaderboard-wrap tr:hover td {
    background: rgba(255, 255, 255, 0.045);
  }

  .sub-section-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1px 2px 3px 2px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  }

  /* Streamlined & Breathing 6 Strategy Cards (1-Column Vertical Stack) */
  .strategies-grid-compact {
    display: grid;
    grid-template-columns: 1fr;
    gap: 3.5px;
    flex-shrink: 0;
    position: relative;
  }

  .strat-card-mini {
    background: var(--bg-elevated);
    border: 1px solid var(--border-subtle);
    border-left: 3px solid var(--strat-color, var(--text-muted));
    border-radius: 5px;
    padding: 3.5px 7px;
    display: flex;
    flex-direction: column;
    gap: 2.5px;
    min-width: 0;
    will-change: transform;
    transition: transform 0.45s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.25s ease, border-color 0.2s ease;
  }

  .strat-card-mini:hover {
    transform: translateY(-1.5px);
    border-color: var(--border-medium);
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.5), 0 0 10px rgba(255, 255, 255, 0.04);
  }

  .strat-card-mini.rank-up-anim {
    animation: rankUpPulse 0.65s cubic-bezier(0.16, 1, 0.3, 1);
  }

  .strat-card-mini.rank-down-anim {
    animation: rankDownPulse 0.65s cubic-bezier(0.16, 1, 0.3, 1);
  }

  @keyframes rankUpPulse {
    0% {
      box-shadow: 0 0 16px rgba(0, 230, 118, 0.8), 0 0 24px rgba(0, 230, 118, 0.3);
      border-color: rgba(0, 230, 118, 0.7);
    }
    100% {
      box-shadow: none;
      border-color: var(--border-subtle);
    }
  }

  @keyframes rankDownPulse {
    0% {
      box-shadow: 0 0 16px rgba(255, 51, 75, 0.7), 0 0 24px rgba(255, 51, 75, 0.25);
      border-color: rgba(255, 51, 75, 0.6);
    }
    100% {
      box-shadow: none;
      border-color: var(--border-subtle);
    }
  }

  .strat-card-mini .strat-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 6px;
  }

  .strat-card-mini .strat-left {
    display: flex;
    align-items: center;
    gap: 6px;
    min-width: 0;
  }

  .strat-card-mini .strat-title {
    font-size: 11px;
    font-weight: 700;
    line-height: 1.2;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .strat-card-mini .strat-pill {
    font-size: 8px;
    color: var(--text-muted);
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.07);
    padding: 0 4px;
    border-radius: 3px;
    white-space: nowrap;
  }

  .strat-card-mini .strat-right {
    display: flex;
    align-items: center;
    gap: 5px;
    flex-shrink: 0;
  }

  .strat-card-mini .rank-badge {
    font-size: 9px;
    font-weight: 700;
    padding: 0.5px 5px;
    border-radius: 3px;
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.1);
  }

  .strat-card-mini .strat-kpis {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 6px;
    background: rgba(0, 0, 0, 0.22);
    border: 1px solid rgba(255, 255, 255, 0.045);
    border-radius: 4px;
    padding: 3.5px 6px;
  }

  .strat-card-mini .kpi-cell {
    display: flex;
    flex-direction: column;
    gap: 1px;
    min-width: 0;
  }

  .strat-card-mini .kpi-cell span:first-child {
    font-size: 8px;
    font-weight: 500;
    color: var(--text-muted);
    line-height: 1.1;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .strat-card-mini .kpi-cell span:last-child {
    font-size: 10.5px;
    font-weight: 700;
    line-height: 1.15;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .pos-badge {
    font-size: 8px;
    font-weight: 700;
    padding: 1px 5px;
    border-radius: 3px;
    letter-spacing: 0.03em;
    display: inline-block;
  }

  .pos-badge.in-pos {
    background: var(--up-dim);
    color: var(--up);
    border: 1px solid rgba(0, 230, 118, 0.35);
    box-shadow: 0 0 6px rgba(0, 230, 118, 0.2);
  }

  .pos-badge.flat {
    background: rgba(255, 255, 255, 0.05);
    color: var(--text-muted);
    border: 1px solid rgba(255, 255, 255, 0.08);
  }

  .strat-card-mini .bracket-bar-wrap {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 1px 0;
  }

  .strat-card-mini .bracket-track {
    height: 3px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.08);
    position: relative;
    overflow: visible;
  }

  .strat-card-mini .bracket-fill {
    height: 100%;
    border-radius: 999px;
    position: absolute;
    left: 0;
    top: 0;
    opacity: 0.70;
    transition: width 0.35s cubic-bezier(0.2, 0.8, 0.2, 1);
  }

  .strat-card-mini .bracket-marker {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #FFF;
    border: 2px solid;
    position: absolute;
    top: 50%;
    transform: translate(-50%, -50%);
    animation: markerPulse 2.2s infinite ease-in-out;
    transition: left 0.35s cubic-bezier(0.2, 0.8, 0.2, 1);
  }

  .strat-card-mini .bracket-labels {
    font-size: 8px;
    line-height: 1.1;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .strat-card-mini .strat-idle-bar {
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 8px;
    color: var(--text-secondary);
    padding: 1px 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .strat-card-mini .idle-dot {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: var(--text-muted);
    flex-shrink: 0;
    animation: idleBlink 2.5s infinite ease-in-out;
  }

  /* Table Action & Status Badges */
  .tag-live {
    color: var(--up);
    background: var(--up-dim);
    border: 1px solid rgba(0, 230, 118, 0.3);
    padding: 1px 4.5px;
    border-radius: 2px;
    font-size: 8px;
    font-weight: 700;
    margin-right: 4px;
    display: inline-block;
  }

  .tag-warmup {
    color: var(--text-muted);
    background: rgba(255, 255, 255, 0.04);
    padding: 1px 4px;
    border-radius: 2px;
    font-size: 8px;
    margin-right: 4px;
    display: inline-block;
  }

  .badge-buy {
    color: var(--up);
    background: var(--up-dim);
    border: 1px solid rgba(0, 230, 118, 0.3);
    padding: 1px 5px;
    border-radius: 3px;
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.03em;
    display: inline-block;
  }

  .badge-sell {
    color: var(--down);
    background: var(--down-dim);
    border: 1px solid rgba(255, 51, 75, 0.3);
    padding: 1px 5px;
    border-radius: 3px;
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.03em;
    display: inline-block;
  }

  .new-fill-row {
    animation: newFillFlash 1.2s cubic-bezier(0.2, 0.8, 0.2, 1);
  }

  .live-pulse-badge {
    color: var(--up);
    font-weight: 600;
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }

  .live-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--up);
    display: inline-block;
    box-shadow: 0 0 6px var(--up);
    animation: radarRipple 2.2s infinite ease-out;
  }

  .panel {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: 7px;
    display: flex;
    flex-direction: column;
    min-height: 0;
    min-width: 0;
    overflow: hidden;
    box-shadow: 0 6px 24px rgba(0, 0, 0, 0.55);
  }

  .panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    padding: 7px 11px;
    border-bottom: 1px solid var(--border-subtle);
    background: var(--bg-elevated);
    flex-shrink: 0;
  }

  .panel-title {
    font-size: 12px;
    font-weight: 700;
    color: var(--text-primary);
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .panel-tools {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 11px;
    color: var(--text-secondary);
  }

  .seg-control {
    display: inline-flex;
    background: var(--bg-input);
    border: 1px solid var(--border-subtle);
    border-radius: 4px;
    padding: 1px;
  }

  .seg-btn {
    background: transparent;
    border: none;
    color: var(--text-secondary);
    font-size: 10.5px;
    font-weight: 600;
    padding: 2px 7px;
    border-radius: 3px;
    cursor: pointer;
    transition: all 0.12s ease;
  }

  .seg-btn.active {
    background: var(--bg-elevated);
    color: var(--text-primary);
    border: 1px solid var(--border-medium);
  }

  .legend-item {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 10.5px;
    color: var(--text-secondary);
  }

  .legend-swatch {
    width: 8px;
    height: 3px;
    border-radius: 1px;
  }

  .canvas-wrap {
    position: relative;
    flex: 1;
    width: 100%;
    height: 100%;
    min-height: 110px;
    overflow: hidden;
  }

  canvas {
    display: block;
    width: 100%;
    height: 100%;
  }

  /* Floating Chart Inspect Tooltip */
  .chart-tooltip {
    position: absolute;
    display: none;
    pointer-events: none;
    background: rgba(14, 17, 24, 0.96);
    border: 1px solid var(--border-medium);
    border-radius: 5px;
    padding: 6px 9px;
    font-size: 10.5px;
    color: var(--text-primary);
    box-shadow: 0 8px 24px rgba(0,0,0,0.65);
    z-index: 10;
    line-height: 1.45;
  }

  /* 4 Strategy Cards Grid */
  .strategies-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    grid-auto-rows: 1fr;
    gap: 7px;
    padding: 7px;
    flex: 1;
    min-height: 0;
    overflow-y: auto;
  }

  @media (max-width: 680px) {
    .strategies-grid { grid-template-columns: 1fr; }
  }

  .strat-card {
    background: var(--bg-elevated);
    border: 1px solid var(--border-subtle);
    border-top-width: 2.5px;
    border-radius: 6px;
    padding: 8px 10px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    gap: 5px;
    min-width: 0;
    transition: border-color 0.15s ease;
  }

  .strat-top {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 6px;
  }

  .strat-name-wrap { min-width: 0; }

  .strat-title {
    font-size: 12.5px;
    font-weight: 700;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .strat-genome {
    font-size: 9.5px;
    color: var(--text-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .rank-badge {
    font-size: 10.5px;
    font-weight: 700;
    padding: 1px 6px;
    border-radius: 3px;
    background: rgba(255, 255, 255, 0.05);
    color: var(--text-primary);
    border: 1px solid var(--border-subtle);
    flex-shrink: 0;
  }

  .strat-kpis {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 5px;
    background: rgba(0, 0, 0, 0.4);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 4px;
    padding: 5px 7px;
  }

  .kpi-cell {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }

  .kpi-cell span:first-child {
    font-size: 9px;
    text-transform: uppercase;
    color: var(--text-muted);
    letter-spacing: 0.04em;
  }

  .kpi-cell span:last-child {
    font-size: 12px;
    font-weight: 700;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .pos-box {
    display: flex;
    flex-direction: column;
    gap: 3px;
  }

  .pos-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 10.5px;
  }

  .pos-tag {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-weight: 700;
    font-size: 10px;
    padding: 1px 5px;
    border-radius: 3px;
  }

  .pos-tag.in-pos {
    background: var(--up-dim);
    color: var(--up);
  }

  .pos-tag.flat {
    background: rgba(255, 255, 255, 0.08);
    color: var(--text-secondary);
  }

  .bracket-bar-wrap {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .bracket-track {
    position: relative;
    height: 5px;
    border-radius: 999px;
    background: linear-gradient(90deg, rgba(255,51,75,0.45) 0%, rgba(0,210,255,0.25) 45%, rgba(0,230,118,0.45) 100%);
    overflow: visible;
  }

  .bracket-marker {
    position: absolute;
    top: -3px;
    width: 11px;
    height: 11px;
    border-radius: 50%;
    background: #FFFFFF;
    border: 2px solid var(--up);
    box-shadow: 0 0 6px rgba(255,255,255,0.7);
    transform: translateX(-50%);
    transition: left 0.25s ease;
  }

  .bracket-labels {
    display: flex;
    justify-content: space-between;
    font-size: 9.5px;
    color: var(--text-secondary);
  }

  .strat-intent {
    font-size: 10px;
    color: var(--text-secondary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    padding-top: 2px;
    border-top: 1px dashed var(--border-subtle);
  }

  /* Table styling */
  .table-scroll {
    flex: 1;
    overflow: auto;
    min-height: 0;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 11px;
  }

  th {
    position: sticky;
    top: 0;
    background: var(--bg-elevated);
    color: var(--text-muted);
    font-size: 9.5px;
    font-weight: 600;
    letter-spacing: 0.02em;
    padding: 6px 8px;
    text-align: left;
    border-bottom: 1px solid var(--border-medium);
    z-index: 2;
  }

  td {
    padding: 5px 8px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    white-space: nowrap;
  }

  tr:hover td {
    background: rgba(255, 255, 255, 0.035);
  }

  .text-right { text-align: right; }

  /* Bottom Split */
  .bottom-right-split {
    display: grid;
    grid-template-rows: 1fr auto;
    min-height: 0;
    flex: 1;
  }

  .omni-footer {
    padding: 6px 10px;
    background: var(--bg-input);
    border-top: 1px solid var(--border-subtle);
    font-size: 10.5px;
    color: var(--text-secondary);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }

  .omni-text {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  /* Thin Scrollbars */
  ::-webkit-scrollbar { width: 5px; height: 5px; }
  ::-webkit-scrollbar-track { background: var(--bg-canvas); }
  ::-webkit-scrollbar-thumb { background: #252D3D; border-radius: 3px; }
  ::-webkit-scrollbar-thumb:hover { background: #3B4863; }

  /* Position Notification Toast Micro-Interactions (Motion Design System) */
  .chart-notification-container {
    position: absolute;
    top: 12px;
    left: 14px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    pointer-events: none;
    z-index: 50;
    max-width: 380px;
  }

  .chart-toast {
    pointer-events: auto;
    position: relative;
    display: flex;
    flex-direction: column;
    background: rgba(14, 17, 24, 0.95);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-left: 4px solid var(--toast-color, #FFB800);
    border-radius: 7px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.7), 0 0 16px rgba(0, 0, 0, 0.5);
    overflow: hidden;
    animation: toastSpringIn 0.38s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    transition: transform 0.2s ease, opacity 0.25s ease;
  }

  .chart-toast.toast-exit {
    animation: toastSlideOut 0.35s cubic-bezier(0.7, 0, 0.84, 0) forwards;
  }

  @keyframes toastSpringIn {
    0% {
      opacity: 0;
      transform: translate3d(-35px, 0, 0) scale(0.92);
      filter: blur(4px);
    }
    70% {
      opacity: 1;
      transform: translate3d(3px, 0, 0) scale(1.015);
      filter: blur(0px);
    }
    100% {
      opacity: 1;
      transform: translate3d(0, 0, 0) scale(1);
      filter: blur(0px);
    }
  }

  @keyframes toastSlideOut {
    0% {
      opacity: 1;
      transform: translate3d(0, 0, 0) scale(1);
      max-height: 120px;
      margin-bottom: 0px;
    }
    100% {
      opacity: 0;
      transform: translate3d(-25px, -8px, 0) scale(0.94);
      max-height: 0px;
      margin-bottom: -8px;
      padding-top: 0;
      padding-bottom: 0;
    }
  }

  .toast-body {
    padding: 8px 11px 9px 11px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .toast-top-row {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .toast-tag {
    display: inline-flex;
    align-items: center;
    gap: 4.5px;
    padding: 1.5px 6px;
    border-radius: 4px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.02em;
    border: 1px solid currentColor;
  }

  .toast-pulse-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    animation: toastDotPulse 1.2s infinite ease-in-out;
  }

  @keyframes toastDotPulse {
    0%, 100% { transform: scale(1); opacity: 1; }
    50% { transform: scale(1.5); opacity: 0.45; }
  }

  .toast-action-badge {
    font-size: 10px;
    font-weight: 700;
    color: #FFFFFF;
    background: rgba(255, 255, 255, 0.08);
    padding: 1px 5px;
    border-radius: 3px;
  }

  .toast-clock {
    margin-left: auto;
    font-size: 9.5px;
    color: var(--text-muted);
  }

  .toast-close {
    cursor: pointer;
    font-size: 13px;
    line-height: 1;
    color: var(--text-muted);
    margin-left: 6px;
    padding: 0 4px;
    border-radius: 3px;
    transition: color 0.15s, background 0.15s;
  }

  .toast-close:hover {
    color: #FFFFFF;
    background: rgba(255, 255, 255, 0.12);
  }

  .toast-main-row {
    display: flex;
    align-items: baseline;
    gap: 8px;
    font-size: 11.5px;
    color: #FFFFFF;
  }

  .toast-main-row strong {
    color: #FFFFFF;
  }

  .toast-bracket-row {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 10px;
    background: rgba(0, 0, 0, 0.25);
    padding: 3px 6px;
    border-radius: 4px;
    border: 1px solid rgba(255, 255, 255, 0.06);
  }

  .toast-bracket-item {
    display: inline-flex;
    align-items: center;
    gap: 3px;
  }

  .toast-bracket-item.up { color: var(--up); font-weight: 600; }
  .toast-bracket-item.down { color: var(--down); font-weight: 600; }
  .toast-bracket-item small { opacity: 0.85; font-size: 9px; }
  .toast-sep { color: var(--border-medium); }

  .toast-progress {
    height: 2px;
    width: 100%;
    background: var(--toast-color, #FFB800);
    animation: toastProgressShrink 4.2s linear forwards;
    opacity: 0.85;
  }

  @keyframes toastProgressShrink {
    from { width: 100%; }
    to { width: 0%; }
  }
</style>
</head>
<body>
  <div class="app-shell">
    <!-- Top Command & Live Quote Ribbon -->
    <header class="top-ribbon">
      <div class="brand-cluster">
        <div id="liveBadge" class="brand-badge">
          <span class="pulse-dot"></span>
          <span id="liveStatusText">Live Feed</span>
        </div>
        <div class="title-group">
          <h1>TradeBot0 <span style="font-size:10.5px;font-weight:600;color:var(--accent);background:var(--accent-dim);padding:2px 7px;border-radius:4px;border:1px solid var(--accent-border);letter-spacing:0.02em;">ETH/USD Quant Arena</span></h1>
          <span class="title-sub" id="sourceSubtitle">Connecting | Baseline Capital: $500,000.00 / Strategy ($3,000,000 Total)</span>
        </div>
      </div>

      <div class="ticker-strip">
        <div class="stat-block">
          <span class="stat-lbl">ETH Spot Price</span>
          <span class="stat-val spot-hero num" id="spotPrice">$0.00</span>
        </div>
        <div class="stat-block">
          <span class="stat-lbl">24h Change</span>
          <span class="stat-val num" id="change24h">+0.00%</span>
        </div>
        <div class="stat-block">
          <span class="stat-lbl">Bid / Ask</span>
          <span class="stat-val num" id="bidAskSpread">$0.00 / $0.00</span>
        </div>
        <div class="stat-block">
          <span class="stat-lbl">24h High / Low</span>
          <span class="stat-val num" id="highLow24h">$0.00 / $0.00</span>
        </div>
        
        <!-- Evolution Countdown & Interval Switcher Widget -->
        <div class="auto-evolve-pill num">
          <span><strong id="genLabel">Gen #1</strong></span>
          <span style="color:var(--border-medium)">|</span>
          <span style="color:var(--text-muted)">Cycle:</span>
          <select class="interval-select" id="evolveIntervalSelect" onchange="changeEvolveInterval(this.value)" title="Change auto evolution cycle">
            <option value="3600">1h</option>
            <option value="7200">2h</option>
            <option value="14400">4h</option>
            <option value="21600" selected>6h (Default)</option>
            <option value="43200">12h</option>
            <option value="86400">24h</option>
          </select>
          <span style="color:var(--border-medium)">|</span>
          <span style="color:var(--text-muted)">Next:</span>
          <strong id="countdownLabel" style="color:var(--accent);">06:00:00</strong>
          <button class="auto-evolve-btn" onclick="toggleAutoEvolve()" id="autoEvolveToggleBtn" title="Click to toggle auto evolution">
            [Active]
          </button>
        </div>
      </div>

      <div class="action-cluster">
        <button class="btn btn-primary" onclick="triggerEvolution()" title="Trigger tournament selection and crossover mutation now">
          Evolve Gen
        </button>
        <button class="btn" id="pauseBtn" onclick="togglePause()">
          Pause Feed
        </button>
        <button class="btn" onclick="resetArena()" title="Reset all competitor portfolios to $500,000.00 cash">
          Reset Arena
        </button>
        <button class="btn" onclick="toggleFullscreen()" title="Toggle Fullscreen Mode (F11)">
          Fullscreen [F11]
        </button>
      </div>
    </header>

    <!-- Main Fluid Workspace -->
    <main class="workspace-grid">
      <!-- Left Column: Full-Height Rich ETH/USD Tactical Candlestick Chart -->
      <section class="left-column">
        <div class="panel">
          <div class="panel-header">
            <div class="panel-title">
              <span class="serif">ETH/USD Tactical Depth (1m Candles · High Precision)</span>
            </div>
            <div class="panel-tools">
              <div class="seg-control">
                <button class="seg-btn active" id="btnScaleAuto" onclick="setScaleMode('auto')" title="Focus on visible candle action">Focus Candles</button>
                <button class="seg-btn" id="btnScaleFull" onclick="setScaleMode('full')" title="Include distant bracket orders">Full Range</button>
              </div>
              <div class="seg-control">
                <button class="seg-btn active" id="btnModeCandles" onclick="setChartMode('candles')">1m Candles</button>
                <button class="seg-btn" id="btnModeLine" onclick="setChartMode('line')">Trend Line</button>
              </div>
              <span class="legend-item"><i class="legend-swatch" style="background:var(--c-cons)"></i>EMA(9)</span>
              <span class="legend-item"><i class="legend-swatch" style="background:var(--c-atr)"></i>EMA(21)</span>
              <span class="legend-item"><i class="legend-swatch" style="background:var(--c-vwap)"></i>VWAP</span>
              <span class="legend-item" title="Aggressive Momentum"><i class="legend-swatch" style="background:var(--c-agg)"></i>AGG</span>
              <span class="legend-item" title="Conservative Scalper"><i class="legend-swatch" style="background:var(--c-cons)"></i>CONS</span>
              <span class="legend-item" title="ATR Dynamic Adaptive"><i class="legend-swatch" style="background:var(--c-atr)"></i>ATR</span>
              <span class="legend-item" title="Trailing Ratchet Guard"><i class="legend-swatch" style="background:var(--c-trail)"></i>TRAIL</span>
              <span class="legend-item" title="Opening Range Breakout (15m)"><i class="legend-swatch" style="background:var(--c-orb)"></i>ORB</span>
              <span class="legend-item" title="Institutional VWAP Pullback"><i class="legend-swatch" style="background:var(--c-vwap)"></i>VWAP</span>
            </div>
          </div>
          <div class="canvas-wrap" id="priceCanvasWrap">
            <canvas id="priceCanvas"></canvas>
            <div id="chartNotificationContainer" class="chart-notification-container"></div>
            <div id="priceTooltip" class="chart-tooltip num"></div>
          </div>
        </div>
      </section>

      <!-- Right Column: Quant Arena Tactical Desk + Execution Tape -->
      <section class="right-column">
        <!-- Right Panel 1: Tactical HUD + Strategies Matrix + Full Leaderboard -->
        <div class="panel">
          <div class="panel-header">
            <div class="panel-title">
              <span>Quant Arena Tactical Hub</span>
            </div>
          </div>
          <div class="top-right-body">
            <!-- Tactical HUD: 4 Key Metric & Champion Cards -->
            <div class="tactical-hud">
              <div class="hud-card" style="border-top:2px solid var(--accent);">
                <div class="hud-title" id="hudChampTitle">6H Arena Champion</div>
                <div class="hud-value" id="hudChampName" style="color:var(--accent);">Evaluating...</div>
                <div class="hud-sub" id="hudChampStats">ROI +0.00% | Next --:--</div>
              </div>
              <div class="hud-card" style="border-top:2px solid var(--c-agg);">
                <div class="hud-title">Momentum / Volatility</div>
                <div class="hud-value num" id="hudRsiVal">RSI 50.0</div>
                <div class="hud-sub num" id="hudAtrVal">ATR $0.00 (0.00%)</div>
              </div>
              <div class="hud-card" style="border-top:2px solid var(--c-cons);">
                <div class="hud-title">Gross Exposure</div>
                <div class="hud-value num" id="hudExposureQty">0.0000 ETH</div>
                <div class="hud-sub num" id="hudExposureVal">$0.00 | Cash 100%</div>
              </div>
              <div class="hud-card" style="border-top:2px solid var(--c-atr);">
                <div class="hud-title">Genetic Engine</div>
                <div class="hud-value num" id="hudGenVal" style="color:var(--c-atr);">Gen #1</div>
                <div class="hud-sub num" id="hudGenSub">Style B Evolution</div>
              </div>
            </div>

            <!-- View A: 4 Strategy Cards -->
            <div id="tabCardsView" class="strategies-grid-compact"></div>

            <!-- View B: Quantitative Leaderboard Table -->
            <div id="tabLeaderboardWrap" class="leaderboard-wrap">
              <div class="sub-section-header">
                <span style="font-weight:700;color:var(--text-primary);font-size:11px;">Strategy Performance Leaderboard</span>
                <span class="num" style="font-size:9.5px;color:var(--text-muted);">Baseline Capital: $500,000 / Strategy ($3,000,000 Total)</span>
              </div>
              <div class="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Rank</th>
                      <th>Strategy</th>
                      <th class="text-right">Total Equity</th>
                      <th class="text-right">ROI</th>
                      <th class="text-right">Unrealized PnL</th>
                      <th class="text-right">Max Drawdown</th>
                      <th class="text-right">Win Rate</th>
                      <th class="text-right">Sharpe</th>
                      <th class="text-right">Fitness</th>
                    </tr>
                  </thead>
                  <tbody id="leaderboardBody"></tbody>
                </table>
              </div>
            </div>
          </div>
        </div>

        <!-- Live Execution Tape & OmniRoute Bar -->
        <div class="panel">
          <div class="panel-header">
            <div class="panel-title">
              <span>Real-Time Execution & Order Tape</span>
            </div>
            <div class="panel-tools">
              <span id="fillCountLabel">0 Records</span>
            </div>
          </div>
          <div class="bottom-right-split">
            <div class="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th style="width:36px;">#</th>
                    <th>Time</th>
                    <th>Strategy</th>
                    <th>Action</th>
                    <th class="text-right">Qty (ETH)</th>
                    <th class="text-right">Fill Price</th>
                    <th class="text-right">Realized PnL</th>
                    <th>Trigger Reason</th>
                  </tr>
                </thead>
                <tbody id="fillsBody"></tbody>
              </table>
            </div>
            <div class="omni-footer">
              <div style="display:inline-flex;align-items:center;gap:6px;flex-shrink:0;">
                <span style="color:var(--accent);font-weight:700;">[OmniRoute]</span>
                <span id="omniSourceBadge" class="brand-badge" onclick="showOmniInfo()" style="font-size:10px;padding:2px 7px;cursor:pointer;" title="Click to view OmniRoute diagnostic telemetry">
                  Source: Local Engine (0 Token Offline)
                </span>
                <span id="omniQuotaBadge" class="brand-badge" style="font-size:10px;padding:2px 7px;background:rgba(0,230,118,0.12);color:var(--up);border-color:rgba(0,230,118,0.3);">
                  Quota: 100%
                </span>
              </div>
              <span class="omni-text" id="omniSummary" style="margin-left:8px;">Synchronizing live orderflow...</span>
            </div>
          </div>
        </div>
      </section>
    </main>
  </div>

<script>
  let latestState = null;
  let isPolling = false;
  let chartMode = 'candles'; // 'candles' or 'line'
  let scaleMode = 'auto';    // 'auto' (focus on visible candles) or 'full' (include all distant orders)

  // Color & Motion Helpers
  function hexToRgba(hex, alpha) {
    if (!hex || hex[0] !== '#') return `rgba(255, 184, 0, ${alpha})`;
    let c = hex.substring(1);
    if (c.length === 3) c = c.split('').map(x => x + x).join('');
    const num = parseInt(c, 16);
    const r = (num >> 16) & 255;
    const g = (num >> 8) & 255;
    const b = num & 255;
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  }

  // Active Motion Beacons & Animation Loop
  let chartBeacons = [];
  let animFrameId = null;

  function addChartBeacon(s) {
    if (!s || !s.entry_price) return;
    const tagMap = {
      'comp_agg': 'AGG',
      'comp_cons': 'CONS',
      'comp_atr': 'ATR',
      'comp_trail': 'TRAIL'
    };
    chartBeacons.push({
      id: s.id,
      stratTag: tagMap[s.id] || (s.name ? s.name.slice(0, 4) : 'STRAT'),
      color: s.color || '#FFB800',
      price: Number(s.entry_price),
      startTime: Date.now(),
      duration: 3800
    });
    if (chartBeacons.length > 5) chartBeacons.shift();
    triggerAnimLoop();
  }

  function triggerAnimLoop() {
    if (typeof startChartAnimLoop === 'function') {
      startChartAnimLoop();
    }
  }

  // Notification Toast Micro-Interactions (Motion Design System)
  function showPositionToast(strat) {
    const container = document.getElementById('chartNotificationContainer');
    if (!container || !strat) return;

    const tagMap = {
      'comp_agg': 'Aggressive Momentum',
      'comp_cons': 'Conservative Scalper',
      'comp_atr': 'ATR Dynamic',
      'comp_trail': 'Trailing Guard'
    };
    const stratName = tagMap[strat.id] || strat.name || 'Quant Strategy';
    const sColor = strat.color || '#FFB800';
    const entryP = Number(strat.entry_price || 0);
    const tpP = Number(strat.take_profit || 0);
    const slP = Number(strat.stop_loss || 0);
    const qty = Number(strat.qty || 0);

    const tpPct = (entryP > 0 && tpP > 0) ? (((tpP - entryP) / entryP) * 100).toFixed(2) : null;
    const slPct = (entryP > 0 && slP > 0) ? (((entryP - slP) / entryP) * 100).toFixed(2) : null;

    const toast = document.createElement('div');
    toast.className = 'chart-toast';
    toast.style.setProperty('--toast-color', sColor);

    const timeStr = new Date().toTimeString().split(' ')[0];

    toast.innerHTML = `
      <div class="toast-body">
        <div class="toast-top-row">
          <span class="toast-tag" style="color:${sColor};border-color:${sColor};background:${hexToRgba(sColor, 0.14)};">
            <span class="toast-pulse-dot" style="background:${sColor};box-shadow:0 0 6px ${sColor};"></span>
            ${stratName}
          </span>
          <span class="toast-action-badge">Order Placed</span>
          <span class="toast-clock num">${timeStr}</span>
          <span class="toast-close" onclick="this.closest('.chart-toast').remove()" title="Close notification">×</span>
        </div>
        <div class="toast-main-row num">
          <span class="toast-qty">BUY <strong>${qty.toFixed(4)}</strong> ETH</span>
          <span style="color:var(--text-muted);margin:0 2px;">|</span>
          <span class="toast-entry">Entry <strong>$${entryP.toFixed(2)}</strong></span>
        </div>
        <div class="toast-bracket-row num">
          <span class="toast-bracket-item up">
            TP $${tpP > 0 ? tpP.toFixed(1) : '--'} ${tpPct ? `<small>(+${tpPct}%)</small>` : ''}
          </span>
          <span class="toast-sep">|</span>
          <span class="toast-bracket-item down">
            SL $${slP > 0 ? slP.toFixed(1) : '--'} ${slPct ? `<small>(-${slPct}%)</small>` : ''}
          </span>
        </div>
      </div>
      <div class="toast-progress"></div>
    `;

    while (container.children.length >= 3) {
      container.removeChild(container.firstChild);
    }

    container.appendChild(toast);

    setTimeout(() => {
      toast.classList.add('toast-exit');
      setTimeout(() => {
        if (toast.parentNode) {
          toast.parentNode.removeChild(toast);
        }
      }, 360);
    }, 4200);
  }

  function previewPositionAnimation() {
    if (!latestState) return;
    const strategies = latestState.strategies || [];
    if (strategies.length === 0) return;
    const inPosStrat = strategies.find(s => s.in_position);
    const chosen = inPosStrat || strategies[Math.floor(Math.random() * strategies.length)];
    const spot = Number((latestState.quote && latestState.quote.price) || 2249.5);
    const mock = {
      ...chosen,
      entry_price: spot,
      take_profit: Number((spot + (chosen.id === 'comp_cons' ? 4.5 : 8.0)).toFixed(2)),
      stop_loss: Number((spot - (chosen.id === 'comp_cons' ? 3.0 : 5.5)).toFixed(2)),
      qty: chosen.qty > 0 ? chosen.qty : 0.6655,
      in_position: true
    };
    showPositionToast(mock);
    addChartBeacon(mock);
  }

  let knownStrategyPositions = {};
  let hasInitializedPositions = false;

  function setChartMode(mode) {
    chartMode = mode;
    document.getElementById('btnModeCandles').className = 'seg-btn ' + (mode === 'candles' ? 'active' : '');
    document.getElementById('btnModeLine').className = 'seg-btn ' + (mode === 'line' ? 'active' : '');
    if (latestState) drawPriceChart(latestState);
  }

  function setScaleMode(mode) {
    scaleMode = mode;
    document.getElementById('btnScaleAuto').className = 'seg-btn ' + (mode === 'auto' ? 'active' : '');
    document.getElementById('btnScaleFull').className = 'seg-btn ' + (mode === 'full' ? 'active' : '');
    if (latestState) drawPriceChart(latestState);
  }

  const fmtUsd = (val, digits = 2) => {
    const n = Number(val || 0);
    return '$' + n.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits });
  };

  const fmtSignedUsd = (val) => {
    const n = Number(val || 0);
    const sign = n >= 0 ? '+' : '-';
    return sign + '$' + Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  };

  const fmtPct = (val) => {
    const n = Number(val || 0);
    return (n >= 0 ? '+' : '') + n.toFixed(2) + '%';
  };

  const fmtTimeSec = (totalSec) => {
    const s = Math.max(0, Math.floor(totalSec));
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = s % 60;
    if (h > 0) {
      return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
    }
    return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
  };

  async function pollBackend() {
    if (isPolling) return;
    isPolling = true;
    try {
      if (window.pywebview && window.pywebview.api) {
        const state = await window.pywebview.api.get_state();
        if (state) {
          latestState = state;

          // Position change detector
          const currentStrats = state.strategies || [];
          if (!hasInitializedPositions) {
            currentStrats.forEach(s => {
              knownStrategyPositions[s.id] = {
                in_position: Boolean(s.in_position),
                entry_price: Number(s.entry_price || 0),
                qty: Number(s.qty || 0),
                trades: Number(s.closed_trades || 0)
              };
            });
            hasInitializedPositions = true;
          } else {
            currentStrats.forEach(s => {
              const prev = knownStrategyPositions[s.id];
              const isNowInPos = Boolean(s.in_position);
              const wasInPos = prev ? Boolean(prev.in_position) : false;
              const curEntry = Number(s.entry_price || 0);
              const prevEntry = prev ? Number(prev.entry_price || 0) : 0;

              const isNewEntry = (isNowInPos && !wasInPos) ||
                (isNowInPos && wasInPos && curEntry > 0 && prevEntry > 0 && Math.abs(curEntry - prevEntry) > 0.05);

              if (isNewEntry) {
                showPositionToast(s);
                addChartBeacon(s);
              }

              knownStrategyPositions[s.id] = {
                in_position: isNowInPos,
                entry_price: curEntry,
                qty: Number(s.qty || 0),
                trades: Number(s.closed_trades || 0)
              };
            });
          }

          renderAll(state);
        }
      }
    } catch (err) {
      console.error("Bridge poll error:", err);
    } finally {
      isPolling = false;
    }
  }

  async function triggerEvolution() {
    if (!window.pywebview || !window.pywebview.api) return;
    const state = await window.pywebview.api.evolve_now();
    if (state) { latestState = state; renderAll(state); }
  }

  async function togglePause() {
    if (!window.pywebview || !window.pywebview.api) return;
    const state = await window.pywebview.api.toggle_pause();
    if (state) { latestState = state; renderAll(state); }
  }

  async function toggleAutoEvolve() {
    if (!window.pywebview || !window.pywebview.api) return;
    const state = await window.pywebview.api.toggle_auto_evolve();
    if (state) { latestState = state; renderAll(state); }
  }

  async function changeEvolveInterval(seconds) {
    if (!window.pywebview || !window.pywebview.api) return;
    const sec = parseInt(seconds, 10);
    if (isNaN(sec) || sec <= 0) return;
    const state = await window.pywebview.api.set_evolve_interval(sec);
    if (state) { latestState = state; renderAll(state); }
  }

  async function resetArena() {
    if (!window.pywebview || !window.pywebview.api) return;
    knownStrategyPositions = {};
    hasInitializedPositions = false;
    chartBeacons = [];
    const state = await window.pywebview.api.reset_arena();
    if (state) { latestState = state; renderAll(state); }
  }

  let rightTab = 'all'; // 'all', 'leaderboard', 'cards'

  function setRightTab(tab) {
    rightTab = tab;
    const btnA = document.getElementById('btnTabAll');
    const btnL = document.getElementById('btnTabLeaderboard');
    const btnC = document.getElementById('btnTabCards');
    const vL = document.getElementById('tabLeaderboardWrap');
    const vC = document.getElementById('tabCardsView');
    if (btnA) btnA.className = 'seg-btn ' + (tab === 'all' ? 'active' : '');
    if (btnL) btnL.className = 'seg-btn ' + (tab === 'leaderboard' ? 'active' : '');
    if (btnC) btnC.className = 'seg-btn ' + (tab === 'cards' ? 'active' : '');
    if (vC) vC.style.display = (tab === 'all' || tab === 'cards') ? 'grid' : 'none';
    if (vL) vL.style.display = (tab === 'all' || tab === 'leaderboard') ? 'block' : 'none';
  }

  function showTVConfigInfo() {
    alert(
      `[TradingView Paper Trading Integration Architecture]\n\n` +
      `Q: Why is direct one-click execution to web Paper Trading unsupported?\n` +
      `1. Closed Web Sandbox: Native Paper Trading on tradingview.com does not expose public REST order endpoints or client SDKs.\n` +
      `2. Webhook Directionality: Native Webhooks emit alerts outbound from TradingView, but do not accept arbitrary inbound order execution.\n\n` +
      `Production Automated Trading Solutions:\n` +
      `Option A (Industry Standard): Connect Binance Testnet or Alpaca Paper Trading via TradingView Broker Integration.\n` +
      `Option B (Webhook Dispatch): Use TradingView webhook alert receiver gateways.\n` +
      `Option C (Browser Automation): Playwright headless session agent.\n\n` +
      `Current TradeBot0 State:\n` +
      `The engine autonomously tracks the hourly champion strategy with real-time brackets ready for upstream dispatch.`
    );
  }

  function renderAll(state) {
    renderHeader(state);
    renderTacticalHud(state);
    renderStrategies(state);
    renderLeaderboard(state);
    renderFills(state);
    drawPriceChart(state);
  }

  let lastSpotPrice = 0;
  function renderHeader(state) {
    const q = state.quote || {};
    const spotEl = document.getElementById('spotPrice');
    const curP = Number(q.price || 0);
    spotEl.textContent = fmtUsd(curP, 2);

    if (lastSpotPrice > 0 && curP !== lastSpotPrice) {
      spotEl.classList.remove('tick-up', 'tick-down');
      void spotEl.offsetWidth;
      if (curP > lastSpotPrice) {
        spotEl.classList.add('tick-up');
      } else {
        spotEl.classList.add('tick-down');
      }
    }
    lastSpotPrice = curP;

    const chg = Number(q.change_24h_pct || 0);
    const chgEl = document.getElementById('change24h');
    chgEl.textContent = fmtPct(chg);
    chgEl.className = 'stat-val num ' + (chg >= 0 ? 'up' : 'down');
    spotEl.className = 'stat-val spot-hero num ' + (chg >= 0 ? 'up' : 'down');

    document.getElementById('bidAskSpread').textContent = `${fmtUsd(q.bid, 2)} / ${fmtUsd(q.ask, 2)}`;
    document.getElementById('highLow24h').textContent = `${fmtUsd(q.high_24h, 0)} / ${fmtUsd(q.low_24h, 0)}`;
    document.getElementById('genLabel').textContent = `Gen #${state.generation}`;

    // Auto Evolve Countdown & Interval Sync
    const cdEl = document.getElementById('countdownLabel');
    const autoBtn = document.getElementById('autoEvolveToggleBtn');
    const intSelect = document.getElementById('evolveIntervalSelect');
    if (intSelect && state.auto_evolve_interval_sec) {
      const curVal = String(state.auto_evolve_interval_sec);
      if (intSelect.value !== curVal) {
        intSelect.value = curVal;
      }
    }

    if (state.auto_evolve_enabled) {
      cdEl.textContent = fmtTimeSec(state.next_evolve_sec || 0);
      cdEl.style.color = 'var(--terracotta)';
      autoBtn.textContent = '[Active]';
      autoBtn.style.color = 'var(--terracotta)';
    } else {
      cdEl.textContent = 'PAUSED';
      cdEl.style.color = 'var(--text-muted)';
      autoBtn.textContent = '[Click to Enable]';
      autoBtn.style.color = 'var(--text-secondary)';
    }

    document.getElementById('sourceSubtitle').textContent =
      `Feed: ${q.source || 'Live'} (${q.timestamp || ''}) | Baseline: $500,000.00 USDT / Strategy ($3,000,000 Total)`;

    const badge = document.getElementById('liveBadge');
    const statusText = document.getElementById('liveStatusText');
    const pauseBtn = document.getElementById('pauseBtn');
    if (state.paused) {
      badge.style.background = 'rgba(217, 101, 101, 0.15)';
      badge.style.color = 'var(--down)';
      badge.style.borderColor = 'rgba(217, 101, 101, 0.35)';
      statusText.textContent = 'PAUSED';
      pauseBtn.textContent = 'Resume Feed';
    } else {
      badge.style.background = 'var(--terracotta-dim)';
      badge.style.color = 'var(--terracotta)';
      badge.style.borderColor = 'var(--terracotta-border)';
      statusText.textContent = 'LIVE 24/7';
      pauseBtn.textContent = 'Pause Feed';
    }

    document.getElementById('omniSummary').textContent = state.omni_summary || '';

    if (state.omni_meta) {
      const om = state.omni_meta;
      const srcEl = document.getElementById('omniSourceBadge');
      if (srcEl) {
        srcEl.textContent = `Source: ${om.source}`;
        if (om.is_online) {
          srcEl.style.background = 'var(--up-dim)';
          srcEl.style.color = 'var(--up)';
          srcEl.style.borderColor = 'rgba(106,168,122,0.35)';
        } else {
          srcEl.style.background = 'var(--terracotta-dim)';
          srcEl.style.color = 'var(--terracotta)';
          srcEl.style.borderColor = 'var(--terracotta-border)';
        }
      }
      const qEl = document.getElementById('omniQuotaBadge');
      if (qEl) {
        qEl.textContent = `Quota: ${om.quota_pct}%`;
      }
    }
  }

  function showOmniInfo() {
    if (!latestState || !latestState.omni_meta) return;
    const om = latestState.omni_meta;
    alert(
      `[OmniRoute Intelligent Routing & Diagnostics]\n\n` +
      `* Status: ${om.is_online ? 'Online (Self-Hosted Microservice)' : 'Offline'}\n` +
      `* Endpoint: ${om.endpoint}\n` +
      `* Active Model: ${om.active_model}\n` +
      `* Authentication: Zero-Config Keyless\n` +
      `* Token Compression: RTK / Caveman Enabled\n` +
      `* Tokens Saved: ${om.tokens_saved} Tokens\n` +
      `* Daily Quota Remaining: ${om.quota_pct}%\n\n` +
      `Automation Details:\n` +
      `TradeBot0 features a fully automated OmniRoute gateway.\n` +
      `Microservices spawn automatically in the background with zero setup, zero keys, providing prompt compression and quantitative analytics.`
    );
  }

  const stratCardDomMap = new Map();
  const prevRankRecord = new Map();

  function renderStrategies(state) {
    const grid = document.getElementById('tabCardsView') || document.getElementById('strategiesGrid');
    if (!grid) return;
    const strategies = (state.strategies || []).slice().sort((a, b) => a.rank - b.rank);
    const spot = Number((state.quote && state.quote.price) || 0);

    // 1. Measure initial visual bounding box tops for FLIP animation
    const firstTops = new Map();
    strategies.forEach(s => {
      const el = stratCardDomMap.get(s.id);
      if (el) {
        firstTops.set(s.id, el.getBoundingClientRect().top);
      }
    });

    // 2. Build / Update each card DOM element
    strategies.forEach(s => {
      const roiClass = s.roi_pct >= 0 ? 'up' : 'down';
      const upnlClass = s.unrealized_pnl >= 0 ? 'up' : 'down';
      const isBlocked = s.intent && s.intent.indexOf('EV Gate Blocked') !== -1;

      let bracketHtml = '';
      if (s.in_position) {
        let pct = 50;
        if (s.stop_loss && s.take_profit && s.take_profit > s.stop_loss) {
          pct = Math.max(3, Math.min(97, ((spot - s.stop_loss) / (s.take_profit - s.stop_loss)) * 100));
        }
        const slText = s.stop_loss ? `SL ${fmtUsd(s.stop_loss, 1)}` : 'Dynamic SL';
        const tpText = s.take_profit ? `TP ${fmtUsd(s.take_profit, 1)}` : 'Uncapped';
        const evText = s.expected_r !== undefined ? `MC EV ${s.expected_r >= 0 ? '+' : ''}${s.expected_r.toFixed(2)}R · Odds ${(s.target_prob * 100).toFixed(0)}%` : 'R-Sized';
        bracketHtml = `
          <div class="bracket-bar-wrap">
            <div class="bracket-track">
              <div class="bracket-fill" style="width:${pct.toFixed(1)}%;background:${s.color}"></div>
              <div class="bracket-marker" style="left:${pct.toFixed(1)}%;border-color:${s.color}"></div>
            </div>
            <div class="bracket-labels num">
              <span class="down">${slText}</span>
              <span style="color:var(--text-secondary)">Entry ${fmtUsd(s.entry_price, 1)} <span style="color:var(--accent);font-size:9.5px;margin-left:4px;">(${evText})</span></span>
              <span class="up">${tpText}</span>
            </div>
          </div>
        `;
      } else if (isBlocked) {
        bracketHtml = `
          <div class="strat-idle-bar" style="border-color:rgba(239,68,68,0.25);background:rgba(239,68,68,0.05);">
            <span class="idle-dot" style="background:#EF4444;box-shadow:0 0 6px #EF4444;"></span>
            <span style="color:#FCA5A5;font-weight:600;">TimeMachine EV Gate · Blocked (${s.mc_verdict || 'Low EV'})</span>
          </div>
        `;
      } else {
        bracketHtml = `
          <div class="strat-idle-bar">
            <span class="idle-dot"></span>
            <span>Standby · TimeMachine EV Gate Active & R-Sizing</span>
          </div>
        `;
      }

      const posPill = s.in_position
        ? `<span class="pos-badge in-pos">Long ${s.qty.toFixed(4)} ETH</span>`
        : `<span class="pos-badge flat">Idle</span>`;

      const pnlLabel = s.in_position ? 'Unrealized PnL' : 'Cash Balance';
      const pnlValue = s.in_position
        ? `<span class="${upnlClass}">${fmtSignedUsd(s.unrealized_pnl)}</span>`
        : `<span>${fmtUsd(s.cash, 0)}</span>`;

      const cardInner = `
        <div class="strat-top">
          <div class="strat-left">
            <span class="rank-badge num" style="color:${s.color}">#${s.rank}</span>
            <span class="strat-title" style="color:${s.color}">${s.name}</span>
            <span class="strat-pill num">Gen #${s.generation} · ${s.genome}</span>
          </div>
          <div class="strat-right num">
            ${posPill}
          </div>
        </div>

        <div class="strat-kpis num">
          <div class="kpi-cell">
            <span>Total Equity</span>
            <span>${fmtUsd(s.equity, 2)}</span>
          </div>
          <div class="kpi-cell">
            <span>ROI</span>
            <span class="${roiClass}">${fmtPct(s.roi_pct)}</span>
          </div>
          <div class="kpi-cell">
            <span>${pnlLabel}</span>
            ${pnlValue}
          </div>
          <div class="kpi-cell">
            <span>Win / Max DD</span>
            <span style="color:var(--text-secondary)">${s.win_rate_pct.toFixed(0)}% / ${s.max_dd_pct.toFixed(1)}%</span>
          </div>
        </div>

        ${bracketHtml}
      `;

      let card = stratCardDomMap.get(s.id);
      if (!card) {
        card = document.createElement('div');
        card.className = 'strat-card-mini';
        card.dataset.stratId = s.id;
        stratCardDomMap.set(s.id, card);
      }
      card.style.setProperty('--strat-color', s.color);
      card.innerHTML = cardInner;
      grid.appendChild(card);
    });

    // 3. FLIP: Invert & Play physical block shifting animation
    let hasRankShift = false;
    strategies.forEach(s => {
      const prevTop = firstTops.get(s.id);
      const card = stratCardDomMap.get(s.id);
      if (prevTop !== undefined && card) {
        const newTop = card.getBoundingClientRect().top;
        const dy = prevTop - newTop;
        if (Math.abs(dy) > 1) {
          hasRankShift = true;
          card.style.transform = `translateY(${dy}px)`;
          card.style.transition = 'none';
        }
      }
    });

    if (hasRankShift) {
      void grid.offsetHeight;

      requestAnimationFrame(() => {
        strategies.forEach(s => {
          const card = stratCardDomMap.get(s.id);
          if (!card) return;
          card.style.transition = 'transform 0.45s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.25s ease';
          card.style.transform = '';

          const oldRank = prevRankRecord.get(s.id);
          if (oldRank !== undefined && oldRank !== s.rank) {
            if (s.rank < oldRank) {
              card.classList.add('rank-up-anim');
              setTimeout(() => card.classList.remove('rank-up-anim'), 650);
            } else {
              card.classList.add('rank-down-anim');
              setTimeout(() => card.classList.remove('rank-down-anim'), 650);
            }
          }
          prevRankRecord.set(s.id, s.rank);
        });
      });
    } else {
      strategies.forEach(s => prevRankRecord.set(s.id, s.rank));
    }
  }

  function renderTacticalHud(state) {
    if (!state) return;
    const tv = state.tv_hub || {};
    const champ = tv.champion || (state.strategies && state.strategies[0]) || {};
    const spot = Number((state.quote && state.quote.price) || 0);

    // 1. Champion Spotlight
    const cTitleEl = document.getElementById('hudChampTitle');
    if (cTitleEl) {
      const hVal = Math.round((state.auto_evolve_interval_sec || 21600) / 3600);
      cTitleEl.textContent = `${hVal > 0 ? hVal + 'H ' : ''}Arena Champion`;
    }
    const cNameEl = document.getElementById('hudChampName');
    if (cNameEl) {
      cNameEl.textContent = champ.name ? champ.name.split(' ')[0] : 'Evaluating...';
      cNameEl.title = champ.name || '';
    }
    const cStatsEl = document.getElementById('hudChampStats');
    if (cStatsEl) {
      const rotStr = fmtTimeSec(tv.next_rotation_sec || 0);
      cStatsEl.textContent = `ROI ${fmtPct(champ.roi_pct || 0)} · Next ${rotStr}`;
    }

    // 2. Momentum & Volatility (RSI & ATR)
    const ind = state.indicators || {};
    const rsi = Number(ind.rsi !== undefined ? ind.rsi : 50.0);
    const atr = Number(ind.atr !== undefined ? ind.atr : 2.5);
    const rsiEl = document.getElementById('hudRsiVal');
    if (rsiEl) {
      const rsiMood = rsi >= 65 ? ' (Bullish)' : (rsi <= 35 ? ' (Oversold)' : ' (Neutral)');
      rsiEl.textContent = `RSI ${rsi.toFixed(1)}${rsiMood}`;
      rsiEl.className = 'hud-value num ' + (rsi >= 55 ? 'up' : (rsi <= 45 ? 'down' : ''));
    }
    const atrEl = document.getElementById('hudAtrVal');
    if (atrEl) {
      const atrPct = spot > 0 ? ((atr / spot) * 100).toFixed(2) : '0.00';
      atrEl.textContent = `ATR $${atr.toFixed(2)} (${atrPct}%)`;
    }

    // 3. Gross Exposure
    const strategies = state.strategies || [];
    let totQty = 0;
    let totCash = 0;
    strategies.forEach(s => {
      totQty += Number(s.qty || 0);
      totCash += Number(s.cash || 0);
    });
    const expVal = totQty * spot;
    const totCap = totCash + expVal;
    const cashPct = totCap > 0 ? ((totCash / totCap) * 100).toFixed(1) : '100.0';

    const expQtyEl = document.getElementById('hudExposureQty');
    if (expQtyEl) expQtyEl.textContent = `${totQty.toFixed(4)} ETH`;
    const expValEl = document.getElementById('hudExposureVal');
    if (expValEl) expValEl.textContent = `${fmtUsd(expVal, 2)} · Cash ${cashPct}%`;

    // 4. Genetic Engine
    const genEl = document.getElementById('hudGenVal');
    if (genEl) genEl.textContent = `Generation #${state.generation || 1}`;
    const genSubEl = document.getElementById('hudGenSub');
    if (genSubEl) {
      const hVal = Math.round((state.auto_evolve_interval_sec || 21600) / 3600);
      genSubEl.textContent = `EV Gate & R-Sizing (${hVal}H Cycle)`;
    }
  }

  const leaderRowDomMap = new Map();

  function renderLeaderboard(state) {
    const tbody = document.getElementById('leaderboardBody');
    if (!tbody) return;
    const strategies = (state.strategies || []).slice().sort((a, b) => a.rank - b.rank);

    const firstTops = new Map();
    strategies.forEach(s => {
      const el = leaderRowDomMap.get(s.id);
      if (el) firstTops.set(s.id, el.getBoundingClientRect().top);
    });

    strategies.forEach(s => {
      const roiCls = s.roi_pct >= 0 ? 'up' : 'down';
      const upnlCls = s.unrealized_pnl >= 0 ? 'up' : 'down';
      const rowInner = `
        <td style="font-weight:700;color:${s.color}">#${s.rank}</td>
        <td style="font-weight:600;color:${s.color}">${s.name}</td>
        <td class="text-right" style="font-weight:700">${fmtUsd(s.equity, 2)}</td>
        <td class="text-right ${roiCls}">${fmtPct(s.roi_pct)}</td>
        <td class="text-right ${upnlCls}">${fmtSignedUsd(s.unrealized_pnl)}</td>
        <td class="text-right down">${s.max_dd_pct.toFixed(2)}%</td>
        <td class="text-right">${s.win_rate_pct.toFixed(1)}% (${s.closed_trades})</td>
        <td class="text-right">${s.sharpe.toFixed(2)}</td>
        <td class="text-right" style="font-weight:700">${s.fitness >= 0 ? '+' : ''}${s.fitness.toFixed(2)}</td>
      `;

      let tr = leaderRowDomMap.get(s.id);
      if (!tr) {
        tr = document.createElement('tr');
        tr.className = 'num';
        tr.dataset.stratId = s.id;
        leaderRowDomMap.set(s.id, tr);
      }
      tr.innerHTML = rowInner;
      tbody.appendChild(tr);
    });

    let hasShift = false;
    strategies.forEach(s => {
      const prevTop = firstTops.get(s.id);
      const tr = leaderRowDomMap.get(s.id);
      if (prevTop !== undefined && tr) {
        const newTop = tr.getBoundingClientRect().top;
        const dy = prevTop - newTop;
        if (Math.abs(dy) > 1) {
          hasShift = true;
          tr.style.transform = `translateY(${dy}px)`;
          tr.style.transition = 'none';
        }
      }
    });

    if (hasShift) {
      void tbody.offsetHeight;
      requestAnimationFrame(() => {
        strategies.forEach(s => {
          const tr = leaderRowDomMap.get(s.id);
          if (!tr) return;
          tr.style.transition = 'transform 0.45s cubic-bezier(0.16, 1, 0.3, 1)';
          tr.style.transform = '';
        });
      });
    }
  }

  let lastTopFillSeq = 0;
  function renderFills(state) {
    const fills = state.fills || [];
    const liveCount = fills.filter(f => f.is_live).length;
    const warmupCount = fills.length - liveCount;
    const labelEl = document.getElementById('fillCountLabel');
    if (labelEl) {
      labelEl.innerHTML = `
        <span class="live-pulse-badge"><span class="live-dot"></span>Live Orderflow Active</span>
        <span style="margin-left:8px;color:var(--text-secondary);font-size:10px;">(${liveCount} Live / ${warmupCount} Warmup)</span>
      `;
    }
    const tbody = document.getElementById('fillsBody');
    const topSeq = fills.length > 0 ? fills[0].seq : 0;
    const isNewTop = (lastTopFillSeq > 0 && topSeq > lastTopFillSeq);
    lastTopFillSeq = topSeq;

    tbody.innerHTML = fills.map((f, idx) => {
      const isBuy = f.side === 'BUY';
      const pnlVal = f.pnl !== null && f.pnl !== undefined ? Number(f.pnl) : null;
      const pnlStr = pnlVal !== null ? fmtSignedUsd(pnlVal) : '—';
      const pnlCls = pnlVal === null ? '' : (pnlVal >= 0 ? 'up' : 'down');
      const tagHtml = f.is_live
        ? '<span class="tag-live">LIVE</span>'
        : '<span class="tag-warmup">WARMUP</span>';

      const actionBadge = isBuy
        ? '<span class="badge-buy">BUY</span>'
        : '<span class="badge-sell">SELL</span>';

      const seqStr = f.seq ? `#${f.seq}` : '';
      const priceSubHtml = (!isBuy && f.entry_price)
        ? `<div style="font-size:8.5px;color:var(--text-muted);font-weight:400;">Cost $${Number(f.entry_price).toFixed(2)}</div>`
        : '';

      const animCls = (idx === 0 && isNewTop) ? ' new-fill-row' : '';

      return `
        <tr class="num${animCls}">
          <td style="color:var(--text-muted);font-size:9.5px;">${seqStr}</td>
          <td style="color:var(--text-secondary)">${tagHtml}${f.time}</td>
          <td style="font-weight:600">${f.strategy}</td>
          <td>${actionBadge}</td>
          <td class="text-right">${Number(f.qty).toFixed(4)}</td>
          <td class="text-right">${fmtUsd(f.price, 2)}${priceSubHtml}</td>
          <td class="text-right ${pnlCls}" style="font-weight:700;">${pnlStr}</td>
          <td style="color:var(--text-secondary)">${f.reason}</td>
        </tr>
      `;
    }).join('');
  }

  /* HiDPI Vector Canvas Helpers */
  function setupHiDPICanvas(canvas) {
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.parentElement.getBoundingClientRect();
    const w = Math.max(200, Math.floor(rect.width));
    const h = Math.max(100, Math.floor(rect.height));
    if (canvas.width !== Math.floor(w * dpr) || canvas.height !== Math.floor(h * dpr)) {
      canvas.width = Math.floor(w * dpr);
      canvas.height = Math.floor(h * dpr);
    }
    const ctx = canvas.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return { ctx, w, h };
  }

  /* Catmull-Rom / Cardinal Cubic Bézier Smooth Spline Interpolator for Silky Trend Lines */
  function drawSmoothCurve(ctx, points, color, width, lineDash = []) {
    if (!points || points.length < 2) return;
    ctx.save();
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    if (lineDash.length > 0) ctx.setLineDash(lineDash);
    ctx.beginPath();
    ctx.moveTo(points[0].x, points[0].y);

    if (points.length === 2) {
      ctx.lineTo(points[1].x, points[1].y);
      ctx.stroke();
      ctx.restore();
      return;
    }

    const tension = 0.28; // Optimal curve smoothness without overshooting or kink
    for (let i = 0; i < points.length - 1; i++) {
      const p0 = i > 0 ? points[i - 1] : points[i];
      const p1 = points[i];
      const p2 = points[i + 1];
      const p3 = i < points.length - 2 ? points[i + 2] : p2;

      const cp1x = p1.x + (p2.x - p0.x) * tension;
      const cp1y = p1.y + (p2.y - p0.y) * tension;
      const cp2x = p2.x - (p3.x - p1.x) * tension;
      const cp2y = p2.y - (p3.y - p1.y) * tension;

      ctx.bezierCurveTo(cp1x, cp1y, cp2x, cp2y, p2.x, p2.y);
    }
    ctx.stroke();
    ctx.restore();
  }

  /* Detailed Chart 1: Dynamic Auto-Scaled Price / Candles + Indicators + Levels (60 FPS Morphing & Pure OLED High Contrast) */
  let priceHoverPos = null;
  let chartAnimRaf = null;

  // Real-time interpolated animation coordinates (Lerp State)
  let animSpot = 0, targetSpot = 0;
  let animMinP = 0, targetMinP = 0;
  let animMaxP = 0, targetMaxP = 0;
  let animCandles = []; // Array of { o, h, l, c, t }
  let targetCandles = [];

  function drawPriceChart(state) {
    if (!state) return;
    latestState = state;

    const rawCandles = state.candles || [];
    const rawPrices = state.price_history || [];
    const useCandles = chartMode === 'candles' && rawCandles.length >= 2;
    const strategies = state.strategies || [];

    targetSpot = Number((state.quote && state.quote.price) || 0);

    const canvas = document.getElementById('priceCanvas');
    const canvasW = canvas ? (canvas.clientWidth || 800) : 800;
    const plotW = Math.max(50, canvasW - 10 - 72);
    // Dynamic high-density candle count: ~9.5px to 11.5px per candle so wide monitors remain dense
    const optimalCount = Math.max(45, Math.min(rawCandles.length, Math.floor(plotW / 9.5)));
    targetCandles = rawCandles.slice(-optimalCount);

    let minP = Infinity, maxP = -Infinity;
    if (useCandles && targetCandles.length > 0) {
      targetCandles.forEach(c => {
        if (c.l < minP) minP = c.l;
        if (c.h > maxP) maxP = c.h;
      });
    } else if (rawPrices.length > 0) {
      const visP = rawPrices.slice(-80);
      visP.forEach(p => {
        if (p < minP) minP = p;
        if (p > maxP) maxP = p;
      });
    }

    if (targetSpot > 0) {
      minP = Math.min(minP, targetSpot);
      maxP = Math.max(maxP, targetSpot);
    }

    if (!isFinite(minP) || !isFinite(maxP) || minP <= 0) {
      minP = targetSpot > 0 ? targetSpot - 4 : 2240;
      maxP = targetSpot > 0 ? targetSpot + 4 : 2260;
    }

    if (scaleMode === 'full') {
      strategies.forEach(s => {
        if (s.in_position) {
          if (s.entry_price && s.entry_price > 0) {
            minP = Math.min(minP, s.entry_price);
            maxP = Math.max(maxP, s.entry_price);
          }
          if (s.stop_loss && s.stop_loss > 0) minP = Math.min(minP, s.stop_loss);
          if (s.take_profit && s.take_profit > 0) maxP = Math.max(maxP, s.take_profit);
        }
      });
    }

    const span = Math.max(2.5, maxP - minP);
    targetMinP = minP - span * 0.16;
    targetMaxP = maxP + span * 0.16;

    // Bootstrap values on initial load
    if (animSpot === 0) animSpot = targetSpot;
    if (animMinP === 0) animMinP = targetMinP;
    if (animMaxP === 0) animMaxP = targetMaxP;
    if (animCandles.length === 0 && targetCandles.length > 0) {
      animCandles = targetCandles.map(c => ({ o: c.o, h: c.h, l: c.l, c: c.c, t: c.t }));
    }

    startChartAnimLoop();
  }

  function startChartAnimLoop() {
    if (!chartAnimRaf) {
      chartAnimRaf = requestAnimationFrame(stepChartAnimLoop);
    }
  }

  function stepChartAnimLoop() {
    chartAnimRaf = null;
    if (!latestState) return;

    const ease = 0.22; // Responsive 60 FPS damping
    let needsMore = false;

    // 1. Lerp Spot Price (Smooth Glide)
    const dSpot = targetSpot - animSpot;
    if (Math.abs(dSpot) > 0.02) {
      animSpot += dSpot * ease;
      needsMore = true;
    } else {
      animSpot = targetSpot;
    }

    // 2. Lerp Price Bounds (Smooth Dynamic Scale)
    const dMin = targetMinP - animMinP;
    if (Math.abs(dMin) > 0.02) {
      animMinP += dMin * ease;
      needsMore = true;
    } else {
      animMinP = targetMinP;
    }

    const dMax = targetMaxP - animMaxP;
    if (Math.abs(dMax) > 0.02) {
      animMaxP += dMax * ease;
      needsMore = true;
    } else {
      animMaxP = targetMaxP;
    }

    // 3. Lerp Candle Heights & Wicks (Dynamic Morphing Transition)
    if (animCandles.length !== targetCandles.length) {
      animCandles = targetCandles.map(c => ({ o: c.o, h: c.h, l: c.l, c: c.c, t: c.t }));
      needsMore = true;
    } else {
      for (let i = 0; i < targetCandles.length; i++) {
        const tc = targetCandles[i];
        const ac = animCandles[i];
        ac.o = tc.o;
        ac.t = tc.t;

        const dC = tc.c - ac.c;
        const dH = tc.h - ac.h;
        const dL = tc.l - ac.l;

        if (Math.abs(dC) > 0.02) { ac.c += dC * ease; needsMore = true; } else { ac.c = tc.c; }
        if (Math.abs(dH) > 0.02) { ac.h += dH * ease; needsMore = true; } else { ac.h = tc.h; }
        if (Math.abs(dL) > 0.02) { ac.l += dL * ease; needsMore = true; } else { ac.l = tc.l; }
      }
    }

    // 4. Active radar beacons
    if (chartBeacons && chartBeacons.length > 0) {
      const now = Date.now();
      chartBeacons = chartBeacons.filter(b => (now - b.startTime) < b.duration);
      if (chartBeacons.length > 0) needsMore = true;
    }

    // 5. Render Canvas Frame
    renderPriceCanvas(latestState, animCandles, animSpot, animMinP, animMaxP);

    if (needsMore) {
      chartAnimRaf = requestAnimationFrame(stepChartAnimLoop);
    }
  }

  function renderPriceCanvas(state, visibleCandles, spot, minP, maxP) {
    const canvas = document.getElementById('priceCanvas');
    if (!canvas || !state) return;
    const { ctx, w, h } = setupHiDPICanvas(canvas);
    ctx.clearRect(0, 0, w, h);

    const rawPrices = state.price_history || [];
    const ema9 = state.ema_fast_history || [];
    const ema21 = state.ema_slow_history || [];
    const strategies = state.strategies || [];
    const useCandles = chartMode === 'candles' && visibleCandles.length >= 2;

    const padLeft = 10;
    const padRight = 72; // comfortable width for strategy badges
    const padTop = 16;
    const padBottom = 22;
    const plotW = Math.max(50, w - padLeft - padRight);
    const plotH = Math.max(40, h - padTop - padBottom);

    const toY = (v) => padTop + (1 - (v - minP) / (maxP - minP)) * plotH;

    // Horizontal Grid Lines with Price Labels (Ultra-Crisp Minimalist Lines)
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.06)';
    ctx.lineWidth = 1;
    ctx.font = '10px "Cascadia Mono", Consolas, monospace';
    ctx.fillStyle = '#8391A7';
    const gridCount = plotH > 380 ? 6 : 4;
    for (let g = 0; g <= gridCount; g++) {
      const gv = minP + ((maxP - minP) * (gridCount - g)) / gridCount;
      const gy = toY(gv);
      ctx.beginPath();
      ctx.moveTo(padLeft, gy);
      ctx.lineTo(padLeft + plotW, gy);
      ctx.stroke();
      ctx.fillText('$' + gv.toFixed(1), padLeft + plotW + 6, gy + 3.5);
    }

    const tagMap = {
      'comp_agg': 'AGG',
      'comp_cons': 'CONS',
      'comp_atr': 'ATR',
      'comp_trail': 'TRAIL',
      'comp_orb': 'ORB',
      'comp_vwap': 'VWAP'
    };

    // NOTE: Shaded Corridors REMOVED -> PURE OLED OBSIDIAN HIGH CONTRAST (ZERO MUDDY GRADIENT)

    // 2. Candlesticks or Smooth Line Chart
    if (useCandles && visibleCandles.length > 0) {
      const n = visibleCandles.length;
      // Caps maximum center-to-center distance to avoid wide horizontal gaps on fullscreen or sparse data
      const maxStep = 13.0;
      const minStep = 5.5;
      const naturalStep = plotW / Math.max(1, n);
      const step = Math.min(maxStep, Math.max(minStep, naturalStep));
      const bodyW = Math.max(3.5, Math.min(10, Math.round(step * 0.72))); // 72% body, 28% crisp gap

      // If candles do not fill the whole width (e.g. startup or sparse data), right-align next to price scale
      const totalCandleW = n * step;
      const startX = totalCandleW < plotW ? (padLeft + plotW - totalCandleW) : padLeft;

      let maxC = visibleCandles[0], minC = visibleCandles[0];
      let maxIdx = 0, minIdx = 0;

      visibleCandles.forEach((c, i) => {
        if (c.h > maxC.h) { maxC = c; maxIdx = i; }
        if (c.l < minC.l) { minC = c; minIdx = i; }

        const cx = startX + (i + 0.5) * step;
        const isUp = c.c >= c.o;
        const bodyColor = isUp ? '#00E676' : '#FF334B';
        const wickColor = isUp ? '#00FF88' : '#FF5E73';
        const yOpen = toY(c.o);
        const yClose = toY(c.c);
        const yHigh = toY(c.h);
        const yLow = toY(c.l);

        // Wick Shadow
        ctx.strokeStyle = wickColor;
        ctx.lineWidth = 1.3;
        ctx.beginPath();
        ctx.moveTo(cx, yHigh);
        ctx.lineTo(cx, yLow);
        ctx.stroke();

        // Real Body (Smoothly morphing height)
        ctx.fillStyle = bodyColor;
        const topY = Math.min(yOpen, yClose);
        const bHeight = Math.max(2.5, Math.abs(yClose - yOpen));
        ctx.fillRect(cx - bodyW / 2, topY, bodyW, bHeight);

        // Fine Outline for definition
        ctx.strokeStyle = isUp ? 'rgba(0, 255, 136, 0.75)' : 'rgba(255, 94, 115, 0.75)';
        ctx.lineWidth = 0.8;
        ctx.strokeRect(cx - bodyW / 2, topY, bodyW, bHeight);
      });

      // Overlay Silky Smooth Bézier Spline EMA lines on candlesticks
      const drawCandleEma = (emaArr, color, width = 1.6, lineDash = []) => {
        if (!emaArr || emaArr.length < 2) return;
        const sliceEma = emaArr.slice(-n);
        const offset = Math.max(0, n - sliceEma.length);
        const pts = [];
        for (let i = 0; i < sliceEma.length; i++) {
          pts.push({
            x: startX + (offset + i + 0.5) * step,
            y: toY(sliceEma[i])
          });
        }
        drawSmoothCurve(ctx, pts, color, width, lineDash);
      };

      drawCandleEma(ema21, '#FFB800', 1.5);
      drawCandleEma(ema9, '#38BDF8', 1.6);

      // High / Low Markers
      ctx.save();
      ctx.font = '9px "Cascadia Mono", Consolas, monospace';
      ctx.fillStyle = '#CBD5E1';
      const maxCx = startX + (maxIdx + 0.5) * step;
      const minCx = startX + (minIdx + 0.5) * step;
      ctx.fillText(`H $${maxC.h.toFixed(1)}`, Math.max(padLeft, Math.min(padLeft + plotW - 30, maxCx - 18)), toY(maxC.h) - 4);
      ctx.fillText(`L $${minC.l.toFixed(1)}`, Math.max(padLeft, Math.min(padLeft + plotW - 30, minCx - 18)), toY(minC.l) + 12);
      ctx.restore();

    } else if (rawPrices.length >= 2) {
      const n = Math.min(80, rawPrices.length);
      const visiblePrices = rawPrices.slice(-n);
      const toX = (i) => padLeft + (i / (n - 1)) * plotW;

      // Pure High-Contrast Bézier Spline Lines
      const drawLine = (arr, color, width, lineDash = []) => {
        if (!arr || arr.length < 2) return;
        const sliceArr = arr.slice(-n);
        const offset = Math.max(0, n - sliceArr.length);
        const pts = [];
        for (let i = 0; i < sliceArr.length; i++) {
          pts.push({
            x: toX(offset + i),
            y: toY(sliceArr[i])
          });
        }
        drawSmoothCurve(ctx, pts, color, width, lineDash);
      };

      drawLine(ema21, '#FFB800', 1.5);
      drawLine(ema9, '#38BDF8', 1.6);
      drawLine(visiblePrices, '#FFFFFF', 2.2);
    }

    // 3. Strategy Levels, Brackets & Spot Price Badges (Crisp Lines on Pure Obsidian Black)
    const rightBadges = [];
    const offscreenTargets = [];
    const offscreenStops = [];
    const activeStrats = strategies.filter(s => s.in_position);

    activeStrats.forEach((s, idx) => {
      const sTag = tagMap[s.id] || (s.name ? s.name.slice(0, 4).toUpperCase() : 'STRAT');
      const sColor = s.color || '#FFB800';

      let yTP = null, yEntry = null, ySL = null;

      // Take Profit Line
      if (s.take_profit && s.take_profit > 0) {
        if (s.take_profit >= minP && s.take_profit <= maxP) {
          yTP = toY(s.take_profit);
          ctx.save();
          ctx.strokeStyle = sColor;
          ctx.setLineDash([4, 4]);
          ctx.lineWidth = 1.3;
          ctx.beginPath();
          ctx.moveTo(padLeft, yTP);
          ctx.lineTo(padLeft + plotW, yTP);
          ctx.stroke();
          ctx.restore();

          rightBadges.push({
            rawY: yTP,
            price: s.take_profit,
            label: `TP $${s.take_profit.toFixed(1)}`,
            stratTag: sTag,
            color: '#00E676',
            stratColor: sColor,
            type: 'tp'
          });
        } else if (s.take_profit > maxP) {
          offscreenTargets.push({ name: sTag, price: s.take_profit, color: sColor });
        }
      }

      // Entry Price Line
      if (s.entry_price && s.entry_price > 0) {
        if (s.entry_price >= minP && s.entry_price <= maxP) {
          yEntry = toY(s.entry_price);
          ctx.save();
          ctx.strokeStyle = sColor;
          ctx.setLineDash([2, 3]);
          ctx.lineWidth = 1.4;
          ctx.beginPath();
          ctx.moveTo(padLeft, yEntry);
          ctx.lineTo(padLeft + plotW, yEntry);
          ctx.stroke();
          ctx.restore();

          rightBadges.push({
            rawY: yEntry,
            price: s.entry_price,
            label: `ENTRY $${s.entry_price.toFixed(1)}`,
            stratTag: sTag,
            color: '#FFFFFF',
            stratColor: sColor,
            type: 'entry'
          });
        }
      }

      // Stop Loss Line
      if (s.stop_loss && s.stop_loss > 0) {
        if (s.stop_loss >= minP && s.stop_loss <= maxP) {
          ySL = toY(s.stop_loss);
          ctx.save();
          ctx.strokeStyle = sColor;
          ctx.setLineDash([4, 4]);
          ctx.lineWidth = 1.3;
          ctx.beginPath();
          ctx.moveTo(padLeft, ySL);
          ctx.lineTo(padLeft + plotW, ySL);
          ctx.stroke();
          ctx.restore();

          rightBadges.push({
            rawY: ySL,
            price: s.stop_loss,
            label: `SL $${s.stop_loss.toFixed(1)}`,
            stratTag: sTag,
            color: '#FF334B',
            stratColor: sColor,
            type: 'sl'
          });
        } else if (s.stop_loss < minP) {
          offscreenStops.push({ name: sTag, price: s.stop_loss, color: sColor });
        }
      }

      // Vertical Bracket Connector
      const bracketTop = yTP !== null ? yTP : (yEntry !== null ? yEntry : null);
      const bracketBot = ySL !== null ? ySL : (yEntry !== null ? yEntry : null);
      if (bracketTop !== null && bracketBot !== null && bracketBot > bracketTop) {
        const bx = padLeft + plotW - 5 - (idx * 8);
        ctx.save();
        ctx.strokeStyle = sColor;
        ctx.lineWidth = 1.6;
        ctx.beginPath();
        ctx.moveTo(bx, bracketTop);
        ctx.lineTo(bx, bracketBot);
        ctx.moveTo(bx - 3, bracketTop);
        ctx.lineTo(bx + 3, bracketTop);
        ctx.moveTo(bx - 3, bracketBot);
        ctx.lineTo(bx + 3, bracketBot);
        if (yEntry !== null && yEntry > bracketTop && yEntry < bracketBot) {
          ctx.moveTo(bx, yEntry);
          ctx.lineTo(bx - 4, yEntry);
        }
        ctx.stroke();
        ctx.restore();
      }
    });

    // 3b. Institutional Indicators (VWAP & ORB Range Reference Lines)
    const ind = state.indicators || {};
    const vwapVal = Number(ind.vwap || 0);
    if (vwapVal >= minP && vwapVal <= maxP) {
      const vy = toY(vwapVal);
      ctx.save();
      ctx.strokeStyle = 'rgba(20, 241, 149, 0.75)';
      ctx.setLineDash([4, 4]);
      ctx.lineWidth = 1.4;
      ctx.beginPath();
      ctx.moveTo(padLeft, vy);
      ctx.lineTo(padLeft + plotW, vy);
      ctx.stroke();
      ctx.restore();

      rightBadges.push({
        rawY: vy,
        price: vwapVal,
        label: `VWAP $${vwapVal.toFixed(1)}`,
        stratTag: 'VWAP',
        color: '#14F195',
        stratColor: '#14F195',
        type: 'vwap'
      });
    }

    const orbHigh = Number(ind.orb_high || 0);
    const orbLow = Number(ind.orb_low || 0);
    if (orbHigh > 0 && orbHigh >= minP && orbHigh <= maxP) {
      const ohy = toY(orbHigh);
      ctx.save();
      ctx.strokeStyle = 'rgba(168, 85, 247, 0.65)';
      ctx.setLineDash([3, 3]);
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.moveTo(padLeft, ohy);
      ctx.lineTo(padLeft + plotW, ohy);
      ctx.stroke();
      ctx.restore();

      rightBadges.push({
        rawY: ohy,
        price: orbHigh,
        label: `ORB-H $${orbHigh.toFixed(1)}`,
        stratTag: 'ORB',
        color: '#A855F7',
        stratColor: '#A855F7',
        type: 'orb'
      });
    }
    if (orbLow > 0 && orbLow >= minP && orbLow <= maxP) {
      const oly = toY(orbLow);
      ctx.save();
      ctx.strokeStyle = 'rgba(168, 85, 247, 0.65)';
      ctx.setLineDash([3, 3]);
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.moveTo(padLeft, oly);
      ctx.lineTo(padLeft + plotW, oly);
      ctx.stroke();
      ctx.restore();

      rightBadges.push({
        rawY: oly,
        price: orbLow,
        label: `ORB-L $${orbLow.toFixed(1)}`,
        stratTag: 'ORB',
        color: '#A855F7',
        stratColor: '#A855F7',
        type: 'orb'
      });
    }

    // Spot Price Line & Right Badge (Smooth gliding position)
    if (spot >= minP && spot <= maxP) {
      const sy = toY(spot);
      ctx.save();
      ctx.strokeStyle = 'rgba(255, 107, 53, 0.95)';
      ctx.setLineDash([3, 3]);
      ctx.lineWidth = 1.3;
      ctx.beginPath();
      ctx.moveTo(padLeft, sy);
      ctx.lineTo(padLeft + plotW, sy);
      ctx.stroke();
      ctx.restore();

      rightBadges.push({
        rawY: sy,
        price: spot,
        label: '$' + spot.toFixed(1),
        stratTag: null,
        color: '#FFFFFF',
        stratColor: '#FF6B35',
        type: 'spot',
        isSpot: true
      });
    }

    // 4. Collision-Free Right Badges Layout
    const badgeH = 14;
    rightBadges.forEach(b => { b.drawY = b.rawY; });
    rightBadges.sort((a, b) => a.drawY - b.drawY);

    for (let i = 1; i < rightBadges.length; i++) {
      if (rightBadges[i].drawY < rightBadges[i - 1].drawY + badgeH + 2) {
        rightBadges[i].drawY = rightBadges[i - 1].drawY + badgeH + 2;
      }
    }
    for (let i = rightBadges.length - 1; i >= 0; i--) {
      if (rightBadges[i].drawY > padTop + plotH - 5) {
        rightBadges[i].drawY = padTop + plotH - 5;
        if (i > 0 && rightBadges[i - 1].drawY > rightBadges[i].drawY - badgeH - 2) {
          rightBadges[i - 1].drawY = rightBadges[i].drawY - badgeH - 2;
        }
      }
    }

    rightBadges.forEach(b => {
      const by = b.drawY;
      const rx = padLeft + plotW + 2;
      const rw = 68;

      ctx.save();
      if (Math.abs(by - b.rawY) > 3) {
        ctx.strokeStyle = hexToRgba(b.stratColor, 0.45);
        ctx.lineWidth = 1;
        ctx.setLineDash([2, 2]);
        ctx.beginPath();
        ctx.moveTo(padLeft + plotW, b.rawY);
        ctx.lineTo(rx, by);
        ctx.stroke();
      }

      if (b.isSpot) {
        ctx.fillStyle = '#FF6B35';
        ctx.fillRect(rx, by - 8, rw, 16);
        ctx.fillStyle = '#FFFFFF';
        ctx.font = 'bold 10px "Cascadia Mono", Consolas, monospace';
        ctx.fillText(b.label, rx + 5, by + 3.5);
      } else {
        ctx.fillStyle = 'rgba(14, 17, 24, 0.94)';
        ctx.fillRect(rx, by - 7, rw, 14);
        ctx.strokeStyle = hexToRgba(b.stratColor, 0.7);
        ctx.strokeRect(rx, by - 7, rw, 14);

        // Colored left accent bar
        ctx.fillStyle = b.stratColor;
        ctx.fillRect(rx, by - 7, 3, 14);

        // Strategy Tag
        ctx.font = 'bold 8.5px "Cascadia Mono", Consolas, monospace';
        ctx.fillStyle = b.stratColor;
        ctx.fillText(b.stratTag, rx + 5, by + 3.5);

        // Price Label
        ctx.font = '8.5px "Cascadia Mono", Consolas, monospace';
        ctx.fillStyle = b.color;
        ctx.fillText(b.label, rx + 24, by + 3.5);
      }
      ctx.restore();
    });

    // 5. Draw Off-Screen Order Indicators (top & bottom edges in Auto mode)
    if (scaleMode === 'auto') {
      if (offscreenTargets.length > 0) {
        ctx.save();
        ctx.font = '9.5px "Cascadia Mono", Consolas, monospace';
        let tx = padLeft + 6;
        offscreenTargets.slice(0, 4).forEach(t => {
          const diffPct = spot > 0 ? (((t.price - spot) / spot) * 100).toFixed(1) : '0';
          const txt = `[${t.name}] TP $${t.price.toFixed(0)} (+${diffPct}%)`;
          const tw = ctx.measureText(txt).width + 10;
          ctx.fillStyle = hexToRgba(t.color, 0.16);
          ctx.strokeStyle = hexToRgba(t.color, 0.6);
          ctx.fillRect(tx, padTop + 2, tw, 15);
          ctx.strokeRect(tx, padTop + 2, tw, 15);
          ctx.fillStyle = t.color;
          ctx.fillText(txt, tx + 5, padTop + 13);
          tx += tw + 6;
        });
        ctx.restore();
      }

      if (offscreenStops.length > 0) {
        ctx.save();
        ctx.font = '9.5px "Cascadia Mono", Consolas, monospace';
        let sx = padLeft + 6;
        offscreenStops.slice(0, 4).forEach(s => {
          const diffPct = spot > 0 ? (((spot - s.price) / spot) * 100).toFixed(1) : '0';
          const txt = `[${s.name}] SL $${s.price.toFixed(0)} (-${diffPct}%)`;
          const tw = ctx.measureText(txt).width + 10;
          ctx.fillStyle = hexToRgba(s.color, 0.16);
          ctx.strokeStyle = hexToRgba(s.color, 0.6);
          ctx.fillRect(sx, padTop + plotH - 18, tw, 15);
          ctx.strokeRect(sx, padTop + plotH - 18, tw, 15);
          ctx.fillStyle = s.color;
          ctx.fillText(txt, sx + 5, padTop + plotH - 7);
          sx += tw + 6;
        });
        ctx.restore();
      }
    }

    // 6. Active Strategy Entry Beacon Waves (Sonar Wave / Radar Ping)
    if (chartBeacons && chartBeacons.length > 0) {
      const now = Date.now();
      const n = useCandles ? visibleCandles.length : rawPrices.length;
      const step = plotW / Math.max(1, n);
      const activeHeadX = padLeft + (Math.max(0, n - 1) + 0.5) * step;

      chartBeacons.forEach(b => {
        const elapsed = now - b.startTime;
        if (elapsed >= b.duration) return;
        const p = elapsed / b.duration;
        const by = Math.max(padTop + 10, Math.min(padTop + plotH - 10, toY(b.price)));
        const bx = Math.min(padLeft + plotW - 12, Math.max(padLeft + 12, activeHeadX));

        ctx.save();
        // Ring 1
        const r1 = 4 + p * 38;
        const a1 = Math.max(0, (1 - p) * 0.9);
        ctx.strokeStyle = b.color;
        ctx.globalAlpha = a1;
        ctx.lineWidth = 2.2 * (1 - p);
        ctx.shadowColor = b.color;
        ctx.shadowBlur = 12;
        ctx.beginPath();
        ctx.arc(bx, by, r1, 0, Math.PI * 2);
        ctx.stroke();

        // Ring 2
        const p2 = (p + 0.38) % 1;
        const r2 = 4 + p2 * 38;
        const a2 = Math.max(0, (1 - p2) * 0.65);
        ctx.globalAlpha = a2;
        ctx.lineWidth = 1.8 * (1 - p2);
        ctx.beginPath();
        ctx.arc(bx, by, r2, 0, Math.PI * 2);
        ctx.stroke();

        // Pulsing Core
        const pulse = Math.sin(p * Math.PI * 8);
        ctx.globalAlpha = 0.95;
        ctx.fillStyle = b.color;
        ctx.beginPath();
        ctx.arc(bx, by, 3.5 + pulse * 1.5, 0, Math.PI * 2);
        ctx.fill();

        // Badge
        ctx.fillStyle = b.color;
        ctx.font = 'bold 9px "Cascadia Mono", Consolas, monospace';
        ctx.fillText(`[${b.stratTag}] ENTRY`, bx + 10, by - 8);
        ctx.restore();
      });
    }

    // 7. Interactive Hover Crosshair
    if (priceHoverPos && priceHoverPos.x >= padLeft && priceHoverPos.x <= padLeft + plotW) {
      ctx.save();
      ctx.strokeStyle = 'rgba(243, 239, 230, 0.35)';
      ctx.setLineDash([3, 3]);
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(priceHoverPos.x, padTop);
      ctx.lineTo(priceHoverPos.x, padTop + plotH);
      ctx.stroke();
      if (priceHoverPos.y >= padTop && priceHoverPos.y <= padTop + plotH) {
        ctx.beginPath();
        ctx.moveTo(padLeft, priceHoverPos.y);
        ctx.lineTo(padLeft + plotW, priceHoverPos.y);
        ctx.stroke();
      }
      ctx.restore();
    }
  }

  // Interactive Hover Tooltip for Price Chart
  function setupChartInteraction() {
    const wrap = document.getElementById('priceCanvasWrap');
    const tip = document.getElementById('priceTooltip');
    if (!wrap || !tip) return;

    wrap.addEventListener('mousemove', (e) => {
      if (!latestState) return;
      const rect = wrap.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;
      priceHoverPos = { x: mouseX, y: mouseY };

      const candles = (animCandles && animCandles.length > 0) ? animCandles : (latestState.candles || []);
      const useCandles = chartMode === 'candles' && candles.length >= 2;
      const padLeft = 10, padRight = 72;
      const plotW = Math.max(50, rect.width - padLeft - padRight);

      if (useCandles) {
        const n = candles.length;
        const maxStep = 13.0;
        const minStep = 5.5;
        const naturalStep = plotW / Math.max(1, n);
        const step = Math.min(maxStep, Math.max(minStep, naturalStep));
        const totalCandleW = n * step;
        const startX = totalCandleW < plotW ? (padLeft + plotW - totalCandleW) : padLeft;
        const idx = Math.floor((mouseX - startX) / step);
        if (idx >= 0 && idx < n) {
          const c = candles[idx];
          const isUp = c.c >= c.o;
          const chg = c.o > 0 ? (((c.c - c.o) / c.o) * 100).toFixed(2) : '0.00';
          const tStr = new Date(c.t * 1000).toTimeString().split(' ')[0];
          tip.style.display = 'block';
          tip.style.left = Math.min(rect.width - 190, Math.max(10, mouseX + 12)) + 'px';
          tip.style.top = Math.max(10, mouseY - 55) + 'px';
          tip.innerHTML = `
            <div style="font-weight:700;color:var(--text-secondary);">${tStr} (1m Candle)</div>
            <div>O: <strong>$${c.o.toFixed(1)}</strong> H: <strong>$${c.h.toFixed(1)}</strong></div>
            <div>L: <strong>$${c.l.toFixed(1)}</strong> C: <strong class="${isUp ? 'up' : 'down'}">$${c.c.toFixed(1)} (${chg}%)</strong></div>
          `;
        } else {
          tip.style.display = 'none';
        }
      } else {
        tip.style.display = 'none';
      }
      drawPriceChart(latestState);
    });

    wrap.addEventListener('mouseleave', () => {
      priceHoverPos = null;
      tip.style.display = 'none';
      if (latestState) drawPriceChart(latestState);
    });
  }

  // Fluid ResizeObserver with 60 FPS requestAnimationFrame throttling
  let resizeRaf = null;
  const triggerSmoothResize = () => {
    if (resizeRaf) cancelAnimationFrame(resizeRaf);
    resizeRaf = requestAnimationFrame(() => {
      if (latestState) drawPriceChart(latestState);
    });
  };

  const resizeObserver = new ResizeObserver(triggerSmoothResize);

  function toggleFullscreen() {
    if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.toggle_fullscreen === 'function') {
      window.pywebview.api.toggle_fullscreen().catch(function(err) {
        console.warn('Native toggle_fullscreen fallback:', err);
        toggleDomFullscreen();
      });
    } else {
      toggleDomFullscreen();
    }
  }

  function toggleDomFullscreen() {
    if (!document.fullscreenElement) {
      if (document.documentElement.requestFullscreen) {
        document.documentElement.requestFullscreen().catch(function() {});
      }
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen().catch(function() {});
      }
    }
  }

  // Handle F11 keypress across entire window for Fullscreen Toggle
  window.addEventListener('keydown', function(e) {
    if (e.key === 'F11' || e.code === 'F11' || e.keyCode === 122) {
      e.preventDefault();
      e.stopPropagation();
      toggleFullscreen();
    }
  }, true);

  window.addEventListener('DOMContentLoaded', () => {
    const pWrap = document.getElementById('priceCanvasWrap');
    if (pWrap) resizeObserver.observe(pWrap);
    setupChartInteraction();

    window.addEventListener('resize', triggerSmoothResize);

    setTimeout(pollBackend, 120);
    setInterval(pollBackend, 1000);
  });
</script>
</body>
</html>
"""


class ArenaDashboard:
    """
    Native Windows GPU-Accelerated HiDPI Live Multi-Strategy Trading Desk.
    Powered by Edge WebView2 DirectX 11 Compositor + LiveArenaEngine.
    """

    def __init__(self, initial_cash: Decimal = Decimal("500000.00")) -> None:
        self.initial_cash = initial_cash
        self.engine = LiveArenaEngine(symbol="ETH/USD", initial_cash=initial_cash)
        self.window = None
        self._bridge = _ArenaBridgeApi(self)

    def reset_engine(self) -> None:
        old_interval = self.engine.auto_evolve_interval_sec
        old_enabled = self.engine.auto_evolve_enabled
        self.engine.stop()
        self.engine = LiveArenaEngine(symbol="ETH/USD", initial_cash=self.initial_cash)
        self.engine.auto_evolve_interval_sec = old_interval
        self.engine.auto_evolve_enabled = old_enabled
        self.engine.start_live_loop(interval_sec=1.5)

    def run(self) -> None:
        import webview

        # Start real-time live ETH/USD streaming & multi-strategy execution immediately
        self.engine.start_live_loop(interval_sec=1.5)

        window = webview.create_window(
            title="TradeBot0 — ETH/USD Multi-Strategy Quant Arena (Obsidian High-Contrast · Style B Evolution)",
            html=HTML_TEMPLATE,
            js_api=self._bridge,
            width=1540,
            height=940,
            min_size=(960, 640),
            background_color="#08090C",
            resizable=True,
            maximized=True,
            text_select=False,
        )
        self.window = window

        try:
            webview.start(debug=False)
        finally:
            self.engine.stop()
