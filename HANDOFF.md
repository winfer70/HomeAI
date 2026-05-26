# HANDOFF — HomeAI / Infra Session
Date: 2026-05-25

## What Was Accomplished

### Cluster recovery after power outage
- REDACTED-HOST: ethernet not in DHCP list — fixed netplan (added `dhcp4: true` to `eno1`), assigned new IP 10.0.0.104 (ethernet MAC `XX:XX:XX:XX:XX:XX`)
- REDACTED-HOST: hardened — `restart=unless-stopped` on all containers, `systemctl enable docker tailscaled`, `wait-network.conf` added
- REDACTED-HOST: came back online on ethernet (WiFi never worked). `wait-network.conf` added.
- REDACTED-HOST: DNS broken — Tailscale MagicDNS returned SERVFAIL for all external domains. Fixed: `tailscale set --accept-dns=false`, `/etc/resolv.conf` → `8.8.8.8, 1.1.1.1`
- cloudflared on REDACTED-HOST: was crash-looping — fixed by adding `dns: [8.8.8.8, 1.1.1.1]` to the cloudflared service in docker-compose.yml (committed + deployed)

### ProjectNemo fixes (REDACTED-HOST)
- nemo-mosquitto: crash-looping. Root causes: log dir owned by `kamilo` (not 1883), passwd file had placeholder hash. Fixed both — container now stable.
- nemo-zigbee2mqtt: crash-looping (no ZBDongle-E connected). Stopped + `docker update --restart=no`. Will re-enable when dongle added.

### ai-agent-stack (REDACTED-HOST)
- ai_agent_dashboard was perpetually unhealthy — root cause: monitor's `/status` runs 8 service checks sequentially with 10s timeouts each (40s+ worst case). Healthcheck timeout was only 10s.
- Fix: parallelized `check_all_services()` with `asyncio.gather()` in `monitor/main.py`. Increased healthcheck timeout 10s → 30s in `docker-compose.yml`. Committed + deployed. Dashboard now healthy.

### Memory / config updates
- All 5 memory files referencing REDACTED-HOST IP updated: .107 → .108
- project_infrastructure.md: added switch speeds, DNS fix, updated Remaining Infra Tasks
- project_services.md: major cleanup — removed stale KamiloPC Ollama / Kali Laptop sections
- ai-agent-stack.md, project_nemo.md: updated to current state
- PROJECT_REGISTRY.md: date + REDACTED-HOST IP updated

### Analysis / planning
- Switch link speeds: REDACTED-HOST 1Gbps ✅, REDACTED-HOST 100Mbps ⚠️, REDACTED-HOST 100Mbps ⚠️, REDACTED-HOST 10Mbps 🔴. Cause: bad cables.
- Docker registry: approved plan — self-hosted `registry:2` on REDACTED-HOST, build on KamiloPC. Docs in `docker-registry.md`.
- Backup: approved plan — restic to REDACTED-HOST HDD (UUID D607-6CE3) + B2. Docs in `homelab-backups.md`. Router USB rejected.

## Current State
- All nodes online and healthy
- All containers stable (no crash loops)
- REDACTED-HOST DNS working
- ai_agent_dashboard healthy

## Exact Next Actions

1. **Replace cables** on REDACTED-HOST and REDACTED-HOST (and REDACTED-HOST if still 100Mbps after autoneg reset). Use Cat5e/Cat6. Run `sudo ethtool -s <iface> autoneg on speed 1000 duplex full` first.
2. **BIOS AC Recovery** — set "Restore on AC Power Loss → Power On" on REDACTED-HOST, REDACTED-HOST, REDACTED-HOST, REDACTED-HOST. Physical access required per machine.
3. **Docker registry on REDACTED-HOST** — run `registry:2` container, add insecure-registries to all nodes, update compose files. See `docker-registry.md`.
4. **Restic backups** — mount HDD on REDACTED-HOST, install restic on all nodes, write backup scripts + cron. See `homelab-backups.md`.
5. **Uptime Kuma UI** — open http://10.0.0.102:3001 and configure monitors.
6. **HomeAI swarm-api** — implement `SWARM_DESIGN.md` → FastAPI code, deploy to REDACTED-HOST.

## Blockers
- None blocking. Cable replacement + BIOS = physical access only.
