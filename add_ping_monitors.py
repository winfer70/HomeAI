"""One-off utility: add ICMP ping monitors to Uptime Kuma via socket.io.

Configure Uptime Kuma access with KUMA_HOST / KUMA_USERNAME / KUMA_PASSWORD.
Set MONITORS_CONFIG to a local JSON file (kept out of git) containing either a
JSON array for this script or an object with a "ping_monitors" array.
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


def load_ping_monitors() -> list[dict[str, object]]:
    if not MONITORS_CONFIG:
        return []

    config_path = Path(MONITORS_CONFIG)
    config_data = json.loads(config_path.read_text(encoding="utf-8"))

    if isinstance(config_data, list):
        return config_data
    if isinstance(config_data, dict):
        monitors = config_data.get("ping_monitors", [])
        if isinstance(monitors, list):
            return monitors
    raise ValueError("MONITORS_CONFIG must contain a JSON array or a {'ping_monitors': [...]} object")


async def main() -> None:
    ping_monitors = load_ping_monitors()
    if not ping_monitors:
        print("No ping monitors configured. Populate MONITORS_CONFIG locally before running this script.")
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
    if not result.get("ok"):
        print("Login failed:", result)
        await sio.disconnect()
        return
    print("Logged in.\n")

    success: list[str] = []
    failed: list[tuple[str, str]] = []

    for monitor in ping_monitors:
        data = {
            "name": monitor["name"],
            "type": monitor["type"],
            "hostname": monitor["hostname"],
            "interval": monitor.get("interval", 60),
            "retryInterval": 60,
            "maxretries": 3,
            "upsideDown": False,
            "active": True,
            "accepted_statuscodes": monitor.get("accepted_statuscodes", ["200-299"]),
        }

        try:
            res = await sio.call("add", data, timeout=15)
            print(f"  raw response: {res}")
            if res and res.get("ok"):
                print(f"  [OK]   {monitor['name']}  (id={res.get('id', '?')})")
                success.append(str(monitor["name"]))
            else:
                print(f"  [FAIL] {monitor['name']}  -> {res}")
                failed.append((str(monitor["name"]), str(res)))
        except Exception as exc:
            print(f"  [ERR]  {monitor['name']}  -> {exc}")
            failed.append((str(monitor["name"]), str(exc)))

    await sio.disconnect()

    print("\n=== Summary ===")
    print(f"Created: {len(success)}/{len(ping_monitors)}")
    for name in success:
        print(f"  + {name}")
    if failed:
        print(f"Failed:  {len(failed)}")
        for name, err in failed:
            print(f"  - {name}: {err}")


asyncio.run(main())
