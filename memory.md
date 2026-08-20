# Claude Memory — Projects

## HusariaBeats Website
- [husariabeats-project.md](husariabeats-project.md) — full architecture, stack, decisions, release automation via upload-post.com, workflow IDs (updated 2026-05-12)
- [husariabeats-port-plan.md](husariabeats-port-plan.md) — 24-item checklist: Claude Design → Next.js 14 port (COMPLETE, commit 9c3584a)
- [husariabeats-next-steps.md](husariabeats-next-steps.md) — TikTok/Meta API approval NOT needed (upload-post handles it). Resend ✅ done. ZAPOMNIANI: `/releases/zapomniani/` empty — MP4 files missing, need to locate + copy. Telegram bot loop deferred.
- [husariabeats-upload-post.md](husariabeats-upload-post.md) — upload-post.com API key, profile, confirmed field names (`video`, `user`, `platform[]`)
- [feedback_n8n_code_node.md](feedback_n8n_code_node.md) — n8n 2.x task runner: use `helpers.httpRequest` (no $), URL-encoded body; fetch/FormData/$helpers/N8N_RUNNERS_ENABLED don't work

---

# TickerTap Project

## Project Overview
- **Type**: Full-stack finance/trading web app
- **Root**: `/home/user/projects/finance/tickerTap`
- **Branch**: `tradingAI0.1` for Trading AI feature set
- **Plan**: `TRADING_AI_PLAN.md` — all 6 phases (95 items) COMPLETED

## Stack
- **Backend**: FastAPI 0.95.2, SQLAlchemy 1.4.49 (async), Pydantic v1 (1.10.11), Python 3.11
- **Frontend**: React 19, Vite 7.x, served from `frontend/dist` by nginx
- **DB**: TimescaleDB (Postgres 15), Redis 7
- **Workers**: arq (async Redis queue)
- **Docker**: 7 services — db, redis, app, trading-worker, paper-worker, trading-ml, alert-worker
- **alert-worker**: arq worker (`backend/app/trading/alert_worker.py`) — polls active `PriceAlert` rows, checks conditions (above/below/crosses) via yfinance, fires in-app notifications, self-re-enqueues every 60s (market hours) / 300s (closed). Max 50 alerts/user.
- **Deploy cmd**: `docker compose --env-file .env.prod -f docker-compose.prod.yml up -d` ⚠️ MUST use prod compose (see tickertap-prod-ops.md)

## Key Patterns (see [tickertap-patterns.md](tickertap-patterns.md) for details)
- SQLAlchemy 1.4 async style (NOT 2.x)
- Pydantic v1 `orm_mode = True` (NOT model_config)
- `get_current_user` returns User ORM — access via `.user_id`
- Strategy slugs in `definition_json.strategy_slug` (no slug column)
- Backend bind-mounted: `./backend/app:/app/app:ro`
- Frontend must be rebuilt (`npm run build`) after changes

## Pending Work
- Re-enable rate limits on trading endpoints (19 decorators commented out in trading.py) — deferred intentionally
- **Improvements Master Plan**: ask user which phase (A-I) to work on next

## Ops Notes
- [tickertap-prod-ops.md](tickertap-prod-ops.md) — CRITICAL: prod compose requirement, news AI worker on prior Linux laptop, correct LAN IP (<LAN_IP>), deploy commands

## User Preferences
- Uses subagents for parallel work
- Prefers "resume, and use subagents" workflow
- Development protocol: RESEARCH → INNOVATE → PLAN → EXECUTE modes

---

# AI Agent Stack (`/home/user/ai-agent-stack`)
- [ai-agent-stack.md](ai-agent-stack.md) — full state: Docker services, lab nodes, Ollama on node-b (qwen3.5:9b + codestral:22b), workflow IDs (updated 2026-05-17)

## Node-A Dashboard — ✅ COMPLETE (2026-05-11)
All 5 parts done. Ollama moved to node-b (<LAN_IP>). Models: qwen3.5:9b (default/think/big) + codestral:22b (code). llava:13b + nomic-embed-text not yet pulled.

## Home Lab Migration — IN PROGRESS (2026-05-18)
Checklist at `/home/user/MIGRATION_CHECKLIST.md`

**DONE:** Phase 0 ✓, Phase 1.1–1.5 ✓ (including restic backups to external HDD), Phase 2 ✓ (node-b full stack), Phase 3a ✓ (node-c), Phase 3b ✓ (Prometheus+Grafana+tickertap-worker on node-e, reboot smoke test passed), Phase 4 mostly ✓ (node-d: Tailscale+WoL+node_exporter+Uptime Kuma container), Phase 5 ✓ (UptimeRobot: 5 monitors, email alerts)

**REMAINING:**
- `4.4.2–4.4.3` Uptime Kuma UI setup (needs node-d on network — node-d is ethernet-only, no cable available)
- `4.1.2` BIOS AC Recovery on node-d (physical)
- `6.x` Final validation

**Backup:** restic on external HDD (1TB, /mnt/backup, UUID D607-6CE3, fstab nofail). Repo ID 33c56e2979. Daily cron 03:00. Telegram alerts on success/failure. Password in /etc/restic-env.

**SSH config on all nodes:** `ssh node-b/node-c/node-d/node-e` works from node-a (no username needed)

---

# HomeAI Project

## Heimdall (bilingual PL/EN Home Assistant voice assistant, `heimdall/` subdir)
**Status as of 2026-08-20: all 8 original brief tasks + 1 add-on complete.**
Task 7 pushed (`feature/heimdall-task7-test-matrix`), PR not yet
merged — everything else (Tasks 0, 1, 2, 3, 4, 5, 6, 8) merged to `dev`.
Full detail lives in `HomeAI/HANDOFF.md` and `heimdall/*.md` (one doc per
task: `BENCHMARKS.md`, `BAKEOFF_RESULTS.md`, `HA_CONFIG_CHANGES.md`,
`PROJECTNEMO_API.md`, `N8N_ROUTER.md`, `TEST_MATRIX.md`). Quick index:

- **Task 0** — alarm-exposure CI guardrail (`check_no_alarm_exposure.py` +
  GH Action) — never touch anything Satel/alarm-related, enforced in CI.
- **Task 1 (M0)** — GPU/STT baseline benchmark on jaskier.
- **Task 2 (M1)** — Wyoming faster-whisper/piper containers + HA Assist
  pipelines (`Heimdall-EN`/`Heimdall-PL`, Gemini-backed).
- **Task 3 (M2)** — local tool-calling agent bake-off (winner:
  `qwen2.5:7b-instruct`) + full entity exposure to Assist, incl. the gate
  relay (re-exposed at user's explicit request after a risk discussion —
  no per-agent exposure scoping in HA).
- **Task 4 (M3)** — aquarium tools (temp read/history, filter switch) via
  ProjectNemo's real REST API (`heimdall/PROJECTNEMO_API.md`).
- **Task 5 (M4)** — Google Calendar integration. Built a custom
  `heimdall_llm_api` HA component so qwen keeps every tool except
  calendar-write (Gemini keeps full read+write) — HA has no
  per-conversation-agent tool scoping otherwise. 3 real qwen date/tool bugs
  found and fixed (wrong year, wrong tool selection, wrong PL relative-date
  math).
- **Task 6 (M5)** — n8n AI task router on `labserver`
  (`https://n8n.kamilon8n.win`, not the stale `swiss-knife`/`node-a` in
  older infra docs) — bilingual keyword classifier routes to local Ollama
  (open-domain/no-tools) or Gemini via HA `conversation.process`
  (device-control).
- **Task 7 (M6)** — automated live test matrix
  (`heimdall/tests/test_matrix.py`, standalone, not pytest-collected) +
  ntfy-based soak-failure logger (`ntfy_failure_logger.py`, topic
  `heimdall-failures` on `nemo-ntfy`/vesemir). First live run found and
  fixed a real entity-naming bug (phantom Tuya light winning fuzzy-match
  over the real relay); two qwen-only resolution gaps
  (`switch.office_led` ambiguity, climate-alias garbling) were diagnosed
  and accepted as permanent, documented limitations rather than chased
  further. Final result: 25/25 implementable checks passed.
- **Task 8 (M7, add-on, not in original brief)** — persistent
  cross-session conversation memory: FastAPI+SQLite service on jaskier,
  hybrid capture (explicit HA tool calls + a WS-transcript-mining poller
  safety net), injected into both agents' system prompts via a `rest:`
  sensor. Verified cross-session recall in both languages.

**Outstanding, not yet done:** open/merge the Task 7 PR; manually delete a
stray test calendar event ("Gemini regression check", 2026-08-20) via
Google Calendar's UI (no `calendar.delete_event` service exists in this HA
version to automate it).

## Heimdall Phase 1.5 (hardening) + Phase 2 (voice hardware) — plan locked 2026-08-20
Full plan: `heimdall/PHASE1_5_HARDENING_AND_PHASE2_PLAN.md`. Key points:
- **Phase 1.5 backlog (10 items, priority-ordered)** surfaced during Phase 1 build-out.
  Two already resolved during planning recon: #4 (kamilo-assistant stays a separate
  general-purpose assistant, not folded into Heimdall) and #7 (expose_entities.py already
  has a runtime `assert_no_alarm_entities()` check, not just the CI file-scan).
- **Backlog #1 DONE (2026-08-20):** vesemir's ProjectNemo clone was stale/orphaned since the
  2026-08-15 `git-filter-repo` rewrite (zero common ancestor with `origin/dev`). Reset to
  `origin/dev`, committed the real Heimdall config drift, split it into `heimdall.yaml` (HA
  `packages` mechanism), deleted 49 ad hoc `.bak-*` files (one had plaintext secrets),
  gitignored the pattern. Pushed `feature/heimdall-config-sync-20260820` — PR needs manual
  open+merge: https://github.com/winfer70/ProjectNemo/pull/new/feature/heimdall-config-sync-20260820
  **Rotate `heimdall_memory_token`, `influxdb_token`, and the Satel `alarm_code`** — briefly
  printed in plaintext during `check_config --secrets` validation this session (mistake, not
  to be repeated). Also found (not fixed): pre-existing `influxdb.include.component_config`
  schema placement bug, predates this session.
- Still open: exposed Google OAuth `client_secret_*.json` on Desktop root
  (`Kamil/client_secret_914645144271-....json`) needs moving to a password manager or
  deletion — flagged, action pending user confirmation.
- **Phase 2 (M7-M11):** M7 phone/watch quick-trigger (build first, near-zero cost) → M8
  custom "Heimdall" wake word via openWakeWord on jaskier's RTX 3060 → M9 first satellite
  (Raspberry Pi + ReSpeaker, not ESP32 — openWakeWord toolchain more mature) → M10 speaker-ID
  (pyannote/SpeechBrain) → M11 always-listening privacy/security hardening. Sequencing
  decision: M7 now, M8 onward later — not competing approaches.

## Public-repo security remediation (2026-08-15, superseded by above but still relevant)
- **2026-08-15** — Public-repo safety remediation completed: second full `git-filter-repo` pass covered all remaining branches/history, GitHub `main` was aligned to sanitized `dev`, sanitized `feature/matter-server` was left unmerged intentionally, and stale secret-bearing remote branches were deleted. Repo is now safe to make public.
- **Follow-up:** rotate the real WiFi password that was previously exposed in GitHub history; rewritten history may still persist in caches, forks, or scrapers. Re-confirm this was actually done if not independently verified since.
