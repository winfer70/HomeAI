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
