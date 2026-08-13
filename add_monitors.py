"""One-off utility: add HTTP and ping monitors to Uptime Kuma via socket.io.

Configure Uptime Kuma access with KUMA_HOST / KUMA_USERNAME / KUMA_PASSWORD.
Set MONITORS_CONFIG to a local JSON file (kept out of git) containing either a
JSON array for this script or an object with a "monitors" array.
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


def load_monitors() -> list[dict[str, object]]:
    if not MONITORS_CONFIG:
        return []

    config_path = Path(MONITORS_CONFIG)
    config_data = json.loads(config_path.read_text(encoding="utf-8"))

    if isinstance(config_data, list):
        return config_data
    if isinstance(config_data, dict):
        monitors = config_data.get("monitors", [])
        if isinstance(monitors, list):
            return monitors
    raise ValueError("MONITORS_CONFIG must contain a JSON array or a {'monitors': [...]} object")


async def main() -> None:
    monitors = load_monitors()
    if not monitors:
        print("No monitors configured. Populate MONITORS_CONFIG locally before running this script.")
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

    print("\nAdding monitors...\n")
    success: list[str] = []
    failed: list[tuple[str, str]] = []

    for monitor in monitors:
        data = {
            "name": monitor["name"],
            "type": monitor["type"],
            "interval": monitor.get("interval", 60),
            "retryInterval": 60,
            "maxretries": 3,
            "upsideDown": False,
            "active": True,
        }
        if monitor["type"] == "http":
            data["url"] = monitor["url"]
            data["method"] = monitor.get("method", "GET")
            data["ignoreTls"] = bool(monitor.get("ignoreTls", False))
            data["accepted_statuscodes"] = monitor.get("accepted_statuscodes", ["200-299"])
        elif monitor["type"] == "ping":
            data["hostname"] = monitor["hostname"]
            data["accepted_statuscodes"] = monitor.get("accepted_statuscodes", ["200-299"])

        try:
            res = await sio.call("add", data, timeout=15)
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
    print(f"Created: {len(success)}/{len(monitors)}")
    for name in success:
        print(f"  + {name}")
    if failed:
        print(f"Failed:  {len(failed)}")
        for name, err in failed:
            print(f"  - {name}: {err}")


asyncio.run(main())
