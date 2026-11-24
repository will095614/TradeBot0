# Graph Report - TradeBot0_Local  (2026-11-25)

## Corpus Check
- 131 files · ~176,699 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 11 file(s) not represented in the graph (top: (none) 4, .iss 1, .lnk 1)

## Summary
- 2567 nodes · 7487 edges · 135 communities (93 shown, 42 thin omitted)
- Extraction: 88% EXTRACTED · 12% INFERRED · 0% AMBIGUOUS · INFERRED: 900 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `f82a0e36`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- renderIntelHub
- test_debug_optimize_regression.py
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
- .bootstrap_intraday_session
- view_model.py
- test_phase2_omniroute_client.py
- FillEvent
- _ArenaBridgeApi
- GeminiClient
- test_live_engine.py
- Leaderboard
- syncAppShellInert
- test_phase3_ingestion.py
- soak_engine.py
- Stage
- dashboard.py
- re
- eth_feed.py
- MonteCarloOddsEvaluator
- test_performance_and_optimizations.py
- test_gemini_client_quota_fastpath_sse_error_and_timeout
- conftest.py
- ConfigManager
- LiveArenaEngine
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
- test_autosave_35.py
- test_gateway_setup_wizard.py
- test_llm_json_mode_fallback.py
- soak_engine.py
- DeduplicationBuffer
- test_505_leaderboard_cache.py
- MultiTimeframeEngine
- test_risk_semantics.py
- MacroCommander
- renderIntelHub
- test_phase3_soak.py
- .get_intel_hub_telemetry
- test_intel_hub_layout.py
- renderAll
- ingestion.py
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
- test_intel_veto.py
- test_chop_gate_seed.py
- .total_equity
- test_card_reorder_anim.py
- test_507_candle_write_on_close.py
- test_llm_concurrent_sessions.py
- StreamingCryptoFeed
- test_weighted_sentiment.py
- threading
- MacroRegimeState
- FakeWS
- test_orb_anchor_34.py
- test_502_ui_state_delta.py
- test_track_c_gemini_max_concurrent_1_repair_no_deadlock
- _mock_resp
- test_phase2g_graphics.py
- test_320_save_history_storage.py
- test_321_auto_redeploy.py
- test_orb_day_rollover.py
- _open_short
- test_318_system_config_untracked.py
- test_telemetry_no_articles.py
- test_312_gateway_failed.py
- _open_long
- ._handle_ws_quote
- _OKHandler
- drawPriceChart
- test_live_engine_toggle_pause_and_auto_evolve_shift_math
- .compute_r_multiple_qty
- .refresh_digest_async
- .stop
- fix_item5_patch.py
- Choreography

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

## Communities (135 total, 42 thin omitted)

### Community 0 - "renderIntelHub"
Cohesion: 0.10
Nodes (28): buildIntelEventCard(), clearIntelSearch(), clearOverlapTransitionStyles(), handleAiPrefsChanged(), initIntelFilterControls(), intelEventKey(), invalidateCanvasSizeCache(), isReducedMotionPreferred() (+20 more)

### Community 1 - "test_debug_optimize_regression.py"
Cohesion: 0.13
Nodes (6): _symbols_from_registry(), test_track_a_portfolio_cross_gen_leverage_partial_close_conserves_equity(), test_track_b_non_integer_cadence_advances_slots(), test_track_b_quote_feeds_rejects_non_positive_and_non_finite(), test_track_c_forum_collector_parses_dot_x_symbols(), test_track_d_frontend_contracts_css_html_js()

### Community 2 - "test_update_checker.py"
Cohesion: 0.07
Nodes (27): _check(), check_for_updates(), _compare_prerelease(), compare_versions(), get_manifest_url(), _is_date_version(), test_track_c_update_checker_rejects_non_https_and_clears_download_url_when_up_to_date(), _mock_response() (+19 more)

### Community 3 - "test_v200_fixes.py"
Cohesion: 0.08
Nodes (23): AggressiveCompetitor, BaseCompetitor, CompetitorGenome, ConservativeCompetitor, ORBCompetitor, SessionMeanPullbackCompetitor, TrailingGuardCompetitor, _r_multiple() (+15 more)

### Community 6 - "TimeMachineArena"
Cohesion: 0.12
Nodes (13): CandleBar, TimeMachineArena, test_backtest_slippage_uses_measured_atr(), _bars(), test_backtest_opens_shorts_on_downtrend(), test_evolution_tournament_runs_multiple_generations(), test_orb_window_excludes_current_bar(), test_timemachine_evolution_preserves_portfolio() (+5 more)

### Community 7 - "test_v260_debug_and_optimize.py"
Cohesion: 0.08
Nodes (15): configure_logging(), get_log_dir(), _SafeRotatingFileHandler, _flush_file_handlers(), _remove_test_handlers(), test_configure_logging_never_raises_on_unwritable_dir(), test_get_log_dir_resolution(), test_stream_handler_present_when_stdout_exists() (+7 more)

### Community 8 - "test_forum_collector.py"
Cohesion: 0.10
Nodes (15): ForumCollector, parse_stocktwits_stream(), _registry_mock_get(), _stream_json(), test_fetch_from_registry_dispatches_by_type_and_skips_forum(), test_forum_batch_scored_without_llm_when_offline(), mock_get(), test_forum_collector_fast_test_short_circuits() (+7 more)

### Community 9 - "BrokerSim"
Cohesion: 0.08
Nodes (39): Architectural Highlights, BrokerSim, OrderTicket, Portfolio, _open_long(), test_apply_fill_value_error_does_not_kill_cadence(), _boom(), test_submit_order_returns_none_when_apply_fill_fails() (+31 more)

### Community 10 - "getCommandPaletteItems"
Cohesion: 0.13
Nodes (22): createPositionClosedToastElement(), createPositionToastElement(), cycleBackdropMode(), escapeHtml(), exportTradeJournal(), getCommandPaletteItems(), hexToRgba(), initCommandPalette() (+14 more)

### Community 11 - ".chat_json"
Cohesion: 0.11
Nodes (7): _clean_key_input(), _extract_gemini_detail_signals(), _consume_sse_frame(), _emit(), _looks_like_format_rejection(), _parse_duration_seconds(), resolve_gemini_model()

### Community 12 - "ArenaDashboard"
Cohesion: 0.07
Nodes (21): ArenaDashboard, __getattr__(), test_track_c_save_and_launch_aborts_if_key_save_fails(), test_track_d_dashboard_save_launch_aborts_on_key_sync_failure(), test_track_d_reset_engine_preserves_fills_after_bootstrap_completes(), test_v24_track_b_live_engine_custom_llm_url_and_reset_broker_binding(), test_setup_status_has_no_gateway_auto_spawn_option(), test_manual_evolve_does_not_block_bridge() (+13 more)

### Community 14 - "OrderSide"
Cohesion: 0.09
Nodes (16): ExecutionReason, OrderSide, OrderStatus, OrderType, PositionSide, parse_symbol_pairs(), test_trade_and_equity_history_persistence(), _keyframes_block() (+8 more)

### Community 15 - "IntelligenceHarvester"
Cohesion: 0.08
Nodes (15): IntelligenceHarvester, RawEvent, test_fetch_live_feeds_still_returns_test_fixtures(), test_process_batch_carries_tier_thread_and_consensus(), _run(), test_process_batch_fallback_consensus_from_score(), _run(), _run() (+7 more)

### Community 16 - ".bootstrap_intraday_session"
Cohesion: 0.09
Nodes (10): test_signal_exit_fast_path_closes_under_hold_cash(), test_close_ticket_bypasses_veto_and_gates_under_hold_cash(), _cache_rows(), test_bootstrap_hydrates_fresh_sqlite_candles(), test_bootstrap_rejects_stale_sqlite_candles(), test_bootstrap_anchors_orb_range_to_first_15_warmup_bars(), test_session_state_save_and_restore_and_shutdown_bridge(), _fixture_bars() (+2 more)

### Community 17 - "view_model.py"
Cohesion: 0.08
Nodes (19): _build_activity_heatmap(), _build_engine_view_model_impl(), _build_risk_telemetry(), _clone_json_tree(), _downsample_equity_history(), _empty_view_model(), _safe_fmt_hms(), _safe_genome_params() (+11 more)

### Community 18 - "test_phase2_omniroute_client.py"
Cohesion: 0.10
Nodes (22): compute_backoff(), extract_json(), _mock_429_session(), _mock_resp(), test_chat_json_all_retries_429_returns_none(), _run(), test_chat_json_per_call_timeout_override(), _run() (+14 more)

### Community 19 - "FillEvent"
Cohesion: 0.19
Nodes (12): FillEvent, test_track_a_portfolio_failed_fill_does_not_corrupt_fees(), test_v24_track_a_portfolio_apply_fill_upfront_quantization(), test_bidirectional_short_win_rate_and_closing_fill(), _assert_equity_conservation(), _fill(), test_add_to_short_recomputes_avg_entry_and_margin(), test_equity_conservation_across_all_fill_cases() (+4 more)

### Community 21 - "GeminiClient"
Cohesion: 0.10
Nodes (12): GeminiClient, test_success_counted_only_after_parseable_json(), _run(), test_gemini_client_200_ok(), _run(), test_gemini_client_429_then_200(), _run(), test_gemini_client_unreachable_safe_mode() (+4 more)

### Community 22 - "test_live_engine.py"
Cohesion: 0.09
Nodes (27): _drive(), _drive_fixed(), _fixture_bars(), _quote(), _startup_engine_long(), test_auto_evolve_fires_on_closed_trades(), _round_trips(), test_auto_evolve_timer_and_toggle() (+19 more)

### Community 24 - "Leaderboard"
Cohesion: 0.05
Nodes (31): GeneticEvolver, __getattr__(), CompetitorStats, Leaderboard, test_evolve_generation_early_return_does_not_crash(), test_last_records_class_default_present(), _breakeven_portfolio(), test_breakeven_close_counts_as_closed_trade() (+23 more)

### Community 25 - "syncAppShellInert"
Cohesion: 0.10
Nodes (26): blurActiveFocus(), closeCommandPalette(), closeResetModal(), closeSetupWizardModal(), closeShutdownModal(), closeStrategyDetailModal(), closeWizardCloseConfirm(), confirmCloseWizardWithoutSaving() (+18 more)

### Community 26 - "test_phase3_ingestion.py"
Cohesion: 0.22
Nodes (11): _fake_registry_response(), _new_harvester(), _registry_get_ok(), _rss_and_atom_payloads(), test_feed_registry_completeness_r3(), test_fetch_from_registry_parses_real_rss_xml(), _recording_get(), test_fetch_from_registry_skips_bad_sources() (+3 more)

### Community 27 - "soak_engine.py"
Cohesion: 0.14
Nodes (12): ETHFeed, _bar(), _ccxt_ohlcv(), test_fetch_dataframe_both_sources_fail_raises(), test_fetch_dataframe_falls_back_to_ccxt_kraken(), test_fetch_historical_bars_yahoo_multiindex_columns(), test_fetch_historical_bars_yahoo_success(), test_generate_signal_real_path_setups_and_exits() (+4 more)

### Community 28 - "Stage"
Cohesion: 0.05
Nodes (43): animCandles, changeEvolveInterval(), chartBeacons, currentSplashSteps, EVOLVE_INTERVAL_OPTIONS, fillRoundRect(), initialSplashSteps, INTEL_KNOWN_TICKERS (+35 more)

### Community 29 - "dashboard.py"
Cohesion: 0.06
Nodes (20): _build_html_template(), _destroy_win32_hicons(), _destroy_window_hicons(), _load_asset(), _load_binary_data_uri(), test_classify_llm_error_structured_gemini_429_and_spend_cap(), test_resolve_gemini_model_aliases(), test_launchers_and_shortcut_integrity() (+12 more)

### Community 30 - "re"
Cohesion: 0.06
Nodes (52): _scanned_files(), test_no_src_ai_reference_remains(), test_splash_toast_catchup_present_with_restored_guard(), _css(), _css_block(), _fn_body(), _html(), _js() (+44 more)

### Community 31 - "eth_feed.py"
Cohesion: 0.22
Nodes (4): _fixture_bars(), test_bootstrap_resets_live_trading_state_when_orders_disabled(), _fixture_bars(), test_bootstrap_spawns_mtf_seed_thread_instead_of_blocking()

### Community 32 - "MonteCarloOddsEvaluator"
Cohesion: 0.18
Nodes (8): MonteCarloBracketOdds, MonteCarloOddsEvaluator, test_track_b_timemachine_rejects_wrong_side_tp(), test_v24_track_b_timemachine_single_sim_and_flat_empirical_candles(), test_monte_carlo_ev_gate_odds_evaluation(), test_monte_carlo_without_numpy_reports_unknown(), test_uncapped_runner_r_assumption_is_labelled(), test_v200_31_33_mixins_and_timemachine_student_t()

### Community 33 - "test_performance_and_optimizations.py"
Cohesion: 0.06
Nodes (18): check_and_ensure_environment(), main(), _set_windows_app_user_model_id(), _apply_window_icon(), _activate_foreground_startup(), _on_window_closing(), _on_window_shown(), _delayed_activation() (+10 more)

### Community 34 - "test_gemini_client_quota_fastpath_sse_error_and_timeout"
Cohesion: 0.08
Nodes (9): _FakeCM, _FakeResp, test_gemini_client_check_health_and_update_api_key(), _run(), test_gemini_client_rest_payload_thought_skipping_and_block_reason(), _run(), test_gemini_client_sse_streaming_and_real_error_code(), _run() (+1 more)

### Community 36 - "ConfigManager"
Cohesion: 0.08
Nodes (12): ConfigManager, _extract_env_var_from_file(), test_track_c_config_manager_preserves_existing_config_on_write_error(), test_blank_save_allows_standby_mode(), test_bridge_stepwise_simulation_erroneous_then_valid(), test_config_manager_atomic_recovery_from_corruption(), test_config_manager_gemini_key_persistence(), test_config_manager_input_sanitization() (+4 more)

### Community 38 - "LiveArenaEngine"
Cohesion: 0.08
Nodes (17): LiveArenaEngine, test_evolve_now_with_fewer_than_two_rankings_does_not_raise(), test_stale_engine_save_session_state_refused(), test_anti_churn_cooldown_prevents_same_timestamp_reentry(), test_deserialize_ticket_round_trips_and_rejects_garbage(), test_ensure_active_live_positions_short_brackets(), test_evaluate_live_strategies_short_entries(), test_mtf_gate_blocks_counter_trend_entries() (+9 more)

### Community 40 - "Any"
Cohesion: 0.11
Nodes (3): _dedup_tickers(), _runner(), _on_progress()

### Community 41 - "test_debug_report_fixes.py"
Cohesion: 0.09
Nodes (11): _fixture_bars(), _raise_no_network(), test_cooperative_stop_event(), test_full_restore_bootstrap_start_integration(), test_get_ui_state_mutation_isolation(), test_offline_start_does_not_execute_stale_candles(), test_session_save_and_restore_with_locked_margin(), test_slow_bootstrap_stop_safety() (+3 more)

### Community 42 - "ArenaStorage"
Cohesion: 0.19
Nodes (11): ArenaStorage, test_restore_survives_garbage_stop_ticket_and_entry_ts(), _candle(), test_p2_concurrent_candle_writes_all_persist(), writer(), test_p2_engine_stop_closes_storage_and_restart_still_writes(), test_p2_persistent_connection_recovers_from_stale_handle(), test_p2_persistent_connection_reused_and_candle_persists_across_close() (+3 more)

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
Cohesion: 0.20
Nodes (9): efficiency_ratio(), _bar(), _choppy_bars(), test_efficiency_ratio_unit(), test_gate_blocks_entries_on_choppy_tape(), test_gate_inactive_on_trend_tape(), test_gate_never_blocks_closes(), _total_closed() (+1 more)

### Community 50 - "time"
Cohesion: 0.22
Nodes (16): check_binance_rest(), check_binance_ws(), _run(), check_ccxt_kraken(), check_coinbase_rest(), check_feed_registry(), check_gemini_health(), check_kraken_rest() (+8 more)

### Community 51 - "test_autosave_35.py"
Cohesion: 0.18
Nodes (8): _bars(), _engine(), _raise_no_network(), test_autosave_does_not_fire_when_stopped_or_superseded(), test_crash_like_stop_leaves_restorable_autosave(), test_evolution_marks_autosave_pending_and_it_fires_immediately(), test_live_loop_triggers_periodic_autosave(), test_periodic_autosave_writes_snapshot_when_interval_elapses()

### Community 52 - "test_gateway_setup_wizard.py"
Cohesion: 0.12
Nodes (9): probe_gemini_api_key(), test_v24_track_c_gemini_header_and_save_no_split_brain(), test_gemini_key_probe_http_responses(), test_gemini_key_probe_validation_defensive(), test_ui_assets_art_jargon_and_cjk_cleanliness(), test_wizard_close_confirm_dialog(), test_wizard_vertical_content_sized_layout(), test_key_rate_limit_429_is_not_verified() (+1 more)

### Community 53 - "test_llm_json_mode_fallback.py"
Cohesion: 0.12
Nodes (13): _now_iso(), _offline_commander(), _strong_bearish_events(), test_empty_digest_expires_stale_fallback(), test_fallback_clears_when_llm_recovers(), test_fallback_regime_is_marked_and_expires(), _client_with(), _CM (+5 more)

### Community 54 - "soak_engine.py"
Cohesion: 0.13
Nodes (14): closing_fills_since(), db_stats(), do_slice(), genome_valid(), main(), _sample(), make_quote(), _parse_args() (+6 more)

### Community 55 - "DeduplicationBuffer"
Cohesion: 0.22
Nodes (5): _dedup_normalize_title(), DeduplicationBuffer, test_v24_track_c_gemini_extract_json_retry_hint_dedup_and_https_redirect(), test_deduplication_buffer(), test_ingestion_clean_html_strips_script_style_and_dedup_forget()

### Community 56 - "test_505_leaderboard_cache.py"
Cohesion: 0.17
Nodes (10): _counting_periods(), _portfolio_with_history(), test_fill_invalidates_cache(), test_metrics_cached_across_ticks_with_no_fills(), test_replace_equity_history_invalidates_cache(), test_reset_invalidates_cache(), test_risk_free_rate_change_invalidates_cache(), test_track_a_leaderboard_caches_flat_portfolio() (+2 more)

### Community 57 - "MultiTimeframeEngine"
Cohesion: 0.07
Nodes (16): IndicatorEngineMixin, MultiTimeframeEngine, test_track_b_mtf_engine_delta_volume_and_neutral_on_conflict(), test_v24_track_b_mtf_seed_1h_merges_same_slot(), _buckets(), _hourly_bars(), _minute_bars(), test_engine_seed_fetch_failure_stays_neutral() (+8 more)

### Community 58 - "test_risk_semantics.py"
Cohesion: 0.17
Nodes (10): RiskGuard, test_tripped_champion_revives_next_generation(), _broker(), test_aggressive_stopout_loss_capped_at_risk_pct(), test_drawdown_trip_closes_positions_via_broker(), test_genome_rejects_nonsense(), test_risk_budget_ignores_leverage(), test_risk_guard_cap_ignores_leverage() (+2 more)

### Community 60 - "MacroCommander"
Cohesion: 0.11
Nodes (20): StructuredEvent, MacroCommander, test_synthesize_plumbs_raw_snippet(), test_structured_event_new_fields_default(), test_fallback_thresholds_do_not_veto_on_single_word(), _run(), test_llm_numeric_parsing_never_raises(), _run() (+12 more)

### Community 61 - "renderIntelHub"
Cohesion: 0.24
Nodes (12): cleanIntelSummary(), formatIntelEventTime(), hashTickerName(), intelArticleBodyEl(), renderIntelArticle(), requestIntelArticle(), startIntelArticleProgressPoll(), stopIntelArticleProgressPoll() (+4 more)

### Community 63 - ".get_intel_hub_telemetry"
Cohesion: 0.20
Nodes (4): test_quota_pct_has_no_invented_denominator(), _run_429(), test_quota_pct_uses_user_set_budget(), test_quota_throttling_slows_digest()

### Community 64 - "test_intel_hub_layout.py"
Cohesion: 0.25
Nodes (12): _commander(), _css(), _js(), _mock_pipeline(), _rule(), _structured(), test_stream_loading_block_is_centered_with_meter(), test_sync_status_failed_when_feeds_down() (+4 more)

### Community 65 - "renderAll"
Cohesion: 0.13
Nodes (23): applyStratCurveHover(), buildSparklineGeometry(), canonicalStrategyKey(), fillMatchesStrategy(), fmtPct(), fmtSignedUsd(), fmtTimeSec(), fmtUsd() (+15 more)

### Community 66 - "ingestion.py"
Cohesion: 0.09
Nodes (14): _clean_html_text(), _compile_word_group(), _compiled_word_re(), _contains_word(), _first_child_text(), _parse_feed_ts(), _parse_iso_ts(), parse_rss_atom() (+6 more)

### Community 67 - "._build_snapshot_locked"
Cohesion: 0.21
Nodes (3): _safe_fmt_hms(), test_phase6_modular_view_model_and_state_delta_streaming(), test_safe_fmt_hms_handles_invalid_and_valid_timestamps()

### Community 68 - "openSetupWizardModal"
Cohesion: 0.16
Nodes (17): applyBackdropMode(), applyPrivateBalanceUi(), checkOnboardingBoot(), clearSplashTimers(), confirmShutdown(), destroyAmbientBackdrop(), initAmbientBackdrop(), initAppBoot() (+9 more)

### Community 70 - "controls/index.ts"
Cohesion: 0.19
Nodes (10): _broker(), _commander(), test_backtest_default_sizing_is_one(), test_compute_r_multiple_qty_scales_budget_and_clamps(), test_evaluate_signal_sizing_shrinks_qty_not_sl(), test_no_confidence_means_no_sizing_effect(), test_per_strategy_sensitivity_scales_the_deviation(), test_sizing_formula_exact_values() (+2 more)

### Community 71 - "Any"
Cohesion: 0.22
Nodes (3): InterruptDebouncer, test_stage2_interrupt_debouncing_r4(), _run()

### Community 72 - "macro_commander.py"
Cohesion: 0.18
Nodes (8): build_event_article_prompts(), _event_age_min(), _safe_float(), _event_dict(), test_prompt_includes_raw_snippet(), test_prompt_without_snippet_omits_line(), test_telemetry_strips_raw_snippet(), test_article_prompt_asks_for_1000_words_and_six_paragraphs()

### Community 73 - "ArenaStorage"
Cohesion: 0.11
Nodes (6): _retry_on_db_error(), wrapper(), _sanitize_json_value(), test_track_b_persistence_batch_fills_and_prune_candles(), test_evolution_seed_recorded_in_history(), test_phase2_sqlite_wal_persistence_and_cold_start_hydration()

### Community 75 - "QuoteManager"
Cohesion: 0.19
Nodes (3): QuoteManager, test_dead_cascade_state_is_gone(), test_ws_quote_path_still_works()

### Community 76 - "test_ui_feedback.py"
Cohesion: 0.29
Nodes (3): _copy_text_to_clipboard_windows(), test_copy_text_to_clipboard_windows_non_windows(), test_copy_text_to_clipboard_windows_roundtrip()

### Community 77 - "gemini_client.py"
Cohesion: 0.18
Nodes (6): classify_llm_error(), _error_body_text(), _walk(), _retry_window_seconds(), test_chat_json_400_format_rejection_is_not_quota(), _run()

### Community 78 - ".bootstrap_intraday_session"
Cohesion: 0.10
Nodes (4): _on_done(), test_stale_engine_evolve_now_refused(), test_stale_engine_harvest_fills_refused(), test_stale_engine_state_publish_skipped()

### Community 80 - "test_intel_veto.py"
Cohesion: 0.20
Nodes (10): parse_polymarket_events(), parse_reddit_posts(), _fallback_structured(), _mock_commander(), test_feed_numeric_parsing_never_raises(), test_keyword_word_boundaries_no_substring_false_positives(), test_no_fabricated_seed_events_and_honest_quota(), test_veto_never_blocks_close() (+2 more)

### Community 82 - "test_chop_gate_seed.py"
Cohesion: 0.29
Nodes (10): _engine(), _feed_1m(), _tape_end_anchored(), _tape_slot_aligned(), test_seed_helper_feeds_continuous_chain_and_arms_gate(), test_seed_helper_gap_truncates_to_suffix_after_gap(), test_seed_helper_malformed_row_skipped_not_fabricated(), test_seed_helper_misaligned_or_empty_seeds_nothing() (+2 more)

### Community 83 - ".total_equity"
Cohesion: 0.28
Nodes (4): test_portfolio_reset_clears_all_metrics(), test_portfolio_buy_and_sell_accounting(), test_portfolio_initialization(), test_portfolio_short_accounting_and_overcovering()

### Community 84 - "test_card_reorder_anim.py"
Cohesion: 0.35
Nodes (10): _css(), _js(), _reorder_block(), test_cards_are_stable_nodes_never_recreated_on_reorder(), test_flip_cleanup_clears_class_and_transform(), test_flip_inverts_with_translate_and_plays_via_class(), test_flip_records_first_rects_before_moving_nodes(), test_flip_runs_only_when_order_changes() (+2 more)

### Community 85 - "test_507_candle_write_on_close.py"
Cohesion: 0.42
Nodes (7): _counting_save(), _engine(), test_bar_close_persists_final_bar_once(), test_closed_bar_is_in_sqlite_after_close(), test_out_of_order_tick_does_not_double_save(), test_three_minutes_persist_two_closed_bars(), test_ticks_within_one_minute_write_nothing()

### Community 86 - "test_llm_concurrent_sessions.py"
Cohesion: 0.21
Nodes (4): _StubGateway, test_four_threads_expand_concurrently_without_closing_each_other(), _one(), _worker()

### Community 87 - "StreamingCryptoFeed"
Cohesion: 0.24
Nodes (3): StreamingCryptoFeed, test_phase1_websocket_feed_parsing_and_fast_path_fallback(), test_parse_binance_ticker_rejects_garbage()

### Community 88 - "test_weighted_sentiment.py"
Cohesion: 0.34
Nodes (12): _ev(), _now_iso(), _offline_commander(), test_direction_thresholds_long_and_short(), test_events_older_than_60_min_excluded(), test_fallback_never_enters_hold_cash(), test_half_life_decay_60_min_is_half_weight(), test_llm_hold_cash_with_confidence_passes_through() (+4 more)

### Community 89 - "threading"
Cohesion: 0.06
Nodes (18): _FakeCM, _FakeForum, _FakeHarvester, _FakeResp, _FakeSession, _make_commander(), test_concurrent_article_call_survives_refresh(), test_two_refreshes_leave_session_open() (+10 more)

### Community 90 - "MacroRegimeState"
Cohesion: 0.21
Nodes (3): MacroRegimeState, test_regime_state_dict_exposes_fallback(), test_ingestion_zero_count_and_macro_safe_timestamp()

### Community 92 - "test_orb_anchor_34.py"
Cohesion: 0.22
Nodes (4): _tape_bar(), test_backtest_orb_range_anchored_to_first_15_tape_bars(), test_live_orb_range_does_not_drift_with_rolling_buffer(), _warmup_bars()

### Community 93 - "test_502_ui_state_delta.py"
Cohesion: 0.33
Nodes (5): _engine(), _snapshot(), test_deepcopy_never_receives_heavy_arrays_on_unchanged_poll(), test_delta_is_still_a_defensive_copy(), test_delta_output_identical_to_old_path()

### Community 95 - "_mock_resp"
Cohesion: 0.31
Nodes (10): _coinbase_stats_payload(), _coinbase_ticker_payload(), _kraken_payload(), _mock_resp(), test_binance_quote_success_parses_all_fields(), test_coinbase_quote_success_parses(), test_kraken_quote_success_parses(), dispatch() (+2 more)

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

### Community 100 - "_open_short"
Cohesion: 0.20
Nodes (5): _open_short(), test_evaluate_live_strategies_short_exits_are_signal_only(), test_evaluate_live_strategies_small_gain_does_not_close_shorts(), test_stagnation_exit_closes_after_40m(), test_trailing_guard_short_ratchet_moves_stop_down()

### Community 101 - "test_318_system_config_untracked.py"
Cohesion: 0.33
Nodes (5): _git(), test_system_config_is_ignored_by_git(), test_system_config_is_untracked_but_present_on_disk(), test_p2_eth_feed_first_fetch_loads_pandas_and_behaves(), test_p2_eth_feed_import_does_not_import_pandas()

### Community 102 - "test_telemetry_no_articles.py"
Cohesion: 0.53
Nodes (4): _commander_with_expanded_events(), test_article_lock_map_stays_bounded(), test_on_demand_article_is_intact_after_the_snapshot(), test_snapshot_carries_no_article_bodies()

### Community 104 - "test_312_gateway_failed.py"
Cohesion: 0.52
Nodes (5): _dead_gateway_commander(), _mock_pipeline(), _structured(), test_sync_status_done_when_dead_gateway_still_yields_fallback_digest(), test_sync_status_failed_when_gateway_dead_and_nothing_produced()

### Community 105 - "_open_long"
Cohesion: 0.33
Nodes (3): _open_long(), test_bracket_take_profit_closes_via_on_tick(), test_evaluate_live_strategies_small_gain_does_not_close_longs()

### Community 108 - "drawPriceChart"
Cohesion: 0.50
Nodes (8): drawPriceChart(), formatChartReadoutLabel(), getActiveChartSeries(), locateMouseAndRefreshChart(), setChartTimeframe(), setLgWallpaper(), setupChartInteraction(), updateChartMouseHover()

### Community 127 - ".refresh_digest_async"
Cohesion: 0.12
Nodes (6): _shutting_down(), _shutting_down(), _wrapped(), _parse_event_epoch(), test_sync_status_failed_when_gateway_down(), test_iso_z_parsing_and_macro_quiet_cycle_skip()

### Community 138 - ".stop"
Cohesion: 0.15
Nodes (13): build_engine_view_model(), test_v24_track_d_view_model_sanitizes_mc_stats_and_dev_bat_structure(), _rankings(), test_view_model_does_not_fabricate_take_profit(), test_view_model_reports_unknown_mc_and_quota(), test_view_model_short_unrealized_pnl_pct(), test_view_model_skips_stale_ranking_entry(), test_view_model_survives_missing_or_broken_engine() (+5 more)

### Community 139 - "fix_item5_patch.py"
Cohesion: 0.17
Nodes (19): addChartBeacon(), attachToastInteractions(), dismissToast(), enqueueToast(), ensureLiveTradingStarted(), pollBackend(), previewPositionAnimation(), previewPositionClosedAnimation() (+11 more)

### Community 146 - "Choreography"
Cohesion: 0.29
Nodes (6): 1. Launch Packaged Desktop Executable (`.exe`), 2. Run Self-Test Verification, 3. Run Automated Unit Test Suite (32 Tests), 4. Build Standalone Windows Executable, Quick Start Guide, TradeBot0: Multi-Agent Paper Trading & Genetic Evolution Arena (BTC/USD)

## Knowledge Gaps
- **42 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `LiveArenaEngine` connect `LiveArenaEngine` to `test_debug_optimize_regression.py`, `test_update_checker.py`, `test_v200_fixes.py`, `TimeMachineArena`, `test_v260_debug_and_optimize.py`, `BrokerSim`, `.stop`, `ArenaDashboard`, `OrderSide`, `.bootstrap_intraday_session`, `view_model.py`, `GeminiClient`, `test_live_engine.py`, `Leaderboard`, `dashboard.py`, `eth_feed.py`, `MonteCarloOddsEvaluator`, `test_performance_and_optimizations.py`, `ConfigManager`, `test_debug_report_fixes.py`, `ArenaStorage`, `test_live_chop_gate.py`, `LiveStrategyRunnerMixin`, `time`, `test_autosave_35.py`, `soak_engine.py`, `MultiTimeframeEngine`, `MacroCommander`, `test_phase3_soak.py`, `._build_snapshot_locked`, `LiveQuote`, `controls/index.ts`, `SessionCodecMixin`, `.bootstrap_intraday_session`, `test_intel_veto.py`, `test_chop_gate_seed.py`, `test_507_candle_write_on_close.py`, `StreamingCryptoFeed`, `threading`, `test_orb_anchor_34.py`, `test_502_ui_state_delta.py`, `_mock_resp`, `test_321_auto_redeploy.py`, `test_orb_day_rollover.py`, `_open_short`, `_open_long`, `._handle_ws_quote`, `test_live_engine_toggle_pause_and_auto_evolve_shift_math`, `.is_fresh`?**
  _High betweenness centrality (0.117) - this node is a cross-community bridge._
- **Are the 10 inferred relationships involving `LiveArenaEngine` (e.g. with `Architectural Highlights` and `ViewModelPublisher`) actually correct?**
  _`LiveArenaEngine` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Should `renderIntelHub` be split into smaller, more focused modules?**
  _Cohesion score 0.10317460317460317 - nodes in this community are weakly interconnected._
- **Why does `GeminiClient` connect `GeminiClient` to `test_debug_optimize_regression.py`, `test_update_checker.py`, `test_v200_fixes.py`, `test_v260_debug_and_optimize.py`, `test_forum_collector.py`, `.chat_json`, `OrderSide`, `IntelligenceHarvester`, `view_model.py`, `test_phase2_omniroute_client.py`, `dashboard.py`, `test_gemini_client_quota_fastpath_sse_error_and_timeout`, `LiveArenaEngine`, `test_llm_json_mode_fallback.py`, `MacroCommander`, `.get_intel_hub_telemetry`, `ingestion.py`, `Any`, `macro_commander.py`, `gemini_client.py`, `test_intel_veto.py`, `test_llm_concurrent_sessions.py`, `threading`, `MacroRegimeState`, `test_track_c_gemini_max_concurrent_1_repair_no_deadlock`, `test_telemetry_no_articles.py`, `.refresh_digest_async`?**
  _High betweenness centrality (0.095) - this node is a cross-community bridge._
- **Are the 81 inferred relationships involving `OrderSide` (e.g. with `main()` and `BrokerSim`) actually correct?**
  _`OrderSide` has 81 INFERRED edges - model-reasoned connections that need verification._
- **Should `test_debug_optimize_regression.py` be split into smaller, more focused modules?**
  _Cohesion score 0.13333333333333333 - nodes in this community are weakly interconnected._
- **Why does `MacroCommander` connect `MacroCommander` to `test_v200_fixes.py`, `test_v260_debug_and_optimize.py`, `test_forum_collector.py`, `OrderSide`, `IntelligenceHarvester`, `view_model.py`, `GeminiClient`, `dashboard.py`, `LiveArenaEngine`, `Any`, `test_event_article.py`, `test_llm_json_mode_fallback.py`, `.get_intel_hub_telemetry`, `test_intel_hub_layout.py`, `ingestion.py`, `controls/index.ts`, `macro_commander.py`, `test_intel_veto.py`, `test_weighted_sentiment.py`, `threading`, `MacroRegimeState`, `test_telemetry_no_articles.py`, `._get_article_lock`, `test_312_gateway_failed.py`, `.refresh_digest_async`?**
  _High betweenness centrality (0.078) - this node is a cross-community bridge._