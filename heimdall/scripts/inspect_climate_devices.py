#!/usr/bin/env python3
"""Read-only: dump full device_registry entries for all 8 climate devices,
to compare climate.0xa4c138b1ad7dfd57 (GrzejnikSypialniaGora, problem entity)
against its siblings (name_by_user, manufacturer, model, area_id, identifiers).
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

import websockets

HA_WS_URL = os.environ.get("HEIMDALL_HA_WS_URL", "ws://192.168.0.108:8123/api/websocket")

# entity_id -> device_id, from the earlier entity_registry dump
DEVICES = {
    "climate.0xa4c138b1ad7dfd57": "30a600d2625a3e4025d013f571440be4",  # PROBLEM
    "climate.0xa4c13842240065f9": "899dd62e0fee2dabeb3cb22c1806c8a4",
    "climate.0xa4c1387c4f428097": "61ef6a1bc463324ded9852fe0868b7af",
    "climate.0xa4c13881297bc097": "78bb8759167cb0ed0f9dd62d22113eaf",
    "climate.0xa4c138b90fef70c7": "b38639bbed3544d3f528d1cb4169c27d",
    "climate.0xa4c138c7970d8809": "34ec53417c71cfcd51ec1511637d2113",
    "climate.0xa4c138d920585e93": "d3e6f365bd3768bed19f10d0ca29ecc0",
    "climate.0x001e5e0902ce8e9a": "73342a65c2df0fc7947ad79b8b848483",
}


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

        await ws.send(json.dumps({"id": 2, "type": "config/device_registry/list"}))
        result = json.loads(await ws.recv())
        all_devices = {d["id"]: d for d in result.get("result", [])}

        for entity_id, device_id in DEVICES.items():
            entry = all_devices.get(device_id, {})
            marker = " <-- PROBLEM" if entity_id == "climate.0xa4c138b1ad7dfd57" else ""
            print(f"=== {entity_id} (device {device_id}){marker} ===")
            print(json.dumps({
                "name": entry.get("name"),
                "name_by_user": entry.get("name_by_user"),
                "manufacturer": entry.get("manufacturer"),
                "model": entry.get("model"),
                "model_id": entry.get("model_id"),
                "sw_version": entry.get("sw_version"),
                "hw_version": entry.get("hw_version"),
                "area_id": entry.get("area_id"),
                "identifiers": entry.get("identifiers"),
                "disabled_by": entry.get("disabled_by"),
                "labels": entry.get("labels"),
                "config_entries": entry.get("config_entries"),
            }, indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
