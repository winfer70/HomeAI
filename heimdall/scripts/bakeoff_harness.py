#!/usr/bin/env python3
"""Task 3 bake-off harness: compare candidate local models on tool-calling.

Sends each prompt in heimdall/tests/bakeoff_prompts.json to every candidate
model via Ollama's /api/chat with a tool schema built from Heimdall's
currently-exposed entities (see expose_entities.py) plus a placeholder
calendar tool (Task 5 isn't built yet, but calendar-intent tool-calling can
still be scored the same way). Records tool-call correctness, latency, and
the raw response for every (model, prompt) pair into heimdall/BAKEOFF_RESULTS.md.

Usage:
    python bakeoff_harness.py [--host jaskier-ip] [--models m1,m2,m3]

Requires the candidate models to already be pulled on the Ollama host
(verified manually for qwen2.5:7b-instruct, qwen2.5-coder:7b, deepseek-r1:8b
on jaskier before running this - see Task 3 notes).
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_HOST = "192.168.0.125"
DEFAULT_PORT = 11434
DEFAULT_MODELS = ["qwen2.5:7b-instruct", "qwen2.5-coder:7b", "deepseek-r1:8b"]

REPO_ROOT = Path(__file__).resolve().parents[2]
PROMPTS_PATH = REPO_ROOT / "heimdall" / "tests" / "bakeoff_prompts.json"
RESULTS_PATH = REPO_ROOT / "heimdall" / "BAKEOFF_RESULTS.md"

SYSTEM_PROMPT = (
    "You are Heimdall, a bilingual (Polish/English) home assistant. The user "
    "may speak either language - always understand the request regardless of "
    "language and respond by calling the single most appropriate tool. Only "
    "use entity_ids that are explicitly listed in each tool's enum. Do not "
    "explain your reasoning in plain text if a tool call is possible - just "
    "call the tool."
)

# Tool schema built from the entities actually exposed to Assist in Task 3
# (see heimdall/scripts/expose_entities.py) plus aquarium switches/sensors
# that already exist in HA (ahead of Task 4's dedicated aquarium API) and a
# placeholder calendar tool (ahead of Task 5).
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "control_switch",
            "description": (
                "Turn a light or aquarium switch on or off."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {
                        "type": "string",
                        "enum": [
                            "switch.0x54ef4410016759d1_up",  # BiuroSwiatłoGłówne
                            "switch.0x54ef44100167601c_up",  # SypialniaŚwiatłoGłówne
                            "switch.0x54ef4410015687f1_left",  # WłącznikSalon fireplace
                            "switch.0x54ef4410015687f1_right",  # WłącznikSalon main light
                            "switch.0x54ef441001525ff8_up",  # WłącznikKuchniaLed
                            "switch.0x54ef44100156879e_left",  # WłącznikDółDrzwi light
                            "switch.0x54ef44100156879e_right",  # WłącznikDółDrzwi light
                            "switch.grzalka",  # aquarium heater
                            "switch.filtr",  # aquarium filter
                            "switch.pompka",  # aquarium pump
                            "switch.0xa4c1380f6229ffff",  # WtyczkaAkwarium
                        ],
                    },
                    "state": {"type": "string", "enum": ["on", "off"]},
                },
                "required": ["entity_id", "state"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_climate_temperature",
            "description": "Set the target temperature of a TRV/heating entity.",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {
                        "type": "string",
                        "enum": [
                            "climate.0xa4c138b1ad7dfd57",  # GrzejnikSypialniaGóra
                            "climate.0xa4c138c7970d8809",  # GrzejnikBiuro
                            "climate.0xa4c1387c4f428097",  # GrzejnikŁazienkaGóraOkno
                            "climate.0xa4c13881297bc097",  # GrzejnikŁazienkaGóraDrzwi
                            "climate.0x001e5e0902ce8e9a",  # Ogrzewanie
                        ],
                    },
                    "temperature": {"type": "number"},
                },
                "required": ["entity_id", "temperature"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_sensor_state",
            "description": "Read the current value of a read-only sensor.",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {
                        "type": "string",
                        "enum": [
                            "sensor.0xa4c138060885ffff_temperature",  # Termometr (aquarium)
                            "binary_sensor.0x54ef441001548c9b_water_leak",  # CzujkaWodyAkwarium
                        ],
                    }
                },
                "required": ["entity_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_calendar_event",
            "description": "Create a calendar event (placeholder ahead of Task 5).",
            "parameters": {
                "type": "object",
                "properties": {
                    "calendar": {"type": "string", "enum": ["kamil", "marzena"]},
                    "title": {"type": "string"},
                    "start_time": {"type": "string"},
                    "end_time": {"type": "string"},
                },
                "required": ["calendar", "title", "start_time"],
            },
        },
    },
]


@dataclass
class PromptResult:
    prompt_id: str
    model: str
    language: str
    category: str
    prompt_text: str
    correct: bool
    latency_seconds: float
    tool_called: str | None
    arguments: dict[str, Any] | None
    raw_message: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


def call_ollama(host: str, port: int, model: str, prompt: str, timeout: int = 120) -> tuple[dict, float]:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "tools": TOOLS,
        "stream": False,
    }
    req = urllib.request.Request(
        f"http://{host}:{port}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    start = time.monotonic()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.load(resp)
    elapsed = time.monotonic() - start
    return body, elapsed


def evaluate(prompt_spec: dict, model: str, response_body: dict, elapsed: float) -> PromptResult:
    message = response_body.get("message", {})
    tool_calls = message.get("tool_calls") or []

    tool_called = None
    arguments: dict[str, Any] | None = None
    if tool_calls:
        first_call = tool_calls[0]["function"]
        tool_called = first_call.get("name")
        arguments = first_call.get("arguments") or {}

    correct = tool_called == prompt_spec["expected_tool"]

    if correct and "expected_entity_id" in prompt_spec:
        correct = (arguments or {}).get("entity_id") == prompt_spec["expected_entity_id"]

    if correct and "expected_state" in prompt_spec:
        correct = (arguments or {}).get("state") == prompt_spec["expected_state"]

    if correct and "expected_temperature" in prompt_spec:
        try:
            correct = float((arguments or {}).get("temperature")) == float(
                prompt_spec["expected_temperature"]
            )
        except (TypeError, ValueError):
            correct = False

    if correct and "expected_title_contains" in prompt_spec:
        title = str((arguments or {}).get("title", "")).lower()
        correct = prompt_spec["expected_title_contains"].lower() in title

    return PromptResult(
        prompt_id=prompt_spec["id"],
        model=model,
        language=prompt_spec["language"],
        category=prompt_spec["category"],
        prompt_text=prompt_spec["prompt"],
        correct=correct,
        latency_seconds=elapsed,
        tool_called=tool_called,
        arguments=arguments,
        raw_message=message,
    )


def run_bakeoff(host: str, port: int, models: list[str], prompts: list[dict]) -> list[PromptResult]:
    results: list[PromptResult] = []
    for model in models:
        for prompt_spec in prompts:
            try:
                body, elapsed = call_ollama(host, port, model, prompt_spec["prompt"])
                result = evaluate(prompt_spec, model, body, elapsed)
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                result = PromptResult(
                    prompt_id=prompt_spec["id"],
                    model=model,
                    language=prompt_spec["language"],
                    category=prompt_spec["category"],
                    prompt_text=prompt_spec["prompt"],
                    correct=False,
                    latency_seconds=0.0,
                    tool_called=None,
                    arguments=None,
                    error=str(exc),
                )
            results.append(result)
            status = "OK" if result.correct else "MISS"
            print(f"[{model}] {prompt_spec['id']}: {status} ({result.latency_seconds:.2f}s)")
    return results


def write_results_md(results: list[PromptResult], models: list[str]) -> None:
    lines = ["# Heimdall Task 3 Bake-off Results", ""]
    lines.append(
        "Generated by `heimdall/scripts/bakeoff_harness.py` against the tool "
        "schema built from Task 3's exposed entities. Scores are exact-match "
        "on tool name + arguments against `heimdall/tests/bakeoff_prompts.json`."
    )
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append("| Model | Correct | Total | Score | Avg latency (s) |")
    lines.append("|---|---|---|---|---|")
    for model in models:
        model_results = [r for r in results if r.model == model]
        correct = sum(r.correct for r in model_results)
        total = len(model_results)
        timed = [r.latency_seconds for r in model_results if r.latency_seconds > 0]
        avg_latency = sum(timed) / len(timed) if timed else 0.0
        lines.append(
            f"| {model} | {correct} | {total} | {correct}/{total} | {avg_latency:.2f} |"
        )
    lines.append("")

    winner = max(
        models,
        key=lambda m: sum(r.correct for r in results if r.model == m),
    )
    lines.append(f"**Winner: `{winner}`** (highest correct tool-call count; see per-prompt detail below for ties/edge cases.)")
    lines.append("")

    lines.append("## Per-prompt detail")
    lines.append("")
    lines.append("| Model | Prompt ID | Lang | Category | Correct | Tool called | Arguments | Latency (s) | Error |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for r in results:
        args_str = json.dumps(r.arguments, ensure_ascii=False) if r.arguments else ""
        lines.append(
            f"| {r.model} | {r.prompt_id} | {r.language} | {r.category} | "
            f"{'✅' if r.correct else '❌'} | {r.tool_called or ''} | "
            f"{args_str} | {r.latency_seconds:.2f} | {r.error or ''} |"
        )
    lines.append("")

    lines.append("## Raw prompts used")
    lines.append("")
    lines.append("See `heimdall/tests/bakeoff_prompts.json` for the full prompt set "
                  "and expected tool/argument values.")
    lines.append("")

    RESULTS_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote {RESULTS_PATH}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Task 3 model bake-off.")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Ollama host (default: jaskier)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--models",
        default=",".join(DEFAULT_MODELS),
        help="Comma-separated candidate model names.",
    )
    args = parser.parse_args()

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    prompts = json.loads(PROMPTS_PATH.read_text(encoding="utf-8"))

    results = run_bakeoff(args.host, args.port, models, prompts)
    write_results_md(results, models)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
