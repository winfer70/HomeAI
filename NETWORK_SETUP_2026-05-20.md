# Network & Server Room Setup — 2026-05-20

## Problem Fixed: WR940N No Internet
- Cause: uplink cable from AX5400 was in WAN port (blue) instead of LAN port (yellow)
- Fix: moved cable to yellow LAN port

## Devices Configured

### WR940N (192.168.10.2) — AP
- DHCP: disabled
- LAN IP: 192.168.10.2
- SSID: LabLAN (2.4GHz)
- Uplink: LAN port → AX5400

### TL-WPA7517 (192.168.10.3) — Powerline AP
- LAN IP: 192.168.10.3 (static)
- 2.4GHz SSID: Lab-IoT / password: <set-locally>
- 5GHz: enabled (kept for range)
- Use: IoT devices

## DHCP Reservations (AX5400 final state)

| Device | MAC | IP |
|--------|-----|----|
| node-a | XX:XX:XX:XX:XX:XX | 10.0.1.107 |
| node-b | XX:XX:XX:XX:XX:XX | 10.0.1.101 |
| node-c | XX:XX:XX:XX:XX:XX | 10.0.1.103 |
| node-e | XX:XX:XX:XX:XX:XX | 10.0.1.111 |
| node-d | XX:XX:XX:XX:XX:XX | 10.0.1.102 |
| workstation | XX:XX:XX:XX:XX:XX | 10.0.1.105 |

## IP Changes (old → new)

| Node | Old IP | New IP |
|------|--------|--------|
| node-b | 10.0.1.112 | 10.0.1.101 |
| node-e | 10.0.1.109 | 10.0.1.111 |
| node-d | 10.0.1.108 | 10.0.1.102 |
| node-a | 10.0.1.107 | 10.0.1.107 (unchanged) |
| node-c | 10.0.1.103 | 10.0.1.103 (unchanged) |

## Node Network Changes

### node-b
- WiFi disabled permanently via netplan (`/etc/netplan/00-installer-config.yaml`)
- Ethernet only: enp0s31f6 (XX:XX:XX:XX:XX:XX)
- Old WiFi MAC: XX:XX:XX:XX:XX:XX (reservation deleted)

### node-a
- Ethernet: enp1s0 (XX:XX:XX:XX:XX:XX) → 10.0.1.107
- WiFi: wlp2s0 (XX:XX:XX:XX:XX:XX) → still active at 10.0.1.106 (disable later)
- Old duplicate reservation (.138) deleted from AX5400

## Pending

- [ ] Disable WiFi on node-a (wlp2s0)
- [ ] Update ai-agent-stack .env: OLLAMA_BASE_URL → http://10.0.1.101:11434
- [ ] Monday: TL-SG108E switch arrives → connect node-c via ethernet → update reservation
- [ ] Monday: verify node-c ethernet MAC → add to AX5400 reservations
- [ ] Configure SG108E (VLAN for IoT isolation — optional, later)
- [ ] Uptime Kuma UI on node-d (10.0.1.102:3001)

## Switch Purchase
- TL-SG108E (managed, 8-port Gigabit) — arriving Monday
- Cheaper than TL-SG108 (unmanaged) by 4zł + supports VLANs
