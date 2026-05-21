# Contributing to HomeAI

## Adding a New Tool

Tools are the actions the LLM can take during the ReAct loop. Each tool is a self-contained async function that returns a `ToolResult`.

### Step 1 — Create the tool file

Create `src/homeai/tools/my_tool.py`:

```python
from __future__ import annotations

import logging

from homeai.tools.base import ToolResult

log = logging.getLogger(__name__)


async def my_tool(param_one: str, param_two: int = 5) -> ToolResult:
    """One-line description used by the tool registry."""
    try:
        # ... implementation using httpx.AsyncClient ...
        return ToolResult(ok=True, output=f"Result: {param_one}")
    except Exception as exc:
        log.exception("my_tool failed")
        return ToolResult(ok=False, output="", error=str(exc))
```

Rules:
- The function **must be async**.
- Return `ToolResult(ok=True, output=...)` on success and `ToolResult(ok=False, error=...)` on failure.
- Never raise exceptions out of a tool function. Catch them internally.
- Keep `output` to a readable, factual string under 500 characters. The LLM reads it verbatim as the observation.

### Step 2 — Register the tool schema

Open `src/homeai/prompts.py` and add an entry to `TOOL_SCHEMAS`:

```python
TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    # ... existing tools ...
    "my_tool": {
        "description": "One sentence — when should the LLM call this, and what will it return.",
        "parameters": {
            "param_one": "string — description of this parameter",
            "param_two": "integer (optional) — description, default 5",
        },
    },
}
```

Write the description from the model's perspective: *when should I call this?*

### Step 3 — Add the dispatch case

In `_dispatch()` in `src/homeai/agent_brain.py`:

```python
if action == "my_tool":
    param_one = action_input.get("param_one", "")
    if not param_one:
        return "Error: my_tool requires 'param_one'."
    result = await my_tool(param_one, action_input.get("param_two", 5))
    return result.output if result.ok else f"Tool error: {result.error}"
```

### Step 4 — Export from the tools package

Add to `src/homeai/tools/__init__.py`:

```python
from homeai.tools.my_tool import my_tool

__all__ = [..., "my_tool"]
```

### Step 5 — Write tests

Add tests to `tests/test_tools.py` covering the success path, failure path, and edge cases:

```python
@pytest.mark.asyncio
async def test_my_tool_success():
    """Returns ToolResult with ok=True on valid input."""
    result = await my_tool("example_input")
    assert result.ok
    assert "Result:" in result.output

@pytest.mark.asyncio
async def test_my_tool_error_handling():
    """Returns ToolResult with ok=False when dependency raises."""
    with patch("homeai.tools.my_tool.some_dep", side_effect=RuntimeError("fail")):
        result = await my_tool("example_input")
    assert not result.ok
    assert result.error is not None
```

---

## Adding a New Language

HomeAI uses the LLM's native multilingual capability. No ML training is required.

### Step 1 — Update the system prompt

Open `src/homeai/prompts.py` and extend the language instruction in `_SYSTEM_PROMPT_TEMPLATE`:

```python
# Before
"You understand both English and Polish perfectly."

# After (adding French)
"You understand English, Polish, and French perfectly."
```

### Step 2 — Add a spaCy model (if the full NLP pipeline is active)

```bash
python -m spacy download fr_core_news_sm
```

Register it in the language-to-model mapping in `agent_brain.py`:

```python
_SPACY_MODELS = {
    "pl": "pl_core_news_sm",
    "en": "en_core_web_sm",
    "fr": "fr_core_news_sm",
}
```

### Step 3 — Add test fixtures

Add labeled example commands in the new language to `tests/intent-fixtures/` for regression testing.

---

## Code Style

### Formatter and linter

```bash
ruff format src/ tests/       # format in place
ruff check src/ tests/        # lint
ruff check --fix src/ tests/  # lint with auto-fix
```

### Type checking

All code must pass mypy in strict mode:

```bash
mypy src/homeai --strict
```

Requirements:
- Every function must have annotated parameters and return type.
- Use `from __future__ import annotations` at the top of every module.
- Do not use `Any` unless interfacing with an external library that has no stubs.

### Async-first

All I/O must be async. Never call synchronous HTTP libraries (`requests`, `urllib`). Use `httpx.AsyncClient` with an explicit timeout.

```python
# Correct
async with httpx.AsyncClient(timeout=settings.ha_timeout_s) as client:
    resp = await client.get(url)

# Wrong — blocks the event loop
import requests
resp = requests.get(url)
```

### Error handling

Never use a bare `except`. Catch specific exceptions:

```python
# Correct
try:
    resp = await client.get(url)
    resp.raise_for_status()
except httpx.HTTPStatusError as exc:
    return ToolResult(ok=False, error=f"HTTP {exc.response.status_code}")
except httpx.RequestError as exc:
    return ToolResult(ok=False, error=f"Connection error: {exc}")

# Wrong
try:
    resp = await client.get(url)
except:
    return ToolResult(ok=False, error="something went wrong")
```

### Logging

Use the module-level logger, not `print`:

```python
import logging
log = logging.getLogger(__name__)

log.debug("detail only needed during development")
log.info("normal operational event")
log.warning("recoverable problem, execution continues")
log.error("non-recoverable error in this code path")
log.exception("error with full traceback — only inside except blocks")
```

### No secrets in code

Configuration is loaded exclusively through `Settings`. Never hardcode tokens, URLs, or credentials. Never commit `.env`.

---

## Pull Request Checklist

- [ ] `ruff format src/ tests/` produces no diff
- [ ] `ruff check src/ tests/` reports zero errors
- [ ] `mypy src/homeai --strict` reports zero errors
- [ ] `pytest tests/ -v` passes with no failures or new warnings
- [ ] New tools have tests covering success and failure paths
- [ ] New config variables are documented in `README.md` Configuration Reference
- [ ] No bare `except` clauses introduced
- [ ] No synchronous I/O introduced
- [ ] No secrets or personal data in any committed file
- [ ] PR description explains *why* the change is needed, not just what it does
