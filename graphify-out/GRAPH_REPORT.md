# Graph Report - TradeBot0  (2026-11-13)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 3308 nodes · 8718 edges · 162 communities (152 shown, 10 thin omitted)
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 833 edges (avg confidence: 0.9)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `5b6b7d50`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- test_intel_veto.py
- scan.py
- live_engine.py
- film-checks.mjs
- trader-timemachine/timemachine.py
- entry.py
- kit/index.ts
- GatewaySupervisor
- size.py
- CompetitorGenome
- exit.py
- Chart
- test_evolution.py
- parts/index.ts
- check.py
- Collapse
- test_performance_and_optimizations.py
- BrokerSim
- google-calendar/index.tsx
- Act
- os
- film.mjs
- TimeMachineArena
- _ArenaBridgeApi
- ruled-bento/index.tsx
- .bootstrap_intraday_session
- app.js
- linear/index.tsx
- Stage
- contrasts.tsx
- lucide-react
- OrderSide
- package.json
- FillEvent
- LiveArenaEngine
- test_live_engine.py
- cursor.tsx
- TradeBot0 — Full System Optimization & Engineering Implementation Guide
- Phone
- messages/index.tsx
- wikipedia/index.tsx
- composition.tsx
- bento/index.tsx
- annotations/index.tsx
- Any
- .run
- Row
- finder-glass/index.tsx
- HeroDemo.tsx
- react
- jumps.mjs
- scenes.tsx
- calendar/index.tsx
- controls/index.tsx
- cursor-morph.tsx
- kit-extras/index.tsx
- ArenaStorage
- Portfolio
- staggered-bento/index.tsx
- Bar
- States
- dynamic-island/index.tsx
- details.tsx
- relationships.tsx
- InterruptDebouncer
- renderAll
- hero-grid/index.tsx
- telegram/index.tsx
- MultiTimeframeEngine
- Avatar
- controls/index.ts
- finder/index.tsx
- phone-touch/index.tsx
- powerpoint/index.tsx
- slack/index.tsx
- build_engine_view_model
- choreography/index.tsx
- google-docs/index.tsx
- imessage/index.tsx
- upload/index.tsx
- ViewModelPublisher
- test_debug_report_fixes.py
- Icon
- gmail/index.tsx
- share/index.tsx
- layout.mjs
- Unified Memory
- test_phase2_omniroute_client.py
- ._try_enter_bracket
- pollBackend
- freeform-drag/index.tsx
- compilerOptions
- trader-scanner
- drawPriceChart
- .rect
- main.tsx
- viewer.tsx
- trader-budget
- AggressiveCompetitor
- cards/index.tsx
- presence/index.tsx
- Motion
- Parts
- class-clash.mjs
- shoot
- Stageshow
- trader-risk
- fix_item2_patch.py
- cursors/index.tsx
- loading/index.tsx
- Count
- preview.tsx
- Teaching pairs
- Verify
- edges.tsx
- style.tsx
- trader-entry
- datetime
- trader-exit
- trader-timemachine
- startSplashSequence
- composed.tsx
- cursor-resize/index.tsx
- reorder/index.tsx
- Craft
- Looks
- dev.mjs
- renderPriceCanvas
- Core Pillars
- Frontend Design
- backgrounds/index.tsx
- payout-flow/index.tsx
- Connector
- Framing
- Rehearse
- Core Pillars
- Quick Start Guide
- fix_item3_patch.py
- fix_item4b_patch.py
- fix_item5_patch.py
- Python & Financial Engineering Standards (TradeBot0)
- Core Pillars
- NOTICE.md
- Stageshow
- Backgrounds and the whole picture
- Bento
- Choreography
- fix_item3_patch2.py
- fix_item3_patch3.py
- AIMRAN Library Skill (814 Animated UI Components)
- Roll
- scripts
- SimClock
- Test-Driven Development (TDD) Workflow
- Trading Safety & Multi-Portfolio Guardrails
- argparse
- scheduleProcessToastQueue
- Review
- cursor-morph/README.md
- products.md

## God Nodes (most connected - your core abstractions)
1. `Stage()` - 208 edges
2. `LiveArenaEngine` - 153 edges
3. `Bar()` - 122 edges
4. `Window()` - 111 edges
5. `OrderSide` - 96 edges
6. `Act` - 89 edges
7. `react` - 85 edges
8. `BrokerSim` - 84 edges
9. `Text()` - 82 edges
10. `filmChecksSource()` - 79 edges

## Surprising Connections (you probably didn't know these)
- `6.1 Problem Statement` --references--> `GeneticEvolver`  [INFERRED]
  OptimizationFullGuide.md → src/arena/evolution.py
- `3. Concurrency & Thread Safety` --references--> `BrokerSim`  [INFERRED]
  .agent/rules/coding-standards.md → src/arena/broker_sim.py
- `1. Executive Summary & Architectural Vision` --references--> `LiveArenaEngine`  [INFERRED]
  OptimizationFullGuide.md → src/data/live_engine.py
- `5.3 Implementation in `LiveArenaEngine`` --references--> `LiveArenaEngine`  [INFERRED]
  OptimizationFullGuide.md → src/data/live_engine.py
- `Integration Guidelines for Desktop / PyWebView (`TradeBot0_Arena.exe`)` --references--> `test_zero_cjk_in_frontend_assets()`  [INFERRED]
  .agent/skills/aimran-library/SKILL.md → tests/test_performance_and_optimizations.py

## Import Cycles
- 2-file cycle: `.agent/skills/stageshow/teaching/contrasts.tsx -> .agent/skills/stageshow/teaching/relationships.tsx -> .agent/skills/stageshow/teaching/contrasts.tsx`
- 2-file cycle: `.agent/skills/stageshow/teaching/composition.tsx -> .agent/skills/stageshow/teaching/contrasts.tsx -> .agent/skills/stageshow/teaching/composition.tsx`

## Communities (162 total, 10 thin omitted)

### Community 0 - "test_intel_veto.py"
Cohesion: 0.04
Nodes (47): _clean_html_text(), _contains_word(), IntelligenceHarvester, parse_polymarket_events(), parse_reddit_posts(), parse_rss_atom(), RawEvent, StructuredEvent (+39 more)

### Community 1 - "scan.py"
Cohesion: 0.06
Nodes (49): _absorb(), build_universe(), chart_path(), classify(), clock_label(), cmd_daily(), cmd_orb(), confirm() (+41 more)

### Community 2 - "live_engine.py"
Cohesion: 0.05
Nodes (22): ArenaDashboard, _build_html_template(), _get_native_hwnd(), _load_asset(), __getattr__(), _build_engine_view_model_impl(), ConfigManager, test_setup_status_includes_gateway_auto_spawn() (+14 more)

### Community 3 - "film-checks.mjs"
Cohesion: 0.12
Nodes (78): alphaOf(), animating(), cameraMoving(), checkStage(), collectSurfaces(), detectBoxEdges(), detectBylineGap(), detectClipped() (+70 more)

### Community 4 - "trader-timemachine/timemachine.py"
Cohesion: 0.05
Nodes (43): build_pool(), cents_away(), chart_result(), chart_url(), clock12(), clock24(), cmd_chart(), cmd_run() (+35 more)

### Community 5 - "entry.py"
Cohesion: 0.07
Nodes (47): ampm(), bar_line(), chart_path(), chart_range(), cmd_check(), cmd_watch(), emit(), on_trigger() (+39 more)

### Community 6 - "kit/index.ts"
Cohesion: 0.07
Nodes (55): ActEnv, checkSeam(), createAct(), Ref, Script, Stopped, clock, Host (+47 more)

### Community 7 - "GatewaySupervisor"
Cohesion: 0.04
Nodes (18): _default_daemon_log_path(), GatewaySupervisor, _FakeEvent, _FakeWebview, _FakeWindow, test_daemon_log_default_path_is_project_logs(), test_daemon_log_rotates_over_5mb(), test_existing_daemon_check_uses_2s_probe() (+10 more)

### Community 8 - "size.py"
Cohesion: 0.07
Nodes (36): Brand marks, allocate(), bracket_order(), eastern_offset(), eastern_to_utc(), _f(), fresh_price(), load_config() (+28 more)

### Community 9 - "CompetitorGenome"
Cohesion: 0.07
Nodes (11): ATRDynamicCompetitor, BaseCompetitor, CompetitorGenome, ConservativeCompetitor, ORBCompetitor, SessionMeanPullbackCompetitor, TrailingGuardCompetitor, test_all_four_competitors_initialization_and_first_buy() (+3 more)

### Community 10 - "exit.py"
Cohesion: 0.09
Nodes (37): ampm(), atr_of(), build_plan(), cents(), cmd_plan(), cmd_show(), compute(), D() (+29 more)

### Community 11 - "Chart"
Cohesion: 0.05
Nodes (35): ChartScrub(), DAYS, money(), NAMES, S, script(), TOTAL, W (+27 more)

### Community 12 - "test_evolution.py"
Cohesion: 0.09
Nodes (17): 9. Rollout Schedule & Execution Checklist, GeneticEvolver, CompetitorStats, Leaderboard, _ranked_four(), test_composite_fitness_matches_leaderboard_fitness(), test_evolution_save_history_decoupled_from_lock(), test_evolution_seed_recorded_in_history() (+9 more)

### Community 13 - "parts/index.ts"
Cohesion: 0.07
Nodes (34): BrandMarks(), groups, names, Sheet(), FigmaDemo(), hex(), initial, LayerIcon() (+26 more)

### Community 14 - "check.py"
Cohesion: 0.08
Nodes (29): account(), business_days(), _cent(), check(), day_trades(), eastern_offset(), eastern_to_utc(), _f() (+21 more)

### Community 15 - "Collapse"
Cohesion: 0.06
Nodes (36): DarkHero(), initial, Label(), Mark(), OLD, Row(), S, Side() (+28 more)

### Community 16 - "test_performance_and_optimizations.py"
Cohesion: 0.06
Nodes (14): main(), _read(), _write(), LiveQuote, QuoteManager, StreamingCryptoFeed, _get_assets_dir(), test_provider_cooldown_respected_when_all_cooling() (+6 more)

### Community 17 - "BrokerSim"
Cohesion: 0.12
Nodes (20): 4.1 Problem Statement, 4.2 Mathematical Formulation, 4.3 Implementation in `BrokerSim`, 4. Phase 3 (P2): Realistic Orderbook Depth & Volatility-Adjusted Slippage, BrokerSim, OrderTicket, test_broker_sim_bracket_stop_loss_trigger(), test_broker_sim_leverage_liquidation_protection() (+12 more)

### Community 18 - "google-calendar/index.tsx"
Cohesion: 0.08
Nodes (32): Glass(), clock(), clockFull(), EVENTS, FOUR, GEO, GoogleCalendar(), Grid() (+24 more)

### Community 19 - "Act"
Cohesion: 0.06
Nodes (20): ACCENTS, initial, poster, S, initial, money(), ROWS, S (+12 more)

### Community 20 - "os"
Cohesion: 0.09
Nodes (16): fail(), grep_repo(), main(), read_text(), rep(), repo_files(), main(), _read() (+8 more)

### Community 21 - "film.mjs"
Cohesion: 0.05
Nodes (35): args, at, cameraSkipped, clipped, clipSamples, colsOpt, count, delay (+27 more)

### Community 22 - "TimeMachineArena"
Cohesion: 0.11
Nodes (10): check_and_ensure_environment(), main(), CandleBar, ETHFeed, MonteCarloOddsEvaluator, TimeMachineArena, test_eth_feed_fast_fallback_under_test_flag(), test_orb_window_excludes_current_bar() (+2 more)

### Community 24 - "ruled-bento/index.tsx"
Cohesion: 0.10
Nodes (29): Chrome(), Content(), Figure(), files, Specimen, specimens, Tool(), after (+21 more)

### Community 25 - ".bootstrap_intraday_session"
Cohesion: 0.10
Nodes (6): test_close_ticket_bypasses_veto_and_gates_under_hold_cash(), test_anti_churn_cooldown_prevents_same_timestamp_reentry(), test_macro_veto_intent_preserved_in_live_evaluation(), _fixture_bars(), test_candle_cadence_dispatcher_timing_and_dispatch(), test_micro_bar_aggregation_preserves_wick_extremes_r1()

### Community 26 - "app.js"
Cohesion: 0.07
Nodes (24): animCandles, chartBeacons, checkOnboardingBoot(), closeResetModal(), closeShutdownModal(), confirmResetArena(), currentSplashSteps, handleModalOverlayClick() (+16 more)

### Community 27 - "linear/index.tsx"
Cohesion: 0.08
Nodes (23): DAYS, FLIGHTS, initial, poster, S, initial, poster, S (+15 more)

### Community 28 - "Stage"
Cohesion: 0.11
Nodes (22): AiCards(), Buttons(), Card(), PaymentsStatic(), REVENUE, ROWS, FadeCrop(), FILL (+14 more)

### Community 29 - "contrasts.tsx"
Cohesion: 0.09
Nodes (24): compositionLessons, ContinuityComparison(), Action(), cases, Comparison(), Contrasts(), ExitScene(), FILES (+16 more)

### Community 30 - "lucide-react"
Cohesion: 0.08
Nodes (20): initial, POSTER, S, Art(), Eq(), fmt(), Id, initial (+12 more)

### Community 31 - "OrderSide"
Cohesion: 0.34
Nodes (8): ExecutionReason, OrderSide, OrderStatus, OrderType, PositionSide, RiskGuard, test_bidirectional_short_win_rate_and_closing_fill(), test_risk_guard_cap_ignores_leverage()

### Community 32 - "package.json"
Cohesion: 0.10
Nodes (26): description, devDependencies, playwright-core@~1.48.2, postcss@^8.5.6, @types/react@^18.3.1, @types/react-dom@^18.3.1, typescript@^5.6.3, vite@^6.4.5 (+18 more)

### Community 33 - "FillEvent"
Cohesion: 0.11
Nodes (10): FillEvent, isolate_arena_memory(), _keyframes_block(), _make_fill(), test_splash_overlay_is_lightened_not_removed(), test_stale_engine_harvest_fills_refused(), test_portfolio_breakeven_trade_does_not_count_as_loss(), test_portfolio_insufficient_cash() (+2 more)

### Community 34 - "LiveArenaEngine"
Cohesion: 0.11
Nodes (7): 2.1 Problem Statement, LiveArenaEngine, test_pause_feed_updates_ui_snapshot_immediately(), test_stale_engine_evolve_now_refused(), test_stale_engine_state_publish_skipped(), test_pause_time_freezing_and_arena_transitions(), test_live_engine_refresh_intel_digest()

### Community 35 - "test_live_engine.py"
Cohesion: 0.14
Nodes (17): _drive(), _fixture_bars(), _quote(), test_auto_evolve_fires_on_closed_trades(), _round_trips(), test_auto_evolve_timer_and_toggle(), test_fill_event_has_monotonic_seq_and_action_label(), test_lifecycle_sequence_warmup_before_live_orders() (+9 more)

### Community 36 - "cursor.tsx"
Cohesion: 0.14
Nodes (22): ARROW_HOTSPOT, Cursor(), GLYPHS, HOTSPOT, ripple(), MacCrosshair(), MacGrab(), MacIbeam() (+14 more)

### Community 37 - "TradeBot0 — Full System Optimization & Engineering Implementation Guide"
Cohesion: 0.08
Nodes (25): 1. Executive Summary & Architectural Vision, 2.2 Architectural Solution, 2.3 Detailed Implementation Steps, 2. Phase 1 (P1): Low-Latency WebSocket Streaming & Resilient Circuit Breaking, 3.1 Problem Statement, 3.2 Architectural Solution, 3.3 Database Schema & Implementation, 3. Phase 2 (P1): Native SQLite (WAL Mode) Embedded Persistence (+17 more)

### Community 38 - "Phone"
Cohesion: 0.13
Nodes (22): mail, Checkout(), Phones(), BANDS, Battery(), CORNER, FRAMES, IPHONE (+14 more)

### Community 39 - "messages/index.tsx"
Cohesion: 0.14
Nodes (17): IMessage(), ArrowUp(), initial, Messages(), poster, S, MESSAGES, OppositeCorners() (+9 more)

### Community 40 - "wikipedia/index.tsx"
Cohesion: 0.13
Nodes (22): CDX, CdxIcon(), CROPS, Fuji(), Header(), Infobox(), initial, Lake() (+14 more)

### Community 41 - "composition.tsx"
Cohesion: 0.15
Nodes (22): Anatomy(), Compact(), CompositionComparison(), Contrast(), ControlAlignment(), Decoration(), Density(), EdgeSeparation() (+14 more)

### Community 42 - "bento/index.tsx"
Cohesion: 0.17
Nodes (20): calendar, figma, notion, slack, testFlight, after, Approvals(), Beat (+12 more)

### Community 43 - "annotations/index.tsx"
Cohesion: 0.11
Nodes (16): Annotations(), BranchState, BranchStudy(), ChartState, ChartStudy(), FlowState, FlowStudy(), FollowState (+8 more)

### Community 44 - "Any"
Cohesion: 0.11
Nodes (4): test_session_save_and_restore_with_locked_margin(), test_trade_and_equity_history_persistence(), test_stale_engine_save_session_state_refused(), test_session_state_save_and_restore_and_shutdown_bridge()

### Community 45 - ".run"
Cohesion: 0.11
Nodes (8): _activate_foreground_startup(), _on_window_closed(), _on_window_closing(), _on_window_shown(), _delayed_activation(), test_gateway_auto_spawn_default_is_true(), test_config_manager_atomic_recovery_from_corruption(), test_config_manager_input_sanitization()

### Community 46 - "Row"
Cohesion: 0.11
Nodes (14): CloseUp(), initial, poster, S, NAV, ROWS, StaticCard(), Busy() (+6 more)

### Community 47 - "finder-glass/index.tsx"
Cohesion: 0.13
Nodes (19): Column(), DOCUMENTS, FileIcon(), FILMS, FinderGlassDemo(), Geo, GEO, initial (+11 more)

### Community 48 - "HeroDemo.tsx"
Cohesion: 0.13
Nodes (18): annotate(), HeroDemo(), hidden(), initial, Marker, POSTER, REST, S (+10 more)

### Community 49 - "react"
Cohesion: 0.24
Nodes (11): Rect, Fly(), FlyProps, Follow(), FollowProps, PopoverOrigin, Swap(), Tooltip() (+3 more)

### Community 50 - "jumps.mjs"
Cohesion: 0.16
Nodes (17): Film, clipFindings(), finishReport(), has(), args, analyse(), contentChanges(), record() (+9 more)

### Community 51 - "scenes.tsx"
Cohesion: 0.22
Nodes (21): Action(), ColoredLayers(), CropFiller(), DashboardPhone(), FileList(), FOLDER, LibraryApp(), Mark() (+13 more)

### Community 52 - "calendar/index.tsx"
Cohesion: 0.13
Nodes (19): Avail, BUSY, carry(), Cell, cellRect(), DAYS, END, GRIP (+11 more)

### Community 53 - "controls/index.tsx"
Cohesion: 0.12
Nodes (15): Controls(), DATA, DIFF, initial, MORE, POSTER, ROWS, S (+7 more)

### Community 54 - "cursor-morph.tsx"
Cohesion: 0.12
Nodes (17): CIRCLE, CursorMorph(), HEAD, Look, MorphStyle, path(), POINTER, Pt (+9 more)

### Community 55 - "kit-extras/index.tsx"
Cohesion: 0.11
Nodes (14): GLYPHS, initial, KitExtras(), LINES, POSTER, REST, S, STRENGTH (+6 more)

### Community 57 - "Portfolio"
Cohesion: 0.19
Nodes (5): Architectural Highlights, Portfolio, test_portfolio_reset_clears_all_metrics(), test_portfolio_buy_and_sell_accounting(), test_portfolio_initialization()

### Community 58 - "staggered-bento/index.tsx"
Cohesion: 0.19
Nodes (18): after, AZ, Azulejo(), Beat, beat(), before, Book(), Coast() (+10 more)

### Community 59 - "Bar"
Cohesion: 0.19
Nodes (17): AiChat(), Ledger(), Receipt(), Sidebar(), FOCUS, ManyOfOne(), W, Sidebar() (+9 more)

### Community 60 - "States"
Cohesion: 0.14
Nodes (13): StreamStudy(), FormError(), initial, poster, S, CHANGED, initial, Parts() (+5 more)

### Community 61 - "dynamic-island/index.tsx"
Cohesion: 0.12
Nodes (15): Bag(), BASE, Box, boxStyle(), BUD, DynamicIsland(), GEO, GROW (+7 more)

### Community 62 - "details.tsx"
Cohesion: 0.15
Nodes (15): Bar(), ChartDraw(), Copy(), DetailComparison(), detailLessons, Emoji(), Id, LINE (+7 more)

### Community 63 - "relationships.tsx"
Cohesion: 0.19
Nodes (18): Actions(), change(), Check(), Horizontal(), initial, LessonId, List(), Person() (+10 more)

### Community 64 - "InterruptDebouncer"
Cohesion: 0.15
Nodes (5): DeduplicationBuffer, InterruptDebouncer, test_deduplication_buffer(), test_stage2_interrupt_debouncing_r4(), _run()

### Community 65 - "renderAll"
Cohesion: 0.19
Nodes (18): changeEvolveInterval(), escapeHtml(), fmtPct(), fmtSignedUsd(), fmtTimeSec(), fmtUsd(), renderAll(), renderFills() (+10 more)

### Community 66 - "hero-grid/index.tsx"
Cohesion: 0.18
Nodes (14): at(), composition(), Draft, Drafting(), HeroGrid(), Icons(), INITIAL, KEY_ROWS (+6 more)

### Community 67 - "telegram/index.tsx"
Cohesion: 0.18
Nodes (14): Back(), Clip(), initial, Meta(), Mic(), poster, REST, S (+6 more)

### Community 69 - "Avatar"
Cohesion: 0.17
Nodes (11): Calendar(), CornerChip(), S, DarkBento(), TRACKS, FreeformDrag(), SwipeDemo(), Avatar() (+3 more)

### Community 70 - "controls/index.ts"
Cohesion: 0.17
Nodes (9): CursorMorphDemo(), ButtonProps, Draft(), DraftProps, FieldProps, Segmented(), Tabs(), Toggle() (+1 more)

### Community 71 - "finder/index.tsx"
Cohesion: 0.17
Nodes (13): DragImage(), FileIcon(), FinderDemo(), Geo, GEO, Ghost, initial, Kind (+5 more)

### Community 72 - "phone-touch/index.tsx"
Cohesion: 0.15
Nodes (13): ART, CARD, CARD_NAMES, LIST_TEXT, MobileApp(), Pause(), Phase, Play() (+5 more)

### Community 73 - "powerpoint/index.tsx"
Cohesion: 0.14
Nodes (13): Box, Design, fit(), G, ICON, IDEAS, initial, LOOK (+5 more)

### Community 74 - "slack/index.tsx"
Cohesion: 0.24
Nodes (13): Composer(), Face(), HoverBar(), I(), initial, Older(), poster, Rail() (+5 more)

### Community 75 - "build_engine_view_model"
Cohesion: 0.17
Nodes (8): build_engine_view_model(), test_cooperative_stop_event(), test_slow_bootstrap_stop_safety(), _rankings(), test_view_model_does_not_fabricate_take_profit(), test_view_model_reports_unknown_mc_and_quota(), test_view_model_skips_stale_ranking_entry(), test_view_model_survives_missing_or_broken_engine()

### Community 76 - "choreography/index.tsx"
Cohesion: 0.19
Nodes (12): Bank(), Checkout(), Choreography(), ChoreographyComparison(), choreographyLessons, initial, Locale, locales (+4 more)

### Community 77 - "google-docs/index.tsx"
Cohesion: 0.21
Nodes (12): Card, Docs(), Drop(), GoogleDocs(), Header(), initial, P, poster (+4 more)

### Community 78 - "imessage/index.tsx"
Cohesion: 0.15
Nodes (11): initial, S, SUGGEST, suggestions(), Glyph(), Keyboard(), KeyboardProps, ROWS (+3 more)

### Community 79 - "upload/index.tsx"
Cohesion: 0.18
Nodes (12): DragImage(), Geo, GEO, Ghost, initial, Kind, PdfIcon(), Row() (+4 more)

### Community 80 - "ViewModelPublisher"
Cohesion: 0.16
Nodes (3): _empty_view_model(), ViewModelPublisher, test_phase6_modular_view_model_and_state_delta_streaming()

### Community 81 - "test_debug_report_fixes.py"
Cohesion: 0.17
Nodes (6): _fixture_bars(), test_full_restore_bootstrap_start_integration(), test_get_ui_state_mutation_isolation(), test_offline_start_does_not_execute_stale_candles(), test_start_live_trading_does_not_wipe_restored_positions(), test_start_live_trading_readiness_handshake()

### Community 82 - "Icon"
Cohesion: 0.26
Nodes (9): looks, studies, DimensionalLook(), CanvasLook(), ConsoleLook(), FinanceLook(), MessagesLook(), ResearchLook() (+1 more)

### Community 83 - "gmail/index.tsx"
Cohesion: 0.24
Nodes (10): Actions(), GmailArchive(), initial, M, Nav(), REST, Row(), ROWS (+2 more)

### Community 84 - "share/index.tsx"
Cohesion: 0.18
Nodes (10): EDIT, Geo, GEO, initial, Person(), poster, roleMenu(), ROLES (+2 more)

### Community 85 - "layout.mjs"
Cohesion: 0.19
Nodes (9): launch(), checkClipsForStage(), args, auditLayout(), layoutResult(), errors, options, result (+1 more)

### Community 86 - "Unified Memory"
Cohesion: 0.15
Nodes (12): 1. Recall before writing, 2. Save context, 3. Hand off work, 4. Validate the vault, MCP Setup, Recall is evidence, not certainty, Runtime Prerequisite, Trust And Data Boundaries (+4 more)

### Community 87 - "test_phase2_omniroute_client.py"
Cohesion: 0.23
Nodes (8): compute_backoff(), extract_json(), test_compute_backoff(), test_extract_json_invalid_or_non_dict(), test_extract_json_valid_dict(), test_extract_json_with_closed_think_block(), test_extract_json_with_code_fences(), test_extract_json_with_unclosed_think_block()

### Community 88 - "._try_enter_bracket"
Cohesion: 0.21
Nodes (4): MonteCarloBracketOdds, test_startup_ev_gate_enforcement(), test_live_engine_enforces_macro_commander_veto(), test_monte_carlo_ev_gate_odds_evaluation()

### Community 89 - "pollBackend"
Cohesion: 0.22
Nodes (13): addChartBeacon(), copyOmniPassword(), createPositionClosedToastElement(), createPositionToastElement(), enqueueToast(), hexToRgba(), pollBackend(), previewPositionAnimation() (+5 more)

### Community 90 - "freeform-drag/index.tsx"
Cohesion: 0.20
Nodes (10): BUSY, Cell, cellRect(), DAYS, END, HOURS, move(), S (+2 more)

### Community 91 - "compilerOptions"
Cohesion: 0.17
Nodes (11): compilerOptions, jsx, lib, module, moduleResolution, noEmit, skipLibCheck, strict (+3 more)

### Community 92 - "trader-scanner"
Cohesion: 0.17
Nodes (11): Data and limits, Example: the reel, Rules, Safety, Steps, The daily scan (before the open), The opening-range breakout scan (during the session), The universe (+3 more)

### Community 93 - "drawPriceChart"
Cohesion: 0.24
Nodes (12): drawPriceChart(), locateMouseAndRefreshChart(), renderIntelHub(), setChartMode(), setLgWallpaper(), setRightTab(), setScaleMode(), setupChartInteraction() (+4 more)

### Community 94 - ".rect"
Cohesion: 0.20
Nodes (9): Annotations, guides and connecting lines, Attach to what is drawn, Check attachment in motion, Choose a line for a relationship, Frame the whole relationship, Show the cause, then hold the explanation, From a codebase, What to watch (+1 more)

### Community 95 - "main.tsx"
Cohesion: 0.33
Nodes (9): installVirtualClock(), boot(), errorText(), params, showFailure(), Clock, Controls, createFrameDriver() (+1 more)

### Community 96 - "viewer.tsx"
Cohesion: 0.24
Nodes (9): curated, examples, extra, groups, listed, products, specimens, mount() (+1 more)

### Community 97 - "trader-budget"
Cohesion: 0.18
Nodes (10): Example: the reel, Rules, Safety, Step 1: set the rules once, Step 2: size the trade, Step 3: show the user, trader-budget, Weights mode (kept from v1) (+2 more)

### Community 98 - "AggressiveCompetitor"
Cohesion: 0.25
Nodes (5): AggressiveCompetitor, test_evaluate_signal_short_entries_mirror_long_brackets(), _broker(), test_aggressive_stopout_loss_capped_at_risk_pct(), test_risk_budget_ignores_leverage()

### Community 99 - "cards/index.tsx"
Cohesion: 0.24
Nodes (5): Cards(), initial, S, Divider(), Kbd()

### Community 100 - "presence/index.tsx"
Cohesion: 0.24
Nodes (7): initial, Peer(), PEOPLE, Presence(), S, Spot, spot()

### Community 101 - "Motion"
Cohesion: 0.20
Nodes (8): cellOf(), Drags and selection, Index, Motion, Pace and easing, Recipes, Scrolling and the camera, Story

### Community 102 - "Parts"
Cohesion: 0.31
Nodes (8): css(), Camera(), Expand(), Stream(), Chip(), Parts, Phones in motion, The kit

### Community 103 - "class-clash.mjs"
Cohesion: 0.31
Nodes (7): args, classDefinitions(), findClashes(), splitSelectors(), unwrapAttributeWhere(), withoutConditions(), find()

### Community 104 - "shoot"
Cohesion: 0.22
Nodes (10): checkClips(), clipFor(), fail(), overlaid(), secs(), series(), shoot(), stageRoot() (+2 more)

### Community 105 - "Stageshow"
Cohesion: 0.20
Nodes (9): Examples, Gold, How hard to press, Product studies, Specimen and reference sheets, Stageshow, The one idea, The references (+1 more)

### Community 106 - "trader-risk"
Cohesion: 0.20
Nodes (9): Entries and exits, Example: the reel, Rules, Safety, Steps, The checks, trader-risk, What it never does (+1 more)

### Community 107 - "fix_item2_patch.py"
Cohesion: 0.24
Nodes (3): main(), _norm(), _read()

### Community 108 - "cursors/index.tsx"
Cohesion: 0.25
Nodes (5): Cursors(), S, Scene(), START, TRACK

### Community 109 - "loading/index.tsx"
Cohesion: 0.22
Nodes (6): AW, BW, Loading(), ROWS, S, W

### Community 110 - "Count"
Cohesion: 0.28
Nodes (8): PayoutFlow(), Voice(), Count(), CountProps, digitsFromRight(), STRIP, unitOf(), Changing text and values

### Community 111 - "preview.tsx"
Cohesion: 0.25
Nodes (5): react-dom@^18.3.1, Boundary, modules, mount(), react-dom

### Community 112 - "Teaching pairs"
Cohesion: 0.22
Nodes (8): Details, Making a comparison, Motion between neighbors, Style (stills), Teaching pairs, UI details (stills), What a pair can't show, Whole scenes (stills)

### Community 113 - "Verify"
Cohesion: 0.22
Nodes (8): Framing (first, because nothing else matters if this is wrong), Gate, Hand over, Hierarchy and density, Motion (animated scenes), Polish (last), Verify, What you see, what you do

### Community 114 - "edges.tsx"
Cohesion: 0.28
Nodes (6): EdgeComparison(), edgeLessons, initial, LabelSlot(), State, Viewport()

### Community 115 - "style.tsx"
Cohesion: 0.28
Nodes (8): Card(), Deploy, DEPLOYS, ICON, Id, MadeUp(), StyleComparison(), styleLessons

### Community 116 - "trader-entry"
Cohesion: 0.22
Nodes (8): Example: the reel, Rules, Safety, Steps, The rule, trader-entry, What it never does, What it reads and writes

### Community 117 - "datetime"
Cohesion: 0.33
Nodes (6): eastern_offset(), eastern_to_utc(), _nth_sunday(), eastern_offset(), eastern_to_utc(), _nth_sunday()

### Community 118 - "trader-exit"
Cohesion: 0.22
Nodes (8): Example: the reel, Rules, Safety, Steps, Stops and targets, trader-exit, What it never does, What it reads and writes

### Community 119 - "trader-timemachine"
Cohesion: 0.22
Nodes (8): Example: the reel, How it works, Rules, Safety, Steps, trader-timemachine, What it never does, What it reads and writes

### Community 120 - "startSplashSequence"
Cohesion: 0.33
Nodes (9): closeSetupWizardModal(), ensureLiveTradingStarted(), handleWizardOverlayClick(), saveAndLaunchGateway(), setSplashTarget(), setWizardBanner(), skipToPureMathCore(), startSplashSequence() (+1 more)

### Community 121 - "composed.tsx"
Cohesion: 0.29
Nodes (5): Collection, CollectionStudy(), Detail, DetailStudy(), UsageDelivery()

### Community 122 - "cursor-resize/index.tsx"
Cohesion: 0.29
Nodes (6): CursorResize(), HANDLES, pull(), S, script(), START

### Community 123 - "reorder/index.tsx"
Cohesion: 0.25
Nodes (5): initial, ITEMS, poster, Reorder(), S

### Community 124 - "Craft"
Cohesion: 0.25
Nodes (7): A page of demos, Craft, Density, Icons and logos, Recipes, Restraint, Type

### Community 125 - "Looks"
Cohesion: 0.25
Nodes (7): Check it, Defining a look, From a public site, Looks, The built-in looks, The tokens, What a look doesn't change

### Community 126 - "dev.mjs"
Cohesion: 0.32
Nodes (4): devCommand(), main(), packageBin(), root

### Community 127 - "renderPriceCanvas"
Cohesion: 0.25
Nodes (8): drawSmoothCurve(), fillRoundRect(), renderPriceCanvas(), setupHiDPICanvas(), startChartAnimLoop(), stepChartAnimLoop(), strokeRoundRect(), triggerAnimLoop()

### Community 128 - "Core Pillars"
Cohesion: 0.29
Nodes (6): 1. Hypothesis-Testing Workflow, 2. Runtime Telemetry & NDJSON Probing, 3. DAP Protocol & Thread Contention Diagnostics, 4. Verification Protocol, Core Pillars, Evidence-Based Telemetry & DAP Debugger Skill

### Community 129 - "Frontend Design"
Cohesion: 0.29
Nodes (6): Design principles, Frontend Design, Ground your designs in the subject matter, More on writing in design, Process: plan, review against the brief, build, critique, Restraint and self-critique

### Community 130 - "backgrounds/index.tsx"
Cohesion: 0.43
Nodes (5): Backgrounds(), Digest(), Halftone(), studies, Study()

### Community 131 - "payout-flow/index.tsx"
Cohesion: 0.29
Nodes (3): ROWS, S, START

### Community 132 - "Connector"
Cohesion: 0.52
Nodes (6): along(), bend(), Connector(), corners(), elbow(), Route

### Community 133 - "Framing"
Cohesion: 0.29
Nodes (6): Checks, Framing, Phones, Small formats and the page, The layouts, The rules

### Community 134 - "Rehearse"
Cohesion: 0.29
Nodes (6): Lines that are never intentional, Other film lines, Prove the still before choreography, Rehearse, The host's own controls, The last pass

### Community 135 - "Core Pillars"
Cohesion: 0.29
Nodes (6): 1. GPU Compositor Acceleration & Layer Promotion, 2. Canvas Overdraw Elimination & Layer Separation, 3. DOM Reflow & Layout Thrashing Prevention, 4. Automatic Performance Verification & Rollback, Core Pillars, UI GPU Compositor & 60 FPS Render Optimizer Skill

### Community 136 - "Quick Start Guide"
Cohesion: 0.29
Nodes (6): 1. Launch Packaged Desktop Executable (`.exe`), 2. Run Self-Test Verification, 3. Run Automated Unit Test Suite (32 Tests), 4. Build Standalone Windows Executable, Quick Start Guide, TradeBot0: Multi-Agent Paper Trading & Genetic Evolution Arena (BTC/USD)

### Community 137 - "fix_item3_patch.py"
Cohesion: 0.38
Nodes (3): main(), _read(), _write()

### Community 138 - "fix_item4b_patch.py"
Cohesion: 0.38
Nodes (3): main(), _read(), _write()

### Community 139 - "fix_item5_patch.py"
Cohesion: 0.38
Nodes (3): main(), _read(), _write()

### Community 140 - "Python & Financial Engineering Standards (TradeBot0)"
Cohesion: 0.33
Nodes (5): 1. High-Precision Financial Math, 2. Strong Typing & Documentation, 3. Concurrency & Thread Safety, 4. Defensive Exception Handling & Logging, Python & Financial Engineering Standards (TradeBot0)

### Community 141 - "Core Pillars"
Cohesion: 0.33
Nodes (5): 1. Multi-Agent Role Decoupling, 2. Lock-Free Double-Buffered State Publishing, 3. Numerical Precision & Arithmetic Guardrails, Core Pillars, Quant Data Pipeline & Multi-Agent Architecture Skill

### Community 142 - "NOTICE.md"
Cohesion: 0.33
Nodes (3): Photograph sources, Brand artwork sources, Notices

### Community 143 - "Stageshow"
Cohesion: 0.33
Nodes (5): Contents, Preview, Stageshow, Use the kit, Verify

### Community 144 - "Backgrounds and the whole picture"
Cohesion: 0.33
Nodes (5): Backgrounds and the whole picture, Choose the ground for what it does, Compose the set before the tiles, Objects and drawings as tiles, Recompose for the host

### Community 145 - "Bento"
Cohesion: 0.33
Nodes (5): Bento, Kinds of tile, Layouts, Planning a grid, The rules

### Community 146 - "Choreography"
Cohesion: 0.33
Nodes (5): A change passing through an interface, Choose the curve for the movement, Choreography, Review the full change, Timing has different jobs

### Community 147 - "fix_item3_patch2.py"
Cohesion: 0.47
Nodes (3): main(), _read(), _write()

### Community 148 - "fix_item3_patch3.py"
Cohesion: 0.47
Nodes (3): main(), _read(), _write()

### Community 149 - "AIMRAN Library Skill (814 Animated UI Components)"
Cohesion: 0.40
Nodes (4): AIMRAN Library Skill (814 Animated UI Components), Categories (17 Total / 814 Components), How to Search & Retrieve Components, Integration Guidelines for Desktop / PyWebView (`TradeBot0_Arena.exe`)

### Community 150 - "Roll"
Cohesion: 0.70
Nodes (3): Button(), Roll(), RollNow()

### Community 151 - "scripts"
Cohesion: 0.40
Nodes (5): scripts, build, check:css, dev, typecheck

### Community 153 - "Test-Driven Development (TDD) Workflow"
Cohesion: 0.50
Nodes (3): 1. Golden Rule, 2. Test Coverage Requirements, Test-Driven Development (TDD) Workflow

### Community 154 - "Trading Safety & Multi-Portfolio Guardrails"
Cohesion: 0.50
Nodes (3): 1. Dual Mode Operation, 2. Invariant Risk Limits (AgentShield), Trading Safety & Multi-Portfolio Guardrails

### Community 156 - "scheduleProcessToastQueue"
Cohesion: 0.67
Nodes (4): attachToastInteractions(), dismissToast(), processToastQueue(), scheduleProcessToastQueue()

## Knowledge Gaps
- **10 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Parts` connect `Parts` to `film-checks.mjs`, `Connector`, `size.py`, `Chart`, `parts/index.ts`, `Collapse`, `google-calendar/index.tsx`, `Act`, `Roll`, `linear/index.tsx`, `Stage`, `cursor.tsx`, `Phone`, `HeroDemo.tsx`, `react`, `calendar/index.tsx`, `controls/index.tsx`, `kit-extras/index.tsx`, `Bar`, `States`, `Avatar`, `controls/index.ts`, `.rect`, `cards/index.tsx`, `Motion`, `Count`?**
  _High betweenness centrality (0.403) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `Stage()` (e.g. with `The rules` and `Recipes`) actually correct?**
  _`Stage()` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Should `test_intel_veto.py` be split into smaller, more focused modules?**
  _Cohesion score 0.03998261625380269 - nodes in this community are weakly interconnected._
- **Why does `size()` connect `size.py` to `Parts`?**
  _High betweenness centrality (0.400) - this node is a cross-community bridge._
- **Are the 35 inferred relationships involving `LiveArenaEngine` (e.g. with `1. Executive Summary & Architectural Vision` and `2.1 Problem Statement`) actually correct?**
  _`LiveArenaEngine` has 35 INFERRED edges - model-reasoned connections that need verification._
- **Should `scan.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05727848101265823 - nodes in this community are weakly interconnected._
- **Why does `surface()` connect `film-checks.mjs` to `size.py`, `Parts`?**
  _High betweenness centrality (0.088) - this node is a cross-community bridge._