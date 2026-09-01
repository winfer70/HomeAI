#!/usr/bin/env python3
"""Read-only: list assist_satellite entities and any wake-word-related
binary_sensors/switches, to find the voice hardware trigger mechanism and
whether wake-word/VAD sensitivity is configurable there.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request

HA_URL = os.environ.get("HEIMDALL_HA_URL", "http://192.168.0.108:8123")


def main() -> int:
    token = os.environ.get("HEIMDALL_HA_TOKEN")
    if not token:
        print("ERROR: set HEIMDALL_HA_TOKEN", file=sys.stderr)
        return 1

    req = urllib.request.Request(
        f"{HA_URL}/api/states",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req) as resp:
        states = json.loads(resp.read())

    for s in states:
        entity_id = s["entity_id"]
        domain = entity_id.split(".", 1)[0]
        if domain == "assist_satellite" or "wake" in entity_id.lower():
            print(entity_id, "|", s.get("state"), "|", json.dumps(s.get("attributes", {}), ensure_ascii=False))

    return 0


if __name__ == "__main__":
    sys.exit(main())
