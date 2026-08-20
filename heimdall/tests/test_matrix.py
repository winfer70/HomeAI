#!/usr/bin/env python3
"""Task 7 (M6) — automated regression test matrix against HA's `conversation.process`.

This is a live-infrastructure script, not a mocked unit test — it is **not**
collected by the repo's normal `pytest` run (`pyproject.toml`'s
`testpaths = ["tests"]` only covers the repo-root `tests/` package that tests
the `homeai` agent code). Run it manually, or on a schedule, against the real
jaskier/vesemir stack:

    HEIMDALL_HA_TOKEN=<long-lived token> python heimdall/tests/test_matrix.py

Optionally set HEIMDALL_NTFY_TOKEN (the `heimdall_bot` ntfy access token — see
provisioning notes below) to auto-publish any FAILing implementable row to the
`heimdall-failures` ntfy topic, for `heimdall/scripts/ntfy_failure_logger.py`
to pick up and append to `heimdall/SOAK_LOG.md` during unattended soak runs.

Rows covered (per the brief's Task 7 description — one per entity-domain/
action, each attempted in both EN and PL, against BOTH conversation agents:
Gemini `conversation.google_ai_conversation` and qwen
`conversation.heimdall_local_qwen2_5` — confirmed with the user this is the
right scope, since qwen's known, accepted limitations need to be asserted as
*expected* behaviour, not failures):

    light_switch, climate, gate, aquarium_read, aquarium_write,
    calendar_read_own, calendar_write_own, calendar_write_other,
    open_domain, ambiguous_mixed_language

Deliberate deviations from a strict "row x language x agent" grid, each
confirmed rather than silently assumed:

  - **gate**: exposure-check only (via HA's `homeassistant/expose_entity/list`
    WebSocket call), never a live "open/close the gate" voice command. Chosen
    explicitly with the user over full live actuation, because this test is
    meant to run repeatedly (soak testing) and a real driveway gate shouldn't
    cycle unattended — and an exposure check is exactly what would have caught
    the real regression from earlier this project (a stale `expose_entities.py`
    run silently re-hid the gate relay). Language-agnostic, run once.

  - **calendar_write_other**: NOT IMPLEMENTABLE. The original brief assumed
    two Google accounts/calendars ("Kamil" + "Marzena"); Task 5 only actually
    connected one. Confirmed live via `/api/states` (only
    `calendar.kamil_koterba95_gmail_com`, `calendar.birthdays`, and
    `calendar.holidays_in_ireland*` exist — no second-person calendar) and
    confirmed with the user to leave this row out rather than fake a
    cross-calendar scenario that doesn't exist. Reported as N/A, not a
    failure.

  - **calendar_write_own**: real (Gemini) writes are SKIPPED BY DEFAULT. HA
    has no `calendar.delete_event` service in this version (confirmed via
    `GET /api/services` — see `heimdall/HA_CONFIG_CHANGES.md`), so every real
    write leaves a permanent event on the actual calendar with no automated
    cleanup. Pass `--allow-calendar-write` to actually exercise it (and clean
    up the resulting `HEIMDALL-TESTMATRIX-*` event by hand afterward). qwen's
    half of this row always runs regardless — it asserts an *honest refusal*
    (no event created), which is qwen's correct, expected behaviour, not a
    limitation being worked around.

  - **ambiguous_mixed_language**: one soft check per agent, not multiplied by
    language — the input phrase itself deliberately mixes EN/PL, so a
    separate "PL version" wouldn't test anything different. Only asserts the
    pipeline doesn't hard-error; exact entity resolution isn't required given
    the input is genuinely ambiguous by design.

  - **light_switch / climate / aquarium_write / ambiguous_mixed_language**:
    physical actuation is SKIPPED BY DEFAULT (added 2026-08-20, after the
    daily-scheduled timer made unattended real toggling of the office
    light/radiator/aquarium filter a real annoyance, not just a theoretical
    concern - this includes ambiguous_mixed_language, whose test phrase is
    also a real "turn on the office light" command that previously left the
    light on with no restore step). Pass `--allow-physical-actuation` to
    actually flip these and verify end-to-end - state is still restored
    afterward when it runs, same as before, but now opt-in rather than every
    run.

Write-type rows (light_switch, climate, aquarium_write) capture the entity's
state before speaking the command, verify it changed, then restore the
original value directly via HA's REST API (not via voice) so repeated runs
stay idempotent and don't depend on which state they happened to start in.

Known, accepted qwen-only limitations (found by this test's first live run,
2026-08-20 — confirmed with the user rather than silently patched around;
see KNOWN_QWEN_LIMITATIONS below and `heimdall/HA_CONFIG_CHANGES.md`):

  - **light_switch**: qwen resolves "office light" to `switch.office_led` (a
    separate, real TP-Link device — a lamp/LED strip, not the main ceiling
    light) instead of the intended Zigbee relay
    `switch.0x54ef4410016759d1_up`. Its literal name-matching prefers the
    closer English match over Gemini's fuzzier area/synonym matching, which
    correctly resolves to the relay in both languages after an unrelated fix
    (see below).

  - **climate**: qwen cannot resolve `climate.0xa4c138b1ad7dfd57` even after
    adding an English entity-registry alias ("Bedroom radiator") — Gemini
    needs no alias at all and already handles the Polish name
    ("GrzejnikSypialniaGóra") correctly in both languages without one.
    Aliases appear to only feed HA's built-in intent fuzzy matcher, not
    whatever tool schema qwen's Ollama-based conversation agent actually
    calls.

These are marked KNOWN-LIM in the report (not PASS, not silently hidden, and
NOT counted as a suite failure) rather than chased further, per the user's
explicit call.

This first run also found and fixed a real, unrelated bug: a dead-end Tuya
fixture (`light.office_light` / `fan.office_light` — a real light that is
powered *through* the office relay, so it reports "unavailable" whenever the
relay is off) had a cleaner English name than the relay itself and was
winning Assist's fuzzy match for BOTH agents in BOTH languages, so "turn on
the office light" silently "succeeded" against an unreachable entity while
the real relay never toggled. Fixed by hiding both from Assist exposure in
`heimdall/scripts/expose_entities.py` — voice control now correctly reaches
the relay for Gemini in both languages (qwen's remaining gap is the
`switch.office_led` conflict described above, which is a genuinely different
device, not the same bug recurring).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import requests
import websockets

DEFAULT_HA_URL = "http://192.168.0.108:8123"
DEFAULT_HA_WS_URL = "ws://192.168.0.108:8123/api/websocket"
DEFAULT_NTFY_URL = "http://192.168.0.108:8081"
DEFAULT_NTFY_TOPIC = "heimdall-failures"

GEMINI_AGENT = "conversation.google_ai_conversation"
QWEN_AGENT = "conversation.heimdall_local_qwen2_5"
AGENTS = {"gemini": GEMINI_AGENT, "qwen": QWEN_AGENT}

# Entity IDs below match heimdall/scripts/expose_entities.py exactly.
LIGHT_ENTITY = "switch.0x54ef4410016759d1_up"  # BiuroSwiatłoGłówne (office light)
CLIMATE_ENTITY = "climate.0xa4c138b1ad7dfd57"  # GrzejnikSypialniaGóra (bedroom radiator)
GATE_ENTITY = "switch.brama_sonoff_100254194e_1"  # Brama (gate relay)
AQUARIUM_TEMP_SENSOR = "sensor.0xa4c138060885ffff_temperature"  # Termometr
AQUARIUM_SWITCH = "switch.filtr"  # same choice as Task 4's Influx-write verification (observable, low-risk)
CALENDAR_ENTITY = "calendar.kamil_koterba95_gmail_com"

STATE_POLL_TIMEOUT_SECONDS = 10
STATE_POLL_INTERVAL_SECONDS = 1.5


@dataclass
class RowResult:
    row: str
    language: str
    agent: str
    passed: bool
    detail: str
    implementable: bool = True
    skipped: bool = False
    known_limitation: bool = False


# Documented, user-confirmed qwen-only gaps (see module docstring for the full
# investigation) - a failure here is reported as KNOWN-LIM, not FAIL, and does
# not fail the suite or publish to ntfy. Keyed by (row, agent_label).
KNOWN_QWEN_LIMITATIONS: dict[tuple[str, str], str] = {
    ("light_switch", "qwen"): (
        "qwen resolves \"office light\" to switch.office_led (a separate real TP-Link "
        "device) instead of the intended relay switch.0x54ef4410016759d1_up - accepted "
        "2026-08-20, not chased further (see heimdall/HA_CONFIG_CHANGES.md)."
    ),
    ("climate", "qwen"): (
        "qwen cannot resolve climate.0xa4c138b1ad7dfd57 even with an added English "
        "alias - aliases appear to only feed HA's built-in intent matcher, not qwen's "
        "own tool schema. Accepted 2026-08-20, not chased further."
    ),
}


def _apply_known_limitations(results: list[RowResult]) -> list[RowResult]:
    for r in results:
        if not r.passed and not r.skipped and (r.row, r.agent) in KNOWN_QWEN_LIMITATIONS:
            r.known_limitation = True
            r.detail += f" [KNOWN LIMITATION: {KNOWN_QWEN_LIMITATIONS[(r.row, r.agent)]}]"
    return results


class HaClient:
    def __init__(self, base_url: str, token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def get_state(self, entity_id: str) -> dict:
        resp = requests.get(f"{self.base_url}/api/states/{entity_id}", headers=self.headers, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def call_service(self, domain: str, service: str, entity_id: str, extra: dict | None = None) -> None:
        payload = {"entity_id": entity_id, **(extra or {})}
        resp = requests.post(
            f"{self.base_url}/api/services/{domain}/{service}",
            headers=self.headers,
            json=payload,
            timeout=15,
        )
        resp.raise_for_status()

    def process(self, text: str, language: str, agent_id: str) -> dict:
        resp = requests.post(
            f"{self.base_url}/api/conversation/process",
            headers=self.headers,
            json={"text": text, "language": language, "agent_id": agent_id},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def list_calendar_events(self, entity_id: str, start: datetime, end: datetime) -> list[dict]:
        resp = requests.get(
            f"{self.base_url}/api/calendars/{entity_id}",
            headers=self.headers,
            params={"start": start.isoformat(), "end": end.isoformat()},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else [data]


def _wait_for_state_change(ha: HaClient, entity_id: str, before: str) -> str:
    deadline = time.time() + STATE_POLL_TIMEOUT_SECONDS
    last = before
    while time.time() < deadline:
        time.sleep(STATE_POLL_INTERVAL_SECONDS)
        last = ha.get_state(entity_id)["state"]
        if last != before:
            return last
    return last


def _wait_for_attr_change(ha: HaClient, entity_id: str, attr: str, before):
    deadline = time.time() + STATE_POLL_TIMEOUT_SECONDS
    last = before
    while time.time() < deadline:
        time.sleep(STATE_POLL_INTERVAL_SECONDS)
        last = ha.get_state(entity_id)["attributes"].get(attr)
        if last != before:
            return last
    return last


# ---------------------------------------------------------------------------
# Gate: exposure-check only (see module docstring for why)
# ---------------------------------------------------------------------------


async def _check_exposure_ws(ws_url: str, token: str, entity_id: str) -> tuple[bool, str]:
    async with websockets.connect(ws_url, max_size=10_000_000) as ws:
        auth_required = json.loads(await ws.recv())
        if auth_required.get("type") != "auth_required":
            return False, f"unexpected handshake: {auth_required}"
        await ws.send(json.dumps({"type": "auth", "access_token": token}))
        auth_result = json.loads(await ws.recv())
        if auth_result.get("type") != "auth_ok":
            return False, f"authentication failed: {auth_result}"

        await ws.send(json.dumps({"id": 1, "type": "homeassistant/expose_entity/list"}))
        result = json.loads(await ws.recv())
        if not result.get("success"):
            return False, f"expose_entity/list failed: {result}"

        exposed = result["result"].get("exposed_entities", {})
        flag = exposed.get(entity_id, {}).get("conversation")
        return flag is True, f"conversation exposure flag = {flag!r}"


def check_gate_exposure(ws_url: str, token: str) -> RowResult:
    try:
        exposed, detail = asyncio.run(_check_exposure_ws(ws_url, token, GATE_ENTITY))
    except Exception as exc:  # noqa: BLE001 - report as a failed row, not a crash
        return RowResult("gate", "n/a", "n/a", False, f"exposure check errored: {exc}")
    return RowResult(
        "gate",
        "n/a",
        "n/a",
        exposed,
        f"{GATE_ENTITY}: {detail} (exposure-check only, no physical actuation — see module docstring)",
    )


# ---------------------------------------------------------------------------
# Generic on/off toggle row (light_switch, aquarium_write)
# ---------------------------------------------------------------------------


def check_toggle(
    ha: HaClient,
    row: str,
    entity: str,
    language: str,
    agent_id: str,
    agent_label: str,
    phrase_on: str,
    phrase_off: str,
    allow_actuation: bool,
) -> RowResult:
    if not allow_actuation:
        return RowResult(
            row,
            language,
            agent_label,
            True,
            f"SKIPPED by default: {entity} toggling flips a real physical device. Rerun with "
            "--allow-physical-actuation to actually exercise this row.",
            skipped=True,
        )

    before = ha.get_state(entity)["state"]
    phrase = phrase_off if before == "on" else phrase_on
    ha.process(phrase, language, agent_id)
    after = _wait_for_state_change(ha, entity, before)
    passed = after != before
    detail = f'{entity}: {before} -> {after} via {agent_label} ("{phrase}")'

    # Restore directly via the REST API (not voice) so repeated/soak runs stay idempotent.
    if passed:
        domain = entity.split(".")[0]
        ha.call_service(domain, "turn_on" if before == "on" else "turn_off", entity)

    return RowResult(row, language, agent_label, passed, detail)


# ---------------------------------------------------------------------------
# Climate row
# ---------------------------------------------------------------------------


def check_climate(
    ha: HaClient, language: str, agent_id: str, agent_label: str, phrase: str, allow_actuation: bool
) -> RowResult:
    if not allow_actuation:
        return RowResult(
            "climate",
            language,
            agent_label,
            True,
            f"SKIPPED by default: {CLIMATE_ENTITY} setpoint change affects a real radiator. Rerun with "
            "--allow-physical-actuation to actually exercise this row.",
            skipped=True,
        )

    before = ha.get_state(CLIMATE_ENTITY)["attributes"].get("temperature")
    ha.process(phrase, language, agent_id)
    after = _wait_for_attr_change(ha, CLIMATE_ENTITY, "temperature", before)
    passed = after is not None and after != before
    detail = f'{CLIMATE_ENTITY} target temperature: {before} -> {after} via {agent_label} ("{phrase}")'

    if passed and before is not None:
        ha.call_service("climate", "set_temperature", CLIMATE_ENTITY, {"temperature": before})

    return RowResult("climate", language, agent_label, passed, detail)


# ---------------------------------------------------------------------------
# Aquarium read row
# ---------------------------------------------------------------------------


def check_aquarium_read(ha: HaClient, language: str, agent_id: str, agent_label: str, phrase: str) -> RowResult:
    actual = ha.get_state(AQUARIUM_TEMP_SENSOR)["state"]
    resp = ha.process(phrase, language, agent_id)
    speech = resp["response"]["speech"]["plain"]["speech"]

    try:
        actual_int = str(int(float(actual)))
    except ValueError:
        actual_int = actual

    passed = resp["response"]["response_type"] != "error" and actual_int in speech
    detail = f"actual={actual}, response={speech!r}"
    return RowResult("aquarium_read", language, agent_label, passed, detail)


# ---------------------------------------------------------------------------
# Calendar read row
# ---------------------------------------------------------------------------


def check_calendar_read(ha: HaClient, language: str, agent_id: str, agent_label: str, phrase: str) -> RowResult:
    resp = ha.process(phrase, language, agent_id)
    speech = resp["response"]["speech"]["plain"]["speech"]
    passed = resp["response"]["response_type"] != "error" and len(speech.strip()) > 0
    return RowResult("calendar_read_own", language, agent_label, passed, f"response={speech!r}")


# ---------------------------------------------------------------------------
# Calendar write row (own calendar only — see module docstring)
# ---------------------------------------------------------------------------


def check_calendar_write(
    ha: HaClient, language: str, agent_id: str, agent_label: str, allow_write: bool
) -> RowResult:
    is_qwen = agent_id == QWEN_AGENT

    if not is_qwen and not allow_write:
        return RowResult(
            "calendar_write_own",
            language,
            agent_label,
            True,
            "SKIPPED by default: no calendar.delete_event service exists (confirmed via /api/services), "
            "so a real Gemini write leaves a permanent event. Rerun with --allow-calendar-write to "
            "actually exercise this row, then delete the resulting event manually.",
            skipped=True,
        )

    marker = f"HEIMDALL-TESTMATRIX-{uuid.uuid4().hex[:8]}"
    if language == "pl":
        phrase = f"Dodaj wydarzenie o nazwie {marker} jutro o 17:00 do mojego kalendarza"
    else:
        phrase = f"Add an event called {marker} tomorrow at 5pm to my calendar"

    ha.process(phrase, language, agent_id)
    time.sleep(3)  # give the Google Calendar round-trip a moment to land

    window_start = datetime.now(timezone.utc) - timedelta(hours=1)
    window_end = datetime.now(timezone.utc) + timedelta(days=3)
    events = ha.list_calendar_events(CALENDAR_ENTITY, window_start, window_end)
    created = any(e.get("summary") == marker for e in events)

    if is_qwen:
        passed = not created  # honest refusal is the CORRECT behaviour here, not a failure
        detail = f"qwen refusal check: event {'was WRONGLY created' if created else 'correctly NOT created'} ({marker})"
    else:
        passed = created
        detail = f"Gemini write check: event {'created' if created else 'MISSING'} ({marker})"
        if created:
            detail += " — not auto-deleted (no delete service); remove manually in Google Calendar."

    return RowResult("calendar_write_own", language, agent_label, passed, detail)


# ---------------------------------------------------------------------------
# Open-domain row
# ---------------------------------------------------------------------------


def check_open_domain(ha: HaClient, language: str, agent_id: str, agent_label: str) -> RowResult:
    if language == "pl":
        phrase, expected = "Jaka jest stolica Francji?", "paryż"
    else:
        phrase, expected = "What is the capital of France?", "paris"

    resp = ha.process(phrase, language, agent_id)
    speech = resp["response"]["speech"]["plain"]["speech"]
    passed = resp["response"]["response_type"] != "error" and expected in speech.lower()
    return RowResult("open_domain", language, agent_label, passed, f"response={speech!r}")


# ---------------------------------------------------------------------------
# Ambiguous / mixed-language row (soft check — see module docstring)
# ---------------------------------------------------------------------------


def check_ambiguous_mixed(ha: HaClient, agent_id: str, agent_label: str, allow_actuation: bool) -> RowResult:
    if not allow_actuation:
        return RowResult(
            "ambiguous_mixed_language",
            "mixed",
            agent_label,
            True,
            "SKIPPED by default: this phrase is a real 'turn on the office light' command "
            "(deliberately code-switched EN/PL), same physical device as light_switch. Rerun with "
            "--allow-physical-actuation to actually exercise this row.",
            skipped=True,
        )

    phrase = "Turn on światło w biurze please"  # deliberately code-switched EN/PL
    before = ha.get_state(LIGHT_ENTITY)["state"]
    resp = ha.process(phrase, "en", agent_id)
    response_type = resp["response"]["response_type"]
    speech = resp["response"]["speech"]["plain"]["speech"]
    passed = response_type != "error"  # soft check: must not hard-error; exact entity match not required
    detail = f"response_type={response_type}, response={speech!r} (soft check only)"

    # This phrase is a real actuation command, not a read - restore the light the same way
    # check_toggle does, so this row doesn't leave it on/off differently than it found it.
    after = ha.get_state(LIGHT_ENTITY)["state"]
    if after != before:
        ha.call_service("switch", "turn_on" if before == "on" else "turn_off", LIGHT_ENTITY)

    return RowResult("ambiguous_mixed_language", "mixed", agent_label, passed, detail)


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def run_matrix(
    ha: HaClient, ws_url: str, token: str, allow_calendar_write: bool, allow_physical_actuation: bool
) -> list[RowResult]:
    results: list[RowResult] = [check_gate_exposure(ws_url, token)]

    for lang in ("en", "pl"):
        for agent_label, agent_id in AGENTS.items():
            if lang == "en":
                on_phrase, off_phrase = "Turn on the office light", "Turn off the office light"
                climate_phrase = "Set the bedroom radiator to 22 degrees"
                aq_read_phrase = "What's the water temperature in the aquarium?"
                aq_on, aq_off = "Turn on the aquarium filter", "Turn off the aquarium filter"
                cal_read_phrase = "What's on my calendar this week?"
            else:
                on_phrase, off_phrase = "Włącz światło w biurze", "Wyłącz światło w biurze"
                climate_phrase = "Ustaw grzejnik w sypialni na 22 stopnie"
                aq_read_phrase = "Jaka jest temperatura wody w akwarium?"
                aq_on, aq_off = "Włącz filtr w akwarium", "Wyłącz filtr w akwarium"
                cal_read_phrase = "Co mam w kalendarzu w tym tygodniu?"

            results.append(
                check_toggle(
                    ha, "light_switch", LIGHT_ENTITY, lang, agent_id, agent_label, on_phrase, off_phrase,
                    allow_physical_actuation,
                )
            )
            results.append(check_climate(ha, lang, agent_id, agent_label, climate_phrase, allow_physical_actuation))
            results.append(check_aquarium_read(ha, lang, agent_id, agent_label, aq_read_phrase))
            results.append(
                check_toggle(
                    ha, "aquarium_write", AQUARIUM_SWITCH, lang, agent_id, agent_label, aq_on, aq_off,
                    allow_physical_actuation,
                )
            )
            results.append(check_calendar_read(ha, lang, agent_id, agent_label, cal_read_phrase))
            results.append(check_calendar_write(ha, lang, agent_id, agent_label, allow_calendar_write))
            results.append(check_open_domain(ha, lang, agent_id, agent_label))

    results.append(
        RowResult(
            "calendar_write_other",
            "n/a",
            "n/a",
            True,
            "NOT IMPLEMENTABLE: only one Google Calendar account is connected (confirmed live via "
            "/api/states — no second-person calendar exists). The original brief assumed two accounts; "
            "Task 5 only set up one. Confirmed with the user to leave this out rather than fake it.",
            implementable=False,
        )
    )

    for agent_label, agent_id in AGENTS.items():
        results.append(check_ambiguous_mixed(ha, agent_id, agent_label, allow_physical_actuation))

    return _apply_known_limitations(results)


def publish_failure(ntfy_url: str, ntfy_token: str, topic: str, result: RowResult) -> None:
    title = f"Heimdall test-matrix FAILURE: {result.row} ({result.language}/{result.agent})"
    headers = {"Title": title, "Priority": "4", "Authorization": f"Bearer {ntfy_token}"}
    try:
        requests.post(
            f"{ntfy_url.rstrip('/')}/{topic}",
            data=result.detail.encode("utf-8"),
            headers=headers,
            timeout=10,
        )
    except requests.RequestException as exc:
        print(f"WARNING: failed to publish failure to ntfy: {exc}", file=sys.stderr)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Windows cp1252 can't print Polish diacritics

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ha-url", default=os.environ.get("HEIMDALL_HA_URL", DEFAULT_HA_URL))
    parser.add_argument("--ha-ws-url", default=os.environ.get("HEIMDALL_HA_WS_URL", DEFAULT_HA_WS_URL))
    parser.add_argument("--ntfy-url", default=os.environ.get("HEIMDALL_NTFY_URL", DEFAULT_NTFY_URL))
    parser.add_argument("--ntfy-topic", default=os.environ.get("HEIMDALL_NTFY_TOPIC", DEFAULT_NTFY_TOPIC))
    parser.add_argument(
        "--allow-calendar-write",
        action="store_true",
        help="Actually exercise Gemini's calendar-write row (leaves a permanent test event — see docstring).",
    )
    parser.add_argument(
        "--allow-physical-actuation",
        action="store_true",
        help="Actually toggle the office light/aquarium filter and change the bedroom radiator setpoint "
        "(restored afterward, but briefly real - annoying for unattended/scheduled runs, so off by default).",
    )
    args = parser.parse_args()

    token = os.environ.get("HEIMDALL_HA_TOKEN")
    if not token:
        print("ERROR: set HEIMDALL_HA_TOKEN to a Home Assistant long-lived access token.", file=sys.stderr)
        return 1

    ntfy_token = os.environ.get("HEIMDALL_NTFY_TOKEN")

    ha = HaClient(args.ha_url, token)
    results = run_matrix(ha, args.ha_ws_url, token, args.allow_calendar_write, args.allow_physical_actuation)

    print(f"\n{'ROW':<24}{'LANG':<7}{'AGENT':<8}{'RESULT':<11}DETAIL")
    print("-" * 110)
    failures = 0
    for r in results:
        if not r.implementable:
            status = "N/A"
        elif r.skipped:
            status = "SKIPPED"
        elif r.known_limitation:
            status = "KNOWN-LIM"
        else:
            status = "PASS" if r.passed else "FAIL"
            if not r.passed:
                failures += 1
                if ntfy_token:
                    publish_failure(args.ntfy_url, ntfy_token, args.ntfy_topic, r)
        print(f"{r.row:<24}{r.language:<7}{r.agent:<8}{status:<11}{r.detail}")

    implementable = [r for r in results if r.implementable and not r.skipped and not r.known_limitation]
    na_count = sum(1 for r in results if not r.implementable)
    skipped_count = sum(1 for r in results if r.skipped)
    known_limitation_count = sum(1 for r in results if r.known_limitation)
    print("-" * 110)
    print(
        f"{len(implementable) - failures}/{len(implementable)} implementable checks passed "
        f"({na_count} N/A, {skipped_count} skipped-by-default, {known_limitation_count} known-limitation)"
    )

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
