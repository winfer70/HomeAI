# ProjectNemo API (`nemo-api`) — investigation notes for Task 4 (M3, aquarium tools)

The original Heimdall brief flagged Task 4 as blocked until this doc existed.
This is the result of that investigation, done live against the running
`nemo-api` container on vesemir (image `projectnemo-nemo-api`, port 8000,
source bind-mounted at `/home/kamilo/nemo/ProjectNemo/api`) rather than
guessing from the brief's assumptions.

## Summary / decision

**`nemo-api` is bypassed for all six of Task 4's target entities.** They're
exposed directly to Assist instead, via
`heimdall/scripts/expose_entities.py` (same mechanism as Task 3's
lights/TRVs). Rationale:

- `nemo-api`'s device-toggle endpoint is a thin proxy with no logic beyond an
  allowlist check — HA's native Assist API already does state-read +
  toggle for exposed entities with zero custom tool code.
- Two of the six target entities (`CzujkaWodyAkwarium`, `WtyczkaAkwarium`)
  aren't even in `nemo-api`'s hardcoded device map.
- `nemo-api` has **no authentication at all** (see below) — routing voice
  control through it wouldn't add any security benefit either.

The one real bug found (`/api/sensors/history` always returning empty) was
fixed at its actual root cause — HA's `influxdb:` integration's
measurement-naming — not by working around it in Heimdall. See
`heimdall/HA_CONFIG_CHANGES.md` §6 for the fix and verification.

## Full endpoint surface (from live `/openapi.json`, FastAPI)

No security scheme defined anywhere in the spec (`securitySchemes: {}`,
`security: []` on every operation) — **confirmed the entire API is
unauthenticated**. Any host on the network can call it freely. Not fixed as
part of this task (out of scope — flagging here so it isn't forgotten).

```
/health                                    GET
/api/sensors/current                       GET
/api/sensors/history                       GET
/api/devices                               GET
/api/devices/fluval/channels               GET
/api/devices/{entity_id}/toggle            POST
/api/calendar/today                        GET
/api/calendar/month/{year}/{month}         GET
/api/calendar/tasks                        GET/POST
/api/calendar/tasks/{task_id}              GET/PATCH/DELETE
/api/calendar/complete                     POST
/api/dosing                                GET
/api/dosing/{task_id}                      GET/PATCH
/api/dosing/{task_id}/complete             POST
/api/dosing/supplies/{supply_id}/restock   POST
/api/maintenance                           GET
/api/maintenance/{task_id}/start           POST
/api/maintenance/{task_id}/complete        POST
/api/maintenance/{task_id}/steps           GET
/api/obsada/fish                           GET/POST
/api/obsada/fish/{fish_id}                 GET/PATCH/DELETE
/api/obsada/plants                         GET/POST
/api/obsada/plants/{plant_id}              GET/PATCH/DELETE
/api/obsada/search                         GET
/api/schedule/feedings                     GET
/api/schedule/feedings/{feeding_id}        GET/PATCH
/api/schedule/feedings/history             GET
/api/supplies                              GET/POST
/api/supplies/{supply_id}                  GET/PATCH/DELETE
/api/supplies/{supply_id}/restock          POST
/api/actions/feed-now                      POST
/api/actions/feed-status                   GET
/api/actions/cancel-feed                   POST
/api/water-tests/parameters                GET
/api/water-tests/sessions                  GET/POST
/api/water-tests/sessions/latest           GET
/api/water-tests/trends/{param_key}        GET
/api/water-tests/analyze_strip             POST
/api/water-tests/debug_strip               POST
```

Endpoints relevant to Task 4 are `/api/sensors/current`,
`/api/sensors/history`, `/api/devices`, and
`/api/devices/{entity_id}/toggle` — detailed below. The rest (calendar,
dosing, maintenance, obsada, schedule, supplies, water-tests) are unrelated
to this task and weren't investigated further.

## `/api/sensors/current` (`routers/sensors.py`)

Reads live HA entity state **directly** (calls out to HA's own API/state
machine) — does not touch InfluxDB. No caching, no transformation beyond
picking a fixed set of entities. Confirmed via source read.

## `/api/sensors/history` (`routers/sensors.py`) — was broken, now fixed

Queries InfluxDB via Flux, filtering `_measurement == "<measurement>"` where
`<measurement>` is one of `temperature | ph | tds | orp` (query param).

**Root cause of the bug**: this filter assumes InfluxDB stores data under
semantic measurement names. In reality, the actual writer isn't `nemo-api`
at all — it's HA's own native `influxdb:` YAML integration (found in
vesemir's `configuration.yaml`), which by default names measurements after
`unit_of_measurement` (`measurement_attr: unit_of_measurement`, the
integration's default). So the water-temp sensor's points were being
written under measurement `"°C"`, never `"temperature"` — the endpoint
returned an empty list for every time window, unconditionally.

**Fix**: per-entity `component_config: <entity_id>: override_measurement:
temperature` added to vesemir's `influxdb:` config, scoped to just the one
water-temp sensor so the working `W`/`kWh` power-tracking measurements
aren't affected. Full details, exact YAML, and live verification (confirmed
`/api/sensors/history?measurement=temperature` now returns real points) in
`heimdall/HA_CONFIG_CHANGES.md` §6.

Only the temperature measurement was fixed — `ph`/`tds`/`orp` were out of
scope for Task 4's requested entities (none of them are pH/TDS/ORP
sensors), so those measurement names may still not match anything real if
ever queried. Flagging for future reference, not fixing preemptively.

## `services/influx_client.py` — `write_sensor()` / `write_power()` are dead code

Grepped the entire repo for callers of these two functions (the only
functions that would write `temperature`/`ph`/`tds`/`orp`/power-measurement
points into InfluxDB) — **zero callers found anywhere**. Confirmed by also
querying InfluxDB directly (`schema.measurements(bucket: "aquarium")`) and
finding only `W`, `kWh`, `°C` present before the fix above — exactly what
HA's native `influxdb:` integration would produce, not what
`write_sensor()`/`write_power()` would produce. `nemo-api` never actually
writes to InfluxDB in practice; HA's own integration does all of it.

## `/api/devices` + `/api/devices/{entity_id}/toggle` (`routers/devices.py`)

- `GET /api/devices` only tracks **4 hardcoded entities**: `switch.filtr`,
  `switch.grzalka`, `switch.tapo_light`, `switch.pompka` (a fixed
  `DEVICE_MAP` dict in source, not derived from HA's entity registry). Does
  **not** include `CzujkaWodyAkwarium` or `WtyczkaAkwarium` at all — no
  amount of Heimdall-side config could route through this endpoint for
  those two without first patching `nemo-api` itself, which is out of
  scope (a system Heimdall doesn't own).
- `POST /api/devices/{entity_id}/toggle` is a **thin proxy**: checks
  `entity_id` against the same hardcoded allowlist, then calls
  `ha_client.toggle_entity(entity_id)` — no additional logic, validation,
  or side effects. Confirmed via direct source read of `routers/devices.py`.

## Entity ID resolution (brief's names → live HA entity IDs)

Resolved by querying live HA states, not guessed:

| Brief's name          | Entity ID                                          | Notes |
|------------------------|----------------------------------------------------|-------|
| Termometr              | `sensor.0xa4c138060885ffff_temperature`             | Zigbee, water temp |
| Grzałka                | `switch.grzalka`                                    | heater |
| Filtr                  | `switch.filtr`                                      | filter |
| Pompka                 | `switch.pompka`                                     | air pump |
| CzujkaWodyAkwarium      | `binary_sensor.0x54ef441001548c9b_water_leak`       | Zigbee water leak sensor, friendly_name "CzujkaWodyAkwarium Moisture"; read-only |
| WtyczkaAkwarium         | `switch.0xa4c1380f6229ffff`                         | Zigbee smart plug — do not confuse with sibling plugs `0xa4c1380fb294ffff` / `0xa4c1380fa42bffff` ("WtyczkaHallDółTył" / "WtyczkaHallDółPrzód"), which are unrelated |

## Finding: switch on/off state itself is never written to InfluxDB

Discovered while writing the setpoint-write assertion test
(`heimdall/scripts/verify_aquarium_influx_write.py`). vesemir's `influxdb:`
config uses an explicit `include.entities` allowlist of 8 specific *sensor*
entities (power/energy consumption + water temp) — it does **not** include
`switch.grzalka`, `switch.filtr`, or `switch.pompka` themselves. So toggling
one of these switches (by voice or any other means) never produces an
InfluxDB point for the switch's own state — only its associated
power-consumption sensor does, and only if the toggle produces an
*observable value change* in that sensor.

Confirmed live (2026-08-19):

- `switch.filtr` / `switch.pompka` — steady non-zero draw whenever on, so a
  toggle reliably produces a clean drop-then-recover pattern in InfluxDB
  within ~20-40 seconds (verified twice, independently, via the assertion
  script — see two separate drop/recover cycles: `19:51:39→19:51:59` and a
  second fresh one at `19:53:23→19:53:43`).
- `switch.grzalka` — a heater with its **own internal thermostat**. If the
  thermostat isn't actively calling for heat when the switch is toggled,
  current draw is already `0 W` both before and after, so **no InfluxDB
  point is produced at all** for that toggle. This isn't a bug to fix (the
  heater's thermostat logic is intentional aquarium hardware behavior) — but
  it does mean "did the setpoint write land in InfluxDB" can't be verified
  for `grzalka` on every toggle, only when it coincides with an actual
  heating cycle. Documented here so this isn't mistaken for a broken
  integration later.

This is out of scope to "fix" (it would mean changing vesemir's
`include.entities` allowlist to add the raw switch entities, a broader
config change not requested by this task) — flagging as a known limitation,
not fixing preemptively.

## What Task 4 actually shipped

- No new `nemo-api` wrapper scripts (`expose_aquarium_tools.py` from the
  original brief was not written — decided unnecessary per the above, with
  the user's explicit sign-off).
- All six entities added to `heimdall/scripts/expose_entities.py`'s
  `ENTITIES_TO_EXPOSE`, exposed directly to Assist for both conversation
  agents.
- The `/api/sensors/history` InfluxDB measurement-naming bug fixed at its
  root cause (HA's `influxdb:` config), not worked around.
- Setpoint-write → InfluxDB assertion test: see
  `heimdall/scripts/verify_aquarium_influx_write.py`.
- **History-by-voice tool** (`rest_command.heimdall_aquarium_temp_history` +
  `script.heimdall_aquarium_temp_history`, exposed to Assist). Added after
  live voice testing showed the agent could read the *current* temperature
  but had no way to answer "has it changed recently" — the original Task 4
  scope fixed the history endpoint's bug but never wired a tool to call it.
  Returns a min/max/latest summary rather than raw JSON points, matching
  the Task 8 memory tools' pattern. Full YAML, three bugs found while
  wiring it up (JSON auto-parsing, `stop:` vs `response_variable`, dict vs.
  string response shape), and live verification steps are in
  `heimdall/HA_CONFIG_CHANGES.md` section 7.
