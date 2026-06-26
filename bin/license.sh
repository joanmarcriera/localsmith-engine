#!/usr/bin/env bash
# license.sh — Localsmith Pro license activation via Lemon Squeezy.
#
# Uses Lemon Squeezy's PUBLIC license API (https://docs.lemonsqueezy.com/api/license-api).
# No API key lives in the client — only the customer's license key. Pro features
# (e.g. the self-repair loop) check `license.sh validate` before running.
#
# Usage:
#   bin/license.sh activate <license-key>   # one-time, per machine
#   bin/license.sh validate                 # exit 0 = Pro active, 2 = free tier
#   bin/license.sh status                   # human-readable
#   bin/license.sh deactivate               # release this machine's seat
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LIC_FILE="${LOCALSMITH_LICENSE_FILE:-$ROOT/.license}"
API="https://api.lemonsqueezy.com/v1/licenses"

# parse a top-level/nested JSON field with stdlib python (no jq dependency)
_json() { python3 -c "import json,sys
d=json.load(sys.stdin)
p='$1'.split('.')
for k in p:
    d=d.get(k) if isinstance(d,dict) else None
    if d is None: break
print('' if d is None else d)" 2>/dev/null || true; }

cmd="${1:-status}"
case "$cmd" in
  activate)
    key="${2:?usage: bin/license.sh activate <license-key>}"
    inst="$(hostname 2>/dev/null || echo host)-$$"
    resp="$(curl -s -m 20 -X POST "$API/activate" -H 'Accept: application/json' \
      --data-urlencode "license_key=$key" --data-urlencode "instance_name=$inst")"
    if [ "$(printf '%s' "$resp" | _json activated)" = "True" ]; then
      iid="$(printf '%s' "$resp" | _json instance.id)"
      printf 'key=%s\ninstance_id=%s\n' "$key" "$iid" > "$LIC_FILE"; chmod 600 "$LIC_FILE"
      echo "✅ Localsmith Pro activated on this machine."
    else
      echo "❌ Activation failed: $(printf '%s' "$resp" | _json error)"; exit 1
    fi ;;
  validate|status)
    if [ ! -f "$LIC_FILE" ]; then
      [ "$cmd" = status ] && echo "Free tier (no license installed)."
      exit 2
    fi
    key="$(sed -n 's/^key=//p' "$LIC_FILE")"; iid="$(sed -n 's/^instance_id=//p' "$LIC_FILE")"
    resp="$(curl -s -m 15 -X POST "$API/validate" -H 'Accept: application/json' \
      --data-urlencode "license_key=$key" --data-urlencode "instance_id=$iid" 2>/dev/null || true)"
    if [ "$(printf '%s' "$resp" | _json valid)" = "True" ]; then
      [ "$cmd" = status ] && echo "✅ Localsmith Pro — license valid."
      exit 0
    elif [ -z "$resp" ]; then
      # offline grace: a previously-activated license stays usable while offline
      [ "$cmd" = status ] && echo "✅ Localsmith Pro — offline (using cached license)."
      exit 0
    else
      [ "$cmd" = status ] && echo "❌ License invalid/expired: $(printf '%s' "$resp" | _json error). Reverting to free tier."
      exit 2
    fi ;;
  deactivate)
    [ -f "$LIC_FILE" ] || { echo "No license to deactivate."; exit 0; }
    key="$(sed -n 's/^key=//p' "$LIC_FILE")"; iid="$(sed -n 's/^instance_id=//p' "$LIC_FILE")"
    curl -s -m 15 -X POST "$API/deactivate" -H 'Accept: application/json' \
      --data-urlencode "license_key=$key" --data-urlencode "instance_id=$iid" >/dev/null || true
    rm -f "$LIC_FILE"; echo "Seat released on this machine." ;;
  *) echo "usage: bin/license.sh {activate <key>|validate|status|deactivate}"; exit 2 ;;
esac
