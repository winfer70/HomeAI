# HomeSwarm — Multi-Agent AI Advisory System
### Design Document v1.0 — 2025-05-14

Built on the HomeAI async ReAct pattern. Fixes every flaw identified in the Google AI plan review.

---

## 1. System Overview

A personal multi-agent advisory swarm triggered by Telegram or voice (Google Home / Alexa).
Three specialist AI agents (Logician, Devil's Advocate, Aggregator) run locally on spare laptops
via Ollama. n8n on the main server handles all routing and callbacks.
Financial scoring data from a dedicated laptop feeds the business analysis agent.

```
[ Telegram / Voice ]
        │
        ▼
[ n8n on Main Server ]  ←─── Nginx (HTTPS termination)
        │
        │  POST /swarm/analyze  (X-Swarm-Token header)
        ▼
[ Swarm API — Worker Laptop 1 ]
        │
        ├── asyncio.Queue (task buffer)
        │
        ├── Logician ──────────── Ollama (local)
        ├── Devil's Advocate ───── Ollama (local)  } parallel if PARALLEL_AGENTS=true
        └── Aggregator ─────────── Ollama (local)  } sequential always
                │
                ├── Financial API  (Financial Laptop)
                └── SQLite Memory  (per chat_id session)
        │
        ▼ POST /webhook/swarm-callback
[ n8n callback flow ]
        │
        ▼
[ Telegram Bot → User ]
```

---

## 2. Hardware Assignment

| Machine | Role | Services | Recommended Model |
|---|---|---|---|
| Main server (old PC, Docker + n8n + nginx) | Orchestration only — no AI inference | n8n, nginx, Caddy/nginx reverse proxy | — |
| Worker Laptop 1 (best spare, ≥8GB RAM) | Swarm API + LLM inference | swarm-api, ollama, redis | llama3.2:3b (8GB) or qwen3:4b (16GB) |
| Worker Laptop 2 (second spare, optional) | Scale-out LLM (Phase 3+) | ollama (second instance) | Same as Laptop 1 |
| Worker Laptop 3 (weakest) | Monitoring + Redis (Phase 2+) | prometheus, grafana, redis | — |
| Financial Laptop (existing) | Financial data API | financial-api (lightweight FastAPI) | — |

### Model selection guide (based on hardware research)

| RAM available | Recommended model | Est. latency per 3-call pipeline |
|---|---|---|
| 8 GB | llama3.2:3b Q4_K_M | 50–90 seconds |
| 16 GB | qwen3:4b Q4_K_M | 60–120 seconds |
| 16 GB+ (good CPU) | qwen3:8b Q4_K_M | 90–180 seconds |

> **Important:** Old laptops throttle under sustained load. Expect 20-40% slower t/s
> after 3+ minutes. Design timeouts accordingly (default: 120s per LLM call).
> `OLLAMA_NUM_PARALLEL=1` always — don't try to run two models at once on old hardware.

---

## 3. Service Map

### 3.1 swarm-api (Worker Laptop 1)

| Property | Value |
|---|---|
| Framework | FastAPI + Uvicorn |
| Port | 8000 (internal LAN only — NOT exposed to internet) |
| Auth | `X-Swarm-Token` header (env var) |
| Queue | `asyncio.Queue` with configurable worker count (default: 1) |
| Memory | SQLite per `chat_id` — same schema as HomeAI |
| Language | Python 3.11+ |

Endpoints:
- `POST /swarm/analyze` — accepts task, returns `task_id` immediately (non-blocking)
- `GET /swarm/status/{task_id}` — poll-based status check
- `GET /health` — liveness probe (no auth required)

### 3.2 ollama (Worker Laptop 1)

| Property | Value |
|---|---|
| Port | 11434 (LAN only) |
| Model default | `llama3.2:3b` |
| Parallel | `OLLAMA_NUM_PARALLEL=1` |
| Context | `OLLAMA_NUM_CTX=4096` |
| Timeout | 120s per generation (configured in swarm-api) |

### 3.3 financial-api (Financial Laptop)

| Property | Value |
|---|---|
| Framework | FastAPI (lightweight) |
| Port | 5000 (LAN only) |
| Auth | `X-Financial-Token` header |
| Endpoints | `GET /scores?ticker=XXX&limit=5` |
| Data source | Reads from existing scoring script output (SQLite or CSV) |

### 3.4 n8n (Main Server — already running)

New workflows to add:
- `swarm-trigger` — Telegram Trigger → parse command → POST to swarm-api → immediate ACK to user
- `swarm-callback` — Webhook (POST /webhook/swarm-callback) → send full report via Telegram

### 3.5 redis (Worker Laptop 1 or 3)

Used for: task result caching (TTL 10 minutes), optional distributed queue upgrade path.
Phase 1: optional. Phase 2+: required for multi-user concurrent requests.

---

## 4. Agent Design

### 4.1 Logician — "First Principles Analyst"

```
Role: Strip away emotion and cognitive bias. Deconstruct the problem
      into foundational, undeniable truths using First Principles Thinking.

System prompt:
  You are a Master Logician and Decision Scientist. You have no emotional bias.
  Analyze the given problem by:
  1. FIRST PRINCIPLES: Identify the 3-5 most basic, verifiable facts about this situation.
  2. SECOND-ORDER THINKING: For the most likely solution, ask "and then what?" twice.
  3. KEY ASSUMPTION: State the single assumption that, if wrong, would invalidate your analysis.
  Show your reasoning step by step before your conclusion.
  Output language: match the user's language (Polish or English).

Input context:
  - User's original problem/question
  - Financial data (if ticker/market topic detected)
  - Last N conversation turns (sliding window memory)

Output: structured analysis in markdown (max 500 words)
```

### 4.2 Devil's Advocate — "Risk Detector"

```
Role: Find everything that could go wrong. Apply Inversion Thinking.

System prompt:
  You are the Devil's Advocate. Your only purpose is to find hidden risks.
  Apply INVERSION THINKING: Assume the proposed plan completely fails.
  Work backwards to identify exactly HOW it failed.
  Output:
  1. THREE structural risks (specific, not generic)
  2. TWO cognitive biases detected in the original framing
  3. ONE critical assumption that was never questioned
  Be ruthlessly specific. Generic warnings are useless.
  Output language: match the user's language (Polish or English).

Input context:
  - User's original problem/question
  - Logician's analysis (if PARALLEL_AGENTS=false)
  - OR same input as Logician (if PARALLEL_AGENTS=true)

Output: structured risk report in markdown (max 400 words)
```

### 4.3 Aggregator — "Executive Synthesizer"

```
Role: Synthesize the Logician and Devil's Advocate into one actionable brief.

System prompt:
  You are the Executive Synthesizer. You have received two expert analyses.
  Your job is to produce a clean, actionable executive brief that:
  1. States the core recommendation in ONE sentence at the top.
  2. Lists the 3 most important supporting facts from the Logician.
  3. Lists the 2 most important risks from the Devil's Advocate.
  4. Gives a DECISION FRAMEWORK: under what conditions should the user act vs. wait?
  Use clean Markdown with headers. Max 600 words total.
  Output language: match the user's language (Polish or English).

Input context:
  - Logician's full analysis
  - Devil's Advocate's full risk report
  - User's original question

Output: formatted executive brief
```

### 4.4 Agent Execution Modes

| Mode | When | How |
|---|---|---|
| `PARALLEL_AGENTS=false` (default) | 8GB hardware | Logician → Devil's Advocate → Aggregator (sequential, ~90s) |
| `PARALLEL_AGENTS=true` | 16GB+ hardware | `asyncio.gather(Logician, Devil's Advocate)` → Aggregator (~60s) |

> Note: Because `OLLAMA_NUM_PARALLEL=1`, parallel mode only helps if you run two separate
> Ollama instances on different machines. With a single Ollama, both modes have the same
> wall-clock time. Set `PARALLEL_AGENTS=true` only when using Worker Laptop 2 as a second Ollama.

---

## 5. Data Flow Diagrams

### 5.1 Standard Telegram command

```
User types: "/analyze Should I move my investments to bonds?"
        │
        ▼
[Telegram Bot] → n8n Telegram Trigger node fires
        │
        ▼
[n8n: Code node — parse command]
  rawText = "/analyze Should I move my investments to bonds?"
  command = "/analyze"
  user_input = "Should I move my investments to bonds?"
  chat_id = 123456789
        │
        ▼
[n8n: HTTP Request node]
  POST http://WORKER_LAPTOP_1_IP:8000/swarm/analyze
  Header: X-Swarm-Token: $env.SWARM_TOKEN
  Body: {"chat_id": 123456789, "command": "/analyze",
         "user_input": "Should I move...", "language": "en"}
        │
        ▼ (immediate response — non-blocking)
[swarm-api returns instantly]
  {"task_id": "uuid-1234", "status": "queued", "estimated_seconds": 90}
        │
        ▼
[n8n: Telegram Send — immediate ACK to user]
  "Processing your request... (est. 90 seconds)"
        │
        ▼ [meanwhile, in background on Worker Laptop 1...]
[asyncio.Queue worker dequeues task]
        ├── Fetch financial data: GET http://FIN_LAPTOP_IP:5000/scores?ticker=bonds
        ├── [PARALLEL_AGENTS=false] Run Logician → Ollama (llama3.2:3b)
        ├── Run Devil's Advocate → Ollama (with Logician output)
        └── Run Aggregator → Ollama (synthesis)
        │
        ▼ (task complete)
[swarm-api: POST http://N8N_URL/webhook/swarm-callback]
  {"chat_id": 123456789, "task_id": "uuid-1234",
   "output": "# Executive Brief\n...", "duration_ms": 87000}
        │
        ▼
[n8n: Swarm Callback webhook receives POST]
        │
        ▼
[n8n: Telegram Send — full report to user]
  Full markdown report split into Telegram-friendly chunks (4096 char limit)
```

### 5.2 Voice trigger (Google Home or Alexa)

```
User says: "Hey Google, run a business panel on Tesla stock"
        │
        ▼
[Google Home Routine or Alexa Skill]
  HTTP POST to: https://YOUR_DOMAIN/n8n-webhook/voice-trigger
  Body: {"voice_text": "run a business panel on Tesla stock"}
        │
        ▼
[nginx: routes /n8n-webhook/* → n8n internal port]
        │
        ▼
[n8n: Voice Trigger webhook]
  Parses voice_text → extracts command + user_input (same Code node as Telegram)
  Sets chat_id = OWNER_TELEGRAM_CHAT_ID (env var — voice always goes to your phone)
        │
        ▼ [same flow as 5.1 from this point]
[n8n: HTTP Request → swarm-api]
        │
        ▼
[Voice device receives immediate text response]
  "Got it. Sending your business panel report to Telegram now."
        │
        ▼
[Full report delivered to Telegram ~90 seconds later]
```

### 5.3 Financial data enrichment

```
[swarm-api worker: financial topic detected in user_input]
        │
        ▼
[Extract tickers/assets from user_input]
  Pattern match: uppercase 2-5 letter words, known asset names, "stock", "akcje" etc.
        │
        ▼
[GET http://FIN_LAPTOP_IP:5000/scores?ticker=TSLA&limit=5]
  Header: X-Financial-Token: $env.FINANCIAL_TOKEN
        │
        ├── Success: inject into Logician prompt as "Live Market Data:"
        └── Failure/timeout: proceed without data, note "financial data unavailable"
```

---

## 6. API Contracts

### POST /swarm/analyze

**Request:**
```json
{
  "chat_id": 123456789,
  "command": "/analyze",
  "user_input": "Should I move my investments to bonds?",
  "language": "en"
}
```

**Immediate response (202 Accepted):**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "estimated_seconds": 90,
  "queued_at": "2025-05-14T10:00:00Z"
}
```

**Error responses:**
- `403 Forbidden` — missing or wrong `X-Swarm-Token`
- `422 Unprocessable Entity` — missing required fields
- `503 Service Unavailable` — queue full (max queue depth exceeded)

---

### GET /swarm/status/{task_id}

**Response:**
```json
{
  "task_id": "550e8400...",
  "status": "running|queued|complete|failed",
  "progress": "logician_complete",
  "started_at": "2025-05-14T10:00:05Z",
  "completed_at": null
}
```

---

### POST /webhook/swarm-callback  *(n8n receives this)*

**Sent by swarm-api when a task finishes:**
```json
{
  "chat_id": 123456789,
  "task_id": "550e8400...",
  "status": "complete",
  "output": "# Executive Brief\n\n**Recommendation:** ...",
  "agents_used": ["logician", "devil_advocate", "aggregator"],
  "financial_data_used": true,
  "duration_ms": 87234,
  "language": "en"
}
```

---

### GET /scores  *(financial-api on Financial Laptop)*

**Request:** `GET /scores?ticker=TSLA&limit=5`
**Auth:** `X-Financial-Token` header

**Response:**
```json
{
  "ticker": "TSLA",
  "score": 0.72,
  "sentiment": "bullish",
  "articles_analyzed": 47,
  "summary": "Strong Q2 delivery numbers offset by margin concerns...",
  "last_updated": "2025-05-14T09:45:00Z",
  "top_headlines": [
    {"title": "Tesla beats delivery estimates", "score": 0.85, "source": "Reuters"}
  ]
}
```

---

### Memory schema (SQLite — per swarm-api instance)

```sql
CREATE TABLE IF NOT EXISTS sessions (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id   INTEGER NOT NULL,
    ts        TEXT    NOT NULL,  -- UTC ISO 8601
    role      TEXT    NOT NULL,  -- "user" | "assistant"
    content   TEXT    NOT NULL,
    command   TEXT                -- "/analyze", "/sc:business-panel" etc.
);
CREATE INDEX IF NOT EXISTS idx_chat_id ON sessions(chat_id, id DESC);
```

---

## 7. Task Queue Architecture

Using `asyncio.Queue` — no Redis required for Phase 1/2. Redis upgrade path in Phase 3.

```python
# Architecture (NOT implementation — see /sc:implement phase)

TaskQueue = asyncio.Queue(maxsize=20)  # reject at 20 queued tasks

QueueWorker:
  - Single coroutine loop (1 worker per Ollama instance)
  - Dequeues one TaskItem at a time
  - Runs agent pipeline (sequential or parallel)
  - POSTs result to N8N_CALLBACK_URL
  - Handles timeout: if any LLM call > LLM_TIMEOUT_S, returns partial result

TaskItem:
  - task_id: UUID
  - chat_id: int
  - command: str
  - user_input: str
  - language: str
  - enqueued_at: datetime
  - callback_url: str  # set from N8N_CALLBACK_URL env var at enqueue time

TaskResult (stored in-memory dict, TTL 10 min):
  - task_id → {status, output, started_at, completed_at}
```

**Concurrency model:**
```
[FastAPI (async)] — handles many HTTP connections concurrently
       │
       │ .put_nowait() or 503 if full
       ▼
[asyncio.Queue] — max 20 items
       │
       │ .get() — one at a time
       ▼
[Worker coroutine] — runs one pipeline at a time
       │
       ▼
[Ollama] — OLLAMA_NUM_PARALLEL=1, sequential internally
```

This means: **one analysis at a time**, up to 20 queued. For a personal system this is correct.
Multi-user scale-out in Phase 3 adds a second worker pointing at Worker Laptop 2's Ollama.

---

## 8. Environment Variables (complete list)

```bash
# swarm-api (.env on Worker Laptop 1)
SWARM_API_KEY=generate-a-strong-random-token-here

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b               # or qwen3:4b on 16GB
LLM_TEMPERATURE=0.1
LLM_TIMEOUT_S=120
REACT_MAX_ITERATIONS=3                  # logician → critic → aggregator

PARALLEL_AGENTS=false                   # true only with 2x Ollama instances

FINANCIAL_API_URL=http://192.168.1.XXX:5000   # LAN IP of financial laptop
FINANCIAL_API_TOKEN=generate-token-here
FINANCIAL_TIMEOUT_S=5

N8N_CALLBACK_URL=http://192.168.1.YYY:5678/webhook/swarm-callback  # LAN IP of main server
N8N_CALLBACK_TOKEN=generate-token-here  # n8n webhook uses this to verify origin

MEMORY_DB_PATH=./swarm_memory.db
MEMORY_WINDOW=8                          # turns per chat_id

MAX_QUEUE_DEPTH=20
WORKER_CONCURRENCY=1

LOG_LEVEL=INFO
LOG_FILE=./swarm.log

# financial-api (.env on Financial Laptop)
FINANCIAL_API_TOKEN=same-token-as-above
DATA_SOURCE_PATH=./scores.db            # or path to CSV/SQLite from existing script
PORT=5000

# n8n environment (added to n8n Docker env)
SWARM_WORKER_URL=http://192.168.1.XXX:8000   # LAN IP of Worker Laptop 1
SWARM_API_KEY=same-token-as-swarm-api
OWNER_TELEGRAM_CHAT_ID=your_telegram_chat_id  # for voice triggers
```

---

## 9. Docker Compose

### Worker Laptop 1  (`docker-compose.worker.yml`)

```yaml
services:
  ollama:
    image: ollama/ollama:latest
    ports:
      - "127.0.0.1:11434:11434"  # localhost only — not exposed on LAN
    volumes:
      - ollama-data:/root/.ollama
    environment:
      - OLLAMA_NUM_PARALLEL=1
      - OLLAMA_NUM_CTX=4096
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 10G  # cap to protect OS (adjust per actual RAM)

  swarm-api:
    build: ./swarm-api
    ports:
      - "8000:8000"  # exposed on LAN, protected by X-Swarm-Token
    env_file: .env
    volumes:
      - swarm-data:/app/data
    depends_on:
      - ollama
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  redis:
    image: redis:7-alpine
    ports:
      - "127.0.0.1:6379:6379"
    volumes:
      - redis-data:/data
    restart: unless-stopped

volumes:
  ollama-data:
  swarm-data:
  redis-data:
```

### Financial Laptop  (`docker-compose.financial.yml`)

```yaml
services:
  financial-api:
    build: ./financial-api
    ports:
      - "5000:5000"  # LAN only — no nginx exposure
    env_file: .env
    volumes:
      - ./data:/app/data:ro  # read-only mount of existing scoring data
    restart: unless-stopped
```

### Main Server additions  (add to existing `docker-compose.yml`)

```yaml
# Add to existing n8n service environment:
environment:
  - SWARM_WORKER_URL=${SWARM_WORKER_URL}
  - SWARM_API_KEY=${SWARM_API_KEY}
  - OWNER_TELEGRAM_CHAT_ID=${OWNER_TELEGRAM_CHAT_ID}

# No new services needed on main server for Phase 1/2
```

---

## 10. n8n Workflow Design

### Workflow 1: swarm-trigger (Telegram + Voice → Swarm API)

```
[Telegram Trigger]
      │
[Code: parse command]
  ─────────────────────────────────────────────────────
  const text = $json.message?.text || $json.voice_text || "";
  const match = text.match(/^(\/[a-zA-Z0-9:_-]+)\s*(.*)/s);
  const command = match ? match[1] : "/analyze";
  const userInput = match ? match[2].trim() : text.trim();
  const lang = /[ąęóśźżćńł]/i.test(userInput) ? "pl" : "en";

  return {
    chat_id: $json.message?.chat?.id || parseInt(process.env.OWNER_TELEGRAM_CHAT_ID),
    command,
    user_input: userInput,
    language: lang
  };
  ─────────────────────────────────────────────────────
      │
[HTTP Request → swarm-api /swarm/analyze]
  Method: POST
  URL: {{ $env.SWARM_WORKER_URL }}/swarm/analyze
  Headers: {"X-Swarm-Token": "{{ $env.SWARM_API_KEY }}"}
  Body: {{ $json }}
      │
[Telegram Send — immediate ACK]
  chat_id: {{ $('Code').item.json.chat_id }}
  text: "⏳ Processing... I'll send the full report in ~90 seconds."
```

### Workflow 2: swarm-callback (Swarm API → Telegram)

```
[Webhook: POST /webhook/swarm-callback]
      │
[Code: split long output for Telegram 4096-char limit]
  ──────────────────────────────────────────────────────
  const output = $json.output || "No output received.";
  const chunks = [];
  let i = 0;
  while (i < output.length) {
    chunks.push(output.slice(i, i + 3800));
    i += 3800;
  }
  return chunks.map(c => ({chat_id: $json.chat_id, text: c}));
  ──────────────────────────────────────────────────────
      │
[Loop: Telegram Send for each chunk]
  chat_id: {{ $json.chat_id }}
  text: {{ $json.text }}
  parse_mode: Markdown
```

---

## 11. Security Baseline

| Threat | Mitigation |
|---|---|
| Unauthorized swarm-api access | `X-Swarm-Token` on every request. Rotate monthly. |
| Swarm-api exposed to internet | Port 8000 bound to LAN interface only, NOT forwarded through nginx |
| Financial API accessed without auth | `X-Financial-Token` header, same pattern |
| Prompt injection via user input | Sanitize user_input: strip markdown, cap at 500 chars before injecting into prompts |
| Telegram bot spam | n8n Code node: allowlist your `chat_id` only (personal system) |
| Voice endpoint exposed | nginx: restrict `/n8n-webhook/voice-trigger` to HTTPS + secret path |
| n8n callback spoofed | n8n webhook uses a secret path + optional header token check |
| Sensitive data in logs | Log user_input truncated to 50 chars, never log full LLM outputs |

---

## 12. Phased Rollout

### Phase 1 — Core Swarm, Text Only (2–3 weeks)

**What you build:**
- `swarm-api` with asyncio.Queue, auth, health check
- Logician + Devil's Advocate + Aggregator (sequential, `PARALLEL_AGENTS=false`)
- SQLite session memory per `chat_id`
- n8n: `swarm-trigger` + `swarm-callback` workflows
- Deploy on Worker Laptop 1 with `llama3.2:3b`

**Commands working:** `/analyze [question]` only  
**Trigger:** Telegram only  
**Financial data:** not yet — no-op fallback  
**Test:** Send 3 analysis requests back-to-back, verify queue, verify responses arrive on Telegram

---

### Phase 2 — Financial Integration + Command Router (2 weeks)

**What you build:**
- `financial-api` on Financial Laptop (reads existing scoring output)
- `swarm-api`: auto-detect financial topics → enrich Logician prompt
- n8n: command router (`/analyze`, `/sc:business-panel`, `/risk`, `/brainstorm` etc.)
- Command → agent configuration mapping (different system prompts per command)

**Commands working:** `/analyze`, `/sc:business-panel`, `/risk`  
**Financial data:** live from Financial Laptop  
**Test:** Send `/sc:business-panel Apple stock outlook` — verify financial data appears in report

---

### Phase 3 — Voice Trigger + Polish Language (1–2 weeks)

**What you build:**
- nginx rule: `/n8n-webhook/voice-trigger` HTTPS endpoint
- n8n: Voice Trigger webhook → same command parser → same swarm pipeline
- Google Home Routine or Alexa Skill pointing at nginx endpoint
- Polish language detection in n8n Code node (diacritics heuristic, same as HomeAI)
- Verify Polish prompts produce Polish responses (should work natively with qwen3 models)

**Test:** Say "Hey Google, analyze should I sell my stocks" → confirm Telegram report arrives

---

### Phase 4 — Scale-Out + Monitoring (ongoing)

**What you build:**
- Worker Laptop 2: second Ollama instance
- `PARALLEL_AGENTS=true` (Logician + Devil's Advocate in parallel → both feed Aggregator)
- Redis queue upgrade (swap asyncio.Queue for Redis-backed queue for multi-laptop distribution)
- Prometheus + Grafana on Worker Laptop 3:
  - KPIs: p95 task latency, queue depth, LLM timeout rate, financial API uptime
- Weekly automated test: send fixed test prompt, verify response quality hasn't drifted

---

## 13. Project Structure (new repo: `homeswarm/`)

```
homeswarm/
├── swarm-api/
│   ├── main.py              # FastAPI app, auth, /analyze endpoint
│   ├── queue_worker.py      # asyncio.Queue worker, pipeline orchestrator
│   ├── agents.py            # Logician, Devil's Advocate, Aggregator prompts + LLM calls
│   ├── financial.py         # Financial Laptop API client
│   ├── memory.py            # SQLite session store (same pattern as HomeAI)
│   ├── config.py            # Pydantic Settings
│   ├── Dockerfile
│   └── requirements.txt
├── financial-api/
│   ├── main.py              # Lightweight FastAPI exposing scoring data
│   ├── config.py
│   ├── Dockerfile
│   └── requirements.txt
├── n8n-workflows/
│   ├── swarm-trigger.json   # Export from n8n for version control
│   └── swarm-callback.json
├── docker-compose.worker.yml
├── docker-compose.financial.yml
├── .env.example
└── SWARM_DESIGN.md          # This document
```

---

## 14. What This Is NOT

- Not a replacement for Claude Code `/sc:` skills — those are developer tools in VS Code.
  This swarm is a personal advisory system you talk to via Telegram and voice.
- Not CrewAI — no framework overhead, no sync blocking, no opaque orchestration.
- Not cloud-dependent — Ollama runs locally. Cloud APIs are an optional future upgrade.
- Not a general-purpose chatbot — it is an opinionated 3-agent advisory panel.
  For general chat, HomeAI already handles that.

---

## 15. Key Differences from Google AI's Plan

| Issue | Google AI (broken) | This design (fixed) |
|---|---|---|
| Task queue | `BackgroundTasks` (same-process, no queue) | `asyncio.Queue(maxsize=20)` with single worker |
| LLM config | Never specified | Explicit model per hardware tier, VRAM table |
| Auth | None | `X-Swarm-Token` on all endpoints |
| n8n callback | `http://localhost:5678` (wrong machine) | `N8N_CALLBACK_URL` env var (LAN IP of main server) |
| Hardcoded IPs | `FIN_LAPTOP_IP = "11.0.0"` (broken) | All IPs in env vars, never in code |
| Claude skills mapping | "logical_analyst powers /sc:analyze" (nonsense) | Swarm = separate advisory system, not a clone of Claude |
| Parallel agents | Claimed but sequential in code | Explicit flag, only when 2x Ollama instances available |
| Session memory | Deferred to "let me know" | SQLite per chat_id, same proven pattern as HomeAI |
| Aggregator | Promised, never built | Third agent with explicit synthesis prompt |
| Model for old hardware | llama3:8b (OOM risk on 8GB) | llama3.2:3b (8GB) or qwen3:4b (16GB) |

**Next step:** `/sc:implement Phase 1` — build the swarm-api, queue_worker, agents, and n8n workflows.
