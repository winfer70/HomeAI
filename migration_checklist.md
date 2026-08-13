# Home Lab Migration Checklist
**Generated: 2026-05-15**
**Goal: Move all devices to server room, fix broken Ollama dependency, add monitoring + backup**
**Network: LabLAN AX5400 in router mode. Lab subnet: 192.168.0.x. Gateway: <LAN_IP>. LabLAN LAN = 192.168.0.x (confirmed from DHCP reservations).**

---

## Legend
- `[ ]` = todo
- `[x]` = done
- `[!]` = manual/physical step
- `[P]` = pending (future phase, skip now)

---

## PHASE 0 — Pre-Migration (do before moving hardware)

### 0.1 Data Safety — node-b
```
[x] 0.1.1  N/A — node-b wiped (was prior Linux laptop), backup confirmed done to node-a /home/user/backups/node-b/ (see 2.0.1)

[x] 0.1.2  N/A — models re-pulled on node-b (see 2.4.3): qwen3:4b, qwen3:8b, deepseek-r1:8b, codestral:22b, llama3:8b-instruct-q4_K_M
```

### 0.2 Network Setup

**⚠️ CONNECTIVITY NOTE: WiFi-first phase**
All lab devices connect via WiFi to LabLAN AX5400 (Wi-Fi 6) initially.
Ethernet switch (old TP-Link in dumb mode) deferred until cable arrives.
Cable arrives → do step 0.2.5 then.

```
[x] 0.2.0  LabLAN confirmed router mode, LAN = 192.168.0.x. All node IPs use 192.168.0.x as listed.

[x] 0.2.1  DHCP reservations in LabLAN AX5400 router
            (NOT Vodafone router — lab devices connect through LabLAN)
            MAC → IP mapping (confirmed 2026-05-16):
              node-a WiFi    08-D4-0C-77-38-0A → <LAN_IP> ✓
              node-a ETH     D8-CB-8A-DA-7D-D6 → <LAN_IP> ✓
              node-b (Ubuntu inst.) 28-16-AD-97-71-79 → <LAN_IP> ✓  (LabLAN shows "ubuntu-server" — update to "node-b" after 2.1.1)
              node-c (HP Pavil.)  48-5A-B6-03-F7-B1 → <LAN_IP> ✓  (LabLAN label fixed to "node-c" ✓)
              workstation             DC-97-BA-89-AD-FF → <LAN_IP> ✓
              node-e (MacBook)   A8-66-7F-1A-7C-69 → <LAN_IP> ✓  (already reserved — keep .226 or renumber, see note)
              node-d                B8-EE-65-F7-26-C2 → <LAN_IP> ✓  (add reservation in LabLAN)
            NOTE node-e: .226 is valid but ugly. If you want a clean number (e.g. .105),
            change reservation in LabLAN before first-time setup on node-e.
            ⚠️  LabLAN label fix remaining:
              - Rename "ubuntu-server" (.102) → "node-b" in router after hostname set (step 2.1.1)
            Where: LabLAN admin panel → Advanced → DHCP → Address Reservation

[x] 0.2.2  MACs collected (see 0.2.1 above — all confirmed 2026-05-16)

[!] 0.2.3  DEFERRED — Configure old TP-Link as dumb switch
            Wait for long ethernet cable to arrive.
            When cable arrives:
            - Old TP-Link: disable DHCP, unplug WAN port
            - Run cable: LabLAN LAN port → switch uplink port
            - Connect each lab node to switch via ethernet
            - Update all nodes to static ethernet IPs (same IPs, different interface)

[!] 0.2.4  DEFERRED — Run ethernet cable to server room
            Order/arrive first, then do 0.2.3
```

---

### 0.3 node-a IP Transition

```
[x] 0.3.1  Done — Phase 1 steps already used correct new IPs ✓

[x] 0.3.2  Cloudflare A records ✓ — WAN IP 109.76.52.152, sites reachable (husariabeats.com 200, ticker-tap.com 200)

[!] 0.3.3  Cloudflare Tunnel (n8n + dashboard) — NO ACTION NEEDED
            node-a-n8n tunnel connects outbound from cloudflared container.
            No IP config in Cloudflare for tunnels — they work regardless of public IP.

[x] 0.3.4  Port forwarding on LabLAN ✓ — 80/443 → <LAN_IP> confirmed (public sites reachable)

[x] 0.3.5  Public sites verified ✓ — husariabeats.com 200, ticker-tap.com 200

[x] 0.3.6  monitor/main.py and worker/main.py — NO ACTION NEEDED
            node-a keeps same IP (.139) on LabLAN. Hardcoded IPs in these files are already correct:
              monitor/main.py: <LAN_IP>:8000/health ✓
              worker/main.py:  WOL_BROADCAST_IP default <LAN_IP> ✓

[x] 0.3.7  .env.production remaining IP vars — NO ACTION NEEDED
            SWISS_KNIFE_IP, KALI_TRADING_IP, WOL_BROADCAST_IP all already correct values.
            Only OLLAMA_PRIMARY_ENDPOINT needs changing → handled in Phase 1.1.1
```

---

## PHASE 1 — node-a Changes (no reinstall, just config)
**Host: <LAN_IP> | i3-6100 | 7.7GB RAM | 913GB disk**
**Already running: nginx, TickerTap, HusariaBeats, ai-agent-stack (18 containers)**

### 1.1 Fix Broken Ollama Endpoint (HIGHEST PRIORITY — do this first after node-b Ollama is up)
```
[x] 1.1.1  Update ai-agent-stack Ollama endpoint ✓
            OLLAMA_PRIMARY_ENDPOINT=http://<LAN_IP>:11434 confirmed

[x] 1.1.2  Restart ai-agent-stack worker ✓ — ai_agent_worker Up (healthy) 

[x] 1.1.3  Telegram chat works end-to-end ✓ — bot responds (fixed corrupted shared_workflow PK index via REINDEX)

[x] 1.1.4  Update TickerTap Ollama URL ✓ — OLLAMA_URL=http://<LAN_IP>:11434, app restarted
```

### 1.2 Tailscale (remote access + subnet routing)
```
[x] 1.2.1  Install Tailscale ✓
[x] 1.2.2  Brought up with SSH + subnet routing (<LAN_IP>/24) ✓ — 100.64.0.99
            IPv6 forwarding enabled, UDP GRO fixed on enp1s0
[x] 1.2.3  Tailscale subnet route approved ✓ (confirmed via tailscale status)
[x] 1.2.4  Remote SSH via Tailscale verified ✓
```

### 1.3 AdGuard Home (DNS ad blocker for whole LAN)
```
[x] 1.3.1  Disable systemd-resolved stub listener ✓ — port 53 freed
[x] 1.3.2  AdGuard Home deployed ✓ — container up, http://<LAN_IP>:3000 → setup wizard
[x] 1.3.3  Setup wizard complete ✓ — admin on :3000, DNS on :53, credentials set
            NOTE: wizard typo (port 300) fixed via docker exec sed on config
[x] 1.3.4  LabLAN DNS → <LAN_IP> ✓
[x] 1.3.5  DNS verified from all 5 nodes ✓ — resolving via AdGuard (ProtonDNS upstream)
            Blocklists: AdGuard DNS filter (165k) + AdAway (6.5k) + OISD Full (402k) = 573k+ rules
            Upstream: ProtonDNS 194.242.2.4 / 193.110.81.2 (ad+malware blocking)
```

### 1.4 Restic Backups to External HDD
```
[x] 1.4.1  Install restic ✓
            sudo apt install -y restic

[x] 1.4.2  External HDD backup target configured ✓
            1TB exFAT drive, label "Project", mounted at /mnt/backup
            UUID: D607-6CE3 — added to /etc/fstab with nofail
            (Changed from Backblaze B2 — using local external HDD instead)

[x] 1.4.3  /etc/restic-env created, chmod 600 ✓
            RESTIC_REPOSITORY=/mnt/backup/restic-repo
            RESTIC_PASSWORD=<passphrase>

[x] 1.4.4  Restic repo initialized ✓
            Repo path: /mnt/backup/restic-repo (ID 33c56e2979)

[x] 1.4.5  /usr/local/bin/restic-backup.sh created ✓
            Backs up: postgres dump + /home/user/ai-agent-stack + /home/user/projects
            Telegram alerts on success/failure

[x] 1.4.6  First backup tested ✓
            Snapshot: e44bdb08 | Size: 1.86GB

[x] 1.4.7  Daily cron 03:00 added to root crontab ✓
            0 3 * * * /usr/local/bin/restic-backup.sh >> /var/log/restic-backup.log 2>&1
```

### 1.5 node_exporter (for Prometheus on node-c to scrape)
```
[x] 1.5.1  node_exporter installed + running ✓ — v1.8.2, active at :9100
            NOTE: also installed on node-b (missed in 2.x) + opened UFW port 9100
            NOTE: installed on node-e as native binary + launchd agent
            All 5 targets UP in Prometheus: node-a, node-b, node-c, node-d, node-e
```

---

## PHASE 2 — node-b Fresh Setup (was prior Linux laptop)
**Host: <LAN_IP> | username: deploy | i5 | 16GB RAM | headless laptop with battery backup**
**Purpose: Ollama inference + Redis + ChromaDB + NATS + SearXNG**
**Device: node-b — Ubuntu Server 24.04 installed ✓ (confirmed online at <LAN_IP>, hostname currently "ubuntu-server" — set to "node-b" in 2.1.1)**

### 2.0 Pre-wipe
```
[x] 2.0.1  Confirm node-b data backed up (see Phase 0.1) — backup done to node-a /home/user/backups/node-b/ ✓
[x] 2.0.2  tickertap-worker stopped (was on prior Linux laptop, wiped) ✓
```

### 2.1 OS Install
```
[x] 2.1.1  Ubuntu Server 24.04 LTS installed ✓ — online at <LAN_IP>
            Hostname currently "ubuntu-server" — run to fix:
            sudo hostnamectl set-hostname node-b
            sudo sed -i 's/127.0.1.1.*/127.0.1.1\tREDACTED-HOST/' /etc/hosts
            Then update LabLAN label "ubuntu-server" → "node-b" ✓ DONE

[x] 2.1.2  First boot — system update ✓
            sudo apt update && sudo apt full-upgrade -y && sudo apt autoremove -y
            sudo apt install -y curl wget git vim htop net-tools dnsutils \
              python3-pip build-essential ca-certificates gnupg lsb-release

[x] 2.1.3  Disable swap (required for Ollama performance) ✓
            sudo swapoff -a
            sudo sed -i '/\bswap\b/d' /etc/fstab
            sudo rm -f /swapfile
            sudo systemctl disable --now systemd-zram-setup@zram0.service 2>/dev/null || true
            # Verify after reboot: free -h → Swap: 0B 0B 0B

[x] 2.1.4  Disable lid-close suspend (headless laptop) ✓
            sudo tee -a /etc/systemd/logind.conf <<'EOF'

            HandleLidSwitch=ignore
            HandleLidSwitchExternalPower=ignore
            HandleLidSwitchDocked=ignore
            EOF
            sudo systemctl kill -s HUP systemd-logind

[x] 2.1.5  UFW firewall — LAN-scoped for all sensitive ports ✓
            sudo ufw default deny incoming
            sudo ufw default allow outgoing
            sudo ufw allow 22/tcp comment 'SSH'
            sudo ufw allow from <LAN_IP>/24 to any port 11434 proto tcp comment 'Ollama'
            sudo ufw allow from <LAN_IP>/24 to any port 6379 proto tcp comment 'Redis'
            sudo ufw allow from <LAN_IP>/24 to any port 8009 proto tcp comment 'ChromaDB'
            sudo ufw allow from <LAN_IP>/24 to any port 4222 proto tcp comment 'NATS'
            sudo ufw allow from <LAN_IP>/24 to any port 8222 proto tcp comment 'NATS monitor'
            sudo ufw allow from <LAN_IP>/24 to any port 8888 proto tcp comment 'SearXNG'
            sudo ufw allow from 100.64.0.0/10 comment 'Tailscale'
            sudo ufw --force enable

[x] 2.1.6  Reboot ✓
```

### 2.2 Docker
```
[x] 2.2.1  Install Docker CE ✓ — Docker 29.5.0
            sudo install -m 0755 -d /etc/apt/keyrings
            curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
              | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
            sudo chmod a+r /etc/apt/keyrings/docker.gpg
            echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
              https://download.docker.com/linux/ubuntu \
              $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
              | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
            sudo apt update
            sudo apt install -y docker-ce docker-ce-cli containerd.io \
              docker-buildx-plugin docker-compose-plugin
            sudo usermod -aG docker $USER
            sudo systemctl enable --now docker
            newgrp docker
            # Verify:
            docker --version && docker compose version
```

### 2.3 Tailscale
```
[x] 2.3.1  Install and connect ✓ — 100.120.73.19 (node-b)
            curl -fsSL https://tailscale.com/install.sh | sh
            sudo tailscale up --ssh
            # Approve in Tailscale admin console
            # Verify: tailscale status
```

### 2.4 Ollama
```
[x] 2.4.1  Install Ollama ✓
[x] 2.4.2  Configure Ollama to listen on all interfaces ✓ — OLLAMA_HOST=0.0.0.0, confirmed 0.0.0.0:11434
[x] 2.4.3  Pull models ✓ — all 5 models pulled (qwen3:4b, qwen3:8b, deepseek-r1:8b, codestral:22b, llama3:8b-instruct-q4_K_M)
[x] 2.4.4  Verify Ollama reachable from node-a ✓ — curl confirmed qwen3:4b in response
```

### 2.5 Docker Compose Stack (Redis, ChromaDB, NATS, SearXNG)
```
[x] 2.5.1  Create directory and SearXNG config ✓ — /home/deploy/node-b-stack/searxng/settings.yml

[x] 2.5.2  Write docker-compose.yml ✓ — /home/deploy/node-b-stack/docker-compose.yml
            NOTE: path changed from /home/server/ → /home/deploy/ (no sudo on node-b)
            NOTE: --max_payload removed from NATS command (not a valid CLI flag)

[x] 2.5.3  Start stack ✓ — all 4 containers up

[x] 2.5.4  Validate all services ✓
            redis:   PONG ✓
            chroma:  /api/v2/heartbeat ✓ (v2 API)
            nats:    {"status":"ok"} ✓
            searxng: 200 ✓

[x] 2.5.5  Full reboot smoke test ✓ — all 4 containers + Ollama back up after reboot
```

---

## PHASE 3 — node-c + node-e Setup
**node-c: <LAN_IP> | username: deploy | i5 | 8GB RAM | already running lightly | Ubuntu Server**
**node-e: <LAN_IP> | MAC A8-66-7F-1A-7C-69 | MacBook Intel Core M 1.2GHz | 8GB DDR3 | Intel HD 5300 | macOS Big Sur**
**⚠️ node-e uses Colima (not Docker Desktop — Big Sur not supported). No systemd — use Homebrew services + launchd.**

---

### Phase 3a — node-c (Compute Node — Docker, Tailscale, node_exporter only)
**Role: Compute — swarm-api agents, extra Ollama models, HomeAI (future). No Prometheus/Grafana/news-worker.**

> **NOTE: Ubuntu 26.04 LTS already installed. Skip OS install. Battery healthy (100% capacity, 39.4Wh). Has built-in UPS — same as node-b.**

### 3a.0 One-time hostname fix (hostname was "vesimir", corrected to "node-c")
```
[x] 3a.0.1  Hostname already set via hostnamectl. Fix /etc/hosts if it still has the old typo "vesimir":
            sudo sed -i 's/vesimir/node-c/g' /etc/hosts
            cat /etc/hosts | grep node-c
            # Should show: 127.0.1.1   node-c
```

### 3a.1 Base Setup
```
[x] 3a.1.1  System update + packages ✓
[x] 3a.1.2  Docker 29.5.0 installed ✓
[x] 3a.1.3  Tailscale connected ✓ — 100.72.171.14 (node-c, winfer70@)
```

### 3a.2 node_exporter (for node-e Prometheus to scrape)
```
[x] 3a.2.1  node_exporter installed + running ✓ — metrics at :9100
```

---

### Phase 3b — node-e (Monitoring Node — MacBook, macOS Big Sur)

### 3b.1 DHCP Reservation
```
[x] 3b.1.1  MAC confirmed: A8-66-7F-1A-7C-69 → <LAN_IP> (reservation exists in LabLAN as "Kamils-MacBook")
            Optionally rename label in LabLAN to "node-e".
            If you want cleaner IP (e.g. .105), update LabLAN reservation BEFORE running node-e setup.
```

### 3b.2 Prevent Sleep with Lid Closed
```
[x] 3b.2.2  Disable sleep via pmset ✓
            sudo pmset -a sleep 0 disksleep 0 hibernatemode 0

[x] 3b.3.1  Install Homebrew ✓ — v5.1.11 (Big Sur compatible, unshallowed)

[x] 3b.4.1  Colima + Docker — SKIPPED: macOS Big Sur too old (Go requires Monterey+)
            Using native Prometheus + Grafana binaries instead (no Docker needed)

[x] 3b.5.1  Colima autostart — N/A (no Colima)

[x] 3b.6.1  prometheus.yml written ✓ — ~/monitoring/prometheus.yml
            Targets: node-a, node-b, node-c, node-d, node-e (:9100) + n8n (:5678)

[x] 3b.7.1  Prometheus installed ✓ — native binary ~/monitoring/prometheus
            launchd: com.prometheus (auto-start, keep-alive)

[x] 3b.7.2  Grafana installed ✓ — native binary ~/grafana/bin/grafana v11.1.0
            launchd: com.grafana (auto-start, keep-alive)
            Prometheus: http://<LAN_IP>:9090 ✓ (200)
            Grafana:    http://<LAN_IP>:3000 ✓ (302 → login)
```

### 3b.3 Install Homebrew
```
[x] 3b.3.1  Homebrew installed ✓ — Big Sur compatible
```

### 3b.4 Install Colima + Docker CLI
```
[x] 3b.4.1  SKIPPED — Big Sur too old for Colima (Go requires Monterey+). Using native binaries.
```

### 3b.5 Configure Colima Autostart
```
[x] 3b.5.1  N/A — no Colima
```

### 3b.6 Write prometheus.yml
```
[ ] 3b.6.1  Create monitoring directory and write prometheus.yml
            mkdir -p ~/monitoring
            cat > ~/monitoring/prometheus.yml <<'EOF'
            global:
              scrape_interval: 15s
              evaluation_interval: 15s

            scrape_configs:
              - job_name: 'node_exporter'
                static_configs:
                  - targets: ['<LAN_IP>:9100']
                    labels: {instance: 'node-a'}
                  - targets: ['<LAN_IP>:9100']
                    labels: {instance: 'node-b'}
                  - targets: ['<LAN_IP>:9100']
                    labels: {instance: 'node-c'}
                  - targets: ['<LAN_IP>:9100']
                    labels: {instance: 'node-d'}
                  - targets: ['<LAN_IP>:9100']
                    labels: {instance: 'node-e'}
              - job_name: 'n8n'
                metrics_path: '/metrics'
                static_configs:
                  - targets: ['<LAN_IP>:5678']
                    labels: {instance: 'node-a'}
            EOF
```

### 3b.7 Start Prometheus + Grafana via Docker Compose
```
[ ] 3b.7.1  Write docker-compose.yml
            cat > ~/monitoring/docker-compose.yml <<'EOF'
            services:
              prometheus:
                image: prom/prometheus:latest
                container_name: prometheus
                restart: unless-stopped
                ports:
                  - "9090:9090"
                volumes:
                  - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
                  - prometheus_data:/prometheus
                command:
                  - '--config.file=/etc/prometheus/prometheus.yml'
                  - '--storage.tsdb.path=/prometheus'
                  - '--storage.tsdb.retention.time=30d'
                  - '--web.enable-lifecycle'
              grafana:
                image: grafana/grafana:latest
                container_name: grafana
                restart: unless-stopped
                ports:
                  - "3000:3000"
                volumes:
                  - grafana_data:/var/lib/grafana
                environment:
                  - GF_SECURITY_ADMIN_USER=admin
                  - GF_SECURITY_ADMIN_PASSWORD=changeme
                  - GF_USERS_ALLOW_SIGN_UP=false
                depends_on:
                  - prometheus
            volumes:
              prometheus_data:
              grafana_data:
            EOF

[ ] 3b.7.2  Start stack
            cd ~/monitoring && docker compose up -d
            # Verify: curl -s http://localhost:9090/-/healthy
            #         →  "Prometheus Server is Healthy."

[x] 3b.7.3  Grafana configured ✓ — Prometheus datasource (http://localhost:9090) + Node Exporter Full dashboard (ID 1860) imported
```

### 3b.8 Migrate tickertap-worker (news scorer) — macOS / launchd
```
[x] 3b.8.1  N/A — model is qwen3.5:9b (replaced llama3:8b-instruct-q4_K_M), already on node-b ✓
[x] 3b.8.2  Worker files rsynced ✓ — source: node-a /home/user/projects/finance/tickerTap/server-b-worker/ → node-e /opt/tickertap-worker/
[x] 3b.8.3  Venv created + deps installed ✓ — Python 3.8.9 on node-e
[x] 3b.8.4  Smoke test ✓ — Ollama 200, TickerTap server 200
[x] 3b.8.5  launchd plist created ✓ — ~/Library/LaunchAgents/com.tickertap.worker.plist (qwen3.5:9b)
[x] 3b.8.6  Worker loaded + running ✓ — PID 4882, scoring articles (45 fetched, cycle 1 started)
[x] 3b.8.7  N/A — worker was on old prior Linux laptop (wiped), nothing to stop on node-b
```

### 3b.9 Validate All Services on node-e
```
[x] 3b.9.1  Prometheus scraping all nodes ✓ — node-a, node-b, node-c, node-d, node-e all up

[x] 3b.9.2  Grafana accessible ✓ — 302 on :3000

[x] 3b.9.3  tickertap-worker running ✓ — PID active, scoring articles via qwen3.5:9b

[x] 3b.9.4  Full reboot smoke test (node-e) ✓
            All 4 services came back: prometheus, grafana, node-exporter, tickertap-worker
            Prometheus healthy ✓, Grafana v11.1.0 DB ok ✓
            sudo pmset -a autorestart 1  — power-outage auto-restart enabled ✓
```

---

## PHASE 4 — node-d Setup (fresh install, dead battery)
**Host: <LAN_IP> | MAC: B8-EE-65-F7-26-C2 | i3 | 4-6GB RAM | dead battery | stateless only**

### 4.1 OS Install
```
[x] 4.1.1  Install Ubuntu Server 24.04 LTS ✓ — Ubuntu 26.04, hostname: node-d, username: deploy, online at <LAN_IP>
            - Hostname: node-d
            - Username: deploy
            - Enable OpenSSH: YES
            - Full disk, default LVM
            # After install, confirm/set hostname:
            sudo hostnamectl set-hostname node-d
            # Update /etc/hosts:
            sudo sed -i 's/127.0.1.1.*/127.0.1.1\tnode-d/' /etc/hosts

[!] 4.1.2  BIOS: set AC Recovery to "Power On"
            Boot into BIOS (Del or F2 during POST)
            → Power Management → AC Power Recovery → Power On
            Save and exit
            TEST: cut mains power, restore → node-d should boot automatically

[x] 4.1.3  System update ✓ — packages installed

[x] 4.1.4  Install Docker ✓ — Docker 29.5.0, deploy user in docker group

[x] 4.1.5  Install Tailscale ✓ — 100.83.75.16 (node-d)
```

### 4.2 Wake-on-LAN
```
[x] 4.2.1  Enable WoL on boot via udev rule ✓ — interface eno1, wol g set, /etc/udev/rules.d/99-wol.rules created
            # Get interface name:
            IFACE=$(ip -o link show | awk '$2 != "lo:" {print $2}' | tr -d ':' | head -1)
            echo "Interface: $IFACE"

            # Set immediately:
            sudo ethtool -s "$IFACE" wol g
            sudo ethtool "$IFACE" | grep 'Wake-on'  # should show: g

            # Persist via udev:
            sudo tee /etc/udev/rules.d/99-wol.rules <<EOF
            SUBSYSTEM=="net", ACTION=="add", KERNEL=="${IFACE}", RUN+="/usr/sbin/ethtool -s ${IFACE} wol g"
            EOF
            sudo udevadm control --reload-rules
            # Verify after reboot: sudo ethtool $IFACE | grep 'Wake-on'  → g
```

### 4.3 node_exporter
```
[x] 4.3.1  Install node_exporter ✓ — v1.8.2, active at :9100
            NE_VER=1.8.2
            wget -q -O /tmp/ne.tgz \
              "https://github.com/prometheus/node_exporter/releases/download/v${NE_VER}/node_exporter-${NE_VER}.linux-amd64.tar.gz"
            tar -xzf /tmp/ne.tgz -C /tmp
            sudo cp /tmp/node_exporter-${NE_VER}.linux-amd64/node_exporter /usr/local/bin/node_exporter
            sudo useradd -rs /bin/false node_exporter 2>/dev/null || true
            sudo tee /etc/systemd/system/node_exporter.service <<'EOF'
            [Unit]
            Description=Prometheus Node Exporter
            After=network.target
            [Service]
            User=node_exporter
            ExecStart=/usr/local/bin/node_exporter
            Restart=on-failure
            [Install]
            WantedBy=multi-user.target
            EOF
            sudo systemctl daemon-reload && sudo systemctl enable --now node_exporter
```

### 4.4 Uptime Kuma
```
[x] 4.4.1  Create and start Uptime Kuma ✓ — healthy at <LAN_IP>:3001
            sudo mkdir -p /opt/uptime-kuma
            sudo chown -R $USER:$USER /opt/uptime-kuma
            cat > /opt/uptime-kuma/docker-compose.yml <<'EOF'
            services:
              uptime-kuma:
                image: louislam/uptime-kuma:1
                container_name: uptime-kuma
                restart: unless-stopped
                ports:
                  - "3001:3001"
                volumes:
                  - uptime_kuma_data:/app/data
            volumes:
              uptime_kuma_data:
            EOF
            cd /opt/uptime-kuma && docker compose up -d
            # Verify: curl -s -o /dev/null -w "%{http_code}" http://localhost:3001  → 200

[ ] 4.4.2  Create admin account
            Open the Uptime Kuma UI on the target node — set a local admin username and password

[ ] 4.4.3  Add monitors (in Uptime Kuma UI — Add New Monitor, interval 60s each)

            Monitor 1: "node-b Ollama"
              Type: HTTP(s)
              URL: http://<LAN_IP>:11434/api/tags
              Expected HTTP code: 200

            Monitor 2: "node-b NATS"
              Type: TCP Port
              Host: <LAN_IP>  Port: 4222

            Monitor 3: "node-b Redis"
              Type: TCP Port
              Host: <LAN_IP>  Port: 6379

            Monitor 4: "node-c Prometheus"
              Type: HTTP(s)
              URL: http://<LAN_IP>:9090/-/healthy
              Expected HTTP code: 200

            Monitor 5: "node-a n8n"
              Type: HTTP(s)
              URL: http://<LAN_IP>:5678/healthz

            Monitor 6: "node-a AdGuard"
              Type: HTTP(s)
              URL: http://<LAN_IP>:3000
              Note: add AFTER AdGuard deployed (Phase 1.3)

            Monitor 7: "node-d Uptime-Kuma self"
              Type: HTTP(s)
              URL: http://<LAN_IP>:3001
```

---

## PHASE 5 — External Monitoring (UptimeRobot)
**Survives power outage — independent of all local nodes**

```
[x] 5.1  UptimeRobot account created ✓

[x] 5.2  5 monitors added ✓: husariabeats.com, admin.husariabeats.com, dashboard.kamilon8n.win, ticker-tap.com, n8n.kamilon8n.win

[x] 5.3  ticker-tap.com monitor added ✓

[x] 5.4  Email alert contact configured ✓ (Telegram requires paid plan — using email instead)
```

---

## PHASE 6 — Post-Migration Validation

### 6.1 Full System Check
```
[ ] 6.1.1  From node-a — verify all containers healthy
            docker ps --format "table {{.Names}}\t{{.Status}}" | grep -v healthy
            # Should return empty (all healthy)

[ ] 6.1.2  End-to-end Telegram AI chat test
            Send message to Telegram bot → expect LLM response
            (confirms: Telegram → n8n → ai-agent-worker → Ollama@node-b → response)

[ ] 6.1.3  TickerTap news ingestion test
            # Check recent news arrived from node-c worker:
            docker exec tickertap-app-1 curl -s http://localhost:8000/api/v1/news?limit=5 \
              | python3 -m json.tool | head -30

[ ] 6.1.4  HusariaBeats release workflow test
            Trigger test webhook (private mode):
            curl -X POST https://n8n.kamilon8n.win/webhook/husariabeats-release-test \
              -H "Content-Type: application/json" -d '{"test":true}'

[ ] 6.1.5  Restic backup test
            source /etc/restic-env && restic snapshots
            # Should show at least one snapshot

[ ] 6.1.6  DNS via AdGuard test
            nslookup google.com <LAN_IP>
            # Should resolve — confirm AdGuard logs show the query

[ ] 6.1.7  Tailscale remote access test
            From phone/laptop off WiFi → ssh node-a via Tailscale IP
            Confirm: full LAN reachable through subnet route
            ssh -J <tailscale-ip-node-a> kamilo420@<LAN_IP>
            # Should land on node-c without VPN configuration

[ ] 6.1.8  Power outage simulation
            Cut power to node-a + node-c + node-d (keep node-b on battery)
            Confirm: UptimeRobot fires Telegram alert within 5 min
            Restore power:
            - node-a: powers on (always-on power supply)
            - node-d: powers on automatically (BIOS AC Recovery → Power On)
            - node-c: has built-in battery (UPS) — same as node-b, stays up through brief outages
            Confirm all services recover automatically

[ ] 6.1.9  Grafana dashboards populated (on node-e)
            Open http://<LAN_IP>:3000
            Confirm: all nodes showing CPU/RAM/disk metrics

[ ] 6.1.10 node-e services fully operational
            # From node-e:
            colima status                                           # Running
            docker compose -f ~/monitoring/docker-compose.yml ps  # prometheus + grafana Up
            curl -s http://localhost:9090/api/v1/targets \
              | python3 -m json.tool | grep '"health"'             # all "up"
            launchctl list | grep tickertap                        # news worker PID present
            tail -10 /tmp/tickertap-worker.log                     # no fatal errors
```

### 6.2 IP Config Audit — Nothing Pointing to Old IPs
```
[ ] 6.2.1  No reference to old node-b IP (<LAN_IP>) anywhere
            grep -r "<LAN_IP>" \
              /home/user/ai-agent-stack/ \
              /home/user/projects/ \
              2>/dev/null

[ ] 6.2.2  No reference to Windows laptop Ollama (<LAN_IP>) anywhere
            grep -r "<LAN_IP>" \
              /home/user/ai-agent-stack/ \
              /home/user/projects/ \
              2>/dev/null
            # Both should return empty
```

---

## PENDING (Future Phases — not blocking migration)
```
[P]  swarm-api Phase 1 (FastAPI + 3 agents + n8n workflows on node-b)
[P]  financial-api on financial laptop (Phase 2 swarm enrichment)
[P]  HomeAI Python package as systemd service on node-b
[P]  n8n workflow export → git commit cron (nightly change history)
[P]  Ansible playbooks for all 4 nodes (idempotent reprovisioning)
[P]  Grafana alerting rules → Telegram (complement Uptime Kuma)
[P]  node-a: add trading-ml service to TickerTap compose (if ML features needed)
```

---

## Quick Reference — All Static IPs
| Node | IP | Role |
|------|----|------|
| node-a (node-a) | <LAN_IP> | Main server — nginx, TickerTap, HusariaBeats, ai-agent-stack |
| node-b | <LAN_IP> | AI inference — Ollama, Redis, ChromaDB, NATS, SearXNG |
| node-c | <LAN_IP> | Compute — swarm-api, extra Ollama, HomeAI (future) (HP Pavilion 17, Ubuntu 26.04, healthy battery) |
| node-d | <LAN_IP> | Aux — Uptime Kuma |
| node-e | <LAN_IP> | Monitoring — Prometheus, Grafana, news worker (MacBook, macOS Big Sur) |
| workstation (Windows) | <LAN_IP> | Daily driver — Ollama until node-b ready |

## Quick Reference — Key Env Fixes Done
| File | Old Value | New Value |
|------|-----------|-----------|
| ai-agent-stack/.env.production | `OLLAMA_PRIMARY_ENDPOINT=http://<LAN_IP>:11434` | `http://<LAN_IP>:11434` |
| tickerTap/.env.prod | `OLLAMA_URL=http://<LAN_IP>:11434` | `http://<LAN_IP>:11434` |
| node-e tickertap-worker (launchd) | `OLLAMA_URL=http://localhost:11434` | `http://<LAN_IP>:11434` |
| ai-agent-stack/.env.production (monitor) | `monitor TickerTap URL=http://<LAN_IP>:8000/health` | `http://<LAN_IP>:8000/health` |
