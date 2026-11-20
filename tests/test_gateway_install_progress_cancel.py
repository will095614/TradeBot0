"""Tests for the setup-wizard install progress bar and cancel path.

Covers gateway_supervisor progress reporting (real Content-Length percent
for the Node.js download, indeterminate when Content-Length is absent, and
estimated 0-99% from real written bytes during the OmniRoute npm install)
and the cancel_runtime_install path (worker stops, partial artifacts
removed, omniroute_installed() never misreports a half-installed package).
All network/subprocess access is mocked; zero real downloads.
"""
import io
import shutil
import threading
import time
import zipfile
from pathlib import Path
from unittest.mock import patch

from src.gui.dashboard import ArenaDashboard, _ArenaBridgeApi
from src.intelligence.config_manager import ConfigManager
from src.intelligence.gateway_supervisor import GatewaySupervisor


def _make_supervisor(tmp_path):
    return GatewaySupervisor(
        daemon_log_path=tmp_path / "daemon.log",
        install_log_path=tmp_path / "install.log",
    )


class _FakeDownloadResp:
    """Chunked fake for urllib responses: at most chunk_size per read."""

    def __init__(self, payload, total_header=True, chunk_size=1000):
        self._buf = io.BytesIO(payload)
        self.chunk_size = chunk_size
        self.headers = {"Content-Length": str(len(payload))} if total_header else {}

    def read(self, n=-1):
        if n and n > 0:
            return self._buf.read(min(self.chunk_size, n))
        return self._buf.read(self.chunk_size)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _SlowResp(_FakeDownloadResp):
    """Each chunk takes 0.05 s so a cancel can land mid-download."""

    def read(self, n=-1):
        time.sleep(0.05)
        return super().read(n)


class _FakeProc:
    """Fake Popen that runs until kill() is called."""

    def __init__(self, *args, **kwargs):
        self._killed = False
        self.returncode = None
        self.pid = 12345

    def poll(self):
        return -9 if self._killed else None

    def kill(self):
        self._killed = True
        self.returncode = -9

    def wait(self, timeout=None):
        return self.returncode


def _fake_node_zip_bytes():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("node-v24.21.0-win-x64/node.exe", b"fake-node")
    return buf.getvalue()


def _wait_for_status(sup, wanted, timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if sup.install_status == wanted:
            return True
        time.sleep(0.05)
    return False


def test_install_runtime_status_includes_progress_fields(tmp_path):
    sup = _make_supervisor(tmp_path)
    st = sup.install_runtime_status()
    assert st == {"status": "idle", "message": "", "progress": None, "phase": ""}


def test_node_download_reports_real_percent(tmp_path, monkeypatch):
    sup = _make_supervisor(tmp_path)
    recorded = []
    monkeypatch.setattr(sup, "_set_install_progress", recorded.append)
    payload = _fake_node_zip_bytes()
    base = tmp_path / "runtime"
    base.mkdir(parents=True)
    with patch("urllib.request.urlopen",
               return_value=_FakeDownloadResp(payload, chunk_size=max(1, len(payload) // 4))):
        result = sup._download_node(base)
    assert result == str(base / "node" / "node.exe")
    assert (base / "node" / "node.exe").is_file()
    assert recorded[-1] == 100
    assert recorded == sorted(recorded)
    assert len(set(recorded)) >= 3  # several increasing steps, not a single jump


def test_node_download_without_content_length_is_indeterminate(tmp_path, monkeypatch):
    sup = _make_supervisor(tmp_path)
    recorded = []
    monkeypatch.setattr(sup, "_set_install_progress", recorded.append)
    payload = _fake_node_zip_bytes()
    base = tmp_path / "runtime"
    base.mkdir(parents=True)
    with patch("urllib.request.urlopen",
               return_value=_FakeDownloadResp(payload, total_header=False)):
        result = sup._download_node(base)
    assert result == str(base / "node" / "node.exe")
    # No intermediate percent without a total; only the final 100 on completion.
    assert recorded == [100]


def test_cancel_when_idle_returns_not_running(tmp_path):
    sup = _make_supervisor(tmp_path)
    res = sup.cancel_runtime_install()
    assert res["ok"] is False
    assert sup.install_status == "idle"


def test_cancel_during_node_download(tmp_path, monkeypatch):
    sup = _make_supervisor(tmp_path)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(GatewaySupervisor, "_resolve_node_bin", classmethod(lambda cls: None))
    monkeypatch.setattr(shutil, "which", lambda name: None)
    payload = b"x" * 1000000
    with patch("urllib.request.urlopen", return_value=_SlowResp(payload)):
        t = threading.Thread(target=sup._run_runtime_install, daemon=True)
        t.start()
        assert _wait_for_status(sup, "downloading-node")
        res = sup.cancel_runtime_install()
        assert res["ok"] is True
        t.join(timeout=10)
        assert not t.is_alive()
    assert sup.install_status == "cancelled"
    assert not (tmp_path / "TradeBot0" / "runtime" / "node.zip").exists()
    assert sup.omniroute_installed() is False


def test_cancel_during_npm_install_removes_partial_package(tmp_path, monkeypatch):
    sup = _make_supervisor(tmp_path)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(GatewaySupervisor, "_resolve_node_bin",
                        classmethod(lambda cls: str(tmp_path / "node.exe")))
    monkeypatch.setattr(GatewaySupervisor, "_resolve_npm_bin",
                        classmethod(lambda cls, node_bin=None: str(tmp_path / "npm.cmd")))
    monkeypatch.setattr(shutil, "which", lambda name: None)
    runtime = tmp_path / "TradeBot0" / "runtime"
    partial_mjs = runtime / "omniroute" / "node_modules" / "omniroute" / "bin" / "omniroute.mjs"
    partial_mjs.parent.mkdir(parents=True)
    partial_mjs.write_text("// partial", encoding="utf-8")
    # Pre-cancel the .mjs exists, so omniroute_installed() would misreport
    # the half-installed package as good if cancel left it behind.
    assert sup.omniroute_installed() is True
    with patch("subprocess.Popen", _FakeProc):
        t = threading.Thread(target=sup._run_runtime_install, daemon=True)
        t.start()
        assert _wait_for_status(sup, "installing-omniroute")
        res = sup.cancel_runtime_install()
        assert res["ok"] is True
        t.join(timeout=10)
        assert not t.is_alive()
    assert sup.install_status == "cancelled"
    assert not (runtime / "omniroute").exists()
    assert sup.omniroute_installed() is False


def test_restart_after_cancel(tmp_path, monkeypatch):
    sup = _make_supervisor(tmp_path)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(GatewaySupervisor, "_resolve_node_bin", classmethod(lambda cls: None))
    monkeypatch.setattr(shutil, "which", lambda name: None)
    payload = b"x" * 1000000
    with patch("urllib.request.urlopen", return_value=_SlowResp(payload)):
        t = threading.Thread(target=sup._run_runtime_install, daemon=True)
        t.start()
        assert _wait_for_status(sup, "downloading-node")
        assert sup.cancel_runtime_install()["ok"] is True
        t.join(timeout=10)
        assert sup.install_status == "cancelled"
        # Restart via the public entry point; the cancel event must be reset.
        res = sup.start_runtime_install()
        assert res["ok"] is True
        assert sup.install_status == "downloading-node"
        assert not sup._install_cancel_event.is_set()
        # Stop the restarted worker so the test leaves no thread behind.
        assert sup.cancel_runtime_install()["ok"] is True
        sup._install_thread.join(timeout=10)
        assert sup.install_status == "cancelled"


def test_bridge_cancel_and_status_shape(tmp_path):
    dash = ArenaDashboard()
    try:
        dash.config_manager = ConfigManager(
            data_dir=tmp_path / "data",
            omni_env_path=tmp_path / ".omniroute" / ".env",
        )
        dash.gateway_supervisor = _make_supervisor(tmp_path)
        bridge = _ArenaBridgeApi(dash)
        res = bridge.cancel_gateway_runtime_install()
        assert res["ok"] is False
        st = bridge.get_setup_status()
        assert st["runtime_install_status"] == {
            "status": "idle", "message": "", "progress": None, "phase": "",
        }
    finally:
        dash.engine.stop()


def test_frontend_progress_bar_and_cancel_confirm_ids():
    """DOM parity: every new getElementById id exists in index.html, and the
    confirm dialog + progress bar reuse the existing modal tokens."""
    assets = Path(__file__).resolve().parent.parent / "src" / "gui" / "assets"
    html = (assets / "index.html").read_text(encoding="utf-8")
    js = (assets / "app.js").read_text(encoding="utf-8")
    css = (assets / "app.css").read_text(encoding="utf-8")
    for element_id in ["setupInstallProgress", "setupInstallProgressFill",
                       "installCancelConfirmModal"]:
        assert 'id="%s"' % element_id in html
    for fn in ["requestCloseSetupWizardModal", "confirmCancelInstallAndClose",
               "openInstallCancelConfirm", "closeInstallCancelConfirm",
               "cancel_gateway_runtime_install"]:
        assert fn in js
    assert "Closing the setup wizard will interrupt the download" in html
    assert ".setup-install-progress" in css
    assert ".install-cancel-confirm-overlay" in css
    assert "setup-install-progress-slide" in css
    modal_block = css.split(".setup-wizard-modal {", 1)[1].split("}", 1)[0]
    assert "overflow-y: hidden" in modal_block
    assert "max-height: 92vh" in modal_block


def test_wizard_two_column_fixed_layout():
    """Two-column wizard (2026-11-14, user-approved mockup): the modal is a
    two-column grid, the 1040px scroll fallback is gone, every dynamic
    element reserves a fixed-height slot (visibility, never display: none),
    and the dynamic regions carry transitions so any residual shift
    animates instead of jumping."""
    assets = Path(__file__).resolve().parent.parent / "src" / "gui" / "assets"
    html = (assets / "index.html").read_text(encoding="utf-8")
    js = (assets / "app.js").read_text(encoding="utf-8")
    css = (assets / "app.css").read_text(encoding="utf-8")

    # Two columns: keys left, gateway right; the actions row still spans
    # both columns below the grid (unchanged).
    assert html.count('class="setup-wizard-column"') == 2
    assert ".setup-wizard-column" in css
    assert "grid-template-columns: minmax(0, 1fr) minmax(0, 1fr)" in css
    modal_block = css.split(".setup-wizard-modal {", 1)[1].split("}", 1)[0]
    assert "width: 1080px" in modal_block
    assert "gap: 0" in modal_block
    assert "overflow-y: hidden" in modal_block
    assert "max-height: 92vh" in modal_block

    # No scroll fallback at any height: the 1040px media query is gone, and
    # the compact-mode block (720px) tightens spacing without overflow.
    assert "@media (max-height: 1040px)" not in css
    assert "@media (max-height: 720px)" in css
    compact = css.split("@media (max-height: 720px)", 1)[1].split("@media", 1)[0]
    assert "overflow" not in compact

    # Fixed slots: the four dynamic elements no longer carry an inline
    # display:none, and their CSS hides them with visibility + opacity.
    for frag in ['id="gatewayUnavailableNote" style="display:none;"',
                 'id="btnInstallGatewayRuntime" onclick="installGatewayRuntime()" style="display:none;"',
                 'id="setupWizardStatusBanner" class="setup-wizard-banner" style="display:none;"',
                 'id="setupInstallProgress" class="setup-install-progress" style="display:none;"']:
        assert frag not in html
    for sel in ["#gatewayUnavailableNote", "#btnInstallGatewayRuntime"]:
        rule = css.split(sel + " {", 1)[1].split("}", 1)[0]
        assert "visibility: hidden" in rule
        assert "opacity: 0" in rule
    banner_rule = css.split(".setup-wizard-banner {", 1)[1].split("}", 1)[0]
    assert "visibility: hidden" in banner_rule
    assert "min-height: 48px" in banner_rule
    assert "opacity 0.25s var(--lg-spring)" in banner_rule
    prog_rule = css.split(".setup-install-progress {", 1)[1].split("}", 1)[0]
    assert "visibility: hidden" in prog_rule
    assert "min-height: 8px" in prog_rule
    assert "gwNote.style.display" not in js
    assert "gwBtn.style.display" not in js
    assert "prog.style.display" not in js
    assert "b.style.display" not in js
    assert "b.style.visibility" in js
    assert "gwNote.style.visibility" in js
    assert "gwBtn.style.visibility" in js
    assert "prog.style.visibility" in js

    # Long text cannot grow a slot: pills truncate to one line, the test
    # button has a fixed width, the gateway note and banner clamp to two.
    pill_rule = css.split(".setup-status-pill {", 1)[1].split("}", 1)[0]
    assert "text-overflow: ellipsis" in pill_rule
    assert "white-space: nowrap" in pill_rule
    test_btn_rule = css.split(".setup-test-btn {", 1)[1].split("}", 1)[0]
    assert "width: 64px" in test_btn_rule
    note_rule = css.split("#gatewayUnavailableNote {", 1)[1].split("}", 1)[0]
    assert "-webkit-line-clamp: 2" in note_rule
    assert "min-height: 29px" in note_rule
    assert "-webkit-line-clamp: 2" in banner_rule


def _setup_npm_only_env(tmp_path, monkeypatch, expected_bytes):
    import src.intelligence.gateway_supervisor as gs_mod

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(GatewaySupervisor, "_resolve_node_bin",
                        classmethod(lambda cls: str(tmp_path / "node.exe")))
    monkeypatch.setattr(GatewaySupervisor, "_resolve_npm_bin",
                        classmethod(lambda cls, node_bin=None: str(tmp_path / "npm.cmd")))
    monkeypatch.setattr(shutil, "which", lambda name: None)
    monkeypatch.setattr(gs_mod, "RUNTIME_OMNIROUTE_EXPECTED_BYTES", expected_bytes)
    monkeypatch.setattr(gs_mod, "RUNTIME_OMNIROUTE_PROGRESS_INTERVAL_SEC", 0.02)
    return tmp_path / "TradeBot0" / "runtime"


def _wait_until(pred, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if pred():
            return True
        time.sleep(0.02)
    return False


def test_npm_install_reports_growing_determinate_progress(tmp_path, monkeypatch):
    """During installing-omniroute, progress tracks real written bytes in [0, 99],
    is None-free and non-decreasing, and reaches 100 only at done."""
    sup = _make_supervisor(tmp_path)
    runtime = _setup_npm_only_env(tmp_path, monkeypatch, expected_bytes=10_000)
    prefix = runtime / "omniroute"

    observed_during_npm = []
    orig_set_progress = sup._set_install_progress

    def spy_set_progress(progress, message=None):
        orig_set_progress(progress, message=message)
        st = sup.install_runtime_status()
        if st["status"] == "installing-omniroute":
            observed_during_npm.append(st["progress"])

    monkeypatch.setattr(sup, "_set_install_progress", spy_set_progress)
    monkeypatch.setattr(sup, "start_daemon", lambda max_wait_sec=30.0: (True, "ok"))

    class _StagedNpmProc:
        def __init__(self, *args, **kwargs):
            self.returncode = None
            self.pid = 22345
            self._worker = threading.Thread(target=self._populate, daemon=True)
            self._worker.start()

        def _populate(self):
            (prefix / "pkg_a.bin").write_bytes(b"a" * 2_000)
            assert _wait_until(lambda: (sup.install_runtime_status()["progress"] or 0) >= 20)
            (prefix / "pkg_b.bin").write_bytes(b"b" * 3_000)
            assert _wait_until(lambda: (sup.install_runtime_status()["progress"] or 0) >= 50)
            (prefix / "pkg_c.bin").write_bytes(b"c" * 3_000)
            assert _wait_until(lambda: (sup.install_runtime_status()["progress"] or 0) >= 80)
            mjs = prefix / "node_modules" / "omniroute" / "bin" / "omniroute.mjs"
            mjs.parent.mkdir(parents=True, exist_ok=True)
            mjs.write_text("// ready", encoding="utf-8")
            self.returncode = 0

        def poll(self):
            return self.returncode

        def kill(self):
            self.returncode = -9

        def wait(self, timeout=None):
            return self.returncode

    with patch("subprocess.Popen", _StagedNpmProc):
        sup._run_runtime_install()

    assert observed_during_npm, "expected progress updates during installing-omniroute"
    assert all(isinstance(p, int) for p in observed_during_npm)
    assert all(0 <= p <= 99 for p in observed_during_npm)
    assert observed_during_npm == sorted(observed_during_npm)
    assert len(set(observed_during_npm)) >= 3
    final = sup.install_runtime_status()
    assert final["status"] == "done"
    assert final["progress"] == 100


def test_npm_install_clamps_at_99_until_exit_zero(tmp_path, monkeypatch):
    """If written bytes exceed the ~2.6 GB estimate, progress clamps at 99 until
    npm exits 0; 100 appears only on real success (done)."""
    sup = _make_supervisor(tmp_path)
    runtime = _setup_npm_only_env(tmp_path, monkeypatch, expected_bytes=1_000)
    prefix = runtime / "omniroute"
    mid_status = {}

    monkeypatch.setattr(sup, "start_daemon", lambda max_wait_sec=30.0: (True, "ok"))

    class _OverflowProc:
        def __init__(self, *args, **kwargs):
            self.returncode = None
            self.pid = 22346
            threading.Thread(target=self._populate, daemon=True).start()

        def _populate(self):
            (prefix / "oversize.bin").write_bytes(b"x" * 2_500)
            assert _wait_until(lambda: sup.install_runtime_status()["progress"] == 99)
            mid_status.update(sup.install_runtime_status())
            mjs = prefix / "node_modules" / "omniroute" / "bin" / "omniroute.mjs"
            mjs.parent.mkdir(parents=True, exist_ok=True)
            mjs.write_text("// ready", encoding="utf-8")
            self.returncode = 0

        def poll(self):
            return self.returncode

        def kill(self):
            self.returncode = -9

        def wait(self, timeout=None):
            return self.returncode

    with patch("subprocess.Popen", _OverflowProc):
        sup._run_runtime_install()

    assert mid_status["status"] == "installing-omniroute"
    assert mid_status["progress"] == 99
    final = sup.install_runtime_status()
    assert final["status"] == "done"
    assert final["progress"] == 100


def test_npm_install_progress_monotonic_if_dir_shrinks(tmp_path, monkeypatch):
    """Temporary staging deletions by npm must never make progress go backwards."""
    sup = _make_supervisor(tmp_path)
    runtime = _setup_npm_only_env(tmp_path, monkeypatch, expected_bytes=1_000)
    prefix = runtime / "omniroute"
    after_shrink_samples = []

    monkeypatch.setattr(sup, "start_daemon", lambda max_wait_sec=30.0: (True, "ok"))

    class _ShrinkProc:
        def __init__(self, *args, **kwargs):
            self.returncode = None
            self.pid = 22347
            threading.Thread(target=self._populate, daemon=True).start()

        def _populate(self):
            big = prefix / "stage.bin"
            big.write_bytes(b"z" * 600)
            assert _wait_until(lambda: (sup.install_runtime_status()["progress"] or 0) >= 60)
            big.write_bytes(b"z" * 200)
            # Let at least one more measurement poll tick run while directory is smaller.
            for _ in range(8):
                time.sleep(0.05)
                after_shrink_samples.append(sup.install_runtime_status()["progress"])
            mjs = prefix / "node_modules" / "omniroute" / "bin" / "omniroute.mjs"
            mjs.parent.mkdir(parents=True, exist_ok=True)
            mjs.write_text("// ready", encoding="utf-8")
            self.returncode = 0

        def poll(self):
            return self.returncode

        def kill(self):
            self.returncode = -9

        def wait(self, timeout=None):
            return self.returncode

    with patch("subprocess.Popen", _ShrinkProc):
        sup._run_runtime_install()

    assert after_shrink_samples
    assert all(p >= 60 and p <= 99 for p in after_shrink_samples)


def test_omniroute_eta_message_formatting():
    import src.intelligence.gateway_supervisor as gs_mod

    fmt = GatewaySupervisor._format_omniroute_progress_message
    base = gs_mod.RUNTIME_OMNIROUTE_BASE_MESSAGE

    # Before 10s or at 0%: show base message with no ETA guess.
    assert fmt(20, 200, 200, 5.0, 1000) == base
    assert fmt(0, 0, 0, 15.0, 1000) == base

    # Plausible remaining time in seconds and minutes.
    assert fmt(40, 400, 400, 20.0, 1000) == "Installing OmniRoute — 40% (~30 s left)"
    assert fmt(40, 400, 400, 80.0, 1000) == "Installing OmniRoute — 40% (~2 min left)"

    # Zero throughput, exceeded expected total, or >1h ETA: omit ETA cleanly.
    assert fmt(40, 0, 400, 20.0, 1000) == "Installing OmniRoute — 40%"
    assert fmt(99, 1200, 1200, 30.0, 1000) == "Installing OmniRoute — 99%"
    assert fmt(1, 1, 10, 100.0, 10_000) == "Installing OmniRoute — 1%"


def test_frontend_banner_does_not_duplicate_embedded_percent():
    assets = Path(__file__).resolve().parent.parent / "src" / "gui" / "assets"
    js = (assets / "app.js").read_text(encoding="utf-8")
    # 5-second poll interval stays unchanged.
    assert "}, 5000);" in js
    # Banner formatter checks whether the backend message already carries pct%.
    fn_block = js.split("function updateRuntimeInstallBanner", 1)[1].split("function stopSaveLaunchPoll", 1)[0]
    assert "new RegExp('(?:^|\\\\D)' + pct + '%').test(msg)" in fn_block

