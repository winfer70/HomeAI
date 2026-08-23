#!/usr/bin/env python3
"""Read/write: append the heimdall_pulse_gate script to /config/heimdall.yaml
right after heimdall_boost_revert_worker (inside the same `script:` block).
The physical gate relay is momentary/impulse-triggered (same as the wall
Aqara button's pulse automation) - this gives voice a script that does the
same turn_on -> wait 1s -> turn_off pulse, instead of just leaving the
switch on. Backs up first, idempotent (skips if already present).
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

HEIMDALL_YAML_PATH = Path("/config/heimdall.yaml")
BACKUP_PATH = Path("/config/heimdall.yaml.bak-pulse-gate-20260821")

ANCHOR = "\n# Heimdall persistent memory context sensor"

NEW_SCRIPT = '''
  # Gate: voice pulse trigger (added 2026-08-21). The physical gate relay
  # (switch.brama_sonoff_100254194e_1) is momentary/impulse-triggered, same
  # as the wall-mounted Aqara button's "pulse_gate_relay" automation - turn
  # on, wait ~1s, turn off. Every pulse toggles the gate open/closed; the
  # switch's on/off STATE in HA does not represent open/closed, so voice
  # commands must never just call switch.turn_on and leave it - that only
  # leaves the relay energized without ever pulsing it back off, which
  # reads as "gate opened" in the switch state but does nothing physically
  # until someone flips it off again. This script is the only voice-exposed
  # way to operate the gate; the raw switch is unexposed from Assist (see
  # HA_CONFIG_CHANGES.md) so neither conversation agent can call turn_on/
  # turn_off on it directly.
  heimdall_pulse_gate:
    alias: "Heimdall: Pulse gate relay (open/close)"
    mode: single
    description: >-
      Open or close the driveway gate by pulsing its relay (mirrors the
      physical wall button). Use this for ANY request to open, close, or
      toggle the gate, in either Polish or English (e.g. "open the gate",
      "otwórz bramę", "zamknij bramę") - there is no separate open vs.
      close action, every pulse toggles it.
    sequence:
      - action: switch.turn_on
        target:
          entity_id: switch.brama_sonoff_100254194e_1
      - delay:
          seconds: 1
      - action: switch.turn_off
        target:
          entity_id: switch.brama_sonoff_100254194e_1
      - stop: "Gate pulsed"
'''


def main() -> int:
    if not HEIMDALL_YAML_PATH.exists():
        print(f"ERROR: {HEIMDALL_YAML_PATH} not found", file=sys.stderr)
        return 1

    content = HEIMDALL_YAML_PATH.read_text(encoding="utf-8")

    if "heimdall_pulse_gate:" in content:
        print("heimdall_pulse_gate already present - not double-adding.")
        return 0

    if ANCHOR not in content:
        print("ERROR: anchor text not found - file may have changed", file=sys.stderr)
        return 1

    shutil.copy2(HEIMDALL_YAML_PATH, BACKUP_PATH)
    print(f"Backed up to {BACKUP_PATH}")

    new_content = content.replace(ANCHOR, NEW_SCRIPT + ANCHOR, 1)
    HEIMDALL_YAML_PATH.write_text(new_content, encoding="utf-8")
    print("Inserted heimdall_pulse_gate script.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
