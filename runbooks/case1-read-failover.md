# Case 1 — Single data-node hard failure under read load  `[core]`

**Why:** The primary HA promise — a node dies, reads keep serving. If this doesn't hold, nothing
else matters.

**Prediction:** in-flight queries on the failed node may abort; system re-routes, "typically up
to 30 s"; a retry-enabled client sees ~no downtime.

## Setup
- Pick a node you will kill (a **non-leader** node, e.g. m3) and a node you will **probe through**
  (a survivor, e.g. m1). Get their IPs from `gcloud compute instances list`.
- 3 terminals:

```bash
# T1 (laptop) — read probe THROUGH m1, hitting the heavy k-hop query
python3 harness/probe.py \
  --url "http://<M1_IP>:9000/query/finGraph/kHopTransfers?acc=acc0&k=3" \
  --interval 0.2 --out results/case1_probe.csv --token "$TG_TOKEN"

# T2 (laptop) — liveness probe through m1
bash harness/ping_probe.sh <M1_IP> 0.2 > results/case1_ping.log

# T3 (ssh to m1, as tigergraph) — server-side witness
bash harness/status_watch.sh > results/case1_status.log
```

## Inject failure — run all three variants (contrast), ≥3× each
Let the probe run ~30 s of clean baseline first. Note wall-clock `T0` when you inject.

```bash
# (a) GRACEFUL baseline (drains) — ssh to m3:
gadmin stop gpe -y

# (b) HARD process kill — ssh to m3:
sudo kill -9 $(pgrep -f gpe)

# (c) FULL VM power-off — from laptop:
gcloud compute instances stop tg-m3 --zone=us-central1-a
```

## Measure
```bash
python3 harness/analyze.py results/case1_probe.csv --recover-n 10 --chart results/case1.png
```
Record: client-observed downtime, # failed probes, latency spike, whether it **self-heals with no
operator action**. Compare (a) vs (b) vs (c) — graceful should understate impact.

**Retry column:** re-run `analyze.py` mentally as "would a client with 3 retries have seen an
outage?" — if failed runs are shorter than the re-route window, a retrying client sees ~0.

## Recover
```bash
gcloud compute instances start tg-m3 --zone=us-central1-a   # or: gadmin start gpe -y
```
Time until `gadmin status -v` shows m3 services RUNNING again (feeds Case 6).

**Pass:** reads continue or resume within the re-route window; retry-enabled client ~no downtime;
no manual intervention needed to restore read service.
