from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import re
import time
from typing import Any, Dict, Optional
import aiohttp

logger = logging.getLogger(__name__)

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
    and extracts the outermost JSON dictionary {...}.
    Returns None if no valid JSON dictionary can be parsed.
    """
    if not text or not isinstance(text, str):
        return None

    # 1. Strip closed and unclosed thinking blocks from reasoning models
    s = _THINK_CLOSED.sub("", text)
    s = _THINK_OPEN.sub("", s)

    # 2. Extract code fence if present
    m = _FENCE.search(s)
    if m:
        s = m.group(1)

    # 3. Locate outermost {...}
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

_KNOWN_PROVIDERS = ("deepseek", "gemini", "groq", "openrouter")

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
    r"(?:try again in|retry (?:after|in))\s*:?\s*([^.;\n]{1,40})",
    re.IGNORECASE,
)
_RETRY_UNIT_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(d(?:ays?)?|h(?:ours?|rs?)?|m(?:in(?:ute)?s?)?|s(?:ec(?:ond)?s?)?)\b",
    re.IGNORECASE,
)
_PROVIDER_PREFIX_RE = re.compile(r"\[\s*(deepseek|gemini|groq|openrouter)\s*\]")


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
        raw_url = base_url or os.getenv("LLM_BASE_URL", "http://localhost:20128/v1")
        self.base_url = raw_url.rstrip("/")
        # Extract root URL (e.g. http://localhost:20128) for /api/health probe
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
        self._session = session
        self._session_loop: Optional[asyncio.AbstractEventLoop] = None
        self._owns_session = session is None

        # Telemetry & Status
        self.is_gateway_online: bool = False
        self.last_health_check_ts: float = 0.0
        self.total_requests: int = 0
        self.successful_requests: int = 0
        self.failed_requests: int = 0
        self.retried_requests: int = 0
        self.total_tokens_used: int = 0
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
        self.last_failure: Optional[Dict[str, Any]] = None
        self._quota_failures: Dict[str, float] = {}
        self._unattributed_quota_ts: Optional[float] = None

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
        self._rate_limit_until = time.monotonic() + cooldown

    def is_rate_limited(self) -> bool:
        """True while the cooldown from an observed 429 is still running."""
        return time.monotonic() < self._rate_limit_until

    def is_over_quota(self) -> bool:
        """True once measured token usage reaches the daily quota, or while
        a recently observed 429 cooldown is running.

        The quota is a soft display budget, not a limiter (item 12 / A4-4);
        callers use this to throttle the digest cadence, never to block a
        single request. With no DAILY_TOKEN_QUOTA set there is no usage
        threshold at all -- only the 429 signal can trip this (F4).
        """
        if self.daily_quota_limit is not None and self.daily_quota_limit > 0:
            if self.total_tokens_used >= self.daily_quota_limit:
                return True
        return self.is_rate_limited()

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
            self.last_failure = {
                "kind": kind,
                "provider": provider,
                "status": classification.get("status"),
                "detail": (classification.get("detail") or "")[:200],
                "ts": time.monotonic(),
            }
            if kind == "quota":
                now = time.monotonic()
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
            self._quota_failures.clear()
            self._unattributed_quota_ts = None
        except Exception as e:
            logger.debug("Failed to clear quota records on success: %s", e)

    def is_daily_budget_exhausted(self) -> bool:
        """True only when the user's own DAILY_TOKEN_QUOTA budget is used
        up. Unset budget means unknown, never exhausted."""
        limit = self.daily_quota_limit
        return limit is not None and limit > 0 and self.total_tokens_used >= limit

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
            fresh = {
                p: ts
                for p, ts in self._quota_failures.items()
                if now - ts <= _QUOTA_RECORD_TTL_SEC
            }
            if len(configured) == 1:
                only = configured[0]
                if only in fresh:
                    return True
                return (
                    self._unattributed_quota_ts is not None
                    and now - self._unattributed_quota_ts <= _QUOTA_RECORD_TTL_SEC
                )
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
        except Exception:
            pass
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
        if self.daily_quota_limit is None or self.daily_quota_limit <= 0:
            return None
        remaining = max(0, self.daily_quota_limit - self.total_tokens_used)
        return round((remaining / self.daily_quota_limit) * 100.0, 1)

    def _get_semaphore(self) -> asyncio.Semaphore:
        try:
            current_loop = asyncio.get_running_loop()
            if self._sem_loop is not current_loop:
                self._sem = asyncio.Semaphore(self.max_concurrent)
                self._sem_loop = current_loop
        except RuntimeError:
            pass
        return self._sem

    async def get_session(self) -> aiohttp.ClientSession:
        if not self._owns_session and self._session is not None and not self._session.closed:
            return self._session
        current_loop = asyncio.get_running_loop()
        if (
            self._session is None
            or self._session.closed
            or (self._session_loop is not None and self._session_loop is not current_loop)
        ):
            if self._session and not self._session.closed and self._owns_session:
                try:
                    await self._session.close()
                except Exception as e:
                    logger.debug("Failed to close previous session: %s", e)
            timeout = aiohttp.ClientTimeout(total=self.timeout_sec)
            self._session = aiohttp.ClientSession(timeout=timeout)
            self._session_loop = current_loop
            self._owns_session = True
        return self._session

    async def check_health(self) -> bool:
        """
        Unauthenticated liveness probe to GET /api/health on OmniRoute gateway.
        """
        try:
            sess = await self.get_session()
            url = f"{self.root_url}/api/health"
            async with sess.get(url, timeout=aiohttp.ClientTimeout(total=0.75)) as r:
                if r.status == 200:
                    data = await r.json()
                    self.is_gateway_online = bool(data.get("ok", True))
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
    ) -> Optional[Dict[str, Any]]:
        """
        Sends an OpenAI-compatible chat completion request and returns a parsed JSON dictionary.
        Applies exponential backoff on 429/502/503. Falls back safely to None on failure.
        """
        sess = await self.get_session()
        # 2026-11-15: the gateway routes some calls to a model that
        # answers in prose ("**Analysis Summary:**", "**headline_zh:**",
        # plain sentences, even an empty string) -- 44x "200 OK returned
        # unparseable content" in one afternoon's app log. extract_json
        # then finds no braces and the whole digest/article call is
        # wasted. Force JSON mode (OpenAI-compatible standard): a
        # provider that rejects it answers 400, which is terminal here
        # and falls back exactly as an unparseable 200 does today.
        # classify_llm_error maps 400 to kind "unknown", never quota.
        payload = {
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        # Item 10 A3: never send a placeholder key. With no key configured
        # the request goes out without an Authorization header at all.
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        endpoint = f"{self.base_url}/chat/completions"
        self.total_requests += 1

        for attempt in range(self.max_retries + 1):
            try:
                async with self._get_semaphore():
                    async with sess.post(
                        endpoint,
                        json=payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=self.timeout_sec),
                    ) as resp:
                        status = resp.status
                        retry_after = resp.headers.get("Retry-After")
                        if status != 200:
                            # Diagnosis (gateway failure workstream): read
                            # the error body once and classify it. Only
                            # failure paths read the body; success paths
                            # never touch it. A body that cannot be read
                            # classifies from the status code alone.
                            err_body = await self._read_error_body(resp)
                            self.note_failure(classify_llm_error(
                                status, err_body,
                                headers=dict(resp.headers),
                                retry_after=retry_after,
                            ))
                        if status == 429:
                            # Observed rate-limit signal (F4): start the
                            # cooldown even if the retry later succeeds.
                            self.note_rate_limit(retry_after)

                        if status == 200:
                            body = await resp.json()
                            self.is_gateway_online = True
                            # A 200 proves a provider has quota right now.
                            self.note_success()
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
                            return None

                        if status in _RETRY_STATUSES and attempt < self.max_retries:
                            self.retried_requests += 1
                            delay = compute_backoff(attempt, retry_after)
                            logger.info(
                                "OmniRoute status %d on attempt %d/%d. Backoff %.2fs",
                                status, attempt + 1, self.max_retries, delay
                            )
                            await asyncio.sleep(delay)
                            continue

                        # Terminal non-retryable error (e.g. 401, 404, or exhausted retries)
                        self.failed_requests += 1
                        logger.warning("OmniRoute request terminated with HTTP %d (attempt %d)", status, attempt)
                        return None

            except aiohttp.ClientConnectorError as exc:
                self.failed_requests += 1
                self.is_gateway_online = False
                self.note_failure({"kind": "connection", "provider": None, "status": None, "detail": str(exc)[:200]})
                logger.debug("OmniRoute gateway offline (connection refused): %s", exc)
                return None
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                if attempt < self.max_retries:
                    self.retried_requests += 1
                    delay = compute_backoff(attempt)
                    logger.debug("OmniRoute connection error (%s). Retrying in %.2fs...", exc, delay)
                    await asyncio.sleep(delay)
                else:
                    self.failed_requests += 1
                    self.is_gateway_online = False
                    self.note_failure({"kind": "connection", "provider": None, "status": None, "detail": str(exc)[:200]})
                    logger.warning("OmniRoute gateway unreachable after %d retries: %s", self.max_retries, exc)
                    return None
            except Exception as e:
                self.failed_requests += 1
                logger.error("Unexpected error in OmniRouteClient: %s", e)
                return None

        self.failed_requests += 1
        return None

    async def close(self) -> None:
        """Properly closes underlying aiohttp session to prevent resource leaks."""
        if self._session and not self._session.closed and self._owns_session:
            await self._session.close()
            self._session = None

    def close_sync(self) -> None:
        """Synchronously closes underlying session or schedules close on loop."""
        if self._session and not self._session.closed and self._owns_session:
            try:
                loop = None
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    pass
                if loop and loop.is_running():
                    loop.create_task(self._session.close())
                elif self._session_loop is None or not self._session_loop.is_closed():
                    asyncio.run(self._session.close())
            except Exception as e:
                logger.debug("Failed to close session synchronously: %s", e)
            self._session = None

    def __del__(self) -> None:
        try:
            self.close_sync()
        except Exception as e:
            logger.debug("Failed to close session in destructor: %s", e)

