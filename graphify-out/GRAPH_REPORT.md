# Graph Report - win_wt  (2026-11-25)

## Corpus Check
- 131 files · ~176,840 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 12 file(s) not represented in the graph (top: (none) 5, .iss 1, .lnk 1)

## Summary
- 2568 nodes · 7489 edges · 153 communities (106 shown, 47 thin omitted)
- Extraction: 88% EXTRACTED · 12% INFERRED · 0% AMBIGUOUS · INFERRED: 902 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `15bbc791`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- renderIntelHub
- _symbols_from_registry
- test_update_checker.py
- test_v200_fixes.py
- TimeMachineArena
- test_v260_debug_and_optimize.py
- test_forum_collector.py
- BrokerSim
- getCommandPaletteItems
- .chat_json
- ArenaDashboard
- OrderSide
- IntelligenceHarvester
- LiveArenaEngine
- view_model.py
- test_phase2_omniroute_client.py
- Portfolio
- _ArenaBridgeApi
- GeminiClient
- test_live_engine.py
- GeneticEvolver
- syncAppShellInert
- test_phase3_ingestion.py
- soak_engine.py
- Stage
- test_v250_fixes.py
- test_ui_contract.py
- live_engine.py
- MonteCarloOddsEvaluator
- main
- test_track_c_gemini_max_concurrent_1_repair_no_deadlock
- conftest.py
- ConfigManager
- test_generation_fence.py
- _SliceableDeque
- Any
- test_debug_report_fixes.py
- ArenaStorage
- test_save_launch_progress.py
- test_ai_panels_frontend.py
- test_event_article.py
- test_live_chop_gate.py
- test_ws_feed.py
- test_508_chop_gate.py
- LiveStrategyRunnerMixin
- time
- test_intel_stream_redesign.py
- test_llm_json_mode_fallback.py
- soak_engine.py
- DeduplicationBuffer
- test_505_leaderboard_cache.py
- MultiTimeframeEngine
- test_evolution.py
- MacroCommander
- renderIntelHub
- test_phase3_soak.py
- .get_intel_hub_telemetry
- test_intel_hub_layout.py
- renderAll
- test_news_freshness.py
- ._build_snapshot_locked
- openSetupWizardModal
- LiveQuote
- controls/index.ts
- Any
- macro_commander.py
- ArenaStorage
- SessionCodecMixin
- QuoteManager
- test_ui_feedback.py
- gemini_client.py
- .bootstrap_intraday_session
- ingestion.py
- test_chop_gate_seed.py
- .check_health
- test_card_reorder_anim.py
- test_507_candle_write_on_close.py
- threading
- StreamingCryptoFeed
- test_weighted_sentiment.py
- threading
- test_item12a_omniroute.py
- FakeWS
- test_orb_anchor_34.py
- test_502_ui_state_delta.py
- RawEvent
- _mock_resp
- test_phase2g_graphics.py
- re
- test_321_auto_redeploy.py
- test_orb_day_rollover.py
- _open_short
- test_318_system_config_untracked.py
- test_telemetry_no_articles.py
- test_ui_optimization_v26.py
- _open_long
- leaderboard.py
- .fetch_from_registry
- drawPriceChart
- test_leaderboard_metrics.py
- test_competitors.py
- .compute_r_multiple_qty
- test_performance_and_optimizations.py
- .refresh_digest_async
- test_snapshot_counters_37.py
- test_gemini_client_quota_fastpath_sse_error_and_timeout
- test_v287_render_guards.py
- test_ws_start_stop_delivers_then_stops
- _apply_window_icon
- test_bootstrap_hydrates_fresh_sqlite_candles
- test_app_icon.py
- .run
- .stop
- fix_item5_patch.py
- _referenced_classes
- CompetitorStats
- .compute_weighted_sentiment
- _FakeThread
- .get_ai_diagnosis
- test_319_src_ai_gone.py
- Choreography
- test_blank_save_allows_standby_mode
- _destroy_win32_hicons
- _StubGateway

## God Nodes (most connected - your core abstractions)
1. `LiveArenaEngine` - 215 edges
2. `OrderSide` - 154 edges
3. `GeminiClient` - 112 edges
4. `BrokerSim` - 110 edges
5. `OrderTicket` - 102 edges
6. `Portfolio` - 102 edges
7. `MacroCommander` - 97 edges
8. `OrderType` - 74 edges
9. `ExecutionReason` - 70 edges
10. `_ArenaBridgeApi` - 68 edges

## Surprising Connections (you probably didn't know these)
- `Architectural Highlights` --references--> `GeneticEvolver`  [INFERRED]
  README.md → src/arena/evolution.py
- `Architectural Highlights` --references--> `CompetitorGenome`  [INFERRED]
  README.md → src/competitors/base.py
- `Architectural Highlights` --references--> `LiveArenaEngine`  [INFERRED]
  README.md → src/data/live_engine.py
- `Architectural Highlights` --references--> `BrokerSim`  [INFERRED]
  README.md → src/arena/broker_sim.py
- `test_last_records_class_default_present()` --uses--> `GeneticEvolver`  [INFERRED]
  tests/test_311_last_records.py → src/arena/evolution.py

## Import Cycles
- None detected.

## Communities (153 total, 47 thin omitted)

### Community 0 - "renderIntelHub"
Cohesion: 0.10
Nodes (28): buildIntelEventCard(), clearIntelSearch(), clearOverlapTransitionStyles(), handleAiPrefsChanged(), initIntelFilterControls(), intelEventKey(), invalidateCanvasSizeCache(), isReducedMotionPreferred() (+20 more)

### Community 2 - "test_update_checker.py"
Cohesion: 0.08
Nodes (24): _check(), check_for_updates(), _compare_prerelease(), compare_versions(), get_manifest_url(), _is_date_version(), test_track_c_update_checker_rejects_non_https_and_clears_download_url_when_up_to_date(), _mock_response() (+16 more)

### Community 3 - "test_v200_fixes.py"
Cohesion: 0.09
Nodes (25): ExecutionReason, AggressiveCompetitor, BaseCompetitor, CompetitorGenome, ConservativeCompetitor, ORBCompetitor, SessionMeanPullbackCompetitor, TrailingGuardCompetitor (+17 more)

### Community 6 - "TimeMachineArena"
Cohesion: 0.12
Nodes (13): CandleBar, TimeMachineArena, _fixture_bars(), _bars(), test_backtest_slippage_uses_measured_atr(), _bars(), _fixture_bars(), test_evolution_tournament_runs_multiple_generations() (+5 more)

### Community 7 - "test_v260_debug_and_optimize.py"
Cohesion: 0.09
Nodes (13): _safe_fmt_hms(), configure_logging(), get_log_dir(), _SafeRotatingFileHandler, _flush_file_handlers(), _remove_test_handlers(), test_configure_logging_never_raises_on_unwritable_dir(), test_get_log_dir_resolution() (+5 more)

### Community 8 - "test_forum_collector.py"
Cohesion: 0.14
Nodes (13): parse_stocktwits_stream(), _registry_mock_get(), _stream_json(), test_fetch_from_registry_dispatches_by_type_and_skips_forum(), test_forum_batch_scored_without_llm_when_offline(), mock_get(), test_forum_collector_stocktwits_flow_and_cadence(), mock_get() (+5 more)

### Community 9 - "BrokerSim"
Cohesion: 0.08
Nodes (32): BrokerSim, OrderTicket, test_submit_order_returns_none_when_apply_fill_fails(), test_broker_sim_bracket_stop_loss_trigger(), test_broker_sim_leverage_liquidation_long_crash(), test_broker_sim_leverage_liquidation_protection(), test_broker_sim_multi_portfolio_simultaneous_execution(), test_broker_sim_position_cap_enforcement() (+24 more)

### Community 10 - "getCommandPaletteItems"
Cohesion: 0.13
Nodes (22): createPositionClosedToastElement(), createPositionToastElement(), cycleBackdropMode(), escapeHtml(), exportTradeJournal(), getCommandPaletteItems(), hexToRgba(), initCommandPalette() (+14 more)

### Community 11 - ".chat_json"
Cohesion: 0.15
Nodes (5): _extract_gemini_detail_signals(), _consume_sse_frame(), _emit(), _looks_like_format_rejection(), _parse_duration_seconds()

### Community 12 - "ArenaDashboard"
Cohesion: 0.08
Nodes (19): ArenaDashboard, __getattr__(), test_track_c_save_and_launch_aborts_if_key_save_fails(), test_track_d_dashboard_save_launch_aborts_on_key_sync_failure(), test_track_d_reset_engine_preserves_fills_after_bootstrap_completes(), test_v24_track_b_live_engine_custom_llm_url_and_reset_broker_binding(), test_v24_track_c_gemini_header_and_save_no_split_brain(), test_setup_status_has_no_gateway_auto_spawn_option() (+11 more)

### Community 14 - "OrderSide"
Cohesion: 0.11
Nodes (20): __getattr__(), OrderSide, OrderStatus, OrderType, PositionSide, RiskGuard, _open_long(), test_apply_fill_value_error_does_not_kill_cadence() (+12 more)

### Community 15 - "IntelligenceHarvester"
Cohesion: 0.09
Nodes (12): IntelligenceHarvester, test_process_batch_carries_tier_thread_and_consensus(), _run(), test_process_batch_fallback_consensus_from_score(), _run(), _fallback_structured(), _run(), test_keyword_word_boundaries_no_substring_false_positives() (+4 more)

### Community 16 - "LiveArenaEngine"
Cohesion: 0.07
Nodes (27): LiveArenaEngine, test_bootstrap_resets_live_trading_state_when_orders_disabled(), test_signal_exit_fast_path_closes_under_hold_cash(), _engine(), test_autosave_does_not_fire_when_stopped_or_superseded(), test_crash_like_stop_leaves_restorable_autosave(), test_evolution_marks_autosave_pending_and_it_fires_immediately(), test_periodic_autosave_writes_snapshot_when_interval_elapses() (+19 more)

### Community 17 - "view_model.py"
Cohesion: 0.11
Nodes (16): _build_activity_heatmap(), _build_engine_view_model_impl(), _build_risk_telemetry(), _clone_json_tree(), _downsample_equity_history(), _safe_fmt_hms(), _safe_genome_params(), _safe_int_val() (+8 more)

### Community 18 - "test_phase2_omniroute_client.py"
Cohesion: 0.10
Nodes (22): compute_backoff(), extract_json(), _mock_429_session(), _mock_resp(), test_chat_json_all_retries_429_returns_none(), _run(), test_chat_json_per_call_timeout_override(), _run() (+14 more)

### Community 19 - "Portfolio"
Cohesion: 0.08
Nodes (25): Architectural Highlights, FillEvent, Portfolio, test_track_a_leaderboard_caches_flat_portfolio(), test_track_a_portfolio_cross_gen_leverage_partial_close_conserves_equity(), test_track_a_portfolio_failed_fill_does_not_corrupt_fees(), test_track_b_non_integer_cadence_advances_slots(), test_track_b_quote_feeds_rejects_non_positive_and_non_finite() (+17 more)

### Community 21 - "GeminiClient"
Cohesion: 0.13
Nodes (11): GeminiClient, _shutting_down(), test_success_counted_only_after_parseable_json(), _run(), test_gemini_client_200_ok(), _run(), test_gemini_client_429_then_200(), _run() (+3 more)

### Community 22 - "test_live_engine.py"
Cohesion: 0.06
Nodes (34): _drive(), _drive_fixed(), _fixture_bars(), _quote(), _startup_engine_long(), test_anti_churn_cooldown_prevents_same_timestamp_reentry(), test_auto_evolve_fires_on_closed_trades(), test_auto_evolve_timer_and_toggle() (+26 more)

### Community 24 - "GeneticEvolver"
Cohesion: 0.12
Nodes (10): GeneticEvolver, _records(), test_save_history_closes_storage_it_creates(), close(), __init__(), test_save_history_reuses_caller_storage_without_closing(), __init__(), test_evolution_save_history_decoupled_from_lock() (+2 more)

### Community 25 - "syncAppShellInert"
Cohesion: 0.10
Nodes (26): blurActiveFocus(), closeCommandPalette(), closeResetModal(), closeSetupWizardModal(), closeShutdownModal(), closeStrategyDetailModal(), closeWizardCloseConfirm(), confirmCloseWizardWithoutSaving() (+18 more)

### Community 26 - "test_phase3_ingestion.py"
Cohesion: 0.18
Nodes (13): _fake_registry_response(), _new_harvester(), _registry_get_ok(), _rss_and_atom_payloads(), test_feed_registry_completeness_r3(), test_fetch_from_registry_parses_real_rss_xml(), _recording_get(), test_fetch_from_registry_skips_bad_sources() (+5 more)

### Community 27 - "soak_engine.py"
Cohesion: 0.12
Nodes (12): ETHFeed, _bar(), _ccxt_ohlcv(), test_fetch_dataframe_both_sources_fail_raises(), test_fetch_dataframe_falls_back_to_ccxt_kraken(), test_fetch_historical_bars_yahoo_multiindex_columns(), test_fetch_historical_bars_yahoo_success(), test_generate_signal_real_path_setups_and_exits() (+4 more)

### Community 28 - "Stage"
Cohesion: 0.05
Nodes (43): animCandles, changeEvolveInterval(), chartBeacons, currentSplashSteps, EVOLVE_INTERVAL_OPTIONS, fillRoundRect(), initialSplashSteps, INTEL_KNOWN_TICKERS (+35 more)

### Community 29 - "test_v250_fixes.py"
Cohesion: 0.07
Nodes (11): _get_assets_dir(), probe_gemini_api_key(), test_gemini_key_probe_http_responses(), test_gemini_key_probe_validation_defensive(), test_ui_assets_art_jargon_and_cjk_cleanliness(), test_wizard_close_confirm_dialog(), test_wizard_vertical_content_sized_layout(), test_key_rate_limit_429_is_not_verified() (+3 more)

### Community 30 - "test_ui_contract.py"
Cohesion: 0.15
Nodes (15): _badge_cls_producer_values(), _bridge_class_node(), _bridge_methods(), _bridge_obj_calls(), _bridge_self_calls(), _defined_classes(), _html_ids(), _js_defined_functions() (+7 more)

### Community 31 - "live_engine.py"
Cohesion: 0.11
Nodes (4): parse_symbol_pairs(), _raise_no_network(), test_live_loop_triggers_periodic_autosave(), _ticker_msg()

### Community 32 - "MonteCarloOddsEvaluator"
Cohesion: 0.17
Nodes (8): MonteCarloBracketOdds, MonteCarloOddsEvaluator, test_track_b_timemachine_rejects_wrong_side_tp(), test_v24_track_b_timemachine_single_sim_and_flat_empirical_candles(), test_monte_carlo_ev_gate_odds_evaluation(), test_monte_carlo_without_numpy_reports_unknown(), test_v200_31_33_mixins_and_timemachine_student_t(), test_v200_bug08_macro_tp_expansion_scales_actual_ticket_distance()

### Community 33 - "main"
Cohesion: 0.18
Nodes (6): check_and_ensure_environment(), main(), _set_windows_app_user_model_id(), close_native_splash(), test_close_native_splash_safe_and_calls_pyi_splash(), test_splash_logo_png_and_build_wiring()

### Community 34 - "test_track_c_gemini_max_concurrent_1_repair_no_deadlock"
Cohesion: 0.09
Nodes (10): test_track_c_gemini_max_concurrent_1_repair_no_deadlock(), __init__(), post(), _FakeCM, _FakeResp, test_gemini_client_rest_payload_thought_skipping_and_block_reason(), _run(), test_gemini_client_sse_streaming_and_real_error_code() (+2 more)

### Community 36 - "ConfigManager"
Cohesion: 0.09
Nodes (9): ConfigManager, _extract_env_var_from_file(), test_track_c_config_manager_preserves_existing_config_on_write_error(), test_config_manager_atomic_recovery_from_corruption(), test_config_manager_gemini_key_persistence(), test_config_manager_input_sanitization(), test_config_manager_legacy_omniroute_migration_once(), test_config_manager_ai_preferences_roundtrip() (+1 more)

### Community 38 - "test_generation_fence.py"
Cohesion: 0.17
Nodes (6): _keyframes_block(), test_splash_overlay_is_lightened_not_removed(), test_stale_engine_evolve_now_refused(), test_stale_engine_harvest_fills_refused(), test_stale_engine_save_session_state_refused(), test_stale_engine_state_publish_skipped()

### Community 40 - "Any"
Cohesion: 0.10
Nodes (5): _dedup_tickers(), _runner(), _on_progress(), MacroRegimeState, test_ingestion_zero_count_and_macro_safe_timestamp()

### Community 41 - "test_debug_report_fixes.py"
Cohesion: 0.09
Nodes (12): _fixture_bars(), _raise_no_network(), test_cooperative_stop_event(), test_full_restore_bootstrap_start_integration(), test_get_ui_state_mutation_isolation(), test_offline_start_does_not_execute_stale_candles(), test_session_save_and_restore_with_locked_margin(), test_slow_bootstrap_stop_safety() (+4 more)

### Community 42 - "ArenaStorage"
Cohesion: 0.24
Nodes (8): wrapper(), _candle(), test_p2_concurrent_candle_writes_all_persist(), writer(), test_p2_engine_stop_closes_storage_and_restart_still_writes(), test_p2_persistent_connection_recovers_from_stale_handle(), test_p2_persistent_connection_reused_and_candle_persists_across_close(), test_p2_save_candle_is_fast_with_persistent_connection()

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
Cohesion: 0.16
Nodes (7): _run_feed(), test_ws_clean_server_close_counts_as_reconnect(), test_ws_connect_and_stream_delivers_quotes(), _on_quote(), test_ws_reconnect_backoff_on_disconnect(), _fake_connect(), _fake_sleep()

### Community 48 - "test_508_chop_gate.py"
Cohesion: 0.18
Nodes (9): efficiency_ratio(), _bar(), _choppy_bars(), test_efficiency_ratio_unit(), test_gate_blocks_entries_on_choppy_tape(), test_gate_inactive_on_trend_tape(), test_gate_never_blocks_closes(), _total_closed() (+1 more)

### Community 50 - "time"
Cohesion: 0.26
Nodes (13): check_binance_rest(), check_binance_ws(), _run(), check_ccxt_kraken(), check_coinbase_rest(), check_feed_registry(), check_gemini_health(), check_kraken_rest() (+5 more)

### Community 51 - "test_intel_stream_redesign.py"
Cohesion: 0.21
Nodes (16): _fn_body(), _html(), _js(), test_article_failure_shows_reason_not_summary(), test_article_lazy_once_and_cached(), test_article_loading_shows_determinate_stage_progress_bar(), test_article_render_is_not_rewritten_every_tick(), test_articles_preload_while_collapsed() (+8 more)

### Community 53 - "test_llm_json_mode_fallback.py"
Cohesion: 0.18
Nodes (7): _client_with(), _CM, _FakeSession, _Resp, test_generic_400_does_not_trigger_the_format_retry(), test_rejected_format_is_remembered_for_later_calls(), test_rejected_response_format_retries_without_it_and_parses()

### Community 54 - "soak_engine.py"
Cohesion: 0.15
Nodes (14): closing_fills_since(), db_stats(), do_slice(), genome_valid(), main(), _sample(), make_quote(), _parse_args() (+6 more)

### Community 55 - "DeduplicationBuffer"
Cohesion: 0.20
Nodes (5): _dedup_normalize_title(), DeduplicationBuffer, test_v24_track_c_gemini_extract_json_retry_hint_dedup_and_https_redirect(), test_deduplication_buffer(), test_ingestion_clean_html_strips_script_style_and_dedup_forget()

### Community 56 - "test_505_leaderboard_cache.py"
Cohesion: 0.20
Nodes (10): Leaderboard, _counting_periods(), _portfolio_with_history(), test_fill_invalidates_cache(), test_metrics_cached_across_ticks_with_no_fills(), test_replace_equity_history_invalidates_cache(), test_reset_invalidates_cache(), test_risk_free_rate_change_invalidates_cache() (+2 more)

### Community 57 - "MultiTimeframeEngine"
Cohesion: 0.07
Nodes (16): IndicatorEngineMixin, MultiTimeframeEngine, test_track_b_mtf_engine_delta_volume_and_neutral_on_conflict(), test_v24_track_b_mtf_seed_1h_merges_same_slot(), _buckets(), _hourly_bars(), _minute_bars(), test_engine_seed_fetch_failure_stays_neutral() (+8 more)

### Community 58 - "test_evolution.py"
Cohesion: 0.14
Nodes (11): test_evolve_generation_early_return_does_not_crash(), _ranked_three(), test_evolution_parents_are_fitness_first_not_equity_first(), test_evolution_seed_recorded_in_history(), test_evolved_genomes_all_valid(), test_generation_seed_is_deterministic_and_recorded(), _run_once(), test_runner_up_is_fine_tuned_not_copied() (+3 more)

### Community 60 - "MacroCommander"
Cohesion: 0.08
Nodes (23): StructuredEvent, MacroCommander, test_synthesize_plumbs_raw_snippet(), test_sync_status_failed_when_gateway_down(), _mock_commander(), test_fallback_thresholds_do_not_veto_on_single_word(), _run(), test_llm_numeric_parsing_never_raises() (+15 more)

### Community 61 - "renderIntelHub"
Cohesion: 0.24
Nodes (12): cleanIntelSummary(), formatIntelEventTime(), hashTickerName(), intelArticleBodyEl(), renderIntelArticle(), requestIntelArticle(), startIntelArticleProgressPoll(), stopIntelArticleProgressPoll() (+4 more)

### Community 62 - "test_phase3_soak.py"
Cohesion: 0.24
Nodes (5): _bootstrapped_engine(), _load_soak_helpers(), soak(), test_p3_breaker_trips_force_closes_and_resets_on_evolve(), test_p3_mini_soak_many_ticks_no_growth_blowup()

### Community 63 - ".get_intel_hub_telemetry"
Cohesion: 0.17
Nodes (5): test_quota_pct_has_no_invented_denominator(), _run_429(), test_quota_pct_uses_user_set_budget(), test_quota_throttling_slows_digest(), test_intel_hub_telemetry_structure()

### Community 64 - "test_intel_hub_layout.py"
Cohesion: 0.25
Nodes (12): _commander(), _css(), _js(), _mock_pipeline(), _rule(), _structured(), test_stream_loading_block_is_centered_with_meter(), test_sync_status_failed_when_feeds_down() (+4 more)

### Community 65 - "renderAll"
Cohesion: 0.13
Nodes (23): applyStratCurveHover(), buildSparklineGeometry(), canonicalStrategyKey(), fillMatchesStrategy(), fmtPct(), fmtSignedUsd(), fmtTimeSec(), fmtUsd() (+15 more)

### Community 66 - "test_news_freshness.py"
Cohesion: 0.16
Nodes (7): _first_child_text(), parse_rss_atom(), _rank_fresh_events(), test_parse_rss_atom_extracts_real_pubdate_and_atom_updated(), test_rank_fresh_events_caps_single_source_flooding_per_batch(), test_parse_atom(), test_parse_rss_20()

### Community 68 - "openSetupWizardModal"
Cohesion: 0.16
Nodes (17): applyBackdropMode(), applyPrivateBalanceUi(), checkOnboardingBoot(), clearSplashTimers(), confirmShutdown(), destroyAmbientBackdrop(), initAmbientBackdrop(), initAppBoot() (+9 more)

### Community 70 - "controls/index.ts"
Cohesion: 0.21
Nodes (10): _broker(), _commander(), test_backtest_default_sizing_is_one(), test_compute_r_multiple_qty_scales_budget_and_clamps(), test_evaluate_signal_sizing_shrinks_qty_not_sl(), test_no_confidence_means_no_sizing_effect(), test_per_strategy_sensitivity_scales_the_deviation(), test_sizing_formula_exact_values() (+2 more)

### Community 71 - "Any"
Cohesion: 0.27
Nodes (3): InterruptDebouncer, test_stage2_interrupt_debouncing_r4(), _run()

### Community 72 - "macro_commander.py"
Cohesion: 0.36
Nodes (6): build_event_article_prompts(), _event_dict(), test_prompt_includes_raw_snippet(), test_prompt_without_snippet_omits_line(), test_telemetry_strips_raw_snippet(), test_article_prompt_asks_for_1000_words_and_six_paragraphs()

### Community 73 - "ArenaStorage"
Cohesion: 0.13
Nodes (9): ArenaStorage, _retry_on_db_error(), _sanitize_json_value(), test_track_b_persistence_batch_fills_and_prune_candles(), test_phase2_sqlite_wal_persistence_and_cold_start_hydration(), test_restore_survives_garbage_stop_ticket_and_entry_ts(), test_persistence_sanitizes_nan_and_inf_strict_json(), test_session_codec_rejects_symbol_mismatch_and_roundtrips_pending_and_orb() (+1 more)

### Community 75 - "QuoteManager"
Cohesion: 0.23
Nodes (3): QuoteManager, test_dead_cascade_state_is_gone(), test_ws_quote_path_still_works()

### Community 76 - "test_ui_feedback.py"
Cohesion: 0.29
Nodes (3): _copy_text_to_clipboard_windows(), test_copy_text_to_clipboard_windows_non_windows(), test_copy_text_to_clipboard_windows_roundtrip()

### Community 77 - "gemini_client.py"
Cohesion: 0.20
Nodes (7): classify_llm_error(), _error_body_text(), _walk(), _retry_window_seconds(), test_classify_llm_error_structured_gemini_429_and_spend_cap(), test_chat_json_400_format_rejection_is_not_quota(), _run()

### Community 78 - ".bootstrap_intraday_session"
Cohesion: 0.09
Nodes (4): _on_done(), test_pause_feed_updates_ui_snapshot_immediately(), _drive(), test_live_engine_toggle_pause_and_auto_evolve_shift_math()

### Community 80 - "ingestion.py"
Cohesion: 0.11
Nodes (7): _clean_key_input(), _clean_html_text(), _parse_feed_ts(), _parse_iso_ts(), parse_polymarket_events(), parse_reddit_posts(), test_feed_numeric_parsing_never_raises()

### Community 82 - "test_chop_gate_seed.py"
Cohesion: 0.29
Nodes (10): _engine(), _feed_1m(), _tape_end_anchored(), _tape_slot_aligned(), test_seed_helper_feeds_continuous_chain_and_arms_gate(), test_seed_helper_gap_truncates_to_suffix_after_gap(), test_seed_helper_malformed_row_skipped_not_fabricated(), test_seed_helper_misaligned_or_empty_seeds_nothing() (+2 more)

### Community 83 - ".check_health"
Cohesion: 0.12
Nodes (6): resolve_gemini_model(), test_gemini_client_check_health_and_update_api_key(), _run(), test_resolve_gemini_model_aliases(), test_gemini_client_env_guards_model_reset_and_sse_long_lines(), _collect()

### Community 84 - "test_card_reorder_anim.py"
Cohesion: 0.35
Nodes (10): _css(), _js(), _reorder_block(), test_cards_are_stable_nodes_never_recreated_on_reorder(), test_flip_cleanup_clears_class_and_transform(), test_flip_inverts_with_translate_and_plays_via_class(), test_flip_records_first_rects_before_moving_nodes(), test_flip_runs_only_when_order_changes() (+2 more)

### Community 85 - "test_507_candle_write_on_close.py"
Cohesion: 0.42
Nodes (7): _counting_save(), _engine(), test_bar_close_persists_final_bar_once(), test_closed_bar_is_in_sqlite_after_close(), test_out_of_order_tick_does_not_double_save(), test_three_minutes_persist_two_closed_bars(), test_ticks_within_one_minute_write_nothing()

### Community 86 - "threading"
Cohesion: 0.07
Nodes (18): test_manual_evolve_does_not_block_bridge(), test_shutdown_closes_window_on_calling_thread(), test_four_threads_expand_concurrently_without_closing_each_other(), _one(), _worker(), _OKHandler, _quote(), _safe_refresh() (+10 more)

### Community 87 - "StreamingCryptoFeed"
Cohesion: 0.20
Nodes (3): StreamingCryptoFeed, test_phase1_websocket_feed_parsing_and_fast_path_fallback(), test_parse_binance_ticker_rejects_garbage()

### Community 88 - "test_weighted_sentiment.py"
Cohesion: 0.23
Nodes (17): _dead_gateway_commander(), _mock_pipeline(), _structured(), test_sync_status_done_when_dead_gateway_still_yields_fallback_digest(), test_sync_status_failed_when_gateway_dead_and_nothing_produced(), _ev(), _now_iso(), _offline_commander() (+9 more)

### Community 89 - "threading"
Cohesion: 0.10
Nodes (8): _FakeCM, _FakeForum, _FakeHarvester, _FakeResp, _FakeSession, _make_commander(), test_concurrent_article_call_survives_refresh(), test_two_refreshes_leave_session_open()

### Community 90 - "test_item12a_omniroute.py"
Cohesion: 0.23
Nodes (7): _now_iso(), _offline_commander(), _strong_bearish_events(), test_empty_digest_expires_stale_fallback(), test_fallback_clears_when_llm_recovers(), test_fallback_regime_is_marked_and_expires(), test_regime_state_dict_exposes_fallback()

### Community 92 - "test_orb_anchor_34.py"
Cohesion: 0.22
Nodes (4): _tape_bar(), test_backtest_orb_range_anchored_to_first_15_tape_bars(), test_live_orb_range_does_not_drift_with_rolling_buffer(), _warmup_bars()

### Community 93 - "test_502_ui_state_delta.py"
Cohesion: 0.39
Nodes (5): _engine(), _snapshot(), test_deepcopy_never_receives_heavy_arrays_on_unchanged_poll(), test_delta_is_still_a_defensive_copy(), test_delta_output_identical_to_old_path()

### Community 94 - "RawEvent"
Cohesion: 0.16
Nodes (5): ForumCollector, RawEvent, test_forum_collector_fast_test_short_circuits(), test_forum_collector_hourly_cap(), test_dedup_hits_counted_not_token_estimate()

### Community 95 - "_mock_resp"
Cohesion: 0.31
Nodes (10): _coinbase_stats_payload(), _coinbase_ticker_payload(), _kraken_payload(), _mock_resp(), test_binance_quote_success_parses_all_fields(), test_coinbase_quote_success_parses(), test_kraken_quote_success_parses(), dispatch() (+2 more)

### Community 96 - "test_phase2g_graphics.py"
Cohesion: 0.31
Nodes (4): _js(), test_p2g_chart_loop_capped_at_60fps(), test_p2g_hidden_view_stops_chart_loop(), test_p2g_no_temporary_probe_left_in_shipped_assets()

### Community 97 - "re"
Cohesion: 0.20
Nodes (11): _compile_word_group(), _compiled_word_re(), _contains_word(), test_splash_toast_catchup_present_with_restored_guard(), _css(), _css_block(), test_article_renders_with_fade_in(), test_chevron_and_accordion_spring() (+3 more)

### Community 98 - "test_321_auto_redeploy.py"
Cohesion: 0.39
Nodes (5): _flat_engine(), test_no_redeploy_when_any_position_open(), test_redeploy_logs_once_per_flat_episode(), test_switch_off_does_not_redeploy(), test_switch_on_default_redeploys_when_flat()

### Community 99 - "test_orb_day_rollover.py"
Cohesion: 0.36
Nodes (5): _minute_candles(), _tape_bar(), test_backtest_orb_range_rolls_at_utc_midnight(), test_live_orb_range_is_forming_on_a_partial_new_day(), test_live_orb_range_rolls_at_utc_midnight()

### Community 100 - "_open_short"
Cohesion: 0.20
Nodes (5): _open_short(), test_evaluate_live_strategies_short_exits_are_signal_only(), test_evaluate_live_strategies_small_gain_does_not_close_shorts(), test_stagnation_exit_closes_after_40m(), test_trailing_guard_short_ratchet_moves_stop_down()

### Community 101 - "test_318_system_config_untracked.py"
Cohesion: 0.33
Nodes (5): _git(), test_system_config_is_ignored_by_git(), test_system_config_is_untracked_but_present_on_disk(), test_p2_eth_feed_first_fetch_loads_pandas_and_behaves(), test_p2_eth_feed_import_does_not_import_pandas()

### Community 102 - "test_telemetry_no_articles.py"
Cohesion: 0.53
Nodes (4): _commander_with_expanded_events(), test_article_lock_map_stays_bounded(), test_on_demand_article_is_intact_after_the_snapshot(), test_snapshot_carries_no_article_bodies()

### Community 104 - "test_ui_optimization_v26.py"
Cohesion: 0.15
Nodes (4): _build_html_template(), _load_asset(), _load_binary_data_uri(), test_grainient_webp_asset_and_inline_injection()

### Community 105 - "_open_long"
Cohesion: 0.33
Nodes (3): _open_long(), test_bracket_take_profit_closes_via_on_tick(), test_evaluate_live_strategies_small_gain_does_not_close_longs()

### Community 106 - "leaderboard.py"
Cohesion: 0.20
Nodes (6): test_evolve_now_with_fewer_than_two_rankings_does_not_raise(), test_last_records_class_default_present(), _breakeven_portfolio(), test_breakeven_close_counts_as_closed_trade(), test_breakeven_close_keeps_win_rate_decided_only(), test_breakeven_count_resets()

### Community 107 - ".fetch_from_registry"
Cohesion: 0.15
Nodes (3): test_fetch_live_feeds_still_returns_test_fixtures(), test_fetch_from_registry_filters_stale_articles_and_sorts_newest_first(), test_p2_fetch_from_registry_parallel_same_events_faster()

### Community 108 - "drawPriceChart"
Cohesion: 0.50
Nodes (8): drawPriceChart(), formatChartReadoutLabel(), getActiveChartSeries(), locateMouseAndRefreshChart(), setChartTimeframe(), setLgWallpaper(), setupChartInteraction(), updateChartMouseHover()

### Community 109 - "test_leaderboard_metrics.py"
Cohesion: 0.22
Nodes (5): _portfolio_with_history(), test_annualization_period_is_named_constant_with_documented_convention(), test_rankings_handles_undefined_sortino(), test_sortino_no_downside_returns_is_not_invented(), test_sortino_with_losses_is_real_downside_deviation()

### Community 111 - "test_competitors.py"
Cohesion: 0.21
Nodes (6): _fresh_broker_competitor(), _r_multiple(), test_evaluate_signal_returns_none_when_breaker_tripped_all_strategies(), test_evaluate_signal_short_entries_mirror_long_brackets_all_strategies(), test_orb_competitor_box_breakout_and_r_multiple(), test_strategy_qty_zero_returns_none()

### Community 113 - ".compute_r_multiple_qty"
Cohesion: 0.11
Nodes (3): _parse_pos_dec(), _open_short(), test_short_trailing_stop_ratchets_down_then_exits_at_trailed_level()

### Community 115 - "test_performance_and_optimizations.py"
Cohesion: 0.17
Nodes (9): test_launchers_and_shortcut_integrity(), test_macro_veto_intent_preserved_in_live_evaluation(), test_phase4_mtf_trend_confluence_gatekeeper(), test_phase5_multi_objective_composite_fitness(), test_portfolio_no_duplicate_apply_fill_returns(), test_splash_logo_concentric_alignment_and_svg_zap(), test_stageshow_ui_design_system_integrity(), test_window_startup_foreground_configuration() (+1 more)

### Community 127 - ".refresh_digest_async"
Cohesion: 0.18
Nodes (4): _shutting_down(), _wrapped(), _parse_event_epoch(), test_iso_z_parsing_and_macro_quiet_cycle_skip()

### Community 130 - "test_snapshot_counters_37.py"
Cohesion: 0.27
Nodes (5): _bars(), _round_trips(), _stats_for(), test_short_history_is_not_marked_truncated(), test_snapshot_counters_survive_restore_with_truncated_history()

### Community 132 - "test_v287_render_guards.py"
Cohesion: 0.40
Nodes (7): _fn_body(), _js(), test_hub_header_writes_guarded(), test_intel_card_element_refs_cached(), test_macro_ribbon_writes_guarded(), test_spotlight_vars_written_once_per_frame(), test_strat_color_and_gen_label_writes_guarded()

### Community 133 - "test_ws_start_stop_delivers_then_stops"
Cohesion: 0.22
Nodes (3): SlowFakeWS, _fake_connect(), test_ws_start_stop_delivers_then_stops()

### Community 134 - "_apply_window_icon"
Cohesion: 0.28
Nodes (5): _apply_window_icon(), _get_app_icon_path(), _get_native_hwnd(), test_runtime_taskbar_and_html_icon_wiring(), test_run_loads_config_once_and_uses_window_title_constant()

### Community 135 - "test_bootstrap_hydrates_fresh_sqlite_candles"
Cohesion: 0.22
Nodes (3): _cache_rows(), test_bootstrap_hydrates_fresh_sqlite_candles(), test_bootstrap_rejects_stale_sqlite_candles()

### Community 137 - ".run"
Cohesion: 0.38
Nodes (4): _activate_foreground_startup(), _on_window_closing(), _on_window_shown(), _delayed_activation()

### Community 138 - ".stop"
Cohesion: 0.15
Nodes (14): build_engine_view_model(), _empty_view_model(), _rankings(), test_setup_status_never_returns_gemini_key(), test_view_model_does_not_fabricate_take_profit(), test_view_model_reports_unknown_mc_and_quota(), test_view_model_short_unrealized_pnl_pct(), test_view_model_skips_stale_ranking_entry() (+6 more)

### Community 139 - "fix_item5_patch.py"
Cohesion: 0.17
Nodes (19): addChartBeacon(), attachToastInteractions(), dismissToast(), enqueueToast(), ensureLiveTradingStarted(), pollBackend(), previewPositionAnimation(), previewPositionClosedAnimation() (+11 more)

### Community 140 - "_referenced_classes"
Cohesion: 0.33
Nodes (3): _class_value_tokens(), _referenced_classes(), _string_literals()

### Community 141 - "CompetitorStats"
Cohesion: 0.40
Nodes (3): CompetitorStats, test_composite_fitness_matches_leaderboard_fitness(), test_timemachine_frozen_report_uses_appdata_memory_dir()

### Community 146 - "Choreography"
Cohesion: 0.29
Nodes (6): 1. Launch Packaged Desktop Executable (`.exe`), 2. Run Self-Test Verification, 3. Run Automated Unit Test Suite (32 Tests), 4. Build Standalone Windows Executable, Quick Start Guide, TradeBot0: Multi-Agent Paper Trading & Genetic Evolution Arena (BTC/USD)

## Knowledge Gaps
- **47 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `LiveArenaEngine` connect `LiveArenaEngine` to `test_snapshot_counters_37.py`, `test_v200_fixes.py`, `TimeMachineArena`, `test_bootstrap_hydrates_fresh_sqlite_candles`, `test_v260_debug_and_optimize.py`, `BrokerSim`, `.stop`, `ArenaDashboard`, `OrderSide`, `view_model.py`, `Portfolio`, `GeminiClient`, `test_live_engine.py`, `soak_engine.py`, `test_v250_fixes.py`, `live_engine.py`, `MonteCarloOddsEvaluator`, `ConfigManager`, `test_generation_fence.py`, `test_debug_report_fixes.py`, `ArenaStorage`, `test_live_chop_gate.py`, `LiveStrategyRunnerMixin`, `soak_engine.py`, `MultiTimeframeEngine`, `MacroCommander`, `test_phase3_soak.py`, `._build_snapshot_locked`, `LiveQuote`, `controls/index.ts`, `ArenaStorage`, `SessionCodecMixin`, `.bootstrap_intraday_session`, `ingestion.py`, `test_chop_gate_seed.py`, `test_507_candle_write_on_close.py`, `threading`, `StreamingCryptoFeed`, `test_orb_anchor_34.py`, `test_502_ui_state_delta.py`, `_mock_resp`, `test_321_auto_redeploy.py`, `test_orb_day_rollover.py`, `_open_short`, `_open_long`, `leaderboard.py`, `.is_fresh`, `test_performance_and_optimizations.py`?**
  _High betweenness centrality (0.166) - this node is a cross-community bridge._
- **Are the 10 inferred relationships involving `LiveArenaEngine` (e.g. with `Architectural Highlights` and `ViewModelPublisher`) actually correct?**
  _`LiveArenaEngine` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Should `renderIntelHub` be split into smaller, more focused modules?**
  _Cohesion score 0.10317460317460317 - nodes in this community are weakly interconnected._
- **Why does `GeminiClient` connect `GeminiClient` to `test_v200_fixes.py`, `test_gemini_client_quota_fastpath_sse_error_and_timeout`, `test_v260_debug_and_optimize.py`, `test_forum_collector.py`, `.chat_json`, `IntelligenceHarvester`, `LiveArenaEngine`, `.get_ai_diagnosis`, `test_phase2_omniroute_client.py`, `Portfolio`, `test_v250_fixes.py`, `live_engine.py`, `test_track_c_gemini_max_concurrent_1_repair_no_deadlock`, `Any`, `test_llm_json_mode_fallback.py`, `DeduplicationBuffer`, `MacroCommander`, `.get_intel_hub_telemetry`, `gemini_client.py`, `ingestion.py`, `.check_health`, `threading`, `threading`, `test_item12a_omniroute.py`, `RawEvent`, `test_telemetry_no_articles.py`, `.fetch_from_registry`, `test_performance_and_optimizations.py`, `.refresh_digest_async`?**
  _High betweenness centrality (0.098) - this node is a cross-community bridge._
- **Are the 81 inferred relationships involving `OrderSide` (e.g. with `main()` and `BrokerSim`) actually correct?**
  _`OrderSide` has 81 INFERRED edges - model-reasoned connections that need verification._
- **Should `test_update_checker.py` be split into smaller, more focused modules?**
  _Cohesion score 0.08333333333333333 - nodes in this community are weakly interconnected._
- **Why does `OrderSide` connect `OrderSide` to `test_snapshot_counters_37.py`, `test_v200_fixes.py`, `TimeMachineArena`, `test_v260_debug_and_optimize.py`, `BrokerSim`, `.stop`, `view_model.py`, `Portfolio`, `test_live_engine.py`, `test_v250_fixes.py`, `live_engine.py`, `test_generation_fence.py`, `test_debug_report_fixes.py`, `test_live_chop_gate.py`, `LiveStrategyRunnerMixin`, `soak_engine.py`, `test_505_leaderboard_cache.py`, `MultiTimeframeEngine`, `test_evolution.py`, `MacroCommander`, `test_phase3_soak.py`, `controls/index.ts`, `SessionCodecMixin`, `ingestion.py`, `threading`, `_open_short`, `_open_long`, `leaderboard.py`, `test_competitors.py`, `.compute_r_multiple_qty`, `test_performance_and_optimizations.py`?**
  _High betweenness centrality (0.058) - this node is a cross-community bridge._