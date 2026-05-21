"""
test_tools.py — unit tests for tools.web_search, tools.home_service,
and tools.home_state.

All HTTP calls are intercepted with `respx` (async httpx mock router).
No real network traffic is made.

Coverage:
    web_search:
        - SearXNG success — results formatted correctly
        - SearXNG returns empty results list
        - SearXNG HTTP error triggers Brave fallback (with key configured)
        - SearXNG connection refused triggers Brave fallback
        - Both SearXNG and Brave unavailable — returns graceful string
        - Brave configured, SearXNG URL empty — goes straight to Brave
        - Polish-character query preserved in output
        - search_results limit respected

    home_service:
        - 200 OK returns success string
        - HTTP 401 Unauthorized returns error string with status code
        - HTTP 403 Forbidden returns error string
        - Connection refused returns connection-error string
        - Extra `data` dict merged into payload
        - Missing entity_id parameter handled by _dispatch (not tested here)

    home_state:
        - 200 with full attributes returns formatted string
        - friendly_name excluded from attr_summary but used in prefix
        - 404 Not Found returns error string
        - Connection refused returns error string
        - Attributes summary truncated at 400 chars
        - Polish entity friendly_name preserved
"""
from __future__ import annotations

import json

import httpx
import pytest
import respx

import config as cfg_module
import tools as tools_module
from tools import home_service, home_state, web_search


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SEARXNG_BASE = "http://searxng.test:8888"
BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"
HA_BASE = "http://ha.test:8123"


@pytest.fixture(autouse=True)
def patch_settings(monkeypatch):
    """
    Redirect all outgoing URLs to test doubles and inject a dummy HA token.
    autouse=True means every test in this file gets it automatically.
    """
    monkeypatch.setattr(cfg_module.settings, "searxng_url", SEARXNG_BASE)
    monkeypatch.setattr(cfg_module.settings, "brave_api_key", "")
    monkeypatch.setattr(cfg_module.settings, "search_results", 3)
    monkeypatch.setattr(cfg_module.settings, "search_timeout_s", 5)
    monkeypatch.setattr(cfg_module.settings, "ha_url", HA_BASE)
    monkeypatch.setattr(cfg_module.settings, "ha_token", "test-token")
    monkeypatch.setattr(cfg_module.settings, "ha_timeout_s", 5)
    monkeypatch.setitem(tools_module._HA_HEADERS, "Authorization", "Bearer test-token")


# ---------------------------------------------------------------------------
# web_search — SearXNG success paths
# ---------------------------------------------------------------------------


class TestWebSearchSearXNG:
    @respx.mock
    async def test_searxng_success_returns_formatted_results(self):
        """SearXNG 200 with results produces a numbered list prefixed by query."""
        payload = {
            "results": [
                {"title": "Title One", "url": "https://one.example.com", "content": "Snippet one"},
                {"title": "Title Two", "url": "https://two.example.com", "content": "Snippet two"},
            ]
        }
        respx.get(f"{SEARXNG_BASE}/search").mock(
            return_value=httpx.Response(200, json=payload)
        )

        result = await web_search("pytest testing")

        assert "pytest testing" in result
        assert "[1]" in result
        assert "Title One" in result
        assert "https://one.example.com" in result
        assert "Snippet one" in result
        assert "[2]" in result

    @respx.mock
    async def test_searxng_result_count_capped_at_search_results_setting(self):
        """Only `search_results` (3) results are included even if SearXNG returns more."""
        payload = {
            "results": [
                {"title": f"T{i}", "url": f"https://x{i}.com", "content": f"S{i}"}
                for i in range(6)
            ]
        }
        respx.get(f"{SEARXNG_BASE}/search").mock(
            return_value=httpx.Response(200, json=payload)
        )

        result = await web_search("anything")

        assert "[3]" in result
        assert "[4]" not in result

    @respx.mock
    async def test_searxng_empty_results_returns_no_results_message(self):
        """SearXNG 200 with empty results list returns a 'no results' string."""
        respx.get(f"{SEARXNG_BASE}/search").mock(
            return_value=httpx.Response(200, json={"results": []})
        )

        result = await web_search("very obscure query")

        assert "no results" in result.lower() or "SearXNG returned no results" in result

    @respx.mock
    async def test_searxng_uses_snippet_field_as_fallback_for_content(self):
        """When 'content' is absent, 'snippet' is used instead."""
        payload = {
            "results": [
                {"title": "T", "url": "https://t.com", "snippet": "fallback snippet"}
            ]
        }
        respx.get(f"{SEARXNG_BASE}/search").mock(
            return_value=httpx.Response(200, json=payload)
        )

        result = await web_search("something")

        assert "fallback snippet" in result

    @respx.mock
    async def test_searxng_query_preserved_with_polish_characters(self):
        """A query containing Polish diacritics appears verbatim in the output."""
        payload = {
            "results": [
                {"title": "Pogoda", "url": "https://pogoda.pl", "content": "Dziś deszcz."}
            ]
        }
        respx.get(f"{SEARXNG_BASE}/search").mock(
            return_value=httpx.Response(200, json=payload)
        )

        result = await web_search("pogoda Kraków jutro")

        assert "pogoda Kraków jutro" in result
        assert "Dziś deszcz." in result


# ---------------------------------------------------------------------------
# web_search — Brave fallback paths
# ---------------------------------------------------------------------------


class TestWebSearchBraveFallback:
    @respx.mock
    async def test_searxng_http_error_falls_back_to_brave(self, monkeypatch):
        """A 500 from SearXNG triggers a silent fallback to Brave Search."""
        monkeypatch.setattr(cfg_module.settings, "brave_api_key", "bravesecret")

        respx.get(f"{SEARXNG_BASE}/search").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )
        brave_payload = {
            "web": {
                "results": [
                    {"title": "Brave Result", "url": "https://brave.com", "description": "desc"}
                ]
            }
        }
        respx.get(BRAVE_URL).mock(return_value=httpx.Response(200, json=brave_payload))

        result = await web_search("test query")

        assert "Brave Result" in result

    @respx.mock
    async def test_searxng_connection_refused_falls_back_to_brave(self, monkeypatch):
        """A ConnectError from SearXNG triggers the Brave fallback."""
        monkeypatch.setattr(cfg_module.settings, "brave_api_key", "bravesecret")

        respx.get(f"{SEARXNG_BASE}/search").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        brave_payload = {
            "web": {
                "results": [
                    {"title": "Brave Only", "url": "https://brave.com", "description": "info"}
                ]
            }
        }
        respx.get(BRAVE_URL).mock(return_value=httpx.Response(200, json=brave_payload))

        result = await web_search("fallback test")

        assert "Brave Only" in result

    @respx.mock
    async def test_brave_used_directly_when_searxng_url_empty(self, monkeypatch):
        """When searxng_url is empty, Brave is the only path attempted."""
        monkeypatch.setattr(cfg_module.settings, "searxng_url", "")
        monkeypatch.setattr(cfg_module.settings, "brave_api_key", "bravesecret")

        brave_payload = {
            "web": {
                "results": [
                    {"title": "Direct Brave", "url": "https://b.com", "description": "x"}
                ]
            }
        }
        respx.get(BRAVE_URL).mock(return_value=httpx.Response(200, json=brave_payload))

        result = await web_search("direct brave")

        assert "Direct Brave" in result

    @respx.mock
    async def test_brave_no_results_returns_no_results_string(self, monkeypatch):
        """Brave 200 with empty web results returns 'No results found.'"""
        monkeypatch.setattr(cfg_module.settings, "searxng_url", "")
        monkeypatch.setattr(cfg_module.settings, "brave_api_key", "bravesecret")

        respx.get(BRAVE_URL).mock(
            return_value=httpx.Response(200, json={"web": {"results": []}})
        )

        result = await web_search("noresults")

        assert "No results found" in result


# ---------------------------------------------------------------------------
# web_search — both sources down
# ---------------------------------------------------------------------------


class TestWebSearchBothDown:
    @respx.mock
    async def test_both_unavailable_returns_graceful_message(self, monkeypatch):
        """When SearXNG is down and no Brave key, return an unavailability notice."""
        monkeypatch.setattr(cfg_module.settings, "brave_api_key", "")

        respx.get(f"{SEARXNG_BASE}/search").mock(
            side_effect=httpx.ConnectError("refused")
        )

        result = await web_search("lost query")

        assert "unavailable" in result.lower() or "Could not retrieve" in result

    @respx.mock
    async def test_both_sources_error_query_preserved_in_message(self, monkeypatch):
        """The original query string appears in the unavailability fallback message."""
        monkeypatch.setattr(cfg_module.settings, "brave_api_key", "")

        respx.get(f"{SEARXNG_BASE}/search").mock(
            side_effect=httpx.ConnectError("refused")
        )

        result = await web_search("zapytanie po polsku")

        assert "zapytanie po polsku" in result


# ---------------------------------------------------------------------------
# home_service
# ---------------------------------------------------------------------------


class TestHomeService:
    @respx.mock
    async def test_success_returns_ok_string(self):
        """A 200 from HA services endpoint returns a success confirmation string."""
        url = f"{HA_BASE}/api/services/light/turn_on"
        respx.post(url).mock(return_value=httpx.Response(200, json=[]))

        result = await home_service("light", "turn_on", "light.kitchen")

        assert "OK" in result
        assert "light.turn_on" in result
        assert "light.kitchen" in result

    @respx.mock
    async def test_http_401_returns_error_with_status_code(self):
        """HA returning 401 Unauthorized is surfaced as a string with the status code."""
        url = f"{HA_BASE}/api/services/light/turn_on"
        respx.post(url).mock(
            return_value=httpx.Response(401, text="Unauthorized")
        )

        result = await home_service("light", "turn_on", "light.kitchen")

        assert "401" in result
        assert "error" in result.lower() or "Error" in result

    @respx.mock
    async def test_http_403_returns_error_with_status_code(self):
        """HA returning 403 Forbidden surfaces the status code in the return string."""
        url = f"{HA_BASE}/api/services/switch/turn_off"
        respx.post(url).mock(
            return_value=httpx.Response(403, text="Forbidden")
        )

        result = await home_service("switch", "turn_off", "switch.boiler")

        assert "403" in result

    @respx.mock
    async def test_connection_refused_returns_connection_error_string(self):
        """A ConnectError is returned as a human-readable connection-error string."""
        url = f"{HA_BASE}/api/services/climate/set_temperature"
        respx.post(url).mock(side_effect=httpx.ConnectError("refused"))

        result = await home_service("climate", "set_temperature", "climate.living_room")

        assert "connection error" in result.lower() or "HA connection error" in result

    @respx.mock
    async def test_extra_data_dict_is_accepted(self):
        """Extra `data` kwargs are forwarded without error and success is reported."""
        url = f"{HA_BASE}/api/services/climate/set_temperature"
        respx.post(url).mock(return_value=httpx.Response(200, json=[]))

        result = await home_service(
            "climate",
            "set_temperature",
            "climate.bedroom",
            data={"temperature": 22, "hvac_mode": "heat"},
        )

        assert "OK" in result

    @respx.mock
    async def test_service_call_for_cover_domain(self):
        """home_service works for arbitrary HA domains (e.g., cover/open_cover)."""
        url = f"{HA_BASE}/api/services/cover/open_cover"
        respx.post(url).mock(return_value=httpx.Response(200, json=[]))

        result = await home_service("cover", "open_cover", "cover.garage_door")

        assert "cover.open_cover" in result
        assert "cover.garage_door" in result

    @respx.mock
    async def test_response_text_included_in_http_error(self):
        """The first 300 chars of HA error body appear in the returned error string."""
        url = f"{HA_BASE}/api/services/light/turn_on"
        respx.post(url).mock(
            return_value=httpx.Response(400, text="Invalid entity_id format")
        )

        result = await home_service("light", "turn_on", "bad entity")

        assert "Invalid entity_id format" in result

    @respx.mock
    async def test_timeout_returns_connection_error_string(self):
        """A ReadTimeout is treated as a RequestError and returns a connection-error string."""
        url = f"{HA_BASE}/api/services/light/turn_on"
        respx.post(url).mock(side_effect=httpx.ReadTimeout("timed out"))

        result = await home_service("light", "turn_on", "light.hall")

        assert "connection error" in result.lower() or "HA connection error" in result


# ---------------------------------------------------------------------------
# home_state
# ---------------------------------------------------------------------------


class TestHomeState:
    @respx.mock
    async def test_success_with_full_attributes(self):
        """200 response is formatted as 'friendly_name (entity): state=X | attrs'."""
        entity = "light.kitchen_ceiling"
        payload = {
            "state": "on",
            "attributes": {
                "friendly_name": "Kitchen Ceiling",
                "brightness": 200,
                "color_temp": 370,
            },
        }
        respx.get(f"{HA_BASE}/api/states/{entity}").mock(
            return_value=httpx.Response(200, json=payload)
        )

        result = await home_state(entity)

        assert "Kitchen Ceiling" in result
        assert "light.kitchen_ceiling" in result
        assert "state=on" in result
        assert "brightness" in result

    @respx.mock
    async def test_friendly_name_not_duplicated_in_attributes(self):
        """friendly_name is in the prefix but NOT repeated inside the attr_summary JSON."""
        entity = "sensor.temperature"
        payload = {
            "state": "21.5",
            "attributes": {
                "friendly_name": "Living Room Temp",
                "unit_of_measurement": "°C",
            },
        }
        respx.get(f"{HA_BASE}/api/states/{entity}").mock(
            return_value=httpx.Response(200, json=payload)
        )

        result = await home_state(entity)

        # The summary JSON portion should not contain friendly_name key
        # Extract the part after the first '|'
        summary_part = result.split("|", 1)[-1]
        assert "friendly_name" not in summary_part

    @respx.mock
    async def test_entity_not_found_404(self):
        """A 404 from HA is surfaced as a string containing the status code."""
        entity = "light.nonexistent"
        respx.get(f"{HA_BASE}/api/states/{entity}").mock(
            return_value=httpx.Response(404, text="Entity not found")
        )

        result = await home_state(entity)

        assert "404" in result
        assert "error" in result.lower() or "Error" in result

    @respx.mock
    async def test_connection_refused_returns_error_string(self):
        """ConnectError returns a human-readable HA connection error string."""
        entity = "switch.router"
        respx.get(f"{HA_BASE}/api/states/{entity}").mock(
            side_effect=httpx.ConnectError("refused")
        )

        result = await home_state(entity)

        assert "connection error" in result.lower() or "HA connection error" in result

    @respx.mock
    async def test_attributes_summary_truncated_at_400_chars(self):
        """Attribute summary JSON is capped at 400 characters."""
        entity = "sensor.huge"
        long_value = "x" * 500
        payload = {
            "state": "ok",
            "attributes": {"friendly_name": "Huge", "data": long_value},
        }
        respx.get(f"{HA_BASE}/api/states/{entity}").mock(
            return_value=httpx.Response(200, json=payload)
        )

        result = await home_state(entity)

        # The attr summary part follows ' | ' in the output
        attr_part = result.split("| ", 1)[-1]
        assert len(attr_part) <= 400

    @respx.mock
    async def test_entity_with_no_attributes(self):
        """Entity with empty attributes dict returns state without crashing."""
        entity = "input_boolean.test"
        payload = {"state": "off", "attributes": {}}
        respx.get(f"{HA_BASE}/api/states/{entity}").mock(
            return_value=httpx.Response(200, json=payload)
        )

        result = await home_state(entity)

        assert "state=off" in result
        assert entity in result

    @respx.mock
    async def test_polish_friendly_name_preserved(self):
        """Entity friendly_name containing Polish characters is not mangled."""
        entity = "sensor.temperatura_salon"
        payload = {
            "state": "22",
            "attributes": {"friendly_name": "Temperatura w salonie", "unit_of_measurement": "°C"},
        }
        respx.get(f"{HA_BASE}/api/states/{entity}").mock(
            return_value=httpx.Response(200, json=payload)
        )

        result = await home_state(entity)

        assert "Temperatura w salonie" in result

    @respx.mock
    async def test_missing_friendly_name_falls_back_to_entity_id(self):
        """When friendly_name is absent, the entity_id is used as the display name."""
        entity = "sensor.raw_entity"
        payload = {"state": "42", "attributes": {"unit_of_measurement": "W"}}
        respx.get(f"{HA_BASE}/api/states/{entity}").mock(
            return_value=httpx.Response(200, json=payload)
        )

        result = await home_state(entity)

        # entity_id should appear as the name prefix
        assert result.startswith(entity)

    @respx.mock
    async def test_http_401_returns_error_string(self):
        """A 401 from the states endpoint surfaces the status code."""
        entity = "sensor.secure"
        respx.get(f"{HA_BASE}/api/states/{entity}").mock(
            return_value=httpx.Response(401, text="Unauthorized")
        )

        result = await home_state(entity)

        assert "401" in result
