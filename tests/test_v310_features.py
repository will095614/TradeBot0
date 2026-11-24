"""V3.1.0 verification tests: chop ER telemetry, preferences persistence,
view model payloads/deltas, bridge journal export & AI settings, and UI contracts.
"""
import csv
import json
import re
import time
from decimal import Decimal
from pathlib import Path

from src.arena.leaderboard import Leaderboard
from src.arena.order import ExecutionReason, FillEvent, OrderSide, PositionSide
from src.data.indicator_engine import CHOP_GATE_ER_THRESHOLD, CHOP_GATE_WINDOW_BARS
from src.data.live_engine import LiveArenaEngine
from src.gui.dashboard import ArenaDashboard, _ArenaBridgeApi
from src.gui.view_model import ViewModelPublisher, _empty_view_model, build_engine_view_model
from src.intelligence.config_manager import (
    ALLOWED_GEMINI_MODELS,
    DEFAULT_GEMINI_MODEL,
    ConfigManager,
)

_REPO = Path(__file__).resolve().parents[1]
_ASSETS = _REPO / "src" / "gui" / "assets"


def _make_15m_bars(closes):
    return [
        {
            "t": float(1700000000 + i * 900),
            "o": float(c),
            "h": float(c),
            "l": float(c),
            "c": float(c),
            "v": 1.0,
        }
        for i, c in enumerate(closes)
    ]


def test_chop_er_20_warmup_and_values():
    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    try:
        # Exactly CHOP_GATE_WINDOW_BARS closed bars + 1 forming -> still warming up
        engine.candles_15m = _make_15m_bars([3500.0] * (CHOP_GATE_WINDOW_BARS + 1))
        assert engine.get_chop_er_20() is None
        assert engine._chop_gate_blocks() is False

        # One additional closed bar crosses warmup boundary -> float in [0, 1]
        choppy = [3500.0 + (20.0 if i % 2 else 0.0) for i in range(CHOP_GATE_WINDOW_BARS + 2)]
        engine.candles_15m = _make_15m_bars(choppy)
        er_chop = engine.get_chop_er_20()
        assert er_chop is not None
        assert 0.0 <= er_chop < CHOP_GATE_ER_THRESHOLD
        assert engine._chop_gate_blocks() is True

        # Monotonic trend -> ER close to 1.0, gate open
        trend = [3500.0 + 10.0 * i for i in range(CHOP_GATE_WINDOW_BARS + 2)]
        engine.candles_15m = _make_15m_bars(trend)
        er_trend = engine.get_chop_er_20()
        assert er_trend is not None
        assert CHOP_GATE_ER_THRESHOLD <= er_trend <= 1.0
        assert engine._chop_gate_blocks() is False
    finally:
        engine.stop()


def test_config_manager_ai_preferences_roundtrip(tmp_path):
    assert DEFAULT_GEMINI_MODEL in ALLOWED_GEMINI_MODELS
    cm = ConfigManager(data_dir=tmp_path / "data")
    assert cm.get_gemini_model() == DEFAULT_GEMINI_MODEL
    assert cm.get_preload_intel_articles() is True

    target_model = ALLOWED_GEMINI_MODELS[-1]
    res = cm.set_gemini_model(target_model)
    assert res["ok"] is True
    assert cm.get_gemini_model() == target_model

    bad = cm.set_gemini_model("unknown-model-999")
    assert bad["ok"] is False
    assert cm.get_gemini_model() == target_model

    empty_bad = cm.set_gemini_model("")
    assert empty_bad["ok"] is False
    assert cm.get_gemini_model() == target_model

    p_res = cm.set_preload_intel_articles(False)
    assert p_res["ok"] is True
    assert cm.get_preload_intel_articles() is False

    # Reload from persisted system_config.json on disk
    cm2 = ConfigManager(data_dir=tmp_path / "data")
    assert cm2.get_gemini_model() == target_model
    assert cm2.get_preload_intel_articles() is False

    p_res2 = cm2.set_preload_intel_articles(True)
    assert p_res2["ok"] is True
    assert cm2.get_preload_intel_articles() is True


def test_view_model_v310_fields_and_delta_suppression():
    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    try:
        trend = [3500.0 + 5.0 * i for i in range(CHOP_GATE_WINDOW_BARS + 2)]
        engine.candles_15m = _make_15m_bars(trend)
        engine.candles_5m = [
            {"t": float(1700000000 + i * 300), "o": 3500.0, "h": 3510.0, "l": 3495.0, "c": 3505.0, "v": 2.0}
            for i in range(10)
        ]
        engine.live_chop_gate_blocked = 3
        comp = engine.competitors[0]
        comp.portfolio.equity_history = [(float(1700000000 + i * 60), 100000.0 + i) for i in range(120)]

        rankings = Leaderboard.get_rankings(engine.broker.portfolios)
        vm = build_engine_view_model(engine, rankings, gen=2)

        rt = vm["risk_telemetry"]
        for key in (
            "chop_er_20",
            "chop_threshold",
            "chop_blocked",
            "chop_blocked_count",
            "gross_exposure_usd",
            "total_equity_usd",
            "gross_leverage",
            "macro_risk_mult",
            "activity_heatmap",
        ):
            assert key in rt
        assert rt["chop_blocked_count"] == 3
        assert len(rt["activity_heatmap"]["matrix"]) == 5
        assert all(len(row) == 12 for row in rt["activity_heatmap"]["matrix"])

        assert len(vm["candles_5m"]) == 10
        assert len(vm["candles_15m"]) == len(trend)
        assert "gemini_model" in vm["ui_prefs"]
        assert "preload_intel_articles" in vm["ui_prefs"]

        s0 = vm["strategies"][0]
        assert isinstance(s0["genome_params"], dict) and len(s0["genome_params"]) >= 5
        assert len(s0["equity_history"]) <= 60
        assert all("t" in pt and "v" in pt for pt in s0["equity_history"])

        # Delta publisher suppresses unchanged 5m/15m candles and emits them on change
        pub = ViewModelPublisher()
        d1 = pub.compute_delta_from_snapshot(vm)
        assert d1["is_delta"] is False
        assert "candles_5m" in d1 and "candles_15m" in d1

        d2 = pub.compute_delta_from_snapshot(vm)
        assert d2["is_delta"] is True
        assert d2["candles_5m_unchanged"] is True
        assert d2["candles_15m_unchanged"] is True
        assert "candles_5m" not in d2 and "candles_15m" not in d2

        vm_changed = json.loads(json.dumps(vm))
        vm_changed["candles_5m"].append({"t": 1700009999.0, "o": 3600.0, "h": 3610.0, "l": 3595.0, "c": 3605.0, "v": 1.0})
        d3 = pub.compute_delta_from_snapshot(vm_changed)
        assert d3["candles_5m_unchanged"] is False
        assert d3["candles_15m_unchanged"] is True
        assert "candles_5m" in d3 and "candles_15m" not in d3

        empty = _empty_view_model("probe")
        assert "risk_telemetry" in empty
        assert "ui_prefs" in empty
        assert "candles_5m" in empty and "candles_15m" in empty
    finally:
        engine.stop()


def test_bridge_update_ai_preferences_and_invalid_model(tmp_path):
    dash = ArenaDashboard()
    dash.config_manager = ConfigManager(data_dir=tmp_path / "data")
    bridge = _ArenaBridgeApi(dash)
    captured = {}

    class _FakeLlm:
        def set_models(self, ingest, commander):
            captured["ingest"] = ingest
            captured["commander"] = commander

    dash.engine.llm_client = _FakeLlm()
    try:
        target_model = ALLOWED_GEMINI_MODELS[-1]
        res = bridge.update_ai_preferences(model=target_model, preload_articles=False)
        assert res["ok"] is True
        assert res["gemini_model"] == target_model
        assert res["preload_intel_articles"] is False
        assert dash.config_manager.get_gemini_model() == target_model
        assert dash.config_manager.get_preload_intel_articles() is False
        assert dash.engine.preload_intel_articles is False
        assert captured == {"ingest": target_model, "commander": target_model}

        bad = bridge.update_ai_preferences(model="nonexistent-model-x")
        assert bad["ok"] is False
        assert dash.config_manager.get_gemini_model() == target_model
    finally:
        dash.engine.stop()


def test_bridge_export_trade_journal_csv_json_and_invalid(tmp_path):
    dash = ArenaDashboard()
    dash.config_manager = ConfigManager(data_dir=tmp_path / "data")
    bridge = _ArenaBridgeApi(dash)
    try:
        now = time.time()
        dash.engine.fill_records = [
            FillEvent(
                order_id="ord-1",
                portfolio_id="comp_agg",
                symbol="ETH/USD",
                side=OrderSide.BUY,
                qty=Decimal("1.50"),
                price=Decimal("3200.00"),
                fee=Decimal("1.20"),
                timestamp=now - 10,
                realized_pnl=Decimal("0.00"),
                reason=ExecutionReason.SIGNAL,
                fill_seq=1,
                position_side=PositionSide.LONG,
            ),
            FillEvent(
                order_id="ord-2",
                portfolio_id="comp_agg",
                symbol="ETH/USD",
                side=OrderSide.SELL,
                qty=Decimal("1.50"),
                price=Decimal("3240.00"),
                fee=Decimal("1.22"),
                timestamp=now,
                realized_pnl=Decimal("57.58"),
                reason=ExecutionReason.TAKE_PROFIT,
                fill_seq=2,
                entry_price=Decimal("3200.00"),
                position_side=PositionSide.LONG,
            ),
        ]

        csv_out = tmp_path / "exports" / "journal.csv"
        res_csv = bridge.export_trade_journal("csv", output_path=str(csv_out))
        assert res_csv["ok"] is True
        assert res_csv["count"] == 2
        assert csv_out.is_file()
        with csv_out.open("r", encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 2
        assert rows[0]["action"] == "OPEN LONG"
        assert rows[1]["action"] == "CLOSE LONG"

        json_out = tmp_path / "exports" / "journal.json"
        res_json = bridge.export_trade_journal("json", output_path=str(json_out))
        assert res_json["ok"] is True
        assert res_json["count"] == 2
        assert json_out.is_file()
        payload = json.loads(json_out.read_text(encoding="utf-8"))
        assert "version" in payload and "exported_at" in payload
        assert payload["count"] == 2
        assert len(payload["trades"]) == 2

        bad = bridge.export_trade_journal("xml", output_path=str(tmp_path / "x.xml"))
        assert bad["ok"] is False
    finally:
        dash.engine.stop()


def test_v310_frontend_dom_css_and_wizard_invariants():
    html = (_ASSETS / "index.html").read_text(encoding="utf-8")
    css = (_ASSETS / "app.css").read_text(encoding="utf-8")
    js = (_ASSETS / "app.js").read_text(encoding="utf-8")

    # Required V3.1.0 DOM anchors
    required_ids = [
        "modularSlotPanel",
        "modBayTabBar",
        "modBayGauges",
        "modBayHeatmap",
        "modBayEvolutions",
        "modBayStatusPill",
        "btnPrivateBalance",
        "chartTimeframeGroup",
        "btnTf1m",
        "btnTf5m",
        "btnTf15m",
        "btnExportJournal",
        "btnOfflineExit",
        "aiBotAvatar",
        "macroHubDirective",
        "intelChipSlider",
        "intelEmptyState",
        "btnSetupTabAi",
        "btnSetupTabAppearance",
        "setupTabAi",
        "setupTabAppearance",
        "setupGeminiModelSelect",
        "setupPreloadToggle",
        "backdropCardShader",
        "backdropCardGrainient",
        "backdropCardMinimal",
        "strategyDetailModal",
        "stratDetailCurveSvg",
        "stratDetailGenomeGrid",
        "stratDetailFillsBody",
    ]
    for dom_id in required_ids:
        assert f'id="{dom_id}"' in html, f"Missing id={dom_id!r} in index.html"

    # Zero CJK glyphs across shipped frontend bundle
    for fname, content in (("index.html", html), ("app.css", css), ("app.js", js)):
        assert not re.search(r"[\u4e00-\u9fff]", content), f"CJK glyph found in {fname}"

    # Wizard invariants: no vertical scroll, single provider card, single action button
    wiz_m = re.search(r'\.setup-wizard-modal\s*\{[^}]*\}', css)
    assert wiz_m is not None
    assert "overflow-y: hidden;" in wiz_m.group(0)

    wiz_start = html.index('id="setupWizardModal"')
    wiz_end = html.index('id="wizardCloseConfirmModal"')
    wizard_html = html[wiz_start:wiz_end]
    assert wizard_html.count('class="setup-provider-card"') == 1
    act_start = wizard_html.index('class="setup-wizard-actions"')
    act_block = wizard_html[act_start:act_start + 500]
    assert act_block.count("<button") == 1

    # GPU pause selectors: hidden window & reduced motion cover new continuous animations
    hidden_block = css.split("body.window-hidden", 1)[1].split("@media (prefers-reduced-motion: reduce)", 1)[0]
    reduced_block = css.split("@media (prefers-reduced-motion: reduce) {", -1)[-1]
    assert ".ai-bot-avatar.is-working .ai-bot-eye" in hidden_block
    assert ".ai-bot-avatar.is-working .ai-bot-eye" in reduced_block
    assert ".directive-word" in reduced_block
