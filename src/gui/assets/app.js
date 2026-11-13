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
let currentSplashSteps = [];

// Coordinated boot & setup states
let hasBootInitiated = false;
let hasCompletedSetup = false;
let hasCheckedOnboarding = false;
let isWizardOpen = false;

// Global Arena Data & Polling States
let latestState = null;
let isPolling = false;
let chartMode = 'candles'; // 'candles' or 'line'
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
  { threshold: 15, text: "Initializing 6 Strategy Ledgers ($100,000 U x 6)..." },
  { threshold: 35, text: "Connecting to Real-Time Multi-Exchange Orderflow..." },
  { threshold: 55, text: "Replaying 120m Intraday Historical Simulation..." },
  { threshold: 75, text: "Translating & Synthesizing Global Macro Intelligence Digest (\u7e41\u9ad4\u4e2d\u6587)..." },
  { threshold: 90, text: "Pre-rendering Left K-Line Chart & Right Tactical Tables..." },
  { threshold: 100, text: "Arena Fully Loaded. Launching Live Arena..." }
];

const resetSplashSteps = [
  { threshold: 15, text: "Resetting 6 Strategy Portfolios ($100,000 U x 6)..." },
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

let isStartingLiveTrading = false;
async function ensureLiveTradingStarted() {
  if (isStartingLiveTrading) return;
  if (!window.pywebview || !window.pywebview.api || typeof window.pywebview.api.start_live_trading !== 'function') return;
  if (!latestState || !latestState.is_bootstrapped) return;
  if (latestState.live_orders_enabled) return;

  isStartingLiveTrading = true;
  try {
    const res = await window.pywebview.api.start_live_trading();
    if (res) {
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
    const splashStartTime = performance.now();
    const minSplashDurationMs = isReset ? 2200 : 2500;

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
    if (toastContainer) toastContainer.innerHTML = '';

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

    // If backend state is already populated/bootstrapped, advance smoothly to 100% across the 6 milestones
    if (latestState && latestState.is_bootstrapped) {
      setTimeout(() => setSplashTarget(35), 350);
      setTimeout(() => setSplashTarget(55), 800);
      setTimeout(() => setSplashTarget(75), 1300);
      setTimeout(() => setSplashTarget(90), 1800);
      setTimeout(() => {
        hasFirstChartDrawn = true;
        hasFirstTableRendered = true;
        setSplashTarget(100);
      }, 2350);
    }

    // Smooth animation loop for progress bar
    splashLoop = setInterval(() => {
      if (splashCompleted) {
        clearInterval(splashLoop);
        splashLoop = null;
        return;
      }

      const elapsedMs = performance.now() - splashStartTime;
      const canComplete = elapsedMs >= minSplashDurationMs;

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

        setTimeout(() => {
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
          setTimeout(() => {
            if (overlayEl) {
              overlayEl.style.display = 'none';
              overlayEl.classList.remove('fade-out');
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
          setTimeout(() => {
            overlayEl.style.display = 'none';
            overlayEl.classList.remove('fade-out');
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

function setSplashTarget(percent) {
  if (splashCompleted) return;
  targetSplashProgress = Math.min(100, Math.max(targetSplashProgress, percent));
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
    'comp_atr': 'ATR',
    'comp_trail': 'TRAIL',
    'comp_orb': 'ORB',
    'comp_vwap': 'VWAP'
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

function enqueueToast(toastItem) {
  if (!toastItem || typeof toastItem.renderElement !== 'function') return;
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

  toast._countdownInterval = setInterval(() => {
    if (toast._isDismissing) {
      clearInterval(toast._countdownInterval);
      toast._countdownInterval = null;
      return;
    }
    if (!toast._isPaused) {
      const elapsed = Date.now() - toast._startTime;
      toast._remainingMs = Math.max(0, toast._totalDurationMs - elapsed);
      if (ringFill) {
        const offset = RING_CIRCUMFERENCE * (1 - toast._remainingMs / toast._totalDurationMs);
        ringFill.style.strokeDashoffset = offset.toFixed(2);
      }
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
    'comp_atr': 'ATR Dynamic',
    'comp_trail': 'Trailing Guard',
    'comp_orb': 'ORB Breakout (15m)',
    'comp_vwap': 'Institutional VWAP'
  };
  const stratName = tagMap[strat.id] || strat.name || 'Quant Strategy';
  const sColor = strat.color || '#F59E0B';
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
  const title = opts.triggerReason || 'Arena Event';
  const priceStr = opts.price ? `$${Number(opts.price).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '';
  const action = opts.action || 'SYNC';
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
              <span class="side-verb up">${opts.symbol || 'ETH/USD'}</span>
            </div>
            <div class="toast-price-col">
              <span class="price-value" style="font-size:12px;">${priceStr}</span>
            </div>
          </div>
        </div>
      `;
      const closeBtn = toast.querySelector('.toast-close');
      if (closeBtn) {
        closeBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          toast.remove();
        });
      }
      return toast;
    }
  });
}

function createPositionClosedToastElement(strat, fill, prevPos) {
  const tagMap = {
    'comp_agg': 'Aggressive Momentum',
    'comp_cons': 'Conservative Scalper',
    'comp_atr': 'ATR Dynamic',
    'comp_trail': 'Trailing Guard',
    'comp_orb': 'ORB Breakout (15m)',
    'comp_vwap': 'Institutional VWAP'
  };
  const stratName = tagMap[strat.id] || strat.name || 'Quant Strategy';
  const trigger = (fill && fill.trigger) ? fill.trigger : 'Strategy Exit';
  const isTP = trigger.toLowerCase().includes('profit') || trigger.toLowerCase().includes('take profit');
  const isSL = trigger.toLowerCase().includes('loss') || trigger.toLowerCase().includes('stop loss');

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

  const timeStr = (fill && fill.time) ? fill.time : new Date().toTimeString().split(' ')[0];

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
          <span>Realized PnL: <strong>${pnlVal >= 0 ? '+' : ''}$${Math.abs(pnlVal).toFixed(2)}</strong></span>
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

function setChartMode(mode) {
  chartMode = mode;
  syncSegThumb('chartModeSeg', mode === 'candles' ? 0 : 1);
  const scrubEl = document.getElementById('chartScrubReadout');
  if (scrubEl) {
    scrubEl.textContent = mode === 'candles' ? '1m Candles' : 'Wave';
  }
  if (latestState) drawPriceChart(latestState);
}

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
  if (isPolling) return;
  if (isWizardOpen && !hasCompletedSetup) {
    // Hold background arena activity while initial setup wizard is open
    return;
  }
  isPolling = true;
  try {
    if (window.pywebview && window.pywebview.api) {
      checkOnboardingBoot();
      const useDelta = Boolean(latestState && typeof window.pywebview.api.get_state_delta === 'function');
      const state = useDelta
        ? await window.pywebview.api.get_state_delta(false)
        : await window.pywebview.api.get_state();
      if (state) {
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
              in_position: false,
              entry_price: 0,
              qty: 0,
              trades: 0,
              position_side: 'LONG'
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

            const isNewEntry = (isNowInPos && !wasInPos) ||
              (isNowInPos && wasInPos && curEntry > 0 && prevEntry > 0 && Math.abs(curEntry - prevEntry) > 0.05);

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
              position_side: s.position_side || 'LONG'
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
                const stratF = (f.strategy || '').toLowerCase();
                return stratF.includes(s.id.replace('comp_', '')) || sShort.includes(stratF);
              });
              showPositionClosedToast(s, latestExitFill, prev);
            });
          }
        }

        renderAll(state);
      }
    }
  } catch (err) {
    console.error("Bridge poll error:", err);
  } finally {
    isPolling = false;
  }
}

async function triggerEvolution() {
  if (!window.pywebview || !window.pywebview.api) return;
  const state = await window.pywebview.api.evolve_now();
  if (state) { latestState = state; renderAll(state); }
}

async function togglePause() {
  if (!window.pywebview || !window.pywebview.api) return;
  // Immediate optimistic toggle for zero-latency UI transition
  const willPause = !Boolean(latestState && latestState.paused);
  document.body.classList.toggle('arena-paused', willPause);
  const pauseBtn = document.getElementById('pauseBtn');
  if (pauseBtn) {
    const nextLbl = willPause ? 'Resume Feed' : 'Pause Feed';
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
  } else {
    latestState = { paused: willPause };
  }
  updateUiClockDisplay();

  const state = await window.pywebview.api.toggle_pause();
  if (state) {
    latestState = state;
    document.body.classList.toggle('arena-paused', Boolean(state.paused));
    renderAll(state);
  }
}

async function toggleAutoEvolve() {
  if (!window.pywebview || !window.pywebview.api) return;
  const state = await window.pywebview.api.toggle_auto_evolve();
  if (state) { latestState = state; renderAll(state); }
}

async function changeEvolveInterval(seconds) {
  if (!window.pywebview || !window.pywebview.api) return;
  const sec = parseInt(seconds, 10);
  if (isNaN(sec) || sec <= 0) return;
  const state = await window.pywebview.api.set_evolve_interval(sec);
  if (state) { latestState = state; renderAll(state); }
}

let isResettingArena = false;

async function resetArena() {
  if (!window.pywebview || !window.pywebview.api) return;
  if (isResettingArena || !splashCompleted) return;
  isResettingArena = true;

  // Reset local tracking states BEFORE starting splash sequence
  latestState = null;
  knownStrategyPositions = {};
  hasInitializedPositions = false;
  chartBeacons = [];
  lastRenderedFillSig = '';
  lastTopFillSeq = 0;

  // Immediately start the reload progress overlay to hide the teardown/rebuild
  startSplashSequence(true);

  try {
    const state = await window.pywebview.api.reset_arena();
    if (state) {
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
  renderTacticalHud(state);
  renderStrategies(state);
  renderLeaderboard(state);
  renderFills(state);
  renderIntelHub(state);
  drawPriceChart(state);

  // Verify right-side tables are mounted and populated with data
  const lbBody = document.getElementById('leaderboardBody');
  const stratGrid = document.getElementById('tabCardsView');
  if (lbBody && lbBody.children.length >= 6 && stratGrid && stratGrid.children.length >= 6) {
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
    badge.className = 'macro-badge ss-badge';
    if (mc.regime === 'BULLISH_SURGE') badge.classList.add('regime-bullish');
    else if (mc.regime === 'BEARISH_PANIC') badge.classList.add('regime-bearish');
    else if (mc.regime === 'HIGH_VOLATILITY_CHOP') badge.classList.add('regime-chop');
    
    const regimeLabels = {
      'NORMAL': '\u9ad4\u5236: \u5747\u8861\u5e38\u614b',
      'BULLISH_SURGE': '\u9ad4\u5236: \u591a\u982d\u5f37\u52e2',
      'BEARISH_PANIC': '\u9ad4\u5236: \u6050\u614c\u7194\u65b7',
      'HIGH_VOLATILITY_CHOP': '\u9ad4\u5236: \u9ad8\u6ce2\u9707\u76ea'
    };
    regimeTxt.textContent = regimeLabels[mc.regime] || ('\u9ad4\u5236: ' + mc.regime);
  }

  if (biasTag) {
    biasTag.textContent = mc.directional_bias || 'BIDIRECTIONAL';
    if (mc.directional_bias === 'LONG_ONLY') biasTag.style.color = '#4ADE80';
    else if (mc.directional_bias === 'SHORT_ONLY') biasTag.style.color = '#FB7185';
    else biasTag.style.color = '';
  }

  if (multTag) {
    multTag.textContent = (Number(mc.risk_multiplier) || 1.0).toFixed(2) + 'x';
  }

  if (vetoTag) {
    vetoTag.textContent = String(mc.veto_count_today || 0);
  }

  if (omniTag) {
    if (mc.status === 'ONLINE') {
      omniTag.textContent = '\u667a\u8166: \u9023\u7db2\u5728\u7dda (100k)';
      omniTag.style.color = '#10F5A0';
    } else {
      omniTag.textContent = '\u63a8\u8ad6: \u672c\u6a5f NLP \u6975\u901f';
      omniTag.style.color = '#38BDF8';
    }
  }

  if (headline) {
    headline.textContent = mc.active_headline || '\u5168\u7403\u8a02\u55ae\u6d41\u7dad\u6301\u5b8f\u89c0\u5747\u8861\u3002\u5be6\u6642\u667a\u80fd\u60c5\u5831\u76e3\u63a7\u904b\u884c\u4e2d\u3002';
  }

  // Populate central latest impactful catalyst news
  const evt = mc.latest_event;
  if (evt) {
    if (catalystHeadline) {
      catalystHeadline.textContent = evt.headline || evt.raw_title || '';
    }
    if (catalystSummary) {
      catalystSummary.textContent = evt.summary || '';
    }
    if (catalystTime) {
      catalystTime.textContent = (evt.source || 'Intel Feed') + ' \u00b7 ' + (evt.time || 'Live');
    }
    if (catalystImpact) {
      const acts = evt.strategy_actions;
      if (acts && acts.length > 0) {
        const a = acts[0];
        catalystImpact.textContent = '\u64cd\u4f5c: ' + a.name + ' ' + a.action;
        catalystImpact.className = 'catalyst-impact-pill ' + (a.badge_cls || 'buy');
      } else {
        if (mc.directional_bias === 'LONG_ONLY') {
          catalystImpact.textContent = '\u7b56\u7565\u653e\u884c: \u591a\u982d\u7a81\u7834 \u00b7 \u5426\u6c7a\u9006\u52e2\u7a7a\u55ae';
          catalystImpact.className = 'catalyst-impact-pill profit';
        } else if (mc.directional_bias === 'SHORT_ONLY') {
          catalystImpact.textContent = '\u7b56\u7565\u653e\u884c: \u9ed1\u5929\u9d5d\u7194\u65b7 \u00b7 \u5426\u6c7a\u9006\u52e2\u591a\u55ae';
          catalystImpact.className = 'catalyst-impact-pill loss';
        } else {
          catalystImpact.textContent = '\u7b56\u7565\u653e\u884c: 6\u5927\u7b56\u7565\u96d9\u5411\u5168\u958b \u00b7 \u57fa\u6e96\u904b\u4f5c';
          catalystImpact.className = 'catalyst-impact-pill info';
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
  document.getElementById('genLabel').textContent = `Gen #${state.generation}`;

  const isPaused = Boolean(state.paused);
  document.body.classList.toggle('arena-paused', isPaused);

  // Auto Evolve Countdown & Interval Sync
  const cdEl = document.getElementById('countdownLabel');
  const autoBtn = document.getElementById('autoEvolveToggleBtn');
  const intSelect = document.getElementById('evolveIntervalSelect');
  if (intSelect && state.auto_evolve_interval_sec) {
    const curVal = String(state.auto_evolve_interval_sec);
    if (intSelect.value !== curVal) {
      intSelect.value = curVal;
    }
  }

  const autoLbl = document.getElementById('autoEvolveLabelText');
  cdEl.textContent = fmtTimeSec(state.next_evolve_sec || 0);

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
    srcEl.textContent = 'Pure Math Core';
    srcEl.style.background = 'rgba(0, 242, 254, 0.14)';
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
    '* Architecture: Pure Math Deterministic Core (0 External AI Sockets)\n' +
    '* Strategy Evolution: Tournament Selection + Uniform Crossover\n' +
    '* Risk Mitigation: Monte Carlo EV Gate (10,000 Synthetic Paths)\n' +
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
  strategies.forEach(s => {
    const roiClass = s.roi_pct >= 0 ? 'up' : 'down';
    const upnlClass = s.unrealized_pnl >= 0 ? 'up' : 'down';
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
      const evBadge = (typeof s.expected_r === 'number' && Math.abs(s.expected_r) > 0.01)
        ? `<span class="ev-micro-pill num" title="Monte Carlo EV">${s.expected_r >= 0 ? '+' : ''}${s.expected_r.toFixed(1)}R</span>`
        : '';
      bracketHtml = `
          <div class="bracket-bar-wrap">
            <div class="bracket-track">
              <div class="bracket-fill" style="width:${pct.toFixed(1)}%;background:${s.color}"></div>
              <div class="bracket-marker" style="left:${pct.toFixed(1)}%;border-color:${s.color}"></div>
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
        const evVal = typeof s.expected_r === 'number' ? `${s.expected_r >= 0 ? '+' : ''}${s.expected_r.toFixed(2)}R` : '-';
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
      ? `<span class="lev-pill lev-active" title="Active Leverage">${s.leverage ? s.leverage.toFixed(1) : '2.0'}x</span>`
      : `<span class="lev-pill lev-spot" title="Spot Only">Spot 1x</span>`;

    const posPill = s.in_position
      ? (s.position_side === 'SHORT'
        ? `<span class="pos-badge in-pos-short">Short ${s.qty.toFixed(1)} ETH</span>`
        : `<span class="pos-badge in-pos">Long ${s.qty.toFixed(1)} ETH</span>`)
      : `<span class="pos-badge flat">Idle</span>`;

    const cardShortNames = {
      'comp_agg': 'Aggressive',
      'comp_cons': 'Conservative',
      'comp_orb': 'ORB Breakout',
      'comp_vwap': 'Inst. VWAP',
      'comp_atr': 'ATR Dynamic',
      'comp_trail': 'Trailing Guard'
    };
    const displayName = cardShortNames[s.id] || s.name;

    const pnlLabel = s.in_position ? 'Unrealized PnL' : 'Cash Balance';
    const pnlValue = s.in_position
      ? `<span class="${upnlClass}">${fmtSignedUsd(s.unrealized_pnl)}</span>`
      : `<span>${fmtUsd(s.cash, 0)}</span>`;

    const cardInner = `
        <span class="lg-strat-orb" aria-hidden="true"></span>
        <div class="strat-top">
          <div class="strat-left">
            <span class="rank-badge num" style="color:${s.color}">#${s.rank}</span>
            <span class="strat-title" title="${escapeHtml(s.name)}">${displayName}</span>
            <span class="strat-pill num">Gen #${s.generation} · ${s.genome}</span>
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
            <span class="${roiClass}">${fmtPct(s.roi_pct)}</span>
          </div>
          <div class="kpi-cell">
            <span>${pnlLabel}</span>
            ${pnlValue}
          </div>
          <div class="kpi-cell">
            <span>Win / Max DD</span>
            <span style="color:var(--ss-text)">${s.win_rate_pct.toFixed(0)}% / ${s.max_dd_pct.toFixed(1)}%</span>
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
    card.style.setProperty('--strat-color', s.color);
    if (card._lastHtml !== cardInner) {
      card._lastHtml = cardInner;
      card.innerHTML = cardInner;
    }
    if (!card.parentNode) {
      grid.appendChild(card);
    }
  });

  const currentCardOrder = Array.from(grid.children).map(el => el.dataset.stratId).join(',');
  const nextCardOrder = strategies.map(s => s.id).join(',');
  if (currentCardOrder !== nextCardOrder) {
    strategies.forEach(s => {
      const card = stratCardDomMap.get(s.id);
      if (card) grid.appendChild(card);
    });
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
    genSubEl.textContent = `EV Gate (${hVal}H)`;
  }

  // 5. AIMRAN uvq11-wg Liquid Vessel Fluid Level Synchronization (--lv)
  const setVesselLevel = (id, level) => {
    const tube = document.getElementById(id);
    if (!tube) return;
    const clamped = Math.max(0.14, Math.min(0.94, Number(level) || 0.5));
    tube.style.setProperty('--lv', clamped.toFixed(2));
    const card = tube.closest('.lg-vessel-card');
    if (card) card.style.setProperty('--lv', clamped.toFixed(2));
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

  const firstTops = new Map();
  strategies.forEach(s => {
    const el = leaderRowDomMap.get(s.id);
    if (el) firstTops.set(s.id, el.getBoundingClientRect().top);
  });

  const currentRowOrder = Array.from(tbody.children).map(el => el.dataset.stratId).join(',');
  const nextRowOrder = strategies.map(s => String(s.id)).join(',');
  const orderChanged = currentRowOrder !== nextRowOrder;

  const leadShortCodes = {
    'comp_agg': 'AGG',
    'comp_cons': 'CONS',
    'comp_atr': 'ATR',
    'comp_trail': 'TRAIL',
    'comp_orb': 'ORB',
    'comp_vwap': 'VWAP'
  };

  strategies.forEach(s => {
    const roiCls = s.roi_pct >= 0 ? 'up' : 'down';
    const upnlCls = s.unrealized_pnl >= 0 ? 'up' : 'down';
    const stratCode = leadShortCodes[s.id] || (s.name ? s.name.slice(0, 5) : 'STRAT');
    const rowInner = `
        <td style="font-weight:700;color:${s.color}">#${s.rank}</td>
        <td title="${escapeHtml(s.name)}">
          <span style="display:inline-flex;align-items:center;gap:4px;">
            <i style="width:5px;height:5px;border-radius:50%;background:${s.color};display:inline-block;flex-shrink:0;"></i>
            <span style="font-weight:700;color:var(--ss-text-strong);">${stratCode}</span>
          </span>
        </td>
        <td class="text-right" style="font-weight:700">${fmtUsd(s.equity, 0)}</td>
        <td class="text-right ${roiCls}">${fmtPct(s.roi_pct)}</td>
        <td class="text-right ${upnlCls}">${fmtSignedUsd(s.unrealized_pnl)}</td>
        <td class="text-right down">${s.max_dd_pct.toFixed(1)}%</td>
        <td class="text-right" style="color:var(--ss-text)" title="${s.closed_trades} trades">${s.win_rate_pct.toFixed(0)}%</td>
        <td class="text-right" style="color:var(--ss-text)">${s.sharpe.toFixed(1)}</td>
        <td class="text-right" style="font-weight:700">${s.fitness >= 0 ? '+' : ''}${s.fitness.toFixed(1)}</td>
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
    'ATR Dynamic Adaptive': 'ATR',
    'ATR Dynamic': 'ATR',
    'ATR': 'ATR',
    'Trailing Ratchet Guard': 'TRAIL',
    'Trailing Guard': 'TRAIL',
    'Opening Range Breakout': 'ORB',
    'ORB (15m)': 'ORB',
    'ORB': 'ORB',
    'Institutional VWAP Pullback': 'VWAP',
    'Institutional VWAP': 'VWAP',
    'Institutional': 'VWAP',
    'VWAP': 'VWAP'
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
        actionBadge = `<span class="${isBuy ? 'badge-buy' : 'badge-sell'}">${f.action_label}</span>`;
      }
    } else {
      actionBadge = isBuy
        ? '<span class="badge-buy">BUY</span>'
        : '<span class="badge-sell">SELL</span>';
    }

    const displaySeq = (f.seq !== undefined && f.seq !== null && f.seq > 0)
      ? (f.seq <= liveCount ? f.seq : (liveCount - idx))
      : (liveCount - idx);
    const seqStr = `#${displaySeq}`;
    const priceSubHtml = (!f.is_entry && f.entry_price)
      ? `<div style="font-size:8.5px;color:var(--ss-text-faint);font-weight:400;">Cost $${Number(f.entry_price).toFixed(2)}</div>`
      : '';

    const animCls = (idx === 0 && isNewTop) ? ' new-fill-row' : '';
    const sShort = stratShortMap[f.strategy] || (f.strategy ? f.strategy.slice(0, 5) : 'STRAT');
    const qtyStr = Number(f.qty) ? Number(f.qty).toFixed(2) : '0.00';

    return `
      <tr class="num${animCls}">
        <td style="color:var(--ss-text-faint);font-size:9.5px;">${seqStr}</td>
        <td style="color:var(--ss-text);white-space:nowrap;font-family:var(--font-mono);">${f.time}</td>
        <td style="font-weight:700;color:var(--ss-text-strong);white-space:nowrap;" title="${f.strategy}">${sShort}</td>
        <td style="white-space:nowrap;">${actionBadge}</td>
        <td class="text-right">${qtyStr}</td>
        <td class="text-right">${fmtUsd(f.price, 2)}${priceSubHtml}</td>
        <td class="text-right ${pnlCls}" style="font-weight:650;">${pnlStr}</td>
        <td style="color:var(--ss-text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" title="${f.trigger || f.reason || ''}">${f.trigger || f.reason || '—'}</td>
      </tr>
    `;
  }).join('');
}

/* HiDPI Vector Canvas Helpers */
function setupHiDPICanvas(canvas) {
  const dpr = Math.min(window.devicePixelRatio || 1, 2.0);
  const rect = (canvas.parentElement || canvas).getBoundingClientRect();
  const w = Math.max(200, Math.floor(rect.width));
  const h = Math.max(100, Math.floor(rect.height));
  if (canvas.width !== Math.floor(w * dpr) || canvas.height !== Math.floor(h * dpr)) {
    canvas.width = Math.floor(w * dpr);
    canvas.height = Math.floor(h * dpr);
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

/* Catmull-Rom / Cardinal Cubic Bézier Smooth Spline Interpolator for Silky Trend Lines */
function drawSmoothCurve(ctx, points, color, width, lineDash = []) {
  if (!points || points.length < 2) return;
  ctx.save();
  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  if (lineDash.length > 0) ctx.setLineDash(lineDash);
  ctx.beginPath();
  ctx.moveTo(points[0].x, points[0].y);

  if (points.length === 2) {
    ctx.lineTo(points[1].x, points[1].y);
    ctx.stroke();
    ctx.restore();
    return;
  }

  const tension = 0.28;
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = i > 0 ? points[i - 1] : points[i];
    const p1 = points[i];
    const p2 = points[i + 1];
    const p3 = i < points.length - 2 ? points[i + 2] : p2;

    const cp1x = p1.x + (p2.x - p0.x) * tension;
    const cp1y = p1.y + (p2.y - p0.y) * tension;
    const cp2x = p2.x - (p3.x - p1.x) * tension;
    const cp2y = p2.y - (p3.y - p1.y) * tension;

    ctx.bezierCurveTo(cp1x, cp1y, cp2x, cp2y, p2.x, p2.y);
  }
  ctx.stroke();
  ctx.restore();
}

/* Detailed Chart 1: Dynamic Auto-Scaled Price / Candles + Indicators + Levels (Stageshow Crafted Canvas) */
let priceHoverPos = null;
let hoveredCandleData = null;
let lastHoverIdx = -1;
let lastHoverSnapY = -1;
let chartAnimRaf = null;

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
  const useCandles = chartMode === 'candles' && rawCandles.length >= 2;
  const strategies = state.strategies || [];

  const quotePrice = Number((state.quote && state.quote.price) || 0);
  const lastClose = rawCandles.length > 0 ? Number(rawCandles[rawCandles.length - 1].c || 0) : 0;
  targetSpot = quotePrice > 0 ? quotePrice : (lastClose > 0 ? lastClose : 0);

  const canvas = document.getElementById('priceCanvas');
  const canvasW = canvas ? (canvas.clientWidth || 800) : 800;
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
  if (useCandles && targetCandles.length > 0) {
    targetCandles.forEach(c => {
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
        if (s.stop_loss && s.stop_loss > 0) minP = Math.min(minP, s.stop_loss);
        if (s.take_profit && s.take_profit > 0) maxP = Math.max(maxP, s.take_profit);
      }
    });
  }

  const span = Math.max(25.0, maxP - minP);
  targetMinP = minP - span * 0.16;
  targetMaxP = maxP + span * 0.16;

  // Bootstrap values on initial load
  if (animSpot === 0) animSpot = targetSpot;
  if (animMinP === 0) animMinP = targetMinP;
  if (animMaxP === 0) animMaxP = targetMaxP;
  if (animCandles.length === 0 && targetCandles.length > 0) {
    animCandles = targetCandles.map(c => ({ o: c.o, h: c.h, l: c.l, c: c.c, t: c.t }));
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
  if (!latestState) return;
  if (latestState.paused) {
    renderPriceCanvas(latestState, animCandles, animSpot, animMinP, animMaxP);
    return;
  }

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
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = '#080c13';
  ctx.fillRect(0, 0, w, h);

  const rawPrices = state.price_history || [];
  const ema9 = state.ema_fast_history || [];
  const ema21 = state.ema_slow_history || [];
  const strategies = state.strategies || [];
  const useCandles = chartMode === 'candles' && visibleCandles.length >= 2;

  const padLeft = 12;
  const padRight = 98;
  const padTop = 16;
  const padBottom = 22;
  const plotW = Math.max(50, w - padLeft - padRight);
  const plotH = Math.max(40, h - padTop - padBottom);
  const candleRightOffset = 80;
  const candlePlotW = Math.max(50, plotW - candleRightOffset);

  const toY = (v) => padTop + (1 - (v - minP) / (maxP - minP)) * plotH;

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
    'comp_atr': 'ATR',
    'comp_trail': 'TRAIL',
    'comp_orb': 'ORB',
    'comp_vwap': 'VWAP'
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

    visibleCandles.forEach((c, i) => {
      if (c.h > maxC.h) { maxC = c; maxIdx = i; }
      if (c.l < minC.l) { minC = c; minIdx = i; }

      const cx = startX + (i + 0.5) * step + shiftX;
      if (i === n - 1) activeHeadX = cx;

      const isUp = c.c >= c.o;
      const bodyColor = isUp ? '#00E676' : '#FF334B';
      const wickColor = isUp ? 'rgba(0, 230, 118, 0.85)' : 'rgba(255, 51, 75, 0.85)';
      const yOpen = toY(c.o);
      const yClose = toY(c.c);
      const yHigh = toY(c.h);
      const yLow = toY(c.l);

      // Wick
      ctx.strokeStyle = wickColor;
      ctx.lineWidth = 1.25;
      ctx.beginPath();
      ctx.moveTo(cx, yHigh);
      ctx.lineTo(cx, yLow);
      ctx.stroke();

      // Rounded Candle Body
      ctx.fillStyle = bodyColor;
      const topY = Math.min(yOpen, yClose);
      const bHeight = Math.max(2.5, Math.abs(yClose - yOpen));
      fillRoundRect(ctx, cx - bodyW / 2, topY, bodyW, bHeight, 1.5);
    });

    // Overlay Silky Smooth Bézier Spline EMA lines
    const drawCandleEma = (emaArr, color, width = 1.6, lineDash = []) => {
      if (!emaArr || emaArr.length < 2) return;
      const sliceEma = emaArr.slice(-n);
      const offset = Math.max(0, n - sliceEma.length);
      const pts = [];
      for (let i = 0; i < sliceEma.length; i++) {
        pts.push({
          x: startX + (offset + i + 0.5) * step + shiftX,
          y: toY(sliceEma[i])
        });
      }
      drawSmoothCurve(ctx, pts, color, width, lineDash);
    };

    drawCandleEma(ema21, '#FFB800', 1.4);
    drawCandleEma(ema9, '#38BDF8', 1.6);

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
  } else if (rawPrices.length >= 2) {
    const n = Math.min(80, rawPrices.length);
    const visiblePrices = rawPrices.slice(-n);
    const toX = (i) => padLeft + (i / (n - 1)) * candlePlotW;
    activeHeadX = toX(n - 1);

    const drawLine = (arr, color, width, lineDash = []) => {
      if (!arr || arr.length < 2) return;
      const sliceArr = arr.slice(-n);
      const offset = Math.max(0, n - sliceArr.length);
      const pts = [];
      for (let i = 0; i < sliceArr.length; i++) {
        pts.push({
          x: toX(offset + i),
          y: toY(sliceArr[i])
        });
      }
      drawSmoothCurve(ctx, pts, color, width, lineDash);
    };

    drawLine(ema21, '#FFB800', 1.4);
    drawLine(ema9, '#38BDF8', 1.5);
    drawLine(visiblePrices, '#F2F3F5', 2.0);
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
        ctx.setLineDash([4, 4]);
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
        ctx.setLineDash([2, 3]);
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
        ctx.setLineDash([4, 4]);
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

  // 3b. Institutional Indicators (VWAP & ORB Range Reference Lines)
  const ind = state.indicators || {};
  const vwapVal = Number(ind.vwap || 0);
  if (vwapVal >= minP && vwapVal <= maxP) {
    const vy = toY(vwapVal);
    ctx.save();
    ctx.strokeStyle = 'rgba(20, 241, 149, 0.65)';
    ctx.setLineDash([4, 4]);
    ctx.lineWidth = 1.25;
    ctx.beginPath();
    ctx.moveTo(padLeft, vy);
    ctx.lineTo(padLeft + plotW, vy);
    ctx.stroke();
    ctx.restore();

    rightBadges.push({
      rawY: vy,
      price: vwapVal,
      stratTag: 'VWAP',
      subTag: '',
      label: `$${vwapVal.toFixed(0)}`,
      color: '#14F195',
      stratColor: '#14F195',
      type: 'vwap'
    });
  }

  const orbHigh = Number(ind.orb_high || 0);
  const orbLow = Number(ind.orb_low || 0);
  if (orbHigh > 0 && orbHigh >= minP && orbHigh <= maxP) {
    const ohy = toY(orbHigh);
    ctx.save();
    ctx.strokeStyle = 'rgba(168, 85, 247, 0.58)';
    ctx.setLineDash([3, 3]);
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
    ctx.setLineDash([3, 3]);
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
    ctx.setLineDash([3, 3]);
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
      ctx.setLineDash([2, 2]);
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
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(padLeft, priceHoverPos.y);
      ctx.lineTo(padLeft + plotW, priceHoverPos.y);
      ctx.stroke();
    }

    if (hoveredCandleData) {
      const cy = toY(hoveredCandleData.c);
      ctx.setLineDash([]);
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
  let target = null;
  if (evt.clientX !== undefined && evt.clientY !== undefined) {
    target = document.elementFromPoint(evt.clientX, evt.clientY);
  }
  if (!target && evt.target) {
    target = evt.target;
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

window.addEventListener('pointermove', (e) => {
  latestPointerEvent = e;
  lastGlobalPointerX = e.clientX;
  lastGlobalPointerY = e.clientY;
  document.documentElement.style.setProperty('--gx', `${e.clientX}px`);
  document.documentElement.style.setProperty('--gy', `${e.clientY}px`);
  if (!spotlightRaf) {
    spotlightRaf = requestAnimationFrame(() => {
      spotlightRaf = null;
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
    const useCandles = chartMode === 'candles' && candles.length >= 2;
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
        tip.innerHTML = `
            <div style="font-weight:600;color:var(--ss-text);margin-bottom:2px;">${tStr} · 1m Candle</div>
            <div>O <strong>$${c.o.toFixed(1)}</strong> · H <strong>$${c.h.toFixed(1)}</strong></div>
            <div>L <strong>$${c.l.toFixed(1)}</strong> · C <strong class="${isUp ? 'up' : 'down'}">$${c.c.toFixed(1)} (${isUp ? '+' : ''}${chg}%)</strong></div>
          `;
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
      scrubEl.textContent = chartMode === 'candles' ? '1m Candles' : 'Wave';
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
      scrubEl.textContent = chartMode === 'candles' ? '1m Candles' : 'Wave';
    }
    if (latestState) drawPriceChart(latestState);
  });
}

// Fluid ResizeObserver with 60 FPS requestAnimationFrame throttling
let resizeRaf = null;
const triggerSmoothResize = () => {
  if (resizeRaf) cancelAnimationFrame(resizeRaf);
  resizeRaf = requestAnimationFrame(() => {
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

window.addEventListener('keydown', function (e) {
  if (e.key === 'F11' || e.code === 'F11' || e.keyCode === 122) {
    e.preventDefault();
    e.stopPropagation();
    toggleFullscreen();
    return;
  }
  const tag = (e.target && e.target.tagName) ? e.target.tagName.toUpperCase() : '';
  if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA' || e.ctrlKey || e.altKey || e.metaKey) {
    return;
  }
  if (e.code === 'Space') {
    e.preventDefault();
    togglePause();
  } else if (e.code === 'Digit1' || e.key === '1') {
    switchMainView('arena');
  } else if (e.code === 'Digit2' || e.key === '2') {
    switchMainView('intel');
  } else if (e.code === 'KeyE' || e.key === 'e' || e.key === 'E') {
    triggerEvolution();
  } else if (e.code === 'KeyC' || e.key === 'c' || e.key === 'C') {
    setChartMode(chartMode === 'candles' ? 'line' : 'candles');
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
    const showNetOverlay = isOffline && document.body && document.body.classList.contains('arena-ready');
    netOverlay.classList.toggle('modal-visible', showNetOverlay);
  }

  const clockEl = document.getElementById('isoClockDisplay');
  if (!isPaused) {
    const now = new Date();
    const hh = String(now.getHours()).padStart(2, '0');
    const mm = String(now.getMinutes()).padStart(2, '0');
    const ss = String(now.getSeconds()).padStart(2, '0');
    const timeStr = `${hh}:${mm}:${ss}`;
    if (clockEl) {
      clockEl.textContent = timeStr;
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
        clockEl.textContent = clockEl._frozenTimeStr;
      }
    }

    const badgeEl = document.querySelector('.clock-cadence-badge');
    if (badgeEl) {
      if (isPaused) {
        badgeEl.textContent = 'PAUSED';
        badgeEl.style.background = 'rgba(255, 51, 75, 0.22)';
        badgeEl.style.color = '#FF334B';
        badgeEl.style.borderColor = 'rgba(255, 51, 75, 0.55)';
      } else if (isOffline) {
        badgeEl.textContent = 'OFFLINE';
        badgeEl.style.background = 'rgba(255, 170, 0, 0.22)';
        badgeEl.style.color = '#FFAA00';
        badgeEl.style.borderColor = 'rgba(255, 170, 0, 0.55)';
      } else {
        badgeEl.textContent = 'LIVE';
        badgeEl.style.background = 'rgba(16, 245, 160, 0.22)';
        badgeEl.style.color = '#10F5A0';
        badgeEl.style.borderColor = 'rgba(16, 245, 160, 0.45)';
      }
    }

    const subEl = document.getElementById('sourceSubtitle');
    if (subEl) {
      if (isPaused) {
        subEl.textContent = 'Feed Simulation Paused · Standing By';
      } else if (isOffline) {
        subEl.textContent = 'Exchange Feed Offline · Reconnecting...';
      } else {
        subEl.textContent = 'Realtime Stream · $600,000 Arena Pool';
      }
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
      }
      if (latestState) renderIntelHub(latestState);
    } else {
      if (intelEl) intelEl.style.display = 'none';
      if (arenaEl) {
        arenaEl.style.display = 'grid';
        arenaEl.classList.remove('view-entering');
        void arenaEl.offsetWidth;
        arenaEl.classList.add('view-entering');
      }
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

    if (typeof showChartToast === 'function') {
      showChartToast({
        triggerReason: 'Refreshing Macro AI Digest & News Intelligence...',
        action: 'INTEL'
      });
    }

    try {
      if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.refresh_intel_digest === 'function') {
        const state = await window.pywebview.api.refresh_intel_digest();
        if (state) {
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
          <span>Refresh AI Digest</span>
        `;
        }
      }, 1000);
    }
  }
  window.requestAiIntelDigest = requestAiIntelDigest;

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
      // Item 12 / A3 option 2: when the current regime came from the local
      // keyword fallback, say so on the pill instead of generic STANDBY.
      const isFallback = macro.fallback === true;
      const nextPillHtml = `<span class="ss-badge__dot"></span><span class="ss-badge__label">${isOnline ? 'ONLINE (24/7)' : (isFallback ? 'STANDBY / KEYWORD FALLBACK' : 'STANDBY / LOCAL NLP')}</span>`;
      if (statusPill._lastHtml !== nextPillHtml) {
        statusPill.innerHTML = nextPillHtml;
        statusPill._lastHtml = nextPillHtml;
      }
    }

    const epEl = document.getElementById('omniEndpointVal');
    if (epEl) epEl.textContent = omni.endpoint || 'http://localhost:20128/v1';

    const tokensEl = document.getElementById('omniTokensVal');
    if (tokensEl) {
      const used = (omni.tokens_used || 0).toLocaleString();
      const saved = (omni.tokens_saved || 0).toLocaleString();
      tokensEl.textContent = `${used} used / ${saved} saved`;
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
      tokensSub.textContent = (typeof hits === 'number' && hits > 0)
        ? `${hits.toLocaleString()} dupes skipped (SHA-256)`
        : `${pct}% SHA-256 Dedup Saved`;
      // The Remaining Quota cell was removed (2026-11-13); the digest
      // throttle note (item 12 / A4-4) moves here so it stays visible.
      if (omni.quota_throttled === true) {
        tokensSub.textContent += ' — Digest throttled';
      }
    }

    const ingEl = document.getElementById('omniIngestModel');
    if (ingEl) ingEl.textContent = omni.model_ingest || 'auto';

    const cmdEl = document.getElementById('omniCommanderModel');
    if (cmdEl) cmdEl.textContent = omni.model_commander || 'auto';

    const reqEl = document.getElementById('omniReqCounters');
    if (reqEl) {
      reqEl.textContent = `Reqs: ${omni.total_requests || 0} | OK: ${omni.successful_requests || 0} | Fail: ${omni.failed_requests || 0}`;
    }

    // 2. Macro Regime Card
    const regBadge = document.getElementById('macroRegimeHubBadge');
    if (regBadge) {
      const reg = (macro.regime || 'NORMAL').toUpperCase();
      let cls = 'neutral';
      if (reg.includes('SURGE')) cls = 'surge';
      else if (reg.includes('PANIC') || reg.includes('CHOP')) cls = 'standby';
      regBadge.className = `intel-status-pill ss-badge ${cls}`;
      regBadge.textContent = reg;
    }

    const biasEl = document.getElementById('macroHubBias');
    if (biasEl) biasEl.textContent = macro.directional_bias || 'BIDIRECTIONAL';

    const biasSub = document.getElementById('macroHubBiasSub');
    if (biasSub) {
      const b = macro.directional_bias || 'BIDIRECTIONAL';
      if (b === 'LONG_ONLY') biasSub.textContent = 'Strict Veto Active: All Short Trades Blocked';
      else if (b === 'SHORT_ONLY') biasSub.textContent = 'Strict Veto Active: All Long Trades Blocked';
      else if (b === 'HOLD_CASH') biasSub.textContent = 'Severe Risk-Off: All Opening Orders Blocked';
      else biasSub.textContent = 'All 6 Arena Strategies Permitted';
    }

    const multEl = document.getElementById('macroHubRiskMult');
    if (multEl) multEl.textContent = `${Number(macro.risk_multiplier || 1.0).toFixed(2)}x`;

    const confEl = document.getElementById('macroHubConfidence');
    if (confEl) confEl.textContent = `${Math.round(Number(macro.confidence || 0.8) * 100)}%`;

    const lastEval = document.getElementById('macroHubLastEval');
    if (lastEval) lastEval.textContent = `Last Eval: ${macro.last_synthesis_time || 'Continuous'}`;

    const vetoEl = document.getElementById('macroHubVetoCount');
    if (vetoEl) vetoEl.textContent = String(macro.veto_count_today || 0);

    const headEl = document.getElementById('macroHubHeadline');
    if (headEl) headEl.textContent = macro.active_headline || 'Market in balanced equilibrium.';

    // 3. Curated Event Cards
    const countLbl = document.getElementById('intelEventCountLabel');
    if (countLbl) countLbl.textContent = `${events.length} Curated Events`;

    const listContainer = document.getElementById('intelEventsList');
    if (listContainer) {
      if (currentMainView !== 'intel' && listContainer.children.length > 0) {
        // Hub panel is hidden; preserve existing DOM nodes to save rendering cycles
      } else if (events.length === 0) {
        const emptyHtml = '<div style="color:var(--ss-text-faint);font-size:12px;padding:24px;text-align:center;">Synchronizing multi-domain live intelligence stream...</div>';
        if (listContainer._lastHtml !== emptyHtml) {
          listContainer.innerHTML = emptyHtml;
          listContainer._lastHtml = emptyHtml;
        }
      } else {
        const nextEventsHtml = events.map(evt => {
          const sent = Number(evt.sentiment || 0);
          let sentCls = 'neutral', sentTxt = `${sent >= 0 ? '+' : ''}${sent.toFixed(2)} Neutral`;
          if (sent > 0.2) { sentCls = 'bullish'; sentTxt = `+${sent.toFixed(2)} Bullish`; }
          else if (sent < -0.2) { sentCls = 'bearish'; sentTxt = `${sent.toFixed(2)} Bearish`; }

          const urg = Number(evt.urgency || 5);
          const urgBadge = urg >= 8
            ? `<span class="intel-urgency-badge num">URG ${urg}/10 CRITICAL</span>`
            : `<span class="intel-domain-badge num">URG ${urg}/10</span>`;

          const actions = evt.strategy_actions || [];
          let actionsHtml = '';
          if (actions.length > 0) {
            actionsHtml = actions.map(act => {
              const bCls = act.badge_cls || 'neutral';
              return `<span class="strat-action-pill ${bCls}">
                <strong>${escapeHtml(act.name)}</strong>: ${escapeHtml(act.action)} <small style="opacity:0.75;">(${escapeHtml(act.time || '')})</small>
              </span>`;
            }).join('');
          } else {
            actionsHtml = `<span class="strat-action-pill neutral">Strategies 1~6: Active Monitoring under ${escapeHtml(macro.directional_bias || 'BIDIRECTIONAL')} Directive</span>`;
          }

          return `
            <div class="intel-event-card lg-spot-card">
              <div class="intel-card-header">
                <span class="intel-event-time num">${escapeHtml(evt.time || '')}</span>
                <span class="intel-domain-badge">${escapeHtml((evt.domain || 'macro').toUpperCase())}</span>
                <span class="intel-source-badge">${escapeHtml(evt.source || 'News Wire')}</span>
                ${urgBadge}
                <span class="intel-sentiment-badge num ${sentCls}">${sentTxt}</span>
              </div>
              <div class="intel-card-headline">${escapeHtml(evt.headline || '')}</div>
              <div class="intel-card-summary">${escapeHtml(evt.summary || '')}</div>
              <div class="intel-strategy-actions-box">
                <div class="intel-strategy-box-title">Arena Competitor Impact (Strategies 1 ~ 6)</div>
                <div class="strat-actions-wrap">
                  ${actionsHtml}
                </div>
              </div>
            </div>
          `;
        }).join('');
        if (listContainer._lastHtml !== nextEventsHtml) {
          listContainer.innerHTML = nextEventsHtml;
          listContainer._lastHtml = nextEventsHtml;
        }
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
      const updateIntelCardSpotlight = (e) => {
        const card = e.target.closest('.intel-event-card');
        if (card) {
          const r = card.getBoundingClientRect();
          const lx = Math.round(e.clientX - r.left);
          const ly = Math.round(e.clientY - r.top);
          card.style.setProperty('--x', `${lx}px`);
          card.style.setProperty('--y', `${ly}px`);
          card.style.setProperty('--mx', `${lx}px`);
          card.style.setProperty('--my', `${ly}px`);
        }
      };
      iList.addEventListener('pointermove', updateIntelCardSpotlight, { passive: true });
      iList.addEventListener('pointerenter', updateIntelCardSpotlight, true);
    }

    const bentoDock = document.getElementById('tabCardsView');
    if (bentoDock) {
      const updateBentoSpotlight = (e) => {
        const card = e.target.closest('.strat-card-mini');
        if (card) {
          const r = card.getBoundingClientRect();
          const lx = Math.round(e.clientX - r.left);
          const ly = Math.round(e.clientY - r.top);
          card.style.setProperty('--x', `${lx}px`);
          card.style.setProperty('--y', `${ly}px`);
          card.style.setProperty('--mx', `${lx}px`);
          card.style.setProperty('--my', `${ly}px`);
        }
      };
      bentoDock.addEventListener('pointermove', updateBentoSpotlight, { passive: true });
      bentoDock.addEventListener('pointerenter', updateBentoSpotlight, true);
    }

    window.addEventListener('resize', triggerSmoothResize);

    setTimeout(pollBackend, 120);
    window.pollIntervalTimer = setInterval(pollBackend, 1000);
  });

  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && !isPolling) {
      pollBackend();
    }
  });

  /* ==========================================================================
     SHUTDOWN & PROGRESS PERSISTENCE MODAL CONTROLLERS
     ========================================================================== */
  function requestShutdown() {
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
      setTimeout(() => {
        modal.style.display = 'none';
        modal.classList.remove('modal-closing');
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
    const modal = document.getElementById('setupWizardModal');
    const closeBtn = document.getElementById('btnWizardClose');
    if (closeBtn) {
      closeBtn.style.display = canDismiss ? 'flex' : 'none';
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
      deepseek: 'DeepSeek',
      gemini: 'Gemini',
      groq: 'Groq',
      openrouter: 'OpenRouter'
    };

    if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.get_setup_status === 'function') {
      window.pywebview.api.get_setup_status().then((res) => {
        if (res && res.status === 'ok') {
          const configured = res.configured_providers || [];
          Object.entries(provIdMap).forEach(([pKey, domId]) => {
            const stEl = document.getElementById(`status${domId}`);
            if (stEl) {
              if (configured.includes(pKey)) {
                stEl.innerHTML = '<span class="setup-status-pill valid">Configured in .env</span>';
              } else {
                stEl.innerHTML = '<span class="setup-status-pill neutral">Not Configured</span>';
              }
            }
          });

          const chk = document.getElementById('chkAutoSpawnGateway');
          if (chk && typeof res.gateway_auto_spawn === 'boolean') {
            chk.checked = res.gateway_auto_spawn;
          }

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
              ? '<span class="setup-status-pill valid">Configured in .env</span>'
              : '<span class="setup-status-pill neutral">Not Set - Required</span>';
          }

          applyGatewayAvailability(res);
          updateRuntimeInstallBanner(res.runtime_install_status);
        }
      }).catch((e) => console.debug('get_setup_status err:', e));
    }
  }

  function closeSetupWizardModal() {
    const modal = document.getElementById('setupWizardModal');
    if (modal) {
      modal.classList.remove('wizard-visible');
      modal.classList.add('wizard-closing');
      isWizardOpen = false;
      setTimeout(() => {
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
    // copies it to the OS clipboard server-side and only reports success,
    // so the button can truthfully show "copied!" again.
    const showEnvHint = () => {
      if (typeof showChartToast === 'function') {
        showChartToast({ triggerReason: 'Admin password is stored in ~/.omniroute/.env', action: 'INFO' });
      }
    };
    if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.copy_omniroute_password === 'function') {
      window.pywebview.api.copy_omniroute_password().then((res) => {
        if (res && res.status === 'ok') {
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
        closeSetupWizardModal();
      }
    }
  }

  function setWizardBanner(message, type = 'info') {
    const b = document.getElementById('setupWizardStatusBanner');
    if (!b) return;
    if (!message) {
      b.style.display = 'none';
      b.textContent = '';
      return;
    }
    b.className = `setup-wizard-banner ${type}`;
    b.textContent = message;
    b.style.display = 'block';
  }

  let runtimeInstallPollTimer = null;

  // Gateway availability (item 10 A4): show the reason + one-click install
  // button when Node.js / OmniRoute is missing; hide both when available.
  function applyGatewayAvailability(res) {
    if (!res) return;
    if (typeof res.gateway_port === 'number') {
      window.__tradebotGatewayPort = res.gateway_port;
    }
    const gwNote = document.getElementById('gatewayUnavailableNote');
    const gwBtn = document.getElementById('btnInstallGatewayRuntime');
    if (gwNote) {
      if (res.gateway_unavailable_reason) {
        gwNote.textContent = res.gateway_unavailable_reason + ' The arena still works in Pure Math mode meanwhile.';
        gwNote.style.display = 'block';
      } else {
        gwNote.style.display = 'none';
        gwNote.textContent = '';
      }
    }
    if (gwBtn) {
      gwBtn.style.display = res.gateway_unavailable_reason ? 'inline-flex' : 'none';
    }
  }

  function updateRuntimeInstallBanner(statusObj) {
    if (!statusObj) return;
    const st = statusObj.status || 'idle';
    const msg = statusObj.message || '';
    if (st === 'idle') return;
    if (st === 'done') {
      setWizardBanner(msg || 'OmniRoute installed.', 'success');
      if (runtimeInstallPollTimer) { clearInterval(runtimeInstallPollTimer); runtimeInstallPollTimer = null; }
      refreshGatewayAvailability();
    } else if (st === 'failed') {
      setWizardBanner(msg || 'Installation failed.', 'error');
      if (runtimeInstallPollTimer) { clearInterval(runtimeInstallPollTimer); runtimeInstallPollTimer = null; }
      const btn = document.getElementById('btnInstallGatewayRuntime');
      if (btn) btn.disabled = false;
    } else {
      setWizardBanner(msg || 'Installing...', 'info');
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
          if (runtimeInstallPollTimer) clearInterval(runtimeInstallPollTimer);
          runtimeInstallPollTimer = setInterval(() => {
            if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.get_setup_status === 'function') {
              window.pywebview.api.get_setup_status().then((r) => {
                if (r && r.status === 'ok') updateRuntimeInstallBanner(r.runtime_install_status);
              }).catch((e) => console.debug('install poll err:', e));
            }
          }, 5000);
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
      deepseek: 'DeepSeek',
      gemini: 'Gemini',
      groq: 'Groq',
      openrouter: 'OpenRouter'
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
          if (stEl) stEl.innerHTML = `<span class="setup-status-pill valid">&#x2713; ${res.message || 'Verified'}</span>`;
        } else {
          const msg = (res && res.message) ? res.message : 'Verification failed';
          if (stEl) stEl.innerHTML = `<span class="setup-status-pill error">&#x2717; ${msg}</span>`;
        }
      } else {
        setTimeout(() => {
          if (stEl) stEl.innerHTML = '<span class="setup-status-pill valid">&#x2713; Format Accepted (Preview)</span>';
        }, 400);
      }
    } catch (err) {
      if (stEl) stEl.innerHTML = '<span class="setup-status-pill error">&#x2717; Network error</span>';
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  async function saveAndLaunchGateway() {
    const saveBtn = document.getElementById('btnSaveAndLaunch');
    const chk = document.getElementById('chkAutoSpawnGateway');
    const autoSpawn = chk ? chk.checked : true;

    const keys = {
      deepseek: (document.getElementById('keyDeepSeek')?.value || '').trim(),
      gemini: (document.getElementById('keyGemini')?.value || '').trim(),
      groq: (document.getElementById('keyGroq')?.value || '').trim(),
      openrouter: (document.getElementById('keyOpenRouter')?.value || '').trim(),
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

    if (saveBtn) {
      saveBtn.disabled = true;
      saveBtn.innerHTML = '<span>Saving &amp; Launching...</span>';
    }
    setWizardBanner('Synchronizing credentials with local gateway...', 'info');

    try {
      if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.save_and_launch_gateway === 'function') {
        const res = await window.pywebview.api.save_and_launch_gateway(keys, autoSpawn, adminPw || null);
        if (res && res.ok) {
          hasCompletedSetup = true;
          setWizardBanner(res.message || 'Credentials saved successfully!', 'success');
          setTimeout(() => {
            closeSetupWizardModal();
            if (!splashCompleted) {
              startSplashSequence(false);
              setSplashTarget(75);
            } else {
              if (typeof showChartToast === 'function') {
                showChartToast({
                  strategyId: 'comp_cons',
                  action: 'BUY',
                  symbol: 'ETH/USD',
                  price: (latestState && latestState.quote && latestState.quote.price) || (latestState && latestState.candles && latestState.candles.length > 0 ? latestState.candles[latestState.candles.length - 1].c : 2650.0),
                  qty: 0,
                  triggerReason: 'API Credentials & Gateway Synchronized',
                  timestamp: Date.now()
                });
              }
            }
          }, 400);
        } else {
          setWizardBanner((res && res.message) ? res.message : 'Failed to launch gateway', 'error');
        }
      } else {
        hasCompletedSetup = true;
        setWizardBanner('Configured in mock mode. Launching arena...', 'success');
        setTimeout(() => {
          closeSetupWizardModal();
          if (!splashCompleted) {
            startSplashSequence(false);
            setSplashTarget(75);
          }
        }, 400);
      }
    } catch (err) {
      setWizardBanner(`Encountered error: ${err}`, 'error');
    } finally {
      if (saveBtn) {
        saveBtn.disabled = false;
        saveBtn.innerHTML = '<span>Save &amp; Launch Arena</span>';
      }
    }
  }

  async function skipToPureMathCore() {
    setWizardBanner('Activating 100% Pure Math Deterministic Core...', 'info');
    try {
      if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.skip_to_pure_math === 'function') {
        await window.pywebview.api.skip_to_pure_math();
      }
    } catch (err) {
      console.debug('skip_to_pure_math err:', err);
    }
    hasCompletedSetup = true;
    closeSetupWizardModal();
    if (!splashCompleted) {
      startSplashSequence(false);
      setSplashTarget(75);
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
      closeShutdownModal();
      closeResetModal();
      const closeBtn = document.getElementById('btnWizardClose');
      if (closeBtn && closeBtn.style.display !== 'none') {
        closeSetupWizardModal();
      }
    }
  });

  /* ==========================================================================
     RESET CONFIRMATION MODAL CONTROLLERS
     ========================================================================== */
  function requestResetArena() {
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
      setTimeout(() => {
        modal.style.display = 'none';
        modal.classList.remove('modal-closing');
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

