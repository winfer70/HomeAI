# HomeAI Architecture

MVP single-process architecture. For the full multi-service production target, see [`HOMEAI_ARCHITECTURE.md`](../HOMEAI_ARCHITECTURE.md).

## Component Responsibilities

| Component | File | Responsibility |
|---|---|---|
| `Settings` | `src/homeai/config.py` | Single source of truth for all configuration. Loaded from `.env` at startup; validated by Pydantic. Imported as a singleton `settings` by every module. |
| `Memory` | `src/homeai/agent_brain.py` | Persists every user and assistant turn to SQLite. `recent()` returns the last `window * 2` rows for injection into the LLM context window. |
| `run_pipeline()` | `src/homeai/agent_brain.py` | Entry point for one user turn. Builds the message list, drives the ReAct iteration loop, dispatches tool calls, and returns the final answer string. |
| `_llm_step()` | `src/homeai/agent_brain.py` | One round-trip to the Ollama `/api/chat` endpoint with `format: json`. Returns the raw response string. |
| `_extract_json()` | `src/homeai/agent_brain.py` | Robust JSON extractor: tries direct parse, then markdown-fence strip, then regex. Raises `ValueError` only when all three fail. |
| `_dispatch()` | `src/homeai/agent_brain.py` | Routes the LLM's chosen `action` to the correct tool function. Returns a plain observation string for re-injection. |
| `ToolResult` | `src/homeai/tools/base.py` | Dataclass contract shared by all tools: `ok: bool`, `output: str`, `error: str \| None`. |
| `web_search()` | `src/homeai/tools/search.py` | Queries SearXNG (primary) then Brave Search API (fallback). Returns up to `SEARCH_RESULTS` formatted results. |
| `home_service()` | `src/homeai/tools/home_assistant.py` | Calls a Home Assistant service via `POST /api/services/{domain}/{service}`. |
| `home_state()` | `src/homeai/tools/home_assistant.py` | Fetches current state and attributes of a HA entity via `GET /api/states/{entity_id}`. |
| `TOOL_SCHEMAS` | `src/homeai/prompts.py` | Tool registry read by the LLM to learn what tools are available and how to call them. |
| `__main__.py` | `src/homeai/__main__.py` | REPL loop. Initializes logging, creates `Memory`, calls `run_pipeline()`, prints responses. Handles SIGTERM and KeyboardInterrupt. |

---

## Request Lifecycle: "Zgaś światło w kuchni" to bulb off

**1. Input received**

`__main__.py` reads input and passes it to `run_pipeline(user_input, memory)`.

**2. Context assembly**

`run_pipeline()` builds:
```
[system prompt with tool schemas (from prompts.py)]
[...memory.recent() — last N turn-pairs from SQLite...]
[{"role": "user", "content": "Zgaś światło w kuchni"}]
```
The user turn is written to SQLite immediately.

**3. First LLM call — state check**

`_llm_step()` posts to Ollama. `_extract_json()` parses the response:
```json
{
  "thought": "User wants the kitchen light off. I'll check the entity state first.",
  "action": "home_state",
  "action_input": {"entity_id": "light.kitchen_ceiling"}
}
```

**4. Tool dispatch — home_state**

`_dispatch()` calls `home_state("light.kitchen_ceiling")` → `GET /api/states/light.kitchen_ceiling`.
Observation: `Kuchnia sufit (light.kitchen_ceiling): state=on | {"brightness": 200}`

**5. Observation injected**

```
[assistant]: <raw LLM JSON from step 3>
[user]:      Observation: Kuchnia sufit (light.kitchen_ceiling): state=on | ...
```

**6. Second LLM call — service call**

```json
{
  "thought": "Light is on. I will turn it off.",
  "action": "home_service",
  "action_input": {"domain": "light", "service": "turn_off", "entity_id": "light.kitchen_ceiling"}
}
```

**7. Tool dispatch — home_service**

`POST /api/services/light/turn_off` → HA → Zigbee → bulb off.
Observation: `OK: light.turn_off on light.kitchen_ceiling succeeded.`

**8. Third LLM call — final answer**

```json
{
  "thought": "Service call succeeded.",
  "action": "final_answer",
  "action_input": {"text": "Zgaszono światło w kuchni."}
}
```

**9. Response returned**

`run_pipeline()` extracts the text, writes it to SQLite, and returns it to `__main__.py` for display.

**Total:** 3 LLM calls, 2 HA API calls. A faster path skips `home_state` when the entity ID is unambiguous (2 LLM calls, 1 HA call).

---

## ReAct Loop

The loop is ~100 lines of plain Python in `run_pipeline()`. No framework required.

### Loop invariant

Each iteration:
1. Call `_llm_step(messages)` — one Ollama round-trip.
2. Parse with `_extract_json()`.
3. `action == "final_answer"` → extract text and return.
4. `action` is a known tool → dispatch, append observation, continue.
5. JSON malformed → append correction message, retry (does not count as an iteration).
6. `react_max_iterations` reached → return bilingual fallback string.

### Example ReAct trace — conditional command

**Turn:** `"Jaka jest temperatura? Jeśli poniżej 5°C, włącz ogrzewanie."`

| Iter | Output | Observation |
|---|---|---|
| 1 | `web_search("aktualna temperatura Warszawa")` | `[1] meteo.pl — Aktualna temperatura: 3°C.` |
| 2 | `home_service("climate", "turn_on", "climate.salon")` | `OK: climate.turn_on on climate.salon succeeded.` |
| 3 | `final_answer("Temperatura 3°C — ogrzewanie włączone.")` | — |

### Malformed JSON recovery

When all three extraction strategies fail, the correction message added is:

```
Your response was not valid JSON. Output a single JSON object only,
with keys: thought, action, action_input.
```

This recovery does not consume an iteration count, so the model effectively gets one free retry per malformed response.

---

## Memory Model

### What gets stored

Only `user` and `assistant` turns are persisted. Tool calls and intermediate observations are ephemeral — they exist in the in-memory `messages` list for the duration of one `run_pipeline()` call only.

### SQLite schema

```sql
CREATE TABLE IF NOT EXISTS turns (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ts      TEXT    NOT NULL,   -- UTC ISO 8601 timestamp
    role    TEXT    NOT NULL,   -- "user" or "assistant"
    content TEXT    NOT NULL
);
```

### Window size and context injection

`Memory.recent()` executes:
```sql
SELECT role, content FROM turns ORDER BY id DESC LIMIT :window_times_2
```
Results are reversed to chronological order before injection. Turns beyond the window are retained in SQLite but never sent to the LLM.

**Example with `MEMORY_WINDOW=3` and 10 stored turns:** `recent()` returns turns 5–10 (3 most recent pairs). Turns 1–4 remain on disk but are invisible to the current request.

---

## Tool Contract

### ToolResult

```python
@dataclass
class ToolResult:
    ok: bool           # True if the tool completed without error
    output: str        # Observation injected into the LLM message list
    error: str | None = None  # Present when ok=False
```

`_dispatch()` calls `result.output` on success and `f"Tool error: {result.error}"` on failure.

### How observations reach the LLM

```python
messages.append({"role": "assistant", "content": raw_llm_json})
messages.append({"role": "user",      "content": f"Observation: {observation}"})
```

The `Observation:` prefix signals to the model that the next content is factual input to reason over, not a new user command.

### Tool output size

Keep `output` under 500 characters. The model reads the full observation on every subsequent iteration — long outputs waste context window and slow down inference. Existing tools truncate content snippets at 350 characters and attribute JSON summaries at 400 characters.
