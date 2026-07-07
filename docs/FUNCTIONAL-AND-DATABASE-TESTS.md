# Functional & Database Testing

> **Docs:** [Overview](../README.md) &middot; [HA Report](REPORT.md) &middot; [Test-Case Matrix](TEST-CASES.md) &middot; [Evidence](TEST-EVIDENCE-REPORT.md) &middot; **Functional &amp; DB** &middot; [Decisions](DECISION.md) &middot; [Test Plan](TEST-PLAN.md) &middot; [pytest suite](../tests/README.md) &middot; [🌐 Report site](index.html)


This complements the HA failure-recovery report ([REPORT.md](REPORT.md)) with **functional** testing
(does the database work correctly under *normal* conditions?) and deeper **database/data-correctness**
testing. Every test asserts an **expected value against the actual result**; raw output and images are
in [`../results/`](../results/) and [`../results/screenshots/`](../results/screenshots/).

> **The complete enumerated test-case matrix (all 45 cases, ID / expected / actual / status) is in
> [TEST-CASES.md](TEST-CASES.md).** This file is the narrative walkthrough with verdicts.

**How it was run:** the functional/database/messy cases are a **pytest suite** —
[`tests/`](../tests/) (`pytest -v`, markers `functional` / `database` / `messy`) — built on a
controlled fixture with hand-computable expected values, checked via the RESTPP API. Aggregations
are verified with a small installed GSQL query (`ftAgg`) so server-side computation is tested, not
client-side. The **destructive** scenarios (node power-off, backup/restore) are deliberately *not*
in pytest — they stop cloud VMs, so they run as explicit operator procedures
(`harness/consistency_after_recovery.py`, `runbooks/`); see [`tests/README.md`](../tests/README.md)
for the two-tier rationale.

**pytest run reports** (the actual `pytest -v` output):
[functional + database — 19 passed](../results/logs/S05_functional_db.log) ·
[messy / larger data — 12 passed](../results/logs/S06_messy_data.log) ·
suite source [`tests/`](../tests/) · screenshots of the runs in [TEST-EVIDENCE-REPORT.md](TEST-EVIDENCE-REPORT.md).

---

## 1. Functional testing — normal operation (12 tests, 12 PASS)

*Evidence: `results/logs/S05_functional_db.log`, `results/screenshots/real/S05_functional_database_tests.png` (see [TEST-EVIDENCE-REPORT.md](TEST-EVIDENCE-REPORT.md)).*

| # | Test | Expected | Actual | Result |
|---|---|---|---|---|
| FT1 | Create vertex (accepted count) | 1 | 1 | ✅ |
| FT2 | Read-back returns correct attribute | 500.00 | 500 | ✅ |
| FT3 | Update-in-place (not a duplicate) | 750.25 | 750.25 | ✅ |
| FT4 | Create edge (accepted count) | 1 | 1 | ✅ |
| FT5 | Out-edge count after 1 insert | 1 | 1 | ✅ |
| FT6 | Upsert dedup — no duplicate edge | 1 | 1 | ✅ |
| FT7 | Delete vertex → no longer readable | None | None | ✅ |
| FT8 | Installed query `getAccount(acc0)` | "acc0" | "acc0" | ✅ |
| FT9 | k-hop traversal deterministic (2 runs) | 42 | 42 | ✅ |
| FT10 | Aggregation — COUNT over fixture | 3 | 3 | ✅ |
| FT11 | Aggregation — SUM(balance) | 6000.50 | 6000.50 | ✅ |
| FT12 | Filtering — COUNT(balance>1500) | 2 | 2 | ✅ |

**Verdict:** core CRUD, installed queries, traversals, aggregation and filtering all behave correctly
under normal conditions. This is the "the database simply works as intended" baseline.

## 2. Database testing — data correctness (7 tests, 7 PASS)

*Evidence: same as above.*

| # | Test | Expected | Actual | Result |
|---|---|---|---|---|
| DT1 | Read-after-write consistency (immediate) | 111.11 | 111.11 | ✅ |
| DT2 | Query-result determinism (3 identical runs) | acc5 ×3 | acc5 ×3 | ✅ |
| DT3 | Double-precision round-trip (no truncation) | 123.456789 | 123.456789 | ✅ |
| DT4 | Edge attribute (amount) round-trip | 987.65 | 987.65 | ✅ |
| DT5 | Referential integrity — edge target exists | true | true | ✅ |
| DT6 | Controlled out-edge count is exact | 1 | 1 | ✅ |
| DT7 | Missing vertex → clean error (not a crash) | error=true | error=true | ✅ |

**Verdict:** reads and writes are correct and consistent; numeric precision is preserved; queries are
deterministic; error handling for missing data is clean.

## 3. Behaviour under messy / larger data (12 tests, 12 PASS)

*Evidence: `results/logs/S06_messy_data.log`, `results/screenshots/real/S06_messy_larger_data.png`.*

| # | Test | Result |
|---|---|---|
| MD1 | Unicode + emoji name round-trip (`José García 日本語 Ω 😀`) | ✅ |
| MD2 | Special chars preserved (`O'Brien, "Bob" <script> & Co.`) — no injection/loss | ✅ |
| MD3–6 | Extreme numerics: very large, negative, zero, very small (1e-8) stored exactly | ✅ |
| MD7 | Duplicate primary-id **dedups** (last write wins) | ✅ |
| MD8–9 | Empty-string and whitespace-only values handled | ✅ |
| MD10 | 500-character string stored intact | ✅ |
| MD11–12 | **Bulk insert 5,000 vertices**, spot-checked present with exact values | ✅ |

**Verdict:** the database handles adversarial inputs safely (no injection via `<script>`, exact
numeric storage, correct primary-key dedup) and scales to a bulk insert without issue.

## 4. Consistency after node failure + recovery (4 checks, 4 PASS)

*Evidence: `results/logs/S07_consistency.log`, `results/screenshots/real/S07_consistency_after_recovery.png` + `S07b_replicas_after_recovery.png`.*

Loaded a known fixture (50 vertices, balance sum 12,250; 49 chained edges), then **powered off a data
node (m2)**, verified data still served from the survivor, recovered m2, and re-verified:

| Check | Result |
|---|---|
| All 50 vertices present after recovery | ✅ (50/50) |
| Balance sum intact (expected 12,250) | ✅ |
| Every vertex has its exact original value (no corruption) | ✅ |
| Edge structure intact | ✅ |
| Cross-replica identical (m1 vs m2 via `gstatusgraph`) | ✅ (75,053 vertices / 601,985 edges, identical) |

**Verdict:** data survives a full data-node failure and recovery with **exact values and
byte-identical replicas** — no loss, no corruption, no divergence.

## 5. Backup & restore (point-in-time revert)

*Evidence: `results/logs/S08_backup.log`, `results/screenshots/real/S08_backup_restore.png` + `S08b_restore_verified.png`.*

Enabled the Local backup provider, created a full backup (`qatest`, 7.3 MB), **modified data after
the backup** (changed a marker 111→999, inserted a new marker), then **restored**:

| Check | Result |
|---|---|
| Backup created (`gadmin backup create`) | ✅ FULL, 4.1.4, 7.3 MB |
| Post-backup change reverted (999 → **111**) | ✅ |
| Post-backup insert removed by restore | ✅ (GONE) |
| Original graph intact after restore (acc0 present) | ✅ |

**Verdict:** `gadmin backup`/`restore` correctly captures and restores a point-in-time database state.
Note: restore is disruptive — it stops GPE/GSE/RESTPP/GSQL, replaces the store, and restarts (took
~2.5 min here), so it is a planned-maintenance operation.

---

## Test count summary — three distinct kinds

| Kind | Suite | Tests | Passed | How it runs |
|---|---|---|---|---|
| **Automated pytest** | Functional (normal operation) | 12 | 12 | `pytest tests/test_functional.py` |
| | Database (data correctness) | 7 | 7 | `pytest tests/test_database.py` |
| | Messy / larger data | 12 | 12 | `pytest tests/test_messy_data.py` |
| | **subtotal (automated)** | **31** | **31** | `pytest -v` — fast, safe, CI-able |
| **Destructive / manual** | Consistency after recovery | 4 | 4 | operator procedure (powers off a node) |
| | Backup & restore | 4 | 4 | operator procedure (stops services) |
| | **subtotal (destructive)** | **8** | **8** | consciously triggered, not in pytest |
| **HA / resilience** | node-failure scenarios ([REPORT.md](REPORT.md)) | 6 | — | measured downtime & MTTR |
| | **Grand total** | **45** | — | |

These are deliberately **not** counted as one homogeneous "test" number: the 31 are automated pytest
tests; the 8 are destructive/manual functional-database checks (they stop cloud VMs, so they live as
operator procedures — see [`../tests/README.md`](../tests/README.md)); the 6 are the HA/resilience
scenarios. That split is more honest — and stronger — than claiming 45 identical tests.
