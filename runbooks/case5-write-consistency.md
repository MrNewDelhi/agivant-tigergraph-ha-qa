# Case 5 — Write path + consistency across failure/recovery  `[stretch, high value]`

**Why:** Availability ≠ correctness. Verify no lost/duplicated writes and no lasting divergence
when a node dies mid-write and later rejoins.

**Prediction:** writes are synchronously sent to all replicas and complete only after all ack; a
transaction in flight when a server dies may abort (fail cleanly). After convergence: no loss, no
dupes.

## Setup — a counting write load with known-answer verification
Use a driver that inserts TRANSFER edges with a unique, countable marker so you can audit exactly.

```bash
# T1 (laptop) — fire N writes, log which SUCCEEDED (HTTP 200) vs failed
python3 - <<'PY'
import requests, csv, time, os
M1=os.environ["M1_IP"]; TOK=os.environ.get("TG_TOKEN","")
H={"Authorization":f"Bearer {TOK}"} if TOK else {}
ok=0; sent=0
with open("results/case5_writes.csv","w",newline="") as f:
    w=csv.writer(f); w.writerow(["i","epoch","status","code"])
    for i in range(5000):
        url=f"http://{M1}:9000/query/finGraph/addTransfer?from_acc=acc0&to_acc=acc{i%50}&amt=1"
        t=time.time()
        try:
            r=requests.post(url,headers=H,timeout=5); code=r.status_code
            good = code==200 and not (r.json().get("error") in (True,"true"))
        except Exception as e:
            code=-1; good=False
        w.writerow([i,f"{t:.3f}","PASS" if good else "FAIL",code]); f.flush()
        sent+=1; ok+=good
        print(f"\rsent={sent} ok={ok}",end="")
        time.sleep(0.05)
print(f"\nSUCCEEDED writes = {ok}")
PY
```

## Inject
Midway through the write stream, hard-kill a node (or `iptables` partition it), then let it rejoin.
```bash
gcloud compute instances stop tg-m3 --zone=us-central1-a
# ...wait ~30s while writes continue...
gcloud compute instances start tg-m3 --zone=us-central1-a
```

## Verify (the whole point)
After the rejoined node has caught up:
```bash
# Count edges out of acc0 — should equal the number of PASS writes in case5_writes.csv
gsql -g finGraph "INTERPRET QUERY () FOR GRAPH finGraph {
  S = {Account.*}; R = SELECT s FROM S:s -(TRANSFER>)- :t WHERE s.id==\"acc0\" ACCUM @@c+=1; PRINT @@c; }"
# Cross-check replica consistency:
gstatusgraph          # vertex/edge totals; run before + after catch-up
```
Compare: successful-writes (from CSV) vs edges present. Watch for **stale reads** during catch-up
(query the rejoining node right after it comes back and see if counts lag).

**Pass:** #edges == #successful writes (no loss, no dupes) after convergence; you characterize the
catch-up window and any temporary read staleness.
