# HANDOFF — HomeAI / Heimdall
Date: 2026-09-01 (session wrap)

## Current branch
`dev` — includes merged [PR #22](https://github.com/winfer70/HomeAI/pull/22) (`feature/heimdall-secrets-and-gpu-notes`) plus:
- `2492235` `.gitignore` for `secrets.yaml` / `*.token` / OAuth json
- `f6191a8` docs: 2026-09-01 secret rotation

Task 7 (`test_matrix.py`, `TEST_MATRIX.md`) **is on `dev`** (commit `c09354b` via earlier PRs). The old “zero commits on task7 branch” note is stale.

## Live services (Heimdall leftover, still running)

| Service | Host | Notes |
|---|---|---|
| heimdall-memory | jaskier :10400 | token **rotated 2026-09-01**; poller recreated |
| heimdall-whisper | jaskier | **medium-int8** (shared with Kamilo voice) |
| heimdall-piper | jaskier | TTS |
| n8n Heimdall router | labserver | `https://n8n.kamilon8n.win/webhook/heimdall/route` |

Kamilo is now the HA conversation agent. Heimdall local qwen agent is legacy; do not add parallel Assist pipelines.

## Secrets (2026-09-01)

| Item | Status |
|---|---|
| `heimdall_memory_token` | Rotated live (HA secrets.yaml + jaskier `heimdall/memory/.env` + HomeAI `.env.local`) |
| `influxdb_token` | New Influx all-access auth; old auths deleted; HA + nemo-api switched |
| Satel `alarm_code` | New PIN in HA secrets.yaml only. **Keypad still must be set** — file `C:\Users\koter\.cursor\rotated-alarm-pin.txt` then delete it |
| WiFi AP password | Git history clean. **AP password not verified** on Vodafone/LabLAN |
| `check_config --secrets` | Never run in a way that dumps plaintext into chat/logs |

## Phase 1.5

| # | Item | Status |
|---|------|--------|
| 1 | vesemir HA config in git | DONE (ProjectNemo `heimdall.yaml`) |
| 2 | Schedule test matrix | **NOT DONE** |
| 3 | ntfy_failure_logger as service | **NOT DONE** |
| 4 | kamilo-assistant scoping | Resolved — Kamilo is the product now |
| 5/9 | `.env.local` | DONE |
| 6 | Entity naming | DONE |
| 8 | Google OAuth json | Deleted |

## Do next

1. Apply Satel keypad PIN (see file above) so auto-arm/disarm works
2. Confirm/change WiFi AP password if not done after 2026-08-15 filter-repo
3. Phase 1.5 #2 cron/n8n for `test_matrix.py`; #3 deploy `ntfy_failure_logger`
4. Phase 2 M7 phone/watch trigger — `heimdall/PHASE1_5_HARDENING_AND_PHASE2_PLAN.md`

## Do not

- Touch `alarm_control_panel.*` / Satel entities from agents
- Re-hide gate relay `switch.brama_sonoff_100254194e_1`
