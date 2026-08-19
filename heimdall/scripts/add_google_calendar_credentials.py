"""Heimdall Task 5 (M4) — add Google Calendar OAuth Application Credentials to HA.

HA has no REST endpoint for Application Credentials (UI/frontend uses the
websocket API only), so this script speaks the websocket protocol directly:
authenticates with a long-lived token, then calls
`application_credentials/create`.

This only registers the OAuth *client* (client_id/client_secret) with HA -
it does NOT complete the OAuth consent flow. That final step (choosing the
Google account, granting calendar access) requires an interactive browser
session under the user's own Google login and cannot be scripted; do it
via Settings > Devices & Services > Add Integration > Google Calendar in
the HA UI after running this script.

Usage:
    python add_google_calendar_credentials.py <client_id> <client_secret>

Reads the HA URL and long-lived access token from environment variables
HEIMDALL_HA_URL (default http://192.168.0.108:8123) and
HEIMDALL_HA_TOKEN (required).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

import websockets


async def add_credentials(ha_url: str, token: str, client_id: str, client_secret: str) -> None:
    ws_url = ha_url.replace("http://", "ws://").replace("https://", "wss://") + "/api/websocket"
    async with websockets.connect(ws_url) as ws:
        # Handshake: server sends auth_required, we send auth, expect auth_ok.
        hello = json.loads(await ws.recv())
        if hello.get("type") != "auth_required":
            raise RuntimeError(f"Unexpected handshake message: {hello}")

        await ws.send(json.dumps({"type": "auth", "access_token": token}))
        auth_resp = json.loads(await ws.recv())
        if auth_resp.get("type") != "auth_ok":
            raise RuntimeError(f"Authentication failed: {auth_resp}")

        msg_id = 1
        await ws.send(
            json.dumps(
                {
                    "id": msg_id,
                    "type": "application_credentials/create",
                    "domain": "google",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "name": "Heimdall Calendar",
                }
            )
        )
        result = json.loads(await ws.recv())
        if not result.get("success"):
            error = result.get("error", {})
            code = error.get("code", "")
            if code == "already_exists" or "already" in str(error.get("message", "")).lower():
                print("Application credential for domain 'google' already exists - skipping.")
                return
            raise RuntimeError(f"application_credentials/create failed: {result}")

        print("Application credential added:", json.dumps(result.get("result"), indent=2))
        print()
        print("Next: in the HA UI, go to Settings > Devices & Services > Add")
        print("Integration > 'Google Calendar', pick this application credential,")
        print("and complete the Google consent flow in your browser.")


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2

    client_id, client_secret = sys.argv[1], sys.argv[2]
    ha_url = os.environ.get("HEIMDALL_HA_URL", "http://192.168.0.108:8123")
    token = os.environ.get("HEIMDALL_HA_TOKEN")
    if not token:
        print("ERROR: HEIMDALL_HA_TOKEN environment variable is required.", file=sys.stderr)
        return 2

    asyncio.run(add_credentials(ha_url, token, client_id, client_secret))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
