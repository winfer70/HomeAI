# Network & Server Room Setup — 2026-05-20

## Problem Fixed: WR940N No Internet
- Cause: uplink cable from AX5400 was in WAN port (blue) instead of LAN port (yellow)
- Fix: moved cable to yellow LAN port

## Devices Configured

### WR940N (<LAN_IP>) — AP
- DHCP: disabled
- LAN IP: <LAN_IP>
- SSID: LabLAN (2.4GHz)
- Uplink: LAN port → AX5400

### TL-WPA7517 (<LAN_IP>) — Powerline AP
- LAN IP: <LAN_IP> (static)
- 2.4GHz SSID: Lab-IoT / password: <set-locally>
- 5GHz: enabled (kept for range)
- Use: IoT devices

## DHCP Reservations (AX5400 final state)

| Device | MAC | IP |
|--------|-----|----|
| node-a | XX:XX:XX:XX:XX:XX | <LAN_IP> |
| node-b | XX:XX:XX:XX:XX:XX | <LAN_IP> |
| node-c | XX:XX:XX:XX:XX:XX | <LAN_IP> |
| node-e | XX:XX:XX:XX:XX:XX | <LAN_IP> |
| node-d | XX:XX:XX:XX:XX:XX | <LAN_IP> |
| workstation | XX:XX:XX:XX:XX:XX | <LAN_IP> |

## IP Changes (old → new)

| Node | Old IP | New IP |
|------|--------|--------|
| node-b | <LAN_IP> | <LAN_IP> |
| node-e | <LAN_IP> | <LAN_IP> |
| node-d | <LAN_IP> | <LAN_IP> |
| node-a | <LAN_IP> | <LAN_IP> (unchanged) |
| node-c | <LAN_IP> | <LAN_IP> (unchanged) |

## Node Network Changes

### node-b
- WiFi disabled permanently via netplan (`/etc/netplan/00-installer-config.yaml`)
- Ethernet only: enp0s31f6 (XX:XX:XX:XX:XX:XX)
- Old WiFi MAC: XX:XX:XX:XX:XX:XX (reservation deleted)

### node-a
- Ethernet: enp1s0 (XX:XX:XX:XX:XX:XX) → <LAN_IP>
- WiFi: wlp2s0 (XX:XX:XX:XX:XX:XX) → still active at <LAN_IP> (disable later)
- Old duplicate reservation (.138) deleted from AX5400

## Pending

- [ ] Disable WiFi on node-a (wlp2s0)
- [ ] Update ai-agent-stack .env: OLLAMA_BASE_URL → http://<LAN_IP>:11434
- [ ] Monday: TL-SG108E switch arrives → connect node-c via ethernet → update reservation
- [ ] Monday: verify node-c ethernet MAC → add to AX5400 reservations
- [ ] Configure SG108E (VLAN for IoT isolation — optional, later)
- [ ] Uptime Kuma UI on node-d (<LAN_IP>:3001)

## Switch Purchase
- TL-SG108E (managed, 8-port Gigabit) — arriving Monday
- Cheaper than TL-SG108 (unmanaged) by 4zł + supports VLANs
