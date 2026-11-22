# Graph Report - TradeBot0_Local  (2026-11-23)

## Corpus Check
- 129 files · ~172,915 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 10 file(s) not represented in the graph (top: (none) 4, .iss 1, .lnk 1)

## Summary
- 2709 nodes · 7665 edges · 133 communities (95 shown, 38 thin omitted)
- Extraction: 86% EXTRACTED · 14% INFERRED · 0% AMBIGUOUS · INFERRED: 1048 edges (avg confidence: 0.89)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `e31e626f`
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
- OrderSide
- IntelligenceHarvester
- .start_daemon
- ViewModelPublisher
- OmniRouteClient
- Portfolio
- _ArenaBridgeApi
- MacroCommander
- _make_supervisor
- GatewaySupervisor
- _symbols_from_registry
- syncAppShellInert
- test_phase3_ingestion.py
- soak_engine.py
- Stage
- ingestion.py
- .run
- test_track_c_gateway_npm_strips_secrets_and_no_blind_retry
- time
- ArenaStorage
- test_gui_item7.py
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
- .test_single_key
- ._get_connection
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
- test_item12a_omniroute.py
- ._build_snapshot_locked
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
- .get_gateway_diagnosis
- test_digest_refresh_session.py
- live_engine.py
- _StubGateway
- .sync_admin_password
- test_card_reorder_anim.py
- FakeWS
- test_mtf_seed_async_25.py
- test_507_candle_write_on_close.py
- ._try_enter_bracket
- _mock_resp
- _open_short
- .run_digest_sync
- test_orb_anchor_34.py
- subprocess
- parse_omni_env_line
- .bootstrap_intraday_session
- test_phase2g_graphics.py
- conftest.py
- test_321_auto_redeploy.py
- presence/index.tsx
- _make_bridge
- _FakeWindow
- ._reset_connection
- test_orb_day_rollover.py
- test_wizard_close_confirm_dialog
- test_restore_applies_genome_leverage_to_portfolio
- MultiTimeframeEngine
- cursors/index.tsx
- .chat_json
- _error_body_text
- _open_long
- test_gateway_item8.py
- test_competitors.py
- _OKHandler
- test_track_b_quote_feeds_rejects_non_positive_and_non_finite
- closeResetModal
- fix_item5_patch.py
- Choreography
- smoke_external.py
- test_phase3_soak.py

## God Nodes (most connected - your core abstractions)
1. `LiveArenaEngine` - 223 edges
2. `OrderSide` - 183 edges
3. `GatewaySupervisor` - 115 edges
4. `BrokerSim` - 112 edges
5. `OmniRouteClient` - 106 edges
6. `OrderTicket` - 102 edges
7. `Portfolio` - 102 edges
8. `OrderType` - 89 edges
9. `MacroCommander` - 88 edges
10. `ExecutionReason` - 80 edges

## Surprising Connections (you probably didn't know these)
- `Architectural Highlights` --references--> `BrokerSim`  [INFERRED]
  README.md → src/arena/broker_sim.py
- `Architectural Highlights` --references--> `Portfolio`  [INFERRED]
  README.md → src/arena/portfolio.py
- `Architectural Highlights` --references--> `LiveArenaEngine`  [INFERRED]
  README.md → src/data/live_engine.py
- `Architectural Highlights` --references--> `GeneticEvolver`  [INFERRED]
  README.md → src/arena/evolution.py
- `test_last_records_class_default_present()` --uses--> `GeneticEvolver`  [INFERRED]
  tests/test_311_last_records.py → src/arena/evolution.py

## Import Cycles
- None detected.

## Communities (133 total, 38 thin omitted)

### Community 0 - "test_phase2_omniroute_client.py"
Cohesion: 0.09
Nodes (24): compute_backoff(), extract_json(), _mock_429_session(), _mock_resp(), test_chat_json_400_response_format_rejection_is_not_quota(), _run(), test_chat_json_all_retries_429_returns_none(), _run() (+16 more)

### Community 1 - "json"
Cohesion: 0.53
Nodes (4): _commander_with_expanded_events(), test_article_lock_map_stays_bounded(), test_on_demand_article_is_intact_after_the_snapshot(), test_snapshot_carries_no_article_bodies()

### Community 2 - "test_update_checker.py"
Cohesion: 0.08
Nodes (24): _check(), check_for_updates(), compare_versions(), get_manifest_url(), _is_date_version(), test_track_c_update_checker_rejects_non_https_and_clears_download_url_when_up_to_date(), _mock_response(), test_bridge_check_for_updates_not_configured() (+16 more)

### Community 3 - "test_v200_fixes.py"
Cohesion: 0.06
Nodes (36): Architectural Highlights, GeneticEvolver, CompetitorStats, AggressiveCompetitor, BaseCompetitor, CompetitorGenome, ConservativeCompetitor, ORBCompetitor (+28 more)

### Community 6 - "TimeMachineArena"
Cohesion: 0.11
Nodes (11): CandleBar, _fixture_bars(), test_bootstrap_resets_live_trading_state_when_orders_disabled(), _bars(), _fixture_bars(), test_evolution_tournament_runs_multiple_generations(), test_orb_window_excludes_current_bar(), test_timemachine_evolution_preserves_portfolio() (+3 more)

### Community 7 - "logging"
Cohesion: 0.12
Nodes (10): configure_logging(), get_log_dir(), _SafeRotatingFileHandler, _flush_file_handlers(), _remove_test_handlers(), test_configure_logging_never_raises_on_unwritable_dir(), test_get_log_dir_resolution(), test_stream_handler_present_when_stdout_exists() (+2 more)

### Community 8 - "test_item10_packaging.py"
Cohesion: 0.09
Nodes (10): _FakeNpmProc, _FakeNpmProcFail, _FakeURLDownload, _make_node_zip_bytes(), _node_supervisor(), test_download_node_corrupt_zip_raises_without_installing(), test_download_node_verifies_zip_and_extracts(), test_npm_install_omniroute_failure_reports_status() (+2 more)

### Community 9 - "CompetitorGenome"
Cohesion: 0.09
Nodes (30): BrokerSim, OrderTicket, test_submit_order_returns_none_when_apply_fill_fails(), test_broker_sim_bracket_stop_loss_trigger(), test_broker_sim_leverage_liquidation_long_crash(), test_broker_sim_leverage_liquidation_protection(), test_broker_sim_multi_portfolio_simultaneous_execution(), test_broker_sim_position_cap_enforcement() (+22 more)

### Community 10 - "Leaderboard"
Cohesion: 0.06
Nodes (30): Leaderboard, test_evolve_now_with_fewer_than_two_rankings_does_not_raise(), test_last_records_class_default_present(), test_signal_exit_fast_path_closes_under_hold_cash(), _counting_periods(), _portfolio_with_history(), test_fill_invalidates_cache(), test_metrics_cached_across_ticks_with_no_fills() (+22 more)

### Community 11 - "re"
Cohesion: 0.06
Nodes (52): _scanned_files(), test_no_src_ai_reference_remains(), _css(), _css_block(), _fn_body(), _html(), _js(), test_article_failure_shows_reason_not_summary() (+44 more)

### Community 12 - "ArenaDashboard"
Cohesion: 0.07
Nodes (18): ArenaDashboard, _get_native_hwnd(), __getattr__(), test_track_c_save_and_launch_aborts_if_password_db_sync_fails(), test_track_d_dashboard_save_launch_aborts_on_key_sync_failure(), test_track_d_reset_engine_preserves_fills_after_bootstrap_completes(), test_v24_track_b_live_engine_custom_gateway_url_and_reset_broker_binding(), test_setup_status_has_no_gateway_auto_spawn_option() (+10 more)

### Community 14 - "OrderSide"
Cohesion: 0.08
Nodes (32): __getattr__(), ExecutionReason, OrderSide, OrderStatus, OrderType, RiskGuard, _open_long(), test_apply_fill_value_error_does_not_kill_cadence() (+24 more)

### Community 15 - "IntelligenceHarvester"
Cohesion: 0.05
Nodes (31): ForumCollector, IntelligenceHarvester, parse_stocktwits_stream(), RawEvent, _registry_mock_get(), _stream_json(), test_fetch_from_registry_dispatches_by_type_and_skips_forum(), test_fetch_live_feeds_still_returns_test_fixtures() (+23 more)

### Community 17 - "ViewModelPublisher"
Cohesion: 0.15
Nodes (5): _build_engine_view_model_impl(), _empty_view_model(), ViewModelPublisher, test_track_d_view_model_publisher_excludes_fills_and_detects_is_live_change(), test_view_model_delta_omits_unchanged_history_and_intel_events_equivalently()

### Community 18 - "OmniRouteClient"
Cohesion: 0.07
Nodes (19): OmniRouteClient, test_chat_json_connection_refused_records_connection(), _run(), test_success_counted_only_after_parseable_json(), _run(), _mock_200_session(), test_key_present_sends_authorization(), _run() (+11 more)

### Community 19 - "Portfolio"
Cohesion: 0.07
Nodes (31): FillEvent, PositionSide, Portfolio, test_track_a_portfolio_cross_gen_leverage_partial_close_conserves_equity(), test_track_a_portfolio_failed_fill_does_not_corrupt_fees(), test_track_b_non_integer_cadence_advances_slots(), test_track_d_frontend_contracts_css_html_js(), test_v24_track_a_portfolio_apply_fill_upfront_quantization() (+23 more)

### Community 21 - "MacroCommander"
Cohesion: 0.04
Nodes (33): StructuredEvent, build_event_article_prompts(), _dedup_tickers(), _event_age_min(), MacroCommander, _runner(), _shutting_down(), MacroRegimeState (+25 more)

### Community 22 - "_make_supervisor"
Cohesion: 0.06
Nodes (21): _fake_node_zip_bytes(), _FakeDownloadResp, _make_supervisor(), _setup_npm_only_env(), _SlowResp, test_bridge_cancel_and_status_shape(), test_cancel_during_node_download(), test_cancel_during_npm_install_removes_partial_package() (+13 more)

### Community 23 - "GatewaySupervisor"
Cohesion: 0.13
Nodes (10): GatewaySupervisor, test_watchdog_backoff_schedule(), test_omniroute_eta_message_formatting(), test_daemon_log_rotates_over_5mb(), _make_bridge(), test_admin_password_required_before_onboarding(), test_daemon_command_falls_back_to_global(), test_daemon_command_prefers_runtime_install() (+2 more)

### Community 25 - "syncAppShellInert"
Cohesion: 0.15
Nodes (19): blurActiveFocus(), closeInstallCancelConfirm(), closeSetupWizardModal(), closeWizardCloseConfirm(), confirmCancelInstallAndClose(), confirmCloseWizardWithoutSaving(), handleInstallCancelOverlayClick(), handleWizardCloseOverlayClick() (+11 more)

### Community 26 - "test_phase3_ingestion.py"
Cohesion: 0.10
Nodes (16): InterruptDebouncer, parse_rss_atom(), _fake_registry_response(), _new_harvester(), _registry_get_ok(), test_feed_registry_completeness_r3(), test_fetch_from_registry_parses_real_rss_xml(), _recording_get() (+8 more)

### Community 27 - "soak_engine.py"
Cohesion: 0.06
Nodes (36): closing_fills_since(), db_stats(), do_slice(), genome_valid(), main(), _sample(), make_quote(), _parse_args() (+28 more)

### Community 28 - "Stage"
Cohesion: 0.06
Nodes (33): animCandles, attachToastInteractions(), changeEvolveInterval(), chartBeacons, closeShutdownModal(), currentSplashSteps, dismissToast(), EVOLVE_INTERVAL_OPTIONS (+25 more)

### Community 29 - "ingestion.py"
Cohesion: 0.10
Nodes (13): _clean_html_text(), _compile_word_group(), _compiled_word_re(), _contains_word(), _parse_iso_ts(), parse_polymarket_events(), parse_reddit_posts(), _mock_commander() (+5 more)

### Community 30 - ".run"
Cohesion: 0.09
Nodes (10): check_and_ensure_environment(), main(), _activate_foreground_startup(), _on_window_closing(), _on_window_shown(), _delayed_activation(), _FakeWebview, test_run_auto_spawn_waits_30_seconds() (+2 more)

### Community 31 - "test_track_c_gateway_npm_strips_secrets_and_no_blind_retry"
Cohesion: 0.13
Nodes (5): test_track_c_gateway_npm_strips_secrets_and_no_blind_retry(), _fake_popen(), _FakeProc, test_gateway_env_sets_server_host_and_strips_provider_keys_when_env_exists(), _fake_popen()

### Community 32 - "time"
Cohesion: 0.06
Nodes (14): _build_html_template(), _get_assets_dir(), _load_asset(), _assets_root(), test_wizard_has_no_autolaunch_checkbox(), test_frontend_progress_bar_and_cancel_confirm_ids(), test_wizard_vertical_content_sized_layout(), test_gateway_supervisor_http_responses() (+6 more)

### Community 33 - "ArenaStorage"
Cohesion: 0.21
Nodes (5): ArenaStorage, test_evolution_seed_recorded_in_history(), test_restore_survives_garbage_stop_ticket_and_entry_ts(), test_persistence_sanitizes_nan_and_inf_strict_json(), test_session_codec_rejects_symbol_mismatch_and_roundtrips_pending_and_orb()

### Community 34 - "test_gui_item7.py"
Cohesion: 0.14
Nodes (13): build_engine_view_model(), _rankings(), test_shutdown_closes_window_on_calling_thread(), test_view_model_does_not_fabricate_take_profit(), test_view_model_reports_unknown_mc_and_quota(), test_view_model_short_unrealized_pnl_pct(), test_view_model_skips_stale_ranking_entry(), test_view_model_survives_missing_or_broken_engine() (+5 more)

### Community 35 - "StreamingCryptoFeed"
Cohesion: 0.20
Nodes (3): StreamingCryptoFeed, test_phase1_websocket_feed_parsing_and_fast_path_fallback(), test_parse_binance_ticker_rejects_garbage()

### Community 36 - "ConfigManager"
Cohesion: 0.07
Nodes (12): ConfigManager, format_omni_env_value(), test_track_c_config_manager_refuses_to_wipe_unreadable_env(), test_v24_track_c_env_roundtrip_and_no_initial_password_in_environ(), test_gateway_auto_spawn_option_removed(), test_bridge_stepwise_simulation_erroneous_then_valid(), test_config_manager_atomic_recovery_from_corruption(), test_config_manager_env_preservation() (+4 more)

### Community 37 - "test_gateway_autolaunch_mandatory.py"
Cohesion: 0.15
Nodes (4): _FakeEvent, _FakeWebview, _FakeWindow, test_run_spawns_despite_stored_false()

### Community 38 - "test_live_engine.py"
Cohesion: 0.09
Nodes (28): _drive(), _drive_fixed(), _fixture_bars(), _quote(), _startup_engine_long(), test_anti_churn_cooldown_prevents_same_timestamp_reentry(), test_auto_evolve_fires_on_closed_trades(), _round_trips() (+20 more)

### Community 40 - ".omniroute_installed"
Cohesion: 0.15
Nodes (3): test_gateway_unavailable_reason_no_node(), test_gateway_unavailable_reason_node_but_no_omniroute(), test_start_runtime_install_does_not_start_twice()

### Community 41 - "test_cooperative_stop_event"
Cohesion: 0.29
Nodes (3): _raise_no_network(), test_cooperative_stop_event(), test_slow_bootstrap_stop_safety()

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
Cohesion: 0.27
Nodes (12): _event_id(), _make_commander(), test_article_generation_uses_long_timeout(), test_bridge_get_event_article(), test_curated_event_carries_tickers_article_fields(), test_curated_event_empty_tickers_becomes_empty_list(), test_first_expand_generates_once_and_caches(), test_gateway_offline_returns_failure_without_llm() (+4 more)

### Community 46 - "test_live_chop_gate.py"
Cohesion: 0.19
Nodes (11): _bars(), _choppy_closes(), _engine_with_15m(), test_chop_gate_blocks_entry_through_try_enter_bracket(), test_chop_gate_blocks_on_choppy_15m(), test_chop_gate_excludes_the_forming_bucket(), test_chop_gate_never_blocks_signal_exit_close(), test_chop_gate_open_on_trending_15m() (+3 more)

### Community 47 - "test_ws_feed.py"
Cohesion: 0.14
Nodes (8): test_ws_clean_server_close_counts_as_reconnect(), test_ws_connect_and_stream_delivers_quotes(), _fake_connect(), _on_quote(), test_ws_reconnect_backoff_on_disconnect(), _fake_connect(), _fake_sleep(), test_ws_start_stop_delivers_then_stops()

### Community 48 - "._run_runtime_install"
Cohesion: 0.09
Nodes (4): _default_daemon_log_path(), _default_install_log_path(), _InstallCancelledError, test_daemon_log_default_path_is_project_logs()

### Community 50 - "DeduplicationBuffer"
Cohesion: 0.18
Nodes (6): _dedup_normalize_title(), DeduplicationBuffer, _retry_window_seconds(), test_v24_track_c_omniroute_extract_json_retry_hint_dedup_and_https_redirect(), test_deduplication_buffer(), test_ingestion_clean_html_strips_script_style_and_dedup_forget()

### Community 51 - "test_gateway_diagnosis.py"
Cohesion: 0.07
Nodes (44): classify_llm_error(), _client(), _css(), _FakeWebview, _js(), _make_dash(), _supervisor(), test_all_providers_quota_exhausted_needs_every_provider() (+36 more)

### Community 52 - "test_phase1_debug_sweep.py"
Cohesion: 0.10
Nodes (12): test_four_threads_expand_concurrently_without_closing_each_other(), _one(), _worker(), _quote(), _safe_refresh(), test_deserialize_ticket_garbage_numbers_return_none(), test_engine_stop_closes_quote_session_pool(), test_gateway_supervisor_atexit_does_not_retain_instances() (+4 more)

### Community 53 - "test_llm_json_mode_fallback.py"
Cohesion: 0.11
Nodes (12): _engine(), _snapshot(), test_deepcopy_never_receives_heavy_arrays_on_unchanged_poll(), test_delta_is_still_a_defensive_copy(), test_delta_output_identical_to_old_path(), _client_with(), _CM, _FakeSession (+4 more)

### Community 54 - ".test_single_key"
Cohesion: 0.18
Nodes (4): test_v24_track_c_gemini_header_and_save_gateway_no_split_brain(), test_gateway_supervisor_key_validation_defensive(), test_gateway_supervisor_nvidia_endpoint(), test_key_rate_limit_429_is_not_verified()

### Community 55 - "._get_connection"
Cohesion: 0.18
Nodes (5): _retry_on_db_error(), _sanitize_json_value(), test_track_b_persistence_batch_fills_and_prune_candles(), test_phase2_sqlite_wal_persistence_and_cold_start_hydration(), test_p2_persistent_connection_reused_and_candle_persists_across_close()

### Community 56 - "test_508_chop_gate.py"
Cohesion: 0.26
Nodes (7): _bar(), _choppy_bars(), test_gate_blocks_entries_on_choppy_tape(), test_gate_inactive_on_trend_tape(), test_gate_never_blocks_closes(), _total_closed(), _trend_bars()

### Community 57 - "MonteCarloOddsEvaluator"
Cohesion: 0.18
Nodes (7): MonteCarloBracketOdds, MonteCarloOddsEvaluator, test_track_b_timemachine_rejects_wrong_side_tp(), test_v24_track_b_timemachine_single_sim_and_flat_empirical_candles(), test_monte_carlo_ev_gate_odds_evaluation(), test_monte_carlo_without_numpy_reports_unknown(), test_v200_31_33_mixins_and_timemachine_student_t()

### Community 58 - "test_autosave_35.py"
Cohesion: 0.18
Nodes (8): _bars(), _engine(), _raise_no_network(), test_autosave_does_not_fire_when_stopped_or_superseded(), test_crash_like_stop_leaves_restorable_autosave(), test_evolution_marks_autosave_pending_and_it_fires_immediately(), test_live_loop_triggers_periodic_autosave(), test_periodic_autosave_writes_snapshot_when_interval_elapses()

### Community 59 - "QuoteManager"
Cohesion: 0.19
Nodes (3): QuoteManager, test_dead_cascade_state_is_gone(), test_ws_quote_path_still_works()

### Community 60 - "test_phase2_optimize.py"
Cohesion: 0.22
Nodes (8): _candle(), test_p2_concurrent_candle_writes_all_persist(), writer(), test_p2_engine_stop_closes_storage_and_restart_still_writes(), test_p2_eth_feed_first_fetch_loads_pandas_and_behaves(), test_p2_eth_feed_import_does_not_import_pandas(), test_p2_persistent_connection_recovers_from_stale_handle(), test_p2_save_candle_is_fast_with_persistent_connection()

### Community 61 - "renderIntelHub"
Cohesion: 0.19
Nodes (14): buildIntelEventCard(), cleanIntelSummary(), hashTickerName(), intelArticleBodyEl(), intelEventKey(), preloadIntelArticles(), pumpIntelArticlePreload(), renderIntelArticle() (+6 more)

### Community 62 - "_FakeCM"
Cohesion: 0.09
Nodes (5): test_track_c_omniroute_max_concurrent_1_repair_no_deadlock(), post(), _FakeCM, _FakeResp, _FakeSession

### Community 63 - "threading"
Cohesion: 0.19
Nodes (6): _drive(), _make_engine(), _quote(), test_concurrent_publish_harvests_each_fill_once(), test_publish_state_snapshot_holds_engine_lock(), publish_many()

### Community 64 - "test_intel_hub_layout.py"
Cohesion: 0.25
Nodes (12): _commander(), _css(), _js(), _mock_pipeline(), _rule(), _structured(), test_stream_loading_block_is_centered_with_meter(), test_sync_status_failed_when_feeds_down() (+4 more)

### Community 65 - "renderAll"
Cohesion: 0.24
Nodes (16): createPositionToastElement(), escapeHtml(), fmtPct(), fmtSignedUsd(), fmtTimeSec(), fmtUsd(), renderAll(), renderFills() (+8 more)

### Community 66 - "test_item12a_omniroute.py"
Cohesion: 0.23
Nodes (7): _now_iso(), _offline_commander(), _strong_bearish_events(), test_empty_digest_expires_stale_fallback(), test_fallback_clears_when_llm_recovers(), test_fallback_regime_is_marked_and_expires(), test_regime_state_dict_exposes_fallback()

### Community 70 - "controls/index.ts"
Cohesion: 0.19
Nodes (10): _broker(), _commander(), test_backtest_default_sizing_is_one(), test_compute_r_multiple_qty_scales_budget_and_clamps(), test_evaluate_signal_sizing_shrinks_qty_not_sl(), test_no_confidence_means_no_sizing_effect(), test_per_strategy_sensitivity_scales_the_deviation(), test_sizing_formula_exact_values() (+2 more)

### Community 71 - "test_504_omni_env_cache.py"
Cohesion: 0.28
Nodes (8): _counting_read_text(), _manager(), test_content_change_is_visible_after_rewrite(), test_missing_file_then_created(), test_mtime_change_invalidates_even_with_same_content(), test_repeated_reads_hit_cache(), test_returned_dict_is_a_copy(), test_write_then_read_sees_new_password()

### Community 72 - "test_generation_fence.py"
Cohesion: 0.22
Nodes (4): _keyframes_block(), test_save_history_failure_is_logged_not_swallowed(), test_splash_overlay_is_lightened_not_removed(), test_stale_engine_harvest_fills_refused()

### Community 73 - "persistence.py"
Cohesion: 0.36
Nodes (6): _records(), test_save_history_closes_storage_it_creates(), close(), __init__(), test_save_history_reuses_caller_storage_without_closing(), __init__()

### Community 75 - "saveAndLaunchGateway"
Cohesion: 0.20
Nodes (17): applyGatewayAvailability(), clearSplashTimers(), confirmShutdown(), ensureRuntimeInstallPoll(), initAppBoot(), installGatewayRuntime(), openSetupWizardModal(), refreshGatewayAvailability() (+9 more)

### Community 76 - "test_ui_feedback.py"
Cohesion: 0.23
Nodes (7): _copy_text_to_clipboard_windows(), _bridge_with_env(), test_copy_password_copies_value_but_never_returns_it(), test_copy_password_helper_failure(), test_copy_password_not_configured(), test_copy_text_to_clipboard_windows_non_windows(), test_copy_text_to_clipboard_windows_roundtrip()

### Community 77 - "LiveArenaEngine"
Cohesion: 0.12
Nodes (12): LiveArenaEngine, test_pause_feed_updates_ui_snapshot_immediately(), test_stale_engine_save_session_state_refused(), test_ensure_active_live_positions_short_brackets(), test_recompute_candle_indicators_rsi_atr_orb_mean(), test_restore_open_position_recomputes_margin_and_stops(), test_macro_veto_intent_preserved_in_live_evaluation(), test_pause_time_freezing_and_arena_transitions() (+4 more)

### Community 78 - "._live_loop"
Cohesion: 0.11
Nodes (4): _on_done(), test_start_live_trading_readiness_handshake(), test_stale_engine_evolve_now_refused(), test_stale_engine_state_publish_skipped()

### Community 79 - ".get_gateway_diagnosis"
Cohesion: 0.24
Nodes (6): _mock_resp(), _mock_session(), test_chat_json_402_records_quota_failure(), _run(), test_chat_json_transient_429_then_200_clears_quota_records(), _run()

### Community 80 - "test_digest_refresh_session.py"
Cohesion: 0.23
Nodes (5): _FakeForum, _FakeHarvester, _make_commander(), test_concurrent_article_call_survives_refresh(), test_two_refreshes_leave_session_open()

### Community 81 - "live_engine.py"
Cohesion: 0.18
Nodes (3): parse_symbol_pairs(), efficiency_ratio(), test_efficiency_ratio_unit()

### Community 84 - "test_card_reorder_anim.py"
Cohesion: 0.35
Nodes (10): _css(), _js(), _reorder_block(), test_cards_are_stable_nodes_never_recreated_on_reorder(), test_flip_cleanup_clears_class_and_transform(), test_flip_inverts_with_translate_and_plays_via_class(), test_flip_records_first_rects_before_moving_nodes(), test_flip_runs_only_when_order_changes() (+2 more)

### Community 86 - "test_mtf_seed_async_25.py"
Cohesion: 0.22
Nodes (3): _FakeThread, _fixture_bars(), test_bootstrap_spawns_mtf_seed_thread_instead_of_blocking()

### Community 87 - "test_507_candle_write_on_close.py"
Cohesion: 0.42
Nodes (7): _counting_save(), _engine(), test_bar_close_persists_final_bar_once(), test_closed_bar_is_in_sqlite_after_close(), test_out_of_order_tick_does_not_double_save(), test_three_minutes_persist_two_closed_bars(), test_ticks_within_one_minute_write_nothing()

### Community 88 - "._try_enter_bracket"
Cohesion: 0.20
Nodes (18): _dead_gateway_commander(), _mock_pipeline(), _structured(), test_sync_status_done_when_dead_gateway_still_yields_fallback_digest(), test_sync_status_failed_when_gateway_dead_and_nothing_produced(), _ev(), _now_iso(), _offline_commander() (+10 more)

### Community 89 - "_mock_resp"
Cohesion: 0.31
Nodes (10): _coinbase_stats_payload(), _coinbase_ticker_payload(), _kraken_payload(), _mock_resp(), test_binance_quote_success_parses_all_fields(), test_coinbase_quote_success_parses(), test_kraken_quote_success_parses(), dispatch() (+2 more)

### Community 90 - "_open_short"
Cohesion: 0.20
Nodes (5): _open_short(), test_evaluate_live_strategies_short_exits_are_signal_only(), test_evaluate_live_strategies_small_gain_does_not_close_shorts(), test_stagnation_exit_closes_after_40m(), test_trailing_guard_short_ratchet_moves_stop_down()

### Community 92 - "test_orb_anchor_34.py"
Cohesion: 0.20
Nodes (5): _tape_bar(), test_backtest_orb_range_anchored_to_first_15_tape_bars(), test_bootstrap_anchors_orb_range_to_first_15_warmup_bars(), test_live_orb_range_does_not_drift_with_rolling_buffer(), _warmup_bars()

### Community 93 - "subprocess"
Cohesion: 0.60
Nodes (3): _git(), test_system_config_is_ignored_by_git(), test_system_config_is_untracked_but_present_on_disk()

### Community 95 - ".bootstrap_intraday_session"
Cohesion: 0.10
Nodes (8): test_get_ui_state_mutation_isolation(), test_offline_start_does_not_execute_stale_candles(), test_close_ticket_bypasses_veto_and_gates_under_hold_cash(), _cache_rows(), test_bootstrap_hydrates_fresh_sqlite_candles(), test_bootstrap_rejects_stale_sqlite_candles(), test_live_engine_enforces_macro_commander_veto(), test_live_engine_refresh_intel_digest()

### Community 96 - "test_phase2g_graphics.py"
Cohesion: 0.31
Nodes (4): _js(), test_p2g_chart_loop_capped_at_60fps(), test_p2g_hidden_view_stops_chart_loop(), test_p2g_no_temporary_probe_left_in_shipped_assets()

### Community 99 - "test_321_auto_redeploy.py"
Cohesion: 0.39
Nodes (5): _flat_engine(), test_no_redeploy_when_any_position_open(), test_redeploy_logs_once_per_flat_episode(), test_switch_off_does_not_redeploy(), test_switch_on_default_redeploys_when_flat()

### Community 100 - "presence/index.tsx"
Cohesion: 0.19
Nodes (14): addChartBeacon(), checkOnboardingBoot(), copyOmniPassword(), createPositionClosedToastElement(), enqueueToast(), ensureLiveTradingStarted(), hexToRgba(), pollBackend() (+6 more)

### Community 101 - "_make_bridge"
Cohesion: 0.50
Nodes (3): _make_bridge(), test_save_and_launch_spawns_despite_stored_false(), test_setup_status_has_no_autolaunch_option()

### Community 104 - "test_orb_day_rollover.py"
Cohesion: 0.36
Nodes (5): _minute_candles(), _tape_bar(), test_backtest_orb_range_rolls_at_utc_midnight(), test_live_orb_range_is_forming_on_a_partial_new_day(), test_live_orb_range_rolls_at_utc_midnight()

### Community 107 - "MultiTimeframeEngine"
Cohesion: 0.12
Nodes (16): MultiTimeframeEngine, test_track_b_mtf_engine_delta_volume_and_neutral_on_conflict(), test_v24_track_b_mtf_seed_1h_merges_same_slot(), test_mtf_gate_blocks_counter_trend_entries(), _buckets(), _hourly_bars(), _minute_bars(), test_engine_seed_fetch_failure_stays_neutral() (+8 more)

### Community 108 - "cursors/index.tsx"
Cohesion: 0.23
Nodes (12): drawPriceChart(), invalidateCanvasSizeCache(), locateMouseAndRefreshChart(), setIntelSortMode(), setLgWallpaper(), setRightTab(), setScaleMode(), setupChartInteraction() (+4 more)

### Community 110 - "_error_body_text"
Cohesion: 0.33
Nodes (3): _error_body_text(), _walk(), _extract_error_provider()

### Community 111 - "_open_long"
Cohesion: 0.33
Nodes (3): _open_long(), test_bracket_take_profit_closes_via_on_tick(), test_evaluate_live_strategies_small_gain_does_not_close_longs()

### Community 112 - "test_gateway_item8.py"
Cohesion: 0.09
Nodes (7): _FakeEvent, _FakeHTTPResponse, _FakeWindow, test_existing_daemon_check_uses_2s_probe(), test_probe_health_success_failure_timeout(), test_save_and_launch_gateway_waits_30_seconds(), test_start_daemon_default_wait_is_30_seconds()

### Community 113 - "test_competitors.py"
Cohesion: 0.08
Nodes (7): _parse_pos_dec(), _fresh_broker_competitor(), _r_multiple(), test_evaluate_signal_returns_none_when_breaker_tripped_all_strategies(), test_evaluate_signal_short_entries_mirror_long_brackets_all_strategies(), test_orb_competitor_box_breakout_and_r_multiple(), test_strategy_qty_zero_returns_none()

### Community 134 - "closeResetModal"
Cohesion: 0.50
Nodes (4): closeResetModal(), confirmResetArena(), handleResetOverlayClick(), resetArena()

### Community 139 - "fix_item5_patch.py"
Cohesion: 0.20
Nodes (10): fillRoundRect(), isSplashGateOpen(), renderPriceCanvas(), setSplashTarget(), setupHiDPICanvas(), startChartAnimLoop(), stepChartAnimLoop(), strokeRoundRect() (+2 more)

### Community 146 - "Choreography"
Cohesion: 0.29
Nodes (6): 1. Launch Packaged Desktop Executable (`.exe`), 2. Run Self-Test Verification, 3. Run Automated Unit Test Suite (32 Tests), 4. Build Standalone Windows Executable, Quick Start Guide, TradeBot0: Multi-Agent Paper Trading & Genetic Evolution Arena (BTC/USD)

### Community 161 - "smoke_external.py"
Cohesion: 0.25
Nodes (14): check_binance_rest(), check_binance_ws(), _run(), check_ccxt_kraken(), check_coinbase_rest(), check_feed_registry(), check_kraken_rest(), check_node_head() (+6 more)

### Community 163 - "test_phase3_soak.py"
Cohesion: 0.28
Nodes (4): _bootstrapped_engine(), _load_soak_helpers(), soak(), test_p3_mini_soak_many_ticks_no_growth_blowup()

## Knowledge Gaps
- **38 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `LiveArenaEngine` connect `LiveArenaEngine` to `test_v200_fixes.py`, `TimeMachineArena`, `CompetitorGenome`, `Leaderboard`, `ArenaDashboard`, `OrderSide`, `ViewModelPublisher`, `OmniRouteClient`, `Portfolio`, `MacroCommander`, `soak_engine.py`, `ingestion.py`, `time`, `ArenaStorage`, `test_gui_item7.py`, `StreamingCryptoFeed`, `ConfigManager`, `test_phase3_soak.py`, `test_live_engine.py`, `test_cooperative_stop_event`, `test_live_chop_gate.py`, `LiveStrategyRunnerMixin`, `test_phase1_debug_sweep.py`, `test_llm_json_mode_fallback.py`, `MonteCarloOddsEvaluator`, `test_autosave_35.py`, `QuoteManager`, `test_phase2_optimize.py`, `threading`, `._build_snapshot_locked`, `IndicatorEngineMixin`, `LiveQuote`, `controls/index.ts`, `test_generation_fence.py`, `SessionCodecMixin`, `._live_loop`, `live_engine.py`, `test_mtf_seed_async_25.py`, `test_507_candle_write_on_close.py`, `_mock_resp`, `_open_short`, `test_orb_anchor_34.py`, `.bootstrap_intraday_session`, `.is_fresh`, `test_321_auto_redeploy.py`, `test_orb_day_rollover.py`, `test_restore_applies_genome_leverage_to_portfolio`, `MultiTimeframeEngine`, `_open_long`?**
  _High betweenness centrality (0.145) - this node is a cross-community bridge._
- **Are the 29 inferred relationships involving `LiveArenaEngine` (e.g. with `Architectural Highlights` and `BrokerSim`) actually correct?**
  _`LiveArenaEngine` has 29 INFERRED edges - model-reasoned connections that need verification._
- **Should `test_phase2_omniroute_client.py` be split into smaller, more focused modules?**
  _Cohesion score 0.0907563025210084 - nodes in this community are weakly interconnected._
- **Why does `GatewaySupervisor` connect `GatewaySupervisor` to `test_item10_packaging.py`, `re`, `ArenaDashboard`, `.start_daemon`, `Portfolio`, `_make_supervisor`, `ingestion.py`, `.run`, `test_track_c_gateway_npm_strips_secrets_and_no_blind_retry`, `time`, `test_gui_item7.py`, `ConfigManager`, `.omniroute_installed`, `.shutdown`, `test_save_launch_progress.py`, `._run_runtime_install`, `test_gateway_diagnosis.py`, `test_phase1_debug_sweep.py`, `.test_single_key`, `test_item12a_omniroute.py`, `.sync_admin_password`, `parse_omni_env_line`, `_make_bridge`, `test_gateway_item8.py`?**
  _High betweenness centrality (0.097) - this node is a cross-community bridge._
- **Are the 113 inferred relationships involving `OrderSide` (e.g. with `main()` and `BrokerSim`) actually correct?**
  _`OrderSide` has 113 INFERRED edges - model-reasoned connections that need verification._
- **Should `test_update_checker.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07676767676767676 - nodes in this community are weakly interconnected._
- **Why does `OmniRouteClient` connect `OmniRouteClient` to `test_phase2_omniroute_client.py`, `json`, `test_v200_fixes.py`, `IntelligenceHarvester`, `Portfolio`, `MacroCommander`, `ingestion.py`, `time`, `test_gateway_diagnosis.py`, `test_phase1_debug_sweep.py`, `test_llm_json_mode_fallback.py`, `_FakeCM`, `test_item12a_omniroute.py`, `LiveArenaEngine`, `.get_gateway_diagnosis`, `test_digest_refresh_session.py`, `live_engine.py`, `.run_digest_sync`, `.chat_json`?**
  _High betweenness centrality (0.077) - this node is a cross-community bridge._