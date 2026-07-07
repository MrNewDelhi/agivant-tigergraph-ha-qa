# Case 6 — Node recovery, rejoin, and replacement (full MTTR)  `[stretch]`

**Why:** The brief asks directly "how soon does it recover, if at all?" Restarting a service and
replacing a dead node are **different** recovery paths with different MTTR.

## 6a. Service restart MTTR
```bash
# after a kill in Case 1, on the affected node:
t0=$(date +%s.%3N); gadmin start gpe -y
# poll until RUNNING:
while ! gadmin status -v gpe | grep -q RUNNING; do sleep 1; done
t1=$(date +%s.%3N); echo "MTTR-service = $(echo "$t1-$t0"|bc)s"
```
Also note time until it's **back in query rotation** (probe latency returns to baseline) — that can
lag "RUNNING".

## 6b. Redundancy MTTR (rejoin + catch-up)
After a VM power-off/start (Case 1c or 5), time from node boot → cluster back at full replica count
and the rejoined node caught up:
```bash
gcloud compute instances start tg-m3 --zone=us-central1-a
# watch until all services on m3 RUNNING and gstatusgraph consistent:
watch -n2 'gadmin status -v | grep -E "m3|Node3"; gstatusgraph'
```
This depends on write volume during the outage — note that dependency in the report.

## 6c. Replacement MTTR (unrecoverable node)
Simulate a node that won't come back, and run the remove/replace workflow.
```bash
# Remove a failed node from the cluster (documented as no-data-loss for a single node):
gadmin cluster remove m3:<M3_INTERNAL_IP>
# (Optional) Node Replacement V2 workflow to add a fresh node in its place.
```
Time the whole workflow **and** its planned-downtime window (cluster resize incurs a brief planned
downtime).

## Report output — three distinct, quantified numbers
| MTTR type | What it measures | Your number |
|---|---|---|
| MTTR-service | restart killed service → RUNNING + in rotation | ...s |
| MTTR-redundancy | node boot → rejoined + caught up | ...s / min |
| MTTR-replacement | remove/replace workflow + planned downtime | ...min |

**Pass:** three separate recovery numbers with the operator steps for each.
