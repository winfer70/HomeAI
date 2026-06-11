"""One-off utility: add ICMP ping monitors to Uptime Kuma via socket.io.

Connects to Uptime Kuma at 10.0.0.102:3001 and registers ping monitors for all
homelab infrastructure nodes. Run manually; not imported by any module.
"""

import asyncio
import socketio

sio = socketio.AsyncClient(logger=False, engineio_logger=False)

ping_monitors = [
    {"type": "ping", "name": "ping REDACTED-HOST", "hostname": "10.0.0.107", "interval": 60},
    {"type": "ping", "name": "ping REDACTED-HOST", "hostname": "10.0.0.101", "interval": 60},
    {"type": "ping", "name": "ping REDACTED-HOST", "hostname": "10.0.0.104", "interval": 60},
    {"type": "ping", "name": "ping REDACTED-HOST", "hostname": "10.0.0.102", "interval": 60},
    {"type": "ping", "name": "ping REDACTED-HOST", "hostname": "10.0.0.111", "interval": 60},
]

async def main():
    print("Connecting to Uptime Kuma at http://10.0.0.102:3001 ...")
    await sio.connect(
        "http://10.0.0.102:3001",
        socketio_path="/socket.io",
        transports=["websocket"],
    )
    print("Connected.")

    result = await sio.call("login", {"username": "kamilo", "password": "REDACTED_PASSWORD", "token": ""}, timeout=15)
    if not result.get("ok"):
        print("Login failed:", result)
        await sio.disconnect()
        return
    print("Logged in.\n")

    success = []
    failed = []

    for m in ping_monitors:
        # Include accepted_statuscodes so the server's .every() validation doesn't crash
        data = {
            "name": m["name"],
            "type": m["type"],
            "hostname": m["hostname"],
            "interval": m["interval"],
            "retryInterval": 60,
            "maxretries": 3,
            "upsideDown": False,
            "active": True,
            "accepted_statuscodes": ["200-299"],
        }

        try:
            res = await sio.call("add", data, timeout=15)
            print(f"  raw response: {res}")
            if res and res.get("ok"):
                print(f"  [OK]   {m['name']}  (id={res.get('id', '?')})")
                success.append(m["name"])
            else:
                print(f"  [FAIL] {m['name']}  -> {res}")
                failed.append((m["name"], str(res)))
        except Exception as e:
            print(f"  [ERR]  {m['name']}  -> {e}")
            failed.append((m["name"], str(e)))

    await sio.disconnect()

    print(f"\n=== Summary ===")
    print(f"Created: {len(success)}/{len(ping_monitors)}")
    for name in success:
        print(f"  + {name}")
    if failed:
        print(f"Failed:  {len(failed)}")
        for name, err in failed:
            print(f"  - {name}: {err}")

asyncio.run(main())
