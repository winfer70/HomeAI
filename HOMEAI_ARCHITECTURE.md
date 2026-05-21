# HomeAI — Full Architecture Blueprint (PL + EN)
> Generated 2025-05-14. Tier B recommended starting point.

---

## 1. Vision & Principles

Build a local-first home assistant that understands Polish and English natural language, controls smart-home devices safely, answers questions with grounded web search, and keeps all data on-premises by default.

**Core commitments:**
- Local-first: voice + control loops work without internet
- LLM plans, orchestrator executes — no direct tool calls from language model
- Confirmations for high-risk actions (unlock, purchases, delete)
- All web answers cite sources
- Modular: replace any service independently

---

## 2. End-to-End Request Pipeline

```
[User speaks/types in PL or EN]
       ↓
  [voice-io]  STT via faster-whisper → transcript
       ↓
  [gateway]   auth, rate-limit, request-id
       ↓
  [orchestrator]  drives the state machine:
       ↓
  [nlp-pipeline]  lang-detect → intent class → entity extract → IntentResult
       ↓
  [safety-gate]   risk-score → confirm if HIGH/CRITICAL
       ↓
  [tool adapters] execute plan steps (parallel where deps allow)
       ↓  (if WEB_SEARCH intent)
  [web-search]    query-rewrite → SearXNG → extract → rerank → cite
       ↓
  [llm-service]   compose final answer with evidence
       ↓
  [voice-io]  TTS via Piper → speaker output
       ↓
  [memory-store + observability]  async logging
```

---

## 3. Service Architecture (10 Services)

All internal sync communication is HTTP/REST. All async events go through **NATS 2.10** (JetStream for durability). NATS was chosen over Redis pub/sub (no persistence on restart) and Kafka (too heavy for home scale).

| Service | Responsibility | Stack | Protocol |
|---|---|---|---|
| `gateway` | TLS termination, JWT auth, WebSocket for audio streaming, routing | FastAPI + Caddy 2 | HTTPS/WSS in; HTTP out |
| `voice-io` | Wake word, STT, TTS | Python, OpenWakeWord, faster-whisper, Piper1 | WebSocket stream; NATS |
| `nlp-pipeline` | Lang detection, intent classification, entity extraction | Python, fastText, XLM-RoBERTa, spaCy, dateparser | HTTP sync |
| `llm-service` | Ollama wrapper, prompt templates, cloud fallback | Python, Ollama, httpx | HTTP sync + NATS async |
| `orchestrator` | LangGraph state machine, plan execution, step parallelism | Python, LangGraph | HTTP in; HTTP to adapters |
| `safety-gate` | Risk scoring, policy matrix, confirmation flows, audit log | Python | HTTP sync |
| `automation-adapter` | Wraps HA REST + WebSocket API; resolves entity aliases | Python, aiohttp | HTTP sync + NATS HA events |
| `web-search` | Query rewrite, SearXNG, Playwright extraction, bge-reranker | Python, httpx, Playwright, sentence-transformers | HTTP sync |
| `memory-store` | Session context (Redis TTL), embeddings (ChromaDB), prefs (SQLite) | Python, Redis 7, ChromaDB | HTTP + NATS consume |
| `scheduler` | Reminders, alarms, routine triggers | Python, APScheduler 4 | NATS pub; HTTP from orchestrator |

---

## 4. Data Flow Diagrams

### (a) Simple automation — "Zgaś światło w kuchni" / "Turn off the kitchen lights"

```
Microphone [PCM audio, WebSocket]
    ↓
voice-io  [faster-whisper STT] → transcript: "Zgaś światło w kuchni"
    ↓ HTTP → gateway → orchestrator
nlp-pipeline:
    fastText: lang=pl (0.99)
    XLM-RoBERTa: intent=AUTOMATION (0.97)
    spaCy NER: device=kitchen_lights, action=turn_off
    → IntentResult JSON
    ↓
safety-gate: risk_level=LOW, requires_confirmation=false
    ↓
automation-adapter:
    resolves "kitchen_lights" → entity_id: "light.kitchen_ceiling"
    POST /api/services/light/turn_off → Home Assistant → Zigbee → bulb off
    NATS publish "ha.state_changed" {state: "off"}
    ↓
voice-io [Piper1 TTS] → speaker: "Zgaszono światło w kuchni."

Target latency: < 1200ms on Tier B
```

### (b) Web search — "What's the weather tomorrow?"

```
voice-io [STT] → gateway → orchestrator
    ↓
nlp-pipeline: lang=en, intent=WEB_SEARCH, entities={topic: weather, time: tomorrow}
    ↓
web-search:
    LLM query rewrite: "weather forecast Warsaw Poland 2025-05-15"      ~200ms
    SearXNG meta-search (Google+Brave+DDG): top 10 results              ~800ms
    Playwright content extract: top 3 URLs, parallel                   ~1500ms
    bge-reranker-v2-m3: rank passages against original query
    → SearchResult JSON with citations
    ↓
llm-service [Ollama Qwen3:8B]:
    grounding_template + query + top_passages
    → "Tomorrow in Warsaw expect 18°C, partly cloudy. [C1]"
    ↓
voice-io [Piper1 TTS] → speaker

Target: < 5s Tier B / < 3s Tier C (GPU inference)
```

### (c) High-risk command — "Unlock the front door"

```
voice-io [STT] → gateway → orchestrator
    ↓
nlp-pipeline: intent=LOCK_CONTROL, action=unlock, entity=front_door
    ↓
safety-gate:
    risk_level = HIGH  (unlock_door in HIGH_RISK_ACTIONS policy)
    requires_confirmation = true, method = voice_pin OR mobile_push
    NATS publish "safety.confirmation_required"
    ↓
gateway [voice response]:
    "Potwierdzenie wymagane. Powiedz PIN lub zatwierdź w aplikacji."
    ↓ [user speaks PIN / taps approve]
safety-gate:
    validate TOTP / signed push approval
    write audit log: {timestamp, user, action, method, ip}
    ↓
automation-adapter → HA → Z-Wave lock → door unlocks
    ↓
voice-io [TTS]: "Drzwi wejściowe odblokowane."
```

---

## 5. NLP Pipeline Detail (Bilingual)

### Stage 1 — Language Detection (< 5ms)
**Model:** fastText `lid.176.ftz` (917 KB).
Rule: accept if confidence > 0.85. If ambiguous, check for Polish diacritics (ą ę ó ś ź ż ć ń ł) as tiebreaker, then default to English.

### Stage 2 — Intent Classification (< 80ms, or < 500ms with LLM fallback)
**Primary:** XLM-RoBERTa-base fine-tuned on ~2000 labeled PL+EN home automation commands.
Eight classes: `AUTOMATION` `WEB_SEARCH` `REMINDER` `ALARM` `MEDIA_CONTROL` `THERMOSTAT` `STATUS_QUERY` `UNKNOWN`.
If classifier confidence < 0.70 → fallback to `llm-service` with few-shot classification prompt.

### Stage 3 — Entity Extraction (< 100ms)
- `pl_core_news_sm` or `en_core_web_sm` for base NER (dates, persons)
- Custom `EntityRuler` patterns loaded from `entity_aliases.yaml` (maps user-friendly names to HA entity IDs)
- Time expressions via `dateparser` (supports Polish: "za godzinę", "pojutrze", "w piątek o 19")

### Stage 4 — Plan Generation (orchestrator)
Fuzzy entity resolution against HA entity registry (refreshed every 5 min).
Risk scoring from `risk_policy.yaml`:
```yaml
rules:
  - match: {action: unlock, domain: lock}       risk: HIGH
  - match: {action: turn_off, domain: light}     risk: LOW
  - match: {action: delete, domain: "*"}         risk: HIGH
  - match: {action: purchase}                    risk: CRITICAL
```

---

## 6. Key API Contracts (JSON Schemas)

### IntentResult
```json
{
  "intent_id": "uuid",
  "language": "pl",
  "confidence": 0.97,
  "intent_type": "AUTOMATION",
  "action": "turn_off",
  "entities": {
    "device": "kitchen_lights",
    "location": "kitchen",
    "value": null,
    "time_expression": null
  },
  "raw_text": "Zgaś światło w kuchni",
  "normalized_text": "Turn off the lights in the kitchen"
}
```

### ExecutionPlan
```json
{
  "plan_id": "uuid",
  "intent_id": "uuid",
  "risk_level": "LOW",
  "requires_confirmation": false,
  "confirmation_method": null,
  "steps": [
    {
      "step_id": 1,
      "tool": "automation-adapter",
      "action": "call_ha_service",
      "params": { "domain": "light", "service": "turn_off", "entity_id": "light.kitchen_ceiling" },
      "idempotent": true,
      "timeout_ms": 5000,
      "retry_max": 2,
      "depends_on": []
    }
  ],
  "rollback_steps": [],
  "created_at": "2025-05-14T10:00:00Z"
}
```
`depends_on` enables parallel step execution where safe.

### SearchResult
```json
{
  "query_id": "uuid",
  "original_query": "What's the weather tomorrow?",
  "rewritten_query": "weather forecast Warsaw Poland 2025-05-15",
  "results": [
    {
      "rank": 1,
      "citation_id": "C1",
      "url": "https://www.meteo.pl/...",
      "title": "Prognoza pogody dla Warszawy",
      "content_extract": "Jutro w Warszawie spodziewamy się 18°C...",
      "relevance_score": 0.91,
      "fetched_at": "2025-05-14T10:00:05Z"
    }
  ],
  "synthesized_answer": "Tomorrow in Warsaw expect 18°C, partly cloudy. [C1]",
  "citations": ["C1: meteo.pl — Prognoza pogody dla Warszawy (2025-05-14)"],
  "search_duration_ms": 2340
}
```

---

## 7. Web Search Subsystem — All Bells & Whistles

```
query_rewrite (LLM)
       ↓
  SearXNG (self-hosted, aggregates Google + Brave + DDG + 70+ sources)
       ↓
  Top N URLs → parallel Playwright fetch → Trafilatura content extraction
       ↓
  BAAI/bge-reranker-v2-m3 cross-encoder (multilingual, handles Polish)
       ↓
  Top K passages + metadata → llm-service grounding prompt
       ↓
  Synthesized answer with inline [C1][C2] citations + full citation list
```

**Stack choices:**
- **SearXNG** — no meaningful self-hosted competition; runs in one Docker container
- **Trafilatura** — best open-source HTML→text extractor (beats BeautifulSoup, readability, newspaper3k in benchmarks)
- **Playwright** — pre-renders JS-heavy pages before Trafilatura extraction
- **bge-reranker-v2-m3** — multilingual cross-encoder, fits alongside other models, via FlagEmbedding
- **Brave Search API** — configured as SearXNG fallback source (not a direct code dependency)

---

## 8. Recommended Models

| Task | Model | VRAM | Source |
|---|---|---|---|
| Polish NLP / chat | Bielik-11B-v2.3-Instruct Q4_K_M | ~8 GB | HuggingFace: speakleash/Bielik-11B-v2.3-Instruct |
| Reasoning + tool use | Qwen3:8B (Q4 via Ollama) | ~5 GB | ollama pull qwen3:8b |
| Fast sub-tasks | Llama 3.2:3B | ~3 GB | ollama pull llama3.2:3b |
| STT | faster-whisper large-v3-turbo | ~6 GB (GPU) / CPU OK | wyoming-faster-whisper |
| TTS (Polish voice) | Piper1 medium PL voice | CPU only | OHF-Voice/piper1-gpl |
| Wake word | OpenWakeWord custom phrase | CPU only | openWakeWord |
| Reranker | BAAI/bge-reranker-v2-m3 | ~600 MB | FlagEmbedding |
| Lang detect | fastText lid.176.ftz | 917 KB CPU | Meta fastText |

**LLM serving:** Ollama (home use, single user, auto GPU offload, OpenAI-compatible API). vLLM is only worth the ops overhead at multi-user scale.

**Home Assistant integration:** Use the `ConversationEntity` custom agent API (`developers.home-assistant.io/docs/core/conversation/custom_agent`) — declare `supported_languages = ["pl", "en"]` and implement `_async_handle_message()`. Cleaner than polling REST.

---

## 9. Project Structure

```
homeai/
├── services/
│   ├── gateway/
│   ├── nlp-pipeline/
│   ├── llm-service/
│   ├── orchestrator/
│   ├── safety-gate/
│   ├── automation-adapter/
│   ├── web-search/
│   ├── voice-io/
│   ├── memory-store/
│   └── scheduler/
├── shared/
│   ├── models/          # Pydantic schemas (IntentResult, ExecutionPlan, SearchResult)
│   ├── nats_client/     # Shared NATS connection factory + topic constants
│   ├── config/          # Pydantic Settings base class, env loader
│   └── security/        # JWT validation, TOTP helpers, audit log writer
├── ui/
│   └── web-dashboard/   # Next.js 15 + Tailwind + WebSocket voice controls
├── infra/
│   ├── docker/          # Per-service Dockerfiles
│   ├── caddy/           # Caddyfile
│   ├── nats/            # nats-server.conf
│   └── scripts/         # bootstrap.sh, model-download.sh, backup.sh
├── data/
│   ├── models/          # GGUF weights, Whisper models, Piper voices
│   ├── ha-config/       # Home Assistant configuration.yaml
│   └── user-config/     # entity_aliases.yaml, risk_policy.yaml, user_prefs.yaml
├── tests/
│   ├── intent-fixtures/ # PL+EN labeled command examples for NLU evaluation
│   └── integration/
├── docker-compose.yml
└── .env.example
```

`shared/models` is the single source of truth for all inter-service Pydantic schemas. Schema drift between services is how multi-service Python projects rot.

---

## 10. Docker Compose Skeleton

```yaml
services:
  # Infrastructure
  nats:               # image: nats:2.10-alpine          ports: 4222, 8222
  redis:              # image: redis:7-alpine             ports: 6379   vol: redis-data
  chromadb:           # image: chromadb/chroma            ports: 8009   vol: chroma-data

  # Home Automation + AI
  home-assistant:     # image: ghcr.io/home-assistant/home-assistant  ports: 8123  network_mode: host
  searxng:            # image: searxng/searxng             ports: 8888 (internal only)
  ollama:             # image: ollama/ollama               ports: 11434  vol: ./data/models/ollama
                      #   deploy.resources.reservations.devices: [nvidia gpu] (optional)

  # Application Services
  gateway:            # build: ./services/gateway          ports: 8080  deps: nats, redis
  voice-io:           # build: ./services/voice-io          devices: /dev/snd  deps: nats
  nlp-pipeline:       # build: ./services/nlp-pipeline      ports: 8001  deps: nats
  llm-service:        # build: ./services/llm-service       ports: 8002  deps: ollama, nats
  orchestrator:       # build: ./services/orchestrator      ports: 8003  deps: nlp, llm, safety, adapter
  safety-gate:        # build: ./services/safety-gate       ports: 8004  deps: nats, redis
  automation-adapter: # build: ./services/automation-adapter ports: 8005 deps: nats, ha
  web-search:         # build: ./services/web-search         ports: 8006  deps: nats, searxng
  memory-store:       # build: ./services/memory-store       ports: 8007  deps: redis, chromadb
  scheduler:          # build: ./services/scheduler          ports: 8008  deps: nats, redis

  # Reverse proxy
  caddy:              # image: caddy:2-alpine   ports: 443, 80  deps: gateway
```

---

## 11. Hardware Tiers (EU/Poland, 2025 prices in EUR)

### Tier A — Budget (~380 EUR)

| Component | Part | EUR |
|---|---|---|
| Host | Beelink EQ12 Pro (Intel N100, 16GB RAM, 500GB NVMe) | 185 |
| Mic | RØDE NT-USB Mini | 65 |
| Zigbee | SONOFF Zigbee 3.0 USB Dongle Plus (CC2652P) | 20 |
| UPS | APC Back-UPS 700VA BX700UI | 50 |
| Misc | USB hub, cables | 15 |

CPU inference only. Use Whisper `small` + Qwen3:4B-Q4. Expect ~3-5 tok/s LLM, ~4-6s response. Best for: text-first prototyping + lightweight automations.

### Tier B — Balanced / Recommended (~1050 EUR)

| Component | Part | EUR |
|---|---|---|
| Host | MinisForum UM790 Pro (Ryzen 9 7940HS, 32GB DDR5, 512GB NVMe) | 420 |
| Storage | WD Black SN850X 2TB NVMe | 130 |
| Mic | ReSpeaker USB 4-Mic Array v2 | 45 |
| Zigbee + Thread | SONOFF Plus + HA SkyConnect | 45 |
| Z-Wave | Aeotec Z-Stick 7 Gen7 | 50 |
| UPS | APC Back-UPS 1000VA BX1000MI-GR | 110 |
| Speaker | Harman Kardon Go Play 3 (line-in) | 120 |
| Optional | Raspberry Pi 5 4GB (remote mic satellite node) | 75 |

Ryzen 9 7940HS iGPU (Radeon 780M) handles Whisper + Piper via ROCm (experimental). LLM CPU ~8-12 tok/s Q5_K_M. Adding a used RTX 3060 12GB eGPU (~180 EUR) pushes LLM to ~35-50 tok/s.

### Tier C — Premium (~2650 EUR)

| Component | Part | EUR |
|---|---|---|
| CPU | AMD Ryzen 7 9700X | 330 |
| Motherboard | ASRock B650I Lightning WiFi | 200 |
| RAM | 64GB DDR5-6000 (2×32GB Crucial Pro) | 150 |
| GPU | NVIDIA RTX 4070 Ti SUPER 16GB | 800 |
| NVMe | Samsung 990 Pro 2TB | 130 |
| HDD | Seagate IronWolf 8TB (backup) | 150 |
| Mic | ReSpeaker 6-Mic Circular Array (USB) | 90 |
| Zigbee + Thread | HA SkyConnect + SONOFF Plus | 45 |
| Z-Wave | Aeotec Z-Stick 7 | 50 |
| UPS | APC Smart-UPS 1500VA SMT1500IC (line-interactive, LAN) | 550 |
| Case + PSU | Fractal Node 304 + Seasonic Focus 650W Gold | 155 |

RTX 4070 Ti SUPER 16GB runs Llama 3.1 70B-Q4 at ~25 tok/s, or Bielik-11B at ~120 tok/s. 16GB VRAM lets Whisper large-v3 + Piper + 11B model coexist without swapping.

---

## 12. Memory Architecture

| Layer | Store | Scope | Eviction |
|---|---|---|---|
| Session context | Redis 7 (TTL 1h) | Current conversation turns | Auto-expire |
| Semantic memory | ChromaDB | Past summaries, routine patterns | Manual |
| Structured prefs | SQLite (WAL mode) | User names, room schedules, device aliases | Manual |
| Artifacts/transcripts | Local filesystem | Audio clips, logs | Cron cleanup |

**Migration path:** SQLite + ChromaDB for MVP. Migrate to **Mem0** (self-hosted Docker) when the SQLite schema becomes unmanageable. Upgrade to **Zep/Graphiti** for relationship-aware temporal memory (e.g., "user dims lights at 40% after 9pm when watching TV").

---

## 13. Security Baseline

- Secrets in SOPS-encrypted env files, never plain text in repo
- Network egress allowlist on web-search service (only SearXNG + approved APIs)
- Signed JWT for internal service-to-service calls
- Audit log for all tool actions and confirmations (append-only SQLite table)
- Encrypt backups; test restore monthly
- Prompt injection filtering on all content fetched from web before it reaches the LLM

---

## 14. Observability

- Traces: OpenTelemetry → Jaeger
- Metrics: Prometheus + Grafana
- Logs: Loki with PII redaction middleware
- Key KPIs: p95 request latency, tool success rate, citation rate, cloud fallback ratio, intent classifier confidence distribution

---

## 15. Build Roadmap

### Phase 1 — Text-first MVP (2-4 weeks)
- Text input only (no voice yet)
- NLP pipeline: fastText + XLM-RoBERTa + spaCy (PL+EN)
- 3 tools: lights, reminders, web search
- Basic safety gate + audit log
- Docker Compose single-host deployment

### Phase 2 — Full Voice (4-8 weeks)
- Wake word + STT + TTS pipeline
- Better reranking and citation quality
- Async scheduler for reminders/alarms
- Web dashboard with voice controls

### Phase 3 — Multi-user + Production (8-12+ weeks)
- Household user profiles with per-user policies
- Semantic memory with privacy controls
- k3s/Kubernetes for HA deployment
- Full NLU regression evaluation suite

---

## 16. Quick-Start Stack (Start Here)

**Hardware:** Tier B (MinisForum UM790 Pro) or any machine with 32GB RAM.

**Core software to install first:**
```
Home Assistant OS (or HAOS in VM)
Ollama + qwen3:8b + bielik:11b-q4
wyoming-faster-whisper + whisper turbo
Piper1 (Polish medium voice)
SearXNG (Docker)
Redis 7 + ChromaDB
OpenWakeWord
```

This gives best balance of speed, Polish language quality, privacy, and upgrade path.
Cloud LLM fallback (OpenAI/Anthropic) is opt-in only — expected < 10% of requests for cost control.
