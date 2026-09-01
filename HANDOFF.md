# HANDOFF — HomeAI
Date: 2026-08-29 (updated by Cursor 4-agent scan)

## Current branch
`feature/heimdall-secrets-and-gpu-notes` — 12 commits ahead of `dev`, not yet merged.

## What's in this branch (not yet on dev)
| SHA | Change |
|-----|--------|
| 944a000 | fix: gate now pulses instead of sticking on; fix automations 500 |
| 461d459 | fix: qwen now lists all office devices across every domain |
| 464b75e | docs: correct misdiagnosis - siren fix confirmed working |
| 3d43e20 | fix: assign area to unassigned alarm siren devices |
| 7119e8e | docs: close out backlog #6 - real root cause fixed |
| ca4e933 | fix: bedroom radiator card + 3 missing room radiators |
| 12571e6 | docs: document kitchen boost dashboard buttons + HA restart |
| f5e14b5 | feat: add heating boost voice command |
| 830f61b | fix: climate alias root cause, entity exposure, whisper VAD |
| 364aa48 | docs: record qwen entity-rename findings for backlog #6 |
| 6de41eb | docs: close out backlog #8 (OAuth json deleted) |
| 5ad0d63 | chore: consolidate local secrets into .env.local (backlog #5/#9) |

## Task 7 — CRITICAL CORRECTION
`feature/heimdall-task7-test-matrix` branch exists locally but has **ZERO commits**.
The actual Task 7 work (`test_matrix.py`, `ntfy_failure_logger.py`) has been **run live but never committed to git**.
Before the PR can be opened, all Task 7 files must be staged and committed first.

### Task 7 remaining steps (in order):
1. Revert `climate.0xa4c138b1ad7dfd57` aliases from two (`["Bedroom radiator", "bedroom heater"]`) back to one — live in vesemir HA, then retest qwen climate row.
2. Document `switch.office_led` as accepted permanent qwen limitation in `test_matrix.py` comments.
3. Add inter-call delays to prevent Gemini free-tier 429 (15 req/min ceiling; full run makes ~13 calls).
4. Re-run full test matrix for clean final readout.
5. Write Task 7 summary doc (same pattern as `N8N_ROUTER.md`).
6. Move `heimdall_bot` ntfy token out of `%TEMP%\heimdall_ntfy_token.txt` into `.env.local`.
7. Git commit + push all Task 7 files, open PR (`feature/heimdall-task7-test-matrix → dev`).

## PRs needed (manual — no gh CLI on KamiloPC; `winget install --id GitHub.cli` to fix)
1. Task 7 (above — must commit first, then open PR)
2. `feature/heimdall-secrets-and-gpu-notes → dev`
3. ProjectNemo: `feature/heimdall-config-sync-20260820 → dev`

## Phase 1.5 hardening status
| # | Item | Status |
|---|------|--------|
| 1 | vesemir HA config into git | DONE — confirm live on vesemir, PR pending on ProjectNemo |
| 2 | Schedule test matrix (cron/n8n) | **NOT DONE** |
| 3 | Deploy ntfy_failure_logger as service | **NOT DONE** — SOAK_LOG.md doesn't exist |
| 4 | kamilo-assistant scoping | Resolved — stays separate |
| 5/9 | .env.local secrets consolidation | DONE (5ad0d63) |
| 6 | Entity naming (office light, bedroom radiator) | DONE |
| 7 | Runtime alarm guardrail | Already existed |
| 8 | Google OAuth json | Deleted (6de41eb) |

## Live HA state (on vesemir — not in git yet)
- `climate.0xa4c138b1ad7dfd57` currently has TWO aliases — needs revert to one before Task 7 rerun.
- `switch.office_led` ("Office LED", TP-Link) is a real separate device; qwen resolves to it instead of the Zigbee relay. Accepted permanent limitation.
- n8n workflow `k8tTX2TbnsCm69NC` (`Heimdall AI Task Router`) live at `https://n8n.kamilon8n.win/webhook/heimdall/route`.

## Urgent (not code)
- Rotate `heimdall_memory_token`, `influxdb_token`, Satel `alarm_code` (briefly exposed 2026-08-20).
- Confirm WiFi password rotated post git-filter-repo sanitization.
- Delete stray "Gemini regression check" Google Calendar event (manual, no API).
- Move ntfy `heimdall_bot` token from `%TEMP%\heimdall_ntfy_token.txt` to `.env.local`.

## Phase 2 next
M7 phone/watch trigger — read `heimdall/PHASE1_5_HARDENING_AND_PHASE2_PLAN.md` M7 section.
