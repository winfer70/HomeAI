# Home Lab Infrastructure Plan — Corrected & Complete
> Written 2026-05-15. Supersedes the Google AI conversation.
> Addresses 10 specific failures in that advice.

> **Node naming convention:** Witcher characters — REDACTED-HOST (main), REDACTED-HOST (AI), REDACTED-HOST (data/monitoring), REDACTED-HOST (aux). REDACTED-HOST and REDACTED-HOST are already live with their IPs assigned.

---

## 1. Hardware Inventory

| Label  | Hardware                          | RAM  | CPU | Battery | OS Target          |
|--------|-----------------------------------|------|-----|---------|-------------------|
| REDACTED-HOST | Old PC                            | 8 GB | i3  | wall    | Ubuntu Server 24.04 |
| REDACTED-HOST | Ex-Kali Laptop                    | 16 GB| i5  | ok      | Ubuntu Server 24.04 |
| REDACTED-HOST | Second Laptop                     | 8 GB | i5  | ok      | Ubuntu Server 24.04 |
| REDACTED-HOST | Old Laptop                        | 4-6 GB | i3 | DEAD  | Ubuntu Server 24.04 |
| daily  | Windows Laptop (i9/32GB)          | 32 GB| i9  | ok      | Windows — NOT a server |

---

## 2. Final Node Role Assignments (these do not change)

The original AI shifted the ex-Kali laptop through three different roles across the conversation.
That oscillation ends here. Assignments are driven by two hard constraints:
- DNS must run on the most reliable node (power-safe, no battery dependency).
- AI inference needs the most RAM; it should not share a node with infrastructure services.

### REDACTED-HOST — Primary / Orchestration
**Services:** caddy, n8n, AdGuard Home, Uptime Kuma, cloudflared (Cloudflare Tunnel daemon),
husariabeats.com, ticker-tap.com backend

> **Current state (2026-05-15):** REDACTED-HOST already runs nginx (not Caddy) as the reverse proxy and already has a Cloudflare Tunnel running (REDACTED-HOST-n8n). Do not replace nginx with Caddy — extend what exists. Add AdGuard and Tailscale only.

**Why AdGuard here, not on the weak node:** REDACTED-HOST is on wall power and already runs 24/7.
DNS is critical infrastructure. Putting it on the weakest or most unreliable node creates a
single point of failure for every device on your network. AdGuard Home uses under 50 MB RAM
at idle — it adds no meaningful load to REDACTED-HOST.

### REDACTED-HOST — AI / Inference (dedicated)
**Services:** Ollama, HomeAI application stack, Redis, ChromaDB, NATS, SearXNG

**Why nothing else here:** 16 GB RAM sounds like a lot until Ollama loads a 7B Q4 model
(~4.5 GB), Redis, ChromaDB, and a few Python services. Leave this node for AI work only.
No DNS, no monitoring dashboards, no reverse proxy.

### REDACTED-HOST — Data / Secondary
**Services:** news article scoring script, Prometheus, Grafana, ticker-tap data pipeline

**Why here:** i5/8GB is strong enough for the scoring script plus a monitoring stack.
Prometheus + Grafana use ~300-500 MB combined. This node also serves as hot standby
if REDACTED-HOST needs maintenance.

### REDACTED-HOST — Auxiliary / Experiments (dead battery)
**Services:** stateless workloads only — see Section 10 for the battery caveat.
Candidates: WireGuard exit node (stateless config), secondary SearXNG instance,
load test target. Never run DNS, databases, or monitoring here.

---

## 3. Network Topology — Server Room Move

### Current (correct BezReklam setup, keep it)

```
Internet
    |
[Vodafone Router — 192.168.0.1] (downstairs)
    |  (WiFi backhaul or ethernet to extender)
[Vodafone Extender] (office — has ethernet ports)
    |
    +-- [BezReklam Office Router — WAN port]
            10.0.2.1 (separate subnet, DHCP on)
            WiFi for office devices
```

This is already correct. The BezReklam WAN-in from the extender creates proper subnet
separation. Do not change this.

### Adding the Server Room

Run a single ethernet cable from the Vodafone extender to the server room.
Use one TP-Link router as a **dumb switch** — LAN port to LAN port, DHCP disabled.

```
[Vodafone Extender] (office)
    |
    | ethernet run to server room
    |
[TP-Link — DUMB SWITCH MODE]
    LAN1 — REDACTED-HOST (10.0.0.107, static)
    LAN2 — REDACTED-HOST (10.0.0.112, static)
    LAN3 — REDACTED-HOST (10.0.0.103, static)
    LAN4 — REDACTED-HOST (TBD, static)
```

Dumb switch configuration on the TP-Link:
1. Connect your laptop to TP-Link LAN port (not WAN).
2. Open TP-Link admin (192.168.0.1 or 192.168.0.1 default).
3. DHCP server: disabled.
4. Do not configure the WAN port at all — leave it unplugged.
5. Connect the cable from the Vodafone extender to any LAN port.

Servers now sit on the 192.168.0.x subnet (Vodafone DHCP range). Assign static IPs
either via DHCP reservation in the Vodafone router or by setting them in
/etc/netplan/ on each node.

The BezReklam router (office devices, 192.168.2.x) stays separate as before.

### Setting static IPs on nodes (netplan example for REDACTED-HOST)

```yaml
# /etc/netplan/00-installer-config.yaml
network:
  version: 2
  ethernets:
    eth0:
      dhcp4: false
      addresses: [10.0.0.107/24]
      routes:
        - to: default
          via: 192.168.0.1
      nameservers:
        addresses: [10.0.0.107]   # REDACTED-HOST itself runs AdGuard
```

```bash
sudo netplan apply
```

---

## 4. Cloudflare Tunnel — Replacing Port Forwarding

Port forwarding is the wrong appREDACTED-HOST for public websites. Cloudflare Tunnel gives you:
- Zero open inbound ports on your router.
- Free SSL/TLS termination.
- DDoS protection at Cloudflare edge.
- Works behind CGNAT (which Vodafone Ireland likely uses).

### Install and configure on REDACTED-HOST

```bash
# Install cloudflared
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg \
  | sudo tee /usr/share/keyrings/cloudflare-main.gpg > /dev/null
echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] \
  https://pkg.cloudflare.com/cloudflared focal main' \
  | sudo tee /etc/apt/sources.list.d/cloudflared.list
sudo apt update && sudo apt install cloudflared

# Authenticate (opens browser — do this from a machine with a browser, then
# copy credentials to REDACTED-HOST or run directly if desktop is available)
cloudflared tunnel login

# Create the tunnel
cloudflared tunnel create homelab
# Note the TUNNEL_UUID it prints

# Create config
sudo mkdir -p /etc/cloudflared
sudo tee /etc/cloudflared/config.yml <<'EOF'
tunnel: TUNNEL_UUID_HERE
credentials-file: /root/.cloudflared/TUNNEL_UUID_HERE.json

ingress:
  - hostname: husariabeats.com
    service: http://localhost:8080
  - hostname: ticker-tap.com
    service: http://localhost:8081
  - service: http_status:404
EOF

# Add DNS CNAME records in Cloudflare dashboard:
# husariabeats.com CNAME TUNNEL_UUID.cfargotunnel.com
# ticker-tap.com   CNAME TUNNEL_UUID.cfargotunnel.com
# Or use the CLI:
cloudflared tunnel route dns homelab husariabeats.com
cloudflared tunnel route dns homelab ticker-tap.com

# Install as systemd service
sudo cloudflared service install
sudo systemctl enable --now cloudflared
```

Caddy on REDACTED-HOST now listens on localhost only (no 0.0.0.0:443), and cloudflared
proxies inbound traffic to it. Your router firewall needs zero changes.

---

## 5. Tailscale — Remote SSH Access to All 4 Nodes

The original AI gave no remote access solution. You have 4 headless nodes.
Tailscale is the correct answer: zero-config mesh VPN, free for up to 100 devices,
no port forwarding, works behind CGNAT, SSH built in.

### Install on every node

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up --ssh --hostname=REDACTED-HOST   # change per node
```

The `--ssh` flag enables Tailscale SSH. After enrollment in the Tailscale admin console,
you SSH to any node from anywhere using:

```bash
ssh REDACTED-HOST    # resolves via Tailscale MagicDNS — no IP needed
ssh REDACTED-HOST
```

No keys to distribute, no jump hosts, no VPN config files.

### Subnet router (optional but useful)

Run this on REDACTED-HOST to expose the full 192.168.0.0/24 server subnet over Tailscale:

```bash
sudo tailscale up --ssh --hostname=REDACTED-HOST \
  --advertise-routes=192.168.0.0/24
```

Approve the route in the Tailscale admin console. You can then reach any server room
device by LAN IP from your Windows laptop over Tailscale, even services without
Tailscale installed.

---

## 6. Monitoring — External and Internal Separated

The original AI suggested Uptime Kuma (local), which is what you already have —
and it failed during the power outage because it runs on the same hardware being monitored.
Internal and external monitoring serve different purposes and must both exist.

### External (survives your power outage)

Sign up for **UptimeRobot** free tier (50 monitors, 5-minute checks, email + Telegram alerts)
or **Freshping** (free, 1-minute checks, 50 monitors).

Monitors to create:
- HTTPS husariabeats.com — keyword check for a string on the page
- HTTPS ticker-tap.com — HTTP 200 check
- Optional: HTTPS check on any cloudflared-exposed internal dashboard

These run from external servers. If your power goes out, they alert you.
The Telegram alert is sent from UptimeRobot's infrastructure, not yours.

### Internal (Uptime Kuma — keep it, different purpose)

Uptime Kuma on REDACTED-HOST monitors internal services that are not internet-reachable:
- http://REDACTED-HOST:11434 — Ollama API health
- http://REDACTED-HOST:4222 — NATS
- http://REDACTED-HOST:9090 — Prometheus
- tcp://REDACTED-HOST:6379 — Redis (if running)
- http://REDACTED-HOST:3000 — AdGuard Home admin

Internal monitoring catches service-level failures that the external checker cannot see.
External monitoring catches "is the site up from the internet" failures.
Both are necessary.

### Telegram alert that survives power loss

Your current Telegram monitoring is local-only — you confirmed it failed during the outage.
The fix: configure Telegram notifications in UptimeRobot (Settings → Alert Contacts → Telegram).
UptimeRobot sends the Telegram message from their servers when your site goes down.
Your REDACTED-HOST does not need to be running for this to work.

---

## 7. AdGuard Home — DNS and Ad Blocking

### Install on REDACTED-HOST as Docker container

Add to REDACTED-HOST's docker-compose.yml:

```yaml
services:
  adguard:
    image: adguard/adguardhome:latest
    container_name: adguard
    restart: unless-stopped
    ports:
      - "53:53/tcp"
      - "53:53/udp"
      - "3000:3000/tcp"   # admin UI — internal only
    volumes:
      - ./adguard/work:/opt/adguardhome/work
      - ./adguard/conf:/opt/adguardhome/conf
```

After first start, open http://REDACTED-HOST:3000 and complete the setup wizard.

### Point your routers at AdGuard

On the BezReklam router admin panel:
- DHCP DNS server 1: 10.0.0.107 (REDACTED-HOST)
- DHCP DNS server 2: 1.1.1.1 (Cloudflare fallback)

On the Vodafone router (if you have admin access):
- Same change, or leave it — the servers set their own DNS via netplan.

### Add local DNS entries in AdGuard

Under Filters → Custom filtering rules (or DNS Rewrites):
```
REDACTED-HOST.home   10.0.0.107
REDACTED-HOST.home   10.0.0.112
REDACTED-HOST.home   10.0.0.103
REDACTED-HOST.home   TBD
```

Services can now reference each other by name (e.g., http://REDACTED-HOST.home:11434)
instead of hardcoded IPs.

---

## 8. HomeAI — Concrete Starting Point

The original AI gave vague phases without addressing what actually runs on your hardware.
Here is what works on an i5/16GB without a GPU.

### Viable models on REDACTED-HOST (no GPU, 16GB RAM)

| Model                    | Pull command                      | RAM usage | Speed (CPU) | Use for             |
|--------------------------|-----------------------------------|-----------|-------------|---------------------|
| llama3.2:3b              | `ollama pull llama3.2:3b`         | ~2.5 GB   | fast (~15 t/s) | Quick Q&A, routing |
| phi3:mini                | `ollama pull phi3:mini`           | ~2.3 GB   | fast         | Lightweight tasks   |
| mistral:7b-instruct-q4   | `ollama pull mistral:7b-instruct` | ~4.5 GB   | ~6-8 t/s     | Better reasoning    |
| qwen3:4b                 | `ollama pull qwen3:4b`            | ~3.0 GB   | ~10 t/s      | Polish + English    |

Do not attempt 13B models on this hardware. They will either OOM or produce a response
in 3-5 minutes, which is not usable. Start with mistral:7b-instruct-q4 or qwen3:4b.

> **Real system context:** The existing ai-agent-stack on REDACTED-HOST currently uses Ollama on the Windows laptop (10.0.0.105) with qwen3:8b and codestral:22b. Moving Ollama to REDACTED-HOST eliminates the laptop sleep dependency. The /wake-laptop WoL endpoint in the AI worker becomes unnecessary once Ollama runs on REDACTED-HOST.

### Why your current HomeAI stack is OOM

Your `HOMEAI_ARCHITECTURE.md` lists Bielik-11B-v2.3 Q4_K_M (~8 GB RAM) as the
primary Polish model, plus Qwen3:8B (~5 GB) as the reasoning model. Those two models
alone consume 13 GB, leaving 3 GB for the OS and all other services.
That is why it crashes. Pick one model to start. qwen3:4b handles Polish adequately
and leaves room to breathe.

### Ollama setup on REDACTED-HOST

```bash
curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl enable --now ollama

# Set Ollama to listen on LAN (not just localhost) so n8n on REDACTED-HOST can reach it
sudo mkdir -p /etc/systemd/system/ollama.service.d
sudo tee /etc/systemd/system/ollama.service.d/override.conf <<'EOF'
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
EOF
sudo systemctl daemon-reload && sudo systemctl restart ollama

ollama pull qwen3:4b
```

Verify from REDACTED-HOST:
```bash
curl http://10.0.0.112:11434/api/tags
```

### n8n to Ollama integration (the actual HomeAI pipeline)

In n8n on REDACTED-HOST, the simplest working HomeAI workflow:

1. Trigger node (Telegram Message, Webhook, or Manual)
2. HTTP Request node:
   - Method: POST
   - URL: http://REDACTED-HOST.home:11434/api/chat
   - Body (JSON):
     ```json
     {
       "model": "qwen3:4b",
       "messages": [
         {
           "role": "system",
           "content": "You are a home assistant. Answer concisely in the same language the user wrote in."
         },
         {
           "role": "user",
           "content": "={{ $json.message }}"
         }
       ],
       "stream": false
     }
     ```
3. Set node: extract `{{ $json.message.content }}` from the Ollama response
4. Telegram node (or response): send the extracted content back to the user

This is the functional baseline. The full pipeline in HOMEAI_ARCHITECTURE.md
(NLP pipeline, safety gate, LangGraph orchestrator) is correct architecturally but
represents weeks of build time. Get this 4-node workflow running first, then layer
complexity on top.

### HomeAI service on REDACTED-HOST (docker-compose.yml)

```yaml
services:
  ollama:
    image: ollama/ollama:latest
    container_name: ollama
    restart: unless-stopped
    ports:
      - "11434:11434"
    volumes:
      - ollama-models:/root/.ollama
    environment:
      - OLLAMA_HOST=0.0.0.0

  redis:
    image: redis:7-alpine
    container_name: redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data

  nats:
    image: nats:2.10-alpine
    container_name: nats
    restart: unless-stopped
    ports:
      - "4222:4222"
      - "8222:8222"

  chromadb:
    image: chromadb/chroma:latest
    container_name: chromadb
    restart: unless-stopped
    ports:
      - "8009:8000"
    volumes:
      - chroma-data:/chroma/chroma

  searxng:
    image: searxng/searxng:latest
    container_name: searxng
    restart: unless-stopped
    ports:
      - "8888:8080"
    volumes:
      - ./searxng:/etc/searxng

volumes:
  ollama-models:
  redis-data:
  chroma-data:
```

Note: no `version:` key. See Section 11.

---

## 9. Ansible — Managing 4 Headless Nodes

Four headless nodes managed purely by hand via SSH degrades quickly.
Configuration drift (one node gets an apt update, others don't; one has a different
Docker version) causes hard-to-debug failures.

Ansible fixes this. You do not need to learn all of Ansible — four playbooks cover
90% of the maintenance burden.

### Install on your Windows daily driver (via WSL or directly)

```bash
# In WSL or any Linux machine
pip install ansible

# Or on Ubuntu
sudo apt install ansible
```

### Inventory file

```ini
# ~/homelab/inventory.ini
[all]
REDACTED-HOST ansible_host=REDACTED-HOST  # resolves via Tailscale MagicDNS
REDACTED-HOST ansible_host=REDACTED-HOST
REDACTED-HOST ansible_host=REDACTED-HOST
REDACTED-HOST ansible_host=REDACTED-HOST

[servers]
REDACTED-HOST
REDACTED-HOST
REDACTED-HOST

[ai]
REDACTED-HOST

[aux]
REDACTED-HOST
```

### Playbook: common setup (run once on fresh installs)

```yaml
# ~/homelab/playbooks/common.yml
---
- name: Common setup for all nodes
  hosts: all
  become: true
  tasks:
    - name: Set HandleLidSwitch=ignore for laptops
      lineinfile:
        path: /etc/systemd/logind.conf
        regexp: '^#?HandleLidSwitch='
        line: 'HandleLidSwitch=ignore'
      notify: restart systemd-logind

    - name: Disable swap
      command: swapoff -a
      changed_when: false

    - name: Remove swap from fstab
      lineinfile:
        path: /etc/fstab
        regexp: '\sswap\s'
        state: absent

    - name: Install Docker
      shell: curl -fsSL https://get.docker.com | sh
      args:
        creates: /usr/bin/docker

    - name: Add ubuntu user to docker group
      user:
        name: ubuntu
        groups: docker
        append: true

    - name: Install Tailscale
      shell: curl -fsSL https://tailscale.com/install.sh | sh
      args:
        creates: /usr/bin/tailscale

  handlers:
    - name: restart systemd-logind
      systemd:
        name: systemd-logind
        state: restarted
```

### Playbook: rolling apt update across all nodes

```yaml
# ~/homelab/playbooks/update.yml
---
- name: Update all nodes
  hosts: all
  become: true
  serial: 1         # one node at a time to avoid taking everything down
  tasks:
    - name: apt update and upgrade
      apt:
        update_cache: true
        upgrade: dist
        autoremove: true

    - name: Pull latest Docker images
      shell: |
        cd /opt/homelab && docker compose pull && docker compose up -d
      ignore_errors: true
```

Run with:
```bash
ansible-playbook -i inventory.ini playbooks/common.yml
ansible-playbook -i inventory.ini playbooks/update.yml
```

---

## 10. Dead Battery Node (REDACTED-HOST) — What Actually Works

The original AI recommended setting `CriticalPowerAction=Ignore` in logind.conf
and suggested BIOS "Restore on AC Power Loss". The logind fix is correct.
The BIOS advice is unreliable — most consumer laptop BIOSes (Lenovo, HP, Asus, Acer)
do not have this setting. Here is the actual decision tree:

### Step 1: Check your BIOS

Boot into BIOS/UEFI. Look under:
- Power Management
- Advanced → ACPI Settings
- Boot → Power On After AC Power Loss

If you find "Power On After Power Failure" or "AC Recovery" and can set it to "Power On":
REDACTED-HOST will auto-start when power is restored. You are done.

### Step 2: If BIOS has no such setting, use Wake-on-LAN

```bash
# On REDACTED-HOST: enable WOL on the ethernet interface
sudo apt install ethtool
IFACE=$(ip -br l | awk '$2 == "UP" {print $1}' | head -1)
sudo ethtool -s $IFACE wol g

# Make it persistent across reboots
sudo tee /etc/systemd/system/wol.service <<'EOF'
[Unit]
Description=Enable Wake-on-LAN
After=network.target

[Service]
Type=oneshot
ExecStart=/sbin/ethtool -s eth0 wol g
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl enable --now wol.service

# Get the MAC address — you need this
ip link show $IFACE | awk '/ether/{print $2}'
```

From REDACTED-HOST (which is always on after power restore), to wake REDACTED-HOST:
```bash
sudo apt install wakeonlan
wakeonlan AA:BB:CC:DD:EE:FF   # replace with REDACTED-HOST MAC
```

You can automate this with an n8n workflow: on Telegram command "wake REDACTED-HOST",
n8n triggers a script on REDACTED-HOST via SSH that runs `wakeonlan`.

### Step 3: If WOL is also unavailable

Accept the constraint and run only stateless services on REDACTED-HOST:
- Services where losing the node loses no data and restarting is trivial.
- No databases, no monitoring agents, no DNS, no AI models.
- Candidates: SearXNG (no state), a test Ollama instance, a cron job that reads
  from other nodes.

After every power outage, you manually press REDACTED-HOST's power button once.
Budget this inconvenience accordingly — if it happens rarely (once a month),
it may not be worth the WOL complexity.

---

## 11. Backup Strategy

The original AI mentioned "backups" in node role descriptions but never specified
what to back up, with what tool, to where, or how often.

### Tool: restic to Backblaze B2

Restic is incremental, encrypted, deduplicating. Backblaze B2 has a free 10 GB tier
and costs $6/TB/month beyond that. A home lab with configs and exports rarely exceeds
10 GB.

```bash
# Install restic on REDACTED-HOST
sudo apt install restic

# Create B2 bucket in Backblaze console, then:
export B2_ACCOUNT_ID=your_account_id
export B2_ACCOUNT_KEY=your_application_key
export RESTIC_PASSWORD=a_strong_encryption_passphrase

# Initialize the repository
restic -r b2:your-bucket-name:homelab init

# Backup script — save to /opt/backup/backup.sh on REDACTED-HOST
cat > /opt/backup/backup.sh <<'SCRIPT'
#!/bin/bash
set -euo pipefail

export B2_ACCOUNT_ID=your_account_id
export B2_ACCOUNT_KEY=your_application_key
export RESTIC_PASSWORD=a_strong_encryption_passphrase
REPO="b2:your-bucket-name:homelab"

# Docker volumes (databases, configs)
restic -r $REPO backup /var/lib/docker/volumes

# n8n workflow exports
docker exec n8n n8n export:workflow --all --output=/backups/n8n/workflows.json
restic -r $REPO backup /backups/n8n

# AdGuard config
restic -r $REPO backup /opt/homelab/adguard/conf

# Prune: keep last 7 daily, 4 weekly, 6 monthly
restic -r $REPO forget --keep-daily 7 --keep-weekly 4 --keep-monthly 6 --prune
SCRIPT
chmod +x /opt/backup/backup.sh

# Schedule daily at 3am
(crontab -l 2>/dev/null; echo "0 3 * * * /opt/backup/backup.sh >> /var/log/restic.log 2>&1") | crontab -
```

### What to back up

| What | Where | Priority |
|------|-------|----------|
| Docker named volumes | /var/lib/docker/volumes | High — databases, model configs |
| n8n workflow exports | via `n8n export:workflow` | High — automation logic |
| AdGuard config | /opt/homelab/adguard/conf | Medium — easy to rebuild but tedious |
| Tailscale auth keys | Tailscale admin console | Low — re-auth takes 2 minutes |
| Ansible playbooks | Git repository | High — commit these to a private repo |

### n8n workflows to Git

n8n workflow JSON should be version-controlled separately from the binary backup:

```bash
# On REDACTED-HOST, run nightly
docker exec n8n n8n export:workflow --all --output=/opt/homelab/n8n-exports/
cd /opt/homelab
git add n8n-exports/
git commit -m "n8n workflow export $(date +%Y-%m-%d)" || true
git push origin main
```

This gives you a change history for your automation logic, separate from the
data-level backup.

---

## 12. Docker Compose — Remove the Deprecated version Key

The original AI snippet used `version: '3'`. Modern Docker Compose (v2.x+, which ships
with Docker Engine 23+) ignores this key but emits a warning. It is dead syntax from
the Compose V1 era.

Remove it from every docker-compose.yml:

```yaml
# WRONG — produces deprecation warning
version: '3'
services:
  ...

# CORRECT — no version key
services:
  ...
```

If you see the warning `the attribute version is obsolete`, that is what it means.

---

## 13. Bootstrap Order — What to Set Up First

Do not try to bring everything up at once. This sequence minimizes wasted effort:

1. **Static IPs on all nodes** — netplan, then confirm with `ping REDACTED-HOST.home` etc.
2. **Tailscale on all nodes** — `tailscale up --ssh`. SSH from Windows laptop to confirm.
3. **REDACTED-HOST: Docker + AdGuard** — `docker compose up -d adguard`. Point router DNS at 10.0.0.107.
4. **REDACTED-HOST: Cloudflare Tunnel** — already running (REDACTED-HOST-n8n) for n8n and dashboard. husariabeats.com and ticker-tap.com are served via nginx + Cloudflare DNS proxy (full strict SSL). Extend tunnel config only if adding new internal services that need zero-port exposure.
5. **REDACTED-HOST: n8n** — migrate n8n from old PC if not already done.
6. **External monitoring** — UptimeRobot checks on both sites. Telegram alert confirmed from a mobile with WiFi off.
7. **REDACTED-HOST: Ollama + qwen3:4b** — `ollama pull qwen3:4b`, confirm `curl http://REDACTED-HOST:11434/api/tags` from REDACTED-HOST.
8. **REDACTED-HOST: n8n Ollama workflow** — single HTTP Request node hitting REDACTED-HOST. Confirm end-to-end.
9. **REDACTED-HOST: full HomeAI stack** — Redis, ChromaDB, NATS, SearXNG via docker-compose.
10. **REDACTED-HOST: Prometheus + Grafana** — scrape all other nodes.
11. **Ansible playbooks** — codify everything already done. Run on REDACTED-HOST fresh install.
12. **Restic backup** — configure and run manually once to confirm before scheduling.

---

## 14. Summary of Changes from Original AI Advice

| Issue | Original Advice | Correct AppREDACTED-HOST |
|-------|----------------|------------------|
| Public website access | Port forwarding | Cloudflare Tunnel — zero open ports |
| Remote SSH to headless nodes | Not mentioned | Tailscale with --ssh flag |
| Monitoring | Uptime Kuma (local only) | UptimeRobot external + Uptime Kuma internal |
| Node roles | Shifted 3 times across conversation | Stable assignments defined above |
| DNS placement | AdGuard on AI node (i5/16GB) | AdGuard on REDACTED-HOST (wall power, most reliable) |
| AI node | Mixed with DNS/monitoring | REDACTED-HOST dedicated to inference only |
| HomeAI models | Bielik-11B + Qwen3:8B simultaneously | Start with qwen3:4b or mistral:7b-q4 only |
| n8n to AI integration | Not shown | HTTP Request node to Ollama /api/chat shown above |
| Cluster management | Manual SSH to each node | Ansible inventory + 4 playbooks |
| Backup | Mentioned, never specified | restic to B2, n8n exports to git |
| Dead battery node | BIOS restore (often unavailable) | Decision tree: BIOS check → WOL → stateless only |
| Docker Compose syntax | `version: '3'` key present | No version key — modern Compose spec |
| Network: server room | Oscillated switch/AP mode | Dumb switch: LAN-to-LAN, DHCP off, no WAN used |
