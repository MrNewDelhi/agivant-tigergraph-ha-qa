# Environment & scope decisions (and why)

> **Docs:** [Overview](../README.md) &middot; [HA Report](REPORT.md) &middot; [Test-Case Matrix](TEST-CASES.md) &middot; [Evidence](TEST-EVIDENCE-REPORT.md) &middot; [Functional &amp; DB](FUNCTIONAL-AND-DATABASE-TESTS.md) &middot; **Decisions** &middot; [Test Plan](TEST-PLAN.md) &middot; [pytest suite](../tests/README.md) &middot; [🌐 Report site](index.html)


Putting this in the repo (and a condensed version in the report) shows *intention* rather than
omission — it's the "judgment" the brief explicitly asks for.

## Decision 1 — Run on GCP with the $300 credit (not the Always-Free tier)

| Option | What you get | Verdict |
|---|---|---|
| Always Free | **1× e2-micro = 1 GB RAM** (us-west1/central1/east1) | Can't even boot TigerGraph (needs ≥8 GB). ❌ |
| **$300 credit** | full-size VMs for the few days of testing | ✅ Use this |

We use a billing-enabled account with the $300 credit applied (region `us-central1`). A 3-node,
3-day run costs **~$38** of the credit. VMs are **stopped** between sessions so idle compute cost
is ~$0.

## Decision 2 — Node size: e2-standard-4 (quota is full, so use the proper spec)

- TigerGraph 4.1.x minimum per node: **8 GB RAM, 4 cores, 50 GB SSD**.
- Measured account quota: regional `CPUS`=200, `E2_CPUS`=24, global `CPUS_ALL_REGIONS`=32 — **not**
  the capped free-trial ceiling. So the textbook node size fits.

| Node | vCPU/RAM | 3 nodes | Fits quota? |
|---|---|---|---|
| **e2-standard-4** | **4 / 16 GB** | 12 vCPU | ✅ chosen — meets the 4-core + 8 GB min with headroom |
| e2-standard-2 | 2 / 8 GB | 6 vCPU | fallback if quota were capped |

**Chosen: 3× e2-standard-4.** Clears the per-node minimum comfortably (16 GB RAM lets TigerGraph
hold the working graph in memory). SSD is **mandatory** (TigerGraph fails on spinning disk) →
`--boot-disk-type=pd-ssd`.

## Decision 3 — Topology: 3 nodes, replication factor 2

- **RF 2** is the minimum for HA; combined with the minimum 3 nodes, this is the smallest valid HA
  cluster and keeps the focus on replication + quorum behaviour (rather than partitioning).
- With RF 2 on 3 nodes, TigerGraph places the graph data (GPE/GSE) on **2 of the 3 nodes** and uses
  the third as a coordination/compute node. That placement became a finding in itself — *which* node
  you lose matters (see Case 1: losing the non-data node is transparent; losing a data-replica node
  triggers a brief reroute).
- It also sets up the report's sharpest observation — the **quorum boundary**: with 2 of 3 nodes
  down, the survivor still holds a full data replica, yet the cluster is unusable because the
  ZK/etcd quorum lost majority. Effective node-loss tolerance = 1, set by the *coordination* layer,
  not replication.
- Alternative `2×2` (4 nodes) adds a data-partitioning story, but muddies the quorum story.
  Kept as "future work".

## Decision 4 — Edition: Enterprise Free / Developer (HA-capable), NOT Community

This one is a correctness gate, not a preference. TigerGraph's **Community Edition** is, per their
own page, **"Clustering: No. Single-server only."** It has no replication, no failover, no quorum —
so it **cannot host the HA cluster or the node-failure tests this project requires.** The HA
feature set lives only in the Enterprise/Developer editions, which are also free (the free license
grants full features incl. clustering). A license is **mandatory** — *"without a valid license key,
database operations will not work"* — so there is no license-free multi-node path.

## Decision 5 — Manual offline install

Path: offline tarball from `dl.tigergraph.com` + a free Enterprise/Developer **license key** +
`install.sh -n` with `install_conf.json` (the 3 internal IPs + replication factor 2). On a paid
account the GCP Marketplace image is available, but it's a single-node image — the manual installer
is the way to stand up a real multi-node HA cluster with controlled sizing.

## Scope boundaries (state these explicitly)

**In scope:** single-node failure across read availability, GSQL/control-plane failover,
degraded-mode restrictions, the quorum boundary, and recovery/MTTR.
**Out of scope (future work):** exhaustive GSQL feature testing, performance benchmarking,
data partitioning (`2×2`), multi-region DR, Kubernetes chaos, sustained load / OOM / disk-full.
