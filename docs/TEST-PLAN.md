# Test plan & measurement methodology

> **Docs:** [Overview](../README.md) &middot; [HA Report](REPORT.md) &middot; [Test-Case Matrix](TEST-CASES.md) &middot; [Evidence](TEST-EVIDENCE-REPORT.md) &middot; [Functional &amp; DB](FUNCTIONAL-AND-DATABASE-TESTS.md) &middot; [Decisions](DECISION.md) &middot; **Test Plan** &middot; [pytest suite](../tests/README.md) &middot; [🌐 Report site](index.html)


## Measurement methodology (the differentiator)

Define timing terms up front, then treat documented numbers as **predictions your test confirms
or refutes**.

| Term | Meaning |
|---|---|
| Detection time | failure → system registers node/service down (heartbeat timeout) |
| Failover / re-route time | detection → requests served by a surviving replica |
| **Client-observed downtime** | wall-clock window where client requests fail/hang — *the number users feel*. Report **with and without** client retry. |
| MTTR (service) | failure → service answering again (seconds) |
| MTTR (redundancy) | failure → cluster back to full replica count, rejoined node caught up (minutes) |

**Procedure for every case (the same short loop):**
1. **Baseline** — start `probe.py` (+ `ping_probe.sh`, + `status_watch.sh` on a survivor). Confirm all green, note p50/p99.
2. **Break one thing** — graceful (`gadmin stop`) *and* hard (`kill -9` / `poweroff` / `iptables` partition).
3. **Watch two screens** — client probe vs. server `gadmin status`.
4. **Measure** — `analyze.py` computes downtime + MTTR from the CSV.
5. **Recover** — bring it back, time to healthy.
6. **Record** — what broke, downtime, MTTR, why.

**Repeat each scenario ≥3× (5× ideal); report median / max / spread.** The variance *is* the MTTR
characterization. Always probe through a node you are **not** killing (or an LB) — curling the
dead node measures nothing.

## Documented facts to validate (predictions)

| Behavior | Documented value |
|---|---|
| Data-plane query re-route after node failure | typically ≤ 30 s; client retry recommended |
| GSQL leader election | ≈ heartbeat interval × max-miss (default 2000 ms × 4 ≈ 8 s) |
| App server (GUI) | active-active on first 3 nodes |
| Blocked while a node is down | INSTALL QUERY, schema change, DB export |
| Min HA | RF ≥ 2 and ≥ 3 nodes (smallest HA cluster = 3 nodes, RF 2) |

## Test cases (depth over breadth — do 1–4, add 5 or 6)

| # | Case | Plane | Why | File |
|---|---|---|---|---|
| 1 | Single data-node hard failure under read load | Data | The core HA promise: node dies, reads keep serving | [case1](../runbooks/case1-read-failover.md) |
| 2 | GSQL primary (leader) failure | Control | Different failover path — leader/follower, not leaderless | [case2](../runbooks/case2-gsql-leader.md) |
| 3 | Control-plane ops during node failure | Control | Map the sharp edges: what's blocked *by design* | [case3](../runbooks/case3-control-plane.md) |
| 4 | Quorum boundary (majority failure) | Control | Find the cliff — HA tolerates exactly 1 node | [case4](../runbooks/case4-quorum-cliff.md) |
| 5 | Write path + consistency across failure | Data | Availability ≠ correctness — no lost/dup writes | [case5](../runbooks/case5-write-consistency.md) |
| 6 | Recovery / rejoin / replacement (full MTTR) | Both | "How soon does it recover?" — 3 distinct MTTRs | [case6](../runbooks/case6-recovery-mttr.md) |

**Scope call:** do 1–4 well, add 5 *or* 6 as the standout = 4–5 deep cases.
