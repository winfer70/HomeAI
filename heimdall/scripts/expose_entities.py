#!/usr/bin/env python3
"""Expose the confirmed Heimdall entity list to Assist (HA voice control).

Uses HA's public WebSocket API (`homeassistant/expose_entity` to set,
`homeassistant/expose_entity/list` to read current state) — never touches
`.storage/` directly, consistent with this project's guardrail around
Assist internal state.

Entity IDs below were resolved against the live HA instance by matching the
brief's device names to the entity registry / current states (some names in
the original brief didn't match exactly - see inline notes). Ambiguous cases
(WłącznikSalon's two channels, the renamed "Hive Active Heating Receiver")
were confirmed with the user before being added here - do not add further
entities to this list without the same confirmation step.

Deliberately excludes (per the brief, confirmed unchanged):
  - WłącznikDółDrzwi, WłącznikBiurko, WłącznikSypialniaGóra2
    (wireless trigger buttons, not toggle-able lights)
  - Brama (gate relay - separate decision, not part of this task)
  - Anything alarm-related (blocked by Task 0's guardrail regardless)

Usage:
    HEIMDALL_HA_TOKEN=<long-lived token> python expose_entities.py

Idempotent: only calls expose_entity for entities not already exposed with
should_expose=True for the "conversation" assistant.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

import websockets

DEFAULT_HA_URL = "ws://192.168.0.108:8123/api/websocket"

ASSISTANT = "conversation"

# entity_id -> brief name, for readable output only.
ENTITIES_TO_EXPOSE = {
    "climate.0xa4c138b1ad7dfd57": "GrzejnikSypialniaGóra",
    "climate.0xa4c138c7970d8809": "GrzejnikBiuro",
    "climate.0xa4c1387c4f428097": "GrzejnikŁazienkaGóraOkno",
    "climate.0xa4c13881297bc097": "GrzejnikŁazienkaGóraDrzwi",
    "switch.0x54ef4410016759d1_up": "BiuroSwiatłoGłówne",
    "switch.0x54ef44100167601c_up": "SypialniaŚwiatłoGłówne",
    "switch.0x54ef4410015687f1_left": "WłącznikSalon (fireplace lights)",
    "switch.0x54ef4410015687f1_right": "WłącznikSalon (main light)",
    "switch.0x54ef441001525ff8_up": "WłącznikKuchniaLed",
    "climate.0x001e5e0902ce8e9a": "Ogrzewanie (formerly Hive Active Heating Receiver)",
    # WłącznikDółDrzwi's relays turned out to be real mains-powered lights (not
    # a wireless button as the original brief assumed) - confirmed with user
    # 2026-08-19, added to exposure.
    "switch.0x54ef44100156879e_left": "WłącznikDółDrzwi (light, left relay)",
    "switch.0x54ef44100156879e_right": "WłącznikDółDrzwi (light, right relay)",
    # Gate relay + its button-click sensor were originally hidden (see
    # ENTITIES_TO_HIDE's old comment, still below in git history) to keep
    # physical access control away from the local 7B model. Re-exposed to
    # BOTH conversation agents at the user's explicit, informed request
    # (2026-08-19) after a full risk discussion covering: HA has no
    # per-conversation-agent exposure scoping (so this can't be Gemini-only),
    # no confirmation step exists before a tool call executes, and the
    # button-click sensor is an equally capable trigger for the same
    # gate-toggle automation. The user's call: "convenience matters more
    # here." Confirmed working live via voice (opens and closes the gate).
    # Do not silently re-hide this - if it needs revisiting, that's a new
    # decision to make with the user, not a default to restore.
    "switch.brama_sonoff_100254194e_1": "Brama (gate relay)",
    "switch.0x54ef44100156879e_multi_click_left_down": (
        "WłącznikDółDrzwi button-click sensor (drives a gate-toggle automation)"
    ),
    # Task 8 (M7) — persistent memory tool-calling scripts. Exposing a
    # script entity with `fields` to the "conversation" assistant is what
    # makes HA's built-in Assist LLM API auto-generate a callable tool from
    # it, for both conversation agents.
    "script.heimdall_remember_fact": "Heimdall: Remember a fact",
    "script.heimdall_recall_facts": "Heimdall: Recall facts",
}

# HA exposes entire domains (switch, climate, light, ...) to Assist by
# default unless an entity is explicitly hidden. That default sweeps in
# things this project must NOT expose: the physical button-click-type
# entity that drives an unrelated night-light automation. Explicitly hide
# it regardless of its current default-exposed state - this is a narrower,
# unrelated concern from the alarm guardrail, but same spirit: don't let
# voice touch things it has no reason to.
ENTITIES_TO_HIDE = {
    "switch.0x54ef44100156879e_multi_click_right_down": (
        "WłącznikDółDrzwi button-click sensor (drives a night-light automation)"
    ),
}

# Guardrail: reject anything from the alarm domain even if accidentally added
# above. The full forbidden-name check (see Task 0's CI guardrail script) is
# already enforced repo-wide on every file under heimdall/** - this is just a
# narrow, domain-based backstop specific to the entity list this script
# actually submits to HA.
FORBIDDEN_DOMAIN_PREFIXES = ("alarm_control_panel.", "alarm.")


def assert_no_alarm_entities() -> None:
    for entity_id in ENTITIES_TO_EXPOSE:
        if entity_id.lower().startswith(FORBIDDEN_DOMAIN_PREFIXES):
            raise SystemExit(
                f"REFUSING TO RUN: forbidden alarm-related entity found: {entity_id}"
            )


class HaWebSocket:
    """Tiny helper around HA's WebSocket API with auto-incrementing message ids."""

    def __init__(self, ws: websockets.WebSocketClientProtocol) -> None:
        self._ws = ws
        self._next_id = 1

    async def call(self, payload: dict) -> dict:
        msg_id = self._next_id
        self._next_id += 1
        payload = {"id": msg_id, **payload}
        await self._ws.send(json.dumps(payload))
        result = json.loads(await self._ws.recv())
        if result.get("id") != msg_id:
            raise RuntimeError(f"Unexpected response id: {result}")
        return result


async def authenticate(ws: websockets.WebSocketClientProtocol, token: str) -> None:
    auth_required = json.loads(await ws.recv())
    if auth_required.get("type") != "auth_required":
        raise RuntimeError(f"Unexpected handshake message: {auth_required}")

    await ws.send(json.dumps({"type": "auth", "access_token": token}))
    auth_result = json.loads(await ws.recv())
    if auth_result.get("type") != "auth_ok":
        raise RuntimeError(f"Authentication failed: {auth_result}")


async def main() -> int:
    # Windows' default cp1252 console can't print Polish diacritics in the
    # entity labels above - force UTF-8 stdout so this runs cleanly there too.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    assert_no_alarm_entities()

    token = os.environ.get("HEIMDALL_HA_TOKEN")
    if not token:
        print(
            "ERROR: set HEIMDALL_HA_TOKEN to a Home Assistant long-lived access token.",
            file=sys.stderr,
        )
        return 1

    ha_url = os.environ.get("HEIMDALL_HA_URL", DEFAULT_HA_URL)

    async with websockets.connect(ha_url, max_size=10_000_000) as ws:
        await authenticate(ws, token)
        client = HaWebSocket(ws)

        current = await client.call({"type": "homeassistant/expose_entity/list"})
        if not current.get("success"):
            print(f"ERROR: could not list exposed entities: {current}", file=sys.stderr)
            return 1

        exposed = current["result"].get("exposed_entities", {})

        for entity_id, label in ENTITIES_TO_EXPOSE.items():
            already_exposed = exposed.get(entity_id, {}).get(ASSISTANT) is True
            if already_exposed:
                print(f"SKIP: {entity_id} ({label}) already exposed.")
                continue

            result = await client.call(
                {
                    "type": "homeassistant/expose_entity",
                    "assistants": [ASSISTANT],
                    "entity_ids": [entity_id],
                    "should_expose": True,
                }
            )
            if not result.get("success"):
                print(
                    f"ERROR: failed to expose {entity_id} ({label}): {result}",
                    file=sys.stderr,
                )
                return 1

            print(f"EXPOSED: {entity_id} ({label})")

        for entity_id, label in ENTITIES_TO_HIDE.items():
            currently_exposed = exposed.get(entity_id, {}).get(ASSISTANT) is True
            if not currently_exposed:
                print(f"SKIP: {entity_id} ({label}) already hidden.")
                continue

            result = await client.call(
                {
                    "type": "homeassistant/expose_entity",
                    "assistants": [ASSISTANT],
                    "entity_ids": [entity_id],
                    "should_expose": False,
                }
            )
            if not result.get("success"):
                print(
                    f"ERROR: failed to hide {entity_id} ({label}): {result}",
                    file=sys.stderr,
                )
                return 1

            print(f"HIDDEN: {entity_id} ({label})")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
