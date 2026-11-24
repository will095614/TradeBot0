# Graph Report - TradeBot0_Local  (2026-11-25)

## Corpus Check
- 129 files · ~165,591 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 11 file(s) not represented in the graph (top: (none) 4, .iss 1, .lnk 1)

## Summary
- 2474 nodes · 7141 edges · 136 communities (89 shown, 47 thin omitted)
- Extraction: 88% EXTRACTED · 12% INFERRED · 0% AMBIGUOUS · INFERRED: 873 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `ea9277a1`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- .chat_json
- test_debug_optimize_regression.py
- test_update_checker.py
- test_v200_fixes.py
- TimeMachineArena
- sys
- test_forum_collector.py
- BrokerSim
- test_505_leaderboard_cache.py
- test_ui_contract.py
- ArenaDashboard
- OrderSide
- IntelligenceHarvester
- test_gemini_client_quota_fastpath_sse_error_and_timeout
- ViewModelPublisher
- GeminiClient
- FillEvent
- _ArenaBridgeApi
- Any
- .get_ui_state
- Leaderboard
- syncAppShellInert
- test_phase3_ingestion.py
- soak_engine.py
- Stage
- test_performance_and_optimizations.py
- test_intel_stream_redesign.py
- time
- MonteCarloOddsEvaluator
- test_performance_and_optimizations.py
- QuoteManager
- CandleBar
- ConfigManager
- test_live_engine.py
- _SliceableDeque
- threading
- test_debug_report_fixes.py
- ArenaStorage
- test_save_launch_progress.py
- test_ai_panels_frontend.py
- test_event_article.py
- test_live_chop_gate.py
- test_ws_feed.py
- test_508_chop_gate.py
- LiveStrategyRunnerMixin
- test_v252_ui_fixes.py
- test_autosave_35.py
- test_llm_concurrent_sessions.py
- test_llm_json_mode_fallback.py
- soak_engine.py
- DeduplicationBuffer
- test_auto_evolve_fires_on_closed_trades
- MultiTimeframeEngine
- StreamingCryptoFeed
- MacroCommander
- renderIntelHub
- test_phase3_soak.py
- test_quota_pct_has_no_invented_denominator
- test_intel_hub_layout.py
- renderAll
- ingestion.py
- ._build_snapshot_locked
- getCommandPaletteItems
- LiveQuote
- controls/index.ts
- test_v260_debug_and_optimize.py
- FakeWS
- ArenaStorage
- SessionCodecMixin
- InterruptDebouncer
- test_ui_feedback.py
- test_snapshot_counters_37.py
- .bootstrap_intraday_session
- test_v287_render_guards.py
- test_chop_gate_seed.py
- gemini_client.py
- test_card_reorder_anim.py
- test_507_candle_write_on_close.py
- .total_equity
- test_item12a_omniroute.py
- ._try_enter_bracket
- test_digest_refresh_session.py
- _fresh_broker_competitor
- .run_digest_sync
- test_orb_anchor_34.py
- test_502_ui_state_delta.py
- test_track_c_gemini_max_concurrent_1_repair_no_deadlock
- persistence.py
- test_phase2g_graphics.py
- test_320_save_history_storage.py
- test_321_auto_redeploy.py
- test_orb_day_rollover.py
- _FakeThread
- test_318_system_config_untracked.py
- test_article_real_streamed_progress_and_viewmodel_delta
- .get_ai_diagnosis
- _referenced_classes
- ._handle_ws_quote
- conftest.py
- _OKHandler
- cursors/index.tsx
- _build_engine_view_model_impl
- test_319_src_ai_gone.py
- .compute_r_multiple_qty
- test_gui_item7.py
- _empty_view_model
- LiveArenaEngine
- fix_item5_patch.py
- Choreography

## God Nodes (most connected - your core abstractions)
1. `LiveArenaEngine` - 209 edges
2. `OrderSide` - 152 edges
3. `BrokerSim` - 110 edges
4. `GeminiClient` - 108 edges
5. `Portfolio` - 102 edges
6. `OrderTicket` - 102 edges
7. `MacroCommander` - 95 edges
8. `OrderType` - 74 edges
9. `ExecutionReason` - 69 edges
10. `ArenaStorage` - 65 edges

## Surprising Connections (you probably didn't know these)
- `Architectural Highlights` --references--> `LiveArenaEngine`  [INFERRED]
  README.md → src/data/live_engine.py
- `Architectural Highlights` --references--> `GeneticEvolver`  [INFERRED]
  README.md → src/arena/evolution.py
- `Architectural Highlights` --references--> `CompetitorGenome`  [INFERRED]
  README.md → src/competitors/base.py
- `Architectural Highlights` --references--> `BrokerSim`  [INFERRED]
  README.md → src/arena/broker_sim.py
- `Architectural Highlights` --references--> `Portfolio`  [INFERRED]
  README.md → src/arena/portfolio.py

## Import Cycles
- None detected.

## Communities (136 total, 47 thin omitted)

### Community 0 - ".chat_json"
Cohesion: 0.10
Nodes (9): classify_llm_error(), _error_body_text(), _walk(), _extract_gemini_detail_signals(), _looks_like_format_rejection(), _parse_duration_seconds(), _shutting_down(), test_chat_json_400_format_rejection_is_not_quota() (+1 more)

### Community 1 - "test_debug_optimize_regression.py"
Cohesion: 0.13
Nodes (7): _symbols_from_registry(), _retry_window_seconds(), test_track_b_non_integer_cadence_advances_slots(), test_track_b_quote_feeds_rejects_non_positive_and_non_finite(), test_track_c_forum_collector_parses_dot_x_symbols(), test_track_d_frontend_contracts_css_html_js(), test_v24_track_c_gemini_extract_json_retry_hint_dedup_and_https_redirect()

### Community 2 - "test_update_checker.py"
Cohesion: 0.08
Nodes (24): _check(), check_for_updates(), compare_versions(), get_manifest_url(), _is_date_version(), test_track_c_update_checker_rejects_non_https_and_clears_download_url_when_up_to_date(), _mock_response(), test_bridge_check_for_updates_not_configured() (+16 more)

### Community 3 - "test_v200_fixes.py"
Cohesion: 0.10
Nodes (19): AggressiveCompetitor, BaseCompetitor, CompetitorGenome, ConservativeCompetitor, ORBCompetitor, SessionMeanPullbackCompetitor, TrailingGuardCompetitor, test_all_four_competitors_initialization_and_first_buy() (+11 more)

### Community 6 - "TimeMachineArena"
Cohesion: 0.12
Nodes (9): TimeMachineArena, test_evolution_tournament_runs_multiple_generations(), test_orb_window_excludes_current_bar(), test_timemachine_evolution_preserves_portfolio(), test_timemachine_simulation_with_synthetic_bars(), test_zero_volume_bar_does_not_invent_volume(), _tape(), test_backtest_short_exits_at_trailed_level_not_original_stop() (+1 more)

### Community 7 - "sys"
Cohesion: 0.14
Nodes (9): configure_logging(), get_log_dir(), _flush_file_handlers(), _remove_test_handlers(), test_configure_logging_never_raises_on_unwritable_dir(), test_get_log_dir_resolution(), test_stream_handler_present_when_stdout_exists(), test_stream_handler_skipped_when_stdout_is_none() (+1 more)

### Community 8 - "test_forum_collector.py"
Cohesion: 0.10
Nodes (15): ForumCollector, parse_stocktwits_stream(), _registry_mock_get(), _stream_json(), test_forum_batch_scored_without_llm_when_offline(), mock_get(), test_forum_collector_fast_test_short_circuits(), test_forum_collector_hourly_cap() (+7 more)

### Community 9 - "BrokerSim"
Cohesion: 0.08
Nodes (37): Architectural Highlights, BrokerSim, OrderTicket, Portfolio, test_apply_fill_value_error_does_not_kill_cadence(), _boom(), test_submit_order_returns_none_when_apply_fill_fails(), test_broker_sim_bracket_stop_loss_trigger() (+29 more)

### Community 10 - "test_505_leaderboard_cache.py"
Cohesion: 0.24
Nodes (8): _counting_periods(), _portfolio_with_history(), test_fill_invalidates_cache(), test_metrics_cached_across_ticks_with_no_fills(), test_replace_equity_history_invalidates_cache(), test_reset_invalidates_cache(), test_risk_free_rate_change_invalidates_cache(), test_track_a_leaderboard_caches_flat_portfolio()

### Community 11 - "test_ui_contract.py"
Cohesion: 0.15
Nodes (15): _badge_cls_producer_values(), _bridge_class_node(), _bridge_methods(), _bridge_obj_calls(), _bridge_self_calls(), _defined_classes(), _html_ids(), _js_defined_functions() (+7 more)

### Community 12 - "ArenaDashboard"
Cohesion: 0.08
Nodes (19): check_and_ensure_environment(), main(), _set_windows_app_user_model_id(), ArenaDashboard, _on_window_closing(), close_native_splash(), __getattr__(), test_track_c_save_and_launch_aborts_if_key_save_fails() (+11 more)

### Community 14 - "OrderSide"
Cohesion: 0.08
Nodes (26): __getattr__(), ExecutionReason, OrderSide, OrderStatus, OrderType, PositionSide, RiskGuard, parse_symbol_pairs() (+18 more)

### Community 15 - "IntelligenceHarvester"
Cohesion: 0.07
Nodes (17): IntelligenceHarvester, RawEvent, test_fetch_from_registry_dispatches_by_type_and_skips_forum(), test_fetch_live_feeds_still_returns_test_fixtures(), test_process_batch_carries_tier_thread_and_consensus(), _run(), test_process_batch_fallback_consensus_from_score(), _run() (+9 more)

### Community 16 - "test_gemini_client_quota_fastpath_sse_error_and_timeout"
Cohesion: 0.09
Nodes (9): _FakeCM, _FakeResp, test_gemini_client_check_health_and_update_api_key(), _run(), test_gemini_client_rest_payload_thought_skipping_and_block_reason(), _run(), test_gemini_client_sse_streaming_and_real_error_code(), _run() (+1 more)

### Community 17 - "ViewModelPublisher"
Cohesion: 0.21
Nodes (4): ViewModelPublisher, test_track_d_view_model_publisher_excludes_fills_and_detects_is_live_change(), test_view_model_delta_omits_unchanged_history_and_intel_events_equivalently(), test_view_model_delta_shallow_clones_and_cache()

### Community 18 - "GeminiClient"
Cohesion: 0.08
Nodes (30): extract_json(), GeminiClient, test_success_counted_only_after_parseable_json(), _run(), _mock_429_session(), _mock_resp(), test_chat_json_all_retries_429_returns_none(), _run() (+22 more)

### Community 19 - "FillEvent"
Cohesion: 0.15
Nodes (13): FillEvent, test_track_a_portfolio_cross_gen_leverage_partial_close_conserves_equity(), test_track_a_portfolio_failed_fill_does_not_corrupt_fees(), test_v24_track_a_portfolio_apply_fill_upfront_quantization(), test_bidirectional_short_win_rate_and_closing_fill(), _assert_equity_conservation(), _fill(), test_add_to_short_recomputes_avg_entry_and_margin() (+5 more)

### Community 21 - "Any"
Cohesion: 0.08
Nodes (8): build_event_article_prompts(), _runner(), _on_progress(), _event_dict(), test_prompt_includes_raw_snippet(), test_prompt_without_snippet_omits_line(), test_telemetry_strips_raw_snippet(), test_article_prompt_asks_for_1000_words_and_six_paragraphs()

### Community 22 - ".get_ui_state"
Cohesion: 0.13
Nodes (14): test_get_ui_state_mutation_isolation(), test_pause_feed_updates_ui_snapshot_immediately(), _drive(), test_auto_evolve_timer_and_toggle(), test_fill_event_has_monotonic_seq_and_action_label(), test_live_engine_bidirectional_long_and_short_execution(), test_live_engine_eth_and_leverage_configuration(), test_live_engine_evolve_preserves_fill_tape_and_portfolio_positions() (+6 more)

### Community 24 - "Leaderboard"
Cohesion: 0.05
Nodes (29): GeneticEvolver, CompetitorStats, Leaderboard, test_evolve_generation_early_return_does_not_crash(), test_last_records_class_default_present(), _breakeven_portfolio(), test_breakeven_close_counts_as_closed_trade(), test_breakeven_close_keeps_win_rate_decided_only() (+21 more)

### Community 25 - "syncAppShellInert"
Cohesion: 0.10
Nodes (25): blurActiveFocus(), closeResetModal(), closeSetupWizardModal(), closeShutdownModal(), closeWizardCloseConfirm(), confirmCloseWizardWithoutSaving(), confirmResetArena(), confirmShutdown() (+17 more)

### Community 26 - "test_phase3_ingestion.py"
Cohesion: 0.11
Nodes (20): parse_polymarket_events(), parse_reddit_posts(), _mock_commander(), test_feed_numeric_parsing_never_raises(), test_keyword_word_boundaries_no_substring_false_positives(), test_no_fabricated_seed_events_and_honest_quota(), test_veto_never_blocks_close(), _fake_registry_response() (+12 more)

### Community 27 - "soak_engine.py"
Cohesion: 0.14
Nodes (12): ETHFeed, _bar(), _ccxt_ohlcv(), test_fetch_dataframe_both_sources_fail_raises(), test_fetch_dataframe_falls_back_to_ccxt_kraken(), test_fetch_historical_bars_yahoo_multiindex_columns(), test_fetch_historical_bars_yahoo_success(), test_generate_signal_real_path_setups_and_exits() (+4 more)

### Community 28 - "Stage"
Cohesion: 0.06
Nodes (38): animCandles, changeEvolveInterval(), chartBeacons, currentSplashSteps, EVOLVE_INTERVAL_OPTIONS, fillRoundRect(), hashTickerName(), initialSplashSteps (+30 more)

### Community 29 - "test_performance_and_optimizations.py"
Cohesion: 0.21
Nodes (8): test_launchers_and_shortcut_integrity(), test_macro_veto_intent_preserved_in_live_evaluation(), test_phase4_mtf_trend_confluence_gatekeeper(), test_portfolio_no_duplicate_apply_fill_returns(), test_splash_logo_concentric_alignment_and_svg_zap(), test_stageshow_ui_design_system_integrity(), test_window_startup_foreground_configuration(), test_zero_cjk_in_frontend_assets()

### Community 30 - "test_intel_stream_redesign.py"
Cohesion: 0.17
Nodes (24): test_splash_toast_catchup_present_with_restored_guard(), _css(), _css_block(), _fn_body(), _html(), _js(), test_article_failure_shows_reason_not_summary(), test_article_lazy_once_and_cached() (+16 more)

### Community 31 - "time"
Cohesion: 0.33
Nodes (11): check_binance_rest(), check_binance_ws(), check_ccxt_kraken(), check_coinbase_rest(), check_feed_registry(), check_gemini_health(), check_kraken_rest(), check_stocktwits() (+3 more)

### Community 32 - "MonteCarloOddsEvaluator"
Cohesion: 0.16
Nodes (9): MonteCarloBracketOdds, MonteCarloOddsEvaluator, test_track_b_timemachine_rejects_wrong_side_tp(), test_v24_track_b_timemachine_single_sim_and_flat_empirical_candles(), test_backtest_opens_shorts_on_downtrend(), test_monte_carlo_ev_gate_odds_evaluation(), test_monte_carlo_without_numpy_reports_unknown(), test_uncapped_runner_r_assumption_is_labelled() (+1 more)

### Community 33 - "test_performance_and_optimizations.py"
Cohesion: 0.06
Nodes (18): _apply_window_icon(), _activate_foreground_startup(), _on_window_shown(), _delayed_activation(), _build_html_template(), _destroy_win32_hicons(), _destroy_window_hicons(), _get_app_icon_path() (+10 more)

### Community 34 - "QuoteManager"
Cohesion: 0.19
Nodes (3): QuoteManager, test_dead_cascade_state_is_gone(), test_ws_quote_path_still_works()

### Community 35 - "CandleBar"
Cohesion: 0.20
Nodes (7): CandleBar, _fixture_bars(), test_bootstrap_resets_live_trading_state_when_orders_disabled(), test_backtest_slippage_uses_measured_atr(), _bars(), _fixture_bars(), test_bootstrap_spawns_mtf_seed_thread_instead_of_blocking()

### Community 36 - "ConfigManager"
Cohesion: 0.08
Nodes (13): ConfigManager, _extract_env_var_from_file(), test_track_c_config_manager_preserves_existing_config_on_write_error(), test_blank_save_allows_standby_mode(), test_bridge_stepwise_simulation_erroneous_then_valid(), test_config_manager_atomic_recovery_from_corruption(), test_config_manager_gemini_key_persistence(), test_config_manager_input_sanitization() (+5 more)

### Community 38 - "test_live_engine.py"
Cohesion: 0.05
Nodes (32): _cache_rows(), _coinbase_stats_payload(), _coinbase_ticker_payload(), _kraken_payload(), _mock_resp(), _open_long(), _open_short(), _startup_engine_long() (+24 more)

### Community 40 - "threading"
Cohesion: 0.15
Nodes (9): _safe_refresh(), test_refresh_intel_digest_is_serialized_under_concurrent_calls(), _run(), _drive(), _make_engine(), _quote(), test_concurrent_publish_harvests_each_fill_once(), test_publish_state_snapshot_holds_engine_lock() (+1 more)

### Community 41 - "test_debug_report_fixes.py"
Cohesion: 0.08
Nodes (14): _fixture_bars(), _raise_no_network(), test_cooperative_stop_event(), test_full_restore_bootstrap_start_integration(), test_offline_start_does_not_execute_stale_candles(), test_session_save_and_restore_with_locked_margin(), test_slow_bootstrap_stop_safety(), test_start_live_trading_does_not_wipe_restored_positions() (+6 more)

### Community 42 - "ArenaStorage"
Cohesion: 0.18
Nodes (13): ArenaStorage, wrapper(), _candle(), test_p2_concurrent_candle_writes_all_persist(), writer(), test_p2_engine_stop_closes_storage_and_restart_still_writes(), test_p2_eth_feed_first_fetch_loads_pandas_and_behaves(), test_p2_eth_feed_import_does_not_import_pandas() (+5 more)

### Community 43 - "test_save_launch_progress.py"
Cohesion: 0.13
Nodes (10): _make_bridge(), _read_app_js(), test_get_save_launch_status_returns_copy(), test_save_and_launch_does_not_jump_splash_to_75(), test_save_launch_failed_stage_never_reports_100(), test_save_launch_stage_advances_and_done_only_on_return(), test_save_launch_stage_resets_between_runs(), test_save_launch_status_polled_from_js() (+2 more)

### Community 44 - "test_ai_panels_frontend.py"
Cohesion: 0.23
Nodes (19): _css(), _dashboard(), _html(), _js(), test_commander_and_stream_titles(), test_compact_mode_fits_intro_line_and_status_lines_hold_width(), test_deck_empty_slots_collapse_and_level_bottoms(), test_dock_gear_tooltip_is_ai_services() (+11 more)

### Community 45 - "test_event_article.py"
Cohesion: 0.21
Nodes (13): _event_id(), _make_commander(), test_ai_offline_returns_failure_without_llm(), test_article_generation_uses_long_timeout(), test_bridge_get_event_article(), test_concurrent_expands_merge_into_one_llm_call(), test_curated_event_carries_tickers_article_fields(), test_curated_event_empty_tickers_becomes_empty_list() (+5 more)

### Community 46 - "test_live_chop_gate.py"
Cohesion: 0.19
Nodes (11): _bars(), _choppy_closes(), _engine_with_15m(), test_chop_gate_blocks_entry_through_try_enter_bracket(), test_chop_gate_blocks_on_choppy_15m(), test_chop_gate_excludes_the_forming_bucket(), test_chop_gate_never_blocks_signal_exit_close(), test_chop_gate_open_on_trending_15m() (+3 more)

### Community 47 - "test_ws_feed.py"
Cohesion: 0.14
Nodes (10): _run_feed(), test_ws_clean_server_close_counts_as_reconnect(), test_ws_connect_and_stream_delivers_quotes(), _fake_connect(), _on_quote(), test_ws_reconnect_backoff_on_disconnect(), _fake_connect(), _fake_sleep() (+2 more)

### Community 48 - "test_508_chop_gate.py"
Cohesion: 0.18
Nodes (9): efficiency_ratio(), _bar(), _choppy_bars(), test_efficiency_ratio_unit(), test_gate_blocks_entries_on_choppy_tape(), test_gate_inactive_on_trend_tape(), test_gate_never_blocks_closes(), _total_closed() (+1 more)

### Community 50 - "test_v252_ui_fixes.py"
Cohesion: 0.13
Nodes (3): _assets_root(), test_skip_bridge_deleted_but_mode_readers_kept(), test_wizard_has_no_skip_button()

### Community 51 - "test_autosave_35.py"
Cohesion: 0.18
Nodes (8): _bars(), _engine(), _raise_no_network(), test_autosave_does_not_fire_when_stopped_or_superseded(), test_crash_like_stop_leaves_restorable_autosave(), test_evolution_marks_autosave_pending_and_it_fires_immediately(), test_live_loop_triggers_periodic_autosave(), test_periodic_autosave_writes_snapshot_when_interval_elapses()

### Community 52 - "test_llm_concurrent_sessions.py"
Cohesion: 0.21
Nodes (4): _StubGateway, test_four_threads_expand_concurrently_without_closing_each_other(), _one(), _worker()

### Community 53 - "test_llm_json_mode_fallback.py"
Cohesion: 0.18
Nodes (7): _client_with(), _CM, _FakeSession, _Resp, test_generic_400_does_not_trigger_the_format_retry(), test_rejected_format_is_remembered_for_later_calls(), test_rejected_response_format_retries_without_it_and_parses()

### Community 54 - "soak_engine.py"
Cohesion: 0.15
Nodes (14): closing_fills_since(), db_stats(), do_slice(), genome_valid(), main(), _sample(), make_quote(), _parse_args() (+6 more)

### Community 55 - "DeduplicationBuffer"
Cohesion: 0.20
Nodes (4): _dedup_normalize_title(), DeduplicationBuffer, test_deduplication_buffer(), test_ingestion_clean_html_strips_script_style_and_dedup_forget()

### Community 56 - "test_auto_evolve_fires_on_closed_trades"
Cohesion: 0.15
Nodes (8): _drive_fixed(), _quote(), test_auto_evolve_fires_on_closed_trades(), _round_trips(), test_live_tick_integration_fixed_price_series(), test_next_evolve_sec_counts_trades_not_only_hours(), test_no_cached_price_when_feed_down(), test_toggle_auto_evolve_reenable_compensates_disabled_time()

### Community 57 - "MultiTimeframeEngine"
Cohesion: 0.08
Nodes (16): IndicatorEngineMixin, MultiTimeframeEngine, test_track_b_mtf_engine_delta_volume_and_neutral_on_conflict(), test_v24_track_b_mtf_seed_1h_merges_same_slot(), _buckets(), _hourly_bars(), _minute_bars(), test_engine_seed_fetch_failure_stays_neutral() (+8 more)

### Community 58 - "StreamingCryptoFeed"
Cohesion: 0.24
Nodes (3): StreamingCryptoFeed, test_phase1_websocket_feed_parsing_and_fast_path_fallback(), test_parse_binance_ticker_rejects_garbage()

### Community 60 - "MacroCommander"
Cohesion: 0.07
Nodes (26): StructuredEvent, _dedup_tickers(), _event_age_min(), MacroCommander, MacroRegimeState, _parse_event_epoch(), _safe_float(), test_synthesize_plumbs_raw_snippet() (+18 more)

### Community 61 - "renderIntelHub"
Cohesion: 0.14
Nodes (23): buildIntelEventCard(), cleanIntelSummary(), clearIntelSearch(), escapeHtml(), formatIntelEventTime(), initIntelFilterControls(), intelArticleBodyEl(), intelEventKey() (+15 more)

### Community 62 - "test_phase3_soak.py"
Cohesion: 0.28
Nodes (4): _bootstrapped_engine(), _load_soak_helpers(), soak(), test_p3_mini_soak_many_ticks_no_growth_blowup()

### Community 63 - "test_quota_pct_has_no_invented_denominator"
Cohesion: 0.20
Nodes (4): test_quota_pct_has_no_invented_denominator(), _run_429(), test_quota_pct_uses_user_set_budget(), test_quota_throttling_slows_digest()

### Community 64 - "test_intel_hub_layout.py"
Cohesion: 0.25
Nodes (12): _commander(), _css(), _js(), _mock_pipeline(), _rule(), _structured(), test_stream_loading_block_is_centered_with_meter(), test_sync_status_failed_when_feeds_down() (+4 more)

### Community 65 - "renderAll"
Cohesion: 0.17
Nodes (20): buildSparklineGeometry(), createStrategyCardSkeleton(), fmtPct(), fmtSignedUsd(), fmtTimeSec(), fmtUsd(), isReducedMotionPreferred(), morphText() (+12 more)

### Community 66 - "ingestion.py"
Cohesion: 0.08
Nodes (18): _clean_html_text(), _compile_word_group(), _compiled_word_re(), _contains_word(), _first_child_text(), _parse_feed_ts(), _parse_iso_ts(), parse_rss_atom() (+10 more)

### Community 68 - "getCommandPaletteItems"
Cohesion: 0.12
Nodes (22): applyBackdropMode(), closeCommandPalette(), cycleBackdropMode(), getCommandPaletteItems(), handleCmdPaletteOverlayClick(), initAmbientBackdrop(), initCommandPalette(), initScrollAreaFades() (+14 more)

### Community 70 - "controls/index.ts"
Cohesion: 0.19
Nodes (10): _broker(), _commander(), test_backtest_default_sizing_is_one(), test_compute_r_multiple_qty_scales_budget_and_clamps(), test_evaluate_signal_sizing_shrinks_qty_not_sl(), test_no_confidence_means_no_sizing_effect(), test_per_strategy_sensitivity_scales_the_deviation(), test_sizing_formula_exact_values() (+2 more)

### Community 71 - "test_v260_debug_and_optimize.py"
Cohesion: 0.16
Nodes (5): _safe_fmt_hms(), _SafeRotatingFileHandler, test_safe_fmt_hms_handles_invalid_and_valid_timestamps(), test_safe_rotating_handler_rollover_cooldown(), test_timemachine_frozen_report_uses_appdata_memory_dir()

### Community 73 - "ArenaStorage"
Cohesion: 0.15
Nodes (4): _retry_on_db_error(), _sanitize_json_value(), test_track_b_persistence_batch_fills_and_prune_candles(), test_phase2_sqlite_wal_persistence_and_cold_start_hydration()

### Community 75 - "InterruptDebouncer"
Cohesion: 0.24
Nodes (3): InterruptDebouncer, test_stage2_interrupt_debouncing_r4(), _run()

### Community 76 - "test_ui_feedback.py"
Cohesion: 0.29
Nodes (3): _copy_text_to_clipboard_windows(), test_copy_text_to_clipboard_windows_non_windows(), test_copy_text_to_clipboard_windows_roundtrip()

### Community 77 - "test_snapshot_counters_37.py"
Cohesion: 0.27
Nodes (5): _bars(), _round_trips(), _stats_for(), test_short_history_is_not_marked_truncated(), test_snapshot_counters_survive_restore_with_truncated_history()

### Community 78 - ".bootstrap_intraday_session"
Cohesion: 0.09
Nodes (6): _on_done(), test_evolve_now_with_fewer_than_two_rankings_does_not_raise(), test_stale_engine_evolve_now_refused(), test_stale_engine_harvest_fills_refused(), test_stale_engine_state_publish_skipped(), test_session_state_save_and_restore_and_shutdown_bridge()

### Community 80 - "test_v287_render_guards.py"
Cohesion: 0.40
Nodes (7): _fn_body(), _js(), test_hub_header_writes_guarded(), test_intel_card_element_refs_cached(), test_macro_ribbon_writes_guarded(), test_spotlight_vars_written_once_per_frame(), test_strat_color_and_gen_label_writes_guarded()

### Community 82 - "test_chop_gate_seed.py"
Cohesion: 0.29
Nodes (10): _engine(), _feed_1m(), _tape_end_anchored(), _tape_slot_aligned(), test_seed_helper_feeds_continuous_chain_and_arms_gate(), test_seed_helper_gap_truncates_to_suffix_after_gap(), test_seed_helper_malformed_row_skipped_not_fabricated(), test_seed_helper_misaligned_or_empty_seeds_nothing() (+2 more)

### Community 83 - "gemini_client.py"
Cohesion: 0.08
Nodes (14): _clean_key_input(), compute_backoff(), probe_gemini_api_key(), resolve_gemini_model(), test_gemini_key_probe_http_responses(), test_classify_llm_error_structured_gemini_429_and_spend_cap(), test_resolve_gemini_model_aliases(), test_key_rate_limit_429_is_not_verified() (+6 more)

### Community 84 - "test_card_reorder_anim.py"
Cohesion: 0.35
Nodes (10): _css(), _js(), _reorder_block(), test_cards_are_stable_nodes_never_recreated_on_reorder(), test_flip_cleanup_clears_class_and_transform(), test_flip_inverts_with_translate_and_plays_via_class(), test_flip_records_first_rects_before_moving_nodes(), test_flip_runs_only_when_order_changes() (+2 more)

### Community 85 - "test_507_candle_write_on_close.py"
Cohesion: 0.42
Nodes (7): _counting_save(), _engine(), test_bar_close_persists_final_bar_once(), test_closed_bar_is_in_sqlite_after_close(), test_out_of_order_tick_does_not_double_save(), test_three_minutes_persist_two_closed_bars(), test_ticks_within_one_minute_write_nothing()

### Community 86 - ".total_equity"
Cohesion: 0.28
Nodes (4): test_portfolio_reset_clears_all_metrics(), test_portfolio_buy_and_sell_accounting(), test_portfolio_initialization(), test_portfolio_short_accounting_and_overcovering()

### Community 87 - "test_item12a_omniroute.py"
Cohesion: 0.23
Nodes (7): _now_iso(), _offline_commander(), _strong_bearish_events(), test_empty_digest_expires_stale_fallback(), test_fallback_clears_when_llm_recovers(), test_fallback_regime_is_marked_and_expires(), test_regime_state_dict_exposes_fallback()

### Community 88 - "._try_enter_bracket"
Cohesion: 0.27
Nodes (14): _run(), _ws_once(), _ev(), _now_iso(), _offline_commander(), test_direction_thresholds_long_and_short(), test_events_older_than_60_min_excluded(), test_fallback_never_enters_hold_cash() (+6 more)

### Community 89 - "test_digest_refresh_session.py"
Cohesion: 0.10
Nodes (8): _FakeCM, _FakeForum, _FakeHarvester, _FakeResp, _FakeSession, _make_commander(), test_concurrent_article_call_survives_refresh(), test_two_refreshes_leave_session_open()

### Community 90 - "_fresh_broker_competitor"
Cohesion: 0.29
Nodes (5): _fresh_broker_competitor(), _r_multiple(), test_evaluate_signal_returns_none_when_breaker_tripped_all_strategies(), test_evaluate_signal_short_entries_mirror_long_brackets_all_strategies(), test_strategy_qty_zero_returns_none()

### Community 92 - "test_orb_anchor_34.py"
Cohesion: 0.20
Nodes (5): _tape_bar(), test_backtest_orb_range_anchored_to_first_15_tape_bars(), test_bootstrap_anchors_orb_range_to_first_15_warmup_bars(), test_live_orb_range_does_not_drift_with_rolling_buffer(), _warmup_bars()

### Community 93 - "test_502_ui_state_delta.py"
Cohesion: 0.39
Nodes (5): _engine(), _snapshot(), test_deepcopy_never_receives_heavy_arrays_on_unchanged_poll(), test_delta_is_still_a_defensive_copy(), test_delta_output_identical_to_old_path()

### Community 96 - "test_phase2g_graphics.py"
Cohesion: 0.31
Nodes (4): _js(), test_p2g_chart_loop_capped_at_60fps(), test_p2g_hidden_view_stops_chart_loop(), test_p2g_no_temporary_probe_left_in_shipped_assets()

### Community 97 - "test_320_save_history_storage.py"
Cohesion: 0.36
Nodes (6): _records(), test_save_history_closes_storage_it_creates(), close(), __init__(), test_save_history_reuses_caller_storage_without_closing(), __init__()

### Community 98 - "test_321_auto_redeploy.py"
Cohesion: 0.39
Nodes (5): _flat_engine(), test_no_redeploy_when_any_position_open(), test_redeploy_logs_once_per_flat_episode(), test_switch_off_does_not_redeploy(), test_switch_on_default_redeploys_when_flat()

### Community 99 - "test_orb_day_rollover.py"
Cohesion: 0.36
Nodes (5): _minute_candles(), _tape_bar(), test_backtest_orb_range_rolls_at_utc_midnight(), test_live_orb_range_is_forming_on_a_partial_new_day(), test_live_orb_range_rolls_at_utc_midnight()

### Community 101 - "test_318_system_config_untracked.py"
Cohesion: 0.53
Nodes (3): _git(), test_system_config_is_ignored_by_git(), test_system_config_is_untracked_but_present_on_disk()

### Community 104 - "_referenced_classes"
Cohesion: 0.33
Nodes (3): _class_value_tokens(), _referenced_classes(), _string_literals()

### Community 108 - "cursors/index.tsx"
Cohesion: 0.20
Nodes (14): clearOverlapTransitionStyles(), drawPriceChart(), invalidateCanvasSizeCache(), locateMouseAndRefreshChart(), refreshScrollAreaFades(), setIntelSortMode(), setLgWallpaper(), setRightTab() (+6 more)

### Community 114 - "test_gui_item7.py"
Cohesion: 0.18
Nodes (11): build_engine_view_model(), _rankings(), test_manual_evolve_does_not_block_bridge(), test_run_loads_config_once_and_uses_window_title_constant(), test_setup_status_never_returns_gemini_key(), test_shutdown_closes_window_on_calling_thread(), test_view_model_does_not_fabricate_take_profit(), test_view_model_reports_unknown_mc_and_quota() (+3 more)

### Community 138 - "LiveArenaEngine"
Cohesion: 0.07
Nodes (24): LiveArenaEngine, test_signal_exit_fast_path_closes_under_hold_cash(), test_v24_track_d_view_model_sanitizes_mc_stats_and_dev_bat_structure(), test_stale_engine_save_session_state_refused(), test_close_ticket_bypasses_veto_and_gates_under_hold_cash(), _quote(), test_generate_fallback_bars_deleted(), test_is_quote_fresh() (+16 more)

### Community 139 - "fix_item5_patch.py"
Cohesion: 0.11
Nodes (27): addChartBeacon(), attachToastInteractions(), checkOnboardingBoot(), clearSplashTimers(), createPositionClosedToastElement(), createPositionToastElement(), dismissToast(), enqueueToast() (+19 more)

### Community 146 - "Choreography"
Cohesion: 0.29
Nodes (6): 1. Launch Packaged Desktop Executable (`.exe`), 2. Run Self-Test Verification, 3. Run Automated Unit Test Suite (32 Tests), 4. Build Standalone Windows Executable, Quick Start Guide, TradeBot0: Multi-Agent Paper Trading & Genetic Evolution Arena (BTC/USD)

## Knowledge Gaps
- **47 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `LiveArenaEngine` connect `LiveArenaEngine` to `test_debug_optimize_regression.py`, `test_v200_fixes.py`, `BrokerSim`, `ArenaDashboard`, `OrderSide`, `ViewModelPublisher`, `GeminiClient`, `.get_ui_state`, `Leaderboard`, `test_phase3_ingestion.py`, `test_performance_and_optimizations.py`, `MonteCarloOddsEvaluator`, `test_performance_and_optimizations.py`, `CandleBar`, `ConfigManager`, `test_live_engine.py`, `threading`, `test_debug_report_fixes.py`, `ArenaStorage`, `test_live_chop_gate.py`, `LiveStrategyRunnerMixin`, `test_autosave_35.py`, `soak_engine.py`, `test_auto_evolve_fires_on_closed_trades`, `MultiTimeframeEngine`, `StreamingCryptoFeed`, `MacroCommander`, `test_phase3_soak.py`, `._build_snapshot_locked`, `LiveQuote`, `controls/index.ts`, `test_v260_debug_and_optimize.py`, `SessionCodecMixin`, `test_snapshot_counters_37.py`, `.bootstrap_intraday_session`, `test_chop_gate_seed.py`, `test_507_candle_write_on_close.py`, `test_orb_anchor_34.py`, `test_502_ui_state_delta.py`, `persistence.py`, `test_321_auto_redeploy.py`, `test_orb_day_rollover.py`, `._handle_ws_quote`, `.is_fresh`, `test_gui_item7.py`?**
  _High betweenness centrality (0.167) - this node is a cross-community bridge._
- **Are the 10 inferred relationships involving `LiveArenaEngine` (e.g. with `Architectural Highlights` and `ViewModelPublisher`) actually correct?**
  _`LiveArenaEngine` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Should `.chat_json` be split into smaller, more focused modules?**
  _Cohesion score 0.0990990990990991 - nodes in this community are weakly interconnected._
- **Why does `GeminiClient` connect `GeminiClient` to `.chat_json`, `test_debug_optimize_regression.py`, `test_v200_fixes.py`, `test_forum_collector.py`, `BrokerSim`, `LiveArenaEngine`, `OrderSide`, `IntelligenceHarvester`, `test_gemini_client_quota_fastpath_sse_error_and_timeout`, `test_phase3_ingestion.py`, `test_performance_and_optimizations.py`, `test_v252_ui_fixes.py`, `test_llm_concurrent_sessions.py`, `test_llm_json_mode_fallback.py`, `DeduplicationBuffer`, `MacroCommander`, `test_quota_pct_has_no_invented_denominator`, `ingestion.py`, `test_v260_debug_and_optimize.py`, `gemini_client.py`, `test_item12a_omniroute.py`, `test_digest_refresh_session.py`, `.run_digest_sync`, `test_track_c_gemini_max_concurrent_1_repair_no_deadlock`, `test_article_real_streamed_progress_and_viewmodel_delta`, `.get_ai_diagnosis`?**
  _High betweenness centrality (0.106) - this node is a cross-community bridge._
- **Are the 81 inferred relationships involving `OrderSide` (e.g. with `main()` and `BrokerSim`) actually correct?**
  _`OrderSide` has 81 INFERRED edges - model-reasoned connections that need verification._
- **Should `test_debug_optimize_regression.py` be split into smaller, more focused modules?**
  _Cohesion score 0.1323529411764706 - nodes in this community are weakly interconnected._
- **Why does `_ArenaBridgeApi` connect `_ArenaBridgeApi` to `test_performance_and_optimizations.py`, `test_debug_optimize_regression.py`, `test_update_checker.py`, `ConfigManager`, `test_v200_fixes.py`, `test_article_real_streamed_progress_and_viewmodel_delta`, `.get_ai_diagnosis`, `test_v260_debug_and_optimize.py`, `test_save_launch_progress.py`, `ArenaDashboard`, `test_event_article.py`, `.bootstrap_intraday_session`, `test_ui_contract.py`, `test_gui_item7.py`, `gemini_client.py`, `test_v252_ui_fixes.py`, `MacroCommander`, `test_performance_and_optimizations.py`?**
  _High betweenness centrality (0.056) - this node is a cross-community bridge._