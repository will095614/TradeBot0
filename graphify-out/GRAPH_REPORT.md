# Graph Report - TradeBot0  (2026-11-07)

## Corpus Check
- 257 files · ~293,595 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 141 file(s) not represented in the graph (top: .css 133, (none) 3, .bat 2)
- WARNING: 141 of 451 files seen (31%) have no supported extractor and are missing from this graph entirely. It may look complete while representing only part of the codebase.

## Summary
- 2841 nodes · 7478 edges · 126 communities (117 shown, 9 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 683 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `3a5de2ae`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Roll
- Window
- LiveArenaEngine
- Collapse
- scan.py
- film-checks.mjs
- size.py
- trader-timemachine/timemachine.py
- entry.py
- Stage
- app.js
- parts/index.tsx
- exit.py
- film.mjs
- check.py
- BrokerSim
- audit_all_components.py
- _ArenaBridgeApi
- kit/index.ts
- Portfolio
- Teaching pairs
- OmniRoute Deployment & Integration Guide
- kit/index.ts
- Chart
- ruled-bento/index.tsx
- notion/index.tsx
- bento/index.tsx
- live_engine.py
- Avatar
- subscriptions/index.tsx
- stage.tsx
- OmniRoute Headless Installation, Auto-Routing & Troubleshooting Playbook for AI Agents
- test_phase3_ingestion.py
- package.json
- spotify/index.tsx
- figma/index.tsx
- OmniRouteClient
- wikipedia/index.tsx
- act.ts
- contrasts.tsx
- composition.tsx
- .evaluate_bracket
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
- P3 — Packaging, dependencies, hygiene
- Text
- dynamic-island/index.tsx
- finder/index.tsx
- Stage
- telegram/index.tsx
- powerpoint/index.tsx
- slack/index.tsx
- choreography/index.tsx
- google-docs/index.tsx
- upload/index.tsx
- imessage/index.tsx
- Motion
- layout.mjs
- Unified Memory
- cursor-morph.tsx
- Avatar
- compilerOptions
- datetime
- trader-scanner
- lucide-react
- Part 2: Complete Verbatim Audit Report
- ._live_loop
- .bootstrap_intraday_session
- linear/index.tsx
- class-clash.mjs
- trader-budget
- phone-touch/index.tsx
- excel/index.tsx
- trader-risk
- raycast/index.tsx
- `Thread`, `Bubble`, `Stamp`, `Receipt`, `Keyboard`
- .stop
- Verify
- dev.mjs
- text-settle.tsx
- edges.tsx
- style.tsx
- trader-entry
- trader-exit
- trader-timemachine
- cursor-resize/index.tsx
- Icon
- TradeBot0 — Optimization Audit & Work Order
- Frontend Design
- presence/index.tsx
- Framing
- Python & Financial Engineering Standards (TradeBot0)
- Stageshow
- NOTICE.md
- ClockControl
- Stageshow
- Backgrounds and the whole picture
- Bento
- Choreography
- SimClock
- Rehearse
- Keyboard
- scripts
- Detailed Execution Phases & Tasks
- Test-Driven Development (TDD) Workflow
- Trading Safety & Multi-Portfolio Guardrails
- Review
- cursor-morph/README.md
- products.md
- A4. Repeated wiring, scattered constants, lookup tables in the wrong place
- Craft
- Point
- scan_daily
- LiveQuote

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
- 2-file cycle: `.agent/skills/stageshow/teaching/contrasts.tsx -> .agent/skills/stageshow/teaching/relationships.tsx -> .agent/skills/stageshow/teaching/contrasts.tsx`
- 2-file cycle: `.agent/skills/stageshow/teaching/composition.tsx -> .agent/skills/stageshow/teaching/contrasts.tsx -> .agent/skills/stageshow/teaching/composition.tsx`

## Communities (126 total, 9 thin omitted)

### Community 0 - "Roll"
Cohesion: 0.07
Nodes (32): Controls(), DATA, DIFF, initial, MORE, POSTER, ROWS, S (+24 more)

### Community 1 - "Window"
Cohesion: 0.06
Nodes (31): CloseUp(), initial, poster, S, FadeCrop(), FILL, ROWS, FormError() (+23 more)

### Community 2 - "LiveArenaEngine"
Cohesion: 0.20
Nodes (16): LiveArenaEngine, _drive(), _quote(), test_anti_churn_cooldown_prevents_same_timestamp_reentry(), test_auto_evolve_timer_and_toggle(), test_fill_event_has_monotonic_seq_and_action_label(), test_lifecycle_sequence_warmup_before_live_orders(), test_live_engine_bidirectional_long_and_short_execution() (+8 more)

### Community 3 - "Collapse"
Cohesion: 0.08
Nodes (18): AiCards(), DAYS, FLIGHTS, initial, poster, S, AiChat(), initial (+10 more)

### Community 4 - "scan.py"
Cohesion: 0.07
Nodes (43): _absorb(), build_universe(), chart_path(), classify(), clock_label(), cmd_daily(), cmd_orb(), confirm() (+35 more)

### Community 5 - "film-checks.mjs"
Cohesion: 0.12
Nodes (78): alphaOf(), animating(), cameraMoving(), checkStage(), collectSurfaces(), detectBoxEdges(), detectBylineGap(), detectClipped() (+70 more)

### Community 6 - "size.py"
Cohesion: 0.07
Nodes (36): Brand marks, allocate(), bracket_order(), eastern_offset(), eastern_to_utc(), _f(), fresh_price(), load_config() (+28 more)

### Community 7 - "trader-timemachine/timemachine.py"
Cohesion: 0.05
Nodes (43): build_pool(), cents_away(), chart_result(), chart_url(), clock12(), clock24(), cmd_chart(), cmd_run() (+35 more)

### Community 8 - "entry.py"
Cohesion: 0.07
Nodes (45): ampm(), bar_line(), chart_path(), chart_range(), cmd_check(), cmd_watch(), emit(), on_trigger() (+37 more)

### Community 9 - "Stage"
Cohesion: 0.07
Nodes (37): Collection, CollectionStudy(), Detail, DetailStudy(), UsageDelivery(), Annotations(), BranchState, BranchStudy() (+29 more)

### Community 10 - "app.js"
Cohesion: 0.07
Nodes (59): P6. Front-end rebuilds its whole DOM every second, addChartBeacon(), animCandles, changeEvolveInterval(), chartBeacons, currentSplashSteps, drawPriceChart(), drawSmoothCurve() (+51 more)

### Community 11 - "parts/index.tsx"
Cohesion: 0.08
Nodes (22): GLYPHS, initial, KitExtras(), LINES, POSTER, REST, S, STRENGTH (+14 more)

### Community 12 - "exit.py"
Cohesion: 0.08
Nodes (39): ampm(), atr_of(), build_plan(), cents(), cmd_plan(), cmd_show(), compute(), D() (+31 more)

### Community 13 - "film.mjs"
Cohesion: 0.05
Nodes (45): args, at, cameraSkipped, checkClips(), checkClipsForStage(), clipFor(), clipped, clipSamples (+37 more)

### Community 14 - "check.py"
Cohesion: 0.08
Nodes (29): account(), business_days(), _cent(), check(), day_trades(), eastern_offset(), eastern_to_utc(), _f() (+21 more)

### Community 15 - "BrokerSim"
Cohesion: 0.09
Nodes (26): 2. Ground rules — do not break these, Architectural Highlights, audit_broker_matching_engine(), BrokerSim, ExecutionReason, OrderSide, OrderStatus, OrderTicket (+18 more)

### Community 16 - "audit_all_components.py"
Cohesion: 0.11
Nodes (19): C7. Sharpe / Sortino are numerically meaningless as displayed, assert_true(), audit_competitors_and_sizing(), audit_frontend_cjk(), audit_genetic_evolution(), audit_leaderboard(), audit_macro_commander(), audit_omniroute_and_ingestion() (+11 more)

### Community 18 - "kit/index.ts"
Cohesion: 0.09
Nodes (31): calendar, figma, mail, notion, slack, testFlight, DynamicIsland(), Checkout() (+23 more)

### Community 19 - "Portfolio"
Cohesion: 0.12
Nodes (12): C6. Breakeven exits are counted as losses, P3. Rankings recomputed on every poll, over ever-growing data, FillEvent, Portfolio, isolate_arena_memory(), test_bidirectional_short_win_rate_and_closing_fill(), test_portfolio_breakeven_trade_does_not_count_as_loss(), test_portfolio_buy_and_sell_accounting() (+4 more)

### Community 20 - "Teaching pairs"
Cohesion: 0.10
Nodes (16): Check it, Defining a look, From a codebase, From a public site, Looks, The built-in looks, The tokens, What a look doesn't change (+8 more)

### Community 21 - "OmniRoute Deployment & Integration Guide"
Cohesion: 0.05
Nodes (37): 10.1 Monitoring **[V]**, 10.2 Circuit breakers **[V]**, 10.3 Data, backup, upgrade, uninstall, 10. Operations, 11. Troubleshooting, 12. Client Reference Sketch for the Arena App (non-normative) **[R]**, 13. Deployment Acceptance Checklist (maps to plan Phase 2 checkpoint), 14. Sources (+29 more)

### Community 22 - "kit/index.ts"
Cohesion: 0.09
Nodes (29): BrandMarks(), groups, names, Sheet(), BrandAsset, brandMarks, BrandName, Code() (+21 more)

### Community 23 - "Chart"
Cohesion: 0.17
Nodes (16): ChartScrub(), DAYS, money(), NAMES, S, script(), TOTAL, W (+8 more)

### Community 24 - "ruled-bento/index.tsx"
Cohesion: 0.10
Nodes (28): Chrome(), Content(), Figure(), files, Specimen, specimens, Tool(), after (+20 more)

### Community 25 - "notion/index.tsx"
Cohesion: 0.17
Nodes (12): Crumb(), initial, Item, ITEMS, NotionSlash(), Page(), S, Scene() (+4 more)

### Community 26 - "bento/index.tsx"
Cohesion: 0.21
Nodes (18): after, Approvals(), Beat, beat(), before, Bento(), Cards(), Close() (+10 more)

### Community 27 - "live_engine.py"
Cohesion: 0.08
Nodes (19): main(), H6. Doc drift and small inconsistencies, CompetitorStats, CandleBar, ETHFeed, MonteCarloOddsEvaluator, TimeMachineArena, ArenaDashboard (+11 more)

### Community 28 - "Avatar"
Cohesion: 0.10
Nodes (18): Cards(), initial, S, AvatarProps, hue(), PEOPLE, Card(), Chip() (+10 more)

### Community 29 - "subscriptions/index.tsx"
Cohesion: 0.14
Nodes (14): Mark(), Checkout(), OLD, Pay, POSTER, Pulse, pulse(), S (+6 more)

### Community 30 - "stage.tsx"
Cohesion: 0.18
Nodes (17): Script, CursorKind, CursorStyle, capsOf(), KEYCAPS, Keycaps(), KeysAt, Fidelity (+9 more)

### Community 31 - "OmniRoute Headless Installation, Auto-Routing & Troubleshooting Playbook for AI Agents"
Cohesion: 0.07
Nodes (27): 1. Agent Directives & Execution Rules, 2.1 Check Port `20128` Availability, 2.2 Verify Strict Node.js Runtime Version, 2.3 Verify Native Build Tools (Required for `better-sqlite3`), 2.4 Clean Up Corrupted Previous State, 2. Phase 1: Pre-Flight Diagnostics & Cleanup, 3.1 Generate Consolidated `.env` File, 3. Phase 2: Pure Backend & Auto-Routing Configuration (`.env`) (+19 more)

### Community 32 - "test_phase3_ingestion.py"
Cohesion: 0.07
Nodes (18): _test_debouncer(), DeduplicationBuffer, IntelligenceHarvester, InterruptDebouncer, parse_polymarket_events(), parse_reddit_posts(), parse_rss_atom(), RawEvent (+10 more)

### Community 33 - "package.json"
Cohesion: 0.10
Nodes (24): description, devDependencies, postcss@^8.5.6, @types/react@^18.3.1, @types/react-dom@^18.3.1, typescript@^5.6.3, vite@^6.4.5, @vitejs/plugin-react@^4.7.0 (+16 more)

### Community 34 - "spotify/index.tsx"
Cohesion: 0.21
Nodes (9): Art(), Eq(), fmt(), Id, initial, ROWS, S, SONGS (+1 more)

### Community 35 - "figma/index.tsx"
Cohesion: 0.25
Nodes (9): FigmaDemo(), hex(), initial, LayerIcon(), LAYERS, MAYA, mayaAt(), S (+1 more)

### Community 36 - "OmniRouteClient"
Cohesion: 0.06
Nodes (26): main(), StructuredEvent, MacroCommander, MacroRegimeState, compute_backoff(), extract_json(), OmniRouteClient, test_macro_commander_skips_chat_when_gateway_offline() (+18 more)

### Community 37 - "wikipedia/index.tsx"
Cohesion: 0.13
Nodes (22): CDX, CdxIcon(), CROPS, Fuji(), Header(), Infobox(), initial, Lake() (+14 more)

### Community 38 - "act.ts"
Cohesion: 0.18
Nodes (20): checkSeam(), createAct(), Ref, Stopped, bezier(), drawnScale(), EMPTY, layoutRectOf() (+12 more)

### Community 39 - "contrasts.tsx"
Cohesion: 0.09
Nodes (27): Cursor(), MacPointer(), CompositionComparison(), ContinuityComparison(), continuityLessons, drag(), initial, pending() (+19 more)

### Community 40 - "composition.tsx"
Cohesion: 0.14
Nodes (22): Anatomy(), Compact(), compositionLessons, Contrast(), ControlAlignment(), Decoration(), Density(), EdgeSeparation() (+14 more)

### Community 41 - ".evaluate_bracket"
Cohesion: 0.27
Nodes (5): MonteCarloBracketOdds, _get_assets_dir(), test_startup_ev_gate_enforcement(), test_monte_carlo_ev_gate_odds_evaluation(), 2. What Is Verified Green

### Community 42 - "HeroDemo.tsx"
Cohesion: 0.13
Nodes (16): annotate(), hidden(), initial, Marker, POSTER, REST, S, script() (+8 more)

### Community 43 - "cursor.tsx"
Cohesion: 0.20
Nodes (15): ARROW_HOTSPOT, GLYPHS, HOTSPOT, ripple(), MacCrosshair(), MacGrab(), MacIbeam(), MacOpenHand() (+7 more)

### Community 44 - "finder-glass/index.tsx"
Cohesion: 0.13
Nodes (19): Column(), DOCUMENTS, FileIcon(), FILMS, FinderGlassDemo(), Geo, GEO, initial (+11 more)

### Community 45 - "Act"
Cohesion: 0.17
Nodes (6): Act, `Act`, `Stage`, The cursor, The stage, Loops

### Community 46 - "scenes.tsx"
Cohesion: 0.24
Nodes (20): Action(), ColoredLayers(), CropFiller(), DashboardPhone(), FileList(), FOLDER, LibraryApp(), Mark() (+12 more)

### Community 47 - "calendar/index.tsx"
Cohesion: 0.14
Nodes (20): Avail, BUSY, Calendar(), carry(), Cell, cellRect(), DAYS, END (+12 more)

### Community 48 - "staggered-bento/index.tsx"
Cohesion: 0.20
Nodes (19): after, AZ, Azulejo(), Beat, beat(), before, Book(), Coast() (+11 more)

### Community 49 - "jumps.mjs"
Cohesion: 0.17
Nodes (16): clipFindings(), finishReport(), has(), args, analyse(), contentChanges(), record(), errors (+8 more)

### Community 50 - "react"
Cohesion: 0.15
Nodes (19): Rect, Count(), CountProps, digitsFromRight(), STRIP, unitOf(), Expand(), Fly() (+11 more)

### Community 51 - "google-calendar/index.tsx"
Cohesion: 0.14
Nodes (19): clock(), clockFull(), EVENTS, FOUR, GEO, GoogleCalendar(), Grid(), Header() (+11 more)

### Community 52 - "details.tsx"
Cohesion: 0.15
Nodes (15): Bar(), ChartDraw(), Copy(), DetailComparison(), detailLessons, Emoji(), Id, LINE (+7 more)

### Community 53 - "relationships.tsx"
Cohesion: 0.19
Nodes (18): Actions(), change(), Check(), Horizontal(), initial, LessonId, List(), Person() (+10 more)

### Community 54 - "P3 — Packaging, dependencies, hygiene"
Cohesion: 0.15
Nodes (13): 3. Findings, A1. ~250 lines of duplicated strategy logic (also the root cause of C1), A2. `dashboard.py` is a 3,288-line file whose middle is a raw HTML string, A3. Dead module and dead dependency: `theme.py` / `dearpygui`, A5. `main.py --self-test` is opaque and has side effects, H1. Dependencies are unpinned, unpinned-past-major, and mix concerns, H2. Two build configs that will drift, H3. Tests are not hermetic — they mutate user data (+5 more)

### Community 55 - "Text"
Cohesion: 0.13
Nodes (17): Actions(), GmailArchive(), initial, M, Nav(), REST, Row(), ROWS (+9 more)

### Community 56 - "dynamic-island/index.tsx"
Cohesion: 0.12
Nodes (14): Bag(), BASE, Box, boxStyle(), BUD, GEO, GROW, Island() (+6 more)

### Community 57 - "finder/index.tsx"
Cohesion: 0.17
Nodes (14): DragImage(), FileIcon(), FinderDemo(), Geo, GEO, Ghost, initial, Kind (+6 more)

### Community 58 - "Stage"
Cohesion: 0.06
Nodes (38): Card(), PaymentsStatic(), REVENUE, ROWS, Glass(), at(), composition(), Draft (+30 more)

### Community 59 - "telegram/index.tsx"
Cohesion: 0.18
Nodes (14): Back(), Clip(), initial, Meta(), Mic(), poster, REST, S (+6 more)

### Community 60 - "powerpoint/index.tsx"
Cohesion: 0.10
Nodes (23): ACCENTS, initial, PanelAnnotation(), poster, S, Big(), Box, Design (+15 more)

### Community 61 - "slack/index.tsx"
Cohesion: 0.24
Nodes (13): Composer(), Face(), HoverBar(), I(), initial, Older(), poster, Rail() (+5 more)

### Community 62 - "choreography/index.tsx"
Cohesion: 0.19
Nodes (12): Bank(), Checkout(), Choreography(), ChoreographyComparison(), choreographyLessons, initial, Locale, locales (+4 more)

### Community 63 - "google-docs/index.tsx"
Cohesion: 0.21
Nodes (12): Card, Docs(), Drop(), GoogleDocs(), Header(), initial, P, poster (+4 more)

### Community 64 - "upload/index.tsx"
Cohesion: 0.18
Nodes (12): DragImage(), Geo, GEO, Ghost, initial, Kind, PdfIcon(), Row() (+4 more)

### Community 65 - "imessage/index.tsx"
Cohesion: 0.11
Nodes (22): IMessage(), initial, S, SUGGEST, suggestions(), ArrowUp(), initial, Messages() (+14 more)

### Community 66 - "Motion"
Cohesion: 0.20
Nodes (8): Changing text and values, Index, Motion, Pace and easing, Phones in motion, Recipes, Scrolling and the camera, Story

### Community 67 - "layout.mjs"
Cohesion: 0.18
Nodes (10): playwright-core@~1.48.2, launch(), args, auditLayout(), layoutResult(), errors, options, result (+2 more)

### Community 68 - "Unified Memory"
Cohesion: 0.15
Nodes (12): 1. Recall before writing, 2. Save context, 3. Hand off work, 4. Validate the vault, MCP Setup, Recall is evidence, not certainty, Runtime Prerequisite, Trust And Data Boundaries (+4 more)

### Community 69 - "cursor-morph.tsx"
Cohesion: 0.05
Nodes (42): CIRCLE, CursorMorph(), HEAD, Look, MorphStyle, path(), POINTER, Pt (+34 more)

### Community 70 - "Avatar"
Cohesion: 0.07
Nodes (28): CornerChip(), S, DarkBento(), TRACKS, BUSY, Cell, cellRect(), DAYS (+20 more)

### Community 71 - "compilerOptions"
Cohesion: 0.17
Nodes (11): compilerOptions, jsx, lib, module, moduleResolution, noEmit, skipLibCheck, strict (+3 more)

### Community 72 - "datetime"
Cohesion: 0.23
Nodes (8): eastern_offset(), _nth_sunday(), daily_closes(), eastern_offset(), eastern_to_utc(), _nth_sunday(), to_eastern(), ts_to_eastern()

### Community 73 - "trader-scanner"
Cohesion: 0.17
Nodes (11): Data and limits, Example: the reel, Rules, Safety, Steps, The daily scan (before the open), The opening-range breakout scan (during the session), The universe (+3 more)

### Community 74 - "lucide-react"
Cohesion: 0.11
Nodes (15): Buttons(), initial, POSTER, S, DarkHero(), initial, Label(), OLD (+7 more)

### Community 75 - "Part 2: Complete Verbatim Audit Report"
Cohesion: 0.17
Nodes (11): 1. Correction on Splash Screen & Packaging, 3. The One Claim That Didn't Hold: The 15 KB Gate, 4. Four Items From the Audit Still Untouched, 5. Two Remaining Risks Worth Naming, 6. Verdict, Do Not Break (Verified Green Baseline), Part 1: Actionable Task List for the Programming Agent, Part 2: Complete Verbatim Audit Report (+3 more)

### Community 76 - "._live_loop"
Cohesion: 0.13
Nodes (12): series(), C1. Monte Carlo EV gate is bypassed at startup, C2. Offline fallback trades against a hardcoded price, C4. Eleven silent `except Exception: pass` blocks, zero logging, C5. Returned list references race with the worker thread, P0 — Correctness, P1. ~94% of every UI poll is built and thrown away, P1 — Performance (+4 more)

### Community 77 - ".bootstrap_intraday_session"
Cohesion: 0.13
Nodes (5): Phase 4: Macro Commander with Strict Veto (Option A), test_macro_veto_intent_preserved_in_live_evaluation(), test_micro_bar_aggregation_preserves_wick_extremes_r1(), test_live_engine_enforces_macro_commander_veto(), test_live_engine_refresh_intel_digest()

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

### Community 82 - "excel/index.tsx"
Cohesion: 0.19
Nodes (12): Caret(), ChartObject(), Excel(), ExcelDemo(), fmt(), GEO, initial, Row() (+4 more)

### Community 83 - "trader-risk"
Cohesion: 0.20
Nodes (9): Entries and exits, Example: the reel, Rules, Safety, Steps, The checks, trader-risk, What it never does (+1 more)

### Community 84 - "raycast/index.tsx"
Cohesion: 0.17
Nodes (12): Clip(), ENTRIES, Entry, EntryIcon(), FALLBACK, initial, RaycastDemo(), Root() (+4 more)

### Community 85 - "`Thread`, `Bubble`, `Stamp`, `Receipt`, `Keyboard`"
Cohesion: 0.40
Nodes (4): Explicit replay, Layout and CSS scope, Motion parts, The kit, piece by piece

### Community 86 - ".stop"
Cohesion: 0.24
Nodes (6): 4. Suggested execution order, C3. `stop()` does not join the worker thread, audit_cadence_and_microbar(), audit_ui_bridge_state(), seed_engine_candles(), test_candle_cadence_dispatcher_timing_and_dispatch()

### Community 87 - "Verify"
Cohesion: 0.22
Nodes (8): Framing (first, because nothing else matters if this is wrong), Gate, Hand over, Hierarchy and density, Motion (animated scenes), Polish (last), Verify, What you see, what you do

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

### Community 96 - "Icon"
Cohesion: 0.08
Nodes (24): Backgrounds(), Digest(), Halftone(), studies, Study(), Cursors(), S, Scene() (+16 more)

### Community 97 - "TradeBot0 — Optimization Audit & Work Order"
Cohesion: 0.12
Nodes (14): 0. TL;DR, 1. Project context (read this first), 5. Verification checklist, 6. Decisions the human must make before you start, 7. Appendix — measured facts, Commands, Not a git repository, TradeBot0 — Optimization Audit & Work Order (+6 more)

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

### Community 102 - "Stageshow"
Cohesion: 0.20
Nodes (9): Examples, Gold, How hard to press, Product studies, Specimen and reference sheets, Stageshow, The one idea, The references (+1 more)

### Community 103 - "NOTICE.md"
Cohesion: 0.33
Nodes (3): Photograph sources, Brand artwork sources, Notices

### Community 104 - "ClockControl"
Cohesion: 0.15
Nodes (4): clock, ClockControl, Host, Timing

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

### Community 110 - "Rehearse"
Cohesion: 0.22
Nodes (8): Film, Lines that are never intentional, Other film lines, Prove the still before choreography, Rehearse, The host's own controls, The last pass, What to watch

### Community 111 - "Keyboard"
Cohesion: 0.50
Nodes (4): Glyph(), Keyboard(), KeyboardProps, ROWS

### Community 112 - "scripts"
Cohesion: 0.40
Nodes (5): scripts, build, check:css, dev, typecheck

### Community 113 - "Detailed Execution Phases & Tasks"
Cohesion: 0.22
Nodes (8): Approved Architectural Refinements (R1-R5), Architecture Overview, Detailed Execution Phases & Tasks, Macro Commander & OmniRoute Intelligence Ingestion Workflow Plan (Updated v2 - Approved, 5 Refinements Integrated), Phase 1: Paced 3~5s Candlestick Cadence Dispatcher & Equity-Ranked Leaderboard, Phase 2: Real OmniRoute Gateway Connection Layer, Phase 3: Multi-Domain Intelligence Ingestion Pipeline, Phase 5: UI Macro Ticker & End-to-End Validation

### Community 114 - "Test-Driven Development (TDD) Workflow"
Cohesion: 0.50
Nodes (3): 1. Golden Rule, 2. Test Coverage Requirements, Test-Driven Development (TDD) Workflow

### Community 115 - "Trading Safety & Multi-Portfolio Guardrails"
Cohesion: 0.50
Nodes (3): 1. Dual Mode Operation, 2. Invariant Risk Limits (AgentShield), Trading Safety & Multi-Portfolio Guardrails

### Community 122 - "Craft"
Cohesion: 0.25
Nodes (7): A page of demos, Craft, Density, Icons and logos, Recipes, Restraint, Type

### Community 123 - "Point"
Cohesion: 0.38
Nodes (4): ActEnv, Keys, Point, Target

### Community 124 - "scan_daily"
Cohesion: 0.33
Nodes (3): find_setups(), rsi(), scan_daily()

## Knowledge Gaps
- **9 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Parts` connect `kit/index.ts` to `Roll`, `Collapse`, `film-checks.mjs`, `size.py`, `Stage`, `parts/index.tsx`, `kit/index.ts`, `Chart`, `notion/index.tsx`, `bento/index.tsx`, `Avatar`, `contrasts.tsx`, `HeroDemo.tsx`, `Act`, `calendar/index.tsx`, `react`, `Text`, `Stage`, `Motion`, `Avatar`, ``Thread`, `Bubble`, `Stamp`, `Receipt`, `Keyboard``, `Icon`?**
  _High betweenness centrality (0.252) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `Stage()` (e.g. with `The rules` and `Recipes`) actually correct?**
  _`Stage()` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Should `Roll` be split into smaller, more focused modules?**
  _Cohesion score 0.07092198581560284 - nodes in this community are weakly interconnected._
- **Why does `size()` connect `size.py` to `kit/index.ts`?**
  _High betweenness centrality (0.221) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `Window()` (e.g. with `Recipes` and ``Window``) actually correct?**
  _`Window()` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Should `Window` be split into smaller, more focused modules?**
  _Cohesion score 0.06292517006802721 - nodes in this community are weakly interconnected._
- **Why does `Close()` connect `bento/index.tsx` to `Detailed Execution Phases & Tasks`, `react`?**
  _High betweenness centrality (0.161) - this node is a cross-community bridge._