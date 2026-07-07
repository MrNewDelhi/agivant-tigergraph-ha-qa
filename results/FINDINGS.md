# Live test findings — TigerGraph 4.1.4 HA (3-node, RF=2) on GCP

Cluster: 3× e2-standard-4, us-central1-a. Topology (from `gssh`):
- **Data plane (GPE/GSE): m1, m2 only** — RF=2 → graph data replicated on 2 of 3 nodes.
- **m3: coordination/compute** — GSQL, RESTPP, NGINX, ZK, ETCD, KAFKA, but **no GPE/GSE data replica**.
- Control plane (GSQL, ZK, ETCD, RESTPP, NGINX): all 3 nodes.

Probe: internal high-rate (~7/s, sub-ms latency) on a survivor node hitting local RESTPP.
Baseline: 100% pass, p50≈18-19ms (internal), kHop k=3 over ~500k transfers.

---

## Case 1 — Single-node failure under read load

### 1a — kill -9 GPE on **m3** (non-data node), probe m1
- **100% availability (714/714)**, zero failed requests, p50=18ms. No blip.
- **Finding:** killing a node that holds no data replica is **transparent** to reads.

### 1b — full VM **power-off of m3** (true node failure), probe m1, heavy kHop
- **100% availability (1118/1118)** across ~65s with m3 fully powered off.
- **Finding:** confirms 1a under a real node-down (not just process crash). m3 not in data path.

### 1c — kill -9 GPE on **m2** (DATA replica holder), probe m1, heavy kHop  ← the core test
- **99.54% availability (1077/1082).**
- **5 isolated failures**, each exactly a **4.0s client timeout (code 000)**, ~1 per 4.25s across a
  **~18s adjustment window** (first fail = T0+0.92s, last = T0+17.94s), then fully clean.
- Every failure immediately followed by a success → **a retry-enabled client sees ZERO downtime.**
- **MTTR to stable (5 consec PASS): ~21s** from injection; matches TigerGraph's documented
  *"system typically adjusts within up to ~30s"* for query reroute on node failure.
- **Finding:** when a **data-replica** node dies, reads stay ~fully available; a small fraction of
  in-flight requests routed to the dead replica time out during a bounded (~18-21s) adjustment
  window, after which routing stabilizes to the surviving replica. Retry masks it entirely.

**Headline:** node-failure impact on reads depends on whether the node holds a data replica.
Non-data node = transparent; data-replica node = brief (~18-21s) reroute window with intermittent
timeouts, no sustained outage, retry-maskable. Matches the documented HA contract.

Evidence CSVs: results/case1a_gpe_kill.csv, case1b_m3_poweroff.csv, case1c_gpe_kill_m2.csv

---

## Case 2 — GSQL leader (control-plane) failover

Setup: GSQL runs on all 3 nodes (leader + 2 standbys). Identified leader from logs (`GsqlHAHandler`).
Probe: fresh `gsql` login + catalog `ls` every ~1.5s (a fresh login requires the GSQL leader for
session creation) on a follower node; killed the **leader's GSQL process** (node otherwise up).

**Finding — failover happened, but far slower than the documented ~8s heartbeat:**
- GSQL control-plane (logins / catalog / DDL) unavailable for **~58s** (first fail T0+0.4s).
- Logs confirm leadership moved (`switched to new leader: m1`), but the switch completed ~57s after
  the kill — coinciding with the old leader's GSQL restart.
- Documented default failover = HeartBeatInterval 2000ms × MaxMiss 4 ≈ **8s to *detect***. But full
  new-leader *readiness* (abort/clear sessions → download catalog) plus the controller's in-place
  GSQL restart attempt (GSQL cold-start ~30-50s) dominated recovery → ~58s observed.
- **Two-plane separation confirmed:** during the GSQL-leader outage, **data-plane reads/writes via
  RESTPP were unaffected** (RESTPP does not depend on the GSQL leader), and the GUI stayed up. Only
  the *control plane* (DDL, query install, new GSQL sessions) was impacted.

**Takeaway:** GSQL leader loss is a control-plane event — existing data serving continues, but
schema/DDL/new-session operations pause for the leader-recovery window (~1 min here, dominated by
GSQL restart/promotion, not the 8s heartbeat). Raising HeartBeatMaxMiss would only *delay* detection;
the dominant cost is new-leader readiness. Evidence: results/case2_gsql_leader.csv + GSQL logs.

---

## Case 3 — Control-plane operations while degraded (m3 down)  [highest signal]

Powered off m3 (true node-down), then attempted ops from m1. **A verify step overturned the
first read — the lesson of the case.**

| Operation | CLI appeared to | ACTUAL verified state | Verdict |
|---|---|---|---|
| Interpreted query | ok | returns result | **works** ✓ (positive control) |
| Existing installed query (REST) | ok | returns account data | **works** ✓ |
| CREATE QUERY (catalog metadata) | ok | added to catalog | works (metadata only) |
| **INSTALL QUERY** | printed endpoint (looked ok) | query stuck **`pendingInstall`**, endpoint = *"not found"* | **BLOCKED** ✓ |
| **Schema change** | — | *"Other operation is running, lock the catalog, timeout 600s"* | **BLOCKED** ✓ |

**Why the verify mattered:** `INSTALL QUERY` printed a success-looking endpoint hint, but querying
it returned *"Endpoint is not found"* and `ls` showed state `pendingInstall`. The install cannot
deploy the compiled query to the down node, so it never completes — matching the documented
degraded-mode restriction. Trusting the CLI output alone would have produced a **wrong** finding.

**Recovery timing:** restarted m3 → cluster healed in **~32s** → retried `INSTALL QUERY`, which then
**completed (54s)** and the endpoint went live (`{"hi":"hi"}`). So the blocked control-plane op
un-blocks as soon as the cluster returns to full membership.

**Finding:** HA is *partial by design* — during a node outage the **data plane keeps serving**
(reads, interpreted & existing queries) while **catalog-mutating control-plane ops (INSTALL QUERY,
schema change) are blocked** until full membership is restored. This is correct product behaviour,
not a bug. Evidence: results/case3_control_plane.txt.

---

## Case 4 — Quorum boundary (the "quorum cliff")  [headline]

Read probe on m1 while sequentially killing nodes via fast mesh power-off.

| Phase | Cluster | ZK/etcd quorum | Reads | Writes |
|---|---|---|---|---|
| A | 3 nodes healthy | 3/3 | **100%** | OK |
| B | m2 down (1 lost) | **2/3 OK** | serving (brief blip) | OK |
| C | m2+m3 down (2 lost) | **1/3 LOST** | **unreliable — flap ~50%, →full fail** | **fail outright** |

**CORRECTION (measured carefully 2026-07-06):** an earlier pass reported phase C as a clean "0%".
A fine-grained 1s-probe re-measurement showed that was a **too-short-window artefact** — reads with
quorum lost actually **flap ~50/50** (PASS/FAIL alternating) for minutes before fully failing, not
an instant clean halt. **Writes**, however, **fail deterministically** (need consensus) — that's the
clean signal. Corrected everywhere. The conclusion holds and is stronger: the cluster is unusable.

**The boundary:** in phase C, **m1 still holds a full data replica** (GPE_1#1 = complete copy at
RF=2), yet the cluster is **effectively unusable** — writes rejected, reads unreliable. The data is
present; the cluster won't function because the coordination quorum has lost majority. So in this 3-node RF2
cluster:

> **Effective node-loss tolerance = 1, set by the coordination-quorum layer — NOT by data
> replication.** Even with a full data replica still present on the survivor, the *cluster* does not
> survive losing 2 of 3 quorum members. This is the single most important HA boundary to understand.

(Phase B degraded to ~50% because the kill was a full-VM power-off of a *data + ZK* node at once —
more disruptive than the clean GPE-process kill in Case 1c (99.5%). The point of Case 4 is the
A→B→C trend, and especially the cluster becoming **unusable at C despite the data being present**.)

**Recovery:** restarted both nodes → `gadmin start all` → reads back after **~49s** (plus ~40s VM
boot beforehand). Note: manual start was required because full VM power-off leaves TG services
stopped on GCP reboot; a systemd-enabled auto-start would reduce operator involvement.
Evidence: results/case4_quorum.csv.

**Bonus finding (self-healing coordination):** I separately tried killing *only* the ZooKeeper+etcd
**processes** (not the whole node). Reads did **not** halt — because (a) TigerGraph's controller
**auto-restarts** killed ZK/etcd within seconds, and (b) an already-warm GPE on m1 keeps serving
point-lookups from memory. The cliff therefore requires losing the **whole nodes** (confirmed twice
via full power-off: 3 nodes = reads 200, 2-of-3 down = reads 000). So the precise statement is:
*losing 2 of 3 **nodes** halts the cluster despite a surviving full data replica* — and the
coordination layer is resilient to transient single-process failures on its own.

---

## Case 5 — Write path + consistency across failure/recovery

Wrote 2000 distinct edges from a fresh source `wtest`; **killed data-replica m2 at write #1000**;
counted persisted edges; then recovered m2 and re-counted.

- Attempted 2000 → **1994 succeeded**, 6 failed during the failure transition.
- **Edges persisted while degraded = 1994 — exact match to successes.** No lost writes, **no
  duplicates**, and the 6 clean failures left **no partial edges**.
- After m2 rejoined (~18s) and caught up: count **still 1994** — no divergence.
- `gstatusgraph`: **m1 and m2 byte-identical** (70001 vertices / 601935 edges each); m3 = 0 (no
  data replica, reconfirming topology).

**Finding:** writes are **atomic and strongly consistent** across a mid-write node failure —
successful writes persist, failed writes leave no trace, no duplicates, and a rejoining replica
**catches up to an exact match** (no split-brain, no data loss). Availability ≠ correctness, and
here correctness held. Evidence: results/case5_writes.csv + gstatusgraph.

---

## Case 6 — Recovery / MTTR (measured across all cases)

Distinct recovery paths, each measured live:

| Recovery type | Trigger | Measured MTTR |
|---|---|---|
| Data-replica reroute (read) | GPE crash on data node (Case 1c) | **~18–21s** to stable (retry-maskable) |
| Non-data node loss (read) | m3 crash/poweroff (Case 1a/b) | **0s** — transparent |
| GSQL leader (control plane) | leader GSQL killed (Case 2) | **~58s** to new leader ready |
| Control-plane un-block | node restored (Case 3) | cluster heal **~32s**, then INSTALL completes **~54s** |
| Quorum restoration | 2 nodes back (Case 4) | reads back **~49s** after `gadmin start` (+~40s VM boot) |
| Data-replica rejoin + catch-up | m2 back (Case 5) | GPE replica online **~18s**, synced to exact match |

**Note on measurement:** MTTR defined as time from failure/restore action to *stable service*
(≥5 consecutive successful probes, or service `Online` + serving). Full VM power-off adds ~30–40s
boot; on GCP the TG services required a manual `gadmin start all` after reboot (no systemd
auto-start configured) — a real deployment would enable auto-start to shrink operator MTTR.

Evidence: results/case6_recovery_mttr.txt (traces each figure to its source case).-
