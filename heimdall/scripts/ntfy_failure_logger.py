#!/usr/bin/env python3
"""Task 7 (M6) — ntfy failure logger for `heimdall/tests/test_matrix.py` soak runs.

Reuses ProjectNemo's existing `nemo-ntfy` container (image `binwiederhier/ntfy`,
already running on vesemir at :8081 — see `heimdall/N8N_ROUTER.md`-style infra
discovery notes below) rather than standing up a new server. No new container
was added for this task.

Auth provisioning (done live, 2026-08-19, via passwordless SSH to vesemir —
not scriptable/idempotent here on purpose, since it's a one-time bootstrap of
a dedicated low-privilege identity, not something this poller should be able
to re-run):

    docker exec nemo-ntfy ntfy user add --role=user heimdall_bot
    docker exec nemo-ntfy ntfy access heimdall_bot heimdall-failures rw
    docker exec nemo-ntfy ntfy token add heimdall_bot   # -> HEIMDALL_NTFY_TOKEN

The server's `ntfy/server.yml` has `auth-default-access: deny-all`, so this
scoped user/token is required — anonymous publish/subscribe to the new
`heimdall-failures` topic is refused (confirmed live: 403). `test_matrix.py`
publishes one message per FAILing implementable row using the same token.

This poller uses ntfy's `since=<last message id>` + `poll=1` pattern (see
https://docs.ntfy.sh/subscribe/api/#fetch-cached-messages) rather than a
long-lived streaming connection — more robust across reconnects/network
blips, and lets a restart resume from exactly where it left off (last-seen
message id persisted in a small local state file, not in-memory only).

Known limitation, documented rather than hidden: ntfy's message cache has a
retention window (server-side, a couple of hours by default). If this poller
is down longer than that, older failures published while it was down will be
lost rather than backfilled — acceptable for a soak-test log, not for
anything safety-critical.

Usage:
    HEIMDALL_NTFY_TOKEN=<heimdall_bot token> python ntfy_failure_logger.py
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("heimdall.ntfy_failure_logger")

NTFY_URL = os.environ.get("HEIMDALL_NTFY_URL", "http://192.168.0.108:8081")
NTFY_TOPIC = os.environ.get("HEIMDALL_NTFY_TOPIC", "heimdall-failures")
NTFY_TOKEN = os.environ.get("HEIMDALL_NTFY_TOKEN", "")
POLL_INTERVAL_SECONDS = float(os.environ.get("HEIMDALL_NTFY_POLL_INTERVAL_SECONDS", "30"))

REPO_ROOT = Path(__file__).resolve().parents[2]
SOAK_LOG_PATH = Path(os.environ.get("HEIMDALL_SOAK_LOG_PATH", str(REPO_ROOT / "heimdall" / "SOAK_LOG.md")))
STATE_PATH = Path(
    os.environ.get(
        "HEIMDALL_NTFY_STATE_PATH",
        str(Path(__file__).resolve().parent / ".ntfy_failure_logger_state.json"),
    )
)

SOAK_LOG_HEADER = (
    "# Heimdall soak-test failure log\n\n"
    "Appended automatically by `heimdall/scripts/ntfy_failure_logger.py` whenever "
    "`heimdall/tests/test_matrix.py` publishes a failing row to the `heimdall-failures` "
    "ntfy topic. Do not hand-edit above this line.\n"
)


def _load_since() -> str:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8")).get("since", "all")
        except (json.JSONDecodeError, OSError):
            log.warning("Could not read state file %s, starting from 'all'", STATE_PATH)
    return "all"


def _save_since(message_id: str) -> None:
    STATE_PATH.write_text(json.dumps({"since": message_id}), encoding="utf-8")


def _append_to_soak_log(msg: dict) -> None:
    ts = datetime.fromtimestamp(msg.get("time", time.time()), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    title = msg.get("title", "(no title)")
    body = msg.get("message", "")
    entry = f"\n## {ts} — {title}\n\n{body}\n"

    SOAK_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not SOAK_LOG_PATH.exists():
        SOAK_LOG_PATH.write_text(SOAK_LOG_HEADER, encoding="utf-8")

    with SOAK_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(entry)


def poll_once(session: requests.Session, since: str) -> str:
    headers = {"Authorization": f"Bearer {NTFY_TOKEN}"}
    resp = session.get(
        f"{NTFY_URL.rstrip('/')}/{NTFY_TOPIC}/json",
        params={"poll": "1", "since": since},
        headers=headers,
        timeout=15,
    )
    resp.raise_for_status()

    latest_id = since
    for line in resp.text.strip().splitlines():
        if not line.strip():
            continue
        msg = json.loads(line)
        if msg.get("event") != "message":
            continue  # skip the initial "open" keepalive event
        _append_to_soak_log(msg)
        log.info("Logged failure: %s", msg.get("title"))
        latest_id = msg["id"]

    return latest_id


def main() -> int:
    if not NTFY_TOKEN:
        print("ERROR: set HEIMDALL_NTFY_TOKEN to the heimdall_bot ntfy access token.", file=sys.stderr)
        return 1

    since = _load_since()
    log.info(
        "Starting Heimdall ntfy failure logger: url=%s topic=%s since=%s interval=%ss soak_log=%s",
        NTFY_URL,
        NTFY_TOPIC,
        since,
        POLL_INTERVAL_SECONDS,
        SOAK_LOG_PATH,
    )

    with requests.Session() as session:
        while True:
            start = time.monotonic()
            try:
                since = poll_once(session, since)
                _save_since(since)
            except Exception:  # noqa: BLE001 - keep the logger alive across transient errors
                log.exception("Poll cycle failed, will retry next interval")

            elapsed = time.monotonic() - start
            time.sleep(max(0.0, POLL_INTERVAL_SECONDS - elapsed))


if __name__ == "__main__":
    sys.exit(main())
