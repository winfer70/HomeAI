#!/usr/bin/env python3
"""Read-only: dump area_registry entries for all areas used by the 8 climate
devices, to check if 'sypialniagora' area's registered name/aliases differ
from what qwen guessed ('SypialniaGora') in a way that would make HA's
MatchTargetsConstraints area_name match fail.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

import websockets

HA_WS_URL = os.environ.get("HEIMDALL_HA_WS_URL", "ws://192.168.0.108:8123/api/websocket")

AREA_IDS = [
    "sypialniagora",  # PROBLEM
    "goscinny",
    "lazienkagora",
    "salon",
    "office",
    "sypialniadol",
    "kuchnia",
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

        await ws.send(json.dumps({"id": 2, "type": "config/area_registry/list"}))
        result = json.loads(await ws.recv())
        all_areas = {a["area_id"]: a for a in result.get("result", [])}

        for area_id in AREA_IDS:
            entry = all_areas.get(area_id)
            marker = " <-- PROBLEM" if area_id == "sypialniagora" else ""
            if entry is None:
                print(f"=== {area_id}{marker}: NOT FOUND IN AREA REGISTRY ===")
                continue
            print(f"=== {area_id}{marker} ===")
            print(json.dumps({
                "name": entry.get("name"),
                "aliases": entry.get("aliases"),
                "floor_id": entry.get("floor_id"),
                "labels": entry.get("labels"),
                "icon": entry.get("icon"),
            }, indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
