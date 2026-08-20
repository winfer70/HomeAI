#!/usr/bin/env python3
"""One-off: expose script.heimdall_boost_heating to Assist (should_expose)
so it becomes an LLM tool for both conversation agents. Deliberately does
NOT expose script.heimdall_boost_revert_worker - that one is an internal
implementation detail, not a voice command.
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
            "entity_id": "script.heimdall_boost_heating",
            "options_domain": "conversation",
            "options": {"should_expose": True},
        }))
        result = json.loads(await ws.recv())
        if result.get("success"):
            entry = result["result"]["entity_entry"]
            exposed = (entry.get("options") or {}).get("conversation", {}).get("should_expose")
            print(f"OK: script.heimdall_boost_heating should_expose={exposed}")
        else:
            print(f"ERROR: {result}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
