# Test Case Matrix — TigerGraph 4.1.4 HA

> **Docs:** [Overview](../README.md) &middot; [HA Report](REPORT.md) &middot; **Test-Case Matrix** &middot; [Evidence](TEST-EVIDENCE-REPORT.md) &middot; [Functional &amp; DB](FUNCTIONAL-AND-DATABASE-TESTS.md) &middot; [Decisions](DECISION.md) &middot; [Test Plan](TEST-PLAN.md) &middot; [pytest suite](../tests/README.md) &middot; [🌐 Report site](index.html)


The complete, enumerated test suite: **45 test cases** across three kinds. Every case lists its
input/method, expected result, actual result, status, and evidence. Assertion code for the automated
cases is in [`../tests/`](../tests/); screenshots are mapped in
[TEST-EVIDENCE-REPORT.md](TEST-EVIDENCE-REPORT.md); HA analysis and MTTR in [REPORT.md](REPORT.md).

**pytest run reports** (`pytest -v` output):
[functional + database — 19 passed](../results/logs/S05_functional_db.log) ·
[messy / larger data — 12 passed](../results/logs/S06_messy_data.log).

**Environment:** TigerGraph 4.1.4 Enterprise · 3-node HA · RF=2 · GCP e2-standard-4 · graph `finGraph`
(20k Person, 50k Account, ~500k TRANSFER). **Fixture** for aggregation cases: `ftA=1000.00`,
`ftB=2000.00`, `ftC=3000.50` with edges ftA→ftB, ftA→ftC, ftB→ftC (see `tests/conftest.py`).

Legend — **Status:** ✅ Pass. **Kind:** `AUTO` = automated pytest · `MANUAL` = destructive/operator ·
`HA` = resilience scenario.

---

## 1. Functional tests — normal operation (AUTO · `tests/test_functional.py`)

| ID | Test case | Method / input | Expected | Actual | Status |
|---|---|---|---|---|---|
| FT1 | Create vertex, accepted count | POST Account `ftD` balance 500 | `accepted_vertices=1` | 1 | ✅ |
| FT2 | Read-back returns correct value | GET the created vertex | `balance=500.00` | 500 | ✅ |
| FT3 | Update-in-place (upsert, not duplicate) | POST same id with 750.25 | `balance=750.25`, one vertex | 750.25 | ✅ |
| FT4 | Create edge, accepted count | POST TRANSFER ftD4→ftA | `accepted_edges=1` | 1 | ✅ |
| FT5 | Out-edge count after 1 insert | GET out-edges of ftD5 | 1 | 1 | ✅ |
| FT6 | Upsert dedup — no duplicate edge | POST same edge twice | 1 (deduped) | 1 | ✅ |
| FT7 | Delete vertex → no longer readable | DELETE then GET ftD7 | not found (None) | None | ✅ |
| FT8 | Installed query `getAccount(acc0)` | GET /query/getAccount | returns `acc0` | acc0 | ✅ |
| FT9 | k-hop traversal deterministic | run `kHopTransfers(acc0,2)` twice | both runs equal | equal | ✅ |
| FT10 | Aggregation — COUNT over fixture | `ftAgg()` → n | 3 | 3 | ✅ |
| FT11 | Aggregation — SUM(balance) | `ftAgg()` → bal | 6000.50 | 6000.50 | ✅ |
| FT12 | Filtering — COUNT(balance>1500) | `ftAgg()` → hi | 2 | 2 | ✅ |

## 2. Database / data-correctness (AUTO · `tests/test_database.py`)

| ID | Test case | Method / input | Expected | Actual | Status |
|---|---|---|---|---|---|
| DT1 | Read-after-write consistency (immediate) | write 111.11, read back | 111.11 | 111.11 | ✅ |
| DT2 | Query-result determinism (3 runs) | `getAccount(acc5)` ×3 | acc5, acc5, acc5 | acc5 ×3 | ✅ |
| DT3 | Double-precision round-trip (no truncation) | store 123.456789 | 123.456789 | 123.456789 | ✅ |
| DT4 | Edge attribute (amount) round-trip | edge amount 987.65 | 987.65 | 987.65 | ✅ |
| DT5 | Referential integrity — edge target exists | check ftA present | exists | true | ✅ |
| DT6 | Controlled out-edge count is exact | 1 edge inserted | 1 | 1 | ✅ |
| DT7 | Missing vertex → clean error (not crash) | GET nonexistent id | `error=true` | error=true | ✅ |

## 3. Messy / larger data (AUTO · `tests/test_messy_data.py`)

| ID | Test case | Method / input | Expected | Actual | Status |
|---|---|---|---|---|---|
| MD1 | Unicode + emoji round-trip | name `José García 日本語 Ω 😀` | stored intact | intact | ✅ |
| MD2 | Special chars / injection-shaped | `O'Brien, "Bob" <script> & Co.` | stored verbatim, no injection | verbatim | ✅ |
| MD3 | Very large balance | 999999999999.99 | exact | exact | ✅ |
| MD4 | Negative balance | -500.25 | exact | -500.25 | ✅ |
| MD5 | Zero balance | 0.0 | exact | 0 | ✅ |
| MD6 | Very small value (1e-8) | 0.00000001 | exact | 0.00000001 | ✅ |
| MD7 | Duplicate primary-id dedups | write id twice (100 then 200) | last wins = 200 | 200 | ✅ |
| MD8 | Empty-string value | name `""` | stored as empty | "" | ✅ |
| MD9 | Whitespace-only value preserved | name `"   "` | preserved | "   " | ✅ |
| MD10 | Long string (500 chars) intact | 500× `X` | 500 chars intact | intact | ✅ |
| MD11 | Bulk insert 5,000 vertices | POST 5×1000 batches | spot-checked present | 4/4 present | ✅ |
| MD12 | Bulk value integrity | read `bulk4999` | 4999 | 4999 | ✅ |

## 4. Consistency after node failure + recovery (MANUAL · `harness/consistency_after_recovery.py`)

**Preconditions:** load 50-vertex fixture (balance sum 12,250; 49 chained edges).
**Steps:** power off data node m2 → verify while degraded → recover m2 → re-verify → compare replicas.

| ID | Test case | Expected | Actual | Status |
|---|---|---|---|---|
| CR1 | All 50 vertices present (during outage & after recovery) | 50 | 50 | ✅ |
| CR2 | Balance sum intact | 12,250 | 12,250 | ✅ |
| CR3 | Every vertex has exact original value (no corruption) | exact | exact | ✅ |
| CR4 | Edge structure intact; replicas m1==m2 identical after rejoin | identical | 75,053 v / 601,985 e, identical | ✅ |

## 5. Backup & restore — point-in-time (MANUAL · `gadmin backup`)

**Steps:** plant marker 111 → `gadmin backup create` → change marker to 999 → `gadmin backup restore` → verify.

| ID | Test case | Expected | Actual | Status |
|---|---|---|---|---|
| BR1 | Backup created & listed (`gadmin backup list`) | FULL, 4.1.4 | FULL 4.1.4, 7.3 MB | ✅ |
| BR2 | Post-backup change visible before restore | 999 | 999 | ✅ |
| BR3 | Restore reverts value to backup state | 111 | 111 | ✅ |
| BR4 | Original graph intact after restore | acc0 present | present | ✅ |

## 6. HA / resilience scenarios (HA · [REPORT.md](REPORT.md) · probe CSVs in `../results/`)

**Method:** drive a continuous read/write probe, inject the failure, measure impact and mean-time-to-recovery.

| ID | Scenario | Steps | Expected | Actual / observed | MTTR | Status |
|---|---|---|---|---|---|---|
| HA1a | Kill GPE on a non-data node (m3) | `gpe kill` on m3 | reads unaffected | reads 100% | 0 s | ✅ |
| HA1b | Power off a non-data node (m3) | `gcloud stop tg-m3` | reads unaffected | reads 100% | 0 s | ✅ |
| HA1c | Kill a data-replica node (m2) | `gcloud stop tg-m2` | brief reroute, reads recover | reads 99.5%, ~18–21 s reroute (retry-maskable) | ~18–21 s | ✅ |
| HA2 | Kill the GSQL leader | kill leader, watch failover | control-plane failover; data plane unaffected | reads/writes served throughout; leader m1→m3 in logs | ~58 s | ✅ |
| HA3 | INSTALL QUERY / schema while degraded | node down, run INSTALL | DDL blocked while degraded | `(pendingInstall)`, REST 404; CLI falsely "success" | heal ~32 s | ✅ |
| HA4 | Quorum boundary — 2nd node down | stop m2 **and** m3 | quorum lost | writes rejected, reads flap — despite full replica on m1 | ~40–60 s on restore | ✅ |
| HA5 | Writes during a data-node failure | 2,000 writes through m2 kill | no loss, no duplicates | 1,994 ok = 1,994 persisted; replicas byte-identical | re-sync ~18 s | ✅ |
| HA6 | Recovery MTTR synthesis | aggregate the above | recovery within seconds | service ~18–21 s · leader ~58 s · heal ~32 s · quorum ~49 s | — | ✅ |

---

## Summary

| Kind | Cases | Passed | Where |
|---|---|---|---|
| Functional (FT) | 12 | 12 | `tests/test_functional.py` |
| Database (DT) | 7 | 7 | `tests/test_database.py` |
| Messy / larger (MD) | 12 | 12 | `tests/test_messy_data.py` |
| **Automated subtotal** | **31** | **31** | `pytest -v` |
| Consistency (CR) | 4 | 4 | `harness/consistency_after_recovery.py` |
| Backup/restore (BR) | 4 | 4 | `gadmin backup` procedure |
| **Destructive/manual subtotal** | **8** | **8** | operator procedures |
| HA / resilience (HA1a–HA6) | 6 | 6 | measured scenarios |
| **Grand total** | **45** | **45** | |

Every automated case asserts expected-vs-actual and exits non-zero on failure; the 8 destructive and
6 HA cases are operator-run because they power off cloud VMs. Full command output is in
[`../results/logs/`](../results/logs/); captured screenshots in
[`../results/screenshots/real/`](../results/screenshots/real/).
