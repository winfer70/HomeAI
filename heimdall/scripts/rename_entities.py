#!/usr/bin/env python3
"""One-off: rename entities to clear, unambiguous English names so qwen's
literal name-matching stops confusing them (Heimdall backlog #6, 2026-08-20).

- switch.0x54ef4410016759d1_up: 'BiuroSwiatloGlowne Up' -> 'Office Main Light'
  (the actual relay meant by "turn on the office light") - FIXED qwen's
  light_switch resolution, confirmed via live test_matrix.py run.
- switch.office_led: 'Office LED' -> 'Office LED Strip'
  (a separate, real LED strip - was winning qwen's fuzzy match over the relay)

climate.0xa4c138b1ad7dfd57 ('GrzejnikSypialniaGora') was ALSO renamed to
'Bedroom Radiator' as part of this same fix attempt - it did NOT help (qwen's
climate resolution failed identically before and after), and the user
reverted it back to the original Polish name. Root cause confirmed via HA
core source (homeassistant/components/climate/intent.py): the SetTemperature
intent's slot schema has `temperature` as required but `name` as optional -
qwen isn't reliably including `name` when a required numeric slot is also
present, so this is a qwen tool-calling capability gap, not an entity-naming
problem. Intentionally left out of RENAMES below - do not re-add without a
new plan (see heimdall/PHASE1_5_HARDENING_AND_PHASE2_PLAN.md backlog #6).

Usage:
    HEIMDALL_HA_TOKEN=<token> python rename_entities.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

import websockets

HA_WS_URL = os.environ.get("HEIMDALL_HA_WS_URL", "ws://192.168.0.108:8123/api/websocket")

RENAMES = {
    "switch.0x54ef4410016759d1_up": "Office Main Light",
    "switch.office_led": "Office LED Strip",
}


async def main() -> int:
    token = os.environ.get("HEIMDALL_HA_TOKEN")
    if not token:
        print("ERROR: set HEIMDALL_HA_TOKEN", file=sys.stderr)
        return 1

    async with websockets.connect(HA_WS_URL, max_size=10_000_000) as ws:
        auth_required = json.loads(await ws.recv())
        assert auth_required["type"] == "auth_required", auth_required
        await ws.send(json.dumps({"type": "auth", "access_token": token}))
        auth_result = json.loads(await ws.recv())
        if auth_result["type"] != "auth_ok":
            print(f"ERROR: auth failed: {auth_result}", file=sys.stderr)
            return 1

        msg_id = 1
        for entity_id, new_name in RENAMES.items():
            msg_id += 1
            await ws.send(json.dumps({
                "id": msg_id,
                "type": "config/entity_registry/update",
                "entity_id": entity_id,
                "name": new_name,
            }))
            result = json.loads(await ws.recv())
            if result.get("success"):
                print(f"OK: {entity_id} -> {new_name!r}")
            else:
                print(f"ERROR: {entity_id}: {result}", file=sys.stderr)
                return 1

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
