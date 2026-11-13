"""Item 3 follow-up patch 3: rework the network-offline overlay to follow the
project skills instead of an invented style.

Audit against .agent/skills (read via kernel from the PC):
- frontend-design: failure states explain what went wrong + how to fix it,
  one job per written element, no single-word accenting, no middle-dot
  meta strings. Copy rewritten to plain sentences, plain title.
- stageshow: the project already has the modal pattern .ss-modal-overlay +
  .ss-modal (+ lg-glass), used by #shutdownModal and #resetConfirmModal.
  The invented .network-offline-overlay class duplicated it with different
  values (z-index 10000, blur 1px, 0.4s ease, .hidden toggle) -> deleted;
  the overlay now reuses .ss-modal-overlay and toggles .modal-visible.
- aimran-library: components/overlays.json has 29 overlay components, no
  network-offline one (nearest is uv-ov-session-timeout); the in-project
  stageshow modal blend governs. The amber warning variant
  (.ss-modal-glow--amber / .ss-orb--amber / .modal-reset-icon /
  .ss-callout--amber) is copied from the reset confirmation modal.

Usage: python fix_item3_patch3.py [project_root]
Verifies EVERY replacement anchor appears exactly once before writing anything.
"""
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
assert (ROOT / "src/data/live_engine.py").exists(), f"not a TradeBot0 root: {ROOT}"

REPLACEMENTS = []


def rep(rel, old, new):
    REPLACEMENTS.append((rel, old, new))


def _read(path):
    raw = path.read_bytes()
    crlf = b"\r\n" in raw
    text = raw.decode("utf-8")
    if crlf:
        text = text.replace("\r\n", "\n")
    return text, crlf


def _write(path, text, crlf):
    if crlf:
        text = text.replace("\n", "\r\n")
    path.write_bytes(text.encode("utf-8"))


# ---------------------------------------------------------------- index.html: modal-pattern overlay
rep("src/gui/assets/index.html",
    '''  <!-- Network Offline Blocking Overlay: shown while the market feed is down.
       Trading is paused until a fresh quote arrives; clears automatically. -->
  <div id="networkOfflineOverlay" class="network-offline-overlay hidden">
    <div class="splash-container lg-glass lg-spot-card">
      <div class="splash-brand">
        <div class="splash-title">Network Offline <span class="splash-highlight">Waiting to Reconnect</span></div>
        <div class="splash-subtitle">Trading paused · resumes automatically when the connection returns</div>
      </div>
      <div class="splash-footer-note">
        <span class="live-dot" style="margin-right:7px;"></span>
        <span>Check your network connection · this overlay clears automatically on reconnect</span>
      </div>
    </div>
  </div>''',
    '''  <!-- Network Offline Blocking Overlay: reuses the stageshow modal pattern
       (.ss-modal-overlay + .ss-modal + lg-glass), amber warning variant
       copied from the reset confirmation modal. Shown while the market feed
       is down; trading is paused until a fresh quote arrives. No close
       button and no backdrop click: it clears only when the connection
       returns. -->
  <div id="networkOfflineOverlay" class="ss-modal-overlay" role="dialog" aria-modal="true" aria-labelledby="networkOfflineTitle">
    <div class="ss-modal lg-glass lg-spot-card">
      <div class="ss-modal-ambient-glow ss-modal-glow--amber" aria-hidden="true"></div>
      <div class="ss-modal-hero">
        <div class="ss-modal-icon-orb ss-orb--amber">
          <div class="orb-ring" aria-hidden="true"></div>
          <svg class="ss-svg-icon modal-reset-icon" viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M12 20h.01"></path>
            <path d="M8.5 16.4a5 5 0 0 1 7 0"></path>
            <path d="M2 8.82a15 15 0 0 1 4.17-2.65"></path>
            <path d="M10.66 5c4.01-.36 8.14.9 11.34 3.76"></path>
            <path d="M16.85 11.25a10 10 0 0 1 2.22 1.68"></path>
            <path d="M5 13a10 10 0 0 1 5.24-2.76"></path>
            <line x1="2" x2="22" y1="2" y2="22"></line>
          </svg>
        </div>
        <h2 class="ss-modal-title" id="networkOfflineTitle">Network Offline</h2>
        <p class="ss-modal-desc">Trading is paused while the market feed is down. It resumes automatically when the connection returns.</p>
      </div>
      <div class="ss-modal-callout ss-callout--amber">
        <svg class="ss-svg-icon" viewBox="0 0 16 16" width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M8 3v5M8 11.5v1M15 8A7 7 0 1 1 1 8a7 7 0 0 1 14 0z"></path>
        </svg>
        <span>Check your network connection. This overlay clears automatically on reconnect.</span>
      </div>
    </div>
  </div>''')

# ---------------------------------------------------------------- app.css: delete the invented overlay rules
rep("src/gui/assets/app.css",
    '''/* Network Offline Blocking Overlay (reuses the splash overlay pattern) */
.network-offline-overlay {
  position: fixed;
  inset: 0;
  z-index: 10000;
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    radial-gradient(circle at 50% 40%, rgba(255, 255, 255, 0.03), transparent 70%),
    rgba(2, 6, 15, 0.50);
  backdrop-filter: blur(1px) saturate(115%);
  -webkit-backdrop-filter: blur(1px) saturate(115%);
  opacity: 1;
  visibility: visible;
  transition: opacity 0.4s ease, visibility 0.4s ease;
}

.network-offline-overlay.hidden {
  opacity: 0;
  visibility: hidden;
  pointer-events: none;
}
''',
    "")

# ---------------------------------------------------------------- app.js: toggle .modal-visible (the modal pattern)
rep("src/gui/assets/app.js",
    '''  // Network offline blocking overlay: shown only after the arena has
  // revealed, so it never flashes over the startup splash.
  const netOverlay = document.getElementById('networkOfflineOverlay');
  if (netOverlay) {
    const showNetOverlay = isOffline && document.body && document.body.classList.contains('arena-ready');
    netOverlay.classList.toggle('hidden', !showNetOverlay);
  }''',
    '''  // Network offline blocking overlay (stageshow .ss-modal-overlay pattern):
  // shown only after the arena has revealed, so it never flashes over the
  // startup splash. Base .ss-modal-overlay styles already hide it; toggling
  // .modal-visible fades it in with the modal's own 1.25s entrance.
  const netOverlay = document.getElementById('networkOfflineOverlay');
  if (netOverlay) {
    const showNetOverlay = isOffline && document.body && document.body.classList.contains('arena-ready');
    netOverlay.classList.toggle('modal-visible', showNetOverlay);
  }''')


def main():
    files = {}
    for rel, _old, _new in REPLACEMENTS:
        files.setdefault(rel, _read(ROOT / rel))
    for rel, old, _new in REPLACEMENTS:
        text, _crlf = files[rel]
        n = text.count(old)
        assert n == 1, f"{rel}: expected exactly 1 occurrence, found {n}: {old[:100]!r}"
    print(f"All {len(REPLACEMENTS)} anchors verified.")
    new_texts = {rel: text for rel, (text, _c) in files.items()}
    for rel, old, new in REPLACEMENTS:
        new_texts[rel] = new_texts[rel].replace(old, new, 1)
    for rel, text in new_texts.items():
        _write(ROOT / rel, text, files[rel][1])
        print(f"patched {rel}")
    print("ITEM3 PATCH3 OK")


if __name__ == "__main__":
    main()
