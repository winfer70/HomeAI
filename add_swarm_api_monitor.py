"""One-off utility: add HTTP monitor for swarm-api to Uptime Kuma on REDACTED-HOST.

Connects to Uptime Kuma at 10.0.0.102:3001 (REDACTED-HOST), authenticates via
socket.io, and registers an HTTP monitor for the swarm-api health endpoint.
Run manually; not imported by any module.
"""

import asyncio
import socketio

sio = socketio.AsyncClient(logger=False, engineio_logger=False)

KUMA_HOST = "http://10.0.0.101:3001"  # REDACTED-HOST (REDACTED-HOST decommissioned)

monitor = {
    "name": "swarm-api",
    "type": "http",
    "url": "http://10.0.0.103:8010/health",
    "interval": 60,
}


async def main():
    print(f"Connecting to Uptime Kuma at {KUMA_HOST} ...")
    await sio.connect(
        KUMA_HOST,
        socketio_path="/socket.io",
        transports=["websocket"],
    )
    print("Connected.")

    result = await sio.call(
        "login",
        {"username": "kamilo", "password": "REDACTED_PASSWORD", "token": ""},
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
        "method": "GET",
        "interval": monitor["interval"],
        "retryInterval": 60,
        "maxretries": 3,
        "upsideDown": False,
        "active": True,
        "ignoreTls": False,
        "accepted_statuscodes": ["200-299"],
    }

    try:
        res = await sio.call("add", data, timeout=15)
        print(f"  raw response: {res}")
        if res and res.get("ok"):
            print(f"  [OK]   {monitor['name']}  (id={res.get('id', '?')})")
        else:
            print(f"  [FAIL] {monitor['name']}  -> {res}")
    except Exception as e:
        print(f"  [ERR]  {monitor['name']}  -> {e}")

    await sio.disconnect()


asyncio.run(main())
