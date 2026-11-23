# Graph Report - TradeBot0_Local  (2026-11-23)

## Corpus Check
- 134 files · ~184,347 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 11 file(s) not represented in the graph (top: (none) 4, .iss 1, .lnk 1)

## Summary
- 2834 nodes · 7955 edges · 130 communities (96 shown, 34 thin omitted)
- Extraction: 87% EXTRACTED · 13% INFERRED · 0% AMBIGUOUS · INFERRED: 1024 edges (avg confidence: 0.89)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `8dc22434`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- test_phase2_omniroute_client.py
- test_debug_optimize_regression.py
- test_update_checker.py
- test_v200_fixes.py
- CandleBar
- logging
- test_item10_packaging.py
- BrokerSim
- Leaderboard
- re
- ArenaDashboard
- live_engine.py
- IntelligenceHarvester
- OrderSide
- ViewModelPublisher
- OmniRouteClient
- FillEvent
- _ArenaBridgeApi
- MacroCommander
- test_gateway_install_progress_cancel.py
- GatewaySupervisor
- GeneticEvolver
- syncAppShellInert
- test_phase3_ingestion.py
- soak_engine.py
- Stage
- ._run_runtime_install
- Any
- test_track_c_gateway_npm_strips_secrets_and_no_blind_retry
- smoke_external.py
- test_performance_and_optimizations.py
- .get_intel_hub_telemetry
- .shutdown
- ConfigManager
- test_gateway_autolaunch_mandatory.py
- test_live_engine.py
- _SliceableDeque
- threading
- test_debug_report_fixes.py
- test_phase2_optimize.py
- test_save_launch_progress.py
- test_ai_panels_frontend.py
- test_event_article.py
- test_live_chop_gate.py
- StreamingCryptoFeed
- test_chop_gate_seed.py
- LiveStrategyRunnerMixin
- config_manager.py
- test_gateway_diagnosis.py
- test_llm_concurrent_sessions.py
- test_llm_json_mode_fallback.py
- soak_engine.py
- DeduplicationBuffer
- test_autosave_35.py
- MultiTimeframeEngine
- RawEvent
- ._run_runtime_install
- StructuredEvent
- renderIntelHub
- test_phase3_soak.py
- .omniroute_installed
- test_intel_hub_layout.py
- renderAll
- ingestion.py
- ._build_snapshot_locked
- getCommandPaletteItems
- LiveQuote
- controls/index.ts
- .total_equity
- .get_gateway_diagnosis
- ArenaStorage
- SessionCodecMixin
- saveAndLaunchGateway
- test_ui_feedback.py
- test_snapshot_counters_37.py
- ._live_loop
- test_504_omni_env_cache.py
- _mock_resp
- Any
- .load_session_snapshot
- .test_single_key
- test_card_reorder_anim.py
- test_507_candle_write_on_close.py
- _open_short
- _FakeWindow
- ._try_enter_bracket
- test_digest_refresh_session.py
- test_article_real_streamed_progress_and_viewmodel_delta
- .run_digest_sync
- _error_body_text
- test_502_ui_state_delta.py
- test_track_c_omniroute_max_concurrent_1_repair_no_deadlock
- .bootstrap_intraday_session
- test_phase2g_graphics.py
- _FakeWebview
- test_orb_day_rollover.py
- test_321_auto_redeploy.py
- _FakeThread
- test_318_system_config_untracked.py
- _open_long
- conftest.py
- _OKHandler
- cursors/index.tsx
- test_restore_applies_genome_leverage_to_portfolio
- test_stale_engine_save_session_state_refused
- .compute_r_multiple_qty
- test_gateway_item8.py
- closeResetModal
- isReducedMotionPreferred
- .stop
- fix_item5_patch.py
- Choreography

## God Nodes (most connected - your core abstractions)
1. `LiveArenaEngine` - 222 edges
2. `OrderSide` - 174 edges
3. `GatewaySupervisor` - 113 edges
4. `BrokerSim` - 112 edges
5. `OmniRouteClient` - 106 edges
6. `OrderTicket` - 102 edges
7. `Portfolio` - 102 edges
8. `MacroCommander` - 92 edges
9. `OrderType` - 83 edges
10. `_ArenaBridgeApi` - 77 edges

## Surprising Connections (you probably didn't know these)
- `Architectural Highlights` --references--> `GeneticEvolver`  [INFERRED]
  README.md → src/arena/evolution.py
- `Architectural Highlights` --references--> `CompetitorGenome`  [INFERRED]
  README.md → src/competitors/base.py
- `Architectural Highlights` --references--> `LiveArenaEngine`  [INFERRED]
  README.md → src/data/live_engine.py
- `test_dashboard_init_passes_configured_port_to_supervisor()` --uses--> `ArenaDashboard`  [INFERRED]
  tests/test_item10_packaging.py → src/gui/dashboard.py
- `test_omniroute_eta_message_formatting()` --uses--> `GatewaySupervisor`  [INFERRED]
  tests/test_gateway_install_progress_cancel.py → src/intelligence/gateway_supervisor.py

## Import Cycles
- None detected.

## Communities (130 total, 34 thin omitted)

### Community 0 - "test_phase2_omniroute_client.py"
Cohesion: 0.09
Nodes (24): compute_backoff(), extract_json(), _mock_429_session(), _mock_resp(), test_chat_json_400_response_format_rejection_is_not_quota(), _run(), test_chat_json_all_retries_429_returns_none(), _run() (+16 more)

### Community 1 - "test_debug_optimize_regression.py"
Cohesion: 0.12
Nodes (7): _symbols_from_registry(), test_track_a_portfolio_cross_gen_leverage_partial_close_conserves_equity(), test_track_a_portfolio_failed_fill_does_not_corrupt_fees(), test_track_b_non_integer_cadence_advances_slots(), test_track_b_quote_feeds_rejects_non_positive_and_non_finite(), test_track_c_forum_collector_parses_dot_x_symbols(), test_track_d_frontend_contracts_css_html_js()

### Community 2 - "test_update_checker.py"
Cohesion: 0.08
Nodes (23): _check(), check_for_updates(), compare_versions(), get_manifest_url(), _is_date_version(), test_track_c_update_checker_rejects_non_https_and_clears_download_url_when_up_to_date(), _mock_response(), test_bridge_check_for_updates_not_configured() (+15 more)

### Community 3 - "test_v200_fixes.py"
Cohesion: 0.07
Nodes (29): AggressiveCompetitor, CompetitorGenome, ConservativeCompetitor, ORBCompetitor, SessionMeanPullbackCompetitor, TrailingGuardCompetitor, _r_multiple(), test_all_four_competitors_initialization_and_first_buy() (+21 more)

### Community 6 - "CandleBar"
Cohesion: 0.06
Nodes (25): CompetitorStats, CandleBar, MonteCarloBracketOdds, MonteCarloOddsEvaluator, TimeMachineArena, test_backtest_slippage_uses_measured_atr(), _bars(), test_track_b_timemachine_rejects_wrong_side_tp() (+17 more)

### Community 7 - "logging"
Cohesion: 0.12
Nodes (10): configure_logging(), get_log_dir(), _SafeRotatingFileHandler, _flush_file_handlers(), _remove_test_handlers(), test_configure_logging_never_raises_on_unwritable_dir(), test_get_log_dir_resolution(), test_stream_handler_present_when_stdout_exists() (+2 more)

### Community 8 - "test_item10_packaging.py"
Cohesion: 0.08
Nodes (15): _FakeNpmProc, _FakeNpmProcFail, _FakeURLDownload, _make_bridge(), _make_node_zip_bytes(), _node_supervisor(), test_admin_password_required_before_onboarding(), test_console_url_follows_gateway_port() (+7 more)

### Community 9 - "BrokerSim"
Cohesion: 0.08
Nodes (38): Architectural Highlights, BrokerSim, OrderTicket, Portfolio, _open_long(), test_apply_fill_value_error_does_not_kill_cadence(), _boom(), test_submit_order_returns_none_when_apply_fill_fails() (+30 more)

### Community 10 - "Leaderboard"
Cohesion: 0.08
Nodes (22): Leaderboard, _counting_periods(), _portfolio_with_history(), test_fill_invalidates_cache(), test_metrics_cached_across_ticks_with_no_fills(), test_replace_equity_history_invalidates_cache(), test_reset_invalidates_cache(), test_risk_free_rate_change_invalidates_cache() (+14 more)

### Community 11 - "re"
Cohesion: 0.06
Nodes (51): _scanned_files(), test_no_src_ai_reference_remains(), _css(), _css_block(), _fn_body(), _html(), _js(), test_article_failure_shows_reason_not_summary() (+43 more)

### Community 12 - "ArenaDashboard"
Cohesion: 0.08
Nodes (18): ArenaDashboard, __getattr__(), test_track_c_save_and_launch_aborts_if_password_db_sync_fails(), test_track_d_dashboard_save_launch_aborts_on_key_sync_failure(), test_track_d_reset_engine_preserves_fills_after_bootstrap_completes(), test_v24_track_b_live_engine_custom_gateway_url_and_reset_broker_binding(), test_setup_status_has_no_gateway_auto_spawn_option(), test_reset_engine_preserves_pause_generation_and_fills() (+10 more)

### Community 14 - "live_engine.py"
Cohesion: 0.06
Nodes (17): parse_symbol_pairs(), _parse_feed_ts(), _keyframes_block(), test_splash_overlay_is_lightened_not_removed(), test_manual_evolve_does_not_block_bridge(), _quote(), test_generate_fallback_bars_deleted(), test_is_quote_fresh() (+9 more)

### Community 15 - "IntelligenceHarvester"
Cohesion: 0.07
Nodes (19): IntelligenceHarvester, _rank_fresh_events(), RawEvent, test_fetch_from_registry_dispatches_by_type_and_skips_forum(), test_fetch_live_feeds_still_returns_test_fixtures(), test_process_batch_carries_tier_thread_and_consensus(), _run(), test_process_batch_fallback_consensus_from_score() (+11 more)

### Community 16 - "OrderSide"
Cohesion: 0.11
Nodes (28): __getattr__(), ExecutionReason, OrderSide, OrderStatus, OrderType, PositionSide, RiskGuard, BaseCompetitor (+20 more)

### Community 17 - "ViewModelPublisher"
Cohesion: 0.15
Nodes (5): _build_engine_view_model_impl(), _empty_view_model(), ViewModelPublisher, test_track_d_view_model_publisher_excludes_fills_and_detects_is_live_change(), test_view_model_delta_omits_unchanged_history_and_intel_events_equivalently()

### Community 18 - "OmniRouteClient"
Cohesion: 0.06
Nodes (18): _looks_like_format_rejection(), OmniRouteClient, test_chat_json_connection_refused_records_connection(), _run(), test_success_counted_only_after_parseable_json(), _run(), _mock_200_session(), test_key_present_sends_authorization() (+10 more)

### Community 19 - "FillEvent"
Cohesion: 0.19
Nodes (11): FillEvent, test_v24_track_a_portfolio_apply_fill_upfront_quantization(), _assert_equity_conservation(), _fill(), test_add_to_short_recomputes_avg_entry_and_margin(), test_equity_conservation_across_all_fill_cases(), test_partial_close_releases_margin_proportionally(), test_portfolio_breakeven_trade_does_not_count_as_loss() (+3 more)

### Community 21 - "MacroCommander"
Cohesion: 0.06
Nodes (22): _event_age_min(), MacroCommander, _shutting_down(), _safe_float(), test_synthesize_plumbs_raw_snippet(), test_sync_status_failed_when_gateway_down(), test_fallback_thresholds_do_not_veto_on_single_word(), _run() (+14 more)

### Community 22 - "test_gateway_install_progress_cancel.py"
Cohesion: 0.06
Nodes (25): _fake_node_zip_bytes(), _FakeDownloadResp, _make_supervisor(), _setup_npm_only_env(), _SlowResp, test_bridge_cancel_and_status_shape(), test_cancel_during_node_download(), test_cancel_during_npm_install_removes_partial_package() (+17 more)

### Community 23 - "GatewaySupervisor"
Cohesion: 0.12
Nodes (4): GatewaySupervisor, test_watchdog_backoff_schedule(), test_daemon_log_rotates_over_5mb(), test_gateway_supervisor_port_and_health_conflict()

### Community 24 - "GeneticEvolver"
Cohesion: 0.09
Nodes (14): GeneticEvolver, test_evolve_generation_early_return_does_not_crash(), test_evolve_now_with_fewer_than_two_rankings_does_not_raise(), test_last_records_class_default_present(), _records(), test_save_history_closes_storage_it_creates(), close(), __init__() (+6 more)

### Community 25 - "syncAppShellInert"
Cohesion: 0.14
Nodes (20): blurActiveFocus(), closeInstallCancelConfirm(), closeSetupWizardModal(), closeWizardCloseConfirm(), confirmCancelInstallAndClose(), confirmCloseWizardWithoutSaving(), handleInstallCancelOverlayClick(), handleWizardCloseOverlayClick() (+12 more)

### Community 26 - "test_phase3_ingestion.py"
Cohesion: 0.08
Nodes (26): _first_child_text(), parse_polymarket_events(), parse_reddit_posts(), parse_rss_atom(), _mock_commander(), test_feed_numeric_parsing_never_raises(), test_keyword_word_boundaries_no_substring_false_positives(), test_no_fabricated_seed_events_and_honest_quota() (+18 more)

### Community 27 - "soak_engine.py"
Cohesion: 0.14
Nodes (12): ETHFeed, _bar(), _ccxt_ohlcv(), test_fetch_dataframe_both_sources_fail_raises(), test_fetch_dataframe_falls_back_to_ccxt_kraken(), test_fetch_historical_bars_yahoo_multiindex_columns(), test_fetch_historical_bars_yahoo_success(), test_generate_signal_real_path_setups_and_exits() (+4 more)

### Community 28 - "Stage"
Cohesion: 0.05
Nodes (45): animCandles, changeEvolveInterval(), chartBeacons, closeShutdownModal(), copyOmniPassword(), currentSplashSteps, EVOLVE_INTERVAL_OPTIONS, fillRoundRect() (+37 more)

### Community 29 - "._run_runtime_install"
Cohesion: 0.15
Nodes (4): test_track_c_gateway_sync_admin_password_fresh_and_existing_db(), test_daemon_command_falls_back_to_global(), test_daemon_command_prefers_runtime_install(), test_gateway_cli_command_never_falls_back_to_npx()

### Community 30 - "Any"
Cohesion: 0.08
Nodes (10): build_event_article_prompts(), _dedup_tickers(), _runner(), _on_progress(), _parse_event_epoch(), _event_dict(), test_prompt_includes_raw_snippet(), test_prompt_without_snippet_omits_line() (+2 more)

### Community 31 - "test_track_c_gateway_npm_strips_secrets_and_no_blind_retry"
Cohesion: 0.13
Nodes (5): test_track_c_gateway_npm_strips_secrets_and_no_blind_retry(), _fake_popen(), _FakeProc, test_gateway_env_sets_server_host_and_strips_provider_keys_when_env_exists(), _fake_popen()

### Community 32 - "smoke_external.py"
Cohesion: 0.25
Nodes (14): check_binance_rest(), check_binance_ws(), _run(), check_ccxt_kraken(), check_coinbase_rest(), check_feed_registry(), check_kraken_rest(), check_node_head() (+6 more)

### Community 33 - "test_performance_and_optimizations.py"
Cohesion: 0.06
Nodes (22): check_and_ensure_environment(), main(), _set_windows_app_user_model_id(), _apply_window_icon(), _activate_foreground_startup(), _on_window_closing(), _on_window_shown(), _delayed_activation() (+14 more)

### Community 34 - ".get_intel_hub_telemetry"
Cohesion: 0.19
Nodes (4): test_quota_pct_has_no_invented_denominator(), _run_429(), test_quota_pct_uses_user_set_budget(), test_quota_throttling_slows_digest()

### Community 35 - ".shutdown"
Cohesion: 0.12
Nodes (7): test_start_daemon_polls_health_with_2s_timeout_and_logs_to_file(), fake_probe(), test_start_daemon_spawns_and_waits_with_fake_proc(), _free_port(), test_shutdown_does_not_kill_foreign_process(), test_shutdown_kills_own_child(), test_start_daemon_concurrent_calls_spawn_once()

### Community 36 - "ConfigManager"
Cohesion: 0.06
Nodes (14): ConfigManager, format_omni_env_value(), parse_omni_env_line(), test_track_c_config_manager_refuses_to_wipe_unreadable_env(), test_v24_track_c_env_roundtrip_and_no_initial_password_in_environ(), test_gateway_auto_spawn_option_removed(), test_bridge_stepwise_simulation_erroneous_then_valid(), test_config_manager_atomic_recovery_from_corruption() (+6 more)

### Community 37 - "test_gateway_autolaunch_mandatory.py"
Cohesion: 0.11
Nodes (9): _assets_root(), _FakeEvent, _FakeWebview, _FakeWindow, _make_bridge(), test_run_spawns_despite_stored_false(), test_save_and_launch_spawns_despite_stored_false(), test_setup_status_has_no_autolaunch_option() (+1 more)

### Community 38 - "test_live_engine.py"
Cohesion: 0.07
Nodes (39): LiveArenaEngine, test_get_ui_state_mutation_isolation(), _drive(), _drive_fixed(), _fixture_bars(), _quote(), _startup_engine_long(), test_anti_churn_cooldown_prevents_same_timestamp_reentry() (+31 more)

### Community 40 - "threading"
Cohesion: 0.23
Nodes (6): _drive(), _make_engine(), _quote(), test_concurrent_publish_harvests_each_fill_once(), test_publish_state_snapshot_holds_engine_lock(), publish_many()

### Community 41 - "test_debug_report_fixes.py"
Cohesion: 0.10
Nodes (10): _fixture_bars(), _raise_no_network(), test_cooperative_stop_event(), test_full_restore_bootstrap_start_integration(), test_offline_start_does_not_execute_stale_candles(), test_session_save_and_restore_with_locked_margin(), test_slow_bootstrap_stop_safety(), test_start_live_trading_does_not_wipe_restored_positions() (+2 more)

### Community 42 - "test_phase2_optimize.py"
Cohesion: 0.19
Nodes (9): wrapper(), _candle(), test_p2_concurrent_candle_writes_all_persist(), writer(), test_p2_engine_stop_closes_storage_and_restart_still_writes(), test_p2_eth_feed_first_fetch_loads_pandas_and_behaves(), test_p2_eth_feed_import_does_not_import_pandas(), test_p2_persistent_connection_recovers_from_stale_handle() (+1 more)

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

### Community 47 - "StreamingCryptoFeed"
Cohesion: 0.05
Nodes (17): QuoteManager, StreamingCryptoFeed, test_dead_cascade_state_is_gone(), test_ws_quote_path_still_works(), FakeWS, _run_feed(), SlowFakeWS, test_parse_binance_ticker_rejects_garbage() (+9 more)

### Community 48 - "test_chop_gate_seed.py"
Cohesion: 0.29
Nodes (10): _engine(), _feed_1m(), _tape_end_anchored(), _tape_slot_aligned(), test_seed_helper_feeds_continuous_chain_and_arms_gate(), test_seed_helper_gap_truncates_to_suffix_after_gap(), test_seed_helper_malformed_row_skipped_not_fabricated(), test_seed_helper_misaligned_or_empty_seeds_nothing() (+2 more)

### Community 50 - "config_manager.py"
Cohesion: 0.08
Nodes (7): test_launchers_and_shortcut_integrity(), test_splash_logo_concentric_alignment_and_svg_zap(), test_zero_cjk_in_frontend_assets(), test_password_eye_button_and_reveal_bridge(), _assets_root(), test_skip_bridge_deleted_but_mode_readers_kept(), test_wizard_has_no_skip_button()

### Community 51 - "test_gateway_diagnosis.py"
Cohesion: 0.07
Nodes (44): classify_llm_error(), _client(), _css(), _FakeWebview, _js(), _make_dash(), _supervisor(), test_all_providers_quota_exhausted_needs_every_provider() (+36 more)

### Community 52 - "test_llm_concurrent_sessions.py"
Cohesion: 0.21
Nodes (4): _StubGateway, test_four_threads_expand_concurrently_without_closing_each_other(), _one(), _worker()

### Community 53 - "test_llm_json_mode_fallback.py"
Cohesion: 0.18
Nodes (7): _client_with(), _CM, _FakeSession, _Resp, test_generic_400_does_not_trigger_the_format_retry(), test_rejected_format_is_remembered_for_later_calls(), test_rejected_response_format_retries_without_it_and_parses()

### Community 54 - "soak_engine.py"
Cohesion: 0.12
Nodes (14): closing_fills_since(), db_stats(), do_slice(), genome_valid(), main(), _sample(), make_quote(), _parse_args() (+6 more)

### Community 55 - "DeduplicationBuffer"
Cohesion: 0.18
Nodes (6): _dedup_normalize_title(), DeduplicationBuffer, _retry_window_seconds(), test_v24_track_c_omniroute_extract_json_retry_hint_dedup_and_https_redirect(), test_deduplication_buffer(), test_ingestion_clean_html_strips_script_style_and_dedup_forget()

### Community 56 - "test_autosave_35.py"
Cohesion: 0.18
Nodes (8): _bars(), _engine(), _raise_no_network(), test_autosave_does_not_fire_when_stopped_or_superseded(), test_crash_like_stop_leaves_restorable_autosave(), test_evolution_marks_autosave_pending_and_it_fires_immediately(), test_live_loop_triggers_periodic_autosave(), test_periodic_autosave_writes_snapshot_when_interval_elapses()

### Community 57 - "MultiTimeframeEngine"
Cohesion: 0.05
Nodes (25): IndicatorEngineMixin, MultiTimeframeEngine, efficiency_ratio(), _bar(), _choppy_bars(), test_efficiency_ratio_unit(), test_gate_blocks_entries_on_choppy_tape(), test_gate_inactive_on_trend_tape() (+17 more)

### Community 58 - "RawEvent"
Cohesion: 0.11
Nodes (14): ForumCollector, parse_stocktwits_stream(), _registry_mock_get(), _stream_json(), test_forum_batch_scored_without_llm_when_offline(), mock_get(), test_forum_collector_fast_test_short_circuits(), test_forum_collector_hourly_cap() (+6 more)

### Community 59 - "._run_runtime_install"
Cohesion: 0.09
Nodes (3): _default_daemon_log_path(), _default_install_log_path(), _InstallCancelledError

### Community 60 - "StructuredEvent"
Cohesion: 0.14
Nodes (10): InterruptDebouncer, StructuredEvent, _dead_gateway_commander(), _mock_pipeline(), _structured(), test_sync_status_done_when_dead_gateway_still_yields_fallback_digest(), test_sync_status_failed_when_gateway_dead_and_nothing_produced(), test_structured_event_new_fields_default() (+2 more)

### Community 61 - "renderIntelHub"
Cohesion: 0.12
Nodes (24): buildIntelEventCard(), cleanIntelSummary(), clearIntelSearch(), formatIntelEventTime(), hashTickerName(), initIntelFilterControls(), intelArticleBodyEl(), intelEventKey() (+16 more)

### Community 62 - "test_phase3_soak.py"
Cohesion: 0.24
Nodes (5): _bootstrapped_engine(), _load_soak_helpers(), soak(), test_p3_breaker_trips_force_closes_and_resets_on_evolve(), test_p3_mini_soak_many_ticks_no_growth_blowup()

### Community 63 - ".omniroute_installed"
Cohesion: 0.15
Nodes (3): test_gateway_unavailable_reason_no_node(), test_gateway_unavailable_reason_node_but_no_omniroute(), test_start_runtime_install_does_not_start_twice()

### Community 64 - "test_intel_hub_layout.py"
Cohesion: 0.25
Nodes (12): _commander(), _css(), _js(), _mock_pipeline(), _rule(), _structured(), test_stream_loading_block_is_centered_with_meter(), test_sync_status_failed_when_feeds_down() (+4 more)

### Community 65 - "renderAll"
Cohesion: 0.16
Nodes (23): buildSparklineGeometry(), createPositionClosedToastElement(), createPositionToastElement(), createStrategyCardSkeleton(), escapeHtml(), fmtPct(), fmtSignedUsd(), fmtTimeSec() (+15 more)

### Community 66 - "ingestion.py"
Cohesion: 0.08
Nodes (18): _clean_html_text(), _compile_word_group(), _compiled_word_re(), _contains_word(), _parse_iso_ts(), MacroRegimeState, _now_iso(), _offline_commander() (+10 more)

### Community 68 - "getCommandPaletteItems"
Cohesion: 0.15
Nodes (17): applyBackdropMode(), closeCommandPalette(), cycleBackdropMode(), getCommandPaletteItems(), handleCmdPaletteOverlayClick(), initCommandPalette(), openCommandPalette(), openOmniRouteConsole() (+9 more)

### Community 69 - "LiveQuote"
Cohesion: 0.16
Nodes (3): LiveQuote, QuoteFeedsMixin, test_phase1_websocket_feed_parsing_and_fast_path_fallback()

### Community 70 - "controls/index.ts"
Cohesion: 0.19
Nodes (10): _broker(), _commander(), test_backtest_default_sizing_is_one(), test_compute_r_multiple_qty_scales_budget_and_clamps(), test_evaluate_signal_sizing_shrinks_qty_not_sl(), test_no_confidence_means_no_sizing_effect(), test_per_strategy_sensitivity_scales_the_deviation(), test_sizing_formula_exact_values() (+2 more)

### Community 71 - ".total_equity"
Cohesion: 0.31
Nodes (3): test_portfolio_reset_clears_all_metrics(), test_portfolio_buy_and_sell_accounting(), test_portfolio_initialization()

### Community 72 - ".get_gateway_diagnosis"
Cohesion: 0.20
Nodes (6): _mock_resp(), _mock_session(), test_chat_json_402_records_quota_failure(), _run(), test_chat_json_transient_429_then_200_clears_quota_records(), _run()

### Community 73 - "ArenaStorage"
Cohesion: 0.20
Nodes (5): ArenaStorage, _retry_on_db_error(), test_track_b_persistence_batch_fills_and_prune_candles(), test_phase2_sqlite_wal_persistence_and_cold_start_hydration(), test_p2_persistent_connection_reused_and_candle_persists_across_close()

### Community 75 - "saveAndLaunchGateway"
Cohesion: 0.18
Nodes (18): applyGatewayAvailability(), clearSplashTimers(), confirmShutdown(), destroyAmbientBackdrop(), ensureRuntimeInstallPoll(), initAppBoot(), installGatewayRuntime(), openSetupWizardModal() (+10 more)

### Community 76 - "test_ui_feedback.py"
Cohesion: 0.23
Nodes (7): _copy_text_to_clipboard_windows(), _bridge_with_env(), test_copy_password_copies_value_but_never_returns_it(), test_copy_password_helper_failure(), test_copy_password_not_configured(), test_copy_text_to_clipboard_windows_non_windows(), test_copy_text_to_clipboard_windows_roundtrip()

### Community 77 - "test_snapshot_counters_37.py"
Cohesion: 0.27
Nodes (5): _bars(), _round_trips(), _stats_for(), test_short_history_is_not_marked_truncated(), test_snapshot_counters_survive_restore_with_truncated_history()

### Community 78 - "._live_loop"
Cohesion: 0.09
Nodes (6): _on_done(), test_pause_feed_updates_ui_snapshot_immediately(), test_stale_engine_evolve_now_refused(), test_stale_engine_harvest_fills_refused(), test_stale_engine_state_publish_skipped(), test_live_engine_toggle_pause_and_auto_evolve_shift_math()

### Community 79 - "test_504_omni_env_cache.py"
Cohesion: 0.28
Nodes (8): _counting_read_text(), _manager(), test_content_change_is_visible_after_rewrite(), test_missing_file_then_created(), test_mtime_change_invalidates_even_with_same_content(), test_repeated_reads_hit_cache(), test_returned_dict_is_a_copy(), test_write_then_read_sees_new_password()

### Community 80 - "_mock_resp"
Cohesion: 0.31
Nodes (10): _coinbase_stats_payload(), _coinbase_ticker_payload(), _kraken_payload(), _mock_resp(), test_binance_quote_success_parses_all_fields(), test_coinbase_quote_success_parses(), test_kraken_quote_success_parses(), dispatch() (+2 more)

### Community 82 - ".load_session_snapshot"
Cohesion: 0.22
Nodes (4): _sanitize_json_value(), test_restore_survives_garbage_stop_ticket_and_entry_ts(), test_persistence_sanitizes_nan_and_inf_strict_json(), test_session_codec_rejects_symbol_mismatch_and_roundtrips_pending_and_orb()

### Community 83 - ".test_single_key"
Cohesion: 0.17
Nodes (5): test_v24_track_c_gemini_header_and_save_gateway_no_split_brain(), test_gateway_supervisor_http_responses(), test_gateway_supervisor_key_validation_defensive(), test_gateway_supervisor_nvidia_endpoint(), test_key_rate_limit_429_is_not_verified()

### Community 84 - "test_card_reorder_anim.py"
Cohesion: 0.35
Nodes (10): _css(), _js(), _reorder_block(), test_cards_are_stable_nodes_never_recreated_on_reorder(), test_flip_cleanup_clears_class_and_transform(), test_flip_inverts_with_translate_and_plays_via_class(), test_flip_records_first_rects_before_moving_nodes(), test_flip_runs_only_when_order_changes() (+2 more)

### Community 85 - "test_507_candle_write_on_close.py"
Cohesion: 0.42
Nodes (7): _counting_save(), _engine(), test_bar_close_persists_final_bar_once(), test_closed_bar_is_in_sqlite_after_close(), test_out_of_order_tick_does_not_double_save(), test_three_minutes_persist_two_closed_bars(), test_ticks_within_one_minute_write_nothing()

### Community 86 - "_open_short"
Cohesion: 0.20
Nodes (5): _open_short(), test_evaluate_live_strategies_short_exits_are_signal_only(), test_evaluate_live_strategies_small_gain_does_not_close_shorts(), test_stagnation_exit_closes_after_40m(), test_trailing_guard_short_ratchet_moves_stop_down()

### Community 88 - "._try_enter_bracket"
Cohesion: 0.34
Nodes (12): _ev(), _now_iso(), _offline_commander(), test_direction_thresholds_long_and_short(), test_events_older_than_60_min_excluded(), test_fallback_never_enters_hold_cash(), test_half_life_decay_60_min_is_half_weight(), test_llm_hold_cash_with_confidence_passes_through() (+4 more)

### Community 89 - "test_digest_refresh_session.py"
Cohesion: 0.09
Nodes (10): post(), _FakeCM, _FakeForum, _FakeHarvester, _FakeResp, _FakeSession, _make_commander(), test_concurrent_article_call_survives_refresh() (+2 more)

### Community 92 - "_error_body_text"
Cohesion: 0.33
Nodes (3): _error_body_text(), _walk(), _extract_error_provider()

### Community 93 - "test_502_ui_state_delta.py"
Cohesion: 0.39
Nodes (5): _engine(), _snapshot(), test_deepcopy_never_receives_heavy_arrays_on_unchanged_poll(), test_delta_is_still_a_defensive_copy(), test_delta_output_identical_to_old_path()

### Community 95 - ".bootstrap_intraday_session"
Cohesion: 0.08
Nodes (11): _fixture_bars(), test_bootstrap_resets_live_trading_state_when_orders_disabled(), test_signal_exit_fast_path_closes_under_hold_cash(), test_close_ticket_bypasses_veto_and_gates_under_hold_cash(), _cache_rows(), test_bootstrap_hydrates_fresh_sqlite_candles(), test_bootstrap_rejects_stale_sqlite_candles(), _fixture_bars() (+3 more)

### Community 96 - "test_phase2g_graphics.py"
Cohesion: 0.31
Nodes (4): _js(), test_p2g_chart_loop_capped_at_60fps(), test_p2g_hidden_view_stops_chart_loop(), test_p2g_no_temporary_probe_left_in_shipped_assets()

### Community 97 - "_FakeWebview"
Cohesion: 0.25
Nodes (3): _FakeWebview, test_run_auto_spawn_waits_30_seconds(), test_run_skips_auto_spawn_without_admin_password()

### Community 98 - "test_orb_day_rollover.py"
Cohesion: 0.36
Nodes (5): _minute_candles(), _tape_bar(), test_backtest_orb_range_rolls_at_utc_midnight(), test_live_orb_range_is_forming_on_a_partial_new_day(), test_live_orb_range_rolls_at_utc_midnight()

### Community 99 - "test_321_auto_redeploy.py"
Cohesion: 0.39
Nodes (5): _flat_engine(), test_no_redeploy_when_any_position_open(), test_redeploy_logs_once_per_flat_episode(), test_switch_off_does_not_redeploy(), test_switch_on_default_redeploys_when_flat()

### Community 101 - "test_318_system_config_untracked.py"
Cohesion: 0.53
Nodes (3): _git(), test_system_config_is_ignored_by_git(), test_system_config_is_untracked_but_present_on_disk()

### Community 104 - "_open_long"
Cohesion: 0.33
Nodes (3): _open_long(), test_bracket_take_profit_closes_via_on_tick(), test_evaluate_live_strategies_small_gain_does_not_close_longs()

### Community 108 - "cursors/index.tsx"
Cohesion: 0.23
Nodes (13): clearOverlapTransitionStyles(), drawPriceChart(), invalidateCanvasSizeCache(), locateMouseAndRefreshChart(), setIntelSortMode(), setLgWallpaper(), setRightTab(), setScaleMode() (+5 more)

### Community 114 - "test_gateway_item8.py"
Cohesion: 0.08
Nodes (9): _FakeEvent, _FakeHTTPResponse, _FakeWindow, test_daemon_log_default_path_is_project_logs(), test_existing_daemon_check_uses_2s_probe(), test_probe_health_success_failure_timeout(), test_save_and_launch_gateway_waits_30_seconds(), test_start_daemon_default_wait_is_30_seconds() (+1 more)

### Community 123 - "closeResetModal"
Cohesion: 0.40
Nodes (6): closeResetModal(), confirmResetArena(), handleResetOverlayClick(), initResetSlideConfirm(), resetArena(), resetSlideConfirmState()

### Community 127 - "isReducedMotionPreferred"
Cohesion: 0.40
Nodes (5): initAmbientBackdrop(), isReducedMotionPreferred(), morphText(), mountSilverStreamAmbient(), renderMacroRibbon()

### Community 138 - ".stop"
Cohesion: 0.13
Nodes (14): build_engine_view_model(), test_v24_track_d_view_model_sanitizes_mc_stats_and_dev_bat_structure(), _rankings(), test_view_model_does_not_fabricate_take_profit(), test_view_model_reports_unknown_mc_and_quota(), test_view_model_short_unrealized_pnl_pct(), test_view_model_skips_stale_ranking_entry(), _fixture_bars() (+6 more)

### Community 139 - "fix_item5_patch.py"
Cohesion: 0.18
Nodes (15): addChartBeacon(), attachToastInteractions(), checkOnboardingBoot(), dismissToast(), enqueueToast(), ensureLiveTradingStarted(), pollBackend(), previewPositionAnimation() (+7 more)

### Community 146 - "Choreography"
Cohesion: 0.29
Nodes (6): 1. Launch Packaged Desktop Executable (`.exe`), 2. Run Self-Test Verification, 3. Run Automated Unit Test Suite (32 Tests), 4. Build Standalone Windows Executable, Quick Start Guide, TradeBot0: Multi-Agent Paper Trading & Genetic Evolution Arena (BTC/USD)

## Knowledge Gaps
- **34 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `LiveArenaEngine` connect `test_live_engine.py` to `test_debug_optimize_regression.py`, `test_v200_fixes.py`, `CandleBar`, `BrokerSim`, `Leaderboard`, `.stop`, `ArenaDashboard`, `live_engine.py`, `OrderSide`, `ViewModelPublisher`, `OmniRouteClient`, `FillEvent`, `MacroCommander`, `GeneticEvolver`, `test_phase3_ingestion.py`, `soak_engine.py`, `test_performance_and_optimizations.py`, `ConfigManager`, `threading`, `test_debug_report_fixes.py`, `test_phase2_optimize.py`, `test_live_chop_gate.py`, `StreamingCryptoFeed`, `test_chop_gate_seed.py`, `LiveStrategyRunnerMixin`, `soak_engine.py`, `test_autosave_35.py`, `MultiTimeframeEngine`, `test_phase3_soak.py`, `ingestion.py`, `._build_snapshot_locked`, `LiveQuote`, `controls/index.ts`, `ArenaStorage`, `SessionCodecMixin`, `test_snapshot_counters_37.py`, `._live_loop`, `_mock_resp`, `.load_session_snapshot`, `test_507_candle_write_on_close.py`, `_open_short`, `test_502_ui_state_delta.py`, `.bootstrap_intraday_session`, `test_orb_day_rollover.py`, `test_321_auto_redeploy.py`, `_open_long`, `test_restore_applies_genome_leverage_to_portfolio`, `test_stale_engine_save_session_state_refused`?**
  _High betweenness centrality (0.174) - this node is a cross-community bridge._
- **Are the 28 inferred relationships involving `LiveArenaEngine` (e.g. with `Architectural Highlights` and `BrokerSim`) actually correct?**
  _`LiveArenaEngine` has 28 INFERRED edges - model-reasoned connections that need verification._
- **Should `test_phase2_omniroute_client.py` be split into smaller, more focused modules?**
  _Cohesion score 0.0907563025210084 - nodes in this community are weakly interconnected._
- **Why does `OmniRouteClient` connect `OmniRouteClient` to `test_phase2_omniroute_client.py`, `test_debug_optimize_regression.py`, `test_v200_fixes.py`, `test_item10_packaging.py`, `live_engine.py`, `IntelligenceHarvester`, `OrderSide`, `MacroCommander`, `test_phase3_ingestion.py`, `.get_intel_hub_telemetry`, `test_live_engine.py`, `config_manager.py`, `test_gateway_diagnosis.py`, `test_llm_concurrent_sessions.py`, `test_llm_json_mode_fallback.py`, `RawEvent`, `ingestion.py`, `.get_gateway_diagnosis`, `test_digest_refresh_session.py`, `test_article_real_streamed_progress_and_viewmodel_delta`, `.run_digest_sync`, `test_track_c_omniroute_max_concurrent_1_repair_no_deadlock`?**
  _High betweenness centrality (0.094) - this node is a cross-community bridge._
- **Are the 104 inferred relationships involving `OrderSide` (e.g. with `main()` and `BrokerSim`) actually correct?**
  _`OrderSide` has 104 INFERRED edges - model-reasoned connections that need verification._
- **Should `test_debug_optimize_regression.py` be split into smaller, more focused modules?**
  _Cohesion score 0.11764705882352941 - nodes in this community are weakly interconnected._
- **Why does `GatewaySupervisor` connect `GatewaySupervisor` to `test_debug_optimize_regression.py`, `test_item10_packaging.py`, `re`, `ArenaDashboard`, `live_engine.py`, `test_gateway_install_progress_cancel.py`, `test_phase3_ingestion.py`, `._run_runtime_install`, `test_track_c_gateway_npm_strips_secrets_and_no_blind_retry`, `test_performance_and_optimizations.py`, `.shutdown`, `ConfigManager`, `test_gateway_autolaunch_mandatory.py`, `test_save_launch_progress.py`, `config_manager.py`, `test_gateway_diagnosis.py`, `._run_runtime_install`, `.omniroute_installed`, `ingestion.py`, `Any`, `.test_single_key`, `test_gateway_item8.py`?**
  _High betweenness centrality (0.057) - this node is a cross-community bridge._