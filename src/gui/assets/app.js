// ==========================================================================
// Splash Screen Initialization Controller (Strict Sequential Lifecycle)
// 1. Replay & simulate 120m historical orderflow
// 2. Pre-render Left K-Line Chart and Right Strategy/Leaderboard Tables
// 3. Verify ALL elements rendered -> 100% -> Reveal Arena
// 4. Activate Live Order Dispatch
// Supports both initial application boot and on-demand Reset Arena re-entry
// ==========================================================================
let splashProgress = 0;
let targetSplashProgress = 15;
let splashCompleted = false;
let hasFirstChartDrawn = false;
let hasFirstTableRendered = false;
let splashLoop = null;
let splashSafetyTimer = null;
let splashTimers = [];
let currentSplashSteps = [];
// Exit-gate timing, hoisted so setSplashTarget() can tell whether the
// gate is open: 100% is only ever shown once the first chart frame and
// the first tables are really rendered AND the minimum splash duration
// has elapsed.
let splashStartTimeMs = 0;
let splashMinDurationMs = 2500;

// Coordinated boot & setup states
let hasBootInitiated = false;
let hasBootResolved = false;
let hasCompletedSetup = false;
let hasCheckedOnboarding = false;
let isWizardOpen = false;
let wizardOpenGen = 0;
let isSavingGateway = false;
let isCheckingWizardClose = false;

// Global Arena Data & Polling States
let latestState = null;
let isPolling = false;
let pendingControlActions = 0;
let stateApplyEpoch = 0;
let forceNextFullDelta = false;
let scaleMode = 'auto';    // 'auto' or 'full'
let lastPausedCanvasSig = '';
let toastWatchdogInterval = null;

// Position tracking states
let knownStrategyPositions = {};
let hasInitializedPositions = false;

// Toast Notification Stagger Queue & Micro-Interactions
let toastQueue = [];
let isProcessingToastQueue = false;
let toastStaggerTimer = null;
const MAX_VISIBLE_TOASTS = 3;
const TOAST_DURATION_MS = 6000;

const initialSplashSteps = [
  { threshold: 15, text: "Initializing 5 Strategy Ledgers ($100,000 U x 5)..." },
  { threshold: 35, text: "Connecting to Real-Time Multi-Exchange Orderflow..." },
  { threshold: 55, text: "Replaying 120m Intraday Historical Simulation..." },
  { threshold: 75, text: "Translating & Synthesizing Global Macro Intelligence Digest (\u7e41\u9ad4\u4e2d\u6587)..." },
  { threshold: 90, text: "Pre-rendering Left K-Line Chart & Right Tactical Tables..." },
  { threshold: 100, text: "Arena Fully Loaded. Launching Live Arena..." }
];

const resetSplashSteps = [
  { threshold: 15, text: "Resetting 5 Strategy Portfolios ($100,000 U x 5)..." },
  { threshold: 35, text: "Purging Order Tape & Active Bracket Orders..." },
  { threshold: 55, text: "Replaying 120m Intraday Historical Simulation..." },
  { threshold: 75, text: "Translating & Synthesizing Macro News Digest (\u7e41\u9ad4\u4e2d\u6587)..." },
  { threshold: 90, text: "Pre-rendering Fresh K-Line Depth & Tactical Tables..." },
  { threshold: 100, text: "Arena Reset Complete. Launching Fresh Arena..." }
];

// Segmented Control Thumb Helper
function syncSegThumb(segId, activeIdx) {
  const seg = document.getElementById(segId);
  if (!seg) return;
  const prevIdx = seg.dataset.activeIdx;
  seg.style.setProperty('--active-idx', String(activeIdx));
  seg.dataset.activeIdx = String(activeIdx);
  if (prevIdx !== undefined && String(prevIdx) !== String(activeIdx)) {
    seg.classList.add('lg-seg--stretching');
    setTimeout(() => seg.classList.remove('lg-seg--stretching'), 210);
  }
  const buttons = seg.querySelectorAll('.ss-seg__option');
  buttons.forEach((btn, idx) => {
    if (idx === activeIdx) {
      btn.classList.add('active');
      btn.setAttribute('data-on', '');
    } else {
      btn.classList.remove('active');
      btn.removeAttribute('data-on');
    }
  });
}

// AIMRAN High-Contrast Pure Black Obsidian Stage Switcher
function setLgWallpaper(wall) {
  const chosen = wall || 'obsidian';
  document.documentElement.setAttribute('data-wallpaper', chosen);
  if (document.body) {
    document.body.setAttribute('data-wallpaper', chosen);
  }
  if (latestState) drawPriceChart(latestState);
}

function sanitizeCssColor(val, fallback) {
  const s = String(val || '').trim();
  if (/^#[0-9a-fA-F]{3,8}$/.test(s) || /^rgba?\(\s*\d+\s*,\s*\d+\s*,\s*\d+(?:\s*,\s*[\d.]+)?\s*\)$/.test(s)) {
    return s;
  }
  return fallback || '#F59E0B';
}

function clearSplashTimers() {
  splashTimers.forEach((id) => clearTimeout(id));
  splashTimers.length = 0;
}

function scheduleSplashTimer(fn, delayMs) {
  const id = setTimeout(() => {
    const idx = splashTimers.indexOf(id);
    if (idx !== -1) splashTimers.splice(idx, 1);
    fn();
  }, delayMs);
  splashTimers.push(id);
  return id;
}

let isStartingLiveTrading = false;
async function ensureLiveTradingStarted() {
  if (isStartingLiveTrading) return;
  if (!window.pywebview || !window.pywebview.api || typeof window.pywebview.api.start_live_trading !== 'function') return;
  if (!latestState || !latestState.is_bootstrapped) return;
  if (latestState.live_orders_enabled) return;

  isStartingLiveTrading = true;
  const myEpoch = ++stateApplyEpoch;
  try {
    const res = await window.pywebview.api.start_live_trading();
    if (res && res.status !== 'blocked' && Array.isArray(res.strategies) && myEpoch === stateApplyEpoch) {
      latestState = res;
      renderAll(res);
    }
  } catch (e) {
    console.warn('start_live_trading err:', e);
  } finally {
    isStartingLiveTrading = false;
  }
}

function startSplashSequence(isReset = false) {
  try {
    clearSplashTimers();
    if (splashLoop) {
      clearInterval(splashLoop);
      splashLoop = null;
    }
    if (splashSafetyTimer) {
      clearTimeout(splashSafetyTimer);
      splashSafetyTimer = null;
    }

    // Immediately hide the workspace underneath so inner charts never flash or show prematurely
    if (document.body) {
      document.body.classList.remove('arena-ready');
    }

    const appShell = document.querySelector('.app-shell');
    if (appShell) {
      appShell.classList.remove('arena-entering');
      appShell.style.opacity = '0';
    }

    splashProgress = 0;
    targetSplashProgress = 15;
    splashCompleted = false;
    hasFirstChartDrawn = false;
    hasFirstTableRendered = false;
    currentSplashSteps = isReset ? resetSplashSteps : initialSplashSteps;
    splashStartTimeMs = performance.now();
    splashMinDurationMs = isReset ? 2200 : 2500;

    // Reset local tracking states and queues so toasts never fire prematurely behind the splash screen
    knownStrategyPositions = {};
    hasInitializedPositions = false;
    toastQueue.length = 0;
    isProcessingToastQueue = false;
    if (toastStaggerTimer) {
      clearTimeout(toastStaggerTimer);
      toastStaggerTimer = null;
    }
    const toastContainer = document.getElementById('chartNotificationContainer');
    if (toastContainer) {
      Array.from(toastContainer.children).forEach((el) => {
        if (el._countdownInterval) {
          clearInterval(el._countdownInterval);
          el._countdownInterval = null;
        }
        if (el._dismissTimeout) {
          clearTimeout(el._dismissTimeout);
          el._dismissTimeout = null;
        }
      });
      toastContainer.innerHTML = '';
    }

    const overlay = document.getElementById('splashOverlay');
    const bar = document.getElementById('splashProgressBar');
    const pLbl = document.getElementById('splashPercentLabel');
    const sLbl = document.getElementById('splashStepLabel');
    const fNote = document.getElementById('splashFooterNoteText');

    if (overlay) {
      overlay.style.display = 'flex';
      overlay.style.opacity = '1';
      overlay.style.visibility = 'visible';
      overlay.classList.remove('fade-out');
    }
    if (bar) bar.style.width = '0%';
    if (pLbl) pLbl.textContent = '0%';
    if (sLbl) sLbl.textContent = currentSplashSteps[0].text;
    if (fNote) {
      fNote.textContent = isReset
        ? "Re-initializing Portfolios & Re-simulating 120m Orderflow..."
        : "Simulating 120m Orderflow & Pre-Rendering Arena...";
    }

    // If backend state is already populated/bootstrapped, advance smoothly
    // across the milestones. The step to 100% is NOT on a timer: it is
    // released only by the exit gate (first chart frame + first tables
    // really rendered), so the bar can never claim 100% early. The 2350ms
    // jump below only tops the target up to the 90% cap.
    if (latestState && latestState.is_bootstrapped) {
      scheduleSplashTimer(() => setSplashTarget(35), 350);
      scheduleSplashTimer(() => setSplashTarget(55), 800);
      scheduleSplashTimer(() => setSplashTarget(75), 1300);
      scheduleSplashTimer(() => setSplashTarget(90), 1800);
      scheduleSplashTimer(() => setSplashTarget(100), 2350);
    }

    // Smooth animation loop for progress bar
    splashLoop = setInterval(() => {
      if (splashCompleted) {
        clearInterval(splashLoop);
        splashLoop = null;
        return;
      }

      const elapsedMs = performance.now() - splashStartTimeMs;
      const canComplete = elapsedMs >= splashMinDurationMs;

      // Release the 90% cap the moment the exit gate genuinely opens:
      // the bar animates 90 -> 100 only when the arena is ready to
      // reveal, never before.
      if (canComplete && hasFirstChartDrawn && hasFirstTableRendered) {
        setSplashTarget(100);
      }

      if (splashProgress < targetSplashProgress) {
        const remaining = targetSplashProgress - splashProgress;
        const maxStep = canComplete ? 2.5 : Math.min(1.4, remaining * 0.08);
        const step = Math.min(maxStep, Math.max(0.35, remaining * 0.12));
        splashProgress = Math.min(targetSplashProgress, splashProgress + step);
      }

      if (bar) bar.style.width = splashProgress + '%';
      if (pLbl) pLbl.textContent = Math.round(splashProgress) + '%';

      let activeStep = currentSplashSteps[0].text;
      for (let i = 0; i < currentSplashSteps.length; i++) {
        if (splashProgress >= currentSplashSteps[i].threshold) {
          activeStep = currentSplashSteps[i].text;
        }
      }
      if (sLbl) sLbl.textContent = activeStep;

      // Strict exit condition: 100% reached AND minimum duration met AND left chart drawn AND right tables rendered
      if (splashProgress >= 99.5 && targetSplashProgress >= 100 && canComplete && hasFirstChartDrawn && hasFirstTableRendered) {
        splashProgress = 100;
        if (pLbl) pLbl.textContent = '100%';
        if (sLbl) sLbl.textContent = currentSplashSteps[currentSplashSteps.length - 1].text;
        splashCompleted = true;
        clearInterval(splashLoop);
        splashLoop = null;
        if (splashSafetyTimer) {
          clearTimeout(splashSafetyTimer);
          splashSafetyTimer = null;
        }

        scheduleSplashTimer(() => {
          // Reveal the workspace smoothly once everything is 100% ready
          if (document.body) {
            document.body.classList.add('arena-ready');
          }

          const appShell = document.querySelector('.app-shell');
          if (appShell) {
            appShell.style.opacity = '';
            appShell.classList.add('arena-entering');
          }

          const overlayEl = document.getElementById('splashOverlay');
          if (overlayEl) {
            overlayEl.style.opacity = '';
            overlayEl.style.visibility = '';
            overlayEl.classList.add('fade-out');
          }

          // Automatic mouse location and immediate chart refresh upon entering arena
          locateMouseAndRefreshChart();

          // Second refresh and final live order activation after overlay transition
          scheduleSplashTimer(() => {
            if (overlayEl) {
              overlayEl.style.display = 'none';
              overlayEl.classList.remove('fade-out');
            }
            if (appShell) {
              appShell.classList.remove('arena-entering');
            }
            locateMouseAndRefreshChart();
            hasInitializedPositions = true;
            ensureLiveTradingStarted();
          }, 1650);
        }, 250);
      }
    }, 25);

    // Safety fallback: ensure splash screen never hangs longer than 3.5 seconds
    // (defers while reset_arena is still mid-rebuild so half-reset state is never exposed)
    const runSplashSafetyFallback = () => {
      if (splashCompleted) return;
      if (isResettingArena) {
        splashSafetyTimer = setTimeout(runSplashSafetyFallback, 1000);
        return;
      }
      splashCompleted = true;
      hasFirstChartDrawn = true;
      hasFirstTableRendered = true;
      setSplashTarget(100);
      splashProgress = 100;
      if (splashLoop) {
        clearInterval(splashLoop);
        splashLoop = null;
      }
      if (document.body) {
        document.body.classList.add('arena-ready');
      }
      const appShell = document.querySelector('.app-shell');
      if (appShell) {
        appShell.style.opacity = '1';
        appShell.classList.add('arena-entering');
      }
      const overlayEl = document.getElementById('splashOverlay');
      if (overlayEl) {
        overlayEl.classList.add('fade-out');
        scheduleSplashTimer(() => {
          overlayEl.style.display = 'none';
          overlayEl.classList.remove('fade-out');
          if (appShell) appShell.classList.remove('arena-entering');
        }, 1200);
      }
      locateMouseAndRefreshChart();
      hasInitializedPositions = true;
      ensureLiveTradingStarted();
    };
    splashSafetyTimer = setTimeout(runSplashSafetyFallback, 3500);
  } catch (err) {
    console.error('CRITICAL: startSplashSequence failed, recovering arena display:', err);
    splashCompleted = true;
    if (document.body) document.body.classList.add('arena-ready');
    const appShell = document.querySelector('.app-shell');
    if (appShell) {
      appShell.style.opacity = '1';
      appShell.classList.add('arena-entering');
    }
    const overlay = document.getElementById('splashOverlay');
    if (overlay) {
      overlay.style.display = 'none';
      overlay.classList.remove('fade-out');
    }
  }
}

// The exit gate: first chart frame drawn, first tables rendered, and the
// minimum splash duration elapsed. The bar must not show 100% while this
// is closed.
function isSplashGateOpen() {
  return hasFirstChartDrawn && hasFirstTableRendered &&
    (performance.now() - splashStartTimeMs) >= splashMinDurationMs;
}

function setSplashTarget(percent) {
  if (splashCompleted) return;
  // Honest 100%: while the gate is closed the target is capped at 90,
  // so the displayed percent (and the final step label) can never claim
  // the arena is ready before it is. The animation loop releases the
  // cap to 100 the moment the gate opens.
  const cap = isSplashGateOpen() ? 100 : 90;
  targetSplashProgress = Math.min(cap, Math.max(targetSplashProgress, percent));
}

function updateSplashProgress(percent) {
  setSplashTarget(percent);
}

// Coordinated boot sequence: check onboarding status before showing arena or splash
async function initAppBoot() {
  if (hasBootInitiated) return;
  hasBootInitiated = true;

  if (document.body) {
    document.body.classList.remove('arena-ready');
  }
  const appShell = document.querySelector('.app-shell');
  if (appShell) {
    appShell.style.opacity = '0';
    appShell.classList.remove('arena-entering');
  }

  let needsOnboarding = false;
  let setupCheckedOk = false;
  if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.get_setup_status === 'function') {
    try {
      const res = await window.pywebview.api.get_setup_status();
      if (res && res.status === 'ok') {
        setupCheckedOk = true;
        if (typeof res.gateway_port === 'number') {
          window.__tradebotGatewayPort = res.gateway_port;
        }
        if ((!res.onboarding_completed && !res.skip_ai_mode) || res.admin_password_required) {
          needsOnboarding = true;
        } else {
          hasCompletedSetup = true;
        }
      }
    } catch (e) {
      console.debug('Initial get_setup_status err:', e);
    }
  }

  if (setupCheckedOk) {
    hasCheckedOnboarding = true;
  }
  hasBootResolved = true;

  if (needsOnboarding) {
    const overlay = document.getElementById('splashOverlay');
    if (overlay) overlay.style.display = 'none';
    openSetupWizardModal(false);
  } else {
    startSplashSequence(false);
  }
}

if (window.pywebview && window.pywebview.api) {
  initAppBoot();
} else {
  window.addEventListener('pywebviewready', () => {
    if (!hasBootInitiated) {
      initAppBoot();
    } else if (!hasCheckedOnboarding) {
      checkOnboardingBoot();
    }
  });
  setTimeout(() => {
    if (!hasBootInitiated) {
      initAppBoot();
    }
  }, 2500);
}

// Latest state & mode tracking initialized at top of script

// Color & Motion Helpers
function hexToRgba(hex, alpha) {
  if (!hex || hex[0] !== '#') return `rgba(255, 184, 0, ${alpha})`;
  let c = hex.substring(1);
  if (c.length === 3) c = c.split('').map(x => x + x).join('');
  const num = parseInt(c, 16);
  const r = (num >> 16) & 255;
  const g = (num >> 8) & 255;
  const b = num & 255;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

// Active Motion Beacons & Animation Loop
let chartBeacons = [];
let animFrameId = null;

function addChartBeacon(s) {
  if (!s || !s.entry_price) return;
  const tagMap = {
    'comp_agg': 'AGG',
    'comp_cons': 'CONS',
    'comp_trail': 'TRAIL',
    'comp_orb': 'ORB',
    'comp_vwap': 'MEAN'
  };
  chartBeacons.push({
    id: s.id,
    stratTag: tagMap[s.id] || (s.name ? s.name.slice(0, 4) : 'STRAT'),
    color: s.color || '#F59E0B',
    price: Number(s.entry_price),
    startTime: Date.now(),
    duration: 3800
  });
  if (chartBeacons.length > 5) chartBeacons.shift();
  triggerAnimLoop();
}

function triggerAnimLoop() {
  if (typeof startChartAnimLoop === 'function') {
    startChartAnimLoop();
  }
}

// ==========================================================================
// TOAST NOTIFICATION STAGGER QUEUE & MICRO-INTERACTIONS
// ==========================================================================
// Toast queue & parameters initialized at top of script
const TOAST_STAGGER_MS = 380; // 380ms stagger ensures crisp sequential cascade entry and exit

const MAX_TOAST_QUEUE = 24;

function enqueueToast(toastItem) {
  if (!toastItem || typeof toastItem.renderElement !== 'function') return;
  if (toastQueue.length >= MAX_TOAST_QUEUE) {
    toastQueue.shift();
  }
  toastQueue.push(toastItem);
  scheduleProcessToastQueue(0);
}

  function scheduleProcessToastQueue(delayMs = 0) {
    if (toastStaggerTimer) return;
    toastStaggerTimer = setTimeout(() => {
      toastStaggerTimer = null;
      processToastQueue();
  }, delayMs);
}

function syncToastStackLayout() {
  const container = document.getElementById('chartNotificationContainer');
  if (!container) return;
  const items = Array.from(container.children).filter(el => el.classList && el.classList.contains('toast-stack-item') && !el.classList.contains('toast-exit'));
  if (items.length === 0) {
    container.style.setProperty('--toast-host-h', '0px');
    container.style.setProperty('--toast-host-expanded-h', '0px');
    return;
  }
  let expandedY = 0;
  let frontH = 92;
  // Most recent toast sits at the front (index 0)
  const ordered = items.slice().reverse();
  ordered.forEach((el, idx) => {
    const h = el.offsetHeight || 96;
    if (idx === 0) frontH = h;
    const collapsedY = idx * 10;
    const scale = Math.max(0.86, 1 - idx * 0.045);
    el.style.setProperty('--stack-idx', String(idx));
    el.style.setProperty('--stack-y', collapsedY + 'px');
    el.style.setProperty('--stack-scale', scale.toFixed(3));
    el.style.setProperty('--stack-expanded-y', expandedY + 'px');
    expandedY += h + 8;
  });
  const collapsedTotal = frontH + Math.max(0, ordered.length - 1) * 10;
  container.style.setProperty('--toast-host-h', collapsedTotal + 'px');
  container.style.setProperty('--toast-host-expanded-h', Math.max(collapsedTotal, expandedY) + 'px');
}

function processToastQueue() {
  const container = document.getElementById('chartNotificationContainer');
  if (!container) return;

  // Count active non-exiting toasts currently mounted in container
  const activeToasts = Array.from(container.children).filter(el => !el.classList.contains('toast-exit'));

  // Up to MAX_VISIBLE_TOASTS (3) stacked cards
  if (activeToasts.length >= MAX_VISIBLE_TOASTS || toastQueue.length === 0) {
    return;
  }

  // Dequeue and render exactly ONE item
  const nextItem = toastQueue.shift();
  if (nextItem) {
    const toastEl = nextItem.renderElement();
    if (toastEl) {
      toastEl.classList.add('toast-stack-item');
      container.appendChild(toastEl);
      attachToastInteractions(toastEl, container, TOAST_DURATION_MS);
      requestAnimationFrame(syncToastStackLayout);
    }
  }

  // If more in queue and slots available, stagger entrance by TOAST_STAGGER_MS (380ms)
  const updatedActive = Array.from(container.children).filter(el => !el.classList.contains('toast-exit'));
  if (toastQueue.length > 0 && updatedActive.length < MAX_VISIBLE_TOASTS) {
    scheduleProcessToastQueue(TOAST_STAGGER_MS);
  }
}

function dismissToast(toast) {
  if (!toast || toast._isDismissing) return;
  toast._isDismissing = true;
  if (toast._countdownInterval) {
    clearInterval(toast._countdownInterval);
    toast._countdownInterval = null;
  }
  if (toast._dismissTimeout) {
    clearTimeout(toast._dismissTimeout);
    toast._dismissTimeout = null;
  }
  toast.classList.add('toast-exit');
  syncToastStackLayout();

  // Smooth 450ms exit transition matching CSS
  setTimeout(() => {
    if (toast.parentNode) {
      toast.parentNode.removeChild(toast);
    }
    syncToastStackLayout();
    // As soon as a slot is freed, check the queue and slide in the next waiting toast
    if (toastQueue.length > 0) {
      scheduleProcessToastQueue(0);
    }
  }, 450);
}

function attachToastInteractions(toast, container, totalDurationMs = 5500) {
  toast._totalDurationMs = totalDurationMs;
  toast._remainingMs = totalDurationMs;
  toast._startTime = Date.now();
  toast._isPaused = false;
  toast._isDismissing = false;
  toast._createdAt = Date.now();

  const closeBtn = toast.querySelector('.toast-close');
  if (closeBtn) {
    closeBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      dismissToast(toast);
    });
  }

  const ringFill = toast.querySelector('.toast-ring-fill');
  if (ringFill) {
    ringFill.style.animation = `toastRingDrain ${totalDurationMs}ms linear forwards`;
  }

  const scheduleDismiss = (ms) => {
    if (toast._dismissTimeout) clearTimeout(toast._dismissTimeout);
    toast._startTime = Date.now();
    toast._dismissTimeout = setTimeout(() => {
      toast._dismissTimeout = null;
      dismissToast(toast);
    }, Math.max(0, ms));
  };
  scheduleDismiss(totalDurationMs);

  toast.addEventListener('mouseenter', () => {
    if (toast._isDismissing) return;
    toast._isPaused = true;
    if (toast._dismissTimeout) {
      clearTimeout(toast._dismissTimeout);
      toast._dismissTimeout = null;
    }
    toast._remainingMs = Math.max(0, toast._remainingMs - (Date.now() - toast._startTime));
  });

  toast.addEventListener('mouseleave', () => {
    if (toast._isDismissing) return;
    toast._isPaused = false;
    scheduleDismiss(toast._remainingMs);
  });
}

// Global watchdog timer: dismisses any stale toast older than 18 seconds that is not hovered
toastWatchdogInterval = setInterval(() => {
  if (document.hidden) return;
  const container = document.getElementById('chartNotificationContainer');
  if (!container) return;
  const now = Date.now();
  Array.from(container.children).forEach(toast => {
    if (!toast._isDismissing && (now - (toast._createdAt || now) > 18000) && !toast.matches(':hover')) {
      dismissToast(toast);
    }
  });
}, 2500);

function createPositionToastElement(strat) {
  const tagMap = {
    'comp_agg': 'Aggressive Momentum',
    'comp_cons': 'Conservative Scalper',
    'comp_trail': 'Trailing Guard',
    'comp_orb': 'ORB Breakout (15m)',
    'comp_vwap': 'Session Mean'
  };
  const stratName = escapeHtml(tagMap[strat.id] || strat.name || 'Quant Strategy');
  const sColor = sanitizeCssColor(strat.color, '#F59E0B');
  const entryP = Number(strat.entry_price || 0);
  const tpP = Number(strat.take_profit || 0);
  const slP = Number(strat.stop_loss || 0);
  const qty = Number(strat.qty || 0);
  const isShort = strat.position_side === 'SHORT';
  const sideVerb = isShort ? 'SHORT' : 'LONG';
  const badgeCls = isShort ? 'badge-short' : 'badge-long';
  const sideVerbCls = isShort ? 'down' : 'up';

  const tpPct = (entryP > 0 && tpP > 0) ? ((Math.abs(tpP - entryP) / entryP) * 100).toFixed(2) : null;
  const slPct = (entryP > 0 && slP > 0) ? ((Math.abs(entryP - slP) / entryP) * 100).toFixed(2) : null;

  const toast = document.createElement('div');
  toast.className = 'chart-toast';
  toast.style.setProperty('--toast-color', sColor);
  toast.style.setProperty('--toast-glow', hexToRgba(sColor, 0.28));

  const timeStr = new Date().toTimeString().split(' ')[0];

  toast.innerHTML = `
    <div class="toast-ambient-glow"></div>
    <div class="toast-body">
      <div class="toast-top-row">
        <span class="toast-tag" style="color:${sColor};background:${hexToRgba(sColor, 0.12)};border-color:${hexToRgba(sColor, 0.28)};">
          <span class="toast-pulse-dot" style="background:${sColor};box-shadow:0 0 6px ${sColor};"></span>
          <span class="toast-strat-name">${strat.rank ? `#${strat.rank} ` : ''}${stratName}</span>
        </span>
        <span class="toast-action-badge ${badgeCls}">OPEN ${sideVerb}</span>
        <div class="toast-meta-right">
          <span class="toast-clock num">${timeStr}</span>
          <div class="toast-countdown-ring" title="Remaining time">
            <svg viewBox="0 0 20 20" width="14" height="14">
              <circle class="toast-ring-bg" cx="10" cy="10" r="7"></circle>
              <circle class="toast-ring-fill" cx="10" cy="10" r="7"></circle>
            </svg>
          </div>
          <button class="toast-close" type="button" title="Dismiss" aria-label="Dismiss">
            <svg viewBox="0 0 12 12" width="8" height="8" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
              <path d="M2.5 2.5l7 7M9.5 2.5l-7 7"></path>
            </svg>
          </button>
        </div>
      </div>
      <div class="toast-main-row">
        <div class="toast-qty-col">
          <span class="side-verb ${sideVerbCls}">${sideVerb}</span>
          <strong>${qty.toFixed(4)}</strong>
          <span class="asset-tag">ETH</span>
        </div>
        <div class="toast-price-col">
          <span class="price-label">Entry</span>
          <span class="price-value">$${entryP.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
        </div>
      </div>
      <div class="toast-bracket-row">
        <div class="toast-bracket-pill up">
          <span class="pill-target-lbl">TP</span>
          <span class="pill-target-val">$${tpP > 0 ? tpP.toFixed(1) : '--'}</span>
          ${tpPct ? `<span class="pill-target-delta">(+${tpPct}%)</span>` : ''}
        </div>
        <div class="toast-bracket-pill down">
          <span class="pill-target-lbl">SL</span>
          <span class="pill-target-val">$${slP > 0 ? slP.toFixed(1) : '--'}</span>
          ${slPct ? `<span class="pill-target-delta">(-${slPct}%)</span>` : ''}
        </div>
      </div>
    </div>
  `;
  return toast;
}

function showPositionToast(strat) {
  if (!strat) return;
  enqueueToast({
    id: `entry_${strat.id}_${Date.now()}`,
    renderElement: () => createPositionToastElement(strat)
  });
}

function showChartToast(opts = {}) {
  const title = escapeHtml(opts.triggerReason || 'Arena Event');
  const priceStr = opts.price ? `$${Number(opts.price).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '';
  const action = escapeHtml(opts.action || 'SYNC');
  const symStr = escapeHtml(opts.symbol || 'ETH/USD');
  const color = '#10F5A0';

  enqueueToast({
    id: `event_${Date.now()}_${Math.random()}`,
    renderElement: () => {
      const toast = document.createElement('div');
      toast.className = 'chart-toast';
      toast.style.setProperty('--toast-color', color);
      toast.style.setProperty('--toast-glow', hexToRgba(color, 0.28));

      const timeStr = new Date().toTimeString().split(' ')[0];
      toast.innerHTML = `
        <div class="toast-ambient-glow"></div>
        <div class="toast-body">
          <div class="toast-top-row">
            <span class="toast-tag" style="color:${color};background:${hexToRgba(color, 0.12)};border-color:${hexToRgba(color, 0.28)};">
              <span class="toast-pulse-dot" style="background:${color};box-shadow:0 0 6px ${color};"></span>
              <span class="toast-strat-name">${title}</span>
            </span>
            <span class="toast-action-badge badge-long">${action}</span>
            <div class="toast-meta-right">
              <span class="toast-clock num">${timeStr}</span>
              <button class="toast-close" type="button" title="Dismiss" aria-label="Dismiss">
                <svg viewBox="0 0 12 12" width="8" height="8" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                  <path d="M2.5 2.5l7 7M9.5 2.5l-7 7"></path>
                </svg>
              </button>
            </div>
          </div>
          <div class="toast-main-row" style="margin-top:6px;">
            <div class="toast-qty-col">
              <span class="side-verb up">${symStr}</span>
            </div>
            <div class="toast-price-col">
              <span class="price-value" style="font-size:12px;">${priceStr}</span>
            </div>
          </div>
        </div>
      `;
      return toast;
    }
  });
}

function createPositionClosedToastElement(strat, fill, prevPos) {
  const tagMap = {
    'comp_agg': 'Aggressive Momentum',
    'comp_cons': 'Conservative Scalper',
    'comp_trail': 'Trailing Guard',
    'comp_orb': 'ORB Breakout (15m)',
    'comp_vwap': 'Session Mean'
  };
  const stratName = escapeHtml(tagMap[strat.id] || strat.name || 'Quant Strategy');
  const rawTrigger = (fill && (fill.trigger || fill.reason)) ? String(fill.trigger || fill.reason) : 'Strategy Exit';
  const trigger = escapeHtml(rawTrigger);
  const trigLower = rawTrigger.toLowerCase();
  const isTP = trigLower.includes('profit') || trigLower.includes('take profit');
  const isSL = trigLower.includes('loss') || trigLower.includes('stop loss') || trigLower.includes('trailing stop') || trigLower.includes('liquidation') || trigLower.includes('circuit breaker');

  let pnlVal = 0;
  if (fill && fill.pnl !== null && fill.pnl !== undefined) {
    pnlVal = Number(fill.pnl);
  } else if (prevPos && prevPos.entry_price > 0 && latestState && latestState.quote && latestState.quote.price) {
    const entry = Number(prevPos.entry_price);
    const exit = Number(latestState.quote.price);
    const qty = Number(prevPos.qty || 1);
    const isShort = prevPos.position_side === 'SHORT';
    pnlVal = isShort ? ((entry - exit) * qty) : ((exit - entry) * qty);
  }

  const isProfit = pnlVal >= 0;
  const pnlCls = isProfit ? 'up' : 'down';
  const badgeCls = isTP ? 'badge-tp' : (isSL ? 'badge-sl' : (isProfit ? 'badge-long' : 'badge-short'));
  const badgeText = isTP ? 'TAKE PROFIT' : (isSL ? 'STOP LOSS' : 'POSITION CLOSED');
  const sColor = isProfit ? '#10B981' : '#EF4444';
  const exitPrice = (fill && fill.price) ? Number(fill.price) : Number((latestState && latestState.quote && latestState.quote.price) || 0);
  const qty = (fill && fill.qty) ? Number(fill.qty) : Number((prevPos && prevPos.qty) || 0);

  const toast = document.createElement('div');
  toast.className = 'chart-toast';
  toast.style.setProperty('--toast-color', sColor);
  toast.style.setProperty('--toast-glow', hexToRgba(sColor, 0.32));

  const timeStr = escapeHtml((fill && fill.time) ? fill.time : new Date().toTimeString().split(' ')[0]);

  toast.innerHTML = `
    <div class="toast-ambient-glow"></div>
    <div class="toast-body">
      <div class="toast-top-row">
        <span class="toast-tag" style="color:${sColor};background:${hexToRgba(sColor, 0.12)};border-color:${hexToRgba(sColor, 0.28)};">
          <span class="toast-pulse-dot" style="background:${sColor};box-shadow:0 0 6px ${sColor};"></span>
          <span class="toast-strat-name">${strat.rank ? `#${strat.rank} ` : ''}${stratName}</span>
        </span>
        <span class="toast-action-badge ${badgeCls}">${badgeText}</span>
        <div class="toast-meta-right">
          <span class="toast-clock num">${timeStr}</span>
          <div class="toast-countdown-ring" title="Remaining time">
            <svg viewBox="0 0 20 20" width="14" height="14">
              <circle class="toast-ring-bg" cx="10" cy="10" r="7"></circle>
              <circle class="toast-ring-fill" cx="10" cy="10" r="7"></circle>
            </svg>
          </div>
          <button class="toast-close" type="button" title="Dismiss" aria-label="Dismiss">
            <svg viewBox="0 0 12 12" width="8" height="8" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
              <path d="M2.5 2.5l7 7M9.5 2.5l-7 7"></path>
            </svg>
          </button>
        </div>
      </div>
      <div class="toast-main-row">
        <div class="toast-qty-col">
          <span class="side-verb ${pnlCls}">CLOSED</span>
          <strong>${qty > 0 ? qty.toFixed(4) : '--'}</strong>
          <span class="asset-tag">ETH</span>
        </div>
        <div class="toast-price-col">
          <span class="price-label">Exit</span>
          <span class="price-value">$${exitPrice.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
        </div>
      </div>
      <div class="toast-bracket-row">
        <div class="toast-pnl-pill ${pnlCls}">
          <span>Realized PnL: <strong>${pnlVal >= 0 ? '+' : '-'}$${Math.abs(pnlVal).toFixed(2)}</strong></span>
          <span class="toast-pnl-trigger">${trigger}</span>
        </div>
      </div>
    </div>
  `;
  return toast;
}

function showPositionClosedToast(strat, fill, prevPos) {
  if (!strat) return;
  enqueueToast({
    id: `exit_${strat.id}_${Date.now()}`,
    renderElement: () => createPositionClosedToastElement(strat, fill, prevPos)
  });
}

let previewToastToggle = false;
function previewPositionAnimation() {
  if (!latestState) return;
  const strategies = latestState.strategies || [];
  if (strategies.length === 0) return;
  const inPosStrat = strategies.find(s => s.in_position);
  const chosen = inPosStrat || strategies[Math.floor(Math.random() * strategies.length)];
  const spot = Number((latestState.quote && latestState.quote.price) || 2500.0);

  previewToastToggle = !previewToastToggle;
  if (previewToastToggle) {
    const mock = {
      ...chosen,
      entry_price: spot,
      take_profit: Number((spot + (chosen.id === 'comp_cons' ? 22.0 : 48.0)).toFixed(2)),
      stop_loss: Number((spot - (chosen.id === 'comp_cons' ? 14.0 : 28.0)).toFixed(2)),
      qty: chosen.qty > 0 ? chosen.qty : 8.5000,
      in_position: true
    };
    showPositionToast(mock);
    addChartBeacon(mock);
  } else {
    previewPositionClosedAnimation();
  }
}

function previewPositionClosedAnimation() {
  if (!latestState) return;
  const strategies = latestState.strategies || [];
  if (strategies.length === 0) return;
  const chosen = strategies[Math.floor(Math.random() * strategies.length)];
  const spot = Number((latestState.quote && latestState.quote.price) || 2500.0);
  const isWin = Math.random() > 0.4;
  const pnl = isWin ? Number((Math.random() * 85 + 15).toFixed(2)) : -Number((Math.random() * 45 + 10).toFixed(2));
  const mockFill = {
    trigger: isWin ? 'Take Profit' : 'Stop Loss',
    pnl: pnl,
    price: spot,
    qty: 6.25,
    time: new Date().toTimeString().split(' ')[0]
  };
  showPositionClosedToast(chosen, mockFill, null);
}

window.previewPositionAnimation = previewPositionAnimation;
window.previewPositionClosedAnimation = previewPositionClosedAnimation;

// Position tracking maps initialized at top of script

function setScaleMode(mode) {
  scaleMode = mode;
  syncSegThumb('scaleModeSeg', mode === 'auto' ? 0 : 1);
  if (latestState) drawPriceChart(latestState);
}

const fmtUsd = (val, digits = 2) => {
  const n = Number(val || 0);
  return '$' + n.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits });
};

const fmtSignedUsd = (val) => {
  const n = Number(val || 0);
  const sign = n >= 0 ? '+' : '-';
  return sign + '$' + Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

const fmtPct = (val) => {
  const n = Number(val || 0);
  return (n >= 0 ? '+' : '') + n.toFixed(2) + '%';
};

const fmtTimeSec = (totalSec) => {
  const s = Math.max(0, Math.floor(totalSec));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) {
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
  }
  return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
};

async function pollBackend() {
  if (document.hidden) return;
  if (!hasBootResolved || isResettingArena) return;
  if (isPolling || pendingControlActions > 0) return;
  if (isWizardOpen && !hasCompletedSetup) {
    // Hold background arena activity while initial setup wizard is open
    return;
  }
  isPolling = true;
  const pollEpoch = ++stateApplyEpoch;
  let useDelta = false;
  try {
    if (window.pywebview && window.pywebview.api) {
      checkOnboardingBoot();
      useDelta = Boolean(latestState && Array.isArray(latestState.candles) && typeof window.pywebview.api.get_state_delta === 'function');
      const state = useDelta
        ? await window.pywebview.api.get_state_delta(forceNextFullDelta)
        : await window.pywebview.api.get_state();
      if (state && pollEpoch === stateApplyEpoch) {
        forceNextFullDelta = false;
        if (state.candles_unchanged && latestState && latestState.candles) {
          state.candles = latestState.candles;
        }
        if (state.fills_unchanged && latestState && latestState.fills) {
          state.fills = latestState.fills;
        }
        if (state.history_unchanged && latestState) {
          if (latestState.price_history) state.price_history = latestState.price_history;
          if (latestState.ema_fast_history) state.ema_fast_history = latestState.ema_fast_history;
          if (latestState.ema_slow_history) state.ema_slow_history = latestState.ema_slow_history;
        }
        if (state.intel_events_unchanged && state.intel_hub && latestState && latestState.intel_hub && latestState.intel_hub.events) {
          state.intel_hub.events = latestState.intel_hub.events;
        }
        latestState = state;
        if (!splashCompleted && !isWizardOpen) {
          const hasQuote = state.quote && (state.quote.price > 0 || state.quote.is_offline);
          const candleCount = (state.candles && state.candles.length) || 0;
          const isBootstrapped = Boolean(state.is_bootstrapped);
          const hasZhNews = Boolean(state.intel_hub && state.intel_hub.events && state.intel_hub.events.length > 0 &&
            state.intel_hub.events.some(e => /[\u4e00-\u9fff]/.test(e.headline || '')));

          if (hasQuote) {
            setSplashTarget(35);
          }
          if (isBootstrapped) {
            setSplashTarget(55);
          }
          if (isBootstrapped && (hasZhNews || candleCount >= 20)) {
            setSplashTarget(75);
          }
          if (isBootstrapped && candleCount >= 30 && hasZhNews && hasFirstTableRendered) {
            setSplashTarget(90);
          }
          if (isBootstrapped && candleCount >= 30 && hasZhNews && hasFirstChartDrawn && hasFirstTableRendered) {
            setSplashTarget(100);
          }
        }

        if (state.is_bootstrapped && splashCompleted && !state.live_orders_enabled) {
          ensureLiveTradingStarted();
        }

        // Position change detector
        const currentStrats = state.strategies || [];
        if (!hasInitializedPositions || !splashCompleted) {
          currentStrats.forEach(s => {
            knownStrategyPositions[s.id] = {
              in_position: Boolean(s.in_position),
              entry_price: Number(s.entry_price || 0),
              qty: Number(s.qty || 0),
              trades: Number(s.closed_trades || 0),
              position_side: s.position_side || 'LONG'
            };
          });
        } else {
          const newEntryStrats = [];
          const closedStrats = [];

          currentStrats.forEach(s => {
            const prev = knownStrategyPositions[s.id];
            const isNowInPos = Boolean(s.in_position);
            const wasInPos = prev ? Boolean(prev.in_position) : false;
            const curEntry = Number(s.entry_price || 0);
            const prevEntry = prev ? Number(prev.entry_price || 0) : 0;
            const curSide = s.position_side || 'LONG';
            const prevSide = prev ? (prev.position_side || 'LONG') : 'LONG';

            const curTrades = Number(s.closed_trades || 0);
            const prevTrades = prev ? Number(prev.trades || 0) : 0;

            const isNewEntry = (isNowInPos && !wasInPos) ||
              (isNowInPos && wasInPos && (
                (curEntry > 0 && prevEntry > 0 && Math.abs(curEntry - prevEntry) > 0.05) ||
                (curSide !== prevSide) ||
                (curTrades > prevTrades)
              ));

            const isClosed = (wasInPos && !isNowInPos) ||
              (wasInPos && isNowInPos && curTrades > prevTrades);

            if (splashCompleted) {
              if (isClosed) {
                closedStrats.push({ strat: s, prev: prev });
              }
              if (isNewEntry) {
                newEntryStrats.push(s);
              }
            }

            knownStrategyPositions[s.id] = {
              in_position: isNowInPos,
              entry_price: curEntry,
              qty: Number(s.qty || 0),
              trades: Number(s.closed_trades || 0),
              position_side: curSide
            };
          });

          if (newEntryStrats.length > 0) {
            // Sort by current leaderboard rank ascending: Rank #1 is enqueued FIRST!
            newEntryStrats.sort((a, b) => {
              const rankA = Number(a.rank) || 99;
              const rankB = Number(b.rank) || 99;
              if (rankA !== rankB) return rankA - rankB;
              return (Number(b.roi_pct) || 0) - (Number(a.roi_pct) || 0);
            });
            newEntryStrats.forEach(s => {
              showPositionToast(s);
              addChartBeacon(s);
            });
          }

          if (closedStrats.length > 0) {
            closedStrats.forEach(({ strat: s, prev }) => {
              const sShort = (s.name || s.id || '').toLowerCase();
              const latestExitFill = (state.fills || []).find(f => {
                if (!f || f.is_entry) return false;
                const stratF = (f.strategy || '').toLowerCase().trim();
                if (!stratF) return false;
                return stratF.includes(s.id.replace('comp_', '')) || sShort.includes(stratF);
              });
              showPositionClosedToast(s, latestExitFill, prev);
            });
          }
        }

        renderAll(state);
      } else if (useDelta) {
        // Discarded delta advanced backend watermarks; request a full payload next tick.
        forceNextFullDelta = true;
      }
    }
  } catch (err) {
    if (useDelta) forceNextFullDelta = true;
    console.error("Bridge poll error:", err);
  } finally {
    isPolling = false;
  }
}

async function triggerEvolution() {
  if (!window.pywebview || !window.pywebview.api) return;
  pendingControlActions += 1;
  const myEpoch = ++stateApplyEpoch;
  try {
    const state = await window.pywebview.api.evolve_now();
    if (state && myEpoch === stateApplyEpoch) { latestState = state; renderAll(state); }
  } catch (err) {
    console.warn('evolve_now error:', err);
  } finally {
    pendingControlActions = Math.max(0, pendingControlActions - 1);
  }
}

async function togglePause() {
  if (!window.pywebview || !window.pywebview.api) return;
  // Immediate optimistic toggle for zero-latency UI transition
  const prevPaused = Boolean(latestState && latestState.paused);
  const willPause = !prevPaused;
  const applyPauseChrome = (pausedVal) => {
    document.body.classList.toggle('arena-paused', pausedVal);
    const pauseBtn = document.getElementById('pauseBtn');
    if (pauseBtn) {
      const nextLbl = pausedVal ? 'Resume Feed' : 'Pause Feed';
      pauseBtn._lastLabel = nextLbl;
      const swapLbl = pauseBtn.querySelector('.action-swap-label');
      if (swapLbl) {
        if (swapLbl.textContent !== nextLbl) swapLbl.textContent = nextLbl;
      } else {
        pauseBtn.innerHTML = `<span class="action-swap-label">${nextLbl}</span>`;
      }
      pauseBtn.classList.toggle('is-morphed', pausedVal);
      pauseBtn.classList.toggle('btn-paused-active', pausedVal);
      pauseBtn.title = pausedVal ? 'Resume Live Feed (Press Space)' : 'Pause Live Feed (Press Space)';
    }
    const badge = document.getElementById('liveBadge');
    const statusText = document.getElementById('liveStatusText');
    if (badge && statusText) {
      badge.classList.toggle('is-paused', pausedVal);
      statusText.textContent = pausedVal ? 'Paused' : 'Live 24/7';
    }
    if (latestState) {
      latestState.paused = pausedVal;
    }
    if (typeof syncAmbientShaderMotion === 'function') syncAmbientShaderMotion();
    updateUiClockDisplay();
  };
  applyPauseChrome(willPause);

  pendingControlActions += 1;
  const myEpoch = ++stateApplyEpoch;
  try {
    const state = await window.pywebview.api.toggle_pause();
    if (state && myEpoch === stateApplyEpoch) {
      latestState = state;
      document.body.classList.toggle('arena-paused', Boolean(state.paused));
      renderAll(state);
    }
  } catch (err) {
    console.warn('toggle_pause error:', err);
    if (myEpoch === stateApplyEpoch) {
      applyPauseChrome(prevPaused);
    }
  } finally {
    pendingControlActions = Math.max(0, pendingControlActions - 1);
  }
}

function pulseAutoEvolveStretch() {
  const autoBtn = document.getElementById('autoEvolveToggleBtn');
  if (!autoBtn) return;
  autoBtn.classList.remove('lg-switch--stretching');
  void autoBtn.offsetWidth;
  autoBtn.classList.add('lg-switch--stretching');
  if (autoBtn._stretchTimer) clearTimeout(autoBtn._stretchTimer);
  autoBtn._stretchTimer = setTimeout(() => {
    autoBtn._stretchTimer = null;
    autoBtn.classList.remove('lg-switch--stretching');
  }, 240);
}

async function toggleAutoEvolve() {
  if (!window.pywebview || !window.pywebview.api) return;
  pulseAutoEvolveStretch();
  pendingControlActions += 1;
  const myEpoch = ++stateApplyEpoch;
  try {
    const state = await window.pywebview.api.toggle_auto_evolve();
    if (state && myEpoch === stateApplyEpoch) { latestState = state; renderAll(state); }
  } catch (err) {
    console.warn('toggle_auto_evolve error:', err);
  } finally {
    pendingControlActions = Math.max(0, pendingControlActions - 1);
  }
}

async function changeEvolveInterval(seconds) {
  if (!window.pywebview || !window.pywebview.api) return;
  const sec = parseInt(seconds, 10);
  if (isNaN(sec) || sec <= 0) return;
  pendingControlActions += 1;
  const myEpoch = ++stateApplyEpoch;
  try {
    const state = await window.pywebview.api.set_evolve_interval(sec);
    if (state && myEpoch === stateApplyEpoch) { latestState = state; renderAll(state); }
  } catch (err) {
    console.warn('set_evolve_interval error:', err);
  } finally {
    pendingControlActions = Math.max(0, pendingControlActions - 1);
  }
}

// Custom Gen interval dropdown (2026-11-13): replaces the native <select>.
// The native popup is rendered by the OS/browser and cannot match the
// liquid-glass style, so the picker is a button + menu built on the
// AIMRAN uv-f-dd-scale pattern (scale-from-top menu, staggered option
// entrance, chevron flip) restyled with the Stageshow / liquid-glass
// tokens. Behaviour is unchanged: choosing an interval still calls
// changeEvolveInterval(), which posts to the Python bridge exactly as
// before; backend state changes sync the label via renderAll.
const EVOLVE_INTERVAL_OPTIONS = [
  { seconds: '3600', label: '1h' },
  { seconds: '7200', label: '2h' },
  { seconds: '14400', label: '4h' },
  { seconds: '21600', label: '6h' },
  { seconds: '43200', label: '12h' },
  { seconds: '86400', label: '24h' },
];

function syncEvolveIntervalUI(valueStr) {
  const labelEl = document.getElementById('evolveIntervalLabel');
  const opt = EVOLVE_INTERVAL_OPTIONS.find((o) => o.seconds === valueStr);
  if (labelEl && opt && labelEl.textContent !== opt.label) labelEl.textContent = opt.label;
  const menu = document.getElementById('evolveIntervalMenu');
  if (!menu || menu._lastVal === valueStr) return;
  menu._lastVal = valueStr;
  menu.querySelectorAll('.lg-dropdown__item').forEach((item) => {
    const selected = item.dataset.seconds === valueStr;
    item.classList.toggle('is-selected', selected);
    item.setAttribute('aria-checked', selected ? 'true' : 'false');
  });
}

function toggleEvolveIntervalMenu(force) {
  const dd = document.getElementById('evolveIntervalDropdown');
  const trigger = document.getElementById('evolveIntervalSelect');
  if (!dd || !trigger) return;
  const open = typeof force === 'boolean' ? force : !dd.classList.contains('is-open');
  dd.classList.toggle('is-open', open);
  trigger.setAttribute('aria-expanded', open ? 'true' : 'false');
}

function selectEvolveInterval(seconds) {
  toggleEvolveIntervalMenu(false);
  syncEvolveIntervalUI(String(seconds));
  changeEvolveInterval(seconds);
}

document.addEventListener('click', (event) => {
  const dd = document.getElementById('evolveIntervalDropdown');
  if (dd && dd.classList.contains('is-open') && !dd.contains(event.target)) {
    toggleEvolveIntervalMenu(false);
  }
});

document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') toggleEvolveIntervalMenu(false);
});

let isResettingArena = false;

async function resetArena() {
  if (!window.pywebview || !window.pywebview.api) return;
  if (isResettingArena || !splashCompleted) return;
  isResettingArena = true;
  const myEpoch = ++stateApplyEpoch;
  forceNextFullDelta = true;

  // Reset local tracking states & chart interpolation BEFORE starting splash sequence
  latestState = null;
  knownStrategyPositions = {};
  hasInitializedPositions = false;
  chartBeacons = [];
  lastRenderedFillSig = '';
  lastTopFillSeq = 0;
  animSpot = 0; targetSpot = 0;
  animMinP = 0; targetMinP = 0;
  animMaxP = 0; targetMaxP = 0;
  animCandles = []; targetCandles = [];
  candleSlideOffset = 0;
  lastNewestCandleTime = 0;
  priceHoverPos = null;
  hoveredCandleData = null;
  lastHoverIdx = -1;
  lastHoverSnapY = -1;
  lastPausedCanvasSig = '';
  Object.keys(intelArticleCache).forEach((k) => { delete intelArticleCache[k]; });
  intelExpandedIds.clear();
  intelArticlePreloadQueue.length = 0;

  // Immediately start the reload progress overlay to hide the teardown/rebuild
  startSplashSequence(true);

  try {
    const state = await window.pywebview.api.reset_arena();
    if (state && myEpoch === stateApplyEpoch) {
      latestState = state;
      renderAll(state);
    }
  } catch (err) {
    console.warn('reset_arena error:', err);
  } finally {
    setTimeout(() => {
      isResettingArena = false;
    }, 1000);
  }
}

let rightTab = 'cards'; // 'all', 'cards', 'leaderboard'

function setRightTab(tab) {
  rightTab = tab;
  const idx = tab === 'all' ? 0 : (tab === 'cards' ? 1 : 2);
  syncSegThumb('rightTabSeg', idx);
  const dockBody = document.querySelector('.lg-bento-dock-body');
  const vL = document.getElementById('tabLeaderboardWrap');
  const vC = document.getElementById('tabCardsView');
  if (dockBody) {
    if (tab === 'all') dockBody.classList.add('dual-mode');
    else dockBody.classList.remove('dual-mode');
  }
  if (vC) {
    vC.style.display = 'grid';
  }
  if (vL) {
    vL.style.display = 'block';
  }
}

function showTVConfigInfo() {
  alert(
    `[TradingView Paper Trading Integration Architecture]\n\n` +
    `Q: Why is direct one-click execution to web Paper Trading unsupported?\n` +
    `1. Closed Web Sandbox: Native Paper Trading on tradingview.com does not expose public REST order endpoints or client SDKs.\n` +
    `2. Webhook Directionality: Native Webhooks emit alerts outbound from TradingView, but do not accept arbitrary inbound order execution.\n\n` +
    `Production Automated Trading Solutions:\n` +
    `Option A (Industry Standard): Connect Binance Testnet or Alpaca Paper Trading via TradingView Broker Integration.\n` +
    `Option B (Webhook Dispatch): Use TradingView webhook alert receiver gateways.\n` +
    `Option C (Browser Automation): Playwright headless session agent.\n\n` +
    `Current TradeBot0 State:\n` +
    `The engine autonomously tracks the hourly champion strategy with real-time brackets ready for upstream dispatch.`
  );
}

function renderAll(state) {
  renderHeader(state);
  renderMacroRibbon(state);
  const inIntel = currentMainView === 'intel';
  if (!hasFirstTableRendered || !inIntel) {
    renderTacticalHud(state);
    renderStrategies(state);
    renderLeaderboard(state);
    renderFills(state);
    drawPriceChart(state);
  }
  if (!hasFirstTableRendered || inIntel) {
    renderIntelHub(state);
  }

  // Verify right-side tables are mounted and populated with data
  const lbBody = document.getElementById('leaderboardBody');
  const stratGrid = document.getElementById('tabCardsView');
  const expectedStrats = (Array.isArray(state.strategies) && state.strategies.length > 0) ? state.strategies.length : 5;
  if (lbBody && lbBody.children.length >= expectedStrats && stratGrid && stratGrid.children.length >= expectedStrats) {
    hasFirstTableRendered = true;
  }
}

function isReducedMotionPreferred() {
  return typeof window.matchMedia === 'function'
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

function morphText(el, nextText) {
  if (!el) return;
  const val = String(nextText == null ? '' : nextText);
  if (el._morphedValue === val && el.textContent === val) return;
  const shouldAnimate = el._morphedValue !== undefined
    && !document.hidden
    && !(document.body && document.body.classList.contains('window-hidden'))
    && !isReducedMotionPreferred();
  el._morphedValue = val;
  el.textContent = val;
  if (!shouldAnimate) return;
  el.classList.remove('text-morph-enter');
  void el.offsetWidth;
  el.classList.add('text-morph-enter');
  if (el._morphTimer) clearTimeout(el._morphTimer);
  el._morphTimer = setTimeout(() => {
    el._morphTimer = null;
    el.classList.remove('text-morph-enter');
  }, 240);
}

function updateRollingText(el, nextText, trend = 0) {
  if (!el) return;
  const nextVal = String(nextText == null ? '' : nextText);
  if (el._rollingInitialized && el._rollingValue === nextVal) return;

  const prevVal = el._rollingValue;
  el._rollingValue = nextVal;

  const canRoll = el._rollingInitialized
    && prevVal !== undefined
    && prevVal !== nextVal
    && !document.hidden
    && !(document.body && document.body.classList.contains('window-hidden'))
    && !isReducedMotionPreferred()
    && Boolean(el.offsetParent);

  el._rollingInitialized = true;
  if (el._rollingTimer) {
    clearTimeout(el._rollingTimer);
    el._rollingTimer = null;
  }

  if (!canRoll || nextVal.length > 22) {
    el.textContent = nextVal;
    return;
  }

  const prevChars = Array.from(String(prevVal));
  const nextChars = Array.from(nextVal);
  const padOffset = prevChars.length - nextChars.length;
  const token = (el._rollingToken = (el._rollingToken || 0) + 1);
  const wrap = document.createElement('span');
  wrap.className = 'nf-wrap';
  const cols = [];
  let staggerIdx = 0;

  for (let i = nextChars.length - 1; i >= 0; i--) {
    const ch = nextChars[i];
    const pIdx = i + padOffset;
    const prevCh = pIdx >= 0 && pIdx < prevChars.length ? prevChars[pIdx] : '';
    const isDigit = ch >= '0' && ch <= '9';
    if (isDigit && ch !== prevCh) {
      const col = document.createElement('span');
      const colCls = trend < 0 ? 'nf-digit-col nf-dir-down' : 'nf-digit-col';
      col.className = colCls;
      col.style.setProperty('--nf-i', String(Math.min(staggerIdx, 6)));
      staggerIdx += 1;

      const strip = document.createElement('span');
      strip.className = 'nf-digit-strip';

      const currSpan = document.createElement('span');
      currSpan.className = 'nf-digit-curr';
      currSpan.textContent = ch;

      const prevSpan = document.createElement('span');
      prevSpan.className = 'nf-digit-prev';
      prevSpan.textContent = (prevCh >= '0' && prevCh <= '9') ? prevCh : ch;

      strip.appendChild(currSpan);
      strip.appendChild(prevSpan);
      col.appendChild(strip);
      cols.unshift(col);
    } else {
      const st = document.createElement('span');
      st.className = 'nf-static';
      st.textContent = ch;
      cols.unshift(st);
    }
  }

  if (staggerIdx === 0) {
    el.textContent = nextVal;
    return;
  }

  cols.forEach((node) => wrap.appendChild(node));
  el.textContent = '';
  el.appendChild(wrap);

  requestAnimationFrame(() => {
    if (el._rollingToken !== token) return;
    cols.forEach((node) => {
      if (node.classList && node.classList.contains('nf-digit-col')) {
        node.classList.add('nf-is-rolling');
      }
    });
  });

  el._rollingTimer = setTimeout(() => {
    el._rollingTimer = null;
    if (el._rollingToken !== token) return;
    el.textContent = nextVal;
  }, 270);
}

function renderMacroRibbon(state) {
  const mc = state.macro_commander;
  if (!mc) return;

  const badge = document.getElementById('macroRegimeBadge');
  const regimeTxt = document.getElementById('macroRegimeText');
  const biasTag = document.getElementById('macroBiasTag');
  const multTag = document.getElementById('macroMultTag');
  const vetoTag = document.getElementById('macroVetoTag');
  const omniTag = document.getElementById('macroOmniTag');
  const headline = document.getElementById('macroHeadlineText');

  const catalystHeadline = document.getElementById('macroCatalystHeadline');
  const catalystSummary = document.getElementById('macroCatalystSummary');
  const catalystTime = document.getElementById('macroCatalystTime');
  const catalystImpact = document.getElementById('macroCatalystImpact');
  const macroOrbs = document.getElementById('macroThinkingOrbs');

  if (macroOrbs) {
    const isThinkingActive = mc.status === 'ONLINE' && !Boolean(state.paused);
    macroOrbs.classList.toggle('macro-is-thinking', isThinkingActive);
  }

  if (badge && regimeTxt) {
    // Guarded className: the regime class is part of the final string,
    // so one compare-and-set replaces the reset + add. The badge class
    // set is fully determined here, so the result is identical.
    const nextBadgeCls = 'macro-badge ss-badge lg-island-pill'
      + (mc.regime === 'BULLISH_SURGE' ? ' regime-bullish'
        : mc.regime === 'BEARISH_PANIC' ? ' regime-bearish'
        : mc.regime === 'HIGH_VOLATILITY_CHOP' ? ' regime-chop' : '');
    if (badge.className !== nextBadgeCls) badge.className = nextBadgeCls;
    
    const regimeLabels = {
      'NORMAL': '\u9ad4\u5236: \u5747\u8861\u5e38\u614b',
      'BULLISH_SURGE': '\u9ad4\u5236: \u591a\u982d\u5f37\u52e2',
      'BEARISH_PANIC': '\u9ad4\u5236: \u6050\u614c\u7194\u65b7',
      'HIGH_VOLATILITY_CHOP': '\u9ad4\u5236: \u9ad8\u6ce2\u9707\u76ea'
    };
    const nextRegimeTxt = regimeLabels[mc.regime] || ('\u9ad4\u5236: ' + mc.regime);
    if (regimeTxt.textContent !== nextRegimeTxt) morphText(regimeTxt, nextRegimeTxt);
  }

  if (biasTag) {
    const nextBias = mc.directional_bias || 'BIDIRECTIONAL';
    if (biasTag.textContent !== nextBias) biasTag.textContent = nextBias;
    if (mc.directional_bias === 'LONG_ONLY') biasTag.style.color = '#4ADE80';
    else if (mc.directional_bias === 'SHORT_ONLY') biasTag.style.color = '#FB7185';
    else biasTag.style.color = '';
  }

  if (multTag) {
    const nextMult = (Number(mc.risk_multiplier) || 1.0).toFixed(2) + 'x';
    if (multTag.textContent !== nextMult) multTag.textContent = nextMult;
  }

  if (vetoTag) {
    const nextVeto = String(mc.veto_count_today || 0);
    if (vetoTag.textContent !== nextVeto) vetoTag.textContent = nextVeto;
  }

  if (omniTag) {
    const nextOmni = mc.status === 'ONLINE' ? '\u667a\u8166: \u9023\u7db2\u5728\u7dda' : '\u63a8\u8ad6: \u672c\u6a5f NLP \u6975\u901f';
    if (omniTag.textContent !== nextOmni) omniTag.textContent = nextOmni;
    if (mc.status === 'ONLINE') {
      omniTag.style.color = '#10F5A0';
    } else {
      omniTag.style.color = '#38BDF8';
    }
  }

  if (headline) {
    const nextHeadline = mc.active_headline || '\u5168\u7403\u8a02\u55ae\u6d41\u7dad\u6301\u5b8f\u89c0\u5747\u8861\u3002\u5be6\u6642\u667a\u80fd\u60c5\u5831\u76e3\u63a7\u904b\u884c\u4e2d\u3002';
    if (headline.textContent !== nextHeadline) headline.textContent = nextHeadline;
  }

  // Populate central latest impactful catalyst news
  const evt = mc.latest_event;
  if (evt) {
    if (catalystHeadline) {
      const nextCatHead = evt.headline || evt.raw_title || '';
      if (catalystHeadline.textContent !== nextCatHead) catalystHeadline.textContent = nextCatHead;
    }
    if (catalystSummary) {
      const nextCatSum = evt.summary || '';
      if (catalystSummary.textContent !== nextCatSum) catalystSummary.textContent = nextCatSum;
    }
    if (catalystTime) {
      const nextCatTime = (evt.source || 'Intel Feed') + ' \u00b7 ' + (evt.time || 'Live');
      if (catalystTime.textContent !== nextCatTime) catalystTime.textContent = nextCatTime;
    }
    if (catalystImpact) {
      const acts = evt.strategy_actions;
      if (acts && acts.length > 0) {
        const a = acts[0];
        const nextCatText = '\u64cd\u4f5c: ' + a.name + ' ' + a.action;
        if (catalystImpact.textContent !== nextCatText) catalystImpact.textContent = nextCatText;
        const nextCatCls = 'catalyst-impact-pill ' + (a.badge_cls || 'buy');
        if (catalystImpact.className !== nextCatCls) catalystImpact.className = nextCatCls;
      } else {
        if (mc.directional_bias === 'LONG_ONLY') {
          const nextCatText = '\u7b56\u7565\u653e\u884c: \u591a\u982d\u7a81\u7834 \u00b7 \u5426\u6c7a\u9006\u52e2\u7a7a\u55ae';
          if (catalystImpact.textContent !== nextCatText) catalystImpact.textContent = nextCatText;
          if (catalystImpact.className !== 'catalyst-impact-pill profit') catalystImpact.className = 'catalyst-impact-pill profit';
        } else if (mc.directional_bias === 'SHORT_ONLY') {
          const nextCatText = '\u7b56\u7565\u653e\u884c: \u9ed1\u5929\u9d5d\u7194\u65b7 \u00b7 \u5426\u6c7a\u9006\u52e2\u591a\u55ae';
          if (catalystImpact.textContent !== nextCatText) catalystImpact.textContent = nextCatText;
          if (catalystImpact.className !== 'catalyst-impact-pill loss') catalystImpact.className = 'catalyst-impact-pill loss';
        } else {
          const nextCatText = '\u7b56\u7565\u653e\u884c: 5\u5927\u7b56\u7565\u96d9\u5411\u5168\u958b \u00b7 \u57fa\u6e96\u904b\u4f5c';
          if (catalystImpact.textContent !== nextCatText) catalystImpact.textContent = nextCatText;
          if (catalystImpact.className !== 'catalyst-impact-pill info') catalystImpact.className = 'catalyst-impact-pill info';
        }
      }
    }
  }
}

let lastSpotPrice = 0;
let _hdrRefs = null;
function renderHeader(state) {
  if (!_hdrRefs) {
    _hdrRefs = {
      spotEl: document.getElementById('spotPrice'),
      chgEl: document.getElementById('change24h'),
      bidAskEl: document.getElementById('bidAskSpread'),
      highLowEl: document.getElementById('highLow24h'),
      genLbl: document.getElementById('genLabel'),
      cdEl: document.getElementById('countdownLabel'),
      autoBtn: document.getElementById('autoEvolveToggleBtn'),
      autoLbl: document.getElementById('autoEvolveLabelText'),
      badge: document.getElementById('liveBadge'),
      statusText: document.getElementById('liveStatusText'),
      pauseBtn: document.getElementById('pauseBtn'),
      omniSummary: document.getElementById('omniSummary'),
      srcEl: document.getElementById('omniSourceBadge'),
      qEl: document.getElementById('omniQuotaBadge'),
    };
  }
  const q = state.quote || {};
  const spotEl = _hdrRefs.spotEl;
  const candles = state.candles || [];
  const lastCandleClose = candles.length > 0 ? Number(candles[candles.length - 1].c || 0) : 0;
  const quotePrice = Number(q.price || 0);
  const curP = quotePrice > 0 ? quotePrice : (lastCandleClose > 0 ? lastCandleClose : 0);

  const nextSpotTxt = curP > 0 ? fmtUsd(curP, 2) : '—';
  const spotTrend = lastSpotPrice > 0 ? (curP >= lastSpotPrice ? 1 : -1) : 0;
  if (spotEl) updateRollingText(spotEl, nextSpotTxt, spotTrend);
  lastSpotPrice = curP;

  const chg = Number(q.change_24h_pct || 0);
  const chgEl = _hdrRefs.chgEl;
  const nextChgTxt = fmtPct(chg);
  const nextChgCls = 'stat-val island-delta-pill num ' + (chg >= 0 ? 'up' : 'down');
  const nextSpotCls = 'stat-val spot-hero num ' + (chg >= 0 ? 'up' : 'down');
  if (chgEl) {
    updateRollingText(chgEl, nextChgTxt, chg >= 0 ? 1 : -1);
    if (chgEl.className !== nextChgCls) chgEl.className = nextChgCls;
  }
  if (spotEl && spotEl.className !== nextSpotCls) spotEl.className = nextSpotCls;

  const bidAskEl = _hdrRefs.bidAskEl;
  if (bidAskEl) {
    let nextBidAsk;
    if (q.bid && q.ask && !q.is_offline) {
      nextBidAsk = `${fmtUsd(q.bid, 2)} / ${fmtUsd(q.ask, 2)}`;
    } else if (curP > 0) {
      nextBidAsk = `${fmtUsd(curP, 2)} (Candle)`;
    } else {
      nextBidAsk = '— / —';
    }
    if (bidAskEl.textContent !== nextBidAsk) bidAskEl.textContent = nextBidAsk;
  }

  const highLowEl = _hdrRefs.highLowEl;
  if (highLowEl) {
    let nextHL;
    if (q.high_24h && q.low_24h && !q.is_offline) {
      nextHL = `${fmtUsd(q.high_24h, 0)} / ${fmtUsd(q.low_24h, 0)}`;
    } else if (curP > 0) {
      nextHL = `${fmtUsd(curP, 0)} / ${fmtUsd(curP, 0)}`;
    } else {
      nextHL = '— / —';
    }
    if (highLowEl.textContent !== nextHL) highLowEl.textContent = nextHL;
  }
  const genLbl = _hdrRefs.genLbl;
  if (genLbl) {
    const nextGen = `Gen #${state.generation}`;
    if (genLbl.textContent !== nextGen) genLbl.textContent = nextGen;
  }

  const isPaused = Boolean(state.paused);
  document.body.classList.toggle('arena-paused', isPaused);

  // Auto Evolve Countdown & Interval Sync
  const cdEl = _hdrRefs.cdEl;
  const autoBtn = _hdrRefs.autoBtn;
  if (state.auto_evolve_interval_sec) {
    syncEvolveIntervalUI(String(state.auto_evolve_interval_sec));
  }

  const autoLbl = _hdrRefs.autoLbl;
  const nextCdTxt = fmtTimeSec(state.next_evolve_sec || 0);
  if (cdEl) {
    updateRollingText(cdEl, nextCdTxt, -1);
    if (typeof state.next_evolve_sec_note === 'string' && state.next_evolve_sec_note && cdEl.title !== state.next_evolve_sec_note) {
      cdEl.title = state.next_evolve_sec_note;
    }
  }

  const autoActive = !isPaused && Boolean(state.auto_evolve_enabled);
  const nextCdColor = autoActive ? 'var(--ss-accent-text)' : 'var(--ss-text-faint)';
  const nextAutoOn = autoActive ? 'true' : 'false';
  const nextAutoWord = autoActive ? 'Active' : 'Paused';
  if (cdEl && cdEl.style.color !== nextCdColor) cdEl.style.color = nextCdColor;
  if (autoBtn && autoBtn.dataset.on !== nextAutoOn) {
    if (autoBtn.dataset.on !== undefined) pulseAutoEvolveStretch();
    autoBtn.dataset.on = nextAutoOn;
  }
  if (autoLbl) {
    if (autoLbl.textContent !== nextAutoWord) autoLbl.textContent = nextAutoWord;
  } else if (autoBtn && autoBtn.textContent !== nextAutoWord) {
    autoBtn.textContent = nextAutoWord;
  }

  lastCadenceFeedTs = (q && q.timestamp) || '';
  updateUiClockDisplay();

  const badge = _hdrRefs.badge;
  const statusText = _hdrRefs.statusText;
  const pauseBtn = _hdrRefs.pauseBtn;
  const isOffline = state.market_online === false || (q && q.is_offline);
  const desiredPauseLabel = isPaused ? 'Resume Feed' : 'Pause Feed';
  if (pauseBtn) {
    if (pauseBtn._lastLabel !== desiredPauseLabel) {
      pauseBtn._lastLabel = desiredPauseLabel;
      const swapLbl = pauseBtn.querySelector('.action-swap-label');
      if (swapLbl) {
        swapLbl.textContent = desiredPauseLabel;
      } else {
        pauseBtn.innerHTML = `<span class="action-swap-label">${desiredPauseLabel}</span>`;
      }
    }
    pauseBtn.classList.toggle('is-morphed', isPaused);
    pauseBtn.classList.toggle('btn-paused-active', isPaused);
    const nextPauseTitle = isPaused ? 'Resume Live Feed (Press Space)' : 'Pause Live Feed (Press Space)';
    if (pauseBtn.title !== nextPauseTitle) pauseBtn.title = nextPauseTitle;
  }
  if (badge && statusText) {
    badge.classList.toggle('is-paused', isPaused);
    const nextStatusTxt = isPaused ? 'Paused' : (isOffline ? 'Feed Offline' : 'Live 24/7');
    if (statusText.textContent !== nextStatusTxt) statusText.textContent = nextStatusTxt;
  }

  const nextOmniSum = state.omni_summary || '';
  if (_hdrRefs.omniSummary && _hdrRefs.omniSummary.textContent !== nextOmniSum) {
    _hdrRefs.omniSummary.textContent = nextOmniSum;
  }

  const srcEl = _hdrRefs.srcEl;
  if (srcEl) {
    const mcState = state.macro_commander || {};
    const omniState = (state.intel_hub && state.intel_hub.omniroute) || {};
    const isAiOnline = (omniState.status === 'ONLINE') || (mcState.status === 'ONLINE');
    const nextSrcTxt = isAiOnline ? 'OmniRoute AI' : 'Pure Math Core';
    if (srcEl.textContent !== nextSrcTxt) {
      srcEl.textContent = nextSrcTxt;
      srcEl.style.background = isAiOnline ? 'rgba(56, 189, 248, 0.16)' : 'rgba(0, 242, 254, 0.14)';
      srcEl.style.color = 'var(--ss-text-strong)';
    }
  }
  const qEl = _hdrRefs.qEl;
  if (qEl) {
    const nextQTxt = isOffline ? 'Feed: Offline' : 'Feed: Active';
    if (qEl.textContent !== nextQTxt) {
      qEl.textContent = nextQTxt;
      qEl.style.background = isOffline ? 'var(--ss-danger-soft)' : 'var(--ss-success-soft)';
      qEl.style.color = isOffline ? 'var(--ss-danger-text)' : 'var(--ss-success-text)';
    }
  }
}

function showEngineInfo() {
  alert(
    '[TradeBot0 High-Performance Quant Core]\n\n' +
    '* Architecture: Deterministic Quant Engine + OmniRoute Macro Intelligence\n' +
    '* Strategy Evolution: Tournament Selection + Uniform Crossover\n' +
    '* Risk Mitigation: Monte Carlo EV Gate (1,000 Antithetic Student-t / Bootstrap Paths)\n' +
    '* Market Data Feed: Multi-Exchange Sub-Second Live Websocket/REST Stream\n' +
    '* Network Loss: Trading pauses and waits to reconnect (no stale quotes, no synthetic bars)\n' +
    '* Latency: Sub-millisecond in-memory execution'
  );
}
function showOmniInfo() { showEngineInfo(); }

const stratCardDomMap = new Map();

const stratEquityHistory = new Map();

function buildSparklineGeometry(values, width = 160, height = 16) {
  const pts = (values && values.length > 0) ? values : [100000, 100000];
  const series = pts.length === 1 ? [pts[0], pts[0]] : pts;
  let minV = series[0];
  let maxV = series[0];
  for (let i = 1; i < series.length; i++) {
    if (series[i] < minV) minV = series[i];
    if (series[i] > maxV) maxV = series[i];
  }
  const span = maxV - minV;
  const padY = 2;
  const innerH = height - padY * 2;
  const coords = series.map((v, i) => {
    const x = (i / (series.length - 1)) * width;
    const norm = span > 1e-6 ? (v - minV) / span : 0.5;
    const y = padY + innerH * (1 - norm);
    return [Number(x.toFixed(1)), Number(y.toFixed(1))];
  });
  const lineD = coords.map((p, i) => (i === 0 ? 'M' : 'L') + p[0] + ' ' + p[1]).join(' ');
  const last = coords[coords.length - 1];
  const areaD = lineD + ` L ${last[0]} ${height} L ${coords[0][0]} ${height} Z`;
  return { lineD, areaD, lastX: last[0], lastY: last[1] };
}

function createStrategyCardSkeleton(s) {
  const card = document.createElement('div');
  card.className = 'strat-card-mini';
  card.dataset.stratId = s.id;
  card.innerHTML = `
    <span class="border-beam-ring" aria-hidden="true"></span>
    <span class="lg-strat-orb" aria-hidden="true"></span>
    <div class="strat-top">
      <div class="strat-left">
        <span class="rank-badge num" data-role="rank">#0</span>
        <span class="strat-title" data-role="title"></span>
        <span class="strat-pill num" data-role="pill"></span>
      </div>
      <div class="strat-right num" data-role="badges"></div>
    </div>
    <div class="strat-kpis num">
      <div class="kpi-cell">
        <span>Total Equity</span>
        <span class="kpi-equity-val" data-role="equity">$0.00</span>
      </div>
      <div class="kpi-cell">
        <span>ROI</span>
        <span class="kpi-roi-val" data-role="roi">+0.00%</span>
      </div>
      <div class="kpi-cell">
        <span data-role="pnl-lbl">Cash Balance</span>
        <span data-role="pnl-val">$0</span>
      </div>
      <div class="kpi-cell">
        <span>Win / Max DD</span>
        <span style="color:var(--ss-text)" data-role="windd">0% / 0.0%</span>
      </div>
    </div>
    <div class="strat-sparkline-wrap">
      <span class="strat-sparkline-lbl">Curve</span>
      <svg class="strat-sparkline-svg" viewBox="0 0 160 16" preserveAspectRatio="none" aria-hidden="true">
        <path class="strat-sparkline-area" data-role="spk-area" d="M0 8 L160 8 L160 16 L0 16 Z"></path>
        <path class="strat-sparkline-line" data-role="spk-line" d="M0 8 L160 8"></path>
        <circle class="strat-sparkline-dot" data-role="spk-dot" cx="160" cy="8" r="2.1"></circle>
      </svg>
      <span class="strat-sparkline-delta num" data-role="spk-delta">+0.00%</span>
    </div>
    <div data-role="bracket"></div>
  `;
  card._refs = {
    rank: card.querySelector('[data-role="rank"]'),
    title: card.querySelector('[data-role="title"]'),
    pill: card.querySelector('[data-role="pill"]'),
    badges: card.querySelector('[data-role="badges"]'),
    equity: card.querySelector('[data-role="equity"]'),
    roi: card.querySelector('[data-role="roi"]'),
    pnlLbl: card.querySelector('[data-role="pnl-lbl"]'),
    pnlVal: card.querySelector('[data-role="pnl-val"]'),
    windd: card.querySelector('[data-role="windd"]'),
    spkArea: card.querySelector('[data-role="spk-area"]'),
    spkLine: card.querySelector('[data-role="spk-line"]'),
    spkDot: card.querySelector('[data-role="spk-dot"]'),
    spkDelta: card.querySelector('[data-role="spk-delta"]'),
    bracket: card.querySelector('[data-role="bracket"]'),
  };
  return card;
}

function renderStrategies(state) {
  const grid = document.getElementById('tabCardsView');
  if (!grid) return;
  const strategies = (state.strategies || []).slice().sort((a, b) => (b.equity - a.equity) || (a.rank - b.rank));
  const candles = state.candles || [];
  const lastCandleClose = candles.length > 0 ? Number(candles[candles.length - 1].c || 0) : 0;
  const quotePrice = Number((state.quote && state.quote.price) || 0);
  const spot = quotePrice > 0 ? quotePrice : (lastCandleClose > 0 ? lastCandleClose : 0);
  const isPaused = Boolean(state.paused);

  // Build / Update each card DOM element persistently without wiping rolling spans or SVG curves
  const activeStratIds = new Set();
  strategies.forEach((s, idx) => {
    activeStratIds.add(s.id);
    const sColor = sanitizeCssColor(s.color, '#F59E0B');
    const equityNum = Number(s.equity) || 0;
    const roiNum = Number(s.roi_pct) || 0;
    const upnlNum = Number(s.unrealized_pnl) || 0;
    const qtyNum = Number(s.qty) || 0;
    const winRateNum = Number(s.win_rate_pct) || 0;
    const maxDdNum = Number(s.max_dd_pct) || 0;
    const levNum = Number(s.leverage) || 2.0;
    const roiClass = roiNum >= 0 ? 'up' : 'down';
    const upnlClass = upnlNum >= 0 ? 'up' : 'down';
    const isBlocked = s.intent && s.intent.indexOf('EV Gate Blocked') !== -1;
    const isMacroVeto = s.intent && (s.intent.indexOf('Macro Veto:') !== -1 || s.intent.indexOf('MTF Veto:') !== -1);

    let eqHist = stratEquityHistory.get(s.id);
    if (!eqHist) {
      eqHist = [equityNum];
      stratEquityHistory.set(s.id, eqHist);
    } else if (Math.abs(eqHist[eqHist.length - 1] - equityNum) > 0.01) {
      eqHist.push(equityNum);
      if (eqHist.length > 32) eqHist.shift();
    }

    let bracketHtml = '';
    if (s.in_position) {
      let pct = 50;
      const isShort = s.position_side === 'SHORT';
      if (s.stop_loss && s.take_profit) {
        if (isShort) {
          const span = s.stop_loss - s.take_profit;
          if (span > 0) {
            pct = Math.max(3, Math.min(97, ((s.stop_loss - spot) / span) * 100));
          }
        } else {
          const span = s.take_profit - s.stop_loss;
          if (span > 0) {
            pct = Math.max(3, Math.min(97, ((spot - s.stop_loss) / span) * 100));
          }
        }
      }
      const slText = s.stop_loss ? `SL ${fmtUsd(s.stop_loss, 0)}` : 'SL Dyn';
      const tpText = s.take_profit ? `TP ${fmtUsd(s.take_profit, 0)}` : 'TP Max';
      const evBadge = (typeof s.expected_r === 'number' && Number.isFinite(s.expected_r) && Math.abs(s.expected_r) > 0.01)
        ? `<span class="ev-micro-pill num" title="Monte Carlo EV">${s.expected_r >= 0 ? '+' : ''}${s.expected_r.toFixed(1)}R</span>`
        : '';
      bracketHtml = `
          <div class="bracket-bar-wrap">
            <div class="bracket-track">
              <div class="bracket-fill" style="width:${pct.toFixed(1)}%;background:${sColor}"></div>
              <div class="bracket-marker" style="left:${pct.toFixed(1)}%;border-color:${sColor}"></div>
            </div>
            <div class="bracket-labels num">
              <span class="down">${slText}</span>
              <span class="bracket-entry-center">Entry ${fmtUsd(s.entry_price, 0)} ${evBadge}</span>
              <span class="up">${tpText}</span>
            </div>
          </div>
        `;
    } else if (isMacroVeto) {
      bracketHtml = `
          <div class="strat-idle-bar" style="border-color:rgba(245,158,11,0.28);background:rgba(245,158,11,0.08);">
            <span class="idle-dot" style="background:#F59E0B;box-shadow:0 0 6px #F59E0B;"></span>
            <span class="idle-text" style="color:#FBBF24;">${escapeHtml(s.intent || 'Macro Veto Active')}</span>
          </div>
        `;
    } else if (isBlocked) {
      let cleanVerdict = s.mc_verdict || '';
      cleanVerdict = cleanVerdict.replace(/^Blocked by EV Gate\s*/i, '').replace(/^[()]+|[()]+$/g, '').trim();
      if (!cleanVerdict && s.intent) {
        cleanVerdict = s.intent.replace(/^EV Gate Blocked:\s*/i, '').trim();
      }
      if (!cleanVerdict) {
        const evVal = (typeof s.expected_r === 'number' && Number.isFinite(s.expected_r)) ? `${s.expected_r >= 0 ? '+' : ''}${s.expected_r.toFixed(2)}R` : '-';
        cleanVerdict = `EV ${evVal}`;
      }
      bracketHtml = `
          <div class="strat-idle-bar" style="border-color:rgba(239,68,68,0.25);background:rgba(239,68,68,0.07);">
            <span class="idle-dot" style="background:#EF4444;box-shadow:0 0 6px #EF4444;"></span>
            <span class="idle-text" style="color:#FB7185;">EV Gate Blocked · ${escapeHtml(cleanVerdict)}</span>
          </div>
        `;
    } else {
      bracketHtml = `
          <div class="strat-idle-bar">
            <span class="idle-dot"></span>
            <span class="idle-text">Standby · EV Sizing Active</span>
          </div>
        `;
    }

    const levBadge = s.leverage_enabled
      ? `<span class="lev-pill lev-active" title="Active Leverage">${levNum.toFixed(1)}x</span>`
      : `<span class="lev-pill lev-spot" title="Spot Only">Spot 1x</span>`;

    const posPill = s.in_position
      ? (s.position_side === 'SHORT'
        ? `<span class="pos-badge in-pos-short">Short ${qtyNum.toFixed(1)} ETH</span>`
        : `<span class="pos-badge in-pos">Long ${qtyNum.toFixed(1)} ETH</span>`)
      : `<span class="pos-badge flat">Idle</span>`;

    const cardShortNames = {
      'comp_agg': 'Aggressive',
      'comp_cons': 'Conservative',
      'comp_orb': 'ORB Breakout',
      'comp_vwap': 'Session Mean',
      'comp_trail': 'Trailing Guard'
    };
    const displayName = cardShortNames[s.id] || s.name || '';

    const pnlLabel = s.in_position ? 'Unrealized PnL' : 'Cash Balance';
    const pnlValText = s.in_position ? fmtSignedUsd(upnlNum) : fmtUsd(s.cash, 0);
    const pnlValCls = s.in_position ? upnlClass : '';

    let card = stratCardDomMap.get(s.id);
    if (!card) {
      card = createStrategyCardSkeleton(s);
      stratCardDomMap.set(s.id, card);
    }
    if (card._stratColor !== s.color) {
      card.style.setProperty('--strat-color', sColor);
      card._stratColor = s.color;
    }

    const isChampionBeam = (idx === 0) && !isPaused;
    card.classList.toggle('is-champion-beam', isChampionBeam);

    const refs = card._refs;
    const rankTxt = '#' + (Number(s.rank) || 0);
    if (refs.rank.textContent !== rankTxt) refs.rank.textContent = rankTxt;
    if (refs.rank.style.color !== sColor) refs.rank.style.color = sColor;
    if (refs.title.textContent !== displayName) refs.title.textContent = displayName;
    if (refs.title.title !== (s.name || '')) refs.title.title = s.name || '';

    const pillTxt = `Gen #${Number(s.generation) || 1} · ${s.genome || ''}`;
    if (refs.pill.textContent !== pillTxt) refs.pill.textContent = pillTxt;

    const badgesHtml = levBadge + posPill;
    if (card._lastBadgesHtml !== badgesHtml) {
      card._lastBadgesHtml = badgesHtml;
      refs.badges.innerHTML = badgesHtml;
    }

    const prevEq = typeof card._lastEquity === 'number' ? card._lastEquity : equityNum;
    updateRollingText(refs.equity, fmtUsd(equityNum, 2), equityNum >= prevEq ? 1 : -1);
    card._lastEquity = equityNum;

    const prevRoi = typeof card._lastRoi === 'number' ? card._lastRoi : roiNum;
    updateRollingText(refs.roi, fmtPct(roiNum), roiNum >= prevRoi ? 1 : -1);
    card._lastRoi = roiNum;
    const nextRoiCls = 'kpi-roi-val ' + roiClass;
    if (refs.roi.className !== nextRoiCls) refs.roi.className = nextRoiCls;

    if (refs.pnlLbl.textContent !== pnlLabel) refs.pnlLbl.textContent = pnlLabel;
    if (refs.pnlVal.textContent !== pnlValText) refs.pnlVal.textContent = pnlValText;
    if (refs.pnlVal.className !== pnlValCls) refs.pnlVal.className = pnlValCls;

    const winDdTxt = `${winRateNum.toFixed(0)}% / ${maxDdNum.toFixed(1)}%`;
    if (refs.windd.textContent !== winDdTxt) refs.windd.textContent = winDdTxt;

    const spkSig = eqHist.join(',');
    if (card._lastSpkSig !== spkSig || card._lastSpkColor !== sColor) {
      card._lastSpkSig = spkSig;
      card._lastSpkColor = sColor;
      const geom = buildSparklineGeometry(eqHist, 160, 16);
      const spkColor = roiNum > 0.005 ? '#10F5A0' : (roiNum < -0.005 ? '#FF4D79' : sColor);
      refs.spkLine.setAttribute('d', geom.lineD);
      refs.spkLine.setAttribute('stroke', spkColor);
      refs.spkArea.setAttribute('d', geom.areaD);
      refs.spkArea.setAttribute('fill', spkColor);
      refs.spkDot.setAttribute('cx', String(geom.lastX));
      refs.spkDot.setAttribute('cy', String(geom.lastY));
      refs.spkDot.setAttribute('fill', spkColor);
      const baseVal = eqHist[0] || equityNum || 100000;
      const winPct = baseVal > 0 ? ((equityNum - baseVal) / baseVal) * 100 : 0;
      refs.spkDelta.textContent = `${winPct >= 0 ? '+' : ''}${winPct.toFixed(2)}%`;
      refs.spkDelta.style.color = spkColor;
    }

    if (card._lastBracketHtml !== bracketHtml) {
      card._lastBracketHtml = bracketHtml;
      refs.bracket.innerHTML = bracketHtml;
    }

    if (!card.parentNode) {
      grid.appendChild(card);
    }
  });

  // Prune any stale strategy card nodes no longer present in the roster
  for (const [id, node] of stratCardDomMap.entries()) {
    if (!activeStratIds.has(id)) {
      if (node && node.parentNode) node.parentNode.removeChild(node);
      stratCardDomMap.delete(id);
    }
  }

  const currentCardOrder = Array.from(grid.children).map(el => el.dataset.stratId).join(',');
  const nextCardOrder = strategies.map(s => s.id).join(',');
  if (currentCardOrder !== nextCardOrder) {
    // FLIP reorder animation: cards are stable nodes (stratCardDomMap),
    // so record each card's position, move the nodes to their new slots,
    // then invert with a transform and let the .strat-card-reordering
    // transition play it back to the natural position. Transform-only,
    // so no layout is triggered. Only runs when the ORDER changes --
    // equity updates on the 1s tick never animate.
    const reduceMotion = typeof window.matchMedia === 'function'
      && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const firstRects = new Map();
    strategies.forEach(s => {
      const card = stratCardDomMap.get(s.id);
      if (!card) return;
      // Cancel any in-flight reorder cleanly: drop the class and the
      // transform so the card sits at its current DOM slot before we
      // measure. Renders are 1s apart and the animation is 0.35s, so
      // this only fires on non-cadence re-renders.
      card.classList.remove('strat-card-reordering');
      card.style.transform = '';
      firstRects.set(s.id, card.getBoundingClientRect());
    });
    strategies.forEach(s => {
      const card = stratCardDomMap.get(s.id);
      if (card) grid.appendChild(card);
    });
    if (!reduceMotion) {
      const moved = [];
      strategies.forEach(s => {
        const card = stratCardDomMap.get(s.id);
        const first = firstRects.get(s.id);
        if (!card || !first) return;
        const last = card.getBoundingClientRect();
        const dx = first.left - last.left;
        const dy = first.top - last.top;
        if (dx !== 0 || dy !== 0) {
          card.style.transform = 'translate(' + dx + 'px, ' + dy + 'px)';
          moved.push(card);
        }
      });
      if (moved.length > 0) {
        // Force a reflow so the inverted transform paints before the
        // transition class is added; otherwise the browser may skip it.
        void grid.offsetHeight;
        const flipToken = performance.now();
        moved.forEach(card => {
          card._flipToken = flipToken;
          card.classList.add('strat-card-reordering');
        });
        requestAnimationFrame(() => {
          moved.forEach(card => {
            if (card._flipToken !== flipToken) return;
            card.style.transform = '';
          });
        });
        // Single timeout cleanup (350ms + slack): never depends on
        // transitionend delivery, so a render arriving mid-flight
        // cannot leave a stuck class or transform behind. The token
        // guard keeps a newer reorder's animation alive if a second
        // reorder lands inside this window.
        setTimeout(() => {
          moved.forEach(card => {
            if (card._flipToken !== flipToken) return;
            card.classList.remove('strat-card-reordering');
            card.style.transform = '';
          });
        }, 400);
      }
    }
  }
}

let _hudRefs = null;
function renderTacticalHud(state) {
  if (!state) return;
  if (!_hudRefs) {
    _hudRefs = {
      cTitleEl: document.getElementById('hudChampTitle'),
      cNameEl: document.getElementById('hudChampName'),
      cStatsEl: document.getElementById('hudChampStats'),
      rsiEl: document.getElementById('hudRsiVal'),
      atrEl: document.getElementById('hudAtrVal'),
      expQtyEl: document.getElementById('hudExposureQty'),
      expValEl: document.getElementById('hudExposureVal'),
      genEl: document.getElementById('hudGenVal'),
      genSubEl: document.getElementById('hudGenSub'),
    };
  }
  const tv = state.tv_hub || {};
  const champ = tv.champion || (state.strategies && state.strategies[0]) || {};
  const candles = state.candles || [];
  const lastCandleClose = candles.length > 0 ? Number(candles[candles.length - 1].c || 0) : 0;
  const quotePrice = Number((state.quote && state.quote.price) || 0);
  const spot = quotePrice > 0 ? quotePrice : (lastCandleClose > 0 ? lastCandleClose : 0);

  // 1. Champion Spotlight
  const champCard = document.getElementById('hudVesselChampCard');
  if (champCard) {
    const showChampBeam = Boolean(champ && champ.name && !state.paused);
    champCard.classList.toggle('is-champion-beam', showChampBeam);
  }
  const hVal = Math.round((state.auto_evolve_interval_sec || 21600) / 3600);
  const cTitleEl = _hudRefs.cTitleEl;
  if (cTitleEl) {
    const nextCTitle = `${hVal > 0 ? hVal + 'H ' : ''}Champion`;
    if (cTitleEl.textContent !== nextCTitle) cTitleEl.textContent = nextCTitle;
  }
  const cNameEl = _hudRefs.cNameEl;
  if (cNameEl) {
    const nextCName = champ.name ? champ.name.split(' ')[0] : 'Evaluating...';
    const nextCTitleAttr = champ.name || '';
    if (cNameEl.textContent !== nextCName) cNameEl.textContent = nextCName;
    if (cNameEl.title !== nextCTitleAttr) cNameEl.title = nextCTitleAttr;
  }
  const cStatsEl = _hudRefs.cStatsEl;
  if (cStatsEl) {
    const rotStr = fmtTimeSec(tv.next_rotation_sec || 0);
    const nextCStats = `ROI ${fmtPct(champ.roi_pct || 0)} · ${rotStr}`;
    if (cStatsEl.textContent !== nextCStats) cStatsEl.textContent = nextCStats;
  }

  // 2. Momentum & Volatility (RSI & ATR)
  const ind = state.indicators || {};
  const rsi = Number(ind.rsi !== undefined ? ind.rsi : 50.0);
  const atr = Number(ind.atr !== undefined ? ind.atr : 2.5);
  const rsiEl = _hudRefs.rsiEl;
  if (rsiEl) {
    const nextRsiTxt = `RSI ${rsi.toFixed(1)}`;
    const nextRsiCls = 'hud-value num ' + (rsi >= 55 ? 'up' : (rsi <= 45 ? 'down' : ''));
    if (rsiEl.textContent !== nextRsiTxt) rsiEl.textContent = nextRsiTxt;
    if (rsiEl.className !== nextRsiCls) rsiEl.className = nextRsiCls;
  }
  const atrEl = _hudRefs.atrEl;
  if (atrEl) {
    const atrPct = spot > 0 ? ((atr / spot) * 100).toFixed(2) : '0.00';
    const nextAtrTxt = `ATR $${atr.toFixed(2)} · ${atrPct}%`;
    if (atrEl.textContent !== nextAtrTxt) atrEl.textContent = nextAtrTxt;
  }

  // 3. Gross Exposure
  const strategies = state.strategies || [];
  let totQty = 0;
  let totCash = 0;
  let totEquity = 0;
  strategies.forEach(s => {
    totQty += Number(s.qty || 0);
    totCash += Number(s.cash || 0);
    totEquity += Number(s.equity || 0);
  });
  const expVal = totQty * spot;
  const totCap = totEquity > 0 ? totEquity : (totCash + expVal);
  const cashPct = totCap > 0 ? Math.max(0, Math.min(100, (totCash / totCap) * 100)).toFixed(1) : '100.0';

  const expQtyEl = _hudRefs.expQtyEl;
  if (expQtyEl) {
    const nextExpQty = `${totQty.toFixed(3)} ETH`;
    if (expQtyEl.textContent !== nextExpQty) expQtyEl.textContent = nextExpQty;
  }
  const expValEl = _hudRefs.expValEl;
  if (expValEl) {
    const nextExpVal = `${fmtUsd(expVal, 0)} · ${cashPct}% Cash`;
    if (expValEl.textContent !== nextExpVal) expValEl.textContent = nextExpVal;
  }

  // 4. Genetic Engine
  const genEl = _hudRefs.genEl;
  if (genEl) {
    const nextGenVal = `Gen #${state.generation || 1}`;
    if (genEl.textContent !== nextGenVal) genEl.textContent = nextGenVal;
  }
  const genSubEl = _hudRefs.genSubEl;
  if (genSubEl) {
    const tradesLabel = (typeof state.next_evolve_trades_label === 'string' && state.next_evolve_trades_label)
      ? state.next_evolve_trades_label
      : '';
    const nextGenSub = tradesLabel ? `EV Gate (${hVal}H) · ${tradesLabel}` : `EV Gate (${hVal}H)`;
    if (genSubEl.textContent !== nextGenSub) genSubEl.textContent = nextGenSub;
  }

  // 5. AIMRAN uvq11-wg Liquid Vessel Fluid Level Synchronization (--lv)
  const setVesselLevel = (id, level) => {
    const tube = document.getElementById(id);
    if (!tube) return;
    const clamped = Math.max(0.14, Math.min(0.94, Number(level) || 0.5));
    const nextLv = clamped.toFixed(2);
    if (tube._lastLv === nextLv) return;
    tube._lastLv = nextLv;
    tube.style.setProperty('--lv', nextLv);
    const card = tube._vesselCard || (tube._vesselCard = tube.closest('.lg-vessel-card'));
    if (card) card.style.setProperty('--lv', nextLv);
  };

  const champRoi = Number(champ.roi_pct || 0);
  setVesselLevel('hudVesselChamp', 0.56 + Math.max(-0.36, Math.min(0.36, champRoi / 10.0)));
  setVesselLevel('hudVesselRsi', rsi / 100.0);
  const deployedRatio = totCap > 0 ? (expVal / totCap) : 0.25;
  setVesselLevel('hudVesselExp', 0.20 + deployedRatio * 0.72);
  const intervalSec = Math.max(60, Number(state.auto_evolve_interval_sec || 21600));
  const nextSec = Math.max(0, Number(state.next_evolve_sec || 0));
  setVesselLevel('hudVesselGen', 1.0 - Math.min(0.82, (nextSec / intervalSec) * 0.76));
}

const leaderRowDomMap = new Map();
let leaderboardSortKey = 'equity';
let leaderboardSortDir = 'desc';

function setLeaderboardSort(key) {
  const allowedKeys = ['rank', 'equity', 'roi_pct', 'unrealized_pnl', 'max_dd_pct', 'win_rate_pct', 'sharpe', 'fitness'];
  if (allowedKeys.indexOf(key) === -1) return;
  if (leaderboardSortKey === key) {
    leaderboardSortDir = leaderboardSortDir === 'desc' ? 'asc' : 'desc';
  } else {
    leaderboardSortKey = key;
    leaderboardSortDir = key === 'rank' ? 'asc' : 'desc';
  }
  document.querySelectorAll('#leaderboardTable th[data-sort-key]').forEach((th) => {
    const k = th.getAttribute('data-sort-key');
    const isActive = k === leaderboardSortKey;
    const isAsc = isActive && leaderboardSortDir === 'asc';
    th.classList.toggle('sort-th--active', isActive);
    th.classList.toggle('sort-th--asc', isAsc);
  });
  if (latestState) renderLeaderboard(latestState);
}
window.setLeaderboardSort = setLeaderboardSort;

function renderLeaderboard(state) {
  const tbody = document.getElementById('leaderboardBody');
  if (!tbody) return;
  const dir = leaderboardSortDir === 'asc' ? 1 : -1;
  const strategies = (state.strategies || []).slice().sort((a, b) => {
    const va = Number(a[leaderboardSortKey] || 0);
    const vb = Number(b[leaderboardSortKey] || 0);
    if (va !== vb) return (va - vb) * dir;
    return (Number(a.rank || 0) - Number(b.rank || 0));
  });

  const currentRowOrder = Array.from(tbody.children).map(el => el.dataset.stratId).join(',');
  const nextRowOrder = strategies.map(s => String(s.id)).join(',');
  const orderChanged = currentRowOrder !== nextRowOrder;

  const firstTops = new Map();
  if (orderChanged) {
    strategies.forEach(s => {
      const el = leaderRowDomMap.get(s.id);
      if (el) {
        el.style.transition = 'none';
        el.style.transform = '';
        firstTops.set(s.id, el.getBoundingClientRect().top);
      }
    });
  }

  const leadShortCodes = {
    'comp_agg': 'AGG',
    'comp_cons': 'CONS',
    'comp_trail': 'TRAIL',
    'comp_orb': 'ORB',
    'comp_vwap': 'MEAN'
  };

  const activeLeaderIds = new Set();
  strategies.forEach(s => {
    activeLeaderIds.add(s.id);
    const sColor = sanitizeCssColor(s.color, '#F59E0B');
    const roiNum = Number(s.roi_pct) || 0;
    const upnlNum = Number(s.unrealized_pnl) || 0;
    const ddNum = Number(s.max_dd_pct) || 0;
    const wrNum = Number(s.win_rate_pct) || 0;
    const sharpeNum = Number(s.sharpe) || 0;
    const fitnessNum = Number(s.fitness) || 0;
    const roiCls = roiNum >= 0 ? 'up' : 'down';
    const upnlCls = upnlNum >= 0 ? 'up' : 'down';
    const stratCode = escapeHtml(leadShortCodes[s.id] || (s.name ? s.name.slice(0, 5) : 'STRAT'));
    const rowInner = `
        <td style="font-weight:700;color:${sColor}">#${Number(s.rank) || 0}</td>
        <td title="${escapeHtml(s.name)}">
          <span style="display:inline-flex;align-items:center;gap:4px;">
            <i style="width:5px;height:5px;border-radius:50%;background:${sColor};display:inline-block;flex-shrink:0;"></i>
            <span style="font-weight:700;color:var(--ss-text-strong);">${stratCode}</span>
          </span>
        </td>
        <td class="text-right" style="font-weight:700">${fmtUsd(s.equity, 0)}</td>
        <td class="text-right ${roiCls}">${fmtPct(roiNum)}</td>
        <td class="text-right ${upnlCls}">${fmtSignedUsd(upnlNum)}</td>
        <td class="text-right down">${ddNum.toFixed(1)}%</td>
        <td class="text-right" style="color:var(--ss-text)" title="${Number(s.closed_trades) || 0} trades">${wrNum.toFixed(0)}%</td>
        <td class="text-right" style="color:var(--ss-text)">${sharpeNum.toFixed(1)}</td>
        <td class="text-right" style="font-weight:700">${fitnessNum >= 0 ? '+' : ''}${fitnessNum.toFixed(1)}</td>
      `;

    let tr = leaderRowDomMap.get(s.id);
    if (!tr) {
      tr = document.createElement('tr');
      tr.className = 'num';
      tr.dataset.stratId = s.id;
      leaderRowDomMap.set(s.id, tr);
    }
    if (tr._lastHtml !== rowInner) {
      tr.innerHTML = rowInner;
      tr._lastHtml = rowInner;
    }
    if (!tr.parentNode || orderChanged) {
      tbody.appendChild(tr);
    }
  });

  for (const [id, node] of leaderRowDomMap.entries()) {
    if (!activeLeaderIds.has(id)) {
      if (node && node.parentNode) node.parentNode.removeChild(node);
      leaderRowDomMap.delete(id);
    }
  }

  if (orderChanged) {
    const reduceMotion = typeof window.matchMedia === 'function'
      && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (!reduceMotion) {
      const movedRows = [];
      strategies.forEach(s => {
        const prevTop = firstTops.get(s.id);
        const tr = leaderRowDomMap.get(s.id);
        if (prevTop !== undefined && tr) {
          const newTop = tr.getBoundingClientRect().top;
          const dy = prevTop - newTop;
          if (Math.abs(dy) > 1) {
            tr.style.transform = `translateY(${dy}px)`;
            tr.style.transition = 'none';
            movedRows.push(tr);
          }
        }
      });

      if (movedRows.length > 0) {
        void tbody.offsetHeight;
        const flipToken = performance.now();
        movedRows.forEach(tr => { tr._flipToken = flipToken; });
        requestAnimationFrame(() => {
          movedRows.forEach(tr => {
            if (tr._flipToken !== flipToken) return;
            tr.style.transition = 'transform 0.42s cubic-bezier(0.22, 1, 0.36, 1)';
            tr.style.transform = '';
          });
        });
        setTimeout(() => {
          movedRows.forEach(tr => {
            if (tr._flipToken !== flipToken) return;
            tr.style.transition = '';
            tr.style.transform = '';
          });
        }, 460);
      }
    }
  }
}

let lastTopFillSeq = 0;
let lastRenderedFillSig = '';
function renderFills(state) {
  const allFills = state.fills || [];
  const liveFills = allFills.filter(f => f.is_live);
  const liveCount = liveFills.length;
  const topSeq = liveFills.length > 0 ? liveFills[0].seq : 0;
  const fillSig = `${topSeq}:${liveCount}`;
  if (fillSig === lastRenderedFillSig) {
    return;
  }
  lastRenderedFillSig = fillSig;

  const labelEl = document.getElementById('fillCountLabel');
  if (labelEl) {
    labelEl.innerHTML = `
      <span class="live-pulse-badge"><span class="live-dot"></span>Active</span>
      <span class="num" style="margin-left:5px;color:var(--ss-text-faint);font-size:9.5px;">${liveCount} Live Orders</span>
    `;
  }
  const tbody = document.getElementById('fillsBody');
  if (!tbody) return;

  if (liveFills.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="8" style="text-align:center;padding:36px 12px;color:var(--ss-text-faint);font-size:11px;">
          <div style="display:inline-flex;align-items:center;gap:8px;opacity:0.75;">
            <span class="live-dot" style="background:var(--ss-accent);box-shadow:0 0 6px var(--ss-accent);"></span>
            <span>Awaiting live order executions...</span>
          </div>
        </td>
      </tr>
    `;
    return;
  }

  const isNewTop = (lastTopFillSeq > 0 && topSeq > lastTopFillSeq);
  lastTopFillSeq = topSeq;

  const stratShortMap = {
    'Aggressive Momentum': 'AGG',
    'Aggressive': 'AGG',
    'Conservative Scalper': 'CONS',
    'Conservative': 'CONS',
    'Trailing Ratchet Guard': 'TRAIL',
    'Trailing Guard': 'TRAIL',
    'Trailing': 'TRAIL',
    'Opening Range Breakout': 'ORB',
    'ORB (15m)': 'ORB',
    'ORB': 'ORB',
    'Session Mean Pullback': 'MEAN',
    'Session Mean': 'MEAN',
    'Session': 'MEAN',
    'MEAN': 'MEAN',
    'Institutional VWAP Pullback': 'MEAN',
    'Institutional VWAP': 'MEAN',
    'Institutional': 'MEAN',
    'VWAP': 'MEAN'
  };

  tbody.innerHTML = liveFills.map((f, idx) => {
    const isBuy = f.side === 'BUY';
    const pnlVal = f.pnl !== null && f.pnl !== undefined ? Number(f.pnl) : null;
    const pnlStr = pnlVal !== null ? fmtSignedUsd(pnlVal) : '—';
    const pnlCls = pnlVal === null ? '' : (pnlVal >= 0 ? 'up' : 'down');

    let actionBadge = '';
    if (f.action_label) {
      if (f.action_label === 'OPEN LONG') {
        actionBadge = '<span class="badge-buy">OPEN LONG</span>';
      } else if (f.action_label === 'CLOSE LONG') {
        actionBadge = '<span class="badge-sell">CLOSE LONG</span>';
      } else if (f.action_label === 'OPEN SHORT') {
        actionBadge = '<span class="badge-sell">OPEN SHORT</span>';
      } else if (f.action_label === 'COVER SHORT') {
        actionBadge = '<span class="badge-buy">COVER SHORT</span>';
      } else {
        actionBadge = `<span class="${isBuy ? 'badge-buy' : 'badge-sell'}">${escapeHtml(f.action_label)}</span>`;
      }
    } else {
      actionBadge = isBuy
        ? '<span class="badge-buy">BUY</span>'
        : '<span class="badge-sell">SELL</span>';
    }

    const displaySeq = (f.seq !== undefined && f.seq !== null && f.seq > 0)
      ? f.seq
      : (liveCount - idx);
    const seqStr = `#${displaySeq}`;
    const priceSubHtml = (!f.is_entry && f.entry_price)
      ? `<div style="font-size:8.5px;color:var(--ss-text-faint);font-weight:400;">Cost $${Number(f.entry_price).toFixed(2)}</div>`
      : '';

    const animCls = (idx === 0 && isNewTop) ? ' new-fill-row' : '';
    const sShort = escapeHtml(stratShortMap[f.strategy] || (f.strategy ? f.strategy.slice(0, 5) : 'STRAT'));
    const stratTitle = escapeHtml(f.strategy || '');
    const timeEsc = escapeHtml(f.time || '');
    const reasonEsc = escapeHtml(f.trigger || f.reason || '—');
    const qtyStr = Number(f.qty) ? Number(f.qty).toFixed(2) : '0.00';

    return `
      <tr class="num${animCls}">
        <td style="color:var(--ss-text-faint);font-size:9.5px;">${seqStr}</td>
        <td style="color:var(--ss-text);white-space:nowrap;font-family:var(--font-mono);">${timeEsc}</td>
        <td style="font-weight:700;color:var(--ss-text-strong);white-space:nowrap;" title="${stratTitle}">${sShort}</td>
        <td style="white-space:nowrap;">${actionBadge}</td>
        <td class="text-right">${qtyStr}</td>
        <td class="text-right">${fmtUsd(f.price, 2)}${priceSubHtml}</td>
        <td class="text-right ${pnlCls}" style="font-weight:650;">${pnlStr}</td>
        <td style="color:var(--ss-text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" title="${reasonEsc}">${reasonEsc}</td>
      </tr>
    `;
  }).join('');
}

/* HiDPI Vector Canvas Helpers */
let cachedCanvasSize = null;

function invalidateCanvasSizeCache() {
  cachedCanvasSize = null;
}

function setupHiDPICanvas(canvas) {
  const dpr = Math.min(window.devicePixelRatio || 1, 2.0);
  if (!cachedCanvasSize || cachedCanvasSize.dpr !== dpr) {
    const rect = (canvas.parentElement || canvas).getBoundingClientRect();
    const rawW = Math.floor(rect.width);
    const rawH = Math.floor(rect.height);
    if (rawW <= 0 || rawH <= 0) {
      return { ctx: canvas.getContext('2d'), w: 0, h: 0 };
    }
    cachedCanvasSize = {
      w: Math.max(200, rawW),
      h: Math.max(100, rawH),
      dpr: dpr
    };
  }
  const { w, h } = cachedCanvasSize;
  const targetW = Math.floor(w * dpr);
  const targetH = Math.floor(h * dpr);
  if (canvas.width !== targetW || canvas.height !== targetH) {
    canvas.width = targetW;
    canvas.height = targetH;
  }
  const ctx = canvas.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { ctx, w, h };
}

function fillRoundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  if (typeof ctx.roundRect === 'function') {
    ctx.roundRect(x, y, w, h, r);
  } else {
    ctx.rect(x, y, w, h);
  }
  ctx.fill();
}

function strokeRoundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  if (typeof ctx.roundRect === 'function') {
    ctx.roundRect(x, y, w, h, r);
  } else {
    ctx.rect(x, y, w, h);
  }
  ctx.stroke();
}

/* Detailed Chart 1: Dynamic Auto-Scaled Price / Candles + Indicators + Levels (Stageshow Crafted Canvas) */
let priceHoverPos = null;
let hoveredCandleData = null;
let lastHoverIdx = -1;
let lastHoverSnapY = -1;
let chartAnimRaf = null;

// 60 FPS cap (2026-11-13 user decision: 2K 180Hz screen, app caps at 60fps).
// At most one chart frame per 16.7ms; see stepChartAnimLoop().
const CHART_FRAME_MIN_INTERVAL_MS = 16.7;
let chartAnimLastRenderMs = 0;

// Real-time interpolated animation coordinates (Lerp State)
let animSpot = 0, targetSpot = 0;
let animMinP = 0, targetMinP = 0;
let animMaxP = 0, targetMaxP = 0;
let animCandles = [];
let targetCandles = [];

// Smooth Horizontal Kinetic Slide Offset when new bars arrive
let candleSlideOffset = 0;
let lastNewestCandleTime = 0;

function drawPriceChart(state) {
  if (!state) return;
  latestState = state;

  const rawCandles = state.candles || [];
  const rawPrices = state.price_history || [];
  const useCandles = rawCandles.length >= 2;
  const strategies = state.strategies || [];

  const quotePrice = Number((state.quote && state.quote.price) || 0);
  const lastClose = rawCandles.length > 0 ? Number(rawCandles[rawCandles.length - 1].c || 0) : 0;
  targetSpot = quotePrice > 0 ? quotePrice : (lastClose > 0 ? lastClose : 0);

  const canvas = document.getElementById('priceCanvas');
  const canvasW = (cachedCanvasSize && cachedCanvasSize.w) ? cachedCanvasSize.w : (canvas ? (canvas.clientWidth || 800) : 800);
  const padLeft = 12;
  const padRight = 98;
  const plotW = Math.max(50, canvasW - padLeft - padRight);
  const candleRightOffset = 80;
  const candlePlotW = Math.max(50, plotW - candleRightOffset);
  const optimalCount = Math.max(45, Math.min(rawCandles.length, Math.floor(candlePlotW / 9.5)));
  targetCandles = rawCandles.slice(-optimalCount);

  // Detect new candle arrival and trigger smooth horizontal kinetic slide to the left
  if (useCandles && targetCandles.length > 0) {
    const n = targetCandles.length;
    const maxStep = 13.0, minStep = 5.5;
    const naturalStep = candlePlotW / Math.max(1, n);
    const step = Math.min(maxStep, Math.max(minStep, naturalStep));

    const newest = targetCandles[targetCandles.length - 1];
    const newestTime = Number(newest.t || 0);

    if (lastNewestCandleTime === 0) {
      lastNewestCandleTime = newestTime;
    } else if (newestTime > lastNewestCandleTime) {
      lastNewestCandleTime = newestTime;
      candleSlideOffset = Math.min(step * 2.5, candleSlideOffset + step);

      if (animCandles.length > 0) {
        const oldMap = new Map();
        animCandles.forEach(c => oldMap.set(c.t, c));
        animCandles = targetCandles.map(tc => {
          const existing = oldMap.get(tc.t);
          if (existing) {
            return existing;
          }
          return { o: tc.o, h: tc.o, l: tc.o, c: tc.o, t: tc.t };
        });
      }
    }
  }

  let minP = Infinity, maxP = -Infinity;
  // Full mode scales to the whole loaded history; Focus ('auto')
  // keeps the tight recent window (targetCandles).
  const rangeCandles = (scaleMode === 'full') ? rawCandles : targetCandles;
  if (useCandles && rangeCandles.length > 0) {
    rangeCandles.forEach(c => {
      if (c.l < minP) minP = c.l;
      if (c.h > maxP) maxP = c.h;
    });
  } else if (rawPrices.length > 0) {
    const visP = rawPrices.slice(-80);
    visP.forEach(p => {
      if (p < minP) minP = p;
      if (p > maxP) maxP = p;
    });
  }

  if (targetSpot > 0) {
    minP = Math.min(minP, targetSpot);
    maxP = Math.max(maxP, targetSpot);
  }

  if (!isFinite(minP) || !isFinite(maxP) || minP <= 0) {
    minP = targetSpot > 0 ? targetSpot - 40 : 2450;
    maxP = targetSpot > 0 ? targetSpot + 40 : 2550;
  }

  if (scaleMode === 'full') {
    strategies.forEach(s => {
      if (s.in_position) {
        if (s.entry_price && s.entry_price > 0) {
          minP = Math.min(minP, s.entry_price);
          maxP = Math.max(maxP, s.entry_price);
        }
        // Brackets extend both sides: for a long the SL sits below
        // and the TP above; for a short it is the other way round.
        // The old code only covered the long direction, so distant
        // short brackets never widened the scale and Full looked
        // identical to Focus.
        if (s.stop_loss && s.stop_loss > 0) {
          minP = Math.min(minP, s.stop_loss);
          maxP = Math.max(maxP, s.stop_loss);
        }
        if (s.take_profit && s.take_profit > 0) {
          minP = Math.min(minP, s.take_profit);
          maxP = Math.max(maxP, s.take_profit);
        }
      }
    });
  }

  const span = Math.max(25.0, maxP - minP);
  targetMinP = minP - span * 0.16;
  targetMaxP = maxP + span * 0.16;

  // Bootstrap values on initial load, or snap immediately when paused (e.g. Focus/Full scale switch)
  if (animSpot === 0 || state.paused) animSpot = targetSpot;
  if (animMinP === 0 || state.paused) animMinP = targetMinP;
  if (animMaxP === 0 || state.paused) animMaxP = targetMaxP;
  if (animCandles.length === 0 && targetCandles.length > 0) {
    animCandles = targetCandles.map(c => ({ o: c.o, h: c.h, l: c.l, c: c.c, t: c.t }));
  }

  // G2 (Phase 2G): the arena chart is display:none while Intel Hub is
  // shown, so do not start the animation loop for it. Snap the animated
  // values to their targets so switching back to the arena shows the
  // current chart immediately (no catch-up glide).
  const intelEl = document.getElementById('intelHubMainView');
  if (intelEl && intelEl.style.display !== 'none' && !intelEl.classList.contains('view-transition-leaving')) {
    animSpot = targetSpot;
    animMinP = targetMinP;
    animMaxP = targetMaxP;
    candleSlideOffset = 0;
    animCandles = targetCandles.map(c => ({ o: c.o, h: c.h, l: c.l, c: c.c, t: c.t }));
    return;
  }

  if (state.paused) {
    const lastC = targetCandles.length > 0 ? targetCandles[targetCandles.length - 1] : null;
    const hKey = priceHoverPos ? `${Math.round(priceHoverPos.x)}:${Math.round(priceHoverPos.y)}` : '';
    const sKey = strategies.map(s => `${s.id}:${s.in_position ? 1 : 0}:${s.entry_price || 0}:${s.stop_loss || 0}:${s.take_profit || 0}`).join('|');
    const pausedSig = `${targetSpot}:${targetCandles.length}:${lastC ? lastC.t + ':' + lastC.c : ''}:${scaleMode}:${canvasW}:${hKey}:${sKey}`;
    if (pausedSig === lastPausedCanvasSig && hasFirstChartDrawn) {
      return;
    }
    lastPausedCanvasSig = pausedSig;
  } else {
    lastPausedCanvasSig = '';
  }

  startChartAnimLoop();
}

function startChartAnimLoop() {
  if (!chartAnimRaf) {
    chartAnimRaf = requestAnimationFrame(stepChartAnimLoop);
  }
}

function stepChartAnimLoop() {
  chartAnimRaf = null;
  if (!latestState || document.hidden || currentMainView !== 'arena') return;
  if (latestState.paused) {
    renderPriceCanvas(latestState, animCandles, animSpot, animMinP, animMaxP);
    return;
  }

  // 60 FPS cap: skip rendering until 16.7ms have passed since the last
  // rendered frame. Defer with a one-shot timer (not another rAF) so the
  // loop still stops on convergence instead of spinning idle at display
  // refresh rate. The -1 sentinel keeps startChartAnimLoop() from starting
  // a second loop while the timer is pending; the timer clears it before
  // re-entering. Paused state is handled above and never deferred.
  const nowMs = performance.now();
  if (nowMs - chartAnimLastRenderMs < CHART_FRAME_MIN_INTERVAL_MS) {
    chartAnimRaf = -1;
    const delayMs = CHART_FRAME_MIN_INTERVAL_MS - (nowMs - chartAnimLastRenderMs);
    setTimeout(() => {
      chartAnimRaf = null;
      stepChartAnimLoop();
    }, delayMs);
    return;
  }
  chartAnimLastRenderMs = nowMs;

  const ease = 0.08;
  let needsMore = false;

  if (Math.abs(candleSlideOffset) > 0.05) {
    candleSlideOffset += (0 - candleSlideOffset) * 0.05;
    needsMore = true;
  } else {
    candleSlideOffset = 0;
  }

  // 1. Lerp Spot Price
  const dSpot = targetSpot - animSpot;
  if (Math.abs(dSpot) > 0.02) {
    animSpot += dSpot * ease;
    needsMore = true;
  } else {
    animSpot = targetSpot;
  }

  // 2. Lerp Price Bounds
  const dMin = targetMinP - animMinP;
  if (Math.abs(dMin) > 0.02) {
    animMinP += dMin * ease;
    needsMore = true;
  } else {
    animMinP = targetMinP;
  }

  const dMax = targetMaxP - animMaxP;
  if (Math.abs(dMax) > 0.02) {
    animMaxP += dMax * ease;
    needsMore = true;
  } else {
    animMaxP = targetMaxP;
  }

  // 3. Lerp Candle Heights & Wicks
  if (animCandles.length !== targetCandles.length) {
    animCandles = targetCandles.map(c => ({ o: c.o, h: c.h, l: c.l, c: c.c, t: c.t }));
    needsMore = true;
  } else {
    for (let i = 0; i < targetCandles.length; i++) {
      const tc = targetCandles[i];
      const ac = animCandles[i];
      ac.o = tc.o;
      ac.t = tc.t;

      const dC = tc.c - ac.c;
      const dH = tc.h - ac.h;
      const dL = tc.l - ac.l;

      if (Math.abs(dC) > 0.02) { ac.c += dC * ease; needsMore = true; } else { ac.c = tc.c; }
      if (Math.abs(dH) > 0.02) { ac.h += dH * ease; needsMore = true; } else { ac.h = tc.h; }
      if (Math.abs(dL) > 0.02) { ac.l += dL * ease; needsMore = true; } else { ac.l = tc.l; }
    }
  }

  // 4. Active radar beacons
  if (chartBeacons && chartBeacons.length > 0) {
    const now = Date.now();
    chartBeacons = chartBeacons.filter(b => (now - b.startTime) < b.duration);
    if (chartBeacons.length > 0) needsMore = true;
  }

  // 5. Render Canvas Frame
  renderPriceCanvas(latestState, animCandles, animSpot, animMinP, animMaxP);

  if (needsMore) {
    chartAnimRaf = requestAnimationFrame(stepChartAnimLoop);
  }
}

function renderPriceCanvas(state, visibleCandles, spot, minP, maxP) {
  const canvas = document.getElementById('priceCanvas');
  if (!canvas || !state) return;
  const { ctx, w, h } = setupHiDPICanvas(canvas);
  if (w <= 0 || h <= 0) return;
  ctx.fillStyle = '#080c13';
  ctx.fillRect(0, 0, w, h);

  const rawPrices = state.price_history || [];
  const strategies = state.strategies || [];
  const useCandles = visibleCandles.length >= 2;

  const padLeft = 12;
  const padRight = 98;
  const padTop = 16;
  const padBottom = 22;
  const plotW = Math.max(50, w - padLeft - padRight);
  const plotH = Math.max(40, h - padTop - padBottom);
  const candleRightOffset = 80;
  const candlePlotW = Math.max(50, plotW - candleRightOffset);

  const priceSpan = (maxP - minP) || 1;
  const toY = (v) => padTop + (1 - (v - minP) / priceSpan) * plotH;

  // 1. Precision Hairline Grid & Tabular Price Axis (Pure Monochrome on Pure Black)
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.06)';
  ctx.lineWidth = 1;
  ctx.font = '600 9.5px "SF Mono", "JetBrains Mono", Consolas, monospace';
  ctx.fillStyle = '#94A3B8';
  const gridCount = plotH > 380 ? 6 : 4;
  for (let g = 0; g <= gridCount; g++) {
    const gv = minP + ((maxP - minP) * (gridCount - g)) / gridCount;
    const gy = Math.round(toY(gv)) + 0.5;
    ctx.beginPath();
    ctx.moveTo(padLeft, gy);
    ctx.lineTo(padLeft + plotW, gy);
    ctx.stroke();
    ctx.fillText('$' + gv.toFixed(0), padLeft + plotW + 8, gy + 3);
  }

  // Right Price Axis Divider Hairline
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.10)';
  ctx.beginPath();
  ctx.moveTo(Math.round(padLeft + plotW) + 0.5, padTop);
  ctx.lineTo(Math.round(padLeft + plotW) + 0.5, padTop + plotH);
  ctx.stroke();

  const tagMap = {
    'comp_agg': 'AGG',
    'comp_cons': 'CONS',
    'comp_trail': 'TRAIL',
    'comp_orb': 'ORB',
    'comp_vwap': 'MEAN'
  };

  let activeHeadX = padLeft + candlePlotW;

  // 2. Candlesticks or Smooth Line Chart
  if (useCandles && visibleCandles.length > 0) {
    if (visibleCandles.length >= 10) {
      hasFirstChartDrawn = true;
      if (latestState && latestState.is_bootstrapped) {
        setSplashTarget(100);
      }
    }
    const n = visibleCandles.length;
    const maxStep = 13.0;
    const minStep = 5.5;
    const naturalStep = candlePlotW / Math.max(1, n);
    const step = Math.min(maxStep, Math.max(minStep, naturalStep));
    const bodyW = Math.max(3.5, Math.min(9.5, Math.round(step * 0.7)));

    const totalCandleW = n * step;
    const startX = totalCandleW < candlePlotW ? (padLeft + candlePlotW - totalCandleW) : padLeft;

    ctx.save();
    ctx.beginPath();
    ctx.rect(padLeft, padTop - 6, candlePlotW + 4, plotH + 12);
    ctx.clip();

    const shiftX = candleSlideOffset;
    let maxC = visibleCandles[0], minC = visibleCandles[0];
    let maxIdx = 0, minIdx = 0;

    // Pass 1: Batch candle wicks into 2 paths (up / down) instead of N stroke calls
    ctx.lineWidth = 1.25;
    ctx.strokeStyle = 'rgba(0, 230, 118, 0.85)';
    ctx.beginPath();
    for (let i = 0; i < n; i++) {
      const c = visibleCandles[i];
      if (c.h > maxC.h) { maxC = c; maxIdx = i; }
      if (c.l < minC.l) { minC = c; minIdx = i; }
      if (c.c >= c.o) {
        const cx = startX + (i + 0.5) * step + shiftX;
        ctx.moveTo(cx, toY(c.h));
        ctx.lineTo(cx, toY(c.l));
      }
    }
    ctx.stroke();

    ctx.strokeStyle = 'rgba(255, 51, 75, 0.85)';
    ctx.beginPath();
    for (let i = 0; i < n; i++) {
      const c = visibleCandles[i];
      if (c.c < c.o) {
        const cx = startX + (i + 0.5) * step + shiftX;
        ctx.moveTo(cx, toY(c.h));
        ctx.lineTo(cx, toY(c.l));
      }
    }
    ctx.stroke();

    // Pass 2: Rounded Candle Bodies
    for (let i = 0; i < n; i++) {
      const c = visibleCandles[i];
      const cx = startX + (i + 0.5) * step + shiftX;
      if (i === n - 1) activeHeadX = cx;

      const isUp = c.c >= c.o;
      ctx.fillStyle = isUp ? '#00E676' : '#FF334B';
      const yOpen = toY(c.o);
      const yClose = toY(c.c);
      const topY = Math.min(yOpen, yClose);
      const bHeight = Math.max(2.5, Math.abs(yClose - yOpen));
      fillRoundRect(ctx, cx - bodyW / 2, topY, bodyW, bHeight, 1.5);
    }


    // Session High / Low Callout Pills
    ctx.save();
    ctx.font = '500 9px "SF Mono", "JetBrains Mono", Consolas, monospace';
    ctx.fillStyle = '#9A9EA7';
    const maxCx = startX + (maxIdx + 0.5) * step + shiftX;
    const minCx = startX + (minIdx + 0.5) * step + shiftX;
    ctx.fillText(`H $${maxC.h.toFixed(1)}`, Math.max(padLeft + 2, Math.min(padLeft + candlePlotW - 42, maxCx - 18)), toY(maxC.h) - 5);
    ctx.fillText(`L $${minC.l.toFixed(1)}`, Math.max(padLeft + 2, Math.min(padLeft + candlePlotW - 42, minCx - 18)), toY(minC.l) + 12);
    ctx.restore();

    ctx.restore();
  } else if (visibleCandles.length === 1) {
    const c = visibleCandles[0];
    const cx = padLeft + candlePlotW * 0.5;
    activeHeadX = cx;
    const isUp = c.c >= c.o;
    ctx.save();
    ctx.strokeStyle = isUp ? 'rgba(0, 230, 118, 0.85)' : 'rgba(255, 51, 75, 0.85)';
    ctx.lineWidth = 1.25;
    ctx.beginPath();
    ctx.moveTo(cx, toY(c.h));
    ctx.lineTo(cx, toY(c.l));
    ctx.stroke();
    ctx.fillStyle = isUp ? '#00E676' : '#FF334B';
    const yO = toY(c.o), yC = toY(c.c);
    fillRoundRect(ctx, cx - 4, Math.min(yO, yC), 8, Math.max(2.5, Math.abs(yC - yO)), 1.5);
    ctx.restore();
  } else if (rawPrices.length >= 2) {
    const visP = rawPrices.slice(-80);
    const stepX = candlePlotW / Math.max(1, visP.length - 1);
    ctx.save();
    ctx.strokeStyle = 'rgba(0, 242, 254, 0.85)';
    ctx.lineWidth = 1.75;
    ctx.beginPath();
    for (let i = 0; i < visP.length; i++) {
      const px = padLeft + i * stepX;
      const py = toY(visP[i]);
      if (i === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
      if (i === visP.length - 1) activeHeadX = px;
    }
    ctx.stroke();
    ctx.restore();
  }

  // 3. Strategy Levels, Brackets & Spot Price Badges
  const rightBadges = [];
  const offscreenTop = [];
  const offscreenBot = [];
  const activeStrats = strategies.filter(s => s.in_position);

  activeStrats.forEach((s, idx) => {
    const sTag = tagMap[s.id] || (s.name ? s.name.slice(0, 4).toUpperCase() : 'STRAT');
    const sColor = s.color || '#FFB800';

    let yTP = null, yEntry = null, ySL = null;

    // Take Profit Line
    if (s.take_profit && s.take_profit > 0) {
      if (s.take_profit >= minP && s.take_profit <= maxP) {
        yTP = toY(s.take_profit);
        ctx.save();
        ctx.strokeStyle = hexToRgba(sColor, 0.72);
        ctx.lineWidth = 1.15;
        ctx.beginPath();
        ctx.moveTo(padLeft, yTP);
        ctx.lineTo(padLeft + plotW, yTP);
        ctx.stroke();
        ctx.restore();

        rightBadges.push({
          rawY: yTP,
          price: s.take_profit,
          stratTag: sTag,
          subTag: 'TP',
          label: `$${s.take_profit.toFixed(0)}`,
          color: '#4ADE80',
          stratColor: sColor,
          type: 'tp'
        });
      } else if (s.take_profit > maxP) {
        const tpPct = (s.entry_price && s.entry_price > 0)
          ? Math.abs(((s.take_profit - s.entry_price) / s.entry_price) * 100).toFixed(1)
          : (spot > 0 ? Math.abs(((s.take_profit - spot) / spot) * 100).toFixed(1) : '0.0');
        offscreenTop.push({ label: `${sTag} TP $${s.take_profit.toFixed(0)} (+${tpPct}%)`, color: sColor });
      } else if (s.take_profit < minP) {
        const tpPct = (s.entry_price && s.entry_price > 0)
          ? Math.abs(((s.entry_price - s.take_profit) / s.entry_price) * 100).toFixed(1)
          : (spot > 0 ? Math.abs(((spot - s.take_profit) / spot) * 100).toFixed(1) : '0.0');
        offscreenBot.push({ label: `${sTag} TP $${s.take_profit.toFixed(0)} (+${tpPct}%)`, color: sColor });
      }
    }

    // Entry Price Line
    if (s.entry_price && s.entry_price > 0) {
      if (s.entry_price >= minP && s.entry_price <= maxP) {
        yEntry = toY(s.entry_price);
        ctx.save();
        ctx.strokeStyle = hexToRgba(sColor, 0.85);
        ctx.lineWidth = 1.25;
        ctx.beginPath();
        ctx.moveTo(padLeft, yEntry);
        ctx.lineTo(padLeft + plotW, yEntry);
        ctx.stroke();
        ctx.restore();

        rightBadges.push({
          rawY: yEntry,
          price: s.entry_price,
          stratTag: sTag,
          subTag: 'IN',
          label: `$${s.entry_price.toFixed(0)}`,
          color: '#F2F3F5',
          stratColor: sColor,
          type: 'entry'
        });
      }
    }

    // Stop Loss Line
    if (s.stop_loss && s.stop_loss > 0) {
      if (s.stop_loss >= minP && s.stop_loss <= maxP) {
        ySL = toY(s.stop_loss);
        ctx.save();
        ctx.strokeStyle = hexToRgba(sColor, 0.72);
        ctx.lineWidth = 1.15;
        ctx.beginPath();
        ctx.moveTo(padLeft, ySL);
        ctx.lineTo(padLeft + plotW, ySL);
        ctx.stroke();
        ctx.restore();

        rightBadges.push({
          rawY: ySL,
          price: s.stop_loss,
          stratTag: sTag,
          subTag: 'SL',
          label: `$${s.stop_loss.toFixed(0)}`,
          color: '#FB7185',
          stratColor: sColor,
          type: 'sl'
        });
      } else if (s.stop_loss < minP) {
        const slPct = (s.entry_price && s.entry_price > 0)
          ? Math.abs(((s.entry_price - s.stop_loss) / s.entry_price) * 100).toFixed(1)
          : (spot > 0 ? Math.abs(((spot - s.stop_loss) / spot) * 100).toFixed(1) : '0.0');
        offscreenBot.push({ label: `${sTag} SL $${s.stop_loss.toFixed(0)} (-${slPct}%)`, color: sColor });
      } else if (s.stop_loss > maxP) {
        const slPct = (s.entry_price && s.entry_price > 0)
          ? Math.abs(((s.stop_loss - s.entry_price) / s.entry_price) * 100).toFixed(1)
          : (spot > 0 ? Math.abs(((s.stop_loss - spot) / spot) * 100).toFixed(1) : '0.0');
        offscreenTop.push({ label: `${sTag} SL $${s.stop_loss.toFixed(0)} (-${slPct}%)`, color: sColor });
      }
    }

    // Vertical Bracket Connector in Corridor
    const validYs = [yTP, yEntry, ySL].filter(y => y !== null);
    if (validYs.length >= 2) {
      const bracketTop = Math.min(...validYs);
      const bracketBot = Math.max(...validYs);
      if (bracketBot > bracketTop + 2) {
        const bx = padLeft + candlePlotW + 12 + (idx * 10);
        ctx.save();
        ctx.strokeStyle = hexToRgba(sColor, 0.85);
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(bx, bracketTop);
        ctx.lineTo(bx, bracketBot);
        ctx.moveTo(bx - 3, bracketTop);
        ctx.lineTo(bx + 3, bracketTop);
        ctx.moveTo(bx - 3, bracketBot);
        ctx.lineTo(bx + 3, bracketBot);
        if (yEntry !== null && yEntry > bracketTop && yEntry < bracketBot) {
          ctx.moveTo(bx, yEntry);
          ctx.lineTo(bx - 4, yEntry);
        }
        ctx.stroke();
        ctx.restore();
      }
    }
  });

  // 3b. Reference Mean & ORB Range Reference Lines
  const ind = state.indicators || {};
  const vwapVal = Number(ind.typical_mean != null ? ind.typical_mean : (ind.vwap || 0));
  if (vwapVal > 0 && vwapVal >= minP && vwapVal <= maxP) {
    const vy = toY(vwapVal);
    ctx.save();
    ctx.strokeStyle = 'rgba(255, 214, 10, 0.65)';
    ctx.lineWidth = 1.25;
    ctx.beginPath();
    ctx.moveTo(padLeft, vy);
    ctx.lineTo(padLeft + plotW, vy);
    ctx.stroke();
    ctx.restore();

    rightBadges.push({
      rawY: vy,
      price: vwapVal,
      stratTag: 'MEAN',
      subTag: '',
      label: `$${vwapVal.toFixed(0)}`,
      color: '#FFD60A',
      stratColor: '#FFD60A',
      type: 'vwap'
    });
  }

  const orbHigh = Number(ind.orb_high || 0);
  const orbLow = Number(ind.orb_low || 0);
  if (orbHigh > 0 && orbHigh >= minP && orbHigh <= maxP) {
    const ohy = toY(orbHigh);
    ctx.save();
    ctx.strokeStyle = 'rgba(168, 85, 247, 0.58)';
    ctx.lineWidth = 1.15;
    ctx.beginPath();
    ctx.moveTo(padLeft, ohy);
    ctx.lineTo(padLeft + plotW, ohy);
    ctx.stroke();
    ctx.restore();

    rightBadges.push({
      rawY: ohy,
      price: orbHigh,
      stratTag: 'ORB',
      subTag: 'H',
      label: `$${orbHigh.toFixed(0)}`,
      color: '#C084FC',
      stratColor: '#A855F7',
      type: 'orb'
    });
  }
  if (orbLow > 0 && orbLow >= minP && orbLow <= maxP) {
    const oly = toY(orbLow);
    ctx.save();
    ctx.strokeStyle = 'rgba(168, 85, 247, 0.58)';
    ctx.lineWidth = 1.15;
    ctx.beginPath();
    ctx.moveTo(padLeft, oly);
    ctx.lineTo(padLeft + plotW, oly);
    ctx.stroke();
    ctx.restore();

    rightBadges.push({
      rawY: oly,
      price: orbLow,
      stratTag: 'ORB',
      subTag: 'L',
      label: `$${orbLow.toFixed(0)}`,
      color: '#C084FC',
      stratColor: '#A855F7',
      type: 'orb'
    });
  }

  // Spot Price Line, Live Head Dot & Right Badge
  if (spot >= minP && spot <= maxP) {
    const sy = toY(spot);
    ctx.save();
    ctx.strokeStyle = 'rgba(56, 189, 248, 0.85)';
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.moveTo(padLeft, sy);
    ctx.lineTo(padLeft + plotW, sy);
    ctx.stroke();
    ctx.restore();

    rightBadges.push({
      rawY: sy,
      price: spot,
      stratTag: 'SPOT',
      subTag: '',
      label: '$' + spot.toFixed(1),
      color: '#FFFFFF',
      stratColor: '#0284C7',
      type: 'spot',
      isSpot: true
    });
  }

  // 4. Collision-Free Right Badges Layout (Stageshow Rounded Pills)
  const badgeH = 16;
  const spacing = badgeH + 2;
  rightBadges.forEach(b => { b.drawY = b.rawY; });
  rightBadges.sort((a, b) => a.drawY - b.drawY);

  // Group into contiguous overlapping clusters and center each cluster symmetrically around its mean rawY
  if (rightBadges.length > 0) {
    const clusters = [];
    let currentCluster = [rightBadges[0]];

    for (let i = 1; i < rightBadges.length; i++) {
      const prev = rightBadges[i - 1];
      const cur = rightBadges[i];
      if (Math.abs(cur.rawY - prev.rawY) < spacing) {
        currentCluster.push(cur);
      } else {
        clusters.push(currentCluster);
        currentCluster = [cur];
      }
    }
    clusters.push(currentCluster);

    clusters.forEach(cluster => {
      const meanRawY = cluster.reduce((sum, b) => sum + b.rawY, 0) / cluster.length;
      const totalClusterSpan = (cluster.length - 1) * spacing;
      const startY = meanRawY - (totalClusterSpan / 2);
      cluster.forEach((b, idx) => {
        b.drawY = startY + (idx * spacing);
      });
    });
  }

  // Push-down pass for any remaining collisions between clusters
  for (let i = 1; i < rightBadges.length; i++) {
    if (rightBadges[i].drawY < rightBadges[i - 1].drawY + spacing) {
      rightBadges[i].drawY = rightBadges[i - 1].drawY + spacing;
    }
  }
  // Bottom boundary clamp & upward push pass
  for (let i = rightBadges.length - 1; i >= 0; i--) {
    if (rightBadges[i].drawY > padTop + plotH - 8) {
      rightBadges[i].drawY = padTop + plotH - 8;
      if (i > 0 && rightBadges[i - 1].drawY > rightBadges[i].drawY - spacing) {
        rightBadges[i - 1].drawY = rightBadges[i].drawY - spacing;
      }
    }
  }
  // Top boundary clamp
  for (let i = 0; i < rightBadges.length; i++) {
    if (rightBadges[i].drawY < padTop + 8) {
      rightBadges[i].drawY = padTop + 8;
      if (i + 1 < rightBadges.length && rightBadges[i + 1].drawY < rightBadges[i].drawY + spacing) {
        rightBadges[i + 1].drawY = rightBadges[i].drawY + spacing;
      }
    }
  }

  rightBadges.forEach(b => {
    const by = b.drawY;
    const rx = padLeft + plotW + 3;

    ctx.save();
    if (Math.abs(by - b.rawY) > 2) {
      ctx.strokeStyle = hexToRgba(b.stratColor, 0.45);
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(padLeft + plotW, b.rawY);
      ctx.lineTo(rx, by);
      ctx.stroke();
    }

    const maxBadgeW = Math.max(60, padRight - 5);
    if (b.isSpot) {
      ctx.font = '600 10px "SF Mono", "JetBrains Mono", Consolas, monospace';
      const txtW = ctx.measureText(b.label).width;
      const rw = Math.min(maxBadgeW, Math.max(84, txtW + 16));

      ctx.fillStyle = '#0284C7';
      fillRoundRect(ctx, rx, by - 8, rw, 16, 5);
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.22)';
      ctx.lineWidth = 1;
      strokeRoundRect(ctx, rx, by - 8, rw, 16, 5);

      ctx.fillStyle = '#FFFFFF';
      ctx.fillText(b.label, rx + (rw - txtW) / 2, by + 3.5);
    } else {
      ctx.font = '600 8.5px "SF Mono", "JetBrains Mono", Consolas, monospace';
      const tagText = b.subTag ? `${b.stratTag}·${b.subTag}` : b.stratTag;
      const tagW = ctx.measureText(tagText).width;

      ctx.font = '500 8.5px "SF Mono", "JetBrains Mono", Consolas, monospace';
      const valW = ctx.measureText(b.label).width;
      const rw = Math.min(maxBadgeW, Math.max(84, tagW + valW + 20));

      // Raised Pill Badge
      ctx.fillStyle = 'rgba(6, 18, 42, 0.85)';
      fillRoundRect(ctx, rx, by - 7.5, rw, 15, 4.5);
      ctx.strokeStyle = 'rgba(186, 230, 253, 0.22)';
      ctx.lineWidth = 1;
      strokeRoundRect(ctx, rx, by - 7.5, rw, 15, 4.5);

      // Strategy Color Dot inside Pill
      ctx.fillStyle = b.stratColor;
      ctx.beginPath();
      ctx.arc(rx + 6.5, by, 2.5, 0, Math.PI * 2);
      ctx.fill();

      ctx.save();
      ctx.beginPath();
      ctx.rect(rx + 10, by - 7.5, rw - 12, 15);
      ctx.clip();

      ctx.font = '600 8px "SF Mono", "JetBrains Mono", Consolas, monospace';
      ctx.fillStyle = b.stratColor;
      ctx.fillText(tagText, rx + 12, by + 3);

      ctx.font = '500 8.5px "SF Mono", "JetBrains Mono", Consolas, monospace';
      ctx.fillStyle = b.color;
      ctx.fillText(b.label, rx + 12 + tagW + 4, by + 3);

      ctx.restore();
    }
    ctx.restore();
  });

  // 5. Off-Screen Order Indicator Pills (Auto Scale Mode)
  if (scaleMode === 'auto') {
    const maxPillX = padLeft + plotW - 12;
    if (offscreenTop.length > 0) {
      ctx.save();
      ctx.font = '500 9px "SF Mono", "JetBrains Mono", Consolas, monospace';
      let tx = padLeft + 6;
      for (const item of offscreenTop.slice(0, 4)) {
        const tw = ctx.measureText(item.label).width + 12;
        if (tx + tw > maxPillX) break;
        ctx.fillStyle = 'rgba(6, 18, 42, 0.85)';
        fillRoundRect(ctx, tx, padTop + 2, tw, 16, 5);
        ctx.strokeStyle = hexToRgba(item.color, 0.45);
        strokeRoundRect(ctx, tx, padTop + 2, tw, 16, 5);
        ctx.fillStyle = item.color;
        ctx.fillText(item.label, tx + 6, padTop + 13);
        tx += tw + 6;
      }
      ctx.restore();
    }

    if (offscreenBot.length > 0) {
      ctx.save();
      ctx.font = '500 9px "SF Mono", "JetBrains Mono", Consolas, monospace';
      let sx = padLeft + 6;
      for (const item of offscreenBot.slice(0, 4)) {
        const tw = ctx.measureText(item.label).width + 12;
        if (sx + tw > maxPillX) break;
        ctx.fillStyle = 'rgba(6, 18, 42, 0.85)';
        fillRoundRect(ctx, sx, padTop + plotH - 18, tw, 16, 5);
        ctx.strokeStyle = hexToRgba(item.color, 0.45);
        strokeRoundRect(ctx, sx, padTop + plotH - 18, tw, 16, 5);
        ctx.fillStyle = item.color;
        ctx.fillText(item.label, sx + 6, padTop + plotH - 7);
        sx += tw + 6;
      }
      ctx.restore();
    }
  }

  // 6. Active Strategy Entry Beacon Waves
  if (chartBeacons && chartBeacons.length > 0) {
    const now = Date.now();
    chartBeacons.forEach(b => {
      const elapsed = now - b.startTime;
      if (elapsed >= b.duration) return;
      const p = elapsed / b.duration;
      const by = Math.max(padTop + 10, Math.min(padTop + plotH - 10, toY(b.price)));
      const bx = Math.min(padLeft + candlePlotW + 4, Math.max(padLeft + 12, activeHeadX));

      ctx.save();
      const r1 = 4 + p * 30;
      const a1 = Math.max(0, (1 - p) * 0.85);
      ctx.strokeStyle = b.color;
      ctx.globalAlpha = a1;
      ctx.lineWidth = 1.8 * (1 - p);
      ctx.beginPath();
      ctx.arc(bx, by, r1, 0, Math.PI * 2);
      ctx.stroke();

      const p2 = (p + 0.38) % 1;
      const r2 = 4 + p2 * 30;
      const a2 = Math.max(0, (1 - p2) * 0.6);
      ctx.globalAlpha = a2;
      ctx.lineWidth = 1.4 * (1 - p2);
      ctx.beginPath();
      ctx.arc(bx, by, r2, 0, Math.PI * 2);
      ctx.stroke();

      const pulse = Math.sin(p * Math.PI * 8);
      ctx.globalAlpha = 0.95;
      ctx.fillStyle = b.color;
      ctx.beginPath();
      ctx.arc(bx, by, 3.2 + pulse * 1.1, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = b.color;
      ctx.font = '600 8.5px "SF Mono", "JetBrains Mono", Consolas, monospace';
      ctx.fillText(`${b.stratTag} ENTRY`, Math.max(padLeft + 6, bx - 35), by - 10);
      ctx.restore();
    });
  }

  // 7. Stageshow Interactive Scrub Hairline & Intersection Dot (examples/chart-scrub)
  if (priceHoverPos && priceHoverPos.x >= padLeft && priceHoverPos.x <= padLeft + plotW) {
    ctx.save();
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.16)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    const hx = hoveredCandleData ? hoveredCandleData.cx : priceHoverPos.x;
    ctx.moveTo(hx, padTop);
    ctx.lineTo(hx, padTop + plotH);
    ctx.stroke();

    if (priceHoverPos.y >= padTop && priceHoverPos.y <= padTop + plotH) {
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
      ctx.beginPath();
      ctx.moveTo(padLeft, priceHoverPos.y);
      ctx.lineTo(padLeft + plotW, priceHoverPos.y);
      ctx.stroke();
    }

    if (hoveredCandleData) {
      const cy = toY(hoveredCandleData.c);
      ctx.fillStyle = hoveredCandleData.c >= hoveredCandleData.o ? '#10F5A0' : '#FF4D79';
      ctx.strokeStyle = '#030A1C';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(hoveredCandleData.cx, cy, 4.5, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
    }
    ctx.restore();
  }
}

// Global Mouse Coordinate Tracking & Unified AIMRAN Specular Spotlight Tracker
let lastGlobalPointerX = -1;
let lastGlobalPointerY = -1;
let latestPointerEvent = null;
let spotlightRaf = null;

function trackLgSpotlight(e) {
  const evt = e || latestPointerEvent;
  if (!evt) return;
  let target = (evt.target && typeof evt.target.closest === 'function') ? evt.target : null;
  if (!target && evt.clientX !== undefined && evt.clientY !== undefined) {
    target = document.elementFromPoint(evt.clientX, evt.clientY);
  }
  if (!target || typeof target.closest !== 'function') return;

  const spotTarget = target.closest('.lg-spot-card, .strat-card-mini, .intel-event-card, .metal-fx-cta');
  if (spotTarget) {
    const r = spotTarget.getBoundingClientRect();
    const lx = Math.round(evt.clientX - r.left);
    const ly = Math.round(evt.clientY - r.top);
    spotTarget.style.setProperty('--mx', `${lx}px`);
    spotTarget.style.setProperty('--my', `${ly}px`);
  }
  const ctaTarget = target.closest('.metal-fx-cta');
  if (ctaTarget && ctaTarget !== spotTarget) {
    const cr = ctaTarget.getBoundingClientRect();
    ctaTarget.style.setProperty('--mx', `${Math.round(evt.clientX - cr.left)}px`);
    ctaTarget.style.setProperty('--my', `${Math.round(evt.clientY - cr.top)}px`);
  }
}

let cursorBackdropEl = null;

window.addEventListener('pointermove', (e) => {
  latestPointerEvent = e;
  lastGlobalPointerX = e.clientX;
  lastGlobalPointerY = e.clientY;
  if (!spotlightRaf) {
    spotlightRaf = requestAnimationFrame(() => {
      spotlightRaf = null;
      // Write --gx/--gy on the backdrop node itself rather than documentElement
      // so pointer moves never invalidate styles across the entire DOM tree.
      if (!cursorBackdropEl) {
        cursorBackdropEl = document.querySelector('.global-cursor-backdrop');
      }
      const gxTarget = cursorBackdropEl || document.documentElement;
      gxTarget.style.setProperty('--gx', `${latestPointerEvent.clientX}px`);
      gxTarget.style.setProperty('--gy', `${latestPointerEvent.clientY}px`);
      trackLgSpotlight(latestPointerEvent);
    });
  }
}, { passive: true });

function updateChartMouseHover(clientX, clientY) {
  if (!latestState) return;
  const wrap = document.getElementById('priceCanvasWrap');
  const tip = document.getElementById('priceTooltip');
  const scrubEl = document.getElementById('chartScrubReadout');
  if (!wrap || !tip) return;

  const rect = wrap.getBoundingClientRect();
  const isInside = clientX >= rect.left && clientX <= rect.right && clientY >= rect.top && clientY <= rect.bottom;

  let needsRedraw = false;

  if (isInside) {
    const mouseX = clientX - rect.left;
    const mouseY = clientY - rect.top;
    priceHoverPos = { x: mouseX, y: mouseY };

    const candles = (animCandles && animCandles.length > 0) ? animCandles : (latestState.candles || []);
    const useCandles = candles.length >= 2;
    const padLeft = 12, padRight = 98;
    const candleRightOffset = 80;
    const plotW = Math.max(50, rect.width - padLeft - padRight);
    const candlePlotW = Math.max(50, plotW - candleRightOffset);

    const snapY = Math.round(mouseY / 2) * 2;

    if (useCandles) {
      const n = candles.length;
      const maxStep = 13.0;
      const minStep = 5.5;
      const naturalStep = candlePlotW / Math.max(1, n);
      const step = Math.min(maxStep, Math.max(minStep, naturalStep));
      const totalCandleW = n * step;
      const startX = totalCandleW < candlePlotW ? (padLeft + candlePlotW - totalCandleW) : padLeft;
      const shiftX = candleSlideOffset;
      const idx = Math.floor((mouseX - startX - shiftX) / step);
      if (idx >= 0 && idx < n) {
        const c = candles[idx];
        const cx = startX + (idx + 0.5) * step + shiftX;
        hoveredCandleData = { o: c.o, h: c.h, l: c.l, c: c.c, cx };
        const isUp = c.c >= c.o;
        const chg = c.o > 0 ? (((c.c - c.o) / c.o) * 100).toFixed(2) : '0.00';
        const tStr = new Date(c.t * 1000).toTimeString().split(' ')[0];

        tip.style.display = 'block';
        tip.style.left = Math.min(rect.width - 195, Math.max(10, mouseX + 14)) + 'px';
        tip.style.top = Math.max(10, mouseY - 58) + 'px';
        const tipHtml = `
            <div style="font-weight:600;color:var(--ss-text);margin-bottom:2px;">${tStr} · 1m Candle</div>
            <div>O <strong>$${c.o.toFixed(1)}</strong> · H <strong>$${c.h.toFixed(1)}</strong></div>
            <div>L <strong>$${c.l.toFixed(1)}</strong> · C <strong class="${isUp ? 'up' : 'down'}">$${c.c.toFixed(1)} (${isUp ? '+' : ''}${chg}%)</strong></div>
          `;
        if (tip._lastHtml !== tipHtml) {
          tip._lastHtml = tipHtml;
          tip.innerHTML = tipHtml;
        }
        if (idx !== lastHoverIdx || Math.abs(snapY - lastHoverSnapY) >= 4) {
          needsRedraw = true;
          lastHoverIdx = idx;
          lastHoverSnapY = snapY;
        }
      } else {
        if (hoveredCandleData !== null || lastHoverIdx !== -1 || Math.abs(snapY - lastHoverSnapY) >= 4) {
          needsRedraw = true;
          lastHoverSnapY = snapY;
        }
        hoveredCandleData = null;
        lastHoverIdx = -1;
        tip.style.display = 'none';
      }
    } else {
      if (hoveredCandleData !== null || lastHoverIdx !== -1 || Math.abs(snapY - lastHoverSnapY) >= 4) {
        needsRedraw = true;
        lastHoverSnapY = snapY;
      }
      hoveredCandleData = null;
      lastHoverIdx = -1;
      tip.style.display = 'none';
    }
  } else {
    if (priceHoverPos !== null || hoveredCandleData !== null || lastHoverIdx !== -1) {
      needsRedraw = true;
    }
    priceHoverPos = null;
    hoveredCandleData = null;
    lastHoverIdx = -1;
    lastHoverSnapY = -1;
    tip.style.display = 'none';
    if (scrubEl) {
      scrubEl.textContent = '1m Candles';
    }
  }
  if (needsRedraw) {
    drawPriceChart(latestState);
  }
}

function locateMouseAndRefreshChart() {
  if (!latestState) return;
  const wrap = document.getElementById('priceCanvasWrap');
  if (!wrap) return;

  triggerSmoothResize();

  const isHovered = document.querySelector('#priceCanvasWrap:hover') !== null;
  if (isHovered && lastGlobalPointerX >= 0 && lastGlobalPointerY >= 0) {
    updateChartMouseHover(lastGlobalPointerX, lastGlobalPointerY);
  } else if (lastGlobalPointerX >= 0 && lastGlobalPointerY >= 0) {
    const rect = wrap.getBoundingClientRect();
    if (lastGlobalPointerX >= rect.left && lastGlobalPointerX <= rect.right &&
      lastGlobalPointerY >= rect.top && lastGlobalPointerY <= rect.bottom) {
      updateChartMouseHover(lastGlobalPointerX, lastGlobalPointerY);
    } else {
      priceHoverPos = null;
      hoveredCandleData = null;
      drawPriceChart(latestState);
    }
  } else {
    priceHoverPos = null;
    hoveredCandleData = null;
    drawPriceChart(latestState);
  }
}

function setupChartInteraction() {
  const wrap = document.getElementById('priceCanvasWrap');
  const tip = document.getElementById('priceTooltip');
  const scrubEl = document.getElementById('chartScrubReadout');
  if (!wrap || !tip) return;

  let hoverRaf = null;
  wrap.addEventListener('mousemove', (e) => {
    lastGlobalPointerX = e.clientX;
    lastGlobalPointerY = e.clientY;
    if (!hoverRaf) {
      hoverRaf = requestAnimationFrame(() => {
        hoverRaf = null;
        updateChartMouseHover(lastGlobalPointerX, lastGlobalPointerY);
      });
    }
  });

  wrap.addEventListener('mouseenter', (e) => {
    lastGlobalPointerX = e.clientX;
    lastGlobalPointerY = e.clientY;
    updateChartMouseHover(e.clientX, e.clientY);
  });

  wrap.addEventListener('mouseleave', () => {
    if (hoverRaf) {
      cancelAnimationFrame(hoverRaf);
      hoverRaf = null;
    }
    priceHoverPos = null;
    hoveredCandleData = null;
    lastHoverIdx = -1;
    lastHoverSnapY = -1;
    tip.style.display = 'none';
    if (scrubEl) {
      scrubEl.textContent = '1m Candles';
    }
    if (latestState) drawPriceChart(latestState);
  });
}

// Fluid ResizeObserver with 60 FPS requestAnimationFrame throttling
let resizeRaf = null;
const triggerSmoothResize = () => {
  invalidateCanvasSizeCache();
  if (resizeRaf) cancelAnimationFrame(resizeRaf);
  resizeRaf = requestAnimationFrame(() => {
    resizeRaf = null;
    if (latestState) drawPriceChart(latestState);
  });
};

const resizeObserver = new ResizeObserver(triggerSmoothResize);

function toggleFullscreen() {
  if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.toggle_fullscreen === 'function') {
    window.pywebview.api.toggle_fullscreen().catch(function (err) {
      console.warn('Native toggle_fullscreen fallback:', err);
      toggleDomFullscreen();
    });
  } else {
    toggleDomFullscreen();
  }
}

function toggleDomFullscreen() {
  if (!document.fullscreenElement) {
    if (document.documentElement.requestFullscreen) {
      document.documentElement.requestFullscreen().catch(function () { });
    }
  } else {
    if (document.exitFullscreen) {
      document.exitFullscreen().catch(function () { });
    }
  }
}

function blurActiveFocus() {
  if (document.activeElement && document.activeElement !== document.body && typeof document.activeElement.blur === 'function') {
    document.activeElement.blur();
  }
}

function isAnyModalBlockingShortcuts() {
  if (isWizardOpen) return true;
  const ids = ['shutdownModal', 'resetConfirmModal', 'installCancelConfirmModal', 'wizardCloseConfirmModal', 'networkOfflineOverlay', 'commandPaletteModal'];
  for (let i = 0; i < ids.length; i++) {
    const el = document.getElementById(ids[i]);
    if (el && el.classList.contains('modal-visible')) return true;
  }
  return false;
}

function syncAppShellInert() {
  const shell = document.querySelector('.app-shell');
  if (shell) {
    shell.inert = isAnyModalBlockingShortcuts();
  }
}

window.addEventListener('keydown', function (e) {
  if (e.key === 'F11' || e.code === 'F11' || e.keyCode === 122) {
    e.preventDefault();
    e.stopPropagation();
    toggleFullscreen();
    return;
  }
  const target = e.target;
  const tag = (target && target.tagName) ? target.tagName.toUpperCase() : '';
  const isTextInput = (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA');

  // Ctrl+K / Cmd+K Command Palette (never intercepts when inside Setup Wizard inputs)
  if ((e.ctrlKey || e.metaKey) && !e.altKey && (e.key === 'k' || e.key === 'K' || e.code === 'KeyK')) {
    if (!isWizardOpen && splashCompleted) {
      e.preventDefault();
      e.stopPropagation();
      toggleCommandPalette('commands');
    }
    return;
  }

  if (isTextInput || e.ctrlKey || e.altKey || e.metaKey) {
    return;
  }
  if ((e.key === '?' || (e.code === 'Slash' && e.shiftKey)) && splashCompleted) {
    if (!isAnyModalBlockingShortcuts()) {
      e.preventDefault();
      openCommandPalette('shortcuts');
    }
    return;
  }
  if (isAnyModalBlockingShortcuts() || !splashCompleted) {
    return;
  }
  if (target && target.getAttribute && target.getAttribute('role') === 'button' && (e.key === 'Enter' || e.code === 'Space')) {
    e.preventDefault();
    target.click();
    return;
  }
  if (e.code === 'Space') {
    if (tag === 'BUTTON' || tag === 'A') return;
    e.preventDefault();
    togglePause();
  } else if (e.code === 'Digit1' || e.key === '1') {
    switchMainView('arena');
  } else if (e.code === 'Digit2' || e.key === '2') {
    switchMainView('intel');
  } else if (e.code === 'KeyE' || e.key === 'e' || e.key === 'E') {
    triggerEvolution();
  } else if (e.code === 'KeyF' || e.key === 'f' || e.key === 'F') {
    setScaleMode(scaleMode === 'auto' ? 'full' : 'auto');
  }
}, true);

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

let lastCadenceFeedTs = '';
let uiClockInterval = null;

function updateUiClockDisplay() {
  if (document.hidden) return;
  const isPaused = Boolean(latestState && latestState.paused);
  const q = latestState && latestState.quote;
  const isOffline = Boolean(latestState && (latestState.market_online === false || (q && q.is_offline)));

  // Network offline blocking overlay (stageshow .ss-modal-overlay pattern):
  // shown only after the arena has revealed, so it never flashes over the
  // startup splash. Base .ss-modal-overlay styles already hide it; toggling
  // .modal-visible fades it in with the modal's own 1.25s entrance.
  const netOverlay = document.getElementById('networkOfflineOverlay');
  if (netOverlay) {
    const wasShown = netOverlay.classList.contains('modal-visible');
    const showNetOverlay = isOffline && document.body && document.body.classList.contains('arena-ready');
    netOverlay.classList.toggle('modal-visible', showNetOverlay);
    if (showNetOverlay && !wasShown) blurActiveFocus();
    if (showNetOverlay !== wasShown) syncAppShellInert();
  }

  const clockEl = document.getElementById('isoClockDisplay');
  if (!isPaused) {
    const now = new Date();
    const hh = String(now.getHours()).padStart(2, '0');
    const mm = String(now.getMinutes()).padStart(2, '0');
    const ss = String(now.getSeconds()).padStart(2, '0');
    const timeStr = `${hh}:${mm}:${ss}`;
    if (clockEl) {
      if (clockEl.textContent !== timeStr) clockEl.textContent = timeStr;
      clockEl._frozenTimeStr = timeStr;
    }
  } else {
    // When paused: strictly freeze the clock at the paused moment
    if (clockEl) {
      if (!clockEl._frozenTimeStr) {
        const now = new Date();
        const hh = String(now.getHours()).padStart(2, '0');
        const mm = String(now.getMinutes()).padStart(2, '0');
        const ss = String(now.getSeconds()).padStart(2, '0');
        clockEl._frozenTimeStr = `${hh}:${mm}:${ss}`;
      }
      if (clockEl.textContent !== clockEl._frozenTimeStr) clockEl.textContent = clockEl._frozenTimeStr;
    }
  }

  const clockMode = isPaused ? 'PAUSED' : (isOffline ? 'OFFLINE' : 'LIVE');
  const badgeEl = document.querySelector('.clock-cadence-badge');
  if (badgeEl && badgeEl._lastMode !== clockMode) {
    badgeEl._lastMode = clockMode;
    badgeEl.textContent = clockMode;
    if (isPaused) {
      badgeEl.style.background = 'rgba(255, 51, 75, 0.22)';
      badgeEl.style.color = '#FF334B';
      badgeEl.style.borderColor = 'rgba(255, 51, 75, 0.55)';
    } else if (isOffline) {
      badgeEl.style.background = 'rgba(255, 170, 0, 0.22)';
      badgeEl.style.color = '#FFAA00';
      badgeEl.style.borderColor = 'rgba(255, 170, 0, 0.55)';
    } else {
      badgeEl.style.background = 'rgba(16, 245, 160, 0.22)';
      badgeEl.style.color = '#10F5A0';
      badgeEl.style.borderColor = 'rgba(16, 245, 160, 0.45)';
    }
  }

  const subEl = document.getElementById('sourceSubtitle');
  if (subEl) {
    const nextSub = isPaused
      ? 'Feed Simulation Paused · Standing By'
      : (isOffline ? 'Exchange Feed Offline · Reconnecting...' : 'Realtime Stream · $500,000 Arena Pool');
    if (subEl.textContent !== nextSub) subEl.textContent = nextSub;
  }
}

  function startUiClock() {
    updateUiClockDisplay();
    if (uiClockInterval) clearInterval(uiClockInterval);
    uiClockInterval = setInterval(updateUiClockDisplay, 1000);
  }

  function openOmniRouteConsole() {
    // Console URL follows the configured gateway port (item 10 A2): the
    // bridge is the primary path; the fallback reuses the last port the
    // setup status reported (20128 until the first status call).
    const btn = document.getElementById('btnOpenOmniConsole');
    // No feedback used to make repeated clicks open a new tab each time:
    // show "opening..." immediately and ignore re-clicks until it settles.
    if (btn && btn.dataset.opening === '1') return;
    const labelEl = btn ? btn.querySelector('span') : null;
    const prevLabel = labelEl ? labelEl.textContent : '';
    if (btn) { btn.dataset.opening = '1'; btn.disabled = true; }
    if (labelEl) labelEl.textContent = 'opening...';
    const done = () => {
      if (btn) { delete btn.dataset.opening; btn.disabled = false; }
      if (labelEl) labelEl.textContent = prevLabel || 'Launch Console';
    };
    const port = (typeof window.__tradebotGatewayPort === 'number') ? window.__tradebotGatewayPort : 20128;
    const fallbackUrl = `http://127.0.0.1:${port}`;
    if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.open_omniroute_console === 'function') {
      window.pywebview.api.open_omniroute_console().then(done, () => {
        window.open(fallbackUrl, '_blank');
        done();
      });
    } else {
      window.open(fallbackUrl, '_blank');
      setTimeout(done, 1200);
    }
  }

  // AI panels (W2): 'Get a key' links open the provider's key page
  // in the system browser via the bridge (allowlisted there); the
  // window.open fallback covers the no-bridge preview.
  function openProviderKeyPage(url) {
    if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.open_external_url === 'function') {
      window.pywebview.api.open_external_url(url).catch((e) => console.debug('open key page err:', e));
    } else {
      window.open(url, '_blank');
    }
  }
  window.openProviderKeyPage = openProviderKeyPage;

  let currentMainView = 'arena';
  let viewSwitchToken = 0;
  let viewSwitchTimer = null;
  let viewSwitchRaf = 0;
  let isViewTransitioning = false;

  function clearOverlapTransitionStyles(el) {
    if (!el) return;
    el.classList.remove(
      'view-transition-prepare',
      'view-transition-entering',
      'view-transition-leaving-base',
      'view-transition-leaving',
      'view-entering'
    );
  }

  function switchMainView(viewName) {
    if (currentMainView === viewName) return;
    currentMainView = viewName;
    syncSegThumb('mainViewSeg', viewName === 'intel' ? 1 : 0);

    const stageHost = document.getElementById('viewStageHost');
    const arenaEl = document.querySelector('.workspace-grid');
    const intelEl = document.getElementById('intelHubMainView');
    const incoming = viewName === 'intel' ? intelEl : arenaEl;
    const outgoing = viewName === 'intel' ? arenaEl : intelEl;

    if (viewSwitchTimer) {
      clearTimeout(viewSwitchTimer);
      viewSwitchTimer = null;
    }
    if (viewSwitchRaf) {
      cancelAnimationFrame(viewSwitchRaf);
      viewSwitchRaf = 0;
    }
    clearOverlapTransitionStyles(arenaEl);
    clearOverlapTransitionStyles(intelEl);

    const token = ++viewSwitchToken;
    const reduce = isReducedMotionPreferred() || document.hidden;

    if (reduce || !outgoing || !incoming || !stageHost || outgoing.style.display === 'none') {
      isViewTransitioning = false;
      if (stageHost) stageHost.classList.remove('is-view-transitioning');
      if (outgoing) outgoing.style.display = 'none';
      if (incoming) incoming.style.display = 'grid';
      if (viewName === 'intel') {
        if (latestState) renderIntelHub(latestState);
        pumpIntelArticlePreload();
      } else {
        if (latestState) renderAll(latestState);
        triggerSmoothResize();
      }
      if (typeof refreshScrollAreaFades === 'function') refreshScrollAreaFades();
      if (typeof syncAmbientShaderMotion === 'function') syncAmbientShaderMotion();
      return;
    }

    isViewTransitioning = true;
    stageHost.classList.add('is-view-transitioning');
    if (typeof syncAmbientShaderMotion === 'function') syncAmbientShaderMotion();

    // Prepare outgoing/incoming layers on the same grid track & pre-render before frame 1
    outgoing.style.display = 'grid';
    outgoing.classList.add('view-transition-leaving-base');
    incoming.style.display = 'grid';
    incoming.classList.add('view-transition-prepare');

    if (viewName === 'intel') {
      if (latestState) renderIntelHub(latestState);
    } else {
      if (latestState) {
        renderAll(latestState);
        invalidateCanvasSizeCache();
        drawPriceChart(latestState);
      }
    }

    // Force single layout flush before GPU transition kicks off on next compositor frame
    void incoming.offsetHeight;

    viewSwitchRaf = requestAnimationFrame(() => {
      if (viewSwitchToken !== token) return;
      viewSwitchRaf = requestAnimationFrame(() => {
        viewSwitchRaf = 0;
        if (viewSwitchToken !== token) return;
        outgoing.classList.remove('view-transition-leaving-base');
        outgoing.classList.add('view-transition-leaving');
        incoming.classList.remove('view-transition-prepare');
        incoming.classList.add('view-transition-entering');
      });
    });

    viewSwitchTimer = setTimeout(() => {
      if (viewSwitchToken !== token) return;
      viewSwitchTimer = null;
      outgoing.style.display = 'none';
      clearOverlapTransitionStyles(outgoing);
      clearOverlapTransitionStyles(incoming);
      stageHost.classList.remove('is-view-transitioning');
      isViewTransitioning = false;
      if (typeof syncAmbientShaderMotion === 'function') syncAmbientShaderMotion();
      if (viewName === 'intel') {
        pumpIntelArticlePreload();
      } else {
        triggerSmoothResize();
      }
      if (typeof refreshScrollAreaFades === 'function') refreshScrollAreaFades();
    }, 560);
  }

  async function requestAiIntelDigest() {
    const btn = document.getElementById('btnRefreshDigest');
    if (btn) {
      btn.disabled = true;
      btn.classList.add('loading');
      const swapLbl = btn.querySelector('.action-swap-label');
      if (swapLbl) {
        swapLbl.textContent = 'Synthesizing...';
      } else {
        btn.innerHTML = `
        <svg class="ss-svg-icon btn-spin-icon" viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M14 8A6 6 0 1 1 8 2"></path>
        </svg>
        <span class="action-swap-label">Synthesizing...</span>
      `;
      }
    }

    // AI panels (I6): an indeterminate progress bar runs while the
    // refresh is in flight. A digest refresh has no trustworthy
    // percent, so none is fabricated; the bar hides again when the
    // button settles below.
    const digestProg = document.getElementById('digestRefreshProgress');
    const digestOrbs = document.getElementById('digestThinkingOrbs');
    const digestLbl = document.getElementById('digestRefreshLabel');
    if (digestLbl) digestLbl.textContent = 'Synthesizing live feeds...';
    if (digestOrbs) digestOrbs.classList.add('macro-is-thinking');
    if (digestProg) {
      digestProg.classList.add('active');
    }

    if (typeof showChartToast === 'function') {
      showChartToast({
        triggerReason: 'Refreshing news analysis...',
        action: 'INTEL'
      });
    }

    const myEpoch = ++stateApplyEpoch;
    try {
      if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.refresh_intel_digest === 'function') {
        const state = await window.pywebview.api.refresh_intel_digest();
        if (state && myEpoch === stateApplyEpoch) {
          latestState = state;
          renderAll(state);
        }
      }
    } catch (err) {
      console.error('Failed to refresh AI intel digest:', err);
    } finally {
      setTimeout(() => {
        if (btn) {
          btn.disabled = false;
          btn.classList.remove('loading');
          const swapLbl = btn.querySelector('.action-swap-label');
          if (swapLbl) {
            swapLbl.textContent = 'Refresh News Analysis';
          } else {
            btn.innerHTML = `
            <svg class="ss-svg-icon btn-spin-icon" viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M13.5 8a5.5 5.5 0 1 1-1.6-3.9L14 6.5M14 2.5v4h-4"></path>
            </svg>
            <span class="action-swap-label">Refresh News Analysis</span>
          `;
          }
        }
        if (digestOrbs) digestOrbs.classList.remove('macro-is-thinking');
        if (digestProg) {
          digestProg.classList.remove('active');
        }
      }, 1000);
    }
  }
  window.requestAiIntelDigest = requestAiIntelDigest;

  // Intel Hub stream redesign (Phase B): full-width rows, sort + expand.
  // Sort mode: 'time' (telemetry order) or 'impact' (urgency desc,
  // ties keep telemetry order). Expand state lives outside the render
  // so it survives re-sorts and the 1s re-render.
  let intelSortMode = 'time';
  const intelExpandedIds = new Set();
  const intelEventNodes = {};
  const intelArticleCache = {};
  const intelArticlePending = {};

  // Summary cleaner (sim splitBody): the harvester summary starts with
  // a fixed prefix and ends with a parenthetical tail carrying the
  // related tickers and the raw title. The display shows only the
  // cleaned summary sentence. The CJK literals are unicode escapes so
  // the static assets stay zero-CJK.
  const INTEL_SUMMARY_PREFIX = '\u7D9C\u5408\u5916\u96FB\u5831\u5C0E\uFF1A';
  const INTEL_TAIL_MARK_A = '\u95DC\u806F\u6A19\u7684';
  const INTEL_TAIL_MARK_B = '\u539F\u6587\u6A19\u984C';
  function cleanIntelSummary(summary) {
    let s = String(summary || '');
    if (s.indexOf(INTEL_SUMMARY_PREFIX) === 0) s = s.slice(INTEL_SUMMARY_PREFIX.length);
    let cutTail = false;
    const tailIdx = s.lastIndexOf('\uFF08');
    if (tailIdx >= 0) {
      const tail = s.slice(tailIdx);
      if (tail.indexOf(INTEL_TAIL_MARK_A) >= 0 || tail.indexOf(INTEL_TAIL_MARK_B) >= 0) {
        s = s.slice(0, tailIdx);
        cutTail = true;
      }
    }
    s = s.trim();
    // The tail carried the sentence-final period; put it back so the
    // cleaned sentence still ends with one.
    if (cutTail && s && s.charAt(s.length - 1) !== '\u3002') s += '\u3002';
    return s;
  }

  // Ticker chips: fixed colour per ticker. The five known tickers get
  // their colour from CSS [data-t] rules; anything else gets a stable
  // fallback class from a deterministic hash of the name, so the same
  // ticker is the same colour everywhere (including after a re-sort).
  const INTEL_KNOWN_TICKERS = ['BTC', 'ETH', 'AI', 'XRP', 'MACRO'];
  function hashTickerName(name) {
    let h = 5381;
    for (let i = 0; i < name.length; i++) h = ((h << 5) + h + name.charCodeAt(i)) >>> 0;
    return h;
  }
  function tickerChipClass(name) {
    const up = String(name || '').trim().toUpperCase();
    if (INTEL_KNOWN_TICKERS.indexOf(up) !== -1) return '';
    return 'tick-fh' + (hashTickerName(up) % 5);
  }

  function intelEventKey(evt) {
    return (evt && (evt.id || evt.headline)) || '';
  }

  // Stable sort: Impact orders by urgency descending; ties keep the
  // telemetry order (the decorate step makes the tie-break explicit).
  function sortIntelEvents(events) {
    if (intelSortMode !== 'impact') return events.slice();
    return events
      .map(function (evt, idx) { return { evt: evt, idx: idx }; })
      .sort(function (a, b) {
        const du = Number(b.evt.urgency || 5) - Number(a.evt.urgency || 5);
        return du !== 0 ? du : a.idx - b.idx;
      })
      .map(function (x) { return x.evt; });
  }

  let intelSortSeq = 0;
  let intelSortCollapseTimer = null;
  let intelSortTransitionPending = false;
  let intelSortTargetMode = null;

  function formatIntelEventTime(rawTime) {
    const txt = String(rawTime || '').trim();
    if (!txt) return '';
    const m = txt.match(/(\d{1,2}:\d{2}):\d{2}/);
    return m ? m[1] : txt;
  }

  function reorderIntelEventCards(listContainer, sorted) {
    if (!listContainer || !Array.isArray(sorted)) return;
    const reduceMotion = typeof window.matchMedia === 'function'
      && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const firstRects = new Map();
    if (!reduceMotion && listContainer.children.length > 0) {
      sorted.forEach(function (evt) {
        const key = intelEventKey(evt);
        const card = intelEventNodes[key];
        if (!card || card.parentNode !== listContainer || card.style.display === 'none') return;
        card.classList.remove('intel-card-reordering');
        card.style.transform = '';
        card.style.zIndex = '';
        firstRects.set(key, card.getBoundingClientRect());
      });
    }
    sorted.forEach(function (evt) {
      const card = intelEventNodes[intelEventKey(evt)];
      if (card) listContainer.appendChild(card);
    });
    if (reduceMotion || firstRects.size === 0) return;
    const moved = [];
    sorted.forEach(function (evt) {
      const key = intelEventKey(evt);
      const card = intelEventNodes[key];
      const first = firstRects.get(key);
      if (!card || !first) return;
      const last = card.getBoundingClientRect();
      const dx = first.left - last.left;
      const dy = first.top - last.top;
      if (Math.abs(dx) > 0.5 || Math.abs(dy) > 0.5) {
        card.style.transform = 'translate(' + dx + 'px, ' + dy + 'px)';
        card.style.zIndex = dy < 0 ? '2' : '1';
        moved.push(card);
      }
    });
    if (moved.length === 0) return;
    void listContainer.offsetHeight;
    const flipToken = performance.now();
    moved.forEach(function (card) {
      card._flipToken = flipToken;
      card.classList.add('intel-card-reordering');
    });
    requestAnimationFrame(function () {
      moved.forEach(function (card) {
        if (card._flipToken !== flipToken) return;
        card.style.transform = '';
      });
    });
    setTimeout(function () {
      moved.forEach(function (card) {
        if (card._flipToken !== flipToken) return;
        card.classList.remove('intel-card-reordering');
        card.style.transform = '';
        card.style.zIndex = '';
      });
    }, 460);
  }

  function setIntelSortMode(mode) {
    if (mode !== 'time' && mode !== 'impact') return;
    const effectiveCurrent = intelSortTransitionPending ? intelSortTargetMode : intelSortMode;
    if (effectiveCurrent === mode) return;
    intelSortSeq += 1;
    const seq = intelSortSeq;
    intelSortTargetMode = mode;
    if (intelSortCollapseTimer) {
      clearTimeout(intelSortCollapseTimer);
      intelSortCollapseTimer = null;
    }
    const isTimeMode = mode === 'time';
    const isImpactMode = mode === 'impact';
    syncSegThumb('intelSortSeg', isImpactMode ? 1 : 0);
    const timeBtn = document.getElementById('intelSortTime');
    const impactBtn = document.getElementById('intelSortImpact');
    if (timeBtn) {
      timeBtn.classList.toggle('active', isTimeMode);
      if (isTimeMode) timeBtn.setAttribute('data-on', '');
      else timeBtn.removeAttribute('data-on');
    }
    if (impactBtn) {
      impactBtn.classList.toggle('active', isImpactMode);
      if (isImpactMode) impactBtn.setAttribute('data-on', '');
      else impactBtn.removeAttribute('data-on');
    }

    const applySortNow = function () {
      if (seq !== intelSortSeq) return;
      intelSortTransitionPending = false;
      intelSortTargetMode = null;
      intelSortCollapseTimer = null;
      intelSortMode = mode;
      const list = document.getElementById('intelEventsList');
      if (list) list._intelOrder = '';
      if (latestState) renderIntelHub(latestState);
    };

    const hadExpanded = intelExpandedIds.size > 0;
    if (hadExpanded) {
      intelExpandedIds.forEach(function (openId) {
        const openCard = intelEventNodes[openId];
        if (openCard) openCard.classList.remove('is-open');
      });
      intelExpandedIds.clear();
      const reduceMotion = typeof window.matchMedia === 'function'
        && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      if (reduceMotion) {
        applySortNow();
      } else {
        intelSortTransitionPending = true;
        intelSortCollapseTimer = setTimeout(applySortNow, 360);
      }
      return;
    }

    applySortNow();
  }

  const intelArticleProgressTimers = {};

  function stopIntelArticleProgressPoll(eventId) {
    const t = intelArticleProgressTimers[eventId];
    if (t) {
      clearInterval(t);
      delete intelArticleProgressTimers[eventId];
    }
  }

  function updateIntelArticleLoadingUi(eventId, pct, stage) {
    const body = intelArticleBodyEl(eventId);
    if (!body || !body.classList.contains('is-loading')) return;
    const prevPct = typeof body._articlePct === 'number' ? body._articlePct : 0;
    const rawPct = Number(pct);
    const nextPct = Number.isFinite(rawPct) ? Math.max(prevPct, Math.min(100, Math.round(rawPct))) : prevPct;
    body._articlePct = nextPct;
    const stageEl = body.querySelector('.intel-article-stage');
    if (stageEl && typeof stage === 'string' && stage.trim()) {
      const nextStageTxt = ' \u00b7 ' + stage.trim();
      if (stageEl.textContent !== nextStageTxt) stageEl.textContent = nextStageTxt;
    }
    const pctEl = body.querySelector('.intel-article-pct');
    if (pctEl) {
      const nextPctTxt = nextPct + '%';
      if (pctEl.textContent !== nextPctTxt) pctEl.textContent = nextPctTxt;
    }
    const barEl = body.querySelector('.intel-article-progress');
    if (barEl) barEl.setAttribute('aria-valuenow', String(nextPct));
    const fillEl = body.querySelector('.intel-article-progress-fill');
    if (fillEl) fillEl.style.width = nextPct + '%';
  }

  function startIntelArticleProgressPoll(eventId) {
    stopIntelArticleProgressPoll(eventId);
    if (!window.pywebview || !window.pywebview.api || typeof window.pywebview.api.get_event_article_progress !== 'function') {
      return;
    }
    const tick = function () {
      if (!intelArticlePending[eventId]) {
        stopIntelArticleProgressPoll(eventId);
        return;
      }
      window.pywebview.api.get_event_article_progress(eventId).then(function (prog) {
        if (!intelArticlePending[eventId] || !prog || prog.ok !== true) return;
        updateIntelArticleLoadingUi(eventId, prog.progress, prog.stage);
      }).catch(function () {});
    };
    tick();
    intelArticleProgressTimers[eventId] = setInterval(tick, 400);
  }

  function intelArticleBodyEl(eventId) {
    const card = intelEventNodes[eventId] || null;
    return card ? card.querySelector('.intel-article-body') : null;
  }

  function renderIntelArticle(eventId, result) {
    const body = intelArticleBodyEl(eventId);
    if (!body) return;
    // The 1s re-render calls this for every open card (updateIntelEventCard
    // -> requestIntelArticle cache hit). Re-setting innerHTML here re-created
    // the <p> elements every second -- invisible until V2.8.5 gave them a
    // fade-in, which then replayed forever and the finished article visibly
    // jittered. Skip when this exact cached result is already displayed
    // (same object reference; the cache never replaces a result for an id).
    if (body._renderedResult === result) return;
    body._renderedResult = result;
    body._articlePct = result.state === 'ready' ? 100 : 0;
    if (result.state === 'ready') {
      const paras = String(result.article || '').split(/\n\s*\n/);
      const blocks = paras.length > 1 ? paras : String(result.article || '').split('\n');
      body.innerHTML = blocks
        .map(function (p) { return p.trim(); })
        .filter(function (p) { return p.length > 0; })
        .map(function (p) { return '<p class="intel-article-para">' + escapeHtml(p) + '</p>'; })
        .join('');
      body.classList.remove('is-loading');
    } else {
      // Honest failure: show the backend reason with an explicit retry action.
      body.innerHTML = '<div class="intel-article-error"><span>Article unavailable: '
        + escapeHtml(result.reason || 'Unknown error')
        + '</span><button type="button" class="intel-retry-btn" data-retry-event-id="'
        + escapeHtml(eventId)
        + '">Retry</button></div>';
      body.classList.remove('is-loading');
    }
  }

  // Lazy article load: first expand of an event calls the bridge once;
  // the result (ready or failed) is cached per event id, and an
  // in-flight call is never duplicated.
  function requestIntelArticle(eventId, isPreload = false) {
    const cached = intelArticleCache[eventId];
    if (cached) { renderIntelArticle(eventId, cached); return; }
    if (intelArticlePending[eventId]) return;
    const body = intelArticleBodyEl(eventId);
    if (body) {
      body._renderedResult = null;
      body._articlePct = 8;
      body.innerHTML = '<div class="intel-article-loading-row">'
        + '<div class="intel-article-loading">Loading article\u2026<span class="intel-article-stage"> \u00b7 Preparing event context</span></div>'
        + '<span class="intel-article-pct num">8%</span>'
        + '</div>'
        + '<div class="intel-article-progress" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="8" aria-label="Loading article">'
        + '<div class="digest-refresh-progress-track"><div class="digest-refresh-progress-fill intel-article-progress-fill" style="width:8%"></div></div>'
        + '</div>';
      body.classList.add('is-loading');
    }
    if (!window.pywebview || !window.pywebview.api || typeof window.pywebview.api.get_event_article !== 'function') {
      const fail = { state: 'failed', reason: 'Article service unavailable (bridge not connected)' };
      if (!isPreload) {
        intelArticleCache[eventId] = fail;
        renderIntelArticle(eventId, fail);
      }
      return;
    }
    const p = window.pywebview.api.get_event_article(eventId);
    intelArticlePending[eventId] = p;
    startIntelArticleProgressPoll(eventId);
    p.then(function (res) {
      stopIntelArticleProgressPoll(eventId);
      delete intelArticlePending[eventId];
      let result;
      if (res && res.ok === true && typeof res.article === 'string' && res.article.trim()) {
        updateIntelArticleLoadingUi(eventId, 100, 'Complete');
        result = { state: 'ready', article: res.article };
      } else {
        result = { state: 'failed', reason: (res && res.reason) || 'Article unavailable' };
      }
      if (intelEventNodes[eventId]) {
        // Do not poison cache with failed background preload results while card is collapsed.
        if (result.state === 'ready' || !isPreload || intelExpandedIds.has(eventId)) {
          intelArticleCache[eventId] = result;
          renderIntelArticle(eventId, result);
        }
      }
    }).catch(function (err) {
      stopIntelArticleProgressPoll(eventId);
      delete intelArticlePending[eventId];
      const result = { state: 'failed', reason: 'Article request failed: ' + (err && err.message ? err.message : String(err)) };
      if (intelEventNodes[eventId]) {
        if (!isPreload || intelExpandedIds.has(eventId)) {
          intelArticleCache[eventId] = result;
          renderIntelArticle(eventId, result);
        }
      }
    });
  }

  // Background article preload (user request 2026-11-16): an article used
  // to start loading only on first expand. While the cards sit collapsed,
  // preload them in list order, one at a time, through the same
  // requestIntelArticle path -- its cache/pending dedup means an expand
  // mid-preload never duplicates the call, and the rendered article is
  // already in the (hidden) body when the card opens. Sequential on
  // purpose: each article is one ~1000-word LLM call; a burst would
  // hammer the gateway. Only runs while the Hub view is active (called
  // from renderIntelHub's list-update branch). Preload never expands a card.
  const intelArticlePreloadQueue = [];
  let intelArticlePreloadRunning = false;

  function preloadIntelArticles(eventIds) {
    eventIds.forEach(function (id) {
      if (intelArticleCache[id] || intelArticlePending[id]) return;
      if (intelArticlePreloadQueue.indexOf(id) === -1) intelArticlePreloadQueue.push(id);
    });
    pumpIntelArticlePreload();
  }

  function pumpIntelArticlePreload() {
    if (intelArticlePreloadRunning) return;
    if (currentMainView !== 'intel' || document.hidden) return;
    const omniStatus = latestState && latestState.intel_hub && latestState.intel_hub.omniroute && latestState.intel_hub.omniroute.status;
    if (omniStatus !== 'ONLINE') return;
    let id;
    while ((id = intelArticlePreloadQueue.shift()) !== undefined) {
      // The event may have left the list, or an expand may have already
      // started / cached it, while it waited in the queue.
      if (intelArticleCache[id] || intelArticlePending[id] || !intelEventNodes[id]) continue;
      break;
    }
    if (id === undefined) return;
    intelArticlePreloadRunning = true;
    requestIntelArticle(id, true);
    const p = intelArticlePending[id];
    if (p && typeof p.then === 'function') {
      const done = function () {
        intelArticlePreloadRunning = false;
        pumpIntelArticlePreload();
      };
      p.then(done, done);
    } else {
      // No pending promise: the bridge is missing (failed fast and cached
      // the failure) or the article was already cached.
      intelArticlePreloadRunning = false;
      pumpIntelArticlePreload();
    }
  }

  function buildIntelEventCard(evt) {
    const card = document.createElement('article');
    card.className = 'intel-event-card lg-spot-card';
    card.dataset.eventId = intelEventKey(evt);
    card.innerHTML =
      '<div class="intel-card-header">'
      + '<span class="intel-event-time num"></span>'
      + '<span class="intel-domain-badge"></span>'
      + '<span class="intel-source-badge"></span>'
      + '<span class="intel-urgency-badge num"></span>'
      + '<span class="intel-sentiment-badge num"></span>'
      + '<span class="intel-expand-chevron" aria-hidden="true">&lt;</span>'
      + '</div>'
      + '<div class="intel-card-headline"></div>'
      + '<div class="intel-card-summary"></div>'
      + '<div class="intel-event-detail"><div class="intel-event-detail-inner">'
      + '<div class="intel-article-body"></div>'
      + '<div class="intel-tick-row"></div>'
      + '<div class="intel-strategy-actions-box">'
      + '<div class="intel-strategy-box-title">Arena Competitor Impact (Strategies 1 ~ 5)</div>'
      + '<div class="strat-actions-wrap"></div>'
      + '</div>'
      + '</div></div>';
    return card;
  }

  function updateIntelEventCard(card, evt, macro) {
    // Cached refs (same pattern as _urgEl below): the card node and its
    // header spans are never rebuilt, so one query each on first use and
    // zero per-tick queries afterwards -- was 7 querySelector calls per
    // card on every 1s re-render.
    const head = card._intelHead || (card._intelHead = card.querySelector('.intel-card-header'));
    const timeEl = card._intelTimeEl || (card._intelTimeEl = head.querySelector('.intel-event-time'));
    const domEl = card._intelDomEl || (card._intelDomEl = head.querySelector('.intel-domain-badge'));
    const srcEl = card._intelSrcEl || (card._intelSrcEl = head.querySelector('.intel-source-badge'));
    // Stable-node cache: this badge's class is swapped to
    // 'intel-domain-badge' below when urg < 8, so a fresh
    // '.intel-urgency-badge' query on the next 1s re-render would
    // return null and crash renderIntelHub. The card node (and its
    // header spans) is never rebuilt, so caching the reference is safe.
    const urgEl = card._urgEl || (card._urgEl = head.querySelector('.intel-urgency-badge'));
    const sentEl = card._intelSentEl || (card._intelSentEl = head.querySelector('.intel-sentiment-badge'));
    const rawTime = evt.time || '';
    const nextTime = formatIntelEventTime(rawTime);
    if (timeEl.textContent !== nextTime) timeEl.textContent = nextTime;
    const timeTip = evt.date_time || rawTime;
    if (timeTip && timeEl.title !== timeTip) timeEl.title = timeTip;
    const nextDom = (evt.domain || 'macro').toUpperCase();
    if (domEl.textContent !== nextDom) domEl.textContent = nextDom;
    const nextSrc = evt.source || 'News Wire';
    if (srcEl.textContent !== nextSrc) srcEl.textContent = nextSrc;
    const urg = Number(evt.urgency || 5);
    const nextUrg = urg >= 8 ? ('URG ' + urg + '/10 CRITICAL') : ('URG ' + urg + '/10');
    if (urgEl.textContent !== nextUrg) urgEl.textContent = nextUrg;
    const nextUrgCls = urg >= 8 ? 'intel-urgency-badge num' : 'intel-domain-badge num';
    if (urgEl.className !== nextUrgCls) urgEl.className = nextUrgCls;
    const sent = Number(evt.sentiment || 0);
    let sentCls = 'neutral';
    let sentTxt = (sent >= 0 ? '+' : '') + sent.toFixed(2) + ' Neutral';
    if (sent > 0.2) { sentCls = 'bullish'; sentTxt = '+' + sent.toFixed(2) + ' Bullish'; }
    else if (sent < -0.2) { sentCls = 'bearish'; sentTxt = sent.toFixed(2) + ' Bearish'; }
    const nextSentCls = 'intel-sentiment-badge num ' + sentCls;
    if (sentEl.className !== nextSentCls) sentEl.className = nextSentCls;
    if (sentEl.textContent !== sentTxt) sentEl.textContent = sentTxt;
    const headEl = card._intelHeadlineEl || (card._intelHeadlineEl = card.querySelector('.intel-card-headline'));
    const nextHead = evt.headline || '';
    if (headEl.textContent !== nextHead) headEl.textContent = nextHead;
    const sumEl = card._intelSummaryEl || (card._intelSummaryEl = card.querySelector('.intel-card-summary'));
    const nextSum = cleanIntelSummary(evt.summary || '');
    if (sumEl.textContent !== nextSum) sumEl.textContent = nextSum;
    const tickers = Array.isArray(evt.tickers) ? evt.tickers : [];
    const tickKey = tickers.join('|');
    if (card._tickKey !== tickKey) {
      card._tickKey = tickKey;
      card.querySelector('.intel-tick-row').innerHTML = tickers.map(function (t) {
        const name = String(t).trim().toUpperCase();
        return '<span class="intel-tick ' + tickerChipClass(name) + '" data-t="' + escapeHtml(name) + '">' + escapeHtml(name) + '</span>';
      }).join('');
    }
    const actions = evt.strategy_actions || [];
    const allowedBadgeCls = { bullish: 1, bearish: 1, neutral: 1, buy: 1, sell: 1, profit: 1, loss: 1, info: 1 };
    let actionsHtml = '';
    if (actions.length > 0) {
      actionsHtml = actions.map(function (act) {
        const rawCls = String(act.badge_cls || 'neutral').trim().toLowerCase();
        const bCls = allowedBadgeCls[rawCls] ? rawCls : 'neutral';
        return `<span class="strat-action-pill ${bCls}">`
          + '<strong>' + escapeHtml(act.name) + '</strong>: ' + escapeHtml(act.action) + ' <small style="opacity:0.75;">(' + escapeHtml(act.time || '') + ')</small>'
          + '</span>';
      }).join('');
    } else {
      actionsHtml = '<span class="strat-action-pill neutral">Strategies 1~5: Active Monitoring under ' + escapeHtml(macro.directional_bias || 'BIDIRECTIONAL') + ' Directive</span>';
    }
    if (card._impactHtml !== actionsHtml) {
      card._impactHtml = actionsHtml;
      card.querySelector('.strat-actions-wrap').innerHTML = actionsHtml;
    }
    const eventId = intelEventKey(evt);
    const isOpen = intelExpandedIds.has(eventId);
    card.classList.toggle('is-open', isOpen);
    if (evt.article_state === 'loading' && intelArticlePending[eventId]) {
      updateIntelArticleLoadingUi(eventId, evt.article_progress, evt.article_stage);
    }
    if (isOpen) requestIntelArticle(eventId);
  }

  function toggleIntelEventCard(card) {
    if (!card) return;
    const eventId = card.dataset.eventId || '';
    if (!eventId) return;
    if (intelExpandedIds.has(eventId)) {
      intelExpandedIds.delete(eventId);
      card.classList.remove('is-open');
    } else {
      intelExpandedIds.add(eventId);
      card.classList.add('is-open');
      requestIntelArticle(eventId);
    }
  }

  let intelDomainFilter = 'all';
  let intelSearchQuery = '';

  function setIntelDomainFilter(domain) {
    intelDomainFilter = domain || 'all';
    const chipsWrap = document.getElementById('intelDomainChips');
    if (chipsWrap) {
      chipsWrap.querySelectorAll('.intel-chip').forEach((chip) => {
        const isMatched = chip.getAttribute('data-domain') === intelDomainFilter;
        chip.classList.toggle('is-active', isMatched);
      });
    }
    if (latestState) renderIntelHub(latestState);
  }
  window.setIntelDomainFilter = setIntelDomainFilter;

  function toggleIntelSearch(force) {
    const wrap = document.getElementById('intelSearchWrap');
    const input = document.getElementById('intelSearchInput');
    if (!wrap) return;
    const nextOpen = typeof force === 'boolean' ? force : !wrap.classList.contains('is-open');
    wrap.classList.toggle('is-open', nextOpen);
    if (nextOpen && input) {
      setTimeout(() => input.focus(), 60);
    }
  }
  window.toggleIntelSearch = toggleIntelSearch;

  function clearIntelSearch() {
    const input = document.getElementById('intelSearchInput');
    const clearBtn = document.getElementById('btnIntelSearchClear');
    intelSearchQuery = '';
    if (input) input.value = '';
    if (clearBtn) clearBtn.classList.remove('visible');
    if (latestState) renderIntelHub(latestState);
  }
  window.clearIntelSearch = clearIntelSearch;

  function matchesIntelFilter(evt) {
    if (!evt) return false;
    const dom = String(evt.domain || '').toLowerCase();
    const text = (
      String(evt.headline || '') + ' ' +
      String(evt.summary || '') + ' ' +
      String(evt.source || '') + ' ' +
      String((evt.tickers || []).join(' '))
    ).toLowerCase();

    if (intelDomainFilter && intelDomainFilter !== 'all') {
      if (intelDomainFilter === 'macro') {
        if (dom !== 'macro' && dom !== 'corporate' && !/\b(cpi|gdp|payroll|treasury|yield|ism|macro)\b/i.test(text)) return false;
      } else if (intelDomainFilter === 'fed') {
        if (!/\b(fed|fomc|powell|rate|cpi|pce|treasury)\b|\u806f\u6e96\u6703|\u7f8e\u806f\u5132|\u5229\u7387|\u592e\u884c/i.test(text) && dom !== 'macro') return false;
      } else if (intelDomainFilter === 'crypto') {
        if (dom !== 'crypto' && dom !== 'forum' && dom !== 'prediction' && !/\b(eth|btc|etf|crypto|sol|xrp|defi|ethereum|bitcoin)\b/i.test(text)) return false;
      } else if (intelDomainFilter === 'tech') {
        if (dom !== 'tech' && !/\b(ai|gpu|chip|semi|semiconductor|nvidia|tsmc|amd)\b|\u534a\u5c0e\u9ad4|\u6676\u7247/i.test(text)) return false;
      } else if (intelDomainFilter === 'geopolitics') {
        if (dom !== 'geopolitics') return false;
      }
    }

    if (intelSearchQuery) {
      if (text.indexOf(intelSearchQuery) === -1) return false;
    }
    return true;
  }

  function renderIntelHub(state) {
    if (!state) return;
    const intel = state.intel_hub || {};
    const omni = intel.omniroute || {};
    const macro = intel.macro_state || state.macro_commander || {};
    const events = intel.events || [];

    // 1. OmniRoute Gateway Status
    const statusPill = document.getElementById('omniGatewayStatusPill');
    if (statusPill) {
      const isOnline = omni.status === 'ONLINE';
      const nextPillCls = `intel-status-pill ss-badge ${isOnline ? 'online' : 'standby'}`;
      if (statusPill.className !== nextPillCls) {
        statusPill.className = nextPillCls;
      }
      // AI panels (I1): the pill says only Online / Standby. When
      // the current regime came from the local keyword fallback,
      // say so on the reserved line under the pill instead.
      const isFallback = macro.fallback === true;
      const nextPillHtml = `<span class="ss-badge__dot"></span><span class="ss-badge__label">${isOnline ? 'Online' : 'Standby'}</span>`;
      if (statusPill._lastHtml !== nextPillHtml) {
        statusPill.innerHTML = nextPillHtml;
        statusPill._lastHtml = nextPillHtml;
      }
      const fbLine = document.getElementById('intelFallbackLine');
      if (fbLine) fbLine.classList.toggle('visible', isFallback);
      // Gateway diagnosis workstream: one plain-language line under
      // the pill -- quota exhausted (all providers), connection
      // problem, or restarting. Only the two user-facing states plus
      // the restarting line; anything else leaves the line empty.
      // The slot collapses while empty (user decision 2026-11-16,
      // sim-approved), so showing the line grows the deck.
      const diagLine = document.getElementById('intelDiagnosisLine');
      if (diagLine) {
        const diag = omni.diagnosis || 'ok';
        let diagText = '';
        if (diag === 'quota_exhausted') diagText = 'AI quota exhausted — all providers out of credits';
        else if (diag === 'connection_problem') diagText = 'Connection problem — AI services unreachable';
        else if (diag === 'restarting') diagText = 'AI services stopped — restarting…';
        if (diagLine._lastDiag !== diag) {
          diagLine.textContent = diagText;
          diagLine._lastDiag = diag;
        }
        diagLine.classList.toggle('visible', diagText !== '');
      }
    }

    const epEl = document.getElementById('omniEndpointVal');
    if (epEl) {
      const nextEp = omni.endpoint || 'http://localhost:20128/v1';
      if (epEl.textContent !== nextEp) epEl.textContent = nextEp;
    }

    const tokensEl = document.getElementById('omniTokensVal');
    if (tokensEl) {
      const usedNum = Number(omni.tokens_used || 0);
      const savedNum = Number(omni.tokens_saved || 0);
      const nextTokens = savedNum > 0
        ? `${usedNum.toLocaleString()} used / ${savedNum.toLocaleString()} saved`
        : `${usedNum.toLocaleString()} tokens used`;
      if (tokensEl.textContent !== nextTokens) tokensEl.textContent = nextTokens;
    }

    const tokensSub = document.getElementById('omniTokensSub');
    if (tokensSub) {
      const used = omni.tokens_used || 0;
      const saved = omni.tokens_saved || 0;
      const tot = used + saved;
      const pct = tot > 0 ? ((saved / tot) * 100).toFixed(1) : (omni.dedup_pct ? omni.dedup_pct.toFixed(1) : '0.0');
      // Item 12 / A4-3: token "saved" is no longer a claimed figure, so the
      // dedup line reports the counted hits instead of a fabricated percent.
      const hits = omni.dedup_hits;
      let nextSub = (typeof hits === 'number' && hits > 0)
        ? `${hits.toLocaleString()} dupes skipped (SHA-256)`
        : `${pct}% SHA-256 Dedup Saved`;
      // The Remaining Quota cell was removed (2026-11-13); the digest
      // throttle note (item 12 / A4-4) moves here so it stays visible.
      if (omni.quota_throttled === true) {
        nextSub += ' — Digest throttled';
      }
      if (tokensSub.textContent !== nextSub) tokensSub.textContent = nextSub;
      // AI panels (I3): the user-facing throttle signal is a plain
      // line under the Market Direction card, shown only while throttled.
      const throttleLine = document.getElementById('macroThrottleLine');
      if (throttleLine) throttleLine.classList.toggle('visible', omni.quota_throttled === true);
    }

    // Bencho context-meter segment sync for Token Utilization
    const meterEl = document.getElementById('omniTokenMeter');
    const segAct = document.getElementById('omniTokenSegActive');
    const segSav = document.getElementById('omniTokenSegSaved');
    const lblAct = document.getElementById('omniMeterActiveLbl');
    const lblSav = document.getElementById('omniMeterSavedLbl');
    if (meterEl && segAct && segSav && lblAct && lblSav) {
      const usedNum = Number(omni.tokens_used || 0);
      const savedNum = Number(omni.tokens_saved || 0);
      const totNum = usedNum + savedNum;
      let activePct = 0;
      let savedPct = 0;
      if (totNum > 0) {
        savedPct = Math.round((savedNum / totNum) * 100);
        activePct = Math.max(0, 100 - savedPct);
      } else if (usedNum > 0) {
        activePct = 100;
        savedPct = 0;
      } else if (typeof omni.dedup_pct === 'number' && omni.dedup_pct > 0) {
        savedPct = Math.min(100, Math.round(omni.dedup_pct));
        activePct = Math.max(0, 100 - savedPct);
      }
      const nextActW = activePct + '%';
      const nextSavW = savedPct + '%';
      if (segAct.style.width !== nextActW) segAct.style.width = nextActW;
      if (segSav.style.width !== nextSavW) segSav.style.width = nextSavW;
      const nextActLbl = `Used ${activePct}%`;
      const nextSavLbl = `Saved ${savedPct}%`;
      if (lblAct.textContent !== nextActLbl) lblAct.textContent = nextActLbl;
      if (lblSav.textContent !== nextSavLbl) lblSav.textContent = nextSavLbl;
    }

    // AI panels (I5): the Stage-1 / Stage-2 model tags were removed;
    // the ingest/commander model names are no longer displayed.

    const reqEl = document.getElementById('omniReqCounters');
    if (reqEl) {
      const nextReq = `Reqs: ${omni.total_requests || 0} | OK: ${omni.successful_requests || 0} | Fail: ${omni.failed_requests || 0}`;
      if (reqEl.textContent !== nextReq) reqEl.textContent = nextReq;
    }

    // 2. Macro Regime Card
    const regBadge = document.getElementById('macroRegimeHubBadge');
    if (regBadge) {
      const reg = (macro.regime || 'NORMAL').toUpperCase();
      let cls = 'neutral';
      if (reg.includes('SURGE')) cls = 'surge';
      else if (reg.includes('PANIC') || reg.includes('CHOP')) cls = 'standby';
      const nextRegCls = `intel-status-pill ss-badge ${cls}`;
      if (regBadge.className !== nextRegCls) regBadge.className = nextRegCls;
      if (regBadge.textContent !== reg) regBadge.textContent = reg;
    }

    const biasEl = document.getElementById('macroHubBias');
    if (biasEl) {
      const nextBias = macro.directional_bias || 'BIDIRECTIONAL';
      if (biasEl.textContent !== nextBias) morphText(biasEl, nextBias);
    }

    const biasSub = document.getElementById('macroHubBiasSub');
    if (biasSub) {
      const b = macro.directional_bias || 'BIDIRECTIONAL';
      let nextBiasSub;
      if (b === 'LONG_ONLY') nextBiasSub = 'Strict Veto Active: All Short Trades Blocked';
      else if (b === 'SHORT_ONLY') nextBiasSub = 'Strict Veto Active: All Long Trades Blocked';
      else if (b === 'HOLD_CASH') nextBiasSub = 'Severe Risk-Off: All Opening Orders Blocked';
      else nextBiasSub = 'All 5 Arena Strategies Permitted';
      if (biasSub.textContent !== nextBiasSub) biasSub.textContent = nextBiasSub;
    }

    const multEl = document.getElementById('macroHubRiskMult');
    if (multEl) {
      const nextMult = `${Number(macro.risk_multiplier || 1.0).toFixed(2)}x`;
      if (multEl.textContent !== nextMult) multEl.textContent = nextMult;
    }

    const confEl = document.getElementById('macroHubConfidence');
    if (confEl) {
      const confVal = macro.confidence != null ? Number(macro.confidence) : 0.8;
      const nextConf = `${Math.round((Number.isFinite(confVal) ? confVal : 0.8) * 100)}%`;
      if (confEl.textContent !== nextConf) confEl.textContent = nextConf;
    }

    const lastEval = document.getElementById('macroHubLastEval');
    if (lastEval) {
      const nextEval = `Last Eval: ${macro.last_synthesis_time || 'Continuous'}`;
      if (lastEval.textContent !== nextEval) lastEval.textContent = nextEval;
    }

    const vetoEl = document.getElementById('macroHubVetoCount');
    if (vetoEl) {
      const nextVeto = String(macro.veto_count_today || 0);
      if (vetoEl.textContent !== nextVeto) vetoEl.textContent = nextVeto;
    }

    const headEl = document.getElementById('macroHubHeadline');
    if (headEl) {
      const nextHead = macro.active_headline || 'Market in balanced equilibrium.';
      if (headEl.textContent !== nextHead) headEl.textContent = nextHead;
    }

    // 3. Curated Event Cards
    const countLbl = document.getElementById('intelEventCountLabel');
    if (countLbl) {
      const nextCount = `${events.length} Curated Events`;
      if (countLbl.textContent !== nextCount) countLbl.textContent = nextCount;
    }

    const listContainer = document.getElementById('intelEventsList');
    if (listContainer) {
      if (currentMainView !== 'intel' && listContainer.children.length > 0) {
        // Hub panel is hidden; preserve existing DOM nodes to save rendering cycles
      } else if (events.length === 0) {
        // Intel Hub layout (workstream 3): the empty stream is a
        // loading block centered in the stream section (label +
        // meter + percent), not a line pinned to the top of a void.
        // The percent is the backend pipeline milestone, capped at
        // 90 until the first events actually render -- it never
        // claims 100 while the stream is still loading.
        listContainer.classList.add('is-loading');
        // The stream is empty: drop the stable nodes (the loading
        // block replaces them via innerHTML below), so no stale card
        // can be re-appended when events arrive again.
        Object.keys(intelEventNodes).forEach(function (key) { delete intelEventNodes[key]; });
        Object.keys(intelArticleCache).forEach(function (key) { delete intelArticleCache[key]; });
        intelExpandedIds.clear();
        intelArticlePreloadQueue.length = 0;
        listContainer._intelOrder = '';
        const sync = intel.sync || {};
        const stage = typeof sync.stage === 'string' ? sync.stage : 'idle';
        const rawPct = Number(sync.percent);
        const pct = Math.min(Number.isFinite(rawPct) ? rawPct : 0, 90);
        let loadLabel = (typeof sync.detail === 'string' && sync.detail) ? sync.detail : 'Starting sync…';
        if (stage === 'failed') loadLabel += ' — press Refresh News Analysis to retry';
        const loadHtml = '<div class="intel-stream-loading">'
          + '<div class="intel-stream-loading-label">' + escapeHtml(loadLabel) + '</div>'
          + '<div class="ss-meter intel-stream-progress-track"><div class="ss-meter__fill intel-stream-progress-fill" style="width:' + pct + '%"></div></div>'
          + '<div class="intel-stream-progress-pct num">' + pct + '%</div>'
          + '</div>';
        if (listContainer._lastHtml !== loadHtml) {
          listContainer.innerHTML = loadHtml;
          listContainer._lastHtml = loadHtml;
        }
      } else {
        listContainer.classList.remove('is-loading');
        // 2026-11-15: the empty branch writes the loading block into
        // this container via innerHTML, but this branch only appended
        // card nodes and never removed it -- on a real cold start the
        // "Starting sync... 0%" block stayed pinned above the events
        // forever. Drop it here; the empty branch already cleared
        // intelEventNodes, so no card can be deleted by mistake.
        // Reset _lastHtml too: it still claims the loading HTML is
        // present, and the next empty render would otherwise skip
        // rewriting innerHTML when the stage/label repeat.
        const staleLoad = listContainer.querySelector('.intel-stream-loading');
        if (staleLoad) {
          staleLoad.parentNode.removeChild(staleLoad);
          listContainer._lastHtml = '';
        }
        // Stable per-event nodes (same pattern as stratCardDomMap):
        // create once, update in place, never rebuild innerHTML, so
        // expand state and lazy articles survive the 1s re-render.
        const sorted = sortIntelEvents(events);
        const seenKeys = new Set();
        let visibleCount = 0;
        sorted.forEach(function (evt) {
          const key = intelEventKey(evt);
          seenKeys.add(key);
          let card = intelEventNodes[key];
          if (!card) {
            card = buildIntelEventCard(evt);
            intelEventNodes[key] = card;
            listContainer.appendChild(card);
          }
          updateIntelEventCard(card, evt, macro);
          const matches = matchesIntelFilter(evt);
          card.style.display = matches ? '' : 'none';
          if (matches) visibleCount += 1;
        });
        Object.keys(intelEventNodes).forEach(function (key) {
          if (!seenKeys.has(key)) {
            const stale = intelEventNodes[key];
            if (stale && stale.parentNode) stale.parentNode.removeChild(stale);
            delete intelEventNodes[key];
            delete intelArticleCache[key];
            intelExpandedIds.delete(key);
          }
        });
        let emptyFilterEl = listContainer.querySelector('.intel-empty-filter');
        if (visibleCount === 0) {
          if (!emptyFilterEl) {
            emptyFilterEl = document.createElement('div');
            emptyFilterEl.className = 'intel-empty-filter';
            emptyFilterEl.textContent = 'No events match the active domain chip or search filter.';
            listContainer.appendChild(emptyFilterEl);
          }
        } else if (emptyFilterEl) {
          emptyFilterEl.parentNode.removeChild(emptyFilterEl);
        }
        if (countLbl) {
          const isFiltered = (intelDomainFilter !== 'all') || (intelSearchQuery.length > 0);
          const nextFilteredCount = isFiltered
            ? `${visibleCount} / ${events.length} Filtered`
            : `${events.length} Curated Events`;
          if (countLbl.textContent !== nextFilteredCount) countLbl.textContent = nextFilteredCount;
        }
        const nextOrder = sorted.map(intelEventKey).join('|');
        if (!intelSortTransitionPending && listContainer._intelOrder !== nextOrder) {
          reorderIntelEventCards(listContainer, sorted);
          listContainer._intelOrder = nextOrder;
        }
        // Preload articles for the collapsed cards (see preloadIntelArticles):
        // the list order is the display order, so the cards the user is
        // most likely to open first are preloaded first.
        preloadIntelArticles(sorted.map(intelEventKey));
        if (typeof refreshScrollAreaFades === 'function') refreshScrollAreaFades();
      }
    }
  }


  window.addEventListener('DOMContentLoaded', () => {
    startUiClock();
    setRightTab('cards');
    const pWrap = document.getElementById('priceCanvasWrap');
    if (pWrap) resizeObserver.observe(pWrap);
    setupChartInteraction();

    const iList = document.getElementById('intelEventsList');
    if (iList) {
      // Stream redesign (Phase B): clicking anywhere on an event row
      // expands / collapses it; the "<" chevron is only the visual cue.
      iList.addEventListener('click', (e) => {
        const retryBtn = e.target.closest('.intel-retry-btn');
        if (retryBtn) {
          e.stopPropagation();
          const retryId = retryBtn.getAttribute('data-retry-event-id') || '';
          if (retryId) {
            delete intelArticleCache[retryId];
            requestIntelArticle(retryId);
          }
          return;
        }
        const card = e.target.closest('.intel-event-card');
        if (card) toggleIntelEventCard(card);
      });
    }

    const pwdBadgeEl = document.getElementById('omniConsolePwd');
    if (pwdBadgeEl) {
      pwdBadgeEl.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          copyOmniPassword();
        }
      });
    }

    window.addEventListener('resize', triggerSmoothResize);

    if (typeof initIntelFilterControls === 'function') initIntelFilterControls();
    if (typeof initAdminPasswordStrength === 'function') initAdminPasswordStrength();
    if (typeof initScrollAreaFades === 'function') initScrollAreaFades();
    if (typeof initResetSlideConfirm === 'function') initResetSlideConfirm();
    if (typeof initCommandPalette === 'function') initCommandPalette();
    if (typeof initAmbientBackdrop === 'function') initAmbientBackdrop();

    setTimeout(pollBackend, 120);
    window.pollIntervalTimer = setInterval(pollBackend, 1000);
  });

  document.addEventListener('visibilitychange', () => {
    if (document.body) {
      document.body.classList.toggle('window-hidden', document.hidden);
    }
    if (typeof syncAmbientShaderMotion === 'function') syncAmbientShaderMotion();
    if (!document.hidden) {
      if (!isPolling) pollBackend();
      if (currentMainView === 'intel') pumpIntelArticlePreload();
    }
  });

  /* ==========================================================================
     SHUTDOWN & PROGRESS PERSISTENCE MODAL CONTROLLERS
     ========================================================================== */
  let shutdownCloseTimer = null;
  let resetCloseTimer = null;
  let installCancelCloseTimer = null;
  let wizardCloseConfirmCloseTimer = null;
  let wizardCloseTimer = null;

  function requestShutdown() {
    if (shutdownCloseTimer) { clearTimeout(shutdownCloseTimer); shutdownCloseTimer = null; }
    blurActiveFocus();
    const modal = document.getElementById('shutdownModal');
    if (modal) {
      modal.style.display = 'flex';
      modal.classList.remove('modal-closing');
      void modal.offsetWidth;
      modal.classList.add('modal-visible');
      syncAppShellInert();
    }
  }

  function closeShutdownModal() {
    const modal = document.getElementById('shutdownModal');
    if (modal) {
      modal.classList.remove('modal-visible');
      modal.classList.add('modal-closing');
      syncAppShellInert();
      if (shutdownCloseTimer) clearTimeout(shutdownCloseTimer);
      shutdownCloseTimer = setTimeout(() => {
        shutdownCloseTimer = null;
        if (!modal.classList.contains('modal-visible')) {
          modal.style.display = 'none';
          modal.classList.remove('modal-closing');
        }
      }, 1250);
    }
    if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.cancel_shutdown_prompt === 'function') {
      window.pywebview.api.cancel_shutdown_prompt().catch(() => { });
    }
  }

  function handleModalOverlayClick(e) {
    if (e && e.target && e.target.id === 'shutdownModal') {
      closeShutdownModal();
    }
  }

  function confirmShutdown(saveProgress) {
    const modal = document.getElementById('shutdownModal');
    if (modal) {
      modal.classList.remove('modal-visible');
      modal.style.display = 'none';
    }
    syncAppShellInert();

    // Cease all frontend timers/polling immediately to avoid queuing new IPC roundtrips during shutdown
    if (window.pollIntervalTimer) {
      clearInterval(window.pollIntervalTimer);
      window.pollIntervalTimer = null;
    }
    if (uiClockInterval) { clearInterval(uiClockInterval); uiClockInterval = null; }
    if (toastWatchdogInterval) { clearInterval(toastWatchdogInterval); toastWatchdogInterval = null; }
    if (splashLoop) { clearInterval(splashLoop); splashLoop = null; }
    if (splashSafetyTimer) { clearTimeout(splashSafetyTimer); splashSafetyTimer = null; }
    stopRuntimeInstallPoll();
    stopSaveLaunchPoll();
    if (typeof destroyAmbientBackdrop === 'function') destroyAmbientBackdrop();
    isPolling = true;

    if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.shutdown === 'function') {
      window.pywebview.api.shutdown(Boolean(saveProgress)).catch((err) => {
        console.error('Failed to trigger pywebview shutdown:', err);
      });
    } else {
      console.log('Shutdown triggered. saveProgress =', saveProgress);
    }
  }

  window.promptShutdownSave = function () {
    requestShutdown();
  };

  /* ==========================================================================
     GATEWAY SETUP WIZARD & CREDENTIALS CONTROLLER
     ========================================================================== */
  // Wizard & onboarding flags initialized at top of script

  function toggleKeyVisibility(inputId, btn) {
    const input = document.getElementById(inputId);
    if (!input) return;
    const isPass = input.type === 'password';
    input.type = isPass ? 'text' : 'password';
    if (btn) {
      btn.classList.toggle('active', isPass);
      btn.title = isPass ? 'Hide Key' : 'Show Key';
    }
  }

  function openSetupWizardModal(canDismiss = true) {
    if (wizardCloseTimer) { clearTimeout(wizardCloseTimer); wizardCloseTimer = null; }
    blurActiveFocus();
    if (!canDismiss) {
      clearSplashTimers();
      if (splashLoop) { clearInterval(splashLoop); splashLoop = null; }
      if (splashSafetyTimer) { clearTimeout(splashSafetyTimer); splashSafetyTimer = null; }
    }
    const openGen = ++wizardOpenGen;
    const modal = document.getElementById('setupWizardModal');
    const closeBtn = document.getElementById('btnWizardClose');
    if (closeBtn) {
      closeBtn.style.display = canDismiss ? 'flex' : 'none';
    }
    // Reset transient save progress, eye-toggle mask states & sensitive password fields on reopen
    updateSaveLaunchProgress({ status: 'idle', message: '', progress: null, phase: '' });
    ['keyGemini', 'keyAdminPassword', 'keyAdminPasswordConfirm'].forEach((id) => {
      const inp = document.getElementById(id);
      if (inp) inp.type = 'password';
    });
    if (modal) {
      modal.querySelectorAll('.setup-eye-btn.active').forEach((btn) => {
        btn.classList.remove('active');
        btn.title = 'Show Key';
      });
    }
    const keyGeminiInput = document.getElementById('keyGemini');
    const pwInput = document.getElementById('keyAdminPassword');
    const pwConfirm = document.getElementById('keyAdminPasswordConfirm');
    if (keyGeminiInput) keyGeminiInput.value = '';
    if (pwInput) pwInput.value = '';
    if (pwConfirm) pwConfirm.value = '';
    if (typeof updateAdminPasswordStrength === 'function') updateAdminPasswordStrength('');
    const curInst = window.__runtimeInstallStatus && window.__runtimeInstallStatus.status;
    if (curInst !== 'downloading-node' && curInst !== 'installing-omniroute') {
      setWizardBanner('');
    }
    if (modal) {
      modal.style.display = 'flex';
      modal.classList.remove('wizard-closing');
      void modal.offsetWidth; // Force layout reflow for CSS transition
      modal.classList.add('wizard-visible');
      isWizardOpen = true;
      syncAppShellInert();
    }

    // Pre-populate configured providers from bridge
    const provIdMap = {
      gemini: 'Gemini'
    };

    if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.get_setup_status === 'function') {
      window.pywebview.api.get_setup_status().then((res) => {
        if (openGen !== wizardOpenGen || !isWizardOpen) return;
        if (res && res.status === 'ok') {
          const configured = res.configured_providers || [];
          Object.entries(provIdMap).forEach(([pKey, domId]) => {
            const stEl = document.getElementById(`status${domId}`);
            if (stEl) {
              if (configured.includes(pKey)) {
                stEl.innerHTML = '<span class="setup-status-pill valid">Connected</span>';
              } else {
                stEl.innerHTML = '<span class="setup-status-pill neutral">Not added</span>';
              }
            }
          });

          // The backend never sends the password value: only whether a
          // custom password is configured. The badge always shows a mask
          // (item 7); the real password lives in ~/.omniroute/.env.
          const pwdEl = document.getElementById('omniConsolePwd');
          if (pwdEl) {
            const pwdSpan = pwdEl.querySelector('span') || pwdEl;
            pwdSpan.textContent = '********';
            pwdEl.title = res.omniroute_password_configured
              ? 'Custom admin password configured in ~/.omniroute/.env'
              : 'No admin password set - set one below to protect the gateway console';
          }

          if (typeof res.gateway_port === 'number') {
            window.__tradebotGatewayPort = res.gateway_port;
          }

          // Admin password card (item 10 A1): required on first run and for
          // installs still on the built-in default password; blank keeps the
          // existing password when one is already configured.
          window.__adminPasswordRequired = !!res.admin_password_required;
          const adminStatus = document.getElementById('statusAdminPassword');
          if (adminStatus) {
            adminStatus.innerHTML = res.omniroute_password_configured
              ? '<span class="setup-status-pill valid">Set</span>'
              : '<span class="setup-status-pill neutral">Not Set - Required</span>';
          }

          applyGatewayAvailability(res);
          updateRuntimeInstallBanner(res.runtime_install_status, true);
        }
      }).catch((e) => console.debug('get_setup_status err:', e));
    }
  }

  function closeSetupWizardModal() {
    wizardOpenGen += 1;
    isCheckingWizardClose = false;
    const keyGeminiInput = document.getElementById('keyGemini');
    const pwInput = document.getElementById('keyAdminPassword');
    const pwConfirm = document.getElementById('keyAdminPasswordConfirm');
    if (keyGeminiInput) keyGeminiInput.value = '';
    if (pwInput) pwInput.value = '';
    if (pwConfirm) pwConfirm.value = '';
    if (typeof updateAdminPasswordStrength === 'function') updateAdminPasswordStrength('');
    const modal = document.getElementById('setupWizardModal');
    if (modal) {
      modal.classList.remove('wizard-visible');
      modal.classList.add('wizard-closing');
      isWizardOpen = false;
      syncAppShellInert();
      if (wizardCloseTimer) clearTimeout(wizardCloseTimer);
      wizardCloseTimer = setTimeout(() => {
        wizardCloseTimer = null;
        if (!isWizardOpen) {
          modal.style.display = 'none';
          modal.classList.remove('wizard-closing');
        }
      }, 1400);
    }
    if (hasCompletedSetup) {
      if (document.body) document.body.classList.add('arena-ready');
      const appShell = document.querySelector('.app-shell');
      if (appShell) {
        appShell.style.opacity = '1';
      }
    }
  }

  function fallbackCopyText(text) {
    try {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.setAttribute('readonly', '');
      ta.style.position = 'fixed';
      ta.style.top = '-9999px';
      ta.style.left = '-9999px';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      const ok = document.execCommand('copy');
      document.body.removeChild(ta);
      return ok;
    } catch (e) {
      return false;
    }
  }

  let omniPwdRevealed = false;
  let omniPwdCachedValue = '';

  function syncOmniPwdDisplay() {
    const pwdBadge = document.getElementById('omniConsolePwd');
    const pwdText = document.getElementById('omniConsolePwdText');
    const eyeBtn = document.getElementById('btnToggleOmniPwd');
    if (pwdText && (!pwdBadge || !pwdBadge._copiedTimer)) {
      pwdText.textContent = (omniPwdRevealed && omniPwdCachedValue) ? omniPwdCachedValue : '********';
    }
    if (pwdBadge && !pwdBadge._copiedTimer) {
      pwdBadge.classList.toggle('pwd-revealed', Boolean(omniPwdRevealed && omniPwdCachedValue));
    }
    if (eyeBtn) {
      eyeBtn.classList.toggle('is-revealed', omniPwdRevealed);
      eyeBtn.setAttribute('aria-pressed', omniPwdRevealed ? 'true' : 'false');
      eyeBtn.setAttribute('aria-label', omniPwdRevealed ? 'Hide password' : 'Show password');
      eyeBtn.title = omniPwdRevealed ? 'Hide password' : 'Show password';
    }
  }

  function flashOmniPwdBadge(text, isSuccess) {
    const pwdBadge = document.getElementById('omniConsolePwd');
    const pwdText = document.getElementById('omniConsolePwdText');
    if (!pwdBadge) return;
    if (pwdBadge._copiedTimer) clearTimeout(pwdBadge._copiedTimer);
    if (pwdText) {
      pwdText.textContent = text;
    } else {
      pwdBadge.textContent = text;
    }
    pwdBadge.classList.remove('pwd-revealed');
    pwdBadge.classList.toggle('pwd-copied', Boolean(isSuccess));
    pwdBadge._copiedTimer = setTimeout(() => {
      pwdBadge._copiedTimer = undefined;
      pwdBadge.classList.remove('pwd-copied');
      syncOmniPwdDisplay();
    }, 2000);
  }

  function toggleOmniPasswordVisibility() {
    if (omniPwdRevealed) {
      omniPwdRevealed = false;
      omniPwdCachedValue = '';
      syncOmniPwdDisplay();
      return;
    }
    const onUnavailable = () => {
      omniPwdRevealed = false;
      omniPwdCachedValue = '';
      syncOmniPwdDisplay();
      flashOmniPwdBadge('not set', false);
    };
    if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.reveal_omniroute_password === 'function') {
      window.pywebview.api.reveal_omniroute_password().then((res) => {
        if (res && res.status === 'ok' && typeof res.password === 'string' && res.password.length > 0) {
          omniPwdCachedValue = res.password;
          omniPwdRevealed = true;
          syncOmniPwdDisplay();
        } else {
          onUnavailable();
        }
      }, onUnavailable);
      return;
    }
    onUnavailable();
  }

  function copyOmniPassword() {
    // The clipboard copy stays server-side via copy_omniroute_password:
    // clicking the badge copies the admin password and flashes "copied!"
    // on the badge itself, then restores either the masked or revealed text.
    const showEnvHint = () => {
      flashOmniPwdBadge('copy failed', false);
      if (typeof showChartToast === 'function') {
        showChartToast({ triggerReason: 'Console password saved', action: 'INFO' });
      }
    };
    if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.copy_omniroute_password === 'function') {
      window.pywebview.api.copy_omniroute_password().then((res) => {
        if (res && res.status === 'ok') {
          flashOmniPwdBadge('copied!', true);
          if (typeof showChartToast === 'function') showChartToast({ triggerReason: 'copied!', action: 'COPY' });
        } else {
          showEnvHint();
        }
      }, showEnvHint);
      return;
    }
    showEnvHint();
  }

  window.copyOmniPassword = copyOmniPassword;
  window.toggleOmniPasswordVisibility = toggleOmniPasswordVisibility;

  function handleWizardOverlayClick(e) {
    if (e && e.target && e.target.id === 'setupWizardModal') {
      const closeBtn = document.getElementById('btnWizardClose');
      if (closeBtn && closeBtn.style.display !== 'none') {
        requestCloseSetupWizardModal();
      }
    }
  }

  // Wizard dismiss paths (X button / overlay click / Escape) must confirm
  // first. While an install is running the cancel-install prompt warns
  // that closing would interrupt the download; otherwise the dedicated
  // wizard-close prompt warns that the typed API key / password will not
  // be saved. Save & Skip close the wizard directly and never warn --
  // the install keeps running behind them.
  function requestCloseSetupWizardModal() {
    if (isSavingGateway || !isWizardOpen || isCheckingWizardClose) return;
    const closeBtn = document.getElementById('btnWizardClose');
    if (closeBtn && closeBtn.style.display === 'none') return;
    const myGen = wizardOpenGen;
    const decide = (st) => {
      if (myGen !== wizardOpenGen || !isWizardOpen || isSavingGateway) return;
      if (st === 'downloading-node' || st === 'installing-omniroute') {
        openInstallCancelConfirm();
      } else {
        openWizardCloseConfirm();
      }
    };
    const cached = window.__runtimeInstallStatus;
    if (cached && (cached.status === 'downloading-node' || cached.status === 'installing-omniroute')) {
      decide(cached.status);
      return;
    }
    // Fresh lock-only check (no TCP/HTTP/filesystem I/O): avoids stalling on close.
    if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.get_runtime_install_status === 'function') {
      isCheckingWizardClose = true;
      window.pywebview.api.get_runtime_install_status().then((res) => {
        const s = res ? res.status : null;
        decide(s);
      }).catch(() => decide(cached ? cached.status : null))
        .finally(() => { isCheckingWizardClose = false; });
    } else if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.get_setup_status === 'function') {
      isCheckingWizardClose = true;
      window.pywebview.api.get_setup_status().then((res) => {
        const s = (res && res.runtime_install_status) ? res.runtime_install_status.status : null;
        decide(s);
      }).catch(() => decide(cached ? cached.status : null))
        .finally(() => { isCheckingWizardClose = false; });
    } else {
      decide(cached ? cached.status : null);
    }
  }

  function openInstallCancelConfirm() {
    if (installCancelCloseTimer) { clearTimeout(installCancelCloseTimer); installCancelCloseTimer = null; }
    blurActiveFocus();
    const modal = document.getElementById('installCancelConfirmModal');
    if (modal) {
      modal.style.display = 'flex';
      modal.classList.remove('modal-closing');
      void modal.offsetWidth;
      modal.classList.add('modal-visible');
      syncAppShellInert();
    }
  }

  function closeInstallCancelConfirm() {
    const modal = document.getElementById('installCancelConfirmModal');
    if (modal) {
      modal.classList.remove('modal-visible');
      modal.classList.add('modal-closing');
      syncAppShellInert();
      if (installCancelCloseTimer) clearTimeout(installCancelCloseTimer);
      installCancelCloseTimer = setTimeout(() => {
        installCancelCloseTimer = null;
        if (!modal.classList.contains('modal-visible')) {
          modal.style.display = 'none';
          modal.classList.remove('modal-closing');
        }
      }, 1250);
    }
  }

  function handleInstallCancelOverlayClick(e) {
    if (e && e.target && e.target.id === 'installCancelConfirmModal') {
      closeInstallCancelConfirm();
    }
  }

  async function confirmCancelInstallAndClose() {
    stopRuntimeInstallPoll();
    try {
      if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.cancel_gateway_runtime_install === 'function') {
        await window.pywebview.api.cancel_gateway_runtime_install();
      }
    } catch (err) {
      console.debug('cancel install err:', err);
    }
    stopRuntimeInstallPoll();
    window.__runtimeInstallStatus = { status: 'cancelled', message: '', progress: null, phase: '' };
    const btn = document.getElementById('btnInstallGatewayRuntime');
    if (btn) btn.disabled = false;
    const progWrap = document.getElementById('setupInstallProgressWrap');
    const fill = document.getElementById('setupInstallProgressFill');
    if (progWrap) progWrap.classList.remove('is-open');
    if (fill) {
      fill.classList.remove('indeterminate');
      fill.style.width = '0%';
    }
    closeInstallCancelConfirm();
    closeSetupWizardModal();
  }

  // Wizard-close confirmation (no install running): a dedicated dialog,
  // separate from the shutdown prompt and the cancel-install prompt. It
  // warns that the API key / password typed in the wizard will not be
  // saved. Confirming closes the wizard; dismissing stays on the wizard.
  function openWizardCloseConfirm() {
    if (wizardCloseConfirmCloseTimer) { clearTimeout(wizardCloseConfirmCloseTimer); wizardCloseConfirmCloseTimer = null; }
    blurActiveFocus();
    const modal = document.getElementById('wizardCloseConfirmModal');
    if (modal) {
      modal.style.display = 'flex';
      modal.classList.remove('modal-closing');
      void modal.offsetWidth;
      modal.classList.add('modal-visible');
      syncAppShellInert();
    }
  }

  function closeWizardCloseConfirm() {
    const modal = document.getElementById('wizardCloseConfirmModal');
    if (modal) {
      modal.classList.remove('modal-visible');
      modal.classList.add('modal-closing');
      syncAppShellInert();
      if (wizardCloseConfirmCloseTimer) clearTimeout(wizardCloseConfirmCloseTimer);
      wizardCloseConfirmCloseTimer = setTimeout(() => {
        wizardCloseConfirmCloseTimer = null;
        if (!modal.classList.contains('modal-visible')) {
          modal.style.display = 'none';
          modal.classList.remove('modal-closing');
        }
      }, 1250);
    }
  }

  function handleWizardCloseOverlayClick(e) {
    if (e && e.target && e.target.id === 'wizardCloseConfirmModal') {
      closeWizardCloseConfirm();
    }
  }

  function confirmCloseWizardWithoutSaving() {
    closeWizardCloseConfirm();
    closeSetupWizardModal();
  }

  function setWizardBanner(message, type = 'info') {
    const b = document.getElementById('setupWizardStatusBanner');
    const wrap = document.getElementById('setupWizardBannerWrap');
    if (!b) return;
    if (!message) {
      if (wrap) wrap.classList.remove('is-open');
      b.textContent = '';
      return;
    }
    b.className = `setup-wizard-banner ${type}`;
    b.textContent = message;
    if (wrap) wrap.classList.add('is-open');
  }

  let runtimeInstallPollTimer = null;
  let runtimeInstallPollGen = 0;
  let runtimeInstallPollInFlight = false;
  let saveLaunchPollTimer = null;
  let saveLaunchPollGen = 0;
  let saveLaunchPollInFlight = false;

  function stopRuntimeInstallPoll() {
    runtimeInstallPollGen += 1;
    runtimeInstallPollInFlight = false;
    if (runtimeInstallPollTimer) { clearInterval(runtimeInstallPollTimer); runtimeInstallPollTimer = null; }
  }

  function ensureRuntimeInstallPoll() {
    if (runtimeInstallPollTimer) return;
    const pollGen = ++runtimeInstallPollGen;
    runtimeInstallPollTimer = setInterval(() => {
      if (runtimeInstallPollInFlight || pollGen !== runtimeInstallPollGen) return;
      if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.get_setup_status === 'function') {
        runtimeInstallPollInFlight = true;
        window.pywebview.api.get_setup_status().then((r) => {
          if (pollGen !== runtimeInstallPollGen) return;
          if (r && r.status === 'ok') {
            applyGatewayAvailability(r);
            updateRuntimeInstallBanner(r.runtime_install_status);
          }
        }).catch((e) => console.debug('install poll err:', e))
          .finally(() => { runtimeInstallPollInFlight = false; });
      }
    }, 5000);
  }

  // Gateway availability (item 10 A4): display live detected environment
  // status (Node.js & OmniRoute) and smoothly expand/collapse the missing
  // component note + one-click install button to fit content with zero gap.
  function applyGatewayAvailability(res) {
    if (!res) return;
    if (typeof res.gateway_port === 'number') {
      window.__tradebotGatewayPort = res.gateway_port;
    }
    const nodeOk = !!res.node_available;
    const omniOk = !!res.omniroute_installed;

    const nodePill = document.getElementById('envNodePill');
    if (nodePill) {
      nodePill.className = `setup-status-pill ${nodeOk ? 'valid' : 'neutral'}`;
      nodePill.textContent = nodeOk ? 'Detected' : 'Not installed';
      nodePill.title = nodeOk
        ? 'Node.js is already detected on this machine and will not be re-downloaded'
        : 'Node.js will be downloaded automatically if needed';
    }
    const omniPill = document.getElementById('envOmniRoutePill');
    if (omniPill) {
      omniPill.className = `setup-status-pill ${omniOk ? 'valid' : 'neutral'}`;
      omniPill.textContent = omniOk ? 'Installed' : 'Not installed';
      omniPill.title = omniOk
        ? 'OmniRoute is already installed on this machine and will not be re-downloaded'
        : 'OmniRoute needs a one-time installation (~2.6 GB)';
    }

    const actionWrap = document.getElementById('gatewayRuntimeActionWrap');
    const gwNote = document.getElementById('gatewayUnavailableNote');
    const gwBtn = document.getElementById('btnInstallGatewayRuntime');
    const showAction = !!res.gateway_unavailable_reason;
    if (gwNote) {
      gwNote.textContent = showAction
        ? (res.gateway_unavailable_reason + ' The arena still works in Pure Math mode meanwhile.')
        : '';
    }
    if (gwBtn) {
      const btnSpan = gwBtn.querySelector('span') || gwBtn;
      if (!nodeOk && !omniOk) {
        btnSpan.textContent = 'Install Node.js & OmniRoute';
      } else if (nodeOk && !omniOk) {
        btnSpan.textContent = 'Install OmniRoute';
      } else if (!nodeOk && omniOk) {
        btnSpan.textContent = 'Install Node.js';
      } else {
        btnSpan.textContent = 'Install Node.js & OmniRoute';
      }
    }
    if (actionWrap) {
      actionWrap.classList.toggle('is-open', showAction);
    }
  }

  function updateRuntimeInstallBanner(statusObj, fromOpen = false) {
    if (!statusObj) return;
    const st = statusObj.status || 'idle';
    const msg = statusObj.message || '';
    const pct = (typeof statusObj.progress === 'number') ? statusObj.progress : null;
    // Latest install state, so the close warning can decide without
    // waiting for the next poll (the poll runs every 5 s).
    window.__runtimeInstallStatus = { status: st, message: msg, progress: pct, phase: statusObj.phase || '' };
    const progWrap = document.getElementById('setupInstallProgressWrap');
    const prog = document.getElementById('setupInstallProgress');
    const fill = document.getElementById('setupInstallProgressFill');
    const showBar = (st === 'downloading-node' || st === 'installing-omniroute');
    if (progWrap) progWrap.classList.toggle('is-open', showBar);
    if (prog) {
      if (showBar && fill) {
        if (pct !== null) {
          fill.classList.remove('indeterminate');
          fill.style.width = Math.max(0, Math.min(100, pct)) + '%';
          prog.setAttribute('aria-valuenow', String(pct));
        } else {
          // No trustworthy percent available (e.g. download without
          // Content-Length): show an honest indeterminate bar, never a
          // fabricated number.
          fill.classList.add('indeterminate');
          fill.style.width = '40%';
          prog.removeAttribute('aria-valuenow');
        }
      } else if (!showBar && fill) {
        fill.classList.remove('indeterminate');
      }
    }
    if (showBar) {
      const btn = document.getElementById('btnInstallGatewayRuntime');
      if (btn) btn.disabled = true;
      ensureRuntimeInstallPoll();
    }
    if (st === 'idle') return;
    if (fromOpen && (st === 'done' || st === 'failed' || st === 'cancelled')) {
      stopRuntimeInstallPoll();
      const btn = document.getElementById('btnInstallGatewayRuntime');
      if (btn) btn.disabled = false;
      return;
    }
    if (st === 'done') {
      setWizardBanner(msg || 'OmniRoute installed.', 'success');
      stopRuntimeInstallPoll();
      refreshGatewayAvailability();
    } else if (st === 'failed') {
      setWizardBanner(msg || 'Installation failed.', 'error');
      stopRuntimeInstallPoll();
      const btn = document.getElementById('btnInstallGatewayRuntime');
      if (btn) btn.disabled = false;
    } else if (st === 'cancelled') {
      setWizardBanner(msg || 'Installation cancelled.', 'info');
      stopRuntimeInstallPoll();
      const btn = document.getElementById('btnInstallGatewayRuntime');
      if (btn) btn.disabled = false;
      refreshGatewayAvailability();
    } else {
      // In progress: append the percent when the backend has one and
      // the message does not already embed it (e.g. OmniRoute ETA messages).
      const bannerText = pct !== null
        ? (new RegExp('(?:^|\\D)' + pct + '%').test(msg)
          ? msg
          : ((msg || 'Installing...') + ' ' + pct + '%'))
        : (msg || 'Installing...');
      setWizardBanner(bannerText, 'info');
    }
  }

  function stopSaveLaunchPoll() {
    saveLaunchPollGen += 1;
    saveLaunchPollInFlight = false;
    if (saveLaunchPollTimer) { clearInterval(saveLaunchPollTimer); saveLaunchPollTimer = null; }
  }

  // Save & Launch progress: collapsible bar (determinate by stage milestone;
  // 100% only when the save actually finished). Collapses to 0px when idle
  // or failed so surrounding elements resize and shift cleanly.
  function updateSaveLaunchProgress(statusObj) {
    if (!statusObj) return;
    const st = statusObj.status || 'idle';
    const msg = statusObj.message || '';
    const pct = (typeof statusObj.progress === 'number') ? statusObj.progress : null;
    const progWrap = document.getElementById('setupSaveProgressWrap');
    const prog = document.getElementById('setupSaveProgress');
    const fill = document.getElementById('setupSaveProgressFill');
    const inProgress = (st === 'saving-password' || st === 'syncing-keys' ||
      st === 'saving-config' || st === 'restarting-gateway' ||
      st === 'connecting-gateway' || st === 'starting-gateway' ||
      st === 'starting-engine');
    const showBar = inProgress || st === 'done';
    if (progWrap) progWrap.classList.toggle('is-open', showBar);
    if (prog) {
      if (showBar && fill && pct !== null) {
        fill.style.width = Math.max(0, Math.min(100, pct)) + '%';
        prog.setAttribute('aria-valuenow', String(pct));
      } else if (showBar && fill) {
        prog.removeAttribute('aria-valuenow');
      } else if (!showBar && fill) {
        fill.style.width = '0%';
        prog.removeAttribute('aria-valuenow');
      }
    }
    if (st === 'done' || st === 'failed' || st === 'idle') return;
    if (inProgress) {
      setWizardBanner(pct !== null ? (msg + ' ' + pct + '%') : (msg || 'Saving...'), 'info');
    }
  }

  function refreshGatewayAvailability() {
    if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.get_setup_status === 'function') {
      window.pywebview.api.get_setup_status().then((res) => {
        if (res && res.status === 'ok') applyGatewayAvailability(res);
      }).catch((e) => console.debug('refresh gateway availability err:', e));
    }
  }

  async function installGatewayRuntime() {
    const btn = document.getElementById('btnInstallGatewayRuntime');
    if (btn) btn.disabled = true;
    setWizardBanner('Starting installation in the background...', 'info');
    try {
      if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.install_gateway_runtime === 'function') {
        const res = await window.pywebview.api.install_gateway_runtime();
        if (res && res.ok) {
          setWizardBanner(res.message || 'Installation started in the background.', 'info');
          stopRuntimeInstallPoll();
          ensureRuntimeInstallPoll();
          if (typeof window.pywebview.api.get_runtime_install_status === 'function') {
            window.pywebview.api.get_runtime_install_status()
              .then((st) => { if (st) updateRuntimeInstallBanner(st); })
              .catch(() => { });
          }
        } else {
          setWizardBanner((res && res.message) ? res.message : 'Could not start the installation.', 'error');
          if (btn) btn.disabled = false;
        }
      }
    } catch (err) {
      setWizardBanner(`Encountered error: ${err}`, 'error');
      if (btn) btn.disabled = false;
    }
  }

  async function testProviderKey(provider) {
    const provIdMap = {
      gemini: 'Gemini'
    };
    const normKey = (provider || '').toLowerCase();
    const cap = provIdMap[normKey] || (provider.charAt(0).toUpperCase() + provider.slice(1));
    const input = document.getElementById(`key${cap}`);
    const stEl = document.getElementById(`status${cap}`);
    const btn = document.getElementById(`btnTest${cap}`);
    const rawKey = input ? input.value.trim() : '';

    if (!rawKey) {
      if (stEl) stEl.innerHTML = '<span class="setup-status-pill error">Please enter an API key first</span>';
      return;
    }

    if (stEl) stEl.innerHTML = '<span class="setup-status-pill verifying">Verifying with provider...</span>';
    if (btn) btn.disabled = true;
    const myGen = wizardOpenGen;

    try {
      if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.test_api_key === 'function') {
        const res = await window.pywebview.api.test_api_key(provider, rawKey);
        if (myGen !== wizardOpenGen) return;
        if (res && res.ok) {
          if (stEl) stEl.innerHTML = '<span class="setup-status-pill valid">Connected</span>';
          setWizardBanner('');
        } else {
          const msg = (res && res.message) ? res.message : 'Verification failed';
          if (stEl) stEl.innerHTML = '<span class="setup-status-pill error">Check failed</span>';
          setWizardBanner(msg, 'error');
        }
      } else {
        setTimeout(() => {
          if (myGen !== wizardOpenGen) return;
          if (stEl) stEl.innerHTML = '<span class="setup-status-pill valid">&#x2713; Format Accepted (Preview)</span>';
          setWizardBanner('');
        }, 400);
      }
    } catch (err) {
      if (myGen !== wizardOpenGen) return;
      if (stEl) stEl.innerHTML = '<span class="setup-status-pill error">Check failed</span>';
      setWizardBanner('Network error', 'error');
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  async function saveAndLaunchGateway() {
    if (isSavingGateway) return;
    const saveBtn = document.getElementById('btnSaveAndLaunch');

    const keys = {
      gemini: (document.getElementById('keyGemini')?.value || '').trim(),
    };

    // Admin password (item 10 A1): required when the backend says so, or
    // whenever the user typed one (changing it). Blank keeps the existing
    // password when one is already configured.
    const adminPw = (document.getElementById('keyAdminPassword')?.value || '');
    const adminPwConfirm = (document.getElementById('keyAdminPasswordConfirm')?.value || '');
    if (window.__adminPasswordRequired || adminPw || adminPwConfirm) {
      if (adminPw.length < 8) {
        setWizardBanner('Admin password must be at least 8 characters.', 'error');
        return;
      }
      if (adminPw !== adminPwConfirm) {
        setWizardBanner('Admin password and confirmation do not match.', 'error');
        return;
      }
    }

    isSavingGateway = true;
    if (saveBtn) {
      saveBtn.disabled = true;
      saveBtn.innerHTML = '<span>Saving &amp; Launching...</span>';
    }
    setWizardBanner('Connecting AI services...', 'info');

    // Save progress: show the bar immediately, then poll the backend
    // stage (~500 ms) while the synchronous bridge call runs, so the
    // user sees which step is running. The bar only reaches 100% when
    // the call actually returns ok.
    updateSaveLaunchProgress(
      adminPw
        ? { status: 'saving-password', message: 'Saving password...', progress: 0, phase: 'password' }
        : { status: 'syncing-keys', message: 'Connecting AI services...', progress: 0, phase: 'keys' }
    );
    if (saveLaunchPollTimer) clearInterval(saveLaunchPollTimer);
    const pollGen = ++saveLaunchPollGen;
    saveLaunchPollInFlight = false;
    saveLaunchPollTimer = setInterval(() => {
      if (saveLaunchPollInFlight || pollGen !== saveLaunchPollGen) return;
      if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.get_save_launch_status === 'function') {
        saveLaunchPollInFlight = true;
        window.pywebview.api.get_save_launch_status().then((r) => {
          if (r && pollGen === saveLaunchPollGen) updateSaveLaunchProgress(r);
        }).catch((e) => console.debug('save launch poll err:', e))
          .finally(() => { saveLaunchPollInFlight = false; });
      }
    }, 500);

    try {
      if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.save_and_launch_gateway === 'function') {
        const res = await window.pywebview.api.save_and_launch_gateway(keys, adminPw || null);
        if (res && res.ok) {
          stopSaveLaunchPoll();
          updateSaveLaunchProgress({ status: 'done', message: res.message || 'Credentials saved successfully!', progress: 100, phase: '' });
          hasCompletedSetup = true;
          setWizardBanner(res.message || 'Credentials saved successfully!', 'success');
          setTimeout(() => {
            closeSetupWizardModal();
            if (!splashCompleted) {
              // No jump-start: the splash begins at its real starting
              // point and advances by real milestones.
              startSplashSequence(false);
            } else {
              if (typeof showChartToast === 'function') {
                const livePrice = (latestState && latestState.quote && latestState.quote.price)
                  || (latestState && latestState.candles && latestState.candles.length > 0 ? latestState.candles[latestState.candles.length - 1].c : null);
                showChartToast({
                  action: 'READY',
                  symbol: 'ETH/USD',
                  price: livePrice,
                  triggerReason: 'AI services connected',
                  timestamp: Date.now()
                });
              }
            }
          }, 400);
        } else {
          stopSaveLaunchPoll();
          updateSaveLaunchProgress({ status: 'failed', message: (res && res.message) || 'Failed to launch gateway', progress: null, phase: '' });
          setWizardBanner((res && res.message) ? res.message : 'Failed to launch gateway', 'error');
        }
      } else {
        stopSaveLaunchPoll();
        updateSaveLaunchProgress({ status: 'done', message: 'Configured in mock mode. Launching arena...', progress: 100, phase: '' });
        hasCompletedSetup = true;
        setWizardBanner('Configured in mock mode. Launching arena...', 'success');
        setTimeout(() => {
          closeSetupWizardModal();
          if (!splashCompleted) {
            startSplashSequence(false);
          }
        }, 400);
      }
    } catch (err) {
      stopSaveLaunchPoll();
      updateSaveLaunchProgress({ status: 'failed', message: `Encountered error: ${err}`, progress: null, phase: '' });
      setWizardBanner(`Encountered error: ${err}`, 'error');
    } finally {
      isSavingGateway = false;
      stopSaveLaunchPoll();
      if (saveBtn) {
        saveBtn.disabled = false;
        saveBtn.innerHTML = '<span>Save &amp; Launch Arena</span>';
      }
    }
  }

  function checkOnboardingBoot() {
    if (hasCheckedOnboarding) return;
    hasCheckedOnboarding = true;

    if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.get_setup_status === 'function') {
      window.pywebview.api.get_setup_status().then((res) => {
        if (res && res.status === 'ok') {
          if ((!res.onboarding_completed && !res.skip_ai_mode) || res.admin_password_required) {
            openSetupWizardModal(false);
          }
        }
      }).catch((e) => console.debug('Initial onboarding check failed:', e));
    }
  }

  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      // Dismiss topmost visible modal strictly in descending z-index order:
      // #commandPaletteModal (10006) > #shutdownModal (10005) > #wizardCloseConfirmModal (10003) >
      // #installCancelConfirmModal (10002) > #setupWizardModal (10001) > #resetConfirmModal (9999)
      const cmdModal = document.getElementById('commandPaletteModal');
      if (cmdModal && cmdModal.classList.contains('modal-visible')) {
        closeCommandPalette();
        return;
      }
      const shutdownModal = document.getElementById('shutdownModal');
      if (shutdownModal && shutdownModal.classList.contains('modal-visible')) {
        closeShutdownModal();
        return;
      }
      const wizardCloseModal = document.getElementById('wizardCloseConfirmModal');
      if (wizardCloseModal && wizardCloseModal.classList.contains('modal-visible')) {
        closeWizardCloseConfirm();
        return;
      }
      const cancelModal = document.getElementById('installCancelConfirmModal');
      if (cancelModal && cancelModal.classList.contains('modal-visible')) {
        closeInstallCancelConfirm();
        return;
      }
      if (isWizardOpen) {
        const closeBtn = document.getElementById('btnWizardClose');
        if (closeBtn && closeBtn.style.display !== 'none') {
          requestCloseSetupWizardModal();
        }
        return;
      }
      const resetModal = document.getElementById('resetConfirmModal');
      if (resetModal && resetModal.classList.contains('modal-visible')) {
        closeResetModal();
        return;
      }
    }
  });

  /* ==========================================================================
     RESET CONFIRMATION MODAL CONTROLLERS
     ========================================================================== */
  function requestResetArena() {
    if (resetCloseTimer) { clearTimeout(resetCloseTimer); resetCloseTimer = null; }
    blurActiveFocus();
    if (typeof resetSlideConfirmState === 'function') resetSlideConfirmState();
    const modal = document.getElementById('resetConfirmModal');
    if (modal) {
      modal.style.display = 'flex';
      modal.classList.remove('modal-closing');
      void modal.offsetWidth;
      modal.classList.add('modal-visible');
      syncAppShellInert();
    }
  }

  function closeResetModal() {
    const modal = document.getElementById('resetConfirmModal');
    if (modal) {
      modal.classList.remove('modal-visible');
      modal.classList.add('modal-closing');
      syncAppShellInert();
      if (resetCloseTimer) clearTimeout(resetCloseTimer);
      resetCloseTimer = setTimeout(() => {
        resetCloseTimer = null;
        if (!modal.classList.contains('modal-visible')) {
          modal.style.display = 'none';
          modal.classList.remove('modal-closing');
          if (typeof resetSlideConfirmState === 'function') resetSlideConfirmState();
        }
      }, 1250);
    }
  }

  function handleResetOverlayClick(e) {
    if (e && e.target && e.target.id === 'resetConfirmModal') {
      closeResetModal();
    }
  }

  function confirmResetArena() {
    closeResetModal();
    resetArena();
  }

  /* ==========================================================================
     PHASE 3-4: SEARCH/CHIPS, SCROLL FADES, PASSWORD STRENGTH, SLIDE CONFIRM,
     COMMAND PALETTE, AND HORIZONX SILVER STREAM + GRAINIENT BACKDROP
     ========================================================================== */

  function initIntelFilterControls() {
    const searchInput = document.getElementById('intelSearchInput');
    const clearBtn = document.getElementById('btnIntelSearchClear');
    if (searchInput) {
      searchInput.addEventListener('input', () => {
        intelSearchQuery = String(searchInput.value || '').trim().toLowerCase();
        const hasQuery = intelSearchQuery.length > 0;
        if (clearBtn) clearBtn.classList.toggle('visible', hasQuery);
        if (latestState) renderIntelHub(latestState);
      });
      searchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
          e.stopPropagation();
          if (intelSearchQuery) {
            clearIntelSearch();
          } else {
            toggleIntelSearch(false);
          }
        }
      });
    }
  }

  function updateAdminPasswordStrength(rawValue) {
    const wrap = document.getElementById('adminPwdStrengthWrap');
    const bar = document.getElementById('adminPwdStrengthBar');
    const txt = document.getElementById('adminPwdStrengthText');
    if (!wrap || !txt) return;
    if (bar && !bar._initialized) bar._initialized = true;

    const val = String(rawValue == null ? '' : rawValue);
    let level = 0;
    let label = 'Min 8 chars';
    if (val.length > 0 && val.length < 8) {
      level = 1;
      label = `${8 - val.length} more chars`;
    } else if (val.length >= 8) {
      let score = 1;
      if (/[a-z]/.test(val) && /[A-Z]/.test(val)) score += 1;
      if (/\d/.test(val)) score += 1;
      if (/[^A-Za-z0-9]/.test(val) || val.length >= 14) score += 1;
      level = Math.min(4, Math.max(1, score));
      const labels = ['', 'Weak', 'Fair', 'Good', 'Strong'];
      label = labels[level] || 'Fair';
    }
    wrap.setAttribute('data-level', String(level));
    if (txt.textContent !== label) txt.textContent = label;
  }

  function initAdminPasswordStrength() {
    const pwInput = document.getElementById('keyAdminPassword');
    if (!pwInput) return;
    pwInput.addEventListener('input', () => {
      updateAdminPasswordStrength(pwInput.value || '');
    });
    updateAdminPasswordStrength(pwInput.value || '');
  }

  function updateScrollAreaFades(el) {
    if (!el) return;
    const maxScroll = Math.max(0, el.scrollHeight - el.clientHeight);
    const top = el.scrollTop || 0;
    const hasTop = top > 4;
    const hasBottom = (maxScroll - top) > 4;
    el.classList.toggle('has-scroll-top', hasTop);
    el.classList.toggle('has-scroll-bottom', hasBottom);
  }

  function refreshScrollAreaFades() {
    document.querySelectorAll('.scroll-area-faded').forEach(updateScrollAreaFades);
  }

  function initScrollAreaFades() {
    const els = document.querySelectorAll('.scroll-area-faded');
    const ro = typeof ResizeObserver === 'function'
      ? new ResizeObserver((entries) => {
          entries.forEach((entry) => updateScrollAreaFades(entry.target));
        })
      : null;
    els.forEach((el) => {
      el.addEventListener('scroll', () => updateScrollAreaFades(el), { passive: true });
      if (ro) ro.observe(el);
      updateScrollAreaFades(el);
    });
  }

  function resetSlideConfirmState() {
    const track = document.getElementById('resetSlideTrack');
    const fill = document.getElementById('resetSlideFill');
    const thumb = document.getElementById('resetSlideThumb');
    const label = document.getElementById('resetSlideLabel');
    if (!track || !fill || !thumb || !label) return;
    track._slideCommitted = false;
    track._dragging = false;
    track.classList.remove('is-dragging', 'is-committed');
    track.setAttribute('aria-valuenow', '0');
    thumb.style.transform = '';
    fill.style.width = '0px';
    label.style.opacity = '1';
    label.textContent = 'Slide to Reset Arena';
  }

  function initResetSlideConfirm() {
    const track = document.getElementById('resetSlideTrack');
    const fill = document.getElementById('resetSlideFill');
    const thumb = document.getElementById('resetSlideThumb');
    const label = document.getElementById('resetSlideLabel');
    if (!track || !fill || !thumb || !label) return;

    const getBounds = () => {
      const tw = track.clientWidth || 320;
      const hw = thumb.offsetWidth || 32;
      const pad = 3;
      return { maxOffset: Math.max(1, tw - hw - pad * 2), pad, hw };
    };

    const renderRatio = (ratio) => {
      const clamped = Math.max(0, Math.min(1, ratio));
      const { maxOffset, pad, hw } = getBounds();
      const x = clamped * maxOffset;
      thumb.style.transform = `translateX(${x.toFixed(1)}px)`;
      fill.style.width = `${(x + hw * 0.5 + pad).toFixed(1)}px`;
      label.style.opacity = String(Math.max(0.15, 1 - clamped * 1.15));
      track.setAttribute('aria-valuenow', String(Math.round(clamped * 100)));
      return clamped;
    };

    const commitSlide = () => {
      if (track._slideCommitted) return;
      track._slideCommitted = true;
      track._dragging = false;
      track.classList.remove('is-dragging');
      track.classList.add('is-committed');
      renderRatio(1);
      label.style.opacity = '1';
      label.textContent = 'Resetting Arena...';
      setTimeout(() => {
        confirmResetArena();
      }, 140);
    };

    track.addEventListener('pointerdown', (e) => {
      if (track._slideCommitted || e.button !== 0) return;
      track._dragging = true;
      track._startX = e.clientX;
      track.classList.add('is-dragging');
      if (typeof track.setPointerCapture === 'function') {
        try { track.setPointerCapture(e.pointerId); } catch (_) { }
      }
      const rect = track.getBoundingClientRect();
      const { maxOffset, hw } = getBounds();
      const rel = e.clientX - rect.left - hw * 0.5 - 3;
      renderRatio(rel / maxOffset);
    });

    track.addEventListener('pointermove', (e) => {
      if (!track._dragging || track._slideCommitted) return;
      const rect = track.getBoundingClientRect();
      const { maxOffset, hw } = getBounds();
      const rel = e.clientX - rect.left - hw * 0.5 - 3;
      const ratio = renderRatio(rel / maxOffset);
      if (ratio >= 0.85) {
        commitSlide();
      }
    });

    const releaseSlide = () => {
      if (!track._dragging || track._slideCommitted) return;
      track._dragging = false;
      track.classList.remove('is-dragging');
      const nowPct = Number(track.getAttribute('aria-valuenow') || 0) / 100;
      if (nowPct >= 0.85) {
        commitSlide();
      } else {
        resetSlideConfirmState();
      }
    };

    track.addEventListener('pointerup', releaseSlide);
    track.addEventListener('pointercancel', releaseSlide);
    track.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === 'ArrowRight') {
        e.preventDefault();
        commitSlide();
      }
    });
  }

  let cmdPaletteMode = 'commands';
  let cmdPaletteSelectedIdx = 0;
  let cmdPaletteCloseTimer = null;

  function getCommandPaletteItems() {
    const isPaused = Boolean(latestState && latestState.paused);
    const modeLabel = backdropMode === 'shader'
      ? 'Shader (HorizonX)'
      : (backdropMode === 'grainient' ? 'Grainient Silk' : 'Minimal Obsidian');
    return [
      { id: 'arena', group: 'Navigation', title: 'Switch to Trading Arena', sub: 'Primary live chart, orderflow & strategy matrix', kbd: '1', run: () => switchMainView('arena') },
      { id: 'intel', group: 'Navigation', title: 'Switch to Market Intelligence Hub', sub: 'AI news digest, regime commander & curated events', kbd: '2', run: () => switchMainView('intel') },
      { id: 'pause', group: 'Trading Control', title: isPaused ? 'Resume Live Feed' : 'Pause Live Feed', sub: 'Toggle real-time price ticks & strategy simulation', kbd: 'Space', run: () => togglePause() },
      { id: 'evolve', group: 'Trading Control', title: 'Trigger Evolution Now', sub: 'Run tournament selection & genome crossover', kbd: 'E', run: () => triggerEvolution() },
      { id: 'scale', group: 'Chart', title: 'Toggle Chart Scale Mode (Focus / Full)', sub: 'Zoom on candle range or include distant brackets', kbd: 'F', run: () => setScaleMode(scaleMode === 'auto' ? 'full' : 'auto') },
      { id: 'refresh_intel', group: 'Intelligence', title: 'Refresh News Analysis', sub: 'Synthesize latest multi-domain macro digest', kbd: '', run: () => requestAiIntelDigest() },
      { id: 'console', group: 'Intelligence', title: 'Launch OmniRoute Console', sub: 'Open gateway admin console in browser', kbd: '', run: () => openOmniRouteConsole() },
      { id: 'backdrop', group: 'Appearance', title: `Cycle Backdrop Mode (${modeLabel})`, sub: 'Switch between HorizonX WebGL Shader, Grainient WebP, and Minimal Obsidian', kbd: '', run: () => cycleBackdropMode() },
      { id: 'settings', group: 'System', title: 'Open AI Services Setup', sub: 'Configure Gemini API key & gateway credentials', kbd: '', run: () => openSetupWizardModal(true) },
      { id: 'fullscreen', group: 'System', title: 'Toggle Fullscreen', sub: 'Expand or restore desktop window', kbd: 'F11', run: () => toggleFullscreen() },
      { id: 'shortcuts', group: 'Help', title: 'View Keyboard Shortcuts Cheat Sheet', sub: 'Inspect all hotkeys and navigation keys', kbd: '?', run: () => { openCommandPalette('shortcuts'); return false; } },
      { id: 'reset', group: 'Danger', title: 'Reset Quant Arena Session', sub: 'Open confirmation dialog to reset $100k ledgers', kbd: '', run: () => requestResetArena() },
    ];
  }

  function renderCommandPaletteContent() {
    const listEl = document.getElementById('cmdPaletteList');
    const shortcutsEl = document.getElementById('cmdPaletteShortcutsView');
    const toggleBtn = document.getElementById('btnCmdToggleMode');
    const input = document.getElementById('cmdPaletteInput');
    const badgeEl = document.getElementById('cmdPaletteBackdropBadge');
    if (badgeEl) {
      const labels = { shader: 'Shader', grainient: 'Grainient', minimal: 'Minimal' };
      badgeEl.textContent = labels[backdropMode] || 'Shader';
    }
    if (!listEl || !shortcutsEl) return;

    const isShortcuts = cmdPaletteMode === 'shortcuts';
    if (toggleBtn) toggleBtn.textContent = isShortcuts ? 'Commands' : 'Shortcuts';
    listEl.style.display = isShortcuts ? 'none' : 'flex';
    shortcutsEl.style.display = isShortcuts ? 'flex' : 'none';

    if (isShortcuts) {
      const shortcuts = [
        { kbd: '1', desc: 'Switch to Trading Arena' },
        { kbd: '2', desc: 'Switch to Market Intelligence Hub' },
        { kbd: 'Space', desc: 'Pause or Resume Live Market Feed' },
        { kbd: 'E', desc: 'Trigger Genetic Evolution Tournament' },
        { kbd: 'F', desc: 'Toggle Price Chart Scale (Focus / Full)' },
        { kbd: 'Ctrl+K', desc: 'Open Command Palette' },
        { kbd: '?', desc: 'Open Keyboard Shortcuts Cheat Sheet' },
        { kbd: 'F11', desc: 'Toggle Window Fullscreen' },
        { kbd: 'Esc', desc: 'Close Active Overlay or Modal' },
      ];
      shortcutsEl.innerHTML = shortcuts.map((s) => (
        `<div class="cmd-shortcut-row"><span class="cmd-shortcut-desc">${escapeHtml(s.desc)}</span><kbd class="cmd-palette-kbd">${escapeHtml(s.kbd)}</kbd></div>`
      )).join('');
      return;
    }

    const q = input ? String(input.value || '').trim().toLowerCase() : '';
    const items = getCommandPaletteItems().filter((it) => {
      if (!q) return true;
      return (it.title + ' ' + it.sub + ' ' + it.group).toLowerCase().indexOf(q) !== -1;
    });

    if (items.length === 0) {
      listEl.innerHTML = '<div class="cmd-palette-empty">No matching commands found.</div>';
      cmdPaletteSelectedIdx = 0;
      return;
    }
    if (cmdPaletteSelectedIdx >= items.length) cmdPaletteSelectedIdx = 0;
    if (cmdPaletteSelectedIdx < 0) cmdPaletteSelectedIdx = items.length - 1;

    let lastGroup = '';
    let html = '';
    items.forEach((it, idx) => {
      if (it.group !== lastGroup) {
        lastGroup = it.group;
        html += `<div class="cmd-palette-group">${escapeHtml(it.group)}</div>`;
      }
      const selCls = idx === cmdPaletteSelectedIdx ? 'cmd-palette-item is-selected' : 'cmd-palette-item';
      const kbdHtml = it.kbd ? `<kbd class="cmd-palette-kbd">${escapeHtml(it.kbd)}</kbd>` : '';
      html += `<button type="button" class="${selCls}" role="option" data-cmd-idx="${idx}"><span class="cmd-palette-item-left"><span class="cmd-palette-item-title">${escapeHtml(it.title)}</span><span class="cmd-palette-item-sub">${escapeHtml(it.sub)}</span></span>${kbdHtml}</button>`;
    });
    listEl.innerHTML = html;
    listEl._filteredItems = items;
  }

  function runCommandPaletteItem(item) {
    if (!item || typeof item.run !== 'function') return;
    const res = item.run();
    if (res !== false) {
      closeCommandPalette();
    }
  }

  function openCommandPalette(mode = 'commands') {
    if (cmdPaletteCloseTimer) { clearTimeout(cmdPaletteCloseTimer); cmdPaletteCloseTimer = null; }
    cmdPaletteMode = mode === 'shortcuts' ? 'shortcuts' : 'commands';
    cmdPaletteSelectedIdx = 0;
    const modal = document.getElementById('commandPaletteModal');
    const card = document.getElementById('cmdPaletteCard');
    const input = document.getElementById('cmdPaletteInput');
    if (!modal || !card) return;
    if (input) input.value = '';
    renderCommandPaletteContent();
    modal.style.display = 'flex';
    modal.classList.remove('modal-closing');
    void modal.offsetWidth;
    modal.classList.add('modal-visible');
    syncAppShellInert();
    if (input && cmdPaletteMode === 'commands') {
      setTimeout(() => input.focus(), 40);
    }
  }

  function closeCommandPalette() {
    const modal = document.getElementById('commandPaletteModal');
    if (!modal) return;
    modal.classList.remove('modal-visible');
    modal.classList.add('modal-closing');
    syncAppShellInert();
    if (cmdPaletteCloseTimer) clearTimeout(cmdPaletteCloseTimer);
    cmdPaletteCloseTimer = setTimeout(() => {
      cmdPaletteCloseTimer = null;
      if (!modal.classList.contains('modal-visible')) {
        modal.style.display = 'none';
        modal.classList.remove('modal-closing');
      }
    }, 260);
  }

  function toggleCommandPalette(mode = 'commands') {
    const modal = document.getElementById('commandPaletteModal');
    if (modal && modal.classList.contains('modal-visible')) {
      closeCommandPalette();
    } else {
      openCommandPalette(mode);
    }
  }

  function toggleCommandPaletteMode() {
    cmdPaletteMode = cmdPaletteMode === 'shortcuts' ? 'commands' : 'shortcuts';
    renderCommandPaletteContent();
    const input = document.getElementById('cmdPaletteInput');
    if (input && cmdPaletteMode === 'commands') setTimeout(() => input.focus(), 20);
  }

  function handleCmdPaletteOverlayClick(e) {
    if (e && e.target && e.target.id === 'commandPaletteModal') {
      closeCommandPalette();
    }
  }

  function initCommandPalette() {
    const input = document.getElementById('cmdPaletteInput');
    const listEl = document.getElementById('cmdPaletteList');
    if (input) {
      input.addEventListener('input', () => {
        if (cmdPaletteMode !== 'commands') cmdPaletteMode = 'commands';
        cmdPaletteSelectedIdx = 0;
        renderCommandPaletteContent();
      });
      input.addEventListener('keydown', (e) => {
        if (cmdPaletteMode !== 'commands') return;
        const items = (listEl && listEl._filteredItems) || [];
        if (e.key === 'ArrowDown') {
          e.preventDefault();
          cmdPaletteSelectedIdx = items.length > 0 ? (cmdPaletteSelectedIdx + 1) % items.length : 0;
          renderCommandPaletteContent();
        } else if (e.key === 'ArrowUp') {
          e.preventDefault();
          cmdPaletteSelectedIdx = items.length > 0 ? (cmdPaletteSelectedIdx - 1 + items.length) % items.length : 0;
          renderCommandPaletteContent();
        } else if (e.key === 'Enter') {
          e.preventDefault();
          if (items[cmdPaletteSelectedIdx]) runCommandPaletteItem(items[cmdPaletteSelectedIdx]);
        }
      });
    }
    if (listEl) {
      listEl.addEventListener('click', (e) => {
        const btn = e.target.closest('.cmd-palette-item');
        if (!btn) return;
        const idx = Number(btn.getAttribute('data-cmd-idx'));
        const items = listEl._filteredItems || [];
        if (Number.isFinite(idx) && items[idx]) {
          runCommandPaletteItem(items[idx]);
        }
      });
    }
  }

  window.openCommandPalette = openCommandPalette;
  window.closeCommandPalette = closeCommandPalette;
  window.toggleCommandPaletteMode = toggleCommandPaletteMode;
  window.handleCmdPaletteOverlayClick = handleCmdPaletteOverlayClick;

  let backdropMode = 'shader';
  let ambientShaderHandle = null;

  function applyBackdropMode(mode) {
    const valid = ['shader', 'grainient', 'minimal'];
    backdropMode = valid.indexOf(mode) !== -1 ? mode : 'shader';
    if (document.body) {
      document.body.setAttribute('data-backdrop-mode', backdropMode);
    }
    try {
      localStorage.setItem('tb0_backdrop_mode', backdropMode);
    } catch (_) { }
    const grainEl = document.getElementById('lgAmbientGrainient');
    const canvasEl = document.getElementById('lgAmbientShaderCanvas');
    if (grainEl) grainEl.setAttribute('data-mode', backdropMode);
    if (canvasEl) canvasEl.setAttribute('data-mode', backdropMode);
    syncAmbientShaderMotion();
    if (document.getElementById('commandPaletteModal')?.classList.contains('modal-visible')) {
      renderCommandPaletteContent();
    }
  }

  function cycleBackdropMode() {
    const order = ['shader', 'grainient', 'minimal'];
    const next = order[(order.indexOf(backdropMode) + 1) % order.length];
    applyBackdropMode(next);
    if (typeof showChartToast === 'function') {
      const names = { shader: 'HorizonX Shader', grainient: 'Grainient Obsidian', minimal: 'Minimal Obsidian' };
      showChartToast({ triggerReason: 'Backdrop: ' + (names[next] || next), action: 'VIEW' });
    }
  }
  window.cycleBackdropMode = cycleBackdropMode;

  function mountSilverStreamAmbient(canvas) {
    if (!canvas) return null;
    let gl = null;
    try {
      gl = canvas.getContext('webgl', { alpha: false, antialias: false, powerPreference: 'low-power', preserveDrawingBuffer: false });
    } catch (_) {
      gl = null;
    }
    if (!gl) return null;

    const cfg = {
      bg: [4 / 255, 6 / 255, 10 / 255],
      fg: [159 / 255, 216 / 255, 232 / 255],
      speed: 0.24,
      density: 84,
      pointSize: 2.1,
      trails: 1.0,
      bend: 1.0,
      spread: 1.0,
      exposure: 0.56,
      scale: 1.0,
      phase: 0.0,
    };

    const vsSrc = `
precision highp float;
attribute vec3 particle;
attribute vec2 corner;
uniform vec2 resolution;
uniform float time, phase, pointSize, trails, bend, spread, scale, exposure;
varying vec2 local;
varying float light, extent;
float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1,311.7)))*43758.5453); }
float bell(float x) { return exp(-x*x); }
vec2 surface(float u, float v, float layer) {
  vec2 p;
  if (layer < 0.5) {
    float theta = -1.35 + 2.6*u;
    float r = 0.33 + 1.55*v;
    float twist = 0.12*sin(r*3.1)*bend;
    theta += twist + 0.035*sin(u*8.0+r*2.3)*bend;
    p = vec2(0.28 + r*sin(theta)*spread, 0.255 + r*cos(theta)*0.50);
    p.x += 0.13*bell((r-0.47)*3.8);
    p.y += (0.020*sin(u*9.0+r*3.8) - 0.015*cos(u*5.0+r*2.2))*bend;
    p.x += 0.008*sin(u*17.0+r*9.0)*bell((r-0.7)*3.0)*bend;
  } else if (layer < 1.5) {
    float t = v;
    vec2 a = vec2(0.28+u*0.80,-0.16);
    vec2 b = vec2(0.67+u*0.32,0.09);
    vec2 c = vec2(-0.55+u*2.2,0.14-u*0.015+0.24*pow(u,4.0));
    p = (1.0-t)*(1.0-t)*a + 2.0*t*(1.0-t)*b+t*t*c;
    p.x = 0.76+(p.x-0.76)*spread;
    p.x += 0.008*sin(u*54.0+t*11.0)*bend;
    p.y += 0.006*sin(u*42.0+t*15.0)*bend;
  } else if (layer < 2.5) {
    float x = -0.25+v*1.65;
    p = vec2(x, 0.125 + x*0.18 + x*x*0.015 + (u-0.5)*0.045*spread);
    p.y += 0.005*sin(x*5.0+u*2.0)*bend;
    p.x += 0.10*sin(u*3.14159)*sin(v*2.0);
  } else {
    p = vec2(-0.16+u*0.34 + 0.05*sin(v*5.0+u*2.0), -0.1+v*0.25);
  }
  float t = (time+phase)*0.24;
  p += vec2(sin(t+v*5.0+u*3.0)-sin(v*5.0+u*3.0), cos(t*0.7+u*4.0)-cos(u*4.0))*0.012*bend;
  return p;
}
void main() {
  float u = particle.x, v = particle.y, layer = particle.z;
  float seed = hash(vec2(u*83.0+layer*43.0,v*139.0));
  float flow = mod(v + time*0.015,1.0);
  vec2 p = surface(u,flow,layer);
  float lengthFactor;
  if (layer < 0.5) {
    lengthFactor = (smoothstep(0.56,0.74,u)*0.016 + smoothstep(0.56,0.86,p.y)*0.027)*(0.45+seed*0.8);
  } else if (layer < 1.5) {
    lengthFactor = 0.065*(0.08+seed);
  } else if (layer < 2.5) {
    lengthFactor = 0.042*(0.05+seed);
  } else lengthFactor = 0.0001;
  lengthFactor *= seed > 0.16 ? 0.25+0.75*seed : 0.005;
  float dt = max(0.00008,lengthFactor*trails);
  vec2 tail = surface(u,flow-dt,layer);
  float aspect = resolution.x/max(resolution.y,1.0);
  vec2 fit = vec2(max(1.0,0.5/aspect),max(1.0,aspect/0.5));
  vec2 head = (p-0.5)*vec2(2.0,-2.0)*fit*scale;
  vec2 end = (tail-0.5)*vec2(2.0,-2.0)*fit*scale;
  vec2 metric = resolution*0.5;
  vec2 d = (head-end)*metric;
  float len = length(d);
  vec2 tangent = d/max(len,0.0001);
  vec2 normal = vec2(-tangent.y,tangent.x);
  float radius = max(0.55, pointSize*(0.6+seed*0.65)*resolution.y/2048.0);
  vec2 midpoint = (head+end)*0.5;
  vec2 offset = (tangent*corner.x*(len*0.5+radius) + normal*corner.y*radius*1.6)/metric;
  gl_Position = vec4(midpoint+offset,0.0,1.0);
  local = vec2(corner.x*(len*0.5+radius)/radius,corner.y*1.6);
  extent = len*0.5/radius;
  light = (0.42+0.58*seed)*exposure;
  float cavity = bell((p.x-0.25)*5.0)*bell((p.y-0.355)*14.0);
  light *= 1.0-0.85*cavity;
  if (layer < 0.5) light *= mix(0.27,1.0,max(smoothstep(0.42,0.65,p.y),smoothstep(0.59,0.78,p.x)));
  if (layer > 0.5 && layer < 1.5) light *= 1.42;
  if (layer > 1.5 && layer < 2.5) light *= 0.74;
  light *= 0.55+0.45*hash(vec2(floor(u*72.0)+layer*18.0,5.0));
  light *= 0.60+0.40*sin(u*24.0+flow*13.0+layer)*sin(u*24.0+flow*13.0+layer);
}`;

    const fsSrc = `
precision highp float;
uniform vec3 foreground;
float hash(vec2 p) { return fract(sin(dot(p,vec2(127.101,311.699)))*43758.54531); }
varying vec2 local;
varying float light, extent;
void main() {
  vec2 q=vec2(max(abs(local.x)-extent,0.0),local.y);
  float shape=1.00001-smoothstep(0.549999,1.19999,length(q));
  float tail=mix(0.14,1.00001,clamp((local.x+extent+1.0)/(1.99999*extent+2.0),0.0,0.99999));
  float core=exp(-local.y*local.y*4.0);
  float head=0.99999-smoothstep(0.350001,1.24999,length(local-vec2(extent,0.0)));
  float alpha=light*(shape*tail*0.850001 + head*0.850001)*(0.749999+0.250001*core);
  alpha *= 0.579999+0.42*hash(floor(gl_FragCoord.xy));
  gl_FragColor=vec4(foreground,alpha);
}`;

    let shaders = [];
    let program = null;
    let buffer = null;
    let count = 0;
    const uniforms = {};
    let rafId = 0;
    let lastTs = 0;
    let lastDrawTs = 0;
    let simTime = 0;
    let destroyed = false;

    const compile = (type, src) => {
      const sh = gl.createShader(type);
      shaders.push(sh);
      gl.shaderSource(sh, src);
      gl.compileShader(sh);
      if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) throw new Error('Shader compile error');
      return sh;
    };

    try {
      program = gl.createProgram();
      gl.attachShader(program, compile(gl.VERTEX_SHADER, vsSrc));
      gl.attachShader(program, compile(gl.FRAGMENT_SHADER, fsSrc));
      gl.linkProgram(program);
      if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error('Shader link error');
      gl.useProgram(program);
      buffer = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, buffer);

      const values = [];
      const corners = [[-1, -1], [1, -1], [-1, 1], [-1, 1], [1, -1], [1, 1]];
      const d = cfg.density;
      for (let layer = 0; layer < 4; layer++) {
        const cols = layer === 2 ? Math.round(d * 0.35) : layer === 3 ? Math.round(d * 0.25) : layer === 1 ? Math.round(d * 1.3) : d;
        const rows = layer === 0 ? Math.round(d * 1.2) : Math.round(d * 0.45);
        for (let r = 0; r < rows; r++) {
          for (let c = 0; c < cols; c++) {
            const jx = Math.sin(c * 123.701 + r * 327.1 + layer * 8.1) * 0.18;
            const jy = Math.sin(c * 73.0999 + r * 171.301 + layer * 42.0001) * 0.18;
            for (const [cx, cy] of corners) {
              values.push((c + 0.5 + jx) / cols, (r + 0.5 + jy) / rows, layer, cx, cy);
            }
          }
        }
      }
      count = values.length / 5;
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(values), gl.STATIC_DRAW);

      const pLoc = gl.getAttribLocation(program, 'particle');
      gl.enableVertexAttribArray(pLoc);
      gl.vertexAttribPointer(pLoc, 3, gl.FLOAT, false, 20, 0);
      const cLoc = gl.getAttribLocation(program, 'corner');
      gl.enableVertexAttribArray(cLoc);
      gl.vertexAttribPointer(cLoc, 2, gl.FLOAT, false, 20, 12);
      gl.enable(gl.BLEND);
      gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);

      ['resolution', 'time', 'phase', 'pointSize', 'trails', 'bend', 'spread', 'scale', 'exposure', 'foreground'].forEach((k) => {
        uniforms[k] = gl.getUniformLocation(program, k);
      });
    } catch (_) {
      return null;
    }

    const drawFrame = () => {
      if (destroyed || !program) return;
      const box = canvas.getBoundingClientRect();
      if (box.width < 2 || box.height < 2) return;
      const w = Math.max(1, Math.round(box.width));
      const h = Math.max(1, Math.round(box.height));
      if (canvas.width !== w || canvas.height !== h) {
        canvas.width = w;
        canvas.height = h;
      }
      gl.viewport(0, 0, w, h);
      gl.useProgram(program);
      gl.clearColor(cfg.bg[0], cfg.bg[1], cfg.bg[2], 1.0);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.uniform2f(uniforms.resolution, w, h);
      gl.uniform1f(uniforms.time, simTime);
      gl.uniform1f(uniforms.phase, cfg.phase);
      gl.uniform1f(uniforms.pointSize, cfg.pointSize);
      gl.uniform1f(uniforms.trails, cfg.trails);
      gl.uniform1f(uniforms.bend, cfg.bend);
      gl.uniform1f(uniforms.spread, cfg.spread);
      gl.uniform1f(uniforms.scale, cfg.scale);
      gl.uniform1f(uniforms.exposure, cfg.exposure);
      gl.uniform3fv(uniforms.foreground, cfg.fg);
      gl.drawArrays(gl.TRIANGLES, 0, count);
    };

    const shouldRun = () => (
      !destroyed &&
      !isViewTransitioning &&
      backdropMode === 'shader' &&
      !document.hidden &&
      !(document.body && (document.body.classList.contains('window-hidden') || document.body.classList.contains('arena-paused'))) &&
      !isReducedMotionPreferred()
    );

    const tick = (now) => {
      rafId = 0;
      if (!shouldRun()) return;
      if (!lastDrawTs || (now - lastDrawTs) >= 32) {
        const dt = lastTs ? Math.min((now - lastTs) / 1000, 0.05) : (1 / 30);
        simTime += dt * cfg.speed;
        lastTs = now;
        lastDrawTs = now;
        drawFrame();
      }
      rafId = requestAnimationFrame(tick);
    };

    const sync = () => {
      if (shouldRun()) {
        if (!rafId) {
          lastTs = 0;
          drawFrame();
          rafId = requestAnimationFrame(tick);
        }
      } else if (rafId) {
        cancelAnimationFrame(rafId);
        rafId = 0;
      }
    };

    drawFrame();
    return {
      sync,
      drawOnce: drawFrame,
      destroy() {
        destroyed = true;
        if (rafId) { cancelAnimationFrame(rafId); rafId = 0; }
        shaders.forEach((s) => gl.deleteShader(s));
        if (buffer) gl.deleteBuffer(buffer);
        if (program) gl.deleteProgram(program);
      },
    };
  }

  function syncAmbientShaderMotion() {
    if (ambientShaderHandle && typeof ambientShaderHandle.sync === 'function') {
      ambientShaderHandle.sync();
    }
  }

  function destroyAmbientBackdrop() {
    if (ambientShaderHandle && typeof ambientShaderHandle.destroy === 'function') {
      ambientShaderHandle.destroy();
      ambientShaderHandle = null;
    }
  }

  function initAmbientBackdrop() {
    let savedMode = 'shader';
    try {
      savedMode = localStorage.getItem('tb0_backdrop_mode') || 'shader';
    } catch (_) {
      savedMode = 'shader';
    }
    const canvas = document.getElementById('lgAmbientShaderCanvas');
    ambientShaderHandle = mountSilverStreamAmbient(canvas);
    if (!ambientShaderHandle && savedMode === 'shader') {
      savedMode = 'grainient';
    }
    applyBackdropMode(savedMode);
  }


