#!/bin/bash
# Runs ON m1. Quorum-cliff test: probe reads on m1 while killing m2 (1 down) then m3 (2 down).
# Fast node death via SSH-mesh `sudo poweroff`. Recovery is done from the laptop (gcloud start).
export PATH=$PATH:/home/tigergraph/tigergraph/app/cmd
mkdir -p ~/results
CSV=~/results/case4_quorum.csv
URL="http://127.0.0.1:9000/query/finGraph/getAccount?acc=acc0"
echo "epoch,status,http_code,latency_ms" > "$CSV"
probe() {
  while :; do
    t0=$(date +%s.%3N)
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 4 "$URL" 2>/dev/null)
    t1=$(date +%s.%3N); lat=$(awk -v a="$t0" -v b="$t1" 'BEGIN{printf "%d",(b-a)*1000}')
    st="FAIL"; [ "$code" = "200" ] && st="PASS"
    echo "$t0,$st,$code,$lat" >> "$CSV"; sleep 0.1
  done
}
probe & PP=$!

echo "[$(date +%T)] baseline 15s (3 nodes up) ..."; sleep 15
T1=$(date +%s.%3N)
echo "[$(date +%T)] T1=$T1 KILL m2 (1 node down, quorum 2/3 should survive)"
timeout 8 ssh -o StrictHostKeyChecking=no 10.128.0.3 'sudo poweroff' 2>/dev/null || true
echo "[$(date +%T)] observe 25s (expect reads continue) ..."; sleep 25
T2=$(date +%s.%3N)
echo "[$(date +%T)] T2=$T2 KILL m3 (2 nodes down, quorum 1/3 LOST)"
timeout 8 ssh -o StrictHostKeyChecking=no 10.128.0.4 'sudo poweroff' 2>/dev/null || true
echo "[$(date +%T)] observe 35s (expect halt) ..."; sleep 35

echo "[$(date +%T)] cluster state with quorum lost (timeout-guarded):"
timeout 15 gadmin status 2>&1 | head -12 || echo "  gadmin status HUNG/failed (expected under quorum loss)"

kill $PP 2>/dev/null
echo "T1_KILL_m2=$T1"
echo "T2_KILL_m3=$T2"
echo "CSV rows=$(wc -l < "$CSV")"
