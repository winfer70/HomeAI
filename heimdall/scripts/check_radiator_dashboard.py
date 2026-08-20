#!/usr/bin/env python3
"""Read-only: verify the radiator dashboard fix + additions are live."""
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
        await ws.send(json.dumps({"id": 2, "type": "lovelace/config", "url_path": "dashboard-biuro"}))
        result = json.loads(await ws.recv())
        content = json.dumps(result, ensure_ascii=False)

        checks = {
            "Termostat Salon (new)": "Termostat Salon" in content,
            "Termostat Gościnny (new)": "Termostat Gościnny" in content,
            "Termostat Sypialnia Dół (new)": "Termostat Sypialnia Dół" in content,
            "climate.0xa4c138b90fef70c7 (Salon entity)": "climate.0xa4c138b90fef70c7" in content,
            "climate.0xa4c13842240065f9 (Gościnny entity)": "climate.0xa4c13842240065f9" in content,
            "climate.0xa4c138d920585e93 (Sypialnia Dół entity)": "climate.0xa4c138d920585e93" in content,
            "Malformed nested tile GONE (should be False)": '"type": "tile",\\n                          "entity": "sensor.0xa4c138b1ad7dfd57_error_status"' in content,
        }
        for label, ok in checks.items():
            print(f"{label}: {ok}")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
