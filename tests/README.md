# pytest suite — functional & database tests

> **Docs:** [Overview](../README.md) &middot; [HA Report](../docs/REPORT.md) &middot; [Test-Case Matrix](../docs/TEST-CASES.md) &middot; [Evidence](../docs/TEST-EVIDENCE-REPORT.md) &middot; [Functional &amp; DB](../docs/FUNCTIONAL-AND-DATABASE-TESTS.md) &middot; [Decisions](../docs/DECISION.md) &middot; [Test Plan](../docs/TEST-PLAN.md) &middot; **pytest suite** &middot; [🌐 Report site](../docs/index.html)


31 test cases against the live cluster's RESTPP API, organised with pytest.

**Latest run reports** (`pytest -v` output):
[functional + database — 19 passed](../results/logs/S05_functional_db.log) ·
[messy / larger data — 12 passed](../results/logs/S06_messy_data.log) ·
enumerated matrix in [TEST-CASES.md](../docs/TEST-CASES.md).

| File | Marker | Cases |
|---|---|---|
| `test_functional.py` | `functional` | FT1–FT12 — CRUD, installed queries, traversal determinism, aggregation, filtering |
| `test_database.py` | `database` | DT1–DT7 — read-after-write, determinism, precision, referential integrity, clean errors |
| `test_messy_data.py` | `messy` | MD1–MD12 — unicode/injection-shaped strings, extreme numerics, dedup, 5k bulk insert |

## Run

```bash
# target selection: TG_BASE env var, or auto-read from infra/cluster.env (M1_IP)
export TG_BASE="http://<m1-external-ip>:14240"

python3 -m pytest -v                       # everything (31 tests)
python3 -m pytest -v -m functional         # one group
python3 -m pytest -v --junitxml=results/logs/pytest_report.xml   # machine-readable report
```

`tests/conftest.py` provides the API helper, a **known fixture** with hand-computable expected
values (3 accounts + 3 edges → count 3, sum 6000.50), and scratch fixtures that clean up after
every test.

## Why the failure/recovery tests are NOT in pytest

The HA scenarios (node power-off, quorum loss, backup/restore, consistency-after-recovery) are
**destructive and stateful** — they stop cloud VMs, restart services, and take minutes per run.
Running them implicitly inside a unit-style suite would be dangerous and flaky by design, so they
live as explicit, operator-driven procedures instead:

- `harness/consistency_after_recovery.py`, `harness/case*.sh` — scripted checks used mid-scenario
- `runbooks/` + `capture/CHECKLIST.md` — the step-by-step execution procedures
- `docs/REPORT.md` — measured results (downtime, MTTR) with evidence

In CI terms: this folder is the fast, always-safe regression suite; the HA scenarios are a separate,
consciously-triggered chaos stage.
