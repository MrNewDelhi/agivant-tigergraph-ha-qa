#!/usr/bin/env python3
"""DB test: behaviour under messy / edge-case data.

Feeds deliberately tricky inputs and asserts TigerGraph handles them correctly:
unicode & special characters, extreme numeric values, duplicate primary IDs (must dedup),
empty/whitespace fields, and a bulk insert to show it scales.

Usage: python3 messy_data_tests.py http://<M1_IP>:14240
"""
import sys, json, requests
BASE = sys.argv[1].rstrip("/")
G = f"{BASE}/restpp/graph/finGraph"
S = requests.Session()
passed = failed = 0; LOG = []

def check(name, expected, actual):
    global passed, failed
    ok = expected == actual; passed += ok; failed += (not ok)
    l = f"[{'PASS' if ok else 'FAIL'}] {name}\n        expected = {expected!r}\n        actual   = {actual!r}"
    print(l); LOG.append(l)

def up_person(pid, name):
    r = S.post(G, data=json.dumps({"vertices":{"Person":{pid:{"name":{"value":name}}}}}), timeout=10).json()
    return r["results"][0]["accepted_vertices"] if not r.get("error") else -1
def up_acct(aid, bal):
    r = S.post(G, data=json.dumps({"vertices":{"Account":{aid:{"balance":{"value":bal}}}}}), timeout=10).json()
    return r["results"][0]["accepted_vertices"] if not r.get("error") else -1
def get_person_name(pid):
    j = S.get(f"{G}/vertices/Person/{pid}", timeout=10).json()
    return j["results"][0]["attributes"]["name"] if (not j.get("error") and j.get("results")) else None
def get_bal(aid):
    j = S.get(f"{G}/vertices/Account/{aid}", timeout=10).json()
    return j["results"][0]["attributes"]["balance"] if (not j.get("error") and j.get("results")) else None
def banner(t): print(f"\n{'='*70}\n  {t}\n{'='*70}"); LOG.append(f"\n=== {t} ===")

banner("MESSY / EDGE-CASE DATA TESTS")

# 1. Unicode + emoji round-trip
uni = "José García 日本語 Ω 😀"
up_person("msg_uni", uni)
check("MD1  unicode + emoji name round-trip", uni, get_person_name("msg_uni"))

# 2. Special characters (quotes, comma, angle brackets, apostrophe)
spec = "O'Brien, \"Bob\" <script> & Co."
up_person("msg_spec", spec)
check("MD2  special characters preserved (no injection/loss)", spec, get_person_name("msg_spec"))

# 3. Extreme numeric values
up_acct("msg_big", 999999999999.99)
check("MD3  very large balance stored exactly", 999999999999.99, get_bal("msg_big"))
up_acct("msg_neg", -500.25)
check("MD4  negative balance stored exactly", -500.25, get_bal("msg_neg"))
up_acct("msg_zero", 0.0)
check("MD5  zero balance stored exactly", 0, get_bal("msg_zero"))
up_acct("msg_tiny", 0.00000001)
check("MD6  very small balance stored exactly", 0.00000001, get_bal("msg_tiny"))

# 4. Duplicate primary ID — MUST dedup to one vertex, last write wins
up_acct("msg_dup", 100.0)
up_acct("msg_dup", 200.0)   # same id again, different value
check("MD7  duplicate primary-id dedups (last value wins)", 200.0, get_bal("msg_dup"))

# 5. Empty / whitespace name
up_person("msg_empty", "")
check("MD8  empty-string name handled (round-trips as empty)", "", get_person_name("msg_empty"))
up_person("msg_ws", "   ")
check("MD9  whitespace-only name preserved (not trimmed to loss)", "   ", get_person_name("msg_ws"))

# 6. Long string
long_name = "X" * 500
up_person("msg_long", long_name)
check("MD10 long (500-char) name stored intact", long_name, get_person_name("msg_long"))

# 7. Bulk insert (larger data) — 5000 vertices in batches, then a spot-count
banner("LARGER DATA — bulk insert 5,000 vertices, verify all landed")
BATCH, TOTAL = 1000, 5000
for start in range(0, TOTAL, BATCH):
    verts = {f"bulk{i}": {"balance": {"value": float(i)}} for i in range(start, start+BATCH)}
    S.post(G, data=json.dumps({"vertices": {"Account": verts}}), timeout=30)
present = sum(1 for i in (0, 1234, 2500, 4999) if get_bal(f"bulk{i}") is not None)
check("MD11 bulk insert — spot-checked 4/4 sample vertices present", 4, present)
check("MD12 bulk value integrity — bulk4999 has balance 4999", 4999, get_bal("bulk4999"))

# cleanup
for v in ("msg_big","msg_neg","msg_zero","msg_tiny","msg_dup"):
    S.delete(f"{G}/vertices/Account/{v}", timeout=10)
for v in ("msg_uni","msg_spec","msg_empty","msg_ws","msg_long"):
    S.delete(f"{G}/vertices/Person/{v}", timeout=10)
for i in range(0, 5000):
    if i % 500 == 0:  # delete a sample; full cleanup optional
        S.delete(f"{G}/vertices/Account/bulk{i}", timeout=10)

banner(f"SUMMARY:  {passed} passed, {failed} failed   (total {passed+failed})")
open("results/messy_data_test_output.txt","w").write("\n".join(LOG) + f"\n\nSUMMARY: {passed} passed, {failed} failed\n")
sys.exit(1 if failed else 0)
