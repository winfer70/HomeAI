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


## 7. `configuration.yaml` — `rest_command`/`script` for aquarium temperature history (Task 4 / M3 addendum)

Manual voice testing after item 6 above surfaced a real gap: the local agent
could read the *current* aquarium temperature and toggle switches, but asked
"has the temperature changed recently?" it just restated the live value and
(on a follow-up) admitted historical data wasn't available. Task 4 bypassed
`nemo-api`'s previously-broken history endpoint (see `PROJECTNEMO_API.md`)
but never built a replacement tool for the agent to call it — closing that
gap here, using the same `rest_command`/`script` pattern as Task 8's memory
tools.

Added a new `rest_command` (scoped to `measurement=temperature` only —
`ph`/`tds`/`orp` measurement names were never fixed, so exposing those would
let the agent silently get misleading empty results):

```yaml
rest_command:
  # ... existing entries (set_fluval_channels, heimdall_remember_fact, etc.) ...
  heimdall_aquarium_temp_history:
    url: "http://nemo-api:8000/api/sensors/history?measurement=temperature&hours={{ hours | default(24) }}"
    method: GET
```

And a new `script` that calls it, computes a min/max/latest summary (kept
deliberately small/human-readable rather than handing the LLM a raw JSON
array), and returns it via `response_variable`:

```yaml
script:
  # ... existing entries (heimdall_remember_fact, heimdall_recall_facts, etc.) ...
  heimdall_aquarium_temp_history:
    alias: "Heimdall: Aquarium temperature history"
    description: >-
      Get a summary of the aquarium water temperature over a recent time
      window (min/max/latest reading), not just the current value. Use this
      when asked about temperature trends or "has it changed recently" -
      the current-state read alone cannot answer that.
    fields:
      hours:
        description: "How many hours back to look (1-168, default 24)"
        example: "24"
        required: false
        selector:
          number:
            min: 1
            max: 168
    sequence:
      - action: rest_command.heimdall_aquarium_temp_history
        data:
          hours: "{{ hours | default(24) | int }}"
        response_variable: history_result
      - variables:
          points: "{{ history_result.content if history_result.content is iterable and history_result.content is not string else [] }}"
          history_summary:
            summary: >-
              {% if points | count == 0 %}
              No aquarium temperature history available for that time range.
              {% else %}
              Over the last {{ hours | default(24) | int }} hour(s): {{ points | count }} readings,
              min {{ points | map(attribute='value') | min }}°C,
              max {{ points | map(attribute='value') | max }}°C,
              latest {{ points[-1].value }}°C at {{ points[-1].time }}.
              {% endif %}
      - stop: "Temperature history retrieved"
        response_variable: history_summary
```

Both domains reload live (`rest_command.reload` + `script.reload`) — no HA
restart needed, unlike item 6 above.

### Three real bugs found and fixed while wiring this up

1. **`from_json` on an already-parsed response.** HA's `rest_command`
   `response_variable` auto-parses `application/json` responses into a
   native Python list/dict — `history_result.content` was never a raw
   string. The first version of this script called
   `history_result.content | from_json` anyway, which failed because
   Jinja's implicit stringification of a Python list uses `repr()`
   (single-quoted), which isn't valid JSON. Fixed by using
   `history_result.content` directly (with an `is iterable and is not
   string` guard for safety).
2. **`stop:` message text vs. `response_variable`.** The first fix put the
   computed summary directly in the `stop:` message string with no
   `response_variable:` set. That looked fine in isolated Jinja testing,
   but `stop:`'s message is only a completion/log message — the actual
   value returned to callers (the LLM tool-call result, and the
   `?return_response` REST API) comes from `response_variable`, which
   matches how the working Task 8 memory scripts are built (`stop: "..."`
   + `response_variable: <var>`). Fixed by computing the summary into a
   `variables:` entry and pointing `stop:`'s `response_variable` at it.
3. **`response_variable` must resolve to a dict.** Setting
   `response_variable` to a plain string still failed
   `?return_response` REST calls with `"expected a dictionary, but got
   <class 'str'>"`. Wrapped the summary in a one-key dict
   (`{"summary": "..."}`) to match the shape the memory scripts return
   (their `response_variable` is the raw `rest_command` response dict).

### Verification (2026-08-19)

1. Backed up `configuration.yaml` before each of the 4 patch iterations
   (initial add + 3 bugfixes above), diffed backup vs. new file each time —
   clean, isolated diffs throughout.
2. Validated via `POST /api/config/core/check_config` after each iteration
   → `"result": "valid"` every time.
3. Reloaded `rest_command` and `script` domains after each change (no
   restart needed).
4. Added `script.heimdall_aquarium_temp_history` to
   `heimdall/scripts/expose_entities.py`'s `ENTITIES_TO_EXPOSE`, ran the
   Task 0 guardrail check on the diff (clean), ran the script live —
   entity exposed to Assist.
5. Called the script directly via
   `POST /api/services/script/heimdall_aquarium_temp_history?return_response`
   → confirmed real computed output, e.g.
   `{"summary": "Over the last 6 hour(s): 1 readings, min 26.3°C, max 26.3°C, latest 26.3°C at 2026-08-19T19:50:00Z."}`.
6. Re-tested the original failing scenario live via
   `conversation.process` against `conversation.heimdall_local_qwen2_5`:
   - EN: "What was the aquarium water temperature exactly 3 hours ago, and
     has it changed recently?" → "Over the last 3 hours, the aquarium
     water temperature has remained constant at 26.3°C."
   - PL: "Czy temperatura wody w akwarium zmieniła się ostatnio?" →
     correctly answered in Polish, citing 26.3°C.
   Confirmed via the script entity's `last_triggered` attribute
   (`21:57:29` local, matching the voice test's timestamp to the second)
   that the agent genuinely invoked the new tool rather than restating a
   plausible-sounding guess.

## 8. Google Calendar integration (Task 5 / M4)

### OAuth app setup (one-time, Google Cloud Console)

1. Created a Google Cloud project, enabled the **Google Calendar API**.
2. OAuth consent screen: "External" type, added the account as a **Test
   user** (required — without this, sign-in fails with "Access blocked...
   has not completed Google verification" even with correct
   client_id/secret), scope `.../auth/calendar` (full read+write).
3. Created an OAuth **Web application** client, redirect URI
   `https://my.home-assistant.io/redirect/oauth` (HA's universal "My Home
   Assistant" redirect — works for LAN-only or externally-reachable
   instances; on first use it asks the browser for the real instance URL,
   stored client-side only).
4. Registered the resulting `client_id`/`client_secret` as an HA
   Application Credential via `heimdall/scripts/add_google_calendar_credentials.py`
   (uses the `application_credentials/create` WebSocket command — there is
   no REST equivalent for registering credentials).
5. Completed the interactive OAuth consent flow via HA UI → Settings →
   Devices & Services → Add Integration → Google Calendar.

### Entities created

Google Calendar integration created 4 entities:
- `calendar.kamil_koterba95_gmail_com` — main calendar (read+write)
- `calendar.birthdays`
- `calendar.holidays_in_ireland`
- `calendar.holidays_in_ireland_2` — **true duplicate** of the one above
  (identical event data); left unexposed since exposing both adds no
  value.

Exposed to Assist (via `expose_entities.py`): the main calendar,
birthdays, and one "Holidays in Ireland" instance.

### Finding: HA's built-in Assist LLM API is calendar READ-ONLY

Confirmed via conversation debug logs' "Tools:" list — only
`<CalendarGetEventsTool - calendar_get_events>` exists for any exposed
calendar entity; there is no built-in create/write tool. This is a genuine
HA platform limitation. Writing requires a custom `script:` wrapper.

### `configuration.yaml` — new `script:` entry (calendar write tool)

```yaml
script:
  heimdall_create_calendar_event:
    alias: "Heimdall: Create calendar event"
    description: >-
      Create a new event on the main calendar. You MUST call the
      GetDateTime tool first to get today's real current date before
      computing any date for this tool - never guess or assume the year
      from your training data. Requires exact start/end date-times in
      "YYYY-MM-DD HH:MM:SS" format, computed from GetDateTime's result plus
      the user's relative term (e.g. "tomorrow", "next Tuesday").
    fields:
      summary:
        description: "Event title"
        example: "Dentist appointment"
        required: true
        selector:
          text:
      start_date_time:
        description: "Event start, e.g. 2026-08-25 10:00:00"
        example: "2026-08-25 10:00:00"
        required: true
        selector:
          text:
      end_date_time:
        description: "Event end, e.g. 2026-08-25 11:00:00"
        example: "2026-08-25 11:00:00"
        required: true
        selector:
          text:
      description:
        description: "Optional event description"
        required: false
        selector:
          text:
    sequence:
      - if:
          - condition: template
            value_template: "{{ (summary | default('')) | trim == '' }}"
        then:
          - stop: "summary is required and was empty/missing - refusing to create a blank event"
            error: true
      - action: calendar.create_event
        target:
          entity_id: calendar.kamil_koterba95_gmail_com
        data:
          summary: "{{ summary }}"
          start_date_time: "{{ start_date_time }}"
          end_date_time: "{{ end_date_time }}"
```

The `if`/`stop` guard was added after a real bug (see below) where the
local model called this script with a missing `summary`, silently creating
a blank all-day event — `fields:`/`required: true` is only a UI/LLM-schema
hint, HA does **not** enforce it at runtime, so an explicit template guard
is required to actually block it.

There is no `calendar.delete_event` service in this HA version
(`2026.8.1`) — confirmed via `GET /api/services` (calendar domain lists
only `create_event`/`get_events`). Stray test events created during
development had to be deleted manually via Google Calendar's own UI.

### Three real qwen2.5:7b-instruct bugs found, and what actually fixed them

1. **Wrong date-range keyword.** Called `calendar_get_events` with
   `range: 'today'` for a "what's on tomorrow" question.
2. **Wrong absolute year.** Computed `2023` instead of the real year when
   creating an event, without calling the available `GetDateTime` tool
   first — even after the tool's `description` was strengthened to
   mandate calling `GetDateTime` first. **Strengthening the tool
   description did not reliably fix this** (tested twice, failed both
   times). **What did fix it**: injecting the real date directly into the
   conversation agent's **system prompt** (not the tool description) via
   the subentry reconfigure flow — see prompt text below. Verified correct
   year across 3 repeated tests after this fix.
3. **Wrong tool selection + wrong relative-day math.** Even after the
   date-grounding fix, qwen sometimes called the *write* tool
   (`heimdall_create_calendar_event`) with no `summary` when asked a pure
   *read* question — silently creating a blank all-day event (this is what
   the `if`/`stop` guard above prevents) — and separately miscalculated
   the Polish relative-date word "pojutrze" (day-after-tomorrow),
   landing the event on the wrong day. Gemini has never shown any of these
   three bugs in any test.

### Fix 1: system-prompt date grounding (both agents)

Prepended to both the Ollama/qwen and Gemini conversation subentries'
`prompt` field via the subentry reconfigure flow (same mechanism as
section 5 above):

```
Today's real date and time is {{ now().strftime('%Y-%m-%d %H:%M %A') }}. Always use this as the current date/time - never assume or guess a year from your training data, especially when creating calendar events or resolving relative dates like "tomorrow".
```

This alone fixed bug #2 (wrong year) reliably, but did **not** fix bug #3
(wrong tool / wrong relative-day math for Polish) — those needed the
architectural fix below.

### Fix 2: `heimdall_llm_api` custom component — per-agent tool restriction

HA's entity-exposure system has **no per-conversation-agent scoping** —
every agent selecting the `assist` LLM API sees an identical tool set.
Bug #3 showed the local model could not be trusted with write access to
the calendar (silent blank-event creation), but simply removing the tool
would also remove it for Gemini, which has never misused it.

Built a new custom HA integration,
`heimdall/ha_custom_components/heimdall_llm_api/` (deploy by copying to
HA's own `config/custom_components/heimdall_llm_api/` — requires a full HA
restart, custom integrations are only discovered at startup). It registers
a second LLM API, `heimdall_restricted`, that internally reuses the exact
same tool-gathering logic as the built-in `assist` API (every integration's
`llm.py` platform — script, calendar, homeassistant/GetLiveContext, etc. —
still contributes tools normally, since they're queried with the real
`assist` api_id) but filters out an explicit blocklist of tool names
(currently just `heimdall_create_calendar_event`) before returning the
tool list.

`configuration.yaml` — new bare domain key to load it:

```yaml
heimdall_llm_api:
```

The local model's (`qwen2.5:7b-instruct`) conversation subentry then has
`llm_hass_api` switched from `assist` to `heimdall_restricted`; Gemini's
subentry is untouched (`assist`), so it keeps full calendar read+write.

Verified via debug logs (`"Tools:"` list) that
`heimdall_create_calendar_event` is completely absent from qwen's tool set
after this change, while every other tool (lights, gate, aquarium, memory,
`calendar_get_events`, `GetDateTime`, etc.) remains present. Confirmed
across multiple write-attempt tests that **zero events were ever created**
after this fix (previously silent blank/wrong-year events were created).

### Fix 3: honest-refusal prompt wording (qwen only)

With the write tool hidden, qwen's first response to a write request was
to **hallucinate a false "I've added it" success message** rather than
admit it lacks the capability — a known small-model failure mode. Fixed by
adding to qwen's system prompt (appended after the date-grounding line):

```
IMPORTANT: You do not have a tool to create, modify, or delete calendar events - you can only read the calendar. If asked to add, change, or remove a calendar event, do NOT claim you did it. Honestly tell the user you cannot modify the calendar and suggest they ask Gemini instead. Never state that an action succeeded unless a tool call actually confirmed it.
```

Verified across 3 repeated tests (2 EN phrasings + 1 PL) — qwen now
honestly refuses every time instead of claiming false success. (Minor,
non-blocking observed quirk: the Polish-phrased test got an English
refusal instead of a Polish one — content was still correct/honest, just
not language-matched. Not chased further given the actual data-safety goal
was fully met.)

### Final verified state

- **Gemini** (`conversation.google_ai_conversation`): full calendar
  read+write, correct date/year every time, never misused the tool.
  Recommended for any calendar-write voice request.
- **qwen2.5:7b-instruct** (`conversation.heimdall_local_qwen2_5`):
  calendar read-only (via `heimdall_restricted` LLM API), reliably and
  honestly refuses write requests, correct year for date-grounded reads.
  This is an accepted, documented model limitation, not a Heimdall config
  gap — consistent with Task 3's bake-off findings that qwen2.5:7b is the
  weakest of the surviving candidates on precision-sensitive tasks.
- Debug logging (`conversation`/`llm`/`calendar` components) used
  throughout this investigation was temporarily raised via
  `logger.set_level` (in-memory only) and explicitly reverted to
  `warning` afterward.

## 9. Entity-registry fixes found by Task 7's test matrix (M6)

Task 7's `heimdall/tests/test_matrix.py` — a live regression suite exercising
every domain × language × agent combination via `conversation.process` — was
run for the first time and surfaced two real entity-naming bugs, plus two
accepted qwen-only limitations that were investigated but not chased further.

### 9.1 Phantom Tuya fixture winning fuzzy match over the real relay — FIXED

A Tuya-integration light/fan pair, `light.office_light` +
`fan.office_light` (same `device_id`), was exposed to Assist with the clean
friendly name "Office light". This is a **real fixture**, not dead junk — its
power is physically wired downstream of the office's Zigbee relay
(`switch.0x54ef4410016759d1_up`, friendly name "BiuroSwiatłoGłówne Up"), so
it reports `unavailable` whenever the relay is off. Its cleaner English name
was winning Assist's fuzzy name-match over the actual relay for **both**
agents and **both** languages — "turn on the office light" appeared to
succeed (HA reports `turn_on` against an unavailable entity as a success in
`data.success`) while the real relay never toggled.

Fix: added both entities to `ENTITIES_TO_HIDE` in
`heimdall/scripts/expose_entities.py` with a comment explaining the
power-dependency (not decommissioned junk). Re-ran the script live; both
confirmed hidden. Voice control now correctly reaches the relay for Gemini in
both languages (see 9.3 below for the remaining qwen-only gap).

### 9.2 Bedroom radiator alias — added, then reverted (no net effect for qwen)

`climate.0xa4c138b1ad7dfd57`'s only name is the Polish compound word
"GrzejnikSypialniaGóra" with no English alias. Gemini already resolves "the
bedroom radiator" correctly in both languages without one; qwen initially
failed with "I couldn't find the correct entity."

Tried adding an English alias via `config/entity_registry/update`
(`aliases: ["Bedroom radiator", "bedroom heater"]`) — qwen's response then
showed it had **concatenated both aliases into one malformed search string**
rather than trying them independently, so HA's server-side matcher still
found no match. Reverted to a single alias
(`aliases: ["Bedroom radiator"]`) and retested — qwen **still** failed to
resolve it, this time asking the user to confirm the Polish name instead.

Conclusion: entity-registry aliases appear to only feed HA's **built-in
intent fuzzy matcher** (used by Gemini's built-in tools), not whatever tool
schema qwen's Ollama-based conversation agent actually queries — so no
amount of aliasing was going to fix this for qwen specifically. The single
alias was left in place (harmless, doesn't hurt Gemini, no downside), but
this is now documented as an accepted qwen limitation rather than pursued
further — see 9.3.

### 9.3 Accepted qwen-only limitations (not fixed further, per user's call)

- **`switch.office_led`** ("Office LED") is a third, separate, real TP-Link
  device (a lamp/LED strip, confirmed by the user — genuinely controllable,
  distinct from both the relay and the now-hidden Tuya fixture). qwen's
  literal name-matching resolves "office light" to this device instead of
  the intended relay, in both languages; Gemini's fuzzier matching correctly
  picks the relay. This is accepted as a **known qwen limitation**, not
  fixed by further hiding/renaming, since `office_led` is a real, distinct,
  wanted device that must stay exposed and named.
- **Climate alias garbling** (9.2 above) — also accepted as a known qwen
  limitation.

Both are asserted directly in `test_matrix.py` (marked `KNOWN-LIM` in its
report, not silently hidden and not counted as a suite failure) — see that
file's module docstring and `KNOWN_QWEN_LIMITATIONS` dict for the exact
wording kept in sync with this doc.

### 9.4 Gemini free-tier rate limit (observed, not an HA config issue)

A full `test_matrix.py` run makes ~13 Gemini calls in quick succession,
which sits close to the free tier's `generate_content_free_tier_requests`
ceiling (15 requests/minute for `gemini-3.1-flash-lite`, confirmed via the
literal `429 RESOURCE_EXHAUSTED` error body during one run). A retry after
waiting cleared it; noted here so a spurious single-row Gemini failure
during a full-suite run isn't mistaken for a real regression. Soak-cadence
runs (via `ntfy_failure_logger.py`'s poller, not a tight test-matrix loop)
run far slower than this ceiling and are not expected to trigger it.

### 9.5 Correction (2026-08-20): 9.1 and 9.2/9.3 conclusions superseded

Two follow-up sessions found the actual root causes behind 9.1 and 9.2/9.3,
which had reached wrong or incomplete conclusions at the time:

- **9.1 was wrong that `light.office_light`/`fan.office_light` are junk.**
  The user confirmed both are real, legitimate controls for the office
  light+fan combo unit (only functional when the upstream relay/switch is
  on) — hiding them removed real functionality rather than fixing a bug.
  Both were **re-exposed** (`options.conversation.should_expose: true`) via
  `heimdall/scripts/expose_missing_entities.py`, alongside two other
  entities found missing from Assist entirely: `alarm_control_panel.glowne`
  (main alarm panel) and `siren.driveway_siren`. None had the alias bug
  below, so no further fix was needed for them — untested by voice yet
  (alarm/siren deliberately deferred to daytime, not tested at night).

- **9.2/9.3's "accepted qwen limitation" conclusion for the climate alias
  was wrong** — the real root cause was found by reading HA core source
  directly (`helpers/entity_registry.py::async_get_entity_aliases` and
  `helpers/intent.py::_filter_by_name`): HA's intent name-matcher **only**
  checks an entity's `aliases` list, never its registry `name` field.
  Untouched entities default to an internal `COMPUTED_NAME` sentinel alias
  (serializes as `aliases: [null]` over the WS API) that expands to the
  entity's full computed name — that's why every *other* radiator matched
  by name "for free" without ever having an explicit alias. The Task 5
  alias experiment (9.2) had overwritten this sentinel with a literal
  `["Bedroom radiator"]`, permanently breaking name-matching for Polish
  voice commands regardless of language — it was never actually a qwen-only
  limitation, and Gemini's "fuzzier matching" theory in 9.3 was also a
  misdiagnosis of the same underlying bug.

  Fix: set `aliases: ["GrzejnikSypialniaGóra"]` (the entity's own name,
  as a literal explicit alias) via `config/entity_registry/update`. This
  bypasses the sentinel mechanism entirely and is guaranteed to match.
  Confirmed working live via voice ("Ustaw temperaturę w sypialni górze na
  25 stopni" — resolved correctly where it previously failed with
  `MatchFailedReason.NAME`).

  The `switch.office_led` bullet in 9.3 (a real, separate, distinct device)
  remains accurate and unaffected by this correction.

## 10. STT VAD tuning — background noise producing hallucinated transcripts

Reported symptom: voice commands intermittently producing garbled/unrelated
text, worse with background noise (TV, ambient conversation) present. No
`assist_satellite` entities exist in this setup (confirmed via `/api/states`
— zero entities of that domain) and all 4 Assist pipelines have
`wake_word_entity: null`/`wake_word_id: null` — voice is invoked via the HA
app/tablet's tap-to-talk Assist widget, not always-listening satellite
hardware.

### 10.1 Investigation — confirmed live, not assumed

- **Image version**: `heimdall-whisper` is still `rhasspy/wyoming-whisper:3.6.0`
  (unchanged since Task 2), confirmed via `docker inspect`.
- **Actual supported flags**: pulled directly via
  `docker exec heimdall-whisper /usr/src/.venv/bin/python3 -m wyoming_faster_whisper --help`
  (the plain `python3 -m wyoming_faster_whisper --help` at the container's
  default interpreter fails with `ModuleNotFoundError` — the real venv is at
  `/usr/src/.venv`, per `/usr/src/docker_run.sh`). Relevant flags confirmed
  present: `--vad-filter`, `--vad-threshold` (default 0.5), 
  `--vad-min-speech-ms` (default 250), `--vad-min-silence-ms` (default 2000),
  `--vad-clip`, `--vad-clip-threshold` (default 0.5), `--vad-clip-pad-ms`
  (default 400), and separately `--hass-token`/`--hass-api` (entity-name
  transcription biasing, unrelated to VAD but found in the same investigation).
- **HA pipeline-level VAD**: HA's `assist_pipeline/vad.py` defines a
  `VadSensitivity` enum (`default`=0.7s silence, `relaxed`=1.25s,
  `aggressive`=0.25s) controlling end-of-command silence detection, but
  `assist_pipeline/select.py::get_vad_sensitivity()` reads it from a
  per-satellite `select.<unique_id_prefix>-vad_sensitivity` entity and
  **falls back to `VadSensitivity.DEFAULT` when no such entity exists**.
  Since this setup has zero `assist_satellite` entities, **this control does
  not apply here at all** — there is nothing to tune on the HA-pipeline side
  for this setup; the tablet/app's own client-side push-to-talk handles its
  own start/stop, not HA's server-side segmenter. Confirmed by reading
  source, not assumed.

### 10.2 Change applied — confirmed value before/after

**Before** (unchanged since initial deployment):
```yaml
command: --model small-int8 --language auto --uri tcp://0.0.0.0:10300 --data-dir /data --download-dir /data
```
No VAD filtering of any kind was active — confirmed via the flag's own
`--help` text: "(default: false, faster-whisper only)". This is the direct,
confirmed cause of the reported symptom: with VAD off, faster-whisper
transcribes silence and non-speech audio too, and its well-documented
failure mode there is hallucinating plausible-sounding text.

**After**:
```yaml
command: --model small-int8 --language auto --uri tcp://0.0.0.0:10300 --data-dir /data --download-dir /data --vad-filter --hass-token ${HEIMDALL_HA_TOKEN} --hass-api http://192.168.0.108:8123/api
env_file:
  - .env
```
New file `/home/kamilo/heimdall/.env` (mode 600, not a git repo — no
gitignore risk) holds `HEIMDALL_HA_TOKEN`, copied from the existing
`heimdall-testmatrix/.env` on the same host.

**Deviation from the incremental-application principle, noted honestly**:
`--vad-filter` and `--hass-token`/`--hass-api` were applied in the *same*
deploy, before this task's formal brief (which asked for incremental,
separately-attributable changes) was received. Both are confirmed live
(container restarted cleanly; log shows `Biasing toward names from
http://192.168.0.108:8123/api` and `Ready`), but if a regression shows up,
isolating which flag caused it will require temporarily removing
`--hass-token`/`--hass-api` and re-testing with `--vad-filter` alone.

**Not yet touched** (left at library defaults, available as the next
incremental knob if `--vad-filter` alone proves insufficient):
`--vad-threshold` (0.5), `--vad-min-speech-ms` (250),
`--vad-min-silence-ms` (2000), `--vad-clip*`.

### 10.3 Verification status

- Regression check (`test_matrix.py` light/switch/climate rows) and manual
  noise/silence tests: **pending** — deliberately not run yet, since both
  require `--allow-physical-actuation` and it's nighttime; scheduled for
  daytime alongside the alarm/siren voice test from section 9.5.
- Container-level sanity check only, done: clean restart, no errors, both
  new flags confirmed active in logs.

### 10.4 Non-goals confirmed untouched

No speaker verification/enrollment, no wake-word engine changes, no
hardware changes — all explicitly out of scope for this task (separate M10/M8
decisions). HA's per-pipeline VAD sensitivity control was investigated (see
10.1) and found not applicable to this satellite-less setup, not bypassed or
worked around.

## 11. Heating "boost" feature (2026-08-20, ad hoc — no M-number)

New voice feature: turn a radiator on to a comfort temperature for a fixed
duration, then auto-revert — the "boost" button on old thermostatic radiator
valves. Added as two `script:` entries in `heimdall.yaml`.

### 11.1 Why two scripts, not one

Calling a script directly by its own domain service blocks the caller until
it completes. If the boost logic (set temp → delay → revert) lived in one
script, the voice-tool call would hang for the entire boost duration
(up to 4 hours) before Assist could respond — broken UX. Split instead:

- `heimdall_boost_heating` (exposed to Assist): captures the entity's
  current `hvac_mode`/`temperature`, applies the boost, fires
  `heimdall_boost_revert_worker` via `script.turn_on` (fire-and-forget —
  does NOT wait for it, unlike calling a script by its own domain service),
  then returns immediately with a `reverts_at` time in its response.
- `heimdall_boost_revert_worker` (NOT exposed —
  `options.conversation.should_expose: false`, confirmed via
  `config/entity_registry/get`): delays for the requested duration, then
  restores the original `hvac_mode` (including back to `off` if that was
  the original state) and `temperature`.

Both scripts use `mode: parallel, max: 10` so boosting multiple different
radiators concurrently doesn't queue/block on each other.

### 11.2 Fields (`heimdall_boost_heating`)

- `entity_id` (required, `selector: entity: domain: climate`)
- `duration_minutes` (optional, number 5-240, default 60)
- `temperature` (optional, number 15-28°C step 0.5, default 22)

### 11.3 Known limitation, not fixed in v1

Boosting the **same** entity a second time while a boost is already active
starts a second independent revert worker rather than replacing the first —
the first worker still fires at its original scheduled time, potentially
reverting/cutting the second boost short partway through. Fixing this
properly needs a per-entity "boost generation" token (e.g. an
`input_text`/counter that each worker checks before reverting, aborting if a
newer boost has superseded it) — not implemented, since it adds a real
helper-entity + logic to review, and isn't needed for the common case
(boosting different radiators, or one radiator once).

### 11.4 Deployment

Applied via `heimdall.yaml` (same package file as all other Heimdall
scripts) — backed up as `heimdall.yaml.bak-boost-feature-20260820` before
the edit. Validated with `check_config` (exit code 0) before reload;
applied live via `script.reload` (no full HA restart needed for
`script:` changes). Confirmed both scripts registered
(`script.heimdall_boost_heating`, `script.heimdall_boost_revert_worker`) and
exposure set correctly for each via the entity registry.

### 11.4b Dashboard UI buttons added (2026-08-20, same night)

Clarified after the fact: "heating" in this whole feature meant the
kitchen's Hive thermostat/burner (`climate.0x001e5e0902ce8e9a`, "Ogrzewanie
Kuchnia"), which already had a `thermostat` card on the "Dom" dashboard
(`lovelace.dashboard_biuro` storage file, url-path `dashboard-biuro`,
confusingly titled "Dom" not "Biuro" - that's a different dashboard,
`dashboard_biuro_2`). Added a 3-button grid (Boost 30 min / 1h / 1.5h, all
fixed at 22°C) directly below the existing thermostat card, calling
`script.heimdall_boost_heating` with `entity_id: climate.0x001e5e0902ce8e9a`
hardcoded per button - matches the "physical boost button with fixed
presets" feel of old thermostats rather than exposing a free-text duration
field in the UI.

**Important operational note discovered**: editing a storage-mode Lovelace
dashboard's `.storage/lovelace.dashboard_*` JSON file directly on disk while
HA is running does **not** take effect live - confirmed via `lovelace/config`
WS query still returning the old content after the file was already
overwritten. Unlike `script:`/`automation:` YAML, there is no reload service
for storage-mode dashboards; a full HA container restart was required and
performed (with the user's explicit go-ahead, since this is more disruptive
than the container-only restarts used earlier tonight - it briefly drops
all live states/automations/voice, not just one integration). Confirmed
live after restart via the same WS query, and confirmed the boost scripts
and climate entities survived the restart cleanly.

Backed up as `lovelace.dashboard_biuro.bak-kitchen-boost-20260820` (root-owned
file, required `sudo cp`/`sudo chown` - passwordless sudo confirmed
available on vesemir, same as jaskier) before the edit.

### 11.5 Verification status

**Untested** — no boost has been triggered live yet (added same night as the
VAD tuning work in section 10; deliberately not actuated). Before relying on
this: trigger one boost with a short duration (e.g. 5 minutes) on a
non-critical radiator, confirm (a) the voice response returns immediately
rather than hanging, (b) the entity actually reaches heat/target
temperature, and (c) it correctly reverts to its prior state at the
`reverts_at` time.

## 12. Dashboard radiator cards: bug fix + 3 missing rooms (2026-08-20, same night)

User reported a "connection error" on the bedroom radiator's thermostat card
on the Dom dashboard specifically, while other cards worked fine. Investigated
by pulling the live `lovelace.dashboard_biuro` storage file directly (grep for
all `climate.*` references) rather than guessing.

### 12.1 Root cause found: malformed nested card, not a device/network issue

`climate.0xa4c138b1ad7dfd57`'s (Sypialnia Góra bedroom radiator - the same
entity whose intent-matching alias bug was fixed earlier tonight, see section
9.5; this is a separate, unrelated bug) `tile` card had a full second `tile`
card definition (for `sensor.0xa4c138b1ad7dfd57_error_status`, an error-status
sensor) mistakenly nested **inside** its `features` array:

```json
"features": [
  { "type": "target-temperature" },
  { "type": "climate-hvac-modes", "hvac_modes": ["off", "heat", "auto"] },
  { "type": "tile", "entity": "sensor.0xa4c138b1ad7dfd57_error_status", ... }
]
```

`features` may only contain feature-type objects (`target-temperature`,
`climate-hvac-modes`, etc.) - a full card definition doesn't belong there and
almost certainly broke that card's rendering, which the frontend surfaces as
a generic "connection error". No other radiator card had this malformation.

**Fix**: moved the error-status tile out of `features` to be a proper sibling
card in the same `vertical-stack`, alongside (not inside) the climate tile.

### 12.2 Missing rooms added

Of the 7 individual TRV radiators, 4 already had dashboard cards (bedroom
upstairs, both bathroom units, office) but 3 didn't, despite their rooms
already having dashboard sections with other controls:

- `climate.0xa4c13842240065f9` → "Gościnny" (guest room) section
- `climate.0xa4c138b90fef70c7` → "Salon" (living room) section
- `climate.0xa4c138d920585e93` → "Sypialnia Dół" (downstairs bedroom) section

Added a `tile` card to each (matching the corrected bedroom pattern -
`target-temperature` + `climate-hvac-modes` features only, no preset-mode
button grid or error-status tile, to keep scope to "radiator control" as
requested rather than replicating every custom extra). All 8 climate
entities (7 TRVs + the kitchen Hive from section 11.4b) now have exactly one
dashboard card each - confirmed via `lovelace/config` WS query string-matching
each entity_id and card name after deploy.

### 12.3 Deployment

Same process as 11.4b: backed up as
`lovelace.dashboard_biuro.bak-all-radiators-20260820`, deployed via
`sudo cp`, full HA restart required (same storage-mode-dashboard limitation
as before) and performed with the user's go-ahead. Confirmed live post-restart.

### 12.4 Verification status

**Bug fix untested by the user** — the malformed-card fix should resolve the
reported connection error, but this hasn't been re-confirmed by the user
looking at the dashboard yet. **New room cards untested** - same as the
kitchen boost buttons, these display/control real devices but haven't been
interacted with live yet.

## 13. "What's in the office" area-listing accuracy (2026-08-21)

User compared qwen (phone) vs Gemini (laptop) answers to "what's in the
office" - qwen's was garbled (expected, matches the well-understood
Polish-compound-word tokenization limitation, not investigated further here)
but Gemini's cleaner answer had two apparent defects: missing the Meross
surge protector's outlets, and wrongly including `binary_sensor.syrena_swiatlo`
("Syrena+Światło", an alarm siren+light) as if it were an office device.

### 13.1 Investigated via direct area/device registry query

- **Meross surge protector (`Office surge protector`, device_id
  `d1aa4429ebc7654bf5b07ec632116aac`) is correctly `area_id: office`** - all 6
  outlet entities (Listwa, Monitor_1, Monitor_2, Biurko_LED, StacjaDokująca,
  LED_1) are correctly area-tagged and exposed to Assist. Gemini's answer
  just didn't list all of them in its natural-language summary - this is a
  response-generation completeness issue, not a registry/data bug. Nothing
  fixed here; flagged to the user as a different (harder, LLM-behavior)
  class of problem than the siren one below.

- **`binary_sensor.syrena_swiatlo` and `binary_sensor.syrenazew` (both
  "Syrena+Światło"/"SyrenaZew" alarm siren devices) had `device_area: None`**
  - not assigned to office, or any area at all. So Gemini including them in
  an "office" answer wasn't a registry misassignment either - there was no
  area data to misassign in the first place. Likely cause: with no area
  anchor, an LLM summarizing "devices in this area" has nothing constraining
  it and can misattribute unassigned entities based on other context (e.g.
  earlier conversation turns, name similarity, or just model error).

### 13.2 Fix applied

No dedicated "whole house" area existed. Asked the user where these siren
devices are physically mounted; user chose the existing `domballivor` area
(no floor assigned - a general/non-room-specific area already in the
registry) over the two hall areas (`hall`, `hallgora`). Assigned both
devices' `area_id` to `domballivor` via `config/device_registry/update`
(device-level, matching how every other device in this house is area-tagged
- entities inherit area from device, not set individually). Confirmed via
the update response echoing back `area_id: domballivor` for both.

### 13.3 Verification status — CONFIRMED FIXED, and a self-caught misdiagnosis corrected

The user re-tested and initially reported a list still missing 3 of the 6
Meross outlets (Listwa, Biurko_LED, StacjaDokująca), attributed to Gemini at
the time. That triggered a deeper investigation (direct comparison of all 6
outlets' registry entries - `should_expose`, `entity_category`,
`disabled_by`, `labels` - all identical, ruling out a data cause) which
concluded the omission must be Gemini's own response-generation dropping
items, motivating a system-prompt edit (adding an explicit "list every item,
never summarize" clause to the Google AI Conversation subentry's prompt in
`core.config_entries`, applied and validated but **not yet activated** -
still pending the HA restart storage-mode config entries require).

**The user then clarified the "still missing 3 outlets" answer was actually
qwen's, not Gemini's** - mislabeled in the prior turn. Gemini's real answer
(provided immediately after) is complete and correct: all 6 outlets present,
and critically, **no `Syrena+Światło`** - directly confirming the 13.2 area
fix worked, with zero further action needed. qwen's incomplete answer is the
same already-documented, accepted limitation (small local model, Polish
compound-word tokenization/summarization quality) as `TEST_MATRIX.md`'s
`KNOWN_QWEN_LIMITATIONS`, not a new bug.

**The Gemini system-prompt edit was reverted** before ever taking effect
(HA was never restarted with it loaded, so this was a clean no-op) - it was
based on a false premise and isn't needed; Gemini's actual behavior for this
query was already correct. Restored from
`core.config_entries.bak-gemini-prompt-20260821`, confirmed via re-reading
the file that the added clause is gone. Lesson: when comparing two
"different agent" answers, confirm which literal answer came from which
agent before root-causing a discrepancy - the deeper investigation here
was thorough and well-reasoned, but built on a mislabeled data point.






