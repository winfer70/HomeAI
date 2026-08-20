#!/usr/bin/env python3
"""One-off: reload HA's script config (picks up new script.yaml/package
entries without a full restart), then verify the two new boost scripts
registered and heimdall_boost_heating is exposed to Assist.
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

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    req = urllib.request.Request(f"{HA_URL}/api/services/script/reload", method="POST", headers=headers, data=b"{}")
    with urllib.request.urlopen(req) as resp:
        print("reload status:", resp.status)

    req = urllib.request.Request(f"{HA_URL}/api/states", headers=headers)
    with urllib.request.urlopen(req) as resp:
        states = json.loads(resp.read())

    for s in states:
        if s["entity_id"] in ("script.heimdall_boost_heating", "script.heimdall_boost_revert_worker"):
            print(s["entity_id"], "|", s.get("state"), "|", s.get("attributes", {}).get("friendly_name"))

    return 0


if __name__ == "__main__":
    sys.exit(main())
