# Graph Report - TradeBot0  (2026-11-07)

## Corpus Check
- 277 files · ~1,084,374 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 141 file(s) not represented in the graph (top: .css 133, (none) 3, .bat 2)
- WARNING: 141 of 471 files seen (30%) have no supported extractor and are missing from this graph entirely. It may look complete while representing only part of the codebase.

## Summary
- 2862 nodes · 7527 edges · 126 communities (118 shown, 8 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 682 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `4f87c4b7`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BrokerSim
- Window
- LiveArenaEngine
- cursor-morph.tsx
- scan.py
- film-checks.mjs
- size.py
- trader-timemachine/timemachine.py
- entry.py
- States
- app.js
- viewer.tsx
- exit.py
- film.mjs
- check.py
- brand-marks/index.tsx
- audit_all_components.py
- _ArenaBridgeApi
- Phone
- OrderSide
- Looks
- OmniRoute Deployment & Integration Guide
- Layout
- Chart
- ruled-bento/index.tsx
- notion/index.tsx
- bento/index.tsx
- live_engine.py
- Parts
- subscriptions/index.tsx
- datetime
- OmniRoute Headless Installation, Auto-Routing & Troubleshooting Playbook for AI Agents
- figma/index.tsx
- package.json
- spotify/index.tsx
- Text
- MacroCommander
- wikipedia/index.tsx
- kit/index.ts
- contrasts.tsx
- composition.tsx
- Teaching pairs
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
- P1 — Performance
- Collapse
- dynamic-island/index.tsx
- finder/index.tsx
- hero-grid/index.tsx
- Icon
- powerpoint/index.tsx
- slack/index.tsx
- choreography/index.tsx
- google-docs/index.tsx
- text-settle.tsx
- imessage/index.tsx
- Bento
- layout.mjs
- Unified Memory
- main.tsx
- freeform-drag/index.tsx
- compilerOptions
- telegram/index.tsx
- trader-scanner
- dark-hero/index.tsx
- Part 2: Complete Verbatim Audit Report
- parts/index.ts
- ingestion.py
- linear/index.tsx
- class-clash.mjs
- trader-budget
- phone-touch/index.tsx
- LiveQuote
- trader-risk
- .get_ui_state
- excel/index.tsx
- raycast/index.tsx
- upload/index.tsx
- dev.mjs
- scripts
- edges.tsx
- style.tsx
- trader-entry
- trader-exit
- trader-timemachine
- cursor-resize/index.tsx
- gmail/index.tsx
- TradeBot0 — Optimization Audit & Work Order
- Frontend Design
- table-edit/index.tsx
- Framing
- Python & Financial Engineering Standards (TradeBot0)
- NOTICE.md
- .bootstrap_intraday_session
- Stageshow
- Backgrounds and the whole picture
- Choreography
- SimClock
- AIMRAN Library Skill (814 Animated UI Components)
- MonteCarloBracketOdds
- ClockControl
- Test-Driven Development (TDD) Workflow
- Trading Safety & Multi-Portfolio Guardrails
- Review
- cursor-morph/README.md
- products.md
- preview.tsx
- Stageshow
- argparse
- Verify
- Craft
- Rehearse
- Detailed Execution Phases & Tasks
- Motion

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
- `3. Concurrency & Thread Safety` --references--> `BrokerSim`  [INFERRED]
  .agent/rules/coding-standards.md → src/arena/broker_sim.py
- `Phase 3: Multi-Domain Intelligence Ingestion Pipeline` --references--> `MacroCommander`  [INFERRED]
  macro_commander_omniroute_workflow_plan.md → src/intelligence/macro_commander.py
- `12. Client Reference Sketch for the Arena App (non-normative) **[R]**` --references--> `extract_json()`  [INFERRED]
  omniroute_deployment_guide.md → src/intelligence/omniroute_client.py
- `13. Deployment Acceptance Checklist (maps to plan Phase 2 checkpoint)` --references--> `extract_json()`  [INFERRED]
  omniroute_deployment_guide.md → src/intelligence/omniroute_client.py
- `5. Verification checklist` --references--> `_drive()`  [INFERRED]
  OPTIMIZATION_AUDIT.md → tests/test_live_engine.py

## Import Cycles
- 2-file cycle: `.agent/skills/stageshow/teaching/composition.tsx -> .agent/skills/stageshow/teaching/contrasts.tsx -> .agent/skills/stageshow/teaching/composition.tsx`
- 2-file cycle: `.agent/skills/stageshow/teaching/contrasts.tsx -> .agent/skills/stageshow/teaching/relationships.tsx -> .agent/skills/stageshow/teaching/contrasts.tsx`

## Communities (126 total, 8 thin omitted)

### Community 0 - "BrokerSim"
Cohesion: 0.09
Nodes (29): 2. Ground rules — do not break these, audit_competitors_and_sizing(), BrokerSim, ExecutionReason, OrderSide, OrderStatus, OrderTicket, OrderType (+21 more)

### Community 1 - "Window"
Cohesion: 0.05
Nodes (40): CornerChip(), S, DarkBento(), TRACKS, FreeformDrag(), Glass(), AW, BW (+32 more)

### Community 2 - "LiveArenaEngine"
Cohesion: 0.12
Nodes (8): A4. Repeated wiring, scattered constants, lookup tables in the wrong place, LiveArenaEngine, test_anti_churn_cooldown_prevents_same_timestamp_reentry(), test_auto_evolve_timer_and_toggle(), test_live_engine_bidirectional_long_and_short_execution(), test_macro_veto_intent_preserved_in_live_evaluation(), test_candle_cadence_dispatcher_timing_and_dispatch(), test_live_engine_enforces_macro_commander_veto()

### Community 3 - "cursor-morph.tsx"
Cohesion: 0.12
Nodes (18): CIRCLE, CursorMorph(), HEAD, Look, MorphStyle, path(), POINTER, Pt (+10 more)

### Community 4 - "scan.py"
Cohesion: 0.06
Nodes (49): _absorb(), build_universe(), chart_path(), classify(), clock_label(), cmd_daily(), cmd_orb(), confirm() (+41 more)

### Community 5 - "film-checks.mjs"
Cohesion: 0.12
Nodes (78): alphaOf(), animating(), cameraMoving(), checkStage(), collectSurfaces(), detectBoxEdges(), detectBylineGap(), detectClipped() (+70 more)

### Community 6 - "size.py"
Cohesion: 0.07
Nodes (35): allocate(), bracket_order(), eastern_offset(), eastern_to_utc(), _f(), fresh_price(), load_config(), load_prices() (+27 more)

### Community 7 - "trader-timemachine/timemachine.py"
Cohesion: 0.05
Nodes (43): build_pool(), cents_away(), chart_result(), chart_url(), clock12(), clock24(), cmd_chart(), cmd_run() (+35 more)

### Community 8 - "entry.py"
Cohesion: 0.07
Nodes (45): ampm(), bar_line(), chart_path(), chart_range(), cmd_check(), cmd_watch(), emit(), on_trigger() (+37 more)

### Community 9 - "States"
Cohesion: 0.07
Nodes (38): Collection, CollectionStudy(), Detail, DetailStudy(), UsageDelivery(), Annotations(), BranchState, BranchStudy() (+30 more)

### Community 10 - "app.js"
Cohesion: 0.06
Nodes (63): P6. Front-end rebuilds its whole DOM every second, addChartBeacon(), animCandles, changeEvolveInterval(), chartBeacons, currentSplashSteps, drawPriceChart(), drawSmoothCurve() (+55 more)

### Community 11 - "viewer.tsx"
Cohesion: 0.24
Nodes (9): curated, examples, extra, groups, listed, products, specimens, mount() (+1 more)

### Community 12 - "exit.py"
Cohesion: 0.09
Nodes (37): ampm(), atr_of(), build_plan(), cents(), cmd_plan(), cmd_show(), compute(), D() (+29 more)

### Community 13 - "film.mjs"
Cohesion: 0.05
Nodes (45): args, at, cameraSkipped, checkClips(), clipFor(), clipped, clipSamples, colsOpt (+37 more)

### Community 14 - "check.py"
Cohesion: 0.08
Nodes (29): account(), business_days(), _cent(), check(), day_trades(), eastern_offset(), eastern_to_utc(), _f() (+21 more)

### Community 15 - "brand-marks/index.tsx"
Cohesion: 0.18
Nodes (10): BrandMarks(), groups, names, Sheet(), BrandAsset, brandMarks, BrandName, BrandMarkProps (+2 more)

### Community 16 - "audit_all_components.py"
Cohesion: 0.20
Nodes (15): assert_true(), audit_broker_matching_engine(), audit_cadence_and_microbar(), audit_frontend_cjk(), audit_genetic_evolution(), audit_leaderboard(), audit_macro_commander(), audit_omniroute_and_ingestion() (+7 more)

### Community 17 - "_ArenaBridgeApi"
Cohesion: 0.12
Nodes (6): 4. Suggested execution order, C3. `stop()` does not join the worker thread, _ArenaBridgeApi, ArenaDashboard, test_reset_engine_preserves_cadence(), test_arena_bridge_api_refresh_intel()

### Community 18 - "Phone"
Cohesion: 0.11
Nodes (29): CHANGED, initial, Parts(), POSTER, S, Tile(), Checkout(), Phones() (+21 more)

### Community 19 - "OrderSide"
Cohesion: 0.09
Nodes (15): C6. Breakeven exits are counted as losses, C7. Sharpe / Sortino are numerically meaningless as displayed, P3. Rankings recomputed on every poll, over ever-growing data, Leaderboard, FillEvent, Portfolio, isolate_arena_memory(), test_bidirectional_short_win_rate_and_closing_fill() (+7 more)

### Community 20 - "Looks"
Cohesion: 0.22
Nodes (8): Check it, Defining a look, From a codebase, From a public site, Looks, The built-in looks, The tokens, What a look doesn't change

### Community 21 - "OmniRoute Deployment & Integration Guide"
Cohesion: 0.05
Nodes (37): 10.1 Monitoring **[V]**, 10.2 Circuit breakers **[V]**, 10.3 Data, backup, upgrade, uninstall, 10. Operations, 11. Troubleshooting, 12. Client Reference Sketch for the Arena App (non-normative) **[R]**, 13. Deployment Acceptance Checklist (maps to plan Phase 2 checkpoint), 14. Sources (+29 more)

### Community 22 - "Layout"
Cohesion: 0.23
Nodes (11): ActEnv, Script, CursorKind, CursorStyle, Fidelity, Layout, Look, LookContext (+3 more)

### Community 23 - "Chart"
Cohesion: 0.09
Nodes (26): ChartScrub(), DAYS, money(), NAMES, S, script(), TOTAL, W (+18 more)

### Community 24 - "ruled-bento/index.tsx"
Cohesion: 0.07
Nodes (36): Chrome(), Content(), Figure(), files, Specimen, specimens, Tool(), after (+28 more)

### Community 25 - "notion/index.tsx"
Cohesion: 0.20
Nodes (11): Crumb(), initial, Item, ITEMS, NotionSlash(), Page(), S, Scene() (+3 more)

### Community 26 - "bento/index.tsx"
Cohesion: 0.15
Nodes (22): calendar, figma, mail, notion, slack, testFlight, after, Approvals() (+14 more)

### Community 27 - "live_engine.py"
Cohesion: 0.07
Nodes (19): main(), Architectural Highlights, GeneticEvolver, CompetitorStats, CandleBar, ETHFeed, MonteCarloOddsEvaluator, TimeMachineArena (+11 more)

### Community 28 - "Parts"
Cohesion: 0.09
Nodes (20): Controls(), DATA, DIFF, initial, MORE, POSTER, ROWS, S (+12 more)

### Community 29 - "subscriptions/index.tsx"
Cohesion: 0.10
Nodes (19): Checkout(), OLD, Pay, POSTER, Pulse, pulse(), S, Scene (+11 more)

### Community 30 - "datetime"
Cohesion: 0.24
Nodes (8): eastern_offset(), _nth_sunday(), eastern_offset(), eastern_to_utc(), _nth_sunday(), eastern_offset(), eastern_to_utc(), _nth_sunday()

### Community 31 - "OmniRoute Headless Installation, Auto-Routing & Troubleshooting Playbook for AI Agents"
Cohesion: 0.07
Nodes (27): 1. Agent Directives & Execution Rules, 2.1 Check Port `20128` Availability, 2.2 Verify Strict Node.js Runtime Version, 2.3 Verify Native Build Tools (Required for `better-sqlite3`), 2.4 Clean Up Corrupted Previous State, 2. Phase 1: Pre-Flight Diagnostics & Cleanup, 3.1 Generate Consolidated `.env` File, 3. Phase 2: Pure Backend & Auto-Routing Configuration (`.env`) (+19 more)

### Community 32 - "figma/index.tsx"
Cohesion: 0.25
Nodes (9): FigmaDemo(), hex(), initial, LayerIcon(), LAYERS, MAYA, mayaAt(), S (+1 more)

### Community 33 - "package.json"
Cohesion: 0.10
Nodes (24): description, devDependencies, postcss@^8.5.6, @types/react@^18.3.1, @types/react-dom@^18.3.1, typescript@^5.6.3, vite@^6.4.5, @vitejs/plugin-react@^4.7.0 (+16 more)

### Community 34 - "spotify/index.tsx"
Cohesion: 0.10
Nodes (17): Buttons(), initial, POSTER, S, Art(), Eq(), fmt(), Id (+9 more)

### Community 35 - "Text"
Cohesion: 0.06
Nodes (36): CloseUp(), initial, poster, S, Card(), PaymentsStatic(), REVENUE, ROWS (+28 more)

### Community 36 - "MacroCommander"
Cohesion: 0.07
Nodes (26): main(), StructuredEvent, MacroCommander, MacroRegimeState, compute_backoff(), extract_json(), OmniRouteClient, test_macro_commander_skips_chat_when_gateway_offline() (+18 more)

### Community 37 - "wikipedia/index.tsx"
Cohesion: 0.13
Nodes (22): CDX, CdxIcon(), CROPS, Fuji(), Header(), Infobox(), initial, Lake() (+14 more)

### Community 38 - "kit/index.ts"
Cohesion: 0.15
Nodes (28): checkSeam(), createAct(), Ref, Stopped, bezier(), capsOf(), KEYCAPS, Keycaps() (+20 more)

### Community 39 - "contrasts.tsx"
Cohesion: 0.10
Nodes (23): Cursor(), MacPointer(), ContinuityComparison(), continuityLessons, drag(), initial, State, Action() (+15 more)

### Community 40 - "composition.tsx"
Cohesion: 0.14
Nodes (22): Anatomy(), Compact(), compositionLessons, Contrast(), ControlAlignment(), Decoration(), Density(), EdgeSeparation() (+14 more)

### Community 41 - "Teaching pairs"
Cohesion: 0.22
Nodes (8): Details, Making a comparison, Motion between neighbors, Style (stills), Teaching pairs, UI details (stills), What a pair can't show, Whole scenes (stills)

### Community 42 - "HeroDemo.tsx"
Cohesion: 0.14
Nodes (17): annotate(), HeroDemo(), hidden(), initial, Marker, POSTER, REST, S (+9 more)

### Community 43 - "cursor.tsx"
Cohesion: 0.20
Nodes (15): ARROW_HOTSPOT, GLYPHS, HOTSPOT, ripple(), MacCrosshair(), MacGrab(), MacIbeam(), MacOpenHand() (+7 more)

### Community 44 - "finder-glass/index.tsx"
Cohesion: 0.13
Nodes (19): Column(), DOCUMENTS, FileIcon(), FILMS, FinderGlassDemo(), Geo, GEO, initial (+11 more)

### Community 45 - "Act"
Cohesion: 0.13
Nodes (9): Act, Point, Target, `Act`, `Stage`, The cursor, The stage, Timing (+1 more)

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
Cohesion: 0.16
Nodes (17): Film, clipFindings(), finishReport(), has(), args, analyse(), contentChanges(), record() (+9 more)

### Community 50 - "react"
Cohesion: 0.12
Nodes (23): Bezier, css(), EASE, EaseName, Rect, Camera(), Count(), CountProps (+15 more)

### Community 51 - "google-calendar/index.tsx"
Cohesion: 0.14
Nodes (19): clock(), clockFull(), EVENTS, FOUR, GEO, GoogleCalendar(), Grid(), Header() (+11 more)

### Community 52 - "details.tsx"
Cohesion: 0.15
Nodes (15): Bar(), ChartDraw(), Copy(), DetailComparison(), detailLessons, Emoji(), Id, LINE (+7 more)

### Community 53 - "relationships.tsx"
Cohesion: 0.19
Nodes (18): Actions(), change(), Check(), Horizontal(), initial, LessonId, List(), Person() (+10 more)

### Community 54 - "P1 — Performance"
Cohesion: 0.20
Nodes (10): 3. Findings, A1. ~250 lines of duplicated strategy logic (also the root cause of C1), A2. `dashboard.py` is a 3,288-line file whose middle is a raw HTML string, A3. Dead module and dead dependency: `theme.py` / `dearpygui`, A5. `main.py --self-test` is opaque and has side effects, P1 — Performance, P2 — Architecture & maintainability, P3 — UX / accessibility (only if the user asks for polish) (+2 more)

### Community 55 - "Collapse"
Cohesion: 0.08
Nodes (20): AiCards(), DAYS, FLIGHTS, initial, poster, S, AiChat(), initial (+12 more)

### Community 56 - "dynamic-island/index.tsx"
Cohesion: 0.12
Nodes (15): Bag(), BASE, Box, boxStyle(), BUD, DynamicIsland(), GEO, GROW (+7 more)

### Community 57 - "finder/index.tsx"
Cohesion: 0.17
Nodes (14): DragImage(), FileIcon(), FinderDemo(), Geo, GEO, Ghost, initial, Kind (+6 more)

### Community 58 - "hero-grid/index.tsx"
Cohesion: 0.12
Nodes (21): at(), composition(), Draft, Drafting(), HeroGrid(), Icons(), INITIAL, KEY_ROWS (+13 more)

### Community 59 - "Icon"
Cohesion: 0.06
Nodes (29): Backgrounds(), Digest(), Halftone(), studies, Study(), Calendar(), Cursors(), S (+21 more)

### Community 60 - "powerpoint/index.tsx"
Cohesion: 0.14
Nodes (20): Ledger(), Receipt(), Big(), Box, Design, fit(), G, ICON (+12 more)

### Community 61 - "slack/index.tsx"
Cohesion: 0.24
Nodes (13): Composer(), Face(), HoverBar(), I(), initial, Older(), poster, Rail() (+5 more)

### Community 62 - "choreography/index.tsx"
Cohesion: 0.19
Nodes (12): Bank(), Checkout(), Choreography(), ChoreographyComparison(), choreographyLessons, initial, Locale, locales (+4 more)

### Community 63 - "google-docs/index.tsx"
Cohesion: 0.21
Nodes (12): Card, Docs(), Drop(), GoogleDocs(), Header(), initial, P, poster (+4 more)

### Community 64 - "text-settle.tsx"
Cohesion: 0.25
Nodes (7): CompositionComparison(), Contrasts(), labels, State, TextComparison(), textLessons, UnstableLabel()

### Community 65 - "imessage/index.tsx"
Cohesion: 0.08
Nodes (28): IMessage(), initial, S, SUGGEST, suggestions(), ArrowUp(), initial, Messages() (+20 more)

### Community 66 - "Bento"
Cohesion: 0.33
Nodes (5): Bento, Kinds of tile, Layouts, Planning a grid, The rules

### Community 67 - "layout.mjs"
Cohesion: 0.16
Nodes (11): playwright-core@~1.48.2, launch(), checkClipsForStage(), args, auditLayout(), layoutResult(), errors, options (+3 more)

### Community 68 - "Unified Memory"
Cohesion: 0.15
Nodes (12): 1. Recall before writing, 2. Save context, 3. Hand off work, 4. Validate the vault, MCP Setup, Recall is evidence, not certainty, Runtime Prerequisite, Trust And Data Boundaries (+4 more)

### Community 69 - "main.tsx"
Cohesion: 0.33
Nodes (9): installVirtualClock(), boot(), errorText(), params, showFailure(), Clock, Controls, createFrameDriver() (+1 more)

### Community 70 - "freeform-drag/index.tsx"
Cohesion: 0.20
Nodes (10): BUSY, Cell, cellRect(), DAYS, END, HOURS, move(), S (+2 more)

### Community 71 - "compilerOptions"
Cohesion: 0.17
Nodes (11): compilerOptions, jsx, lib, module, moduleResolution, noEmit, skipLibCheck, strict (+3 more)

### Community 72 - "telegram/index.tsx"
Cohesion: 0.18
Nodes (14): Back(), Clip(), initial, Meta(), Mic(), poster, REST, S (+6 more)

### Community 73 - "trader-scanner"
Cohesion: 0.17
Nodes (11): Data and limits, Example: the reel, Rules, Safety, Steps, The daily scan (before the open), The opening-range breakout scan (during the session), The universe (+3 more)

### Community 74 - "dark-hero/index.tsx"
Cohesion: 0.25
Nodes (8): DarkHero(), initial, Label(), Mark(), OLD, Row(), S, Side()

### Community 75 - "Part 2: Complete Verbatim Audit Report"
Cohesion: 0.17
Nodes (11): 1. Correction on Splash Screen & Packaging, 3. The One Claim That Didn't Hold: The 15 KB Gate, 4. Four Items From the Audit Still Untouched, 5. Two Remaining Risks Worth Naming, 6. Verdict, Do Not Break (Verified Green Baseline), Part 1: Actionable Task List for the Programming Agent, Part 2: Complete Verbatim Audit Report (+3 more)

### Community 76 - "parts/index.ts"
Cohesion: 0.06
Nodes (41): Cards(), initial, S, GLYPHS, initial, KitExtras(), LINES, POSTER (+33 more)

### Community 77 - "ingestion.py"
Cohesion: 0.06
Nodes (19): _test_debouncer(), _clean_html_text(), IntelligenceHarvester, InterruptDebouncer, parse_polymarket_events(), parse_reddit_posts(), parse_rss_atom(), RawEvent (+11 more)

### Community 78 - "linear/index.tsx"
Cohesion: 0.16
Nodes (14): COMMANDS, initial, IssueRow(), LinearDemo(), Priority(), REST, Row, ROWS (+6 more)

### Community 79 - "class-clash.mjs"
Cohesion: 0.27
Nodes (7): args, classDefinitions(), findClashes(), splitSelectors(), unwrapAttributeWhere(), withoutConditions(), find()

### Community 80 - "trader-budget"
Cohesion: 0.18
Nodes (10): Example: the reel, Rules, Safety, Step 1: set the rules once, Step 2: size the trade, Step 3: show the user, trader-budget, Weights mode (kept from v1) (+2 more)

### Community 81 - "phone-touch/index.tsx"
Cohesion: 0.15
Nodes (13): ART, CARD, CARD_NAMES, LIST_TEXT, MobileApp(), Pause(), Phase, Play() (+5 more)

### Community 83 - "trader-risk"
Cohesion: 0.20
Nodes (9): Entries and exits, Example: the reel, Rules, Safety, Steps, The checks, trader-risk, What it never does (+1 more)

### Community 84 - ".get_ui_state"
Cohesion: 0.22
Nodes (13): P1. ~94% of every UI poll is built and thrown away, _drive(), _quote(), test_fill_event_has_monotonic_seq_and_action_label(), test_lifecycle_sequence_warmup_before_live_orders(), test_live_engine_eth_and_leverage_configuration(), test_live_engine_evolve_preserves_fill_tape_and_portfolio_positions(), test_live_engine_ui_state_is_json_safe_and_complete() (+5 more)

### Community 85 - "excel/index.tsx"
Cohesion: 0.19
Nodes (12): Caret(), ChartObject(), Excel(), ExcelDemo(), fmt(), GEO, initial, Row() (+4 more)

### Community 86 - "raycast/index.tsx"
Cohesion: 0.17
Nodes (12): Clip(), ENTRIES, Entry, EntryIcon(), FALLBACK, initial, RaycastDemo(), Root() (+4 more)

### Community 87 - "upload/index.tsx"
Cohesion: 0.18
Nodes (12): DragImage(), Geo, GEO, Ghost, initial, Kind, PdfIcon(), Row() (+4 more)

### Community 88 - "dev.mjs"
Cohesion: 0.28
Nodes (4): devCommand(), main(), packageBin(), root

### Community 89 - "scripts"
Cohesion: 0.40
Nodes (5): scripts, build, check:css, dev, typecheck

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

### Community 96 - "gmail/index.tsx"
Cohesion: 0.24
Nodes (10): Actions(), GmailArchive(), initial, M, Nav(), REST, Row(), ROWS (+2 more)

### Community 97 - "TradeBot0 — Optimization Audit & Work Order"
Cohesion: 0.12
Nodes (14): 0. TL;DR, 1. Project context (read this first), 5. Verification checklist, 6. Decisions the human must make before you start, 7. Appendix — measured facts, Commands, Not a git repository, TradeBot0 — Optimization Audit & Work Order (+6 more)

### Community 98 - "Frontend Design"
Cohesion: 0.29
Nodes (6): Design principles, Frontend Design, Ground your designs in the subject matter, More on writing in design, Process: plan, review against the brief, build, critique, Restraint and self-critique

### Community 99 - "table-edit/index.tsx"
Cohesion: 0.25
Nodes (6): initial, money(), ROWS, S, TableEdit(), TONES

### Community 100 - "Framing"
Cohesion: 0.29
Nodes (6): Checks, Framing, Phones, Small formats and the page, The layouts, The rules

### Community 101 - "Python & Financial Engineering Standards (TradeBot0)"
Cohesion: 0.33
Nodes (5): 1. High-Precision Financial Math, 2. Strong Typing & Documentation, 3. Concurrency & Thread Safety, 4. Defensive Exception Handling & Logging, Python & Financial Engineering Standards (TradeBot0)

### Community 103 - "NOTICE.md"
Cohesion: 0.33
Nodes (3): Photograph sources, Brand artwork sources, Notices

### Community 104 - ".bootstrap_intraday_session"
Cohesion: 0.13
Nodes (9): C1. Monte Carlo EV gate is bypassed at startup, C2. Offline fallback trades against a hardcoded price, C4. Eleven silent `except Exception: pass` blocks, zero logging, C5. Returned list references race with the worker thread, P0 — Correctness, P2. The equity-curve apparatus feeds nothing, P4. Per-tick recomputation of history-derived state, test_micro_bar_aggregation_preserves_wick_extremes_r1() (+1 more)

### Community 105 - "Stageshow"
Cohesion: 0.33
Nodes (5): Contents, Preview, Stageshow, Use the kit, Verify

### Community 106 - "Backgrounds and the whole picture"
Cohesion: 0.33
Nodes (5): Backgrounds and the whole picture, Choose the ground for what it does, Compose the set before the tiles, Objects and drawings as tiles, Recompose for the host

### Community 108 - "Choreography"
Cohesion: 0.33
Nodes (5): A change passing through an interface, Choose the curve for the movement, Choreography, Review the full change, Timing has different jobs

### Community 110 - "AIMRAN Library Skill (814 Animated UI Components)"
Cohesion: 0.33
Nodes (5): AIMRAN Library Skill (814 Animated UI Components), Categories (17 Total / 814 Components), How to Search & Retrieve Components, Integration Guidelines for Desktop / PyWebView (`TradeBot0_Arena.exe`), test_zero_cjk_in_frontend_assets()

### Community 111 - "MonteCarloBracketOdds"
Cohesion: 0.15
Nodes (10): H1. Dependencies are unpinned, unpinned-past-major, and mix concerns, H2. Two build configs that will drift, H3. Tests are not hermetic — they mutate user data, H4. No `.gitignore`, no version control, build artifacts in the tree, H5. The front-end test asserts substrings, not behavior, H6. Doc drift and small inconsistencies, P3 — Packaging, dependencies, hygiene, MonteCarloBracketOdds (+2 more)

### Community 113 - "ClockControl"
Cohesion: 0.20
Nodes (3): clock, ClockControl, Host

### Community 114 - "Test-Driven Development (TDD) Workflow"
Cohesion: 0.50
Nodes (3): 1. Golden Rule, 2. Test Coverage Requirements, Test-Driven Development (TDD) Workflow

### Community 115 - "Trading Safety & Multi-Portfolio Guardrails"
Cohesion: 0.50
Nodes (3): 1. Dual Mode Operation, 2. Invariant Risk Limits (AgentShield), Trading Safety & Multi-Portfolio Guardrails

### Community 121 - "preview.tsx"
Cohesion: 0.22
Nodes (6): StillContext, react-dom@^18.3.1, Boundary, modules, mount(), react-dom

### Community 122 - "Stageshow"
Cohesion: 0.22
Nodes (8): Examples, Gold, How hard to press, Product studies, Specimen and reference sheets, Stageshow, The one idea, The references

### Community 127 - "Verify"
Cohesion: 0.25
Nodes (7): Framing (first, because nothing else matters if this is wrong), Gate, Hand over, Hierarchy and density, Polish (last), Verify, What you see, what you do

### Community 129 - "Craft"
Cohesion: 0.25
Nodes (7): A page of demos, Craft, Density, Icons and logos, Recipes, Restraint, Type

### Community 130 - "Rehearse"
Cohesion: 0.25
Nodes (7): Lines that are never intentional, Other film lines, Prove the still before choreography, Rehearse, The host's own controls, The last pass, What to watch

### Community 131 - "Detailed Execution Phases & Tasks"
Cohesion: 0.22
Nodes (8): Approved Architectural Refinements (R1-R5), Architecture Overview, Detailed Execution Phases & Tasks, Macro Commander & OmniRoute Intelligence Ingestion Workflow Plan (Updated v2 - Approved, 5 Refinements Integrated), Phase 2: Real OmniRoute Gateway Connection Layer, Phase 3: Multi-Domain Intelligence Ingestion Pipeline, Phase 4: Macro Commander with Strict Veto (Option A), Phase 5: UI Macro Ticker & End-to-End Validation

### Community 132 - "Motion"
Cohesion: 0.20
Nodes (8): Changing text and values, Index, Motion, Pace and easing, Phones in motion, Recipes, Scrolling and the camera, Story

## Knowledge Gaps
- **8 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Parts` connect `parts/index.ts` to `Window`, `Text`, `Motion`, `film-checks.mjs`, `size.py`, `States`, `HeroDemo.tsx`, `Act`, `calendar/index.tsx`, `react`, `Phone`, `Collapse`, `Chart`, `Parts`, `subscriptions/index.tsx`?**
  _High betweenness centrality (0.255) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `Stage()` (e.g. with `The rules` and `Recipes`) actually correct?**
  _`Stage()` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Should `BrokerSim` be split into smaller, more focused modules?**
  _Cohesion score 0.08589398023360288 - nodes in this community are weakly interconnected._
- **Why does `size()` connect `size.py` to `parts/index.ts`, `brand-marks/index.tsx`?**
  _High betweenness centrality (0.212) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `Window()` (e.g. with `Recipes` and ``Window``) actually correct?**
  _`Window()` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Should `Window` be split into smaller, more focused modules?**
  _Cohesion score 0.0519774011299435 - nodes in this community are weakly interconnected._
- **Why does `Close()` connect `bento/index.tsx` to `react`, `Detailed Execution Phases & Tasks`?**
  _High betweenness centrality (0.165) - this node is a cross-community bridge._