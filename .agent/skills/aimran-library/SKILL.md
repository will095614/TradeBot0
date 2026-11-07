---
name: aimran-library
description: Access and integrate 814 free animated UI components in HTML, CSS, JS, and React from AIMRAN Library (https://library.aimran.es/) across 17 categories (liquid-glass, loaders, buttons, cards, toggles, filters, inputs, toasts, tooltips, navigation, overlays, text-scroll, microinteractions, checkboxes, radios, patterns, 404). Use whenever the user asks to add animated UI components, liquid glass effects, animated buttons, CSS loaders, microinteractions, or interactive cards from AIMRAN Library.
---

# AIMRAN Library Skill (814 Animated UI Components)

This skill provides full offline access to all **814 animated UI components** from [AIMRAN Library](https://library.aimran.es/), extracted and indexed by category with complete `html`, `css`, `js`, and `react` source code.

## Categories (17 Total / 814 Components)

| Category ID | Total | HTML + CSS | React + Motion | Typical Use Case |
| :--- | :---: | :---: | :---: | :--- |
| `liquid-glass` | 43 | 30 | 13 | Specular glass surfaces, HUD bars, floating docks, glass alerts, search & controls |
| `loaders` | 70 | 60 | 10 | Concentric orbits, radar ripples, conic rings, hex grids, boot splash spinners |
| `buttons` | 52 | 42 | 10 | Conic border sweep, diagonal shine, liquid metal, neon pulse, 3D tactile buttons |
| `cards` | 49 | 46 | 3 | Cursor-tracking spotlight border, magnetic aura, bento metric cards, 3D tilt |
| `filters` | 68 | 65 | 3 | Segmented pill filters, sliding active tabs, animated tag chips |
| `inputs` | 55 | 48 | 7 | Animated focus rings, floating labels, command search inputs |
| `toggles` | 36 | 36 | 0 | Elastic iOS switches, liquid droplet toggles, LED row indicators, tactile rockers |
| `toasts` | 41 | 40 | 1 | Countdown ring alerts, network status wave toasts, live event notifications |
| `tooltips` | 44 | 44 | 0 | Spring pop tooltips, status pulse tooltips, preview cards |
| `navigation` | 42 | 30 | 12 | Sliding indicator tabs, breadcrumb trails, command bars |
| `overlays` | 42 | 30 | 12 | Frosted glass modals, command palettes, drawers |
| `text-scroll` | 41 | 30 | 11 | Ticker tapes, number counters, shimmer headlines |
| `microinteractions` | 42 | 30 | 12 | Live status pulses, action confirmations, interactive meters |
| `checkboxes` | 46 | 46 | 0 | SVG stroke-draw checkmarks, spring checkboxes |
| `radios` | 40 | 40 | 0 | Morphing radio selectors, pill radios |
| `patterns` | 58 | 58 | 0 | Subtle animated grid backgrounds, dot matrices, radar meshes |
| `404` | 45 | 45 | 0 | Full-scene animated status/empty-state illustrations |

## How to Search & Retrieve Components

Use the bundled Python CLI script `.agent/skills/aimran-library/scripts/search_components.py`:

1. **List components in a category (HTML+CSS only)**:
   ```powershell
   python .agent/skills/aimran-library/scripts/search_components.py -c liquid-glass --html-only
   ```
2. **Search across all categories by keyword**:
   ```powershell
   python .agent/skills/aimran-library/scripts/search_components.py -q "radar" --html-only
   ```
3. **Retrieve the full HTML, CSS, JS, and React code for a component ID**:
   ```powershell
   python .agent/skills/aimran-library/scripts/search_components.py -i uv-card-spot
   ```

## Integration Guidelines for Desktop / PyWebView (`TradeBot0_Arena.exe`)

- **Prefer Pure HTML + CSS (`stack: "HTML + CSS"`)** when embedding into `src/gui/assets/index.html`, `src/gui/assets/app.css`, and `src/gui/assets/app.js` so that zero external runtime dependencies are required inside the standalone PyInstaller executable (`dist/TradeBot0_Arena.exe`).
- **Blend with Stageshow Dark Surface Hierarchy**: Adapt component CSS custom properties (`--accent`, backgrounds, borders) to match the existing Stageshow tokens (`--ss-well`, `--ss-surface`, `--ss-chrome`, `--ss-line`) so animations feel native to the institutional quant terminal.
- **Zero CJK in Static Frontend Assets**: Note that AIMRAN Library's raw descriptions and demo labels are in Spanish/English; always use English/ASCII labels inside `src/gui/assets/` to maintain compliance with `test_zero_cjk_in_frontend_assets`.

