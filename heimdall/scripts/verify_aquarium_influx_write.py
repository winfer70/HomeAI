#!/usr/bin/env python3
"""Assert that an aquarium switch toggle (Task 4 / M3) lands in InfluxDB.

The original brief's acceptance criteria for Task 4 explicitly says: "Confirm
setpoint writes made through this path still land in InfluxDB the same way
manual changes do — add an assertion/test for this, not just a manual
spot-check." This script is that assertion.

What it actually does: toggles a switch off then on via HA's REST API, waits
for the associated power-consumption sensor to report a value drop (near
zero) followed by recovery, then queries InfluxDB directly (Flux, HTTP API -
no SSH dependency) to confirm both points landed in the `aquarium` bucket.

IMPORTANT — a real limitation this script deliberately surfaces rather than
hides (found during Task 4's investigation, documented in
heimdall/PROJECTNEMO_API.md and heimdall/HA_CONFIG_CHANGES.md):

  vesemir's `influxdb:` config only lists 8 specific *sensor* entities under
  `include.entities` — it does NOT include the switch entities themselves
  (`switch.grzalka`, `switch.filtr`, `switch.pompka`). So a switch's own
  on/off state change is NEVER written to InfluxDB directly. The only signal
  that shows up is the switch's associated power-consumption sensor, and
  ONLY if the toggle produces an observable change in that sensor's value.

  For `switch.filtr` and `switch.pompka` (steady non-zero draw whenever on),
  this works reliably - confirmed live 2026-08-19: toggling filtr off/on
  produced a 12.x W -> 0 W -> 12.x W pattern in InfluxDB within ~20 seconds.

  For `switch.grzalka` (a heater with its own internal thermostat), this is
  NOT reliable - if the thermostat isn't actively calling for heat when you
  toggle the switch, current draw is already 0 W both before and after, so
  no new InfluxDB point is produced at all. This script defaults to
  `switch.filtr` for exactly this reason. Do not assume grzalka toggles are
  observable in Influx without checking its consumption sensor's current
  value first.

Usage:
    HEIMDALL_HA_TOKEN=<long-lived token> python verify_aquarium_influx_write.py \\
        [--switch switch.filtr] [--sensor sensor.filtr_current_consumption] \\
        [--influx-token <token>]

Exits non-zero (with a clear message) if the expected drop-then-recover
pattern is not found in InfluxDB within the timeout.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import requests

DEFAULT_HA_URL = "http://192.168.0.108:8123"
DEFAULT_INFLUX_URL = "http://192.168.0.108:8086"
DEFAULT_INFLUX_ORG = "nemo"
DEFAULT_INFLUX_BUCKET = "aquarium"

# switch.filtr is the default target: steady non-zero draw whenever on, so a
# toggle reliably produces an observable InfluxDB change (unlike grzalka's
# thermostat-gated heater load - see module docstring).
DEFAULT_SWITCH = "switch.filtr"
DEFAULT_SENSOR = "filtr_current_consumption"  # InfluxDB entity_id tag (no "sensor." prefix)

OFF_WAIT_SECONDS = 20  # give the Zigbee power sensor time to report a real drop
POLL_INTERVAL_SECONDS = 5
POLL_TIMEOUT_SECONDS = 60


def call_ha_service(ha_url: str, token: str, domain: str, service: str, entity_id: str) -> None:
    resp = requests.post(
        f"{ha_url}/api/services/{domain}/{service}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"entity_id": entity_id},
        timeout=10,
    )
    resp.raise_for_status()


def query_influx_recent_points(
    influx_url: str, influx_token: str, org: str, bucket: str, entity_id: str, minutes: int = 5
) -> list[dict]:
    flux = f"""
from(bucket: "{bucket}")
  |> range(start: -{minutes}m)
  |> filter(fn: (r) => r._measurement == "W")
  |> filter(fn: (r) => r._field == "value")
  |> filter(fn: (r) => r.entity_id == "{entity_id}")
  |> sort(columns: ["_time"])
"""
    resp = requests.post(
        f"{influx_url}/api/v2/query",
        params={"org": org},
        headers={"Authorization": f"Token {influx_token}", "Content-Type": "application/vnd.flux"},
        data=flux.encode("utf-8"),
        timeout=15,
    )
    resp.raise_for_status()

    points = []
    lines = resp.text.strip().splitlines()
    if len(lines) < 2:
        return points
    header = lines[0].split(",")
    time_idx = header.index("_time")
    value_idx = header.index("_value")
    for line in lines[1:]:
        if not line.strip():
            continue
        fields = line.split(",")
        points.append({"time": fields[time_idx], "value": float(fields[value_idx])})
    return points


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--switch", default=DEFAULT_SWITCH)
    parser.add_argument("--sensor", default=DEFAULT_SENSOR, help="InfluxDB entity_id tag, no 'sensor.' prefix")
    parser.add_argument("--ha-url", default=os.environ.get("HEIMDALL_HA_URL", DEFAULT_HA_URL))
    parser.add_argument("--influx-url", default=os.environ.get("HEIMDALL_INFLUX_URL", DEFAULT_INFLUX_URL))
    parser.add_argument("--influx-org", default=os.environ.get("HEIMDALL_INFLUX_ORG", DEFAULT_INFLUX_ORG))
    parser.add_argument("--influx-bucket", default=os.environ.get("HEIMDALL_INFLUX_BUCKET", DEFAULT_INFLUX_BUCKET))
    args = parser.parse_args()

    ha_token = os.environ.get("HEIMDALL_HA_TOKEN")
    influx_token = os.environ.get("HEIMDALL_INFLUX_TOKEN")
    if not ha_token or not influx_token:
        print(
            "ERROR: set HEIMDALL_HA_TOKEN (HA long-lived token) and "
            "HEIMDALL_INFLUX_TOKEN (InfluxDB API token).",
            file=sys.stderr,
        )
        return 1

    print(f"Toggling {args.switch} off...")
    call_ha_service(args.ha_url, ha_token, "switch", "turn_off", args.switch)
    print(f"Waiting {OFF_WAIT_SECONDS}s for the power sensor to report a drop...")
    time.sleep(OFF_WAIT_SECONDS)

    print(f"Toggling {args.switch} back on...")
    call_ha_service(args.ha_url, ha_token, "switch", "turn_on", args.switch)

    print("Polling InfluxDB for the drop-then-recover pattern...")
    deadline = time.time() + POLL_TIMEOUT_SECONDS
    while time.time() < deadline:
        time.sleep(POLL_INTERVAL_SECONDS)
        points = query_influx_recent_points(
            args.influx_url, influx_token, args.influx_org, args.influx_bucket, args.sensor
        )
        if len(points) < 2:
            continue

        # Look for a near-zero point followed (anywhere later) by a
        # meaningfully non-zero point - this is the toggle's off->on signal.
        saw_drop = False
        for point in points:
            if point["value"] < 1.0:
                saw_drop = True
            elif saw_drop and point["value"] > 1.0:
                print(
                    f"CONFIRMED: {args.sensor} shows a drop-then-recover in InfluxDB "
                    f"(drop at/after toggle, recovered to {point['value']} W at {point['time']})."
                )
                return 0

    print(
        f"FAILED: no drop-then-recover pattern found in InfluxDB for {args.sensor} "
        f"within {POLL_TIMEOUT_SECONDS}s of toggling {args.switch}. This may mean the "
        "setpoint write isn't landing in InfluxDB - or, if this is switch.grzalka, that "
        "the heater simply wasn't drawing power at toggle time (see module docstring).",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
