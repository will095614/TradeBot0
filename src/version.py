"""TradeBot0 version — single source of truth.

The application version lives here and nowhere else. The Inno Setup
installer (TradeBot0.iss, MyAppVersion) must be kept in sync by hand at
release time: bump APP_VERSION here and MyAppVersion there to the same
value. The in-app update checker (src/update_checker.py) compares the
running version against the manifest version using this constant.

Version scheme: ``VX.Y.Z`` (e.g. "V3.2.1"), matching the installer
version. X = major changes (release milestones / breaking changes),
Y = feature groups (one subsystem counts once, e.g. the whole AI
intelligence stack is one group), Z = fix / optimization groups.
Each new release bumps the matching number by 1 (new feature group -> Y,
fix / optimization batch -> Z, breaking change -> X with Y and Z reset to 0).
The comparison helper accepts an optional ``v``/``V`` prefix and plain ``X.Y.Z``.

Current release: V3.2.1 (2026-11-27) — Full-English interface & AI intelligence (Traditional Chinese translation removed).
"""

APP_NAME = "TradeBot0"
APP_VERSION = "V3.2.1"
