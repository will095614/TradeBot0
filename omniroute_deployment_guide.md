# OmniRoute Deployment & Integration Guide

> **Supplement to:** *Macro Commander & OmniRoute Intelligence Ingestion Workflow Plan (v2)*, Phase 2 (Tasks 2.1 - 2.3).
> **Research date:** 2026-11-04.
> **Upstream project:** `diegosouzapw/OmniRoute` (MIT-licensed, self-hosted, OpenAI-compatible AI gateway).
> **Version note:** A third-party test dated 2026-07-30 used **v3.8.48**; the project wiki also references a v3.9.0 LTS roadmap. Check the version you actually install (dashboard, or `omniroute status`) and read its release notes before upgrading.

**Confidence tags used in this document**

| Tag | Meaning |
|-----|---------|
| **[V]** | Verified against upstream docs / articles found during research (see *Sources*). |
| **[R]** | My recommendation or an assembled example. Built from verified flags but **not executed** here. Validate in your environment. |
| **[?]** | Not confirmed. Verify before relying on it. |

---

## 1. Quick Decisions (TL;DR)

| Topic | Recommendation | Basis |
|-------|----------------|-------|
| Endpoint | `http://localhost:20128/v1` (API and dashboard share port 20128 by default) | **[V]** |
| Install method | **Docker with a pinned tag/digest** for a persistent trading box; `npm i -g omniroute` for quick dev | **[V]** methods, **[R]** choice |
| Auth | Create an endpoint API key and set `REQUIRE_API_KEY=true`, even on localhost | **[R]** |
| Timeouts | Gateway default upstream timeout is **600 s**; the plan's client timeout is **60 s**. Set `REQUEST_TIMEOUT_MS` to about 55000 on a dedicated instance so abandoned calls do not keep burning upstream quota | **[V]** default, **[R]** value |
| `LLM_MODEL_INGEST` | A fast/cheap **combo** (or `auto/fast`) | **[V]** model names, **[R]** choice |
| `LLM_MODEL_COMMANDER` | A **pinned `priority` combo** with a fallback chain. Avoid `auto/*` for the veto-governing model (it is non-deterministic by design) | **[R]** |
| Upstream providers | Put at least one **official API-key provider** in the Commander combo. Do not depend only on free/web-session providers | **[R]** |
| JSON handling | Always apply the R2 defensive parser, even though OmniRoute parses `<think>` tags itself | **[V]** + plan R2 |

---

## 2. What OmniRoute Is (and what it means for this workflow)

OmniRoute is a local routing gateway built on Next.js. It exposes a single OpenAI-compatible surface (`/v1/*`) and routes requests across many upstream providers with format translation, fallback, token refresh, usage tracking, circuit breakers and a dashboard. **[V]**

Capabilities relevant to the plan:

- **Combos / fallback chains:** a "model" can be a named combo that tries several upstream models in order. **[V]**
- **Auto-Combo:** `model: "auto"` and `auto/<variant>` build a virtual combo per request. **[V]**
- **Think-tag parsing:** it parses `<think>...</think>` for reasoning models and keeps a reasoning-content replay cache. **[V]** Upstream variance still exists, so the client-side R2 parser stays mandatory.
- **Resilience:** per-provider circuit breakers, cooldown-aware retries, anti-thundering-herd locking, signature-based request de-duplication cache. **[V]**
- **Persistence:** everything (providers, combos, keys, usage) lives in a local SQLite file. **[V]**

```
 Arena app (aiohttp client)            OmniRoute (localhost:20128)             Upstream providers
 ---------------------------           -------------------------------         -------------------
 LLM_MODEL_INGEST    ----------------> combo "ingest-fast"   ---> provider A / B / C (fast, cheap)
 LLM_MODEL_COMMANDER ----------------> combo "commander-q"   ---> provider X (primary) -> Y (fallback)
        ^                                  | circuit breakers, cooldowns, usage log
        | defensive JSON parse (R2)        v
        +--- NEUTRAL fallback <------ gateway down / all upstreams failing
```

---

## 3. Prerequisites

| Item | Requirement | Tag |
|------|-------------|-----|
| Node.js (npm / source installs) | `>=22.0.0 <23` **or** `>=24.0.0 <27`. **Node 23 is excluded.** | **[V]** |
| Docker (container installs) | Docker Engine + compose plugin, or Docker Desktop on Windows | **[V]** |
| Disk | A persistent volume/directory for the SQLite DB. Losing it loses providers, combos and API keys | **[V]** |
| Memory | The Docker template sets `OMNIROUTE_MEMORY_MB=1024`; match container memory to the heap you set | **[V]** |
| Port | 20128 free on the host (or choose another with `--port` / `PORT`) | **[V]** |
| pnpm users | Run `pnpm approve-builds -g` and approve all, so native builds for `better-sqlite3` and `@swc/core` run | **[V]** |

---

## 4. Installation Methods

### 4.1 npm (simplest)

```bash
npm install -g omniroute
omniroute            # starts at http://localhost:20128, dashboard opens automatically
omniroute --no-open  # same, without opening a browser (use for services)
```

Related CLI (all **[V]**): `omniroute setup`, `omniroute doctor [--json] [--no-liveness]`, `omniroute status`, `omniroute logs --follow`, `omniroute update`, `omniroute providers {available|list|test|test-all|validate}`, `omniroute --port <n>`, `omniroute --mcp` (stdio MCP server).

### 4.2 Docker (recommended for a persistent service)

Minimal form from the project quick start **[V]**:

```bash
docker run -d --name omniroute -p 20128:20128 diegosouzapw/omniroute:latest
```

Hardened form, assembled from documented flags (restart policy, 40 s stop timeout, `/app/data` volume) **[V]** + loopback binding and pinned tag **[R]**:

```bash
docker run -d --name omniroute --restart unless-stopped \
  --stop-timeout 40 \
  -p 127.0.0.1:20128:20128 \
  --env-file ./omniroute.env \
  -v omniroute-data:/app/data \
  diegosouzapw/omniroute:<PINNED_TAG>
```

> Replace `<PINNED_TAG>` with a specific released version (or an image digest). `:latest` can change underneath a trading system. A published Railway template for this image is digest-pinned for the same reason. **[V]**

**Docker Compose example [R]:**

```yaml
services:
  omniroute:
    image: diegosouzapw/omniroute:<PINNED_TAG>
    container_name: omniroute
    restart: unless-stopped
    stop_grace_period: 40s
    ports:
      - "127.0.0.1:20128:20128"      # loopback only; remove "127.0.0.1:" only if you really need LAN access
    env_file: ./omniroute.env         # secrets live here (see section 6)
    environment:
      PORT: "20128"
      HOSTNAME: "0.0.0.0"             # inside the container
      DATA_DIR: /app/data
      NODE_ENV: production
      REQUIRE_API_KEY: "true"
      REQUEST_TIMEOUT_MS: "55000"
      OMNIROUTE_MEMORY_MB: "1024"
    volumes:
      - omniroute-data:/app/data
    healthcheck:
      test: ["CMD", "node", "-e", "fetch('http://127.0.0.1:20128/api/health').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 40s
volumes:
  omniroute-data:
```

Notes: `/api/health` is an unauthenticated liveness check that returns `{"ok":true}` and returns 503 while the service is still starting. **[V]** The healthcheck command itself is **[R]**; confirm the image has `node` on PATH (it is a Node application) and adjust if your tag differs.

### 4.3 From source **[V]**

```bash
git clone https://github.com/diegosouzapw/OmniRoute.git
cd OmniRoute
npm install            # auto-generates .env from .env.example on first run (never overwrites an existing .env)
npm run dev            # or: PORT=20128 DASHBOARD_PORT=20129 NEXT_PUBLIC_BASE_URL=http://localhost:20129 npm run dev
```

### 4.4 Desktop app (Windows / macOS / Linux) **[V]**

An Electron wrapper exists (Windows: NSIS installer + portable build). Installers are attached to GitHub Releases. Useful for a developer workstation; for a headless trading box prefer Docker.

### 4.5 Headless / scripted setup **[V]**

```bash
omniroute setup --non-interactive --password "$OMNIROUTE_PASSWORD"
omniroute setup --non-interactive --add-provider --provider openai --api-key "$OPENAI_API_KEY" --test-provider
omniroute providers test-all
omniroute doctor --json
```

---

## 5. First Run and Verification

1. Open `http://localhost:20128` and log in (see section 6 for the initial password).
2. **Dashboard > Providers > Add Provider:** connect at least one provider (API key, OAuth, or a no-key free provider).
3. **Dashboard > Endpoints:** create an **API key**. Put it in `LLM_API_KEY`.
4. **Dashboard > Combos:** create the two combos from section 9 (optional but recommended).
5. Verify from a shell:

```bash
curl http://localhost:20128/api/health                          # {"ok":true}  (unauthenticated liveness)
omniroute doctor                                                 # local diagnostics, no server needed
curl http://localhost:20128/v1/models -H "Authorization: Bearer $LLM_API_KEY"
curl http://localhost:20128/v1/chat/completions \
  -H "Authorization: Bearer $LLM_API_KEY" -H "Content-Type: application/json" \
  -d '{"model":"auto/fast","messages":[{"role":"user","content":"Reply with the single word OK"}]}'
```

All endpoints above are **[V]**. A third-party test saw `/v1/models` return 99 models on a fresh install before any provider was configured; do not assume a model in that list will be reachable until its provider is connected. **[V]**

Authenticated health detail (uptime, memory, circuit breakers, rate limits): `GET /api/monitoring/health` with a Bearer token. **[V]**

---

## 6. Environment Variables and Secrets

### 6.1 Secrets (generate once, store safely)

| Variable | Purpose | Generate with | Tag |
|----------|---------|---------------|-----|
| `JWT_SECRET` | Signs dashboard session cookies | `openssl rand -base64 48` | **[V]** |
| `API_KEY_SECRET` | AES key protecting API-key values at rest in SQLite | `openssl rand -hex 32` | **[V]** |
| `INITIAL_PASSWORD` | Bootstrap admin password. Change before first use, then rotate in Dashboard > Settings > Security | `openssl rand -base64 16` | **[V]** |
| `STORAGE_ENCRYPTION_KEY` (+ `STORAGE_ENCRYPTION_KEY_VERSION=v1`) | Encrypts stored provider credentials. **Losing this key means losing the encrypted data - back it up** | `openssl rand -hex 32` | **[V]** |
| `MACHINE_ID_SALT` | Stable machine identifier salt | any unique random string | **[V]** |
| `OMNIROUTE_WS_BRIDGE_SECRET` | WebSocket-bridge auth; documented as required in production | `openssl rand -base64 32` | **[V]** |

> **Doc inconsistency [V]:** one environment reference lists the `INITIAL_PASSWORD` default as `123456`, a deployment guide says it falls back to `CHANGEME` when unset. Either way, **set it explicitly**.

PowerShell equivalents for Windows **[R]**:

```powershell
function New-Secret([int]$Bytes = 32, [switch]$Base64) {
  $b = New-Object byte[] $Bytes
  [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
  if ($Base64) { [Convert]::ToBase64String($b) } else { ($b | ForEach-Object { $_.ToString('x2') }) -join '' }
}
"JWT_SECRET=$(New-Secret 48 -Base64)"
"API_KEY_SECRET=$(New-Secret 32)"
"STORAGE_ENCRYPTION_KEY=$(New-Secret 32)"
"OMNIROUTE_WS_BRIDGE_SECRET=$(New-Secret 32 -Base64)"
```

### 6.2 Runtime configuration

| Variable | Default / example | Purpose | Tag |
|----------|-------------------|---------|-----|
| `PORT` | `20128` | API port (and dashboard unless split) | **[V]** |
| `DASHBOARD_PORT` | unset | Serve the dashboard on a separate port (split-port mode) | **[V]** |
| `HOSTNAME` | `0.0.0.0` (containers) | Bind address inside a container | **[V]** |
| `NODE_ENV` | `production` | Runtime mode | **[V]** |
| `DATA_DIR` | `~/.omniroute/` (npm); `/app/data` (Docker) | SQLite + call-log location. Must be on a persistent volume | **[V]** |
| `STORAGE_DRIVER` | `sqlite` | Persistence backend | **[V]** |
| `REQUIRE_API_KEY` | `false` in the VM-guide example | When `true`, unknown keys get `401 Invalid API key` | **[V]** |
| `APP_LOG_TO_FILE` | `false` / `true` | File logging toggle | **[V]** |
| `AUTH_COOKIE_SECURE` | `false` in the VM-guide example | Cookie `Secure` flag; relevant when the dashboard is served over plain HTTP | **[V]** example, behavior **[?]** |
| `BASE_URL`, `NEXT_PUBLIC_BASE_URL` | e.g. `http://localhost:20128` | Public base URL for callbacks/front end; keep aligned | **[V]** |
| `OMNIROUTE_MEMORY_MB` | `1024` | Heap sizing in the Docker template | **[V]** |

### 6.3 Timeouts **[V]**

| Variable | Default | Meaning |
|----------|---------|---------|
| `REQUEST_TIMEOUT_MS` | `600000` | Shared baseline for upstream response-start timeout and API-bridge timeouts |
| `STREAM_IDLE_TIMEOUT_MS` | inherits `REQUEST_TIMEOUT_MS` | Max gap between streamed chunks before the stream is aborted |
| `FETCH_TIMEOUT_MS` / `FETCH_HEADERS_TIMEOUT_MS` / `FETCH_BODY_TIMEOUT_MS` | inherit the baseline | Finer-grained upstream timeouts (override the baseline) |
| `FETCH_CONNECT_TIMEOUT_MS` | `30000` | TCP connect timeout |

> **Alignment rule [R]:** `client timeout (60 s) >= REQUEST_TIMEOUT_MS`. If the client gives up at 60 s but the gateway keeps waiting up to 600 s, the upstream request still consumes quota and a concurrency slot. Behind Nginx/Caddy/Cloudflare, the proxy's timeouts must be **higher** than OmniRoute's. **[V]**

### 6.4 Example `omniroute.env` **[R]**

```dotenv
# --- secrets (generate; never commit) ---
JWT_SECRET=__generate__
API_KEY_SECRET=__generate__
INITIAL_PASSWORD=__generate__
STORAGE_ENCRYPTION_KEY=__generate__
STORAGE_ENCRYPTION_KEY_VERSION=v1
MACHINE_ID_SALT=__generate__
OMNIROUTE_WS_BRIDGE_SECRET=__generate__

# --- runtime ---
PORT=20128
DATA_DIR=/app/data
REQUIRE_API_KEY=true
REQUEST_TIMEOUT_MS=55000
OMNIROUTE_MEMORY_MB=1024
```

### 6.5 Variables consumed by the Arena app (plan Task 2.1)

```dotenv
LLM_BASE_URL=http://localhost:20128/v1
LLM_API_KEY=<key created in Dashboard > Endpoints>
LLM_MODEL_INGEST=ingest-fast          # combo name, or auto/fast
LLM_MODEL_COMMANDER=commander-quality # pinned priority combo
```

---

## 7. Running as a Service

### 7.1 Docker (preferred)

`--restart unless-stopped` (or `restart: unless-stopped` in compose) is enough. On Windows use Docker Desktop with "Start when you sign in" enabled. **[R]**

### 7.2 Windows without Docker (Task Scheduler) **[R]**

Set the variables as *User* environment variables first (`[Environment]::SetEnvironmentVariable('REQUIRE_API_KEY','true','User')`, and so on), then:

```powershell
$action  = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c omniroute --no-open"
$trigger = New-ScheduledTaskTrigger -AtLogOn
Register-ScheduledTask -TaskName "OmniRoute" -Action $action -Trigger $trigger -RunLevel Limited
```

### 7.3 Linux systemd **[V]** (AUR) / **[R]** (custom)

The Arch AUR package (`omniroute-bin`) ships a user service: `systemctl --user enable --now omniroute.service`. **[V]**

### 7.4 Readiness gating for the Arena app **[R]**

At engine start, poll `GET /api/health` every 5 s (it returns 503 while starting) for up to ~60 s, then continue in **offline safe mode** (NEUTRAL macro state) and keep re-probing in the background. This implements plan Task 2.2 without blocking the trading engine.

---

## 8. Security Hardening

| # | Action | Tag |
|---|--------|-----|
| 1 | Bind to loopback (`127.0.0.1:20128`). If you must expose it, put an authenticated reverse proxy or tunnel in front. A tested tunnel setup returned 401 for missing/wrong credentials and only passed correct ones. | **[V]** / **[R]** |
| 2 | `REQUIRE_API_KEY=true` and a dedicated key for the Arena app. Rotate by creating a new key in Dashboard > Endpoints. | **[R]** |
| 3 | Change `INITIAL_PASSWORD` immediately; do not keep `123456` / `CHANGEME`. | **[V]** |
| 4 | Back up `STORAGE_ENCRYPTION_KEY` and the `DATA_DIR` volume (see section 10). | **[V]** |
| 5 | Pin image tag/digest; read release notes before upgrading; upgrade in a maintenance window, not during market hours. | **[R]** |
| 6 | Treat "free" upstreams with care. The project documents ban-detection, stealth and web-cookie/OAuth provider paths, which implies some upstream access is unofficial. Review each provider's terms, and expect throttling or account action. For the Commander use official API-key providers. | **[V]** features, **[R]** advice |
| 7 | Never put exchange keys, balances or private account data into prompts. Prompts should contain only public news text plus a fixed schema. | **[R]** |
| 8 | Remember news text is **untrusted input** (prompt-injection surface). Delimit it clearly, instruct the model to treat it as data, and validate the JSON output against a schema (clamp urgency 1-10, sentiment -1..1, confidence 0..1). | **[R]** |

---

## 9. Model Routing Design for This Workflow

### 9.1 Naming rules **[V]**

- Concrete models use a provider prefix, for example `cc/claude-opus-4-6` or `if/kimi-k2-thinking`. Any combo name defined in the dashboard can be used directly as `model`.
- `GET /v1/models` lists models **and** combos; hidden models are excluded.

### 9.2 Auto variants **[V]**

| Model string | Optimizes | Documented weighting |
|--------------|-----------|----------------------|
| `auto` | balanced default | health 0.22, quota 0.17, ... (9-factor score) |
| `auto/fast` | latency | latency 32%, health 28% |
| `auto/cheap` | cost | cost 37% |
| `auto/smart` | quality + exploration | task-fit 37%, exploration 10% |
| `auto/offline` | capacity | quota 37%, health 28% |
| `auto/coding` | coding tasks | - |

`auto/smart` deliberately **explores** other models some of the time, which is not what you want inside a strict-veto Commander loop. **[R]**

### 9.3 Combo strategies **[V]**

`priority`, `weighted`, `round-robin`, `random`, `least-used`, `cost-optimized`, `strict-random`, `auto`, `fill-first`, `p2c`, `lkgp`, `context-optimized`, `context-relay` (the docs cite 13 or 14 depending on version).

### 9.4 Recommended combos **[R]**

| Combo | Strategy | Members (illustrative) | Used by |
|-------|----------|------------------------|---------|
| `ingest-fast` | `round-robin` or `least-used` | 2-3 fast/cheap models across different providers (free tiers allowed) | `LLM_MODEL_INGEST` - Stage 1 harvester, high volume, tolerant of occasional failure |
| `commander-quality` | `priority` | 1st: strongest reliable model on an **official API-key provider**; 2nd: a second provider; 3rd: a different model family | `LLM_MODEL_COMMANDER` - Stage 2 synthesis, low volume, determinism matters |

Why this split:

- Stage 1 produces many small, schema-bound extractions. Cost and latency dominate, and a bad item is cheap.
- Stage 2 gates every order through the veto. Predictability, and a fallback that is *a different provider*, matter more than raw throughput. Use `temperature: 0` for both stages. **[R]**

### 9.5 Retry layering **[R]**

OmniRoute already performs cooldown-aware retries and circuit-breaking. **[V]** Stacking the plan's client retries (max 5) on top of gateway retries can multiply latency and quota use. Keep the gateway's own retry settings modest, honor `Retry-After` on the client, and keep the client's total deadline bounded (for example 60 s per call, plus an overall per-synthesis budget).

If you see 429s well below 25 concurrent requests, check the gateway's quota/admission documentation (wiki pages "Usage Quota Guide", "Admission Lanes") and each provider's own limits.

---

## 10. Operations

### 10.1 Monitoring **[V]**

| What | Where |
|------|-------|
| Liveness | `GET /api/health` (unauthenticated) |
| Full health, breakers, rate limits | `GET /api/monitoring/health` (Bearer) or `/dashboard/health` |
| Per-provider latency p50/p95/p99 | `GET /api/providers/metrics` |
| Request/usage logs | `/dashboard/logs`, `/dashboard/usage`, `omniroute logs --follow` |
| Correlation | Responses carry an `X-Request-Id` correlation id; log it in the Arena app next to each ingest/commander call |

### 10.2 Circuit breakers **[V]**

States: `CLOSED` (normal), `OPEN` (blocked until cooldown), `HALF_OPEN` (probe). Only provider-level statuses `408, 500, 502, 503, 504` trip a breaker; account-level errors (most 401/403/429) go through cooldown/lockout instead. Documented defaults include API-key providers 5 failures / 30 s and local providers 2 failures / 15 s; cooldown bases are about 5 s (OAuth) and 3 s (API key), with exponential backoff, and API-key 429 prefers the upstream `Retry-After`. A stuck-OPEN provider can be reset from Dashboard > Settings > Resilience or `POST /api/resilience/reset`; verify the provider is actually healthy first.

### 10.3 Data, backup, upgrade, uninstall

- **Data:** `${DATA_DIR}/storage.sqlite` (providers, combos, aliases, keys, settings) and `${DATA_DIR}/call_logs/YYYY-MM-DD/...` when call logging is enabled. **[V]**
- **Backup (Docker):** `docker cp omniroute:/app/data ./backup-$(date +%F)` or tar the volume with a throwaway container. PowerShell: `docker cp omniroute:/app/data ./backup-$(Get-Date -Format yyyy-MM-dd)`. **[V]** / **[R]**
- **Upgrade:** read release notes, change the pinned tag/digest, redeploy; the volume preserves state. **[V]**
- **Uninstall (npm/source):** `npm run uninstall` keeps `~/.omniroute`; `npm run uninstall:full` erases configs, keys and databases. **[V]**

---

## 11. Troubleshooting

| Symptom | Likely cause / action | Tag |
|---------|-----------------------|-----|
| `better-sqlite3` native error after global install | Binary compiled for a different Node ABI/architecture. Reinstall under the Node version you actually run (see section 3). | **[V]** cause |
| Install refuses / odd failures on Node 23 | Node 23 is outside the supported range. | **[V]** |
| `401 Invalid API key` | `REQUIRE_API_KEY=true` and the key is unknown. Recreate/copy from Dashboard > Endpoints. | **[V]** |
| Editor/tool cannot send `Authorization: Bearer` | Use the tokenized compatibility base `http://localhost:20128/api/v1/vscode/<KEY>/` (not needed for the Arena app). | **[V]** |
| Model list empty | All models hidden or no provider connected. | **[V]** |
| Requests fail instantly for one provider | Breaker is `OPEN`; check Dashboard > Health, wait for cooldown or reset after verifying. | **[V]** |
| Dashboard login loops over plain HTTP in production mode | Try `AUTH_COOKIE_SECURE=false` (appears in the VM-guide example). | **[?]** |
| Port clash on 20128 | Change `PORT`, or use split-port mode (`PORT` API, `DASHBOARD_PORT` dashboard). | **[V]** |
| Long requests die behind a reverse proxy | Raise the proxy timeouts above OmniRoute's. | **[V]** |
| Something is wrong and you do not know what | `omniroute doctor` (add `--json` for scripts). | **[V]** |

---

## 12. Client Reference Sketch for the Arena App (non-normative) **[R]**

This sketch is **not** part of the approved plan's implementation and has **not** been run against a live OmniRoute gateway or the real `aiohttp` package. It only illustrates how the settings above, the plan's retry rules, and refinement R2 fit together. What was actually tested (locally, with a fake HTTP session): `extract_json` against 12 cases (think blocks containing braces, unclosed think, fenced and unlabeled-fence JSON, prose-wrapped JSON, nested objects, truncated/malformed output, array top level), and the `chat_json` control flow for 429-then-200, persistent 503 (6 attempts then `None`), gateway unreachable (bounded retries then `None`), 401 (no retry), and malformed response envelopes.

```python
import asyncio, json, os, random, re
import aiohttp

BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:20128/v1")
API_KEY = os.getenv("LLM_API_KEY", "")
_SEM = asyncio.Semaphore(25)
RETRY_STATUS = {429, 502, 503}

_THINK_CLOSED = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_THINK_OPEN = re.compile(r"<think>.*\Z", re.DOTALL | re.IGNORECASE)   # truncated reasoning
_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


def extract_json(text):
    """R2: strip <think> blocks and code fences, then parse the outermost {...}."""
    if not text:
        return None
    s = _THINK_CLOSED.sub("", text)
    s = _THINK_OPEN.sub("", s)
    m = _FENCE.search(s)
    if m:
        s = m.group(1)
    start, end = s.find("{"), s.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        obj = json.loads(s[start:end + 1])
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def _backoff(attempt, retry_after=None):
    if retry_after:
        try:
            return min(float(retry_after), 30.0)
        except ValueError:
            pass
    return min(0.5 * (2 ** attempt), 8.0) * random.uniform(0.75, 1.25)   # 0.5 -> 1 -> 2 -> 4 -> 8 (+/- jitter)


async def chat_json(session, model, system, user, max_retries=5, timeout_s=60):
    """Return a parsed dict, or None (caller falls back to NEUTRAL / skips the event)."""
    payload = {
        "model": model,
        "temperature": 0,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    for attempt in range(max_retries + 1):
        try:
            async with _SEM:                       # hold a slot only while a request is in flight
                async with session.post(
                    f"{BASE_URL}/chat/completions", json=payload, headers=headers,
                    timeout=aiohttp.ClientTimeout(total=timeout_s),
                ) as r:
                    status, retry_after = r.status, r.headers.get("Retry-After")
                    body = await r.json() if status == 200 else None
            if status in RETRY_STATUS and attempt < max_retries:
                await asyncio.sleep(_backoff(attempt, retry_after))
                continue
            if status != 200 or body is None:
                return None
            return extract_json(body["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError):
            return None                            # malformed envelope: do not retry
        except (aiohttp.ClientError, asyncio.TimeoutError):
            if attempt >= max_retries:
                return None                        # gateway unreachable: offline safe mode
            await asyncio.sleep(_backoff(attempt))
    return None
```

Implementation notes:

- Create **one** long-lived `aiohttp.ClientSession` and close it on engine shutdown (plan Task 2.3 leak check).
- Do not rely on `response_format: {"type": "json_object"}`; support varies across upstream providers behind a router. Keep the prompt explicit and let `extract_json` do the defending. **[R]**
- Prefer non-streaming calls for JSON extraction.

---

## 13. Deployment Acceptance Checklist (maps to plan Phase 2 checkpoint)

- [ ] `GET /api/health` returns `{"ok":true}`; `omniroute doctor` is clean.
- [ ] `GET /v1/models` (with key) lists the models/combos named in `LLM_MODEL_INGEST` and `LLM_MODEL_COMMANDER`.
- [ ] A real chat completion through each model returns parseable JSON via `extract_json`.
- [ ] `REQUIRE_API_KEY=true` rejects a missing/wrong key with 401.
- [ ] Stopping the gateway makes the Arena app log a warning, hold `NEUTRAL`, and keep trading engine alive (no crash); restarting the gateway restores `ONLINE` without an app restart.
- [ ] A forced 429/503 (disable a provider or use a test combo) shows jittered backoff and honors `Retry-After`.
- [ ] Gateway `REQUEST_TIMEOUT_MS` is not larger than the client timeout.
- [ ] `STORAGE_ENCRYPTION_KEY` and the data volume are backed up; a restore was rehearsed once.
- [ ] Image tag/digest is pinned and recorded in the deployment notes.
- [ ] The persistent `aiohttp.ClientSession` is closed on shutdown (no unclosed-session warnings).

---

## 14. Sources

Upstream docs (GitHub wiki, `diegosouzapw/OmniRoute`):
- Setup Guide - https://github.com/diegosouzapw/OmniRoute/wiki/Setup-Guide
- Quick Start - https://github.com/diegosouzapw/OmniRoute/wiki/Quick-Start
- Auto Combo - https://github.com/diegosouzapw/OmniRoute/wiki/Auto-Combo
- Auto Combo Guide - https://github.com/diegosouzapw/OmniRoute/wiki/Auto-Combo-Guide
- Architecture - https://github.com/diegosouzapw/OmniRoute/wiki/Architecture
- Resilience Guide - https://github.com/diegosouzapw/OmniRoute/wiki/Resilience-Guide
- Reasoning Replay - https://github.com/diegosouzapw/OmniRoute/wiki/Reasoning-Replay
- Environment variables - https://github.com/diegosouzapw/OmniRoute/wiki/da%E2%80%90Environment
- API Reference - https://github.com/diegosouzapw/OmniRoute/wiki/phi%E2%80%90API-Reference
- VM Deployment Guide - https://github.com/diegosouzapw/OmniRoute/wiki/pt%E2%80%90VM-Deployment-Guide
- Fly.io Deployment Guide - https://github.com/diegosouzapw/OmniRoute/wiki/Fly-io-Deployment-Guide
- Troubleshooting - https://github.com/diegosouzapw/OmniRoute/wiki/id%E2%80%90Troubleshooting
- Repository - https://github.com/diegosouzapw/OmniRoute

Third-party:
- Railway Docker template (digest-pinned image, `/app/data`, restart/stop-timeout flags) - https://railway.com/deploy/omniroute-docker--deploy-omniroute-docker-image
- Self-host test on v3.8.48 (Node engines range, `/v1/models`, tunnel auth behavior) - https://pinggy.io/amp/blog/omniroute_ai_gateway_security/
- Health/monitoring skill notes (`/api/health`, `/api/monitoring/health`, provider metrics) - https://skills.cat/skills/diegosouzapw/omniroute/omni-resilience

**Not independently verified:** exact behavior of `AUTH_COOKIE_SECURE` over plain HTTP; the exact image tag to pin (depends on the release you choose); admission/quota limits for your specific providers; whether your chosen upstream models honor `response_format`.
