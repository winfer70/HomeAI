#!/usr/bin/env python3
"""Read-only benchmark: fetch real state for the known office entities, build
a GetLiveContext-style text blob, then ask 2-3 candidate local models
(qwen2.5:7b baseline, qwen3:14b, gemma4) to list everything in the office
from that context - no HA tool-calling involved, pure completion quality
comparison to see if a bigger local model handles multi-domain lists better.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

import requests
import websockets

HA_WS_URL = os.environ.get("HEIMDALL_HA_WS_URL", "ws://192.168.0.108:8123/api/websocket")
OLLAMA_URL = "http://192.168.0.125:11434/api/chat"

OFFICE_ENTITIES = [
    "binary_sensor.0xf044d3fffe087b1f_contact",
    "binary_sensor.0xf044d3fffe087b54_contact",
    "climate.0xa4c138c7970d8809",
    "fan.office_light",
    "light.office_light",
    "sensor.0xa4c138c7970d8809_local_temperature",
    "switch.0x54ef4410016759d1_up",
    "switch.office_led",
    "switch.smart_switch_20111713503031290d1748e1e93cb12d_outlet",
    "switch.smart_switch_20111713503031290d1748e1e93cb12d_outlet_1",
    "switch.smart_switch_20111713503031290d1748e1e93cb12d_outlet_2",
    "switch.smart_switch_20111713503031290d1748e1e93cb12d_outlet_3",
    "switch.smart_switch_20111713503031290d1748e1e93cb12d_outlet_4",
    "switch.smart_switch_20111713503031290d1748e1e93cb12d_outlet_5",
]

MODELS = ["qwen2.5:7b-instruct", "qwen3:14b", "gemma4:latest"]

PROMPT = (
    "Below is a list of Home Assistant device states in the office (\"Biuro\"). "
    "List EVERY single one of them in your answer, in Polish, grouped or not - "
    "just make sure none are missing, regardless of domain (switch, climate, "
    "sensor, binary_sensor, fan, light).\n\n{context}\n\nQuestion: co jest w biurze?"
)


async def fetch_states() -> dict[str, dict]:
    token = os.environ.get("HEIMDALL_HA_TOKEN")
    if not token:
        print("ERROR: set HEIMDALL_HA_TOKEN", file=sys.stderr)
        sys.exit(1)
    async with websockets.connect(HA_WS_URL, max_size=10_000_000) as ws:
        auth_required = json.loads(await ws.recv())
        assert auth_required["type"] == "auth_required"
        await ws.send(json.dumps({"type": "auth", "access_token": token}))
        auth_result = json.loads(await ws.recv())
        assert auth_result["type"] == "auth_ok", auth_result

        await ws.send(json.dumps({"id": 1, "type": "get_states"}))
        while True:
            resp = json.loads(await ws.recv())
            if resp.get("id") == 1:
                states = {s["entity_id"]: s for s in resp["result"]}
                return {eid: states[eid] for eid in OFFICE_ENTITIES if eid in states}


def build_context(states: dict[str, dict]) -> str:
    lines = []
    for eid, s in states.items():
        name = s["attributes"].get("friendly_name", eid)
        lines.append(f"- {eid} ({name}): state={s['state']}")
    return "\n".join(lines)


def ask_model(model: str, context: str) -> str:
    resp = requests.post(
        OLLAMA_URL,
        json={
            "model": model,
            "messages": [{"role": "user", "content": PROMPT.format(context=context)}],
            "stream": False,
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def main() -> int:
    states = asyncio.run(fetch_states())
    print(f"Fetched {len(states)}/{len(OFFICE_ENTITIES)} entities.\n")
    context = build_context(states)
    print("=== CONTEXT SENT TO MODELS ===")
    print(context)
    print()

    for model in MODELS:
        print(f"=== {model} ===")
        try:
            answer = ask_model(model, context)
            print(answer)
        except Exception as exc:
            print(f"ERROR calling {model}: {exc}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
