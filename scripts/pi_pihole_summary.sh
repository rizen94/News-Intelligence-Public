#!/usr/bin/env bash
# Pull Pi-hole adlists and blocking status from the Pi. Run from Pop OS (SSH to Pi).
# Usage: ./scripts/pi_pihole_summary.sh [user@host]
# Output can be redirected to a file for later review (improve Pi-hole efficiency).

set -e
TARGET="${1:-petes@192.168.93.104}"

echo "=============================================="
echo "Pi-hole summary — $(date -Iseconds)"
echo "Host: $TARGET"
echo "=============================================="
echo ""

ssh -o BatchMode=yes "$TARGET" bash -s << 'REMOTE'
GRAVITY="/etc/pihole/gravity.db"
FTL_DB="/etc/pihole/pihole-FTL.db"

echo "--- Pi-hole status ---"
sudo pihole status 2>/dev/null || echo "Pi-hole not running or pihole CLI failed"

echo ""
echo "--- Summary stats (Pi-hole API) ---"
# Try v6 first (GET /api/dns/blocking works without auth), then v5-style, then other v6 paths
api=""
for url in "http://127.0.0.1/api/dns/blocking" "http://127.0.0.1/admin/api.php?summary" "http://127.0.0.1/api/statistics" "http://127.0.0.1/api/stats/overview" "http://127.0.0.1/api/stats"; do
  resp=$(curl -s "$url" 2>/dev/null)
  [ -z "$resp" ] && continue
  [ "$resp" = '{"error"'* ] && continue
  api="$resp"
  break
done
if [ -n "$api" ]; then
  echo "$api" | python3 -c "
import sys, json
try:
  d = json.load(sys.stdin)
  if 'error' in d:
    print('  API error:', d['error'].get('message', d['error']))
    print('  (v6 docs on Pi: http://pi.hole/api/docs)')
  else:
    # v5 keys
    q = d.get('dns_queries_today') or d.get('queries_today') or d.get('queries')
    b = d.get('ads_blocked_today') or d.get('blocked_today') or d.get('blocked')
    pct = d.get('ads_percentage_today') or d.get('percentage_today') or d.get('percent')
    dom = d.get('domains_being_blocked') or d.get('domains_blocked') or d.get('domains')
    status = d.get('status') or d.get('blocking')
    print('  Queries today:    ', q if q is not None else '?')
    print('  Blocked today:    ', b if b is not None else '?')
    print('  Percent blocked:  ', str(pct) + '%' if pct is not None else '?')
    print('  Domains in list:  ', dom if dom is not None else '?')
    print('  Status:            ', status)
    if q is None and b is None and dom is None:
      print('  (API keys: ', ', '.join(k for k in d.keys() if not k.startswith('_')), ')')
except Exception as e:
  print('  Parse error:', e)
" 2>/dev/null || {
  echo "  Raw API response:"
  echo "$api" | head -c 500
  echo ""
}
else
  echo "  (No API response; v6 docs on Pi: http://pi.hole/api/docs)"
fi

echo ""
echo "--- Adlists (blocklists) ---"
# Try gravity.db via sudo (need sqlite3 on Pi: apt install sqlite3)
if command -v sqlite3 &>/dev/null; then
  adlist_out=$(sudo sqlite3 "$GRAVITY" "SELECT address, enabled FROM adlist ORDER BY enabled DESC, id;" 2>/dev/null)
else
  adlist_out=""
fi
if [ -n "$adlist_out" ]; then
  echo "$adlist_out" | while IFS='|' read -r addr enabled; do
    [ "$enabled" = "1" ] && en="ON " || en="OFF"
    printf "  [%s] %s\n" "$en" "$addr"
  done
  echo ""
  echo "Adlist counts:"
  sudo sqlite3 "$GRAVITY" "SELECT '  Enabled: ' || COUNT(*) FROM adlist WHERE enabled=1; SELECT '  Disabled: ' || COUNT(*) FROM adlist WHERE enabled=0;" 2>/dev/null
else
  echo "  From /etc/pihole/adlists.list:"
  sudo cat /etc/pihole/adlists.list 2>/dev/null | sed 's/^/    /' || echo "  (could not read adlists.list)"
  command -v sqlite3 &>/dev/null || echo "  (Install sqlite3 on Pi for gravity list: sudo apt install sqlite3)"
fi

echo ""
echo "--- Domains in gravity (blocklist size) ---"
if command -v sqlite3 &>/dev/null; then
  sudo sqlite3 "$GRAVITY" "SELECT '  Total domains: ' || COUNT(*) FROM gravity;" 2>/dev/null || echo "  (gravity.db not available)"
else
  echo "  (sqlite3 not installed on Pi; sudo apt install sqlite3)"
fi

echo ""
echo "--- Top blocked domains (last 24h, from FTL) ---"
if command -v sqlite3 &>/dev/null; then
  # Blocked statuses per Pi-hole docs: 1,4,5,6,7,8,9,10,11,15,16,18. Use read-only to avoid locking FTL.
  ftl_out=$(sudo sqlite3 "file:${FTL_DB}?mode=ro" "
    SELECT domain || '|' || count(*) FROM queries
    WHERE status IN (1,4,5,6,7,8,9,10,11,15,16,18)
    AND timestamp >= strftime('%s','now') - 86400
    GROUP BY domain ORDER BY count(*) DESC LIMIT 25;
  " 2>/dev/null)
  if [ -n "$ftl_out" ]; then
    echo "$ftl_out" | while IFS='|' read -r domain cnt; do
      [ -n "$domain" ] && printf "  %-45s %s\n" "$domain" "$cnt"
    done
  else
    # Check if DB is readable and queries view exists (v6 uses VIEW from query_storage + domain_by_id)
    if sudo sqlite3 "file:${FTL_DB}?mode=ro" "SELECT 1 FROM queries LIMIT 1;" 2>/dev/null | grep -q 1; then
      echo "  (No blocked domains in last 24h)"
    else
      echo "  (FTL db locked, missing, or schema differs; FTL may use query_storage in this version)"
    fi
  fi
else
  echo "  (sqlite3 not installed on Pi; sudo apt install sqlite3)"
fi

echo ""
echo "--- Blocking mode and settings (pihole.toml) ---"
sudo test -r /etc/pihole/pihole.toml && sudo grep -E "^(blocking|dns)" /etc/pihole/pihole.toml 2>/dev/null | sed 's/^/  /' || echo "  (pihole.toml not found or empty)"

echo ""
echo "--- Pi-hole version ---"
sudo pihole -v 2>&1 | head -5 || echo "  (pihole -v failed)"
REMOTE

echo ""
echo "--- End Pi-hole summary ---"
