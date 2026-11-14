"""TradeBot0 version — single source of truth.

The application version lives here and nowhere else. The Inno Setup
installer (TradeBot0.iss, MyAppVersion) must be kept in sync by hand at
release time: bump APP_VERSION here and MyAppVersion there to the same
value. The in-app update checker (src/update_checker.py) compares the
running version against the manifest version using this constant.

Version scheme: ``VX.Y.Z`` (e.g. "V2.7.0"), matching the installer
version. X = major changes (release milestones / breaking changes),
Y = feature groups (one subsystem counts once, e.g. the whole AI
intelligence stack is one group), Z = fix / optimization groups.
Counts were reconstructed from git history (2026-11-15: V2.5.3;
V2.6.0 the same day: Intel Hub layout + honest stream sync
progress, Advanced toggle removed;
V2.7.0 the same day: V2.6.0 audit repair program (all 33 findings)
+ full debug & optimize pass) and
are grouped by subsystem so the numbers stay single-digit longer.
Going forward each new batch bumps the matching number by 1 (new
feature group -> Y, fix / optimization batch -> Z, breaking change
-> X with Y and Z reset to 0). The comparison helper accepts an
optional ``v``/``V`` prefix and plain ``X.Y.Z`` too.
"""

APP_NAME = "TradeBot0"
APP_VERSION = "V2.7.0"
