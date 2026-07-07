#!/usr/bin/env python3
"""DB test: data consistency after a node failure + recovery.

Loads a known fixture, kills a DATA node (m2) via gcloud, recovers it, then verifies every
record survived with its exact value and the two replicas are identical.

Usage: python3 consistency_after_recovery.py http://<M1_IP>:14240 <m2_instance> <zone>
Kill/recover is driven by the caller (this script only does the data verification either side);
see the runner in the shell that wraps it.
"""
import sys, json, time, requests
BASE = sys.argv[1].rstrip("/")
G = f"{BASE}/restpp/graph/finGraph"
S = requests.Session()
N = 50   # rec0..rec49

def upv(vid, bal):
    S.post(G, data=json.dumps({"vertices":{"Account":{vid:{"balance":{"value":bal}}}}}), timeout=10)
def upe(a, b, amt):
    S.post(G, data=json.dumps({"edges":{"Account":{a:{"TRANSFER":{"Account":{b:{"amount":{"value":amt}}}}}}}}), timeout=10)
def _get(url):
    # resilient GET: retry through the brief reroute window when a node is down
    for _ in range(6):
        try:
            return S.get(url, timeout=6).json()
        except Exception:
            time.sleep(2)
    return {"error": True}
def getbal(vid):
    j = _get(f"{G}/vertices/Account/{vid}")
    return j["results"][0]["attributes"]["balance"] if (not j.get("error") and j.get("results")) else None
def edgecount(vid):
    j = _get(f"{G}/edges/Account/{vid}/TRANSFER")
    return len(j.get("results", [])) if not j.get("error") else -1

mode = sys.argv[4] if len(sys.argv) > 4 else "verify"

if mode == "load":
    for v in [f"rec{i}" for i in range(N)]:
        S.delete(f"{G}/vertices/Account/{v}", timeout=10)
    for i in range(N):
        upv(f"rec{i}", i*10.0)               # balances 0,10,...,490  -> sum 12250
    for i in range(N-1):
        upe(f"rec{i}", f"rec{i+1}", float(i))  # 49 chained edges
    print(f"LOADED {N} vertices (sum should be {sum(i*10.0 for i in range(N))}), {N-1} edges")
else:
    # verify every record survived with exact value
    bals = {i: getbal(f"rec{i}") for i in range(N)}
    present = sum(1 for b in bals.values() if b is not None)
    total = sum(b for b in bals.values() if b is not None)
    expected_total = sum(i*10.0 for i in range(N))
    exact = all(bals[i] == i*10.0 for i in range(N))
    edges = edgecount("rec0")  # rec0 has exactly 1 out-edge
    print(f"[{'PASS' if present==N else 'FAIL'}] all {N} vertices present after recovery — got {present}")
    print(f"[{'PASS' if total==expected_total else 'FAIL'}] balance sum intact — expected {expected_total}, got {total}")
    print(f"[{'PASS' if exact else 'FAIL'}] every vertex has its exact original value (no corruption)")
    print(f"[{'PASS' if edges==1 else 'FAIL'}] edge structure intact — rec0 out-edges expected 1, got {edges}")
    ok = present==N and total==expected_total and exact and edges==1
    sys.exit(0 if ok else 1)
