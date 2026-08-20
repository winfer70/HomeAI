#!/usr/bin/env python3
"""Read-only: check should_expose for the two new boost scripts."""
from __future__ import annotations

import asyncio
import json
import os
import sys

import websockets

HA_WS_URL = os.environ.get("HEIMDALL_HA_WS_URL", "ws://192.168.0.108:8123/api/websocket")
ENTITIES = ["script.heimdall_boost_revert_worker", "script.heimdall_boost_heating"]


async def main() -> int:
    token = os.environ.get("HEIMDALL_HA_TOKEN")
    if not token:
        print("ERROR: set HEIMDALL_HA_TOKEN", file=sys.stderr)
        return 1

    async with websockets.connect(HA_WS_URL, max_size=10_000_000) as ws:
        await ws.recv()
        await ws.send(json.dumps({"type": "auth", "access_token": token}))
        await ws.recv()
        for eid in ENTITIES:
            await ws.send(json.dumps({"id": 2, "type": "config/entity_registry/get", "entity_id": eid}))
            r = json.loads(await ws.recv())
            print(eid, r["result"].get("options"))

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
