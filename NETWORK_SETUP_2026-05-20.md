# Network & Server Room Setup — 2026-05-20

## Problem Fixed: WR940N No Internet
- Cause: uplink cable from AX5400 was in WAN port (blue) instead of LAN port (yellow)
- Fix: moved cable to yellow LAN port

## Devices Configured

### WR940N (192.168.0.2) — AP
- DHCP: disabled
- LAN IP: 192.168.0.2
- SSID: BezReklam (2.4GHz)
- Uplink: LAN port → AX5400

### TL-WPA7517 (192.168.0.3) — Powerline AP
- LAN IP: 192.168.0.3 (static)
- 2.4GHz SSID: BezReklam-IOT / password: REDACTED_PASSWORD
- 5GHz: enabled (kept for range)
- Use: IoT devices

## DHCP Reservations (AX5400 final state)

| Device | MAC | IP |
|--------|-----|----|
| REDACTED-HOST | XX:XX:XX:XX:XX:XX | 10.0.0.107 |
| REDACTED-HOST | XX:XX:XX:XX:XX:XX | 10.0.0.101 |
| REDACTED-HOST | XX:XX:XX:XX:XX:XX | 10.0.0.103 |
| REDACTED-HOST | XX:XX:XX:XX:XX:XX | 10.0.0.111 |
| REDACTED-HOST | XX:XX:XX:XX:XX:XX | 10.0.0.102 |
| KamiloPC | XX:XX:XX:XX:XX:XX | 10.0.0.105 |

## IP Changes (old → new)

| Node | Old IP | New IP |
|------|--------|--------|
| REDACTED-HOST | 10.0.0.112 | 10.0.0.101 |
| REDACTED-HOST | 10.0.0.109 | 10.0.0.111 |
| REDACTED-HOST | 10.0.0.108 | 10.0.0.102 |
| REDACTED-HOST | 10.0.0.107 | 10.0.0.107 (unchanged) |
| REDACTED-HOST | 10.0.0.103 | 10.0.0.103 (unchanged) |

## Node Network Changes

### REDACTED-HOST
- WiFi disabled permanently via netplan (`/etc/netplan/00-installer-config.yaml`)
- Ethernet only: enp0s31f6 (XX:XX:XX:XX:XX:XX)
- Old WiFi MAC: XX:XX:XX:XX:XX:XX (reservation deleted)

### REDACTED-HOST
- Ethernet: enp1s0 (XX:XX:XX:XX:XX:XX) → 10.0.0.107
- WiFi: wlp2s0 (XX:XX:XX:XX:XX:XX) → still active at 10.0.0.106 (disable later)
- Old duplicate reservation (.138) deleted from AX5400

## Pending

- [ ] Disable WiFi on REDACTED-HOST (wlp2s0)
- [ ] Update ai-agent-stack .env: OLLAMA_BASE_URL → http://10.0.0.101:11434
- [ ] Monday: TL-SG108E switch arrives → connect REDACTED-HOST via ethernet → update reservation
- [ ] Monday: verify REDACTED-HOST ethernet MAC → add to AX5400 reservations
- [ ] Configure SG108E (VLAN for IoT isolation — optional, later)
- [ ] Uptime Kuma UI on REDACTED-HOST (10.0.0.102:3001)

## Switch Purchase
- TL-SG108E (managed, 8-port Gigabit) — arriving Monday
- Cheaper than TL-SG108 (unmanaged) by 4zł + supports VLANs
