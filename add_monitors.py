"""One-off utility: add HTTP and ping monitors to Uptime Kuma via socket.io.

Connects to Uptime Kuma at 10.0.0.101:3001 (REDACTED-HOST — REDACTED-HOST decommissioned),
authenticates, and registers monitors for all homelab infrastructure nodes.
Run manually; not imported by any module.
"""

import asyncio
import socketio

sio = socketio.AsyncClient(logger=False, engineio_logger=False)

monitors = [
    {"type": "http", "name": "REDACTED-HOST nginx", "url": "http://10.0.0.107", "interval": 60},
    {"type": "http", "name": "n8n", "url": "http://10.0.0.107:5678", "interval": 60},
    {"type": "http", "name": "ai-agent dashboard", "url": "https://dashboard.kamilon8n.win", "interval": 60},
    {"type": "http", "name": "REDACTED-HOST Ollama", "url": "http://10.0.0.101:11434", "interval": 60},
    {"type": "http", "name": "ProjectNemo HA", "url": "http://10.0.0.104:8123", "interval": 60},
    {"type": "http", "name": "Grafana", "url": "http://10.0.0.111:3000", "interval": 60},
    {"type": "http", "name": "Prometheus", "url": "http://10.0.0.111:9090", "interval": 60},
    {"type": "http", "name": "swarm-api", "url": "http://10.0.0.104:8010/health", "interval": 60},
    {"type": "ping", "name": "ping REDACTED-HOST", "hostname": "10.0.0.107", "interval": 60},
    {"type": "ping", "name": "ping REDACTED-HOST", "hostname": "10.0.0.101", "interval": 60},
    {"type": "ping", "name": "ping REDACTED-HOST", "hostname": "10.0.0.104", "interval": 60},
    {"type": "ping", "name": "ping REDACTED-HOST", "hostname": "10.0.0.111", "interval": 60},
]

KUMA_HOST = "http://10.0.0.101:3001"  # REDACTED-HOST (REDACTED-HOST decommissioned)

async def main():
    print(f"Connecting to Uptime Kuma at {KUMA_HOST} ...")
    await sio.connect(
        KUMA_HOST,
        socketio_path="/socket.io",
        transports=["websocket"],
    )
    print("Connected.")

    # Login
    result = await sio.call("login", {"username": "kamilo", "password": "REDACTED_PASSWORD", "token": ""}, timeout=15)
    print(f"Login result: {result}")

    if not result.get("ok"):
        print("ERROR: Login failed:", result)
        await sio.disconnect()
        return

    print("\nAdding monitors...\n")
    success = []
    failed = []

    for m in monitors:
        data = {
            "name": m["name"],
            "type": m["type"],
            "interval": m["interval"],
            "retryInterval": 60,
            "maxretries": 3,
            "upsideDown": False,
            "active": True,
        }
        if m["type"] == "http":
            data["url"] = m["url"]
            data["method"] = "GET"
            data["ignoreTls"] = False
            data["accepted_statuscodes"] = ["200-299"]
        elif m["type"] == "ping":
            data["hostname"] = m["hostname"]
            data["accepted_statuscodes"] = ["200-299"]

        try:
            res = await sio.call("add", data, timeout=15)
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
    print(f"Created: {len(success)}/{len(monitors)}")
    for name in success:
        print(f"  + {name}")
    if failed:
        print(f"Failed:  {len(failed)}")
        for name, err in failed:
            print(f"  - {name}: {err}")

asyncio.run(main())
