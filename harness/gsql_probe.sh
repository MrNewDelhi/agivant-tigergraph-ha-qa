#!/bin/bash
# GSQL control-plane probe. Runs ON a follower node. Each iteration does a fresh gsql login +
# catalog op (needs the GSQL leader for session creation) → measures leader availability.
# Usage: gsql_probe.sh <label> <duration_s>
LABEL="$1"; DUR="${2:-90}"
export PATH=$PATH:/home/tigergraph/tigergraph/app/cmd
mkdir -p ~/results
CSV=~/results/${LABEL}.csv
echo "epoch,status,latency_ms,detail" > "$CSV"
END=$(( $(date +%s) + DUR ))
while [ "$(date +%s)" -lt "$END" ]; do
  t0=$(date +%s.%3N)
  out=$(timeout 8 gsql -g finGraph "ls" 2>&1)
  rc=$?
  t1=$(date +%s.%3N)
  lat=$(awk -v a="$t0" -v b="$t1" 'BEGIN{printf "%d",(b-a)*1000}')
  if [ $rc -eq 0 ] && echo "$out" | grep -q "Graph"; then st="PASS"; d="ok"
  else st="FAIL"; d=$(echo "$out" | tr '\n' ' ' | grep -oE '(refused|timeout|leader|Unavailable|Exception|error)[^ ]*' | head -1); fi
  echo "$t0,$st,$lat,${d:-fail}" >> "$CSV"
  sleep 0.3
done
echo "GSQL_PROBE_DONE $CSV rows=$(wc -l < "$CSV")"
