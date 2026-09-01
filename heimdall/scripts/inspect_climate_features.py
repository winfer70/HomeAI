#!/usr/bin/env python3
"""Read-only: fetch live states for all 8 climate entities via REST API,
comparing 'state' (hvac_mode) and 'supported_features' bitmask - to check
if the problem entity's TARGET_TEMPERATURE feature bit (value 1) drops out
when it's 'off', which would explain MatchFailedReason.NAME/states=[] for
SetTemperature while GetTemperature (no feature requirement) still works.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request

HA_URL = os.environ.get("HEIMDALL_HA_URL", "http://192.168.0.108:8123")

ENTITIES = [
    "climate.0xa4c138b1ad7dfd57",  # PROBLEM
    "climate.0xa4c13842240065f9",
    "climate.0xa4c1387c4f428097",
    "climate.0xa4c13881297bc097",
    "climate.0xa4c138b90fef70c7",
    "climate.0xa4c138c7970d8809",
    "climate.0xa4c138d920585e93",
    "climate.0x001e5e0902ce8e9a",
]

TARGET_TEMPERATURE_BIT = 1


def main() -> int:
    token = os.environ.get("HEIMDALL_HA_TOKEN")
    if not token:
        print("ERROR: set HEIMDALL_HA_TOKEN", file=sys.stderr)
        return 1

    for entity_id in ENTITIES:
        req = urllib.request.Request(
            f"{HA_URL}/api/states/{entity_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())

        supported = data.get("attributes", {}).get("supported_features")
        has_target_temp = bool(supported is not None and (supported & TARGET_TEMPERATURE_BIT))
        marker = " <-- PROBLEM" if entity_id == "climate.0xa4c138b1ad7dfd57" else ""
        print(f"{entity_id}{marker}: state={data.get('state')!r} "
              f"supported_features={supported} (binary={bin(supported) if supported is not None else None}) "
              f"has_TARGET_TEMPERATURE={has_target_temp} "
              f"hvac_action={data.get('attributes', {}).get('hvac_action')!r}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
