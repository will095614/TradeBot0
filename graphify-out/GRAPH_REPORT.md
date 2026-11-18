# Graph Report - TradeBot0  (2026-11-19)

## Corpus Check
- 127 files · ~156,111 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 12 file(s) not represented in the graph (top: (none) 3, .bat 3, .iss 1)

## Summary
- 2480 nodes · 6592 edges · 130 communities (102 shown, 28 thin omitted)
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 679 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `876f2bc4`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- test_phase2_omniroute_client.py
- json
- test_update_checker.py
- test_v200_fixes.py
- TimeMachineArena
- logging
- test_item10_packaging.py
- CompetitorGenome
- Leaderboard
- re
- ArenaDashboard
- live_engine.py
- Collapse
- GatewaySupervisor
- view_model.py
- OmniRouteClient
- Act
- _ArenaBridgeApi
- MacroCommander
- test_gateway_install_progress_cancel.py
- test_article_prompt_snippet_210.py
- ruled-bento/index.tsx
- pytest
- test_phase3_ingestion.py
- soak_engine.py
- Stage
- time
- .run
- OrderSide
- test_performance_and_optimizations.py
- .bootstrap_intraday_session
- test_gui_item7.py
- StreamingCryptoFeed
- ConfigManager
- test_gateway_autolaunch_mandatory.py
- test_live_engine.py
- CandleBar
- ._get_daemon_command
- test_debug_report_fixes.py
- .shutdown
- test_save_launch_progress.py
- test_ai_panels_frontend.py
- test_event_article.py
- test_live_chop_gate.py
- test_ws_feed.py
- ._run_runtime_install
- LiveStrategyRunnerMixin
- classify_llm_error
- test_gateway_diagnosis.py
- test_phase1_debug_sweep.py
- test_llm_json_mode_fallback.py
- .test_single_key
- kit-extras/index.tsx
- test_508_chop_gate.py
- MonteCarloOddsEvaluator
- test_autosave_35.py
- QuoteManager
- test_phase2_optimize.py
- renderIntelHub
- _FakeCM
- threading
- test_intel_hub_layout.py
- renderAll
- RiskGuard
- test_chop_gate_seed.py
- IndicatorEngineMixin
- LiveQuote
- controls/index.ts
- test_504_omni_env_cache.py
- test_generation_fence.py
- persistence.py
- SessionCodecMixin
- saveAndLaunchGateway
- test_ui_feedback.py
- LiveArenaEngine
- ._live_loop
- .get_intel_hub_telemetry
- test_digest_refresh_session.py
- Decimal
- test_llm_concurrent_sessions.py
- Any
- test_card_reorder_anim.py
- FakeWS
- test_502_ui_state_delta.py
- test_507_candle_write_on_close.py
- ._try_enter_bracket
- _mock_resp
- _open_short
- compilerOptions
- test_orb_anchor_34.py
- subprocess
- _make_dash
- test_bootstrap_hydrates_fresh_sqlite_candles
- test_phase2g_graphics.py
- test_auto_evolve_fires_on_closed_trades
- test_ws_start_stop_delivers_then_stops
- test_321_auto_redeploy.py
- presence/index.tsx
- _client
- _FakeWindow
- _FakeHTTPResponse
- test_orb_day_rollover.py
- test_312_gateway_failed.py
- MultiTimeframeEngine
- cursors/index.tsx
- _error_body_text
- _open_long
- gateway_supervisor.py
- test_evaluate_signal_short_entries_mirror_long_brackets_all_strategies
- _OKHandler
- startSplashSequence
- fix_item5_patch.py
- Choreography
- smoke_external.py
- os
- scheduleProcessToastQueue

## God Nodes (most connected - your core abstractions)
1. `LiveArenaEngine` - 213 edges
2. `GatewaySupervisor` - 93 edges
3. `OmniRouteClient` - 93 edges
4. `BrokerSim` - 88 edges
5. `Portfolio` - 81 edges
6. `MacroCommander` - 81 edges
7. `OrderTicket` - 77 edges
8. `OrderSide` - 68 edges
9. `_ArenaBridgeApi` - 64 edges
10. `ArenaDashboard` - 61 edges

## Surprising Connections (you probably didn't know these)
- `4.1 Problem Statement` --references--> `BrokerSim`  [INFERRED]
  OptimizationFullGuide.md → src/arena/broker_sim.py
- `4.3 Implementation in `BrokerSim`` --references--> `BrokerSim`  [INFERRED]
  OptimizationFullGuide.md → src/arena/broker_sim.py
- `6.1 Problem Statement` --references--> `GeneticEvolver`  [INFERRED]
  OptimizationFullGuide.md → src/arena/evolution.py
- `1. Executive Summary & Architectural Vision` --references--> `LiveArenaEngine`  [INFERRED]
  OptimizationFullGuide.md → src/data/live_engine.py
- `2.1 Problem Statement` --references--> `LiveArenaEngine`  [INFERRED]
  OptimizationFullGuide.md → src/data/live_engine.py

## Import Cycles
- None detected.

## Communities (130 total, 28 thin omitted)

### Community 0 - "test_phase2_omniroute_client.py"
Cohesion: 0.09
Nodes (24): compute_backoff(), extract_json(), _mock_429_session(), _mock_resp(), test_chat_json_400_response_format_rejection_is_not_quota(), _run(), test_chat_json_all_retries_429_returns_none(), _run() (+16 more)

### Community 1 - "json"
Cohesion: 0.39
Nodes (5): test_setup_status_never_returns_password(), _commander_with_expanded_events(), test_article_lock_map_stays_bounded(), test_on_demand_article_is_intact_after_the_snapshot(), test_snapshot_carries_no_article_bodies()

### Community 2 - "test_update_checker.py"
Cohesion: 0.11
Nodes (17): check_for_updates(), compare_versions(), get_manifest_url(), _is_date_version(), _mock_response(), test_check_failed_on_bad_manifest(), test_check_failed_on_http_error(), test_check_failed_on_invalid_json() (+9 more)

### Community 3 - "test_v200_fixes.py"
Cohesion: 0.07
Nodes (30): 9. Rollout Schedule & Execution Checklist, GeneticEvolver, CompetitorStats, AggressiveCompetitor, ConservativeCompetitor, ORBCompetitor, SessionMeanPullbackCompetitor, TrailingGuardCompetitor (+22 more)

### Community 6 - "TimeMachineArena"
Cohesion: 0.13
Nodes (10): check_and_ensure_environment(), main(), TimeMachineArena, test_backtest_opens_shorts_on_downtrend(), test_evolution_tournament_runs_multiple_generations(), test_orb_window_excludes_current_bar(), test_timemachine_evolution_preserves_portfolio(), test_timemachine_simulation_with_synthetic_bars() (+2 more)

### Community 7 - "logging"
Cohesion: 0.14
Nodes (9): configure_logging(), get_log_dir(), _flush_file_handlers(), _remove_test_handlers(), test_configure_logging_never_raises_on_unwritable_dir(), test_get_log_dir_resolution(), test_stream_handler_present_when_stdout_exists(), test_stream_handler_skipped_when_stdout_is_none() (+1 more)

### Community 8 - "test_item10_packaging.py"
Cohesion: 0.08
Nodes (15): _FakeNpmProc, _FakeNpmProcFail, _FakeURLDownload, _make_bridge(), _make_node_zip_bytes(), _node_supervisor(), test_admin_password_required_before_onboarding(), test_console_url_follows_gateway_port() (+7 more)

### Community 9 - "CompetitorGenome"
Cohesion: 0.06
Nodes (34): BrokerSim, OrderTicket, _open_long(), test_apply_fill_value_error_does_not_kill_cadence(), _boom(), test_submit_order_returns_none_when_apply_fill_fails(), test_broker_sim_bracket_stop_loss_trigger(), test_broker_sim_leverage_liquidation_long_crash() (+26 more)

### Community 10 - "Leaderboard"
Cohesion: 0.11
Nodes (17): Leaderboard, test_evolve_now_with_fewer_than_two_rankings_does_not_raise(), test_last_records_class_default_present(), _counting_periods(), _portfolio_with_history(), test_fill_invalidates_cache(), test_metrics_cached_across_ticks_with_no_fills(), test_replace_equity_history_invalidates_cache() (+9 more)

### Community 11 - "re"
Cohesion: 0.06
Nodes (49): _scanned_files(), test_no_src_ai_reference_remains(), _css(), _css_block(), _fn_body(), _html(), _js(), test_article_failure_shows_reason_not_summary() (+41 more)

### Community 12 - "ArenaDashboard"
Cohesion: 0.07
Nodes (15): ArenaDashboard, _get_native_hwnd(), __getattr__(), test_setup_status_has_no_gateway_auto_spawn_option(), test_save_and_launch_gateway_waits_30_seconds(), test_manual_evolve_does_not_block_bridge(), test_run_loads_config_once_and_uses_window_title_constant(), test_window_startup_foreground_configuration() (+7 more)

### Community 14 - "live_engine.py"
Cohesion: 0.13
Nodes (11): __getattr__(), ExecutionReason, OrderSide, OrderStatus, OrderType, PositionSide, BaseCompetitor, CompetitorGenome (+3 more)

### Community 15 - "Collapse"
Cohesion: 0.08
Nodes (17): _contains_word(), IntelligenceHarvester, RawEvent, test_fetch_from_registry_dispatches_by_type_and_skips_forum(), test_fetch_live_feeds_still_returns_test_fixtures(), test_process_batch_carries_tier_thread_and_consensus(), _run(), test_process_batch_fallback_consensus_from_score() (+9 more)

### Community 16 - "GatewaySupervisor"
Cohesion: 0.13
Nodes (5): GatewaySupervisor, test_watchdog_backoff_schedule(), test_daemon_log_rotates_over_5mb(), test_existing_daemon_check_uses_2s_probe(), test_gateway_supervisor_port_and_health_conflict()

### Community 17 - "view_model.py"
Cohesion: 0.15
Nodes (3): _build_engine_view_model_impl(), _empty_view_model(), ViewModelPublisher

### Community 18 - "OmniRouteClient"
Cohesion: 0.08
Nodes (23): _looks_like_format_rejection(), OmniRouteClient, _mock_resp(), _mock_session(), test_chat_json_402_records_quota_failure(), _run(), test_chat_json_connection_refused_records_connection(), _run() (+15 more)

### Community 19 - "Act"
Cohesion: 0.08
Nodes (23): Architectural Highlights, FillEvent, Portfolio, _breakeven_portfolio(), test_breakeven_close_counts_as_closed_trade(), test_breakeven_close_keeps_win_rate_decided_only(), test_breakeven_count_resets(), test_portfolio_reset_clears_all_metrics() (+15 more)

### Community 21 - "MacroCommander"
Cohesion: 0.06
Nodes (17): _event_age_min(), MacroCommander, _wrapped(), test_synthesize_plumbs_raw_snippet(), test_fallback_thresholds_do_not_veto_on_single_word(), _run(), test_llm_numeric_parsing_never_raises(), _run() (+9 more)

### Community 22 - "test_gateway_install_progress_cancel.py"
Cohesion: 0.10
Nodes (16): _fake_node_zip_bytes(), _FakeDownloadResp, _FakeProc, _make_supervisor(), _SlowResp, test_bridge_cancel_and_status_shape(), test_cancel_during_node_download(), test_cancel_during_npm_install_removes_partial_package() (+8 more)

### Community 23 - "test_article_prompt_snippet_210.py"
Cohesion: 0.10
Nodes (9): build_event_article_prompts(), _dedup_tickers(), _runner(), _safe_float(), _event_dict(), test_prompt_includes_raw_snippet(), test_prompt_without_snippet_omits_line(), test_telemetry_strips_raw_snippet() (+1 more)

### Community 24 - "ruled-bento/index.tsx"
Cohesion: 0.09
Nodes (15): ForumCollector, _symbols_from_registry(), parse_stocktwits_stream(), _registry_mock_get(), _stream_json(), test_forum_batch_scored_without_llm_when_offline(), mock_get(), test_forum_collector_fast_test_short_circuits() (+7 more)

### Community 25 - "pytest"
Cohesion: 0.15
Nodes (11): ETHFeed, _bar(), _ccxt_ohlcv(), test_fetch_dataframe_both_sources_fail_raises(), test_fetch_dataframe_falls_back_to_ccxt_kraken(), test_fetch_historical_bars_yahoo_multiindex_columns(), test_fetch_historical_bars_yahoo_success(), test_generate_signal_real_path_setups_and_exits() (+3 more)

### Community 26 - "test_phase3_ingestion.py"
Cohesion: 0.12
Nodes (15): DeduplicationBuffer, parse_rss_atom(), _fake_registry_response(), _new_harvester(), _registry_get_ok(), test_deduplication_buffer(), test_feed_registry_completeness_r3(), test_fetch_from_registry_parses_real_rss_xml() (+7 more)

### Community 27 - "soak_engine.py"
Cohesion: 0.13
Nodes (14): closing_fills_since(), db_stats(), do_slice(), genome_valid(), main(), _sample(), make_quote(), _parse_args() (+6 more)

### Community 28 - "Stage"
Cohesion: 0.06
Nodes (31): animCandles, chartBeacons, closeInstallCancelConfirm(), closeSetupWizardModal(), closeShutdownModal(), confirmCancelInstallAndClose(), currentSplashSteps, EVOLVE_INTERVAL_OPTIONS (+23 more)

### Community 29 - "time"
Cohesion: 0.09
Nodes (19): _clean_html_text(), _parse_iso_ts(), parse_polymarket_events(), parse_reddit_posts(), MacroRegimeState, _mock_commander(), test_feed_numeric_parsing_never_raises(), test_keyword_word_boundaries_no_substring_false_positives() (+11 more)

### Community 30 - ".run"
Cohesion: 0.19
Nodes (5): _activate_foreground_startup(), _on_window_closed(), _on_window_closing(), _on_window_shown(), _delayed_activation()

### Community 31 - "OrderSide"
Cohesion: 0.06
Nodes (30): 1. Executive Summary & Architectural Vision, 2.1 Problem Statement, 2.2 Architectural Solution, 2.3 Detailed Implementation Steps, 2. Phase 1 (P1): Low-Latency WebSocket Streaming & Resilient Circuit Breaking, 3.1 Problem Statement, 3.2 Architectural Solution, 3.3 Database Schema & Implementation (+22 more)

### Community 32 - "test_performance_and_optimizations.py"
Cohesion: 0.11
Nodes (13): _build_html_template(), _get_assets_dir(), _load_asset(), test_launchers_and_shortcut_integrity(), test_macro_veto_intent_preserved_in_live_evaluation(), test_phase4_mtf_trend_confluence_gatekeeper(), test_portfolio_no_duplicate_apply_fill_returns(), test_reset_engine_preserves_cadence() (+5 more)

### Community 33 - ".bootstrap_intraday_session"
Cohesion: 0.09
Nodes (10): test_signal_exit_fast_path_closes_under_hold_cash(), test_full_restore_bootstrap_start_integration(), test_get_ui_state_mutation_isolation(), test_close_ticket_bypasses_veto_and_gates_under_hold_cash(), test_bootstrap_anchors_orb_range_to_first_15_warmup_bars(), test_session_state_save_and_restore_and_shutdown_bridge(), _fixture_bars(), test_candle_cadence_dispatcher_timing_and_dispatch() (+2 more)

### Community 34 - "test_gui_item7.py"
Cohesion: 0.13
Nodes (13): build_engine_view_model(), _rankings(), test_view_model_does_not_fabricate_take_profit(), test_view_model_reports_unknown_mc_and_quota(), test_view_model_short_unrealized_pnl_pct(), test_view_model_skips_stale_ranking_entry(), test_view_model_survives_missing_or_broken_engine(), test_engine_stop_closes_quote_session_pool() (+5 more)

### Community 35 - "StreamingCryptoFeed"
Cohesion: 0.24
Nodes (3): StreamingCryptoFeed, test_phase1_websocket_feed_parsing_and_fast_path_fallback(), test_parse_binance_ticker_rejects_garbage()

### Community 36 - "ConfigManager"
Cohesion: 0.08
Nodes (9): ConfigManager, test_gateway_auto_spawn_option_removed(), test_bridge_stepwise_simulation_erroneous_then_valid(), test_config_manager_atomic_recovery_from_corruption(), test_config_manager_env_preservation(), test_config_manager_input_sanitization(), test_ui_assets_art_jargon_and_cjk_cleanliness(), test_admin_password_too_short_rejected() (+1 more)

### Community 37 - "test_gateway_autolaunch_mandatory.py"
Cohesion: 0.11
Nodes (9): _assets_root(), _FakeEvent, _FakeWebview, _FakeWindow, _make_bridge(), test_run_spawns_despite_stored_false(), test_save_and_launch_spawns_despite_stored_false(), test_setup_status_has_no_autolaunch_option() (+1 more)

### Community 38 - "test_live_engine.py"
Cohesion: 0.09
Nodes (28): _drive(), _drive_fixed(), _fixture_bars(), _quote(), _startup_engine_long(), test_anti_churn_cooldown_prevents_same_timestamp_reentry(), test_deserialize_ticket_round_trips_and_rejects_garbage(), test_evaluate_live_strategies_short_entries() (+20 more)

### Community 39 - "CandleBar"
Cohesion: 0.13
Nodes (9): CandleBar, _fixture_bars(), test_bootstrap_resets_live_trading_state_when_orders_disabled(), test_backtest_slippage_uses_measured_atr(), _bars(), _open_short(), _tape(), test_backtest_short_exits_at_trailed_level_not_original_stop() (+1 more)

### Community 40 - "._get_daemon_command"
Cohesion: 0.13
Nodes (4): test_daemon_command_falls_back_to_global(), test_daemon_command_prefers_runtime_install(), test_gateway_unavailable_reason_no_node(), test_gateway_unavailable_reason_node_but_no_omniroute()

### Community 41 - "test_debug_report_fixes.py"
Cohesion: 0.10
Nodes (10): _fixture_bars(), _raise_no_network(), test_cooperative_stop_event(), test_offline_start_does_not_execute_stale_candles(), test_session_save_and_restore_with_locked_margin(), test_slow_bootstrap_stop_safety(), test_start_live_trading_does_not_wipe_restored_positions(), test_start_live_trading_readiness_handshake() (+2 more)

### Community 42 - ".shutdown"
Cohesion: 0.10
Nodes (9): test_start_daemon_polls_health_with_2s_timeout_and_logs_to_file(), fake_probe(), test_start_daemon_spawns_and_waits_with_fake_proc(), test_start_daemon_times_out_when_health_never_ok(), _free_port(), test_shutdown_does_not_kill_foreign_process(), test_shutdown_kills_own_child(), _wait_port_open() (+1 more)

### Community 43 - "test_save_launch_progress.py"
Cohesion: 0.13
Nodes (10): _make_bridge(), _read_app_js(), test_get_save_launch_status_returns_copy(), test_save_and_launch_does_not_jump_splash_to_75(), test_save_launch_failed_stage_never_reports_100(), test_save_launch_stage_advances_and_done_only_on_return(), test_save_launch_stage_resets_between_runs(), test_save_launch_status_polled_from_js() (+2 more)

### Community 44 - "test_ai_panels_frontend.py"
Cohesion: 0.22
Nodes (19): _css(), _dashboard(), _html(), _js(), test_commander_and_stream_titles(), test_compact_mode_fits_intro_line_and_status_lines_hold_width(), test_deck_empty_slots_collapse_and_level_bottoms(), test_dock_gear_tooltip_is_ai_services() (+11 more)

### Community 45 - "test_event_article.py"
Cohesion: 0.21
Nodes (13): _event_id(), _make_commander(), test_article_generation_uses_long_timeout(), test_bridge_get_event_article(), test_concurrent_expands_merge_into_one_llm_call(), test_curated_event_carries_tickers_article_fields(), test_curated_event_empty_tickers_becomes_empty_list(), test_first_expand_generates_once_and_caches() (+5 more)

### Community 46 - "test_live_chop_gate.py"
Cohesion: 0.19
Nodes (11): _bars(), _choppy_closes(), _engine_with_15m(), test_chop_gate_blocks_entry_through_try_enter_bracket(), test_chop_gate_blocks_on_choppy_15m(), test_chop_gate_excludes_the_forming_bucket(), test_chop_gate_never_blocks_signal_exit_close(), test_chop_gate_open_on_trending_15m() (+3 more)

### Community 47 - "test_ws_feed.py"
Cohesion: 0.16
Nodes (8): _run_feed(), test_ws_clean_server_close_counts_as_reconnect(), test_ws_connect_and_stream_delivers_quotes(), _on_quote(), test_ws_reconnect_backoff_on_disconnect(), _fake_connect(), _fake_sleep(), _ticker_msg()

### Community 50 - "classify_llm_error"
Cohesion: 0.11
Nodes (16): classify_llm_error(), _retry_window_seconds(), test_classifier_402_plain_text_body_is_quota(), test_classifier_429_without_markers_is_transient(), test_classifier_auth_and_unknown(), test_classifier_deepseek_402_vs_429(), test_classifier_gemini_402_is_quota(), test_classifier_gemini_429_perday_vs_perminute() (+8 more)

### Community 51 - "test_gateway_diagnosis.py"
Cohesion: 0.18
Nodes (14): _css(), _js(), _supervisor(), test_frontend_diagnosis_line_never_wraps(), test_frontend_diagnosis_line_wiring(), test_watchdog_backs_off_between_failures(), test_watchdog_does_not_restart_healthy_gateway(), test_watchdog_first_tick_waits_one_interval() (+6 more)

### Community 52 - "test_phase1_debug_sweep.py"
Cohesion: 0.15
Nodes (8): _quote(), _safe_refresh(), test_deserialize_ticket_garbage_numbers_return_none(), test_ensure_active_live_positions_respects_strategy_cooldown(), test_gateway_supervisor_atexit_does_not_retain_instances(), test_refresh_intel_digest_is_serialized_under_concurrent_calls(), _run(), test_slice_ticks_capped_while_paused_and_cleared_on_resume()

### Community 53 - "test_llm_json_mode_fallback.py"
Cohesion: 0.18
Nodes (7): _client_with(), _CM, _FakeSession, _Resp, test_generic_400_does_not_trigger_the_format_retry(), test_rejected_format_is_remembered_for_later_calls(), test_rejected_response_format_retries_without_it_and_parses()

### Community 54 - ".test_single_key"
Cohesion: 0.18
Nodes (4): test_gateway_supervisor_http_responses(), test_gateway_supervisor_key_validation_defensive(), test_gateway_supervisor_nvidia_endpoint(), test_key_rate_limit_429_is_not_verified()

### Community 55 - "kit-extras/index.tsx"
Cohesion: 0.19
Nodes (4): ArenaStorage, _retry_on_db_error(), test_phase2_sqlite_wal_persistence_and_cold_start_hydration(), test_restore_survives_garbage_stop_ticket_and_entry_ts()

### Community 56 - "test_508_chop_gate.py"
Cohesion: 0.18
Nodes (9): efficiency_ratio(), _bar(), _choppy_bars(), test_efficiency_ratio_unit(), test_gate_blocks_entries_on_choppy_tape(), test_gate_inactive_on_trend_tape(), test_gate_never_blocks_closes(), _total_closed() (+1 more)

### Community 57 - "MonteCarloOddsEvaluator"
Cohesion: 0.17
Nodes (6): MonteCarloBracketOdds, MonteCarloOddsEvaluator, test_monte_carlo_ev_gate_odds_evaluation(), test_monte_carlo_without_numpy_reports_unknown(), test_v200_31_33_mixins_and_timemachine_student_t(), test_v200_bug08_macro_tp_expansion_scales_actual_ticket_distance()

### Community 58 - "test_autosave_35.py"
Cohesion: 0.18
Nodes (8): _bars(), _engine(), _raise_no_network(), test_autosave_does_not_fire_when_stopped_or_superseded(), test_crash_like_stop_leaves_restorable_autosave(), test_evolution_marks_autosave_pending_and_it_fires_immediately(), test_live_loop_triggers_periodic_autosave(), test_periodic_autosave_writes_snapshot_when_interval_elapses()

### Community 59 - "QuoteManager"
Cohesion: 0.19
Nodes (3): QuoteManager, test_dead_cascade_state_is_gone(), test_ws_quote_path_still_works()

### Community 60 - "test_phase2_optimize.py"
Cohesion: 0.25
Nodes (8): wrapper(), _candle(), test_p2_concurrent_candle_writes_all_persist(), writer(), test_p2_engine_stop_closes_storage_and_restart_still_writes(), test_p2_persistent_connection_recovers_from_stale_handle(), test_p2_persistent_connection_reused_and_candle_persists_across_close(), test_p2_save_candle_is_fast_with_persistent_connection()

### Community 61 - "renderIntelHub"
Cohesion: 0.19
Nodes (15): buildIntelEventCard(), cleanIntelSummary(), escapeHtml(), hashTickerName(), intelArticleBodyEl(), intelEventKey(), preloadIntelArticles(), pumpIntelArticlePreload() (+7 more)

### Community 62 - "_FakeCM"
Cohesion: 0.16
Nodes (3): _FakeCM, _FakeResp, _FakeSession

### Community 63 - "threading"
Cohesion: 0.21
Nodes (7): test_shutdown_closes_window_on_calling_thread(), _drive(), _make_engine(), _quote(), test_concurrent_publish_harvests_each_fill_once(), test_publish_state_snapshot_holds_engine_lock(), publish_many()

### Community 64 - "test_intel_hub_layout.py"
Cohesion: 0.25
Nodes (12): _commander(), _css(), _js(), _mock_pipeline(), _rule(), _structured(), test_stream_loading_block_is_centered_with_meter(), test_sync_status_failed_when_feeds_down() (+4 more)

### Community 65 - "renderAll"
Cohesion: 0.16
Nodes (20): changeEvolveInterval(), fmtPct(), fmtSignedUsd(), fmtTimeSec(), fmtUsd(), renderAll(), renderFills(), renderHeader() (+12 more)

### Community 66 - "RiskGuard"
Cohesion: 0.18
Nodes (8): RiskGuard, _broker(), test_aggressive_stopout_loss_capped_at_risk_pct(), test_drawdown_trip_closes_positions_via_broker(), test_risk_budget_ignores_leverage(), test_risk_guard_cap_ignores_leverage(), test_risk_guard_rejects_zero_qty_overclose_overcover_insufficient_margin(), test_v200_bug10_risk_guard_purity_and_dynamic_slippage()

### Community 67 - "test_chop_gate_seed.py"
Cohesion: 0.29
Nodes (10): _engine(), _feed_1m(), _tape_end_anchored(), _tape_slot_aligned(), test_seed_helper_feeds_continuous_chain_and_arms_gate(), test_seed_helper_gap_truncates_to_suffix_after_gap(), test_seed_helper_malformed_row_skipped_not_fabricated(), test_seed_helper_misaligned_or_empty_seeds_nothing() (+2 more)

### Community 70 - "controls/index.ts"
Cohesion: 0.21
Nodes (10): _broker(), _commander(), test_backtest_default_sizing_is_one(), test_compute_r_multiple_qty_scales_budget_and_clamps(), test_evaluate_signal_sizing_shrinks_qty_not_sl(), test_no_confidence_means_no_sizing_effect(), test_per_strategy_sensitivity_scales_the_deviation(), test_sizing_formula_exact_values() (+2 more)

### Community 71 - "test_504_omni_env_cache.py"
Cohesion: 0.28
Nodes (8): _counting_read_text(), _manager(), test_content_change_is_visible_after_rewrite(), test_missing_file_then_created(), test_mtime_change_invalidates_even_with_same_content(), test_repeated_reads_hit_cache(), test_returned_dict_is_a_copy(), test_write_then_read_sees_new_password()

### Community 72 - "test_generation_fence.py"
Cohesion: 0.18
Nodes (6): _keyframes_block(), _make_fill(), test_save_history_failure_is_logged_not_swallowed(), test_splash_overlay_is_lightened_not_removed(), test_stale_engine_harvest_fills_refused(), test_stale_engine_save_session_state_refused()

### Community 73 - "persistence.py"
Cohesion: 0.21
Nodes (6): _records(), test_save_history_closes_storage_it_creates(), close(), __init__(), test_save_history_reuses_caller_storage_without_closing(), __init__()

### Community 75 - "saveAndLaunchGateway"
Cohesion: 0.21
Nodes (12): applyGatewayAvailability(), checkOnboardingBoot(), initAppBoot(), installGatewayRuntime(), openSetupWizardModal(), refreshGatewayAvailability(), saveAndLaunchGateway(), setWizardBanner() (+4 more)

### Community 76 - "test_ui_feedback.py"
Cohesion: 0.23
Nodes (7): _copy_text_to_clipboard_windows(), _bridge_with_env(), test_copy_password_copies_value_but_never_returns_it(), test_copy_password_helper_failure(), test_copy_password_not_configured(), test_copy_text_to_clipboard_windows_non_windows(), test_copy_text_to_clipboard_windows_roundtrip()

### Community 77 - "LiveArenaEngine"
Cohesion: 0.10
Nodes (12): LiveArenaEngine, test_ensure_active_live_positions_short_brackets(), test_mtf_gate_blocks_counter_trend_entries(), test_recompute_candle_indicators_rsi_atr_orb_mean(), test_restore_applies_genome_leverage_to_portfolio(), _quote(), test_generate_fallback_bars_deleted(), test_is_quote_fresh() (+4 more)

### Community 78 - "._live_loop"
Cohesion: 0.09
Nodes (4): test_pause_feed_updates_ui_snapshot_immediately(), test_stale_engine_evolve_now_refused(), test_stale_engine_state_publish_skipped(), test_auto_evolve_timer_and_toggle()

### Community 79 - ".get_intel_hub_telemetry"
Cohesion: 0.15
Nodes (5): test_sync_status_failed_when_gateway_down(), test_quota_pct_has_no_invented_denominator(), _run_429(), test_quota_pct_uses_user_set_budget(), test_quota_throttling_slows_digest()

### Community 80 - "test_digest_refresh_session.py"
Cohesion: 0.23
Nodes (5): _FakeForum, _FakeHarvester, _make_commander(), test_concurrent_article_call_survives_refresh(), test_two_refreshes_leave_session_open()

### Community 82 - "test_llm_concurrent_sessions.py"
Cohesion: 0.22
Nodes (4): _StubGateway, test_four_threads_expand_concurrently_without_closing_each_other(), _one(), _worker()

### Community 84 - "test_card_reorder_anim.py"
Cohesion: 0.35
Nodes (10): _css(), _js(), _reorder_block(), test_cards_are_stable_nodes_never_recreated_on_reorder(), test_flip_cleanup_clears_class_and_transform(), test_flip_inverts_with_translate_and_plays_via_class(), test_flip_records_first_rects_before_moving_nodes(), test_flip_runs_only_when_order_changes() (+2 more)

### Community 86 - "test_502_ui_state_delta.py"
Cohesion: 0.33
Nodes (5): _engine(), _snapshot(), test_deepcopy_never_receives_heavy_arrays_on_unchanged_poll(), test_delta_is_still_a_defensive_copy(), test_delta_output_identical_to_old_path()

### Community 87 - "test_507_candle_write_on_close.py"
Cohesion: 0.42
Nodes (7): _counting_save(), _engine(), test_bar_close_persists_final_bar_once(), test_closed_bar_is_in_sqlite_after_close(), test_out_of_order_tick_does_not_double_save(), test_three_minutes_persist_two_closed_bars(), test_ticks_within_one_minute_write_nothing()

### Community 88 - "._try_enter_bracket"
Cohesion: 0.36
Nodes (12): _ev(), _now_iso(), _offline_commander(), test_direction_thresholds_long_and_short(), test_events_older_than_60_min_excluded(), test_fallback_never_enters_hold_cash(), test_half_life_decay_60_min_is_half_weight(), test_llm_hold_cash_with_confidence_passes_through() (+4 more)

### Community 89 - "_mock_resp"
Cohesion: 0.31
Nodes (10): _coinbase_stats_payload(), _coinbase_ticker_payload(), _kraken_payload(), _mock_resp(), test_binance_quote_success_parses_all_fields(), test_coinbase_quote_success_parses(), test_kraken_quote_success_parses(), dispatch() (+2 more)

### Community 90 - "_open_short"
Cohesion: 0.20
Nodes (5): _open_short(), test_evaluate_live_strategies_short_exits_are_signal_only(), test_evaluate_live_strategies_small_gain_does_not_close_shorts(), test_stagnation_exit_closes_after_40m(), test_trailing_guard_short_ratchet_moves_stop_down()

### Community 91 - "compilerOptions"
Cohesion: 0.20
Nodes (5): InterruptDebouncer, StructuredEvent, test_structured_event_new_fields_default(), test_stage2_interrupt_debouncing_r4(), _run()

### Community 92 - "test_orb_anchor_34.py"
Cohesion: 0.22
Nodes (4): _tape_bar(), test_backtest_orb_range_anchored_to_first_15_tape_bars(), test_live_orb_range_does_not_drift_with_rolling_buffer(), _warmup_bars()

### Community 93 - "subprocess"
Cohesion: 0.33
Nodes (5): _git(), test_system_config_is_ignored_by_git(), test_system_config_is_untracked_but_present_on_disk(), test_p2_eth_feed_first_fetch_loads_pandas_and_behaves(), test_p2_eth_feed_import_does_not_import_pandas()

### Community 94 - "_make_dash"
Cohesion: 0.25
Nodes (7): _FakeWebview, _make_dash(), test_bridge_state_carries_diagnosis(), test_dashboard_diagnosis_states(), test_run_skips_watchdog_without_admin_password(), test_run_starts_watchdog_when_gateway_expected(), test_save_and_launch_starts_watchdog()

### Community 95 - "test_bootstrap_hydrates_fresh_sqlite_candles"
Cohesion: 0.22
Nodes (3): _cache_rows(), test_bootstrap_hydrates_fresh_sqlite_candles(), test_bootstrap_rejects_stale_sqlite_candles()

### Community 96 - "test_phase2g_graphics.py"
Cohesion: 0.31
Nodes (4): _js(), test_p2g_chart_loop_capped_at_60fps(), test_p2g_hidden_view_stops_chart_loop(), test_p2g_no_temporary_probe_left_in_shipped_assets()

### Community 97 - "test_auto_evolve_fires_on_closed_trades"
Cohesion: 0.32
Nodes (3): test_auto_evolve_fires_on_closed_trades(), _round_trips(), test_toggle_auto_evolve_reenable_compensates_disabled_time()

### Community 99 - "test_321_auto_redeploy.py"
Cohesion: 0.39
Nodes (5): _flat_engine(), test_no_redeploy_when_any_position_open(), test_redeploy_logs_once_per_flat_episode(), test_switch_off_does_not_redeploy(), test_switch_on_default_redeploys_when_flat()

### Community 100 - "presence/index.tsx"
Cohesion: 0.22
Nodes (13): addChartBeacon(), copyOmniPassword(), createPositionClosedToastElement(), createPositionToastElement(), enqueueToast(), hexToRgba(), pollBackend(), previewPositionAnimation() (+5 more)

### Community 101 - "_client"
Cohesion: 0.25
Nodes (8): _client(), test_all_providers_quota_exhausted_needs_every_provider(), test_daily_budget_exhausted(), test_no_configured_providers_is_never_exhausted(), test_stale_quota_records_expire(), test_success_clears_quota_records(), test_transient_failures_never_count_as_quota(), test_unattributed_quota_counts_only_for_single_provider()

### Community 104 - "test_orb_day_rollover.py"
Cohesion: 0.36
Nodes (5): _minute_candles(), _tape_bar(), test_backtest_orb_range_rolls_at_utc_midnight(), test_live_orb_range_is_forming_on_a_partial_new_day(), test_live_orb_range_rolls_at_utc_midnight()

### Community 106 - "test_312_gateway_failed.py"
Cohesion: 0.52
Nodes (5): _dead_gateway_commander(), _mock_pipeline(), _structured(), test_sync_status_done_when_dead_gateway_still_yields_fallback_digest(), test_sync_status_failed_when_gateway_dead_and_nothing_produced()

### Community 107 - "MultiTimeframeEngine"
Cohesion: 0.09
Nodes (16): MultiTimeframeEngine, _buckets(), _hourly_bars(), _minute_bars(), test_engine_seed_fetch_failure_stays_neutral(), test_engine_seed_rejects_stale_bars(), test_engine_seed_wires_bias_and_survives_live_bar(), test_seed_1h_buckets_downtrend_goes_bearish_and_vetoes_longs() (+8 more)

### Community 108 - "cursors/index.tsx"
Cohesion: 0.25
Nodes (11): drawPriceChart(), locateMouseAndRefreshChart(), setIntelSortMode(), setLgWallpaper(), setRightTab(), setScaleMode(), setupChartInteraction(), switchMainView() (+3 more)

### Community 110 - "_error_body_text"
Cohesion: 0.33
Nodes (3): _error_body_text(), _walk(), _extract_error_provider()

### Community 111 - "_open_long"
Cohesion: 0.33
Nodes (3): _open_long(), test_bracket_take_profit_closes_via_on_tick(), test_evaluate_live_strategies_small_gain_does_not_close_longs()

### Community 112 - "gateway_supervisor.py"
Cohesion: 0.08
Nodes (9): _default_daemon_log_path(), _default_install_log_path(), _FakeEvent, _FakeWebview, _FakeWindow, test_daemon_log_default_path_is_project_logs(), test_run_auto_spawn_waits_30_seconds(), test_run_skips_auto_spawn_without_admin_password() (+1 more)

### Community 134 - "startSplashSequence"
Cohesion: 0.22
Nodes (9): closeResetModal(), confirmResetArena(), ensureLiveTradingStarted(), handleResetOverlayClick(), isSplashGateOpen(), resetArena(), setSplashTarget(), startSplashSequence() (+1 more)

### Community 139 - "fix_item5_patch.py"
Cohesion: 0.29
Nodes (7): fillRoundRect(), renderPriceCanvas(), setupHiDPICanvas(), startChartAnimLoop(), stepChartAnimLoop(), strokeRoundRect(), triggerAnimLoop()

### Community 146 - "Choreography"
Cohesion: 0.29
Nodes (6): 1. Launch Packaged Desktop Executable (`.exe`), 2. Run Self-Test Verification, 3. Run Automated Unit Test Suite (32 Tests), 4. Build Standalone Windows Executable, Quick Start Guide, TradeBot0: Multi-Agent Paper Trading & Genetic Evolution Arena (BTC/USD)

### Community 161 - "smoke_external.py"
Cohesion: 0.25
Nodes (14): check_binance_rest(), check_binance_ws(), _run(), check_ccxt_kraken(), check_coinbase_rest(), check_feed_registry(), check_kraken_rest(), check_node_head() (+6 more)

### Community 163 - "os"
Cohesion: 0.17
Nodes (4): isolate_arena_memory(), _load_soak_helpers(), soak(), test_p3_breaker_trips_force_closes_and_resets_on_evolve()

### Community 164 - "scheduleProcessToastQueue"
Cohesion: 0.67
Nodes (4): attachToastInteractions(), dismissToast(), processToastQueue(), scheduleProcessToastQueue()

## Knowledge Gaps
- **28 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `LiveArenaEngine` connect `LiveArenaEngine` to `test_v200_fixes.py`, `TimeMachineArena`, `CompetitorGenome`, `Leaderboard`, `ArenaDashboard`, `live_engine.py`, `view_model.py`, `OmniRouteClient`, `Act`, `MacroCommander`, `pytest`, `soak_engine.py`, `time`, `OrderSide`, `test_performance_and_optimizations.py`, `.bootstrap_intraday_session`, `test_gui_item7.py`, `StreamingCryptoFeed`, `ConfigManager`, `os`, `test_live_engine.py`, `CandleBar`, `test_debug_report_fixes.py`, `test_live_chop_gate.py`, `LiveStrategyRunnerMixin`, `test_phase1_debug_sweep.py`, `kit-extras/index.tsx`, `MonteCarloOddsEvaluator`, `test_autosave_35.py`, `QuoteManager`, `test_phase2_optimize.py`, `threading`, `test_chop_gate_seed.py`, `IndicatorEngineMixin`, `LiveQuote`, `controls/index.ts`, `test_generation_fence.py`, `SessionCodecMixin`, `._live_loop`, `test_502_ui_state_delta.py`, `test_507_candle_write_on_close.py`, `_mock_resp`, `_open_short`, `test_orb_anchor_34.py`, `test_bootstrap_hydrates_fresh_sqlite_candles`, `test_auto_evolve_fires_on_closed_trades`, `test_321_auto_redeploy.py`, `test_orb_day_rollover.py`, `MultiTimeframeEngine`, `_open_long`?**
  _High betweenness centrality (0.227) - this node is a cross-community bridge._
- **Are the 27 inferred relationships involving `LiveArenaEngine` (e.g. with `1. Executive Summary & Architectural Vision` and `2.1 Problem Statement`) actually correct?**
  _`LiveArenaEngine` has 27 INFERRED edges - model-reasoned connections that need verification._
- **Should `test_phase2_omniroute_client.py` be split into smaller, more focused modules?**
  _Cohesion score 0.0873015873015873 - nodes in this community are weakly interconnected._
- **Why does `OmniRouteClient` connect `OmniRouteClient` to `test_phase2_omniroute_client.py`, `json`, `test_v200_fixes.py`, `test_item10_packaging.py`, `live_engine.py`, `Collapse`, `MacroCommander`, `ruled-bento/index.tsx`, `time`, `test_performance_and_optimizations.py`, `test_gateway_diagnosis.py`, `test_llm_json_mode_fallback.py`, `LiveArenaEngine`, `.get_intel_hub_telemetry`, `test_digest_refresh_session.py`, `test_llm_concurrent_sessions.py`, `compilerOptions`, `_client`, `._all_sessions`, `.get_session`?**
  _High betweenness centrality (0.090) - this node is a cross-community bridge._
- **Are the 14 inferred relationships involving `GatewaySupervisor` (e.g. with `ArenaDashboard` and `test_watchdog_backoff_schedule()`) actually correct?**
  _`GatewaySupervisor` has 14 INFERRED edges - model-reasoned connections that need verification._
- **Should `test_update_checker.py` be split into smaller, more focused modules?**
  _Cohesion score 0.10695187165775401 - nodes in this community are weakly interconnected._
- **Why does `GatewaySupervisor` connect `GatewaySupervisor` to `json`, `test_item10_packaging.py`, `ArenaDashboard`, `test_gateway_install_progress_cancel.py`, `time`, `.run`, `test_performance_and_optimizations.py`, `test_gui_item7.py`, `ConfigManager`, `test_gateway_autolaunch_mandatory.py`, `._get_daemon_command`, `.shutdown`, `test_save_launch_progress.py`, `._run_runtime_install`, `test_gateway_diagnosis.py`, `test_phase1_debug_sweep.py`, `.test_single_key`, `Any`, `_make_dash`, `_FakeHTTPResponse`, `gateway_supervisor.py`?**
  _High betweenness centrality (0.073) - this node is a cross-community bridge._