"""
src/intelligence/gemini_client.py - Direct Google Gemini REST Client
Communicates directly with Google Generative Language API (generateContent /
streamGenerateContent SSE) over aiohttp without any local gateway proxy.
"""
from __future__ import annotations

import asyncio
from datetime import date
import json
import logging
import math
import os
import random
import re
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
import weakref
from typing import Any, Callable, Dict, List, Optional, Tuple
import aiohttp

logger = logging.getLogger(__name__)

DEFAULT_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_GEMINI_MODEL = "gemini-3.1-flash-lite"

_RETRY_STATUSES = {429, 502, 503}
_RATE_LIMIT_COOLDOWN_SEC = 300.0
_QUOTA_RECORD_TTL_SEC = 86400.0

_THINK_CLOSED = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_THINK_OPEN = re.compile(r"<think>.*\Z", re.DOTALL | re.IGNORECASE)
_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)

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
    "spending cap",
    "monthly spending cap",
)

_RETRY_HINT_RE = re.compile(
    r"(?:try again in|retry (?:after|in))\s*:?\s*((?:[^.;\n]|\.(?=\d)){1,40})",
    re.IGNORECASE,
)
_RETRY_UNIT_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(d(?:ays?)?|h(?:ours?|rs?)?|m(?:in(?:ute)?s?)?|s(?:ec(?:ond)?s?)?)\b",
    re.IGNORECASE,
)


def resolve_gemini_model(model: Any, default: str = DEFAULT_GEMINI_MODEL) -> str:
    """Resolves a configured model alias ('auto', 'gemini/model-id', etc.) to a concrete Gemini model ID."""
    m = str(model or "").strip()
    if not m:
        return default
    lowered = m.lower()
    if lowered == "auto" or lowered.startswith("auto/"):
        return default
    if lowered.startswith("gemini/"):
        stripped = m[len("gemini/"):].strip()
        return stripped or default
    return m


def _looks_like_format_rejection(err_body: Any) -> bool:
    """True when an HTTP 400/422 body indicates JSON mode (responseMimeType) rejection."""
    try:
        text = json.dumps(err_body, ensure_ascii=False) if isinstance(err_body, dict) else str(err_body or "")
    except Exception:
        text = str(err_body or "")
    lowered = text.lower()
    return (
        "responsemimetype" in lowered
        or "response_mime_type" in lowered
        or "response_format" in lowered
        or "response format" in lowered
        or "json_object" in lowered
        or "json mode" in lowered
        or "application/json" in lowered
    )


def extract_json(text: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Defensively strips reasoning tags (<think>...</think>), markdown code fences,
    and extracts a valid JSON dictionary {...}.
    Returns None if no valid JSON dictionary can be parsed.
    """
    if not text or not isinstance(text, str):
        return None

    s = _THINK_CLOSED.sub("", text)
    s = _THINK_OPEN.sub("", s)
    stripped = s.strip()

    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            obj = json.loads(stripped)
            if isinstance(obj, dict):
                return obj
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

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
    """Computes randomized exponential backoff with jitter, honoring Retry-After if valid."""
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


def _error_body_text(body: Any) -> str:
    """Flattens a JSON or text error payload into a lowercase string for classification."""
    if body is None:
        return ""
    if isinstance(body, str):
        return body.lower()
    if isinstance(body, dict):
        parts: List[str] = []

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


def _parse_duration_seconds(raw: Any) -> Optional[float]:
    """Parses protobuf/human retryDelay strings like '67152s', '12.5s', or '2h 5m' into seconds."""
    if not isinstance(raw, str):
        return None
    s = raw.strip().lower()
    if not s:
        return None
    try:
        if s.endswith("ms"):
            return float(s[:-2]) / 1000.0
        if s.endswith("s") and s[:-1].replace(".", "", 1).isdigit():
            return float(s[:-1])
    except (TypeError, ValueError):
        pass
    total = 0.0
    found = False
    for num, unit in _RETRY_UNIT_RE.findall(s):
        found = True
        val = float(num)
        if unit.startswith("d"):
            total += val * 86400.0
        elif unit.startswith("h"):
            total += val * 3600.0
        elif unit.startswith("m"):
            total += val * 60.0
        else:
            total += val
    return total if found else None


def _retry_window_seconds(text: str) -> Optional[float]:
    """Seconds until throttle clears from a natural-language retry hint."""
    m = _RETRY_HINT_RE.search(text)
    if not m:
        return None
    return _parse_duration_seconds(m.group(1))


def _extract_gemini_detail_signals(body: Any) -> Tuple[bool, Optional[float]]:
    """Inspects structured Gemini error.details[] for QuotaFailure daily markers and RetryInfo delay."""
    if not isinstance(body, dict):
        return False, None
    err_obj = body.get("error") if isinstance(body.get("error"), dict) else body
    details = err_obj.get("details")
    if not isinstance(details, list):
        return False, None
    is_daily_quota = False
    retry_delay_sec: Optional[float] = None
    for item in details:
        if not isinstance(item, dict):
            continue
        if "retryDelay" in item:
            parsed = _parse_duration_seconds(item.get("retryDelay"))
            if parsed is not None:
                retry_delay_sec = parsed if retry_delay_sec is None else max(retry_delay_sec, parsed)
        violations = item.get("violations")
        if isinstance(violations, list):
            for v in violations:
                if not isinstance(v, dict):
                    continue
                qid = str(v.get("quotaId") or "").lower()
                if "perday" in qid or "daily" in qid:
                    is_daily_quota = True
    return is_daily_quota, retry_delay_sec


def classify_llm_error(
    status: Optional[int],
    body: Any = None,
    headers: Optional[Dict[str, Any]] = None,
    retry_after: Optional[str] = None,
) -> Dict[str, Any]:
    """Classifies a failed Gemini call into quota / transient / auth / unknown."""
    text = _error_body_text(body)
    result: Dict[str, Any] = {
        "kind": "unknown",
        "provider": "gemini",
        "status": status,
        "detail": text[:200],
    }
    if status is None:
        return result
    if status == 402:
        result["kind"] = "quota"
        return result
    if status in (401, 403):
        result["kind"] = "auth"
        return result
    if status == 400 and ("api_key_invalid" in text or "api key not valid" in text):
        result["kind"] = "auth"
        return result
    if status != 429:
        return result

    is_daily_detail, detail_delay = _extract_gemini_detail_signals(body)
    if is_daily_detail or any(pat in text for pat in _TERMINAL_CREDIT_PATTERNS):
        result["kind"] = "quota"
        return result

    if detail_delay is not None:
        result["kind"] = "quota" if detail_delay >= 3600.0 else "transient"
        return result

    window = _retry_window_seconds(text)
    if window is not None:
        result["kind"] = "quota" if window >= 3600.0 else "transient"
        return result

    if retry_after is not None:
        try:
            val = float(retry_after)
            if val > 0:
                result["kind"] = "quota" if val >= 3600.0 else "transient"
                return result
        except (TypeError, ValueError):
            pass

    # Bare 429 with no daily marker is treated as a transient per-minute limit.
    result["kind"] = "transient"
    return result


def _clean_key_input(raw_key: Any) -> str:
    if not isinstance(raw_key, str):
        return ""
    cleaned = "".join(ch for ch in raw_key.strip() if ord(ch) >= 0x20 and ord(ch) != 0x7F)
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in ("'", '"'):
        cleaned = cleaned[1:-1].strip()
    return cleaned


def probe_gemini_api_key(
    raw_key: str,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: float = 4.0,
) -> Dict[str, Any]:
    """Live-probes a Google Gemini API key via GET /v1beta/models/{model} (0 tokens).

    Never logs or returns the key string itself. HTTP 429 reports ok=False and
    explicitly unconfirmed (never claims the key is valid).
    """
    key = _clean_key_input(raw_key)
    if not key:
        return {"ok": False, "message": "API key cannot be empty", "latency_ms": 0}
    if not key.isascii():
        return {"ok": False, "message": "API key contains invalid non-ASCII characters", "latency_ms": 0}
    if len(key) < 8:
        return {"ok": False, "message": "API key length is suspiciously short", "latency_ms": 0}

    resolved_base = (base_url or os.getenv("LLM_BASE_URL") or DEFAULT_GEMINI_BASE_URL).rstrip("/")
    resolved_model = resolve_gemini_model(model or os.getenv("LLM_MODEL_COMMANDER", DEFAULT_GEMINI_MODEL))
    urls = [f"{resolved_base}/models/{resolved_model}"]
    fallback_list_url = f"{resolved_base}/models"

    t0 = time.perf_counter()
    for idx in range(2):
        target_url = urls[idx]
        req = urllib.request.Request(
            target_url,
            headers={
                "x-goog-api-key": key,
                "User-Agent": "TradeBot0-Validator/3.0",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                elapsed_ms = int((time.perf_counter() - t0) * 1000)
                if resp.status in (200, 201):
                    return {"ok": True, "message": f"Verified ({elapsed_ms}ms)", "latency_ms": elapsed_ms}
                return {"ok": False, "message": f"Unexpected status {resp.status}", "latency_ms": elapsed_ms}
        except urllib.error.HTTPError as he:
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            err_body = ""
            try:
                err_body = (he.read(2048) or b"").decode("utf-8", errors="replace")
            except Exception:
                err_body = ""
            finally:
                try:
                    he.close()
                except Exception:
                    pass
            if he.code == 404 and idx == 0:
                urls.append(fallback_list_url)
                continue
            if he.code in (401, 403):
                return {"ok": False, "message": f"Invalid Key / Unauthorized (HTTP {he.code})", "latency_ms": elapsed_ms}
            if he.code == 400 and ("API_KEY_INVALID" in err_body or "api key not valid" in err_body.lower()):
                return {"ok": False, "message": "Invalid Key / Unauthorized (HTTP 400)", "latency_ms": elapsed_ms}
            if he.code == 429:
                return {
                    "ok": False,
                    "message": "Key status unconfirmed (rate limited, HTTP 429) — retry later",
                    "latency_ms": elapsed_ms,
                }
            return {"ok": False, "message": f"Gemini API error (HTTP {he.code})", "latency_ms": elapsed_ms}
        except (urllib.error.URLError, socket.timeout, TimeoutError):
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            return {"ok": False, "message": f"Connection timed out or offline ({elapsed_ms}ms)", "latency_ms": elapsed_ms}
        except Exception as exc:
            return {"ok": False, "message": f"Validation issue: {type(exc).__name__}", "latency_ms": 0}
    return {"ok": False, "message": "Model metadata endpoint unavailable", "latency_ms": int((time.perf_counter() - t0) * 1000)}


class GeminiClient:
    """
    Direct, asynchronous Google Gemini Generative Language API client.
    Supports concurrency limits, exponential jitter backoff on transient errors,
    per-event-loop aiohttp sessions, SSE progress streaming, and offline fallback.
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
        raw_url = base_url or os.getenv("LLM_BASE_URL") or DEFAULT_GEMINI_BASE_URL
        self.base_url = raw_url.rstrip("/")
        self.root_url = self.base_url

        env_key = os.getenv("GEMINI_API_KEY") or ""
        raw_k = api_key if api_key is not None else env_key
        cleaned_k = _clean_key_input(raw_k)
        self.api_key: Optional[str] = cleaned_k if cleaned_k else None

        self.model_ingest = resolve_gemini_model(model_ingest or os.getenv("LLM_MODEL_INGEST") or DEFAULT_GEMINI_MODEL)
        self.model_commander = resolve_gemini_model(model_commander or os.getenv("LLM_MODEL_COMMANDER") or DEFAULT_GEMINI_MODEL)

        try:
            env_conc = int(os.getenv("LLM_MAX_CONCURRENT_REQUESTS", str(max_concurrent)))
        except (TypeError, ValueError):
            env_conc = int(max_concurrent)
        self.max_concurrent = max(1, env_conc)

        try:
            env_to = float(os.getenv("LLM_REQUEST_TIMEOUT_SEC", str(timeout_sec)))
        except (TypeError, ValueError):
            env_to = float(timeout_sec)
        self.timeout_sec = env_to if (math.isfinite(env_to) and env_to > 0.0) else max(1.0, float(timeout_sec))

        try:
            env_retries = int(os.getenv("LLM_MAX_RETRIES", str(max_retries)))
        except (TypeError, ValueError):
            env_retries = int(max_retries)
        self.max_retries = max(0, env_retries)

        self._sem = asyncio.Semaphore(self.max_concurrent)
        self._sems: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore]" = weakref.WeakKeyDictionary()
        self._session = session
        self._session_loop: Optional[asyncio.AbstractEventLoop] = None
        self._sessions: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, Any]" = weakref.WeakKeyDictionary()
        self._sessions_lock = threading.Lock()
        self._shutdown_event = threading.Event()
        self._owns_session = session is None
        self._json_mode_unsupported: set = set()

        self.is_gateway_online: bool = False
        self.last_health_check_ts: float = 0.0
        self.total_requests: int = 0
        self.successful_requests: int = 0
        self.failed_requests: int = 0
        self.retried_requests: int = 0
        self.total_tokens_used: int = 0
        self._quota_day: date = date.today()
        self.total_tokens_saved: int = 0
        self.total_dedup_hits: int = 0

        _quota_env = os.getenv("DAILY_TOKEN_QUOTA")
        try:
            self.daily_quota_limit: Optional[int] = int(_quota_env) if _quota_env is not None else None
        except (TypeError, ValueError):
            self.daily_quota_limit = None

        self._rate_limit_until: float = 0.0
        self._quota_lock = threading.Lock()
        self.last_failure: Optional[Dict[str, Any]] = None
        self._quota_failures: Dict[str, float] = {}
        self._unattributed_quota_ts: Optional[float] = None

    def update_api_key(self, raw_key: Optional[str]) -> None:
        """Hot-reloads the active Gemini API key and clears stale quota/error state."""
        cleaned = _clean_key_input(raw_key or "")
        with self._quota_lock:
            self.api_key = cleaned if cleaned else None
            self.last_failure = None
            self._quota_failures.clear()
            self._unattributed_quota_ts = None
            self._rate_limit_until = 0.0
        if not self.api_key:
            self.is_gateway_online = False

    def set_models(
        self,
        model_ingest: Optional[str] = None,
        model_commander: Optional[str] = None,
    ) -> None:
        """Hot-updates active Gemini model identifiers and clears stale per-model quota state on change."""
        with self._quota_lock:
            changed = False
            if model_ingest is not None:
                resolved_ingest = resolve_gemini_model(model_ingest)
                if resolved_ingest != self.model_ingest:
                    self.model_ingest = resolved_ingest
                    changed = True
            if model_commander is not None:
                resolved_cmd = resolve_gemini_model(model_commander)
                if resolved_cmd != self.model_commander:
                    self.model_commander = resolved_cmd
                    changed = True
            if changed:
                self._quota_failures.clear()
                self._unattributed_quota_ts = None
                self._rate_limit_until = 0.0
                self.last_failure = None

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
        tok: Optional[int] = None
        if "totalTokenCount" in usage:
            try:
                tok = int(usage.get("totalTokenCount", 0))
            except (TypeError, ValueError):
                tok = None
        elif "promptTokenCount" in usage or "candidatesTokenCount" in usage:
            try:
                tok = int(usage.get("promptTokenCount", 0) or 0) + int(usage.get("candidatesTokenCount", 0) or 0)
            except (TypeError, ValueError):
                tok = None
        elif "total_tokens" in usage:
            try:
                tok = int(usage.get("total_tokens", 0))
            except (TypeError, ValueError):
                tok = None
        if tok is None:
            return
        with self._quota_lock:
            self._maybe_rollover_daily_quota_locked()
            self.total_tokens_used += max(0, tok)

    def record_dedup_hit(self) -> None:
        """Records one SHA-256 deduplication hit (never fabricates saved tokens)."""
        self.total_dedup_hits += 1

    def record_tokens_saved(self, tokens: int) -> None:
        """Legacy compatibility hook for tests; counts saved tokens only when explicitly supplied."""
        if tokens > 0:
            self.total_tokens_saved += int(tokens)

    def note_rate_limit(self, retry_after: Optional[str] = None) -> None:
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
        with self._quota_lock:
            return time.monotonic() < self._rate_limit_until

    def is_over_quota(self) -> bool:
        with self._quota_lock:
            self._maybe_rollover_daily_quota_locked()
            if self.daily_quota_limit is not None and self.daily_quota_limit > 0:
                if self.total_tokens_used >= self.daily_quota_limit:
                    return True
            return time.monotonic() < self._rate_limit_until

    def note_failure(self, classification: Dict[str, Any]) -> None:
        try:
            if not isinstance(classification, dict):
                return
            kind = classification.get("kind") or "unknown"
            provider = classification.get("provider") or "gemini"
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
                    self._quota_failures[str(provider)] = now
                    self._unattributed_quota_ts = now
        except Exception as e:
            logger.debug("Failed to record LLM failure classification: %s", e)

    def note_success(self) -> None:
        try:
            with self._quota_lock:
                self._quota_failures.clear()
                self._unattributed_quota_ts = None
        except Exception as e:
            logger.debug("Failed to clear quota records on success: %s", e)

    def is_daily_budget_exhausted(self) -> bool:
        with self._quota_lock:
            self._maybe_rollover_daily_quota_locked()
            limit = self.daily_quota_limit
            return limit is not None and limit > 0 and self.total_tokens_used >= limit

    def has_quota_failures(self) -> bool:
        now = time.monotonic()
        with self._quota_lock:
            if self._unattributed_quota_ts is not None and (now - self._unattributed_quota_ts) <= _QUOTA_RECORD_TTL_SEC:
                return True
            return any((now - ts) <= _QUOTA_RECORD_TTL_SEC for ts in self._quota_failures.values())

    def is_all_providers_quota_exhausted(self, configured_providers: Any = ("gemini",)) -> bool:
        try:
            if configured_providers is None:
                return self.has_quota_failures()
            configured = [str(p).lower().strip() for p in configured_providers if p]
            if not configured:
                return False
            return self.has_quota_failures()
        except Exception as e:
            logger.debug("Quota-exhaustion check failed: %s", e)
            return False

    def get_quota_pct(self) -> Optional[float]:
        with self._quota_lock:
            self._maybe_rollover_daily_quota_locked()
            if self.daily_quota_limit is None or self.daily_quota_limit <= 0:
                return None
            remaining = max(0, self.daily_quota_limit - self.total_tokens_used)
            return round((remaining / self.daily_quota_limit) * 100.0, 1)

    async def _read_error_body(self, resp: Any) -> Any:
        try:
            return await resp.json()
        except Exception:
            pass
        try:
            text = await resp.text()
            return text[:4000] if isinstance(text, str) else None
        except Exception:
            return None

    def _get_semaphore(self) -> asyncio.Semaphore:
        try:
            current_loop = asyncio.get_running_loop()
            with self._sessions_lock:
                sem = self._sems.get(current_loop)
                if sem is None:
                    sem = asyncio.Semaphore(self.max_concurrent)
                    self._sems[current_loop] = sem
                self._sem = sem
                return sem
        except RuntimeError:
            return self._sem

    async def get_session(self) -> aiohttp.ClientSession:
        """Returns the aiohttp ClientSession owned by the calling event loop."""
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
            self._session = sess
            self._owns_session = True
            return sess

    async def close_loop_session(self) -> None:
        """Closes and forgets the aiohttp session and semaphore owned by the current event loop."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        with self._sessions_lock:
            self._sems.pop(loop, None)
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
        self._shutdown_event.set()
        self.is_gateway_online = False

    def is_shutting_down(self) -> bool:
        return sys.is_finalizing() or self._shutdown_event.is_set()

    @staticmethod
    def _extract_gemini_text(body: Dict[str, Any]) -> Tuple[str, Optional[str]]:
        """Extracts non-thought text from Gemini candidates[0].content.parts[] and finishReason."""
        candidates = body.get("candidates")
        if not isinstance(candidates, list) or not candidates or not isinstance(candidates[0], dict):
            feedback = body.get("promptFeedback")
            if isinstance(feedback, dict) and feedback.get("blockReason"):
                logger.warning("Gemini blocked response: blockReason=%s", feedback.get("blockReason"))
            return "", None

        cand = candidates[0]
        finish_reason = cand.get("finishReason")
        if finish_reason in ("MAX_TOKENS", "SAFETY", "RECITATION", "PROHIBITED_CONTENT"):
            logger.warning("Gemini candidate finishReason=%s", finish_reason)

        content_obj = cand.get("content")
        parts = content_obj.get("parts") if isinstance(content_obj, dict) else None
        if not isinstance(parts, list):
            return "", finish_reason

        chunks: List[str] = []
        for part in parts:
            if not isinstance(part, dict):
                continue
            if part.get("thought") is True:
                continue
            txt = part.get("text")
            if isinstance(txt, str) and txt:
                chunks.append(txt)
        return "".join(chunks), finish_reason

    async def check_health(self) -> bool:
        """Checks Gemini API reachability and key validity using GET /v1beta/models/{model}."""
        if self.is_shutting_down():
            self.is_gateway_online = False
            return False
        api_key = self.api_key
        if not api_key:
            self.is_gateway_online = False
            return False
        if not api_key.isascii():
            self.note_failure({"kind": "auth", "provider": "gemini", "status": 401, "detail": "Non-ASCII API key"})
            self.is_gateway_online = False
            return False
        try:
            sess = await self.get_session()
            model_id = resolve_gemini_model(self.model_commander)
            url = f"{self.base_url}/models/{model_id}"
            headers = {"x-goog-api-key": api_key, "Accept": "application/json"}
            async with sess.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=3.0)) as r:
                if r.status == 200:
                    self.is_gateway_online = True
                    self.note_success()
                else:
                    err_body = await self._read_error_body(r)
                    retry_after = r.headers.get("Retry-After") if hasattr(r, "headers") else None
                    self.note_failure(classify_llm_error(r.status, err_body, retry_after=retry_after))
                    self.is_gateway_online = False
        except Exception as e:
            logger.debug("Gemini health check failed: %s", e)
            self.note_failure({"kind": "connection", "provider": "gemini", "status": None, "detail": str(e)[:200]})
            self.is_gateway_online = False

        self.last_health_check_ts = asyncio.get_running_loop().time()
        return self.is_gateway_online

    @staticmethod
    def _build_gemini_payload(
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
        use_json_mode: bool,
    ) -> Dict[str, Any]:
        gen_cfg: Dict[str, Any] = {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        }
        if use_json_mode:
            gen_cfg["responseMimeType"] = "application/json"
        payload: Dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": gen_cfg,
        }
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}
        return payload

    @staticmethod
    async def _iter_sse_lines(content: Any, max_line_bytes: int = 4 * 1024 * 1024):
        """Yields decoded SSE lines from an aiohttp StreamReader without the 64 KiB readline limit."""
        if hasattr(content, "iter_any"):
            buf = bytearray()
            async for chunk in content.iter_any():
                if not chunk:
                    continue
                if isinstance(chunk, str):
                    chunk_bytes = chunk.encode("utf-8", errors="replace")
                else:
                    chunk_bytes = bytes(chunk)
                buf.extend(chunk_bytes)
                while True:
                    nl_idx = buf.find(b"\n")
                    if nl_idx == -1:
                        break
                    raw_line = bytes(buf[:nl_idx])
                    del buf[:nl_idx + 1]
                    if len(raw_line) > max_line_bytes:
                        logger.warning("Gemini SSE line exceeded %d bytes; truncated", max_line_bytes)
                        raw_line = raw_line[:max_line_bytes]
                    yield raw_line.decode("utf-8", errors="replace").rstrip("\r")
                if len(buf) > max_line_bytes:
                    logger.warning("Gemini SSE frame exceeded %d bytes without newline", max_line_bytes)
                    del buf[:-max_line_bytes]
            if buf:
                yield bytes(buf[:max_line_bytes]).decode("utf-8", errors="replace").rstrip("\r")
            return
        async for raw_line in content:
            if isinstance(raw_line, (bytes, bytearray)):
                yield bytes(raw_line).decode("utf-8", errors="replace").rstrip("\r\n")
            else:
                yield str(raw_line).rstrip("\r\n")

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
        Sends a Gemini generateContent request and returns a parsed JSON dictionary.
        Applies exponential backoff on transient 429/502/503. Returns None cleanly on failure.
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
        api_key = self.api_key
        if api_key and not api_key.isascii():
            self.note_failure({"kind": "auth", "provider": "gemini", "status": 401, "detail": "Non-ASCII API key"})
            self.is_gateway_online = False
            self.total_requests += 1
            self.failed_requests += 1
            return None

        sess = await self.get_session()
        call_timeout = timeout_sec if timeout_sec is not None else self.timeout_sec
        resolved_model = resolve_gemini_model(model)
        raw_model_key = str(model or "").strip()

        with self._sessions_lock:
            skip_json_mode = (
                resolved_model in self._json_mode_unsupported
                or (raw_model_key in self._json_mode_unsupported if raw_model_key else False)
            )
        payload = self._build_gemini_payload(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            use_json_mode=not skip_json_mode,
        )
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["x-goog-api-key"] = api_key

        use_stream = bool(stream_progress)
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
            endpoint = (
                f"{self.base_url}/models/{resolved_model}:streamGenerateContent?alt=sse"
                if use_stream
                else f"{self.base_url}/models/{resolved_model}:generateContent"
            )
            try:
                if getattr(sess, "closed", False):
                    sess = await self.get_session()
                _emit("connecting", 18, "Connecting to Gemini AI")
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

                        if status == 200:
                            ctype = str(resp.headers.get("Content-Type") or "").lower()
                            if use_stream and "text/event-stream" in ctype:
                                chunks: List[str] = []
                                total_chars = 0
                                target_chars = max(1200, int(max_tokens * 0.72))
                                last_pct = 28
                                usage_obj: Any = None
                                sse_error: Any = None
                                _emit("analyzing", 32, "Analyzing market context")
                                data_parts: List[str] = []

                                def _consume_sse_frame(frame: Any) -> bool:
                                    nonlocal usage_obj, sse_error, total_chars, last_pct
                                    if not isinstance(frame, dict):
                                        return False
                                    if frame.get("error"):
                                        sse_error = frame.get("error")
                                        return True
                                    if frame.get("usageMetadata"):
                                        usage_obj = frame.get("usageMetadata")
                                    elif frame.get("usage"):
                                        usage_obj = frame.get("usage")
                                    piece, _ = self._extract_gemini_text(frame)
                                    if piece:
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
                                    return False

                                async for raw_s in self._iter_sse_lines(resp.content):
                                    if self.is_shutting_down():
                                        return None
                                    line = raw_s.strip()
                                    if not line:
                                        if data_parts:
                                            joined = "\n".join(data_parts)
                                            data_parts.clear()
                                            if joined == "[DONE]":
                                                break
                                            try:
                                                frame = json.loads(joined)
                                            except Exception:
                                                frame = None
                                            if _consume_sse_frame(frame):
                                                break
                                        continue
                                    if line.startswith(":") or not line.startswith("data:"):
                                        continue
                                    seg = line[5:].strip()
                                    if not data_parts and seg == "[DONE]":
                                        break
                                    data_parts.append(seg)
                                    joined = "\n".join(data_parts)
                                    if joined == "[DONE]":
                                        data_parts.clear()
                                        break
                                    try:
                                        frame = json.loads(joined)
                                    except Exception:
                                        continue
                                    data_parts.clear()
                                    if _consume_sse_frame(frame):
                                        break

                                if data_parts and sse_error is None:
                                    joined = "\n".join(data_parts)
                                    data_parts.clear()
                                    if joined != "[DONE]":
                                        try:
                                            _consume_sse_frame(json.loads(joined))
                                        except Exception:
                                            pass

                                if sse_error is not None:
                                    err_payload = sse_error if isinstance(sse_error, dict) else {"error": str(sse_error)}
                                    raw_code = err_payload.get("code", 500) if isinstance(err_payload, dict) else 500
                                    try:
                                        err_status = int(raw_code)
                                    except (TypeError, ValueError):
                                        err_status = 500
                                    sse_body = {"error": err_payload}
                                    _, sse_delay = _extract_gemini_detail_signals(sse_body)
                                    sse_retry = str(sse_delay) if sse_delay is not None else None
                                    classification = classify_llm_error(err_status, sse_body, retry_after=sse_retry)
                                    self.note_failure(classification)
                                    if err_status == 429:
                                        self.note_rate_limit(sse_retry)
                                    if classification.get("kind") == "auth":
                                        self.is_gateway_online = False
                                    if (
                                        err_status in _RETRY_STATUSES
                                        and classification.get("kind") != "quota"
                                        and attempt < self.max_retries
                                    ):
                                        self.retried_requests += 1
                                        retry_delay = compute_backoff(attempt, sse_retry)
                                        _emit("retrying", 22, f"Gemini busy, retrying ({attempt + 1}/{self.max_retries})")
                                        logger.warning(
                                            "Gemini 200 SSE transient error (%d); backoff %.2fs",
                                            err_status,
                                            retry_delay,
                                        )
                                    else:
                                        self.failed_requests += 1
                                        logger.warning("Gemini 200 SSE emitted in-band error frame (%d): %s", err_status, str(sse_error)[:150])
                                        return None
                                else:
                                    content = "".join(chunks)
                                    if not content.strip():
                                        self.failed_requests += 1
                                        logger.warning("Gemini 200 SSE stream ended with empty content")
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
                                    logger.warning("Gemini 200 SSE returned unparseable content: %s", content[:150])
                                    need_repair = True
                            else:
                                _emit("receiving", 72, "Receiving AI response")
                                body = await self._parse_ok_json_body(resp)
                                if not isinstance(body, dict):
                                    self.failed_requests += 1
                                    logger.warning("Gemini 200 OK returned non-JSON or non-object body")
                                    return None
                                self.is_gateway_online = True
                                self.note_success()
                                self._record_token_usage(body.get("usageMetadata") or body.get("usage"))
                                _emit("parsing", 90, "Parsing & validating report")
                                content, finish_reason = self._extract_gemini_text(body)
                                if not content:
                                    self.failed_requests += 1
                                    logger.warning("Gemini 200 OK contained no text parts (finishReason=%s)", finish_reason)
                                    return None
                                parsed = extract_json(content)
                                if parsed is not None:
                                    self.successful_requests += 1
                                    return parsed
                                logger.warning("Gemini 200 OK returned unparseable content: %s", content[:150])
                                need_repair = True
                        elif (
                            status in (400, 422)
                            and use_stream
                            and not stream_retried
                            and not _looks_like_format_rejection(err_body)
                        ):
                            use_stream = False
                            stream_retried = True
                            retry_nonstream = True
                            _emit("waiting", 24, "Switching to standard response mode")
                            logger.info("Gemini rejected streaming mode (HTTP %d); retrying non-stream", status)
                        elif (
                            status in (400, 422)
                            and "responseMimeType" in (payload.get("generationConfig") or {})
                            and not format_retried
                            and _looks_like_format_rejection(err_body)
                        ):
                            payload["generationConfig"].pop("responseMimeType", None)
                            with self._sessions_lock:
                                if len(self._json_mode_unsupported) >= 128:
                                    self._json_mode_unsupported.clear()
                                self._json_mode_unsupported.add(resolved_model)
                                if raw_model_key:
                                    self._json_mode_unsupported.add(raw_model_key)
                            self.retried_requests += 1
                            format_retried = True
                            retry_format = True
                            logger.info("Model %s rejected responseMimeType (HTTP %d); retrying without JSON mode", resolved_model, status)
                        else:
                            if status == 429:
                                _, detail_delay = _extract_gemini_detail_signals(err_body)
                                if detail_delay is not None and not retry_after:
                                    retry_after = str(detail_delay)
                                self.note_rate_limit(retry_after)
                            classification = classify_llm_error(
                                status,
                                err_body,
                                headers=dict(resp.headers),
                                retry_after=retry_after,
                            )
                            self.note_failure(classification)
                            if classification.get("kind") == "auth":
                                self.is_gateway_online = False
                            if (
                                status in _RETRY_STATUSES
                                and classification.get("kind") != "quota"
                                and attempt < self.max_retries
                            ):
                                self.retried_requests += 1
                                retry_delay = compute_backoff(attempt, retry_after)
                                _emit("retrying", 22, f"Gemini busy, retrying ({attempt + 1}/{self.max_retries})")
                                logger.info(
                                    "Gemini status %d on attempt %d/%d. Backoff %.2fs",
                                    status, attempt + 1, self.max_retries, retry_delay,
                                )
                            else:
                                self.failed_requests += 1
                                logger.warning("Gemini request terminated with HTTP %d (attempt %d)", status, attempt)
                                return None

                if need_repair:
                    _emit("repairing", 94, "Formatting response structure")
                    repair_endpoint = f"{self.base_url}/models/{resolved_model}:generateContent"
                    repaired = await self._repair_json_once(
                        sess, repair_endpoint, headers, payload, call_timeout
                    )
                    if repaired is not None:
                        self.successful_requests += 1
                        return repaired
                    self.failed_requests += 1
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
                self.note_failure({"kind": "connection", "provider": "gemini", "status": None, "detail": str(exc)[:200]})
                logger.debug("Gemini API unreachable (connection error): %s", exc)
                return None
            except asyncio.TimeoutError as exc:
                if self.is_shutting_down():
                    return None
                timeout_retries = 0 if call_timeout >= 60.0 else min(1, self.max_retries)
                if attempt < timeout_retries:
                    self.retried_requests += 1
                    delay = compute_backoff(attempt)
                    logger.debug("Gemini request timed out (%s). Retrying once in %.2fs...", exc, delay)
                    await asyncio.sleep(delay)
                    attempt += 1
                else:
                    self.failed_requests += 1
                    self.note_failure({"kind": "connection", "provider": "gemini", "status": None, "detail": f"timeout ({call_timeout}s)"})
                    logger.warning("Gemini request timed out after %.1fs (attempt %d)", call_timeout, attempt + 1)
                    return None
            except aiohttp.ClientError as exc:
                if self.is_shutting_down():
                    return None
                if attempt < self.max_retries:
                    self.retried_requests += 1
                    delay = compute_backoff(attempt)
                    logger.debug("Gemini HTTP client error (%s). Retrying in %.2fs...", exc, delay)
                    await asyncio.sleep(delay)
                    attempt += 1
                else:
                    self.failed_requests += 1
                    self.is_gateway_online = False
                    self.note_failure({"kind": "connection", "provider": "gemini", "status": None, "detail": str(exc)[:200]})
                    logger.warning("Gemini API unreachable after %d retries: %s", self.max_retries, exc)
                    return None
            except RuntimeError as e:
                err_txt = str(e)
                if (
                    self.is_shutting_down()
                    or "cannot schedule new futures after shutdown" in err_txt
                    or "Event loop is closed" in err_txt
                ):
                    logger.debug("GeminiClient request aborted during shutdown: %s", e)
                    return None
                self.failed_requests += 1
                logger.error("Unexpected error in GeminiClient: %s", e)
                return None
            except Exception as e:
                if self.is_shutting_down():
                    logger.debug("GeminiClient request aborted during shutdown: %s", e)
                    return None
                self.failed_requests += 1
                logger.error("Unexpected error in GeminiClient: %s", e)
                return None

        self.failed_requests += 1
        return None

    async def _parse_ok_json_body(self, resp: Any) -> Optional[Dict[str, Any]]:
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
                logger.debug("Gemini 200 fallback text JSON parse failed: %s", e)
            return None

    async def _repair_json_once(
        self,
        sess: Any,
        endpoint: str,
        headers: Dict[str, str],
        payload: Dict[str, Any],
        timeout_sec: float,
    ) -> Optional[Dict[str, Any]]:
        """One bounded repair attempt after a 200 OK with unparseable prose content."""
        if self.is_shutting_down():
            return None
        try:
            if getattr(sess, "closed", False):
                sess = await self.get_session()
            repair_payload = dict(payload)
            orig_contents = list(payload.get("contents", []))
            repair_payload["contents"] = orig_contents + [
                {"role": "model", "parts": [{"text": "(Previous response was not valid JSON.)"}]},
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": (
                                "Your previous reply was not a JSON object. "
                                "Reply again with ONLY a JSON object, no other "
                                "text, no markdown, no explanation. Use the exact "
                                "same schema and fields as the original request."
                            )
                        }
                    ],
                },
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
                            _, r_delay = _extract_gemini_detail_signals(err_body)
                            if r_delay is not None and not retry_after:
                                retry_after = str(r_delay)
                            self.note_rate_limit(retry_after)
                        r_class = classify_llm_error(
                            resp.status, err_body, headers=dict(resp.headers), retry_after=retry_after
                        )
                        if r_class.get("kind") == "auth":
                            self.is_gateway_online = False
                        if resp.status in (401, 402, 403, 429) or r_class.get("kind") == "auth":
                            self.note_failure(r_class)
                        return None
                    body = await self._parse_ok_json_body(resp)
                    if not isinstance(body, dict):
                        return None
                    self._record_token_usage(body.get("usageMetadata") or body.get("usage"))
                    content, _ = self._extract_gemini_text(body)
                    parsed = extract_json(content)
                    if parsed is not None:
                        logger.info("Gemini repair retry returned usable JSON")
                        return parsed
                    logger.warning("Gemini repair retry still unparseable: %s", content[:150])
                    return None
        except Exception as e:
            logger.debug("Gemini repair retry failed: %s", e)
            return None

    def _all_sessions_with_loops(self) -> list:
        with self._sessions_lock:
            pairs = list(self._sessions.items())
            self._sessions.clear()
            self._sems.clear()
            latest = self._session
            latest_loop = self._session_loop
            self._session = None
            self._session_loop = None
        if latest is not None and all(latest is not s for _, s in pairs):
            pairs.append((latest_loop, latest))
        return pairs

    def _all_sessions(self) -> list:
        return [s for _, s in self._all_sessions_with_loops()]

    async def close(self) -> None:
        for sess in self._all_sessions():
            if sess is not None and not sess.closed and self._owns_session:
                try:
                    await sess.close()
                except Exception as e:
                    logger.debug("Failed to close session: %s", e)

    def close_sync(self) -> None:
        if sys.is_finalizing():
            return
        pairs = self._all_sessions_with_loops()
        if not self._owns_session:
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
                        owner_loop.call_soon_threadsafe(
                            lambda l=owner_loop, s=sess: l.create_task(s.close()) if not s.closed else None
                        )
                elif running_loop is not None and running_loop.is_running():
                    running_loop.create_task(sess.close())
                else:
                    asyncio.run(sess.close())
            except Exception as e:
                logger.debug("Failed to close session synchronously: %s", e)

    def __del__(self) -> None:
        if sys.is_finalizing():
            return
        try:
            self.close_sync()
        except Exception as e:
            logger.debug("Failed to close session in destructor: %s", e)
