#!/usr/bin/env python3
"""Create the Heimdall Assist pipelines in Home Assistant.

IMPORTANT — architecture note (confirmed against HA core source, 2026.8.1):
A single Assist Pipeline object has exactly ONE fixed language. The
`assist_pipeline/run` WebSocket command has no per-invocation language
override, and `validate_language()` in HA's `assist_pipeline/pipeline.py`
requires a concrete (non-null) `stt_language`/`tts_language` whenever the
corresponding engine is set. There is no supported way to make one pipeline
transparently serve both Polish and English.

Because of this, this script creates TWO pipelines instead of the single
"Heimdall" pipeline named in the original brief:
  - "Heimdall-EN" (English)
  - "Heimdall-PL" (Polish)

Both point at the same jaskier Wyoming containers (stt.faster_whisper /
tts.piper) and the same conversation agent (Gemini, entity id
conversation.google_ai_conversation). Pick whichever pipeline matches the
language you're speaking (e.g. two Companion App / satellite configs, or
switch pipelines per-request) until HA gains real per-run language handling.

This script uses HA's public WebSocket API only (assist_pipeline/pipeline/*
storage-collection commands) — it does not touch `.storage/` files directly,
consistent with this project's guardrail around Assist internal state.

Usage:
    HEIMDALL_HA_TOKEN=<long-lived token> python create_assist_pipeline.py
    HEIMDALL_HA_URL can override the default ws://192.168.0.108:8123/api/websocket

Idempotent: skips creation for any pipeline name that already exists.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

import websockets

DEFAULT_HA_URL = "ws://192.168.0.108:8123/api/websocket"

CONVERSATION_ENGINE = "conversation.google_ai_conversation"
STT_ENGINE = "stt.faster_whisper"
TTS_ENGINE = "tts.piper"

PIPELINES = [
    {
        "name": "Heimdall-EN",
        "conversation_engine": CONVERSATION_ENGINE,
        "conversation_language": "en",
        "language": "en",
        "stt_engine": STT_ENGINE,
        "stt_language": "en",
        "tts_engine": TTS_ENGINE,
        "tts_language": "en_GB",
        "tts_voice": "en_GB-alba-medium",
        "wake_word_entity": None,
        "wake_word_id": None,
    },
    {
        "name": "Heimdall-PL",
        "conversation_engine": CONVERSATION_ENGINE,
        "conversation_language": "pl",
        "language": "pl",
        "stt_engine": STT_ENGINE,
        "stt_language": "pl",
        "tts_engine": TTS_ENGINE,
        "tts_language": "pl_PL",
        "tts_voice": "pl_PL-darkman-medium",
        "wake_word_entity": None,
        "wake_word_id": None,
    },
]


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
        result = json.loads(await self._ws.recv())
        if result.get("id") != msg_id:
            raise RuntimeError(f"Unexpected response id: {result}")
        return result


async def authenticate(ws: websockets.WebSocketClientProtocol, token: str) -> None:
    auth_required = json.loads(await ws.recv())
    if auth_required.get("type") != "auth_required":
        raise RuntimeError(f"Unexpected handshake message: {auth_required}")

    await ws.send(json.dumps({"type": "auth", "access_token": token}))
    auth_result = json.loads(await ws.recv())
    if auth_result.get("type") != "auth_ok":
        raise RuntimeError(f"Authentication failed: {auth_result}")


async def main() -> int:
    token = os.environ.get("HEIMDALL_HA_TOKEN")
    if not token:
        print(
            "ERROR: set HEIMDALL_HA_TOKEN to a Home Assistant long-lived access token.",
            file=sys.stderr,
        )
        return 1

    ha_url = os.environ.get("HEIMDALL_HA_URL", DEFAULT_HA_URL)

    async with websockets.connect(ha_url, max_size=10_000_000) as ws:
        await authenticate(ws, token)
        client = HaWebSocket(ws)

        existing = await client.call({"type": "assist_pipeline/pipeline/list"})
        if not existing.get("success"):
            print(f"ERROR: could not list pipelines: {existing}", file=sys.stderr)
            return 1

        existing_names = {
            p["name"] for p in existing["result"].get("pipelines", [])
        }

        for pipeline in PIPELINES:
            name = pipeline["name"]
            if name in existing_names:
                print(f"SKIP: pipeline '{name}' already exists.")
                continue

            create_result = await client.call(
                {"type": "assist_pipeline/pipeline/create", **pipeline}
            )
            if not create_result.get("success"):
                print(
                    f"ERROR: failed to create pipeline '{name}': {create_result}",
                    file=sys.stderr,
                )
                return 1

            created = create_result["result"]
            print(f"CREATED: pipeline '{name}' (id={created.get('id')})")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
