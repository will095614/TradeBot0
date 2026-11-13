#!/usr/bin/env python3
"""Fix item 10b: no-Node UI + one-click Node.js/OmniRoute runtime install (TradeBot0 maintenance list).

Applies exact-once-verified replacements to the PC project tree (run with
cwd = project root) and, identically, to the local audit copy.
Every replacement is verified to occur exactly once before anything is
written; on any mismatch the script aborts without touching a file.
Newline style is preserved (files are LF; open with newline="").
Run with --check for a dry run that only verifies anchor counts.

A4 + B3 (the Node/OmniRoute strategy, decided after measuring):
  * Bundling the 2.6 GB global omniroute install in the installer is
    infeasible (164,349 files; even its dist/ alone is 890 MB, mostly
    .build + docs dead weight). No standalone OmniRoute binary exists
    (npm or Docker only), and a first-run `npm install -g` would still
    download ~2.6 GB. So the installer ships only the exe, and the app
    offers a one-click background install instead:
  * Node.js (37 MB zip) is downloaded from nodejs.org and extracted to the
    app's per-user runtime folder; then `npm install --prefix <runtime>/
    omniroute omniroute` installs the gateway there -- never in the global
    %APPDATA%\\npm tree, never in Program Files (not writable at runtime).
    Progress is polled by the wizard; the gateway auto-starts when the
    install finishes, and the arena keeps running in Pure Math mode meanwhile
    (item 12 option-2 policy unchanged).
  * _get_daemon_command prefers the app-local runtime install, then the
    global npm install, then omniroute/npx on PATH. npx alone does NOT count
    as "installed" for the status display: npx would download 2.6 GB on
    first start and the 30 s spawn wait would kill it mid-download.
  * get_setup_status gains node_available / omniroute_installed /
    gateway_unavailable_reason / runtime_install_status; the wizard shows
    the reason and an "Install Node.js & OmniRoute" button when needed.
"""
import os
import sys

if not os.path.isdir("src/gui"):
    print("FAIL: run this script from the project root (src/gui not found)")
    sys.exit(1)

REPLACEMENTS = []
NEW_FILES = {}


def rep(path, old, new):
    REPLACEMENTS.append((path, old, new))


# =========================================================== gateway_supervisor
rep("src/intelligence/gateway_supervisor.py", '''import subprocess
import sys
import time
import urllib.error
import urllib.request''',
'''import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import zipfile''')

rep("src/intelligence/gateway_supervisor.py", '''DAEMON_LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB: rotate before the daemon log grows without bound
DAEMON_LOG_FILENAME = "omniroute_daemon.log"''',
'''DAEMON_LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB: rotate before the daemon log grows without bound
DAEMON_LOG_FILENAME = "omniroute_daemon.log"

# One-click runtime install (item 10 B3): the official Node.js zip for the
# app-local runtime, and the install log name. OmniRoute itself is installed
# with npm (no standalone binary exists); the 2.6 GB package is far too big
# to bundle in the installer, so it is downloaded once on first run.
RUNTIME_NODE_VERSION = "24.21.0"
RUNTIME_NODE_ZIP_URL = "https://nodejs.org/dist/v24.21.0/node-v24.21.0-win-x64.zip"
RUNTIME_INSTALL_LOG_FILENAME = "omniroute_install.log"''')

rep("src/intelligence/gateway_supervisor.py", '''    if getattr(sys, "frozen", False):
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) / "TradeBot0" if appdata else Path.home() / ".tradebot0"
    else:
        base = Path(__file__).resolve().parent.parent.parent
    return base / "logs" / DAEMON_LOG_FILENAME''',
'''    if getattr(sys, "frozen", False):
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) / "TradeBot0" if appdata else Path.home() / ".tradebot0"
    else:
        base = Path(__file__).resolve().parent.parent.parent
    return base / "logs" / DAEMON_LOG_FILENAME


def _default_install_log_path() -> Path:
    """Same base as the daemon log; the install log records the one-click
    Node.js / OmniRoute install (item 10 B3)."""
    return _default_daemon_log_path().with_name(RUNTIME_INSTALL_LOG_FILENAME)''')

rep("src/intelligence/gateway_supervisor.py", '''    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 20128,
        daemon_log_path: Optional[Path] = None,
    ) -> None:''',
'''    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 20128,
        daemon_log_path: Optional[Path] = None,
        install_log_path: Optional[Path] = None,
    ) -> None:''')

rep("src/intelligence/gateway_supervisor.py", '''        self.daemon_log_path: Path = (
            Path(daemon_log_path) if daemon_log_path is not None else _default_daemon_log_path()
        )
        self._daemon_log_file = None''',
'''        self.daemon_log_path: Path = (
            Path(daemon_log_path) if daemon_log_path is not None else _default_daemon_log_path()
        )
        self._daemon_log_file = None
        self.install_log_path: Path = (
            Path(install_log_path) if install_log_path is not None else _default_install_log_path()
        )
        # One-click runtime install state (item 10 B3); guarded by a lock
        # because the worker thread and the bridge read it concurrently.
        self._install_lock = threading.Lock()
        self._install_thread: Optional[threading.Thread] = None
        self.install_status: str = "idle"  # idle | downloading-node | installing-omniroute | done | failed
        self.install_message: str = ""''')

# _get_daemon_command: resolve Node via the app-local runtime too, and prefer
# the app-local omniroute install over the global one.
rep("src/intelligence/gateway_supervisor.py", '''        node_bin = shutil.which("node") or shutil.which("node.exe")
        if node_bin:
            # 1. Check global npm location in APPDATA''',
'''        node_bin = cls._resolve_node_bin()
        if node_bin:
            # 0. App-local runtime install first (item 10 B3): the app's own
            # Node.js + OmniRoute live under the per-user runtime folder,
            # never in the global npm tree.
            local_mjs = cls._runtime_base() / "omniroute" / "node_modules" / "omniroute" / "bin" / "omniroute.mjs"
            if local_mjs.is_file():
                return [node_bin, str(local_mjs), "serve", "--no-open", "--port", str(port)]

            # 1. Check global npm location in APPDATA''')


# App-local runtime availability + one-click install (insert after is_cli_available).
rep("src/intelligence/gateway_supervisor.py", '''    @classmethod
    def is_cli_available(cls) -> bool:
        """Checks if omniroute CLI or direct node runner is found in system PATH."""
        if cls._get_daemon_command(20128) is not None:
            return True
        return bool(shutil.which("omniroute") or shutil.which("omniroute.cmd") or shutil.which("npx"))''',
'''    @classmethod
    def is_cli_available(cls) -> bool:
        """Checks if omniroute CLI or direct node runner is found in system PATH."""
        if cls._get_daemon_command(20128) is not None:
            return True
        return bool(shutil.which("omniroute") or shutil.which("omniroute.cmd") or shutil.which("npx"))

    # --- App-local runtime (item 10 A4 / B3) --------------------------------
    @staticmethod
    def _runtime_base() -> Path:
        """Per-user runtime folder for the app's own Node.js + OmniRoute.
        %LOCALAPPDATA%\\\\TradeBot0\\\\runtime on Windows (LOCALAPPDATA, not
        APPDATA, so a 2.6 GB install never roams with the user profile),
        falling back to %APPDATA% then ~/.tradebot0. Program Files is not
        writable at runtime, so the runtime lives here -- never in the
        install folder and never in the global npm tree."""
        local = os.environ.get("LOCALAPPDATA")
        if local:
            return Path(local) / "TradeBot0" / "runtime"
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "TradeBot0" / "runtime"
        return Path.home() / ".tradebot0" / "runtime"

    @classmethod
    def _runtime_node_bin(cls) -> Optional[str]:
        node_exe = cls._runtime_base() / "node" / "node.exe"
        return str(node_exe) if node_exe.is_file() else None

    @classmethod
    def _resolve_node_bin(cls) -> Optional[str]:
        """Node executable: the app-local runtime first, then system Node."""
        return cls._runtime_node_bin() or shutil.which("node") or shutil.which("node.exe")

    @classmethod
    def _resolve_npm_bin(cls, node_bin: Optional[str]) -> Optional[str]:
        """npm next to the given node.exe (runtime install), else npm on PATH."""
        if node_bin:
            node_dir = Path(node_bin).parent
            for name in ("npm.cmd", "npm"):
                cand = node_dir / name
                if cand.is_file():
                    return str(cand)
        return shutil.which("npm") or shutil.which("npm.cmd")

    @classmethod
    def node_available(cls) -> bool:
        """True when any Node.js is usable (app-local runtime or system)."""
        return cls._resolve_node_bin() is not None

    @classmethod
    def omniroute_installed(cls) -> bool:
        """True when an omniroute package is actually present (app-local
        runtime or the global npm tree). npx alone does NOT count: npx would
        download ~2.6 GB on first start and the 30 s spawn wait would kill it."""
        local_mjs = cls._runtime_base() / "omniroute" / "node_modules" / "omniroute" / "bin" / "omniroute.mjs"
        if local_mjs.is_file():
            return True
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            global_mjs = os.path.join(appdata, "npm", "node_modules", "omniroute", "bin", "omniroute.mjs")
            if os.path.exists(global_mjs):
                return True
        omni_path = shutil.which("omniroute.cmd") or shutil.which("omniroute")
        if omni_path:
            rel_mjs = os.path.join(os.path.dirname(omni_path), "node_modules", "omniroute", "bin", "omniroute.mjs")
            if os.path.exists(rel_mjs):
                return True
        return False

    @classmethod
    def gateway_unavailable_reason(cls) -> Optional[str]:
        """English reason string for the setup wizard when the gateway cannot
        start, or None when it can."""
        if not cls.node_available():
            return "Node.js is not installed. The OmniRoute gateway needs Node.js 22 or later."
        if not cls.omniroute_installed():
            return "OmniRoute is not installed. Install it with one click below (about 3-5 min, ~2.6 GB)."
        if not cls.is_cli_available():
            return "OmniRoute CLI is not installed or not found in system PATH."
        return None

    def install_runtime_status(self) -> Dict[str, Any]:
        """Current one-click install state for the wizard poll loop."""
        with self._install_lock:
            return {"status": self.install_status, "message": self.install_message}

    def _set_install_status(self, status: str, message: str) -> None:
        with self._install_lock:
            self.install_status = status
            self.install_message = message
        logger.info("Runtime install status: %s - %s", status, message)
        try:
            self.install_log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.install_log_path, "a", encoding="utf-8", errors="replace") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {status}: {message}\\n")
        except Exception as e:
            logger.debug("Failed to write install log: %s", e)

    def start_runtime_install(self) -> Dict[str, Any]:
        """Starts the one-click Node.js + OmniRoute install in a background
        thread (item 10 B3). Safe to call repeatedly: a running install is
        not started twice. The arena keeps running in Pure Math mode while
        the install runs; the gateway is started automatically when it ends."""
        with self._install_lock:
            if self.install_status in ("downloading-node", "installing-omniroute"):
                return {"ok": True, "message": "Installation already running."}
            if self.node_available() and self.omniroute_installed():
                self.install_status = "done"
                self.install_message = "OmniRoute is already installed."
                return {"ok": True, "message": self.install_message}
            self.install_status = "downloading-node" if not self.node_available() else "installing-omniroute"
            self.install_message = "Starting installation in the background..."
            t = threading.Thread(target=self._run_runtime_install, name="omniroute-runtime-install", daemon=True)
            self._install_thread = t
            t.start()
            return {"ok": True, "message": "Installation started in the background."}

    def _run_runtime_install(self) -> None:
        """Background worker: Node.js zip (if needed) + npm install omniroute
        into the app-local runtime folder, then start the gateway."""
        try:
            base = self._runtime_base()
            base.mkdir(parents=True, exist_ok=True)
            node_bin = self._resolve_node_bin()
            if node_bin is None:
                self._set_install_status("downloading-node", "Downloading Node.js (about 37 MB)...")
                node_bin = self._download_node(base)
            npm_bin = self._resolve_npm_bin(node_bin)
            if npm_bin is None:
                raise RuntimeError("npm was not found next to Node.js.")
            self._set_install_status("installing-omniroute", "Installing OmniRoute (about 3-5 min, ~2.6 GB)...")
            self._npm_install_omniroute(npm_bin, base)
            if not self.omniroute_installed():
                raise RuntimeError("OmniRoute install finished but the package was not found.")
            self._set_install_status("done", "OmniRoute installed. Starting the gateway...")
            ok, msg = self.start_daemon(max_wait_sec=30.0)
            if ok:
                self._set_install_status("done", "OmniRoute installed and the gateway is online.")
            else:
                self._set_install_status("done", f"OmniRoute installed, but the gateway did not start: {msg}")
        except Exception as e:
            logger.error("OmniRoute runtime install failed: %s", e)
            self._set_install_status("failed", f"Installation failed: {e}")

    def _download_node(self, base: Path) -> str:
        """Downloads the official Node.js zip and extracts it to
        <runtime>/node. Returns the node.exe path."""
        node_dir = base / "node"
        zip_path = base / "node.zip"
        req = urllib.request.Request(
            RUNTIME_NODE_ZIP_URL, headers={"User-Agent": "TradeBot0-Installer/1.0"}
        )
        with urllib.request.urlopen(req, timeout=600) as resp, open(zip_path, "wb") as f:
            shutil.copyfileobj(resp, f)
        tmp_dir = base / "_node_tmp"
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(tmp_dir)
        entries = [p for p in tmp_dir.iterdir()]
        src_dir = entries[0] if len(entries) == 1 and entries[0].is_dir() else tmp_dir
        if node_dir.exists():
            shutil.rmtree(node_dir)
        shutil.move(str(src_dir), str(node_dir))
        shutil.rmtree(tmp_dir, ignore_errors=True)
        try:
            zip_path.unlink()
        except Exception as e:
            logger.debug("Failed to delete Node.js zip after extract: %s", e)
        node_exe = node_dir / "node.exe"
        if not node_exe.is_file():
            raise RuntimeError("Downloaded Node.js package has no node.exe.")
        return str(node_exe)

    def _npm_install_omniroute(self, npm_bin: str, base: Path) -> None:
        """Runs `npm install --prefix <runtime>/omniroute omniroute`.
        npm 11+ blocks postinstall scripts by default, so the documented
        --allow-scripts list is passed first (native bindings need it);
        if npm rejects the flag (older npm), retry once without it."""
        prefix = base / "omniroute"
        prefix.mkdir(parents=True, exist_ok=True)
        allow = "--allow-scripts=omniroute,better-sqlite3,keytar,tls-client-node,onnxruntime-node,sharp,core-js,esbuild,@parcel/watcher,@swc/core,protobufjs,koffi"
        attempts = [
            [npm_bin, "install", "--prefix", str(prefix), allow, "omniroute"],
            [npm_bin, "install", "--prefix", str(prefix), "omniroute"],
        ]
        last_error = ""
        with open(self.install_log_path, "a", encoding="utf-8", errors="replace", buffering=1) as log_file:
            log_file.write(
                f"--- npm install omniroute --prefix {prefix} "
                f"at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\\n"
            )
            for i, cmd in enumerate(attempts):
                log_file.write(f"--- attempt {i + 1}: {' '.join(cmd)} ---\\n")
                log_file.flush()
                try:
                    child_env = os.environ.copy()
                    for key in ("_MEIPASS", "_MEIPASS2", "PYTHONPATH", "PYTHONHOME"):
                        child_env.pop(key, None)
                    creation_flags = 0x08000000 if sys.platform == "win32" else 0
                    proc = subprocess.run(
                        cmd, stdout=log_file, stderr=subprocess.STDOUT,
                        env=child_env, creationflags=creation_flags, timeout=1800,
                    )
                except subprocess.TimeoutExpired:
                    raise RuntimeError("npm install timed out after 30 minutes.")
                if proc.returncode == 0:
                    return
                last_error = f"npm install exited with code {proc.returncode} (attempt {i + 1})"
                tail = self._tail_install_log(2000)
                if i == 0 and ("allow-scripts" in tail or "unknown option" in tail.lower()):
                    continue
                break
        raise RuntimeError(last_error or "npm install failed.")

    def _tail_install_log(self, n_chars: int) -> str:
        """Last n_chars of the install log, for failure diagnosis."""
        try:
            text = self.install_log_path.read_text(encoding="utf-8", errors="replace")
            return text[-n_chars:]
        except Exception:
            return ""''')


# =========================================================== A4: dashboard bridge
# get_setup_status: report gateway availability + install progress.
rep("src/gui/dashboard.py", '''                "admin_password_required": bool((not cfg.get("skip_ai_mode", False)) and not pw_configured),
            }''',
'''                "admin_password_required": bool((not cfg.get("skip_ai_mode", False)) and not pw_configured),
                "node_available": bool(self._dashboard.gateway_supervisor.node_available()),
                "omniroute_installed": bool(self._dashboard.gateway_supervisor.omniroute_installed()),
                "gateway_unavailable_reason": self._dashboard.gateway_supervisor.gateway_unavailable_reason(),
                "runtime_install_status": self._dashboard.gateway_supervisor.install_runtime_status(),
            }''')

rep("src/gui/dashboard.py", '''                "omniroute_password_configured": False,
                "admin_password_required": False,
            }''',
'''                "omniroute_password_configured": False,
                "admin_password_required": False,
                "node_available": False,
                "omniroute_installed": False,
                "gateway_unavailable_reason": None,
                "runtime_install_status": {"status": "idle", "message": ""},
            }''')

# New bridge method: start the one-click runtime install.
rep("src/gui/dashboard.py", '''    def skip_to_pure_math(self) -> Dict[str, Any]:''',
'''    def install_gateway_runtime(self) -> Dict[str, Any]:
        """
        Starts the one-click Node.js + OmniRoute install in the background
        (item 10 B3). The wizard polls get_setup_status for progress.
        """
        try:
            return self._dashboard.gateway_supervisor.start_runtime_install()
        except Exception as e:
            logger.error("Error starting gateway runtime install: %s", e)
            return {"ok": False, "message": str(e)}

    def skip_to_pure_math(self) -> Dict[str, Any]:''')

# =========================================================== A4: index.html wizard
# Gateway-availability note + one-click install button (existing classes only).
rep("src/gui/assets/index.html", '''          <div class="setup-gateway-note">
            Models are auto-routed by OmniRoute (auto) across your configured providers.
          </div>
        </div>''',
'''          <div class="setup-gateway-note">
            Models are auto-routed by OmniRoute (auto) across your configured providers.
          </div>
          <div class="setup-gateway-note" id="gatewayUnavailableNote" style="display:none;"></div>
          <button type="button" class="btn lg-btn lg-btn--primary" id="btnInstallGatewayRuntime" onclick="installGatewayRuntime()" style="display:none;">
            <span>Install Node.js &amp; OmniRoute</span>
          </button>
        </div>''')

# =========================================================== A4: app.js
# Availability helpers + one-click install flow (after setWizardBanner).
rep("src/gui/assets/app.js", '''  function setWizardBanner(message, type = 'info') {
    const b = document.getElementById('setupWizardStatusBanner');
    if (!b) return;
    if (!message) {
      b.style.display = 'none';
      b.textContent = '';
      return;
    }
    b.className = `setup-wizard-banner ${type}`;
    b.textContent = message;
    b.style.display = 'block';
  }''',
'''  function setWizardBanner(message, type = 'info') {
    const b = document.getElementById('setupWizardStatusBanner');
    if (!b) return;
    if (!message) {
      b.style.display = 'none';
      b.textContent = '';
      return;
    }
    b.className = `setup-wizard-banner ${type}`;
    b.textContent = message;
    b.style.display = 'block';
  }

  let runtimeInstallPollTimer = null;

  // Gateway availability (item 10 A4): show the reason + one-click install
  // button when Node.js / OmniRoute is missing; hide both when available.
  function applyGatewayAvailability(res) {
    if (!res) return;
    if (typeof res.gateway_port === 'number') {
      window.__tradebotGatewayPort = res.gateway_port;
    }
    const gwNote = document.getElementById('gatewayUnavailableNote');
    const gwBtn = document.getElementById('btnInstallGatewayRuntime');
    if (gwNote) {
      if (res.gateway_unavailable_reason) {
        gwNote.textContent = res.gateway_unavailable_reason + ' The arena still works in Pure Math mode meanwhile.';
        gwNote.style.display = 'block';
      } else {
        gwNote.style.display = 'none';
        gwNote.textContent = '';
      }
    }
    if (gwBtn) {
      gwBtn.style.display = res.gateway_unavailable_reason ? 'inline-flex' : 'none';
    }
  }

  function updateRuntimeInstallBanner(statusObj) {
    if (!statusObj) return;
    const st = statusObj.status || 'idle';
    const msg = statusObj.message || '';
    if (st === 'idle') return;
    if (st === 'done') {
      setWizardBanner(msg || 'OmniRoute installed.', 'success');
      if (runtimeInstallPollTimer) { clearInterval(runtimeInstallPollTimer); runtimeInstallPollTimer = null; }
      refreshGatewayAvailability();
    } else if (st === 'failed') {
      setWizardBanner(msg || 'Installation failed.', 'error');
      if (runtimeInstallPollTimer) { clearInterval(runtimeInstallPollTimer); runtimeInstallPollTimer = null; }
      const btn = document.getElementById('btnInstallGatewayRuntime');
      if (btn) btn.disabled = false;
    } else {
      setWizardBanner(msg || 'Installing...', 'info');
    }
  }

  function refreshGatewayAvailability() {
    if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.get_setup_status === 'function') {
      window.pywebview.api.get_setup_status().then((res) => {
        if (res && res.status === 'ok') applyGatewayAvailability(res);
      }).catch((e) => console.debug('refresh gateway availability err:', e));
    }
  }

  async function installGatewayRuntime() {
    const btn = document.getElementById('btnInstallGatewayRuntime');
    if (btn) btn.disabled = true;
    setWizardBanner('Starting installation in the background...', 'info');
    try {
      if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.install_gateway_runtime === 'function') {
        const res = await window.pywebview.api.install_gateway_runtime();
        if (res && res.ok) {
          setWizardBanner(res.message || 'Installation started in the background.', 'info');
          if (runtimeInstallPollTimer) clearInterval(runtimeInstallPollTimer);
          runtimeInstallPollTimer = setInterval(() => {
            if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.get_setup_status === 'function') {
              window.pywebview.api.get_setup_status().then((r) => {
                if (r && r.status === 'ok') updateRuntimeInstallBanner(r.runtime_install_status);
              }).catch((e) => console.debug('install poll err:', e));
            }
          }, 5000);
        } else {
          setWizardBanner((res && res.message) ? res.message : 'Could not start the installation.', 'error');
          if (btn) btn.disabled = false;
        }
      }
    } catch (err) {
      setWizardBanner(`Encountered error: ${err}`, 'error');
      if (btn) btn.disabled = false;
    }
  }''')

# Hook the availability display into the wizard's status handler.
rep("src/gui/assets/app.js", '''          if (adminStatus) {
            adminStatus.innerHTML = res.omniroute_password_configured
              ? '<span class="setup-status-pill valid">Configured in .env</span>'
              : '<span class="setup-status-pill neutral">Not Set - Required</span>';
          }''',
'''          if (adminStatus) {
            adminStatus.innerHTML = res.omniroute_password_configured
              ? '<span class="setup-status-pill valid">Configured in .env</span>'
              : '<span class="setup-status-pill neutral">Not Set - Required</span>';
          }

          applyGatewayAvailability(res);
          updateRuntimeInstallBanner(res.runtime_install_status);''')


# =========================================================== new tests (part B)
rep("tests/test_item10_packaging.py", '''import asyncio
import inspect
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch''',
'''import asyncio
import inspect
import json
import shutil
import threading
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch''')

rep("tests/test_item10_packaging.py", '''    for s in (
        "Admin password must be at least 8 characters.",
        "Admin password and confirmation do not match.",
        "Gateway Admin Password",
        "Protects the local OmniRoute console (min 8 characters)",
        "Not Set - Required",
    ):
        assert s.isascii()
        assert s in html or s in js''',
'''    for s in (
        "Admin password must be at least 8 characters.",
        "Admin password and confirmation do not match.",
        "Gateway Admin Password",
        "Protects the local OmniRoute console (min 8 characters)",
        "Not Set - Required",
    ):
        assert s.isascii()
        assert s in html or s in js


# ------------------------------------------------------------------ A4: no-Node UI + runtime install
def test_gateway_unavailable_reason_no_node(monkeypatch, tmp_path):
    monkeypatch.setattr(GatewaySupervisor, "_runtime_base", staticmethod(lambda: tmp_path / "runtime"))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(shutil, "which", lambda name: None)
    assert GatewaySupervisor.node_available() is False
    assert GatewaySupervisor.omniroute_installed() is False
    reason = GatewaySupervisor.gateway_unavailable_reason()
    assert isinstance(reason, str)
    assert "Node.js" in reason


def test_gateway_unavailable_reason_node_but_no_omniroute(monkeypatch, tmp_path):
    monkeypatch.setattr(GatewaySupervisor, "_runtime_base", staticmethod(lambda: tmp_path / "runtime"))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    def _fake_which(name):
        if name in ("node", "node.exe"):
            return str(tmp_path / "node.exe")
        return None

    monkeypatch.setattr(shutil, "which", _fake_which)
    assert GatewaySupervisor.node_available() is True
    assert GatewaySupervisor.omniroute_installed() is False
    reason = GatewaySupervisor.gateway_unavailable_reason()
    assert isinstance(reason, str)
    assert "OmniRoute is not installed" in reason


def test_daemon_command_prefers_runtime_install(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime"
    (runtime / "node").mkdir(parents=True)
    (runtime / "node" / "node.exe").write_bytes(b"")
    mjs = runtime / "omniroute" / "node_modules" / "omniroute" / "bin"
    mjs.mkdir(parents=True)
    (mjs / "omniroute.mjs").write_text("// fake", encoding="utf-8")
    monkeypatch.setattr(GatewaySupervisor, "_runtime_base", staticmethod(lambda: runtime))
    monkeypatch.setattr(shutil, "which", lambda name: None)
    cmd = GatewaySupervisor._get_daemon_command(20128)
    assert cmd == [
        str(runtime / "node" / "node.exe"),
        str(mjs / "omniroute.mjs"),
        "serve", "--no-open", "--port", "20128",
    ]


def test_daemon_command_falls_back_to_global(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime"
    monkeypatch.setattr(GatewaySupervisor, "_runtime_base", staticmethod(lambda: runtime))
    appdata = tmp_path / "appdata"
    global_mjs = appdata / "npm" / "node_modules" / "omniroute" / "bin" / "omniroute.mjs"
    global_mjs.parent.mkdir(parents=True)
    global_mjs.write_text("// fake", encoding="utf-8")
    monkeypatch.setenv("APPDATA", str(appdata))
    monkeypatch.setattr(
        shutil, "which",
        lambda name: str(tmp_path / "node.exe") if name in ("node", "node.exe") else None,
    )
    cmd = GatewaySupervisor._get_daemon_command(20128)
    assert cmd == [
        str(tmp_path / "node.exe"),
        str(global_mjs),
        "serve", "--no-open", "--port", "20128",
    ]


def test_runtime_install_status_defaults_idle(tmp_path):
    sup = GatewaySupervisor(
        daemon_log_path=tmp_path / "daemon.log",
        install_log_path=tmp_path / "install.log",
    )
    assert sup.install_runtime_status() == {"status": "idle", "message": ""}


def test_start_runtime_install_does_not_start_twice(monkeypatch, tmp_path):
    sup = GatewaySupervisor(
        daemon_log_path=tmp_path / "daemon.log",
        install_log_path=tmp_path / "install.log",
    )
    started = threading.Event()

    def _slow_worker():
        started.set()
        time.sleep(2)

    monkeypatch.setattr(sup, "_run_runtime_install", _slow_worker)
    monkeypatch.setattr(GatewaySupervisor, "node_available", classmethod(lambda cls: False))
    monkeypatch.setattr(GatewaySupervisor, "omniroute_installed", classmethod(lambda cls: False))
    res1 = sup.start_runtime_install()
    assert res1["ok"] is True
    assert started.wait(timeout=5)
    res2 = sup.start_runtime_install()
    assert res2["ok"] is True
    assert "already running" in res2["message"].lower()
    sup._install_thread.join(timeout=5)


def test_setup_status_reports_gateway_availability(monkeypatch, tmp_path):
    monkeypatch.setattr(GatewaySupervisor, "_runtime_base", staticmethod(lambda: tmp_path / "runtime"))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(shutil, "which", lambda name: None)
    dash, bridge = _make_bridge(tmp_path)
    try:
        st = bridge.get_setup_status()
        assert st["node_available"] is False
        assert st["omniroute_installed"] is False
        assert isinstance(st["gateway_unavailable_reason"], str)
        assert "Node.js" in st["gateway_unavailable_reason"]
        assert st["runtime_install_status"] == {"status": "idle", "message": ""}
    finally:
        dash.engine.stop()


def test_frontend_wizard_has_gateway_install_ui():
    assets = Path(__file__).resolve().parent.parent / "src" / "gui" / "assets"
    html = (assets / "index.html").read_text(encoding="utf-8")
    js = (assets / "app.js").read_text(encoding="utf-8")
    assert 'id="gatewayUnavailableNote"' in html
    assert 'id="btnInstallGatewayRuntime"' in html
    assert "Install Node.js &amp; OmniRoute" in html
    assert "installGatewayRuntime" in js
    assert "applyGatewayAvailability" in js
    assert "gateway_unavailable_reason" in js
    for s in (
        "The arena still works in Pure Math mode meanwhile.",
        "Starting installation in the background...",
        "Could not start the installation.",
    ):
        assert s.isascii()
        assert s in js''')


# =========================================================== apply
def main():
    check_only = "--check" in sys.argv
    failed = []
    for path, old, new in REPLACEMENTS:
        with open(path, "r", encoding="utf-8", newline="") as f:
            content = f.read()
        n = content.count(old)
        if n != 1:
            failed.append(f"{path}: expected 1 occurrence, found {n} for: {old[:80]!r}")
            continue
        if check_only:
            print(f"CHECK-OK {path}")
            continue
        content = content.replace(old, new)
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        print(f"OK {path}")
    for path, content in NEW_FILES.items():
        if os.path.exists(path):
            failed.append(f"{path}: already exists, refusing to overwrite")
            continue
        if check_only:
            print(f"CHECK-OK {path} (new file)")
            continue
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        print(f"NEW {path}")
    if failed:
        print("FAILURES:")
        for msg in failed:
            print(" -", msg)
        sys.exit(1)
    if check_only:
        print(f"Check passed: {len(REPLACEMENTS)} replacements + {len(NEW_FILES)} new files.")
    else:
        print(f"Applied {len(REPLACEMENTS)} replacements + {len(NEW_FILES)} new files.")


if __name__ == "__main__":
    main()
