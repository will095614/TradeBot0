"""V2.5.2 UI & UX regression tests (brand subtitle, password reveal, sort FLIP, real article progress)."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.gui.dashboard import ArenaDashboard, _ArenaBridgeApi
from src.gui.view_model import ViewModelPublisher
from src.intelligence.config_manager import ConfigManager
from src.intelligence.ingestion import StructuredEvent
from src.intelligence.macro_commander import MacroCommander
from src.intelligence.omniroute_client import OmniRouteClient
from src.version import APP_VERSION

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "src" / "gui" / "assets"


def test_brand_subtitle_never_squeezed_to_ellipsis():
    css = (ASSETS / "app.css").read_text(encoding="utf-8")
    brand_block = css.split(".lg-dock-pod--brand {", 1)[1].split("}", 1)[0]
    group_block = css.split(".title-group {", 1)[1].split("}", 1)[0]
    sub_block = css.split(".title-sub {", 1)[1].split("}", 1)[0]

    assert "min-width: max-content" in brand_block
    assert "overflow: visible" in group_block
    assert "overflow: visible" in sub_block
    assert "text-overflow: ellipsis" not in sub_block
    # Media queries must not crush .title-group/.title-sub down to 140px
    assert "140px" not in css


def test_password_eye_button_and_reveal_bridge(tmp_path):
    html = (ASSETS / "index.html").read_text(encoding="utf-8")
    js = (ASSETS / "app.js").read_text(encoding="utf-8")
    css = (ASSETS / "app.css").read_text(encoding="utf-8")

    # Eye button placed immediately to the right of #omniConsolePwd copy badge
    idx_pwd = html.index('id="omniConsolePwd"')
    idx_eye = html.index('id="btnToggleOmniPwd"')
    assert idx_pwd < idx_eye
    assert 'onclick="toggleOmniPasswordVisibility()"' in html
    assert "window.toggleOmniPasswordVisibility = toggleOmniPasswordVisibility;" in js
    assert "window.copyOmniPassword = copyOmniPassword;" in js
    assert ".pwd-eye-btn" in css
    assert ".pwd-badge.pwd-revealed" in css

    # Bridge method returns password on explicit reveal, error when unset
    dash = ArenaDashboard()
    dash.config_manager = ConfigManager(
        data_dir=tmp_path / "data",
        omni_env_path=tmp_path / ".omniroute" / ".env",
    )
    env_dir = tmp_path / ".omniroute"
    env_dir.mkdir(parents=True, exist_ok=True)
    bridge = _ArenaBridgeApi(dash)

    (env_dir / ".env").write_text("GEMINI_API_KEY=sk-test\n", encoding="utf-8")
    missing = bridge.reveal_omniroute_password()
    assert missing["status"] == "error"

    (env_dir / ".env").write_text("INITIAL_PASSWORD=MyV252Secret!\n", encoding="utf-8")
    shown = bridge.reveal_omniroute_password()
    assert shown == {"status": "ok", "password": "MyV252Secret!"}
    dash.engine.stop()


def test_intel_sort_collapses_expanded_cards_and_uses_flip_animation():
    js = (ASSETS / "app.js").read_text(encoding="utf-8")
    css = (ASSETS / "app.css").read_text(encoding="utf-8")

    assert "function reorderIntelEventCards" in js
    assert "intel-card-reordering" in js
    assert ".intel-event-card.intel-card-reordering" in css
    assert "intelSortTransitionPending" in js
    assert "intelExpandedIds.clear()" in js
    # Sort mode collapses open cards before triggering FLIP reorder
    fn_start = js.index("function setIntelSortMode(")
    fn_slice = js[fn_start : fn_start + 2200]
    assert "hadExpanded" in fn_slice
    assert "openCard.classList.remove('is-open')" in fn_slice
    assert "setTimeout(applySortNow, 360)" in fn_slice


def test_intel_event_time_hides_seconds():
    js = (ASSETS / "app.js").read_text(encoding="utf-8")
    assert "function formatIntelEventTime(" in js
    assert "formatIntelEventTime(rawTime)" in js


def test_article_real_streamed_progress_and_viewmodel_delta():
    # 1. Verify SSE streaming in OmniRouteClient.chat_json drives monotonic real progress callbacks
    article_body = (
        "事件經過：以太坊機構資金連續五日淨流入，帶動市場交投熱絡。"
        "背景脈絡：宏觀流動性預期轉暖，市場風險偏好顯著回升。"
        "市場含義：現貨需求支撐價格重心上移，衍生品資金費率維持健康。"
        "風險因素：短線獲利了結賣壓與宏觀數據公布仍可能引發波動。"
        "後續觀察：需持續追蹤鏈上大額轉帳與 ETF 單日申贖變化。"
        "總結：整體結構偏向中性偏多，建議嚴守風控紀律。"
    ) * 6
    payload_json = json.dumps({"article": article_body}, ensure_ascii=False)
    # Split into 10 SSE chunks
    step = max(1, len(payload_json) // 10)
    sse_lines = []
    for i in range(0, len(payload_json), step):
        chunk = payload_json[i : i + step]
        sse_lines.append(
            f"data: {json.dumps({'choices': [{'delta': {'content': chunk}}]}, ensure_ascii=False)}\n".encode("utf-8")
        )
    sse_lines.append(b"data: [DONE]\n")

    class _FakeStreamContent:
        def __aiter__(self):
            self._it = iter(sse_lines)
            return self

        async def __anext__(self):
            try:
                return next(self._it)
            except StopIteration:
                raise StopAsyncIteration

    class _FakeResp:
        status = 200
        headers = {"Content-Type": "text/event-stream"}
        content = _FakeStreamContent()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    class _FakeSession:
        closed = False

        def post(self, *args, **kwargs):
            assert kwargs["json"].get("stream") is True
            return _FakeResp()

    client = OmniRouteClient(base_url="http://127.0.0.1:20128/v1")
    client.is_gateway_online = True
    client.model_ingest = "test-model"

    async def _get_sess():
        return _FakeSession()

    client.get_session = _get_sess  # type: ignore[method-assign]

    progress_events = []
    commander = MacroCommander(client)
    asyncio.run(
        commander.synthesize_regime(
            [
                StructuredEvent(
                    timestamp="2026-11-23T01:39:35Z",
                    source="StockTwits ETH.X",
                    domain="forum",
                    entities_tickers=["ETH"],
                    urgency_score=2,
                    sentiment_score=0.10,
                    summary="測試摘要：以太幣社群討論升溫。",
                    raw_title="ETH community buzz rising",
                    headline_zh="以太幣社群討論升溫",
                )
            ]
        )
    )

    orig_set = commander._set_article_progress

    def _recording_set(evt, pct, stage):
        progress_events.append((pct, stage))
        orig_set(evt, pct, stage)

    commander._set_article_progress = _recording_set  # type: ignore[method-assign]
    evt_id = commander.curated_events[0]["id"]
    bridge = _ArenaBridgeApi(SimpleNamespace(engine=SimpleNamespace(macro_commander=commander)))

    res = bridge.get_event_article(evt_id)
    assert res["ok"] is True
    assert res["article"] == article_body
    # Real multi-stage progress occurred across connecting -> waiting -> streaming -> parsing -> finalizing
    pcts = [p for p, _ in progress_events]
    stages = [s for _, s in progress_events]
    assert len(progress_events) >= 5
    assert pcts == sorted(pcts)
    assert pcts[0] < 30 and pcts[-1] >= 95
    assert any("Waiting" in s for s in stages)
    assert any(("Analyzing" in s or "Drafting" in s) for s in stages)

    prog_final = bridge.get_event_article_progress(evt_id)
    assert prog_final["ok"] is True
    assert prog_final["state"] == "ready"
    assert prog_final["progress"] == 100

    # 2. ViewModel delta detects article_progress / article_stage updates
    pub = ViewModelPublisher()
    snap1 = {
        "candles": [],
        "fills": [],
        "intel_hub": {"events": [{"id": evt_id, "article_state": "loading", "article_progress": 26, "article_stage": "Waiting for AI response"}]},
    }
    snap2 = {
        "candles": [],
        "fills": [],
        "intel_hub": {"events": [{"id": evt_id, "article_state": "loading", "article_progress": 58, "article_stage": "Drafting in-depth report"}]},
    }
    pub.compute_delta_from_snapshot(snap1)
    d2 = pub.compute_delta_from_snapshot(snap2)
    assert d2["intel_events_unchanged"] is False
    assert d2["intel_hub"]["events"][0]["article_progress"] == 58
    assert APP_VERSION == "V2.5.2"
