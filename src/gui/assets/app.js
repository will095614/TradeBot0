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

// Global Arena Data & Polling States
let latestState = null;
let isPolling = false;
let stateApplyEpoch = 0;
let forceNextFullDelta = false;
let scaleMode = 'auto';    // 'auto' or 'full'

// Position tracking states
let knownStrategyPositions = {};
let hasInitializedPositions = false;

// Toast Notification Stagger Queue & Micro-Interactions
let toastQueue = [];
let isProcessingToastQueue = false;
let toastStaggerTimer = null;
const MAX_VISIBLE_TOASTS = 6;
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
    splashSafetyTimer = setTimeout(() => {
      if (!splashCompleted) {
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
      }
    }, 3500);
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
  if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.get_setup_status === 'function') {
    try {
      const res = await window.pywebview.api.get_setup_status();
      if (res && res.status === 'ok') {
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

  hasCheckedOnboarding = true;
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
    initAppBoot();
  });
  setTimeout(() => {
    if (!hasBootInitiated) {
      initAppBoot();
    }
  }, 200);
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

function processToastQueue() {
  const container = document.getElementById('chartNotificationContainer');
  if (!container) return;

  // Count active non-exiting toasts currently mounted in container
  const activeToasts = Array.from(container.children).filter(el => !el.classList.contains('toast-exit'));

  // Up to MAX_VISIBLE_TOASTS (6) concurrent cards
  if (activeToasts.length >= MAX_VISIBLE_TOASTS || toastQueue.length === 0) {
    return;
  }

  // Dequeue and render exactly ONE item
  const nextItem = toastQueue.shift();
  if (nextItem) {
    const toastEl = nextItem.renderElement();
    if (toastEl) {
      container.appendChild(toastEl);
      attachToastInteractions(toastEl, container, TOAST_DURATION_MS);
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

  // Smooth 450ms exit transition matching CSS
  setTimeout(() => {
    if (toast.parentNode) {
      toast.parentNode.removeChild(toast);
    }
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
  const RING_CIRCUMFERENCE = 43.982;

  if (ringFill) {
    toast._countdownInterval = setInterval(() => {
      if (toast._isDismissing) {
        clearInterval(toast._countdownInterval);
        toast._countdownInterval = null;
        return;
      }
      if (!toast._isPaused) {
        const elapsed = Date.now() - toast._startTime;
        toast._remainingMs = Math.max(0, toast._totalDurationMs - elapsed);
        const offset = RING_CIRCUMFERENCE * (1 - toast._remainingMs / toast._totalDurationMs);
        ringFill.style.strokeDashoffset = offset.toFixed(2);
        if (toast._remainingMs <= 0) {
          clearInterval(toast._countdownInterval);
          toast._countdownInterval = null;
          dismissToast(toast);
        }
      }
    }, 50);

    toast.addEventListener('mouseenter', () => {
      if (toast._isDismissing) return;
      toast._isPaused = true;
    });

    toast.addEventListener('mouseleave', () => {
      if (toast._isDismissing) return;
      toast._isPaused = false;
      toast._startTime = Date.now() - (toast._totalDurationMs - toast._remainingMs);
    });
  } else {
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
}

// Global watchdog timer: dismisses any stale toast older than 18 seconds that is not hovered
setInterval(() => {
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
  if (isPolling) return;
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

            const isNewEntry = (isNowInPos && !wasInPos) ||
              (isNowInPos && wasInPos && (
                (curEntry > 0 && prevEntry > 0 && Math.abs(curEntry - prevEntry) > 0.05) ||
                (curSide !== prevSide)
              ));

            const isClosed = (wasInPos && !isNowInPos);

            if (splashCompleted) {
              if (isNewEntry) {
                newEntryStrats.push(s);
              } else if (isClosed) {
                closedStrats.push({ strat: s, prev: prev });
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
  const myEpoch = ++stateApplyEpoch;
  try {
    const state = await window.pywebview.api.evolve_now();
    if (state && myEpoch === stateApplyEpoch) { latestState = state; renderAll(state); }
  } catch (err) {
    console.warn('evolve_now error:', err);
  }
}

async function togglePause() {
  if (!window.pywebview || !window.pywebview.api) return;
  // Immediate optimistic toggle for zero-latency UI transition
  const willPause = !Boolean(latestState && latestState.paused);
  document.body.classList.toggle('arena-paused', willPause);
  const pauseBtn = document.getElementById('pauseBtn');
  if (pauseBtn) {
    const nextLbl = willPause ? 'Resume Feed' : 'Pause Feed';
    pauseBtn._lastLabel = nextLbl;
    pauseBtn.innerHTML = `<span>${nextLbl}</span>`;
    pauseBtn.classList.toggle('btn-paused-active', willPause);
    pauseBtn.title = willPause ? 'Resume Live Feed (Press Space)' : 'Pause Live Feed (Press Space)';
  }
  const badge = document.getElementById('liveBadge');
  const statusText = document.getElementById('liveStatusText');
  if (badge && statusText) {
    badge.classList.toggle('is-paused', willPause);
    statusText.textContent = willPause ? 'Paused' : 'Live 24/7';
  }
  if (latestState) {
    latestState.paused = willPause;
  }
  updateUiClockDisplay();

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
  }
}

async function toggleAutoEvolve() {
  if (!window.pywebview || !window.pywebview.api) return;
  const myEpoch = ++stateApplyEpoch;
  try {
    const state = await window.pywebview.api.toggle_auto_evolve();
    if (state && myEpoch === stateApplyEpoch) { latestState = state; renderAll(state); }
  } catch (err) {
    console.warn('toggle_auto_evolve error:', err);
  }
}

async function changeEvolveInterval(seconds) {
  if (!window.pywebview || !window.pywebview.api) return;
  const sec = parseInt(seconds, 10);
  if (isNaN(sec) || sec <= 0) return;
  const myEpoch = ++stateApplyEpoch;
  try {
    const state = await window.pywebview.api.set_evolve_interval(sec);
    if (state && myEpoch === stateApplyEpoch) { latestState = state; renderAll(state); }
  } catch (err) {
    console.warn('set_evolve_interval error:', err);
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

  if (badge && regimeTxt) {
    // Guarded className: the regime class is part of the final string,
    // so one compare-and-set replaces the reset + add. The badge class
    // set is fully determined here, so the result is identical.
    const nextBadgeCls = 'macro-badge ss-badge'
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
    if (regimeTxt.textContent !== nextRegimeTxt) regimeTxt.textContent = nextRegimeTxt;
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
    const nextOmni = mc.status === 'ONLINE' ? '\u667a\u8166: \u9023\u7db2\u5728\u7dda (100k)' : '\u63a8\u8ad6: \u672c\u6a5f NLP \u6975\u901f';
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
function renderHeader(state) {
  const q = state.quote || {};
  const spotEl = document.getElementById('spotPrice');
  const candles = state.candles || [];
  const lastCandleClose = candles.length > 0 ? Number(candles[candles.length - 1].c || 0) : 0;
  const quotePrice = Number(q.price || 0);
  const curP = quotePrice > 0 ? quotePrice : (lastCandleClose > 0 ? lastCandleClose : 0);

  spotEl.textContent = curP > 0 ? fmtUsd(curP, 2) : '—';
  lastSpotPrice = curP;

  const chg = Number(q.change_24h_pct || 0);
  const chgEl = document.getElementById('change24h');
  chgEl.textContent = fmtPct(chg);
  chgEl.className = 'stat-val island-delta-pill num ' + (chg >= 0 ? 'up' : 'down');
  spotEl.className = 'stat-val spot-hero num ' + (chg >= 0 ? 'up' : 'down');

  const bidAskEl = document.getElementById('bidAskSpread');
  if (q.bid && q.ask && !q.is_offline) {
    bidAskEl.textContent = `${fmtUsd(q.bid, 2)} / ${fmtUsd(q.ask, 2)}`;
  } else if (curP > 0) {
    bidAskEl.textContent = `${fmtUsd(curP, 2)} (Candle)`;
  } else {
    bidAskEl.textContent = '— / —';
  }

  const highLowEl = document.getElementById('highLow24h');
  if (q.high_24h && q.low_24h && !q.is_offline) {
    highLowEl.textContent = `${fmtUsd(q.high_24h, 0)} / ${fmtUsd(q.low_24h, 0)}`;
  } else if (curP > 0) {
    highLowEl.textContent = `${fmtUsd(curP, 0)} / ${fmtUsd(curP, 0)}`;
  } else {
    highLowEl.textContent = '— / —';
  }
  const genLbl = document.getElementById('genLabel');
  if (genLbl) {
    const nextGen = `Gen #${state.generation}`;
    if (genLbl.textContent !== nextGen) genLbl.textContent = nextGen;
  }

  const isPaused = Boolean(state.paused);
  document.body.classList.toggle('arena-paused', isPaused);

  // Auto Evolve Countdown & Interval Sync
  const cdEl = document.getElementById('countdownLabel');
  const autoBtn = document.getElementById('autoEvolveToggleBtn');
  // Custom Gen interval dropdown sync (2026-11-13): the native <select>
  // was replaced by a liquid-glass button + menu (its popup is
  // OS-rendered and cannot be styled); the current interval is shown in
  // #evolveIntervalLabel and the selected menu item is marked by
  // syncEvolveIntervalUI().
  if (state.auto_evolve_interval_sec) {
    syncEvolveIntervalUI(String(state.auto_evolve_interval_sec));
  }

  const autoLbl = document.getElementById('autoEvolveLabelText');
  cdEl.textContent = fmtTimeSec(state.next_evolve_sec || 0);
  // P2 note wiring (2026-11-13): the countdown blends both triggers, so
  // the full honest note (latest time cap + trades still needed) rides on
  // the countdown tooltip; the trades-remaining part is also visible in
  // the Genetic Engine card (hudGenSub below).
  if (cdEl && typeof state.next_evolve_sec_note === 'string' && state.next_evolve_sec_note) {
    cdEl.title = state.next_evolve_sec_note;
  }

  if (isPaused) {
    cdEl.style.color = 'var(--ss-text-faint)';
    if (autoBtn) autoBtn.dataset.on = 'false';
    if (autoLbl) autoLbl.textContent = 'Paused';
    else if (autoBtn) autoBtn.textContent = 'Paused';
  } else if (state.auto_evolve_enabled) {
    cdEl.style.color = 'var(--ss-accent-text)';
    if (autoBtn) autoBtn.dataset.on = 'true';
    if (autoLbl) autoLbl.textContent = 'Active';
    else if (autoBtn) autoBtn.textContent = 'Active';
  } else {
    cdEl.style.color = 'var(--ss-text-faint)';
    if (autoBtn) autoBtn.dataset.on = 'false';
    if (autoLbl) autoLbl.textContent = 'Paused';
    else if (autoBtn) autoBtn.textContent = 'Paused';
  }

  lastCadenceFeedTs = (q && q.timestamp) || '';
  updateUiClockDisplay();

  const badge = document.getElementById('liveBadge');
  const statusText = document.getElementById('liveStatusText');
  const pauseBtn = document.getElementById('pauseBtn');
  const isOffline = state.market_online === false || (q && q.is_offline);
  const desiredPauseLabel = isPaused ? 'Resume Feed' : 'Pause Feed';
  if (pauseBtn) {
    if (pauseBtn._lastLabel !== desiredPauseLabel) {
      pauseBtn._lastLabel = desiredPauseLabel;
      pauseBtn.innerHTML = `<span>${desiredPauseLabel}</span>`;
    }
    pauseBtn.classList.toggle('btn-paused-active', isPaused);
    pauseBtn.title = isPaused ? 'Resume Live Feed (Press Space)' : 'Pause Live Feed (Press Space)';
  }
  if (badge && statusText) {
    badge.classList.toggle('is-paused', isPaused);
    badge.style.background = '';
    badge.style.color = '';
    badge.style.borderColor = '';
    if (isPaused) {
      statusText.textContent = 'Paused';
    } else if (isOffline) {
      statusText.textContent = 'Feed Offline';
    } else {
      statusText.textContent = 'Live 24/7';
    }
  }

  document.getElementById('omniSummary').textContent = state.omni_summary || '';

  const srcEl = document.getElementById('omniSourceBadge');
  if (srcEl) {
    const mcState = state.macro_commander || {};
    const omniState = (state.intel_hub && state.intel_hub.omniroute) || {};
    const isAiOnline = (omniState.status === 'ONLINE') || (mcState.status === 'ONLINE');
    srcEl.textContent = isAiOnline ? 'OmniRoute AI' : 'Pure Math Core';
    srcEl.style.background = isAiOnline ? 'rgba(56, 189, 248, 0.16)' : 'rgba(0, 242, 254, 0.14)';
    srcEl.style.color = 'var(--ss-text-strong)';
  }
  const qEl = document.getElementById('omniQuotaBadge');
  if (qEl) {
    qEl.textContent = isOffline ? 'Feed: Offline' : 'Feed: Active';
    qEl.style.background = isOffline ? 'var(--ss-danger-soft)' : 'var(--ss-success-soft)';
    qEl.style.color = isOffline ? 'var(--ss-danger-text)' : 'var(--ss-success-text)';
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

function renderStrategies(state) {
  const grid = document.getElementById('tabCardsView');
  if (!grid) return;
  const strategies = (state.strategies || []).slice().sort((a, b) => (b.equity - a.equity) || (a.rank - b.rank));
  const candles = state.candles || [];
  const lastCandleClose = candles.length > 0 ? Number(candles[candles.length - 1].c || 0) : 0;
  const quotePrice = Number((state.quote && state.quote.price) || 0);
  const spot = quotePrice > 0 ? quotePrice : (lastCandleClose > 0 ? lastCandleClose : 0);

  // Build / Update each card DOM element
  const activeStratIds = new Set();
  strategies.forEach(s => {
    activeStratIds.add(s.id);
    const sColor = sanitizeCssColor(s.color, '#F59E0B');
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
    const displayName = escapeHtml(cardShortNames[s.id] || s.name || '');

    const pnlLabel = s.in_position ? 'Unrealized PnL' : 'Cash Balance';
    const pnlValue = s.in_position
      ? `<span class="${upnlClass}">${fmtSignedUsd(upnlNum)}</span>`
      : `<span>${fmtUsd(s.cash, 0)}</span>`;

    const cardInner = `
        <span class="lg-strat-orb" aria-hidden="true"></span>
        <div class="strat-top">
          <div class="strat-left">
            <span class="rank-badge num" style="color:${sColor}">#${Number(s.rank) || 0}</span>
            <span class="strat-title" title="${escapeHtml(s.name)}">${displayName}</span>
            <span class="strat-pill num">Gen #${Number(s.generation) || 1} · ${escapeHtml(s.genome || '')}</span>
          </div>
          <div class="strat-right num">
            ${levBadge}
            ${posPill}
          </div>
        </div>

        <div class="strat-kpis num">
          <div class="kpi-cell">
            <span>Total Equity</span>
            <span>${fmtUsd(s.equity, 2)}</span>
          </div>
          <div class="kpi-cell">
            <span>ROI</span>
            <span class="${roiClass}">${fmtPct(roiNum)}</span>
          </div>
          <div class="kpi-cell">
            <span>${pnlLabel}</span>
            ${pnlValue}
          </div>
          <div class="kpi-cell">
            <span>Win / Max DD</span>
            <span style="color:var(--ss-text)">${winRateNum.toFixed(0)}% / ${maxDdNum.toFixed(1)}%</span>
          </div>
        </div>

        ${bracketHtml}
      `;

    let card = stratCardDomMap.get(s.id);
    if (!card) {
      card = document.createElement('div');
      card.className = 'strat-card-mini';
      card.dataset.stratId = s.id;
      stratCardDomMap.set(s.id, card);
    }
    if (card._stratColor !== s.color) {
      card.style.setProperty('--strat-color', sColor);
      card._stratColor = s.color;
    }
    if (card._lastHtml !== cardInner) {
      card._lastHtml = cardInner;
      card.innerHTML = cardInner;
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
          moved.forEach(card => { card.style.transform = ''; });
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

function renderTacticalHud(state) {
  if (!state) return;
  const tv = state.tv_hub || {};
  const champ = tv.champion || (state.strategies && state.strategies[0]) || {};
  const candles = state.candles || [];
  const lastCandleClose = candles.length > 0 ? Number(candles[candles.length - 1].c || 0) : 0;
  const quotePrice = Number((state.quote && state.quote.price) || 0);
  const spot = quotePrice > 0 ? quotePrice : (lastCandleClose > 0 ? lastCandleClose : 0);

  // 1. Champion Spotlight
  const cTitleEl = document.getElementById('hudChampTitle');
  if (cTitleEl) {
    const hVal = Math.round((state.auto_evolve_interval_sec || 21600) / 3600);
    cTitleEl.textContent = `${hVal > 0 ? hVal + 'H ' : ''}Champion`;
  }
  const cNameEl = document.getElementById('hudChampName');
  if (cNameEl) {
    cNameEl.textContent = champ.name ? champ.name.split(' ')[0] : 'Evaluating...';
    cNameEl.title = champ.name || '';
  }
  const cStatsEl = document.getElementById('hudChampStats');
  if (cStatsEl) {
    const rotStr = fmtTimeSec(tv.next_rotation_sec || 0);
    cStatsEl.textContent = `ROI ${fmtPct(champ.roi_pct || 0)} · ${rotStr}`;
  }

  // 2. Momentum & Volatility (RSI & ATR)
  const ind = state.indicators || {};
  const rsi = Number(ind.rsi !== undefined ? ind.rsi : 50.0);
  const atr = Number(ind.atr !== undefined ? ind.atr : 2.5);
  const rsiEl = document.getElementById('hudRsiVal');
  if (rsiEl) {
    rsiEl.textContent = `RSI ${rsi.toFixed(1)}`;
    rsiEl.className = 'hud-value num ' + (rsi >= 55 ? 'up' : (rsi <= 45 ? 'down' : ''));
  }
  const atrEl = document.getElementById('hudAtrVal');
  if (atrEl) {
    const atrPct = spot > 0 ? ((atr / spot) * 100).toFixed(2) : '0.00';
    atrEl.textContent = `ATR $${atr.toFixed(2)} · ${atrPct}%`;
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

  const expQtyEl = document.getElementById('hudExposureQty');
  if (expQtyEl) expQtyEl.textContent = `${totQty.toFixed(3)} ETH`;
  const expValEl = document.getElementById('hudExposureVal');
  if (expValEl) expValEl.textContent = `${fmtUsd(expVal, 0)} · ${cashPct}% Cash`;

  // 4. Genetic Engine
  const genEl = document.getElementById('hudGenVal');
  if (genEl) genEl.textContent = `Gen #${state.generation || 1}`;
  const genSubEl = document.getElementById('hudGenSub');
  if (genSubEl) {
    const hVal = Math.round((state.auto_evolve_interval_sec || 21600) / 3600);
    // P2 note wiring (2026-11-13): the trades-remaining label is rendered
    // by the view model (Python) because frontend assets must stay CJK-free
    // (see test_zero_cjk_in_frontend_assets); JS only displays it opaquely.
    const tradesLabel = (typeof state.next_evolve_trades_label === 'string' && state.next_evolve_trades_label)
      ? state.next_evolve_trades_label
      : '';
    genSubEl.textContent = tradesLabel ? `EV Gate (${hVal}H) · ${tradesLabel}` : `EV Gate (${hVal}H)`;
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

function renderLeaderboard(state) {
  const tbody = document.getElementById('leaderboardBody');
  if (!tbody) return;
  const strategies = (state.strategies || []).slice().sort((a, b) => (b.equity - a.equity) || (a.rank - b.rank));

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
    let hasShift = false;
    strategies.forEach(s => {
      const prevTop = firstTops.get(s.id);
      const tr = leaderRowDomMap.get(s.id);
      if (prevTop !== undefined && tr) {
        const newTop = tr.getBoundingClientRect().top;
        const dy = prevTop - newTop;
        if (Math.abs(dy) > 1) {
          hasShift = true;
          tr.style.transform = `translateY(${dy}px)`;
          tr.style.transition = 'none';
        }
      }
    });

    if (hasShift) {
      void tbody.offsetHeight;
      requestAnimationFrame(() => {
        strategies.forEach(s => {
          const tr = leaderRowDomMap.get(s.id);
          if (!tr) return;
          tr.style.transition = 'transform 0.42s cubic-bezier(0.22, 1, 0.36, 1)';
          tr.style.transform = '';
        });
      });
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
    'Opening Range Breakout': 'ORB',
    'ORB (15m)': 'ORB',
    'ORB': 'ORB',
    'Session Mean Pullback': 'MEAN',
    'Session Mean': 'MEAN',
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
    cachedCanvasSize = {
      w: Math.max(200, Math.floor(rect.width)),
      h: Math.max(100, Math.floor(rect.height)),
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
  if (intelEl && intelEl.style.display !== 'none') {
    animSpot = targetSpot;
    animMinP = targetMinP;
    animMaxP = targetMaxP;
    candleSlideOffset = 0;
    animCandles = targetCandles.map(c => ({ o: c.o, h: c.h, l: c.l, c: c.c, t: c.t }));
    return;
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

    if (b.isSpot) {
      ctx.font = '600 10px "SF Mono", "JetBrains Mono", Consolas, monospace';
      const txtW = ctx.measureText(b.label).width;
      const rw = Math.max(88, txtW + 16);

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
      const rw = Math.max(88, tagW + valW + 20);

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

  const spotTarget = target.closest('.lg-spot-card, .strat-card-mini, .intel-event-card, .btn');
  if (spotTarget) {
    const r = spotTarget.getBoundingClientRect();
    const lx = Math.round(evt.clientX - r.left);
    const ly = Math.round(evt.clientY - r.top);
    spotTarget.style.setProperty('--x', `${lx}px`);
    spotTarget.style.setProperty('--y', `${ly}px`);
    spotTarget.style.setProperty('--mx', `${lx}px`);
    spotTarget.style.setProperty('--my', `${ly}px`);
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
        if (hoveredCandleData !== null || lastHoverIdx !== -1) needsRedraw = true;
        hoveredCandleData = null;
        lastHoverIdx = -1;
        tip.style.display = 'none';
      }
    } else {
      if (hoveredCandleData !== null || lastHoverIdx !== -1) needsRedraw = true;
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
  const ids = ['shutdownModal', 'resetConfirmModal', 'installCancelConfirmModal', 'wizardCloseConfirmModal', 'networkOfflineOverlay'];
  for (let i = 0; i < ids.length; i++) {
    const el = document.getElementById(ids[i]);
    if (el && el.classList.contains('modal-visible')) return true;
  }
  return false;
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
  if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA' || e.ctrlKey || e.altKey || e.metaKey) {
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
  function switchMainView(viewName) {
    if (currentMainView === viewName) return;
    currentMainView = viewName;
    const arenaEl = document.querySelector('.workspace-grid');
    const intelEl = document.getElementById('intelHubMainView');
    syncSegThumb('mainViewSeg', viewName === 'intel' ? 1 : 0);

    if (viewName === 'intel') {
      if (arenaEl) arenaEl.style.display = 'none';
      if (intelEl) {
        intelEl.style.display = 'grid';
        intelEl.classList.remove('view-entering');
        void intelEl.offsetWidth;
        intelEl.classList.add('view-entering');
        if (intelEl._enterTimer) clearTimeout(intelEl._enterTimer);
        intelEl._enterTimer = setTimeout(() => intelEl.classList.remove('view-entering'), 500);
      }
      if (latestState) renderIntelHub(latestState);
      pumpIntelArticlePreload();
    } else {
      if (intelEl) intelEl.style.display = 'none';
      if (arenaEl) {
        arenaEl.style.display = 'grid';
        arenaEl.classList.remove('view-entering');
        void arenaEl.offsetWidth;
        arenaEl.classList.add('view-entering');
        if (arenaEl._enterTimer) clearTimeout(arenaEl._enterTimer);
        arenaEl._enterTimer = setTimeout(() => arenaEl.classList.remove('view-entering'), 500);
      }
      if (latestState) renderAll(latestState);
      triggerSmoothResize();
    }
  }

  async function requestAiIntelDigest() {
    const btn = document.getElementById('btnRefreshDigest');
    if (btn) {
      btn.disabled = true;
      btn.classList.add('loading');
      btn.innerHTML = `
      <svg class="ss-svg-icon btn-spin-icon" viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M14 8A6 6 0 1 1 8 2"></path>
      </svg>
      <span>Synthesizing...</span>
    `;
    }

    // AI panels (I6): an indeterminate progress bar runs while the
    // refresh is in flight. A digest refresh has no trustworthy
    // percent, so none is fabricated; the bar hides again when the
    // button settles below.
    const digestProg = document.getElementById('digestRefreshProgress');
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
          btn.innerHTML = `
          <svg class="ss-svg-icon btn-spin-icon" viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M13.5 8a5.5 5.5 0 1 1-1.6-3.9L14 6.5M14 2.5v4h-4"></path>
          </svg>
          <span>Refresh News Analysis</span>
        `;
        }
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

  function setIntelSortMode(mode) {
    if (mode !== 'time' && mode !== 'impact') return;
    if (intelSortMode === mode) return;
    intelSortMode = mode;
    syncSegThumb('intelSortSeg', mode === 'impact' ? 1 : 0);
    const list = document.getElementById('intelEventsList');
    if (list) list._intelOrder = '';
    if (latestState) renderIntelHub(latestState);
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
  function requestIntelArticle(eventId) {
    const cached = intelArticleCache[eventId];
    if (cached) { renderIntelArticle(eventId, cached); return; }
    if (intelArticlePending[eventId]) return;
    const body = intelArticleBodyEl(eventId);
    if (body) {
      body.innerHTML = '<div class="intel-article-loading">Loading article\u2026</div>'
        + '<div class="intel-article-progress" role="progressbar" aria-label="Loading article">'
        + '<div class="digest-refresh-progress-track"><div class="digest-refresh-progress-fill indeterminate"></div></div>'
        + '</div>';
      body.classList.add('is-loading');
    }
    if (!window.pywebview || !window.pywebview.api || typeof window.pywebview.api.get_event_article !== 'function') {
      const fail = { state: 'failed', reason: 'Article service unavailable (bridge not connected)' };
      intelArticleCache[eventId] = fail;
      renderIntelArticle(eventId, fail);
      return;
    }
    const p = window.pywebview.api.get_event_article(eventId);
    intelArticlePending[eventId] = p;
    p.then(function (res) {
      delete intelArticlePending[eventId];
      let result;
      if (res && res.ok === true && typeof res.article === 'string' && res.article.trim()) {
        result = { state: 'ready', article: res.article };
      } else {
        result = { state: 'failed', reason: (res && res.reason) || 'Article unavailable' };
      }
      if (intelEventNodes[eventId]) {
        intelArticleCache[eventId] = result;
        renderIntelArticle(eventId, result);
      }
    }).catch(function (err) {
      delete intelArticlePending[eventId];
      const result = { state: 'failed', reason: 'Article request failed: ' + (err && err.message ? err.message : String(err)) };
      if (intelEventNodes[eventId]) {
        intelArticleCache[eventId] = result;
        renderIntelArticle(eventId, result);
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
    if (omniStatus && omniStatus !== 'ONLINE') return;
    let id;
    while ((id = intelArticlePreloadQueue.shift()) !== undefined) {
      // The event may have left the list, or an expand may have already
      // started / cached it, while it waited in the queue.
      if (intelArticleCache[id] || intelArticlePending[id] || !intelEventNodes[id]) continue;
      break;
    }
    if (id === undefined) return;
    intelArticlePreloadRunning = true;
    requestIntelArticle(id);
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
    const nextTime = evt.time || '';
    if (timeEl.textContent !== nextTime) timeEl.textContent = nextTime;
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
      if (biasEl.textContent !== nextBias) biasEl.textContent = nextBias;
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
        const nextOrder = sorted.map(intelEventKey).join('|');
        if (listContainer._intelOrder !== nextOrder) {
          sorted.forEach(function (evt) {
            const card = intelEventNodes[intelEventKey(evt)];
            if (card) listContainer.appendChild(card);
          });
          listContainer._intelOrder = nextOrder;
        }
        // Preload articles for the collapsed cards (see preloadIntelArticles):
        // the list order is the display order, so the cards the user is
        // most likely to open first are preloaded first.
        preloadIntelArticles(sorted.map(intelEventKey));
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

    window.addEventListener('resize', triggerSmoothResize);

    setTimeout(pollBackend, 120);
    window.pollIntervalTimer = setInterval(pollBackend, 1000);
  });

  document.addEventListener('visibilitychange', () => {
    if (document.body) {
      document.body.classList.toggle('window-hidden', document.hidden);
    }
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
    }
  }

  function closeShutdownModal() {
    const modal = document.getElementById('shutdownModal');
    if (modal) {
      modal.classList.remove('modal-visible');
      modal.classList.add('modal-closing');
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
      modal.style.display = 'none';
    }

    // Cease frontend polling immediately to avoid queuing new IPC roundtrips during shutdown
    if (window.pollIntervalTimer) {
      clearInterval(window.pollIntervalTimer);
      window.pollIntervalTimer = null;
    }
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
    const pwInput = document.getElementById('keyAdminPassword');
    const pwConfirm = document.getElementById('keyAdminPasswordConfirm');
    if (pwInput) pwInput.value = '';
    if (pwConfirm) pwConfirm.value = '';
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
          updateRuntimeInstallBanner(res.runtime_install_status);
        }
      }).catch((e) => console.debug('get_setup_status err:', e));
    }
  }

  function closeSetupWizardModal() {
    wizardOpenGen += 1;
    const modal = document.getElementById('setupWizardModal');
    if (modal) {
      modal.classList.remove('wizard-visible');
      modal.classList.add('wizard-closing');
      isWizardOpen = false;
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

  function copyOmniPassword() {
    // The password value never enters the frontend (item 7): the bridge
    // copies it to the OS clipboard server-side and only reports success.
    // Success feedback is shown ON the button itself (2026-11-13): the
    // chart toast lives in the Arena view, so it is invisible while the
    // user is on the Intel Hub page where this button sits.
    const pwdBadge = document.getElementById('omniConsolePwd');
    const flashBadgeFeedback = (text, isSuccess) => {
      if (!pwdBadge) return;
      if (pwdBadge._copiedTimer) clearTimeout(pwdBadge._copiedTimer);
      if (pwdBadge._copiedOriginal === undefined) pwdBadge._copiedOriginal = pwdBadge.innerHTML;
      pwdBadge.textContent = text;
      pwdBadge.classList.toggle('pwd-copied', Boolean(isSuccess));
      pwdBadge._copiedTimer = setTimeout(() => {
        pwdBadge.innerHTML = pwdBadge._copiedOriginal;
        pwdBadge.classList.remove('pwd-copied');
        pwdBadge._copiedOriginal = undefined;
        pwdBadge._copiedTimer = undefined;
      }, 2000);
    };
    const showEnvHint = () => {
      flashBadgeFeedback('copy failed', false);
      if (typeof showChartToast === 'function') {
        showChartToast({ triggerReason: 'Console password saved', action: 'INFO' });
      }
    };
    if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.copy_omniroute_password === 'function') {
      window.pywebview.api.copy_omniroute_password().then((res) => {
        if (res && res.status === 'ok') {
          flashBadgeFeedback('copied!', true);
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
    const closeBtn = document.getElementById('btnWizardClose');
    if (closeBtn && closeBtn.style.display === 'none') return;
    const decide = (st) => {
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
    // Fresh check: the poll runs every 5 s, so the cache can lag a close
    // attempted right after Install was pressed.
    if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.get_setup_status === 'function') {
      window.pywebview.api.get_setup_status().then((res) => {
        const s = (res && res.runtime_install_status) ? res.runtime_install_status.status : null;
        decide(s);
      }).catch(() => decide(cached ? cached.status : null));
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
    }
  }

  function closeInstallCancelConfirm() {
    const modal = document.getElementById('installCancelConfirmModal');
    if (modal) {
      modal.classList.remove('modal-visible');
      modal.classList.add('modal-closing');
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
    }
  }

  function closeWizardCloseConfirm() {
    const modal = document.getElementById('wizardCloseConfirmModal');
    if (modal) {
      modal.classList.remove('modal-visible');
      modal.classList.add('modal-closing');
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

  function updateRuntimeInstallBanner(statusObj) {
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

    try {
      if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.test_api_key === 'function') {
        const res = await window.pywebview.api.test_api_key(provider, rawKey);
        if (res && res.ok) {
          if (stEl) stEl.innerHTML = '<span class="setup-status-pill valid">Connected</span>';
        } else {
          const msg = (res && res.message) ? res.message : 'Verification failed';
          if (stEl) stEl.innerHTML = '<span class="setup-status-pill error">Check failed</span>';
          setWizardBanner(msg, 'error');
        }
      } else {
        setTimeout(() => {
          if (stEl) stEl.innerHTML = '<span class="setup-status-pill valid">&#x2713; Format Accepted (Preview)</span>';
        }, 400);
      }
    } catch (err) {
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
                showChartToast({
                  strategyId: 'comp_cons',
                  action: 'BUY',
                  symbol: 'ETH/USD',
                  price: (latestState && latestState.quote && latestState.quote.price) || (latestState && latestState.candles && latestState.candles.length > 0 ? latestState.candles[latestState.candles.length - 1].c : 2650.0),
                  qty: 0,
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
      // A confirm dialog open on top swallows Escape: dismiss the dialog
      // and stay on the wizard instead of closing the wizard behind it.
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
      const shutdownModal = document.getElementById('shutdownModal');
      if (shutdownModal && shutdownModal.classList.contains('modal-visible')) {
        closeShutdownModal();
        return;
      }
      const resetModal = document.getElementById('resetConfirmModal');
      if (resetModal && resetModal.classList.contains('modal-visible')) {
        closeResetModal();
        return;
      }
      if (isWizardOpen) {
        const closeBtn = document.getElementById('btnWizardClose');
        if (closeBtn && closeBtn.style.display !== 'none') {
          requestCloseSetupWizardModal();
        }
      }
    }
  });

  /* ==========================================================================
     RESET CONFIRMATION MODAL CONTROLLERS
     ========================================================================== */
  function requestResetArena() {
    if (resetCloseTimer) { clearTimeout(resetCloseTimer); resetCloseTimer = null; }
    blurActiveFocus();
    const modal = document.getElementById('resetConfirmModal');
    if (modal) {
      modal.style.display = 'flex';
      modal.classList.remove('modal-closing');
      void modal.offsetWidth;
      modal.classList.add('modal-visible');
    }
  }

  function closeResetModal() {
    const modal = document.getElementById('resetConfirmModal');
    if (modal) {
      modal.classList.remove('modal-visible');
      modal.classList.add('modal-closing');
      if (resetCloseTimer) clearTimeout(resetCloseTimer);
      resetCloseTimer = setTimeout(() => {
        resetCloseTimer = null;
        if (!modal.classList.contains('modal-visible')) {
          modal.style.display = 'none';
          modal.classList.remove('modal-closing');
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

