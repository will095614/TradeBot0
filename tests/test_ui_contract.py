"""UI static-contract tests: pin the wiring between index.html / app.js /
app.css / dashboard.py without executing any JavaScript.

These tests parse the assets as text (regex / AST only). They do NOT render
the page, run WebView2, or open a browser tab. What they pin:

1. Every CSS class referenced from HTML/JS exists in app.css — except a
   known list of referenced-but-undefined classes (skill-naming leftovers).
   Any *new* undefined class fails the test; when P2 fixes a class, delete
   it from KNOWN_UNDEFINED_CLASSES.
2. Every inline ``onclick="fn(...)"`` handler is defined in app.js, and
   every ``pywebview.api.*`` call made from JS exists on ``_ArenaBridgeApi``.
3. Every public bridge method is either called from JS or from Python
   production code — otherwise it must be on the KNOWN_DEAD_BRIDGE_METHODS
   list with a reason. A method that gains a caller must be removed from
   the list; a method that loses its last caller must be added (or fixed).
4. Every HTML id is referenced from JS, owns an inline onclick, or is
   listed in DOCUMENTED_DECORATIVE_IDS with its non-JS owner / reason.
   Dynamic template-literal ids (`` `status${cap}` ``) are resolved via
   the provIdMap values in app.js.

Scope note: only *literal* class names are collected. A class name that
arrives purely as a JS variable (e.g. ``${bCls}``) cannot be resolved by
static parsing; the one such data-driven channel — ``badge_cls`` values
produced by Python (``macro_commander`` / ``live_engine``) and rendered by
app.js — is covered by a targeted scan of the producer call sites (see
``_badge_cls_producer_values``). ``log_event`` levels are NOT classes:
app.js never uses them as one.
"""

import ast
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Known state (pinned 2026-11-13; re-verified against the PC sources, NOT
# copied from the audit report -- the report's 17 missed 8, see below).
# ---------------------------------------------------------------------------

# P2 (2026-11-13): all 25 previously undefined classes resolved --
# 17 defined in app.css (ss-stage-host, lg-stage, splash-brand,
# splash-step-lbl, splash-svg-icon, ss-badge__label, lg-island-pill,
# lg-btn--ghost, lg-switch__label, lg-seg--stretching, toast-strat-name,
# profit, loss, buy, sell, standby, surge) and 8 dead references
# deleted from index.html (tactical-hud, hud-card, macro-ribbon,
# macro-dot, auto-evolve-btn, pwd-copy-icon, view-switcher,
# matrix-title). The set stays empty on purpose: any new undefined
# class fails test_all_referenced_css_classes_are_defined.
KNOWN_UNDEFINED_CLASSES = frozenset()

KNOWN_DEAD_BRIDGE_METHODS = {
    # JS never calls it, and the close path + bridge.shutdown() call
    # engine.save_session_state() directly -- the feature works, only
    # this bridge wrapper is dead.
    "save_session_state": (
        "JS never calls it; shutdown/close path calls "
        "engine.save_session_state() directly, so the feature is unaffected"
    ),
    # Update-check scaffolding (another executor's in-progress work):
    # the bridge method exists and delegates to src.update_checker, but
    # the startup path (_maybe_check_for_updates) calls the imported
    # function directly and the frontend is not wired to it yet
    # (dashboard.py: "showing a prompt in the frontend is future work").
    # tests/test_update_checker.py calls it directly -- that is a unit
    # test exercising it, not production wiring. Remove once the
    # frontend calls it.
    "check_for_updates": (
        "update-check scaffolding: no JS call, startup path calls the "
        "imported function directly, frontend not wired yet"
    ),
}

# ---------------------------------------------------------------------------
# File loading
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).resolve().parents[1]
_ASSETS = _ROOT / "src" / "gui" / "assets"


def _read(path):
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# JS string-literal scanner (handles '...' / "..." / `...` incl. ${...})
# ---------------------------------------------------------------------------

_TOKEN = re.compile(r"[A-Za-z_][\w-]*")


def _string_literals(fragment):
    """Contents of every string literal in a JS fragment.

    For template literals, returns the literal parts between interpolations
    plus the string literals *inside* the interpolations, so
    ```${isBuy ? 'badge-buy' : 'badge-sell'}``` yields badge-buy and
    badge-sell. Bare identifiers inside interpolations (``${bCls}``) are
    variables, not literals, and are skipped by design.
    """
    out = []
    i, n = 0, len(fragment)
    while i < n:
        ch = fragment[i]
        if ch in ("'", '"'):
            j = i + 1
            buf = []
            while j < n:
                if fragment[j] == "\\":
                    buf.append(fragment[j : j + 2])
                    j += 2
                    continue
                if fragment[j] == ch:
                    break
                buf.append(fragment[j])
                j += 1
            out.append("".join(buf))
            i = j + 1
        elif ch == "`":
            j = i + 1
            buf = []
            while j < n:
                if fragment[j] == "\\":
                    buf.append(fragment[j : j + 2])
                    j += 2
                    continue
                if fragment[j] == "`":
                    break
                if fragment[j] == "$" and j + 1 < n and fragment[j + 1] == "{":
                    out.append("".join(buf))
                    buf = []
                    depth = 1
                    k = j + 2
                    start = k
                    while k < n and depth > 0:
                        c = fragment[k]
                        if c in ("'", '"', "`"):
                            q = c
                            k += 1
                            while k < n:
                                if fragment[k] == "\\":
                                    k += 2
                                    continue
                                if fragment[k] == q:
                                    break
                                k += 1
                            k += 1
                            continue
                        if c == "{":
                            depth += 1
                        elif c == "}":
                            depth -= 1
                        k += 1
                    out.extend(_string_literals(fragment[start : k - 1]))
                    j = k
                    continue
                buf.append(fragment[j])
                j += 1
            out.append("".join(buf))
            i = j + 1
        else:
            i += 1
    return out


def _class_value_tokens(value):
    """Class tokens of one class="..." value.

    Literal parts are split on whitespace; string literals inside
    ${...} interpolations are collected too (see _string_literals).
    """
    toks = set()
    for part in re.split(r"\$\{[^}]*\}", value):
        toks.update(part.split())
    for m in re.finditer(r"\$\{([^}]*)\}", value):
        for lit in _string_literals(m.group(1)):
            toks.update(lit.split())
    return {t for t in toks if _TOKEN.fullmatch(t)}


# ---------------------------------------------------------------------------
# Class collection
# ---------------------------------------------------------------------------


def _defined_classes(css_text):
    """Classes defined in app.css (selector text only, comments stripped)."""
    css = re.sub(r"/\*.*?\*/", "", css_text, flags=re.S)
    defined = set()
    for chunk in css.split("{"):
        selector = chunk.rsplit("}", 1)[-1]
        defined.update(re.findall(r"\.([A-Za-z_][\w-]*)", selector))
    return defined


def _referenced_classes(html_text, js_text):
    """Classes referenced from index.html / app.js -> {class: {sources}}."""
    ref = {}

    def add(cls, src):
        ref.setdefault(cls, set()).add(src)

    html_nc = re.sub(r"<!--.*?-->", "", html_text, flags=re.S)
    for m in re.finditer(r"""class\s*=\s*["']([^"']*)["']""", html_nc):
        for c in m.group(1).split():
            add(c, "html:class")
    # class="..." attributes inside JS string/template literals.
    for m in re.finditer(r"""class\s*=\s*(["'`])(.*?)\1""", js_text):
        for c in _class_value_tokens(m.group(2)):
            add(c, "js:class-attr")
    # el.classList.add/remove/toggle/contains/replace('...')
    for m in re.finditer(
        r"classList\.(?:add|remove|toggle|contains|replace)\s*\(([^)]*)\)", js_text
    ):
        for lit in _string_literals(m.group(1)):
            for c in lit.split():
                if _TOKEN.fullmatch(c):
                    add(c, "js:classList")
    # el.className = <expr>; -- literals of the whole RHS expression.
    for m in re.finditer(r"className\s*\+?=\s*([^;\n]+)", js_text):
        for lit in _string_literals(m.group(1)):
            for c in lit.split():
                if _TOKEN.fullmatch(c):
                    add(c, "js:className")
    # *Cls variables (badgeCls / pnlCls / nextPillCls / sentCls / cls ...):
    # literals of the assigned expression. RHS stops at ',' so a
    # multi-declarator line (let sentCls = 'neutral', sentTxt = `...`)
    # cannot leak the neighbour declarator's text into the class set.
    for m in re.finditer(
        r"(?:\b(?:const|let|var)\s+)?\b\w*[Cc]ls\s*=\s*([^;,\n]+)", js_text
    ):
        for lit in _string_literals(m.group(1)):
            for c in lit.split():
                if _TOKEN.fullmatch(c):
                    add(c, "js:*Cls")
    # Selector strings: querySelector(All) / closest / matches.
    for m in re.finditer(
        r"(?:querySelector(?:All)?|closest|matches)\s*\(\s*['\"`]([^'\"`]+)['\"`]",
        js_text,
    ):
        for c in re.findall(r"\.([A-Za-z_][\w-]*)", m.group(1)):
            add(c, "js:selector")
    return ref


def _badge_cls_producer_values():
    """Literal badge_cls values Python can hand to the frontend.

    app.js renders ``act.badge_cls`` / ``a.badge_cls`` as a class
    (``strat-action-pill ${bCls}``, ``catalyst-impact-pill ${...}``), but
    the values themselves live in Python: the ``record_strategy_action``
    default, the ``event_type`` ternary in live_engine, and the literal
    4th arguments of its ``record_strategy_action`` calls.
    """
    values = set()
    mc = _read(_ROOT / "src" / "intelligence" / "macro_commander.py")
    m = re.search(
        r"def record_strategy_action\(.*?badge_cls:\s*str\s*=\s*['\"]([^'\"]+)['\"]",
        mc,
        flags=re.S,
    )
    if m:
        values.add(m.group(1))
    le = _read(_ROOT / "src" / "data" / "live_engine.py")
    for m in re.finditer(
        r"""event_type\s*=\s*['"]([^'"]+)['"]\s*if\b.*?else\s*['"]([^'"]+)['"]""",
        le,
    ):
        values.update((m.group(1), m.group(2)))
    for m in re.finditer(r"record_strategy_action\s*\(", le):
        start = m.end()
        depth = 1
        k = start
        while k < len(le) and depth > 0:
            if le[k] == "(":
                depth += 1
            elif le[k] == ")":
                depth -= 1
            k += 1
        block = le[start : k - 1]
        # Drop f-strings first: a closing f-string quote would otherwise
        # pair with the next plain literal's opening quote and swallow it.
        block = re.sub(r"""f"[^"]*\"""", '""', block)
        block = re.sub(r"""f'[^']*'""", "''", block)
        for lit in re.findall(r"""(?<![A-Za-z_])"([^"]*)\"""", block):
            for tok in lit.split():
                if _TOKEN.fullmatch(tok):
                    values.add(tok)
    return values


# ---------------------------------------------------------------------------
# Bridge introspection (AST over dashboard.py -- no import needed)
# ---------------------------------------------------------------------------


def _bridge_class_node():
    tree = ast.parse(_read(_ROOT / "src" / "gui" / "dashboard.py"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "_ArenaBridgeApi":
            return tree, node
    raise AssertionError("_ArenaBridgeApi not found in src/gui/dashboard.py")


def _bridge_methods():
    _, cls = _bridge_class_node()
    return sorted(
        {n.name for n in cls.body if isinstance(n, ast.FunctionDef)}
    )


def _bridge_self_calls():
    """{method: {methods it calls via self.<other>()}} inside the bridge."""
    _, cls = _bridge_class_node()
    out = {}
    for fn in cls.body:
        if not isinstance(fn, ast.FunctionDef):
            continue
        called = set()
        for n in ast.walk(fn):
            if (
                isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute)
                and isinstance(n.func.value, ast.Name)
                and n.func.value.id == "self"
            ):
                called.add(n.func.attr)
        out[fn.name] = called
    return out


def _bridge_obj_calls():
    """Methods called anywhere in dashboard.py via self._bridge.<m>()."""
    tree, _ = _bridge_class_node()
    called = set()
    for n in ast.walk(tree):
        if (
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and isinstance(n.func.value, ast.Attribute)
            and n.func.value.attr == "_bridge"
        ):
            called.add(n.func.attr)
    return called


# ---------------------------------------------------------------------------
# Test 1: CSS classes
# ---------------------------------------------------------------------------


def test_all_referenced_css_classes_are_defined():
    css = _read(_ASSETS / "app.css")
    html = _read(_ASSETS / "index.html")
    js = _read(_ASSETS / "app.js")
    defined = _defined_classes(css)
    assert defined, "app.css yielded no class definitions -- parser broke?"
    referenced = _referenced_classes(html, js)
    assert referenced, "no classes collected -- parser broke?"
    referenced |= {v: {"python:badge_cls"} for v in _badge_cls_producer_values()}
    undefined = set(referenced) - defined
    unexpected = sorted(undefined - KNOWN_UNDEFINED_CLASSES)
    fixed = sorted(KNOWN_UNDEFINED_CLASSES - undefined)
    assert not unexpected, (
        "new referenced-but-undefined CSS classes (fix the CSS or add "
        f"them to KNOWN_UNDEFINED_CLASSES with a reason): {unexpected}"
    )
    assert not fixed, (
        "classes were fixed but are still listed as known-undefined; "
        f"remove them from KNOWN_UNDEFINED_CLASSES: {fixed}"
    )


# ---------------------------------------------------------------------------
# Test 2: onclick handlers + pywebview bridge calls
# ---------------------------------------------------------------------------


def _js_defined_functions(js_text):
    fns = set(re.findall(r"function\s+([A-Za-z_$][\w$]*)\s*\(", js_text))
    fns |= set(
        re.findall(
            r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:\(|function)",
            js_text,
        )
    )
    fns |= set(re.findall(r"window\.([A-Za-z_$][\w$]*)\s*=", js_text))
    return fns


def test_all_onclick_handlers_defined_and_all_bridge_calls_exist():
    html = _read(_ASSETS / "index.html")
    js = _read(_ASSETS / "app.js")
    handlers = sorted(set(re.findall(r'onclick\s*=\s*"([^"(]+)\(', html)))
    assert handlers, "no inline onclick handlers found -- parser broke?"
    defined_fns = _js_defined_functions(js)
    missing = [h for h in handlers if h not in defined_fns]
    assert not missing, (
        f"inline onclick handlers with no definition in app.js: {missing}"
    )
    calls = sorted(set(re.findall(r"pywebview\.api\.([A-Za-z_]\w*)", js)))
    assert calls, "no pywebview.api.* calls found in app.js -- parser broke?"
    methods = _bridge_methods()
    missing_calls = [c for c in calls if c not in methods]
    assert not missing_calls, (
        "JS calls bridge methods that do not exist on _ArenaBridgeApi: "
        f"{missing_calls}"
    )


# ---------------------------------------------------------------------------
# Test 3: dead bridge methods
# ---------------------------------------------------------------------------


def test_no_dead_bridge_methods_or_documented():
    js = _read(_ASSETS / "app.js")
    methods = _bridge_methods()
    public = {m for m in methods if not m.startswith("_")}
    assert public, "no public bridge methods found -- parser broke?"
    js_called = set(re.findall(r"pywebview\.api\.([A-Za-z_]\w*)", js))
    # Live = called from JS, plus anything reachable from a live method
    # via self.<other>() inside the bridge, plus anything called through
    # the bridge object (self._bridge.<m>()) in dashboard.py. The
    # fixpoint matters: a method reachable only from a dead method is
    # itself dead, so the closure is computed to a fixpoint.
    live = set(js_called)
    self_calls = _bridge_self_calls()
    obj_calls = _bridge_obj_calls()
    changed = True
    while changed:
        changed = False
        for meth in list(live):
            for callee in self_calls.get(meth, set()):
                if callee in public and callee not in live:
                    live.add(callee)
                    changed = True
        for callee in obj_calls:
            if callee in public and callee not in live:
                live.add(callee)
                changed = True
    dead = sorted(public - live)
    known = set(KNOWN_DEAD_BRIDGE_METHODS)
    unexpected = [m for m in dead if m not in known]
    resurrected = sorted(known - set(dead))
    assert not unexpected, (
        "bridge methods with no JS call and no Python call that are not "
        "documented in KNOWN_DEAD_BRIDGE_METHODS (wire them up, delete "
        f"them, or document them): {unexpected}"
    )
    assert not resurrected, (
        "methods listed as known-dead now have a caller; remove them "
        f"from KNOWN_DEAD_BRIDGE_METHODS: {resurrected}"
    )

# ---------------------------------------------------------------------------
# Test 4: HTML ids (§3.2, P2)
# ---------------------------------------------------------------------------

# Ids that no JS code references and no inline onclick owns, verified
# 2026-11-13 against the PC sources. Each has a non-JS owner or is
# purely decorative; if an id gains a JS caller, delete it from this
# dict (the test fails on stale entries too).
DOCUMENTED_DECORATIVE_IDS = {
    # aria-labelledby targets of the modal dialogs (the overlay divs
    # carry aria-labelledby="<id>").
    "networkOfflineTitle": "aria-labelledby target of #networkOfflineOverlay",
    "resetModalTitle": "aria-labelledby target of #resetConfirmModal",
    "installCancelModalTitle": "aria-labelledby target of #installCancelConfirmModal",
    "setupWizardTitle": "aria-labelledby target of #setupWizardModal",
    "shutdownModalTitle": "aria-labelledby target of #shutdownModal",
    # SVG gradient referenced by fill="url(#splashZapGrad)" in the
    # splash lightning polygon.
    "splashZapGrad": "SVG gradient referenced by fill=url(#splashZapGrad)",
    # SVG filter defs in the <defs> block. No url(#...) consumer exists
    # anywhere (checked in app.css / index.html / app.js), so they are
    # inert placeholders kept with the defs, not live styling.
    "uvq11-goo": "SVG filter def with no url(#...) consumer; inert",
    "lg-caustic-filter": "SVG filter def with no url(#...) consumer; inert",
    # Static display text, never updated by JS: the concurrency cell
    # always reads "25 Semaphores" (fixed gateway config).
    "omniConcurrencyVal": "static text '25 Semaphores'; never updated by JS",
    # Decorative containers / static chrome: JS updates their children
    # (or nothing at all); the element itself is only styled.
    "fullLedgerPanel": "panel shell; JS fills #leaderboardBody inside it",
    "globalCursorBackdrop": "aria-hidden cursor-glow backdrop div",
    "intelEventsScroll": "scroll wrapper; JS fills #intelEventsList inside it",
    "isoClockPill": "clock pill shell; JS updates #isoClockDisplay inside it",
    "leaderboardTable": "table shell; JS fills #leaderboardBody inside it",
    "lgAmbientField": "aria-hidden ambient background field",
    "macroCatalystActionRow": "row shell; JS updates #macroCatalystImpact inside it",
    "macroCatalystCard": "card shell; JS updates its #macroCatalyst* children",
    "macroDot": "static dot (styled by .ss-badge__dot); never updated by id",
    "modularSlotPanel": "'Modular Extension Bay' placeholder panel (reserved)",
    "omniConsoleSubtext": "label wrapper; the #omniConsolePwd child has the onclick",
    "orderflowPanel": "panel shell; JS fills #fillsBody inside it",
}


def _html_ids(html_text):
    """{id: has_inline_onclick} for every id="..." in index.html."""
    ids = {}
    for m in re.finditer(
        r'<[A-Za-z][\w-]*\b[^>]*?\bid\s*=\s*"([^"]+)"[^>]*>', html_text
    ):
        ids[m.group(1)] = ids.get(m.group(1), False) or ("onclick" in m.group(0))
    return ids


def _js_referenced_ids(js_text):
    """Ids JS reaches, without executing it.

    - Literal ``getElementById('...')`` calls.
    - Template-literal ``getElementById(`prefix${...}`)`` calls, expanded
      with the provider suffixes from the ``provIdMap`` literals in the
      same file (DeepSeek / Gemini / Groq / OpenRouter) -- this is how
      ``statusDeepSeek`` et al. are reached; a rename on either side
      breaks the expansion and fails the test.
    - ``querySelector(All)('#id...')`` (the ``:hover`` pseudo-class
      selector yields its base id, which is a real reference).
    - First-argument literals of ``syncSegThumb`` / ``setVesselLevel``,
      the two id-consuming helpers that take an id instead of calling
      getElementById themselves.
    """
    ref = set(re.findall(r"""getElementById\(\s*['"]([^'"]+)['"]\s*\)""", js_text))
    for m in re.finditer(
        r"querySelector(?:All)?\s*\(\s*['\"`]([^'\"`]+)['\"`]", js_text
    ):
        ref.update(re.findall(r"#([A-Za-z_][\w-]*)", m.group(1)))
    prefixes = set(re.findall(r"getElementById\(`([\w-]+)\$\{", js_text))
    assert prefixes, "no template-literal getElementById found -- pattern broke?"
    values = set()
    for m in re.finditer(r"provIdMap\s*=\s*\{([^}]*)\}", js_text):
        values.update(re.findall(r"""['"]([A-Za-z]+)['"]""", m.group(1)))
    assert values, "provIdMap values not found -- pattern broke?"
    for p in prefixes:
        for v in values:
            ref.add(p + v)
    for fn in ("syncSegThumb", "setVesselLevel"):
        for m in re.finditer(rf"{fn}\(\s*['\"]([^'\"]+)['\"]", js_text):
            ref.add(m.group(1))
    return ref


def test_html_ids_have_owner_or_are_documented_dead():
    html = _read(_ASSETS / "index.html")
    js = _read(_ASSETS / "app.js")
    ids = _html_ids(html)
    assert ids, "no ids found in index.html -- parser broke?"
    js_refs = _js_referenced_ids(js)
    # A JS reference to an id that does not exist in the HTML is a
    # wiring bug, not a stale test: fail loudly instead of ignoring it.
    dangling = sorted(js_refs - set(ids))
    assert not dangling, (
        "JS references ids that do not exist in index.html: " f"{dangling}"
    )
    owned = {i for i, has_onclick in ids.items() if has_onclick or i in js_refs}
    undocumented = sorted(set(ids) - owned - set(DOCUMENTED_DECORATIVE_IDS))
    assert not undocumented, (
        "HTML ids with no JS reference, no onclick, and no documented "
        "reason (reference them from JS, give them an onclick, or add "
        f"them to DOCUMENTED_DECORATIVE_IDS): {undocumented}"
    )
    stale = sorted(set(DOCUMENTED_DECORATIVE_IDS) - set(ids))
    assert not stale, (
        "ids listed as documented-decorative no longer exist in "
        "index.html; remove them from DOCUMENTED_DECORATIVE_IDS: "
        f"{stale}"
    )
