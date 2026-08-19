# Heimdall memory service

Small FastAPI app (Task 8, M7) providing Heimdall's persistent
cross-session memory: a `facts` table (subject/predicate/object) and a
`summaries` table (rolling per-household narrative), backed by SQLite.

Two write paths feed this store:
- **Explicit tool calls** — HA scripts `heimdall_remember_fact` /
  `heimdall_recall_facts`, exposed to Assist, callable by either
  conversation agent (Gemini or the local Ollama model) via
  `rest_command:` entries in HA's `configuration.yaml`.
- **Background poller** (`heimdall/scripts/memory_poller.py`) — polls HA's
  Assist pipeline-debug WebSocket API for new conversation runs and sends
  full transcripts to `/extract`, which asks the local model to pull out
  any facts the tool-based path missed plus refresh the rolling summary.
  This is the safety net for general conversational continuity, since not
  every worthwhile detail will trigger an explicit remember_fact call.

## Endpoints

- `POST /facts` — `{subject, predicate, object, language?, source, conversation_id?}`
  Upserts one fact (unique on `subject`+`predicate` - latest value wins).
- `GET /facts/search?q=...` — naive substring search across subject/predicate/object.
- `GET /memory/context` — `{summary, facts: [...], text}` - `text` is a
  ready-to-inject plain-text block for prompt templates.
- `POST /extract` — `{conversation_id, language, transcript: [{speaker, text}, ...]}`
  Sends the transcript to Ollama for fact/summary extraction, upserts results.
- `GET /health` — liveness check, no auth required.

All endpoints except `/health` require header `X-Heimdall-Memory-Token`
matching the `HEIMDALL_MEMORY_TOKEN` environment variable.

## Running

```
docker compose -f heimdall/docker-compose.memory.yml up -d
```
