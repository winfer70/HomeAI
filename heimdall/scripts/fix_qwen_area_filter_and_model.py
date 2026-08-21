#!/usr/bin/env python3
"""Read/write: replace the earlier vague qwen prompt addition with a precise
instruction to always call GetLiveContext with the `area` parameter set for
"what's in room X" questions (GetLiveContext already supports server-side
area filtering via intent.async_match_targets - the model just wasn't using
it). Also swaps the qwen subentry's model to qwen3:14b. Backs up first.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import json

CONFIG_ENTRIES_PATH = Path("/config/.storage/core.config_entries")
BACKUP_PATH = Path("/config/.storage/core.config_entries.bak-qwen-area-filter-fix-20260821")

OLD_ADDITION = (
    "\n\nWhen asked what's in a room/area (e.g. \"what's in the office\"), "
    "you must call GetLiveContext and then list EVERY exposed entity whose "
    "area matches - across ALL domains (climate, sensor, binary_sensor, "
    "light, fan, switch, etc.), not just switches. Do not silently drop "
    "entities just because they have more attributes than a simple on/off "
    "switch."
)

NEW_ADDITION = (
    "\n\nWhen asked what's in a room/area (e.g. \"what's in the office\", "
    "\"co jest w biurze\"), you MUST call GetLiveContext with its `area` "
    "parameter set to that room's name - never call it with no filter and "
    "never answer from the static device list alone. The tool filters "
    "server-side and will return every matching entity across every domain "
    "(climate, sensor, binary_sensor, light, fan, switch, etc.) - list all "
    "of them, don't drop any."
)

NEW_MODEL = "qwen3:14b"


def main() -> int:
    if not CONFIG_ENTRIES_PATH.exists():
        print(f"ERROR: {CONFIG_ENTRIES_PATH} not found", file=sys.stderr)
        return 1

    shutil.copy2(CONFIG_ENTRIES_PATH, BACKUP_PATH)
    print(f"Backed up to {BACKUP_PATH}")

    data = json.loads(CONFIG_ENTRIES_PATH.read_text(encoding="utf-8"))

    patched = False
    for entry in data["data"]["entries"]:
        if entry.get("domain") != "ollama":
            continue
        for sub in entry.get("subentries", []):
            if sub.get("title") != "Heimdall Local (qwen2.5)":
                continue
            prompt = sub["data"].get("prompt", "")
            if OLD_ADDITION.strip() in prompt:
                prompt = prompt.replace(OLD_ADDITION, "")
                print("Removed old vague addition.")
            if NEW_ADDITION.strip() not in prompt:
                prompt = prompt + NEW_ADDITION
                print("Added new precise area-filter instruction.")
            sub["data"]["prompt"] = prompt

            old_model = sub["data"].get("model")
            sub["data"]["model"] = NEW_MODEL
            print(f"Model: {old_model} -> {NEW_MODEL}")
            patched = True

    if not patched:
        print("ERROR: could not find qwen subentry to patch", file=sys.stderr)
        return 1

    CONFIG_ENTRIES_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
