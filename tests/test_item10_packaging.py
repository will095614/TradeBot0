"""Item 10 tests (part A): forced admin password, console port, no-key auth.

- A1: onboarding cannot complete without an admin password; the password is
  written to ~/.omniroute/.env preserving other vars and is never returned
  to the frontend.
- A2: the console URL follows the configured gateway_port.
- A3: with no key configured, chat_json sends no Authorization header.
"""
import asyncio
import inspect
import io
import json
import pytest
import shutil
import subprocess
import threading
import time
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import src.gui.dashboard as dashboard_mod
from src.gui.dashboard import ArenaDashboard, _ArenaBridgeApi
from src.intelligence.config_manager import ConfigManager
from src.intelligence.gateway_supervisor import GatewaySupervisor, RUNTIME_NODE_ZIP_URL
from src.intelligence.omniroute_client import OmniRouteClient


def _make_bridge(tmp_path):
    dash = ArenaDashboard()
    dash.config_manager = ConfigManager(
        data_dir=tmp_path / "data",
        omni_env_path=tmp_path / ".omniroute" / ".env",
    )
    dash.gateway_supervisor = GatewaySupervisor(
        daemon_log_path=tmp_path / "logs" / "omniroute_daemon.log"
    )
    return dash, _ArenaBridgeApi(dash)


def _mock_200_session():
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.headers = {}
    mock_resp.json = AsyncMock(return_value={
        "choices": [{"message": {"content": '{"directional_bias": "LONG_ONLY", "confidence": 0.92}'}}]
    })
    mock_session = MagicMock()
    mock_session.closed = False
    mock_session.post.return_value.__aenter__.return_value = mock_resp
    return mock_session


# ------------------------------------------------------------------ A1: password
def test_admin_password_required_before_onboarding(tmp_path):
    dash, bridge = _make_bridge(tmp_path)
    try:
        st = bridge.get_setup_status()
        assert st["admin_password_required"] is True
        assert st["omniroute_password_configured"] is False

        # No password supplied -> onboarding refused, nothing saved.
        res = bridge.save_and_launch_gateway(
            {"deepseek": "sk-test-000000000000000000000000"}
        )
        assert res["ok"] is False
        assert "password" in res["message"].lower()
        assert bridge.get_setup_status()["onboarding_completed"] is False

        # With a password -> onboarding completes and the password is stored.
        # Auto-launch is mandatory now, so the save path always tries to
        # start the gateway: keep the (real) supervisor from spawning one
        # during the test.
        with patch.object(dash.gateway_supervisor, "is_port_open", return_value=False), \
             patch.object(dash.gateway_supervisor, "start_daemon", return_value=(False, "not started in test")):
            res2 = bridge.save_and_launch_gateway(
                {"deepseek": "sk-test-000000000000000000000000"},
                admin_password="TestAdmin123",
            )
        assert res2["ok"] is True
        env_text = (tmp_path / ".omniroute" / ".env").read_text(encoding="utf-8")
        assert "INITIAL_PASSWORD=TestAdmin123" in env_text

        st3 = bridge.get_setup_status()
        assert st3["admin_password_required"] is False
        assert st3["omniroute_password_configured"] is True
        assert "TestAdmin123" not in json.dumps(st3)
    finally:
        dash.engine.stop()


def test_admin_password_too_short_rejected(tmp_path):
    cm = ConfigManager(
        data_dir=tmp_path / "data",
        omni_env_path=tmp_path / ".omniroute" / ".env",
    )
    res = cm.set_admin_password("short")
    assert res["ok"] is False
    assert not cm.is_admin_password_configured()
    assert not (tmp_path / ".omniroute" / ".env").exists()


def test_set_admin_password_preserves_other_vars(tmp_path):
    env_path = tmp_path / ".omniroute" / ".env"
    env_path.parent.mkdir(parents=True)
    env_path.write_text(
        "JWT_SECRET=keepme123\nDEEPSEEK_API_KEY=sk-old-000000000000000000000000\n",
        encoding="utf-8",
    )
    cm = ConfigManager(data_dir=tmp_path / "data", omni_env_path=env_path)
    res = cm.set_admin_password("TestAdmin123")
    assert res["ok"] is True
    text = env_path.read_text(encoding="utf-8")
    assert "JWT_SECRET=keepme123" in text
    assert "DEEPSEEK_API_KEY=sk-old-000000000000000000000000" in text
    assert "INITIAL_PASSWORD=TestAdmin123" in text


# ------------------------------------------------------------------ A2: console port
def test_console_url_follows_gateway_port(tmp_path):
    dash = ArenaDashboard()
    try:
        dash.config_manager = ConfigManager(
            data_dir=tmp_path / "data",
            omni_env_path=tmp_path / ".omniroute" / ".env",
        )
        dash.gateway_supervisor = GatewaySupervisor(
            port=20129, daemon_log_path=tmp_path / "logs" / "omniroute_daemon.log"
        )
        bridge = _ArenaBridgeApi(dash)
        with patch("webbrowser.open", return_value=True) as mock_open:
            res = bridge.open_omniroute_console()
        assert res["status"] == "ok"
        assert res["url"] == "http://127.0.0.1:20129"
        mock_open.assert_called_once_with("http://127.0.0.1:20129")
    finally:
        dash.engine.stop()


def test_dashboard_init_passes_configured_port_to_supervisor():
    src = inspect.getsource(dashboard_mod.ArenaDashboard.__init__)
    assert "GatewaySupervisor(host=" in src
    assert "gateway_port" in src


# ------------------------------------------------------------------ A3: no-key auth
def test_no_key_sends_no_authorization(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    async def _run():
        client = OmniRouteClient(base_url="http://mock-omniroute:20128/v1")
        assert client.api_key is None
        mock_session = _mock_200_session()
        client._session = mock_session
        client._owns_session = False
        result = await client.chat_json("auto", "system", "user")
        assert result == {"directional_bias": "LONG_ONLY", "confidence": 0.92}
        _, kwargs = mock_session.post.call_args
        assert "Authorization" not in kwargs.get("headers", {})

    asyncio.run(_run())


def test_key_present_sends_authorization(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    async def _run():
        client = OmniRouteClient(
            base_url="http://mock-omniroute:20128/v1",
            api_key="sk-test-item10-000000000000000000000000",
        )
        mock_session = _mock_200_session()
        client._session = mock_session
        client._owns_session = False
        await client.chat_json("auto", "system", "user")
        _, kwargs = mock_session.post.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer sk-test-item10-000000000000000000000000"

    asyncio.run(_run())


# ------------------------------------------------------------------ A1/A2: frontend
def test_frontend_wizard_has_admin_password_fields():
    assets = Path(__file__).resolve().parent.parent / "src" / "gui" / "assets"
    html = (assets / "index.html").read_text(encoding="utf-8")
    js = (assets / "app.js").read_text(encoding="utf-8")
    assert 'id="keyAdminPassword"' in html
    assert 'id="keyAdminPasswordConfirm"' in html
    assert 'id="statusAdminPassword"' in html
    assert "admin_password_required" in js
    assert "keyAdminPassword" in js
    assert "__tradebotGatewayPort" in js
    # New frontend strings are English-only (project rule: frontend zero CJK).
    for s in (
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
    assert sup.install_runtime_status() == {"status": "idle", "message": "", "progress": None, "phase": ""}


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
        assert st["runtime_install_status"] == {"status": "idle", "message": "", "progress": None, "phase": ""}
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
        assert s in js


# ------------------------------------------------- P1: Node 下載／npm 安裝
def _make_node_zip_bytes():
    """In-memory stand-in for the official Node.js zip (single top dir)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("node-v24.21.0-win-x64/node.exe", b"fake-node-exe")
        zf.writestr("node-v24.21.0-win-x64/npm.cmd", b"fake-npm")
    return buf.getvalue()


class _FakeURLDownload:
    """urlopen stand-in whose context manager yields a readable BytesIO."""

    def __init__(self, data: bytes):
        self._buf = io.BytesIO(data)

    def __enter__(self):
        return self._buf

    def __exit__(self, *exc):
        self._buf.close()
        return False


def _node_supervisor(tmp_path):
    return GatewaySupervisor(
        daemon_log_path=tmp_path / "daemon.log",
        install_log_path=tmp_path / "install.log",
    )


def test_download_node_verifies_zip_and_extracts(tmp_path):
    """Mock 下載固定 zip bytes：下載到正確路徑、解壓後 node.exe 存在、zip 已刪。"""
    base = tmp_path / "runtime"
    base.mkdir(parents=True)
    sup = _node_supervisor(tmp_path)
    with patch("urllib.request.urlopen", return_value=_FakeURLDownload(_make_node_zip_bytes())) as mock_urlopen:
        node_exe = sup._download_node(base)
    assert node_exe == str(base / "node" / "node.exe")
    assert (base / "node" / "node.exe").is_file()
    assert (base / "node" / "npm.cmd").is_file()
    assert not (base / "node.zip").exists()
    req = mock_urlopen.call_args[0][0]
    assert req.full_url == RUNTIME_NODE_ZIP_URL
    assert mock_urlopen.call_args[1]["timeout"] == 600


def test_download_node_corrupt_zip_raises_without_installing(tmp_path):
    """損毀 zip：解壓失敗直接報錯、不炸出別的東西，也不裝出 node.exe。"""
    base = tmp_path / "runtime"
    base.mkdir(parents=True)
    sup = _node_supervisor(tmp_path)
    with patch("urllib.request.urlopen", return_value=_FakeURLDownload(b"this is not a zip file")):
        with pytest.raises(zipfile.BadZipFile):
            sup._download_node(base)
    assert not (base / "node" / "node.exe").exists()


class _FakeNpmProc:
    """Fake subprocess.Popen for _npm_install_omniroute: poll() returns the
    preset returncode at once (no real process is spawned)."""

    RETURNCODE = 0

    def __init__(self, *args, **kwargs):
        self.returncode = self.RETURNCODE
        self.pid = 999

    def poll(self):
        return self.returncode

    def kill(self):
        self.returncode = -9

    def wait(self, timeout=None):
        return self.returncode


class _FakeNpmProcFail(_FakeNpmProc):
    RETURNCODE = 1


def test_npm_install_omniroute_runs_expected_command(tmp_path):
    """Mock subprocess.run：npm 指令含 --prefix <runtime>/omniroute 與 --allow-scripts 清單。"""
    base = tmp_path / "runtime"
    sup = _node_supervisor(tmp_path)
    npm_bin = str(base / "node" / "npm.cmd")
    with patch("subprocess.Popen", return_value=_FakeNpmProc()) as mock_popen:
        sup._npm_install_omniroute(npm_bin, base)
    assert mock_popen.call_count == 1
    cmd = mock_popen.call_args[0][0]
    assert cmd[0] == npm_bin
    assert cmd[1] == "install"
    assert cmd[2] == "--prefix"
    assert cmd[3] == str(base / "omniroute")
    assert cmd[4].startswith("--allow-scripts=")
    for pkg in ("omniroute", "better-sqlite3", "keytar", "tls-client-node",
                "onnxruntime-node", "sharp", "core-js", "esbuild",
                "@parcel/watcher", "@swc/core", "protobufjs", "koffi"):
        assert pkg in cmd[4], f"{pkg} missing from --allow-scripts"
    assert cmd[5] == "omniroute"
    # The 30-minute deadline is enforced by the Popen poll loop, not a
    # subprocess timeout kwarg: Popen must be called without one.
    assert "timeout" not in mock_popen.call_args[1]
    log_text = (tmp_path / "install.log").read_text(encoding="utf-8")
    assert "npm install omniroute --prefix" in log_text
    assert str(base / "omniroute") in log_text


def test_npm_install_omniroute_failure_reports_status(tmp_path):
    """兩次 npm 都失敗（rc=1）：先帶 --allow-scripts 試一次、再不帶重試一次，然後報錯。"""
    base = tmp_path / "runtime"
    sup = _node_supervisor(tmp_path)
    npm_bin = str(base / "node" / "npm.cmd")
    with patch("subprocess.Popen", return_value=_FakeNpmProcFail()) as mock_popen:
        with pytest.raises(RuntimeError, match="npm install exited with code 1"):
            sup._npm_install_omniroute(npm_bin, base)
    assert mock_popen.call_count == 2
    first_cmd = mock_popen.call_args_list[0][0][0]
    second_cmd = mock_popen.call_args_list[1][0][0]
    assert any(a.startswith("--allow-scripts=") for a in first_cmd)
    assert not any(a.startswith("--allow-scripts") for a in second_cmd)
    assert second_cmd[1:4] == ["install", "--prefix", str(base / "omniroute")]
    assert second_cmd[-1] == "omniroute"
