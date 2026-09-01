#!/usr/bin/env python3
"""Read/write: enable debug logging for the ollama + llm helper components,
fire a conversation.process call at the qwen agent for 'what's in the
office', then let the caller grep the container logs for the raw tool
result the model actually received. Reverts logger level at the end.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

import websockets

HA_WS_URL = os.environ.get("HEIMDALL_HA_WS_URL", "ws://192.168.0.108:8123/api/websocket")
QWEN_AGENT_ID = "conversation.heimdall_local_qwen2_5"


async def call(ws, msg_id, msg):
    msg["id"] = msg_id
    await ws.send(json.dumps(msg))
    while True:
        resp = json.loads(await ws.recv())
        if resp.get("id") == msg_id:
            return resp


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
            print("AUTH FAILED", auth_result, file=sys.stderr)
            return 1

        mid = 1

        print("Setting debug logging on ollama + llm + conversation...")
        resp = await call(ws, mid, {
            "type": "call_service",
            "domain": "logger",
            "service": "set_level",
            "service_data": {
                "homeassistant.components.ollama": "debug",
                "homeassistant.helpers.llm": "debug",
                "homeassistant.components.conversation": "debug",
            },
        })
        print("logger.set_level:", resp.get("success"))
        mid += 1

        print("Calling conversation.process for the office query...")
        resp = await call(ws, mid, {
            "type": "call_service",
            "domain": "conversation",
            "service": "process",
            "service_data": {
                "text": "co jest w biurze",
                "agent_id": QWEN_AGENT_ID,
            },
            "return_response": True,
        })
        print("conversation.process result:")
        print(json.dumps(resp.get("result"), indent=2, ensure_ascii=False))
        mid += 1

        print("Reverting logger levels to info...")
        resp = await call(ws, mid, {
            "type": "call_service",
            "domain": "logger",
            "service": "set_level",
            "service_data": {
                "homeassistant.components.ollama": "info",
                "homeassistant.helpers.llm": "info",
                "homeassistant.components.conversation": "info",
            },
        })
        print("logger.set_level (revert):", resp.get("success"))

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
