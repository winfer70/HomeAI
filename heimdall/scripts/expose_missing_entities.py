#!/usr/bin/env python3
"""One-off: expose 4 previously-hidden entities to Assist (should_expose=true):

- alarm_control_panel.glowne  - main alarm panel, wasn't voice-exposed at all
- siren.driveway_siren        - driveway siren, wasn't voice-exposed at all
- light.office_light          - office light+fan combo unit; only powered when
- fan.office_light            - switch.office_led (the upstream relay) is on.
  Both entities were hidden while only the raw power switch was exposed -
  exposing them too gives voice control over brightness/fan speed, not just
  on/off via the switch.

Do NOT test alarm/siren tonight (nighttime) - verify tomorrow.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

import websockets

HA_WS_URL = os.environ.get("HEIMDALL_HA_WS_URL", "ws://192.168.0.108:8123/api/websocket")

ENTITIES_TO_EXPOSE = [
    "alarm_control_panel.glowne",
    "siren.driveway_siren",
    "light.office_light",
    "fan.office_light",
]


async def main() -> int:
    token = os.environ.get("HEIMDALL_HA_TOKEN")
    if not token:
        print("ERROR: set HEIMDALL_HA_TOKEN", file=sys.stderr)
        return 1

    async with websockets.connect(HA_WS_URL, max_size=10_000_000) as ws:
        auth_required = json.loads(await ws.recv())
        assert auth_required["type"] == "auth_required"
        await ws.send(json.dumps({"type": "auth", "access_token": token}))
        auth_result = json.loads(await ws.recv())
        if auth_result["type"] != "auth_ok":
            print(f"ERROR: auth failed: {auth_result}", file=sys.stderr)
            return 1

        msg_id = 1
        for entity_id in ENTITIES_TO_EXPOSE:
            msg_id += 1
            await ws.send(json.dumps({
                "id": msg_id,
                "type": "config/entity_registry/update",
                "entity_id": entity_id,
                "options_domain": "conversation",
                "options": {"should_expose": True},
            }))
            result = json.loads(await ws.recv())
            if result.get("success"):
                entry = result["result"]["entity_entry"]
                exposed = (entry.get("options") or {}).get("conversation", {}).get("should_expose")
                print(f"OK: {entity_id} should_expose={exposed}")
            else:
                print(f"ERROR: {entity_id}: {result}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
