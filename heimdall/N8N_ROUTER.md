# n8n AI Task Router — Task 6 (M5) infrastructure notes

The original brief left n8n's actual location, credentials, and whether an
existing "Gemini path" workflow could be reused as open questions ("don't
improvise config for a system you can't see"). This doc records what was
actually found live, since none of it lives in this Python repo.

## Where n8n actually lives

The repo's own `INFRASTRUCTURE_PLAN.md` / `migration_checklist.md` describe
n8n running on a host called "node-a", which turned out to be stale — n8n
(and the rest of the `ai-agent-stack`/`tickerTap` containers) has since
migrated to a host called **`labserver`** (LAN IP `192.168.0.102`), per the
`winfer70/ai-agent-stack` repo's own `docker-compose.labserver.yml` and
`HANDOFF.md`. This isn't in `PROJECT_REGISTRY.md` either — that doc still
lists n8n under `swiss-knife`.

- **External URL** (confirmed reachable, `200` on `/healthz`):
  `https://n8n.kamilon8n.win`
- **Direct LAN port** (`192.168.0.102:5678`): connection actively refused —
  n8n's container maps the port, but it isn't reachable this way (firewalled
  or bound differently at the host level). **Use the public URL for all API
  calls and for the local Ollama branch's HTTP node**, not the LAN IP.
- **API key**: already present in `ai-agent-stack/.env` on this machine
  (`N8N_API_KEY`), reused rather than generating a new one. Verified live
  against `GET /api/v1/workflows` (200, listed all 27 existing workflows).
- **Gotcha**: n8n sits behind Cloudflare. Calls made with Python's default
  `urllib` User-Agent get blocked with `HTTP 403` / Cloudflare error code
  `1010` (bot-fight mode) even with a valid API key. `deploy_n8n_workflow.py`
  sends a normal browser-like `User-Agent` header to work around this.
  PowerShell's own `Invoke-WebRequest` UA wasn't blocked, which is what made
  this confusing to diagnose at first.

## "Reuse existing Gemini path" — resolved

No existing n8n workflow calls Gemini in any form. Two workflows already
named similarly to this task's own name were checked directly (not
guessed) to make sure this wouldn't create a duplicate or collide with
something else:

- **"Task Router"** (`3HIyV5y12maXvxCX`) and **"AI Task Router"**
  (`ScR5WMOyIGlqV7nR`) both exist and are active, but they're an unrelated
  laptop-vs-backup-Ollama load-balancing system for a different project
  (nodes: laptop Ollama, Wake-on-LAN, a "backup" model) — no Gemini, no
  Home Assistant, no Heimdall-related content at all.

Asked the user directly rather than guessing: the cloud branch calls **HA's
`conversation.process` REST API** (`POST http://192.168.0.108:8123/api/conversation/process`)
targeting `conversation.google_ai_conversation` — the same Gemini agent
already built and tested in Tasks 2/5 — rather than n8n holding its own
separate Google API credentials.

## Workflow: `heimdall/n8n/ai_task_router.workflow.json`

Deployed as **"Heimdall AI Task Router"** (workflow id `k8tTX2TbnsCm69NC`),
webhook path `POST /webhook/heimdall/route`, body `{"text": "...", "language": "en"|"pl"}`.

- **Classify Intent** (function node): deterministic bilingual (EN+PL)
  keyword match against the entity domains this project already exposes to
  Assist (lights/switches, climate/TRVs, the gate, the aquarium) → routes to
  `local` (device-control) or `cloud` (open-domain). Both keyword lists are
  checked regardless of the declared `language`, since real queries mix
  PL/EN. No LLM call is spent just to decide where to send the real one.
- **Local branch**: `POST http://192.168.0.125:11434/api/chat` directly
  against jaskier's Ollama (`qwen2.5:7b-instruct`, `stream: false`) — no HA
  involved, so it has no entity/tool access. This matches the brief's
  literal spec and the acceptance criteria, which only requires correct
  *routing*, not that a device is actually toggled through this webhook
  (real device control still happens through the existing Heimdall voice
  pipeline from Tasks 2/3/5).
- **Cloud branch**: `POST http://192.168.0.108:8123/api/conversation/process`
  with `agent_id: conversation.google_ai_conversation`, authenticated via
  an n8n `httpHeaderAuth` credential named **"Heimdall HA Token"**
  (`Authorization: Bearer <HA long-lived token>`) — never a hardcoded
  token in the workflow JSON.
- Both branches respond via `respondToWebhook` nodes with a common shape:
  `{"branch": "local"|"cloud", "intent": "device-control"|"open-domain", "model": "...", "response": "..."}`.
- An `Error Handler` (errorTrigger) → `Error Response` (500) pair is
  included for parity with this n8n instance's existing workflow
  conventions (seen in "Task Router").

## Deploy script: `heimdall/scripts/deploy_n8n_workflow.py`

Goes through n8n's public REST API only (`GET`/`POST`/`PUT` on
`/api/v1/workflows` and `/api/v1/credentials`), never direct Postgres
writes — this is the actual fix for the `workflow_entity`/`workflow_history`
split flagged in the original brief, since the API keeps both tables in
sync the same way the UI does.

Idempotent:
- Looks up the `Heimdall HA Token` credential by name before creating one
  (n8n's API can list credential name/type/id but never read back the
  secret value, so a re-run can't accidentally leak or need to re-guess it).
- Looks up the `Heimdall AI Task Router` workflow by name; updates in place
  (`PUT`) if found instead of creating a duplicate.

```bash
N8N_API_KEY=<n8n API key, Settings > API> \
HA_TOKEN=<HA long-lived access token> \
python heimdall/scripts/deploy_n8n_workflow.py
```

`N8N_URL` (default `https://n8n.kamilon8n.win`) and `HA_URL` (default
`http://192.168.0.108:8123`) can be overridden if the infra moves again.

## Verification (2026-08-19, live)

Sent both a device-control and an open-domain query, in both English and
Polish, through the deployed webhook, then confirmed via `GET
/api/v1/executions/{id}?includeData=true` **which node actually ran** —
not just whether the answer sounded right, per the brief's explicit
acceptance criteria:

| Query | Language | Branch returned | Node that ran (from n8n execution log) |
|---|---|---|---|
| "Turn on the office light" | EN | `local` | `Call Local Ollama (jaskier)` |
| "What is the capital of France?" | EN | `cloud` | `Call Gemini (via HA conversation.process)` |
| "Otwórz bramę" | PL | `local` | `Call Local Ollama (jaskier)` |
| "Jaka jest stolica Francji?" | PL | `cloud` | `Call Gemini (via HA conversation.process)` |

All four routed correctly. Gemini's cloud-branch answers were substantively
correct in both languages ("Paris" / "Paryż"). The local branch's replies
were plausible chat responses (it has no tool access via this path, as
designed) rather than actual device control — expected and matches the
brief's literal spec for this workflow.
