#!/usr/bin/env bash

HOST="api.team5.cstam.felcloud.tn"
HAPROXY_IP="197.5.133.69"
HEALTH_ENDPOINT="/"

while true; do
    curl -sk -o /dev/null \
        --resolve "${HOST}:443:${HAPROXY_IP}" \
        --connect-timeout 3 \
        --max-time 5 \
        -w "$(date '+%F %T') | HTTP %{http_code} | %{time_total}s\n" \
        "https://${HOST}${HEALTH_ENDPOINT}" \
        || echo "$(date '+%F %T') | Request failed"

    sleep 1
done