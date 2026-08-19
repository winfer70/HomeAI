"""Heimdall Restricted LLM API.

Home Assistant's entity-exposure system ("Expose to Assist") has no
per-conversation-agent scoping: every conversation agent that selects the
built-in "assist" LLM API sees the exact same set of exposed entities and
scripts (see homeassistant.components.homeassistant.exposed_entities). There
is no config-level way to give the local model (qwen2.5:7b-instruct) a
different tool set than Gemini.

This integration registers a second LLM API ("heimdall_restricted") that
internally reuses the *exact same* tool-gathering logic as the built-in
"assist" API - every integration's llm.py platform (script, calendar,
homeassistant/GetLiveContext, etc.) still contributes tools normally,
because we query them with the real "assist" api_id. The only difference is
that a small, explicit blocklist of tool names is filtered out of the
result before it's returned.

Why this exists: qwen2.5:7b-instruct was found (Heimdall Task 5) to be
unreliable when calling `heimdall_create_calendar_event` - even after
system-prompt date-grounding fixed its wrong-year bug, it still sometimes
called the write tool when the user actually asked to *read* the calendar
(risking silent creation of blank/garbage events) and miscalculated
relative-date words like the Polish "pojutrze". Gemini has never shown
either bug. Rather than removing the feature or exposing it identically to
both agents (accepting an unreliable local write-tool with real
side-effects), the local model's conversation subentry is pointed at this
restricted API (`llm_hass_api: heimdall_restricted`) so it keeps every
other Heimdall tool (lights, TRVs, gate, aquarium, memory, calendar
*reads*) but simply doesn't see the calendar *write* tool at all. Gemini's
subentry keeps `llm_hass_api: assist` and is unaffected.

To add another tool to the blocklist later (e.g. if a future write-only
tool turns out to be similarly unreliable for the local model), just add
its script object_id to HIDDEN_TOOL_NAMES below - no other change needed.

Deployment: this directory must be copied to HA's own
`config/custom_components/heimdall_llm_api/` (it lives here in the repo for
version control and review, not for automatic deployment - see
heimdall/HA_CONFIG_CHANGES.md for the exact steps). Registering a new LLM
API requires a full Home Assistant restart to take effect (custom
integrations are only discovered at startup).
"""

from __future__ import annotations

import logging
from typing import override

from homeassistant.components.llm import async_get_tools
from homeassistant.core import HomeAssistant
from homeassistant.helpers.llm import (
    API,
    LLM_API_ASSIST,
    APIInstance,
    LLMContext,
    async_register_api,
    selector_serializer,
)
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "heimdall_llm_api"
API_ID = "heimdall_restricted"

# Script object_ids hidden from this restricted API. Currently just the
# calendar-write tool (see module docstring for why).
HIDDEN_TOOL_NAMES = {"heimdall_create_calendar_event"}


class HeimdallRestrictedAPI(API):
    """Same tools as "assist", minus HIDDEN_TOOL_NAMES."""

    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(hass=hass, id=API_ID, name="Heimdall Restricted")

    @override
    async def async_get_api_instance(self, llm_context: LLMContext) -> APIInstance:
        # Query every integration's llm.py platform with the *real* "assist"
        # api_id - they all gate on `api_id == LLM_API_ASSIST` internally, so
        # passing our own id here would silently return zero tools.
        llm_tools = await async_get_tools(self.hass, llm_context, LLM_API_ASSIST)

        filtered_tools = [
            tool for tool in llm_tools.tools if tool.name not in HIDDEN_TOOL_NAMES
        ]
        hidden_count = len(llm_tools.tools) - len(filtered_tools)
        if hidden_count:
            _LOGGER.debug(
                "heimdall_restricted API: hid %d tool(s) matching %s",
                hidden_count,
                HIDDEN_TOOL_NAMES,
            )

        return APIInstance(
            api=self,
            api_prompt=llm_tools.prompt or "",
            llm_context=llm_context,
            tools=filtered_tools,
            custom_serializer=selector_serializer,
        )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the Heimdall restricted LLM API."""
    async_register_api(hass, HeimdallRestrictedAPI(hass))
    return True
