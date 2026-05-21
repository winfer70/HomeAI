"""
test_agent_brain.py — unit tests for agent_brain internals and run_pipeline.

Strategy:
    - _extract_json is a pure function; tested synchronously with table-driven
      parametrize cases.
    - run_pipeline is async; _llm_step is patched with AsyncMock so no real
      Ollama connection is made.  _dispatch is also patched where a tool call
      path is exercised to avoid real HTTP calls.

Coverage:
    _extract_json:
        - Plain valid JSON object
        - JSON wrapped in ```json ... ``` fences
        - JSON wrapped in plain ``` ... ``` fences
        - JSON buried in prose before/after
        - Nested JSON object
        - Completely invalid text raises ValueError
        - Empty string raises ValueError
        - JSON with Polish string values parses correctly

    run_pipeline:
        - Direct final_answer on first iteration returns answer text
        - Single tool call (web_search) followed by final_answer
        - Single tool call (home_service) followed by final_answer
        - Single tool call (home_state) followed by final_answer
        - Unknown tool name handled gracefully
        - Malformed JSON on first response: pipeline retries then succeeds
        - Max iterations reached: returns bilingual fallback string
        - LLM raises RuntimeError: returns bilingual error string
        - final_answer with action_input as plain string (not dict)
        - User input stored in memory before pipeline runs
        - Final answer stored in memory after pipeline returns
        - Polish user input handled without error
        - Missing required tool parameter handled by _dispatch without crash
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import agent_brain
from agent_brain import Memory, _extract_json, run_pipeline


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_llm_response(thought: str, action: str, action_input: dict | str) -> str:
    """Serialize a well-formed ReAct step as a JSON string (what _llm_step returns)."""
    return json.dumps({"thought": thought, "action": action, "action_input": action_input})


def _final_answer(text: str) -> str:
    """Convenience: a final_answer LLM response string."""
    return _make_llm_response("Done.", "final_answer", {"text": text})


# ---------------------------------------------------------------------------
# _extract_json
# ---------------------------------------------------------------------------


class TestExtractJson:
    def test_plain_valid_json_object(self):
        """A bare JSON object string is parsed directly."""
        raw = '{"action": "final_answer", "action_input": {"text": "hi"}}'
        result = _extract_json(raw)
        assert result["action"] == "final_answer"

    def test_json_in_json_fences(self):
        """JSON wrapped in ```json ... ``` markdown fences is extracted."""
        raw = '```json\n{"action": "web_search", "action_input": {"query": "test"}}\n```'
        result = _extract_json(raw)
        assert result["action"] == "web_search"

    def test_json_in_plain_fences(self):
        """JSON wrapped in plain ``` ... ``` fences is extracted."""
        raw = '```\n{"action": "home_state", "action_input": {"entity_id": "x"}}\n```'
        result = _extract_json(raw)
        assert result["action"] == "home_state"

    def test_json_buried_in_prose_before_and_after(self):
        """When prose surrounds a JSON block, the first {...} is extracted."""
        raw = 'Some preamble text.\n{"action": "final_answer", "action_input": {"text": "ok"}}\nSome trailing text.'
        result = _extract_json(raw)
        assert result["action"] == "final_answer"

    def test_nested_json_object_parsed_correctly(self):
        """Nested dicts in action_input survive parsing intact."""
        raw = json.dumps({
            "thought": "need temp",
            "action": "home_service",
            "action_input": {
                "domain": "climate",
                "service": "set_temperature",
                "entity_id": "climate.hall",
                "data": {"temperature": 21},
            },
        })
        result = _extract_json(raw)
        assert result["action_input"]["data"]["temperature"] == 21

    def test_completely_invalid_text_raises_value_error(self):
        """Non-JSON text raises ValueError with a descriptive message."""
        with pytest.raises(ValueError, match="No valid JSON"):
            _extract_json("This is just plain English text with no JSON.")

    def test_empty_string_raises_value_error(self):
        """An empty string raises ValueError."""
        with pytest.raises(ValueError):
            _extract_json("")

    def test_whitespace_only_raises_value_error(self):
        """A string containing only whitespace raises ValueError."""
        with pytest.raises(ValueError):
            _extract_json("   \n\t  ")

    def test_polish_string_values_preserved(self):
        """Polish characters inside JSON values survive extraction."""
        raw = json.dumps({
            "thought": "Sprawdzam pogodę",
            "action": "final_answer",
            "action_input": {"text": "Dziś będzie słonecznie w Krakowie."},
        })
        result = _extract_json(raw)
        assert result["action_input"]["text"] == "Dziś będzie słonecznie w Krakowie."

    @pytest.mark.parametrize("raw", [
        '```json\n{"a": 1}\n```',
        '```JSON\n{"a": 1}\n```',
        '```\n{"a": 1}\n```',
        '  {"a": 1}  ',
    ])
    def test_various_fence_and_whitespace_variants(self, raw):
        """Several fence and whitespace variants all parse to the same dict."""
        result = _extract_json(raw)
        assert result == {"a": 1}

    def test_json_array_at_top_level_raises(self):
        """A top-level JSON array (not object) raises ValueError (pipeline expects dict)."""
        with pytest.raises((ValueError, AttributeError)):
            result = _extract_json("[1, 2, 3]")
            # If it parses as a list rather than dict, accessing .get would fail in pipeline.
            # We accept either a ValueError from _extract_json or an AttributeError later.
            result.get("action")  # type: ignore[union-attr]

    def test_two_separate_json_objects_in_prose_raises(self):
        """
        Two separate JSON objects on the same line cause the greedy re.DOTALL
        fallback regex to span from the first '{' to the last '}', yielding
        non-parseable text.  _extract_json raises ValueError in this case.
        A well-behaved LLM should never produce this, so raising is correct.
        """
        raw = '{"action": "first"} and {"action": "second"}'
        with pytest.raises(ValueError):
            _extract_json(raw)


# ---------------------------------------------------------------------------
# run_pipeline — fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mem():
    """Fresh in-memory Memory instance for pipeline tests."""
    m = Memory(":memory:", window=10)
    yield m
    m.close()


@pytest.fixture(autouse=True)
def patch_settings_pipeline(monkeypatch):
    """Ensure react_max_iterations is at the documented default of 6."""
    monkeypatch.setattr(agent_brain.settings, "react_max_iterations", 6)


# ---------------------------------------------------------------------------
# run_pipeline — happy path
# ---------------------------------------------------------------------------


class TestRunPipelineDirectAnswer:
    async def test_direct_final_answer_returns_text(self, mem):
        """LLM responds with final_answer on the first iteration; pipeline returns the text."""
        answer_text = "The lights are on."
        with patch.object(agent_brain, "_llm_step", new=AsyncMock(return_value=_final_answer(answer_text))):
            result = await run_pipeline("Are the lights on?", mem)
        assert result == answer_text

    async def test_direct_final_answer_polish_input(self, mem):
        """Polish-language user input and Polish answer text round-trip correctly."""
        answer_text = "Światła są włączone."
        with patch.object(agent_brain, "_llm_step", new=AsyncMock(return_value=_final_answer(answer_text))):
            result = await run_pipeline("Czy światła są włączone?", mem)
        assert result == answer_text

    async def test_final_answer_stored_in_memory(self, mem):
        """The final answer text is added to memory with role='assistant'."""
        answer_text = "Done."
        with patch.object(agent_brain, "_llm_step", new=AsyncMock(return_value=_final_answer(answer_text))):
            await run_pipeline("Do something.", mem)
        turns = mem.recent()
        assistant_turns = [t for t in turns if t["role"] == "assistant"]
        assert any(t["content"] == answer_text for t in assistant_turns)

    async def test_user_input_stored_in_memory(self, mem):
        """The user's input is added to memory before the LLM is called."""
        user_msg = "Turn off the boiler."
        with patch.object(agent_brain, "_llm_step", new=AsyncMock(return_value=_final_answer("OK"))):
            await run_pipeline(user_msg, mem)
        turns = mem.recent()
        user_turns = [t for t in turns if t["role"] == "user"]
        assert any(t["content"] == user_msg for t in user_turns)

    async def test_final_answer_action_input_as_string_not_dict(self, mem):
        """action_input that is a plain string (not dict) is converted via str()."""
        raw = json.dumps({"thought": "done", "action": "final_answer", "action_input": "plain string"})
        with patch.object(agent_brain, "_llm_step", new=AsyncMock(return_value=raw)):
            result = await run_pipeline("hi", mem)
        assert result == "plain string"


# ---------------------------------------------------------------------------
# run_pipeline — tool call then final answer
# ---------------------------------------------------------------------------


class TestRunPipelineToolCall:
    async def test_web_search_tool_call_then_final_answer(self, mem):
        """Pipeline calls web_search once, feeds the observation, then returns the final answer."""
        search_step = _make_llm_response(
            "I need to search.", "web_search", {"query": "current weather Warsaw"}
        )
        final_step = _final_answer("It is sunny in Warsaw.")

        llm_mock = AsyncMock(side_effect=[search_step, final_step])
        tool_mock = AsyncMock(return_value="Search results: sunny, 24°C")

        with patch.object(agent_brain, "_llm_step", new=llm_mock):
            with patch.object(agent_brain, "web_search", new=tool_mock):
                result = await run_pipeline("What's the weather in Warsaw?", mem)

        assert result == "It is sunny in Warsaw."
        tool_mock.assert_awaited_once_with("current weather Warsaw")

    async def test_home_service_tool_call_then_final_answer(self, mem):
        """Pipeline calls home_service and then produces a final answer."""
        service_step = _make_llm_response(
            "Turning on the light.",
            "home_service",
            {"domain": "light", "service": "turn_on", "entity_id": "light.hall"},
        )
        final_step = _final_answer("The hall light is now on.")

        llm_mock = AsyncMock(side_effect=[service_step, final_step])
        tool_mock = AsyncMock(return_value="OK: light.turn_on on light.hall succeeded.")

        with patch.object(agent_brain, "_llm_step", new=llm_mock):
            with patch.object(agent_brain, "home_service", new=tool_mock):
                result = await run_pipeline("Turn on the hall light.", mem)

        assert result == "The hall light is now on."

    async def test_home_state_tool_call_then_final_answer(self, mem):
        """Pipeline calls home_state and then produces a final answer."""
        state_step = _make_llm_response(
            "Checking temperature.",
            "home_state",
            {"entity_id": "sensor.bedroom_temp"},
        )
        final_step = _final_answer("The bedroom is 21°C.")

        llm_mock = AsyncMock(side_effect=[state_step, final_step])
        tool_mock = AsyncMock(return_value="Bedroom Temp (sensor.bedroom_temp): state=21 | {}")

        with patch.object(agent_brain, "_llm_step", new=llm_mock):
            with patch.object(agent_brain, "home_state", new=tool_mock):
                result = await run_pipeline("What's the bedroom temperature?", mem)

        assert result == "The bedroom is 21°C."

    async def test_observation_fed_back_to_llm(self, mem):
        """The tool observation is passed back to _llm_step in the next message."""
        search_step = _make_llm_response("searching", "web_search", {"query": "news"})
        final_step = _final_answer("Here is the news.")

        captured_messages: list = []

        async def capture_llm(messages):
            captured_messages.append(list(messages))
            if len(captured_messages) == 1:
                return search_step
            return final_step

        tool_mock = AsyncMock(return_value="Top story: something happened")

        with patch.object(agent_brain, "_llm_step", new=capture_llm):
            with patch.object(agent_brain, "web_search", new=tool_mock):
                await run_pipeline("Give me news.", mem)

        # The second LLM call should have an "Observation: ..." user message
        second_call_messages = captured_messages[1]
        observation_msgs = [m for m in second_call_messages if "Observation:" in m.get("content", "")]
        assert len(observation_msgs) == 1
        assert "Top story: something happened" in observation_msgs[0]["content"]

    async def test_unknown_tool_name_returns_error_observation(self, mem):
        """An unknown action name is handled by _dispatch without crashing the pipeline."""
        bad_tool_step = _make_llm_response("trying unknown tool", "nonexistent_tool", {"x": 1})
        final_step = _final_answer("Recovered.")

        llm_mock = AsyncMock(side_effect=[bad_tool_step, final_step])

        with patch.object(agent_brain, "_llm_step", new=llm_mock):
            result = await run_pipeline("Do something.", mem)

        # Pipeline should still return the final answer after recovering
        assert result == "Recovered."


# ---------------------------------------------------------------------------
# run_pipeline — malformed JSON recovery
# ---------------------------------------------------------------------------


class TestRunPipelineMalformedJson:
    async def test_malformed_json_triggers_retry_then_succeeds(self, mem, monkeypatch):
        """Malformed JSON from LLM causes a retry message; subsequent valid JSON succeeds."""
        monkeypatch.setattr(agent_brain.settings, "react_max_iterations", 6)

        bad_response = "This is definitely not JSON at all."
        good_response = _final_answer("I recovered.")

        llm_mock = AsyncMock(side_effect=[bad_response, good_response])

        with patch.object(agent_brain, "_llm_step", new=llm_mock):
            result = await run_pipeline("hi", mem)

        assert result == "I recovered."
        assert llm_mock.await_count == 2

    async def test_retry_message_asks_for_json_only(self, mem):
        """After malformed JSON, the pipeline appends a 'JSON only' instruction."""
        bad_response = "not json"
        good_response = _final_answer("fixed")

        captured: list[list[dict]] = []

        async def capture_llm(messages):
            captured.append(list(messages))
            if len(captured) == 1:
                return bad_response
            return good_response

        with patch.object(agent_brain, "_llm_step", new=capture_llm):
            await run_pipeline("test", mem)

        retry_messages = captured[1]
        last_user = next(
            (m for m in reversed(retry_messages) if m["role"] == "user"), None
        )
        assert last_user is not None
        assert "JSON" in last_user["content"]


# ---------------------------------------------------------------------------
# run_pipeline — max iterations reached
# ---------------------------------------------------------------------------


class TestRunPipelineMaxIterations:
    async def test_max_iterations_returns_bilingual_fallback(self, mem, monkeypatch):
        """When max iterations are exhausted, the bilingual fallback string is returned."""
        monkeypatch.setattr(agent_brain.settings, "react_max_iterations", 3)

        # Always return a tool call so final_answer is never reached
        tool_step = _make_llm_response("searching", "web_search", {"query": "x"})
        llm_mock = AsyncMock(return_value=tool_step)
        tool_mock = AsyncMock(return_value="some observation")

        with patch.object(agent_brain, "_llm_step", new=llm_mock):
            with patch.object(agent_brain, "web_search", new=tool_mock):
                result = await run_pipeline("infinite loop", mem)

        assert "Nie mogłem" in result or "could not complete" in result.lower()

    async def test_max_iterations_fallback_stored_in_memory(self, mem, monkeypatch):
        """The fallback string is stored in memory as an assistant turn."""
        monkeypatch.setattr(agent_brain.settings, "react_max_iterations", 2)

        tool_step = _make_llm_response("searching", "web_search", {"query": "x"})
        llm_mock = AsyncMock(return_value=tool_step)
        tool_mock = AsyncMock(return_value="obs")

        with patch.object(agent_brain, "_llm_step", new=llm_mock):
            with patch.object(agent_brain, "web_search", new=tool_mock):
                fallback = await run_pipeline("loop", mem)

        assistant_turns = [t for t in mem.recent() if t["role"] == "assistant"]
        assert any(t["content"] == fallback for t in assistant_turns)

    async def test_llm_called_exactly_max_iterations_times(self, mem, monkeypatch):
        """_llm_step is invoked exactly react_max_iterations times before giving up."""
        monkeypatch.setattr(agent_brain.settings, "react_max_iterations", 4)

        tool_step = _make_llm_response("still going", "web_search", {"query": "q"})
        llm_mock = AsyncMock(return_value=tool_step)
        tool_mock = AsyncMock(return_value="obs")

        with patch.object(agent_brain, "_llm_step", new=llm_mock):
            with patch.object(agent_brain, "web_search", new=tool_mock):
                await run_pipeline("keep going", mem)

        assert llm_mock.await_count == 4


# ---------------------------------------------------------------------------
# run_pipeline — LLM error handling
# ---------------------------------------------------------------------------


class TestRunPipelineLlmError:
    async def test_llm_runtime_error_returns_bilingual_error_string(self, mem):
        """A RuntimeError from _llm_step returns the bilingual connection-error message."""
        llm_mock = AsyncMock(side_effect=RuntimeError("Ollama connection error: refused"))

        with patch.object(agent_brain, "_llm_step", new=llm_mock):
            result = await run_pipeline("anything", mem)

        assert "Przepraszam" in result or "Sorry" in result

    async def test_llm_error_stores_error_string_in_memory(self, mem):
        """The error message is stored in memory so context is preserved."""
        llm_mock = AsyncMock(side_effect=RuntimeError("connection refused"))

        with patch.object(agent_brain, "_llm_step", new=llm_mock):
            error_result = await run_pipeline("test", mem)

        assistant_turns = [t for t in mem.recent() if t["role"] == "assistant"]
        assert any(t["content"] == error_result for t in assistant_turns)


# ---------------------------------------------------------------------------
# run_pipeline — _dispatch parameter validation
# ---------------------------------------------------------------------------


class TestRunPipelineDispatchValidation:
    async def test_web_search_missing_query_returns_error_observation(self, mem):
        """web_search called without 'query' key returns an error observation string."""
        bad_step = _make_llm_response("searching", "web_search", {})
        final_step = _final_answer("Handled missing query.")

        llm_mock = AsyncMock(side_effect=[bad_step, final_step])

        with patch.object(agent_brain, "_llm_step", new=llm_mock):
            result = await run_pipeline("search with no query", mem)

        # Pipeline should survive and return the final answer
        assert result == "Handled missing query."

    async def test_home_state_missing_entity_id_returns_error_observation(self, mem):
        """home_state called without 'entity_id' returns an error observation string."""
        bad_step = _make_llm_response("checking state", "home_state", {})
        final_step = _final_answer("Handled missing entity_id.")

        llm_mock = AsyncMock(side_effect=[bad_step, final_step])

        with patch.object(agent_brain, "_llm_step", new=llm_mock):
            result = await run_pipeline("state with no entity", mem)

        assert result == "Handled missing entity_id."

    async def test_home_service_missing_domain_returns_error_observation(self, mem):
        """home_service without 'domain' returns an error observation string."""
        bad_step = _make_llm_response("calling service", "home_service", {"service": "turn_on", "entity_id": "x"})
        final_step = _final_answer("Handled missing domain.")

        llm_mock = AsyncMock(side_effect=[bad_step, final_step])

        with patch.object(agent_brain, "_llm_step", new=llm_mock):
            result = await run_pipeline("service with no domain", mem)

        assert result == "Handled missing domain."


# ---------------------------------------------------------------------------
# run_pipeline — memory context injection
# ---------------------------------------------------------------------------


class TestRunPipelineMemoryContext:
    async def test_prior_memory_turns_included_in_first_llm_call(self, mem):
        """Existing memory turns appear in the messages list sent to _llm_step."""
        mem.add("user", "previous question")
        mem.add("assistant", "previous answer")

        captured: list[list[dict]] = []

        async def capture_llm(messages):
            captured.append(list(messages))
            return _final_answer("ok")

        with patch.object(agent_brain, "_llm_step", new=capture_llm):
            await run_pipeline("new question", mem)

        first_call = captured[0]
        contents = [m["content"] for m in first_call]
        assert "previous question" in contents
        assert "previous answer" in contents

    async def test_system_prompt_is_first_message(self, mem):
        """The system prompt is always the first message in the LLM call."""
        captured: list[list[dict]] = []

        async def capture_llm(messages):
            captured.append(list(messages))
            return _final_answer("ok")

        with patch.object(agent_brain, "_llm_step", new=capture_llm):
            await run_pipeline("hi", mem)

        first_msg = captured[0][0]
        assert first_msg["role"] == "system"
        assert "HomeAI" in first_msg["content"]
