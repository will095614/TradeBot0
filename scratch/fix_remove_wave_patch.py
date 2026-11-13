# fix_remove_wave_patch.py — 完全移除 Wave 趨勢線兩條＋Candles/Wave 切換撥桿（2026-11-13，使用者指示）。
# 「Wave 趨勢線兩條」= 兩條平滑 EMA 趨勢線（EMA 9 藍 #38BDF8、EMA 21 琥珀 #FFB800）：
# 它們在 K 線模式以 drawCandleEma 疊加在 K 線上（app.js:2295-2296），在 Wave
# 模式以 drawLine 繪製（app.js:2329-2330）。兩處一併移除，才算完全移除。
# 連帶移除整個 Wave 模式（已無入口）：chartMode 變數、setChartMode、鍵盤 C 切換、
# scrubEl 的 Wave 字樣、chartModeSeg 撥桿（index.html）、圖例 EMA 9／EMA 21 兩項、
# 以及失效後無人呼叫的 drawSmoothCurve（Catmull-Rom spline）。
# 刻意保留：Focus／Full 撥桿與 F 鍵、MEAN 圖例、策略 TP／Entry／SL 虛線、進場 beacon、
# LIVE badge 的 lg-wave-bars 動畫與 meniscus 波紋裝飾（與 Wave 模式無關）。
# 注意：K 線不足 2 根時圖表區原本走 Wave 分支顯示價格線，移除後該情況只顯示
# 網格／軸線／策略水平線，直到 K 線載入（bootstrap 會載入 120 分鐘歷史，開場
# splash 期間即完成，實務上幾乎看不到空圖）。
# 每個 replacement 寫入前驗證在目標檔中精確匹配一次。
import os

ROOT = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
BASE = None
for c in [os.getcwd(), ROOT, os.path.dirname(ROOT)]:
    if os.path.isfile(os.path.join(c, "src", "gui", "assets", "index.html")):
        BASE = c
        break
if BASE is None:
    BASE = os.getcwd()


def load(path):
    with open(path, "rb") as f:
        raw = f.read()
    crlf = b"\r\n" in raw
    return raw.decode("utf-8"), crlf


def save(path, text, crlf):
    data = text.replace("\n", "\r\n") if crlf else text
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(data)


def replace_once(path, old, new, label):
    text, crlf = load(path)
    n = text.count(old)
    assert n == 1, f"{label}: expected exactly 1 match in {path}, found {n}"
    save(path, text.replace(old, new), crlf)
    print(f"OK {label}")


APPJS = os.path.join(BASE, "src", "gui", "assets", "app.js")
INDEX = os.path.join(BASE, "src", "gui", "assets", "index.html")

# --- app.js ---
# 1. chartMode 變數
replace_once(
    APPJS,
    "let chartMode = 'candles'; // 'candles' or 'line'\n",
    "",
    "remove chartMode variable",
)
# 2. setChartMode 整函數
replace_once(
    APPJS,
    """function setChartMode(mode) {
  chartMode = mode;
  syncSegThumb('chartModeSeg', mode === 'candles' ? 0 : 1);
  const scrubEl = document.getElementById('chartScrubReadout');
  if (scrubEl) {
    scrubEl.textContent = mode === 'candles' ? '1m Candles' : 'Wave';
  }
  if (latestState) drawPriceChart(latestState);
}

""",
    "",
    "remove setChartMode",
)
# 3. useCandles 簡化（三處）
replace_once(
    APPJS,
    "  const useCandles = chartMode === 'candles' && rawCandles.length >= 2;",
    "  const useCandles = rawCandles.length >= 2;",
    "useCandles drawPriceChart",
)
replace_once(
    APPJS,
    "  const useCandles = chartMode === 'candles' && visibleCandles.length >= 2;",
    "  const useCandles = visibleCandles.length >= 2;",
    "useCandles draw body",
)
replace_once(
    APPJS,
    "    const useCandles = chartMode === 'candles' && candles.length >= 2;",
    "    const useCandles = candles.length >= 2;",
    "useCandles hover",
)
# 4. scrubEl Wave 字樣（兩處，用上下文區分）
replace_once(
    APPJS,
    """    lastHoverSnapY = -1;
    tip.style.display = 'none';
    if (scrubEl) {
      scrubEl.textContent = chartMode === 'candles' ? '1m Candles' : 'Wave';
    }""",
    """    lastHoverSnapY = -1;
    tip.style.display = 'none';
    if (scrubEl) {
      scrubEl.textContent = '1m Candles';
    }""",
    "scrubEl label hover-out",
)
replace_once(
    APPJS,
    """    hoveredCandleData = null;
    tip.style.display = 'none';
    if (scrubEl) {
      scrubEl.textContent = chartMode === 'candles' ? '1m Candles' : 'Wave';
    }""",
    """    hoveredCandleData = null;
    tip.style.display = 'none';
    if (scrubEl) {
      scrubEl.textContent = '1m Candles';
    }""",
    "scrubEl label mouse-leave",
)
# 5. 鍵盤 C 切換
replace_once(
    APPJS,
    """  } else if (e.code === 'KeyC' || e.key === 'c' || e.key === 'C') {
    setChartMode(chartMode === 'candles' ? 'line' : 'candles');
  } else if (e.code === 'KeyF' || e.key === 'f' || e.key === 'F') {""",
    """  } else if (e.code === 'KeyF' || e.key === 'f' || e.key === 'F') {""",
    "remove KeyC chart toggle",
)
# 6. drawSmoothCurve（失效後無人呼叫）
replace_once(
    APPJS,
    """/* Catmull-Rom / Cardinal Cubic Bézier Smooth Spline Interpolator for Silky Trend Lines */
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

""",
    "",
    "remove drawSmoothCurve",
)
# 7. K 線模式的 EMA 疊加（兩條趨勢線之一處）
replace_once(
    APPJS,
    """    // Overlay Silky Smooth Bézier Spline EMA lines
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
""",
    "",
    "remove candle EMA overlay",
)
# 8. Wave 模式整個 else 分支（含兩條 EMA 趨勢線＋價格線）
replace_once(
    APPJS,
    """  } else if (rawPrices.length >= 2) {
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
  }""",
    """  }""",
    "remove Wave branch",
)
# 9. ema9/ema21 宣告（失效後無人使用）
replace_once(
    APPJS,
    """  const ema9 = state.ema_fast_history || [];
  const ema21 = state.ema_slow_history || [];
""",
    "",
    "remove ema declarations",
)

# --- index.html ---
# 10. Candles/Wave 撥桿
replace_once(
    INDEX,
    """                <div class="seg-control ss-seg lg-seg" style="--n:2; --active-idx:0;" data-active-idx="0" id="chartModeSeg">
                  <span class="ss-seg__thumb lg-seg__thumb" aria-hidden="true"></span>
                  <button class="seg-btn ss-seg__option active" id="btnModeCandles" data-on onclick="setChartMode('candles')" title="Candlestick mode (Press C)">Candles</button>
                  <button class="seg-btn ss-seg__option" id="btnModeLine" onclick="setChartMode('line')" title="Spline Wave mode (Press C)">Wave</button>
                </div>
""",
    "",
    "remove chartModeSeg toggle",
)
# 11. 圖例 EMA 9／EMA 21 兩項（線已移除，圖例同步移除；MEAN 與策略保留）
replace_once(
    INDEX,
    """                  <span class="legend-item"><i class="legend-swatch" style="background:var(--c-cons)"></i>EMA 9</span>
                  <span class="legend-item"><i class="legend-swatch" style="background:var(--c-atr)"></i>EMA 21</span>
""",
    "",
    "remove EMA legend items",
)

print("PATCH DONE")
