# Case 4 — Quorum boundary: majority failure  `[core]`

**Why:** HA tolerates *some* failures, not all. "Withstand any node failure" is true for **exactly
one** node in a 3-node cluster. ZK/etcd are quorum systems — find the cliff. This quantifies real
fault tolerance instead of re-confirming the happy path.

**Prediction:** 1 node down = survivable (reads continue). Losing a **second** node destroys the
3-member coordination majority → cluster degrades/halts regardless of the fact that data has 3
copies. Auto-recovers when quorum is restored.

## Steps
```bash
# T1 (laptop) — keep the read probe running the whole time
python3 harness/probe.py --url "http://<M1_IP>:9000/query/finGraph/kHopTransfers?acc=acc0&k=3" \
  --interval 0.2 --out results/case4_probe.csv --token "$TG_TOKEN"

# Step 1: kill node A (m3). Confirm reads CONTINUE (this is the "survives 1" point).
gcloud compute instances stop tg-m3 --zone=us-central1-a

# Step 2: now kill node B (m2). Majority of the 3-member quorum is gone.
gcloud compute instances stop tg-m2 --zone=us-central1-a

# Observe cluster state from m1:
watch -n1 'gadmin status -v 2>&1 | tail -20'
```

## Measure
- Behaviour at **1 failure** (reads OK) vs **2 failures** (read-only? fully down? errors?).
- Exact symptom when quorum is lost (capture `gadmin status` output).
- Recovery time once you bring a node back to **restore majority**:
```bash
gcloud compute instances start tg-m2 --zone=us-central1-a   # quorum restored at 2/3
```
Time from quorum-restored → `gadmin status` healthy and probe green again.

## The report line this earns
> Even with a full data replica still present on the survivor, the ZK/etcd quorum tolerates only
> 1 loss — so **effective node-loss tolerance = 1, set by the coordination layer, not
> replication.** That's the quorum boundary.

**Pass:** you've located and explained the cliff, captured the 1-vs-2 behaviour difference, and
shown recovery on quorum restoration.
