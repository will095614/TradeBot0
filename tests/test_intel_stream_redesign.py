"""Intel Hub stream redesign, Phase B (frontend).

Static contract tests: the stream is full-width rows (not the old
4-column grid), summaries are cleaned the sim's splitBody way, ticker
chips carry fixed colours, expand state survives re-sorts, articles
load lazily exactly once per event, and failures are shown honestly
(never the summary passed off as the article). The chevron rotation
and the expansion use the aimran smooth-accordion spring.

These tests parse the assets as text (regex only), like
test_ui_contract.py -- they do not execute JavaScript.
"""
import re
from pathlib import Path

_ASSETS = Path(__file__).resolve().parents[1] / "src" / "gui" / "assets"
_TESTS = Path(__file__).resolve().parent


def _html():
    return (_ASSETS / "index.html").read_text(encoding="utf-8")


def _js():
    return (_ASSETS / "app.js").read_text(encoding="utf-8")


def _css():
    return (_ASSETS / "app.css").read_text(encoding="utf-8")


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


def _css_block(css, selector):
    """Declarations of the first `<selector> { ... }` rule."""
    m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert m, f"CSS rule {selector} not found"
    return m.group(1)


def test_stream_is_full_width_rows_not_grid():
    css = _css()
    block = _css_block(css, ".intel-events-list")
    assert "repeat(" not in block and "auto-fill" not in block, (
        "stream list is still a multi-column grid: " + block
    )
    assert "flex-direction: column" in block, (
        "stream list must lay out one full-width row per event: " + block
    )


def test_summary_cleaned_splitbody_way():
    js = _js()
    assert "function cleanIntelSummary" in js
    body = _fn_body(js, "cleanIntelSummary")
    assert "INTEL_SUMMARY_PREFIX" in body
    assert "'Wire Digest: '" in js
    assert "'Tickers:'" in js
    assert "'Headline:'" in js
    assert "lastIndexOf('(')" in body
    assert "INTEL_TAIL_MARK_A" in body or "INTEL_TAIL_MARK_B" in body
    # The rendered summary goes through the cleaner, never raw.
    assert "cleanIntelSummary(evt.summary" in js or "cleanIntelSummary(summary" in js


def test_ticker_chips_fixed_colours():
    css = _css()
    js = _js()
    assert ".intel-tick" in css
    colours = {}
    for ticker in ("BTC", "ETH", "AI", "XRP", "MACRO"):
        block = _css_block(css, '.intel-tick[data-t="%s"]' % ticker)
        m = re.search(r"color:\s*([^;]+);", block)
        assert m, f"no text colour for ticker {ticker}"
        colours[ticker] = m.group(1).strip()
    assert len(set(colours.values())) == 5, (
        f"tickers must each have a distinct fixed colour: {colours}"
    )
    for i in range(5):
        assert (".tick-fh%d" % i) in css, f"hash-fallback class tick-fh{i} missing"
    # Chips render from evt.tickers (Phase A), keyed by data-t.
    assert "evt.tickers" in js
    assert 'data-t="' in js
    # The fallback colour is a deterministic hash of the name -- no
    # randomness, no clock, so the same ticker is the same colour
    # everywhere (including after a re-sort).
    body = _fn_body(js, "tickerChipClass")
    assert "Math.random" not in body
    assert "Date" not in body
    assert "tick-fh" in body


def test_sort_toggle_time_impact():
    html = _html()
    js = _js()
    assert 'id="intelSortSeg"' in html
    assert "setIntelSortMode('time')" in html
    assert "setIntelSortMode('impact')" in html
    assert "function setIntelSortMode" in js
    assert "syncSegThumb('intelSortSeg'" in js
    assert "intelSortMode" in js
    body = _fn_body(js, "sortIntelEvents")
    assert "urgency" in body, "Impact sort must order by urgency"
    # Impact is urgency descending; ties keep telemetry order.
    assert re.search(r"Number\(b\.evt\.urgency", body) or re.search(
        r"b\.evt\.urgency[^;]*-\s*Number\(a\.evt\.urgency", body
    ), "Impact sort must be urgency descending"


def test_expand_state_survives_resort():
    js = _js()
    # Expand state lives in a Set keyed by event id, outside the render.
    assert "intelExpandedIds" in js
    assert re.search(r"new Set\(\)", js)
    # Stable per-event DOM nodes (same pattern as stratCardDomMap).
    assert "intelEventNodes" in js
    # The render applies the open class from the set, never from a
    # per-render flag that a re-sort could reset.
    assert "classList.toggle('is-open'" in js
    # Re-ordering moves stable nodes; the whole list is never rebuilt
    # from an HTML string (that would drop expand state and articles).
    assert "nextEventsHtml" not in js
    assert "appendChild" in js


def test_click_anywhere_on_row_toggles_expand():
    js = _js()
    assert "intelEventsList" in js
    assert "addEventListener('click'" in js
    assert "closest('.intel-event-card')" in js
    assert "function toggleIntelEventCard" in js


def test_article_lazy_once_and_cached():
    js = _js()
    # Exactly one bridge call site: the lazy loader (the existence
    # guard above it is not a second call).
    assert js.count("pywebview.api.get_event_article(eventId)") == 1
    body = _fn_body(js, "requestIntelArticle")
    assert "typeof window.pywebview.api.get_event_article" in body
    # Cached (ready or failed) short-circuits before any bridge call.
    assert "intelArticleCache[" in body
    assert "intelArticlePending[" in body
    assert "get_event_article" in body
    # The cache is written for the resolved result, success or failure.
    assert re.search(r"intelArticleCache\[eventId\] = result", body)


def test_article_failure_shows_reason_not_summary():
    js = _js()
    body = _fn_body(js, "renderIntelArticle")
    # The failure path renders the backend reason, honestly.
    assert "reason" in body
    # The article area never gets the one-line summary passed off as
    # the article (comments excluded from the check).
    body_nc = re.sub(r"//.*", "", body)
    assert "summary" not in body_nc
    assert "cleanIntelSummary" not in body_nc
    # Loading shows an honest loading state before the bridge resolves.
    load_body = _fn_body(js, "requestIntelArticle")
    assert "Loading article" in load_body


def test_chevron_and_accordion_spring():
    css = _css()
    js = _js()
    assert ".intel-expand-chevron" in css
    block = _css_block(css, ".intel-event-card.is-open .intel-expand-chevron")
    assert "rotate(-90deg)" in block, "open chevron must point down: " + block
    # The rotation + expansion share the aimran smooth-accordion
    # spring (stiffness 300, damping 30), translated to CSS easing.
    assert "smooth-accordion" in css or "smooth-accordion" in js
    assert "stiffness 300" in css or "stiffness 300" in js
    assert "damping 30" in css or "damping 30" in js
    # Reduced motion disables the accordion transition.
    m = re.search(
        r"@media\s*\(prefers-reduced-motion:\s*reduce\)\s*\{(.*?)\n\}",
        css,
        flags=re.S,
    )
    assert m, "no reduced-motion block in app.css"
    assert ".intel-event-detail" in m.group(1) or ".intel-expand-chevron" in m.group(1)
    assert "transition: none" in m.group(1)


def test_expanded_detail_has_no_raw_title_or_sentiment_row():
    js = _js()
    body = _fn_body(js, "buildIntelEventCard")
    # The expanded detail holds only the article, the ticker chips and
    # the Arena impact box -- no raw title, no sentiment-verdict row.
    assert "raw_title" not in body
    assert "intel-article-body" in body
    assert "intel-tick-row" in body
    assert "intel-strategy-actions-box" in body


def test_get_event_article_removed_from_dead_list():
    text = (_TESTS / "test_ui_contract.py").read_text(encoding="utf-8")
    m = re.search(
        r"KNOWN_DEAD_BRIDGE_METHODS\s*=\s*\{(.*?)\n\}", text, flags=re.S
    )
    assert m, "KNOWN_DEAD_BRIDGE_METHODS block not found"
    assert "get_event_article" not in m.group(1), (
        "get_event_article is called from JS now; remove it from "
        "KNOWN_DEAD_BRIDGE_METHODS or test_no_dead_bridge_methods fails "
        "on 'resurrected'"
    )


def test_urgency_badge_lookup_survives_rerender():
    """The urgency badge's class is swapped to 'intel-domain-badge'
    when urg < 8, so a fresh '.intel-urgency-badge' query on the
    second 1s re-render would return null and crash renderIntelHub
    (the stable-node render never rebuilds the card). The update must
    therefore cache the element reference on the card."""
    js = _js()
    body = _fn_body(js, "updateIntelEventCard")
    assert "card._urgEl" in body, (
        "updateIntelEventCard must cache the urgency badge element "
        "(its class is renamed on update, so re-querying "
        "'.intel-urgency-badge' returns null on the next render)"
    )


def test_summary_prefix_matches_backend():
    """The frontend cleaner must strip the exact English prefix the backend emits."""
    js = _js()
    m = re.search(r"INTEL_SUMMARY_PREFIX\s*=\s*'([^']+)'", js)
    assert m, "INTEL_SUMMARY_PREFIX not found in app.js"
    front = m.group(1)
    backend = (_TESTS.parent / "src" / "intelligence" / "ingestion.py").read_text(encoding="utf-8")
    mb = re.search(r'Wire Digest:\s*', backend)
    assert mb, "backend prefix literal 'Wire Digest: ' not found in ingestion.py"
    assert front == "Wire Digest: ", (
        "frontend prefix %r != 'Wire Digest: '" % (front,)
    )


def test_article_loading_shows_determinate_stage_progress_bar():
    # Article loading (V2.5.2 upgrade): displays "Loading article..." plus
    # the live backend step label and a real determinate progress bar driven
    # by backend pipeline stages and SSE streaming progress.
    js = _js()
    load_body = _fn_body(js, "requestIntelArticle")
    assert "Loading article" in load_body
    assert "intel-article-stage" in load_body
    assert "intel-article-pct" in load_body
    assert "intel-article-progress" in load_body
    assert "intel-article-progress-fill" in load_body
    assert 'role="progressbar"' in load_body
    assert 'aria-valuemin="0"' in load_body
    assert 'aria-valuemax="100"' in load_body
    assert "startIntelArticleProgressPoll" in load_body
    css = _css()
    assert ".intel-article-progress" in css
    assert ".intel-article-progress-fill" in css


def test_article_renders_with_fade_in():
    # Article fade-in (user request 2026-11-16): the lazy article
    # must not pop in instantly when it replaces the loading text.
    css = _css()
    assert "@keyframes intel-article-fade-in" in css
    para = _css_block(css, ".intel-article-para")
    assert "intel-article-fade-in" in para
    assert "0.4s" in para
    # The honest error in the same slot fades in the same way.
    error = _css_block(css, ".intel-article-error")
    assert "intel-article-fade-in" in error
    # Reduced motion disables the fade, next to the loading-pulse
    # override.
    m = re.search(
        r"@media\s*\(prefers-reduced-motion:\s*reduce\)\s*\{(.*?)\n\}",
        css,
        flags=re.S,
    )
    assert m, "no reduced-motion block in app.css"
    assert "intel-article-para" in m.group(1)


def test_article_render_is_not_rewritten_every_tick():
    # Article jitter (user report 2026-11-16): the 1s re-render called
    # renderIntelArticle for every open card, which re-set innerHTML
    # every second. Invisible until V2.8.5 gave the paragraphs a
    # fade-in, which then replayed forever. The render must skip when
    # this exact cached result is already displayed.
    js = _js()
    body = _fn_body(js, "renderIntelArticle")
    assert "_renderedResult" in body
    assert "if (body._renderedResult === result) return;" in body


def test_articles_preload_while_collapsed():
    # Preload (user request 2026-11-16): articles start loading while
    # the cards are still collapsed, so opening one is instant.
    js = _js()
    assert "function preloadIntelArticles" in js
    assert "function pumpIntelArticlePreload" in js
    # Triggered from the list-update branch of renderIntelHub, in
    # display order.
    hub = _fn_body(js, "renderIntelHub")
    assert "preloadIntelArticles(sorted.map(intelEventKey))" in hub
    # Sequential: one in flight at a time, chained on the pending
    # promise of the article just started.
    pump = _fn_body(js, "pumpIntelArticlePreload")
    assert "intelArticlePreloadRunning" in pump
    assert "intelArticlePending[id]" in pump
    # Cached / in-flight / gone events are skipped, never re-queued.
    preload = _fn_body(js, "preloadIntelArticles")
    assert "intelArticleCache[id]" in preload
    assert "intelArticlePending[id]" in preload
    assert "intelArticlePreloadQueue.indexOf(id) === -1" in preload
    # Preload never expands a card.
    assert "intelExpandedIds" not in preload
    assert "intelExpandedIds" not in pump


def test_expand_during_preload_is_safe():
    # Expand-vs-preload race (user requirement 2026-11-16): expanding a
    # card while its article is preloading must not start a second bridge
    # call and must not clobber the in-flight load's loading state.
    js = _js()
    body = _fn_body(js, "requestIntelArticle")
    pending_idx = body.index("if (intelArticlePending[eventId]) return;")
    loading_idx = body.index("intel-article-loading")
    bridge_idx = body.index("get_event_article(eventId)")
    assert pending_idx != -1 and loading_idx != -1 and bridge_idx != -1
    assert pending_idx < loading_idx, (
        "pending check must precede the loading-state write, or an expand "
        "mid-preload would clobber the in-flight load"
    )
    assert pending_idx < bridge_idx, (
        "pending check must precede the bridge call, or an expand "
        "mid-preload would fire a second load"
    )
    # The expand path goes through that dedup point; it never calls the
    # bridge itself.
    toggle = _fn_body(js, "toggleIntelEventCard")
    assert "requestIntelArticle(eventId)" in toggle
    assert "get_event_article" not in toggle
    # The preload pump re-checks pending at dequeue time, so a load the
    # user started by expanding is never duplicated by the pump.
    pump = _fn_body(js, "pumpIntelArticlePreload")
    assert "intelArticlePending[id]" in pump
    # A load that resolves after its card left the list (digest refresh)
    # must not crash: renderIntelArticle bails when the body is gone.
    render = _fn_body(js, "renderIntelArticle")
    assert "if (!body) return;" in render
