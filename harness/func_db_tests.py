#!/usr/bin/env python3
"""Functional + Database correctness test suite for TigerGraph finGraph.

Runs from a client against RESTPP (nginx :14240). Every test asserts an EXPECTED value
against the ACTUAL result and prints PASS/FAIL — results are independently verifiable.

Endpoints used (all standard RESTPP):
  - /graph/finGraph                              upsert vertices/edges
  - /graph/finGraph/vertices/Account/<id>        read / DELETE a vertex
  - /graph/finGraph/edges/Account/<id>/TRANSFER  list out-edges
  - /query/finGraph/<name>                        installed queries (getAccount, kHopTransfers, ftAgg)

Usage: python3 harness/func_db_tests.py http://<M1_IP>:14240
"""
import sys, json
import requests

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:14240"
G = f"{BASE}/restpp/graph/finGraph"
Q = f"{BASE}/restpp/query/finGraph"
S = requests.Session()
passed = failed = 0
LOG = []

def check(name, expected, actual):
    global passed, failed
    ok = expected == actual
    passed += ok; failed += (not ok)
    line = f"[{'PASS' if ok else 'FAIL'}] {name}\n        expected = {expected!r}\n        actual   = {actual!r}"
    print(line); LOG.append(line)

def upv(vid, bal):
    return S.post(G, data=json.dumps({"vertices":{"Account":{vid:{"balance":{"value":bal}}}}}),
                  timeout=10).json()["results"][0]["accepted_vertices"]
def upe(a, b, amt):
    return S.post(G, data=json.dumps({"edges":{"Account":{a:{"TRANSFER":{"Account":{b:{"amount":{"value":amt}}}}}}}}),
                  timeout=10).json()["results"][0]["accepted_edges"]
def getv(vid):
    j = S.get(f"{G}/vertices/Account/{vid}", timeout=10).json()
    return j["results"][0]["attributes"] if (not j.get("error") and j.get("results")) else None
def delv(vid):
    return S.delete(f"{G}/vertices/Account/{vid}", timeout=10).json()
def out_edges(vid):
    j = S.get(f"{G}/edges/Account/{vid}/TRANSFER", timeout=10).json()
    return j.get("results", []) if not j.get("error") else []
def query(name, **params):
    return S.get(f"{Q}/{name}", params=params, timeout=20).json()
def banner(t):
    print(f"\n{'='*70}\n  {t}\n{'='*70}"); LOG.append(f"\n=== {t} ===")

# ---------------------------------------------------------------- FIXTURE
banner("SETUP — controlled fixture with known values")
for v in ("ftA","ftB","ftC","ftD","ftE","ftF","ftG"):
    delv(v)
upv("ftA",1000.00); upv("ftB",2000.00); upv("ftC",3000.50)
upe("ftA","ftB",100.00); upe("ftA","ftC",200.00); upe("ftB","ftC",50.00)
print("fixture: ftA=1000.00, ftB=2000.00, ftC=3000.50 ; edges ftA->ftB, ftA->ftC, ftB->ftC")

# ================================================================ FUNCTIONAL
banner("FUNCTIONAL TESTS — does the database work as intended under normal conditions?")
check("FT1  create vertex — accepted count", 1, upv("ftD", 500.00))
check("FT2  read-back returns correct attribute value", 500.00, (getv("ftD") or {}).get("balance"))
upv("ftD", 750.25)
check("FT3  update-in-place (not a duplicate) — new value", 750.25, (getv("ftD") or {}).get("balance"))
check("FT4  create edge — accepted count", 1, upe("ftD","ftA", 42.00))
check("FT5  out-edge count after 1 insert", 1, len(out_edges("ftD")))
upe("ftD","ftA", 42.00)
check("FT6  upsert dedup — still 1 edge (no duplicate)", 1, len(out_edges("ftD")))
delv("ftD")
check("FT7  delete vertex → no longer readable", None, getv("ftD"))
r = query("getAccount", acc="acc0")
check("FT8  installed query getAccount(acc0) returns acc0", "acc0",
      (r["results"][0]["S"][0]["v_id"] if not r.get("error") else "ERR"))
k1 = query("kHopTransfers", acc="acc0", k=2)["results"][0]["reached"]
k2 = query("kHopTransfers", acc="acc0", k=2)["results"][0]["reached"]
check("FT9  k-hop traversal deterministic (run twice)", k1, k2)
agg = query("ftAgg")["results"][0]
check("FT10 aggregation — COUNT over fixture", 3, agg["n"])
check("FT11 aggregation — SUM(balance) over fixture", 6000.50, agg["bal"])
check("FT12 filtering — COUNT(balance>1500) in fixture", 2, agg["hi"])

# ================================================================ DATABASE
banner("DATABASE TESTS — data correctness across reads, writes, types, structure")
upv("ftE", 111.11)
check("DT1  read-after-write consistency (immediate)", 111.11, (getv("ftE") or {}).get("balance"))
res = [query("getAccount", acc="acc5")["results"][0]["S"][0]["v_id"] for _ in range(3)]
check("DT2  query-result determinism (3 identical runs)", ["acc5"]*3, res)
upv("ftF", 123.456789)
check("DT3  double-precision round-trip (no truncation)", 123.456789, (getv("ftF") or {}).get("balance"))
upv("ftG", 0.0); upe("ftG","ftA", 987.65)
amts = [e["attributes"]["amount"] for e in out_edges("ftG")]
check("DT4  edge attribute (amount) round-trip", [987.65], amts)
check("DT5  referential integrity — edge target vertex exists", True, getv("ftA") is not None)
check("DT6  controlled out-edge count is exact", 1, len(out_edges("ftG")))
# negative test: reading a non-existent vertex is a clean 'not found', not a crash
nf = S.get(f"{G}/vertices/Account/does_not_exist_zzz", timeout=10).json()
check("DT7  missing vertex → clean error (error flag true)", True, nf.get("error") is True)

# cleanup
for v in ("ftA","ftB","ftC","ftE","ftF","ftG"):
    delv(v)

banner(f"SUMMARY:  {passed} passed, {failed} failed   (total {passed+failed})")
open("results/func_db_test_output.txt","w").write("\n".join(LOG) + f"\n\nSUMMARY: {passed} passed, {failed} failed\n")
sys.exit(1 if failed else 0)
