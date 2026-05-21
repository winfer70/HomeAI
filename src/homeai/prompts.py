from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Tool registry — the LLM reads these descriptions to decide what to call
# ---------------------------------------------------------------------------

TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
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
            "data": (
                'object (optional) — extra service params, '
                'e.g. {"temperature": 22, "brightness_pct": 60}'
            ),
        },
    },
    "home_state": {
        "description": (
            "Query the current state of any Home Assistant entity (sensor, switch, light, etc.)."
        ),
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


def build_tools_block() -> str:
    """Render the tool registry as an indented text block for inclusion in the system prompt."""
    lines: list[str] = []
    for name, schema in TOOL_SCHEMAS.items():
        lines.append(f"  {name}: {schema['description']}")
        for param, desc in schema["parameters"].items():
            lines.append(f"    - {param}: {desc}")
    return "\n".join(lines)
