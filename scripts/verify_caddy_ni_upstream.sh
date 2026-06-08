#!/usr/bin/env bash
# Verify FastAPI is reachable from Docker Caddy (host.docker.internal).
# Run on the homelab host where News Intelligence API + ai-lab-caddy run.
set -euo pipefail

echo "== TCP listeners on :8000 (Docker Caddy needs non-loopback bind or firewall allow) =="
ss -tlnp | grep ':8000' || echo "(nothing listening on 8000)"

echo "== Health via host loopback (127.0.0.1:8000) =="
code="$(curl -sS -o /dev/null -w '%{http_code}' --connect-timeout 5 http://127.0.0.1:8000/api/system_monitoring/health || echo fail)"
echo "HTTP $code"

echo "== Same via host LAN IP (pick first non-loopback IPv4) — optional =="
ip -4 addr show scope global | awk '/inet /{print $2}' | cut -d/ -f1 | head -1 | while read -r HIP; do
  [[ -z "${HIP:-}" ]] && continue
  code2="$(curl -sS -o /dev/null -w '%{http_code}' --connect-timeout 5 "http://${HIP}:8000/api/system_monitoring/health" || echo fail)"
  echo "HTTP $code2 (via $HIP:8000)"
done

NET_SUBNET=""
NET_BRIDGE=""
if docker network inspect ai-lab-net &>/dev/null; then
  NET_SUBNET="$(docker network inspect ai-lab-net -f '{{range .IPAM.Config}}{{.Subnet}} {{end}}' 2>/dev/null | awk '{print $1}')"
  NET_BRIDGE="$(docker network inspect ai-lab-net -f '{{ index .Options "com.docker.network.bridge.name" }}' 2>/dev/null)"
fi
echo "== Compose network ai-lab-net (Caddy uses this — traffic is NOT necessarily on docker0) =="
echo "    subnet: ${NET_SUBNET:-unknown}"
echo "    linux bridge name (if set): ${NET_BRIDGE:-unknown}"

echo "== From ai-lab-caddy container → host.docker.internal:8000 =="
if docker exec ai-lab-caddy true 2>/dev/null; then
  if docker exec ai-lab-caddy wget -qO- --timeout=8 http://host.docker.internal:8000/api/system_monitoring/health 2>/dev/null | head -c 400; then
    echo
    echo "(wget succeeded — upstream OK from container)"
  else
    echo "wget FAILED — bind is OK if loopback/LAN curls above are 200; this is almost always UFW INPUT from the compose bridge subnet."
    echo "Fix (narrow — preferred if subnet is known):"
    if [[ -n "${NET_SUBNET}" ]]; then
      echo "    sudo ufw allow from ${NET_SUBNET} to any port 8000 proto tcp comment 'NI API from Docker ai-lab-net'"
    fi
    echo "Fix (broader — typical Docker internal ranges 172.16–172.31):"
    echo "    sudo ufw allow from 172.16.0.0/12 to any port 8000 proto tcp comment 'NI API from Docker nets'"
    if [[ -n "${NET_BRIDGE}" ]]; then
      echo "Fix (interface — if UFW supports your bridge name):"
      echo "    sudo ufw allow in on ${NET_BRIDGE} to any port 8000 proto tcp"
    fi
    echo "Then: sudo ufw reload"
    echo "(docker0-only rules miss custom networks like ai-lab-net.)"
  fi
else
  echo "container ai-lab-caddy not found — skip"
fi
