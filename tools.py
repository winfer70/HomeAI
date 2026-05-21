from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from config import settings

log = logging.getLogger(__name__)

_HA_HEADERS = {
    "Authorization": f"Bearer {settings.ha_token}",
    "Content-Type": "application/json",
}


async def web_search(query: str) -> str:
    """Search the web for real-time information. Supports Polish and English queries."""
    # SearXNG — self-hosted metasearch (primary)
    if settings.searxng_url:
        try:
            async with httpx.AsyncClient(timeout=settings.search_timeout_s) as client:
                resp = await client.get(
                    f"{settings.searxng_url}/search",
                    params={
                        "q": query,
                        "format": "json",
                        "language": "auto",
                        "categories": "general,news",
                        "number_of_results": settings.search_results,
                    },
                )
                resp.raise_for_status()
                results = resp.json().get("results", [])
                if results:
                    lines = [f"Search results for: {query}"]
                    for i, r in enumerate(results[: settings.search_results], 1):
                        title = r.get("title", "")
                        url = r.get("url", "")
                        snippet = r.get("content", r.get("snippet", ""))[:350]
                        lines.append(f"[{i}] {title}\n    {url}\n    {snippet}")
                    return "\n\n".join(lines)
                return f"SearXNG returned no results for: {query}"
        except httpx.RequestError as e:
            log.warning("SearXNG unavailable (%s) — trying Brave API fallback", e)
        except Exception as e:
            log.error("SearXNG error: %s", e)

    # Brave Search API — cloud fallback
    if settings.brave_api_key:
        try:
            async with httpx.AsyncClient(timeout=settings.search_timeout_s) as client:
                resp = await client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    headers={
                        "Accept": "application/json",
                        "X-Subscription-Token": settings.brave_api_key,
                    },
                    params={"q": query, "count": settings.search_results},
                )
                resp.raise_for_status()
                items = resp.json().get("web", {}).get("results", [])
                lines = [f"Search results for: {query}"]
                for i, r in enumerate(items, 1):
                    lines.append(
                        f"[{i}] {r.get('title','')}\n    {r.get('url','')}\n    {r.get('description','')[:350]}"
                    )
                return "\n\n".join(lines) if len(lines) > 1 else "No results found."
        except Exception as e:
            log.error("Brave search error: %s", e)

    return f"Web search unavailable. Could not retrieve results for: {query}"


async def home_service(
    domain: str,
    service: str,
    entity_id: str,
    data: dict[str, Any] | None = None,
) -> str:
    """Call a Home Assistant service (e.g. light/turn_on, climate/set_temperature)."""
    url = f"{settings.ha_url}/api/services/{domain}/{service}"
    payload: dict[str, Any] = {"entity_id": entity_id}
    if data:
        payload.update(data)
    try:
        async with httpx.AsyncClient(timeout=settings.ha_timeout_s) as client:
            resp = await client.post(url, headers=_HA_HEADERS, json=payload)
            resp.raise_for_status()
            return f"OK: {domain}.{service} on {entity_id} succeeded."
    except httpx.HTTPStatusError as e:
        return f"HA service error {e.response.status_code}: {e.response.text[:300]}"
    except httpx.RequestError as e:
        return f"HA connection error: {e}"


async def home_state(entity_id: str) -> str:
    """Get the current state and attributes of a Home Assistant entity."""
    url = f"{settings.ha_url}/api/states/{entity_id}"
    try:
        async with httpx.AsyncClient(timeout=settings.ha_timeout_s) as client:
            resp = await client.get(url, headers=_HA_HEADERS)
            resp.raise_for_status()
            data = resp.json()
            state = data.get("state", "unknown")
            attrs = data.get("attributes", {})
            friendly = attrs.get("friendly_name", entity_id)
            attr_summary = json.dumps(
                {k: v for k, v in attrs.items() if k != "friendly_name"},
                ensure_ascii=False,
            )[:400]
            return f"{friendly} ({entity_id}): state={state} | {attr_summary}"
    except httpx.HTTPStatusError as e:
        return f"HA state error {e.response.status_code}: {e.response.text[:300]}"
    except httpx.RequestError as e:
        return f"HA connection error: {e}"
