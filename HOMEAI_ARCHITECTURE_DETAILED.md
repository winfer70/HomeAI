# HomeAI - Detailed System Architecture

---

## 1. Full Service Map

Ten services, each with a single clear responsibility. All internal traffic is either HTTP/REST (synchronous request-response) or NATS (async pub/sub). NATS is chosen over Kafka or RabbitMQ because it is operationally trivial, supports at-most-once and at-least-once delivery, and has sub-millisecond latency at home scale.

| Service | Responsibility | Stack | Protocol |
|---|---|---|---|
| `gateway` | TLS termination, auth (JWT), WebSocket for voice streaming, request routing | FastAPI + Uvicorn, Caddy reverse proxy | Inbound: HTTPS/WSS. Outbound: HTTP to all services |
| `voice-io` | STT via faster-whisper (medium model, int8), TTS via Piper (pl_PL-darkman-medium + en_US-hfc_male), wake word via openWakeWord | Python, faster-whisper, piper-tts | WS stream in from gateway; NATS publish `voice.transcript`; consume `voice.synthesize` |
| `nlp-pipeline` | Language detection (fastText lid.176.ftz), intent classification, entity extraction | Python, fastText, spaCy (pl+en), XLM-RoBERTa fine-tuned on HA intents | HTTP sync from orchestrator |
| `llm-service` | Local LLM inference wrapper around Ollama; manages prompt templates; cloud fallback via Anthropic API | Python, Ollama (Llama 3.1 8B-Instruct-Q5_K_M default), httpx | HTTP sync; NATS for async completions |
| `orchestrator` | Stateful execution engine: parse plan -> guard -> execute steps -> compose response | Python, LangGraph state machine | HTTP in from gateway; HTTP out to all adapters; NATS for audit events |
| `safety-gate` | Risk scoring, policy evaluation, interactive confirmation flows | Python | HTTP sync from orchestrator; NATS publish `safety.confirmation_required` |
| `automation-adapter` | Wraps Home Assistant REST + WebSocket API; maps abstract entity names to HA entity_ids | Python, aiohttp | HTTP sync from orchestrator; NATS consume HA state changes |
| `web-search` | Query rewriting, SearXNG meta-search, Playwright content extraction, bge-reranker-v2-m3 reranking, citation packaging | Python, httpx, Playwright, sentence-transformers | HTTP sync from orchestrator |
| `memory-store` | Session context (Redis TTL=1h), long-term embeddings (ChromaDB), user preferences (SQLite) | Python, Redis 7, ChromaDB, SQLite | HTTP sync; NATS consume `memory.write` |
| `scheduler` | Reminders, alarms, cron jobs, timed automations | Python, APScheduler | NATS publish `scheduler.trigger`; HTTP from orchestrator to create/delete jobs |

**Key architectural decisions:**

- **Home Assistant as the automation backbone**: HA has 3000+ device integrations. The `automation-adapter` wraps it rather than reimplementing device control. This is the most important shortcut in the entire design.
- **Ollama not vLLM**: vLLM needs CUDA and is engineered for high-throughput. Ollama handles 1-10 concurrent home users, supports model swaps without config changes, and runs on CPU-only hardware.
- **NATS not Kafka**: Kafka requires ZooKeeper/KRaft and is over-engineered for a single home. NATS runs in a single container with 20MB RAM.
- **ChromaDB not pgvector**: Simpler ops than Postgres for a dedicated vector store at this scale. pgvector is kept as an option via the memory-store API contract.

---

## 2. Data Flow Diagrams

### (a) Simple voice command: "Zgaś światło w kuchni" / "Turn off the kitchen lights"

```
Microphone
    |
    | [PCM audio stream, WebSocket]
    v
voice-io  ----[faster-whisper STT]----> transcript: "Zgaś światło w kuchni"
    |
    | [HTTP POST /pipeline/process]
    v
gateway
    |
    | [HTTP POST /orchestrator/run]
    v
orchestrator
    |
    | [HTTP POST /nlp/parse]   <-- sync, ~80ms
    v
nlp-pipeline  --> fastText: lang=pl (0.99)
              --> XLM-RoBERTa: intent=AUTOMATION (0.97)
              --> spaCy NER: device=kitchen_lights, action=turn_off
              --> return IntentResult JSON
    |
    | [HTTP POST /safety/evaluate]
    v
safety-gate  --> risk_level=LOW, no confirmation needed
    |
    | [HTTP POST /automation/execute]
    v
automation-adapter
    | resolves "kitchen_lights" -> entity_id: "light.kitchen_ceiling"
    | [HA REST API: POST /api/services/light/turn_off]
    v
Home Assistant --> Zigbee coordinator --> bulb
    |
    | [HA WebSocket state_changed event]
    v
automation-adapter --> NATS publish "ha.state_changed" {entity_id, new_state: "off"}
    |
orchestrator receives state confirmation, composes response: "Zgaszono światło w kuchni."
    |
    | NATS publish "voice.synthesize"
    v
voice-io [Piper TTS] --> audio stream --> speaker

Total round-trip target: < 1200ms on Tier B hardware
```

### (b) Web search: "What's the weather tomorrow?"

```
voice-io [STT] --> gateway --> orchestrator
    |
    | nlp-pipeline: lang=en, intent=WEB_SEARCH, entities={topic: weather, time: tomorrow}
    |
    | [HTTP POST /search/query]
    v
web-search
    |-- query_rewrite: LLM prompt -> "weather forecast Warsaw Poland tomorrow"  (~200ms)
    |-- SearXNG meta-search (Google+Brave+DuckDuckGo) -> top 10 results (~800ms)
    |-- Playwright content extract: top 3 URLs -> raw text (~1500ms, parallel)
    |-- bge-reranker-v2-m3: rank 3 passages against query -> scored chunks
    |-- return SearchResult JSON with citations
    |
orchestrator -> llm-service
    | prompt: system=grounding_template + user=query + context=top_passages
    v
llm-service [Ollama Llama3.1 8B] -> "Tomorrow in Warsaw expect 18C, partly cloudy. [C1]"
    |
    | NATS "voice.synthesize" + citations appended
    v
voice-io TTS -> speaker

Total target: < 5s on Tier B, < 3s on Tier C (GPU inference)
```

### (c) High-risk command: "Unlock the front door"

```
voice-io [STT] --> gateway --> orchestrator
    |
    | nlp-pipeline: intent=LOCK_CONTROL, action=unlock, entity=front_door
    |
    | [HTTP POST /safety/evaluate]
    v
safety-gate
    | risk_level = HIGH (unlock_door is in HIGH_RISK_ACTIONS policy)
    | requires_confirmation = true
    | confirmation_method = voice_pin OR mobile_push
    |
    | NATS publish "safety.confirmation_required"
    v
gateway [WebSocket push to UI + voice prompt]
    "Potwierdzenie wymagane. Powiedz PIN lub zatwierdź w aplikacji."
    |
    | [user speaks PIN / taps approve in mobile app]
    v
safety-gate receives confirmation token
    | validates token (TOTP or signed push approval)
    | logs: {timestamp, user, action, confirmation_method, ip}
    |
    | [HTTP POST /automation/execute]
    v
automation-adapter -> HA -> Z-Wave lock controller -> front door unlocks
    |
    | NATS publish "audit.action_executed" (always written, regardless of outcome)
    v
orchestrator -> "Drzwi wejściowe odblokowane."
```

---

## 3. API Contracts

### IntentResult (nlp-pipeline response)

```json
{
  "intent_id": "550e8400-e29b-41d4-a716-446655440000",
  "language": "pl",
  "confidence": 0.97,
  "intent_type": "AUTOMATION",
  "action": "turn_off",
  "entities": {
    "device": "kitchen_lights",
    "location": "kitchen",
    "value": null,
    "time_expression": null,
    "duration_seconds": null
  },
  "raw_text": "Zgaś światło w kuchni",
  "normalized_text": "Turn off the lights in the kitchen"
}
```

### ExecutionPlan (orchestrator internal)

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
      "params": {
        "domain": "light",
        "service": "turn_off",
        "entity_id": "light.kitchen_ceiling"
      },
      "idempotent": true,
      "timeout_ms": 5000,
      "retry_max": 2
    }
  ],
  "rollback_steps": [],
  "created_at": "2025-05-14T10:00:00Z"
}
```

### SearchResult (web-search response)

```json
{
  "query_id": "uuid",
  "original_query": "What's the weather tomorrow?",
  "rewritten_query": "weather forecast Warsaw Poland tomorrow 2025-05-15",
  "results": [
    {
      "rank": 1,
      "citation_id": "C1",
      "url": "https://www.meteo.pl/...",
      "title": "Prognoza pogody dla Warszawy",
      "snippet": "15 maja 2025, temperatura 18C, zachmurzenie...",
      "content_extract": "Jutro w Warszawie spodziewamy się...",
      "relevance_score": 0.91,
      "fetched_at": "2025-05-14T10:00:05Z"
    }
  ],
  "synthesized_answer": "Tomorrow in Warsaw expect 18C, partly cloudy. [C1]",
  "citations": ["C1: meteo.pl — Prognoza pogody dla Warszawy (2025-05-14)"],
  "search_duration_ms": 2340
}
```

---

## 4. Folder / Project Structure

```
homeai/
├── services/
│   ├── gateway/            # FastAPI app, Caddy config
│   ├── nlp-pipeline/       # fastText, spaCy, XLM-RoBERTa inference
│   ├── llm-service/        # Ollama wrapper + prompt templates
│   ├── orchestrator/       # LangGraph state machine, plan executor
│   ├── safety-gate/        # Risk matrix, confirmation flows, audit writer
│   ├── automation-adapter/ # HA REST/WS client, entity name resolver
│   ├── web-search/         # SearXNG client, Playwright extractor, reranker
│   ├── voice-io/           # faster-whisper STT, Piper TTS, openWakeWord
│   ├── memory-store/       # Redis session, ChromaDB embeddings, SQLite prefs
│   └── scheduler/          # APScheduler, reminder/alarm CRUD
├── shared/
│   ├── models/             # Pydantic schemas: IntentResult, ExecutionPlan, SearchResult
│   ├── nats_client/        # Shared NATS connection factory + topic constants
│   ├── config/             # Pydantic Settings base class, env loader
│   └── security/           # JWT validation, TOTP helpers, audit log writer
├── ui/
│   └── web-dashboard/      # Next.js 15, Tailwind, WebSocket voice controls
├── infra/
│   ├── docker/             # Per-service Dockerfiles
│   ├── caddy/              # Caddyfile for TLS + reverse proxy
│   ├── nats/               # nats-server.conf
│   └── scripts/            # bootstrap.sh, model-download.sh, backup.sh
├── data/
│   ├── models/             # LLM GGUF weights, Whisper models, Piper voices
│   ├── ha-config/          # Home Assistant configuration.yaml, automations
│   └── user-config/        # user_prefs.yaml, entity_aliases.yaml, risk_policy.yaml
├── tests/
│   ├── intent-fixtures/    # PL + EN labeled command examples for NLU eval
│   └── integration/        # End-to-end test scenarios
├── docker-compose.yml
├── docker-compose.override.yml  # local dev overrides
└── .env.example
```

The `shared/models` package is the single source of truth for all inter-service schemas. Every service imports from it rather than defining its own Pydantic models. This prevents schema drift, which is the most common maintenance failure in multi-service Python projects.

---

## 5. Docker Compose Skeleton

```yaml
# Structure only — not a runnable file
services:

  nats:
    image: nats:2.10-alpine
    ports: ["4222:4222", "8222:8222"]   # NATS + monitoring
    volumes: ["./infra/nats/nats-server.conf:/etc/nats/nats.conf"]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    volumes: ["redis-data:/data"]

  chromadb:
    image: chromadb/chroma:0.5
    ports: ["8009:8000"]
    volumes: ["chroma-data:/chroma/chroma"]

  home-assistant:
    image: ghcr.io/home-assistant/home-assistant:stable
    ports: ["8123:8123"]
    volumes: ["./data/ha-config:/config"]
    network_mode: host   # required for mDNS/Zigbee device discovery

  searxng:
    image: searxng/searxng:latest
    ports: ["8888:8080"]   # internal only, not exposed to LAN
    volumes: ["./infra/searxng:/etc/searxng"]

  ollama:
    image: ollama/ollama:latest
    ports: ["11434:11434"]
    volumes: ["./data/models/ollama:/root/.ollama"]
    deploy:
      resources:
        reservations:
          devices: [{driver: nvidia, count: 1, capabilities: [gpu]}]  # optional

  gateway:
    build: ./services/gateway
    ports: ["8080:8080"]
    depends_on: [nats, redis]

  voice-io:
    build: ./services/voice-io
    volumes: ["./data/models/whisper:/models/whisper",
              "./data/models/piper:/models/piper"]
    devices: ["/dev/snd:/dev/snd"]
    depends_on: [nats, gateway]

  nlp-pipeline:
    build: ./services/nlp-pipeline
    ports: ["8001:8001"]
    volumes: ["./data/models/nlp:/models"]
    depends_on: [nats]

  llm-service:
    build: ./services/llm-service
    ports: ["8002:8002"]
    depends_on: [ollama, nats]

  orchestrator:
    build: ./services/orchestrator
    ports: ["8003:8003"]
    depends_on: [nats, nlp-pipeline, llm-service, safety-gate, automation-adapter]

  safety-gate:
    build: ./services/safety-gate
    ports: ["8004:8004"]
    depends_on: [nats, redis]

  automation-adapter:
    build: ./services/automation-adapter
    ports: ["8005:8005"]
    depends_on: [nats, home-assistant]

  web-search:
    build: ./services/web-search
    ports: ["8006:8006"]
    depends_on: [nats, searxng, llm-service]

  memory-store:
    build: ./services/memory-store
    ports: ["8007:8007"]
    depends_on: [redis, chromadb]

  scheduler:
    build: ./services/scheduler
    ports: ["8008:8008"]
    depends_on: [nats, redis]

  caddy:
    image: caddy:2-alpine
    ports: ["443:443", "80:80"]
    volumes: ["./infra/caddy/Caddyfile:/etc/caddy/Caddyfile",
              "caddy-data:/data"]
    depends_on: [gateway]

volumes:
  redis-data:
  chroma-data:
  caddy-data:
```

---

## 6. Hardware Tiers (2025, EU/Poland Market)

All prices in EUR, approximate retail (Allegro/Morele/Amazon.de).

### Tier A: Budget (~380 EUR total)

| Component | Recommendation | Price |
|---|---|---|
| Host | Beelink EQ12 Pro (Intel N100, 16GB RAM, 500GB NVMe) | 185 EUR |
| Extra RAM | Not needed (comes with 16GB) | — |
| Storage upgrade | Samsung 870 EVO 1TB SATA (if more space needed) | 60 EUR |
| Mic | RØDE NT-USB Mini | 65 EUR |
| Zigbee | SONOFF Zigbee 3.0 USB Dongle Plus (CC2652P) | 20 EUR |
| Z-Wave | None (add later) | — |
| Thread | None (HA Bluetooth can act as minimal border router) | — |
| UPS | APC Back-UPS 700VA BX700UI | 50 EUR |

Notes: CPU inference only. Whisper `small.en`/`small` model (244MB) recommended. Llama 3.1 8B-Q4_K_M runs at ~3-5 tok/s on N100. Expect 3-6s LLM responses.

### Tier B: Balanced — Recommended (~1050 EUR total)

| Component | Recommendation | Price |
|---|---|---|
| Host | MinisForum UM790 Pro (Ryzen 9 7940HS, 32GB DDR5, 512GB NVMe) | 420 EUR |
| Storage | WD Black SN850X 2TB NVMe (main) | 130 EUR |
| Mic | ReSpeaker USB 4-Mic Array v2 | 45 EUR |
| Zigbee + Thread | SONOFF Zigbee USB Dongle Plus + Home Assistant SkyConnect | 45 EUR |
| Z-Wave | Aeotec Z-Stick 7 (700 series, Gen7) | 50 EUR |
| UPS | APC Back-UPS 1000VA BX1000MI-GR | 110 EUR |
| Speaker | Harman Kardon Go Play 3 (line-in or Bluetooth, local only) | 120 EUR |
| Raspberry Pi 5 4GB (satellite mic node, optional) | 75 EUR | |

Notes: Ryzen 9 7940HS integrated Radeon 780M can offload Whisper and Piper to iGPU via ROCm (experimental). LLM on CPU at ~8-12 tok/s with Q5_K_M. Add a used RTX 3060 12GB eGPU (~180 EUR) to cut LLM inference to ~35-50 tok/s.

### Tier C: Premium (~2650 EUR total)

| Component | Recommendation | Price |
|---|---|---|
| Host | Custom ITX build: AMD Ryzen 7 9700X | 330 EUR |
| Motherboard | ASRock B650I Lightning WiFi | 200 EUR |
| RAM | 64GB DDR5-6000 (2x32GB Crucial Pro) | 150 EUR |
| GPU | NVIDIA RTX 4070 Ti SUPER 16GB | 800 EUR |
| Storage | Samsung 990 Pro 2TB NVMe (OS+models) + Seagate IronWolf 8TB (media) | 280 EUR |
| Mic | ReSpeaker 6-Mic Circular Array Kit (USB) | 90 EUR |
| Zigbee + Thread | Home Assistant SkyConnect + SONOFF Plus | 45 EUR |
| Z-Wave | Aeotec Z-Stick 7 | 50 EUR |
| UPS | APC Smart-UPS 1500VA SMT1500IC (line-interactive, LAN card) | 550 EUR |
| Case + PSU | Fractal Design Node 304 + Seasonic Focus 650W Gold | 155 EUR |

Notes: RTX 4070 Ti SUPER runs Llama 3.1 70B-Q4_K_M at ~25 tok/s or Llama 3.1 8B at ~120 tok/s. Enables running the reranker, Whisper large-v3, and Piper simultaneously without latency stacking.

---

## 7. NLP Pipeline Detail

### Step 1: Language Detection (< 5ms)

- Model: fastText `lid.176.ftz` (917KB, 176 languages)
- Decision: if `confidence > 0.85`, use detected language. If ambiguous, check for Polish diacritics (ą ę ó ś ź ż ć ń ł) as a tiebreaker, then default to English.
- This runs before anything else, including the LLM. It gates which spaCy model and which prompt templates are used downstream.

### Step 2: Intent Classification (< 80ms)

- Primary: XLM-RoBERTa-base fine-tuned on a custom dataset of ~2000 labeled PL+EN home automation commands. 8 classes: `AUTOMATION`, `WEB_SEARCH`, `REMINDER`, `ALARM`, `MEDIA_CONTROL`, `THERMOSTAT`, `STATUS_QUERY`, `UNKNOWN`.
- Fallback: if classifier confidence < 0.70, call `llm-service` with a few-shot classification prompt (adds ~400ms).
- The fine-tuned model runs on CPU in ~60ms; the LLM fallback costs time but handles novel phrasings the classifier was not trained on.

### Step 3: Entity Extraction (< 100ms)

- spaCy `pl_core_news_sm` (Polish) or `en_core_web_sm` (English) for base NER (dates, times, persons).
- Custom spaCy `EntityRuler` patterns loaded from `data/user-config/entity_aliases.yaml`. This file maps user-defined names ("kuchnia", "salon", "lampka przy biurku") to canonical HA entity IDs. The user maintains this file; no retraining required.
- Time expressions parsed by `dateparser` library (supports Polish month names, relative times like "za godzinę", "pojutrze").

### Step 4: Plan Generation (orchestrator, not nlp-pipeline)

- The orchestrator receives the `IntentResult` and performs entity resolution: fuzzy-match `entities.device` against the HA entity registry (fetched at startup, refreshed every 5 minutes).
- Risk scoring uses a static policy matrix in `data/user-config/risk_policy.yaml`. Example rules: `{action: unlock, domain: lock} -> HIGH`, `{action: turn_off, domain: light} -> LOW`, `{action: delete, domain: *} -> HIGH`.
- The plan is assembled as an `ExecutionPlan` (see schema above) with ordered steps, timeouts, and rollback definitions.

### Plan Object JSON Schema (condensed)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ExecutionPlan",
  "type": "object",
  "required": ["plan_id", "intent_id", "risk_level", "steps"],
  "properties": {
    "plan_id":             { "type": "string", "format": "uuid" },
    "intent_id":           { "type": "string", "format": "uuid" },
    "risk_level":          { "type": "string", "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"] },
    "requires_confirmation": { "type": "boolean" },
    "confirmation_method": { "type": ["string", "null"], "enum": ["voice_pin", "mobile_push", "totp", null] },
    "steps": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["step_id", "tool", "action", "params"],
        "properties": {
          "step_id":     { "type": "integer" },
          "tool":        { "type": "string", "enum": ["automation-adapter", "web-search", "scheduler", "memory-store", "llm-service"] },
          "action":      { "type": "string" },
          "params":      { "type": "object" },
          "idempotent":  { "type": "boolean", "default": false },
          "timeout_ms":  { "type": "integer", "default": 5000 },
          "retry_max":   { "type": "integer", "default": 2 },
          "depends_on":  { "type": "array", "items": { "type": "integer" } }
        }
      }
    },
    "rollback_steps": { "type": "array" },
    "created_at": { "type": "string", "format": "date-time" }
  }
}
```

The `depends_on` field in each step allows the orchestrator to execute independent steps in parallel (e.g., dim lights and start music simultaneously) while respecting ordering constraints (e.g., check lock state before unlocking).

---

## Key Tradeoffs Summary

**NATS over Redis pub/sub**: Redis pub/sub has no persistence; a service restart drops messages. NATS JetStream adds durable consumers without Kafka's operational weight.

**XLM-RoBERTa classifier + LLM fallback over LLM-only**: A single LLM call for every intent costs 200-400ms minimum. The classifier handles 90% of known commands in 60ms; the LLM only activates for genuinely ambiguous input. The latency budget is where users feel quality, not in model parameter counts.

**Home Assistant as automation layer over direct Zigbee/Z-Wave control**: Direct radio control means writing and maintaining device drivers. HA gives 3000+ integrations, a tested state machine, and an entity model. The `automation-adapter` is a thin wrapper; its entire value is translating HomeAI's abstract entity names into HA's entity_ids. Never bypass HA.

**SQLite for preferences over Postgres**: User preferences are written rarely and read on every request. SQLite with WAL mode handles this perfectly and eliminates a Postgres container from the minimal deployment. Postgres is needed only if semantic search is moved from ChromaDB to pgvector, which is a valid later-stage migration.
