#!/usr/bin/env python3
"""Read/write: move the two alarm automations that reference `!secret
alarm_code` out of /config/automations.yaml (whose UI-editor loader
disallows !secret, breaking the whole automation list with a 500) into
/config/heimdall.yaml's new `automation:` package key (packages load through
the normal secrets-enabled loader, same reason heimdall.yaml's `rest:`
sensor already uses !secret heimdall_memory_token fine). Backs up both
files first. Idempotent (skips if already moved).
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

AUTOMATIONS_PATH = Path("/config/automations.yaml")
HEIMDALL_YAML_PATH = Path("/config/heimdall.yaml")
AUTOMATIONS_BACKUP = Path("/config/automations.yaml.bak-move-alarm-secrets-20260824")
HEIMDALL_BACKUP = Path("/config/heimdall.yaml.bak-move-alarm-secrets-20260824")

START_MARKER = "- id: alarm_auto_arm_away_presence\n"
END_MARKER = "- id: gate_ring_notify_with_open_action\n"


def main() -> int:
    if not AUTOMATIONS_PATH.exists() or not HEIMDALL_YAML_PATH.exists():
        print("ERROR: automations.yaml or heimdall.yaml not found", file=sys.stderr)
        return 1

    automations_content = AUTOMATIONS_PATH.read_text(encoding="utf-8")
    heimdall_content = HEIMDALL_YAML_PATH.read_text(encoding="utf-8")

    if "alarm_auto_arm_away_presence" not in automations_content:
        print("Already moved - alarm automations not in automations.yaml anymore.")
        return 0

    start = automations_content.index(START_MARKER)
    end = automations_content.index(END_MARKER, start)
    moved_block = automations_content[start:end]

    shutil.copy2(AUTOMATIONS_PATH, AUTOMATIONS_BACKUP)
    shutil.copy2(HEIMDALL_YAML_PATH, HEIMDALL_BACKUP)
    print(f"Backed up to {AUTOMATIONS_BACKUP} and {HEIMDALL_BACKUP}")

    new_automations_content = automations_content[:start] + automations_content[end:]
    AUTOMATIONS_PATH.write_text(new_automations_content, encoding="utf-8")

    # Re-indent the moved block by 2 spaces so it parses as a list under
    # heimdall.yaml's new `automation:` package key (top-level automations.yaml
    # entries are 0-indented "- id:", package list items need 2-space indent).
    reindented = "\n".join(
        ("  " + line if line.strip() else line) for line in moved_block.rstrip("\n").split("\n")
    )

    addition = (
        "\n# Moved here from automations.yaml (2026-08-24) - the UI automation "
        "editor's YAML loader (homeassistant/components/config/view.py) "
        "disallows !secret references, and these two used `!secret "
        "alarm_code`, which broke the ENTIRE automation list with a 500 "
        "error. Packages load through the normal secrets-enabled loader, so "
        "moving them here fixes it while keeping the code out of a "
        "UI-editable/committed file. No longer editable via the visual "
        "automation editor (same as every other heimdall.yaml automation/"
        "script) - edit this file directly instead.\nautomation:\n"
        + reindented
        + "\n"
    )

    heimdall_content = heimdall_content.rstrip("\n") + "\n" + addition
    HEIMDALL_YAML_PATH.write_text(heimdall_content, encoding="utf-8")
    print("Moved both alarm automations into heimdall.yaml's automation: key.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
