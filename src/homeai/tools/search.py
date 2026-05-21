from __future__ import annotations

import logging

import httpx

from homeai.config import Settings, settings as _default_settings
from homeai.tools.base import ToolResult

log = logging.getLogger(__name__)


async def web_search(query: str, cfg: Settings | None = None) -> ToolResult:
    """Search the web for real-time information supporting Polish and English queries."""
    cfg = cfg or _default_settings

    # SearXNG — self-hosted metasearch (primary)
    if cfg.searxng_url:
        try:
            async with httpx.AsyncClient(timeout=cfg.search_timeout_s) as client:
                resp = await client.get(
                    f"{cfg.searxng_url}/search",
                    params={
                        "q": query,
                        "format": "json",
                        "language": "auto",
                        "categories": "general,news",
                        "number_of_results": cfg.search_results,
                    },
                )
                resp.raise_for_status()
                results = resp.json().get("results", [])
                if results:
                    lines = [f"Search results for: {query}"]
                    for i, r in enumerate(results[: cfg.search_results], 1):
                        title = r.get("title", "")
                        url = r.get("url", "")
                        snippet = r.get("content", r.get("snippet", ""))[:350]
                        lines.append(f"[{i}] {title}\n    {url}\n    {snippet}")
                    return ToolResult(success=True, data="\n\n".join(lines))
                return ToolResult(
                    success=True,
                    data=f"SearXNG returned no results for: {query}",
                )
        except httpx.RequestError as e:
            log.warning("SearXNG unavailable (%s) — trying Brave API fallback", e)
        except Exception as e:
            log.error("SearXNG error: %s", e)

    # Brave Search API — cloud fallback
    if cfg.brave_api_key:
        try:
            async with httpx.AsyncClient(timeout=cfg.search_timeout_s) as client:
                resp = await client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    headers={
                        "Accept": "application/json",
                        "X-Subscription-Token": cfg.brave_api_key,
                    },
                    params={"q": query, "count": cfg.search_results},
                )
                resp.raise_for_status()
                items = resp.json().get("web", {}).get("results", [])
                lines = [f"Search results for: {query}"]
                for i, r in enumerate(items, 1):
                    lines.append(
                        f"[{i}] {r.get('title', '')}\n"
                        f"    {r.get('url', '')}\n"
                        f"    {r.get('description', '')[:350]}"
                    )
                data = "\n\n".join(lines) if len(lines) > 1 else "No results found."
                return ToolResult(success=True, data=data)
        except Exception as e:
            log.error("Brave search error: %s", e)

    return ToolResult(
        success=False,
        data="",
        error=f"Web search unavailable. Could not retrieve results for: {query}",
    )
