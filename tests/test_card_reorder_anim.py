# Strategy-matrix card reorder animation (FLIP).
#
# User report (2026-11-15): when the rankings change, the cards
# instantly jump to their new positions with no transition animation.
# renderStrategies keeps stable DOM nodes (stratCardDomMap keyed by
# strategy id) and reorders only when the sorted order changes, so the
# reorder is a pure DOM move -- animated with FLIP: record position,
# move nodes, invert with a translate, play it back via the
# .strat-card-reordering transform transition.
from pathlib import Path

_ASSETS = Path(__file__).resolve().parents[1] / "src" / "gui" / "assets"


def _js():
    return (_ASSETS / "app.js").read_text(encoding="utf-8")


def _css():
    return (_ASSETS / "app.css").read_text(encoding="utf-8")


def _reorder_block():
    js = _js()
    start = js.index("const currentCardOrder =")
    end = js.index("function renderTacticalHud", start)
    return js[start:end]


def test_reorder_anim_class_defined_with_transform_transition():
    css = _css()
    assert ".strat-card-mini.strat-card-reordering" in css
    assert "transform 0.35s ease" in css


def test_flip_records_first_rects_before_moving_nodes():
    block = _reorder_block()
    # First (measure) happens before any appendChild (Last).
    assert block.index("firstRects.set(s.id, card.getBoundingClientRect())") < block.index(
        "grid.appendChild(card)"
    )
    assert "card.getBoundingClientRect()" in block


def test_flip_inverts_with_translate_and_plays_via_class():
    block = _reorder_block()
    assert "card.style.transform = 'translate(' + dx + 'px, ' + dy + 'px)'" in block
    assert "card.classList.add('strat-card-reordering')" in block
    # Play: clear the transform on the next animation frame.
    assert "requestAnimationFrame(() => {" in block
    assert block.index("card.classList.add('strat-card-reordering')") < block.index(
        "requestAnimationFrame(() => {"
    )
    # Reflow forced between the inverted transform and the class add.
    assert "void grid.offsetHeight;" in block


def test_flip_cleanup_clears_class_and_transform():
    block = _reorder_block()
    assert "setTimeout(() => {" in block
    assert "}, 400);" in block
    assert "card.classList.remove('strat-card-reordering')" in block
    # A newer reorder inside the window must not be killed by an older
    # cleanup: the timeout is guarded by a per-card token.
    assert "_flipToken" in block


def test_flip_runs_only_when_order_changes():
    block = _reorder_block()
    assert "if (currentCardOrder !== nextCardOrder) {" in block
    assert block.index("if (currentCardOrder !== nextCardOrder) {") < block.index(
        "firstRects.set(s.id, card.getBoundingClientRect())"
    )


def test_flip_skipped_under_reduced_motion():
    block = _reorder_block()
    assert "prefers-reduced-motion: reduce" in block
    assert "reduceMotion" in block


def test_cards_are_stable_nodes_never_recreated_on_reorder():
    js = _js()
    # A card node is created exactly once per strategy id; later renders
    # reuse it from stratCardDomMap.
    assert "let card = stratCardDomMap.get(s.id);" in js
    assert "if (!card) {" in js
    # The grid is never wiped: no innerHTML reset on the container in
    # renderStrategies, so node identity survives every render.
    block = _reorder_block()
    assert "grid.innerHTML" not in block
    assert "innerHTML = ''" not in block
