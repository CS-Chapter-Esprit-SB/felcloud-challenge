#!/usr/bin/env bash
# Failover probe: request a URL every 0.2 s and report every state change.
#
#   scripts/probe.sh <seconds> <url> [extra curl args...]
#
# Examples:
#   scripts/probe.sh 60 https://197.5.133.85/ -k                         # HAProxy, from anywhere
#   scripts/probe.sh 60 https://pypi.org/simple/ -x http://10.0.2.100:3128  # Squid, from the client VM
#
# Output: one line per transition (timestamp, HTTP code or 000 on failure), then a
# summary with the number of failed requests and the longest outage.
# PROBE_TIMEOUT (seconds, default 1) bounds each request, i.e. the outage resolution.
set -u
duration=$1; url=$2; shift 2
end=$(( $(date +%s) + duration ))
ok=0 fail=0 last="" outage_start="" longest=0
while [ "$(date +%s)" -lt "$end" ]; do
  code=$(curl -s -o /dev/null -m "${PROBE_TIMEOUT:-1}" -w '%{http_code}' "$@" "$url")
  now=$(date +%s.%N)
  if [ "${code:0:1}" = 2 ] || [ "${code:0:1}" = 3 ]; then
    ok=$((ok + 1))
    if [ -n "$outage_start" ]; then
      d=$(awk -v a="$outage_start" -v b="$now" 'BEGIN{printf "%.1f", b-a}')
      awk -v d="$d" -v l="$longest" 'BEGIN{exit !(d>l)}' && longest=$d
      outage_start=""
    fi
  else
    fail=$((fail + 1))
    [ -z "$outage_start" ] && outage_start=$now
  fi
  [ "$code" != "$last" ] && echo "$(date +%T.%N | cut -c1-12)  HTTP $code" && last=$code
  sleep 0.2
done
if [ -n "$outage_start" ]; then  # still down when the probe ended
  d=$(awk -v a="$outage_start" -v b="$(date +%s.%N)" 'BEGIN{printf "%.1f", b-a}')
  awk -v d="$d" -v l="$longest" 'BEGIN{exit !(d>l)}' && longest=$d
fi
echo "summary: ok=$ok failed=$fail longest_outage=${longest}s"
