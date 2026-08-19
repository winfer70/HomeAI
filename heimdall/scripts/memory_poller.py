#!/usr/bin/env python3
"""Heimdall memory poller (Task 8 / M7, safety-net path).

HA has no "conversation finished" bus event (confirmed against HA core
source - see heimdall/memory_service/README.md for the full write-path
design). This poller is the workaround: it periodically reads HA's
Assist pipeline-debug WebSocket API (`assist_pipeline/pipeline_debug/list`
+ `/get` - admin-only, in-memory, the same data backing HA's own Assist
debug UI) for every pipeline whose name starts with "Heimdall", extracts
newly-finished conversation transcripts, and forwards them to the memory
service's `/extract` endpoint for fact/summary extraction.

This runs *alongside*, not instead of, the explicit remember_fact/
recall_facts tool path (see configuration.yaml's rest_command/script
entries) - it exists to catch worthwhile details the user never
explicitly asked the assistant to "remember".

Event schema was confirmed against a live HA 2026.8.x instance, not just
guessed from source: a pipeline run's debug events are `run-start`,
`intent-start` (carries the user's text in `intent_input` and the
`conversation_id`), a stream of `intent-progress` events each carrying a
`chat_log_delta` (assistant text arrives as `content` string chunks -
concatenate them in order to reconstruct the full reply; tool-call/
tool-result deltas don't have a `content` key so they're naturally
skipped), and a `run-end` with no data. There is no `intent-end` event in
this HA version.

Already-processed runs are tracked server-side via the memory service's
`/processed_runs/{pipeline_id}/{run_id}` endpoints (not local state) so
the poller can restart without reprocessing or needing a persistent
volume of its own.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time

import httpx
import websockets

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("heimdall.memory_poller")

HA_URL = os.environ.get("HEIMDALL_HA_URL", "ws://vesemir:8123/api/websocket")
HA_TOKEN = os.environ.get("HEIMDALL_HA_TOKEN", "")
MEMORY_URL = os.environ.get("HEIMDALL_MEMORY_URL", "http://heimdall-memory:10400")
MEMORY_TOKEN = os.environ.get("HEIMDALL_MEMORY_TOKEN", "")
POLL_INTERVAL_SECONDS = float(os.environ.get("HEIMDALL_POLL_INTERVAL_SECONDS", "60"))
PIPELINE_NAME_PREFIX = "Heimdall"


class HaWebSocket:
    """Tiny helper around HA's WebSocket API with auto-incrementing message ids."""

    def __init__(self, ws: websockets.WebSocketClientProtocol) -> None:
        self._ws = ws
        self._next_id = 1

    async def call(self, payload: dict) -> dict:
        msg_id = self._next_id
        self._next_id += 1
        payload = {"id": msg_id, **payload}
        await self._ws.send(json.dumps(payload))
        while True:
            result = json.loads(await self._ws.recv())
            if result.get("id") == msg_id:
                return result
            # Ignore stray event/result frames for other subscriptions.


async def authenticate(ws: websockets.WebSocketClientProtocol, token: str) -> None:
    auth_required = json.loads(await ws.recv())
    if auth_required.get("type") != "auth_required":
        raise RuntimeError(f"Unexpected handshake message: {auth_required}")
    await ws.send(json.dumps({"type": "auth", "access_token": token}))
    auth_result = json.loads(await ws.recv())
    if auth_result.get("type") != "auth_ok":
        raise RuntimeError(f"Authentication failed: {auth_result}")


def _reconstruct_transcript(events: list[dict]) -> tuple[str | None, str, str, str]:
    """Extract (user_text, assistant_text, language, conversation_id) from a
    pipeline run's debug events. Returns assistant_text="" if the run never
    produced a response (e.g. it errored out)."""
    user_text: str | None = None
    language = "en"
    conversation_id = ""
    assistant_parts: list[str] = []

    for event in events:
        data = event.get("data") or {}
        if event["type"] == "run-start":
            language = data.get("language", language)
            conversation_id = data.get("conversation_id", conversation_id)
        elif event["type"] == "intent-start":
            user_text = data.get("intent_input")
            language = data.get("language", language)
            conversation_id = data.get("conversation_id", conversation_id)
        elif event["type"] == "intent-progress":
            delta = data.get("chat_log_delta") or {}
            content = delta.get("content")
            if isinstance(content, str) and content:
                assistant_parts.append(content)

    return user_text, "".join(assistant_parts), language, conversation_id


async def _is_processed(client: httpx.AsyncClient, pipeline_id: str, run_id: str) -> bool:
    resp = await client.get(
        f"{MEMORY_URL}/processed_runs/{pipeline_id}/{run_id}",
        headers={"X-Heimdall-Memory-Token": MEMORY_TOKEN},
    )
    resp.raise_for_status()
    return bool(resp.json().get("processed"))


async def _mark_processed(client: httpx.AsyncClient, pipeline_id: str, run_id: str) -> None:
    resp = await client.post(
        f"{MEMORY_URL}/processed_runs/{pipeline_id}/{run_id}",
        headers={"X-Heimdall-Memory-Token": MEMORY_TOKEN},
    )
    resp.raise_for_status()


async def _extract(
    client: httpx.AsyncClient, conversation_id: str, language: str, user_text: str, assistant_text: str
) -> None:
    transcript = [{"speaker": "user", "text": user_text}]
    if assistant_text:
        transcript.append({"speaker": "assistant", "text": assistant_text})

    resp = await client.post(
        f"{MEMORY_URL}/extract",
        headers={"X-Heimdall-Memory-Token": MEMORY_TOKEN},
        json={
            "conversation_id": conversation_id or "unknown",
            "language": language,
            "transcript": transcript,
        },
        timeout=90.0,
    )
    resp.raise_for_status()
    result = resp.json()
    log.info(
        "extracted: conversation_id=%s facts_upserted=%s summary_updated=%s",
        conversation_id,
        result.get("facts_upserted"),
        result.get("summary_updated"),
    )


async def poll_once(client: httpx.AsyncClient) -> None:
    async with websockets.connect(HA_URL, max_size=10_000_000) as ws:
        await authenticate(ws, HA_TOKEN)
        ha = HaWebSocket(ws)

        pipelines_result = await ha.call({"type": "assist_pipeline/pipeline/list"})
        if not pipelines_result.get("success"):
            log.error("Failed to list pipelines: %s", pipelines_result)
            return

        heimdall_pipelines = [
            p
            for p in pipelines_result["result"]["pipelines"]
            if p["name"].startswith(PIPELINE_NAME_PREFIX)
        ]

        for pipeline in heimdall_pipelines:
            pipeline_id = pipeline["id"]
            runs_result = await ha.call(
                {"type": "assist_pipeline/pipeline_debug/list", "pipeline_id": pipeline_id}
            )
            if not runs_result.get("success"):
                log.warning("Failed to list runs for %s: %s", pipeline["name"], runs_result)
                continue

            for run in runs_result["result"]["pipeline_runs"]:
                run_id = run["pipeline_run_id"]
                if await _is_processed(client, pipeline_id, run_id):
                    continue

                run_result = await ha.call(
                    {
                        "type": "assist_pipeline/pipeline_debug/get",
                        "pipeline_id": pipeline_id,
                        "pipeline_run_id": run_id,
                    }
                )
                if not run_result.get("success"):
                    log.warning("Failed to get run %s: %s", run_id, run_result)
                    continue

                user_text, assistant_text, language, conversation_id = _reconstruct_transcript(
                    run_result["result"]["events"]
                )
                if not user_text:
                    # Audio-stage-only runs, or runs still in progress - skip
                    # for now, will be retried (still unprocessed) next poll.
                    continue

                try:
                    await _extract(client, conversation_id, language, user_text, assistant_text)
                except httpx.HTTPError as exc:
                    log.error("Extraction failed for run %s: %s", run_id, exc)
                    continue

                await _mark_processed(client, pipeline_id, run_id)


async def main() -> int:
    if not HA_TOKEN:
        print("ERROR: set HEIMDALL_HA_TOKEN to a Home Assistant long-lived access token.", file=sys.stderr)
        return 1
    if not MEMORY_TOKEN:
        print("ERROR: set HEIMDALL_MEMORY_TOKEN to the memory service's shared token.", file=sys.stderr)
        return 1

    log.info(
        "Starting Heimdall memory poller: ha_url=%s memory_url=%s interval=%ss",
        HA_URL,
        MEMORY_URL,
        POLL_INTERVAL_SECONDS,
    )

    async with httpx.AsyncClient() as client:
        while True:
            start = time.monotonic()
            try:
                await poll_once(client)
            except Exception:  # noqa: BLE001 - keep the poller alive across transient errors
                log.exception("Poll cycle failed, will retry next interval")

            elapsed = time.monotonic() - start
            await asyncio.sleep(max(0.0, POLL_INTERVAL_SECONDS - elapsed))


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
