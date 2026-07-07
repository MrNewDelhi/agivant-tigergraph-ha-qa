#!/usr/bin/env python3
"""External availability probe. Hammer one endpoint on a fixed interval; log every result.

Run this from a 4th box (your laptop) pointed at the cluster THROUGH a node you will NOT kill
(or a load balancer). Curling the node you kill just measures "I unplugged the thing I called".

  python3 probe.py --url "http://NODE_IP:9000/query/finGraph/kHopTransfers?acc=acc0&k=3" \
                   --interval 0.2 --out results/case1_probe.csv [--token <RESTPP_TOKEN>]

CSV columns: epoch, iso, status(PASS/FAIL), http_code, latency_ms, error
Feed the CSV to analyze.py to get downtime + MTTR.
"""
import argparse, csv, sys, time
from datetime import datetime, timezone
try:
    import requests
except ImportError:
    sys.exit("pip install -r harness/requirements.txt  (need `requests`)")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--interval", type=float, default=0.2, help="seconds between probes (0.2 = 5/s)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--timeout", type=float, default=5.0)
    ap.add_argument("--token", default=None, help="RESTPP bearer token if auth is enabled")
    ap.add_argument("--method", default="GET", choices=["GET", "POST"])
    ap.add_argument("--duration", type=float, default=0, help="stop after N seconds (0 = run until Ctrl-C)")
    args = ap.parse_args()

    headers = {"Authorization": f"Bearer {args.token}"} if args.token else {}
    print(f"Probing {args.url} every {args.interval}s -> {args.out}  (Ctrl-C to stop)")
    n = ok = 0
    start = time.time()
    with open(args.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["epoch", "iso", "status", "http_code", "latency_ms", "error"])
        try:
            while True:
                if args.duration and (time.time() - start) >= args.duration:
                    print(f"\nDuration {args.duration}s reached. {ok}/{n} passed. Wrote {args.out}")
                    break
                t0 = time.time()
                code, err = -1, ""
                try:
                    r = requests.request(args.method, args.url, headers=headers, timeout=args.timeout)
                    code = r.status_code
                    # TigerGraph returns 200 with {"error":true,...} on some app errors — treat as FAIL
                    body_ok = True
                    try:
                        j = r.json()
                        if isinstance(j, dict) and j.get("error") in (True, "true"):
                            body_ok = False
                            err = str(j.get("message", ""))[:180]
                    except Exception:
                        pass
                    status = "PASS" if (code == 200 and body_ok) else "FAIL"
                    if status == "FAIL" and not err:
                        err = (r.text or "")[:180]
                except Exception as e:
                    status, err = "FAIL", f"{type(e).__name__}: {e}"[:180]
                lat = round((time.time() - t0) * 1000, 1)
                now = datetime.now(timezone.utc)
                w.writerow([f"{t0:.3f}", now.isoformat(), status, code, lat, err])
                f.flush()
                n += 1; ok += (status == "PASS")
                # live one-liner so you can watch the outage happen
                print(f"\r{now.strftime('%H:%M:%S')} {status} code={code} {lat}ms  "
                      f"[{ok}/{n} ok]   {err[:40]:40}", end="", flush=True)
                dt = args.interval - (time.time() - t0)
                if dt > 0:
                    time.sleep(dt)
        except KeyboardInterrupt:
            print(f"\nStopped. {ok}/{n} passed. Wrote {args.out}")

if __name__ == "__main__":
    main()
