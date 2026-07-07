# TigerGraph High-Availability — Failure & Recovery Testing

> **Docs:** **Overview** &middot; [HA Report](docs/REPORT.md) &middot; [Test-Case Matrix](docs/TEST-CASES.md) &middot; [Evidence](docs/TEST-EVIDENCE-REPORT.md) &middot; [Functional &amp; DB](docs/FUNCTIONAL-AND-DATABASE-TESTS.md) &middot; [Decisions](docs/DECISION.md) &middot; [Test Plan](docs/TEST-PLAN.md) &middot; [pytest suite](tests/README.md) &middot; [🌐 Report site](docs/index.html)


A focused QA investigation into how a **TigerGraph 4.1.4** High-Availability cluster behaves under
node failure: what keeps working, what degrades by design, and how quickly it recovers — with real
measured downtime and MTTR, not hand-waving.

> **Deliverable:** the full test report is in **[docs/REPORT.md](docs/REPORT.md)**.
> Raw evidence (probe CSVs + charts) is in **[results/](results/)**.

> **📊 Report website** — a single self-contained page with findings, the quorum-boundary visual,
> the full 45-case matrix, and every screenshot: **[docs/index.html](docs/index.html)**.
> To serve it live, enable **GitHub Pages** (Settings → Pages → Branch `main`, folder `/docs`) —
> it will publish at `https://mrnewdelhi.github.io/agivant-tigergraph-ha-qa/`.

---

## Test coverage

**45 checks total**, of three different *kinds* (kept distinct on purpose — they are not the same type of test):

| Kind | Count | What | Where | Result |
|---|---|---|---|---|
| **Automated `pytest` tests** | **31** | FT1–12 functional (CRUD, queries, traversal, aggregation, filtering) · DT1–7 database correctness · MD1–12 messy/larger data — run as `pytest -v` against the live API | [tests/](tests/) · [docs/FUNCTIONAL-AND-DATABASE-TESTS.md](docs/FUNCTIONAL-AND-DATABASE-TESTS.md) | 31/31 ✅ |
| **Destructive / manual checks** | **8** | CR1–4 consistency after a node failure+recovery · BR1–4 backup & restore — stop cloud VMs, so run as operator procedures, not in the pytest suite | [docs/FUNCTIONAL-AND-DATABASE-TESTS.md](docs/FUNCTIONAL-AND-DATABASE-TESTS.md) | 8/8 ✅ |
| **HA / resilience scenarios** | **6** | node-failure cases with measured downtime & MTTR | [docs/REPORT.md](docs/REPORT.md) | see report |

Why the split matters: the 31 are fast, safe, repeatable in CI; the 8 are consciously-triggered chaos
(they power off nodes); the 6 are the core HA investigation. Calling them all one "test" would overstate
what runs automatically — see [tests/README.md](tests/README.md) for the two-tier rationale.

**Full test-case matrix** (all 45 enumerated — ID, expected, actual, status):
**[docs/TEST-CASES.md](docs/TEST-CASES.md)**.

Every test asserts **expected vs actual**. Real evidence — **17 captured screenshots** of the live
cluster (terminal + Admin Portal), each mapped to its test case — is collected in
**[docs/TEST-EVIDENCE-REPORT.md](docs/TEST-EVIDENCE-REPORT.md)**. Raw material: probe CSVs and command
output in [results/](results/), screenshots in [results/screenshots/real/](results/screenshots/real/),
full logs in [results/logs/](results/logs/).

## The HA testing

The HA cases are organised around a **two-plane model** — TigerGraph has two planes that fail
differently:

| | **Data plane** (GPE / GSE / RESTPP) | **Control plane** (GSQL leader, ZooKeeper/etcd, GUI) |
|---|---|---|
| Architecture | leaderless, replicated (RF 2) | leader/follower + quorum |
| On a **1-node** loss | reads keep serving (brief reroute) | GSQL fails over to a standby; GUI stays up |
| Blocked while degraded | — | **INSTALL QUERY, schema change** (by design) |

## Findings at a glance

| # | Scenario | Result | MTTR |
|---|---|---|---|
| 1a/b | Kill/power-off a **non-data** node | reads unaffected (100%) — transparent | 0 s |
| 1c | Kill a **data-replica** node | reads 99.5% — brief reroute window, retry-maskable | ~18–21 s |
| 2 | Kill the **GSQL leader** | control-plane pauses; **reads/writes unaffected** | ~58 s |
| 3 | INSTALL / schema change **while degraded** | **blocked by design**; un-blocks on recovery | heal ~32 s |
| 4 | **Quorum boundary** (2nd node down) | cluster **unusable** — writes rejected, reads unreliable — despite a full data replica | ~40–60 s on restore |
| 5 | Writes during a data-node failure | **atomic & consistent** — no loss, no duplicates | replica re-sync ~18 s |

**Headline — the quorum boundary:** the graph data is replicated, but the **coordination quorum
(ZooKeeper/etcd) tolerates only 1 loss**. With 2 of 3 nodes down, the surviving node still holds a
**complete data replica**, yet the cluster is effectively unusable — **writes are rejected
outright** and **reads degrade to an unreliable flap**. So effective node-loss tolerance =
**1 node**, set by the quorum layer, *not* by data replication.

> **A note on rigour:** an initial pass reported that boundary as a clean "0% reads." A finer-grained
> re-measurement showed reads actually *flap* ~50/50 for minutes before fully failing — the earlier
> figure was a too-short-window artefact. The report documents the corrected behaviour; writes,
> which fail deterministically, are the cleaner signal of quorum loss. (See the honesty note in
> [docs/REPORT.md](docs/REPORT.md) §4, Case 4.)

## Environment

- **TigerGraph Enterprise 4.1.4** (offline install), 3-node HA, **replication factor 2**.
- **3× GCP `e2-standard-4`** (4 vCPU / 16 GB) · Ubuntu 22.04 · 50 GB SSD · single zone `us-central1-a`.
- **Data:** 20k Person, 50k Account, 50k OWNS, ~500k TRANSFER edges.
- **Workloads:** point-lookup, 3-hop traversal, and a write path.

*Version note:* the brief asked for 4.1.3; TigerGraph no longer distributes it — **4.1.4** is the
current 4.1 LTS, used deliberately. **Community Edition** (single-server, no clustering) and the
managed **Savanna** cloud (no node-level failure control) were both ruled out as unable to satisfy
an HA node-failure test — see [docs/DECISION.md](docs/DECISION.md).

## Repository layout

```
docs/
  REPORT.md            ← the test report (cases, reasoning, findings, MTTR)
  DECISION.md          environment & scope decisions (and why)
  TEST-PLAN.md         test cases + measurement methodology
results/
  FINDINGS.md          working findings log captured live during testing
  *.csv                raw probe evidence for each case
  *.png                latency + quorum-boundary charts
  final_gadmin_status.txt
tests/
  test_functional.py   pytest: FT1-FT12 (CRUD, queries, aggregation, filtering)
  test_database.py     pytest: DT1-DT7 (correctness, precision, determinism)
  test_messy_data.py   pytest: MD1-MD12 (unicode, injection, dedup, bulk 5k)
  conftest.py          API helper + known fixture (run: python3 -m pytest -v)
harness/
  probe.py / *.sh      probes (read/write/liveness) + MTTR analysis scripts
  *_tests.py           destructive-scenario checkers (node-kill consistency etc.)
infra/
  setup-gcp.sh         provision the 3 VMs (gcloud)
  prereqs.sh           per-node OS prerequisites
  INSTALL.md           TigerGraph HA install runbook
  build_install_conf.sh  generates the non-interactive install config
data/
  schema.gsql / load.gsql / queries.gsql / gen_data.py
runbooks/
  case1..case6.md      per-case execution steps
```

## Reproduce it

```bash
# 1. Provision the cluster (gcloud authenticated, project set)
export TG_PROJECT=your-gcp-project
bash infra/setup-gcp.sh

# 2. Install TigerGraph 4.1.4 HA — follow infra/INSTALL.md (offline installer + install_conf.json)

# 3. Load data + install queries
python3 data/gen_data.py --out /tmp/data
gsql data/schema.gsql && gsql data/load.gsql && gsql data/queries.gsql
gsql -g finGraph "INSTALL QUERY ALL"

# 4. Baseline, then inject a failure per runbooks/, and measure
pip install -r harness/requirements.txt
python3 harness/probe.py --url "http://<NODE_IP>:14240/restpp/query/finGraph/kHopTransfers?acc=acc0&k=3" \
        --interval 0.2 --duration 90 --out results/baseline.csv
python3 harness/analyze.py results/baseline.csv
```
