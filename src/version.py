"""TradeBot0 version — single source of truth.

The application version lives here and nowhere else. The Inno Setup
installer (TradeBot0.iss, MyAppVersion) must be kept in sync by hand at
release time: bump APP_VERSION here and MyAppVersion there to the same
value. The in-app update checker (src/update_checker.py) compares the
running version against the manifest version using this constant.

Version scheme: ``VX.Y.Z`` (e.g. "V1.0.0"), matching the installer
version. X = major changes (release milestones / breaking changes),
Y = feature groups (one subsystem counts once, e.g. the whole AI
intelligence stack is one group), Z = fix / optimization groups.
Counts were reconstructed from git history (2026-11-15: V2.5.3;
V2.6.0 the same day: Intel Hub layout + honest stream sync
progress, Advanced toggle removed;
V2.7.0 the same day: V2.6.0 audit repair program (all 33 findings)
+ full debug & optimize pass;
V2.8.0 the same day: Intel Hub stream redesign (full-width rows, lazy articles) + Dynamic Island extension + card reorder animation + comp_atr removal + chop-gate seeding + full debug & optimize pass;
V2.8.1 the same day: V2.8.0 audit repair program (all 10 findings 2.1-2.10) + VMAP color fix;
V2.8.2 the same day: wizard starter provider DeepSeek -> NVIDIA NIM;
V2.8.3 the same day: Intel Hub top-deck empty slots collapse (deck 221px -> 177px, bottoms stay level);
V2.8.4 the same day: Dynamic Island grows to fill dock gap + article loading indeterminate progress bar;
V2.8.5 the same day: lazy article fades in when it loads;
V2.8.7 the same day: article re-render jitter fixed + articles preload while collapsed;
V1.0.0 (2026-11-18, first public GitHub release): version numbering reset only, code and features unchanged from V2.8.7);
V2.0.0 (2026-11-19): Full BUG-01..BUG-17 resolution, LiveArenaEngine decomposition into 4 cohesive mixins, non-blocking SQLite/evolution lock narrowing, Student-t/bootstrap antithetic Monte Carlo EV gate, and complete ETH/USD docs & regression test suite.
V2.1.0 (2026-11-20): Setup wizard simplified to Google Gemini only; OmniRoute npm install progress bar tracks real written bytes and estimated remaining time.
V2.2.0 (2026-11-20): Full debug & optimization pass across arena ledger/broker/evolution, live engine/MTF/Monte Carlo/SQLite, intelligence/gateway/config, and GUI/frontend rendering & state sync.
V2.4.0 (2026-11-21): Vertical Gemini Setup Wizard with live Node.js/OmniRoute environment detection, real OmniRoute SQLite admin password sync, unified dev_test.bat launcher, and comprehensive second-order debug & optimization sweep across Arena, LiveEngine, Intelligence/Gateway, and GUI/Frontend.
V2.4.1 (2026-11-22): Installer wizard detects existing user data and asks whether to clear it (default: keep); installer filename carries the version.
V2.5.0 (2026-11-22): Full debug & optimization sweep across Arena/BrokerSim/Portfolio/Competitors, LiveEngine/SessionCodec/Persistence/WebSocket/MTF/MonteCarlo, OmniRoute/GatewaySupervisor/MacroCommander/Harvester, and GUI/ViewModel/Frontend/Installer/Tooling.
V2.5.1 (2026-11-23): Restored graphify CLI toolchain and refreshed codebase knowledge graph (graphify-out/) to match V2.5.x architecture.
V2.5.2 (2026-11-23): Fixed brand pod subtitle truncation, added styled password reveal eye button alongside copy, added collapse-then-FLIP news sort animations, removed seconds from event timestamps, and upgraded article loading to real streamed multi-stage progress.
V2.5.3 (2026-11-23): Added installer "Launch TradeBot0" post-install option (checked by default) and instant PyInstaller native startup splash screen auto-closing when the main window opens.
V2.6.0 (2026-11-23): UI optimization overhaul (HorizonX Silver Stream backdrop, grainient fallback, compositor view/splash transitions, rolling counters, command palette, Toast/Intel polish), custom app icon & AppUserModelID, real-time news freshness, and full backend/gateway/frontend debug & optimization sweep.
V3.0.0 (2026-11-25): Complete OmniRoute and Node.js gateway removal — direct Google Gemini REST API client (GeminiClient) with SSE progress and structured error handling, simplified single-key ConfigManager with one-time legacy cleanup, unified AI Hub telemetry, and splash-to-toast catch-up on session restore.
Going forward each new batch bumps the matching number by 1 (new
feature group -> Y, fix / optimization batch -> Z, breaking change
-> X with Y and Z reset to 0). The comparison helper accepts an
optional ``v``/``V`` prefix and plain ``X.Y.Z`` too.
"""

APP_NAME = "TradeBot0"
APP_VERSION = "V3.0.0"
