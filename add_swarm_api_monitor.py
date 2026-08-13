"""One-off utility: add an HTTP monitor for a swarm-api endpoint to Uptime Kuma.

Configure Uptime Kuma access with KUMA_HOST / KUMA_USERNAME / KUMA_PASSWORD.
Set MONITORS_CONFIG to a local JSON file (kept out of git) containing either a
monitor object for this script or an object with a "swarm_api_monitor" entry.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import socketio

sio = socketio.AsyncClient(logger=False, engineio_logger=False)

KUMA_HOST = os.environ.get("KUMA_HOST", "http://localhost:3001")
KUMA_USERNAME = os.environ.get("KUMA_USERNAME", "")
KUMA_PASSWORD = os.environ.get("KUMA_PASSWORD", "")
MONITORS_CONFIG = os.environ.get("MONITORS_CONFIG", "")


def load_monitor() -> dict[str, object]:
    if not MONITORS_CONFIG:
        return {}

    config_path = Path(MONITORS_CONFIG)
    config_data = json.loads(config_path.read_text(encoding="utf-8"))

    if isinstance(config_data, dict):
        monitor = config_data.get("swarm_api_monitor", config_data)
        if isinstance(monitor, dict) and {"name", "type", "url"}.issubset(monitor):
            return monitor
    raise ValueError(
        "MONITORS_CONFIG must contain a monitor object or a {'swarm_api_monitor': {...}} object"
    )


async def main() -> None:
    monitor = load_monitor()
    if not monitor:
        print("No swarm-api monitor configured. Populate MONITORS_CONFIG locally before running this script.")
        return
    if not KUMA_USERNAME or not KUMA_PASSWORD:
        print("Set KUMA_USERNAME and KUMA_PASSWORD before running this script.")
        return

    print(f"Connecting to Uptime Kuma at {KUMA_HOST} ...")
    await sio.connect(
        KUMA_HOST,
        socketio_path="/socket.io",
        transports=["websocket"],
    )
    print("Connected.")

    result = await sio.call(
        "login",
        {"username": KUMA_USERNAME, "password": KUMA_PASSWORD, "token": ""},
        timeout=15,
    )
    print(f"Login result: {result}")

    if not result.get("ok"):
        print("ERROR: Login failed:", result)
        await sio.disconnect()
        return

    print("\nAdding monitor...\n")

    data = {
        "name": monitor["name"],
        "type": monitor["type"],
        "url": monitor["url"],
        "method": monitor.get("method", "GET"),
        "interval": monitor.get("interval", 60),
        "retryInterval": 60,
        "maxretries": 3,
        "upsideDown": False,
        "active": True,
        "ignoreTls": bool(monitor.get("ignoreTls", False)),
        "accepted_statuscodes": monitor.get("accepted_statuscodes", ["200-299"]),
    }

    try:
        res = await sio.call("add", data, timeout=15)
        print(f"  raw response: {res}")
        if res and res.get("ok"):
            print(f"  [OK]   {monitor['name']}  (id={res.get('id', '?')})")
        else:
            print(f"  [FAIL] {monitor['name']}  -> {res}")
    except Exception as exc:
        print(f"  [ERR]  {monitor['name']}  -> {exc}")

    await sio.disconnect()


asyncio.run(main())
