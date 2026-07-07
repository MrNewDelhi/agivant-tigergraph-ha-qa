#!/bin/bash
# Standalone high-rate probe, runs ON a node. Writes epoch,status,http_code,latency_ms for <dur> secs.
# Usage: node_probe.sh <label> <duration_s> <query_path>
LABEL="$1"; DUR="${2:-120}"; Q="${3:-/query/finGraph/getAccount?acc=acc0}"
mkdir -p ~/results
CSV=~/results/${LABEL}.csv
URL="http://127.0.0.1:9000${Q}"
echo "epoch,status,http_code,latency_ms" > "$CSV"
END=$(( $(date +%s) + DUR ))
while [ "$(date +%s)" -lt "$END" ]; do
  t0=$(date +%s.%3N)
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 4 "$URL" 2>/dev/null)
  t1=$(date +%s.%3N)
  lat=$(awk -v a="$t0" -v b="$t1" 'BEGIN{printf "%d",(b-a)*1000}')
  st="FAIL"; [ "$code" = "200" ] && st="PASS"
  echo "$t0,$st,$code,$lat" >> "$CSV"
  sleep 0.1
done
echo "PROBE_DONE $CSV rows=$(wc -l < "$CSV")"
