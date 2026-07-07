#!/usr/bin/env bash
# Liveness probe (no auth) — run in parallel with probe.py. Hits /api/ping on 14240.
# Usage:  ./ping_probe.sh <NODE_IP> [interval_sec] > results/case1_ping.log
HOST="${1:?usage: ping_probe.sh <NODE_IP> [interval]}"
INT="${2:-0.2}"
echo "epoch,http_code"
while true; do
  ts=$(date +%s.%3N)
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "http://$HOST:14240/api/ping" || echo 000)
  echo "$ts,$code"
  sleep "$INT"
done
