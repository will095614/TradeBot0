# AI-tool panels, user-facing wording (W2/W3/W5/W6, I1-I8, N1-N3).
# Static contract tests: the decided labels must be present and the old
# tool-wording must be gone from the frontend assets and the save-flow
# stage messages. Decisions: ai-panels-decisions.md.
from pathlib import Path

_ASSETS = Path(__file__).resolve().parents[1] / "src" / "gui" / "assets"
_SRC = Path(__file__).resolve().parents[1] / "src"

_KEY_URLS = (
    "https://aistudio.google.com/apikey",
)

_REMOVED_KEY_URLS = (
    "https://build.nvidia.com/settings/api-keys",
    "https://console.groq.com/keys",
    "https://openrouter.ai/settings/keys",
)


def _html():
    return (_ASSETS / "index.html").read_text(encoding="utf-8")


def _js():
    return (_ASSETS / "app.js").read_text(encoding="utf-8")


def _css():
    return (_ASSETS / "app.css").read_text(encoding="utf-8")


def _dashboard():
    return (_SRC / "gui" / "dashboard.py").read_text(encoding="utf-8")


def test_wizard_key_cards_plain_wording_and_links():
    html = _html()
    for old_hint in (
        "DeepSeek-V3",
        "Gemini 2.0 Flash",
        "LPU Ultra-Low Latency",
        "Global Multi-Model Unified Router",
    ):
        assert old_hint not in html
    assert html.count("News reading and market analysis.") == 1
    for url in _KEY_URLS:
        assert url in html
    for url in _REMOVED_KEY_URLS:
        assert url not in html
    assert "Get a key" in html
    assert "One key is all you need." in html
    assert "Start with one key if you like" not in html
    assert "multi-provider" not in html
    assert html.count('class="setup-key-help"') == 1
    assert html.count('class="setup-key-help-popup"') == 1
    assert "Lets TradeBot0 ask" in html


def test_wizard_key_status_pills_plain_wording():
    html, js = _html(), _js()
    assert "Not Configured" not in html and "Not Configured" not in js
    assert "Configured in .env" not in html and "Configured in .env" not in js
    assert "Not added" in html
    assert "Connected" in js
    assert "Check failed" in js


def test_wizard_password_card_named_like_login_page():
    html = _html()
    assert "Gateway Admin Password" not in html
    assert '<span class="setup-provider-name">Password</span>' in html
    assert "Password for signing in to the OmniRoute dashboard (min 8 characters)" in html
    assert "Protects the local OmniRoute console" not in html


def test_save_toasts_and_stage_labels_plain_wording():
    js, dash = _js(), _dashboard()
    assert "AI services connected" in js
    assert "Console password saved" in js
    assert "API Credentials & Gateway Synchronized" not in js
    assert "Admin password is stored in ~/.omniroute/.env" not in js
    for label in (
        "Saving password...",
        "Connecting AI services...",
        "Starting AI services...",
        "Restarting AI services...",
        "Connecting to AI services...",
    ):
        assert label in dash
    assert "Saving admin password..." not in dash
    assert "Synchronizing API keys with local gateway..." not in dash
    assert "Starting OmniRoute gateway..." not in dash
    assert "Connecting to active OmniRoute gateway..." not in dash
    assert '"AI services connected."' in dash


def test_dock_gear_tooltip_is_ai_services():
    html = _html()
    assert 'title="AI Services"' in html
    assert "API Credentials &amp; Gateway Settings" not in html


def test_intel_hub_header_and_pill_plain():
    html, js = _html(), _js()
    assert "AI Services" in html
    assert "OmniRoute AI Gateway &amp; Quota Telemetry" not in html
    assert "ONLINE (24/7)" not in js
    assert "STANDBY / KEYWORD FALLBACK" not in js
    assert "STANDBY / LOCAL NLP" not in js
    assert "'Online'" in js and "'Standby'" in js
    assert "Using local backup analysis" in html
    assert 'id="intelDiagnosisLine"' in html
    assert 'id="intelFallbackLine"' in html


def test_intel_advanced_cards_always_shown():
    html, js = _html(), _js()
    # The Advanced toggle was removed at the user's request
    # (2026-11-15): the three engineering cards are always visible.
    assert 'id="btnIntelAdvanced"' not in html
    assert "toggleIntelAdvanced" not in js
    body = html.split('intel-advanced-section')[1].split('id="btnRefreshDigest"')[0]
    for label in ("OmniRoute Controller", "Token Utilization", "Async Concurrency"):
        assert label in body
    assert 'id="btnOpenOmniConsole"' in html
    assert 'id="omniConsolePwd"' in html
    assert 'id="omniTokensVal"' in html
    assert 'id="omniReqCounters"' in html
    assert 'id="macroThrottleLine"' in html
    assert "News updates slowed for now" in html


def test_stage_model_tags_removed():
    html, js = _html(), _js()
    assert "Stage-1 Ingest" not in html and "Stage-1 Ingest" not in js
    assert "Stage-2 Commander" not in html and "Stage-2 Commander" not in js
    assert "omniIngestModel" not in html and "omniIngestModel" not in js
    assert "omniCommanderModel" not in html and "omniCommanderModel" not in js


def test_refresh_button_renamed_with_progress_bar():
    html, js = _html(), _js()
    assert "Refresh News Analysis" in html
    assert "Refresh AI Digest" not in html and "Refresh AI Digest" not in js
    assert 'id="digestRefreshProgress"' in html
    assert "digest-refresh-progress-fill indeterminate" in html
    assert "digestRefreshProgress" in js
    assert "Refreshing news analysis..." in js


def test_commander_and_stream_titles():
    html = _html()
    assert "Market Direction" in html
    assert "Macro Regime Commander Directive (Strict Veto)" not in html
    assert "Market Intelligence Stream" in html
    assert "Curated Real-World Intelligence Stream" not in html


def test_navigation_labels():
    html = _html()
    assert "Market Intelligence (Press 2)" in html
    assert "Macro Intelligence Hub &amp; OmniRoute Monitor (Press 2)" not in html
    assert "Click to open Market Intelligence" in html
    assert "Click to open Macro Intelligence Hub" not in html
    assert "See news &amp; market analysis" in html
    assert "Inspect AI Cognitive Stream &amp; News" not in html
    # N2: the Zone A card title is "Market Intelligence" (the visible
    # title in code was "Macro Commander"; "Macro AI Core" only ever
    # appeared in an HTML comment).
    assert '<div class="macro-core-sub-title">Market Intelligence</div>' in html
    assert "Macro AI Core" not in html


def test_key_page_links_use_allowlisted_bridge():
    dash, js = _dashboard(), _js()
    assert "def open_external_url" in dash
    for url in _KEY_URLS:
        assert url in dash
    for url in _REMOVED_KEY_URLS:
        assert url not in dash
    assert "open_external_url" in js
    assert "openProviderKeyPage" in js


def test_new_panel_classes_are_defined_in_css():
    css = _css()
    for cls in (
        "setup-keys-intro",
        "setup-key-link",
        "setup-key-help",
        "setup-key-help-popup",
        "intel-status-lines",
        "intel-status-line",
        "intel-diagnosis-line",
        "intel-advanced-section",
        "intel-throttle-line",
        "digest-refresh-progress",
        "digest-refresh-progress-track",
        "digest-refresh-progress-fill",
    ):
        assert ("." + cls) in css, "CSS class .%s is not defined" % cls


def test_compact_mode_fits_intro_line_and_status_lines_hold_width():
    css = _css()
    # The intro line must not add its own bottom margin: the column
    # gap already separates it from the first key card, so the
    # wizard still fits at inner height 600 (compact mode) with
    # no scroll.
    intro = css.split(".setup-keys-intro {", 1)[1].split("}", 1)[0]
    assert "margin-bottom: 0" in intro
    idx_media = css.index("@media (max-height: 720px)")
    idx_intro = css.index(".setup-keys-intro { line-height: 1.3; }")
    assert idx_intro > idx_media
    # Reserved status lines are full-width, right-aligned: filling
    # the diagnosis line changes its text only, never its box.
    line = css.split(".intel-status-line {", 1)[1].split("}", 1)[0]
    assert "width: 100%" in line
    assert "text-align: right" in line


def test_deck_empty_slots_collapse_and_level_bottoms():
    # Deck tightening (user decision 2026-11-16, sim-approved):
    # the reserved-but-empty slots collapse to zero height instead
    # of holding dead space, so the deck drops from 221px to ~169px.
    # Both cards still share one height (deck grid stretch), so their
    # bottoms stay level.
    css = _css()
    status = css.split(".intel-status-line {", 1)[1].split("}", 1)[0]
    assert "display: none" in status
    status_vis = css.split(".intel-status-line.visible {", 1)[1].split("}", 1)[0]
    assert "display: block" in status_vis
    throttle = css.split(".intel-throttle-line {", 1)[1].split("}", 1)[0]
    assert "display: none" in throttle
    throttle_vis = css.split(".intel-throttle-line.visible {", 1)[1].split("}", 1)[0]
    assert "display: block" in throttle_vis
    prog = css.split(".digest-refresh-progress {", 1)[1].split("}", 1)[0]
    assert "display: none" in prog
    assert ".digest-refresh-progress.active" in css
    # The deck grid still stretches both cards to one shared height.
    deck = css.split(".intel-top-deck {", 1)[1].split("}", 1)[0]
    assert "align-items: stretch" in deck
    # The progress bar is shown by class now, not inline style.
    js = _js()
    assert "digestProg.classList.add('active')" in js
    assert "digestProg.classList.remove('active')" in js
    assert "digestProg.style.visibility" not in js
