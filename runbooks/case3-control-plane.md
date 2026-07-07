# Case 3 — Control-plane operations during a node failure  `[core — highest signal]`

**Why:** A mature QA report maps the sharp edges, not just the happy path. TigerGraph
**intentionally blocks** a set of operations while any node is down. Verifying that fault model —
rather than assuming it — is exactly what they want to see.

**Prediction:** new-query install, schema change, and DB export are **rejected** while a node is
down; interpreted + existing installed queries still run. Full function restored on node recovery
(or by removing/replacing the node).

## Setup
Kill one node (reuse Case 1's method — e.g. power off m3), leave it down. Confirm reads still work
(Case 1). Then attempt each control-plane op and **capture the exact error + how fast it fails**
(rejected fast is good; hung is a finding).

```bash
# On a survivor (m1), as tigergraph, with m3 DOWN:

# 3a. INSTALL a new query  -> expect rejection
gsql -g finGraph "CREATE QUERY probe3() FOR GRAPH finGraph { PRINT 1; }"
gsql -g finGraph "INSTALL QUERY probe3"            # <-- capture this output

# 3b. SCHEMA change -> expect rejection
gsql -g finGraph "CREATE GLOBAL SCHEMA_CHANGE JOB j3 { ADD VERTEX Bank (PRIMARY_ID id STRING); }"
gsql -g finGraph "RUN GLOBAL SCHEMA_CHANGE JOB j3"  # <-- capture this output

# 3c. DB export -> expect rejection
gadmin backup ...     # or the export path in your build; capture the rejection

# --- CONFIRM what SHOULD still work (positive control) ---
# interpreted query (no install needed):
gsql -g finGraph "INTERPRET QUERY () FOR GRAPH finGraph { PRINT 1; }"
# existing installed query over REST:
curl -s "http://<M1_IP>:9000/query/finGraph/kHopTransfers?acc=acc0&k=2" -H "Authorization: Bearer $TG_TOKEN"
```

## Measure — build one clean table
| Op | With node down | Error text | Fast-fail? | Works after recovery? | Recovery time |
|---|---|---|---|---|---|
| INSTALL QUERY | rejected / allowed | ... | y/n | y | ...s |
| Schema change | ... | ... | ... | ... | ... |
| DB export | ... | ... | ... | ... | ... |
| Interpreted query | works (control) | — | — | — | — |
| Existing installed query | works (control) | — | — | — | — |

## Recover + time the un-blocking
Bring m3 back, then loop each blocked op every 5 s and record when it starts succeeding:
```bash
while true; do date +%s.%3N; gsql -g finGraph "INSTALL QUERY probe3" 2>&1 | tail -1; sleep 5; done \
  | tee results/case3_unblock.log
```

**Pass:** behaviour matches the documented model; you've quantified recovery and named the
workaround (remove/replace the failed node to restore full function without waiting).
