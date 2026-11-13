"""TradeBot0 version — single source of truth.

The application version lives here and nowhere else. The Inno Setup
installer (TradeBot0.iss, MyAppVersion) must be kept in sync by hand at
release time: bump APP_VERSION here and MyAppVersion there to the same
value. The in-app update checker (src/update_checker.py) compares the
running version against the manifest version using this constant.

Version scheme: date-based ``YYYY.MM.DD`` (e.g. "2026.11.13"), matching
the installer version. A ``v`` prefix and ``X.Y.Z`` semver strings are
also accepted by the comparison helper, but releases use the date form.
"""

APP_NAME = "TradeBot0"
APP_VERSION = "2026.11.13"
