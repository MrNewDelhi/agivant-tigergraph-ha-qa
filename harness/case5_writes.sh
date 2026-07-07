#!/bin/bash
# Runs ON m1. Write-consistency across a data-node failure.
# Writes N distinct edges from a fresh source 'wtest' to acc0..accN-1; kills m2 (data replica)
# mid-stream; logs per-write success; then counts persisted edges. Recovery/recount done from laptop.
export PATH=$PATH:/home/tigergraph/tigergraph/app/cmd
mkdir -p ~/results
CSV=~/results/case5_writes.csv
N=2000; KILL_AT=1000; AMT=55555
BASE="http://127.0.0.1:9000"
echo "i,epoch,http,error" > "$CSV"

echo "=== ensure source vertex 'wtest' exists + baseline out-edge count ==="
curl -s -X POST "$BASE/graph/finGraph" -d '{"vertices":{"Account":{"wtest":{"balance":{"value":0}}}}}' >/dev/null 2>&1
countq() {
  gsql -g finGraph 'INTERPRET QUERY () FOR GRAPH finGraph {
    SumAccum<INT> @@c; S = {Account.*};
    R = SELECT t FROM S:s -(TRANSFER>)- Account:t WHERE s.id=="wtest" ACCUM @@c+=1;
    PRINT @@c AS out_edges; }' 2>/dev/null | grep -oE '"out_edges": [0-9]+' | grep -oE '[0-9]+'
}
echo "baseline wtest out-edges: $(countq)"

echo "=== firing $N writes, killing m2 at write #$KILL_AT ==="
ok=0
for i in $(seq 0 $((N-1))); do
  if [ "$i" = "$KILL_AT" ]; then
    echo ">>> [$(date +%T)] KILL m2 (data replica) mid-write"
    timeout 8 ssh -o StrictHostKeyChecking=no 10.128.0.3 'sudo poweroff' 2>/dev/null || true
  fi
  t=$(date +%s.%3N)
  resp=$(curl -s --max-time 5 -X POST "$BASE/query/finGraph/addTransfer?from_acc=wtest&to_acc=acc${i}&amt=${AMT}" 2>/dev/null)
  http=$?
  err=$(echo "$resp" | grep -oE '"error":(true|false)' | head -1)
  echo "$i,$t,$http,$err" >> "$CSV"
  echo "$resp" | grep -q '"error":false' && ok=$((ok+1))
done
echo "SUCCESSFUL_WRITES=$ok  (of $N attempted)"
echo "EDGES_WHILE_DEGRADED=$(countq)"
echo "DONE"
