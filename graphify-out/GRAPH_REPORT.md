# Graph Report - TradeBot0_Local  (2026-11-23)

## Corpus Check
- 132 files · ~181,874 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 10 file(s) not represented in the graph (top: (none) 4, .iss 1, .lnk 1)

## Summary
- 2801 nodes · 7852 edges · 140 communities (99 shown, 41 thin omitted)
- Extraction: 87% EXTRACTED · 13% INFERRED · 0% AMBIGUOUS · INFERRED: 1022 edges (avg confidence: 0.89)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `0b64d193`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- test_phase2_omniroute_client.py
- test_intel_veto.py
- test_update_checker.py
- test_performance_and_optimizations.py
- CandleBar
- logging
- test_item10_packaging.py
- CompetitorGenome
- Leaderboard
- test_ui_contract.py
- ArenaDashboard
- live_engine.py
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
- test_article_prompt_snippet_210.py
- test_track_c_gateway_npm_strips_secrets_and_no_blind_retry
- test_v250_fixes.py
- dashboard.py
- .stop
- StreamingCryptoFeed
- ConfigManager
- test_gateway_autolaunch_mandatory.py
- test_live_engine.py
- _SliceableDeque
- .omniroute_installed
- test_cooperative_stop_event
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
- soak_engine.py
- ArenaStorage
- test_intel_stream_redesign.py
- MonteCarloOddsEvaluator
- RawEvent
- QuoteManager
- InterruptDebouncer
- renderIntelHub
- _FakeCM
- LiveArenaEngine
- test_intel_hub_layout.py
- renderAll
- test_item12a_omniroute.py
- ._build_snapshot_locked
- getCommandPaletteItems
- LiveQuote
- controls/index.ts
- .sync_admin_password
- test_generation_fence.py
- test_phase2_optimize.py
- SessionCodecMixin
- saveAndLaunchGateway
- test_ui_feedback.py
- test_autosave_35.py
- .bootstrap_intraday_session
- test_504_omni_env_cache.py
- .fetch_from_registry
- time
- test_v287_render_guards.py
- GatewaySupervisor
- test_card_reorder_anim.py
- FakeWS
- test_mtf_seed_async_25.py
- .load_session_snapshot
- ._try_enter_bracket
- test_digest_refresh_session.py
- test_502_ui_state_delta.py
- .run_digest_sync
- _referenced_classes
- test_article_real_streamed_progress_and_viewmodel_delta
- test_319_src_ai_gone.py
- test_bootstrap_hydrates_fresh_sqlite_candles
- test_phase2g_graphics.py
- test_orb_anchor_34.py
- test_321_auto_redeploy.py
- test_507_candle_write_on_close.py
- renderPriceCanvas
- test_orb_day_rollover.py
- MultiTimeframeEngine
- cursors/index.tsx
- test_track_c_omniroute_max_concurrent_1_repair_no_deadlock
- _open_short
- test_debug_report_fixes.py
- _FakeHTTPResponse
- OrderSide
- _FakeWindow
- CompetitorGenome
- closeResetModal
- _FakeResp
- test_telemetry_no_articles.py
- isReducedMotionPreferred
- test_320_save_history_storage.py
- _build_engine_view_model_impl
- test_ws_start_stop_delivers_then_stops
- _empty_view_model
- test_snapshot_counters_37.py
- fix_item5_patch.py
- Choreography
- smoke_external.py

## God Nodes (most connected - your core abstractions)
1. `LiveArenaEngine` - 222 edges
2. `OrderSide` - 174 edges
3. `GatewaySupervisor` - 113 edges
4. `BrokerSim` - 112 edges
5. `OmniRouteClient` - 108 edges
6. `OrderTicket` - 102 edges
7. `Portfolio` - 102 edges
8. `MacroCommander` - 88 edges
9. `OrderType` - 83 edges
10. `_ArenaBridgeApi` - 77 edges

## Surprising Connections (you probably didn't know these)
- `Architectural Highlights` --references--> `CompetitorGenome`  [INFERRED]
  README.md → src/competitors/base.py
- `Architectural Highlights` --references--> `GeneticEvolver`  [INFERRED]
  README.md → src/arena/evolution.py
- `Architectural Highlights` --references--> `LiveArenaEngine`  [INFERRED]
  README.md → src/data/live_engine.py
- `test_dashboard_init_passes_configured_port_to_supervisor()` --uses--> `ArenaDashboard`  [INFERRED]
  tests/test_item10_packaging.py → src/gui/dashboard.py
- `test_omniroute_eta_message_formatting()` --uses--> `GatewaySupervisor`  [INFERRED]
  tests/test_gateway_install_progress_cancel.py → src/intelligence/gateway_supervisor.py

## Import Cycles
- None detected.

## Communities (140 total, 41 thin omitted)

### Community 0 - "test_phase2_omniroute_client.py"
Cohesion: 0.10
Nodes (15): compute_backoff(), extract_json(), test_chat_json_400_response_format_rejection_is_not_quota(), test_chat_json_all_retries_429_returns_none(), test_chat_json_per_call_timeout_override(), test_chat_json_repair_retry_gives_up_after_one_failure(), test_chat_json_repair_retry_turns_prose_into_json(), test_chat_json_retries_then_succeeds() (+7 more)

### Community 1 - "test_intel_veto.py"
Cohesion: 0.24
Nodes (8): _fallback_structured(), _run(), _mock_commander(), test_close_ticket_bypasses_veto_and_gates_under_hold_cash(), test_keyword_word_boundaries_no_substring_false_positives(), test_no_fabricated_seed_events_and_honest_quota(), test_veto_never_blocks_close(), _wait_port_open()

### Community 2 - "test_update_checker.py"
Cohesion: 0.08
Nodes (24): _check(), check_for_updates(), compare_versions(), get_manifest_url(), _is_date_version(), test_track_c_update_checker_rejects_non_https_and_clears_download_url_when_up_to_date(), _mock_response(), test_bridge_check_for_updates_not_configured() (+16 more)

### Community 3 - "test_performance_and_optimizations.py"
Cohesion: 0.06
Nodes (39): GeneticEvolver, __getattr__(), AggressiveCompetitor, ConservativeCompetitor, ORBCompetitor, SessionMeanPullbackCompetitor, TrailingGuardCompetitor, test_evolve_generation_early_return_does_not_crash() (+31 more)

### Community 6 - "CandleBar"
Cohesion: 0.09
Nodes (21): CompetitorStats, CandleBar, TimeMachineArena, _bar(), _choppy_bars(), test_gate_blocks_entries_on_choppy_tape(), test_gate_inactive_on_trend_tape(), test_gate_never_blocks_closes() (+13 more)

### Community 7 - "logging"
Cohesion: 0.12
Nodes (10): configure_logging(), get_log_dir(), _SafeRotatingFileHandler, _flush_file_handlers(), _remove_test_handlers(), test_configure_logging_never_raises_on_unwritable_dir(), test_get_log_dir_resolution(), test_stream_handler_present_when_stdout_exists() (+2 more)

### Community 8 - "test_item10_packaging.py"
Cohesion: 0.08
Nodes (15): _FakeNpmProc, _FakeNpmProcFail, _FakeURLDownload, _make_bridge(), _make_node_zip_bytes(), _node_supervisor(), test_admin_password_required_before_onboarding(), test_console_url_follows_gateway_port() (+7 more)

### Community 9 - "CompetitorGenome"
Cohesion: 0.08
Nodes (43): Architectural Highlights, BrokerSim, OrderTicket, OrderType, Portfolio, RiskGuard, _open_long(), test_apply_fill_value_error_does_not_kill_cadence() (+35 more)

### Community 10 - "Leaderboard"
Cohesion: 0.08
Nodes (22): Leaderboard, _counting_periods(), _portfolio_with_history(), test_fill_invalidates_cache(), test_metrics_cached_across_ticks_with_no_fills(), test_replace_equity_history_invalidates_cache(), test_reset_invalidates_cache(), test_risk_free_rate_change_invalidates_cache() (+14 more)

### Community 11 - "test_ui_contract.py"
Cohesion: 0.15
Nodes (15): _badge_cls_producer_values(), _bridge_class_node(), _bridge_methods(), _bridge_obj_calls(), _bridge_self_calls(), _defined_classes(), _html_ids(), _js_defined_functions() (+7 more)

### Community 12 - "ArenaDashboard"
Cohesion: 0.05
Nodes (28): check_and_ensure_environment(), main(), ArenaDashboard, _activate_foreground_startup(), _on_window_closing(), _on_window_shown(), _delayed_activation(), close_native_splash() (+20 more)

### Community 14 - "live_engine.py"
Cohesion: 0.15
Nodes (11): ExecutionReason, OrderStatus, PositionSide, BaseCompetitor, test_signal_exit_fast_path_closes_under_hold_cash(), _broker(), test_aggressive_stopout_loss_capped_at_risk_pct(), test_drawdown_trip_closes_positions_via_broker() (+3 more)

### Community 15 - "IntelligenceHarvester"
Cohesion: 0.11
Nodes (7): IntelligenceHarvester, test_process_batch_carries_tier_thread_and_consensus(), _run(), test_process_batch_fallback_consensus_from_score(), _run(), test_harvester_stage1_processing_and_urgent_interrupt(), _run()

### Community 17 - "ViewModelPublisher"
Cohesion: 0.22
Nodes (3): ViewModelPublisher, test_track_d_view_model_publisher_excludes_fills_and_detects_is_live_change(), test_view_model_delta_omits_unchanged_history_and_intel_events_equivalently()

### Community 18 - "OmniRouteClient"
Cohesion: 0.05
Nodes (37): _looks_like_format_rejection(), OmniRouteClient, _mock_resp(), _mock_session(), test_chat_json_402_records_quota_failure(), _run(), test_chat_json_connection_refused_records_connection(), _run() (+29 more)

### Community 19 - "Portfolio"
Cohesion: 0.08
Nodes (21): FillEvent, isolate_arena_memory(), _git(), test_system_config_is_ignored_by_git(), test_system_config_is_untracked_but_present_on_disk(), test_track_a_portfolio_cross_gen_leverage_partial_close_conserves_equity(), test_track_a_portfolio_failed_fill_does_not_corrupt_fees(), test_v24_track_a_portfolio_apply_fill_upfront_quantization() (+13 more)

### Community 21 - "MacroCommander"
Cohesion: 0.04
Nodes (29): StructuredEvent, _dedup_tickers(), _event_age_min(), MacroCommander, _runner(), _on_progress(), _shutting_down(), MacroRegimeState (+21 more)

### Community 22 - "_make_supervisor"
Cohesion: 0.06
Nodes (25): _fake_node_zip_bytes(), _FakeDownloadResp, _make_supervisor(), _setup_npm_only_env(), _SlowResp, test_bridge_cancel_and_status_shape(), test_cancel_during_node_download(), test_cancel_during_npm_install_removes_partial_package() (+17 more)

### Community 23 - "._get_daemon_command"
Cohesion: 0.16
Nodes (3): test_daemon_command_falls_back_to_global(), test_daemon_command_prefers_runtime_install(), test_gateway_cli_command_never_falls_back_to_npx()

### Community 25 - "syncAppShellInert"
Cohesion: 0.14
Nodes (20): blurActiveFocus(), closeInstallCancelConfirm(), closeSetupWizardModal(), closeWizardCloseConfirm(), confirmCancelInstallAndClose(), confirmCloseWizardWithoutSaving(), handleInstallCancelOverlayClick(), handleWizardCloseOverlayClick() (+12 more)

### Community 26 - "test_phase3_ingestion.py"
Cohesion: 0.10
Nodes (18): parse_polymarket_events(), parse_reddit_posts(), parse_rss_atom(), test_feed_numeric_parsing_never_raises(), _fake_registry_response(), _new_harvester(), _registry_get_ok(), test_feed_registry_completeness_r3() (+10 more)

### Community 27 - "soak_engine.py"
Cohesion: 0.07
Nodes (27): ETHFeed, _engine(), _feed_1m(), _tape_end_anchored(), _tape_slot_aligned(), test_seed_helper_feeds_continuous_chain_and_arms_gate(), test_seed_helper_gap_truncates_to_suffix_after_gap(), test_seed_helper_malformed_row_skipped_not_fabricated() (+19 more)

### Community 28 - "Stage"
Cohesion: 0.06
Nodes (36): animCandles, changeEvolveInterval(), chartBeacons, closeShutdownModal(), copyOmniPassword(), currentSplashSteps, EVOLVE_INTERVAL_OPTIONS, flashOmniPwdBadge() (+28 more)

### Community 29 - "re"
Cohesion: 0.22
Nodes (10): _compile_word_group(), _compiled_word_re(), _contains_word(), _css(), _css_block(), test_article_renders_with_fade_in(), test_chevron_and_accordion_spring(), test_get_event_article_removed_from_dead_list() (+2 more)

### Community 30 - "test_article_prompt_snippet_210.py"
Cohesion: 0.36
Nodes (6): build_event_article_prompts(), _event_dict(), test_prompt_includes_raw_snippet(), test_prompt_without_snippet_omits_line(), test_telemetry_strips_raw_snippet(), test_article_prompt_asks_for_1000_words_and_six_paragraphs()

### Community 31 - "test_track_c_gateway_npm_strips_secrets_and_no_blind_retry"
Cohesion: 0.13
Nodes (5): test_track_c_gateway_npm_strips_secrets_and_no_blind_retry(), _fake_popen(), _FakeProc, test_gateway_env_sets_server_host_and_strips_provider_keys_when_env_exists(), _fake_popen()

### Community 32 - "test_v250_fixes.py"
Cohesion: 0.10
Nodes (5): efficiency_ratio(), _clean_html_text(), test_efficiency_ratio_unit(), test_genetic_evolver_never_emits_1x_leveraged_genome(), test_ingestion_clean_html_strips_script_style_and_dedup_forget()

### Community 33 - "dashboard.py"
Cohesion: 0.05
Nodes (13): _build_html_template(), _get_assets_dir(), _load_asset(), _load_binary_data_uri(), test_start_daemon_default_wait_is_30_seconds(), test_gateway_supervisor_http_responses(), test_ui_assets_art_jargon_and_cjk_cleanliness(), test_grainient_webp_asset_and_inline_injection() (+5 more)

### Community 34 - ".stop"
Cohesion: 0.14
Nodes (14): build_engine_view_model(), test_v24_track_d_view_model_sanitizes_mc_stats_and_dev_bat_structure(), _rankings(), test_shutdown_closes_window_on_calling_thread(), test_view_model_does_not_fabricate_take_profit(), test_view_model_reports_unknown_mc_and_quota(), test_view_model_short_unrealized_pnl_pct(), test_view_model_skips_stale_ranking_entry() (+6 more)

### Community 35 - "StreamingCryptoFeed"
Cohesion: 0.20
Nodes (3): StreamingCryptoFeed, test_phase1_websocket_feed_parsing_and_fast_path_fallback(), test_parse_binance_ticker_rejects_garbage()

### Community 36 - "ConfigManager"
Cohesion: 0.07
Nodes (13): ConfigManager, format_omni_env_value(), parse_omni_env_line(), test_track_c_config_manager_refuses_to_wipe_unreadable_env(), test_v24_track_c_env_roundtrip_and_no_initial_password_in_environ(), test_gateway_auto_spawn_option_removed(), test_bridge_stepwise_simulation_erroneous_then_valid(), test_config_manager_atomic_recovery_from_corruption() (+5 more)

### Community 37 - "test_gateway_autolaunch_mandatory.py"
Cohesion: 0.11
Nodes (9): _assets_root(), _FakeEvent, _FakeWebview, _FakeWindow, _make_bridge(), test_run_spawns_despite_stored_false(), test_save_and_launch_spawns_despite_stored_false(), test_setup_status_has_no_autolaunch_option() (+1 more)

### Community 38 - "test_live_engine.py"
Cohesion: 0.06
Nodes (34): _coinbase_stats_payload(), _coinbase_ticker_payload(), _drive_fixed(), _fixture_bars(), _kraken_payload(), _mock_resp(), _open_long(), _quote() (+26 more)

### Community 40 - ".omniroute_installed"
Cohesion: 0.22
Nodes (3): test_gateway_unavailable_reason_no_node(), test_gateway_unavailable_reason_node_but_no_omniroute(), test_start_runtime_install_does_not_start_twice()

### Community 41 - "test_cooperative_stop_event"
Cohesion: 0.29
Nodes (3): _raise_no_network(), test_cooperative_stop_event(), test_slow_bootstrap_stop_safety()

### Community 42 - ".shutdown"
Cohesion: 0.10
Nodes (8): test_start_daemon_polls_health_with_2s_timeout_and_logs_to_file(), fake_probe(), test_start_daemon_spawns_and_waits_with_fake_proc(), test_start_daemon_times_out_when_health_never_ok(), _free_port(), test_shutdown_does_not_kill_foreign_process(), test_shutdown_kills_own_child(), test_start_daemon_concurrent_calls_spawn_once()

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
Nodes (9): _run_feed(), test_ws_clean_server_close_counts_as_reconnect(), test_ws_connect_and_stream_delivers_quotes(), _fake_connect(), _on_quote(), test_ws_reconnect_backoff_on_disconnect(), _fake_connect(), _fake_sleep() (+1 more)

### Community 48 - "._run_runtime_install"
Cohesion: 0.09
Nodes (4): _default_daemon_log_path(), _default_install_log_path(), _InstallCancelledError, test_daemon_log_default_path_is_project_logs()

### Community 50 - "DeduplicationBuffer"
Cohesion: 0.18
Nodes (5): _dedup_normalize_title(), DeduplicationBuffer, _retry_window_seconds(), test_v24_track_c_omniroute_extract_json_retry_hint_dedup_and_https_redirect(), test_deduplication_buffer()

### Community 51 - "test_gateway_diagnosis.py"
Cohesion: 0.05
Nodes (49): classify_llm_error(), _error_body_text(), _walk(), _extract_error_provider(), _client(), _css(), _FakeEvent, _FakeWebview (+41 more)

### Community 52 - "test_phase1_debug_sweep.py"
Cohesion: 0.06
Nodes (21): test_manual_evolve_does_not_block_bridge(), _StubGateway, test_four_threads_expand_concurrently_without_closing_each_other(), _one(), _worker(), _OKHandler, _quote(), _safe_refresh() (+13 more)

### Community 53 - "test_llm_json_mode_fallback.py"
Cohesion: 0.18
Nodes (7): _client_with(), _CM, _FakeSession, _Resp, test_generic_400_does_not_trigger_the_format_retry(), test_rejected_format_is_remembered_for_later_calls(), test_rejected_response_format_retries_without_it_and_parses()

### Community 54 - "soak_engine.py"
Cohesion: 0.14
Nodes (14): closing_fills_since(), db_stats(), do_slice(), genome_valid(), main(), _sample(), make_quote(), _parse_args() (+6 more)

### Community 55 - "ArenaStorage"
Cohesion: 0.20
Nodes (5): ArenaStorage, _retry_on_db_error(), test_track_b_persistence_batch_fills_and_prune_candles(), test_phase2_sqlite_wal_persistence_and_cold_start_hydration(), test_p2_persistent_connection_reused_and_candle_persists_across_close()

### Community 56 - "test_intel_stream_redesign.py"
Cohesion: 0.21
Nodes (16): _fn_body(), _html(), _js(), test_article_failure_shows_reason_not_summary(), test_article_lazy_once_and_cached(), test_article_loading_shows_determinate_stage_progress_bar(), test_article_render_is_not_rewritten_every_tick(), test_articles_preload_while_collapsed() (+8 more)

### Community 57 - "MonteCarloOddsEvaluator"
Cohesion: 0.10
Nodes (12): MonteCarloBracketOdds, MonteCarloOddsEvaluator, test_track_b_non_integer_cadence_advances_slots(), test_track_b_quote_feeds_rejects_non_positive_and_non_finite(), test_track_b_timemachine_rejects_wrong_side_tp(), test_track_d_frontend_contracts_css_html_js(), test_v24_track_b_timemachine_single_sim_and_flat_empirical_candles(), test_monte_carlo_ev_gate_odds_evaluation() (+4 more)

### Community 58 - "RawEvent"
Cohesion: 0.13
Nodes (14): ForumCollector, parse_stocktwits_stream(), RawEvent, _stream_json(), test_forum_batch_scored_without_llm_when_offline(), mock_get(), test_forum_collector_fast_test_short_circuits(), test_forum_collector_hourly_cap() (+6 more)

### Community 59 - "QuoteManager"
Cohesion: 0.23
Nodes (3): QuoteManager, test_dead_cascade_state_is_gone(), test_ws_quote_path_still_works()

### Community 60 - "InterruptDebouncer"
Cohesion: 0.18
Nodes (4): InterruptDebouncer, _parse_iso_ts(), test_stage2_interrupt_debouncing_r4(), _run()

### Community 61 - "renderIntelHub"
Cohesion: 0.12
Nodes (24): buildIntelEventCard(), cleanIntelSummary(), clearIntelSearch(), formatIntelEventTime(), hashTickerName(), initIntelFilterControls(), intelArticleBodyEl(), intelEventKey() (+16 more)

### Community 63 - "LiveArenaEngine"
Cohesion: 0.11
Nodes (20): LiveArenaEngine, test_get_ui_state_mutation_isolation(), test_pause_feed_updates_ui_snapshot_immediately(), test_stale_engine_save_session_state_refused(), _drive(), test_auto_evolve_timer_and_toggle(), test_fill_event_has_monotonic_seq_and_action_label(), test_live_engine_bidirectional_long_and_short_execution() (+12 more)

### Community 64 - "test_intel_hub_layout.py"
Cohesion: 0.25
Nodes (12): _commander(), _css(), _js(), _mock_pipeline(), _rule(), _structured(), test_stream_loading_block_is_centered_with_meter(), test_sync_status_failed_when_feeds_down() (+4 more)

### Community 65 - "renderAll"
Cohesion: 0.16
Nodes (23): buildSparklineGeometry(), createPositionClosedToastElement(), createPositionToastElement(), createStrategyCardSkeleton(), escapeHtml(), fmtPct(), fmtSignedUsd(), fmtTimeSec() (+15 more)

### Community 66 - "test_item12a_omniroute.py"
Cohesion: 0.29
Nodes (6): _now_iso(), _offline_commander(), _strong_bearish_events(), test_empty_digest_expires_stale_fallback(), test_fallback_clears_when_llm_recovers(), test_fallback_regime_is_marked_and_expires()

### Community 68 - "getCommandPaletteItems"
Cohesion: 0.15
Nodes (17): applyBackdropMode(), closeCommandPalette(), cycleBackdropMode(), getCommandPaletteItems(), handleCmdPaletteOverlayClick(), initCommandPalette(), openCommandPalette(), openOmniRouteConsole() (+9 more)

### Community 70 - "controls/index.ts"
Cohesion: 0.33
Nodes (6): _commander(), test_no_confidence_means_no_sizing_effect(), test_per_strategy_sensitivity_scales_the_deviation(), test_sizing_formula_exact_values(), test_tp_stretch_uses_sizing_mult_not_raw_rm(), _tp_engine()

### Community 72 - "test_generation_fence.py"
Cohesion: 0.32
Nodes (4): _keyframes_block(), _make_fill(), test_splash_overlay_is_lightened_not_removed(), test_stale_engine_harvest_fills_refused()

### Community 73 - "test_phase2_optimize.py"
Cohesion: 0.19
Nodes (9): wrapper(), _candle(), test_p2_concurrent_candle_writes_all_persist(), writer(), test_p2_engine_stop_closes_storage_and_restart_still_writes(), test_p2_eth_feed_first_fetch_loads_pandas_and_behaves(), test_p2_eth_feed_import_does_not_import_pandas(), test_p2_persistent_connection_recovers_from_stale_handle() (+1 more)

### Community 75 - "saveAndLaunchGateway"
Cohesion: 0.18
Nodes (18): applyGatewayAvailability(), clearSplashTimers(), confirmShutdown(), destroyAmbientBackdrop(), ensureRuntimeInstallPoll(), initAppBoot(), installGatewayRuntime(), openSetupWizardModal() (+10 more)

### Community 76 - "test_ui_feedback.py"
Cohesion: 0.23
Nodes (7): _copy_text_to_clipboard_windows(), _bridge_with_env(), test_copy_password_copies_value_but_never_returns_it(), test_copy_password_helper_failure(), test_copy_password_not_configured(), test_copy_text_to_clipboard_windows_non_windows(), test_copy_text_to_clipboard_windows_roundtrip()

### Community 77 - "test_autosave_35.py"
Cohesion: 0.18
Nodes (8): _bars(), _engine(), _raise_no_network(), test_autosave_does_not_fire_when_stopped_or_superseded(), test_crash_like_stop_leaves_restorable_autosave(), test_evolution_marks_autosave_pending_and_it_fires_immediately(), test_live_loop_triggers_periodic_autosave(), test_periodic_autosave_writes_snapshot_when_interval_elapses()

### Community 78 - ".bootstrap_intraday_session"
Cohesion: 0.07
Nodes (12): _on_done(), _fixture_bars(), test_bootstrap_resets_live_trading_state_when_orders_disabled(), _fixture_bars(), test_full_restore_bootstrap_start_integration(), test_offline_start_does_not_execute_stale_candles(), test_start_live_trading_readiness_handshake(), test_stale_engine_evolve_now_refused() (+4 more)

### Community 79 - "test_504_omni_env_cache.py"
Cohesion: 0.28
Nodes (8): _counting_read_text(), _manager(), test_content_change_is_visible_after_rewrite(), test_missing_file_then_created(), test_mtime_change_invalidates_even_with_same_content(), test_repeated_reads_hit_cache(), test_returned_dict_is_a_copy(), test_write_then_read_sees_new_password()

### Community 80 - ".fetch_from_registry"
Cohesion: 0.12
Nodes (5): _registry_mock_get(), test_fetch_from_registry_dispatches_by_type_and_skips_forum(), test_fetch_live_feeds_still_returns_test_fixtures(), test_dedup_hits_counted_not_token_estimate(), test_p2_fetch_from_registry_parallel_same_events_faster()

### Community 81 - "time"
Cohesion: 0.12
Nodes (5): parse_symbol_pairs(), _quote(), test_generate_fallback_bars_deleted(), test_is_quote_fresh(), test_provider_cooldown_respected_when_all_cooling()

### Community 82 - "test_v287_render_guards.py"
Cohesion: 0.40
Nodes (7): _fn_body(), _js(), test_hub_header_writes_guarded(), test_intel_card_element_refs_cached(), test_macro_ribbon_writes_guarded(), test_spotlight_vars_written_once_per_frame(), test_strat_color_and_gen_label_writes_guarded()

### Community 83 - "GatewaySupervisor"
Cohesion: 0.10
Nodes (8): GatewaySupervisor, test_v24_track_c_gemini_header_and_save_gateway_no_split_brain(), test_watchdog_backoff_schedule(), test_daemon_log_rotates_over_5mb(), test_gateway_supervisor_key_validation_defensive(), test_gateway_supervisor_nvidia_endpoint(), test_key_rate_limit_429_is_not_verified(), test_gateway_test_single_key_non_ascii_and_gemini_400()

### Community 84 - "test_card_reorder_anim.py"
Cohesion: 0.35
Nodes (10): _css(), _js(), _reorder_block(), test_cards_are_stable_nodes_never_recreated_on_reorder(), test_flip_cleanup_clears_class_and_transform(), test_flip_inverts_with_translate_and_plays_via_class(), test_flip_records_first_rects_before_moving_nodes(), test_flip_runs_only_when_order_changes() (+2 more)

### Community 87 - ".load_session_snapshot"
Cohesion: 0.22
Nodes (4): _sanitize_json_value(), test_restore_survives_garbage_stop_ticket_and_entry_ts(), test_persistence_sanitizes_nan_and_inf_strict_json(), test_session_codec_rejects_symbol_mismatch_and_roundtrips_pending_and_orb()

### Community 88 - "._try_enter_bracket"
Cohesion: 0.23
Nodes (17): _dead_gateway_commander(), _mock_pipeline(), _structured(), test_sync_status_done_when_dead_gateway_still_yields_fallback_digest(), test_sync_status_failed_when_gateway_dead_and_nothing_produced(), _ev(), _now_iso(), _offline_commander() (+9 more)

### Community 89 - "test_digest_refresh_session.py"
Cohesion: 0.23
Nodes (5): _FakeForum, _FakeHarvester, _make_commander(), test_concurrent_article_call_survives_refresh(), test_two_refreshes_leave_session_open()

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

### Community 98 - "test_orb_anchor_34.py"
Cohesion: 0.20
Nodes (5): _tape_bar(), test_backtest_orb_range_anchored_to_first_15_tape_bars(), test_bootstrap_anchors_orb_range_to_first_15_warmup_bars(), test_live_orb_range_does_not_drift_with_rolling_buffer(), _warmup_bars()

### Community 99 - "test_321_auto_redeploy.py"
Cohesion: 0.39
Nodes (5): _flat_engine(), test_no_redeploy_when_any_position_open(), test_redeploy_logs_once_per_flat_episode(), test_switch_off_does_not_redeploy(), test_switch_on_default_redeploys_when_flat()

### Community 100 - "test_507_candle_write_on_close.py"
Cohesion: 0.42
Nodes (7): _counting_save(), _engine(), test_bar_close_persists_final_bar_once(), test_closed_bar_is_in_sqlite_after_close(), test_out_of_order_tick_does_not_double_save(), test_three_minutes_persist_two_closed_bars(), test_ticks_within_one_minute_write_nothing()

### Community 101 - "renderPriceCanvas"
Cohesion: 0.22
Nodes (9): fillRoundRect(), isSplashGateOpen(), renderPriceCanvas(), setSplashTarget(), setupHiDPICanvas(), startChartAnimLoop(), stepChartAnimLoop(), strokeRoundRect() (+1 more)

### Community 104 - "test_orb_day_rollover.py"
Cohesion: 0.36
Nodes (5): _minute_candles(), _tape_bar(), test_backtest_orb_range_rolls_at_utc_midnight(), test_live_orb_range_is_forming_on_a_partial_new_day(), test_live_orb_range_rolls_at_utc_midnight()

### Community 107 - "MultiTimeframeEngine"
Cohesion: 0.08
Nodes (16): IndicatorEngineMixin, MultiTimeframeEngine, test_track_b_mtf_engine_delta_volume_and_neutral_on_conflict(), test_v24_track_b_mtf_seed_1h_merges_same_slot(), _buckets(), _hourly_bars(), _minute_bars(), test_engine_seed_fetch_failure_stays_neutral() (+8 more)

### Community 108 - "cursors/index.tsx"
Cohesion: 0.21
Nodes (13): clearOverlapTransitionStyles(), drawPriceChart(), invalidateCanvasSizeCache(), locateMouseAndRefreshChart(), setIntelSortMode(), setLgWallpaper(), setRightTab(), setScaleMode() (+5 more)

### Community 110 - "_open_short"
Cohesion: 0.20
Nodes (5): _open_short(), test_evaluate_live_strategies_short_exits_are_signal_only(), test_evaluate_live_strategies_small_gain_does_not_close_shorts(), test_stagnation_exit_closes_after_40m(), test_trailing_guard_short_ratchet_moves_stop_down()

### Community 111 - "test_debug_report_fixes.py"
Cohesion: 0.29
Nodes (3): test_session_save_and_restore_with_locked_margin(), test_start_live_trading_does_not_wipe_restored_positions(), test_trade_and_equity_history_persistence()

### Community 113 - "OrderSide"
Cohesion: 0.08
Nodes (15): OrderSide, _fresh_broker_competitor(), _r_multiple(), test_evaluate_signal_returns_none_when_breaker_tripped_all_strategies(), test_evaluate_signal_short_entries_mirror_long_brackets(), test_evaluate_signal_short_entries_mirror_long_brackets_all_strategies(), test_orb_competitor_box_breakout_and_r_multiple(), test_session_mean_competitor_pullback_and_r_multiple() (+7 more)

### Community 115 - "CompetitorGenome"
Cohesion: 0.12
Nodes (3): CompetitorGenome, _parse_pos_dec(), test_genome_rejects_nonsense()

### Community 123 - "closeResetModal"
Cohesion: 0.40
Nodes (6): closeResetModal(), confirmResetArena(), handleResetOverlayClick(), initResetSlideConfirm(), resetArena(), resetSlideConfirmState()

### Community 125 - "_FakeResp"
Cohesion: 0.33
Nodes (3): post(), _FakeResp, post()

### Community 126 - "test_telemetry_no_articles.py"
Cohesion: 0.53
Nodes (4): _commander_with_expanded_events(), test_article_lock_map_stays_bounded(), test_on_demand_article_is_intact_after_the_snapshot(), test_snapshot_carries_no_article_bodies()

### Community 127 - "isReducedMotionPreferred"
Cohesion: 0.40
Nodes (5): initAmbientBackdrop(), isReducedMotionPreferred(), morphText(), mountSilverStreamAmbient(), renderMacroRibbon()

### Community 128 - "test_320_save_history_storage.py"
Cohesion: 0.40
Nodes (6): _records(), test_save_history_closes_storage_it_creates(), close(), __init__(), test_save_history_reuses_caller_storage_without_closing(), __init__()

### Community 138 - "test_snapshot_counters_37.py"
Cohesion: 0.27
Nodes (5): _bars(), _round_trips(), _stats_for(), test_short_history_is_not_marked_truncated(), test_snapshot_counters_survive_restore_with_truncated_history()

### Community 139 - "fix_item5_patch.py"
Cohesion: 0.18
Nodes (15): addChartBeacon(), attachToastInteractions(), checkOnboardingBoot(), dismissToast(), enqueueToast(), ensureLiveTradingStarted(), pollBackend(), previewPositionAnimation() (+7 more)

### Community 146 - "Choreography"
Cohesion: 0.29
Nodes (6): 1. Launch Packaged Desktop Executable (`.exe`), 2. Run Self-Test Verification, 3. Run Automated Unit Test Suite (32 Tests), 4. Build Standalone Windows Executable, Quick Start Guide, TradeBot0: Multi-Agent Paper Trading & Genetic Evolution Arena (BTC/USD)

### Community 161 - "smoke_external.py"
Cohesion: 0.25
Nodes (14): check_binance_rest(), check_binance_ws(), _run(), check_ccxt_kraken(), check_coinbase_rest(), check_feed_registry(), check_kraken_rest(), check_node_head() (+6 more)

## Knowledge Gaps
- **41 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `LiveArenaEngine` connect `LiveArenaEngine` to `test_intel_veto.py`, `test_performance_and_optimizations.py`, `CandleBar`, `CompetitorGenome`, `Leaderboard`, `test_snapshot_counters_37.py`, `ArenaDashboard`, `live_engine.py`, `ViewModelPublisher`, `OmniRouteClient`, `Portfolio`, `MacroCommander`, `soak_engine.py`, `test_v250_fixes.py`, `dashboard.py`, `.stop`, `StreamingCryptoFeed`, `ConfigManager`, `test_live_engine.py`, `test_cooperative_stop_event`, `test_live_chop_gate.py`, `LiveStrategyRunnerMixin`, `test_phase1_debug_sweep.py`, `soak_engine.py`, `ArenaStorage`, `MonteCarloOddsEvaluator`, `QuoteManager`, `._build_snapshot_locked`, `LiveQuote`, `controls/index.ts`, `test_generation_fence.py`, `test_phase2_optimize.py`, `SessionCodecMixin`, `test_autosave_35.py`, `.bootstrap_intraday_session`, `time`, `.load_session_snapshot`, `test_502_ui_state_delta.py`, `test_bootstrap_hydrates_fresh_sqlite_candles`, `.is_fresh`, `test_orb_anchor_34.py`, `test_321_auto_redeploy.py`, `test_507_candle_write_on_close.py`, `test_orb_day_rollover.py`, `MultiTimeframeEngine`, `_open_short`, `test_debug_report_fixes.py`, `OrderSide`?**
  _High betweenness centrality (0.173) - this node is a cross-community bridge._
- **Are the 28 inferred relationships involving `LiveArenaEngine` (e.g. with `Architectural Highlights` and `BrokerSim`) actually correct?**
  _`LiveArenaEngine` has 28 INFERRED edges - model-reasoned connections that need verification._
- **Should `test_phase2_omniroute_client.py` be split into smaller, more focused modules?**
  _Cohesion score 0.1 - nodes in this community are weakly interconnected._
- **Why does `GatewaySupervisor` connect `GatewaySupervisor` to `test_intel_veto.py`, `test_item10_packaging.py`, `test_ui_contract.py`, `ArenaDashboard`, `.start_daemon`, `_make_supervisor`, `._get_daemon_command`, `test_track_c_gateway_npm_strips_secrets_and_no_blind_retry`, `test_v250_fixes.py`, `dashboard.py`, `.stop`, `ConfigManager`, `test_gateway_autolaunch_mandatory.py`, `.omniroute_installed`, `.shutdown`, `test_save_launch_progress.py`, `._run_runtime_install`, `test_gateway_diagnosis.py`, `test_phase1_debug_sweep.py`, `MonteCarloOddsEvaluator`, `test_item12a_omniroute.py`, `.sync_admin_password`, `_FakeHTTPResponse`?**
  _High betweenness centrality (0.084) - this node is a cross-community bridge._
- **Are the 104 inferred relationships involving `OrderSide` (e.g. with `main()` and `BrokerSim`) actually correct?**
  _`OrderSide` has 104 INFERRED edges - model-reasoned connections that need verification._
- **Should `test_update_checker.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07676767676767676 - nodes in this community are weakly interconnected._
- **Why does `OmniRouteClient` connect `OmniRouteClient` to `test_phase2_omniroute_client.py`, `test_intel_veto.py`, `test_performance_and_optimizations.py`, `test_item10_packaging.py`, `live_engine.py`, `IntelligenceHarvester`, `MacroCommander`, `test_v250_fixes.py`, `dashboard.py`, `test_gateway_diagnosis.py`, `test_phase1_debug_sweep.py`, `test_llm_json_mode_fallback.py`, `MonteCarloOddsEvaluator`, `RawEvent`, `InterruptDebouncer`, `LiveArenaEngine`, `test_item12a_omniroute.py`, `.fetch_from_registry`, `test_digest_refresh_session.py`, `.run_digest_sync`, `test_article_real_streamed_progress_and_viewmodel_delta`, `test_track_c_omniroute_max_concurrent_1_repair_no_deadlock`, `._all_sessions`, `test_telemetry_no_articles.py`?**
  _High betweenness centrality (0.067) - this node is a cross-community bridge._