# Graph Report - .  (2026-06-08)

## Corpus Check
- 22 files · ~0 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 376 nodes · 511 edges · 46 communities detected
- Extraction: 66% EXTRACTED · 34% INFERRED · 0% AMBIGUOUS · INFERRED: 175 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## God Nodes (most connected - your core abstractions)
1. `Memory` - 89 edges
2. `Settings` - 55 edges
3. `TestSettingsDefaults` - 18 edges
4. `_final_answer()` - 17 edges
5. `_make_llm_response()` - 14 edges
6. `TestSettingsEnvOverrides` - 14 edges
7. `TestExtractJson` - 13 edges
8. `run_pipeline()` - 9 edges
9. `TestMemoryAddRecent` - 9 edges
10. `TestMemorySlidingWindow` - 9 edges

## Surprising Connections (you probably didn't know these)
- `test_agent_brain.py — unit tests for agent_brain internals and run_pipeline.` --uses--> `Memory`  [INFERRED]
  tests\test_agent_brain.py → src\homeai\agent_brain.py
- `Serialize a well-formed ReAct step as a JSON string (what _llm_step returns).` --uses--> `Memory`  [INFERRED]
  tests\test_agent_brain.py → src\homeai\agent_brain.py
- `Convenience: a final_answer LLM response string.` --uses--> `Memory`  [INFERRED]
  tests\test_agent_brain.py → src\homeai\agent_brain.py
- `Fresh in-memory Memory instance for pipeline tests.` --uses--> `Memory`  [INFERRED]
  tests\test_agent_brain.py → src\homeai\agent_brain.py
- `Ensure react_max_iterations is at the documented default of 6.` --uses--> `Memory`  [INFERRED]
  tests\test_agent_brain.py → src\homeai\agent_brain.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.04
Nodes (38): BaseSettings, DEPRECATED — use src/homeai/config.py instead.  Legacy configuration module. A, Application-wide configuration loaded from environment variables or a .env file., Settings, test_config.py — unit tests for config.Settings.  Coverage:     - All field d, Log file defaults to a local path., Lowercase env var name is accepted (case_sensitive=False)., Mixed-case env var name is accepted. (+30 more)

### Community 1 - "Community 1"
Cohesion: 0.05
Nodes (37): Memory, Persists conversation turns in SQLite; exposes a fixed-size context window., Persists conversation turns in SQLite and exposes a fixed-size context window., Initialise the SQLite store and create the turns table if absent., Close the underlying SQLite connection., memory_db(), mock_settings(), conftest.py — shared pytest fixtures for the HomeAI test suite.  Fixtures prov (+29 more)

### Community 2 - "Community 2"
Cohesion: 0.08
Nodes (26): _final_answer(), _make_llm_response(), mem(), patch_settings_pipeline(), test_agent_brain.py — unit tests for agent_brain internals and run_pipeline., Fresh in-memory Memory instance for pipeline tests., Ensure react_max_iterations is at the documented default of 6., Pipeline calls web_search once, feeds the observation, then returns the final an (+18 more)

### Community 3 - "Community 3"
Cohesion: 0.05
Nodes (8): patch_settings(), test_tools.py — unit tests for tools.web_search, tools.home_service, and tools., Redirect all outgoing URLs to test doubles and inject a dummy HA token.     aut, TestHomeService, TestHomeState, TestWebSearchBothDown, TestWebSearchBraveFallback, TestWebSearchSearXNG

### Community 4 - "Community 4"
Cohesion: 0.09
Nodes (22): _build_tools_block(), _dispatch(), _extract_json(), _llm_step(), DEPRECATED — use src/homeai/agent_brain.py instead.  Legacy agent brain module, Return the last `window` user/assistant pairs in chronological order., Route a parsed LLM action to the corresponding tool and return observation text., One Ollama chat round; returns raw response text. (+14 more)

### Community 5 - "Community 5"
Cohesion: 0.08
Nodes (13): OLLAMA_MODEL env var replaces the default model name., OLLAMA_BASE_URL env var is applied correctly., LLM_TEMPERATURE is coerced from str to float., LLM_TIMEOUT_S is coerced from str to int., HA_TOKEN env var stores the provided token verbatim., HA_URL env var points to a custom HA instance., SEARXNG_URL env var is applied correctly., BRAVE_API_KEY env var is stored as a plain string. (+5 more)

### Community 6 - "Community 6"
Cohesion: 0.11
Nodes (11): test_memory.py — unit tests for agent_brain.Memory.  The Memory class wraps SQ, Turns added by one Memory instance are visible to a second instance         ope, A second Memory instance can add new turns that a third instance sees., All turns from a multi-turn conversation persist to disk., close() on an open connection completes without raising., The 'turns' table exists after __init__ (schema migration is idempotent)., recent() on a freshly created Memory returns []., recent() always returns a list, even when empty. (+3 more)

### Community 7 - "Community 7"
Cohesion: 0.15
Nodes (12): Return the text representation of this result for LLM consumption., Encapsulates the outcome of a single tool invocation., ToolResult, _ha_headers(), home_service(), home_state(), Build standard Home Assistant API authorisation headers., Call a Home Assistant service (e.g. light/turn_on, climate/set_temperature). (+4 more)

### Community 8 - "Community 8"
Cohesion: 0.13
Nodes (8): A single added turn is returned by recent()., Two turns come back oldest-first (chronological), not newest-first., Role strings are stored and returned verbatim., Polish diacritics in content are stored and retrieved without corruption., Emoji and non-Latin characters round-trip correctly., add() with an empty string does not raise and is retrievable., Strings longer than typical column sizes are stored in full., TestMemoryAddRecent

### Community 9 - "Community 9"
Cohesion: 0.13
Nodes (8): With window=2, at most 4 messages (2 pairs) are returned., The returned turns are the N most recent, not the oldest., When fewer messages exist than window*2, all messages are returned., When the number of messages equals window*2, all are returned., window=1 means at most 1 user + 1 assistant message returned., window=0 edge case: LIMIT 0 returns no rows., After window clamping the surviving turns are still oldest-first., TestMemorySlidingWindow

### Community 10 - "Community 10"
Cohesion: 0.18
Nodes (6): LLM responds with final_answer on the first iteration; pipeline returns the text, Polish-language user input and Polish answer text round-trip correctly., The final answer text is added to memory with role='assistant'., The user's input is added to memory before the LLM is called., action_input that is a plain string (not dict) is converted via str()., TestRunPipelineDirectAnswer

### Community 11 - "Community 11"
Cohesion: 0.5
Nodes (3): build_tools_block(), Tool schemas and system prompt template for the HomeAI ReAct agent.  Defines T, Render the tool registry as an indented text block for inclusion in the system p

### Community 12 - "Community 12"
Cohesion: 0.67
Nodes (1): One-off utility: add HTTP and ping monitors to Uptime Kuma via socket.io.  Conne

### Community 13 - "Community 13"
Cohesion: 0.67
Nodes (1): One-off utility: add ICMP ping monitors to Uptime Kuma via socket.io.  Connects

### Community 14 - "Community 14"
Cohesion: 1.0
Nodes (1): Project-root convenience runner; delegates to the homeai package entry point.

### Community 15 - "Community 15"
Cohesion: 1.0
Nodes (1): One-off utility: merge infrastructure-plan nodes into the knowledge graph.  Re

### Community 16 - "Community 16"
Cohesion: 1.0
Nodes (1): Reject log_level values that are not recognised Python logging levels.

### Community 17 - "Community 17"
Cohesion: 1.0
Nodes (1): Emit a warning when no web-search backend is configured.

### Community 18 - "Community 18"
Cohesion: 1.0
Nodes (1): SearXNG 200 with results produces a numbered list prefixed by query.

### Community 19 - "Community 19"
Cohesion: 1.0
Nodes (1): Only `search_results` (3) results are included even if SearXNG returns more.

### Community 20 - "Community 20"
Cohesion: 1.0
Nodes (1): SearXNG 200 with empty results list returns a 'no results' string.

### Community 21 - "Community 21"
Cohesion: 1.0
Nodes (1): When 'content' is absent, 'snippet' is used instead.

### Community 22 - "Community 22"
Cohesion: 1.0
Nodes (1): A query containing Polish diacritics appears verbatim in the output.

### Community 23 - "Community 23"
Cohesion: 1.0
Nodes (1): A 500 from SearXNG triggers a silent fallback to Brave Search.

### Community 24 - "Community 24"
Cohesion: 1.0
Nodes (1): A ConnectError from SearXNG triggers the Brave fallback.

### Community 25 - "Community 25"
Cohesion: 1.0
Nodes (1): When searxng_url is empty, Brave is the only path attempted.

### Community 26 - "Community 26"
Cohesion: 1.0
Nodes (1): Brave 200 with empty web results returns 'No results found.

### Community 27 - "Community 27"
Cohesion: 1.0
Nodes (1): When SearXNG is down and no Brave key, return an unavailability notice.

### Community 28 - "Community 28"
Cohesion: 1.0
Nodes (1): The original query string appears in the unavailability fallback message.

### Community 29 - "Community 29"
Cohesion: 1.0
Nodes (1): A 200 from HA services endpoint returns a success confirmation string.

### Community 30 - "Community 30"
Cohesion: 1.0
Nodes (1): HA returning 401 Unauthorized is surfaced as a string with the status code.

### Community 31 - "Community 31"
Cohesion: 1.0
Nodes (1): HA returning 403 Forbidden surfaces the status code in the return string.

### Community 32 - "Community 32"
Cohesion: 1.0
Nodes (1): A ConnectError is returned as a human-readable connection-error string.

### Community 33 - "Community 33"
Cohesion: 1.0
Nodes (1): Extra `data` kwargs are forwarded without error and success is reported.

### Community 34 - "Community 34"
Cohesion: 1.0
Nodes (1): home_service works for arbitrary HA domains (e.g., cover/open_cover).

### Community 35 - "Community 35"
Cohesion: 1.0
Nodes (1): The first 300 chars of HA error body appear in the returned error string.

### Community 36 - "Community 36"
Cohesion: 1.0
Nodes (1): A ReadTimeout is treated as a RequestError and returns a connection-error string

### Community 37 - "Community 37"
Cohesion: 1.0
Nodes (1): 200 response is formatted as 'friendly_name (entity): state=X | attrs'.

### Community 38 - "Community 38"
Cohesion: 1.0
Nodes (1): friendly_name is in the prefix but NOT repeated inside the attr_summary JSON.

### Community 39 - "Community 39"
Cohesion: 1.0
Nodes (1): A 404 from HA is surfaced as a string containing the status code.

### Community 40 - "Community 40"
Cohesion: 1.0
Nodes (1): ConnectError returns a human-readable HA connection error string.

### Community 41 - "Community 41"
Cohesion: 1.0
Nodes (1): Attribute summary JSON is capped at 400 characters.

### Community 42 - "Community 42"
Cohesion: 1.0
Nodes (1): Entity with empty attributes dict returns state without crashing.

### Community 43 - "Community 43"
Cohesion: 1.0
Nodes (1): Entity friendly_name containing Polish characters is not mangled.

### Community 44 - "Community 44"
Cohesion: 1.0
Nodes (1): When friendly_name is absent, the entity_id is used as the display name.

### Community 45 - "Community 45"
Cohesion: 1.0
Nodes (1): A 401 from the states endpoint surfaces the status code.

## Knowledge Gaps
- **66 isolated node(s):** `One-off utility: add HTTP and ping monitors to Uptime Kuma via socket.io.  Conne`, `One-off utility: add ICMP ping monitors to Uptime Kuma via socket.io.  Connects`, `DEPRECATED — use src/homeai/agent_brain.py instead.  Legacy agent brain module`, `Persists conversation turns in SQLite; exposes a fixed-size context window.`, `Return the last `window` user/assistant pairs in chronological order.` (+61 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 14`** (2 nodes): `run.py`, `Project-root convenience runner; delegates to the homeai package entry point.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 15`** (2 nodes): `update_graph.py`, `One-off utility: merge infrastructure-plan nodes into the knowledge graph.  Re`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 16`** (1 nodes): `Reject log_level values that are not recognised Python logging levels.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 17`** (1 nodes): `Emit a warning when no web-search backend is configured.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 18`** (1 nodes): `SearXNG 200 with results produces a numbered list prefixed by query.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 19`** (1 nodes): `Only `search_results` (3) results are included even if SearXNG returns more.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 20`** (1 nodes): `SearXNG 200 with empty results list returns a 'no results' string.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 21`** (1 nodes): `When 'content' is absent, 'snippet' is used instead.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 22`** (1 nodes): `A query containing Polish diacritics appears verbatim in the output.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 23`** (1 nodes): `A 500 from SearXNG triggers a silent fallback to Brave Search.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 24`** (1 nodes): `A ConnectError from SearXNG triggers the Brave fallback.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 25`** (1 nodes): `When searxng_url is empty, Brave is the only path attempted.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 26`** (1 nodes): `Brave 200 with empty web results returns 'No results found.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 27`** (1 nodes): `When SearXNG is down and no Brave key, return an unavailability notice.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 28`** (1 nodes): `The original query string appears in the unavailability fallback message.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 29`** (1 nodes): `A 200 from HA services endpoint returns a success confirmation string.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 30`** (1 nodes): `HA returning 401 Unauthorized is surfaced as a string with the status code.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 31`** (1 nodes): `HA returning 403 Forbidden surfaces the status code in the return string.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 32`** (1 nodes): `A ConnectError is returned as a human-readable connection-error string.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 33`** (1 nodes): `Extra `data` kwargs are forwarded without error and success is reported.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 34`** (1 nodes): `home_service works for arbitrary HA domains (e.g., cover/open_cover).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 35`** (1 nodes): `The first 300 chars of HA error body appear in the returned error string.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 36`** (1 nodes): `A ReadTimeout is treated as a RequestError and returns a connection-error string`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 37`** (1 nodes): `200 response is formatted as 'friendly_name (entity): state=X | attrs'.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 38`** (1 nodes): `friendly_name is in the prefix but NOT repeated inside the attr_summary JSON.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 39`** (1 nodes): `A 404 from HA is surfaced as a string containing the status code.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 40`** (1 nodes): `ConnectError returns a human-readable HA connection error string.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 41`** (1 nodes): `Attribute summary JSON is capped at 400 characters.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 42`** (1 nodes): `Entity with empty attributes dict returns state without crashing.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 43`** (1 nodes): `Entity friendly_name containing Polish characters is not mangled.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 44`** (1 nodes): `When friendly_name is absent, the entity_id is used as the display name.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 45`** (1 nodes): `A 401 from the states endpoint surfaces the status code.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Memory` connect `Community 1` to `Community 2`, `Community 4`, `Community 6`, `Community 7`, `Community 8`, `Community 9`, `Community 10`?**
  _High betweenness centrality (0.506) - this node is a cross-community bridge._
- **Why does `Settings` connect `Community 0` to `Community 5`, `Community 7`?**
  _High betweenness centrality (0.362) - this node is a cross-community bridge._
- **Why does `Tool implementations for web search and Home Assistant integration.` connect `Community 7` to `Community 0`, `Community 1`?**
  _High betweenness centrality (0.239) - this node is a cross-community bridge._
- **Are the 82 inferred relationships involving `Memory` (e.g. with `Tool implementations for web search and Home Assistant integration.` and `Configure the root logger from settings.`) actually correct?**
  _`Memory` has 82 INFERRED edges - model-reasoned connections that need verification._
- **Are the 52 inferred relationships involving `Settings` (e.g. with `Tool implementations for web search and Home Assistant integration.` and `Build standard Home Assistant API authorisation headers.`) actually correct?**
  _`Settings` has 52 INFERRED edges - model-reasoned connections that need verification._
- **Are the 15 inferred relationships involving `_final_answer()` (e.g. with `_make_llm_response()` and `.test_direct_final_answer_returns_text()`) actually correct?**
  _`_final_answer()` has 15 INFERRED edges - model-reasoned connections that need verification._
- **Are the 12 inferred relationships involving `_make_llm_response()` (e.g. with `_final_answer()` and `.test_web_search_tool_call_then_final_answer()`) actually correct?**
  _`_make_llm_response()` has 12 INFERRED edges - model-reasoned connections that need verification._