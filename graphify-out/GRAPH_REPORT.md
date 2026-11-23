# Graph Report - TradeBot0_Local  (2026-11-24)

## Corpus Check
- 135 files · ~188,237 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 11 file(s) not represented in the graph (top: (none) 4, .iss 1, .lnk 1)

## Summary
- 2868 nodes · 8047 edges · 132 communities (94 shown, 38 thin omitted)
- Extraction: 88% EXTRACTED · 12% INFERRED · 0% AMBIGUOUS · INFERRED: 1004 edges (avg confidence: 0.89)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `6cfff572`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- BrokerSim
- _symbols_from_registry
- test_update_checker.py
- test_v200_fixes.py
- CandleBar
- smoke_external.py
- test_item10_packaging.py
- OrderTicket
- Leaderboard
- test_ui_contract.py
- ArenaDashboard
- live_engine.py
- IntelligenceHarvester
- test_ticket_reason_38.py
- ViewModelPublisher
- OmniRouteClient
- OrderSide
- _ArenaBridgeApi
- MacroCommander
- test_gateway_install_progress_cancel.py
- GatewaySupervisor
- GeneticEvolver
- syncAppShellInert
- test_phase3_ingestion.py
- soak_engine.py
- Stage
- test_performance_and_optimizations.py
- test_intel_stream_redesign.py
- test_track_c_gateway_npm_strips_secrets_and_no_blind_retry
- MonteCarloOddsEvaluator
- test_performance_and_optimizations.py
- QuoteManager
- test_start_daemon_concurrent_calls_spawn_once
- ConfigManager
- test_gateway_autolaunch_mandatory.py
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
- re
- LiveStrategyRunnerMixin
- config_manager.py
- test_gateway_diagnosis.py
- threading
- test_llm_json_mode_fallback.py
- soak_engine.py
- DeduplicationBuffer
- test_auto_evolve_fires_on_closed_trades
- MultiTimeframeEngine
- StreamingCryptoFeed
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
- _supervisor
- FakeWS
- ArenaStorage
- SessionCodecMixin
- saveAndLaunchGateway
- test_ui_feedback.py
- test_snapshot_counters_37.py
- ._live_loop
- test_504_omni_env_cache.py
- test_v287_render_guards.py
- .sync_admin_password
- test_breakeven_count_29.py
- .test_single_key
- test_card_reorder_anim.py
- test_507_candle_write_on_close.py
- _open_short
- _FakeWindow
- ._try_enter_bracket
- test_digest_refresh_session.py
- _fresh_broker_competitor
- _error_body_text
- test_502_ui_state_delta.py
- _make_dash
- test_bootstrap_hydrates_fresh_sqlite_candles
- test_phase2g_graphics.py
- _FakeWebview
- _client
- _FakeHTTPResponse
- _FakeThread
- test_318_system_config_untracked.py
- test_omniroute_client_quota_fastpath_sse_error_and_timeout
- test_322_apply_fill_failure.py
- _referenced_classes
- ._handle_ws_quote
- conftest.py
- test_phase1_debug_sweep.py
- cursors/index.tsx
- test_restore_applies_genome_leverage_to_portfolio
- test_319_src_ai_gone.py
- .compute_r_multiple_qty
- gateway_supervisor.py
- ._reset_connection
- LiveArenaEngine
- fix_item5_patch.py
- Choreography

## God Nodes (most connected - your core abstractions)
1. `LiveArenaEngine` - 210 edges
2. `OrderSide` - 170 edges
3. `GatewaySupervisor` - 117 edges
4. `OmniRouteClient` - 111 edges
5. `BrokerSim` - 110 edges
6. `OrderTicket` - 102 edges
7. `Portfolio` - 102 edges
8. `MacroCommander` - 95 edges
9. `OrderType` - 82 edges
10. `_ArenaBridgeApi` - 79 edges

## Surprising Connections (you probably didn't know these)
- `Architectural Highlights` --references--> `LiveArenaEngine`  [INFERRED]
  README.md → src/data/live_engine.py
- `Architectural Highlights` --references--> `GeneticEvolver`  [INFERRED]
  README.md → src/arena/evolution.py
- `Architectural Highlights` --references--> `CompetitorGenome`  [INFERRED]
  README.md → src/competitors/base.py
- `Architectural Highlights` --references--> `BrokerSim`  [INFERRED]
  README.md → src/arena/broker_sim.py
- `test_generate_fallback_bars_deleted()` --uses--> `LiveArenaEngine`  [INFERRED]
  tests/test_offline_removal.py → src/data/live_engine.py

## Import Cycles
- None detected.

## Communities (132 total, 38 thin omitted)

### Community 0 - "BrokerSim"
Cohesion: 0.12
Nodes (7): BrokerSim, test_every_ticket_satisfies_tp_ge_sl(), test_evaluate_signal_short_entries_mirror_long_brackets(), test_orb_competitor_box_breakout_and_r_multiple(), test_session_mean_competitor_pullback_and_r_multiple(), test_phase3_dynamic_depth_and_volatility_slippage(), test_r_multiple_dynamic_budget_sizing()

### Community 2 - "test_update_checker.py"
Cohesion: 0.08
Nodes (22): _check(), check_for_updates(), compare_versions(), get_manifest_url(), _is_date_version(), test_track_c_update_checker_rejects_non_https_and_clears_download_url_when_up_to_date(), _mock_response(), test_check_failed_on_bad_manifest() (+14 more)

### Community 3 - "test_v200_fixes.py"
Cohesion: 0.09
Nodes (29): ExecutionReason, AggressiveCompetitor, BaseCompetitor, CompetitorGenome, ConservativeCompetitor, ORBCompetitor, SessionMeanPullbackCompetitor, TrailingGuardCompetitor (+21 more)

### Community 6 - "CandleBar"
Cohesion: 0.05
Nodes (36): CompetitorStats, CandleBar, TimeMachineArena, _fixture_bars(), _bar(), _choppy_bars(), test_efficiency_ratio_unit(), test_gate_blocks_entries_on_choppy_tape() (+28 more)

### Community 7 - "smoke_external.py"
Cohesion: 0.07
Nodes (25): check_binance_rest(), check_binance_ws(), _run(), check_ccxt_kraken(), check_coinbase_rest(), check_feed_registry(), check_kraken_rest(), check_node_head() (+17 more)

### Community 8 - "test_item10_packaging.py"
Cohesion: 0.06
Nodes (18): _FakeNpmProc, _FakeNpmProcFail, _FakeURLDownload, _make_bridge(), _make_node_zip_bytes(), _node_supervisor(), test_admin_password_required_before_onboarding(), test_console_url_follows_gateway_port() (+10 more)

### Community 9 - "OrderTicket"
Cohesion: 0.10
Nodes (31): OrderTicket, OrderType, test_broker_sim_bracket_stop_loss_trigger(), test_broker_sim_leverage_liquidation_long_crash(), test_broker_sim_leverage_liquidation_protection(), test_broker_sim_multi_portfolio_simultaneous_execution(), test_broker_sim_position_cap_enforcement(), test_depth_impact_pool_depth_is_disclosed() (+23 more)

### Community 10 - "Leaderboard"
Cohesion: 0.11
Nodes (17): Leaderboard, _counting_periods(), _portfolio_with_history(), test_fill_invalidates_cache(), test_metrics_cached_across_ticks_with_no_fills(), test_replace_equity_history_invalidates_cache(), test_reset_invalidates_cache(), test_risk_free_rate_change_invalidates_cache() (+9 more)

### Community 11 - "test_ui_contract.py"
Cohesion: 0.15
Nodes (15): _badge_cls_producer_values(), _bridge_class_node(), _bridge_methods(), _bridge_obj_calls(), _bridge_self_calls(), _defined_classes(), _html_ids(), _js_defined_functions() (+7 more)

### Community 12 - "ArenaDashboard"
Cohesion: 0.07
Nodes (18): ArenaDashboard, _get_native_hwnd(), __getattr__(), test_track_c_save_and_launch_aborts_if_password_db_sync_fails(), test_track_d_dashboard_save_launch_aborts_on_key_sync_failure(), test_setup_status_has_no_gateway_auto_spawn_option(), test_manual_evolve_does_not_block_bridge(), test_run_loads_config_once_and_uses_window_title_constant() (+10 more)

### Community 14 - "live_engine.py"
Cohesion: 0.08
Nodes (13): __getattr__(), OrderStatus, PositionSide, parse_symbol_pairs(), efficiency_ratio(), _build_engine_view_model_impl(), _safe_fmt_hms(), _raise_no_network() (+5 more)

### Community 15 - "IntelligenceHarvester"
Cohesion: 0.04
Nodes (32): ForumCollector, IntelligenceHarvester, parse_stocktwits_stream(), RawEvent, _registry_mock_get(), _stream_json(), test_fetch_from_registry_dispatches_by_type_and_skips_forum(), test_fetch_live_feeds_still_returns_test_fixtures() (+24 more)

### Community 17 - "ViewModelPublisher"
Cohesion: 0.18
Nodes (5): _empty_view_model(), ViewModelPublisher, test_track_d_view_model_publisher_excludes_fills_and_detects_is_live_change(), test_view_model_delta_omits_unchanged_history_and_intel_events_equivalently(), test_view_model_delta_shallow_clones_and_cache()

### Community 18 - "OmniRouteClient"
Cohesion: 0.03
Nodes (52): compute_backoff(), extract_json(), _looks_like_format_rejection(), OmniRouteClient, _mock_resp(), _mock_session(), test_chat_json_402_records_quota_failure(), _run() (+44 more)

### Community 19 - "OrderSide"
Cohesion: 0.09
Nodes (30): Architectural Highlights, FillEvent, OrderSide, Portfolio, RiskGuard, test_track_a_leaderboard_caches_flat_portfolio(), test_track_a_portfolio_cross_gen_leverage_partial_close_conserves_equity(), test_track_a_portfolio_failed_fill_does_not_corrupt_fees() (+22 more)

### Community 21 - "MacroCommander"
Cohesion: 0.05
Nodes (13): MacroCommander, _runner(), _on_progress(), _shutting_down(), _shutting_down(), _wrapped(), test_sync_status_failed_when_gateway_down(), test_macro_commander_skips_chat_when_gateway_offline() (+5 more)

### Community 22 - "test_gateway_install_progress_cancel.py"
Cohesion: 0.05
Nodes (25): _fake_node_zip_bytes(), _FakeDownloadResp, _make_supervisor(), _setup_npm_only_env(), _SlowResp, test_bridge_cancel_and_status_shape(), test_cancel_during_node_download(), test_cancel_during_npm_install_removes_partial_package() (+17 more)

### Community 23 - "GatewaySupervisor"
Cohesion: 0.08
Nodes (13): GatewaySupervisor, test_watchdog_backoff_schedule(), test_daemon_log_rotates_over_5mb(), test_start_daemon_polls_health_with_2s_timeout_and_logs_to_file(), fake_probe(), test_start_daemon_spawns_and_waits_with_fake_proc(), test_start_daemon_times_out_when_health_never_ok(), test_gateway_supervisor_port_and_health_conflict() (+5 more)

### Community 24 - "GeneticEvolver"
Cohesion: 0.07
Nodes (18): GeneticEvolver, test_evolve_generation_early_return_does_not_crash(), test_evolve_now_with_fewer_than_two_rankings_does_not_raise(), test_last_records_class_default_present(), _records(), test_save_history_closes_storage_it_creates(), close(), __init__() (+10 more)

### Community 25 - "syncAppShellInert"
Cohesion: 0.14
Nodes (20): blurActiveFocus(), closeInstallCancelConfirm(), closeSetupWizardModal(), closeWizardCloseConfirm(), confirmCancelInstallAndClose(), confirmCloseWizardWithoutSaving(), handleInstallCancelOverlayClick(), handleWizardCloseOverlayClick() (+12 more)

### Community 26 - "test_phase3_ingestion.py"
Cohesion: 0.09
Nodes (24): _first_child_text(), parse_polymarket_events(), parse_reddit_posts(), parse_rss_atom(), _mock_commander(), test_feed_numeric_parsing_never_raises(), test_no_fabricated_seed_events_and_honest_quota(), test_veto_never_blocks_close() (+16 more)

### Community 27 - "soak_engine.py"
Cohesion: 0.10
Nodes (22): ETHFeed, _engine(), _feed_1m(), _tape_end_anchored(), _tape_slot_aligned(), test_seed_helper_feeds_continuous_chain_and_arms_gate(), test_seed_helper_gap_truncates_to_suffix_after_gap(), test_seed_helper_malformed_row_skipped_not_fabricated() (+14 more)

### Community 28 - "Stage"
Cohesion: 0.06
Nodes (35): animCandles, changeEvolveInterval(), chartBeacons, closeResetModal(), closeShutdownModal(), confirmResetArena(), currentSplashSteps, EVOLVE_INTERVAL_OPTIONS (+27 more)

### Community 29 - "test_performance_and_optimizations.py"
Cohesion: 0.11
Nodes (9): test_launchers_and_shortcut_integrity(), test_macro_veto_intent_preserved_in_live_evaluation(), test_phase4_mtf_trend_confluence_gatekeeper(), test_portfolio_no_duplicate_apply_fill_returns(), test_splash_logo_concentric_alignment_and_svg_zap(), test_stageshow_ui_design_system_integrity(), test_window_startup_foreground_configuration(), test_zero_cjk_in_frontend_assets() (+1 more)

### Community 30 - "test_intel_stream_redesign.py"
Cohesion: 0.21
Nodes (16): _fn_body(), _html(), _js(), test_article_failure_shows_reason_not_summary(), test_article_lazy_once_and_cached(), test_article_loading_shows_determinate_stage_progress_bar(), test_article_render_is_not_rewritten_every_tick(), test_articles_preload_while_collapsed() (+8 more)

### Community 31 - "test_track_c_gateway_npm_strips_secrets_and_no_blind_retry"
Cohesion: 0.13
Nodes (5): test_track_c_gateway_npm_strips_secrets_and_no_blind_retry(), _fake_popen(), _FakeProc, test_gateway_env_sets_server_host_and_strips_provider_keys_when_env_exists(), _fake_popen()

### Community 32 - "MonteCarloOddsEvaluator"
Cohesion: 0.18
Nodes (7): MonteCarloBracketOdds, MonteCarloOddsEvaluator, test_track_b_timemachine_rejects_wrong_side_tp(), test_v24_track_b_timemachine_single_sim_and_flat_empirical_candles(), test_monte_carlo_ev_gate_odds_evaluation(), test_monte_carlo_without_numpy_reports_unknown(), test_v200_31_33_mixins_and_timemachine_student_t()

### Community 33 - "test_performance_and_optimizations.py"
Cohesion: 0.07
Nodes (21): check_and_ensure_environment(), main(), _set_windows_app_user_model_id(), _apply_window_icon(), _activate_foreground_startup(), _on_window_closing(), _on_window_shown(), _delayed_activation() (+13 more)

### Community 34 - "QuoteManager"
Cohesion: 0.19
Nodes (3): QuoteManager, test_dead_cascade_state_is_gone(), test_ws_quote_path_still_works()

### Community 36 - "ConfigManager"
Cohesion: 0.06
Nodes (14): ConfigManager, format_omni_env_value(), test_track_c_config_manager_refuses_to_wipe_unreadable_env(), test_v24_track_c_env_roundtrip_and_no_initial_password_in_environ(), test_gateway_auto_spawn_option_removed(), test_bridge_stepwise_simulation_erroneous_then_valid(), test_config_manager_atomic_recovery_from_corruption(), test_config_manager_env_preservation() (+6 more)

### Community 37 - "test_gateway_autolaunch_mandatory.py"
Cohesion: 0.11
Nodes (9): _assets_root(), _FakeEvent, _FakeWebview, _FakeWindow, _make_bridge(), test_run_spawns_despite_stored_false(), test_save_and_launch_spawns_despite_stored_false(), test_setup_status_has_no_autolaunch_option() (+1 more)

### Community 38 - "test_live_engine.py"
Cohesion: 0.06
Nodes (41): _coinbase_stats_payload(), _coinbase_ticker_payload(), _drive(), _fixture_bars(), _kraken_payload(), _mock_resp(), _open_long(), _quote() (+33 more)

### Community 40 - "threading"
Cohesion: 0.23
Nodes (6): _drive(), _make_engine(), _quote(), test_concurrent_publish_harvests_each_fill_once(), test_publish_state_snapshot_holds_engine_lock(), publish_many()

### Community 41 - "test_debug_report_fixes.py"
Cohesion: 0.08
Nodes (12): _fixture_bars(), _raise_no_network(), test_cooperative_stop_event(), test_full_restore_bootstrap_start_integration(), test_get_ui_state_mutation_isolation(), test_offline_start_does_not_execute_stale_candles(), test_session_save_and_restore_with_locked_margin(), test_slow_bootstrap_stop_safety() (+4 more)

### Community 42 - "ArenaStorage"
Cohesion: 0.21
Nodes (11): ArenaStorage, test_restore_survives_garbage_stop_ticket_and_entry_ts(), _candle(), test_p2_concurrent_candle_writes_all_persist(), writer(), test_p2_engine_stop_closes_storage_and_restart_still_writes(), test_p2_persistent_connection_recovers_from_stale_handle(), test_p2_persistent_connection_reused_and_candle_persists_across_close() (+3 more)

### Community 43 - "test_save_launch_progress.py"
Cohesion: 0.13
Nodes (10): _make_bridge(), _read_app_js(), test_get_save_launch_status_returns_copy(), test_save_and_launch_does_not_jump_splash_to_75(), test_save_launch_failed_stage_never_reports_100(), test_save_launch_stage_advances_and_done_only_on_return(), test_save_launch_stage_resets_between_runs(), test_save_launch_status_polled_from_js() (+2 more)

### Community 44 - "test_ai_panels_frontend.py"
Cohesion: 0.22
Nodes (19): _css(), _dashboard(), _html(), _js(), test_commander_and_stream_titles(), test_compact_mode_fits_intro_line_and_status_lines_hold_width(), test_deck_empty_slots_collapse_and_level_bottoms(), test_dock_gear_tooltip_is_ai_services() (+11 more)

### Community 45 - "test_event_article.py"
Cohesion: 0.13
Nodes (19): build_event_article_prompts(), _event_dict(), test_prompt_includes_raw_snippet(), test_prompt_without_snippet_omits_line(), test_telemetry_strips_raw_snippet(), _event_id(), _make_commander(), test_article_generation_uses_long_timeout() (+11 more)

### Community 46 - "test_live_chop_gate.py"
Cohesion: 0.19
Nodes (11): _bars(), _choppy_closes(), _engine_with_15m(), test_chop_gate_blocks_entry_through_try_enter_bracket(), test_chop_gate_blocks_on_choppy_15m(), test_chop_gate_excludes_the_forming_bucket(), test_chop_gate_never_blocks_signal_exit_close(), test_chop_gate_open_on_trending_15m() (+3 more)

### Community 47 - "test_ws_feed.py"
Cohesion: 0.14
Nodes (10): _run_feed(), test_ws_clean_server_close_counts_as_reconnect(), test_ws_connect_and_stream_delivers_quotes(), _fake_connect(), _on_quote(), test_ws_reconnect_backoff_on_disconnect(), _fake_connect(), _fake_sleep() (+2 more)

### Community 48 - "re"
Cohesion: 0.22
Nodes (10): _compile_word_group(), _compiled_word_re(), _contains_word(), _css(), _css_block(), test_article_renders_with_fade_in(), test_chevron_and_accordion_spring(), test_get_event_article_removed_from_dead_list() (+2 more)

### Community 50 - "config_manager.py"
Cohesion: 0.13
Nodes (8): _flat_engine(), test_no_redeploy_when_any_position_open(), test_redeploy_logs_once_per_flat_episode(), test_switch_off_does_not_redeploy(), test_switch_on_default_redeploys_when_flat(), _assets_root(), test_skip_bridge_deleted_but_mode_readers_kept(), test_wizard_has_no_skip_button()

### Community 51 - "test_gateway_diagnosis.py"
Cohesion: 0.15
Nodes (19): classify_llm_error(), _css(), _js(), test_classifier_402_plain_text_body_is_quota(), test_classifier_429_without_markers_is_transient(), test_classifier_auth_and_unknown(), test_classifier_deepseek_402_vs_429(), test_classifier_gemini_402_is_quota() (+11 more)

### Community 52 - "threading"
Cohesion: 0.10
Nodes (10): _FakeForum, _FakeHarvester, _make_commander(), test_concurrent_article_call_survives_refresh(), test_two_refreshes_leave_session_open(), _StubGateway, test_four_threads_expand_concurrently_without_closing_each_other(), _one() (+2 more)

### Community 53 - "test_llm_json_mode_fallback.py"
Cohesion: 0.18
Nodes (7): _client_with(), _CM, _FakeSession, _Resp, test_generic_400_does_not_trigger_the_format_retry(), test_rejected_format_is_remembered_for_later_calls(), test_rejected_response_format_retries_without_it_and_parses()

### Community 54 - "soak_engine.py"
Cohesion: 0.15
Nodes (14): closing_fills_since(), db_stats(), do_slice(), genome_valid(), main(), _sample(), make_quote(), _parse_args() (+6 more)

### Community 55 - "DeduplicationBuffer"
Cohesion: 0.18
Nodes (6): _dedup_normalize_title(), DeduplicationBuffer, _retry_window_seconds(), test_v24_track_c_omniroute_extract_json_retry_hint_dedup_and_https_redirect(), test_deduplication_buffer(), test_ingestion_clean_html_strips_script_style_and_dedup_forget()

### Community 56 - "test_auto_evolve_fires_on_closed_trades"
Cohesion: 0.16
Nodes (5): _drive_fixed(), test_auto_evolve_fires_on_closed_trades(), _round_trips(), test_live_tick_integration_fixed_price_series(), test_toggle_auto_evolve_reenable_compensates_disabled_time()

### Community 57 - "MultiTimeframeEngine"
Cohesion: 0.07
Nodes (16): IndicatorEngineMixin, MultiTimeframeEngine, test_track_b_mtf_engine_delta_volume_and_neutral_on_conflict(), test_v24_track_b_mtf_seed_1h_merges_same_slot(), _buckets(), _hourly_bars(), _minute_bars(), test_engine_seed_fetch_failure_stays_neutral() (+8 more)

### Community 58 - "StreamingCryptoFeed"
Cohesion: 0.24
Nodes (3): StreamingCryptoFeed, test_phase1_websocket_feed_parsing_and_fast_path_fallback(), test_parse_binance_ticker_rejects_garbage()

### Community 60 - "StructuredEvent"
Cohesion: 0.07
Nodes (22): InterruptDebouncer, StructuredEvent, _dedup_tickers(), _event_age_min(), _parse_event_epoch(), _safe_float(), test_synthesize_plumbs_raw_snippet(), test_structured_event_new_fields_default() (+14 more)

### Community 61 - "renderIntelHub"
Cohesion: 0.11
Nodes (26): buildIntelEventCard(), cleanIntelSummary(), clearIntelSearch(), formatIntelEventTime(), hashTickerName(), initIntelFilterControls(), intelArticleBodyEl(), intelEventKey() (+18 more)

### Community 62 - "test_phase3_soak.py"
Cohesion: 0.28
Nodes (4): _bootstrapped_engine(), _load_soak_helpers(), soak(), test_p3_mini_soak_many_ticks_no_growth_blowup()

### Community 63 - ".omniroute_installed"
Cohesion: 0.15
Nodes (3): test_gateway_unavailable_reason_no_node(), test_gateway_unavailable_reason_node_but_no_omniroute(), test_gateway_cli_command_never_falls_back_to_npx()

### Community 64 - "test_intel_hub_layout.py"
Cohesion: 0.25
Nodes (12): _commander(), _css(), _js(), _mock_pipeline(), _rule(), _structured(), test_stream_loading_block_is_centered_with_meter(), test_sync_status_failed_when_feeds_down() (+4 more)

### Community 65 - "renderAll"
Cohesion: 0.12
Nodes (27): buildSparklineGeometry(), createStrategyCardSkeleton(), ensureLiveTradingStarted(), fmtPct(), fmtSignedUsd(), fmtTimeSec(), fmtUsd(), initAppBoot() (+19 more)

### Community 66 - "ingestion.py"
Cohesion: 0.07
Nodes (17): _clean_html_text(), _parse_feed_ts(), _parse_iso_ts(), _rank_fresh_events(), MacroRegimeState, _now_iso(), _offline_commander(), _strong_bearish_events() (+9 more)

### Community 67 - "._build_snapshot_locked"
Cohesion: 0.20
Nodes (3): _safe_fmt_hms(), test_phase6_modular_view_model_and_state_delta_streaming(), test_safe_fmt_hms_handles_invalid_and_valid_timestamps()

### Community 68 - "getCommandPaletteItems"
Cohesion: 0.12
Nodes (22): applyBackdropMode(), closeCommandPalette(), cycleBackdropMode(), escapeHtml(), getCommandPaletteItems(), handleCmdPaletteOverlayClick(), initAmbientBackdrop(), initCommandPalette() (+14 more)

### Community 69 - "LiveQuote"
Cohesion: 0.18
Nodes (3): LiveQuote, QuoteFeedsMixin, test_track_b_quote_feeds_rejects_non_positive_and_non_finite()

### Community 70 - "controls/index.ts"
Cohesion: 0.24
Nodes (10): _broker(), _commander(), test_backtest_default_sizing_is_one(), test_compute_r_multiple_qty_scales_budget_and_clamps(), test_evaluate_signal_sizing_shrinks_qty_not_sl(), test_no_confidence_means_no_sizing_effect(), test_per_strategy_sensitivity_scales_the_deviation(), test_sizing_formula_exact_values() (+2 more)

### Community 71 - "_supervisor"
Cohesion: 0.18
Nodes (10): _supervisor(), test_watchdog_backs_off_between_failures(), test_watchdog_does_not_restart_healthy_gateway(), test_watchdog_first_tick_waits_one_interval(), test_watchdog_gives_up_after_repeated_failures(), test_watchdog_never_restarts_during_install(), test_watchdog_recovers_when_gateway_comes_back(), test_watchdog_restarts_dead_gateway_it_has_seen_healthy() (+2 more)

### Community 73 - "ArenaStorage"
Cohesion: 0.15
Nodes (4): _retry_on_db_error(), _sanitize_json_value(), test_track_b_persistence_batch_fills_and_prune_candles(), test_phase2_sqlite_wal_persistence_and_cold_start_hydration()

### Community 75 - "saveAndLaunchGateway"
Cohesion: 0.16
Nodes (20): applyGatewayAvailability(), checkOnboardingBoot(), clearSplashTimers(), confirmShutdown(), copyOmniPassword(), destroyAmbientBackdrop(), ensureRuntimeInstallPoll(), flashOmniPwdBadge() (+12 more)

### Community 76 - "test_ui_feedback.py"
Cohesion: 0.23
Nodes (7): _copy_text_to_clipboard_windows(), _bridge_with_env(), test_copy_password_copies_value_but_never_returns_it(), test_copy_password_helper_failure(), test_copy_password_not_configured(), test_copy_text_to_clipboard_windows_non_windows(), test_copy_text_to_clipboard_windows_roundtrip()

### Community 77 - "test_snapshot_counters_37.py"
Cohesion: 0.29
Nodes (4): _bars(), _round_trips(), test_short_history_is_not_marked_truncated(), test_snapshot_counters_survive_restore_with_truncated_history()

### Community 78 - "._live_loop"
Cohesion: 0.10
Nodes (6): _on_done(), test_pause_feed_updates_ui_snapshot_immediately(), test_stale_engine_evolve_now_refused(), test_stale_engine_harvest_fills_refused(), test_stale_engine_state_publish_skipped(), test_live_engine_toggle_pause_and_auto_evolve_shift_math()

### Community 79 - "test_504_omni_env_cache.py"
Cohesion: 0.28
Nodes (8): _counting_read_text(), _manager(), test_content_change_is_visible_after_rewrite(), test_missing_file_then_created(), test_mtime_change_invalidates_even_with_same_content(), test_repeated_reads_hit_cache(), test_returned_dict_is_a_copy(), test_write_then_read_sees_new_password()

### Community 80 - "test_v287_render_guards.py"
Cohesion: 0.40
Nodes (7): _fn_body(), _js(), test_hub_header_writes_guarded(), test_intel_card_element_refs_cached(), test_macro_ribbon_writes_guarded(), test_spotlight_vars_written_once_per_frame(), test_strat_color_and_gen_label_writes_guarded()

### Community 82 - "test_breakeven_count_29.py"
Cohesion: 0.33
Nodes (4): _breakeven_portfolio(), test_breakeven_close_counts_as_closed_trade(), test_breakeven_close_keeps_win_rate_decided_only(), test_breakeven_count_resets()

### Community 83 - ".test_single_key"
Cohesion: 0.16
Nodes (6): test_v24_track_c_gemini_header_and_save_gateway_no_split_brain(), test_gateway_supervisor_http_responses(), test_gateway_supervisor_key_validation_defensive(), test_gateway_supervisor_nvidia_endpoint(), test_key_rate_limit_429_is_not_verified(), test_gateway_test_single_key_non_ascii_and_gemini_400()

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
Cohesion: 0.23
Nodes (17): _dead_gateway_commander(), _mock_pipeline(), _structured(), test_sync_status_done_when_dead_gateway_still_yields_fallback_digest(), test_sync_status_failed_when_gateway_dead_and_nothing_produced(), _ev(), _now_iso(), _offline_commander() (+9 more)

### Community 89 - "test_digest_refresh_session.py"
Cohesion: 0.09
Nodes (7): test_track_c_omniroute_max_concurrent_1_repair_no_deadlock(), post(), _FakeCM, _FakeResp, _FakeSession, post(), post()

### Community 90 - "_fresh_broker_competitor"
Cohesion: 0.22
Nodes (5): _fresh_broker_competitor(), _r_multiple(), test_evaluate_signal_returns_none_when_breaker_tripped_all_strategies(), test_evaluate_signal_short_entries_mirror_long_brackets_all_strategies(), test_strategy_qty_zero_returns_none()

### Community 92 - "_error_body_text"
Cohesion: 0.33
Nodes (3): _error_body_text(), _walk(), _extract_error_provider()

### Community 93 - "test_502_ui_state_delta.py"
Cohesion: 0.39
Nodes (5): _engine(), _snapshot(), test_deepcopy_never_receives_heavy_arrays_on_unchanged_poll(), test_delta_is_still_a_defensive_copy(), test_delta_output_identical_to_old_path()

### Community 94 - "_make_dash"
Cohesion: 0.25
Nodes (7): _FakeWebview, _make_dash(), test_bridge_state_carries_diagnosis(), test_dashboard_diagnosis_states(), test_run_skips_watchdog_without_admin_password(), test_run_starts_watchdog_when_gateway_expected(), test_save_and_launch_starts_watchdog()

### Community 95 - "test_bootstrap_hydrates_fresh_sqlite_candles"
Cohesion: 0.22
Nodes (3): _cache_rows(), test_bootstrap_hydrates_fresh_sqlite_candles(), test_bootstrap_rejects_stale_sqlite_candles()

### Community 96 - "test_phase2g_graphics.py"
Cohesion: 0.31
Nodes (4): _js(), test_p2g_chart_loop_capped_at_60fps(), test_p2g_hidden_view_stops_chart_loop(), test_p2g_no_temporary_probe_left_in_shipped_assets()

### Community 97 - "_FakeWebview"
Cohesion: 0.25
Nodes (3): _FakeWebview, test_run_auto_spawn_waits_30_seconds(), test_run_skips_auto_spawn_without_admin_password()

### Community 98 - "_client"
Cohesion: 0.25
Nodes (8): _client(), test_all_providers_quota_exhausted_needs_every_provider(), test_daily_budget_exhausted(), test_no_configured_providers_is_never_exhausted(), test_stale_quota_records_expire(), test_success_clears_quota_records(), test_transient_failures_never_count_as_quota(), test_unattributed_quota_counts_only_for_single_provider()

### Community 101 - "test_318_system_config_untracked.py"
Cohesion: 0.33
Nodes (5): _git(), test_system_config_is_ignored_by_git(), test_system_config_is_untracked_but_present_on_disk(), test_p2_eth_feed_first_fetch_loads_pandas_and_behaves(), test_p2_eth_feed_import_does_not_import_pandas()

### Community 103 - "test_322_apply_fill_failure.py"
Cohesion: 0.38
Nodes (4): _open_long(), test_apply_fill_value_error_does_not_kill_cadence(), _boom(), test_submit_order_returns_none_when_apply_fill_fails()

### Community 104 - "_referenced_classes"
Cohesion: 0.33
Nodes (3): _class_value_tokens(), _referenced_classes(), _string_literals()

### Community 107 - "test_phase1_debug_sweep.py"
Cohesion: 0.18
Nodes (5): _OKHandler, _safe_refresh(), test_deserialize_ticket_garbage_numbers_return_none(), test_refresh_intel_digest_is_serialized_under_concurrent_calls(), _run()

### Community 108 - "cursors/index.tsx"
Cohesion: 0.20
Nodes (14): clearOverlapTransitionStyles(), drawPriceChart(), invalidateCanvasSizeCache(), locateMouseAndRefreshChart(), refreshScrollAreaFades(), setIntelSortMode(), setLgWallpaper(), setRightTab() (+6 more)

### Community 113 - ".compute_r_multiple_qty"
Cohesion: 0.08
Nodes (6): _parse_pos_dec(), _broker(), test_aggressive_stopout_loss_capped_at_risk_pct(), test_drawdown_trip_closes_positions_via_broker(), _open_short(), test_short_trailing_stop_ratchets_down_then_exits_at_trailed_level()

### Community 114 - "gateway_supervisor.py"
Cohesion: 0.08
Nodes (9): parse_omni_env_line(), _default_daemon_log_path(), _default_install_log_path(), _FakeEvent, _FakeWindow, test_daemon_log_default_path_is_project_logs(), test_existing_daemon_check_uses_2s_probe(), test_save_and_launch_gateway_waits_30_seconds() (+1 more)

### Community 138 - "LiveArenaEngine"
Cohesion: 0.07
Nodes (31): LiveArenaEngine, build_engine_view_model(), test_bootstrap_resets_live_trading_state_when_orders_disabled(), test_signal_exit_fast_path_closes_under_hold_cash(), _engine(), test_autosave_does_not_fire_when_stopped_or_superseded(), test_crash_like_stop_leaves_restorable_autosave(), test_evolution_marks_autosave_pending_and_it_fires_immediately() (+23 more)

### Community 139 - "fix_item5_patch.py"
Cohesion: 0.11
Nodes (22): addChartBeacon(), attachToastInteractions(), createPositionClosedToastElement(), createPositionToastElement(), dismissToast(), enqueueToast(), fillRoundRect(), hexToRgba() (+14 more)

### Community 146 - "Choreography"
Cohesion: 0.29
Nodes (6): 1. Launch Packaged Desktop Executable (`.exe`), 2. Run Self-Test Verification, 3. Run Automated Unit Test Suite (32 Tests), 4. Build Standalone Windows Executable, Quick Start Guide, TradeBot0: Multi-Agent Paper Trading & Genetic Evolution Arena (BTC/USD)

## Knowledge Gaps
- **38 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `LiveArenaEngine` connect `LiveArenaEngine` to `test_v200_fixes.py`, `CandleBar`, `OrderTicket`, `ArenaDashboard`, `live_engine.py`, `test_ticket_reason_38.py`, `ViewModelPublisher`, `OmniRouteClient`, `OrderSide`, `MacroCommander`, `GeneticEvolver`, `test_phase3_ingestion.py`, `soak_engine.py`, `test_performance_and_optimizations.py`, `MonteCarloOddsEvaluator`, `test_performance_and_optimizations.py`, `ConfigManager`, `test_live_engine.py`, `threading`, `test_debug_report_fixes.py`, `ArenaStorage`, `test_live_chop_gate.py`, `LiveStrategyRunnerMixin`, `config_manager.py`, `soak_engine.py`, `test_auto_evolve_fires_on_closed_trades`, `MultiTimeframeEngine`, `StreamingCryptoFeed`, `test_phase3_soak.py`, `ingestion.py`, `._build_snapshot_locked`, `LiveQuote`, `controls/index.ts`, `SessionCodecMixin`, `test_snapshot_counters_37.py`, `._live_loop`, `test_507_candle_write_on_close.py`, `_open_short`, `test_502_ui_state_delta.py`, `test_bootstrap_hydrates_fresh_sqlite_candles`, `._handle_ws_quote`, `test_phase1_debug_sweep.py`, `test_restore_applies_genome_leverage_to_portfolio`, `.is_fresh`?**
  _High betweenness centrality (0.106) - this node is a cross-community bridge._
- **Are the 12 inferred relationships involving `LiveArenaEngine` (e.g. with `Architectural Highlights` and `MonteCarloOddsEvaluator`) actually correct?**
  _`LiveArenaEngine` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Should `BrokerSim` be split into smaller, more focused modules?**
  _Cohesion score 0.12310606060606061 - nodes in this community are weakly interconnected._
- **Why does `OmniRouteClient` connect `OmniRouteClient` to `ingestion.py`, `test_v200_fixes.py`, `_client`, `test_omniroute_client_quota_fastpath_sse_error_and_timeout`, `test_item10_packaging.py`, `LiveArenaEngine`, `live_engine.py`, `IntelligenceHarvester`, `OrderSide`, `threading`, `MacroCommander`, `test_gateway_diagnosis.py`, `test_llm_json_mode_fallback.py`, `test_digest_refresh_session.py`, `test_phase3_ingestion.py`, `StructuredEvent`, `test_performance_and_optimizations.py`?**
  _High betweenness centrality (0.080) - this node is a cross-community bridge._
- **Are the 99 inferred relationships involving `OrderSide` (e.g. with `main()` and `BrokerSim`) actually correct?**
  _`OrderSide` has 99 INFERRED edges - model-reasoned connections that need verification._
- **Should `test_update_checker.py` be split into smaller, more focused modules?**
  _Cohesion score 0.08478513356562137 - nodes in this community are weakly interconnected._
- **Why does `GatewaySupervisor` connect `GatewaySupervisor` to `test_item10_packaging.py`, `test_ui_contract.py`, `ArenaDashboard`, `live_engine.py`, `OrderSide`, `test_gateway_install_progress_cancel.py`, `test_phase3_ingestion.py`, `test_track_c_gateway_npm_strips_secrets_and_no_blind_retry`, `test_performance_and_optimizations.py`, `test_start_daemon_concurrent_calls_spawn_once`, `ConfigManager`, `test_gateway_autolaunch_mandatory.py`, `test_save_launch_progress.py`, `config_manager.py`, `test_gateway_diagnosis.py`, `threading`, `._run_runtime_install`, `.omniroute_installed`, `ingestion.py`, `_supervisor`, `.sync_admin_password`, `.test_single_key`, `_make_dash`, `_FakeHTTPResponse`, `test_phase1_debug_sweep.py`, `gateway_supervisor.py`?**
  _High betweenness centrality (0.077) - this node is a cross-community bridge._