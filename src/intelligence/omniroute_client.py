from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import re
from typing import Any, Dict, Optional
import aiohttp

logger = logging.getLogger(__name__)

_RETRY_STATUSES = {429, 502, 503}
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

        self.api_key = api_key or os.getenv("LLM_API_KEY", "sk-omni-local-gateway-key")
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
        self.daily_quota_limit: int = int(os.getenv("DAILY_TOKEN_QUOTA", "100000"))

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

    def is_over_quota(self) -> bool:
        """True once measured token usage reaches the daily quota.

        The quota is a soft display budget, not a limiter (item 12 / A4-4);
        callers use this to throttle the digest cadence, never to block a
        single request.
        """
        return self.daily_quota_limit > 0 and self.total_tokens_used >= self.daily_quota_limit

    def get_quota_pct(self) -> float:
        """Calculates dynamic available quota percentage against daily budget."""
        if self.daily_quota_limit <= 0:
            return 100.0
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
        payload = {
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
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

                        if status == 200:
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

