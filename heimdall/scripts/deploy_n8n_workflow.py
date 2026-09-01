#!/usr/bin/env python3
"""Deploy (create or update) Heimdall's AI Task Router n8n workflow.

Goes through n8n's REST API rather than writing to its Postgres tables
directly - this is the fix for the `workflow_entity`/`workflow_history`
split flagged in the original brief. n8n's UI/import flow keeps both tables
in sync when it writes a workflow; calling the same public API does the
same thing, so this script never touches the database.

Idempotent:
  - The `Heimdall HA Token` httpHeaderAuth credential is only created if a
    credential with that exact name doesn't already exist (n8n's public API
    can list credential names/types/ids, just not read back secret values,
    so this can't accidentally clobber the token if the script is re-run).
  - The `Heimdall AI Task Router` workflow is looked up by name; if found,
    it's updated in place (PUT) instead of creating a duplicate.

Usage:
    N8N_URL=https://n8n.kamilon8n.win \
    N8N_API_KEY=<n8n API key, Settings > API> \
    HEIMDALL_HA_URL=http://192.168.0.108:8123 \
    HEIMDALL_HA_TOKEN=<Home Assistant long-lived access token> \
    python deploy_n8n_workflow.py

Defaults assume the live Heimdall infra (n8n on labserver, HA on vesemir) if
the URL env vars aren't set - only HEIMDALL_HA_TOKEN and N8N_API_KEY are required.
(Renamed from bare HA_TOKEN/HA_URL 2026-08-20 to match every other heimdall/
script's HEIMDALL_-prefixed convention - see backlog #9 in
heimdall/PHASE1_5_HARDENING_AND_PHASE2_PLAN.md.)
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_N8N_URL = "https://n8n.kamilon8n.win"
DEFAULT_HA_URL = "http://192.168.0.108:8123"

WORKFLOW_NAME = "Heimdall AI Task Router"
CREDENTIAL_NAME = "Heimdall HA Token"
CREDENTIAL_TYPE = "httpHeaderAuth"
CREDENTIAL_PLACEHOLDER = "__HEIMDALL_HA_CREDENTIAL_ID__"

WORKFLOW_FILE = Path(__file__).resolve().parent.parent / "n8n" / "ai_task_router.workflow.json"

# Fields n8n's API rejects on update because they're server-managed / not
# part of the writable workflow schema.
READONLY_WORKFLOW_FIELDS = {
    "id", "createdAt", "updatedAt", "active", "shared", "tags",
    "versionId", "triggerCount", "isArchived", "pinData",
}


def _request(method: str, url: str, api_key: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("X-N8N-API-KEY", api_key)
    req.add_header("Content-Type", "application/json")
    # n8n sits behind Cloudflare; the default urllib User-Agent trips
    # Cloudflare's bot-fight mode (error code 1010) even with a valid API
    # key, so present a normal browser-like one instead.
    req.add_header(
        "User-Agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} -> HTTP {exc.code}: {detail}") from exc


def find_credential_id(n8n_url: str, api_key: str, name: str) -> str | None:
    result = _request("GET", f"{n8n_url}/api/v1/credentials", api_key)
    for cred in result.get("data", []):
        if cred.get("name") == name:
            return cred.get("id")
    return None


def ensure_credential(n8n_url: str, api_key: str, ha_token: str) -> str:
    existing_id = find_credential_id(n8n_url, api_key, CREDENTIAL_NAME)
    if existing_id:
        print(f"Credential '{CREDENTIAL_NAME}' already exists (id={existing_id}), reusing.")
        return existing_id

    print(f"Creating credential '{CREDENTIAL_NAME}'...")
    payload = {
        "name": CREDENTIAL_NAME,
        "type": CREDENTIAL_TYPE,
        "data": {
            "name": "Authorization",
            "value": f"Bearer {ha_token}",
        },
    }
    created = _request("POST", f"{n8n_url}/api/v1/credentials", api_key, payload)
    cred_id = created.get("id")
    if not cred_id:
        raise RuntimeError(f"Credential creation didn't return an id: {created}")
    print(f"Created credential id={cred_id}")
    return cred_id


def find_workflow_id(n8n_url: str, api_key: str, name: str) -> str | None:
    result = _request("GET", f"{n8n_url}/api/v1/workflows", api_key)
    for wf in result.get("data", []):
        if wf.get("name") == name:
            return wf.get("id")
    return None


def load_workflow_definition(credential_id: str) -> dict:
    raw = WORKFLOW_FILE.read_text(encoding="utf-8")
    raw = raw.replace(CREDENTIAL_PLACEHOLDER, credential_id)
    return json.loads(raw)


def deploy_workflow(n8n_url: str, api_key: str, definition: dict) -> str:
    existing_id = find_workflow_id(n8n_url, api_key, definition["name"])
    # n8n's update endpoint only accepts the writable subset of the schema.
    body = {k: v for k, v in definition.items() if k not in READONLY_WORKFLOW_FIELDS}

    if existing_id:
        print(f"Workflow '{definition['name']}' already exists (id={existing_id}), updating...")
        _request("PUT", f"{n8n_url}/api/v1/workflows/{existing_id}", api_key, body)
        return existing_id

    print(f"Creating workflow '{definition['name']}'...")
    created = _request("POST", f"{n8n_url}/api/v1/workflows", api_key, body)
    wf_id = created.get("id")
    if not wf_id:
        raise RuntimeError(f"Workflow creation didn't return an id: {created}")
    print(f"Created workflow id={wf_id}")
    return wf_id


def activate_workflow(n8n_url: str, api_key: str, workflow_id: str) -> None:
    _request("POST", f"{n8n_url}/api/v1/workflows/{workflow_id}/activate", api_key)
    print("Workflow activated.")


def main() -> int:
    n8n_url = os.environ.get("N8N_URL", DEFAULT_N8N_URL).rstrip("/")
    ha_url = os.environ.get("HEIMDALL_HA_URL", DEFAULT_HA_URL).rstrip("/")
    api_key = os.environ.get("N8N_API_KEY")
    ha_token = os.environ.get("HEIMDALL_HA_TOKEN")

    if not api_key:
        print("ERROR: N8N_API_KEY environment variable is required.", file=sys.stderr)
        return 1
    if not ha_token:
        print("ERROR: HEIMDALL_HA_TOKEN environment variable is required.", file=sys.stderr)
        return 1
    if not WORKFLOW_FILE.exists():
        print(f"ERROR: workflow definition not found at {WORKFLOW_FILE}", file=sys.stderr)
        return 1

    del ha_url  # HA URL is baked into the workflow's HTTP node; kept here for future flexibility.

    credential_id = ensure_credential(n8n_url, api_key, ha_token)
    definition = load_workflow_definition(credential_id)
    workflow_id = deploy_workflow(n8n_url, api_key, definition)

    try:
        activate_workflow(n8n_url, api_key, workflow_id)
    except RuntimeError as exc:
        # Already-active workflows return an error on re-activate in some
        # n8n versions; don't fail the whole deploy over that.
        print(f"Note: activation call returned an error (may already be active): {exc}")

    print(f"\nDone. Webhook URL: {n8n_url}/webhook/heimdall/route")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
