#!/usr/bin/env python3
"""One-off: append an explicit "list every item, never summarize/omit" clause
to the Google AI Conversation subentry's system prompt in core.config_entries,
to fix the reproducible (not random) omission of 3 of 6 Meross outlet
entities from "what's in the office" answers. Confirmed via direct registry
inspection that all 6 outlets are byte-identical in exposure config - this
is a Gemini response-generation behavior, likely caused by the existing
"Keep it simple and to the point" instruction encouraging it to shorten
long device lists. Edits the file in place; caller is responsible for
backup before running and HA restart after.
"""
from __future__ import annotations

import json
import sys

PATH = "/home/kamilo/nemo/ProjectNemo/homeassistant/config/.storage/core.config_entries"
SUBENTRY_ID = "01KY29VPMN5JJBTPWB1Y6PXNC2"

ADDED_CLAUSE = (
    "\n\nWhen asked what devices, entities, or things are in a room/area, "
    "list every single item returned by the tool call, in full - do not "
    "summarize, shorten, merge similar-looking entries, or omit any of them "
    "for brevity, even if there are many or some seem repetitive (e.g. "
    "multiple similarly-named outlets or sensors). Completeness matters more "
    "than brevity for this specific type of question."
)


def main() -> int:
    with open(PATH, encoding="utf-8") as f:
        data = json.load(f)

    found = False
    for entry in data["data"]["entries"]:
        for sub in entry.get("subentries", []):
            if sub.get("subentry_id") == SUBENTRY_ID:
                old_prompt = sub["data"]["prompt"]
                if ADDED_CLAUSE.strip() in old_prompt:
                    print("Clause already present, no change made.")
                    return 0
                sub["data"]["prompt"] = old_prompt + ADDED_CLAUSE
                found = True
                print("OK: prompt updated for subentry", SUBENTRY_ID)
                print("--- new prompt ---")
                print(sub["data"]["prompt"])

    if not found:
        print(f"ERROR: subentry {SUBENTRY_ID} not found", file=sys.stderr)
        return 1

    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return 0


if __name__ == "__main__":
    sys.exit(main())
