# Graph Report - TradeBot0_Local  (2026-11-25)

## Corpus Check
- 130 files · ~172,631 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 11 file(s) not represented in the graph (top: (none) 4, .iss 1, .lnk 1)

## Summary
- 2528 nodes · 7324 edges · 116 communities (80 shown, 36 thin omitted)
- Extraction: 88% EXTRACTED · 12% INFERRED · 0% AMBIGUOUS · INFERRED: 884 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `7fdd0a7a`
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
- renderCommandPaletteContent
- test_ui_contract.py
- ArenaDashboard
- OrderSide
- time
- test_bootstrap_hydrates_fresh_sqlite_candles
- test_gui_item7.py
- GeminiClient
- FillEvent
- _ArenaBridgeApi
- test_phase1_cadence_and_ranking.py
- .get_ui_state
- Leaderboard
- syncAppShellInert
- test_phase3_ingestion.py
- soak_engine.py
- Stage
- test_performance_and_optimizations.py
- test_intel_stream_redesign.py
- test_316_bootstrap_reset.py
- MonteCarloOddsEvaluator
- test_performance_and_optimizations.py
- test_mtf_seed_async_25.py
- timemachine.py
- ConfigManager
- test_live_engine.py
- _SliceableDeque
- threading
- test_debug_report_fixes.py
- ArenaStorage
- test_save_launch_progress.py
- test_ai_panels_frontend.py
- unittest_mock
- test_live_chop_gate.py
- StreamingCryptoFeed
- test_508_chop_gate.py
- LiveStrategyRunnerMixin
- test_wizard_no_skip.py
- test_autosave_35.py
- test_llm_json_mode_fallback.py
- soak_engine.py
- DeduplicationBuffer
- test_auto_evolve_fires_on_closed_trades
- MultiTimeframeEngine
- MacroCommander
- renderIntelHub
- test_phase3_soak.py
- test_item12a_omniroute.py
- test_intel_hub_layout.py
- renderAll
- _compiled_word_re
- ._build_snapshot_locked
- getCommandPaletteItems
- LiveQuote
- controls/index.ts
- ArenaStorage
- SessionCodecMixin
- test_ui_feedback.py
- .bootstrap_intraday_session
- test_v287_render_guards.py
- test_chop_gate_seed.py
- test_card_reorder_anim.py
- test_507_candle_write_on_close.py
- asyncio
- test_digest_refresh_session.py
- test_orb_anchor_34.py
- test_502_ui_state_delta.py
- test_track_c_gemini_max_concurrent_1_repair_no_deadlock
- persistence.py
- test_phase2g_graphics.py
- test_320_save_history_storage.py
- test_321_auto_redeploy.py
- test_orb_day_rollover.py
- test_318_system_config_untracked.py
- test_article_real_streamed_progress_and_viewmodel_delta
- _referenced_classes
- _OKHandler
- cursors/index.tsx
- .compute_r_multiple_qty
- LiveArenaEngine
- fix_item5_patch.py
- Choreography

## God Nodes (most connected - your core abstractions)
1. `LiveArenaEngine` - 210 edges
2. `OrderSide` - 154 edges
3. `BrokerSim` - 110 edges
4. `GeminiClient` - 107 edges
5. `OrderTicket` - 102 edges
6. `Portfolio` - 102 edges
7. `MacroCommander` - 94 edges
8. `OrderType` - 74 edges
9. `ExecutionReason` - 70 edges
10. `_ArenaBridgeApi` - 65 edges

## Surprising Connections (you probably didn't know these)
- `Architectural Highlights` --references--> `LiveArenaEngine`  [INFERRED]
  README.md → src/data/live_engine.py
- `Architectural Highlights` --references--> `GeneticEvolver`  [INFERRED]
  README.md → src/arena/evolution.py
- `Architectural Highlights` --references--> `CompetitorGenome`  [INFERRED]
  README.md → src/competitors/base.py
- `test_generate_fallback_bars_deleted()` --uses--> `LiveArenaEngine`  [INFERRED]
  tests/test_offline_removal.py → src/data/live_engine.py
- `test_deserialize_ticket_garbage_numbers_return_none()` --uses--> `LiveArenaEngine`  [INFERRED]
  tests/test_phase1_debug_sweep.py → src/data/live_engine.py

## Import Cycles
- None detected.

## Communities (116 total, 36 thin omitted)

### Community 0 - "renderIntelHub"
Cohesion: 0.18
Nodes (15): buildIntelEventCard(), clearIntelSearch(), initIntelFilterControls(), intelEventKey(), isReducedMotionPreferred(), matchesIntelFilter(), morphText(), renderIntelHub() (+7 more)

### Community 2 - "test_update_checker.py"
Cohesion: 0.08
Nodes (22): _check(), check_for_updates(), compare_versions(), get_manifest_url(), _is_date_version(), test_track_c_update_checker_rejects_non_https_and_clears_download_url_when_up_to_date(), _mock_response(), test_bridge_check_for_updates_not_configured() (+14 more)

### Community 3 - "test_v200_fixes.py"
Cohesion: 0.06
Nodes (33): GeneticEvolver, CompetitorStats, AggressiveCompetitor, BaseCompetitor, CompetitorGenome, ConservativeCompetitor, ORBCompetitor, SessionMeanPullbackCompetitor (+25 more)

### Community 6 - "TimeMachineArena"
Cohesion: 0.15
Nodes (11): CandleBar, TimeMachineArena, test_backtest_slippage_uses_measured_atr(), _bars(), test_backtest_opens_shorts_on_downtrend(), test_evolution_tournament_runs_multiple_generations(), test_orb_window_excludes_current_bar(), test_timemachine_evolution_preserves_portfolio() (+3 more)

### Community 7 - "test_v260_debug_and_optimize.py"
Cohesion: 0.05
Nodes (26): check_binance_rest(), check_binance_ws(), _run(), check_ccxt_kraken(), check_coinbase_rest(), check_feed_registry(), check_gemini_health(), check_kraken_rest() (+18 more)

### Community 8 - "test_forum_collector.py"
Cohesion: 0.14
Nodes (7): ForumCollector, test_forum_batch_scored_without_llm_when_offline(), mock_get(), test_forum_collector_fast_test_short_circuits(), test_forum_collector_hourly_cap(), test_forum_collector_stocktwits_flow_and_cadence(), mock_get()

### Community 9 - "BrokerSim"
Cohesion: 0.07
Nodes (41): Architectural Highlights, BrokerSim, OrderTicket, Portfolio, _open_long(), test_apply_fill_value_error_does_not_kill_cadence(), _boom(), test_submit_order_returns_none_when_apply_fill_fails() (+33 more)

### Community 10 - "renderCommandPaletteContent"
Cohesion: 0.24
Nodes (10): closeCommandPalette(), handleCmdPaletteOverlayClick(), initCommandPalette(), initScrollAreaFades(), openCommandPalette(), renderCommandPaletteContent(), runCommandPaletteItem(), toggleCommandPalette() (+2 more)

### Community 11 - "test_ui_contract.py"
Cohesion: 0.15
Nodes (15): _badge_cls_producer_values(), _bridge_class_node(), _bridge_methods(), _bridge_obj_calls(), _bridge_self_calls(), _defined_classes(), _html_ids(), _js_defined_functions() (+7 more)

### Community 12 - "ArenaDashboard"
Cohesion: 0.07
Nodes (18): ArenaDashboard, __getattr__(), test_track_c_save_and_launch_aborts_if_key_save_fails(), test_track_d_dashboard_save_launch_aborts_on_key_sync_failure(), test_v24_track_c_gemini_header_and_save_no_split_brain(), test_setup_status_has_no_gateway_auto_spawn_option(), test_dashboard_save_and_launch_hot_reloads_client_key(), test_manual_evolve_does_not_block_bridge() (+10 more)

### Community 14 - "OrderSide"
Cohesion: 0.08
Nodes (27): __getattr__(), ExecutionReason, OrderSide, OrderStatus, OrderType, PositionSide, RiskGuard, parse_symbol_pairs() (+19 more)

### Community 15 - "time"
Cohesion: 0.05
Nodes (38): _clean_html_text(), _first_child_text(), IntelligenceHarvester, _parse_feed_ts(), _parse_iso_ts(), parse_polymarket_events(), parse_reddit_posts(), parse_rss_atom() (+30 more)

### Community 16 - "test_bootstrap_hydrates_fresh_sqlite_candles"
Cohesion: 0.22
Nodes (3): _cache_rows(), test_bootstrap_hydrates_fresh_sqlite_candles(), test_bootstrap_rejects_stale_sqlite_candles()

### Community 17 - "test_gui_item7.py"
Cohesion: 0.05
Nodes (33): _build_activity_heatmap(), build_engine_view_model(), _build_engine_view_model_impl(), _build_risk_telemetry(), _downsample_equity_history(), _empty_view_model(), _safe_fmt_hms(), _safe_genome_params() (+25 more)

### Community 18 - "GeminiClient"
Cohesion: 0.03
Nodes (55): classify_llm_error(), _clean_key_input(), compute_backoff(), _error_body_text(), _walk(), _extract_gemini_detail_signals(), extract_json(), GeminiClient (+47 more)

### Community 19 - "FillEvent"
Cohesion: 0.09
Nodes (20): FillEvent, test_track_a_portfolio_cross_gen_leverage_partial_close_conserves_equity(), test_track_a_portfolio_failed_fill_does_not_corrupt_fees(), test_track_b_quote_feeds_rejects_non_positive_and_non_finite(), test_track_d_frontend_contracts_css_html_js(), test_track_d_reset_engine_preserves_fills_after_bootstrap_completes(), test_v24_track_a_portfolio_apply_fill_upfront_quantization(), test_portfolio_reset_clears_all_metrics() (+12 more)

### Community 21 - "test_phase1_cadence_and_ranking.py"
Cohesion: 0.38
Nodes (3): _fixture_bars(), test_candle_cadence_dispatcher_timing_and_dispatch(), test_micro_bar_aggregation_preserves_wick_extremes_r1()

### Community 22 - ".get_ui_state"
Cohesion: 0.17
Nodes (12): _drive(), test_fill_event_has_monotonic_seq_and_action_label(), test_live_engine_bidirectional_long_and_short_execution(), test_live_engine_eth_and_leverage_configuration(), test_live_engine_evolve_preserves_fill_tape_and_portfolio_positions(), test_live_engine_ui_state_is_json_safe_and_complete(), test_offline_feed_safety_blocks_mock_fills(), test_pause_flag_round_trips() (+4 more)

### Community 24 - "Leaderboard"
Cohesion: 0.08
Nodes (23): Leaderboard, test_evolve_now_with_fewer_than_two_rankings_does_not_raise(), test_last_records_class_default_present(), _counting_periods(), _portfolio_with_history(), test_fill_invalidates_cache(), test_metrics_cached_across_ticks_with_no_fills(), test_replace_equity_history_invalidates_cache() (+15 more)

### Community 25 - "syncAppShellInert"
Cohesion: 0.09
Nodes (27): blurActiveFocus(), closeResetModal(), closeSetupWizardModal(), closeShutdownModal(), closeStrategyDetailModal(), closeWizardCloseConfirm(), confirmCloseWizardWithoutSaving(), confirmResetArena() (+19 more)

### Community 26 - "test_phase3_ingestion.py"
Cohesion: 0.10
Nodes (17): InterruptDebouncer, _fake_registry_response(), _new_harvester(), _registry_get_ok(), _rss_and_atom_payloads(), test_feed_registry_completeness_r3(), test_fetch_from_registry_parses_real_rss_xml(), _recording_get() (+9 more)

### Community 27 - "soak_engine.py"
Cohesion: 0.14
Nodes (12): ETHFeed, _bar(), _ccxt_ohlcv(), test_fetch_dataframe_both_sources_fail_raises(), test_fetch_dataframe_falls_back_to_ccxt_kraken(), test_fetch_historical_bars_yahoo_multiindex_columns(), test_fetch_historical_bars_yahoo_success(), test_generate_signal_real_path_setups_and_exits() (+4 more)

### Community 28 - "Stage"
Cohesion: 0.05
Nodes (47): animCandles, attachToastInteractions(), changeEvolveInterval(), chartBeacons, createPositionClosedToastElement(), currentSplashSteps, dismissToast(), EVOLVE_INTERVAL_OPTIONS (+39 more)

### Community 29 - "test_performance_and_optimizations.py"
Cohesion: 0.14
Nodes (11): _scanned_files(), test_no_src_ai_reference_remains(), test_launchers_and_shortcut_integrity(), test_macro_veto_intent_preserved_in_live_evaluation(), test_phase4_mtf_trend_confluence_gatekeeper(), test_phase5_multi_objective_composite_fitness(), test_portfolio_no_duplicate_apply_fill_returns(), test_splash_logo_concentric_alignment_and_svg_zap() (+3 more)

### Community 30 - "test_intel_stream_redesign.py"
Cohesion: 0.17
Nodes (23): _css(), _css_block(), _fn_body(), _html(), _js(), test_article_failure_shows_reason_not_summary(), test_article_lazy_once_and_cached(), test_article_loading_shows_determinate_stage_progress_bar() (+15 more)

### Community 32 - "MonteCarloOddsEvaluator"
Cohesion: 0.18
Nodes (7): MonteCarloBracketOdds, MonteCarloOddsEvaluator, test_track_b_timemachine_rejects_wrong_side_tp(), test_v24_track_b_timemachine_single_sim_and_flat_empirical_candles(), test_monte_carlo_ev_gate_odds_evaluation(), test_monte_carlo_without_numpy_reports_unknown(), test_v200_31_33_mixins_and_timemachine_student_t()

### Community 33 - "test_performance_and_optimizations.py"
Cohesion: 0.05
Nodes (24): check_and_ensure_environment(), main(), _set_windows_app_user_model_id(), _apply_window_icon(), _activate_foreground_startup(), _on_window_closing(), _on_window_shown(), _delayed_activation() (+16 more)

### Community 35 - "timemachine.py"
Cohesion: 0.13
Nodes (4): isolate_arena_memory(), _tape(), test_backtest_short_exits_at_trailed_level_not_original_stop(), test_backtest_short_trailing_stop_ratchets_down()

### Community 36 - "ConfigManager"
Cohesion: 0.07
Nodes (13): ConfigManager, _extract_env_var_from_file(), test_track_c_config_manager_preserves_existing_config_on_write_error(), test_blank_save_allows_standby_mode(), test_bridge_stepwise_simulation_erroneous_then_valid(), test_config_manager_atomic_recovery_from_corruption(), test_config_manager_gemini_key_persistence(), test_config_manager_input_sanitization() (+5 more)

### Community 38 - "test_live_engine.py"
Cohesion: 0.08
Nodes (26): _coinbase_stats_payload(), _coinbase_ticker_payload(), _kraken_payload(), _mock_resp(), _open_short(), _startup_engine_long(), test_anti_churn_cooldown_prevents_same_timestamp_reentry(), test_binance_quote_success_parses_all_fields() (+18 more)

### Community 40 - "threading"
Cohesion: 0.14
Nodes (8): _drive_fixed(), test_live_tick_integration_fixed_price_series(), _drive(), _make_engine(), _quote(), test_concurrent_publish_harvests_each_fill_once(), test_publish_state_snapshot_holds_engine_lock(), publish_many()

### Community 41 - "test_debug_report_fixes.py"
Cohesion: 0.10
Nodes (11): _fixture_bars(), _raise_no_network(), test_cooperative_stop_event(), test_get_ui_state_mutation_isolation(), test_offline_start_does_not_execute_stale_candles(), test_pause_feed_updates_ui_snapshot_immediately(), test_session_save_and_restore_with_locked_margin(), test_slow_bootstrap_stop_safety() (+3 more)

### Community 42 - "ArenaStorage"
Cohesion: 0.22
Nodes (11): ArenaStorage, wrapper(), _candle(), test_p2_concurrent_candle_writes_all_persist(), writer(), test_p2_engine_stop_closes_storage_and_restart_still_writes(), test_p2_persistent_connection_recovers_from_stale_handle(), test_p2_persistent_connection_reused_and_candle_persists_across_close() (+3 more)

### Community 43 - "test_save_launch_progress.py"
Cohesion: 0.13
Nodes (10): _make_bridge(), _read_app_js(), test_get_save_launch_status_returns_copy(), test_save_and_launch_does_not_jump_splash_to_75(), test_save_launch_failed_stage_never_reports_100(), test_save_launch_stage_advances_and_done_only_on_return(), test_save_launch_stage_resets_between_runs(), test_save_launch_status_polled_from_js() (+2 more)

### Community 44 - "test_ai_panels_frontend.py"
Cohesion: 0.23
Nodes (19): _css(), _dashboard(), _html(), _js(), test_commander_and_stream_titles(), test_compact_mode_fits_intro_line_and_status_lines_hold_width(), test_deck_empty_slots_collapse_and_level_bottoms(), test_dock_gear_tooltip_is_ai_services() (+11 more)

### Community 45 - "unittest_mock"
Cohesion: 0.11
Nodes (18): build_event_article_prompts(), _event_dict(), test_prompt_includes_raw_snippet(), test_prompt_without_snippet_omits_line(), test_telemetry_strips_raw_snippet(), _event_id(), _make_commander(), test_ai_offline_returns_failure_without_llm() (+10 more)

### Community 46 - "test_live_chop_gate.py"
Cohesion: 0.19
Nodes (11): _bars(), _choppy_closes(), _engine_with_15m(), test_chop_gate_blocks_entry_through_try_enter_bracket(), test_chop_gate_blocks_on_choppy_15m(), test_chop_gate_excludes_the_forming_bucket(), test_chop_gate_never_blocks_signal_exit_close(), test_chop_gate_open_on_trending_15m() (+3 more)

### Community 47 - "StreamingCryptoFeed"
Cohesion: 0.05
Nodes (17): QuoteManager, StreamingCryptoFeed, test_dead_cascade_state_is_gone(), test_ws_quote_path_still_works(), FakeWS, _run_feed(), SlowFakeWS, test_parse_binance_ticker_rejects_garbage() (+9 more)

### Community 48 - "test_508_chop_gate.py"
Cohesion: 0.20
Nodes (9): efficiency_ratio(), _bar(), _choppy_bars(), test_efficiency_ratio_unit(), test_gate_blocks_entries_on_choppy_tape(), test_gate_inactive_on_trend_tape(), test_gate_never_blocks_closes(), _total_closed() (+1 more)

### Community 50 - "test_wizard_no_skip.py"
Cohesion: 0.29
Nodes (3): _assets_root(), test_skip_bridge_deleted_but_mode_readers_kept(), test_wizard_has_no_skip_button()

### Community 51 - "test_autosave_35.py"
Cohesion: 0.18
Nodes (8): _bars(), _engine(), _raise_no_network(), test_autosave_does_not_fire_when_stopped_or_superseded(), test_crash_like_stop_leaves_restorable_autosave(), test_evolution_marks_autosave_pending_and_it_fires_immediately(), test_live_loop_triggers_periodic_autosave(), test_periodic_autosave_writes_snapshot_when_interval_elapses()

### Community 53 - "test_llm_json_mode_fallback.py"
Cohesion: 0.18
Nodes (7): _client_with(), _CM, _FakeSession, _Resp, test_generic_400_does_not_trigger_the_format_retry(), test_rejected_format_is_remembered_for_later_calls(), test_rejected_response_format_retries_without_it_and_parses()

### Community 54 - "soak_engine.py"
Cohesion: 0.15
Nodes (14): closing_fills_since(), db_stats(), do_slice(), genome_valid(), main(), _sample(), make_quote(), _parse_args() (+6 more)

### Community 55 - "DeduplicationBuffer"
Cohesion: 0.22
Nodes (5): _dedup_normalize_title(), DeduplicationBuffer, test_v24_track_c_gemini_extract_json_retry_hint_dedup_and_https_redirect(), test_deduplication_buffer(), test_ingestion_clean_html_strips_script_style_and_dedup_forget()

### Community 56 - "test_auto_evolve_fires_on_closed_trades"
Cohesion: 0.19
Nodes (7): _quote(), test_auto_evolve_fires_on_closed_trades(), _round_trips(), test_auto_evolve_timer_and_toggle(), test_next_evolve_sec_counts_trades_not_only_hours(), test_no_cached_price_when_feed_down(), test_toggle_auto_evolve_reenable_compensates_disabled_time()

### Community 57 - "MultiTimeframeEngine"
Cohesion: 0.07
Nodes (16): IndicatorEngineMixin, MultiTimeframeEngine, test_track_b_mtf_engine_delta_volume_and_neutral_on_conflict(), test_v24_track_b_mtf_seed_1h_merges_same_slot(), _buckets(), _hourly_bars(), _minute_bars(), test_engine_seed_fetch_failure_stays_neutral() (+8 more)

### Community 60 - "MacroCommander"
Cohesion: 0.04
Nodes (34): StructuredEvent, _dedup_tickers(), _event_age_min(), MacroCommander, _runner(), _on_progress(), _shutting_down(), _shutting_down() (+26 more)

### Community 61 - "renderIntelHub"
Cohesion: 0.20
Nodes (14): cleanIntelSummary(), formatIntelEventTime(), hashTickerName(), intelArticleBodyEl(), preloadIntelArticles(), pumpIntelArticlePreload(), renderIntelArticle(), requestIntelArticle() (+6 more)

### Community 62 - "test_phase3_soak.py"
Cohesion: 0.28
Nodes (4): _bootstrapped_engine(), _load_soak_helpers(), soak(), test_p3_mini_soak_many_ticks_no_growth_blowup()

### Community 63 - "test_item12a_omniroute.py"
Cohesion: 0.07
Nodes (16): probe_gemini_api_key(), MacroRegimeState, test_gemini_key_probe_http_responses(), test_gemini_key_probe_validation_defensive(), _now_iso(), _offline_commander(), _strong_bearish_events(), test_empty_digest_expires_stale_fallback() (+8 more)

### Community 64 - "test_intel_hub_layout.py"
Cohesion: 0.25
Nodes (12): _commander(), _css(), _js(), _mock_pipeline(), _rule(), _structured(), test_stream_loading_block_is_centered_with_meter(), test_sync_status_failed_when_feeds_down() (+4 more)

### Community 65 - "renderAll"
Cohesion: 0.12
Nodes (29): buildSparklineGeometry(), createPositionToastElement(), createStrategyCardSkeleton(), escapeHtml(), fillMatchesStrategy(), fmtPct(), fmtSignedUsd(), fmtTimeSec() (+21 more)

### Community 66 - "_compiled_word_re"
Cohesion: 0.40
Nodes (3): _compile_word_group(), _compiled_word_re(), _contains_word()

### Community 67 - "._build_snapshot_locked"
Cohesion: 0.21
Nodes (3): _safe_fmt_hms(), test_phase6_modular_view_model_and_state_delta_streaming(), test_safe_fmt_hms_handles_invalid_and_valid_timestamps()

### Community 68 - "getCommandPaletteItems"
Cohesion: 0.21
Nodes (15): applyBackdropMode(), applyPrivateBalanceUi(), cycleBackdropMode(), exportTradeJournal(), getCommandPaletteItems(), initAmbientBackdrop(), mountSilverStreamAmbient(), requestAiIntelDigest() (+7 more)

### Community 69 - "LiveQuote"
Cohesion: 0.14
Nodes (5): LiveQuote, QuoteFeedsMixin, test_phase1_websocket_feed_parsing_and_fast_path_fallback(), _quote(), test_slice_ticks_capped_while_paused_and_cleared_on_resume()

### Community 70 - "controls/index.ts"
Cohesion: 0.18
Nodes (11): _broker(), _commander(), test_backtest_default_sizing_is_one(), test_compute_r_multiple_qty_scales_budget_and_clamps(), test_evaluate_signal_sizing_shrinks_qty_not_sl(), test_no_confidence_means_no_sizing_effect(), test_per_strategy_sensitivity_scales_the_deviation(), test_sizing_formula_exact_values() (+3 more)

### Community 73 - "ArenaStorage"
Cohesion: 0.15
Nodes (4): _retry_on_db_error(), _sanitize_json_value(), test_track_b_persistence_batch_fills_and_prune_candles(), test_phase2_sqlite_wal_persistence_and_cold_start_hydration()

### Community 76 - "test_ui_feedback.py"
Cohesion: 0.29
Nodes (3): _copy_text_to_clipboard_windows(), test_copy_text_to_clipboard_windows_non_windows(), test_copy_text_to_clipboard_windows_roundtrip()

### Community 78 - ".bootstrap_intraday_session"
Cohesion: 0.07
Nodes (11): _on_done(), test_full_restore_bootstrap_start_integration(), test_stale_engine_evolve_now_refused(), test_stale_engine_harvest_fills_refused(), test_stale_engine_state_publish_skipped(), _fixture_bars(), test_lifecycle_sequence_warmup_before_live_orders(), test_start_live_trading_success_path() (+3 more)

### Community 80 - "test_v287_render_guards.py"
Cohesion: 0.40
Nodes (7): _fn_body(), _js(), test_hub_header_writes_guarded(), test_intel_card_element_refs_cached(), test_macro_ribbon_writes_guarded(), test_spotlight_vars_written_once_per_frame(), test_strat_color_and_gen_label_writes_guarded()

### Community 82 - "test_chop_gate_seed.py"
Cohesion: 0.29
Nodes (10): _engine(), _feed_1m(), _tape_end_anchored(), _tape_slot_aligned(), test_seed_helper_feeds_continuous_chain_and_arms_gate(), test_seed_helper_gap_truncates_to_suffix_after_gap(), test_seed_helper_malformed_row_skipped_not_fabricated(), test_seed_helper_misaligned_or_empty_seeds_nothing() (+2 more)

### Community 84 - "test_card_reorder_anim.py"
Cohesion: 0.35
Nodes (10): _css(), _js(), _reorder_block(), test_cards_are_stable_nodes_never_recreated_on_reorder(), test_flip_cleanup_clears_class_and_transform(), test_flip_inverts_with_translate_and_plays_via_class(), test_flip_records_first_rects_before_moving_nodes(), test_flip_runs_only_when_order_changes() (+2 more)

### Community 85 - "test_507_candle_write_on_close.py"
Cohesion: 0.42
Nodes (7): _counting_save(), _engine(), test_bar_close_persists_final_bar_once(), test_closed_bar_is_in_sqlite_after_close(), test_out_of_order_tick_does_not_double_save(), test_three_minutes_persist_two_closed_bars(), test_ticks_within_one_minute_write_nothing()

### Community 88 - "asyncio"
Cohesion: 0.12
Nodes (22): _dead_gateway_commander(), _mock_pipeline(), _structured(), test_sync_status_done_when_dead_gateway_still_yields_fallback_digest(), test_sync_status_failed_when_gateway_dead_and_nothing_produced(), _FakeForum, _FakeHarvester, _make_commander() (+14 more)

### Community 89 - "test_digest_refresh_session.py"
Cohesion: 0.16
Nodes (3): _FakeCM, _FakeResp, _FakeSession

### Community 92 - "test_orb_anchor_34.py"
Cohesion: 0.22
Nodes (4): _tape_bar(), test_backtest_orb_range_anchored_to_first_15_tape_bars(), test_live_orb_range_does_not_drift_with_rolling_buffer(), _warmup_bars()

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
Cohesion: 0.33
Nodes (5): _git(), test_system_config_is_ignored_by_git(), test_system_config_is_untracked_but_present_on_disk(), test_p2_eth_feed_first_fetch_loads_pandas_and_behaves(), test_p2_eth_feed_import_does_not_import_pandas()

### Community 102 - "test_article_real_streamed_progress_and_viewmodel_delta"
Cohesion: 0.17
Nodes (5): _commander_with_expanded_events(), test_article_lock_map_stays_bounded(), test_on_demand_article_is_intact_after_the_snapshot(), test_snapshot_carries_no_article_bodies(), test_article_real_streamed_progress_and_viewmodel_delta()

### Community 104 - "_referenced_classes"
Cohesion: 0.33
Nodes (3): _class_value_tokens(), _referenced_classes(), _string_literals()

### Community 108 - "cursors/index.tsx"
Cohesion: 0.18
Nodes (15): clearOverlapTransitionStyles(), drawPriceChart(), invalidateCanvasSizeCache(), locateMouseAndRefreshChart(), refreshScrollAreaFades(), setChartTimeframe(), setIntelSortMode(), setLgWallpaper() (+7 more)

### Community 113 - ".compute_r_multiple_qty"
Cohesion: 0.08
Nodes (7): _parse_pos_dec(), _fresh_broker_competitor(), _r_multiple(), test_evaluate_signal_returns_none_when_breaker_tripped_all_strategies(), test_evaluate_signal_short_entries_mirror_long_brackets_all_strategies(), test_orb_competitor_box_breakout_and_r_multiple(), test_strategy_qty_zero_returns_none()

### Community 138 - "LiveArenaEngine"
Cohesion: 0.08
Nodes (22): LiveArenaEngine, test_signal_exit_fast_path_closes_under_hold_cash(), test_v24_track_b_live_engine_custom_llm_url_and_reset_broker_binding(), test_v24_track_d_view_model_sanitizes_mc_stats_and_dev_bat_structure(), test_stale_engine_save_session_state_refused(), test_close_ticket_bypasses_veto_and_gates_under_hold_cash(), _quote(), test_is_quote_fresh() (+14 more)

### Community 139 - "fix_item5_patch.py"
Cohesion: 0.16
Nodes (19): addChartBeacon(), checkOnboardingBoot(), clearSplashTimers(), enqueueToast(), ensureLiveTradingStarted(), initAppBoot(), openSetupWizardModal(), pollBackend() (+11 more)

### Community 146 - "Choreography"
Cohesion: 0.29
Nodes (6): 1. Launch Packaged Desktop Executable (`.exe`), 2. Run Self-Test Verification, 3. Run Automated Unit Test Suite (32 Tests), 4. Build Standalone Windows Executable, Quick Start Guide, TradeBot0: Multi-Agent Paper Trading & Genetic Evolution Arena (BTC/USD)

## Knowledge Gaps
- **36 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `LiveArenaEngine` connect `LiveArenaEngine` to `test_update_checker.py`, `test_v200_fixes.py`, `test_v260_debug_and_optimize.py`, `BrokerSim`, `ArenaDashboard`, `OrderSide`, `time`, `test_bootstrap_hydrates_fresh_sqlite_candles`, `test_gui_item7.py`, `FillEvent`, `test_phase1_cadence_and_ranking.py`, `.get_ui_state`, `Leaderboard`, `test_performance_and_optimizations.py`, `test_316_bootstrap_reset.py`, `MonteCarloOddsEvaluator`, `test_performance_and_optimizations.py`, `test_mtf_seed_async_25.py`, `timemachine.py`, `ConfigManager`, `test_live_engine.py`, `threading`, `test_debug_report_fixes.py`, `ArenaStorage`, `test_live_chop_gate.py`, `StreamingCryptoFeed`, `LiveStrategyRunnerMixin`, `test_autosave_35.py`, `soak_engine.py`, `test_auto_evolve_fires_on_closed_trades`, `MultiTimeframeEngine`, `MacroCommander`, `test_phase3_soak.py`, `._build_snapshot_locked`, `LiveQuote`, `controls/index.ts`, `SessionCodecMixin`, `.bootstrap_intraday_session`, `test_chop_gate_seed.py`, `test_507_candle_write_on_close.py`, `test_orb_anchor_34.py`, `test_502_ui_state_delta.py`, `persistence.py`, `test_321_auto_redeploy.py`, `test_orb_day_rollover.py`?**
  _High betweenness centrality (0.135) - this node is a cross-community bridge._
- **Are the 8 inferred relationships involving `LiveArenaEngine` (e.g. with `Architectural Highlights` and `ViewModelPublisher`) actually correct?**
  _`LiveArenaEngine` has 8 INFERRED edges - model-reasoned connections that need verification._
- **Should `test_update_checker.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07928118393234672 - nodes in this community are weakly interconnected._
- **Why does `GeminiClient` connect `GeminiClient` to `test_update_checker.py`, `test_v200_fixes.py`, `test_article_real_streamed_progress_and_viewmodel_delta`, `test_v260_debug_and_optimize.py`, `test_forum_collector.py`, `unittest_mock`, `OrderSide`, `time`, `test_gui_item7.py`, `FillEvent`, `test_llm_json_mode_fallback.py`, `asyncio`, `MacroCommander`, `test_performance_and_optimizations.py`, `test_track_c_gemini_max_concurrent_1_repair_no_deadlock`, `test_item12a_omniroute.py`?**
  _High betweenness centrality (0.094) - this node is a cross-community bridge._
- **Are the 81 inferred relationships involving `OrderSide` (e.g. with `main()` and `BrokerSim`) actually correct?**
  _`OrderSide` has 81 INFERRED edges - model-reasoned connections that need verification._
- **Should `test_v200_fixes.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06056166056166056 - nodes in this community are weakly interconnected._
- **Why does `OrderSide` connect `OrderSide` to `test_update_checker.py`, `test_v200_fixes.py`, `TimeMachineArena`, `test_v260_debug_and_optimize.py`, `BrokerSim`, `time`, `test_gui_item7.py`, `FillEvent`, `.get_ui_state`, `Leaderboard`, `test_performance_and_optimizations.py`, `test_performance_and_optimizations.py`, `timemachine.py`, `test_live_engine.py`, `test_debug_report_fixes.py`, `test_live_chop_gate.py`, `LiveStrategyRunnerMixin`, `soak_engine.py`, `test_auto_evolve_fires_on_closed_trades`, `MultiTimeframeEngine`, `MacroCommander`, `test_phase3_soak.py`, `controls/index.ts`, `SessionCodecMixin`, `.compute_r_multiple_qty`?**
  _High betweenness centrality (0.056) - this node is a cross-community bridge._