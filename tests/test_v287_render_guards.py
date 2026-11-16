"""V2.8.7 render-path optimization (frontend).

Static contract tests: the 1s render path must not do redundant DOM
work. Event cards cache their element refs (was ~7 querySelector calls
per card per tick); the Intel Hub header, macro ribbon, strategy colour
and generation label only write when the value actually changed; the
pointer spotlight vars are written once per frame, not once per
pointermove event. No displayed value, class, or animation changes --
each guard only skips a write when the new value equals the current
one. These tests parse app.js as text (regex only), like
test_ui_contract.py -- they do not execute JavaScript.
"""
import re
from pathlib import Path

_ASSETS = Path(__file__).resolve().parents[1] / "src" / "gui" / "assets"


def _js():
    return (_ASSETS / "app.js").read_text(encoding="utf-8")


def _fn_body(js, name):
    """Body of `function <name>(...) { ... }` by brace counting."""
    m = re.search(r"function\s+" + re.escape(name) + r"\s*\(", js)
    assert m, f"function {name} not found in app.js"
    start = js.index("{", m.end())
    depth = 0
    for i in range(start, len(js)):
        if js[i] == "{":
            depth += 1
        elif js[i] == "}":
            depth -= 1
            if depth == 0:
                return js[start + 1 : i]
    raise AssertionError(f"unbalanced braces in function {name}")


def test_intel_card_element_refs_cached():
    # Was ~7 querySelector calls per card on every 1s re-render; now one
    # query each on first use, cached on the card (same pattern as the
    # existing _urgEl cache). The tick-row / actions-wrap queries stay:
    # they are already guarded by _tickKey / _impactHtml.
    body = _fn_body(_js(), "updateIntelEventCard")
    for ref in (
        "_intelHead",
        "_intelTimeEl",
        "_intelDomEl",
        "_intelSrcEl",
        "_intelSentEl",
        "_intelHeadlineEl",
        "_intelSummaryEl",
    ):
        assert ref in body, f"card ref cache {ref} missing"
    assert body.count("card.querySelector('.intel-card-header')") == 1
    assert body.count("head.querySelector('.intel-event-time')") == 1
    assert body.count("head.querySelector('.intel-domain-badge')") == 1
    assert body.count("head.querySelector('.intel-source-badge')") == 1
    assert body.count("head.querySelector('.intel-sentiment-badge')") == 1
    assert body.count("card.querySelector('.intel-card-headline')") == 1
    assert body.count("card.querySelector('.intel-card-summary')") == 1


def test_hub_header_writes_guarded():
    # Values that only change when a digest lands must not be rewritten
    # on every 1s tick.
    body = _fn_body(_js(), "renderIntelHub")
    for guard in (
        "if (epEl.textContent !== nextEp)",
        "if (tokensEl.textContent !== nextTokens)",
        "if (tokensSub.textContent !== nextSub)",
        "if (reqEl.textContent !== nextReq)",
        "if (regBadge.className !== nextRegCls)",
        "if (regBadge.textContent !== reg)",
        "if (biasEl.textContent !== nextBias)",
        "if (biasSub.textContent !== nextBiasSub)",
        "if (multEl.textContent !== nextMult)",
        "if (confEl.textContent !== nextConf)",
        "if (lastEval.textContent !== nextEval)",
        "if (vetoEl.textContent !== nextVeto)",
        "if (headEl.textContent !== nextHead)",
        "if (countLbl.textContent !== nextCount)",
    ):
        assert guard in body, f"hub header guard missing: {guard}"


def test_macro_ribbon_writes_guarded():
    body = _fn_body(_js(), "renderMacroRibbon")
    for guard in (
        "if (badge.className !== nextBadgeCls)",
        "if (regimeTxt.textContent !== nextRegimeTxt)",
        "if (biasTag.textContent !== nextBias)",
        "if (multTag.textContent !== nextMult)",
        "if (vetoTag.textContent !== nextVeto)",
        "if (omniTag.textContent !== nextOmni)",
        "if (headline.textContent !== nextHeadline)",
        "if (catalystHeadline.textContent !== nextCatHead)",
        "if (catalystSummary.textContent !== nextCatSum)",
        "if (catalystTime.textContent !== nextCatTime)",
        "if (catalystImpact.textContent !== nextCatText)",
        "if (catalystImpact.className !== nextCatCls)",
    ):
        assert guard in body, f"macro ribbon guard missing: {guard}"
    # The badge class set is fully determined by the regime, so the
    # guarded single assignment must produce the same final string as
    # the old reset + classList.add.
    assert "regime-bullish" in body and "regime-bearish" in body
    assert "regime-chop" in body


def test_strat_color_and_gen_label_writes_guarded():
    strat = _fn_body(_js(), "renderStrategies")
    assert "if (card._stratColor !== s.color)" in strat
    header = _fn_body(_js(), "renderHeader")
    assert "if (genLbl.textContent !== nextGen)" in header


def test_spotlight_vars_written_once_per_frame():
    js = _js()
    start = js.index("window.addEventListener('pointermove'")
    end = js.index("}, { passive: true });", start)
    handler = js[start:end]
    # The --gx/--gy writes must sit inside the rAF callback (after
    # requestAnimationFrame), not on the raw pointermove event.
    raf_idx = handler.index("requestAnimationFrame")
    gx_idx = handler.index("setProperty('--gx'")
    gy_idx = handler.index("setProperty('--gy'")
    assert raf_idx < gx_idx and raf_idx < gy_idx, (
        "spotlight vars are still written on every pointermove event"
    )
    assert handler.count("setProperty('--gx'") == 1
    assert handler.count("setProperty('--gy'") == 1
    # They still track the latest pointer position.
    assert "latestPointerEvent.clientX" in handler
    assert "latestPointerEvent.clientY" in handler
