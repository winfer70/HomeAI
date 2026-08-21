#!/usr/bin/env python3
"""Read-only: check should_expose + full registry entry for all 6 Meross
surge-protector outlets specifically, to find what's different about the
3 that never show up in area-listing answers (Listwa, Biurko_LED,
StacjaDokujaca) vs the 3 that do (Monitor_1, Monitor_2, LED_1).
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

import websockets

HA_WS_URL = os.environ.get("HEIMDALL_HA_WS_URL", "ws://192.168.0.108:8123/api/websocket")

OUTLETS = [
    "switch.smart_switch_20111713503031290d1748e1e93cb12d_outlet",
    "switch.smart_switch_20111713503031290d1748e1e93cb12d_outlet_1",
    "switch.smart_switch_20111713503031290d1748e1e93cb12d_outlet_2",
    "switch.smart_switch_20111713503031290d1748e1e93cb12d_outlet_3",
    "switch.smart_switch_20111713503031290d1748e1e93cb12d_outlet_4",
    "switch.smart_switch_20111713503031290d1748e1e93cb12d_outlet_5",
]


async def main() -> int:
    token = os.environ.get("HEIMDALL_HA_TOKEN")
    if not token:
        print("ERROR: set HEIMDALL_HA_TOKEN", file=sys.stderr)
        return 1

    async with websockets.connect(HA_WS_URL, max_size=10_000_000) as ws:
        await ws.recv()
        await ws.send(json.dumps({"type": "auth", "access_token": token}))
        await ws.recv()

        msg_id = 1
        for entity_id in OUTLETS:
            msg_id += 1
            await ws.send(json.dumps({"id": msg_id, "type": "config/entity_registry/get", "entity_id": entity_id}))
            r = json.loads(await ws.recv())["result"]
            exposed = (r.get("options") or {}).get("conversation", {}).get("should_expose")
            print(f"{entity_id}")
            print(f"  name={r.get('name')!r} original_name={r.get('original_name')!r}")
            print(f"  should_expose={exposed} disabled_by={r.get('disabled_by')} hidden_by={r.get('hidden_by')}")
            print(f"  entity_category={r.get('entity_category')} labels={r.get('labels')}")

        # Live states too, in case one is unavailable
        req_id = msg_id + 1
        await ws.send(json.dumps({"id": req_id, "type": "get_states"}))
        states = json.loads(await ws.recv())["result"]
        states_by_id = {s["entity_id"]: s for s in states}
        print("\n--- live states ---")
        for entity_id in OUTLETS:
            s = states_by_id.get(entity_id)
            print(f"{entity_id}: state={s.get('state') if s else 'MISSING'}")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
