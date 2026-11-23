from __future__ import annotations

import asyncio
from datetime import date
import json
import logging
import os
import random
import re
import sys
import threading
import time
from typing import Any, Callable, Dict, List, Optional
import weakref
import aiohttp

logger = logging.getLogger(__name__)

def _looks_like_format_rejection(err_body: Any) -> bool:
    """True when an error body blames response_format / JSON mode.

    Used to decide whether a 400/422 is worth retrying without the
    ``response_format`` field. Providers phrase this differently
    ("response_format is not supported", "json_object mode requires",
    "response format"), so match on the field and mode names rather
    than one vendor's exact message. A generic 400 does not match.
    """
    try:
        if isinstance(err_body, dict):
            text = json.dumps(err_body, ensure_ascii=False)
        else:
            text = str(err_body or "")
    except Exception:
        text = str(err_body or "")
    lowered = text.lower()
    return (
        "response_format" in lowered
        or "response format" in lowered
        or "json_object" in lowered
        or "json mode" in lowered
    )


_RETRY_STATUSES = {429, 502, 503}
# Cooldown after an observed 429: the digest treats the gateway as over
# quota for this long (F4). A user-set DAILY_TOKEN_QUOTA is separate.
_RATE_LIMIT_COOLDOWN_SEC = 300.0
# Gateway failure diagnosis (gateway diagnosis workstream): per-provider
# quota-failure records expire after one daily cycle. Daily quotas reset
# at midnight (Gemini: midnight Pacific; OpenRouter free allowance:
# daily), so a failure older than this is not evidence for today.
_QUOTA_RECORD_TTL_SEC = 86400.0
_THINK_CLOSED = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_THINK_OPEN = re.compile(r"<think>.*\Z", re.DOTALL | re.IGNORECASE)
_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


def extract_json(text: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Defensively strips reasoning tags (<think>...</think>), markdown code fences,
    and extracts a valid JSON dictionary {...}.
    Returns None if no valid JSON dictionary can be parsed.
    """
    if not text or not isinstance(text, str):
        return None

    # 1. Strip closed and unclosed thinking blocks from reasoning models
    s = _THINK_CLOSED.sub("", text)
    s = _THINK_OPEN.sub("", s)
    stripped = s.strip()

    # 2. Fast-path: whole response is already a JSON object (avoids corrupting
    #    embedded ```code``` fences inside JSON string fields like articles).
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            obj = json.loads(stripped)
            if isinstance(obj, dict):
                return obj
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

    # 3. Try each markdown code fence in order (handles non-JSON fences before the JSON block)
    for m in _FENCE.finditer(s):
        block = m.group(1).strip()
        if not block:
            continue
        try:
            obj = json.loads(block)
            if isinstance(obj, dict):
                return obj
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
        b_start = block.find("{")
        b_end = block.rfind("}")
        if b_start != -1 and b_end > b_start:
            try:
                obj = json.loads(block[b_start : b_end + 1])
                if isinstance(obj, dict):
                    return obj
            except (json.JSONDecodeError, ValueError, TypeError):
                pass

    # 4. Locate outermost {...}
    start = s.find("{")
    end = s.rfind("}")
    if start == -1 or end <= start:
        return None

    try:
        obj = json.loads(s[start : end + 1])
        if isinstance(obj, dict):
            return obj
    except (json.JSONDecodeError, ValueError, TypeError):
        try:
            arr = json.loads("[" + s[start : end + 1] + "]")
            if isinstance(arr, list) and arr and all(isinstance(x, dict) for x in arr):
                return {"events": arr}
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

    # 5. Fallback: scan individual `{` offsets with JSONDecoder.raw_decode so
    # prose containing trailing `{...}` after a valid JSON object still parses.
    # Bounded to 64 attempts so pathological HTML/CSS responses stay O(N).
    decoder = json.JSONDecoder()
    pos = start
    attempts = 0
    while pos != -1 and pos < len(s) and attempts < 64:
        attempts += 1
        try:
            obj, _ = decoder.raw_decode(s, pos)
            if isinstance(obj, dict):
                return obj
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
        pos = s.find("{", pos + 1)

    return None


def compute_backoff(attempt: int, retry_after: Optional[str] = None) -> float:
    """
    Computes randomized exponential backoff with jitter, honoring upstream Retry-After if provided.
    Base backoff: 0.5s -> 1.0s -> 2.0s -> 4.0s -> 8.0s (+/- 25% jitter).
    """
    if retry_after:
        try:
            val = float(retry_after)
            if 0.0 < val <= 30.0:
                return val
        except (ValueError, TypeError):
            pass

    base = min(0.5 * (2 ** attempt), 8.0)
    jitter = random.uniform(0.75, 1.25)
    return max(0.1, base * jitter)


# --- Gateway failure classification (gateway diagnosis workstream) --------
# The UI shows only two failure states -- "quota exhausted (all providers
# combined)" or "connection problem" -- so a failure must be classified
# from the error BODY, never the status code alone:
#   * OpenRouter 402 = insufficient credits / free daily allowance
#     exhausted; 429 = rate limited.
#   * DeepSeek 402 = Insufficient Balance, 429 = rate limit (cleanest split).
#   * Groq quota and rate limit are both 429; the body message names the
#     limit ("Limit 6000 TPM ... try again in 7m 48s" is a per-minute
#     limit, "tokens per day (TPD)" is a daily quota).
#   * Gemini both 429 RESOURCE_EXHAUSTED; quotaId containing PerDay/Daily
#     is a daily quota, per-minute quotaIds are retryable; prepay $0 is 402.
# OmniRoute 3.8.53 itself classifies the same way (its
# shared/utils/classify429.ts, read from the installed package): a terminal
# credits/billing signal wins over any retry hint, a sub-hour retry window
# is a rate limit, a quota keyword is quota, otherwise a 429 is a rate
# limit by definition. This classifier mirrors that decision order.
# Honest limits (do not work around them): no provider reports real
# remaining free quota, so "quota exhausted" can only come from 402/429
# signals or the user's own daily budget; provider-side problems (quota,
# bad key, provider outage) cannot be auto-fixed, only displayed; only a
# dead local gateway process can be auto-fixed (see the watchdog in
# gateway_supervisor.py).

_KNOWN_PROVIDERS = ("deepseek", "gemini", "groq", "nvidia", "openrouter")

# Terminal credits/billing signals in an error body: the provider is out
# of money or out of its daily allowance. Checked before any retry hint
# (mirrors OmniRoute's classify429 order): these do not clear on a timer.
# Deliberately NOT included: a bare "quota exceeded" -- Gemini's
# per-minute 429s say exactly that ("Quota exceeded for metric ..."),
# so it cannot distinguish a daily quota from a per-minute limit.
_TERMINAL_CREDIT_PATTERNS = (
    "insufficient balance",
    "insufficient credits",
    "insufficient credit",
    "insufficient funds",
    "credits exhausted",
    "credit exhausted",
    "credits_exhausted",
    "out of credits",
    "out of credit",
    "no credits",
    "daily free allocation",
    "free daily allowance",
    "daily allowance",
    "per day",
    "per-day",
    "perday",
    "daily limit",
    "daily quota",
    "tokens per day",
    "requests per day",
    "tpd rate limit",
    "organization tpd",
    "used all the included free usage",
)

_RETRY_HINT_RE = re.compile(
    r"(?:try again in|retry (?:after|in))\s*:?\s*((?:[^.;\n]|\.(?=\d)){1,40})",
    re.IGNORECASE,
)
_RETRY_UNIT_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(d(?:ays?)?|h(?:ours?|rs?)?|m(?:in(?:ute)?s?)?|s(?:ec(?:ond)?s?)?)\b",
    re.IGNORECASE,
)
_PROVIDER_PREFIX_RE = re.compile(r"\[\s*(deepseek|gemini|groq|nvidia|openrouter)\s*\]")


def _error_body_text(body: Any) -> str:
    """Flattens an error body (parsed JSON or raw text) to one lowercase
    string for keyword classification. Non-JSON / non-string bodies
    contribute nothing: a status code alone never claims quota."""
    if body is None:
        return ""
    if isinstance(body, str):
        return body.lower()
    if isinstance(body, dict):
        parts: list[str] = []

        def _walk(value: Any) -> None:
            if isinstance(value, str):
                parts.append(value)
            elif isinstance(value, dict):
                for v in value.values():
                    _walk(v)
            elif isinstance(value, list):
                for v in value:
                    _walk(v)

        _walk(body)
        return " ".join(parts).lower()
    return ""


def _retry_window_seconds(text: str) -> Optional[float]:
    """Seconds until the throttle clears, from a 'try again in ...' hint.

    Returns None when the body carries no retry hint. A window of an
    hour or more is a daily-scale reset, not a per-minute limit.
    """
    m = _RETRY_HINT_RE.search(text)
    if not m:
        return None
    window = m.group(1).lower()
    total = 0.0
    found = False
    for num, unit in _RETRY_UNIT_RE.findall(window):
        found = True
        val = float(num)
        if unit.startswith("d"):
            total += val * 86400
        elif unit.startswith("h"):
            total += val * 3600
        elif unit.startswith("m"):
            total += val * 60
        else:
            total += val
    return total if found else None


def _extract_error_provider(body: Any, headers: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Names the failing provider leg, when OmniRoute itself says so.

    Only OmniRoute's own attribution counts: the X-OmniRoute-Provider
    response header, or the '[provider] ...' prefix OmniRoute synthesizes
    for credits-exhausted / no-credentials failures (its
    sse/handlers/chat.ts handleNoCredentials). error.metadata.provider_name
    is deliberately NOT used: its meaning depends on the leg (on the
    OpenRouter leg it can name OpenRouter's own upstream), so it cannot
    identify the TradeBot0 leg that failed. Returns None when unattributed.
    """
    def _norm(name: Any) -> Optional[str]:
        if not isinstance(name, str):
            return None
        cleaned = name.strip().lower()
        return cleaned if cleaned in _KNOWN_PROVIDERS else None

    if headers:
        for key, value in headers.items():
            if str(key).lower() == "x-omniroute-provider":
                found = _norm(value)
                if found:
                    return found
    text = _error_body_text(body)
    if not text:
        return None
    m = _PROVIDER_PREFIX_RE.search(text)
    return m.group(1) if m else None


def classify_llm_error(
    status: Optional[int],
    body: Any = None,
    headers: Optional[Dict[str, Any]] = None,
    retry_after: Optional[str] = None,
) -> Dict[str, Any]:
    """Classifies one failed LLM call from its status + error body.

    Returns {"kind", "provider", "status", "detail"} where kind is one of:
    "quota" (credits/allowance exhausted), "transient" (per-minute rate
    limit -- keep retrying silently, never show "quota exhausted"),
    "auth" (bad key), or "unknown" (cannot honestly say more than the
    status). "connection" (gateway unreachable) is recorded by the caller,
    not here, because it never arrives as an HTTP error body.
    """
    provider = _extract_error_provider(body, headers)
    result: Dict[str, Any] = {
        "kind": "unknown",
        "provider": provider,
        "status": status,
        "detail": _error_body_text(body)[:200],
    }
    if status is None:
        return result
    if status == 402:
        # Insufficient credits / balance / free daily allowance exhausted
        # (OpenRouter, DeepSeek, Gemini prepay $0, and OmniRoute's own
        # credits_exhausted synthesis): a 402 is quota by definition.
        result["kind"] = "quota"
        return result
    if status in (401, 403):
        result["kind"] = "auth"
        return result
    if status != 429:
        return result
    text = _error_body_text(body)
    if any(pat in text for pat in _TERMINAL_CREDIT_PATTERNS):
        result["kind"] = "quota"
        return result
    window = _retry_window_seconds(text)
    if window is not None:
        result["kind"] = "quota" if window >= 3600 else "transient"
        return result
    if retry_after is not None:
        try:
            val = float(retry_after)
            if val > 0:
                result["kind"] = "quota" if val >= 3600 else "transient"
                return result
        except (TypeError, ValueError):
            pass
    # A 429 with no quota marker and no retry hint is a rate limit by
    # definition: keep retrying silently, never show "quota exhausted".
    result["kind"] = "transient"
    return result


class OmniRouteClient:
    """
    Real, asynchronous, OpenAI-compatible client pre-configured for local OmniRoute gateway.
    Supports concurrency limits, exponential jitter backoff on transient errors,
    defensive JSON parsing, and graceful offline fallback.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model_ingest: Optional[str] = None,
        model_commander: Optional[str] = None,
        max_concurrent: int = 25,
        timeout_sec: float = 60.0,
        max_retries: int = 5,
        session: Optional[aiohttp.ClientSession] = None,
    ) -> None:
        raw_url = base_url or os.getenv("LLM_BASE_URL", "http://127.0.0.1:20128/v1")
        self.base_url = raw_url.rstrip("/")
        # Extract root URL (e.g. http://127.0.0.1:20128) for /api/health probe
        if "/v1" in self.base_url:
            self.root_url = self.base_url.split("/v1")[0]
        else:
            self.root_url = self.base_url

        self.api_key = api_key or os.getenv("LLM_API_KEY")
        self.model_ingest = model_ingest or os.getenv("LLM_MODEL_INGEST", "auto")
        self.model_commander = model_commander or os.getenv("LLM_MODEL_COMMANDER", "auto")

        self.max_concurrent = max(1, int(os.getenv("LLM_MAX_CONCURRENT_REQUESTS", str(max_concurrent))))
        self.timeout_sec = float(os.getenv("LLM_REQUEST_TIMEOUT_SEC", str(timeout_sec)))
        self.max_retries = int(os.getenv("LLM_MAX_RETRIES", str(max_retries)))

        self._sem = asyncio.Semaphore(self.max_concurrent)
        self._sem_loop: Optional[asyncio.AbstractEventLoop] = None
        self._sems: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore]" = weakref.WeakKeyDictionary()
        # Session lifecycle (V2.8.0 repair): one ClientSession PER EVENT
        # LOOP. Keyed weakly by the loop object itself so closed loop ids
        # can never collide after GC.
        self._session = session              # shared/injected, or latest
        self._session_loop: Optional[asyncio.AbstractEventLoop] = None
        self._sessions: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, Any]" = weakref.WeakKeyDictionary()
        self._sessions_lock = threading.Lock()
        self._shutdown_event = threading.Event()
        self._owns_session = session is None
        # JSON-mode negotiation (V2.8.0 repair): a provider that rejects
        # response_format with 400 is retried once without it, and concrete
        # model IDs are remembered so later calls skip the field entirely.
        self._json_mode_unsupported: set = set()

        # Telemetry & Status
        self.is_gateway_online: bool = False
        self.last_health_check_ts: float = 0.0
        self.total_requests: int = 0
        self.successful_requests: int = 0
        self.failed_requests: int = 0
        self.retried_requests: int = 0
        self.total_tokens_used: int = 0
        self._quota_day: date = date.today()
        self.total_tokens_saved: int = 0
        # Dedup hits, counted (item 12 / A4-3). No token figure is derived
        # from them: the old record_tokens_saved(420) wrote a fixed estimate
        # per hit with no measurement behind it.
        self.total_dedup_hits: int = 0
        # P0-B / F4: no invented denominator. DAILY_TOKEN_QUOTA is the
        # user's own budget: only when they set it is there a real
        # denominator to divide by. Unset (or unparseable) means unknown.
        _quota_env = os.getenv("DAILY_TOKEN_QUOTA")
        try:
            self.daily_quota_limit: Optional[int] = int(_quota_env) if _quota_env is not None else None
        except (TypeError, ValueError):
            self.daily_quota_limit = None
        # Timestamp (time.monotonic) until which an observed 429 /
        # limitReached signal counts as over quota. No quota math is
        # involved: it is a cooldown after an observed rate-limit signal.
        self._rate_limit_until: float = 0.0
        # Gateway failure diagnosis (gateway diagnosis workstream): the
        # last classified failure and, per provider, the last time it
        # failed with a quota/credit signal. Quota records expire after
        # one daily cycle (see _QUOTA_RECORD_TTL_SEC): a failure from a
        # previous day is not evidence for today.
        self._quota_lock = threading.Lock()
        self.last_failure: Optional[Dict[str, Any]] = None
        self._quota_failures: Dict[str, float] = {}
        self._unattributed_quota_ts: Optional[float] = None

    def _maybe_rollover_daily_quota_locked(self) -> None:
        today = date.today()
        if today != self._quota_day:
            self._quota_day = today
            self.total_tokens_used = 0

    def _maybe_rollover_daily_quota(self) -> None:
        with self._quota_lock:
            self._maybe_rollover_daily_quota_locked()

    def _record_token_usage(self, usage: Any) -> None:
        if not isinstance(usage, dict):
            return
        try:
            tok = int(usage.get("total_tokens", 0))
        except (TypeError, ValueError):
            logger.debug("OmniRoute usage.total_tokens not numeric: %r", usage.get("total_tokens"))
            return
        with self._quota_lock:
            self._maybe_rollover_daily_quota_locked()
            self.total_tokens_used += tok

    def record_dedup_hit(self) -> None:
        """Records one deduplication hit (a duplicate title+URL skipped).

        Counts hits only. The old record_tokens_saved(420) wrote a fixed
        420-token estimate per hit with no measurement behind it (item 12 /
        A4-3): no token figure is claimed anymore.
        """
        self.total_dedup_hits += 1

    def record_tokens_saved(self, tokens: int) -> None:
        """Legacy estimate hook (item 12 / A4-3): kept for backward
        compatibility only. New code uses record_dedup_hit(); no caller
        should treat the accumulated figure as a measured saving."""
        if tokens > 0:
            self.total_tokens_saved += int(tokens)

    def note_rate_limit(self, retry_after: Optional[str] = None) -> None:
        """Records an observed rate-limit signal (429 / limitReached).

        Starts a cooldown during which is_over_quota() reads True. This
        is the only throttle signal when no DAILY_TOKEN_QUOTA is set: no
        provider reports a daily free allowance, so there is no real
        denominator to divide by (F4). A Retry-After longer than the
        default cooldown extends it.
        """
        cooldown = _RATE_LIMIT_COOLDOWN_SEC
        if retry_after:
            try:
                val = float(retry_after)
                if 0.0 < val <= 3600.0:
                    cooldown = max(cooldown, val)
            except (TypeError, ValueError):
                pass
        with self._quota_lock:
            self._rate_limit_until = max(self._rate_limit_until, time.monotonic() + cooldown)

    def is_rate_limited(self) -> bool:
        """True while the cooldown from an observed 429 is still running."""
        with self._quota_lock:
            return time.monotonic() < self._rate_limit_until

    def is_over_quota(self) -> bool:
        """True once measured token usage reaches the daily quota, or while
        a recently observed 429 cooldown is running.

        The quota is a soft display budget, not a limiter (item 12 / A4-4);
        callers use this to throttle the digest cadence, never to block a
        single request. With no DAILY_TOKEN_QUOTA set there is no usage
        threshold at all -- only the 429 signal can trip this (F4).
        """
        with self._quota_lock:
            self._maybe_rollover_daily_quota_locked()
            if self.daily_quota_limit is not None and self.daily_quota_limit > 0:
                if self.total_tokens_used >= self.daily_quota_limit:
                    return True
            return time.monotonic() < self._rate_limit_until

    def note_failure(self, classification: Dict[str, Any]) -> None:
        """Records one classified LLM failure for the gateway diagnosis.

        Quota failures are tracked per provider: the dashboard only
        reports "quota exhausted (all providers combined)" once every
        configured provider has such a record (see
        is_all_providers_quota_exhausted). A quota signal that names no
        provider is kept as unattributed -- it only counts when a single
        provider is configured, because then it could only have come
        from that provider. Never raises.
        """
        try:
            if not isinstance(classification, dict):
                return
            kind = classification.get("kind") or "unknown"
            provider = classification.get("provider")
            now = time.monotonic()
            with self._quota_lock:
                self.last_failure = {
                    "kind": kind,
                    "provider": provider,
                    "status": classification.get("status"),
                    "detail": (classification.get("detail") or "")[:200],
                    "ts": now,
                }
                if kind == "quota":
                    if isinstance(provider, str) and provider in _KNOWN_PROVIDERS:
                        self._quota_failures[provider] = now
                    else:
                        self._unattributed_quota_ts = now
        except Exception as e:
            logger.debug("Failed to record LLM failure classification: %s", e)

    def note_success(self) -> None:
        """A 200 from the gateway proves at least one provider has quota
        right now, so all per-provider quota records are dropped. The
        records are current evidence, not a latch."""
        try:
            with self._quota_lock:
                self._quota_failures.clear()
                self._unattributed_quota_ts = None
        except Exception as e:
            logger.debug("Failed to clear quota records on success: %s", e)

    def is_daily_budget_exhausted(self) -> bool:
        """True only when the user's own DAILY_TOKEN_QUOTA budget is used
        up. Unset budget means unknown, never exhausted."""
        with self._quota_lock:
            self._maybe_rollover_daily_quota_locked()
            limit = self.daily_quota_limit
            return limit is not None and limit > 0 and self.total_tokens_used >= limit

    def has_quota_failures(self) -> bool:
        """O(1) fast-path check indicating whether any recent quota signal exists."""
        now = time.monotonic()
        with self._quota_lock:
            if self._unattributed_quota_ts is not None and (now - self._unattributed_quota_ts) <= _QUOTA_RECORD_TTL_SEC:
                return True
            return any((now - ts) <= _QUOTA_RECORD_TTL_SEC for ts in self._quota_failures.values())

    def is_all_providers_quota_exhausted(self, configured_providers: Any) -> bool:
        """True when every configured provider has failed with a
        quota/credit signal -- the only honest reading of "quota
        exhausted (all providers combined)".

        Records older than one daily cycle do not count (daily quotas
        reset at midnight). With a single configured provider, an
        unattributed quota signal counts for it; with several, an
        unattributed signal counts for none, because it cannot prove
        every provider is out. A provider that was never recorded does
        not count. Never raises.
        """
        try:
            configured = [p for p in (configured_providers or []) if p in _KNOWN_PROVIDERS]
            if not configured:
                return False
            now = time.monotonic()
            with self._quota_lock:
                fresh = {
                    p: ts
                    for p, ts in self._quota_failures.items()
                    if now - ts <= _QUOTA_RECORD_TTL_SEC
                }
                unattr_ts = self._unattributed_quota_ts
            if len(configured) == 1:
                only = configured[0]
                if only in fresh:
                    return True
                return unattr_ts is not None and now - unattr_ts <= _QUOTA_RECORD_TTL_SEC
            return all(p in fresh for p in configured)
        except Exception as e:
            logger.debug("Quota-exhaustion check failed: %s", e)
            return False

    async def _read_error_body(self, resp: Any) -> Any:
        """Best-effort read of a failed response body for diagnosis.

        Returns the parsed JSON object when the body is JSON, else the
        raw text (capped). Never raises: a body that cannot be read
        classifies from the status code alone.
        """
        try:
            return await resp.json()
        except Exception as e:
            logger.debug("OmniRoute error response is not JSON: %s", e)
        try:
            text = await resp.text()
            return text[:4000] if isinstance(text, str) else None
        except Exception as e:
            logger.debug("Failed to read OmniRoute error body: %s", e)
            return None

    def get_quota_pct(self) -> Optional[float]:
        """Remaining quota % against the user's own daily budget, or None.

        Returns None when DAILY_TOKEN_QUOTA is unset: no provider
        reports a daily free allowance, so any % would invent a
        denominator (F4). Only a user-set budget yields a real %.
        """
        with self._quota_lock:
            self._maybe_rollover_daily_quota_locked()
            if self.daily_quota_limit is None or self.daily_quota_limit <= 0:
                return None
            remaining = max(0, self.daily_quota_limit - self.total_tokens_used)
            return round((remaining / self.daily_quota_limit) * 100.0, 1)

    def _get_semaphore(self) -> asyncio.Semaphore:
        try:
            current_loop = asyncio.get_running_loop()
            with self._sessions_lock:
                sem = self._sems.get(current_loop)
                if sem is None:
                    sem = asyncio.Semaphore(self.max_concurrent)
                    self._sems[current_loop] = sem
                self._sem_loop = current_loop
                self._sem = sem
                return sem
        except RuntimeError:
            return self._sem

    async def get_session(self) -> aiohttp.ClientSession:
        """Return the aiohttp session owned by the CALLING event loop.

        A session injected through the constructor (or assigned directly,
        as tests do) has no owning loop and is shared: it is returned
        as-is and never closed by per-loop cleanup. Otherwise every loop
        gets its own session, created on first use. Closing one loop's
        session can therefore never interrupt a request running on a
        different loop or thread.
        """
        current_loop = asyncio.get_running_loop()
        with self._sessions_lock:
            if self._session is not None and not self._session.closed and self._session_loop is None:
                return self._session
            sess = self._sessions.get(current_loop)
            if sess is not None and not sess.closed:
                return sess
            timeout = aiohttp.ClientTimeout(total=self.timeout_sec)
            sess = aiohttp.ClientSession(timeout=timeout)
            self._sessions[current_loop] = sess
            self._session_loop = current_loop
            self._session = sess            # latest, for observability
            self._owns_session = True
            return sess

    async def close_loop_session(self) -> None:
        """Close and forget the session owned by the current event loop.

        Safe from any loop: it removes only that loop's entry, so it can
        never close a session another thread is still using. Called from
        the private asyncio.run() used by article generation and the
        digest refresh, before that loop ends, so no loop-bound session
        is left unclosed.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        with self._sessions_lock:
            sess = self._sessions.pop(loop, None)
            if sess is not None and self._session is sess:
                self._session = None
                self._session_loop = None
        if sess is None:
            return
        try:
            if not sess.closed:
                await sess.close()
        except Exception as e:
            logger.debug("Failed to close loop session: %s", e)

    def mark_shutting_down(self) -> None:
        """Signals all in-flight and future LLM calls to stop immediately on app teardown."""
        self._shutdown_event.set()
        self.is_gateway_online = False

    def is_shutting_down(self) -> bool:
        return sys.is_finalizing() or self._shutdown_event.is_set()

    @staticmethod
    def _is_dynamic_route_alias(model: Any) -> bool:
        m = str(model or "").strip().lower()
        return m == "auto" or m.startswith("auto/")

    async def check_health(self) -> bool:
        """
        Unauthenticated liveness probe to GET /api/health on OmniRoute gateway.
        """
        if self.is_shutting_down():
            self.is_gateway_online = False
            return False
        try:
            sess = await self.get_session()
            url = f"{self.root_url}/api/health"
            async with sess.get(url, timeout=aiohttp.ClientTimeout(total=0.75)) as r:
                if r.status == 200:
                    data = await r.json()
                    self.is_gateway_online = isinstance(data, dict) and bool(data.get("ok", True))
                else:
                    self.is_gateway_online = False
        except Exception as e:
            logger.debug("Gateway health check failed: %s", e)
            self.is_gateway_online = False

        self.last_health_check_ts = asyncio.get_running_loop().time()
        return self.is_gateway_online

    async def chat_json(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 1500,
        timeout_sec: Optional[float] = None,
        on_progress: Optional[Callable[[str, int, str], None]] = None,
        stream_progress: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        Sends an OpenAI-compatible chat completion request and returns a parsed JSON dictionary.
        Applies exponential backoff on transient 429/502/503. Falls back safely to None on failure.
        When `stream_progress` is True and `on_progress` is supplied, requests SSE streaming so
        real token/character arrival advances progress live, falling back transparently to
        standard JSON responses whenever a provider does not stream.
        """
        def _emit(stage: str, pct: int, detail: str) -> None:
            if on_progress is None:
                return
            try:
                on_progress(stage, int(max(0, min(100, pct))), detail)
            except Exception as cb_err:
                logger.debug("chat_json progress callback error: %s", cb_err)

        if self.is_shutting_down():
            return None
        sess = await self.get_session()
        call_timeout = timeout_sec if timeout_sec is not None else self.timeout_sec
        payload: Dict[str, Any] = {
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        model_key = str(model)
        with self._sessions_lock:
            skip_json_mode = (not self._is_dynamic_route_alias(model_key)) and (model_key in self._json_mode_unsupported)
        if not skip_json_mode:
            payload["response_format"] = {"type": "json_object"}
        if stream_progress:
            payload["stream"] = True
        # Item 10 A3: never send a placeholder key. With no key configured
        # the request goes out without an Authorization header at all.
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        endpoint = f"{self.base_url}/chat/completions"
        self.total_requests += 1
        format_retried = False
        stream_retried = False
        attempt = 0

        while attempt <= self.max_retries:
            if self.is_shutting_down():
                return None
            need_repair = False
            retry_delay: Optional[float] = None
            retry_format = False
            retry_nonstream = False
            try:
                if getattr(sess, "closed", False):
                    sess = await self.get_session()
                _emit("connecting", 18, "Connecting to AI gateway")
                async with self._get_semaphore():
                    _emit("waiting", 26, "Waiting for AI response")
                    async with sess.post(
                        endpoint,
                        json=payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=call_timeout),
                    ) as resp:
                        status = resp.status
                        retry_after = resp.headers.get("Retry-After")
                        err_body = None
                        if status != 200:
                            err_body = await self._read_error_body(resp)
                        if status == 429:
                            self.note_rate_limit(retry_after)

                        if status == 200:
                            ctype = str(resp.headers.get("Content-Type") or "").lower()
                            if payload.get("stream") and "text/event-stream" in ctype:
                                chunks: List[str] = []
                                total_chars = 0
                                target_chars = max(1200, int(max_tokens * 0.72))
                                last_pct = 28
                                usage_obj: Any = None
                                sse_error: Any = None
                                _emit("analyzing", 32, "Analyzing market context")
                                async for raw_line in resp.content:
                                    if self.is_shutting_down():
                                        return None
                                    line = raw_line.decode("utf-8", errors="replace").strip()
                                    if not line or line.startswith(":") or not line.startswith("data:"):
                                        continue
                                    data_str = line[5:].strip()
                                    if data_str == "[DONE]":
                                        break
                                    try:
                                        frame = json.loads(data_str)
                                    except Exception:
                                        continue
                                    if isinstance(frame, dict):
                                        if frame.get("error"):
                                            sse_error = frame.get("error")
                                            break
                                        if frame.get("usage"):
                                            usage_obj = frame.get("usage")
                                        f_choices = frame.get("choices")
                                        if isinstance(f_choices, list) and f_choices and isinstance(f_choices[0], dict):
                                            delta = f_choices[0].get("delta") or {}
                                            if isinstance(delta, dict):
                                                piece = delta.get("content")
                                                if isinstance(piece, str) and piece:
                                                    chunks.append(piece)
                                                    total_chars += len(piece)
                                                    frac = min(1.0, total_chars / float(target_chars))
                                                    pct = 32 + int(frac * 56)
                                                    if pct > last_pct:
                                                        last_pct = pct
                                                        if pct < 50:
                                                            _emit("analyzing", pct, "Analyzing market context")
                                                        elif pct < 74:
                                                            _emit("drafting", pct, "Drafting in-depth report")
                                                        else:
                                                            _emit("structuring", pct, "Structuring key takeaways")
                                if sse_error is not None:
                                    err_payload = sse_error if isinstance(sse_error, dict) else {"error": str(sse_error)}
                                    classification = classify_llm_error(500, err_payload)
                                    self.note_failure(classification)
                                    self.failed_requests += 1
                                    logger.warning("OmniRoute 200 SSE emitted in-band error frame: %s", str(sse_error)[:150])
                                    return None
                                content = "".join(chunks)
                                if not content.strip():
                                    self.failed_requests += 1
                                    logger.warning("OmniRoute 200 SSE stream ended with empty content")
                                    return None
                                self.is_gateway_online = True
                                self.note_success()
                                if usage_obj is not None:
                                    self._record_token_usage(usage_obj)
                                _emit("parsing", 91, "Parsing & validating report")
                                parsed = extract_json(content)
                                if parsed is not None:
                                    self.successful_requests += 1
                                    return parsed
                                logger.warning("OmniRoute 200 SSE returned unparseable content: %s", content[:150])
                                need_repair = True
                            else:
                                _emit("receiving", 72, "Receiving AI response")
                                body = await self._parse_ok_json_body(resp)
                                if not isinstance(body, dict):
                                    self.failed_requests += 1
                                    logger.warning("OmniRoute 200 OK returned non-JSON or non-object body")
                                    return None
                                self.is_gateway_online = True
                                self.note_success()
                                self._record_token_usage(body.get("usage"))
                                _emit("parsing", 90, "Parsing & validating report")
                                choices = body.get("choices")
                                if isinstance(choices, list) and choices and isinstance(choices[0], dict) and "message" in choices[0]:
                                    msg = choices[0].get("message") or {}
                                    raw_content = msg.get("content") if isinstance(msg, dict) else ""
                                    content = raw_content if isinstance(raw_content, str) else ""
                                    parsed = extract_json(content)
                                    if parsed is not None:
                                        self.successful_requests += 1
                                        return parsed
                                    logger.warning("OmniRoute 200 OK returned unparseable content: %s", content[:150])
                                    need_repair = True
                                else:
                                    self.failed_requests += 1
                                    return None
                        elif (
                            status in (400, 422)
                            and payload.get("stream")
                            and not stream_retried
                            and not _looks_like_format_rejection(err_body)
                        ):
                            payload.pop("stream", None)
                            stream_retried = True
                            retry_nonstream = True
                            _emit("waiting", 24, "Switching to standard response mode")
                            logger.info(
                                "Provider rejected streaming mode (HTTP %d); retrying without stream",
                                status,
                            )
                        elif (
                            status in (400, 422)
                            and "response_format" in payload
                            and not format_retried
                            and _looks_like_format_rejection(err_body)
                        ):
                            payload.pop("response_format", None)
                            if not self._is_dynamic_route_alias(model_key):
                                with self._sessions_lock:
                                    if len(self._json_mode_unsupported) >= 128:
                                        self._json_mode_unsupported.clear()
                                    self._json_mode_unsupported.add(model_key)
                            self.retried_requests += 1
                            format_retried = True
                            retry_format = True
                            logger.info(
                                "Provider rejected response_format (HTTP %d); retrying without JSON mode",
                                status,
                            )
                        else:
                            classification = classify_llm_error(
                                status, err_body,
                                headers=dict(resp.headers),
                                retry_after=retry_after,
                            )
                            self.note_failure(classification)
                            # Do not burn 5 backoff retries against a terminal daily quota 429.
                            if (
                                status in _RETRY_STATUSES
                                and classification.get("kind") != "quota"
                                and attempt < self.max_retries
                            ):
                                self.retried_requests += 1
                                retry_delay = compute_backoff(attempt, retry_after)
                                _emit("retrying", 22, f"Gateway busy, retrying ({attempt + 1}/{self.max_retries})")
                                logger.info(
                                    "OmniRoute status %d on attempt %d/%d. Backoff %.2fs",
                                    status, attempt + 1, self.max_retries, retry_delay
                                )
                            else:
                                self.failed_requests += 1
                                logger.warning("OmniRoute request terminated with HTTP %d (attempt %d)", status, attempt)
                                return None

                # Both HTTP response and concurrency semaphore are now released before
                # performing a repair call or sleeping for retry backoff (prevents
                # max_concurrent=1 self-deadlock and connection-pool starvation).
                if need_repair:
                    _emit("repairing", 94, "Formatting response structure")
                    repair_payload = dict(payload)
                    repair_payload.pop("stream", None)
                    repaired = await self._repair_json_once(
                        sess, endpoint, headers, repair_payload, call_timeout
                    )
                    if repaired is not None:
                        self.successful_requests += 1
                        return repaired
                    return None
                if retry_nonstream or retry_format:
                    continue
                if retry_delay is not None:
                    if self.is_shutting_down():
                        return None
                    await asyncio.sleep(retry_delay)
                    attempt += 1
                    continue

            except aiohttp.ClientConnectorError as exc:
                if self.is_shutting_down():
                    return None
                self.failed_requests += 1
                self.is_gateway_online = False
                self.note_failure({"kind": "connection", "provider": None, "status": None, "detail": str(exc)[:200]})
                logger.debug("OmniRoute gateway offline (connection refused): %s", exc)
                return None
            except asyncio.TimeoutError as exc:
                if self.is_shutting_down():
                    return None
                timeout_retries = 0 if call_timeout >= 60.0 else min(1, self.max_retries)
                if attempt < timeout_retries:
                    self.retried_requests += 1
                    delay = compute_backoff(attempt)
                    logger.debug("OmniRoute completion timed out (%s). Retrying once in %.2fs...", exc, delay)
                    await asyncio.sleep(delay)
                    attempt += 1
                else:
                    self.failed_requests += 1
                    self.note_failure({"kind": "connection", "provider": None, "status": None, "detail": f"timeout ({call_timeout}s)"})
                    logger.warning("OmniRoute request timed out after %.1fs (attempt %d)", call_timeout, attempt + 1)
                    return None
            except aiohttp.ClientError as exc:
                if self.is_shutting_down():
                    return None
                if attempt < self.max_retries:
                    self.retried_requests += 1
                    delay = compute_backoff(attempt)
                    logger.debug("OmniRoute connection error (%s). Retrying in %.2fs...", exc, delay)
                    await asyncio.sleep(delay)
                    attempt += 1
                else:
                    self.failed_requests += 1
                    self.is_gateway_online = False
                    self.note_failure({"kind": "connection", "provider": None, "status": None, "detail": str(exc)[:200]})
                    logger.warning("OmniRoute gateway unreachable after %d retries: %s", self.max_retries, exc)
                    return None
            except RuntimeError as e:
                err_txt = str(e)
                if (
                    self.is_shutting_down()
                    or "cannot schedule new futures after shutdown" in err_txt
                    or "Event loop is closed" in err_txt
                ):
                    logger.debug("OmniRouteClient request aborted during shutdown: %s", e)
                    return None
                self.failed_requests += 1
                logger.error("Unexpected error in OmniRouteClient: %s", e)
                return None
            except Exception as e:
                if self.is_shutting_down():
                    logger.debug("OmniRouteClient request aborted during shutdown: %s", e)
                    return None
                self.failed_requests += 1
                logger.error("Unexpected error in OmniRouteClient: %s", e)
                return None

        self.failed_requests += 1
        return None

    async def _parse_ok_json_body(self, resp: Any) -> Optional[Dict[str, Any]]:
        """Parses an HTTP 200 response body defensively without treating bad Content-Type as offline."""
        try:
            body = await resp.json()
            return body if isinstance(body, dict) else None
        except (aiohttp.ContentTypeError, ValueError, TypeError, json.JSONDecodeError):
            try:
                raw_text = await resp.text()
                if isinstance(raw_text, str) and raw_text.strip():
                    body = json.loads(raw_text)
                    return body if isinstance(body, dict) else None
            except Exception as e:
                logger.debug("OmniRoute 200 fallback text JSON parse failed: %s", e)
            return None

    async def _repair_json_once(
        self,
        sess: Any,
        endpoint: str,
        headers: Dict[str, str],
        payload: Dict[str, Any],
        timeout_sec: float,
    ) -> Optional[Dict[str, Any]]:
        """One repair attempt after a 200 with unparseable content.

        Re-sends the original messages plus a short user reminder
        demanding a JSON object only. Returns the parsed dict or None.
        Never raises. Bounded to exactly one extra call: a model that
        ignores the reminder (like the routed glm-5.2, which also
        ignores response_format) must not be re-asked forever.
        """
        if self.is_shutting_down():
            return None
        try:
            if getattr(sess, "closed", False):
                sess = await self.get_session()
            repair_payload = dict(payload)
            repair_payload["messages"] = list(payload.get("messages", [])) + [
                {"role": "user",
                 "content": "Your previous reply was not a JSON object. "
                            "Reply again with ONLY a JSON object, no other "
                            "text, no markdown, no explanation. Use the exact "
                            "same schema and fields as the original request."},
            ]
            self.retried_requests += 1
            async with self._get_semaphore():
                async with sess.post(
                    endpoint,
                    json=repair_payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=timeout_sec),
                ) as resp:
                    if resp.status != 200:
                        retry_after = resp.headers.get("Retry-After")
                        err_body = await self._read_error_body(resp)
                        if resp.status == 429:
                            self.note_rate_limit(retry_after)
                        if resp.status in (401, 402, 403, 429):
                            self.note_failure(classify_llm_error(
                                resp.status, err_body, headers=dict(resp.headers), retry_after=retry_after
                            ))
                        return None
                    body = await self._parse_ok_json_body(resp)
                    if not isinstance(body, dict):
                        return None
                    self._record_token_usage(body.get("usage"))
                    choices = body.get("choices")
                    if isinstance(choices, list) and choices and isinstance(choices[0], dict) and "message" in choices[0]:
                        msg = choices[0].get("message") or {}
                        raw_content = msg.get("content") if isinstance(msg, dict) else ""
                        content = raw_content if isinstance(raw_content, str) else ""
                        parsed = extract_json(content)
                        if parsed is not None:
                            logger.info("OmniRoute repair retry returned usable JSON")
                            return parsed
                        logger.warning("OmniRoute repair retry still unparseable: %s", content[:150])
                    return None
        except Exception as e:
            logger.debug("OmniRoute repair retry failed: %s", e)
            return None

    def _all_sessions_with_loops(self) -> list:
        """Every owned (loop_or_none, session) pair, de-duplicated."""
        with self._sessions_lock:
            pairs = list(self._sessions.items())
            self._sessions.clear()
            latest = self._session
            latest_loop = self._session_loop
        if latest is not None and all(latest is not s for _, s in pairs):
            pairs.append((latest_loop, latest))
        return pairs

    def _all_sessions(self) -> list:
        """Every owned session, newest-last / shared first, de-duplicated."""
        return [s for _, s in self._all_sessions_with_loops()]

    async def close(self) -> None:
        """Closes every owned aiohttp session to prevent resource leaks."""
        for sess in self._all_sessions():
            if sess is not None and not sess.closed and self._owns_session:
                try:
                    await sess.close()
                except Exception as e:
                    logger.debug("Failed to close session: %s", e)
        self._session = None
        self._session_loop = None

    def close_sync(self) -> None:
        """Synchronously closes owned sessions or schedules their close on their owning loop."""
        if sys.is_finalizing():
            return
        pairs = self._all_sessions_with_loops()
        if not self._owns_session:
            self._session = None
            return
        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None
        for owner_loop, sess in pairs:
            if sess is None or sess.closed:
                continue
            try:
                if owner_loop is not None and owner_loop.is_running():
                    if running_loop is owner_loop:
                        owner_loop.create_task(sess.close())
                    else:
                        # Defer sess.close() coroutine creation onto owner_loop so a
                        # closed-loop RuntimeError never leaks an unawaited coroutine.
                        owner_loop.call_soon_threadsafe(
                            lambda l=owner_loop, s=sess: l.create_task(s.close()) if not s.closed else None
                        )
                elif running_loop is not None and running_loop.is_running():
                    running_loop.create_task(sess.close())
                else:
                    asyncio.run(sess.close())
            except Exception as e:
                logger.debug("Failed to close session synchronously: %s", e)
        self._session = None
        self._session_loop = None

    def __del__(self) -> None:
        if sys.is_finalizing():
            return
        try:
            self.close_sync()
        except Exception as e:
            logger.debug("Failed to close session in destructor: %s", e)

