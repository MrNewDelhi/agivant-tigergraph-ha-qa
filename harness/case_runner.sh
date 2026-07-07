#!/bin/bash
# Self-contained failure-test runner. Runs ON m1 (a survivor). High-rate internal probe against
# the local RESTPP while a failure is injected on a target node, with precise epoch timestamps.
#
# Usage: case_runner.sh <label> <target_node_ip> <inject_cmd> <recover_cmd> \
#                       <baseline_s> <outage_s> <recover_s> <query_path>
# Writes: ~/results/<label>.csv  and prints T0 (inject) / T1 (recover) epoch markers.
set -u
LABEL="$1"; TARGET="$2"; INJECT="$3"; RECOVER="$4"
BASE="${5:-15}"; OUT="${6:-45}"; REC="${7:-25}"
Q="${8:-/query/finGraph/getAccount?acc=acc0}"
export PATH=$PATH:/home/tigergraph/tigergraph/app/cmd
mkdir -p ~/results
CSV=~/results/${LABEL}.csv
URL="http://127.0.0.1:9000${Q}"
echo "epoch,status,http_code,latency_ms" > "$CSV"

# background high-rate probe
probe() {
  while :; do
    t0=$(date +%s.%3N)
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 4 "$URL" 2>/dev/null)
    t1=$(date +%s.%3N)
    lat=$(awk -v a="$t0" -v b="$t1" 'BEGIN{printf "%d",(b-a)*1000}')
    st="FAIL"; [ "$code" = "200" ] && st="PASS"
    echo "$t0,$st,$code,$lat" >> "$CSV"
    sleep 0.1
  done
}
probe & PROBE_PID=$!

echo "[$(date +%T)] baseline ${BASE}s ..."; sleep "$BASE"
T0=$(date +%s.%3N)
echo "[$(date +%T)] INJECT (T0=$T0): $INJECT"
eval "$INJECT"
echo "[$(date +%T)] observing outage ${OUT}s ..."; sleep "$OUT"
T1=$(date +%s.%3N)
echo "[$(date +%T)] RECOVER (T1=$T1): $RECOVER"
eval "$RECOVER"
echo "[$(date +%T)] observing recovery ${REC}s ..."; sleep "$REC"

kill $PROBE_PID 2>/dev/null
echo "T0_INJECT=$T0"
echo "T1_RECOVER=$T1"
echo "CSV=$CSV rows=$(wc -l < "$CSV")"
