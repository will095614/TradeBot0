"""V3.2.1 regression tests: Full-English interface, English AI prompts/fallbacks, and version sync."""
from __future__ import annotations

import asyncio
import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from src.gui.view_model import _empty_view_model
from src.intelligence.ingestion import IntelligenceHarvester, RawEvent, StructuredEvent
from src.intelligence.macro_commander import (
    ARTICLE_SECTION_HEADINGS,
    DEFAULT_ACTIVE_HEADLINE,
    MacroCommander,
    build_event_article_prompts,
)
from src.version import APP_VERSION

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "src" / "gui" / "assets"

_CJK_CHAR_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff\u3000-\u303f\uff00-\uffef]")
_U_ESCAPE_RE = re.compile(r"\\u([0-9a-fA-F]{4})")
_HTML_ENTITY_HEX_RE = re.compile(r"&#[xX]([0-9a-fA-F]+);")
_HTML_ENTITY_DEC_RE = re.compile(r"&#([0-9]+);")


def _is_cjk_codepoint(cp: int) -> bool:
    return (0x3000 <= cp <= 0x303F) or (0x4E00 <= cp <= 0x9FFF) or (0xFF00 <= cp <= 0xFFEF)


def test_v321_version_and_readme_english():
    assert APP_VERSION == "V3.3.0"
    iss = (ROOT / "TradeBot0.iss").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert '#define MyAppVersion "V3.3.0"' in iss
    assert "VersionInfoVersion=3.3.0" in iss
    assert "https://github.com/will095614/TradeBot0/releases/download/v3.3.0/TradeBot0Setup-V3.3.0.exe" in readme
    assert "Traditional Chinese" not in readme


def test_production_assets_and_modules_have_zero_cjk_strings():
    targets = [
        ASSETS / "index.html",
        ASSETS / "app.js",
        ASSETS / "app.css",
        ROOT / "src" / "gui" / "view_model.py",
        ROOT / "src" / "intelligence" / "ingestion.py",
        ROOT / "src" / "intelligence" / "macro_commander.py",
    ]
    for path in targets:
        text = path.read_text(encoding="utf-8")
        assert not _CJK_CHAR_RE.search(text), f"Raw CJK found in {path.name}"

        for idx, line in enumerate(text.splitlines(), 1):
            #ingestion._contains_cjk intentionally checks the Unicode range [\u4e00-\u9fff]
            if path.name == "ingestion.py" and "_contains_cjk" in line:
                continue
            if path.name == "ingestion.py" and r'[\u4e00-\u9fff]' in line:
                continue
            for m in _U_ESCAPE_RE.finditer(line):
                cp = int(m.group(1), 16)
                assert not _is_cjk_codepoint(cp), f"CJK \\u escape in {path.name}:{idx}: {line.strip()}"
            for m in _HTML_ENTITY_HEX_RE.finditer(line):
                cp = int(m.group(1), 16)
                assert not _is_cjk_codepoint(cp), f"CJK HTML hex entity in {path.name}:{idx}: {line.strip()}"
            for m in _HTML_ENTITY_DEC_RE.finditer(line):
                cp = int(m.group(1), 10)
                assert not _is_cjk_codepoint(cp), f"CJK HTML dec entity in {path.name}:{idx}: {line.strip()}"


def test_app_js_splash_gate_does_not_require_cjk_news():
    js = (ASSETS / "app.js").read_text(encoding="utf-8")
    assert "hasZhNews" not in js
    assert "hasIntelNews" in js


def test_harvester_produces_english_across_online_offline_and_cjk_inputs():
    async def _run():
        # 1. Online English LLM response
        online_client = MagicMock()
        online_client.is_gateway_online = True
        online_client.model_ingest = "gemini-3.1-flash-lite"
        online_client.chat_json = AsyncMock(return_value={
            "events": [{
                "index": 1,
                "entities_tickers": ["ETH"],
                "urgency_score": 7,
                "sentiment_score": 0.45,
                "headline": "Ethereum ETF Inflows Accelerate Ahead of Macro Release",
                "summary": "Spot Ethereum ETF products saw net inflows rise sharply, supporting bullish spot positioning.",
            }]
        })
        harvester = IntelligenceHarvester(client=online_client)
        raw_en = [RawEvent(
            source="CoinDesk",
            domain="crypto",
            title="Ethereum ETF inflows accelerate",
            url="https://example.com/eth-1",
            timestamp=1700000000.0,
        )]
        res_online = await harvester.process_batch(raw_en)
        assert len(res_online) == 1
        assert res_online[0].headline == "Ethereum ETF Inflows Accelerate Ahead of Macro Release"
        assert res_online[0].headline_zh == res_online[0].headline
        assert not _CJK_CHAR_RE.search(res_online[0].summary)

        # Verify prompt requests English, not Traditional Chinese
        sys_prompt = online_client.chat_json.await_args.kwargs["system_prompt"]
        usr_prompt = online_client.chat_json.await_args.kwargs["user_prompt"]
        assert "Traditional Chinese" not in sys_prompt
        assert "English" in sys_prompt and "English" in usr_prompt

        # 2. CJK leakage from LLM or non-English source title is normalized to English
        cjk_client = MagicMock()
        cjk_client.is_gateway_online = True
        cjk_client.model_ingest = "gemini-3.1-flash-lite"
        cjk_client.chat_json = AsyncMock(return_value={
            "events": [{
                "index": 1,
                "entities_tickers": ["AI"],
                "urgency_score": 6,
                "sentiment_score": 0.3,
                "headline_zh": "輝達 AI 晶片需求強勁",
                "summary": "供應鏈消息指出 AI 伺服器出貨維持高檔。",
            }]
        })
        harvester_cjk = IntelligenceHarvester(client=cjk_client)
        raw_cjk = [RawEvent(
            source="TechNews",
            domain="tech",
            title="輝達 AI 晶片需求強勁",
            url="https://example.com/ai-1",
            timestamp=1700000100.0,
        )]
        res_guarded = await harvester_cjk.process_batch(raw_cjk)
        assert len(res_guarded) == 1
        assert res_guarded[0].headline.strip()
        assert res_guarded[0].summary.strip()
        assert not _CJK_CHAR_RE.search(res_guarded[0].headline)
        assert not _CJK_CHAR_RE.search(res_guarded[0].summary)

        # 3. Offline deterministic NLP fallback produces English
        offline_client = MagicMock()
        offline_client.is_gateway_online = False
        offline_client.chat_json = AsyncMock(return_value=None)
        harvester_off = IntelligenceHarvester(client=offline_client)
        raw_off = [RawEvent(
            source="ForexLive",
            domain="macro",
            title="Federal Reserve signals steady rate path as CPI cools",
            url="https://example.com/fed-1",
            timestamp=1700000200.0,
        )]
        res_off = await harvester_off.process_batch(raw_off)
        assert len(res_off) == 1
        assert res_off[0].summary.startswith("Wire Digest: ")
        assert not _CJK_CHAR_RE.search(res_off[0].headline)
        assert not _CJK_CHAR_RE.search(res_off[0].summary)

    asyncio.run(_run())


def test_macro_commander_prompts_and_seed_normalization_english():
    assert not _CJK_CHAR_RE.search(DEFAULT_ACTIVE_HEADLINE)
    for h in ARTICLE_SECTION_HEADINGS:
        assert not _CJK_CHAR_RE.search(h)

    sys_p, usr_p = build_event_article_prompts({
        "source": "CoinDesk",
        "raw_title": "ETH breaks resistance",
        "headline": "ETH Breaks Key Resistance on Spot Volume",
        "summary": "Ethereum gained 4% on rising spot demand.",
        "raw_snippet": "Spot buying accelerated across major venues.",
    })
    assert "English" in sys_p and "English" in usr_p
    assert "Raw Snippet:" in usr_p
    assert not _CJK_CHAR_RE.search(sys_p)
    assert not _CJK_CHAR_RE.search(usr_p)

    async def _run():
        client = MagicMock()
        client.is_gateway_online = True
        client.model_commander = "gemini-3.1-flash-lite"
        client.chat_json = AsyncMock(return_value={
            "regime": "NORMAL",
            "directional_bias": "BIDIRECTIONAL",
            "risk_multiplier": 1.0,
            "active_headline": "測試中文標題不應出現",
            "confidence": 0.7,
        })
        cmd = MacroCommander(client)
        assert cmd.current_state.active_headline == DEFAULT_ACTIVE_HEADLINE

        ev = StructuredEvent(
            timestamp="2026-11-27T00:00:00Z",
            source="CoinDesk",
            domain="crypto",
            entities_tickers=["ETH"],
            urgency_score=6,
            sentiment_score=0.25,
            summary="Spot Ethereum ETF demand stays firm.",
            raw_title="ETH ETF demand stays firm",
            headline_zh="ETH ETF Demand Stays Firm",
        )
        await cmd.synthesize_regime([ev])
        cmd_sys = client.chat_json.await_args.kwargs["system_prompt"]
        assert "Traditional Chinese" not in cmd_sys
        assert "English" in cmd_sys
        # CJK active_headline from LLM is replaced by safe English default
        assert not _CJK_CHAR_RE.search(cmd.current_state.active_headline)

        # ensure_english_seed_events normalizes legacy CJK curated events
        cmd.curated_events[0]["headline"] = "舊版中文標題"
        cmd.curated_events[0]["summary"] = "舊版中文摘要"
        cmd.current_state.active_headline = "舊版中文總經標題"
        cmd.ensure_english_seed_events()
        assert not _CJK_CHAR_RE.search(cmd.curated_events[0]["headline"])
        assert not _CJK_CHAR_RE.search(cmd.curated_events[0]["summary"])
        assert not _CJK_CHAR_RE.search(cmd.current_state.active_headline)

    asyncio.run(_run())


def test_empty_view_model_evolve_labels_are_english():
    vm = _empty_view_model("")
    assert not _CJK_CHAR_RE.search(vm["next_evolve_sec_note"])
    assert not _CJK_CHAR_RE.search(vm["next_evolve_trades_label"])
    assert "Latest in" in vm["next_evolve_sec_note"]
    assert "trades left" in vm["next_evolve_trades_label"]
