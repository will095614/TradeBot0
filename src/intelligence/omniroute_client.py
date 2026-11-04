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
        self._session = session
        self._owns_session = session is None

        # Telemetry & Status
        self.is_gateway_online: bool = False
        self.last_health_check_ts: float = 0.0
        self.total_requests: int = 0
        self.successful_requests: int = 0
        self.failed_requests: int = 0
        self.retried_requests: int = 0

    async def get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout_sec)
            self._session = aiohttp.ClientSession(timeout=timeout)
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
        except Exception:
            self.is_gateway_online = False

        self.last_health_check_ts = asyncio.get_event_loop().time()
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
                async with self._sem:
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
                            self.successful_requests += 1
                            choices = body.get("choices", [])
                            if choices and "message" in choices[0]:
                                content = choices[0]["message"].get("content", "")
                                parsed = extract_json(content)
                                if parsed is not None:
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
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    pass
                if loop and loop.is_running():
                    loop.create_task(self._session.close())
                else:
                    asyncio.run(self._session.close())
            except Exception:
                pass
            self._session = None

    def __del__(self) -> None:
        try:
            self.close_sync()
        except Exception:
            pass

