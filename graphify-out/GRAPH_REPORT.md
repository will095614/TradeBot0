# Graph Report - TradeBot0  (2026-11-07)

## Corpus Check
- 257 files · ~294,449 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 141 file(s) not represented in the graph (top: .css 133, (none) 3, .bat 2)
- WARNING: 141 of 451 files seen (31%) have no supported extractor and are missing from this graph entirely. It may look complete while representing only part of the codebase.

## Summary
- 2850 nodes · 7503 edges · 110 communities (102 shown, 8 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 680 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `c6746645`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- controls/index.ts
- Stage
- LiveArenaEngine
- cursor-morph.tsx
- scan.py
- film-checks.mjs
- size.py
- trader-timemachine/timemachine.py
- entry.py
- Stage
- app.js
- viewer.tsx
- exit.py
- film.mjs
- check.py
- BrokerSim
- audit_all_components.py
- _ArenaBridgeApi
- kit/index.ts
- Portfolio
- .rect
- OmniRoute Deployment & Integration Guide
- devDependencies
- Chart
- ruled-bento/index.tsx
- share/index.tsx
- bento/index.tsx
- live_engine.py
- kit/index.ts
- subscriptions/index.tsx
- cursor-morph/index.tsx
- OmniRoute Headless Installation, Auto-Routing & Troubleshooting Playbook for AI Agents
- test_phase3_ingestion.py
- package.json
- spotify/index.tsx
- continuity.tsx
- OmniRouteClient
- wikipedia/index.tsx
- stage.tsx
- contrasts.tsx
- composition.tsx
- test_performance_and_optimizations.py
- HeroDemo.tsx
- cursor.tsx
- finder-glass/index.tsx
- Act
- scenes.tsx
- calendar/index.tsx
- staggered-bento/index.tsx
- jumps.mjs
- react
- google-calendar/index.tsx
- details.tsx
- relationships.tsx
- TradeBot0 — Optimization Audit & Work Order
- Text
- dynamic-island/index.tsx
- finder/index.tsx
- hero-grid/index.tsx
- backgrounds/index.tsx
- powerpoint/index.tsx
- slack/index.tsx
- choreography/index.tsx
- google-docs/index.tsx
- vite
- imessage/index.tsx
- isolate_arena_memory
- layout.mjs
- Unified Memory
- main.tsx
- freeform-drag/index.tsx
- compilerOptions
- trader-scanner
- react-dom
- Part 2: Complete Verbatim Audit Report
- series
- Collapse
- class-clash.mjs
- trader-budget
- upload/index.tsx
- trader-risk
- dev.mjs
- text-settle.tsx
- edges.tsx
- style.tsx
- trader-entry
- trader-exit
- trader-timemachine
- cursor-resize/index.tsx
- Roll
- Quick Start Guide
- Frontend Design
- presence/index.tsx
- Framing
- Python & Financial Engineering Standards (TradeBot0)
- NOTICE.md
- Stageshow
- Backgrounds and the whole picture
- Bento
- Choreography
- SimClock
- scripts
- Test-Driven Development (TDD) Workflow
- Trading Safety & Multi-Portfolio Guardrails
- Review
- cursor-morph/README.md
- products.md
- Point

## God Nodes (most connected - your core abstractions)
1. `Stage()` - 208 edges
2. `Bar()` - 122 edges
3. `Window()` - 111 edges
4. `Act` - 89 edges
5. `LiveArenaEngine` - 86 edges
6. `react` - 85 edges
7. `Text()` - 82 edges
8. `filmChecksSource()` - 79 edges
9. `BrokerSim` - 64 edges
10. `Icon()` - 58 edges

## Surprising Connections (you probably didn't know these)
- `Phase 3: Multi-Domain Intelligence Ingestion Pipeline` --references--> `MacroCommander`  [INFERRED]
  macro_commander_omniroute_workflow_plan.md → src/intelligence/macro_commander.py
- `12. Client Reference Sketch for the Arena App (non-normative) **[R]**` --references--> `extract_json()`  [INFERRED]
  omniroute_deployment_guide.md → src/intelligence/omniroute_client.py
- `13. Deployment Acceptance Checklist (maps to plan Phase 2 checkpoint)` --references--> `extract_json()`  [INFERRED]
  omniroute_deployment_guide.md → src/intelligence/omniroute_client.py
- `3. Concurrency & Thread Safety` --references--> `BrokerSim`  [INFERRED]
  .agent/rules/coding-standards.md → src/arena/broker_sim.py
- `5. Verification checklist` --references--> `_drive()`  [INFERRED]
  OPTIMIZATION_AUDIT.md → tests/test_live_engine.py

## Import Cycles
- 2-file cycle: `.agent/skills/stageshow/teaching/composition.tsx -> .agent/skills/stageshow/teaching/contrasts.tsx -> .agent/skills/stageshow/teaching/composition.tsx`
- 2-file cycle: `.agent/skills/stageshow/teaching/contrasts.tsx -> .agent/skills/stageshow/teaching/relationships.tsx -> .agent/skills/stageshow/teaching/contrasts.tsx`

## Communities (110 total, 8 thin omitted)

### Community 0 - "controls/index.ts"
Cohesion: 0.13
Nodes (9): ButtonProps, Draft(), DraftProps, FieldProps, Tabs(), DRAWN, FILLED, LUCIDE (+1 more)

### Community 1 - "Stage"
Cohesion: 0.05
Nodes (61): AiCards(), AiChat(), initial, poster, S, Ledger(), Receipt(), Buttons() (+53 more)

### Community 2 - "LiveArenaEngine"
Cohesion: 0.05
Nodes (40): Phase 4: Macro Commander with Strict Veto (Option A), 0. TL;DR, 4. Suggested execution order, A1. ~250 lines of duplicated strategy logic (also the root cause of C1), A2. `dashboard.py` is a 3,288-line file whose middle is a raw HTML string, A3. Dead module and dead dependency: `theme.py` / `dearpygui`, A4. Repeated wiring, scattered constants, lookup tables in the wrong place, A5. `main.py --self-test` is opaque and has side effects (+32 more)

### Community 3 - "cursor-morph.tsx"
Cohesion: 0.21
Nodes (11): CIRCLE, CursorMorph(), HEAD, Look, path(), POINTER, Pt, rgba() (+3 more)

### Community 4 - "scan.py"
Cohesion: 0.05
Nodes (52): _absorb(), build_universe(), chart_path(), classify(), clock_label(), cmd_daily(), cmd_orb(), confirm() (+44 more)

### Community 5 - "film-checks.mjs"
Cohesion: 0.12
Nodes (78): alphaOf(), animating(), cameraMoving(), checkStage(), collectSurfaces(), detectBoxEdges(), detectBylineGap(), detectClipped() (+70 more)

### Community 6 - "size.py"
Cohesion: 0.05
Nodes (44): BrandMarks(), groups, names, Sheet(), BrandAsset, brandMarks, BrandName, CommonProps (+36 more)

### Community 7 - "trader-timemachine/timemachine.py"
Cohesion: 0.05
Nodes (43): build_pool(), cents_away(), chart_result(), chart_url(), clock12(), clock24(), cmd_chart(), cmd_run() (+35 more)

### Community 8 - "entry.py"
Cohesion: 0.07
Nodes (47): ampm(), bar_line(), chart_path(), chart_range(), cmd_check(), cmd_watch(), emit(), on_trigger() (+39 more)

### Community 9 - "Stage"
Cohesion: 0.06
Nodes (41): Collection, CollectionStudy(), Detail, DetailStudy(), UsageDelivery(), Annotations(), BranchState, BranchStudy() (+33 more)

### Community 10 - "app.js"
Cohesion: 0.07
Nodes (59): P6. Front-end rebuilds its whole DOM every second, addChartBeacon(), animCandles, changeEvolveInterval(), chartBeacons, currentSplashSteps, drawPriceChart(), drawSmoothCurve() (+51 more)

### Community 11 - "viewer.tsx"
Cohesion: 0.24
Nodes (9): curated, examples, extra, groups, listed, products, specimens, mount() (+1 more)

### Community 12 - "exit.py"
Cohesion: 0.08
Nodes (39): ampm(), atr_of(), build_plan(), cents(), cmd_plan(), cmd_show(), compute(), D() (+31 more)

### Community 13 - "film.mjs"
Cohesion: 0.05
Nodes (35): args, at, cameraSkipped, clipped, clipSamples, colsOpt, count, delay (+27 more)

### Community 14 - "check.py"
Cohesion: 0.08
Nodes (29): account(), business_days(), _cent(), check(), day_trades(), eastern_offset(), eastern_to_utc(), _f() (+21 more)

### Community 15 - "BrokerSim"
Cohesion: 0.08
Nodes (32): 2. Ground rules — do not break these, Architectural Highlights, audit_broker_matching_engine(), audit_competitors_and_sizing(), BrokerSim, ExecutionReason, OrderSide, OrderStatus (+24 more)

### Community 16 - "audit_all_components.py"
Cohesion: 0.27
Nodes (12): assert_true(), audit_cadence_and_microbar(), audit_frontend_cjk(), audit_genetic_evolution(), audit_leaderboard(), audit_macro_commander(), audit_timemachine_mc(), audit_ui_bridge_state() (+4 more)

### Community 18 - "kit/index.ts"
Cohesion: 0.07
Nodes (41): REVENUE, ROWS, DynamicIsland(), CHANGED, initial, Parts(), POSTER, S (+33 more)

### Community 19 - "Portfolio"
Cohesion: 0.11
Nodes (14): C6. Breakeven exits are counted as losses, C7. Sharpe / Sortino are numerically meaningless as displayed, P3. Rankings recomputed on every poll, over ever-growing data, Leaderboard, FillEvent, Portfolio, test_bidirectional_short_win_rate_and_closing_fill(), test_leaderboard_ranked_strictly_by_total_equity() (+6 more)

### Community 20 - ".rect"
Cohesion: 0.05
Nodes (39): Annotations, guides and connecting lines, Attach to what is drawn, Check attachment in motion, Choose a line for a relationship, Frame the whole relationship, Check it, Defining a look, From a codebase (+31 more)

### Community 21 - "OmniRoute Deployment & Integration Guide"
Cohesion: 0.05
Nodes (37): 10.1 Monitoring **[V]**, 10.2 Circuit breakers **[V]**, 10.3 Data, backup, upgrade, uninstall, 10. Operations, 11. Troubleshooting, 12. Client Reference Sketch for the Arena App (non-normative) **[R]**, 13. Deployment Acceptance Checklist (maps to plan Phase 2 checkpoint), 14. Sources (+29 more)

### Community 22 - "devDependencies"
Cohesion: 0.20
Nodes (10): devDependencies, playwright-core@~1.48.2, postcss@^8.5.6, @types/react@^18.3.1, @types/react-dom@^18.3.1, typescript@^5.6.3, postcss, @types/react (+2 more)

### Community 23 - "Chart"
Cohesion: 0.09
Nodes (28): ChartScrub(), DAYS, money(), NAMES, S, script(), TOTAL, W (+20 more)

### Community 24 - "ruled-bento/index.tsx"
Cohesion: 0.10
Nodes (29): Chrome(), Content(), Figure(), files, Specimen, specimens, Tool(), after (+21 more)

### Community 25 - "share/index.tsx"
Cohesion: 0.09
Nodes (24): Glass(), Crumb(), initial, Item, ITEMS, NotionSlash(), Page(), S (+16 more)

### Community 26 - "bento/index.tsx"
Cohesion: 0.10
Nodes (29): calendar, figma, mail, notion, slack, testFlight, after, Approvals() (+21 more)

### Community 27 - "live_engine.py"
Cohesion: 0.07
Nodes (13): main(), H6. Doc drift and small inconsistencies, GeneticEvolver, CompetitorStats, CandleBar, ETHFeed, MonteCarloBracketOdds, MonteCarloOddsEvaluator (+5 more)

### Community 28 - "kit/index.ts"
Cohesion: 0.05
Nodes (65): Cards(), initial, S, Controls(), DATA, DIFF, initial, MORE (+57 more)

### Community 29 - "subscriptions/index.tsx"
Cohesion: 0.09
Nodes (23): DarkHero(), initial, Label(), Mark(), OLD, Row(), S, Side() (+15 more)

### Community 30 - "cursor-morph/index.tsx"
Cohesion: 0.25
Nodes (6): MorphStyle, LABELS, ORDER, REST, S, STYLES

### Community 31 - "OmniRoute Headless Installation, Auto-Routing & Troubleshooting Playbook for AI Agents"
Cohesion: 0.07
Nodes (27): 1. Agent Directives & Execution Rules, 2.1 Check Port `20128` Availability, 2.2 Verify Strict Node.js Runtime Version, 2.3 Verify Native Build Tools (Required for `better-sqlite3`), 2.4 Clean Up Corrupted Previous State, 2. Phase 1: Pre-Flight Diagnostics & Cleanup, 3.1 Generate Consolidated `.env` File, 3. Phase 2: Pure Backend & Auto-Routing Configuration (`.env`) (+19 more)

### Community 32 - "test_phase3_ingestion.py"
Cohesion: 0.06
Nodes (23): audit_omniroute_and_ingestion(), _test_debouncer(), _clean_html_text(), DeduplicationBuffer, IntelligenceHarvester, InterruptDebouncer, parse_polymarket_events(), parse_reddit_posts() (+15 more)

### Community 33 - "package.json"
Cohesion: 0.18
Nodes (11): description, engines, node, license, name, optionalDependencies, portless@^0.4.1, private (+3 more)

### Community 34 - "spotify/index.tsx"
Cohesion: 0.21
Nodes (9): Art(), Eq(), fmt(), Id, initial, ROWS, S, SONGS (+1 more)

### Community 35 - "continuity.tsx"
Cohesion: 0.29
Nodes (7): Cursor(), ContinuityComparison(), continuityLessons, drag(), initial, State, Contrasts()

### Community 36 - "OmniRouteClient"
Cohesion: 0.07
Nodes (24): main(), MacroCommander, MacroRegimeState, compute_backoff(), extract_json(), OmniRouteClient, test_macro_commander_skips_chat_when_gateway_offline(), _test() (+16 more)

### Community 37 - "wikipedia/index.tsx"
Cohesion: 0.13
Nodes (22): CDX, CdxIcon(), CROPS, Fuji(), Header(), Infobox(), initial, Lake() (+14 more)

### Community 38 - "stage.tsx"
Cohesion: 0.09
Nodes (43): ActEnv, checkSeam(), createAct(), Ref, Script, Stopped, CursorKind, CursorStyle (+35 more)

### Community 39 - "contrasts.tsx"
Cohesion: 0.12
Nodes (19): MacPointer(), compositionLessons, Action(), cases, Comparison(), ExitScene(), FILES, HandoffFlights() (+11 more)

### Community 40 - "composition.tsx"
Cohesion: 0.15
Nodes (22): Anatomy(), Compact(), CompositionComparison(), Contrast(), ControlAlignment(), Decoration(), Density(), EdgeSeparation() (+14 more)

### Community 41 - "test_performance_and_optimizations.py"
Cohesion: 0.16
Nodes (11): ArenaDashboard, _build_html_template(), _get_assets_dir(), _load_asset(), test_launchers_and_shortcut_integrity(), test_portfolio_no_duplicate_apply_fill_returns(), test_reset_engine_preserves_cadence(), test_splash_logo_concentric_alignment_and_svg_zap() (+3 more)

### Community 42 - "HeroDemo.tsx"
Cohesion: 0.09
Nodes (26): FigmaDemo(), hex(), initial, LayerIcon(), LAYERS, MAYA, mayaAt(), S (+18 more)

### Community 43 - "cursor.tsx"
Cohesion: 0.22
Nodes (14): ARROW_HOTSPOT, GLYPHS, HOTSPOT, MacCrosshair(), MacGrab(), MacIbeam(), MacOpenHand(), MacPointingHand() (+6 more)

### Community 44 - "finder-glass/index.tsx"
Cohesion: 0.13
Nodes (19): Column(), DOCUMENTS, FileIcon(), FILMS, FinderGlassDemo(), Geo, GEO, initial (+11 more)

### Community 45 - "Act"
Cohesion: 0.05
Nodes (27): DAYS, FLIGHTS, initial, poster, S, initial, poster, S (+19 more)

### Community 46 - "scenes.tsx"
Cohesion: 0.22
Nodes (21): Action(), ColoredLayers(), CropFiller(), DashboardPhone(), FileList(), FOLDER, LibraryApp(), Mark() (+13 more)

### Community 47 - "calendar/index.tsx"
Cohesion: 0.13
Nodes (19): Avail, BUSY, carry(), Cell, cellRect(), DAYS, END, GRIP (+11 more)

### Community 48 - "staggered-bento/index.tsx"
Cohesion: 0.20
Nodes (19): after, AZ, Azulejo(), Beat, beat(), before, Book(), Coast() (+11 more)

### Community 49 - "jumps.mjs"
Cohesion: 0.17
Nodes (16): clipFindings(), finishReport(), has(), args, analyse(), contentChanges(), record(), errors (+8 more)

### Community 50 - "react"
Cohesion: 0.16
Nodes (16): Rect, CountProps, digitsFromRight(), STRIP, unitOf(), Fly(), FlyProps, cellOf() (+8 more)

### Community 51 - "google-calendar/index.tsx"
Cohesion: 0.14
Nodes (19): clock(), clockFull(), EVENTS, FOUR, GEO, GoogleCalendar(), Grid(), Header() (+11 more)

### Community 52 - "details.tsx"
Cohesion: 0.15
Nodes (15): Bar(), ChartDraw(), Copy(), DetailComparison(), detailLessons, Emoji(), Id, LINE (+7 more)

### Community 53 - "relationships.tsx"
Cohesion: 0.21
Nodes (17): Actions(), change(), Check(), Horizontal(), initial, LessonId, List(), Person() (+9 more)

### Community 54 - "TradeBot0 — Optimization Audit & Work Order"
Cohesion: 0.11
Nodes (19): 1. Project context (read this first), 3. Findings, 5. Verification checklist, 6. Decisions the human must make before you start, 7. Appendix — measured facts, Commands, H1. Dependencies are unpinned, unpinned-past-major, and mix concerns, H2. Two build configs that will drift (+11 more)

### Community 55 - "Text"
Cohesion: 0.24
Nodes (10): Actions(), GmailArchive(), initial, M, Nav(), REST, Row(), ROWS (+2 more)

### Community 56 - "dynamic-island/index.tsx"
Cohesion: 0.12
Nodes (14): Bag(), BASE, Box, boxStyle(), BUD, GEO, GROW, Island() (+6 more)

### Community 57 - "finder/index.tsx"
Cohesion: 0.17
Nodes (13): DragImage(), FileIcon(), FinderDemo(), Geo, GEO, Ghost, initial, Kind (+5 more)

### Community 58 - "hero-grid/index.tsx"
Cohesion: 0.18
Nodes (15): at(), composition(), Draft, Drafting(), HeroGrid(), Icons(), INITIAL, KEY_ROWS (+7 more)

### Community 59 - "backgrounds/index.tsx"
Cohesion: 0.43
Nodes (5): Backgrounds(), Digest(), Halftone(), studies, Study()

### Community 60 - "powerpoint/index.tsx"
Cohesion: 0.14
Nodes (17): Big(), Box, Design, fit(), G, ICON, IDEAS, initial (+9 more)

### Community 61 - "slack/index.tsx"
Cohesion: 0.24
Nodes (13): Composer(), Face(), HoverBar(), I(), initial, Older(), poster, Rail() (+5 more)

### Community 62 - "choreography/index.tsx"
Cohesion: 0.19
Nodes (12): Bank(), Checkout(), Choreography(), ChoreographyComparison(), choreographyLessons, initial, Locale, locales (+4 more)

### Community 63 - "google-docs/index.tsx"
Cohesion: 0.21
Nodes (12): Card, Docs(), Drop(), GoogleDocs(), Header(), initial, P, poster (+4 more)

### Community 64 - "vite"
Cohesion: 0.40
Nodes (4): vite@^6.4.5, @vitejs/plugin-react@^4.7.0, vite, @vitejs/plugin-react

### Community 65 - "imessage/index.tsx"
Cohesion: 0.05
Nodes (48): IMessage(), initial, S, SUGGEST, suggestions(), ArrowUp(), initial, Messages() (+40 more)

### Community 67 - "layout.mjs"
Cohesion: 0.16
Nodes (10): launch(), checkClipsForStage(), args, auditLayout(), layoutResult(), errors, options, result (+2 more)

### Community 68 - "Unified Memory"
Cohesion: 0.15
Nodes (12): 1. Recall before writing, 2. Save context, 3. Hand off work, 4. Validate the vault, MCP Setup, Recall is evidence, not certainty, Runtime Prerequisite, Trust And Data Boundaries (+4 more)

### Community 69 - "main.tsx"
Cohesion: 0.10
Nodes (16): clock, ClockControl, Host, installVirtualClock(), StillContext, boot(), errorText(), params (+8 more)

### Community 70 - "freeform-drag/index.tsx"
Cohesion: 0.20
Nodes (10): BUSY, Cell, cellRect(), DAYS, END, HOURS, move(), S (+2 more)

### Community 71 - "compilerOptions"
Cohesion: 0.17
Nodes (11): compilerOptions, jsx, lib, module, moduleResolution, noEmit, skipLibCheck, strict (+3 more)

### Community 73 - "trader-scanner"
Cohesion: 0.17
Nodes (11): Data and limits, Example: the reel, Rules, Safety, Steps, The daily scan (before the open), The opening-range breakout scan (during the session), The universe (+3 more)

### Community 74 - "react-dom"
Cohesion: 0.40
Nodes (5): dependencies, lucide-react@0.468.0, react@^18.3.1, react-dom@^18.3.1, react-dom

### Community 75 - "Part 2: Complete Verbatim Audit Report"
Cohesion: 0.17
Nodes (11): 1. Correction on Splash Screen & Packaging, 3. The One Claim That Didn't Hold: The 15 KB Gate, 4. Four Items From the Audit Still Untouched, 5. Two Remaining Risks Worth Naming, 6. Verdict, Do Not Break (Verified Green Baseline), Part 1: Actionable Task List for the Programming Agent, Part 2: Complete Verbatim Audit Report (+3 more)

### Community 76 - "series"
Cohesion: 0.22
Nodes (10): checkClips(), clipFor(), fail(), overlaid(), secs(), series(), shoot(), stageRoot() (+2 more)

### Community 78 - "Collapse"
Cohesion: 0.06
Nodes (34): initial, POSTER, S, COMMANDS, initial, IssueRow(), LinearDemo(), Priority() (+26 more)

### Community 79 - "class-clash.mjs"
Cohesion: 0.31
Nodes (7): args, classDefinitions(), findClashes(), splitSelectors(), unwrapAttributeWhere(), withoutConditions(), find()

### Community 80 - "trader-budget"
Cohesion: 0.18
Nodes (10): Example: the reel, Rules, Safety, Step 1: set the rules once, Step 2: size the trade, Step 3: show the user, trader-budget, Weights mode (kept from v1) (+2 more)

### Community 81 - "upload/index.tsx"
Cohesion: 0.07
Nodes (29): ART, CARD, CARD_NAMES, LIST_TEXT, MobileApp(), Pause(), Phase, Play() (+21 more)

### Community 83 - "trader-risk"
Cohesion: 0.20
Nodes (9): Entries and exits, Example: the reel, Rules, Safety, Steps, The checks, trader-risk, What it never does (+1 more)

### Community 88 - "dev.mjs"
Cohesion: 0.28
Nodes (4): devCommand(), main(), packageBin(), root

### Community 89 - "text-settle.tsx"
Cohesion: 0.33
Nodes (5): labels, State, TextComparison(), textLessons, UnstableLabel()

### Community 90 - "edges.tsx"
Cohesion: 0.28
Nodes (6): EdgeComparison(), edgeLessons, initial, LabelSlot(), State, Viewport()

### Community 91 - "style.tsx"
Cohesion: 0.28
Nodes (8): Card(), Deploy, DEPLOYS, ICON, Id, MadeUp(), StyleComparison(), styleLessons

### Community 92 - "trader-entry"
Cohesion: 0.22
Nodes (8): Example: the reel, Rules, Safety, Steps, The rule, trader-entry, What it never does, What it reads and writes

### Community 93 - "trader-exit"
Cohesion: 0.22
Nodes (8): Example: the reel, Rules, Safety, Steps, Stops and targets, trader-exit, What it never does, What it reads and writes

### Community 94 - "trader-timemachine"
Cohesion: 0.22
Nodes (8): Example: the reel, How it works, Rules, Safety, Steps, trader-timemachine, What it never does, What it reads and writes

### Community 95 - "cursor-resize/index.tsx"
Cohesion: 0.29
Nodes (6): CursorResize(), HANDLES, pull(), S, script(), START

### Community 96 - "Roll"
Cohesion: 0.06
Nodes (30): PayoutFlow(), ROWS, S, START, BARS, PRICE, S, START (+22 more)

### Community 97 - "Quick Start Guide"
Cohesion: 0.25
Nodes (6): 1. Launch Packaged Desktop Executable (`.exe`), 2. Run Self-Test Verification, 3. Run Automated Unit Test Suite (32 Tests), 4. Build Standalone Windows Executable, Quick Start Guide, TradeBot0: Multi-Agent Paper Trading & Genetic Evolution Arena (BTC/USD)

### Community 98 - "Frontend Design"
Cohesion: 0.29
Nodes (6): Design principles, Frontend Design, Ground your designs in the subject matter, More on writing in design, Process: plan, review against the brief, build, critique, Restraint and self-critique

### Community 99 - "presence/index.tsx"
Cohesion: 0.24
Nodes (7): initial, Peer(), PEOPLE, Presence(), S, Spot, spot()

### Community 100 - "Framing"
Cohesion: 0.29
Nodes (6): Checks, Framing, Phones, Small formats and the page, The layouts, The rules

### Community 101 - "Python & Financial Engineering Standards (TradeBot0)"
Cohesion: 0.33
Nodes (5): 1. High-Precision Financial Math, 2. Strong Typing & Documentation, 3. Concurrency & Thread Safety, 4. Defensive Exception Handling & Logging, Python & Financial Engineering Standards (TradeBot0)

### Community 103 - "NOTICE.md"
Cohesion: 0.33
Nodes (3): Photograph sources, Brand artwork sources, Notices

### Community 105 - "Stageshow"
Cohesion: 0.33
Nodes (5): Contents, Preview, Stageshow, Use the kit, Verify

### Community 106 - "Backgrounds and the whole picture"
Cohesion: 0.33
Nodes (5): Backgrounds and the whole picture, Choose the ground for what it does, Compose the set before the tiles, Objects and drawings as tiles, Recompose for the host

### Community 107 - "Bento"
Cohesion: 0.33
Nodes (5): Bento, Kinds of tile, Layouts, Planning a grid, The rules

### Community 108 - "Choreography"
Cohesion: 0.33
Nodes (5): A change passing through an interface, Choose the curve for the movement, Choreography, Review the full change, Timing has different jobs

### Community 112 - "scripts"
Cohesion: 0.40
Nodes (5): scripts, build, check:css, dev, typecheck

### Community 114 - "Test-Driven Development (TDD) Workflow"
Cohesion: 0.50
Nodes (3): 1. Golden Rule, 2. Test Coverage Requirements, Test-Driven Development (TDD) Workflow

### Community 115 - "Trading Safety & Multi-Portfolio Guardrails"
Cohesion: 0.50
Nodes (3): 1. Dual Mode Operation, 2. Invariant Risk Limits (AgentShield), Trading Safety & Multi-Portfolio Guardrails

### Community 123 - "Point"
Cohesion: 0.17
Nodes (9): Point, Target, along(), bend(), ConnectorProps, corners(), elbow(), Route (+1 more)

## Knowledge Gaps
- **8 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Parts` connect `kit/index.ts` to `Roll`, `Stage`, `film-checks.mjs`, `size.py`, `Stage`, `HeroDemo.tsx`, `Act`, `Collapse`, `calendar/index.tsx`, `upload/index.tsx`, `react`, `kit/index.ts`, `.rect`, `Chart`, `share/index.tsx`?**
  _High betweenness centrality (0.232) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `Stage()` (e.g. with `The rules` and `Recipes`) actually correct?**
  _`Stage()` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Should `controls/index.ts` be split into smaller, more focused modules?**
  _Cohesion score 0.13450292397660818 - nodes in this community are weakly interconnected._
- **Why does `size()` connect `size.py` to `kit/index.ts`?**
  _High betweenness centrality (0.202) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `Window()` (e.g. with `Recipes` and ``Window``) actually correct?**
  _`Window()` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Should `Stage` be split into smaller, more focused modules?**
  _Cohesion score 0.05329593267882188 - nodes in this community are weakly interconnected._
- **Why does `Close()` connect `bento/index.tsx` to `Roll`, `react`?**
  _High betweenness centrality (0.177) - this node is a cross-community bridge._