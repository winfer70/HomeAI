# HomeAI

Local-first bilingual home assistant that understands Polish and English voice and text commands, controls smart home devices via Home Assistant, and answers questions with cited web search results. The entire reasoning loop runs on your hardware via Ollama — no cloud required for core operation.

## Prerequisites

- [ ] Python 3.11 or later
- [ ] [Ollama](https://ollama.com) installed and running (`ollama serve`)
- [ ] Home Assistant with a long-lived access token generated
- [ ] SearXNG running in Docker, or a Brave Search API key for the cloud fallback
- [ ] Git

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/yourname/homeai.git
cd homeai

# 2. Install the package in editable mode with dev dependencies
pip install -e ".[dev]"

# 3. Copy and edit the environment file
cp .env.example .env
# Open .env and set HA_TOKEN and adjust URLs

# 4. Pull the default reasoning model
ollama pull qwen3:8b

# 5. Run
python -m homeai
```

The prompt `You:` appears when the agent is ready. Type in Polish or English. Press `Ctrl+C` or `Ctrl+D` to exit.

## Configuration Reference

All variables are read from `.env` (or the shell environment). Keys are case-insensitive.

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Base URL of the Ollama API server. Change if Ollama runs in Docker or on another host. |
| `OLLAMA_MODEL` | `qwen3:8b` | Model tag passed to Ollama. Any chat model available locally works. |
| `LLM_TEMPERATURE` | `0.1` | Sampling temperature. Keep at or below `0.2` for predictable JSON tool-call output. |
| `LLM_TIMEOUT_S` | `90` | Seconds before an Ollama request is abandoned. Increase on slow CPU-only hardware. |
| `REACT_MAX_ITERATIONS` | `6` | Maximum ReAct loop iterations per user turn before the fallback message is returned. |
| `HA_URL` | `http://homeassistant.local:8123` | Base URL of the Home Assistant instance. Use an IP address if mDNS is unreliable. |
| `HA_TOKEN` | *(required)* | HA long-lived access token. Generate at HA → Profile → Security → Long-lived access tokens. |
| `HA_TIMEOUT_S` | `10` | Seconds before a Home Assistant REST call is abandoned. |
| `SEARXNG_URL` | `http://localhost:8888` | Base URL of the SearXNG instance. Leave empty to skip SearXNG and go straight to the Brave fallback. |
| `BRAVE_API_KEY` | *(empty)* | Brave Search API key. Used as fallback when SearXNG is unreachable. |
| `SEARCH_RESULTS` | `5` | Number of search results to retrieve and pass to the LLM as context. |
| `SEARCH_TIMEOUT_S` | `15` | Seconds before a search request is abandoned. |
| `MEMORY_DB_PATH` | `./homeai_memory.db` | Path to the SQLite database that stores conversation turns. Created automatically on first run. |
| `MEMORY_WINDOW` | `10` | Number of conversation turn-pairs (user + assistant) kept in the LLM context window per request. |
| `LOG_LEVEL` | `INFO` | Python logging level: `DEBUG`, `INFO`, `WARNING`, or `ERROR`. |
| `LOG_FILE` | `./homeai.log` | Path for the persistent log file. Written alongside the stdout stream. |

### Minimal `.env` for development

```
HA_TOKEN=your_token_here
SEARXNG_URL=http://localhost:8888
```

All other settings can remain at their defaults.

## Architecture

```
User (voice / text)
 │
 ▼
voice-io ─────── STT (faster-whisper) · TTS (Piper)     [Phase 2]
 │
 ▼
gateway ──────── auth · rate-limit · request-id          [Phase 2]
 │
 ▼
orchestrator ─── ReAct loop (agent_brain.py)
 │               Ollama qwen3:8b · SQLite memory (sliding window)
 │
 ├── tools ─────┬─ home_service ──► Home Assistant REST API
 │              ├─ home_state   ──► Home Assistant REST API
 │              └─ web_search   ──► SearXNG ──► Brave API (fallback)
 │
 ▼
response (text / TTS audio back to user)
```

The LLM plans; the dispatcher executes. The model never calls an API directly. All tool observations are fed back as messages so the model can chain multiple calls. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full request lifecycle.

## Example Interactions

### Polish home automation

```
You: Zgaś światło w kuchni i salonie.
HomeAI: Zgaszono światło w kuchni i salonie.
```

### English web search

```
You: What is the current price of electricity in Poland?
HomeAI: As of the latest data, residential electricity in Poland costs
        approximately 0.78 PLN/kWh (Tauron, G11 tariff). [1]
        [1] https://www.tauron.pl — Tauron cennik energii 2025
```

### Polish conditional command

```
You: Jeśli temperatura w salonie jest poniżej 20°C, włącz ogrzewanie.
HomeAI: Obecna temperatura w salonie to 18.5°C. Ogrzewanie zostało włączone.
```

## Development

### Run tests

```bash
pytest tests/ -v
```

### Type checking

```bash
mypy src/homeai --strict
```

### Linting and formatting

```bash
ruff check src/ tests/
ruff format src/ tests/
```

### All checks in one pass

```bash
ruff check src/ tests/ && mypy src/homeai --strict && pytest tests/ -v
```

## Project Structure

```
homeai/
├── src/
│   └── homeai/
│       ├── __init__.py
│       ├── __main__.py       # CLI entry point
│       ├── config.py         # Pydantic Settings (all config from .env)
│       ├── agent_brain.py    # ReAct loop, Memory, JSON extraction
│       ├── prompts.py        # System prompt templates and tool schemas
│       ├── py.typed          # PEP 561 marker
│       └── tools/
│           ├── base.py       # ToolResult dataclass
│           ├── search.py     # web_search (SearXNG + Brave fallback)
│           └── home_assistant.py  # home_service, home_state
├── tests/
│   ├── conftest.py
│   ├── test_config.py
│   ├── test_tools.py
│   ├── test_memory.py
│   └── test_agent_brain.py
├── docs/
│   ├── ARCHITECTURE.md
│   └── CONTRIBUTING.md
├── HOMEAI_ARCHITECTURE.md    # Full multi-service architecture blueprint
├── pyproject.toml
├── run.py                    # Shim → python -m homeai
└── .env.example
```

## Troubleshooting

**Ollama is not running**
Symptom: `RuntimeError: Ollama connection error` in the log.
Fix: Run `ollama serve` in a separate terminal. Verify with `curl http://localhost:11434/api/tags`.

**Home Assistant token is wrong or expired**
Symptom: Tool observations contain `HA service error 401`.
Fix: Generate a new long-lived access token at HA → Profile → Security → Long-lived access tokens. Update `HA_TOKEN` in `.env`.

**SearXNG is unreachable**
Symptom: Log shows `SearXNG unavailable — trying Brave API fallback`. If `BRAVE_API_KEY` is also empty, observations read `Web search unavailable`.
Fix: Ensure SearXNG is running: `docker ps | grep searxng`. Or set `BRAVE_API_KEY` as a standalone fallback.

**Model outputs malformed JSON**
Symptom: Log shows `Malformed JSON on iteration N — asking model to retry`.
Fix: Lower `LLM_TEMPERATURE` to `0.0`. If persistent, switch to a larger model: `ollama pull qwen3:14b`.

**Memory database grows too large**
Symptom: `homeai_memory.db` consuming significant disk space.
Fix: `MEMORY_WINDOW` controls how many turns are sent to the LLM, not how many are stored. To prune:
```bash
sqlite3 homeai_memory.db "DELETE FROM turns WHERE id NOT IN (SELECT id FROM turns ORDER BY id DESC LIMIT 1000);"
```

## License

MIT
