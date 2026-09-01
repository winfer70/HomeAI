#!/usr/bin/env python3
"""One-off: assign the alarm siren devices (Syrena+Swiatlo, SyrenaZew -
previously unassigned, device_area=None) to the 'domballivor' area, per
user's direction. Assigning at the DEVICE level (not entity level) to match
the pattern every other device in this house already uses.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

import websockets

HA_WS_URL = os.environ.get("HEIMDALL_HA_WS_URL", "ws://192.168.0.108:8123/api/websocket")
AREA_ID = "domballivor"


async def main() -> int:
    token = os.environ.get("HEIMDALL_HA_TOKEN")
    if not token:
        print("ERROR: set HEIMDALL_HA_TOKEN", file=sys.stderr)
        return 1

    async with websockets.connect(HA_WS_URL, max_size=10_000_000) as ws:
        await ws.recv()
        await ws.send(json.dumps({"type": "auth", "access_token": token}))
        await ws.recv()

        await ws.send(json.dumps({"id": 2, "type": "config/device_registry/list"}))
        result = json.loads(await ws.recv())["result"]

        targets = [d for d in result if (d.get("name_by_user") or d.get("name")) in ("Syrena+Swiatło", "SyrenaZew")]
        if not targets:
            print("ERROR: no matching devices found", file=sys.stderr)
            return 1

        msg_id = 3
        for d in targets:
            msg_id += 1
            await ws.send(json.dumps({
                "id": msg_id,
                "type": "config/device_registry/update",
                "device_id": d["id"],
                "area_id": AREA_ID,
            }))
            r = json.loads(await ws.recv())
            if r.get("success"):
                entry = r["result"]
                print(f"OK: {d.get('name_by_user') or d.get('name')} -> area_id={entry.get('area_id')}")
            else:
                print(f"ERROR updating {d['id']}: {r}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
