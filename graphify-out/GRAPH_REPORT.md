# Graph Report - .  (2026-09-02)

## Corpus Check
- 69 files · ~0 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 600 nodes · 822 edges · 87 communities detected
- Extraction: 63% EXTRACTED · 37% INFERRED · 0% AMBIGUOUS · INFERRED: 302 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## God Nodes (most connected - your core abstractions)
1. `Memory` - 89 edges
2. `Settings` - 55 edges
3. `TestSettingsDefaults` - 18 edges
4. `_final_answer()` - 17 edges
5. `_make_llm_response()` - 14 edges
6. `TestSettingsEnvOverrides` - 14 edges
7. `TestExtractJson` - 13 edges
8. `run_matrix()` - 12 edges
9. `RowResult` - 10 edges
10. `run_pipeline()` - 9 edges

## Surprising Connections (you probably didn't know these)
- `conftest.py — shared pytest fixtures for the HomeAI test suite.  Fixtures prov` --uses--> `Memory`  [INFERRED]
  tests\conftest.py → src\homeai\agent_brain.py
- `Patch every external-service URL and credential in the global Settings     sing` --uses--> `Memory`  [INFERRED]
  tests\conftest.py → src\homeai\agent_brain.py
- `In-memory SQLite Memory instance with a sliding window of 3 turns.     Closed a` --uses--> `Memory`  [INFERRED]
  tests\conftest.py → src\homeai\agent_brain.py
- `Memory instance backed by a real temporary file, for testing persistence     ac` --uses--> `Memory`  [INFERRED]
  tests\conftest.py → src\homeai\agent_brain.py
- `A single added turn is returned by recent().` --uses--> `Memory`  [INFERRED]
  tests\test_memory.py → src\homeai\agent_brain.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.03
Nodes (81): Memory, Persists conversation turns in SQLite; exposes a fixed-size context window., Persists conversation turns in SQLite and exposes a fixed-size context window., Initialise the SQLite store and create the turns table if absent., Close the underlying SQLite connection., main(), Configure the root logger from settings., Interactive REPL loop that processes user input through the ReAct pipeline. (+73 more)

### Community 1 - "Community 1"
Cohesion: 0.03
Nodes (50): BaseSettings, Application-wide configuration loaded from environment variables or a .env file., Settings, test_config.py — unit tests for config.Settings.  Coverage:     - All field d, Log file defaults to a local path., OLLAMA_MODEL env var replaces the default model name., OLLAMA_BASE_URL env var is applied correctly., LLM_TEMPERATURE is coerced from str to float. (+42 more)

### Community 2 - "Community 2"
Cohesion: 0.06
Nodes (30): _build_tools_block(), _dispatch(), _extract_json(), _llm_step(), DEPRECATED — use src/homeai/agent_brain.py instead.  Legacy agent brain module, Return the last `window` user/assistant pairs in chronological order., Route a parsed LLM action to the corresponding tool and return observation text., One Ollama chat round; returns raw response text. (+22 more)

### Community 3 - "Community 3"
Cohesion: 0.05
Nodes (8): patch_settings(), test_tools.py — unit tests for tools.web_search, tools.home_service, and tools., Redirect all outgoing URLs to test doubles and inject a dummy HA token.     aut, TestHomeService, TestHomeState, TestWebSearchBothDown, TestWebSearchBraveFallback, TestWebSearchSearXNG

### Community 4 - "Community 4"
Cohesion: 0.1
Nodes (17): API, Return the text representation of this result for LLM consumption., Encapsulates the outcome of a single tool invocation., ToolResult, _ha_headers(), home_service(), home_state(), Build standard Home Assistant API authorisation headers. (+9 more)

### Community 5 - "Community 5"
Cohesion: 0.17
Nodes (21): _db(), extract(), ExtractIn, ExtractOut, Fact, FactIn, get_context(), _init_db() (+13 more)

### Community 6 - "Community 6"
Cohesion: 0.25
Nodes (17): _apply_known_limitations(), check_ambiguous_mixed(), check_aquarium_read(), check_calendar_read(), check_calendar_write(), check_climate(), _check_exposure_ws(), check_gate_exposure() (+9 more)

### Community 7 - "Community 7"
Cohesion: 0.16
Nodes (17): AlarmExposureError, assert_no_alarm_exposure(), _iter_patterns(), Scan an arbitrary JSON-like payload for forbidden references., Raise if the payload contains any forbidden alarm references., One forbidden alarm-reference match found during scanning., Raised when forbidden alarm-related content is detected., Scan raw text and return all forbidden matches. (+9 more)

### Community 8 - "Community 8"
Cohesion: 0.13
Nodes (8): A single added turn is returned by recent()., Two turns come back oldest-first (chronological), not newest-first., Role strings are stored and returned verbatim., Polish diacritics in content are stored and retrieved without corruption., Emoji and non-Latin characters round-trip correctly., add() with an empty string does not raise and is retrievable., Strings longer than typical column sizes are stored in full., TestMemoryAddRecent

### Community 9 - "Community 9"
Cohesion: 0.26
Nodes (10): authenticate(), _extract(), HaWebSocket, _is_processed(), main(), _mark_processed(), poll_once(), Tiny helper around HA's WebSocket API with auto-incrementing message ids. (+2 more)

### Community 10 - "Community 10"
Cohesion: 0.42
Nodes (8): BenchmarkResult, _collect_samples(), _expected_language(), _load_model(), main(), _parse_args(), _print_result(), _transcribe_sample()

### Community 11 - "Community 11"
Cohesion: 0.53
Nodes (8): activate_workflow(), deploy_workflow(), ensure_credential(), find_credential_id(), find_workflow_id(), load_workflow_definition(), main(), _request()

### Community 12 - "Community 12"
Cohesion: 0.39
Nodes (5): assert_no_alarm_entities(), authenticate(), HaWebSocket, main(), Tiny helper around HA's WebSocket API with auto-incrementing message ids.

### Community 13 - "Community 13"
Cohesion: 0.57
Nodes (6): call_ollama(), evaluate(), main(), PromptResult, run_bakeoff(), write_results_md()

### Community 14 - "Community 14"
Cohesion: 0.43
Nodes (4): authenticate(), HaWebSocket, main(), Tiny helper around HA's WebSocket API with auto-incrementing message ids.

### Community 15 - "Community 15"
Cohesion: 0.43
Nodes (4): authenticate(), HaWebSocket, main(), Tiny helper around HA's WebSocket API with auto-incrementing message ids.

### Community 16 - "Community 16"
Cohesion: 0.6
Nodes (5): _append_to_soak_log(), _load_since(), main(), poll_once(), _save_since()

### Community 17 - "Community 17"
Cohesion: 0.7
Nodes (4): ask_model(), build_context(), fetch_states(), main()

### Community 18 - "Community 18"
Cohesion: 0.4
Nodes (0): 

### Community 19 - "Community 19"
Cohesion: 0.67
Nodes (3): load_monitors(), main(), One-off utility: add HTTP and ping monitors to Uptime Kuma via socket.io.  Con

### Community 20 - "Community 20"
Cohesion: 0.67
Nodes (3): load_ping_monitors(), main(), One-off utility: add ICMP ping monitors to Uptime Kuma via socket.io.  Configu

### Community 21 - "Community 21"
Cohesion: 0.67
Nodes (3): load_monitor(), main(), One-off utility: add an HTTP monitor for a swarm-api endpoint to Uptime Kuma.

### Community 22 - "Community 22"
Cohesion: 0.67
Nodes (3): add_credentials(), main(), Heimdall Task 5 (M4) — add Google Calendar OAuth Application Credentials to HA.

### Community 23 - "Community 23"
Cohesion: 0.83
Nodes (3): call_ha_service(), main(), query_influx_recent_points()

### Community 24 - "Community 24"
Cohesion: 0.5
Nodes (3): build_tools_block(), Tool schemas and system prompt template for the HomeAI ReAct agent.  Defines T, Render the tool registry as an indented text block for inclusion in the system p

### Community 25 - "Community 25"
Cohesion: 1.0
Nodes (2): _collect_paths(), main()

### Community 26 - "Community 26"
Cohesion: 1.0
Nodes (2): call(), main()

### Community 27 - "Community 27"
Cohesion: 0.67
Nodes (0): 

### Community 28 - "Community 28"
Cohesion: 1.0
Nodes (0): 

### Community 29 - "Community 29"
Cohesion: 1.0
Nodes (0): 

### Community 30 - "Community 30"
Cohesion: 1.0
Nodes (0): 

### Community 31 - "Community 31"
Cohesion: 1.0
Nodes (0): 

### Community 32 - "Community 32"
Cohesion: 1.0
Nodes (0): 

### Community 33 - "Community 33"
Cohesion: 1.0
Nodes (0): 

### Community 34 - "Community 34"
Cohesion: 1.0
Nodes (0): 

### Community 35 - "Community 35"
Cohesion: 1.0
Nodes (0): 

### Community 36 - "Community 36"
Cohesion: 1.0
Nodes (0): 

### Community 37 - "Community 37"
Cohesion: 1.0
Nodes (0): 

### Community 38 - "Community 38"
Cohesion: 1.0
Nodes (0): 

### Community 39 - "Community 39"
Cohesion: 1.0
Nodes (0): 

### Community 40 - "Community 40"
Cohesion: 1.0
Nodes (0): 

### Community 41 - "Community 41"
Cohesion: 1.0
Nodes (0): 

### Community 42 - "Community 42"
Cohesion: 1.0
Nodes (0): 

### Community 43 - "Community 43"
Cohesion: 1.0
Nodes (0): 

### Community 44 - "Community 44"
Cohesion: 1.0
Nodes (0): 

### Community 45 - "Community 45"
Cohesion: 1.0
Nodes (0): 

### Community 46 - "Community 46"
Cohesion: 1.0
Nodes (0): 

### Community 47 - "Community 47"
Cohesion: 1.0
Nodes (0): 

### Community 48 - "Community 48"
Cohesion: 1.0
Nodes (0): 

### Community 49 - "Community 49"
Cohesion: 1.0
Nodes (0): 

### Community 50 - "Community 50"
Cohesion: 1.0
Nodes (0): 

### Community 51 - "Community 51"
Cohesion: 1.0
Nodes (0): 

### Community 52 - "Community 52"
Cohesion: 1.0
Nodes (0): 

### Community 53 - "Community 53"
Cohesion: 1.0
Nodes (1): Project-root convenience runner; delegates to the homeai package entry point.

### Community 54 - "Community 54"
Cohesion: 1.0
Nodes (1): One-off utility: merge infrastructure-plan nodes into the knowledge graph.  Re

### Community 55 - "Community 55"
Cohesion: 1.0
Nodes (0): 

### Community 56 - "Community 56"
Cohesion: 1.0
Nodes (0): 

### Community 57 - "Community 57"
Cohesion: 1.0
Nodes (1): Reject log_level values that are not recognised Python logging levels.

### Community 58 - "Community 58"
Cohesion: 1.0
Nodes (1): Emit a warning when no web-search backend is configured.

### Community 59 - "Community 59"
Cohesion: 1.0
Nodes (1): SearXNG 200 with results produces a numbered list prefixed by query.

### Community 60 - "Community 60"
Cohesion: 1.0
Nodes (1): Only `search_results` (3) results are included even if SearXNG returns more.

### Community 61 - "Community 61"
Cohesion: 1.0
Nodes (1): SearXNG 200 with empty results list returns a 'no results' string.

### Community 62 - "Community 62"
Cohesion: 1.0
Nodes (1): When 'content' is absent, 'snippet' is used instead.

### Community 63 - "Community 63"
Cohesion: 1.0
Nodes (1): A query containing Polish diacritics appears verbatim in the output.

### Community 64 - "Community 64"
Cohesion: 1.0
Nodes (1): A 500 from SearXNG triggers a silent fallback to Brave Search.

### Community 65 - "Community 65"
Cohesion: 1.0
Nodes (1): A ConnectError from SearXNG triggers the Brave fallback.

### Community 66 - "Community 66"
Cohesion: 1.0
Nodes (1): When searxng_url is empty, Brave is the only path attempted.

### Community 67 - "Community 67"
Cohesion: 1.0
Nodes (1): Brave 200 with empty web results returns 'No results found.

### Community 68 - "Community 68"
Cohesion: 1.0
Nodes (1): When SearXNG is down and no Brave key, return an unavailability notice.

### Community 69 - "Community 69"
Cohesion: 1.0
Nodes (1): The original query string appears in the unavailability fallback message.

### Community 70 - "Community 70"
Cohesion: 1.0
Nodes (1): A 200 from HA services endpoint returns a success confirmation string.

### Community 71 - "Community 71"
Cohesion: 1.0
Nodes (1): HA returning 401 Unauthorized is surfaced as a string with the status code.

### Community 72 - "Community 72"
Cohesion: 1.0
Nodes (1): HA returning 403 Forbidden surfaces the status code in the return string.

### Community 73 - "Community 73"
Cohesion: 1.0
Nodes (1): A ConnectError is returned as a human-readable connection-error string.

### Community 74 - "Community 74"
Cohesion: 1.0
Nodes (1): Extra `data` kwargs are forwarded without error and success is reported.

### Community 75 - "Community 75"
Cohesion: 1.0
Nodes (1): home_service works for arbitrary HA domains (e.g., cover/open_cover).

### Community 76 - "Community 76"
Cohesion: 1.0
Nodes (1): The first 300 chars of HA error body appear in the returned error string.

### Community 77 - "Community 77"
Cohesion: 1.0
Nodes (1): A ReadTimeout is treated as a RequestError and returns a connection-error string

### Community 78 - "Community 78"
Cohesion: 1.0
Nodes (1): 200 response is formatted as 'friendly_name (entity): state=X | attrs'.

### Community 79 - "Community 79"
Cohesion: 1.0
Nodes (1): friendly_name is in the prefix but NOT repeated inside the attr_summary JSON.

### Community 80 - "Community 80"
Cohesion: 1.0
Nodes (1): A 404 from HA is surfaced as a string containing the status code.

### Community 81 - "Community 81"
Cohesion: 1.0
Nodes (1): ConnectError returns a human-readable HA connection error string.

### Community 82 - "Community 82"
Cohesion: 1.0
Nodes (1): Attribute summary JSON is capped at 400 characters.

### Community 83 - "Community 83"
Cohesion: 1.0
Nodes (1): Entity with empty attributes dict returns state without crashing.

### Community 84 - "Community 84"
Cohesion: 1.0
Nodes (1): Entity friendly_name containing Polish characters is not mangled.

### Community 85 - "Community 85"
Cohesion: 1.0
Nodes (1): When friendly_name is absent, the entity_id is used as the display name.

### Community 86 - "Community 86"
Cohesion: 1.0
Nodes (1): A 401 from the states endpoint surfaces the status code.

## Knowledge Gaps
- **83 isolated node(s):** `One-off utility: add HTTP and ping monitors to Uptime Kuma via socket.io.  Con`, `One-off utility: add ICMP ping monitors to Uptime Kuma via socket.io.  Configu`, `One-off utility: add an HTTP monitor for a swarm-api endpoint to Uptime Kuma.`, `DEPRECATED — use src/homeai/agent_brain.py instead.  Legacy agent brain module`, `Persists conversation turns in SQLite; exposes a fixed-size context window.` (+78 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 28`** (2 nodes): `add_pulse_gate_script.py`, `main()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 29`** (2 nodes): `assign_siren_area.py`, `main()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 30`** (2 nodes): `check_boost_exposure.py`, `main()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 31`** (2 nodes): `check_dashboard_reload.py`, `main()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 32`** (2 nodes): `check_radiator_dashboard.py`, `main()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 33`** (2 nodes): `clear_climate_alias.py`, `main()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 34`** (2 nodes): `expose_boost_heating.py`, `main()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 35`** (2 nodes): `expose_missing_entities.py`, `main()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 36`** (2 nodes): `fix_gemini_prompt_completeness.py`, `main()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 37`** (2 nodes): `fix_qwen_area_filter_and_model.py`, `main()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 38`** (2 nodes): `inspect_area_registry.py`, `main()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 39`** (2 nodes): `inspect_climate_devices.py`, `main()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 40`** (2 nodes): `inspect_climate_exposure.py`, `main()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 41`** (2 nodes): `inspect_climate_features.py`, `main()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 42`** (2 nodes): `inspect_climate_registry.py`, `main()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 43`** (2 nodes): `inspect_conversation_traces.py`, `main()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 44`** (2 nodes): `inspect_exposed_entities.py`, `main()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 45`** (2 nodes): `inspect_hidden_entities.py`, `main()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 46`** (2 nodes): `inspect_meross_outlets.py`, `main()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 47`** (2 nodes): `inspect_office_area.py`, `main()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 48`** (2 nodes): `inspect_satellite_entities.py`, `main()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 49`** (2 nodes): `list_areas.py`, `main()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 50`** (2 nodes): `move_alarm_secrets_to_package.py`, `main()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 51`** (2 nodes): `reload_and_verify_boost_scripts.py`, `main()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 52`** (2 nodes): `rename_entities.py`, `main()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 53`** (2 nodes): `run.py`, `Project-root convenience runner; delegates to the homeai package entry point.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 54`** (2 nodes): `update_graph.py`, `One-off utility: merge infrastructure-plan nodes into the knowledge graph.  Re`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 55`** (1 nodes): `benchmark_gpu_baseline.ps1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 56`** (1 nodes): `Load-EnvLocal.ps1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 57`** (1 nodes): `Reject log_level values that are not recognised Python logging levels.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 58`** (1 nodes): `Emit a warning when no web-search backend is configured.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 59`** (1 nodes): `SearXNG 200 with results produces a numbered list prefixed by query.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 60`** (1 nodes): `Only `search_results` (3) results are included even if SearXNG returns more.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 61`** (1 nodes): `SearXNG 200 with empty results list returns a 'no results' string.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 62`** (1 nodes): `When 'content' is absent, 'snippet' is used instead.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 63`** (1 nodes): `A query containing Polish diacritics appears verbatim in the output.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 64`** (1 nodes): `A 500 from SearXNG triggers a silent fallback to Brave Search.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 65`** (1 nodes): `A ConnectError from SearXNG triggers the Brave fallback.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 66`** (1 nodes): `When searxng_url is empty, Brave is the only path attempted.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 67`** (1 nodes): `Brave 200 with empty web results returns 'No results found.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 68`** (1 nodes): `When SearXNG is down and no Brave key, return an unavailability notice.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 69`** (1 nodes): `The original query string appears in the unavailability fallback message.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 70`** (1 nodes): `A 200 from HA services endpoint returns a success confirmation string.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 71`** (1 nodes): `HA returning 401 Unauthorized is surfaced as a string with the status code.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 72`** (1 nodes): `HA returning 403 Forbidden surfaces the status code in the return string.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 73`** (1 nodes): `A ConnectError is returned as a human-readable connection-error string.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 74`** (1 nodes): `Extra `data` kwargs are forwarded without error and success is reported.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 75`** (1 nodes): `home_service works for arbitrary HA domains (e.g., cover/open_cover).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 76`** (1 nodes): `The first 300 chars of HA error body appear in the returned error string.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 77`** (1 nodes): `A ReadTimeout is treated as a RequestError and returns a connection-error string`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 78`** (1 nodes): `200 response is formatted as 'friendly_name (entity): state=X | attrs'.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 79`** (1 nodes): `friendly_name is in the prefix but NOT repeated inside the attr_summary JSON.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 80`** (1 nodes): `A 404 from HA is surfaced as a string containing the status code.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 81`** (1 nodes): `ConnectError returns a human-readable HA connection error string.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 82`** (1 nodes): `Attribute summary JSON is capped at 400 characters.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 83`** (1 nodes): `Entity with empty attributes dict returns state without crashing.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 84`** (1 nodes): `Entity friendly_name containing Polish characters is not mangled.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 85`** (1 nodes): `When friendly_name is absent, the entity_id is used as the display name.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 86`** (1 nodes): `A 401 from the states endpoint surfaces the status code.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Memory` connect `Community 0` to `Community 8`, `Community 2`, `Community 4`?**
  _High betweenness centrality (0.205) - this node is a cross-community bridge._
- **Why does `Settings` connect `Community 1` to `Community 2`, `Community 4`?**
  _High betweenness centrality (0.147) - this node is a cross-community bridge._
- **Why does `Tool implementations for web search and Home Assistant integration.` connect `Community 4` to `Community 0`, `Community 1`?**
  _High betweenness centrality (0.107) - this node is a cross-community bridge._
- **Are the 82 inferred relationships involving `Memory` (e.g. with `Tool implementations for web search and Home Assistant integration.` and `Configure the root logger from settings.`) actually correct?**
  _`Memory` has 82 INFERRED edges - model-reasoned connections that need verification._
- **Are the 52 inferred relationships involving `Settings` (e.g. with `Tool implementations for web search and Home Assistant integration.` and `Build standard Home Assistant API authorisation headers.`) actually correct?**
  _`Settings` has 52 INFERRED edges - model-reasoned connections that need verification._
- **Are the 15 inferred relationships involving `_final_answer()` (e.g. with `_make_llm_response()` and `.test_direct_final_answer_returns_text()`) actually correct?**
  _`_final_answer()` has 15 INFERRED edges - model-reasoned connections that need verification._
- **Are the 12 inferred relationships involving `_make_llm_response()` (e.g. with `_final_answer()` and `.test_web_search_tool_call_then_final_answer()`) actually correct?**
  _`_make_llm_response()` has 12 INFERRED edges - model-reasoned connections that need verification._