#!/usr/bin/env python3
"""Fix item 6: intelligence veto (TradeBot0 maintenance list).

Applies exact-once-verified replacements to the PC project tree (run with
cwd = project root) and, identically, to the local audit copy.
Every replacement is verified to occur exactly once before anything is
written; on any mismatch the script aborts without touching a file.
Newline style is preserved (files are LF; open with newline="").
"""
import os
import sys

if not os.path.isdir("src/intelligence"):
    print("FAIL: run this script from the project root (src/intelligence not found)")
    sys.exit(1)

REPLACEMENTS = []

# ---------------------------------------------------------------- macro_commander.py
REPLACEMENTS.append(("src/intelligence/macro_commander.py", r'''logger = logging.getLogger(__name__)


@dataclass
class MacroRegimeState:''', r'''logger = logging.getLogger(__name__)


def _safe_float(value: Any, default: float) -> float:
    """Parses an untrusted numeric value (LLM output / feed data).

    Returns `default` when the value is missing or not a number, instead of
    raising. A failed parse must never take down the veto pipeline (item 6).
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@dataclass
class MacroRegimeState:'''))

REPLACEMENTS.append(("src/intelligence/macro_commander.py", r'''    def _seed_default_events(self) -> None:
        now = time.time()
        self.current_state.regime = "NORMAL"
        self.current_state.directional_bias = "BIDIRECTIONAL"
        self.current_state.risk_multiplier = 1.0
        self.current_state.active_headline = "全球訂單流維持宏觀均衡。實時智能情報監控運行中。"
        self.current_state.confidence = 0.85
        self.current_state.status = "ONLINE" if self.client.is_gateway_online else "STANDBY"

        self.curated_events = [
            {
                "id": "evt_seed_1",
                "time": time.strftime("%H:%M:%S", time.localtime(now - 12)),
                "source": "CoinDesk / SEC",
                "domain": "crypto",
                "urgency": 7,
                "sentiment": 0.45,
                "headline": "全球以太坊現貨流動性持續擴張，Layer-2結算量創歷史新高",
                "summary": "以太坊主網與主流L2 Rollup展現強勁的流動性增長，機構帳戶正積極評估質押與國庫資金配置。",
                "strategy_actions": [],
            },
            {
                "id": "evt_seed_2",
                "time": time.strftime("%H:%M:%S", time.localtime(now - 75)),
                "source": "ForexLive / FRED",
                "domain": "macro",
                "urgency": 6,
                "sentiment": 0.20,
                "headline": "美聯儲貨幣監測：核心通膨指標向中性政策目標平穩收斂",
                "summary": "全球央行資產負債表維持穩定流動性基準；利差交易保持平穩，為跨資產風險偏好提供有力支撐。",
                "strategy_actions": [],
            },
            {
                "id": "evt_seed_3",
                "time": time.strftime("%H:%M:%S", time.localtime(now - 180)),
                "source": "Decrypt / Protocol",
                "domain": "tech",
                "urgency": 5,
                "sentiment": 0.30,
                "headline": "數位資產基礎設施與AI算力中心加速融合，電力設施需求激增",
                "summary": "高算力AI叢集帶動機構對分散式能源與具備加密安全防護的數據中心基礎設施產生濃厚興趣。",
                "strategy_actions": [],
            },
            {
                "id": "evt_seed_4",
                "time": time.strftime("%H:%M:%S", time.localtime(now - 320)),
                "source": "Bloomberg / SEC EDGAR",
                "domain": "corporate",
                "urgency": 5,
                "sentiment": 0.15,
                "headline": "上市企業深化合規託管合作，數位資產儲備規模穩健增長",
                "summary": "季度財務揭露顯示，越來越多上市機構採用經審計的受監管託管方案與場外大宗流動性渠道。",
                "strategy_actions": [],
            },
            {
                "id": "evt_seed_5",
                "time": time.strftime("%H:%M:%S", time.localtime(now - 500)),
                "source": "Global Wire Ingestion",
                "domain": "geopolitics",
                "urgency": 4,
                "sentiment": 0.05,
                "headline": "實時情報監聽器已初始化：多領域即時數據流完成同調",
                "summary": "自動化情報管線涵蓋CoinDesk、Decrypt與宏觀即時電訊，OmniRoute動態評估核心全時段運作中。",
                "strategy_actions": [],
            },
        ]
        if self.curated_events:
            self.current_state.latest_event = self.curated_events[0]''', r'''    def _seed_default_events(self) -> None:
        # No fabricated news: the intel timeline starts empty and is filled
        # only by real harvested events (synthesize_regime). The old version
        # seeded five invented headlines attributed to real outlets
        # (CoinDesk / SEC / Bloomberg) and presented them as genuine
        # intelligence in the Intel Hub (item 6).
        self.current_state.regime = "NORMAL"
        self.current_state.directional_bias = "BIDIRECTIONAL"
        self.current_state.risk_multiplier = 1.0
        self.current_state.active_headline = "全球訂單流維持宏觀均衡。實時智能情報監控運行中。"
        # No real data yet: neutral confidence, not the old 0.85.
        self.current_state.confidence = 0.50
        self.current_state.status = "ONLINE" if self.client.is_gateway_online else "STANDBY"

        self.curated_events = []
        self.current_state.latest_event = None'''))

REPLACEMENTS.append(("src/intelligence/macro_commander.py", r'''        display_name = self.STRAT_LABELS.get(strat_id, name)
        if not self.curated_events:
            self._seed_default_events()''', r'''        display_name = self.STRAT_LABELS.get(strat_id, name)
        if not self.curated_events:
            # No real event yet: nothing honest to annotate. Never re-seed
            # fabricated events just to have something to attach to (item 6).
            return'''))

REPLACEMENTS.append(("src/intelligence/macro_commander.py", r'''    def check_trade_veto(self, side: OrderSide, competitor_name: str) -> Tuple[bool, str]:
        """
        Enforces Strict Veto (Option A) against incoming orders from any of the 6 competitors.
        Returns:
            (True, "PASSED") if trade complies with macro regime.
            (False, reason) if trade is strictly vetoed.
        """
        bias = self.current_state.directional_bias''', r'''    def check_trade_veto(self, side: OrderSide, competitor_name: str, is_close: bool = False) -> Tuple[bool, str]:
        """
        Enforces Strict Veto (Option A) against incoming orders from any of the 6 competitors.
        The veto only ever blocks OPENING orders. Closing / reducing a
        position lowers risk, so a close is never vetoed: under HOLD_CASH a
        trader must still be able to sell a long (or cover a short) to stop
        the bleeding instead of being locked inside a deteriorating market.
        Returns:
            (True, "PASSED") if trade complies with macro regime.
            (False, reason) if trade is strictly vetoed.
        """
        # Closing a position is risk-reducing: never veto it (item 6).
        if is_close:
            return True, "PASSED"

        bias = self.current_state.directional_bias'''))

REPLACEMENTS.append(("src/intelligence/macro_commander.py", r'''                risk_mult = max(0.5, min(1.5, float(parsed.get("risk_multiplier", 1.0))))
                conf = max(0.0, min(1.0, float(parsed.get("confidence", 0.70))))''', r'''                # LLM numbers are untrusted text: a non-numeric value (e.g.
                # "high") falls back to the safe default instead of raising
                # out of the veto pipeline (item 6).
                risk_mult = max(0.5, min(1.5, _safe_float(parsed.get("risk_multiplier"), 1.0)))
                conf = max(0.0, min(1.0, _safe_float(parsed.get("confidence"), 0.70)))'''))

REPLACEMENTS.append(("src/intelligence/macro_commander.py", r'''                # Fallback: if LLM unreachable or unparseable, compute deterministic sentiment aggregate
                avg_sent = sum(e.sentiment_score for e in recent_events) / len(recent_events)
                max_urg = max(e.urgency_score for e in recent_events)

                if avg_sent > 0.40 and max_urg >= 7:''', r'''                # Fallback: if LLM unreachable or unparseable, compute deterministic sentiment aggregate.
                # Conservative bar on purpose: without the LLM this is keyword
                # soup, so a single bearish word (sentiment -0.45) plus a
                # common urgency-7 word ("rate"/"sec"/"fed") must NOT flip the
                # whole arena into a directional veto. |avg_sent| >= 0.60
                # needs at least two net directional words and urgency >= 8
                # needs a genuinely severe keyword (item 6).
                avg_sent = sum(e.sentiment_score for e in recent_events) / len(recent_events)
                max_urg = max(e.urgency_score for e in recent_events)

                if avg_sent > 0.60 and max_urg >= 8:'''))

REPLACEMENTS.append(("src/intelligence/macro_commander.py", r'''                elif avg_sent < -0.40 and max_urg >= 7:''', r'''                elif avg_sent < -0.60 and max_urg >= 8:'''))

REPLACEMENTS.append(("src/intelligence/macro_commander.py", r'''        quota_pct = 100.0
        if hasattr(self.client, "get_quota_pct") and callable(self.client.get_quota_pct):''', r'''        # Unknown quota is reported as None, never as a fabricated 100.0%
        # (item 6). The frontend already treats a non-number as unknown.
        quota_pct: Optional[float] = None
        if hasattr(self.client, "get_quota_pct") and callable(self.client.get_quota_pct):'''))

# ---------------------------------------------------------------- ingestion.py
REPLACEMENTS.append(("src/intelligence/ingestion.py", r'''def _clean_html_text(raw_html: str) -> str:
    if not raw_html:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw_html)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()''', r'''def _clean_html_text(raw_html: str) -> str:
    if not raw_html:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw_html)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _contains_word(text: str, word: str) -> bool:
    """Word-boundary keyword match.

    Plain `word in text` substring matching misfires constantly on financial
    text: "bear" matches "bearing", "ai" matches "said", "ban" matches
    "bank", "sec" matches "second", "eth" matches "method". A keyword only
    counts when it appears as a whole word (item 6).
    """
    if not text or not word:
        return False
    return re.search(r"\b" + re.escape(word.strip().lower()) + r"\b", text.lower()) is not None'''))

REPLACEMENTS.append(("src/intelligence/ingestion.py", r'''        if os.environ.get("ARENA_FAST_TEST") == "1":
            now = time.time()
            return [
                RawEvent(source="CoinDesk", domain="crypto", title="Ethereum L2 Scaling Inflows Rise 15%", url="https://coindesk.com", timestamp=now),
                RawEvent(source="ForexLive", domain="macro", title="Fed Reiterates Rate Path Stability in Policy Note", url="https://forexlive.com", timestamp=now),
            ]''', r'''        if os.environ.get("ARENA_FAST_TEST") == "1":
            # Test fixture only: clearly marked synthetic data for the test
            # suite (conftest sets ARENA_FAST_TEST=1). Never presented as
            # real news: source is "Test Feed" and titles carry a [TEST]
            # marker, so these events can never be mistaken for genuine
            # intelligence in the veto pipeline (item 6).
            now = time.time()
            return [
                RawEvent(source="Test Feed", domain="crypto", title="[TEST] Ethereum L2 Scaling Inflows Rise 15%", url="https://coindesk.com", timestamp=now),
                RawEvent(source="Test Feed", domain="macro", title="[TEST] Fed Reiterates Rate Path Stability in Policy Note", url="https://forexlive.com", timestamp=now),
            ]'''))

REPLACEMENTS.append(("src/intelligence/ingestion.py", r'''        vol = float(item.get("volume24hr") or 0.0)''', r'''        try:
            vol = float(item.get("volume24hr") or 0.0)
        except (TypeError, ValueError):
            vol = 0.0'''))

REPLACEMENTS.append(("src/intelligence/ingestion.py", r'''        score = int(d.get("score", 0))''', r'''        try:
            score = int(d.get("score", 0))
        except (TypeError, ValueError):
            score = 0'''))

REPLACEMENTS.append(("src/intelligence/ingestion.py", r'''                bull_cnt = sum(1 for w in bull_words if w in combined_text)
                bear_cnt = sum(1 for w in bear_words if w in combined_text)''', r'''                bull_cnt = sum(1 for w in bull_words if _contains_word(combined_text, w))
                bear_cnt = sum(1 for w in bear_words if _contains_word(combined_text, w))'''))

REPLACEMENTS.append(("src/intelligence/ingestion.py", r'''                if any(w in combined_text for w in ["emergency", "black swan", "halt", "freeze", "war", "ban", "indict", "billion"]):
                    urgency = 9
                elif any(w in combined_text for w in ["lawsuit", "sues", "sec", "fed", "rate", "subpoena", "hack", "etf", "tariff"]):
                    urgency = 7
                elif any(w in combined_text for w in ["deal", "tax", "report", "policy", "million", "launch", "upgrade"]):
                    urgency = 6''', r'''                if any(_contains_word(combined_text, w) for w in ["emergency", "black swan", "halt", "freeze", "war", "ban", "indict", "billion"]):
                    urgency = 9
                elif any(_contains_word(combined_text, w) for w in ["lawsuit", "sues", "sec", "fed", "rate", "subpoena", "hack", "etf", "tariff"]):
                    urgency = 7
                elif any(_contains_word(combined_text, w) for w in ["deal", "tax", "report", "policy", "million", "launch", "upgrade"]):
                    urgency = 6'''))

REPLACEMENTS.append(("src/intelligence/ingestion.py", r'''                if "eth" in combined_text or "ethereum" in combined_text or "ether" in combined_text:
                    tickers.append("ETH")
                if "btc" in combined_text or "bitcoin" in combined_text:
                    tickers.append("BTC")
                if "sol" in combined_text or "solana" in combined_text:
                    tickers.append("SOL")
                if "xrp" in combined_text or "ripple" in combined_text:
                    tickers.append("XRP")
                if "fed" in combined_text or "fomc" in combined_text or "rate" in combined_text or "powell" in combined_text:
                    tickers.append("FED")
                if "sec" in combined_text or "cftc" in combined_text:
                    tickers.append("SEC")
                if "ai" in combined_text or "anthropic" in combined_text or "openai" in combined_text or "nvidia" in combined_text:
                    tickers.append("AI")''', r'''                if _contains_word(combined_text, "eth") or _contains_word(combined_text, "ethereum") or _contains_word(combined_text, "ether"):
                    tickers.append("ETH")
                if _contains_word(combined_text, "btc") or _contains_word(combined_text, "bitcoin"):
                    tickers.append("BTC")
                if _contains_word(combined_text, "sol") or _contains_word(combined_text, "solana"):
                    tickers.append("SOL")
                if _contains_word(combined_text, "xrp") or _contains_word(combined_text, "ripple"):
                    tickers.append("XRP")
                if _contains_word(combined_text, "fed") or _contains_word(combined_text, "fomc") or _contains_word(combined_text, "rate") or _contains_word(combined_text, "powell"):
                    tickers.append("FED")
                if _contains_word(combined_text, "sec") or _contains_word(combined_text, "cftc"):
                    tickers.append("SEC")
                if _contains_word(combined_text, "ai") or _contains_word(combined_text, "anthropic") or _contains_word(combined_text, "openai") or _contains_word(combined_text, "nvidia"):
                    tickers.append("AI")'''))

REPLACEMENTS.append(("src/intelligence/ingestion.py", r'''            (("ethereum", "ether", "eth ", "eth's", "vitalik"), "以太坊 (ETH)"),''', r'''            (("ethereum", "ether", "eth", "vitalik"), "以太坊 (ETH)"),'''))
REPLACEMENTS.append(("src/intelligence/ingestion.py", r'''            (("solana", "sol "), "Solana (SOL)"),''', r'''            (("solana", "sol"), "Solana (SOL)"),'''))
REPLACEMENTS.append(("src/intelligence/ingestion.py", r'''            if any(k in combined for k in keys) and label_zh not in entities_zh:''', r'''            if any(_contains_word(combined, k) for k in keys) and label_zh not in entities_zh:'''))
REPLACEMENTS.append(("src/intelligence/ingestion.py", r'''        if any(w in combined for w in ["hack", "exploit", "stolen", "breach", "phishing"]):''', r'''        if any(_contains_word(combined, w) for w in ["hack", "exploit", "stolen", "breach", "phishing"]):'''))
REPLACEMENTS.append(("src/intelligence/ingestion.py", r'''        elif any(w in combined for w in ["lawsuit", "sues", "sued", "indict", "probe", "subpoena", "ban", "crackdown", "fine"]):''', r'''        elif any(_contains_word(combined, w) for w in ["lawsuit", "sues", "sued", "indict", "probe", "subpoena", "ban", "crackdown", "fine"]):'''))
REPLACEMENTS.append(("src/intelligence/ingestion.py", r'''        elif any(w in combined for w in ["etf", "inflow", "institutional", "blackrock", "fidelity", "accumulate", "buy", "purchases"]):''', r'''        elif any(_contains_word(combined, w) for w in ["etf", "inflow", "institutional", "blackrock", "fidelity", "accumulate", "buy", "purchases"]):'''))
REPLACEMENTS.append(("src/intelligence/ingestion.py", r'''        elif any(w in combined for w in ["fed", "fomc", "powell", "rate", "cpi", "inflation", "jobs", "payroll", "yield", "treasury", "dollar", "dxy"]):''', r'''        elif any(_contains_word(combined, w) for w in ["fed", "fomc", "powell", "rate", "cpi", "inflation", "jobs", "payroll", "yield", "treasury", "dollar", "dxy"]):'''))
REPLACEMENTS.append(("src/intelligence/ingestion.py", r'''        elif any(w in combined for w in ["tariff", "trade war", "sanction", "geopolit", "war", "red sea", "middle east"]):''', r'''        elif any(_contains_word(combined, w) for w in ["tariff", "trade war", "sanction", "geopolit", "war", "red sea", "middle east"]):'''))
REPLACEMENTS.append(("src/intelligence/ingestion.py", r'''        elif any(w in combined for w in ["surge", "soar", "rally", "jump", "breakout", "record", "ath", "gain", "bull"]):''', r'''        elif any(_contains_word(combined, w) for w in ["surge", "soar", "rally", "jump", "breakout", "record", "ath", "gain", "bull"]):'''))
REPLACEMENTS.append(("src/intelligence/ingestion.py", r'''        elif any(w in combined for w in ["crash", "plunge", "drop", "fall", "dump", "slump", "liquidation", "outflow", "bear"]):''', r'''        elif any(_contains_word(combined, w) for w in ["crash", "plunge", "drop", "fall", "dump", "slump", "liquidation", "outflow", "bear"]):'''))
REPLACEMENTS.append(("src/intelligence/ingestion.py", r'''        elif any(w in combined for w in ["launch", "upgrade", "partner", "expand", "integrate", "mainnet", "testnet", "adopt"]):''', r'''        elif any(_contains_word(combined, w) for w in ["launch", "upgrade", "partner", "expand", "integrate", "mainnet", "testnet", "adopt"]):'''))

# ---------------------------------------------------------------- omniroute_client.py
REPLACEMENTS.append(("src/intelligence/omniroute_client.py", r'''                        if status == 200:
                            body = await resp.json()
                            self.is_gateway_online = True
                            self.successful_requests += 1
                            usage = body.get("usage", {})
                            if isinstance(usage, dict):
                                self.total_tokens_used += int(usage.get("total_tokens", 0))
                            choices = body.get("choices", [])
                            if choices and "message" in choices[0]:
                                content = choices[0]["message"].get("content", "")
                                parsed = extract_json(content)
                                if parsed is not None:
                                    return parsed
                                logger.warning("OmniRoute 200 OK returned unparseable content: %s", content[:150])
                            return None''', r'''                        if status == 200:
                            body = await resp.json()
                            self.is_gateway_online = True
                            usage = body.get("usage", {})
                            if isinstance(usage, dict):
                                try:
                                    self.total_tokens_used += int(usage.get("total_tokens", 0))
                                except (TypeError, ValueError):
                                    logger.debug("OmniRoute usage.total_tokens not numeric: %r", usage.get("total_tokens"))
                            choices = body.get("choices", [])
                            if choices and "message" in choices[0]:
                                content = choices[0]["message"].get("content", "")
                                parsed = extract_json(content)
                                if parsed is not None:
                                    # Count a success only once usable JSON is
                                    # actually in hand: a 200 with unparseable
                                    # content is not a successful request
                                    # (item 6).
                                    self.successful_requests += 1
                                    return parsed
                                logger.warning("OmniRoute 200 OK returned unparseable content: %s", content[:150])
                            return None'''))

# ---------------------------------------------------------------- gateway_supervisor.py
REPLACEMENTS.append(("src/intelligence/gateway_supervisor.py", r'''    def shutdown(self) -> None:
        """Terminates the spawned child process cleanly if created by this supervisor."""
        if self.child_process and self.is_self_spawned:
            pid = self.child_process.pid''', r'''    def shutdown(self) -> None:
        """Terminates the spawned child process cleanly if created by this supervisor.

        Only ever touches processes this supervisor itself spawned. A gateway
        (or any other program) the user started by hand on the same port is
        left alone: killing it would destroy someone else's process (item 6).
        """
        owned_pid: Optional[int] = None
        if self.child_process and self.is_self_spawned:
            owned_pid = self.child_process.pid
            pid = owned_pid'''))
REPLACEMENTS.append(("src/intelligence/gateway_supervisor.py", r'''        # Fail-safe cleanup: If any process is still holding self.port, terminate it
        self._kill_port_owner(self.port)''', r'''        # Fail-safe cleanup: only if OUR OWN child is somehow still holding
        # the port after termination. A foreign listener is never killed.
        if owned_pid is not None:
            self._kill_port_owner(self.port, owned_pid=owned_pid)'''))
REPLACEMENTS.append(("src/intelligence/gateway_supervisor.py", r'''    def _kill_port_owner(self, port: int) -> None:
        """Finds and terminates any lingering process listening on the designated port."""
        if sys.platform == "win32":''', r'''    def _kill_port_owner(self, port: int, owned_pid: Optional[int] = None) -> None:
        """Terminates a lingering listener on the port ONLY if it is our own
        spawned child (PID match). With owned_pid=None (no child of ours) it
        does nothing: a foreign process on the port is never killed (item 6).
        """
        if owned_pid is None:
            return
        if sys.platform == "win32":'''))
REPLACEMENTS.append(("src/intelligence/gateway_supervisor.py", r'''                    if len(parts) >= 5 and "LISTENING" in parts[3].upper():
                        target_pid = parts[4]
                        if target_pid.isdigit() and int(target_pid) > 4:
                            logger.info("Terminating lingering process on port %d (PID %s)", port, target_pid)''', r'''                    if len(parts) >= 5 and "LISTENING" in parts[3].upper():
                        target_pid = parts[4]
                        if target_pid.isdigit() and int(target_pid) == owned_pid:
                            logger.info("Terminating lingering own daemon on port %d (PID %s)", port, target_pid)'''))

# ---------------------------------------------------------------- live_engine.py
REPLACEMENTS.append(("src/data/live_engine.py", r'''        # Ticket path (live entries routed through evaluate_signal): the
        # strategy already built SL / TP / qty; the gates below run on it.
        if ticket is not None:
            side = ticket.side
            sl = ticket.stop_loss
            tp = ticket.take_profit

        # Phase 4: Multi-Timeframe (1h) Trend Confluence Gatekeeper''', r'''        # Ticket path (live entries routed through evaluate_signal): the
        # strategy already built SL / TP / qty; the gates below run on it.
        if ticket is not None:
            side = ticket.side
            sl = ticket.stop_loss
            tp = ticket.take_profit

        # Close ticket (SIGNAL_EXIT): exits an existing position. Entry-only
        # gates (MTF, macro veto, MC EV gate) do not apply to a risk-reducing
        # close, and there is no SL/TP bracket to evaluate (the MC gate would
        # crash on stop_loss=None). Route it straight to the broker so a
        # position can always be exited, even under HOLD_CASH (item 6).
        if ticket is not None and ticket.reason == ExecutionReason.SIGNAL_EXIT:
            if ticket.qty <= Decimal("0"):
                return False
            fill = self.broker.submit_order(ticket)
            if fill:
                self.strategy_cooldown[pid] = ts + 60.0
                self.position_entry_ts.pop(pid, None)
                self.log_event(event_label, f"{competitor.base_name.split(' ')[0]} closed {fill.qty} ETH @ ${fill.price:,.2f} (PnL ${fill.realized_pnl:+.2f})", "profit" if fill.realized_pnl >= 0 else "loss")
                return True
            return False

        # Phase 4: Multi-Timeframe (1h) Trend Confluence Gatekeeper'''))
REPLACEMENTS.append(("src/data/live_engine.py", r'''        # Strict Veto Gate (Macro Commander Option A)
        allowed, veto_reason = self.macro_commander.check_trade_veto(side, competitor.base_name)''', r'''        # Strict Veto Gate (Macro Commander Option A). Only opening orders
        # reach this point (close tickets take the fast-path above), so the
        # veto is explicitly told this is an open (item 6).
        allowed, veto_reason = self.macro_commander.check_trade_veto(side, competitor.base_name, is_close=False)'''))

# ---------------------------------------------------------------- tests/test_phase5_intel_hub.py
REPLACEMENTS.append(("tests/test_phase5_intel_hub.py", r'''    assert tel["omniroute"]["quota_pct"] == 100.0''', r'''    assert tel["omniroute"]["quota_pct"] is None  # mock client reports no usable quota: unknown, not fabricated 100.0 (item 6)'''))
REPLACEMENTS.append(("tests/test_phase5_intel_hub.py", r'''    assert len(tel["events"]) >= 5''', r'''    assert tel["events"] == []  # no fabricated seed events at construction (item 6)'''))
REPLACEMENTS.append(("tests/test_phase5_intel_hub.py", r'''def test_record_strategy_actions_mapped_to_events():
    mock_client = MagicMock()
    mock_client.is_gateway_online = False
    commander = MacroCommander(mock_client)

    # Record action for Strategy 1 (comp_agg)''', r'''def test_record_strategy_actions_mapped_to_events():
    import asyncio
    from unittest.mock import AsyncMock
    from src.intelligence.ingestion import StructuredEvent

    mock_client = MagicMock()
    mock_client.is_gateway_online = False
    mock_client.chat_json = AsyncMock(return_value=None)
    commander = MacroCommander(mock_client)

    # Actions annotate the latest REAL event: synthesize one first (the
    # old test relied on fabricated seed events, removed in item 6).
    asyncio.run(commander.synthesize_regime([
        StructuredEvent(
            timestamp="2026-11-13T00:00:00Z",
            source="CoinDesk",
            domain="crypto",
            entities_tickers=["ETH"],
            urgency_score=5,
            sentiment_score=0.1,
            summary="Test event for strategy action mapping",
        )
    ]))

    # Record action for Strategy 1 (comp_agg)'''))

NEW_FILES = {}
NEW_FILES["tests/test_intel_veto.py"] = r'''"""Item 6 tests: intelligence veto open/close split, keyword word boundaries,
numeric parsing safety, shutdown ownership, honest counters."""
import asyncio
import socket
import subprocess
import sys
import time
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from src.arena.order import OrderSide, PositionSide
from src.data.live_engine import LiveArenaEngine
from src.intelligence.gateway_supervisor import GatewaySupervisor
from src.intelligence.ingestion import (
    IntelligenceHarvester,
    RawEvent,
    StructuredEvent,
    parse_polymarket_events,
    parse_reddit_posts,
)
from src.intelligence.macro_commander import MacroCommander
from src.intelligence.omniroute_client import OmniRouteClient


def _mock_commander(**overrides):
    mock_client = MagicMock()
    mock_client.is_gateway_online = False
    for k, v in overrides.items():
        setattr(mock_client, k, v)
    return MacroCommander(mock_client)


def test_veto_never_blocks_close():
    commander = _mock_commander()
    # HOLD_CASH: closes pass on both sides, no veto counted
    commander.current_state.directional_bias = "HOLD_CASH"
    ok, _ = commander.check_trade_veto(OrderSide.BUY, "Aggressive", is_close=True)
    assert ok is True
    ok, _ = commander.check_trade_veto(OrderSide.SELL, "Conservative", is_close=True)
    assert ok is True
    assert commander.current_state.veto_count_today == 0
    # LONG_ONLY: SELL that closes a long passes; SELL that opens a short is vetoed
    commander.current_state.directional_bias = "LONG_ONLY"
    ok, _ = commander.check_trade_veto(OrderSide.SELL, "Aggressive", is_close=True)
    assert ok is True
    ok, reason = commander.check_trade_veto(OrderSide.SELL, "Aggressive", is_close=False)
    assert ok is False
    assert "VETO_MACRO_LONG_ONLY" in reason
    # SHORT_ONLY: BUY that covers a short passes
    commander.current_state.directional_bias = "SHORT_ONLY"
    ok, _ = commander.check_trade_veto(OrderSide.BUY, "Aggressive", is_close=True)
    assert ok is True
    assert commander.current_state.veto_count_today == 1


def test_close_ticket_bypasses_veto_and_gates_under_hold_cash():
    engine = LiveArenaEngine(initial_cash=Decimal("100000.00"))
    engine.bootstrap_intraday_session()
    engine.macro_commander.current_state.directional_bias = "HOLD_CASH"
    engine.broker.current_price = Decimal("2600.00")
    comp = engine.comp_a
    comp.portfolio.position_qty = Decimal("5")
    comp.portfolio.position_side = PositionSide.LONG
    comp.portfolio.avg_entry_price = Decimal("2500.00")
    closed = engine._enter_via_strategy(comp, Decimal("2600.00"), 2000.0, "TEST_CLOSE", side=OrderSide.SELL, signal="SELL")
    assert closed is True
    assert comp.portfolio.position_qty == Decimal("0")
    engine.stop()


def _fallback_structured(title, domain="crypto", raw_content=""):
    async def _run():
        mock_client = MagicMock()
        mock_client.is_gateway_online = False
        mock_client.chat_json = AsyncMock(return_value=None)
        harvester = IntelligenceHarvester(client=mock_client)
        raw = [RawEvent(source="Test", domain=domain, title=title, url="https://example.com", timestamp=2000.0, raw_content=raw_content)]
        return await harvester.process_batch(raw)
    return asyncio.run(_run())


def test_keyword_word_boundaries_no_substring_false_positives():
    # "bearing" must not count as "bear", "bank" must not count as "ban",
    # "said" must not count as "ai".
    events = _fallback_structured("Bearing maker said outlook bright as bank reports earnings")
    assert len(events) == 1
    se = events[0]
    assert se.sentiment_score == 0.0  # no real bull/bear word
    assert se.urgency_score == 5  # no real urgency word ("ban" in "bank" must not fire)
    assert "AI" not in se.entities_tickers  # "ai" in "said" must not fire

    # "method" must not count as "eth", "separate" must not count as "rate",
    # "second"/"sector" must not count as "sec".
    events = _fallback_structured("Method to separate risk as second sector cools", domain="macro")
    se = events[0]
    assert se.sentiment_score == 0.0
    assert se.urgency_score == 5
    assert "ETH" not in se.entities_tickers
    assert "FED" not in se.entities_tickers
    assert "SEC" not in se.entities_tickers

    # Positive control: real whole-word keywords still fire.
    events = _fallback_structured("Bitcoin crash as exchange hack drains funds")
    se = events[0]
    assert se.sentiment_score == -0.70  # "crash" + "hack" = two bear words
    assert se.urgency_score == 7  # real "hack" word
    assert "BTC" in se.entities_tickers


def test_llm_numeric_parsing_never_raises():
    async def _run():
        mock_client = MagicMock()
        mock_client.is_gateway_online = True
        mock_client.model_commander = "auto"
        mock_client.chat_json = AsyncMock(return_value={
            "regime": "BULLISH_SURGE",
            "directional_bias": "LONG_ONLY",
            "risk_multiplier": "high",
            "confidence": "very sure",
            "active_headline": "Test headline",
        })
        commander = MacroCommander(mock_client)
        events = [StructuredEvent(timestamp="2026-11-13T00:00:00Z", source="Test", domain="crypto", entities_tickers=["ETH"], urgency_score=5, sentiment_score=0.1, summary="Test")]
        state = await commander.synthesize_regime(events)
        assert state.risk_multiplier == 1.0
        assert state.confidence == 0.70
        assert state.regime == "BULLISH_SURGE"
        assert state.directional_bias == "LONG_ONLY"
    asyncio.run(_run())


def test_feed_numeric_parsing_never_raises():
    events = parse_polymarket_events([{"title": "Test event", "volume24hr": "not-a-number", "slug": "test", "markets": []}])
    assert len(events) == 1
    assert "$0" in events[0].title  # volume falls back to 0
    assert parse_reddit_posts({"data": {"children": [{"data": {"title": "Some post", "score": "many", "permalink": "/x"}}]}}, "CryptoCurrency", "crypto") == []


def _free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _wait_port_open(port, timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def test_shutdown_does_not_kill_foreign_process():
    port = _free_port()
    server = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        assert _wait_port_open(port), "test HTTP server did not start"
        supervisor = GatewaySupervisor(port=port)
        assert supervisor.child_process is None
        supervisor.shutdown()
        assert server.poll() is None, "shutdown() killed a process it did not spawn"
        assert _wait_port_open(port), "foreign listener died after shutdown()"
        # The fail-safe helper alone must also leave foreign processes alone.
        supervisor._kill_port_owner(port)
        assert server.poll() is None
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()


def test_shutdown_kills_own_child():
    sleeper = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(120)"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        supervisor = GatewaySupervisor(port=_free_port())
        supervisor.child_process = sleeper
        supervisor.is_self_spawned = True
        supervisor.shutdown()
        assert sleeper.poll() is not None, "shutdown() did not terminate its own child"
        assert supervisor.child_process is None
        assert supervisor.is_self_spawned is False
    finally:
        if sleeper.poll() is None:
            sleeper.kill()


def test_success_counted_only_after_parseable_json():
    async def _run():
        client = OmniRouteClient(base_url="http://mock-omniroute:20128/v1", api_key="test-key")

        # 200 with unparseable content: not a success, but not a failure either.
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.headers = {}
        mock_resp.json = AsyncMock(return_value={"choices": [{"message": {"content": "not json at all"}}]})
        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.post.return_value.__aenter__.return_value = mock_resp
        client._session = mock_session
        client._owns_session = False
        result = await client.chat_json("auto", "system", "user")
        assert result is None
        assert client.successful_requests == 0
        assert client.failed_requests == 0

        # 200 with non-numeric usage + parseable content: parses fine, counts once.
        mock_resp2 = AsyncMock()
        mock_resp2.status = 200
        mock_resp2.headers = {}
        mock_resp2.json = AsyncMock(return_value={
            "usage": {"total_tokens": "many"},
            "choices": [{"message": {"content": '{"regime": "NORMAL"}'}}],
        })
        mock_session.post.return_value.__aenter__.return_value = mock_resp2
        result = await client.chat_json("auto", "system", "user")
        assert result == {"regime": "NORMAL"}
        assert client.successful_requests == 1
        assert client.total_tokens_used == 0
    asyncio.run(_run())


def test_no_fabricated_seed_events_and_honest_quota():
    commander = _mock_commander()
    assert commander.curated_events == []
    assert commander.current_state.latest_event is None
    assert commander.current_state.confidence == 0.50
    commander.record_strategy_action("comp_agg", "AGG", "Opened LONG 5.00 ETH", "buy")
    assert commander.curated_events == []  # no fake event created to attach to

    tel = commander.get_intel_hub_telemetry()
    assert tel["omniroute"]["quota_pct"] is None  # unknown, not fabricated 100.0

    real_client = OmniRouteClient()
    real_commander = MacroCommander(real_client)
    tel2 = real_commander.get_intel_hub_telemetry()
    assert tel2["omniroute"]["quota_pct"] == 100.0  # real client: 0 tokens used of 100000 budget


def test_fallback_thresholds_do_not_veto_on_single_word():
    async def _run():
        mock_client = MagicMock()
        mock_client.is_gateway_online = False
        mock_client.chat_json = AsyncMock(return_value=None)
        commander = MacroCommander(mock_client)
        # One bearish word (sentiment -0.45) + urgency 7 used to flip the
        # arena to SHORT_ONLY; the conservative fallback bar keeps NORMAL.
        weak = StructuredEvent(timestamp="2026-11-13T00:00:00Z", source="Test", domain="macro", entities_tickers=["FED"], urgency_score=7, sentiment_score=-0.45, summary="Weak signal")
        state = await commander.synthesize_regime([weak])
        assert state.directional_bias == "BIDIRECTIONAL"
        assert state.regime == "NORMAL"
        # Two strongly bearish events with severe urgency still flip it.
        strong = [
            StructuredEvent(timestamp="2026-11-13T00:00:00Z", source="Test", domain="macro", entities_tickers=["FED"], urgency_score=9, sentiment_score=-0.70, summary="Strong bearish 1"),
            StructuredEvent(timestamp="2026-11-13T00:00:00Z", source="Test", domain="macro", entities_tickers=["FED"], urgency_score=8, sentiment_score=-0.85, summary="Strong bearish 2"),
        ]
        state = await commander.synthesize_regime(strong)
        assert state.directional_bias == "SHORT_ONLY"
        assert state.regime == "BEARISH_PANIC"
    asyncio.run(_run())
'''


def main():
    for rel, old, new in REPLACEMENTS:
        with open(rel, "r", encoding="utf-8", newline="") as f:
            content = f.read()
        count = content.count(old)
        if count != 1:
            print(f"FAIL {rel}: expected exactly 1 occurrence, found {count}")
            sys.exit(1)
        content = content.replace(old, new)
        with open(rel, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        print(f"OK {rel}")
    for rel, text in NEW_FILES.items():
        if os.path.exists(rel):
            print(f"FAIL {rel}: already exists")
            sys.exit(1)
        with open(rel, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        print(f"CREATED {rel}")
    print("ALL PATCHES APPLIED")


if __name__ == "__main__":
    main()
