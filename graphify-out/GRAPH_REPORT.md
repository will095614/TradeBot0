# Graph Report - TradeBot0_Local  (2026-11-23)

## Corpus Check
- 130 files · ~175,349 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 10 file(s) not represented in the graph (top: (none) 4, .iss 1, .lnk 1)

## Summary
- 2744 nodes · 7715 edges · 125 communities (89 shown, 36 thin omitted)
- Extraction: 87% EXTRACTED · 13% INFERRED · 0% AMBIGUOUS · INFERRED: 1020 edges (avg confidence: 0.89)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `2f5f4b5a`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- test_phase2_omniroute_client.py
- json
- test_update_checker.py
- test_v200_fixes.py
- CandleBar
- logging
- test_item10_packaging.py
- CompetitorGenome
- Leaderboard
- test_ui_contract.py
- ArenaDashboard
- OrderSide
- IntelligenceHarvester
- .start_daemon
- ViewModelPublisher
- OmniRouteClient
- Portfolio
- _ArenaBridgeApi
- MacroCommander
- _make_supervisor
- ._get_daemon_command
- _symbols_from_registry
- syncAppShellInert
- test_phase3_ingestion.py
- soak_engine.py
- Stage
- re
- Any
- test_track_c_gateway_npm_strips_secrets_and_no_blind_retry
- time
- test_performance_and_optimizations.py
- test_gui_item7.py
- StreamingCryptoFeed
- ConfigManager
- test_gateway_autolaunch_mandatory.py
- test_live_engine.py
- _SliceableDeque
- .omniroute_installed
- test_debug_report_fixes.py
- .shutdown
- test_save_launch_progress.py
- test_ai_panels_frontend.py
- test_event_article.py
- test_live_chop_gate.py
- test_ws_feed.py
- ._run_runtime_install
- LiveStrategyRunnerMixin
- DeduplicationBuffer
- test_gateway_diagnosis.py
- test_phase1_debug_sweep.py
- test_llm_json_mode_fallback.py
- test_v250_fixes.py
- ArenaStorage
- test_intel_stream_redesign.py
- MonteCarloOddsEvaluator
- test_forum_collector.py
- QuoteManager
- InterruptDebouncer
- renderIntelHub
- _FakeCM
- threading
- test_intel_hub_layout.py
- renderAll
- test_item12a_omniroute.py
- ._build_snapshot_locked
- IndicatorEngineMixin
- LiveQuote
- controls/index.ts
- main
- Decimal
- RawEvent
- SessionCodecMixin
- saveAndLaunchGateway
- test_ui_feedback.py
- LiveArenaEngine
- ._live_loop
- soak_engine.py
- .fetch_from_registry
- live_engine.py
- test_v287_render_guards.py
- .sync_admin_password
- test_card_reorder_anim.py
- FakeWS
- test_mtf_seed_async_25.py
- .update_from_1m_bar
- ._try_enter_bracket
- _mock_resp
- test_502_ui_state_delta.py
- .run_digest_sync
- _referenced_classes
- test_article_real_streamed_progress_and_viewmodel_delta
- test_319_src_ai_gone.py
- test_bootstrap_hydrates_fresh_sqlite_candles
- test_phase2g_graphics.py
- test_snapshot_counters_37.py
- test_321_auto_redeploy.py
- scheduleProcessToastQueue
- test_engine_seed_fetch_failure_stays_neutral
- test_orb_day_rollover.py
- MultiTimeframeEngine
- cursors/index.tsx
- test_gateway_item8.py
- test_competitors.py
- fix_item5_patch.py
- Choreography
- smoke_external.py

## God Nodes (most connected - your core abstractions)
1. `LiveArenaEngine` - 222 edges
2. `OrderSide` - 174 edges
3. `GatewaySupervisor` - 113 edges
4. `BrokerSim` - 112 edges
5. `OmniRouteClient` - 108 edges
6. `Portfolio` - 102 edges
7. `OrderTicket` - 102 edges
8. `MacroCommander` - 88 edges
9. `OrderType` - 83 edges
10. `_ArenaBridgeApi` - 77 edges

## Surprising Connections (you probably didn't know these)
- `Architectural Highlights` --references--> `Portfolio`  [INFERRED]
  README.md → src/arena/portfolio.py
- `Architectural Highlights` --references--> `LiveArenaEngine`  [INFERRED]
  README.md → src/data/live_engine.py
- `Architectural Highlights` --references--> `BrokerSim`  [INFERRED]
  README.md → src/arena/broker_sim.py
- `test_dashboard_init_passes_configured_port_to_supervisor()` --uses--> `ArenaDashboard`  [INFERRED]
  tests/test_item10_packaging.py → src/gui/dashboard.py
- `test_omniroute_eta_message_formatting()` --uses--> `GatewaySupervisor`  [INFERRED]
  tests/test_gateway_install_progress_cancel.py → src/intelligence/gateway_supervisor.py

## Import Cycles
- None detected.

## Communities (125 total, 36 thin omitted)

### Community 0 - "test_phase2_omniroute_client.py"
Cohesion: 0.09
Nodes (24): compute_backoff(), extract_json(), _mock_429_session(), _mock_resp(), test_chat_json_400_response_format_rejection_is_not_quota(), _run(), test_chat_json_all_retries_429_returns_none(), _run() (+16 more)

### Community 1 - "json"
Cohesion: 0.53
Nodes (4): _commander_with_expanded_events(), test_article_lock_map_stays_bounded(), test_on_demand_article_is_intact_after_the_snapshot(), test_snapshot_carries_no_article_bodies()

### Community 2 - "test_update_checker.py"
Cohesion: 0.08
Nodes (22): _check(), check_for_updates(), compare_versions(), get_manifest_url(), _is_date_version(), test_track_c_update_checker_rejects_non_https_and_clears_download_url_when_up_to_date(), _mock_response(), test_check_failed_on_bad_manifest() (+14 more)

### Community 3 - "test_v200_fixes.py"
Cohesion: 0.06
Nodes (32): Architectural Highlights, GeneticEvolver, AggressiveCompetitor, CompetitorGenome, ConservativeCompetitor, ORBCompetitor, SessionMeanPullbackCompetitor, TrailingGuardCompetitor (+24 more)

### Community 6 - "CandleBar"
Cohesion: 0.07
Nodes (26): check_and_ensure_environment(), main(), CompetitorStats, CandleBar, TimeMachineArena, _bar(), _choppy_bars(), test_efficiency_ratio_unit() (+18 more)

### Community 7 - "logging"
Cohesion: 0.12
Nodes (10): configure_logging(), get_log_dir(), _SafeRotatingFileHandler, _flush_file_handlers(), _remove_test_handlers(), test_configure_logging_never_raises_on_unwritable_dir(), test_get_log_dir_resolution(), test_stream_handler_present_when_stdout_exists() (+2 more)

### Community 8 - "test_item10_packaging.py"
Cohesion: 0.08
Nodes (15): _FakeNpmProc, _FakeNpmProcFail, _FakeURLDownload, _make_bridge(), _make_node_zip_bytes(), _node_supervisor(), test_admin_password_required_before_onboarding(), test_console_url_follows_gateway_port() (+7 more)

### Community 9 - "CompetitorGenome"
Cohesion: 0.09
Nodes (31): BrokerSim, OrderTicket, test_broker_sim_bracket_stop_loss_trigger(), test_broker_sim_leverage_liquidation_long_crash(), test_broker_sim_leverage_liquidation_protection(), test_broker_sim_multi_portfolio_simultaneous_execution(), test_broker_sim_position_cap_enforcement(), test_depth_impact_pool_depth_is_disclosed() (+23 more)

### Community 10 - "Leaderboard"
Cohesion: 0.08
Nodes (20): Leaderboard, _counting_periods(), _portfolio_with_history(), test_fill_invalidates_cache(), test_metrics_cached_across_ticks_with_no_fills(), test_replace_equity_history_invalidates_cache(), test_reset_invalidates_cache(), test_risk_free_rate_change_invalidates_cache() (+12 more)

### Community 11 - "test_ui_contract.py"
Cohesion: 0.15
Nodes (15): _badge_cls_producer_values(), _bridge_class_node(), _bridge_methods(), _bridge_obj_calls(), _bridge_self_calls(), _defined_classes(), _html_ids(), _js_defined_functions() (+7 more)

### Community 12 - "ArenaDashboard"
Cohesion: 0.07
Nodes (18): ArenaDashboard, _activate_foreground_startup(), _on_window_closing(), _on_window_shown(), _delayed_activation(), __getattr__(), test_track_c_save_and_launch_aborts_if_password_db_sync_fails(), test_track_d_dashboard_save_launch_aborts_on_key_sync_failure() (+10 more)

### Community 14 - "OrderSide"
Cohesion: 0.07
Nodes (37): __getattr__(), ExecutionReason, OrderSide, OrderStatus, OrderType, PositionSide, BaseCompetitor, _open_long() (+29 more)

### Community 15 - "IntelligenceHarvester"
Cohesion: 0.10
Nodes (12): IntelligenceHarvester, test_process_batch_carries_tier_thread_and_consensus(), _run(), test_process_batch_fallback_consensus_from_score(), _run(), _fallback_structured(), _run(), test_keyword_word_boundaries_no_substring_false_positives() (+4 more)

### Community 17 - "ViewModelPublisher"
Cohesion: 0.19
Nodes (4): _empty_view_model(), ViewModelPublisher, test_track_d_view_model_publisher_excludes_fills_and_detects_is_live_change(), test_view_model_delta_omits_unchanged_history_and_intel_events_equivalently()

### Community 18 - "OmniRouteClient"
Cohesion: 0.04
Nodes (28): _shutting_down(), OmniRouteClient, _mock_resp(), _mock_session(), test_chat_json_402_records_quota_failure(), _run(), test_chat_json_connection_refused_records_connection(), _run() (+20 more)

### Community 19 - "Portfolio"
Cohesion: 0.08
Nodes (28): FillEvent, Portfolio, RiskGuard, _breakeven_portfolio(), test_breakeven_count_resets(), test_track_a_portfolio_cross_gen_leverage_partial_close_conserves_equity(), test_track_a_portfolio_failed_fill_does_not_corrupt_fees(), test_track_b_non_integer_cadence_advances_slots() (+20 more)

### Community 21 - "MacroCommander"
Cohesion: 0.07
Nodes (23): StructuredEvent, _event_age_min(), MacroCommander, MacroRegimeState, test_synthesize_plumbs_raw_snippet(), test_forum_batch_scored_without_llm_when_offline(), test_sync_status_failed_when_gateway_down(), _mock_commander() (+15 more)

### Community 22 - "_make_supervisor"
Cohesion: 0.06
Nodes (25): _fake_node_zip_bytes(), _FakeDownloadResp, _make_supervisor(), _setup_npm_only_env(), _SlowResp, test_bridge_cancel_and_status_shape(), test_cancel_during_node_download(), test_cancel_during_npm_install_removes_partial_package() (+17 more)

### Community 23 - "._get_daemon_command"
Cohesion: 0.16
Nodes (3): test_daemon_command_falls_back_to_global(), test_daemon_command_prefers_runtime_install(), test_gateway_cli_command_never_falls_back_to_npx()

### Community 25 - "syncAppShellInert"
Cohesion: 0.13
Nodes (21): blurActiveFocus(), closeInstallCancelConfirm(), closeSetupWizardModal(), closeShutdownModal(), closeWizardCloseConfirm(), confirmCancelInstallAndClose(), confirmCloseWizardWithoutSaving(), handleInstallCancelOverlayClick() (+13 more)

### Community 26 - "test_phase3_ingestion.py"
Cohesion: 0.10
Nodes (18): parse_polymarket_events(), parse_reddit_posts(), parse_rss_atom(), test_feed_numeric_parsing_never_raises(), _fake_registry_response(), _new_harvester(), _registry_get_ok(), test_feed_registry_completeness_r3() (+10 more)

### Community 27 - "soak_engine.py"
Cohesion: 0.05
Nodes (36): ETHFeed, isolate_arena_memory(), _git(), test_system_config_is_ignored_by_git(), test_system_config_is_untracked_but_present_on_disk(), _counting_read_text(), _manager(), test_content_change_is_visible_after_rewrite() (+28 more)

### Community 28 - "Stage"
Cohesion: 0.06
Nodes (36): animCandles, changeEvolveInterval(), chartBeacons, closeResetModal(), confirmResetArena(), copyOmniPassword(), currentSplashSteps, EVOLVE_INTERVAL_OPTIONS (+28 more)

### Community 29 - "re"
Cohesion: 0.22
Nodes (10): _compile_word_group(), _compiled_word_re(), _contains_word(), _css(), _css_block(), test_article_renders_with_fade_in(), test_chevron_and_accordion_spring(), test_get_event_article_removed_from_dead_list() (+2 more)

### Community 30 - "Any"
Cohesion: 0.08
Nodes (10): build_event_article_prompts(), _dedup_tickers(), _runner(), _on_progress(), _event_dict(), test_prompt_includes_raw_snippet(), test_prompt_without_snippet_omits_line(), test_telemetry_strips_raw_snippet() (+2 more)

### Community 31 - "test_track_c_gateway_npm_strips_secrets_and_no_blind_retry"
Cohesion: 0.13
Nodes (5): test_track_c_gateway_npm_strips_secrets_and_no_blind_retry(), _fake_popen(), _FakeProc, test_gateway_env_sets_server_host_and_strips_provider_keys_when_env_exists(), _fake_popen()

### Community 32 - "time"
Cohesion: 0.08
Nodes (7): _build_engine_view_model_impl(), _parse_iso_ts(), _looks_like_format_rejection(), test_manual_evolve_does_not_block_bridge(), SlowFakeWS, test_ws_start_stop_delivers_then_stops(), _ticker_msg()

### Community 33 - "test_performance_and_optimizations.py"
Cohesion: 0.11
Nodes (14): _build_html_template(), _get_assets_dir(), _load_asset(), test_launchers_and_shortcut_integrity(), test_macro_veto_intent_preserved_in_live_evaluation(), test_phase4_mtf_trend_confluence_gatekeeper(), test_portfolio_no_duplicate_apply_fill_returns(), test_splash_logo_concentric_alignment_and_svg_zap() (+6 more)

### Community 34 - "test_gui_item7.py"
Cohesion: 0.17
Nodes (10): _get_native_hwnd(), build_engine_view_model(), _rankings(), test_run_loads_config_once_and_uses_window_title_constant(), test_shutdown_closes_window_on_calling_thread(), test_view_model_does_not_fabricate_take_profit(), test_view_model_reports_unknown_mc_and_quota(), test_view_model_short_unrealized_pnl_pct() (+2 more)

### Community 35 - "StreamingCryptoFeed"
Cohesion: 0.20
Nodes (3): StreamingCryptoFeed, test_phase1_websocket_feed_parsing_and_fast_path_fallback(), test_parse_binance_ticker_rejects_garbage()

### Community 36 - "ConfigManager"
Cohesion: 0.06
Nodes (14): ConfigManager, format_omni_env_value(), parse_omni_env_line(), test_track_c_config_manager_refuses_to_wipe_unreadable_env(), test_v24_track_c_env_roundtrip_and_no_initial_password_in_environ(), test_gateway_auto_spawn_option_removed(), test_bridge_stepwise_simulation_erroneous_then_valid(), test_config_manager_atomic_recovery_from_corruption() (+6 more)

### Community 37 - "test_gateway_autolaunch_mandatory.py"
Cohesion: 0.11
Nodes (9): _assets_root(), _FakeEvent, _FakeWebview, _FakeWindow, _make_bridge(), test_run_spawns_despite_stored_false(), test_save_and_launch_spawns_despite_stored_false(), test_setup_status_has_no_autolaunch_option() (+1 more)

### Community 38 - "test_live_engine.py"
Cohesion: 0.06
Nodes (34): _drive(), _drive_fixed(), _fixture_bars(), _quote(), _startup_engine_long(), test_anti_churn_cooldown_prevents_same_timestamp_reentry(), test_auto_evolve_fires_on_closed_trades(), _round_trips() (+26 more)

### Community 40 - ".omniroute_installed"
Cohesion: 0.22
Nodes (3): test_gateway_unavailable_reason_no_node(), test_gateway_unavailable_reason_node_but_no_omniroute(), test_start_runtime_install_does_not_start_twice()

### Community 41 - "test_debug_report_fixes.py"
Cohesion: 0.07
Nodes (14): _fixture_bars(), _raise_no_network(), test_cooperative_stop_event(), test_full_restore_bootstrap_start_integration(), test_get_ui_state_mutation_isolation(), test_offline_start_does_not_execute_stale_candles(), test_pause_feed_updates_ui_snapshot_immediately(), test_session_save_and_restore_with_locked_margin() (+6 more)

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
Cohesion: 0.17
Nodes (8): _run_feed(), test_ws_clean_server_close_counts_as_reconnect(), test_ws_connect_and_stream_delivers_quotes(), _fake_connect(), _on_quote(), test_ws_reconnect_backoff_on_disconnect(), _fake_connect(), _fake_sleep()

### Community 48 - "._run_runtime_install"
Cohesion: 0.09
Nodes (3): _default_daemon_log_path(), _default_install_log_path(), _InstallCancelledError

### Community 50 - "DeduplicationBuffer"
Cohesion: 0.16
Nodes (7): _clean_html_text(), _dedup_normalize_title(), DeduplicationBuffer, _retry_window_seconds(), test_v24_track_c_omniroute_extract_json_retry_hint_dedup_and_https_redirect(), test_deduplication_buffer(), test_ingestion_clean_html_strips_script_style_and_dedup_forget()

### Community 51 - "test_gateway_diagnosis.py"
Cohesion: 0.05
Nodes (49): classify_llm_error(), _error_body_text(), _walk(), _extract_error_provider(), _client(), _css(), _FakeEvent, _FakeWebview (+41 more)

### Community 52 - "test_phase1_debug_sweep.py"
Cohesion: 0.08
Nodes (13): _StubGateway, test_four_threads_expand_concurrently_without_closing_each_other(), _one(), _worker(), _OKHandler, _quote(), _safe_refresh(), test_deserialize_ticket_garbage_numbers_return_none() (+5 more)

### Community 53 - "test_llm_json_mode_fallback.py"
Cohesion: 0.18
Nodes (7): _client_with(), _CM, _FakeSession, _Resp, test_generic_400_does_not_trigger_the_format_retry(), test_rejected_format_is_remembered_for_later_calls(), test_rejected_response_format_retries_without_it_and_parses()

### Community 54 - "test_v250_fixes.py"
Cohesion: 0.09
Nodes (7): test_v24_track_c_gemini_header_and_save_gateway_no_split_brain(), test_gateway_supervisor_http_responses(), test_gateway_supervisor_key_validation_defensive(), test_gateway_supervisor_nvidia_endpoint(), test_ui_assets_art_jargon_and_cjk_cleanliness(), test_key_rate_limit_429_is_not_verified(), test_gateway_test_single_key_non_ascii_and_gemini_400()

### Community 55 - "ArenaStorage"
Cohesion: 0.05
Nodes (40): ArenaStorage, _retry_on_db_error(), wrapper(), _sanitize_json_value(), _records(), test_save_history_closes_storage_it_creates(), close(), __init__() (+32 more)

### Community 56 - "test_intel_stream_redesign.py"
Cohesion: 0.21
Nodes (16): _fn_body(), _html(), _js(), test_article_failure_shows_reason_not_summary(), test_article_lazy_once_and_cached(), test_article_loading_shows_determinate_stage_progress_bar(), test_article_render_is_not_rewritten_every_tick(), test_articles_preload_while_collapsed() (+8 more)

### Community 57 - "MonteCarloOddsEvaluator"
Cohesion: 0.15
Nodes (9): MonteCarloBracketOdds, MonteCarloOddsEvaluator, test_track_b_timemachine_rejects_wrong_side_tp(), test_v24_track_b_timemachine_single_sim_and_flat_empirical_candles(), test_startup_ev_gate_enforcement(), test_monte_carlo_ev_gate_odds_evaluation(), test_monte_carlo_without_numpy_reports_unknown(), test_uncapped_runner_r_assumption_is_labelled() (+1 more)

### Community 58 - "test_forum_collector.py"
Cohesion: 0.15
Nodes (12): parse_stocktwits_stream(), _registry_mock_get(), _stream_json(), test_fetch_from_registry_dispatches_by_type_and_skips_forum(), mock_get(), test_forum_collector_stocktwits_flow_and_cadence(), mock_get(), test_parse_stocktwits_stream_builds_one_forum_event() (+4 more)

### Community 59 - "QuoteManager"
Cohesion: 0.19
Nodes (3): QuoteManager, test_dead_cascade_state_is_gone(), test_ws_quote_path_still_works()

### Community 60 - "InterruptDebouncer"
Cohesion: 0.20
Nodes (3): InterruptDebouncer, test_stage2_interrupt_debouncing_r4(), _run()

### Community 61 - "renderIntelHub"
Cohesion: 0.16
Nodes (19): buildIntelEventCard(), cleanIntelSummary(), formatIntelEventTime(), hashTickerName(), intelArticleBodyEl(), intelEventKey(), preloadIntelArticles(), pumpIntelArticlePreload() (+11 more)

### Community 62 - "_FakeCM"
Cohesion: 0.07
Nodes (11): test_track_c_omniroute_max_concurrent_1_repair_no_deadlock(), post(), _FakeCM, _FakeForum, _FakeHarvester, _FakeResp, _FakeSession, _make_commander() (+3 more)

### Community 63 - "threading"
Cohesion: 0.20
Nodes (5): _drive(), _make_engine(), test_concurrent_publish_harvests_each_fill_once(), test_publish_state_snapshot_holds_engine_lock(), publish_many()

### Community 64 - "test_intel_hub_layout.py"
Cohesion: 0.25
Nodes (12): _commander(), _css(), _js(), _mock_pipeline(), _rule(), _structured(), test_stream_loading_block_is_centered_with_meter(), test_sync_status_failed_when_feeds_down() (+4 more)

### Community 65 - "renderAll"
Cohesion: 0.19
Nodes (20): createPositionClosedToastElement(), createPositionToastElement(), escapeHtml(), fmtPct(), fmtSignedUsd(), fmtTimeSec(), fmtUsd(), hexToRgba() (+12 more)

### Community 66 - "test_item12a_omniroute.py"
Cohesion: 0.23
Nodes (7): _now_iso(), _offline_commander(), _strong_bearish_events(), test_empty_digest_expires_stale_fallback(), test_fallback_clears_when_llm_recovers(), test_fallback_regime_is_marked_and_expires(), test_regime_state_dict_exposes_fallback()

### Community 69 - "LiveQuote"
Cohesion: 0.18
Nodes (3): LiveQuote, QuoteFeedsMixin, test_track_b_quote_feeds_rejects_non_positive_and_non_finite()

### Community 70 - "controls/index.ts"
Cohesion: 0.21
Nodes (10): _broker(), _commander(), test_backtest_default_sizing_is_one(), test_compute_r_multiple_qty_scales_budget_and_clamps(), test_evaluate_signal_sizing_shrinks_qty_not_sl(), test_no_confidence_means_no_sizing_effect(), test_per_strategy_sensitivity_scales_the_deviation(), test_sizing_formula_exact_values() (+2 more)

### Community 71 - "main"
Cohesion: 0.16
Nodes (11): closing_fills_since(), db_stats(), genome_valid(), main(), _sample(), _parse_args(), _PMC, rss_mb() (+3 more)

### Community 72 - "Decimal"
Cohesion: 0.11
Nodes (7): _fixture_bars(), _keyframes_block(), test_splash_overlay_is_lightened_not_removed(), _fixture_bars(), _fixture_bars(), test_leaderboard_ranked_strictly_by_total_equity(), _quote()

### Community 73 - "RawEvent"
Cohesion: 0.20
Nodes (5): ForumCollector, RawEvent, test_forum_collector_fast_test_short_circuits(), test_forum_collector_hourly_cap(), test_dedup_hits_counted_not_token_estimate()

### Community 75 - "saveAndLaunchGateway"
Cohesion: 0.20
Nodes (17): applyGatewayAvailability(), clearSplashTimers(), confirmShutdown(), ensureRuntimeInstallPoll(), initAppBoot(), installGatewayRuntime(), openSetupWizardModal(), refreshGatewayAvailability() (+9 more)

### Community 76 - "test_ui_feedback.py"
Cohesion: 0.23
Nodes (7): _copy_text_to_clipboard_windows(), _bridge_with_env(), test_copy_password_copies_value_but_never_returns_it(), test_copy_password_helper_failure(), test_copy_password_not_configured(), test_copy_text_to_clipboard_windows_non_windows(), test_copy_text_to_clipboard_windows_roundtrip()

### Community 77 - "LiveArenaEngine"
Cohesion: 0.07
Nodes (24): LiveArenaEngine, test_bootstrap_resets_live_trading_state_when_orders_disabled(), test_signal_exit_fast_path_closes_under_hold_cash(), test_v24_track_b_live_engine_custom_gateway_url_and_reset_broker_binding(), test_v24_track_d_view_model_sanitizes_mc_stats_and_dev_bat_structure(), test_stale_engine_save_session_state_refused(), test_close_ticket_bypasses_veto_and_gates_under_hold_cash(), test_bootstrap_spawns_mtf_seed_thread_instead_of_blocking() (+16 more)

### Community 78 - "._live_loop"
Cohesion: 0.10
Nodes (5): _on_done(), test_evolve_now_with_fewer_than_two_rankings_does_not_raise(), test_stale_engine_evolve_now_refused(), test_stale_engine_harvest_fills_refused(), test_stale_engine_state_publish_skipped()

### Community 79 - "soak_engine.py"
Cohesion: 0.22
Nodes (3): do_slice(), make_quote(), synth_bars()

### Community 81 - "live_engine.py"
Cohesion: 0.16
Nodes (4): parse_symbol_pairs(), efficiency_ratio(), _safe_float(), test_last_records_class_default_present()

### Community 82 - "test_v287_render_guards.py"
Cohesion: 0.40
Nodes (7): _fn_body(), _js(), test_hub_header_writes_guarded(), test_intel_card_element_refs_cached(), test_macro_ribbon_writes_guarded(), test_spotlight_vars_written_once_per_frame(), test_strat_color_and_gen_label_writes_guarded()

### Community 83 - ".sync_admin_password"
Cohesion: 0.09
Nodes (5): GatewaySupervisor, test_track_c_gateway_sync_admin_password_fresh_and_existing_db(), test_watchdog_backoff_schedule(), test_daemon_log_rotates_over_5mb(), test_runtime_install_status_defaults_idle()

### Community 84 - "test_card_reorder_anim.py"
Cohesion: 0.35
Nodes (10): _css(), _js(), _reorder_block(), test_cards_are_stable_nodes_never_recreated_on_reorder(), test_flip_cleanup_clears_class_and_transform(), test_flip_inverts_with_translate_and_plays_via_class(), test_flip_records_first_rects_before_moving_nodes(), test_flip_runs_only_when_order_changes() (+2 more)

### Community 88 - "._try_enter_bracket"
Cohesion: 0.23
Nodes (17): _dead_gateway_commander(), _mock_pipeline(), _structured(), test_sync_status_done_when_dead_gateway_still_yields_fallback_digest(), test_sync_status_failed_when_gateway_dead_and_nothing_produced(), _ev(), _now_iso(), _offline_commander() (+9 more)

### Community 89 - "_mock_resp"
Cohesion: 0.31
Nodes (10): _coinbase_stats_payload(), _coinbase_ticker_payload(), _kraken_payload(), _mock_resp(), test_binance_quote_success_parses_all_fields(), test_coinbase_quote_success_parses(), test_kraken_quote_success_parses(), dispatch() (+2 more)

### Community 90 - "test_502_ui_state_delta.py"
Cohesion: 0.39
Nodes (5): _engine(), _snapshot(), test_deepcopy_never_receives_heavy_arrays_on_unchanged_poll(), test_delta_is_still_a_defensive_copy(), test_delta_output_identical_to_old_path()

### Community 92 - "_referenced_classes"
Cohesion: 0.33
Nodes (3): _class_value_tokens(), _referenced_classes(), _string_literals()

### Community 95 - "test_bootstrap_hydrates_fresh_sqlite_candles"
Cohesion: 0.22
Nodes (3): _cache_rows(), test_bootstrap_hydrates_fresh_sqlite_candles(), test_bootstrap_rejects_stale_sqlite_candles()

### Community 96 - "test_phase2g_graphics.py"
Cohesion: 0.31
Nodes (4): _js(), test_p2g_chart_loop_capped_at_60fps(), test_p2g_hidden_view_stops_chart_loop(), test_p2g_no_temporary_probe_left_in_shipped_assets()

### Community 99 - "test_321_auto_redeploy.py"
Cohesion: 0.39
Nodes (5): _flat_engine(), test_no_redeploy_when_any_position_open(), test_redeploy_logs_once_per_flat_episode(), test_switch_off_does_not_redeploy(), test_switch_on_default_redeploys_when_flat()

### Community 100 - "scheduleProcessToastQueue"
Cohesion: 0.67
Nodes (4): attachToastInteractions(), dismissToast(), processToastQueue(), scheduleProcessToastQueue()

### Community 104 - "test_orb_day_rollover.py"
Cohesion: 0.36
Nodes (5): _minute_candles(), _tape_bar(), test_backtest_orb_range_rolls_at_utc_midnight(), test_live_orb_range_is_forming_on_a_partial_new_day(), test_live_orb_range_rolls_at_utc_midnight()

### Community 107 - "MultiTimeframeEngine"
Cohesion: 0.18
Nodes (14): MultiTimeframeEngine, test_v24_track_b_mtf_seed_1h_merges_same_slot(), test_mtf_gate_blocks_counter_trend_entries(), _buckets(), _hourly_bars(), _minute_bars(), test_engine_seed_rejects_stale_bars(), test_engine_seed_wires_bias_and_survives_live_bar() (+6 more)

### Community 108 - "cursors/index.tsx"
Cohesion: 0.23
Nodes (12): drawPriceChart(), invalidateCanvasSizeCache(), locateMouseAndRefreshChart(), setIntelSortMode(), setLgWallpaper(), setRightTab(), setScaleMode(), setupChartInteraction() (+4 more)

### Community 112 - "test_gateway_item8.py"
Cohesion: 0.08
Nodes (9): _FakeEvent, _FakeHTTPResponse, _FakeWebview, _FakeWindow, test_daemon_log_default_path_is_project_logs(), test_existing_daemon_check_uses_2s_probe(), test_probe_health_success_failure_timeout(), test_save_and_launch_gateway_waits_30_seconds() (+1 more)

### Community 113 - "test_competitors.py"
Cohesion: 0.11
Nodes (3): _parse_pos_dec(), _open_short(), test_short_trailing_stop_ratchets_down_then_exits_at_trailed_level()

### Community 139 - "fix_item5_patch.py"
Cohesion: 0.13
Nodes (19): addChartBeacon(), checkOnboardingBoot(), enqueueToast(), ensureLiveTradingStarted(), fillRoundRect(), isSplashGateOpen(), pollBackend(), previewPositionAnimation() (+11 more)

### Community 146 - "Choreography"
Cohesion: 0.29
Nodes (6): 1. Launch Packaged Desktop Executable (`.exe`), 2. Run Self-Test Verification, 3. Run Automated Unit Test Suite (32 Tests), 4. Build Standalone Windows Executable, Quick Start Guide, TradeBot0: Multi-Agent Paper Trading & Genetic Evolution Arena (BTC/USD)

### Community 161 - "smoke_external.py"
Cohesion: 0.25
Nodes (14): check_binance_rest(), check_binance_ws(), _run(), check_ccxt_kraken(), check_coinbase_rest(), check_feed_registry(), check_kraken_rest(), check_node_head() (+6 more)

## Knowledge Gaps
- **36 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `LiveArenaEngine` connect `LiveArenaEngine` to `test_v200_fixes.py`, `CandleBar`, `CompetitorGenome`, `Leaderboard`, `ArenaDashboard`, `OrderSide`, `ViewModelPublisher`, `OmniRouteClient`, `Portfolio`, `MacroCommander`, `soak_engine.py`, `time`, `test_performance_and_optimizations.py`, `test_gui_item7.py`, `StreamingCryptoFeed`, `ConfigManager`, `test_live_engine.py`, `test_debug_report_fixes.py`, `test_live_chop_gate.py`, `LiveStrategyRunnerMixin`, `test_phase1_debug_sweep.py`, `test_v250_fixes.py`, `ArenaStorage`, `MonteCarloOddsEvaluator`, `QuoteManager`, `threading`, `._build_snapshot_locked`, `IndicatorEngineMixin`, `LiveQuote`, `controls/index.ts`, `main`, `Decimal`, `SessionCodecMixin`, `._live_loop`, `soak_engine.py`, `live_engine.py`, `_mock_resp`, `test_502_ui_state_delta.py`, `test_bootstrap_hydrates_fresh_sqlite_candles`, `.is_fresh`, `test_snapshot_counters_37.py`, `test_321_auto_redeploy.py`, `test_engine_seed_fetch_failure_stays_neutral`, `test_orb_day_rollover.py`, `MultiTimeframeEngine`?**
  _High betweenness centrality (0.138) - this node is a cross-community bridge._
- **Are the 28 inferred relationships involving `LiveArenaEngine` (e.g. with `Architectural Highlights` and `BrokerSim`) actually correct?**
  _`LiveArenaEngine` has 28 INFERRED edges - model-reasoned connections that need verification._
- **Should `test_phase2_omniroute_client.py` be split into smaller, more focused modules?**
  _Cohesion score 0.0907563025210084 - nodes in this community are weakly interconnected._
- **Why does `OmniRouteClient` connect `OmniRouteClient` to `test_phase2_omniroute_client.py`, `json`, `test_v200_fixes.py`, `test_item10_packaging.py`, `ArenaDashboard`, `IntelligenceHarvester`, `Portfolio`, `MacroCommander`, `time`, `test_performance_and_optimizations.py`, `test_gateway_diagnosis.py`, `test_phase1_debug_sweep.py`, `test_llm_json_mode_fallback.py`, `test_v250_fixes.py`, `test_forum_collector.py`, `InterruptDebouncer`, `_FakeCM`, `test_item12a_omniroute.py`, `RawEvent`, `LiveArenaEngine`, `.fetch_from_registry`, `live_engine.py`, `.run_digest_sync`, `test_article_real_streamed_progress_and_viewmodel_delta`?**
  _High betweenness centrality (0.104) - this node is a cross-community bridge._
- **Are the 104 inferred relationships involving `OrderSide` (e.g. with `main()` and `BrokerSim`) actually correct?**
  _`OrderSide` has 104 INFERRED edges - model-reasoned connections that need verification._
- **Should `test_update_checker.py` be split into smaller, more focused modules?**
  _Cohesion score 0.08478513356562137 - nodes in this community are weakly interconnected._
- **Why does `GatewaySupervisor` connect `.sync_admin_password` to `test_item10_packaging.py`, `test_ui_contract.py`, `ArenaDashboard`, `.start_daemon`, `Portfolio`, `MacroCommander`, `_make_supervisor`, `._get_daemon_command`, `test_track_c_gateway_npm_strips_secrets_and_no_blind_retry`, `test_performance_and_optimizations.py`, `test_gui_item7.py`, `ConfigManager`, `test_gateway_autolaunch_mandatory.py`, `.omniroute_installed`, `.shutdown`, `test_save_launch_progress.py`, `._run_runtime_install`, `test_gateway_diagnosis.py`, `test_phase1_debug_sweep.py`, `test_v250_fixes.py`, `test_item12a_omniroute.py`, `test_gateway_item8.py`?**
  _High betweenness centrality (0.073) - this node is a cross-community bridge._