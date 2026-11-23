"""Phase 0-4 UI optimization regression tests (Option B: preserves #modularSlotPanel)."""
from __future__ import annotations

from pathlib import Path

from src.gui.dashboard import _build_html_template

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "src" / "gui" / "assets"


def test_unslop_skill_installed():
    skill_md = ROOT / ".agents" / "skills" / "unslop" / "SKILL.md"
    assert skill_md.exists(), "Expected heydamir/unslop SKILL.md to be installed in .agents/skills/unslop/"
    txt = skill_md.read_text(encoding="utf-8")
    assert "unslop" in txt.lower()


def test_grainient_webp_asset_and_inline_injection():
    webp_path = ASSETS / "grainient_obsidian.webp"
    assert webp_path.exists(), "grainient_obsidian.webp missing in src/gui/assets"
    raw = webp_path.read_bytes()
    assert raw[:4] == b"RIFF" and raw[8:12] == b"WEBP", "Invalid WebP header"
    assert len(raw) < 250_000, f"grainient_obsidian.webp too large ({len(raw)} bytes)"

    rendered = _build_html_template()
    assert "data:image/webp;base64," in rendered
    assert "/* __GRAINIENT_OBSIDIAN_DATA_URI__ */" not in rendered


def test_modular_slot_panel_preserved_option_b():
    html = (ASSETS / "index.html").read_text(encoding="utf-8")
    assert 'id="modularSlotPanel"' in html
    assert "Modular Extension Bay" in html
    assert "STANDBY" in html


def test_phase0_to_4_ui_hooks_present():
    html = (ASSETS / "index.html").read_text(encoding="utf-8")
    css = (ASSETS / "app.css").read_text(encoding="utf-8")
    js = (ASSETS / "app.js").read_text(encoding="utf-8")

    # HTML elements across Phases 1-4
    for marker in (
        'id="lgAmbientShaderCanvas"',
        'id="lgAmbientGrainient"',
        'id="commandPaletteModal"',
        'id="omniTokenMeter"',
        'id="intelSearchInput"',
        'id="intelDomainChips"',
        'id="adminPwdStrengthWrap"',
        'id="resetSlideTrack"',
        'id="viewStageHost"',
        'id="hudVesselChampCard"',
        'id="macroThinkingOrbs"',
        'id="digestThinkingOrbs"',
        "scroll-area-faded",
        "toast-stack-host",
        "metal-fx-cta",
    ):
        assert marker in html, f"Missing HTML marker {marker}"

    # CSS tokens & component classes across Phases 0-4
    for cls in (
        "--arc-ease-spring",
        "--arc-dur-base",
        ".nf-digit-col",
        ".strat-sparkline-svg",
        ".toast-stack-item",
        ".ctx-meter-track",
        ".thinking-orb",
        ".border-beam-ring",
        ".metal-fx-cta",
        ".view-stage-host",
        ".view-stage-host.is-view-transitioning .lg-glass",
        ".view-transition-prepare",
        ".view-transition-entering",
        ".view-transition-leaving-base",
        ".view-transition-leaving",
        ".lg-switch--stretching",
        ".sld-track",
        ".cmd-palette-card",
        ".icon-morph-wrap",
        ".text-morph-enter",
        ".sort-th--active",
        ".intel-search-wrap",
        ".intel-chip",
        ".scroll-area-faded",
        ".pwd-strength-wrap",
        ".lg-ambient-grainient",
        ".lg-ambient-shader",
    ):
        assert cls in css, f"Missing CSS rule/token {cls}"

    # JS functions & handlers
    for fn in (
        "function updateRollingText(",
        "function setLeaderboardSort(",
        "function setIntelDomainFilter(",
        "function cycleBackdropMode(",
        "function morphText(",
        "function syncToastStackLayout(",
        "function openCommandPalette(",
        "function initResetSlideConfirm(",
        "function updateAdminPasswordStrength(",
        "function initScrollAreaFades(",
        "function mountSilverStreamAmbient(",
    ):
        assert fn in js, f"Missing JS function {fn}"


def test_new_continuous_animations_respect_hidden_and_reduced_motion():
    css = (ASSETS / "app.css").read_text(encoding="utf-8")
    hidden_block = css.split("body.window-hidden .lg-ambient-blob,", 1)[1].split("}", 1)[0]
    reduced_block = css.split("@media (prefers-reduced-motion: reduce) {", -1)[-1]

    for selector in (".border-beam-ring", ".thinking-orb", ".lg-ambient-shader"):
        assert selector in hidden_block, f"{selector} not paused under body.window-hidden"
        assert selector in reduced_block, f"{selector} not paused under prefers-reduced-motion"


def test_pause_btn_scopes_icon_and_label_widths_without_overflow():
    css = (ASSETS / "app.css").read_text(encoding="utf-8")
    assert "#pauseBtn > span" not in css
    assert "#pauseBtn > .icon-morph-wrap" in css
    assert "#pauseBtn > .action-swap-label" in css
    icon_rule = css.split("#pauseBtn > .icon-morph-wrap", 1)[1].split("}", 1)[0]
    assert "width: 12px !important" in icon_rule
