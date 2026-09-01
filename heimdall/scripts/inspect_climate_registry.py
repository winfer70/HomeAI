#!/usr/bin/env python3
"""Read-only: dump full entity_registry entries (name, original_name, aliases,
area_id, device_id) for all climate entities, to find what's actually
different about climate.0xa4c138b1ad7dfd57 vs its siblings.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

import websockets

HA_WS_URL = os.environ.get("HEIMDALL_HA_WS_URL", "ws://192.168.0.108:8123/api/websocket")

ENTITIES = [
    "climate.0xa4c138b1ad7dfd57",
    "climate.0xa4c13842240065f9",
    "climate.0xa4c1387c4f428097",
    "climate.0xa4c13881297bc097",
    "climate.0xa4c138b90fef70c7",
    "climate.0xa4c138c7970d8809",
    "climate.0xa4c138d920585e93",
    "climate.0x001e5e0902ce8e9a",
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
        for entity_id in ENTITIES:
            msg_id += 1
            await ws.send(json.dumps({
                "id": msg_id,
                "type": "config/entity_registry/get",
                "entity_id": entity_id,
            }))
            result = json.loads(await ws.recv())
            entry = result.get("result", {})
            print(f"=== {entity_id} ===")
            print(json.dumps({
                "name": entry.get("name"),
                "original_name": entry.get("original_name"),
                "aliases": entry.get("aliases"),
                "area_id": entry.get("area_id"),
                "device_id": entry.get("device_id"),
                "disabled_by": entry.get("disabled_by"),
                "hidden_by": entry.get("hidden_by"),
                "icon": entry.get("icon"),
                "labels": entry.get("labels"),
            }, indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
