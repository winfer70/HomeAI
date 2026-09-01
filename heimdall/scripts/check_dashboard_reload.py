#!/usr/bin/env python3
"""Read-only: fetch the current in-memory lovelace config for
dashboard-biuro via the WS API, to check whether the directly-edited
storage file is already reflected without a restart, or whether HA needs
a restart to pick up externally-written storage files.
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
        await ws.send(json.dumps({"id": 2, "type": "lovelace/config", "url_path": "dashboard-biuro"}))
        result = json.loads(await ws.recv())
        content = json.dumps(result)
        print("Contains 'Boost 1h':", "Boost 1h" in content)
        print("Contains 'heimdall_boost_heating':", "heimdall_boost_heating" in content)

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
