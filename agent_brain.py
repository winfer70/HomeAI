"""DEPRECATED — use src/homeai/agent_brain.py instead.

Legacy agent brain module containing older implementations of Memory, LLM dispatch,
and ReAct pipeline logic. All active code is in the src/homeai/ package structure.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import sqlite3
from datetime import UTC, datetime
from typing import Any

import httpx

from config import settings
from tools import home_service, home_state, web_search

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool registry — the LLM reads these descriptions to decide what to call
# ---------------------------------------------------------------------------

_TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "web_search": {
        "description": (
            "Search the internet for current information: weather, news, facts, prices, events. "
            "Supports Polish and English queries."
        ),
        "parameters": {
            "query": "string — the search query",
        },
    },
    "home_service": {
        "description": (
            "Control a smart home device via Home Assistant. "
            "Use home_state first if you are unsure of the exact entity_id."
        ),
        "parameters": {
            "domain": "string — HA domain, e.g. light, climate, switch, cover, media_player",
            "service": "string — HA service, e.g. turn_on, turn_off, set_temperature, open_cover",
            "entity_id": "string — HA entity ID, e.g. light.kitchen_ceiling",
            "data": "object (optional) — extra service params, e.g. {\"temperature\": 22, \"brightness_pct\": 60}",
        },
    },
    "home_state": {
        "description": "Query the current state of any Home Assistant entity (sensor, switch, light, etc.).",
        "parameters": {
            "entity_id": "string — HA entity ID to query",
        },
    },
}

# ---------------------------------------------------------------------------
# System prompt — forces bilingual ReAct JSON output
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT_TEMPLATE = """\
You are HomeAI — an intelligent home assistant with a reasoning brain.
You understand both English and Polish perfectly. Always reply in the SAME language the user used.

Available tools:
{tools_block}

Output FORMAT — you must always return a single valid JSON object and nothing else.

When using a tool:
{{"thought": "your reasoning step", "action": "tool_name", "action_input": {{...}}}}

When you have the final answer:
{{"thought": "I have everything I need", "action": "final_answer", "action_input": {{"text": "your reply to the user"}}}}

Rules:
- Think step by step. For conditional tasks (e.g., "if it rains, turn on heating") always check the condition FIRST.
- Never invent entity IDs. Query home_state first when unsure.
- Keep final_answer text natural and conversational, matching the user's language.
- Output ONLY valid JSON. No markdown, no prose outside the JSON block.
"""


def _build_tools_block() -> str:
    lines: list[str] = []
    for name, schema in _TOOL_SCHEMAS.items():
        lines.append(f"  {name}: {schema['description']}")
        for param, desc in schema["parameters"].items():
            lines.append(f"    - {param}: {desc}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# SQLite sliding-window memory
# ---------------------------------------------------------------------------


class Memory:
    """Persists conversation turns in SQLite; exposes a fixed-size context window."""

    def __init__(self, db_path: str, window: int) -> None:
        self._window = window
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS turns (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                ts      TEXT    NOT NULL,
                role    TEXT    NOT NULL,
                content TEXT    NOT NULL
            )
            """
        )
        self._conn.commit()

    def add(self, role: str, content: str) -> None:
        self._conn.execute(
            "INSERT INTO turns (ts, role, content) VALUES (?, ?, ?)",
            (datetime.now(UTC).isoformat(), role, content),
        )
        self._conn.commit()

    def recent(self) -> list[dict[str, str]]:
        """Return the last `window` user/assistant pairs in chronological order."""
        rows = self._conn.execute(
            "SELECT role, content FROM turns ORDER BY id DESC LIMIT ?",
            (self._window * 2,),
        ).fetchall()
        return [{"role": r, "content": c} for r, c in reversed(rows)]

    def close(self) -> None:
        self._conn.close()


# ---------------------------------------------------------------------------
# LLM call (Ollama /api/chat)
# ---------------------------------------------------------------------------


async def _llm_step(messages: list[dict[str, str]]) -> str:
    """One Ollama chat round; returns raw response text."""
    url = f"{settings.ollama_base_url}/api/chat"
    payload = {
        "model": settings.ollama_model,
        "messages": messages,
        "stream": False,
        "format": "json",
        "options": {"temperature": settings.llm_temperature},
    }
    try:
        async with httpx.AsyncClient(timeout=settings.llm_timeout_s) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()["message"]["content"]
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"Ollama HTTP {e.response.status_code}: {e.response.text[:300]}") from e
    except httpx.RequestError as e:
        raise RuntimeError(f"Ollama connection error: {e}") from e


# ---------------------------------------------------------------------------
# JSON extraction — handles models that wrap JSON in markdown fences
# ---------------------------------------------------------------------------


def _extract_json(raw: str) -> dict[str, Any]:
    stripped = raw.strip()
    # Try direct parse first
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    # Strip markdown fences if present
    stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
    stripped = re.sub(r"\s*```$", "", stripped)
    try:
        return json.loads(stripped.strip())
    except json.JSONDecodeError:
        pass
    # Last resort: grab first {...} block
    m = re.search(r"\{.*\}", stripped, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    raise ValueError(f"No valid JSON in LLM output: {raw[:400]}")


# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------


async def _dispatch(action: str, action_input: dict[str, Any]) -> str:
    try:
        if action == "web_search":
            query = action_input.get("query", "")
            if not query:
                return "Error: web_search requires a 'query' parameter."
            return await web_search(query)

        if action == "home_service":
            domain = action_input.get("domain", "")
            service = action_input.get("service", "")
            entity_id = action_input.get("entity_id", "")
            if not all([domain, service, entity_id]):
                return "Error: home_service requires 'domain', 'service', and 'entity_id'."
            return await home_service(domain, service, entity_id, action_input.get("data"))

        if action == "home_state":
            entity_id = action_input.get("entity_id", "")
            if not entity_id:
                return "Error: home_state requires 'entity_id'."
            return await home_state(entity_id)

        return f"Error: unknown tool '{action}'. Available: {list(_TOOL_SCHEMAS)}"

    except Exception as e:
        log.exception("Tool '%s' raised an exception", action)
        return f"Tool error: {e}"


# ---------------------------------------------------------------------------
# Main ReAct pipeline
# ---------------------------------------------------------------------------


async def run_pipeline(user_input: str, memory: Memory) -> str:
    """
    Run a full ReAct reasoning loop for one user turn.
    Returns the final text response (ready for TTS).
    """
    system_content = _SYSTEM_PROMPT_TEMPLATE.format(tools_block=_build_tools_block())

    messages: list[dict[str, str]] = [{"role": "system", "content": system_content}]
    messages.extend(memory.recent())
    messages.append({"role": "user", "content": user_input})

    memory.add("user", user_input)

    for iteration in range(settings.react_max_iterations):
        log.debug("ReAct iteration %d/%d", iteration + 1, settings.react_max_iterations)

        try:
            raw = await _llm_step(messages)
        except RuntimeError as e:
            log.error("LLM failed: %s", e)
            err = "Przepraszam, wystąpił błąd połączenia z modelem. / Sorry, the AI model is unreachable."
            memory.add("assistant", err)
            return err

        try:
            step = _extract_json(raw)
        except ValueError:
            log.warning("Malformed JSON on iteration %d — asking model to retry", iteration + 1)
            messages.append({"role": "assistant", "content": raw})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Your response was not valid JSON. "
                        "Output a single JSON object only, with keys: thought, action, action_input."
                    ),
                }
            )
            continue

        thought = step.get("thought", "")
        action = step.get("action", "")
        action_input = step.get("action_input", {})

        log.info("[iter %d] thought=%r  action=%s", iteration + 1, thought[:80], action)

        if action == "final_answer":
            answer = (
                action_input.get("text", "")
                if isinstance(action_input, dict)
                else str(action_input)
            )
            memory.add("assistant", answer)
            return answer

        # Execute tool and feed observation back
        observation = await _dispatch(action, action_input)
        log.info("observation: %s", observation[:200])

        messages.append({"role": "assistant", "content": raw})
        messages.append({"role": "user", "content": f"Observation: {observation}"})

    fallback = (
        "Nie mogłem ukończyć zadania w wyznaczonym czasie. "
        "/ I could not complete the task within the allowed steps."
    )
    memory.add("assistant", fallback)
    return fallback
