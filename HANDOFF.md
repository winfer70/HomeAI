# HANDOFF — HomeAI / Cross-Project Audit + ProjectNemo BLE
Date: 2026-06-08

## What Was Accomplished

### ProjectNemo — BLE Fix
- Root cause confirmed: Fluval Roma/Shaker 2.0 channels 03-06 use 0-100 scale, not 0-255. Old code applied `to255()` multiplier (×2.55), device silently dropped values >100.
- Fix: removed `to255()` in `ui/src/services/bleService.js`. Channels now send `clamp(v)` directly (0-100).
- Commit `5cdff82` deployed to REDACTED-HOST.
- **PENDING VERIFICATION**: tablet hard-reload Chrome → `http://10.0.0.103:3000` → connect Fluval → move R slider → confirm `d1 a1 03 XX` where XX ≤ 0x64

### ProjectNemo — SENSORS.md Rewrite
- Full rewrite with hardware fixes: DS18B20 PVC-only warning, `attenuation: 11db` ESPHome fix, median+moving_average filter combo, ADS1115 Phase A upgrade, 5V/3A PSU, GFCI/RCD mandatory, ground loop Phase B warning, Ireland sourcing table, App UI logic requirements.
- SNZB-02LD + ZBDongle-E already ordered — arriving Tuesday.
- Git disaster (ce5aee3 deleted 85+ tracked files) recovered via commit `07a9daa`.

### Graphify Improvements
- HomeAI post-commit hook installed + patched (`PYTHONUTF8=1`, `python3`→`python`).
- ProjectNemo isolated nodes: 107→35. HomeAI: 97→66.

### Deployment Audit (all projects)
- Docker volume types documented: named volumes vs bind mounts per project.
- SSH users: `kamilo420` on REDACTED-HOST, `kamilo` on REDACTED-HOST — no sudo needed for docker compose.
- Migrations: tickerTap=Alembic (needs `alembic upgrade head`), ProjectNemo=create_all on startup, husariabeats/ai-agent-stack=none. No Prisma/Drizzle anywhere.
- Pre-deploy backup strategy in `memory/deploy_ops.md`.

## Current State
- ProjectNemo: 6 containers running on REDACTED-HOST WiFi (.107). BLE fix deployed, tablet verification pending.
- Obsada CRUD + Telegram power alerts: already implemented (previous session).
- HomeAI swarm (Logician/Devil/Aggregator): NOT yet built.

## Exact Next Actions

1. **Tablet**: Hard-reload Chrome → `http://10.0.0.103:3000` → connect Fluval → verify sliders
2. **Tuesday**: SNZB-02LD + ZBDongle-E arrive → plug into REDACTED-HOST USB (1m extension) → Zigbee2MQTT pair → HA temp entity
3. **ProjectNemo App UI**: Nitrate 60s timer, ammonia 24h suppression, iron tip, pH rate-of-change alert (see SENSORS.md App Logic Requirements)
4. **n8n webhooks**: Telegram bot token + chat ID + 4 webhook IDs → `.env` on REDACTED-HOST before power alerts fire
5. **HomeAI swarm**: Build SWARM_DESIGN.md advisory swarm (Logician/Devil/Aggregator)

## Blockers
- Tablet cache: BLE fix deployed, tablet verification not yet done
- n8n webhooks: need Telegram bot token + chat ID configured
- Zigbee: dongle arriving Tuesday
