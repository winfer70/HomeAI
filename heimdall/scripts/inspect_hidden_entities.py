#!/usr/bin/env python3
"""Read-only: for NOT-exposed and disabled/hidden entities, print entity_id +
friendly_name for all 'actionable' domains (skip noisy diagnostic domains:
sensor, binary_sensor, select, update, button, number - just counted, not
listed) so we can see what real controllable things are invisible to Assist.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from collections import defaultdict

import websockets

HA_WS_URL = os.environ.get("HEIMDALL_HA_WS_URL", "ws://192.168.0.108:8123/api/websocket")

NOISY_DOMAINS = {"sensor", "binary_sensor", "select", "update", "button", "number", "automation"}


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

        await ws.send(json.dumps({"id": 3, "type": "get_states"}))
        states_result = json.loads(await ws.recv())
        friendly_names = {
            s["entity_id"]: s.get("attributes", {}).get("friendly_name", "")
            for s in states_result.get("result", [])
        }

    not_exposed: dict[str, list[str]] = defaultdict(list)
    disabled: dict[str, list[str]] = defaultdict(list)
    noisy_not_exposed = defaultdict(int)
    noisy_disabled = defaultdict(int)

    for entry in entries:
        entity_id = entry["entity_id"]
        domain = entity_id.split(".", 1)[0]
        name = entry.get("name") or entry.get("original_name") or friendly_names.get(entity_id, "")

        if entry.get("disabled_by") or entry.get("hidden_by"):
            if domain in NOISY_DOMAINS:
                noisy_disabled[domain] += 1
            else:
                disabled[domain].append(f"{entity_id} ({name})")
            continue

        should_expose = (entry.get("options") or {}).get("conversation", {}).get("should_expose")
        if not should_expose:
            if domain in NOISY_DOMAINS:
                noisy_not_exposed[domain] += 1
            else:
                not_exposed[domain].append(f"{entity_id} ({name})")

    print("=== NOT EXPOSED to Assist - actionable domains ===")
    for domain in sorted(not_exposed):
        ids = sorted(not_exposed[domain])
        print(f"  {domain} ({len(ids)}):")
        for line in ids:
            print(f"    - {line}")
    print("\n  (noisy/diagnostic domains, count only):")
    for domain in sorted(noisy_not_exposed):
        print(f"    {domain}: {noisy_not_exposed[domain]}")

    print("\n=== DISABLED/HIDDEN entirely - actionable domains ===")
    for domain in sorted(disabled):
        ids = sorted(disabled[domain])
        print(f"  {domain} ({len(ids)}):")
        for line in ids:
            print(f"    - {line}")
    print("\n  (noisy/diagnostic domains, count only):")
    for domain in sorted(noisy_disabled):
        print(f"    {domain}: {noisy_disabled[domain]}")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
