# TigerGraph 4.1.x High-Availability — Failure & Recovery Test Report

> **Docs:** [Overview](../README.md) &middot; **HA Report** &middot; [Test-Case Matrix](TEST-CASES.md) &middot; [Evidence](TEST-EVIDENCE-REPORT.md) &middot; [Functional &amp; DB](FUNCTIONAL-AND-DATABASE-TESTS.md) &middot; [Decisions](DECISION.md) &middot; [Test Plan](TEST-PLAN.md) &middot; [pytest suite](../tests/README.md) &middot; [🌐 Report site](index.html)


**Author:** Anmol Soin · **Date:** 2026-07-04
**System under test:** TigerGraph Enterprise 4.1.4 (current 4.1-line LTS; see version note) — 3-node
HA cluster on Google Cloud.

---

## 1. Executive summary

I tested how a TigerGraph HA cluster behaves when nodes fail — **what stays up, what degrades by
design, and how fast it recovers** — with real measured downtime and MTTR.

**Test coverage** is **45 checks of three distinct kinds** (this report covers the HA cases; the
functional/database suites are in [FUNCTIONAL-AND-DATABASE-TESTS.md](FUNCTIONAL-AND-DATABASE-TESTS.md),
the full enumerated matrix in [TEST-CASES.md](TEST-CASES.md), and captured evidence in
[TEST-EVIDENCE-REPORT.md](TEST-EVIDENCE-REPORT.md)):
- **Automated pytest — 31/31**: functional CRUD/queries/aggregation/filtering (12), database
  correctness — precision, determinism, integrity (7), and messy/larger data — unicode, injection,
  dedup, 5k bulk (12).
- **Destructive / manual — 8/8**: consistency after a node failure+recovery (4), and backup & restore (4).
- **HA / resilience** (§4 below): 6 node-failure cases with measured MTTR.
A full **Recommendations** section (what worked / what needs improvement / actions) is in §5.

The results organise around a **two-plane model**, which is the mental model I'd want a reviewer to
take away:

| | **Data plane** (GPE/GSE/RESTPP) | **Control plane** (GSQL leader, ZK/etcd, GUI) |
|---|---|---|
| Architecture | leaderless, replicated (RF=2) | leader/follower + quorum |
| On a **1-node** loss | reads keep serving (brief reroute) | GSQL fails over to a standby; GUI stays up |
| Blocked while degraded | — | **INSTALL QUERY, schema change** (by design) |

**Findings at a glance:**

| # | Scenario | Client impact | MTTR | Verdict |
|---|---|---|---|---|
| 1a/b | Kill/power-off **non-data** node (m3) | **none** (100%) | 0s | HA holds — transparent |
| 1c | Kill **data-replica** node's GPE (m2) | 5 timeouts over ~18s (99.5%) | ~18–21s | HA holds — retry masks it |
| 2 | Kill **GSQL leader** process | control-plane pause; **reads unaffected** | ~58s | Holds, but slow (see finding) |
| 3 | INSTALL QUERY / schema change while degraded | **blocked** (by design) | un-blocks on heal (~32s) | Correct behaviour |
| 4 | **Quorum boundary** (2nd node down) | cluster unusable — writes rejected, reads unreliable, despite data present | ~40–60s on restore | The quorum boundary |
| 5 | Writes during a data-node failure | 6/2000 failed cleanly; **no loss/dupes** | replica re-synced ~18s | Consistent |

**The single most important finding — the "quorum boundary":** the data is replicated, but the
**coordination quorum (ZooKeeper/etcd) tolerates only 1 loss**. So effective node-loss tolerance =
**1 node**, set by the quorum layer, *not* by data replication. I demonstrated this directly: with
2 of 3 nodes down, the surviving node still held a **complete data replica**, yet the cluster was
**effectively unusable** — writes rejected outright, reads degraded to an unreliable ~50% flap
trending to full failure.

---

## 2. Environment & topology

- **TigerGraph Enterprise 4.1.4** (offline installer), 3-node HA, **replication factor 2**.
- **3× GCP `e2-standard-4`** (4 vCPU / 16 GB), Ubuntu 22.04, 50 GB SSD, single zone `us-central1-a`.
- Data: **20,000 Person, 50,000 Account, 50,000 OWNS, ~500,000 TRANSFER** edges (finGraph).
- Workloads: point-lookup (`getAccount`), 3-hop traversal (`kHopTransfers`), write (`addTransfer`).

**Actual service placement (from `gssh`) — this shaped every test:**

```
gpe.servers / gse.servers : m1, m2      ← graph DATA replicas on 2 of 3 nodes (RF=2)
m3                         : GSQL, RESTPP, NGINX, ZK, ETCD, KAFKA — but NO data replica
control plane (GSQL/ZK/etcd/RESTPP/NGINX): all 3 nodes
```

This placement is *itself* a finding: with RF=2 on 3 nodes, TigerGraph puts data on 2 nodes and
uses the 3rd purely for coordination/compute. **Which node you kill matters** — killing the
non-data node is far less impactful than killing a data-replica node.

**Version note:** the brief asked for 4.1.3; TigerGraph no longer distributes 4.1.3 (the download
page now offers **4.1.4** as the current 4.1 LTS), so I used 4.1.4 — same LTS line, deliberately
noted. The Community Edition was ruled out because it is **single-server only** ("Clustering: No")
and cannot host an HA cluster; the managed cloud (Savanna) was ruled out because it gives no
node-level control to inject failures. Only a self-managed Enterprise cluster can satisfy this
kind of node-failure testing.

---

## 3. Methodology

**Probe:** a high-rate loop (≈7/s, sub-ms internal latency) run **on a surviving node** against the
local RESTPP, logging `epoch, status, http_code, latency_ms`. Running the probe *inside* the cluster
avoided ~700 ms transcontinental latency from my laptop and gave clean sub-second MTTR resolution.
**Rule followed:** always probe through a node I was *not* killing.

**Failure injection:** process crash (`kill -9`), full node power-off (`poweroff` / `gcloud stop`),
applied to specific nodes chosen by their role (data vs coordination, leader vs follower).

**MTTR definition:** time from the failure/restore action to **stable service** — I used *5
consecutive successful probes* (or service `Online` and serving) as the recovery condition, so a
single lucky success doesn't count as "recovered."

**Timing terms** (kept distinct in findings): client-observed downtime · failover/reroute window ·
service MTTR · redundancy (catch-up) MTTR.

---

## 4. Findings per test case

### Case 1 — Single-node failure under read load
**Reasoning:** the core HA promise — a node dies, reads keep serving.
**Method & result:**
- **1a/1b (kill & power-off m3, the non-data node):** **100% availability** (714/714, then
  1118/1118 across a full 65 s power-off). Killing a node that holds no data replica is transparent.
- **1c (kill GPE on m2, a data-replica node), heavy 3-hop query:** **99.54%** (1077/1082). The
  failures were **5 isolated 4-second timeouts** across an **~18-second window** — each an in-flight
  request routed to the dead replica — after which routing stabilised. Every failure was immediately
  followed by a success, so **a retry-enabled client sees zero downtime**.
- **MTTR to stable ≈ 18–21 s**, matching TigerGraph's documented *"system typically adjusts within
  up to ~30 s"*, and empirically demonstrating *why the docs recommend client retry*.

**Finding:** node-failure impact on reads depends on whether the node holds a data replica — non-data
node = transparent; data-replica node = a brief, bounded reroute window with intermittent timeouts,
no sustained outage, fully retry-maskable.

### Case 2 — GSQL leader (control-plane) failover
**Reasoning:** GSQL is a leader/follower subsystem — a different failure path from the leaderless
data plane.
**Method & result:** identified the leader from `GsqlHAHandler` logs, killed its GSQL process.
Control-plane operations (fresh logins / catalog / DDL) were unavailable for **~58 s** before a
standby was ready (logs confirm `switched to new leader`). This is **much longer than the documented
~8 s heartbeat**: the 8 s only *detects* the loss; full new-leader *readiness* (clear sessions →
download catalog) plus the controller's in-place GSQL restart (cold-start ~30–50 s) dominated.
**Crucially, the data plane was unaffected** — RESTPP reads/writes and the GUI kept working
throughout; only DDL/new-session operations paused.

**Finding:** GSQL-leader loss is a *control-plane-only* event. Existing data serving continues; the
outage is confined to schema/DDL/new-session work, and its duration is dominated by GSQL
restart/promotion, not the heartbeat interval. Raising `HeartBeatMaxMiss` would only delay detection,
not speed recovery.

### Case 3 — Control-plane operations while degraded  *(highest-signal)*
**Reasoning:** a mature HA report maps the deliberate restrictions, not just the happy path.
**Method & result:** with m3 down, from a survivor I attempted each operation. **A verify step
overturned the first read**, which is the lesson of the case:

| Operation | CLI appeared | Verified actual state | Verdict |
|---|---|---|---|
| Interpreted query | ok | returns result | works ✓ |
| Existing installed query (REST) | ok | returns data | works ✓ |
| **INSTALL QUERY** | printed an endpoint (looked ok) | stuck `pendingInstall`, endpoint *"not found"* | **blocked** ✓ |
| **Schema change** | — | catalog-lock timeout | **blocked** ✓ |

`INSTALL QUERY` *looked* successful in the CLI but the query never became callable — trusting the
CLI output alone would have produced a wrong finding. After restoring m3 (cluster healed **~32 s**),
the same install **completed (~54 s)** and the endpoint went live.

**Finding:** HA is *partial by design* — during a node outage the data plane keeps serving while
catalog-mutating control-plane ops are blocked until full membership returns. Correct behaviour, and
a reminder to **verify effects, not CLI exit messages**. *Evidence:* `results/case3_control_plane.txt`.

### Case 4 — Quorum boundary (the quorum cliff)  *(headline)*
**Reasoning:** "survives any node failure" is true for exactly *one* node in a 3-node cluster —
where's the cliff?
**Method & result:** probed reads **and** writes on m1 while killing nodes in sequence. A follow-up
fine-grained measurement (1 s probe over several minutes) was needed to characterise phase C
correctly — see the honesty note below.

| Phase | Cluster | Quorum | Reads | Writes |
|---|---|---|---|---|
| A | 3 nodes | 3/3 | **100%** | OK |
| B | m2 down | 2/3 OK | serving (brief data-reroute blip) | OK |
| C | m2+m3 down | **1/3 lost** | **unreliable — flap ~50%, trending to full failure** | **fail outright** |

In phase C, m1 still held a **complete data replica**, yet the cluster is **effectively down**:
**writes are rejected outright** (they need a quorum majority to commit) and **reads become
unreliable** — roughly half fail, alternating, and trend to full failure over a few minutes as the
lone node gives up trying to reach absent peers. Recovery: with both nodes restored, service
returned after `gadmin start all` (~40–60 s, plus ~40 s VM boot).

> **Honesty note (and a lesson in measurement).** My first pass reported phase C as a clean
> **"0% reads."** A finer-grained re-measurement showed that was an artefact of a **too-short
> sample window** landing on a failure streak: reads with quorum lost don't cleanly halt — they
> **flap ~50/50** for minutes before fully failing. The *conclusion* is unchanged and arguably
> stronger — losing 2 of 3 nodes renders the cluster unusable despite a full data replica — but the
> failure *mode* is degradation, not an instant stop. Writes, by contrast, fail deterministically,
> which is the cleaner signal of quorum loss. Reporting the flapping honestly (rather than the tidy
> "0%") is the correct QA call.

**Finding:** **effective node-loss tolerance = 1, set by the coordination-quorum layer, not
replication.** Even with a **full data replica still present** on the survivor, the *cluster*
becomes unusable on losing 2 of 3 **nodes** — writes rejected, reads unreliable — because the
coordination quorum has lost its majority.

*Precision note (a bonus finding):* killing only the ZooKeeper/etcd **processes** did **not** take
the cluster down — TigerGraph's controller auto-restarts them within seconds, and a warm GPE keeps
serving from memory. The effect requires losing the whole **nodes**. So the coordination layer is
resilient to transient single-process failures; the boundary is specifically about simultaneous
multi-*node* loss.

### Case 5 — Write path + consistency across failure/recovery
**Reasoning:** availability ≠ correctness.
**Method & result:** wrote 2000 distinct edges from a fresh source, killed data-replica m2 at write
#1000, counted persisted edges, then recovered m2 and re-counted. **1994 writes succeeded → exactly
1994 edges persisted** (no loss, no duplicates); the 6 failures left no partial edges. After m2
rejoined (~18 s) and caught up, the count was **still 1994**, and `gstatusgraph` showed **m1 and m2
byte-identical** (70,001 vertices / 601,935 edges each).

**Finding:** writes are **atomic and strongly consistent** across a mid-write node failure, and a
rejoining replica catches up to an exact match — no split-brain, no data loss.

### Case 6 — Recovery / MTTR (measured across all cases)

| Recovery type | Trigger | Measured MTTR |
|---|---|---|
| Non-data node loss (read) | m3 crash/power-off | **0 s** (transparent) |
| Data-replica reroute (read) | GPE crash on m2 | **~18–21 s** (retry-maskable) |
| GSQL leader (control plane) | leader GSQL killed | **~58 s** to new-leader ready |
| Control-plane un-block | node restored | heal **~32 s**, then INSTALL **~54 s** |
| Quorum restoration | 2 nodes back | reads back **~49 s** (+~40 s VM boot) |
| Data-replica rejoin + catch-up | m2 back | replica online **~18 s**, exact re-sync |

*Each figure traces to its source case + evidence file — see `results/case6_recovery_mttr.txt`.*

---

## 5. Recommendations — what worked, what needs improvement, what to do

### 5.1 What worked as expected (product strengths)
- **Data-plane HA holds.** Losing a data-replica node caused only a brief (~18–21 s) reroute window,
  fully retry-maskable; losing the non-data node was completely transparent. (Case 1)
- **Strong write consistency.** Synchronous all-replica writes meant no lost or duplicated writes
  across a mid-write node failure, and a rejoining replica re-synced to a **byte-identical** copy.
  (Case 5 + consistency-after-recovery test)
- **Correct functional & data behaviour.** 39/39 functional and database-correctness tests passed —
  CRUD, aggregation, filtering, precision, unicode/special-char handling, primary-key dedup, and
  clean error handling all behaved correctly. (see [FUNCTIONAL-AND-DATABASE-TESTS.md](FUNCTIONAL-AND-DATABASE-TESTS.md))
- **Degraded-mode restrictions are correct-by-design.** INSTALL QUERY / schema change block cleanly
  while a node is down rather than half-applying. (Case 3)
- **Backup & restore works** as a point-in-time revert. (backup/restore test)
- **Self-healing coordination.** Killed ZooKeeper/etcd processes were auto-restarted within seconds.

### 5.2 What needs improvement (weaknesses / risks observed)
- **GSQL leader failover is slow (~58 s).** Far longer than the ~8 s heartbeat implies, because
  new-leader readiness (session clear + catalog download) and an in-place GSQL restart dominate.
  During this window all schema/DDL/new-session work is unavailable. (Case 2)
- **The quorum cliff is a sharp, easily-misunderstood limit.** Two of three nodes down makes the
  cluster unusable **even though a full data replica remains** — writes rejected, reads unreliable.
  Effective tolerance is one node, set by the quorum, not replication. (Case 4)
- **No auto-start after reboot.** A power-cycled node did not rejoin until a manual `gadmin start
  all`, inflating operator-visible recovery MTTR.
- **Misleading CLI success.** `INSTALL QUERY` printed a success-looking endpoint while the query was
  actually stuck `pendingInstall` — an operator trusting the CLI would be misled. (Case 3)
- **Restore is disruptive.** It stops the data/query services and restarts them (~2.5 min here), so
  it is strictly a planned-maintenance operation.

### 5.3 Recommendations (actionable)
1. **Enable client-side retry** on the application — it masks the entire data-node reroute window.
2. **Size the quorum for your failure target.** A 3-node cluster tolerates exactly one node; use
   **≥5 nodes** to tolerate two simultaneous failures. Replication improves durability, not
   cluster-level node tolerance.
3. **Consider RF=3** (data on all nodes) if you want uniform, node-independent read-failover behaviour.
4. **Configure systemd auto-start** so a rebooted node rejoins without manual intervention.
5. **Monitor the deterministic quorum-loss signals** — write-error-rate and `gadmin status` /
   `/api/ping` responsiveness — rather than read success rate (which flaps and lags).
6. **Schedule DDL, query installs, and backups for healthy windows** — they are blocked/disruptive
   during any node outage.
7. **Tune the LB health check** to `/api/ping` on 14240 with a short interval so a dead RESTPP drains
   quickly.
8. **In tooling/automation, verify the observable effect, not the CLI exit message.**

## 6. What I'd test next with more time
- Sustained concurrent load during failover (throughput/latency degradation curves) — the biggest gap.
- RF=3 and a 5-node cluster (confirm 2-node tolerance); partitioned topology (2×2).
- Network partition (vs clean power-off); disk-full / OOM-induced failure.
- Node Replacement V2 end-to-end; cross-region DR failover (RPO/RTO).
- Larger dataset (10M–100M+ edges) to re-measure catch-up MTTR at scale.
- CI-ify the harness: parameterised, headless, assert MTTR against thresholds, fail on regression.

## 7. Appendix — evidence

**HA failure-recovery (this report):**
- `results/*.csv` — raw probe logs (baseline, case1a/b/c, case2, case4, case5).
- `results/case3_control_plane.txt`, `results/case6_recovery_mttr.txt` — Case 3 & 6 evidence.
- `results/*.png` — latency (case1c) + quorum-boundary (case4) charts.

**Functional & database testing:** see [FUNCTIONAL-AND-DATABASE-TESTS.md](FUNCTIONAL-AND-DATABASE-TESTS.md)
- `results/func_db_test_output.txt`, `results/messy_data_test_output.txt`,
  `results/consistency_after_recovery_output.txt`, `results/backup_restore_output.txt`.

**Real captured screenshots — see [TEST-EVIDENCE-REPORT.md](TEST-EVIDENCE-REPORT.md)** (each image
mapped to its test case + result). Files in `results/screenshots/real/`:
- `P01`/`P02` — Admin Portal (v4.1.4): all services Online, 3 nodes, RF=2.
- `S01`–`S03` — `gadmin status -v`, `gssh` topology (RF=2), `gstatusgraph` replica consistency.
- `S04`–`S06` — CRUD via REST; pytest functional+database **19/19**; messy/larger-data **12/12**.
- `S07`/`S07b` — consistency after a node failure+recovery; replicas identical.
- `S08`/`S08b` — `gadmin backup create/list`; restore reverts 999→111.
- `S09`–`S12` — GSQL leader-failover log; live `pendingInstall`; live read-failover; live quorum boundary + portal degraded.
- `graphstudio_schema.png` — GraphStudio schema.

**Real logs — `results/logs/`:**
- `terminal_session_node.log` — the full recorded node (Terminal A) session.
- `S04_crud.log`, `S05_functional_db.log`, `S06_messy_data.log`, `S07_consistency.log`,
  `S08_backup.log`, `S11_read_failover.log`, `S12_quorum.log` — full output per capture step.
- `gsql_leader_failover.log` — `GsqlHAHandler` leader-switch lines.
- `install_query_pendinginstall.log` — the `pendingInstall` state + "Endpoint is not found".
- `gadmin_transitions_case_recovery.log` — service going Down during a node failure.

**Reproducibility:** `harness/` — all test + probe scripts. `infra/` — provisioning & install runbook.
`data/` — schema, loader, queries.
