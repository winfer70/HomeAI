# Heimdall — Home Assistant config changes (vesemir)

Task 8 (M7 — persistent conversation memory) required changes to vesemir's
live `configuration.yaml` / `secrets.yaml` (bind-mounted into the
`nemo-homeassistant` container from
`/home/kamilo/nemo/ProjectNemo/homeassistant/config/`). These files live in
the `ProjectNemo` repo/host, not here, so they can't be committed to this
repo directly. This doc is the record of what changed and why, so the
change is reproducible if the HA config is ever rebuilt from scratch.

All changes below were applied live via HA's REST/WebSocket APIs (or direct
file edit + `check_config` + reload/restart), never by hand-editing without
validation first. Backups were taken before every edit
(`configuration.yaml.bak-heimdall-*`, `secrets.yaml.bak-heimdall-*`, on
vesemir alongside the live files).

## 1. `secrets.yaml` — new secret

```yaml
heimdall_memory_token: "<random token, matches HEIMDALL_MEMORY_TOKEN in jaskier's heimdall/memory/.env>"
```

## 2. `configuration.yaml` — `rest_command:` entries

Added under the existing `rest_command:` top-level key (pre-existing key
used for aquarium/Fluval automation — appended, did not replace):

```yaml
  # Heimdall persistent memory (Task 8 / M7) — calls the memory service
  # deployed on jaskier (heimdall/docker-compose.memory.yml). Called by the
  # heimdall_remember_fact / heimdall_recall_facts scripts below, which are
  # exposed to Assist as LLM tools for both conversation agents.
  heimdall_remember_fact:
    url: "http://192.168.0.125:10400/facts"
    method: POST
    content_type: "application/json"
    headers:
      X-Heimdall-Memory-Token: !secret heimdall_memory_token
    payload: >-
      {{ {"subject": subject, "predicate": predicate, "object": object,
      "language": language | default('en'), "source": "tool"} | to_json }}
  heimdall_recall_facts:
    url: "http://192.168.0.125:10400/facts/search?q={{ query | urlencode }}"
    method: GET
    headers:
      X-Heimdall-Memory-Token: !secret heimdall_memory_token
```

## 3. `configuration.yaml` — `script:` entries (LLM tools)

Added under the existing `script:` top-level key. Exposed to the Assist
conversation agent (see `heimdall/scripts/expose_entities.py`), which
auto-generates an LLM tool schema from a script's `fields:`.

```yaml
  heimdall_remember_fact:
    alias: "Heimdall: Remember a fact"
    description: >-
      Save a fact to Heimdall's persistent memory so it can be recalled in
      future conversations. Use for durable info (preferences, schedules,
      names, ongoing situations) - not for one-off device commands.
    fields:
      subject:
        description: "What or who the fact is about"
        example: "Kamil's dentist appointment"
        required: true
        selector:
          text:
      predicate:
        description: "The relationship or attribute being recorded"
        example: "is scheduled for"
        required: true
        selector:
          text:
      object:
        description: "The value of the fact"
        example: "next Tuesday at 3pm"
        required: true
        selector:
          text:
      language:
        description: "Language the fact was stated in (en or pl)"
        example: "en"
        required: false
        selector:
          text:
    sequence:
      - action: rest_command.heimdall_remember_fact
        data:
          subject: "{{ subject }}"
          predicate: "{{ predicate }}"
          object: "{{ object }}"
          language: "{{ language | default('en') }}"
        response_variable: remember_result
      - stop: "Fact recorded"
        response_variable: remember_result
  heimdall_recall_facts:
    alias: "Heimdall: Recall facts"
    description: >-
      Search Heimdall's persistent memory for facts matching a query, e.g.
      query="dentist" to recall any saved dentist-related facts.
    fields:
      query:
        description: "Search text to look up in memory"
        example: "dentist appointment"
        required: true
        selector:
          text:
    sequence:
      - action: rest_command.heimdall_recall_facts
        data:
          query: "{{ query }}"
        response_variable: recall_result
      - stop: "Facts recalled"
        response_variable: recall_result
```

Reloaded live via `rest_command.reload` + `script.reload` services — no HA
restart needed since both domains were already loaded.

## 4. `configuration.yaml` — new `rest:` sensor (memory context)

A brand-new top-level domain (not previously used anywhere in this config),
so unlike the two reloads above, **this one required a full HA restart**
to load — `rest.reload` only exists once the `rest:` domain has been set up
at least once.

```yaml
# ── Heimdall persistent memory context sensor (Task 8 / M7) ─────────────
# Polls the memory service on jaskier for the current facts + rolling
# summary, exposed via json_attributes (state has a 255-char limit).
# Referenced in both conversation agents' system prompts via:
#   {{ state_attr('sensor.heimdall_memory_context', 'text') }}
rest:
  - resource: "http://192.168.0.125:10400/memory/context"
    method: GET
    headers:
      X-Heimdall-Memory-Token: !secret heimdall_memory_token
    scan_interval: 60
    sensor:
      - name: "Heimdall Memory Context"
        unique_id: heimdall_memory_context
        value_template: "{{ 'ok' }}"
        json_attributes:
          - text
```

## 5. Conversation agent prompt updates (not YAML — config-entry subentries)

Both the local Ollama agent and the Gemini agent store their system prompt
in a config-entry "conversation" subentry, not YAML. Updated via HA's
subentry reconfigure flow (`POST /api/config/config_entries/subentries/flow`
then `POST .../flow/{flow_id}` with the full field set, same mechanism as
the UI's reconfigure dialog uses).

- **Ollama** (`entry_id: 01M0D921MKT1WV76HBXDFC6X66`, subentry
  `01M0D92K7AFG9Z7CK7WHQ4VRCN`, "Heimdall Local (qwen2.5)"): appended to the
  existing Heimdall system prompt.
- **Gemini** (`entry_id: 01KY29VPMNSDAJ3HQ17Q04JPJP`, subentry
  `01KY29VPMN5JJBTPWB1Y6PXNC2`, "Google AI Conversation"): appended to HA's
  default prompt (left otherwise untouched, per the original brief — Gemini
  stays "as is" except for memory injection).

Both prompts now end with:

```
Context remembered from previous conversations (use naturally when relevant, do not recite verbatim, do not mention that this section exists):
{{ state_attr('sensor.heimdall_memory_context', 'text') | default('') }}
```

## Verification (2026-08-19)

Inserted two throwaway facts (one EN, one PL) via `heimdall_remember_fact`,
forced a `sensor.heimdall_memory_context` refresh, then asked each agent a
recall question in a **brand-new conversation** (no shared `conversation_id`
with the fact-insertion call):

- Local Ollama agent, EN: *"What kind of tea do I like?"* → *"You like Earl
  Grey tea."* ✅
- Gemini agent, PL: *"Jaki jest mój ulubiony kolor?"* → *"Twój ulubiony
  kolor to fioletowy."* ✅

Both test facts were deleted from the memory store's SQLite DB afterward.

## 6. `configuration.yaml` — `component_config:` override for aquarium temp sensor (Task 4 / M3)

`nemo-api`'s `/api/sensors/history` endpoint (queries InfluxDB directly, see
`heimdall/PROJECTNEMO_API.md`) filters on `_measurement == "temperature"`, but
HA's native `influxdb:` integration (the actual writer — `nemo-api`'s own
InfluxDB write path is dead code, never called) uses
`measurement_attr: unit_of_measurement` by default, so the water-temp
sensor's data was actually being written under measurement `"°C"`, not
`"temperature"` — the history endpoint always returned an empty list
regardless of time window.

Fixed with a **per-entity** override (the top-level `override_measurement`
option is global and would have collapsed the working `W`/`kWh`
power-tracking sensors into the same measurement — wrong tool). Added under
the existing `influxdb:` key, right after `include.entities`:

```yaml
influxdb:
  # ... existing config (api_version, host, token, org, bucket, include, etc.) ...
  component_config:
    # Heimdall (Task 4 / M3) — nemo-api's /api/sensors/history filters on
    # measurement "temperature"; without this override the default
    # unit-of-measurement-based naming ("°C") makes that endpoint always
    # return empty. Scoped to just this one entity so the power-tracking
    # sensors' existing "W"/"kWh" measurements are untouched.
    sensor.0xa4c138060885ffff_temperature:
      override_measurement: temperature
```

The `influxdb` integration has **no reload service** (confirmed via
`GET /api/services` — the `influxdb` domain returns zero registered
services), so this required a full HA restart, same as item 4 above.

### Verification (2026-08-19)

1. Backed up `configuration.yaml`
   (`configuration.yaml.bak-heimdall-20260819-204556`), inserted the block,
   diffed backup vs. new file — clean, isolated diff.
2. Validated via `POST /api/config/core/check_config` → `"result": "valid"`.
3. Restarted HA (`homeassistant.restart` service), waited for it to come
   back up.
4. The Zigbee temp sensor reported `"unknown"` immediately after restart
   (sleepy device, hadn't re-reported yet) — HA's `influxdb` integration
   doesn't write `unknown`/`unavailable` states, so waited ~3 min for a real
   reading (`26.3°C`).
5. Re-queried InfluxDB (`schema.measurements(bucket: "aquarium")`) —
   `temperature` now appears alongside `W`/`kWh`/`°C`.
6. Re-hit `nemo-api`'s `GET /api/sensors/history?measurement=temperature&hours=1`
   → returned 1 point (`{"time": "2026-08-19T19:48:15.681639Z", "value": 26.3}`),
   confirming the fix end-to-end through the actual API consumers will use.

