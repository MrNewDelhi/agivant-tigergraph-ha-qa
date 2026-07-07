#!/usr/bin/env python3
"""Turn a probe CSV into downtime + MTTR numbers (and an optional latency chart).

Definitions (state these in the report):
  - Outage window = last PASS before a FAIL gap  ->  first PASS after it.
  - Client-observed downtime = duration of that gap.
  - Recovery point = first of N consecutive PASSes (default N=10) after the gap.
  - MTTR = recovery point - first FAIL.

  python3 analyze.py results/case1_probe.csv [--recover-n 10] [--chart results/case1.png]

Run each scenario >=3x and report median/max/spread — the variance IS the characterization.
"""
import argparse, csv, sys

def load(path):
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            rows.append({"epoch": float(r["epoch"]), "status": r["status"],
                         "lat": float(r["latency_ms"] or 0), "code": r["http_code"]})
    return rows

def analyze(rows, recover_n):
    if not rows:
        return "empty CSV"
    passes = [r for r in rows if r["status"] == "PASS"]
    fails  = [r for r in rows if r["status"] == "FAIL"]
    total_s = rows[-1]["epoch"] - rows[0]["epoch"]
    lat_pass = sorted(r["lat"] for r in passes)

    def pct(p):
        if not lat_pass: return 0.0
        return lat_pass[min(len(lat_pass)-1, int(p/100*len(lat_pass)))]

    # find contiguous FAIL gaps
    gaps, i = [], 0
    while i < len(rows):
        if rows[i]["status"] == "FAIL":
            j = i
            while j < len(rows) and rows[j]["status"] == "FAIL":
                j += 1
            first_fail = rows[i]["epoch"]
            last_ok_before = rows[i-1]["epoch"] if i > 0 else first_fail
            # recovery = first run of recover_n consecutive PASS at/after j
            rec = None
            k = j
            while k < len(rows):
                if all(rows[k+m]["status"] == "PASS" for m in range(recover_n) if k+m < len(rows)) \
                   and k+recover_n <= len(rows):
                    rec = rows[k]["epoch"]; break
                k += 1
            gaps.append({"first_fail": first_fail, "last_ok_before": last_ok_before,
                         "first_ok_after": rows[j]["epoch"] if j < len(rows) else None,
                         "recovery": rec, "n_failed": j - i})
            i = j
        else:
            i += 1

    out = []
    out.append(f"probes={len(rows)}  pass={len(passes)}  fail={len(fails)}  "
               f"avail={100*len(passes)/len(rows):.2f}%  window={total_s:.1f}s")
    out.append(f"latency(PASS ms): p50={pct(50):.0f}  p90={pct(90):.0f}  p99={pct(99):.0f}  max={max(lat_pass or [0]):.0f}")
    if not gaps:
        out.append("NO OUTAGE detected — reads served continuously through the event.")
    for idx, g in enumerate(gaps, 1):
        downtime = (g["first_ok_after"] - g["last_ok_before"]) if g["first_ok_after"] else None
        mttr = (g["recovery"] - g["first_fail"]) if g["recovery"] else None
        dt_s = f"{downtime:.2f}s" if downtime is not None else "no recovery in log"
        mttr_s = f"{mttr:.2f}s" if mttr is not None else "not recovered in log"
        out.append(f"outage#{idx}: failed_probes={g['n_failed']}  client_downtime={dt_s}")
        out.append(f"          MTTR(to {recover_n} consecutive PASS) = {mttr_s}")
    return "\n".join(out)

def chart(rows, path):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("(matplotlib not installed — skipping chart; paste the CSV into Sheets instead)")
        return
    t0 = rows[0]["epoch"]
    xs = [r["epoch"] - t0 for r in rows]
    ys = [r["lat"] if r["status"] == "PASS" else None for r in rows]
    fx = [r["epoch"] - t0 for r in rows if r["status"] == "FAIL"]
    plt.figure(figsize=(11, 4))
    plt.plot(xs, ys, lw=0.9, label="latency (ms), PASS")
    for x in fx:
        plt.axvline(x, color="red", alpha=0.15, lw=1)
    plt.xlabel("seconds since probe start"); plt.ylabel("latency ms")
    plt.title("Query latency over time (red = failed probe)")
    plt.legend(); plt.tight_layout(); plt.savefig(path, dpi=120)
    print(f"chart -> {path}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--recover-n", type=int, default=10)
    ap.add_argument("--chart", default=None)
    a = ap.parse_args()
    rows = load(a.csv)
    print(analyze(rows, a.recover_n))
    if a.chart:
        chart(rows, a.chart)
