#!/usr/bin/env python3
"""Read-only: find every entity that HA would consider "in the office" - i.e.
matches area_id "office" either directly on the entity, or inherited from its
device - to check why Syrena+Swiatlo (alarm siren, house-wide) is wrongly
included and why the Meross surge-protector USB switches are missing.

Also separately looks up Syrena+Swiatlo and any Meross-branded device to see
their ACTUAL area assignment, wherever it is.
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
        await ws.recv()
        await ws.send(json.dumps({"type": "auth", "access_token": token}))
        await ws.recv()

        async def cmd(msg_id, payload):
            payload["id"] = msg_id
            await ws.send(json.dumps(payload))
            return json.loads(await ws.recv())["result"]

        areas = await cmd(2, {"type": "config/area_registry/list"})
        devices = await cmd(3, {"type": "config/device_registry/list"})
        entities = await cmd(4, {"type": "config/entity_registry/list"})
        states_result = await cmd(5, {"type": "get_states"})
        friendly_names = {s["entity_id"]: s.get("attributes", {}).get("friendly_name", "") for s in states_result}

        office_area_ids = {a["area_id"] for a in areas if a["area_id"] == "office" or a.get("name") in ("Biuro",)}
        print(f"Office-matching area_id(s): {office_area_ids}")
        device_area = {d["id"]: d.get("area_id") for d in devices}
        device_name = {d["id"]: (d.get("name_by_user") or d.get("name")) for d in devices}

        print("\n=== Entities whose EFFECTIVE area is 'office' ===")
        for e in entities:
            if e.get("disabled_by") or e.get("hidden_by"):
                continue
            eff_area = e.get("area_id") or device_area.get(e.get("device_id"))
            if eff_area in office_area_ids:
                name = e.get("name") or friendly_names.get(e["entity_id"], "")
                print(f"  {e['entity_id']} | name={name!r} | entity.area_id={e.get('area_id')} | device_area={device_area.get(e.get('device_id'))} | device={device_name.get(e.get('device_id'))!r}")

        print("\n=== Syrena / Swiatlo entities - actual area, wherever it is ===")
        for e in entities:
            name = (e.get("name") or friendly_names.get(e["entity_id"], "") or "")
            if "syrena" in e["entity_id"].lower() or "syrena" in name.lower():
                eff_area = e.get("area_id") or device_area.get(e.get("device_id"))
                area_name = next((a.get("name") for a in areas if a["area_id"] == eff_area), None)
                print(f"  {e['entity_id']} | name={name!r} | entity.area_id={e.get('area_id')} | device_area={device_area.get(e.get('device_id'))} ({area_name}) | device={device_name.get(e.get('device_id'))!r}")

        print("\n=== Meross-branded devices/entities ===")
        for d in devices:
            if "meross" in (d.get("manufacturer") or "").lower():
                print(f"  device={d.get('name_by_user') or d.get('name')!r} | id={d['id']} | area_id={d.get('area_id')} | manufacturer={d.get('manufacturer')} | model={d.get('model')}")
        for e in entities:
            name = (e.get("name") or friendly_names.get(e["entity_id"], "") or "")
            if "meross" in e["entity_id"].lower() or "meross" in name.lower() or "surge" in name.lower():
                eff_area = e.get("area_id") or device_area.get(e.get("device_id"))
                print(f"  entity={e['entity_id']} | name={name!r} | entity.area_id={e.get('area_id')} | device_area={eff_area}")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
