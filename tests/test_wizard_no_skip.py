"""The setup wizard has no "Skip to Pure Math Core" button anymore.

The user removed the Skip entry point. The `skip_to_pure_math` bridge
method is deleted with it (it was the wizard's entry point; the
dead-bridge contract test forbids an uncalled bridge method). The
`skip_ai_mode` config value and the live launch paths that read it (the
`start_live_trading` guard, the `run()` engine-start and auto-spawn
gates, and the `admin_password_required` computation) are KEPT, so
installs that already skipped keep working; only the creation of new
skip states is gone.
"""
from pathlib import Path

from src.gui.dashboard import ArenaDashboard, _ArenaBridgeApi
from src.intelligence.config_manager import ConfigManager


def _assets_root() -> Path:
    return Path(__file__).resolve().parent.parent / "src" / "gui" / "assets"


def test_wizard_has_no_skip_button():
    """No Skip button in the wizard: not in the HTML, not in the JS, and
    the actions row holds only Save & Launch Arena."""
    html = (_assets_root() / "index.html").read_text(encoding="utf-8")
    js = (_assets_root() / "app.js").read_text(encoding="utf-8")
    assert "btnSkipToPureMath" not in html
    assert "Skip to Pure Math" not in html
    assert "skipToPureMathCore" not in html
    assert "skipToPureMathCore" not in js
    start = html.index("setup-wizard-actions")
    segment = html[start:html.index("</div>", start)]
    assert segment.count("<button") == 1
    assert "btnSaveAndLaunch" in segment


def test_skip_bridge_deleted_but_mode_readers_kept(tmp_path):
    """The skip_to_pure_math bridge method is deleted (it was the
    wizard's entry point; the dead-bridge contract test forbids an
    uncalled bridge method). The skip_ai_mode status field and the live
    launch paths that read it are kept."""
    dash = ArenaDashboard()
    dash.config_manager = ConfigManager(data_dir=tmp_path / "data")
    bridge = _ArenaBridgeApi(dash)
    try:
        assert not hasattr(bridge, "skip_to_pure_math")
        assert "skip_ai_mode" in bridge.get_setup_status()
    finally:
        dash.engine.stop()
