#!/usr/bin/env python3
"""Read-only: fetch HA's own conversation debug traces (Assist 'Debug' feature)
for the most recent qwen climate interaction, to see the EXACT tool call qwen
issued - ground truth instead of guessing. Does not trigger any new
conversation.process calls or touch any entity.

Usage:
    HEIMDALL_HA_TOKEN=<token> python inspect_conversation_traces.py
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

    async with websockets.connect(HA_WS_URL, max_size=20_000_000) as ws:
        auth_required = json.loads(await ws.recv())
        assert auth_required["type"] == "auth_required"
        await ws.send(json.dumps({"type": "auth", "access_token": token}))
        auth_result = json.loads(await ws.recv())
        if auth_result["type"] != "auth_ok":
            print(f"ERROR: auth failed: {auth_result}", file=sys.stderr)
            return 1

        # List recent conversation traces (read-only, does not trigger anything)
        await ws.send(json.dumps({"id": 2, "type": "conversation/trace/list"}))
        result = json.loads(await ws.recv())
        if not result.get("success"):
            print(f"ERROR: conversation/trace/list failed: {result}", file=sys.stderr)
            return 1

        traces = result["result"]
        print(f"Found {len(traces)} recent traces")
        qwen_climate_traces = [
            t for t in traces
            if "qwen" in t.get("agent_id", "").lower() or "heimdall_local" in t.get("agent_id", "").lower()
        ]
        print(f"qwen-agent traces: {len(qwen_climate_traces)}")

        for t in traces[-15:]:
            print(f"  item_id={t.get('item_id')} agent_id={t.get('agent_id')} text={t.get('text', t.get('input'))!r}")

        # Fetch full detail for the most recent qwen trace, if any
        if qwen_climate_traces:
            latest = qwen_climate_traces[-1]
            await ws.send(json.dumps({
                "id": 3,
                "type": "conversation/trace/get",
                "item_id": latest["item_id"],
            }))
            detail = json.loads(await ws.recv())
            print("\n--- FULL TRACE DETAIL (latest qwen trace) ---")
            print(json.dumps(detail, indent=2)[:8000])

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
