#!/usr/bin/env python3
"""Read-only: list all entities and their conversation exposure status.

HA has no per-agent exposure - qwen and Gemini both use the same "conversation"
assistant category (see homeassistant.components.homeassistant.exposed_entities).
The only qwen-specific restriction is the heimdall_restricted LLM API's tool
blocklist (currently just heimdall_create_calendar_event), not an entity-level
difference. This script reports the shared exposed/not-exposed entity set.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from collections import defaultdict

import websockets

HA_WS_URL = os.environ.get("HEIMDALL_HA_WS_URL", "ws://192.168.0.108:8123/api/websocket")


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

        await ws.send(json.dumps({"id": 2, "type": "config/entity_registry/list"}))
        result = json.loads(await ws.recv())
        entries = result.get("result", [])

    exposed: dict[str, list[str]] = defaultdict(list)
    hidden: dict[str, list[str]] = defaultdict(list)
    excluded: dict[str, list[str]] = defaultdict(list)  # disabled/hidden_by

    for entry in entries:
        entity_id = entry["entity_id"]
        domain = entity_id.split(".", 1)[0]

        if entry.get("disabled_by") or entry.get("hidden_by"):
            excluded[domain].append(entity_id)
            continue

        should_expose = (entry.get("options") or {}).get("conversation", {}).get("should_expose")
        if should_expose:
            exposed[domain].append(entity_id)
        else:
            hidden[domain].append(entity_id)

    total_exposed = sum(len(v) for v in exposed.values())
    total_hidden = sum(len(v) for v in hidden.values())
    total_excluded = sum(len(v) for v in excluded.values())

    print(f"=== EXPOSED to Assist (both qwen + Gemini) - {total_exposed} entities ===")
    for domain in sorted(exposed):
        ids = sorted(exposed[domain])
        print(f"  {domain} ({len(ids)}):")
        for eid in ids:
            print(f"    - {eid}")

    print(f"\n=== NOT exposed (should_expose=false) - {total_hidden} entities ===")
    for domain in sorted(hidden):
        print(f"  {domain}: {len(hidden[domain])}")

    print(f"\n=== Disabled/hidden_by (excluded entirely) - {total_excluded} entities ===")
    for domain in sorted(excluded):
        print(f"  {domain}: {len(excluded[domain])}")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
