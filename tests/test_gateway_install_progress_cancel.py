"""Tests for the setup-wizard install progress bar and cancel path.

Covers gateway_supervisor progress reporting (real percent only for the
Node.js download; the npm phase is honestly indeterminate) and the
cancel_runtime_install path (worker stops, partial artifacts removed,
omniroute_installed() never misreports a half-installed package).
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
