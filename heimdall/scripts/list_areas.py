#!/usr/bin/env python3
"""Read-only: list all HA areas (id, name, floor) to find where the alarm
siren entities (Syrena+Swiatlo, SyrenaZew - currently unassigned) should go.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

import websockets

HA_WS_URL = os.environ.get("HEIMDALL_HA_WS_URL", "ws://192.168.0.108:8123/api/websocket")


async def main() -> int:
    token = os.environ.get("HEIMDALL_HA_TOKEN")
    if not token:
        print("ERROR: set HEIMDALL_HA_TOKEN", file=sys.stderr)
        return 1

    async with websockets.connect(HA_WS_URL, max_size=10_000_000) as ws:
        await ws.recv()
        await ws.send(json.dumps({"type": "auth", "access_token": token}))
        await ws.recv()
        await ws.send(json.dumps({"id": 2, "type": "config/area_registry/list"}))
        result = json.loads(await ws.recv())["result"]
        for a in sorted(result, key=lambda x: x.get("name", "")):
            print(f"{a['area_id']!r:35} name={a.get('name')!r} floor={a.get('floor_id')}")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
