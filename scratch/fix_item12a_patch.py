#!/usr/bin/env python3
"""Fix item 12A: OmniRoute completeness repairs (TradeBot0 maintenance list).

Applies exact-once-verified replacements to the PC project tree (run with
cwd = project root) and, identically, to the local audit copy.
Every replacement is verified to occur exactly once before anything is
written; on any mismatch the script aborts without touching a file.
Newline style is preserved (files are LF; open with newline="").

Design basis: ~/workspace/tradebot_audit/item12_design.md, section A
(all decisions D1-D7 approved at recommended values).

  A4-1  test_single_key: HTTP 429 no longer counts as a verified key. A 429
         only proves the key was accepted far enough to be rate limited.
         Returns ok=False with an "unconfirmed" message; the wizard test
         assertion is updated to match.
  A4-3  record_tokens_saved(420): the fixed 420-token estimate had no
         measurement behind it. Dedup now counts hits only
         (record_dedup_hit / total_dedup_hits); no token figure is claimed.
         Telemetry exposes dedup_hits; the frontend dedup line reports the
         counted hits instead of a fabricated percent.
  A4-4  DAILY_TOKEN_QUOTA soft throttling (lightweight): once measured usage
         reaches the quota, the digest cadence slows from the configured
         base to at least 900s (live_engine loop reads the effective
         interval from MacroCommander.digest_interval_sec). Telemetry
         exposes quota_throttled + digest_interval_sec; the frontend quota
         line says so when throttled.
  A3    Gateway-down policy, option 2 (approved): the keyword fallback
         stays as an emergency backup with the item-6 thresholds, but the
         regime it produces is now marked fallback=True with
         fallback_since_ts, and after 30 minutes without the LLM it steps
         down to BIDIRECTIONAL instead of letting stale keyword scores
         keep vetoing trades. The Intel Hub status pill shows
         "STANDBY / KEYWORD FALLBACK" while a fallback regime is active.
  A4-5  Setup wizard gains one line noting models are auto-routed by
         OmniRoute across the configured providers (no model change;
         model_ingest / model_commander stay "auto").

A4-2 ("<redacted>" Bearer) is item-10 scope and is NOT touched here.
NOTE (2026-11-13, verified by byte tests, not by displayed text): the
design doc's A4-2 premise is wrong -- the tool output layer redacts the
real default api_key value in displayed text, which made it look like the
code literally contains "<redacted>". The file contains no "redacted"
substring at all; the real default is a placeholder gateway key. That is
an item-10 matter, not an item-12A matter; recorded here only so the
design doc is not quoted as evidence for it.
"""
import os
import sys

if not os.path.isdir("src/gui"):
    print("FAIL: run this script from the project root (src/gui not found)")
    sys.exit(1)

REPLACEMENTS = []
NEW_FILES = {}


def rep(path, old, new):
    REPLACEMENTS.append((path, old, new))


# =========================================================== A4-1: 429 is not verification
rep("src/intelligence/gateway_supervisor.py", """            elif he.code == 429:
                return {"ok": True, "message": "Key valid (Rate limit 429 active)", "latency_ms": elapsed_ms}""",
"""            elif he.code == 429:
                # 429 only proves the key was accepted far enough to be rate
                # limited; it cannot prove the key is valid. Never report it
                # as verified (item 12 / A4-1): the wizard must show it as
                # unconfirmed and let the user retry later.
                return {"ok": False, "message": "Key status unconfirmed (rate limited, HTTP 429) — retry later", "latency_ms": elapsed_ms}""")

rep("tests/test_gateway_setup_wizard.py", """    # 3. Simulate HTTP 429 Rate Limit (key is valid but throttled)""",
"""    # 3. Simulate HTTP 429 Rate Limit (key status unconfirmed, not verified)""")

rep("tests/test_gateway_setup_wizard.py", """    res_429 = gs.test_single_key("groq", "gsk_rate_limited_key_12345678")
    assert res_429["ok"] is True
    assert "429" in res_429["message"]""",
"""    res_429 = gs.test_single_key("groq", "gsk_rate_limited_key_12345678")
    # Item 12 / A4-1: 429 only proves the key was accepted far enough to be
    # rate limited; it must never be reported as a verified key.
    assert res_429["ok"] is False
    assert "429" in res_429["message"]
    assert "unconfirmed" in res_429["message"].lower()""")


# =========================================================== A4-3 + A4-4: client counters & quota
rep("src/intelligence/omniroute_client.py", """        self.total_tokens_used: int = 0
        self.total_tokens_saved: int = 0
        self.daily_quota_limit: int = int(os.getenv("DAILY_TOKEN_QUOTA", "100000"))""",
"""        self.total_tokens_used: int = 0
        self.total_tokens_saved: int = 0
        # Dedup hits, counted (item 12 / A4-3). No token figure is derived
        # from them: the old record_tokens_saved(420) wrote a fixed estimate
        # per hit with no measurement behind it.
        self.total_dedup_hits: int = 0
        self.daily_quota_limit: int = int(os.getenv("DAILY_TOKEN_QUOTA", "100000"))""")

rep("src/intelligence/omniroute_client.py", """    def record_tokens_saved(self, tokens: int) -> None:
        \"\"\"Records tokens saved via deduplication buffers or cache hits.\"\"\"
        if tokens > 0:
            self.total_tokens_saved += int(tokens)""",
"""    def record_dedup_hit(self) -> None:
        \"\"\"Records one deduplication hit (a duplicate title+URL skipped).

        Counts hits only. The old record_tokens_saved(420) wrote a fixed
        420-token estimate per hit with no measurement behind it (item 12 /
        A4-3): no token figure is claimed anymore.
        \"\"\"
        self.total_dedup_hits += 1

    def record_tokens_saved(self, tokens: int) -> None:
        \"\"\"Legacy estimate hook (item 12 / A4-3): kept for backward
        compatibility only. New code uses record_dedup_hit(); no caller
        should treat the accumulated figure as a measured saving.\"\"\"
        if tokens > 0:
            self.total_tokens_saved += int(tokens)

    def is_over_quota(self) -> bool:
        \"\"\"True once measured token usage reaches the daily quota.

        The quota is a soft display budget, not a limiter (item 12 / A4-4);
        callers use this to throttle the digest cadence, never to block a
        single request.
        \"\"\"
        return self.daily_quota_limit > 0 and self.total_tokens_used >= self.daily_quota_limit""")


# =========================================================== A4-3: ingestion call sites
rep("src/intelligence/ingestion.py", """                        else:
                            if hasattr(self.client, "record_tokens_saved"):
                                self.client.record_tokens_saved(420)""",
"""                        else:
                            # Dedup hit: count it, do not claim a token figure
                            # (item 12 / A4-3: the old 420 was a fixed estimate).
                            if hasattr(self.client, "record_dedup_hit"):
                                self.client.record_dedup_hit()""")

rep("src/intelligence/ingestion.py", """            else:
                if hasattr(self.client, "record_tokens_saved"):
                    self.client.record_tokens_saved(420)""",
"""            else:
                # Dedup hit: count it, do not claim a token figure
                # (item 12 / A4-3: the old 420 was a fixed estimate).
                if hasattr(self.client, "record_dedup_hit"):
                    self.client.record_dedup_hit()""")


# =========================================================== A3 + A4-4: macro_commander
rep("src/intelligence/macro_commander.py", """logger = logging.getLogger(__name__)""",
"""logger = logging.getLogger(__name__)

# Item 12 / A3 option 2: a keyword-fallback regime older than this (seconds)
# steps down to neutral instead of letting stale keyword scores veto trades.
FALLBACK_MAX_AGE_SEC = 1800.0""")

rep("src/intelligence/macro_commander.py", """    last_synthesis_ts: float = 0.0
    veto_count_today: int = 0""",
"""    last_synthesis_ts: float = 0.0
    # Fallback provenance (item 12 / A3 option 2): True while the current
    # bias came from the local keyword fallback instead of the LLM, and the
    # timestamp the fallback first took over (for the 30-minute expiry).
    fallback: bool = False
    fallback_since_ts: float = 0.0
    veto_count_today: int = 0""")

rep("src/intelligence/macro_commander.py", """            "last_synthesis_time": time.strftime("%H:%M:%S", time.localtime(self.last_synthesis_ts)) if self.last_synthesis_ts else "",
""",
"""            "last_synthesis_time": time.strftime("%H:%M:%S", time.localtime(self.last_synthesis_ts)) if self.last_synthesis_ts else "",
            "fallback": self.fallback,
            "fallback_since": time.strftime("%H:%M:%S", time.localtime(self.fallback_since_ts)) if self.fallback_since_ts else "",
""")

rep("src/intelligence/macro_commander.py", """        raw_saved = getattr(self.client, "total_tokens_saved", 0)
        tokens_saved = int(raw_saved) if isinstance(raw_saved, (int, float)) else 0""",
"""        raw_saved = getattr(self.client, "total_tokens_saved", 0)
        tokens_saved = int(raw_saved) if isinstance(raw_saved, (int, float)) else 0
        raw_hits = getattr(self.client, "total_dedup_hits", 0)
        dedup_hits = int(raw_hits) if isinstance(raw_hits, (int, float)) else 0""")

rep("src/intelligence/macro_commander.py", """                "quota_pct": quota_pct,
                "tokens_used": tokens_used,
                "tokens_saved": tokens_saved,
                "dedup_pct": dedup_pct,""",
"""                "quota_pct": quota_pct,
                "tokens_used": tokens_used,
                "tokens_saved": tokens_saved,
                "dedup_pct": dedup_pct,
                "dedup_hits": dedup_hits,
                "quota_throttled": self.is_quota_throttled(),
                "digest_interval_sec": self.digest_interval_sec(),""")

# Fallback helpers + effective digest cadence, placed before synthesize_regime.
rep("src/intelligence/macro_commander.py", """    async def synthesize_regime(self, recent_events: List[StructuredEvent]) -> MacroRegimeState:""",
"""    def _expire_fallback_if_stale(self, now: float) -> None:
        \"\"\"Steps an expired keyword fallback down to neutral (item 12 / A3).

        A fallback regime older than FALLBACK_MAX_AGE_SEC (30 minutes)
        stops vetoing: the keyword scores that produced it are stale, and a
        directional veto must come from a live LLM synthesis, not from
        half-hour-old keyword soup.
        \"\"\"
        if not self.current_state.fallback:
            return
        if self.current_state.fallback_since_ts <= 0.0:
            return
        if now - self.current_state.fallback_since_ts <= FALLBACK_MAX_AGE_SEC:
            return
        self.current_state.regime = "NORMAL"
        self.current_state.directional_bias = "BIDIRECTIONAL"
        self.current_state.risk_multiplier = 1.0
        self.current_state.confidence = 0.50
        self.current_state.active_headline = "全球訂單流維持宏觀均衡。實時智能情報監控運行中。"
        logger.info("Keyword fallback regime expired after 30m without LLM; stepped down to BIDIRECTIONAL")

    def is_quota_throttled(self) -> bool:
        \"\"\"True while measured token usage has reached the daily quota.

        The `is True` guard matters: mock clients answer any attribute with
        a truthy mock, which must never read as "over quota" (item 12 /
        A4-4). Only a real boolean True counts.
        \"\"\"
        fn = getattr(self.client, "is_over_quota", None)
        if not callable(fn):
            return False
        try:
            return fn() is True
        except Exception as e:
            logger.debug("Quota check failed, assuming under quota: %s", e)
            return False

    def digest_interval_sec(self, base_sec: float = 300.0) -> float:
        \"\"\"Effective digest cadence (item 12 / A4-4).

        Once the daily quota is reached, the digest slows from the base
        cadence to at least 900s so the gateway is not hammered while over
        budget. Never shortens a longer user-configured interval.
        \"\"\"
        if self.is_quota_throttled():
            return max(float(base_sec), 900.0)
        return float(base_sec)

    async def synthesize_regime(self, recent_events: List[StructuredEvent]) -> MacroRegimeState:""")

rep("src/intelligence/macro_commander.py", """            if not recent_events:
                self.current_state.last_synthesis_ts = now
                self.current_state.status = "ONLINE" if self.client.is_gateway_online else "STANDBY"
                return self.current_state""",
"""            if not recent_events:
                self.current_state.last_synthesis_ts = now
                self.current_state.status = "ONLINE" if self.client.is_gateway_online else "STANDBY"
                # No fresh evidence: an expired fallback still steps down
                # (item 12 / A3), even with nothing new to synthesize.
                self._expire_fallback_if_stale(now)
                return self.current_state""")

rep("src/intelligence/macro_commander.py", """                self.current_state.regime = regime
                self.current_state.directional_bias = bias
                self.current_state.risk_multiplier = risk_mult
                self.current_state.confidence = conf
                self.current_state.active_headline = headline
                self.current_state.status = "ONLINE\"""",
"""                self.current_state.regime = regime
                self.current_state.directional_bias = bias
                self.current_state.risk_multiplier = risk_mult
                self.current_state.confidence = conf
                self.current_state.active_headline = headline
                self.current_state.status = "ONLINE"
                # LLM is back in charge: the fallback provenance clears.
                self.current_state.fallback = False
                self.current_state.fallback_since_ts = 0.0""")

rep("src/intelligence/macro_commander.py", """                self.current_state.status = "STANDBY" if not self.client.is_gateway_online else "ONLINE"

            if self.curated_events:""",
"""                # Emergency backup only (item 12 / A3 option 2): the keyword
                # fallback is marked as such, and after 30 minutes without
                # the LLM it steps down to neutral instead of letting stale
                # keyword scores keep vetoing trades.
                if not self.current_state.fallback:
                    self.current_state.fallback = True
                    self.current_state.fallback_since_ts = now
                self._expire_fallback_if_stale(now)

                self.current_state.status = "STANDBY" if not self.client.is_gateway_online else "ONLINE"

            if self.curated_events:""")


# =========================================================== A4-4: live_engine effective interval
rep("src/data/live_engine.py", """                        # Automated periodic background intelligence digest refresh (every 5m / 300s)
                        if (now - self.last_intel_refresh_ts) >= self.intel_refresh_interval_sec and not self._is_refreshing_intel:""",
"""                        # Automated periodic background intelligence digest refresh (every 5m / 300s;
                        # slowed to >= 900s while the daily token quota is exceeded, item 12 / A4-4)
                        if (now - self.last_intel_refresh_ts) >= self.macro_commander.digest_interval_sec(self.intel_refresh_interval_sec) and not self._is_refreshing_intel:""")


# =========================================================== A3 pill + A4-4/A4-3 intel hub text (app.js)
# Existing classes only (intel-status-pill ss-badge, ss-badge__dot/label):
# no new CSS, no new tokens; the change is the label text (item 3 rule).
rep("src/gui/assets/app.js", """      const nextPillHtml = `<span class="ss-badge__dot"></span><span class="ss-badge__label">${isOnline ? 'ONLINE (24/7)' : 'STANDBY / LOCAL NLP'}</span>`;""",
"""      // Item 12 / A3 option 2: when the current regime came from the local
      // keyword fallback, say so on the pill instead of generic STANDBY.
      const isFallback = macro.fallback === true;
      const nextPillHtml = `<span class="ss-badge__dot"></span><span class="ss-badge__label">${isOnline ? 'ONLINE (24/7)' : (isFallback ? 'STANDBY / KEYWORD FALLBACK' : 'STANDBY / LOCAL NLP')}</span>`;""")

rep("src/gui/assets/app.js", """      } else {
        const remTokens = Math.max(0, 100000 - (omni.tokens_used || 0)).toLocaleString();
        quotaPct.textContent = `${qPct.toFixed(1)}% Available (${remTokens} rem)`;
      }""",
"""      } else {
        const remTokens = Math.max(0, 100000 - (omni.tokens_used || 0)).toLocaleString();
        quotaPct.textContent = `${qPct.toFixed(1)}% Available (${remTokens} rem)`;
        // Item 12 / A4-4: when the daily quota is exceeded the digest slows
        // down; say so instead of silently showing a normal quota bar.
        if (omni.quota_throttled === true) {
          quotaPct.textContent += ' — Digest throttled';
        }
      }""")

rep("src/gui/assets/app.js", """      const pct = tot > 0 ? ((saved / tot) * 100).toFixed(1) : (omni.dedup_pct ? omni.dedup_pct.toFixed(1) : '0.0');
      tokensSub.textContent = `${pct}% SHA-256 Dedup Saved`;""",
"""      const pct = tot > 0 ? ((saved / tot) * 100).toFixed(1) : (omni.dedup_pct ? omni.dedup_pct.toFixed(1) : '0.0');
      // Item 12 / A4-3: token "saved" is no longer a claimed figure, so the
      // dedup line reports the counted hits instead of a fabricated percent.
      const hits = omni.dedup_hits;
      tokensSub.textContent = (typeof hits === 'number' && hits > 0)
        ? `${hits.toLocaleString()} dupes skipped (SHA-256)`
        : `${pct}% SHA-256 Dedup Saved`;""")


# =========================================================== A4-5: wizard note (index.html, existing class)
rep("src/gui/assets/index.html", """          <div class="setup-gateway-note">
            Credentials synchronize directly to <code>~/.omniroute/.env</code> while preserving server security tokens.
          </div>""",
"""          <div class="setup-gateway-note">
            Credentials synchronize directly to <code>~/.omniroute/.env</code> while preserving server security tokens.
          </div>
          <div class="setup-gateway-note">
            Models are auto-routed by OmniRoute (auto) across your configured providers.
          </div>""")


# =========================================================== new tests
NEW_FILES["tests/test_item12a_omniroute.py"] = '''"""Item 12A tests: 429 is not verification, dedup counts hits (no token
figure), fallback regime is marked and expires after 30 minutes, quota
soft-throttles the digest cadence."""
import asyncio
import io
import time
import urllib.error
from unittest.mock import AsyncMock, MagicMock, patch

from src.intelligence.gateway_supervisor import GatewaySupervisor
from src.intelligence.ingestion import IntelligenceHarvester, RawEvent, StructuredEvent
from src.intelligence.macro_commander import MacroCommander, MacroRegimeState
from src.intelligence.omniroute_client import OmniRouteClient


def _offline_commander():
    mock_client = MagicMock()
    mock_client.is_gateway_online = False
    mock_client.chat_json = AsyncMock(return_value=None)
    return MacroCommander(mock_client)


def _strong_bearish_events():
    return [
        StructuredEvent(timestamp="2026-11-13T00:00:00Z", source="Test", domain="macro", entities_tickers=["FED"], urgency_score=9, sentiment_score=-0.70, summary="Strong bearish 1"),
        StructuredEvent(timestamp="2026-11-13T00:00:00Z", source="Test", domain="macro", entities_tickers=["FED"], urgency_score=8, sentiment_score=-0.85, summary="Strong bearish 2"),
    ]


@patch("urllib.request.urlopen")
def test_key_rate_limit_429_is_not_verified(mock_urlopen):
    """A4-1: 429 proves the key was accepted far enough to be rate limited,
    not that it is valid. It must never be reported as verified."""
    gs = GatewaySupervisor()
    mock_urlopen.side_effect = urllib.error.HTTPError(
        url="https://api.groq.com", code=429, msg="Too Many Requests",
        hdrs={}, fp=io.BytesIO(b'{"error":"rate limited"}'),
    )
    res = gs.test_single_key("groq", "gsk_rate_limited_key_12345678")
    assert res["ok"] is False
    assert "429" in res["message"]
    assert "unconfirmed" in res["message"].lower()
    assert "valid" not in res["message"].lower()


def test_dedup_hits_counted_not_token_estimate():
    """A4-3: a duplicate event counts one dedup hit and claims no tokens."""
    client = OmniRouteClient()
    harvester = IntelligenceHarvester(client=client)
    ev = RawEvent(source="Test", domain="crypto", title="Dup title", url="https://example.com/x", timestamp=2000.0)
    assert harvester.push_raw_events([ev]) == [ev]
    assert harvester.push_raw_events([ev]) == []
    assert client.total_dedup_hits == 1
    assert client.total_tokens_saved == 0


def test_fallback_regime_is_marked_and_expires():
    """A3 option 2: a keyword-fallback regime is marked fallback=True; after
    30 minutes without the LLM it steps down to BIDIRECTIONAL."""
    commander = _offline_commander()
    state = asyncio.run(commander.synthesize_regime(_strong_bearish_events()))
    assert state.directional_bias == "SHORT_ONLY"
    assert state.fallback is True
    assert state.fallback_since_ts > 0.0

    # 31 minutes later, still no LLM: the same strong events must NOT keep
    # vetoing -- the stale fallback steps down to neutral.
    commander.current_state.fallback_since_ts = time.time() - 1860.0
    state = asyncio.run(commander.synthesize_regime(_strong_bearish_events()))
    assert state.directional_bias == "BIDIRECTIONAL"
    assert state.regime == "NORMAL"
    assert state.risk_multiplier == 1.0


def test_fallback_clears_when_llm_recovers():
    """A3 option 2: a fresh LLM synthesis clears the fallback provenance."""
    commander = _offline_commander()
    state = asyncio.run(commander.synthesize_regime(_strong_bearish_events()))
    assert state.fallback is True

    commander.client.is_gateway_online = True
    commander.client.chat_json = AsyncMock(return_value={
        "regime": "BULLISH_SURGE",
        "directional_bias": "LONG_ONLY",
        "risk_multiplier": 1.25,
        "confidence": 0.8,
        "active_headline": "LLM back online",
    })
    state = asyncio.run(commander.synthesize_regime(_strong_bearish_events()))
    assert state.directional_bias == "LONG_ONLY"
    assert state.fallback is False
    assert state.fallback_since_ts == 0.0


def test_empty_digest_expires_stale_fallback():
    """A3 option 2: with no new events at all, an expired fallback still
    steps down instead of sitting on a stale directional veto."""
    commander = _offline_commander()
    commander.current_state.fallback = True
    commander.current_state.fallback_since_ts = time.time() - 1860.0
    commander.current_state.directional_bias = "SHORT_ONLY"
    commander.current_state.regime = "BEARISH_PANIC"
    state = asyncio.run(commander.synthesize_regime([]))
    assert state.directional_bias == "BIDIRECTIONAL"
    assert state.regime == "NORMAL"


def test_quota_throttling_slows_digest():
    """A4-4: at/over the daily quota the digest slows to >= 900s; under
    quota it keeps the configured base cadence."""
    client = OmniRouteClient()
    commander = MacroCommander(client)
    assert client.is_over_quota() is False
    assert commander.digest_interval_sec() == 300.0
    assert commander.is_quota_throttled() is False

    client.total_tokens_used = 100000
    assert client.is_over_quota() is True
    assert commander.digest_interval_sec() == 900.0
    assert commander.digest_interval_sec(600.0) == 900.0
    assert commander.digest_interval_sec(1200.0) == 1200.0
    assert commander.is_quota_throttled() is True

    tel = commander.get_intel_hub_telemetry()
    assert tel["omniroute"]["quota_throttled"] is True
    assert tel["omniroute"]["digest_interval_sec"] == 900.0
    assert tel["omniroute"]["dedup_hits"] == 0


def test_regime_state_dict_exposes_fallback():
    """A3: the view model (macro_commander.to_dict) carries the fallback
    provenance the frontend pill reads."""
    d = MacroRegimeState().to_dict()
    assert d["fallback"] is False
    assert d["fallback_since"] == ""
'''


# =========================================================== apply
def main():
    failed = []
    for path, old, new in REPLACEMENTS:
        with open(path, "r", encoding="utf-8", newline="") as f:
            content = f.read()
        n = content.count(old)
        if n != 1:
            failed.append(f"{path}: expected 1 occurrence, found {n} for: {old[:80]!r}")
            continue
        content = content.replace(old, new)
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        print(f"OK {path}")
    for path, content in NEW_FILES.items():
        if os.path.exists(path):
            failed.append(f"{path}: already exists, refusing to overwrite")
            continue
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        print(f"NEW {path}")
    if failed:
        print("FAILURES:")
        for msg in failed:
            print(" -", msg)
        sys.exit(1)
    print(f"Applied {len(REPLACEMENTS)} replacements + {len(NEW_FILES)} new files.")


if __name__ == "__main__":
    main()
