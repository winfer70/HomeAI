#!/usr/bin/env python3
"""One-off: fix climate.0xa4c138b1ad7dfd57's broken name-matching.

Root cause (confirmed by reading HA's entity_registry.async_get_entity_aliases
and helpers/intent.py::_filter_by_name in the container source): HA's intent
name-matcher ONLY checks an entity's `aliases` list, never its registry `name`
field directly. Untouched entities default to a COMPUTED_NAME sentinel alias
(serializes as aliases: [null] over the WS API) that expands to their full
computed name - that's why every other radiator matches by name "for free".

The Task 5 alias experiment set this entity's aliases to ["Bedroom radiator"],
permanently overwriting that sentinel - so Polish voice commands never
matched (NAME failure). Setting aliases: [] (an earlier fix attempt) made it
worse: a real empty list yields ZERO matchable names at all.

Fix: explicitly alias it to its own name, so `_filter_by_name` matches it
directly regardless of the sentinel mechanism.

Usage:
    HEIMDALL_HA_TOKEN=<token> python clear_climate_alias.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

import websockets

HA_WS_URL = os.environ.get("HEIMDALL_HA_WS_URL", "ws://192.168.0.108:8123/api/websocket")
ENTITY_ID = "climate.0xa4c138b1ad7dfd57"


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

        await ws.send(json.dumps({
            "id": 2,
            "type": "config/entity_registry/update",
            "entity_id": ENTITY_ID,
            "aliases": ["GrzejnikSypialniaGóra"],
        }))
        result = json.loads(await ws.recv())
        if result.get("success"):
            entry = result["result"]["entity_entry"]
            print(f"OK: {ENTITY_ID} aliases now {entry.get('aliases')!r}, name={entry.get('name')!r}")
        else:
            print(f"ERROR: {result}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
