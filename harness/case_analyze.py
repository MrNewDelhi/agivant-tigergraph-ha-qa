#!/usr/bin/env python3
"""Analyze a case_runner CSV (epoch,status,http_code,latency_ms) with inject/recover markers.

Usage: case_analyze.py <csv> <T0_inject_epoch> <T1_recover_epoch> [recover_n]
Reports: availability, latency percentiles, client-observed downtime, MTTR (to N consecutive PASS),
and the failure window relative to the injection instant.
"""
import csv, sys

def main():
    path = sys.argv[1]
    T0 = float(sys.argv[2]) if len(sys.argv) > 2 else None
    T1 = float(sys.argv[3]) if len(sys.argv) > 3 else None
    RN = int(sys.argv[4]) if len(sys.argv) > 4 else 5
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            try:
                rows.append({"t": float(r["epoch"]), "st": r["status"],
                             "lat": float(r["latency_ms"] or 0)})
            except ValueError:
                pass
    if not rows:
        print("empty csv"); return
    rows.sort(key=lambda x: x["t"])
    P = [r for r in rows if r["st"] == "PASS"]
    F = [r for r in rows if r["st"] == "FAIL"]
    lat = sorted(r["lat"] for r in P)
    pct = lambda q: lat[min(len(lat)-1, int(q/100*len(lat)))] if lat else 0
    dur = rows[-1]["t"] - rows[0]["t"]
    print(f"probes={len(rows)}  pass={len(P)}  fail={len(F)}  "
          f"avail={100*len(P)/len(rows):.2f}%  window={dur:.1f}s  rate={len(rows)/dur:.1f}/s")
    print(f"latency(PASS ms): p50={pct(50):.0f} p90={pct(90):.0f} p99={pct(99):.0f} max={max(lat or [0]):.0f}")

    # find outage gaps
    gaps, i = [], 0
    while i < len(rows):
        if rows[i]["st"] == "FAIL":
            j = i
            while j < len(rows) and rows[j]["st"] == "FAIL":
                j += 1
            last_ok = rows[i-1]["t"] if i > 0 else rows[i]["t"]
            first_ok_after = rows[j]["t"] if j < len(rows) else None
            # recovery = first of RN consecutive PASS at/after j
            rec = None; k = j
            while k + RN <= len(rows):
                if all(rows[k+m]["st"] == "PASS" for m in range(RN)):
                    rec = rows[k]["t"]; break
                k += 1
            gaps.append((rows[i]["t"], last_ok, first_ok_after, rec, j-i))
            i = j
        else:
            i += 1
    if not gaps:
        print("NO OUTAGE — reads served continuously through the failure.")
    for n,(ff,lo,fo,rec,cnt) in enumerate(gaps,1):
        dt = (fo-lo) if fo else None
        mttr = (rec-ff) if rec else None
        print(f"outage#{n}: failed_probes={cnt}  "
              f"client_downtime={dt:.2f}s" if dt is not None else f"outage#{n}: no recovery")
        if T0: print(f"          first_fail = T0 + {ff-T0:.2f}s")
        print(f"          MTTR(to {RN} consec PASS) = " + (f"{mttr:.2f}s" if mttr else "n/a"))
    if T0 and T1: print(f"markers: inject→recover span = {T1-T0:.1f}s")

if __name__ == "__main__":
    main()
