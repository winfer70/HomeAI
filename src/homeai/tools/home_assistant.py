from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from homeai.config import Settings, settings as _default_settings
from homeai.tools.base import ToolResult

log = logging.getLogger(__name__)


def _ha_headers(token: str) -> dict[str, str]:
    """Build standard Home Assistant API authorisation headers."""
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


async def home_service(
    domain: str,
    service: str,
    entity_id: str,
    data: dict[str, Any] | None = None,
    cfg: Settings | None = None,
) -> ToolResult:
    """Call a Home Assistant service (e.g. light/turn_on, climate/set_temperature)."""
    cfg = cfg or _default_settings
    url = f"{cfg.ha_url}/api/services/{domain}/{service}"
    payload: dict[str, Any] = {"entity_id": entity_id}
    if data:
        payload.update(data)
    try:
        async with httpx.AsyncClient(timeout=cfg.ha_timeout_s) as client:
            resp = await client.post(url, headers=_ha_headers(cfg.ha_token), json=payload)
            resp.raise_for_status()
            return ToolResult(
                success=True,
                data=f"OK: {domain}.{service} on {entity_id} succeeded.",
            )
    except httpx.HTTPStatusError as e:
        return ToolResult(
            success=False,
            data="",
            error=f"HA service error {e.response.status_code}: {e.response.text[:300]}",
        )
    except httpx.RequestError as e:
        return ToolResult(success=False, data="", error=f"HA connection error: {e}")


async def home_state(
    entity_id: str,
    cfg: Settings | None = None,
) -> ToolResult:
    """Get the current state and attributes of a Home Assistant entity."""
    cfg = cfg or _default_settings
    url = f"{cfg.ha_url}/api/states/{entity_id}"
    try:
        async with httpx.AsyncClient(timeout=cfg.ha_timeout_s) as client:
            resp = await client.get(url, headers=_ha_headers(cfg.ha_token))
            resp.raise_for_status()
            body = resp.json()
            state = body.get("state", "unknown")
            attrs = body.get("attributes", {})
            friendly = attrs.get("friendly_name", entity_id)
            attr_summary = json.dumps(
                {k: v for k, v in attrs.items() if k != "friendly_name"},
                ensure_ascii=False,
            )[:400]
            return ToolResult(
                success=True,
                data=f"{friendly} ({entity_id}): state={state} | {attr_summary}",
            )
    except httpx.HTTPStatusError as e:
        return ToolResult(
            success=False,
            data="",
            error=f"HA state error {e.response.status_code}: {e.response.text[:300]}",
        )
    except httpx.RequestError as e:
        return ToolResult(success=False, data="", error=f"HA connection error: {e}")
