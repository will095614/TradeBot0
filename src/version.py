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
V1.0.0 (2026-11-18, first public GitHub release): version numbering reset only, code and features unchanged from V2.8.7) and
are grouped by subsystem so the numbers stay single-digit longer.
Going forward each new batch bumps the matching number by 1 (new
feature group -> Y, fix / optimization batch -> Z, breaking change
-> X with Y and Z reset to 0). The comparison helper accepts an
optional ``v``/``V`` prefix and plain ``X.Y.Z`` too.
"""

APP_NAME = "TradeBot0"
APP_VERSION = "V1.0.0"
