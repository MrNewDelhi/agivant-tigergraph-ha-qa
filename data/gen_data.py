#!/usr/bin/env python3
"""Generate a non-trivial CSV dataset for the HA test graph.

A trivial graph hides failures (a 5ms query masks a 200ms failover blip), so we make the
k-hop traversal do real work. Default ~50k accounts / ~500k transfers is enough to be
observable without turning this into a benchmark. Scale up with --accounts if you like.

Outputs 4 CSVs into --out:  persons.csv  accounts.csv  owns.csv  transfers.csv
"""
import argparse, csv, os, random

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/tmp/data")
    ap.add_argument("--persons", type=int, default=20000)
    ap.add_argument("--accounts", type=int, default=50000)
    ap.add_argument("--transfers", type=int, default=500000)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    random.seed(args.seed)
    os.makedirs(args.out, exist_ok=True)

    with open(f"{args.out}/persons.csv", "w", newline="") as f:
        w = csv.writer(f)
        for i in range(args.persons):
            w.writerow([f"p{i}", f"Person_{i}"])

    with open(f"{args.out}/accounts.csv", "w", newline="") as f:
        w = csv.writer(f)
        for i in range(args.accounts):
            w.writerow([f"acc{i}", round(random.uniform(0, 100000), 2)])

    # each account owned by a random person
    with open(f"{args.out}/owns.csv", "w", newline="") as f:
        w = csv.writer(f)
        for i in range(args.accounts):
            w.writerow([f"p{random.randint(0, args.persons-1)}", f"acc{i}"])

    # transfers between random accounts -> gives the k-hop query a dense graph to walk
    with open(f"{args.out}/transfers.csv", "w", newline="") as f:
        w = csv.writer(f)
        for _ in range(args.transfers):
            a = random.randint(0, args.accounts-1)
            b = random.randint(0, args.accounts-1)
            if a != b:
                w.writerow([f"acc{a}", f"acc{b}", round(random.uniform(1, 5000), 2)])

    print(f"Wrote CSVs to {args.out}: "
          f"{args.persons} persons, {args.accounts} accounts, ~{args.transfers} transfers")
    print("Copy to a node, then adjust the paths in data/load.gsql before RUN LOADING JOB.")

if __name__ == "__main__":
    main()
