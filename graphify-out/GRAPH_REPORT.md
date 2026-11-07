# Graph Report - TradeBot0  (2026-11-07)

## Corpus Check
- 257 files · ~294,869 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 141 file(s) not represented in the graph (top: .css 133, (none) 3, .bat 2)
- WARNING: 141 of 451 files seen (31%) have no supported extractor and are missing from this graph entirely. It may look complete while representing only part of the codebase.

## Summary
- 2853 nodes · 7512 edges · 134 communities (124 shown, 10 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 680 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `52bde117`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- kit-extras/index.tsx
- Stage
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
- CompetitorGenome
- audit_all_components.py
- _ArenaBridgeApi
- Phone
- OrderSide
- .rect
- OmniRoute Deployment & Integration Guide
- BrokerSim
- Chart
- ruled-bento/index.tsx
- notion/index.tsx
- bento/index.tsx
- live_engine.py
- Parts
- subscriptions/index.tsx
- cursor-morph/index.tsx
- OmniRoute Headless Installation, Auto-Routing & Troubleshooting Playbook for AI Agents
- kit/index.ts
- package.json
- spotify/index.tsx
- Row
- OmniRouteClient
- wikipedia/index.tsx
- act.ts
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
- P3 — Packaging, dependencies, hygiene
- Collapse
- dynamic-island/index.tsx
- finder/index.tsx
- hero-grid/index.tsx
- Icon
- powerpoint/index.tsx
- slack/index.tsx
- choreography/index.tsx
- google-docs/index.tsx
- stage.tsx
- imessage/index.tsx
- parts/index.tsx
- layout.mjs
- Unified Memory
- main.tsx
- freeform-drag/index.tsx
- compilerOptions
- telegram/index.tsx
- trader-scanner
- lucide-react
- Part 2: Complete Verbatim Audit Report
- parts/index.ts
- ._live_loop
- linear/index.tsx
- class-clash.mjs
- trader-budget
- upload/index.tsx
- Connector
- trader-risk
- .get_ui_state
- excel/index.tsx
- raycast/index.tsx
- upload/index.tsx
- dev.mjs
- Leaderboard
- edges.tsx
- style.tsx
- trader-entry
- trader-exit
- trader-timemachine
- cursor-resize/index.tsx
- story/index.tsx
- TradeBot0 — Optimization Audit & Work Order
- Frontend Design
- Window
- Framing
- Python & Financial Engineering Standards (TradeBot0)
- Motion
- NOTICE.md
- .bootstrap_intraday_session
- Stageshow
- Backgrounds and the whole picture
- Bento
- Choreography
- SimClock
- figma/index.tsx
- .evaluate_bracket
- scripts
- ClockControl
- Test-Driven Development (TDD) Workflow
- Trading Safety & Multi-Portfolio Guardrails
- Review
- cursor-morph/README.md
- products.md
- preview.tsx
- Stageshow
- Point
- cursors/index.tsx
- table-edit/index.tsx
- Teaching pairs
- Verify
- LiveQuote
- Craft
- Rehearse
- Detailed Execution Phases & Tasks
- The kit, piece by piece
- .stop

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
- `5. Verification checklist` --references--> `_drive()`  [INFERRED]
  OPTIMIZATION_AUDIT.md → tests/test_live_engine.py
- `12. Client Reference Sketch for the Arena App (non-normative) **[R]**` --references--> `extract_json()`  [INFERRED]
  omniroute_deployment_guide.md → src/intelligence/omniroute_client.py
- `13. Deployment Acceptance Checklist (maps to plan Phase 2 checkpoint)` --references--> `extract_json()`  [INFERRED]
  omniroute_deployment_guide.md → src/intelligence/omniroute_client.py

## Import Cycles
- 2-file cycle: `.agent/skills/stageshow/teaching/composition.tsx -> .agent/skills/stageshow/teaching/contrasts.tsx -> .agent/skills/stageshow/teaching/composition.tsx`
- 2-file cycle: `.agent/skills/stageshow/teaching/contrasts.tsx -> .agent/skills/stageshow/teaching/relationships.tsx -> .agent/skills/stageshow/teaching/contrasts.tsx`

## Communities (134 total, 10 thin omitted)

### Community 0 - "kit-extras/index.tsx"
Cohesion: 0.08
Nodes (21): GLYPHS, initial, KitExtras(), LINES, POSTER, REST, S, STRENGTH (+13 more)

### Community 1 - "Stage"
Cohesion: 0.08
Nodes (35): Ledger(), Receipt(), CloseUp(), initial, poster, S, Card(), PaymentsStatic() (+27 more)

### Community 2 - "LiveArenaEngine"
Cohesion: 0.13
Nodes (9): Phase 4: Macro Commander with Strict Veto (Option A), A4. Repeated wiring, scattered constants, lookup tables in the wrong place, LiveArenaEngine, test_anti_churn_cooldown_prevents_same_timestamp_reentry(), test_auto_evolve_timer_and_toggle(), test_live_engine_bidirectional_long_and_short_execution(), test_macro_veto_intent_preserved_in_live_evaluation(), test_candle_cadence_dispatcher_timing_and_dispatch() (+1 more)

### Community 3 - "cursor-morph.tsx"
Cohesion: 0.21
Nodes (10): CIRCLE, HEAD, Look, path(), POINTER, Pt, rgba(), Shape() (+2 more)

### Community 4 - "scan.py"
Cohesion: 0.05
Nodes (52): _absorb(), build_universe(), chart_path(), classify(), clock_label(), cmd_daily(), cmd_orb(), confirm() (+44 more)

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
Nodes (47): ampm(), bar_line(), chart_path(), chart_range(), cmd_check(), cmd_watch(), emit(), on_trigger() (+39 more)

### Community 9 - "States"
Cohesion: 0.12
Nodes (18): Annotations(), BranchState, BranchStudy(), ChartState, ChartStudy(), FlowState, FlowStudy(), FollowState (+10 more)

### Community 10 - "app.js"
Cohesion: 0.07
Nodes (63): P6. Front-end rebuilds its whole DOM every second, addChartBeacon(), animCandles, changeEvolveInterval(), chartBeacons, currentSplashSteps, drawPriceChart(), drawSmoothCurve() (+55 more)

### Community 11 - "viewer.tsx"
Cohesion: 0.24
Nodes (9): curated, examples, extra, groups, listed, products, specimens, mount() (+1 more)

### Community 12 - "exit.py"
Cohesion: 0.08
Nodes (39): ampm(), atr_of(), build_plan(), cents(), cmd_plan(), cmd_show(), compute(), D() (+31 more)

### Community 13 - "film.mjs"
Cohesion: 0.05
Nodes (46): args, at, cameraSkipped, checkClips(), checkClipsForStage(), clipFor(), clipped, clipSamples (+38 more)

### Community 14 - "check.py"
Cohesion: 0.08
Nodes (29): account(), business_days(), _cent(), check(), day_trades(), eastern_offset(), eastern_to_utc(), _f() (+21 more)

### Community 15 - "CompetitorGenome"
Cohesion: 0.10
Nodes (16): Architectural Highlights, audit_competitors_and_sizing(), audit_genetic_evolution(), GeneticEvolver, AggressiveCompetitor, ATRDynamicCompetitor, BaseCompetitor, CompetitorGenome (+8 more)

### Community 16 - "audit_all_components.py"
Cohesion: 0.21
Nodes (13): assert_true(), audit_cadence_and_microbar(), audit_frontend_cjk(), audit_leaderboard(), audit_macro_commander(), audit_omniroute_and_ingestion(), audit_timemachine_mc(), audit_ui_bridge_state() (+5 more)

### Community 18 - "Phone"
Cohesion: 0.13
Nodes (22): Checkout(), Phones(), BANDS, Battery(), CORNER, FRAMES, IPHONE, LockScreen() (+14 more)

### Community 19 - "OrderSide"
Cohesion: 0.14
Nodes (15): ExecutionReason, FillEvent, OrderSide, OrderStatus, OrderType, PositionSide, Portfolio, RiskGuard (+7 more)

### Community 20 - ".rect"
Cohesion: 0.17
Nodes (10): Check it, Defining a look, From a codebase, From a public site, Looks, The built-in looks, The tokens, What a look doesn't change (+2 more)

### Community 21 - "OmniRoute Deployment & Integration Guide"
Cohesion: 0.05
Nodes (37): 10.1 Monitoring **[V]**, 10.2 Circuit breakers **[V]**, 10.3 Data, backup, upgrade, uninstall, 10. Operations, 11. Troubleshooting, 12. Client Reference Sketch for the Arena App (non-normative) **[R]**, 13. Deployment Acceptance Checklist (maps to plan Phase 2 checkpoint), 14. Sources (+29 more)

### Community 22 - "BrokerSim"
Cohesion: 0.11
Nodes (12): 2. Ground rules — do not break these, audit_broker_matching_engine(), BrokerSim, OrderTicket, test_broker_sim_bracket_stop_loss_trigger(), test_broker_sim_leverage_liquidation_protection(), test_broker_sim_multi_portfolio_simultaneous_execution(), test_broker_sim_position_cap_enforcement() (+4 more)

### Community 23 - "Chart"
Cohesion: 0.17
Nodes (16): ChartScrub(), DAYS, money(), NAMES, S, script(), TOTAL, W (+8 more)

### Community 24 - "ruled-bento/index.tsx"
Cohesion: 0.17
Nodes (21): after, arc(), Beat, beat(), before, create(), Drivers(), PRIMARY (+13 more)

### Community 25 - "notion/index.tsx"
Cohesion: 0.20
Nodes (11): Crumb(), initial, Item, ITEMS, NotionSlash(), Page(), S, Scene() (+3 more)

### Community 26 - "bento/index.tsx"
Cohesion: 0.15
Nodes (22): calendar, figma, mail, notion, slack, testFlight, after, Approvals() (+14 more)

### Community 27 - "live_engine.py"
Cohesion: 0.09
Nodes (10): main(), CompetitorStats, CandleBar, ETHFeed, MonteCarloOddsEvaluator, TimeMachineArena, isolate_arena_memory(), test_eth_feed_fast_fallback_under_test_flag() (+2 more)

### Community 28 - "Parts"
Cohesion: 0.08
Nodes (36): Cards(), initial, S, Controls(), DATA, DIFF, initial, MORE (+28 more)

### Community 29 - "subscriptions/index.tsx"
Cohesion: 0.15
Nodes (14): Checkout(), Dashboard(), OLD, Pay, POSTER, Pulse, pulse(), S (+6 more)

### Community 30 - "cursor-morph/index.tsx"
Cohesion: 0.22
Nodes (8): CursorMorph(), MorphStyle, CursorMorphDemo(), LABELS, ORDER, REST, S, STYLES

### Community 31 - "OmniRoute Headless Installation, Auto-Routing & Troubleshooting Playbook for AI Agents"
Cohesion: 0.07
Nodes (27): 1. Agent Directives & Execution Rules, 2.1 Check Port `20128` Availability, 2.2 Verify Strict Node.js Runtime Version, 2.3 Verify Native Build Tools (Required for `better-sqlite3`), 2.4 Clean Up Corrupted Previous State, 2. Phase 1: Pre-Flight Diagnostics & Cleanup, 3.1 Generate Consolidated `.env` File, 3. Phase 2: Pure Backend & Auto-Routing Configuration (`.env`) (+19 more)

### Community 32 - "kit/index.ts"
Cohesion: 0.10
Nodes (23): BrandMarks(), groups, names, Sheet(), BrandAsset, brandMarks, BrandName, Code() (+15 more)

### Community 33 - "package.json"
Cohesion: 0.10
Nodes (24): description, devDependencies, postcss@^8.5.6, @types/react@^18.3.1, @types/react-dom@^18.3.1, typescript@^5.6.3, vite@^6.4.5, @vitejs/plugin-react@^4.7.0 (+16 more)

### Community 34 - "spotify/index.tsx"
Cohesion: 0.21
Nodes (9): Art(), Eq(), fmt(), Id, initial, ROWS, S, SONGS (+1 more)

### Community 35 - "Row"
Cohesion: 0.10
Nodes (17): FormError(), initial, poster, S, initial, ITEMS, poster, Reorder() (+9 more)

### Community 36 - "OmniRouteClient"
Cohesion: 0.04
Nodes (43): _test_debouncer(), main(), _clean_html_text(), IntelligenceHarvester, InterruptDebouncer, parse_polymarket_events(), parse_reddit_posts(), parse_rss_atom() (+35 more)

### Community 37 - "wikipedia/index.tsx"
Cohesion: 0.13
Nodes (22): CDX, CdxIcon(), CROPS, Fuji(), Header(), Infobox(), initial, Lake() (+14 more)

### Community 38 - "act.ts"
Cohesion: 0.17
Nodes (21): checkSeam(), createAct(), Ref, Stopped, bezier(), capsOf(), drawnScale(), EMPTY (+13 more)

### Community 39 - "contrasts.tsx"
Cohesion: 0.09
Nodes (25): compositionLessons, ContinuityComparison(), continuityLessons, Action(), cases, Comparison(), Contrasts(), ExitScene() (+17 more)

### Community 40 - "composition.tsx"
Cohesion: 0.15
Nodes (22): Anatomy(), Compact(), CompositionComparison(), Contrast(), ControlAlignment(), Decoration(), Density(), EdgeSeparation() (+14 more)

### Community 41 - "test_performance_and_optimizations.py"
Cohesion: 0.13
Nodes (11): ArenaDashboard, _build_html_template(), _load_asset(), test_launchers_and_shortcut_integrity(), test_portfolio_no_duplicate_apply_fill_returns(), test_reset_engine_preserves_cadence(), test_splash_logo_concentric_alignment_and_svg_zap(), test_zero_cjk_in_frontend_assets() (+3 more)

### Community 42 - "HeroDemo.tsx"
Cohesion: 0.13
Nodes (16): annotate(), hidden(), initial, Marker, POSTER, REST, S, script() (+8 more)

### Community 43 - "cursor.tsx"
Cohesion: 0.15
Nodes (21): ARROW_HOTSPOT, Cursor(), GLYPHS, HOTSPOT, ripple(), MacCrosshair(), MacGrab(), MacIbeam() (+13 more)

### Community 44 - "finder-glass/index.tsx"
Cohesion: 0.13
Nodes (19): Column(), DOCUMENTS, FileIcon(), FILMS, FinderGlassDemo(), Geo, GEO, initial (+11 more)

### Community 45 - "Act"
Cohesion: 0.20
Nodes (5): Act, `Act`, `Stage`, The cursor, The stage

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
Cohesion: 0.17
Nodes (17): Rect, Camera(), Count(), CountProps, digitsFromRight(), STRIP, unitOf(), Fly() (+9 more)

### Community 51 - "google-calendar/index.tsx"
Cohesion: 0.09
Nodes (32): Actions(), GmailArchive(), initial, M, Nav(), REST, Row(), ROWS (+24 more)

### Community 52 - "details.tsx"
Cohesion: 0.15
Nodes (15): Bar(), ChartDraw(), Copy(), DetailComparison(), detailLessons, Emoji(), Id, LINE (+7 more)

### Community 53 - "relationships.tsx"
Cohesion: 0.19
Nodes (18): Actions(), change(), Check(), Horizontal(), initial, LessonId, List(), Person() (+10 more)

### Community 54 - "P3 — Packaging, dependencies, hygiene"
Cohesion: 0.15
Nodes (13): 3. Findings, A1. ~250 lines of duplicated strategy logic (also the root cause of C1), A2. `dashboard.py` is a 3,288-line file whose middle is a raw HTML string, A3. Dead module and dead dependency: `theme.py` / `dearpygui`, A5. `main.py --self-test` is opaque and has side effects, H1. Dependencies are unpinned, unpinned-past-major, and mix concerns, H2. Two build configs that will drift, H3. Tests are not hermetic — they mutate user data (+5 more)

### Community 55 - "Collapse"
Cohesion: 0.09
Nodes (16): AiCards(), DAYS, FLIGHTS, initial, poster, S, AiChat(), initial (+8 more)

### Community 56 - "dynamic-island/index.tsx"
Cohesion: 0.12
Nodes (15): Bag(), BASE, Box, boxStyle(), BUD, DynamicIsland(), GEO, GROW (+7 more)

### Community 57 - "finder/index.tsx"
Cohesion: 0.17
Nodes (14): DragImage(), FileIcon(), FinderDemo(), Geo, GEO, Ghost, initial, Kind (+6 more)

### Community 58 - "hero-grid/index.tsx"
Cohesion: 0.18
Nodes (14): at(), composition(), Draft, HeroGrid(), Icons(), INITIAL, KEY_ROWS, Keys() (+6 more)

### Community 59 - "Icon"
Cohesion: 0.10
Nodes (22): Backgrounds(), Digest(), Halftone(), studies, Study(), Chrome(), Content(), Figure() (+14 more)

### Community 60 - "powerpoint/index.tsx"
Cohesion: 0.15
Nodes (15): Box, Design, fit(), G, ICON, IDEAS, initial, LOOK (+7 more)

### Community 61 - "slack/index.tsx"
Cohesion: 0.24
Nodes (13): Composer(), Face(), HoverBar(), I(), initial, Older(), poster, Rail() (+5 more)

### Community 62 - "choreography/index.tsx"
Cohesion: 0.19
Nodes (12): Bank(), Checkout(), Choreography(), ChoreographyComparison(), choreographyLessons, initial, Locale, locales (+4 more)

### Community 63 - "google-docs/index.tsx"
Cohesion: 0.21
Nodes (12): Card, Docs(), Drop(), GoogleDocs(), Header(), initial, P, poster (+4 more)

### Community 64 - "stage.tsx"
Cohesion: 0.16
Nodes (19): Script, clock, Host, CursorKind, CursorStyle, KEYCAPS, Keycaps(), Keys (+11 more)

### Community 65 - "imessage/index.tsx"
Cohesion: 0.09
Nodes (25): IMessage(), initial, S, SUGGEST, suggestions(), ArrowUp(), initial, Messages() (+17 more)

### Community 66 - "parts/index.tsx"
Cohesion: 0.14
Nodes (12): Mark(), CHANGED, initial, Parts(), POSTER, S, Tile(), Popover() (+4 more)

### Community 67 - "layout.mjs"
Cohesion: 0.18
Nodes (10): playwright-core@~1.48.2, launch(), args, auditLayout(), layoutResult(), errors, options, result (+2 more)

### Community 68 - "Unified Memory"
Cohesion: 0.15
Nodes (12): 1. Recall before writing, 2. Save context, 3. Hand off work, 4. Validate the vault, MCP Setup, Recall is evidence, not certainty, Runtime Prerequisite, Trust And Data Boundaries (+4 more)

### Community 69 - "main.tsx"
Cohesion: 0.33
Nodes (9): installVirtualClock(), boot(), errorText(), params, showFailure(), Clock, Controls, createFrameDriver() (+1 more)

### Community 70 - "freeform-drag/index.tsx"
Cohesion: 0.19
Nodes (11): BUSY, Cell, cellRect(), DAYS, END, FreeformDrag(), HOURS, move() (+3 more)

### Community 71 - "compilerOptions"
Cohesion: 0.17
Nodes (11): compilerOptions, jsx, lib, module, moduleResolution, noEmit, skipLibCheck, strict (+3 more)

### Community 72 - "telegram/index.tsx"
Cohesion: 0.17
Nodes (15): Back(), Clip(), initial, Meta(), Mic(), poster, REST, S (+7 more)

### Community 73 - "trader-scanner"
Cohesion: 0.17
Nodes (11): Data and limits, Example: the reel, Rules, Safety, Steps, The daily scan (before the open), The opening-range breakout scan (during the session), The universe (+3 more)

### Community 74 - "lucide-react"
Cohesion: 0.11
Nodes (15): Buttons(), initial, POSTER, S, DarkHero(), initial, Label(), OLD (+7 more)

### Community 75 - "Part 2: Complete Verbatim Audit Report"
Cohesion: 0.17
Nodes (11): 1. Correction on Splash Screen & Packaging, 3. The One Claim That Didn't Hold: The 15 KB Gate, 4. Four Items From the Audit Still Untouched, 5. Two Remaining Risks Worth Naming, 6. Verdict, Do Not Break (Verified Green Baseline), Part 1: Actionable Task List for the Programming Agent, Part 2: Complete Verbatim Audit Report (+3 more)

### Community 76 - "parts/index.ts"
Cohesion: 0.18
Nodes (8): useLook(), AvatarProps, hue(), PEOPLE, Card(), Pin(), PinProps, RowProps

### Community 77 - "._live_loop"
Cohesion: 0.15
Nodes (9): C1. Monte Carlo EV gate is bypassed at startup, C4. Eleven silent `except Exception: pass` blocks, zero logging, C5. Returned list references race with the worker thread, P0 — Correctness, P1 — Performance, P2. The equity-curve apparatus feeds nothing, P4. Per-tick recomputation of history-derived state, P5. Network and disk I/O performed while holding the engine lock (+1 more)

### Community 78 - "linear/index.tsx"
Cohesion: 0.16
Nodes (14): COMMANDS, initial, IssueRow(), LinearDemo(), Priority(), REST, Row, ROWS (+6 more)

### Community 79 - "class-clash.mjs"
Cohesion: 0.27
Nodes (7): args, classDefinitions(), findClashes(), splitSelectors(), unwrapAttributeWhere(), withoutConditions(), find()

### Community 80 - "trader-budget"
Cohesion: 0.18
Nodes (10): Example: the reel, Rules, Safety, Step 1: set the rules once, Step 2: size the trade, Step 3: show the user, trader-budget, Weights mode (kept from v1) (+2 more)

### Community 81 - "upload/index.tsx"
Cohesion: 0.10
Nodes (18): ART, CARD, CARD_NAMES, LIST_TEXT, MobileApp(), Pause(), Phase, Play() (+10 more)

### Community 82 - "Connector"
Cohesion: 0.17
Nodes (12): Collection, CollectionStudy(), Detail, DetailStudy(), UsageDelivery(), Connector(), Annotations, guides and connecting lines, Attach to what is drawn (+4 more)

### Community 83 - "trader-risk"
Cohesion: 0.20
Nodes (9): Entries and exits, Example: the reel, Rules, Safety, Steps, The checks, trader-risk, What it never does (+1 more)

### Community 84 - ".get_ui_state"
Cohesion: 0.24
Nodes (11): P1. ~94% of every UI poll is built and thrown away, _drive(), test_fill_event_has_monotonic_seq_and_action_label(), test_lifecycle_sequence_warmup_before_live_orders(), test_live_engine_eth_and_leverage_configuration(), test_live_engine_evolve_preserves_fill_tape_and_portfolio_positions(), test_live_engine_ui_state_is_json_safe_and_complete(), test_offline_feed_safety_blocks_mock_fills() (+3 more)

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

### Community 89 - "Leaderboard"
Cohesion: 0.21
Nodes (5): C6. Breakeven exits are counted as losses, C7. Sharpe / Sortino are numerically meaningless as displayed, P3. Rankings recomputed on every poll, over ever-growing data, Leaderboard, test_leaderboard_ranked_strictly_by_total_equity()

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

### Community 96 - "story/index.tsx"
Cohesion: 0.20
Nodes (6): BARS, PRICE, S, START, TICKS, Tier

### Community 97 - "TradeBot0 — Optimization Audit & Work Order"
Cohesion: 0.12
Nodes (14): 0. TL;DR, 1. Project context (read this first), 5. Verification checklist, 6. Decisions the human must make before you start, 7. Appendix — measured facts, Commands, Not a git repository, TradeBot0 — Optimization Audit & Work Order (+6 more)

### Community 98 - "Frontend Design"
Cohesion: 0.29
Nodes (6): Design principles, Frontend Design, Ground your designs in the subject matter, More on writing in design, Process: plan, review against the brief, build, critique, Restraint and self-critique

### Community 99 - "Window"
Cohesion: 0.06
Nodes (36): Calendar(), CornerChip(), S, DarkBento(), TRACKS, AW, BW, Loading() (+28 more)

### Community 100 - "Framing"
Cohesion: 0.29
Nodes (6): Checks, Framing, Phones, Small formats and the page, The layouts, The rules

### Community 101 - "Python & Financial Engineering Standards (TradeBot0)"
Cohesion: 0.33
Nodes (5): 1. High-Precision Financial Math, 2. Strong Typing & Documentation, 3. Concurrency & Thread Safety, 4. Defensive Exception Handling & Logging, Python & Financial Engineering Standards (TradeBot0)

### Community 102 - "Motion"
Cohesion: 0.17
Nodes (9): Changing text and values, Index, Loops, Motion, Pace and easing, Phones in motion, Recipes, Scrolling and the camera (+1 more)

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

### Community 110 - "figma/index.tsx"
Cohesion: 0.25
Nodes (9): FigmaDemo(), hex(), initial, LayerIcon(), LAYERS, MAYA, mayaAt(), S (+1 more)

### Community 111 - ".evaluate_bracket"
Cohesion: 0.24
Nodes (6): H6. Doc drift and small inconsistencies, MonteCarloBracketOdds, _get_assets_dir(), test_startup_ev_gate_enforcement(), test_monte_carlo_ev_gate_odds_evaluation(), 2. What Is Verified Green

### Community 112 - "scripts"
Cohesion: 0.40
Nodes (5): scripts, build, check:css, dev, typecheck

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
Cohesion: 0.20
Nodes (9): Examples, Gold, How hard to press, Product studies, Specimen and reference sheets, Stageshow, The one idea, The references (+1 more)

### Community 123 - "Point"
Cohesion: 0.22
Nodes (9): ActEnv, Point, Target, along(), bend(), ConnectorProps, corners(), elbow() (+1 more)

### Community 124 - "cursors/index.tsx"
Cohesion: 0.25
Nodes (5): Cursors(), S, Scene(), START, TRACK

### Community 125 - "table-edit/index.tsx"
Cohesion: 0.25
Nodes (6): initial, money(), ROWS, S, TableEdit(), TONES

### Community 126 - "Teaching pairs"
Cohesion: 0.22
Nodes (8): Details, Making a comparison, Motion between neighbors, Style (stills), Teaching pairs, UI details (stills), What a pair can't show, Whole scenes (stills)

### Community 127 - "Verify"
Cohesion: 0.22
Nodes (8): Framing (first, because nothing else matters if this is wrong), Gate, Hand over, Hierarchy and density, Motion (animated scenes), Polish (last), Verify, What you see, what you do

### Community 128 - "LiveQuote"
Cohesion: 0.25
Nodes (4): C2. Offline fallback trades against a hardcoded price, LiveQuote, _quote(), test_resilient_quote_cache_fallback()

### Community 129 - "Craft"
Cohesion: 0.25
Nodes (7): A page of demos, Craft, Density, Icons and logos, Recipes, Restraint, Type

### Community 130 - "Rehearse"
Cohesion: 0.25
Nodes (7): Film, Lines that are never intentional, Other film lines, Prove the still before choreography, Rehearse, The host's own controls, The last pass

### Community 131 - "Detailed Execution Phases & Tasks"
Cohesion: 0.25
Nodes (7): Approved Architectural Refinements (R1-R5), Architecture Overview, Detailed Execution Phases & Tasks, Macro Commander & OmniRoute Intelligence Ingestion Workflow Plan (Updated v2 - Approved, 5 Refinements Integrated), Phase 2: Real OmniRoute Gateway Connection Layer, Phase 3: Multi-Domain Intelligence Ingestion Pipeline, Phase 5: UI Macro Ticker & End-to-End Validation

### Community 132 - "The kit, piece by piece"
Cohesion: 0.29
Nodes (6): Explicit replay, Frames, Layout and CSS scope, Motion parts, The kit, piece by piece, `Window`

## Knowledge Gaps
- **10 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Parts` connect `Parts` to `kit-extras/index.tsx`, `Stage`, `The kit, piece by piece`, `film-checks.mjs`, `size.py`, `States`, `Phone`, `.rect`, `Chart`, `kit/index.ts`, `HeroDemo.tsx`, `cursor.tsx`, `Act`, `calendar/index.tsx`, `react`, `google-calendar/index.tsx`, `Collapse`, `parts/index.tsx`, `upload/index.tsx`, `Connector`, `Window`, `Motion`?**
  _High betweenness centrality (0.280) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `Stage()` (e.g. with `The rules` and `Recipes`) actually correct?**
  _`Stage()` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Should `kit-extras/index.tsx` be split into smaller, more focused modules?**
  _Cohesion score 0.07816091954022988 - nodes in this community are weakly interconnected._
- **Why does `size()` connect `size.py` to `Parts`?**
  _High betweenness centrality (0.248) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `Window()` (e.g. with `Recipes` and ``Window``) actually correct?**
  _`Window()` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Should `Stage` be split into smaller, more focused modules?**
  _Cohesion score 0.07676767676767676 - nodes in this community are weakly interconnected._
- **Why does `Close()` connect `bento/index.tsx` to `react`, `Detailed Execution Phases & Tasks`?**
  _High betweenness centrality (0.157) - this node is a cross-community bridge._