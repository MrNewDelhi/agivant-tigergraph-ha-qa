#!/usr/bin/env python3
"""Render captured command/test output text files into terminal-style HTML pages,
so they can be screenshotted as images of the test execution.

Usage: python3 render_terminal.py   (writes /tmp/tg_render/*.html)
The HTML content is REAL captured output — only the presentation is a terminal image.
"""
import os, html

OUT = "/tmp/tg_render"
os.makedirs(OUT, exist_ok=True)

# (title, source file, subtitle)
JOBS = [
    ("Functional + Database correctness tests — 19/19 PASS",
     "results/func_db_test_output.txt", "harness/func_db_tests.py against RESTPP"),
    ("Messy / larger data tests — 12/12 PASS",
     "results/messy_data_test_output.txt", "harness/messy_data_tests.py"),
    ("Consistency after node failure + recovery",
     "results/consistency_after_recovery_output.txt", "harness/consistency_after_recovery.py"),
    ("Backup & restore — point-in-time revert verified",
     "results/backup_restore_output.txt", "gadmin backup create/restore"),
    ("GSQL leader failover — real GsqlHAHandler log lines",
     "results/logs/gsql_leader_failover.log", "/home/tigergraph/tigergraph/log/gsql/log.INFO*"),
    ("INSTALL QUERY blocked while degraded — pendingInstall",
     "results/logs/install_query_pendinginstall.log", "gsql ls + REST endpoint check"),
    ("gadmin status -v — 3-node HA cluster healthy",
     "results/logs/gadmin_status_healthy.log", "all services Online across m1/m2/m3"),
    ("Cluster topology (gssh) — data on m1,m2 (RF=2)",
     "results/logs/gssh_topology.log", "gpe.servers / gse.servers"),
]

TPL = """<!doctype html><html><head><meta charset="utf-8"><style>
  body{{margin:0;background:#0d1017;font-family:-apple-system,Segoe UI,sans-serif}}
  .win{{max-width:1100px;margin:24px auto;border-radius:10px;overflow:hidden;
    box-shadow:0 10px 40px rgba(0,0,0,.5);border:1px solid #232833}}
  .bar{{background:#1b1f27;padding:10px 14px;display:flex;align-items:center;gap:8px}}
  .dot{{width:12px;height:12px;border-radius:50%}}
  .r{{background:#ff5f56}}.y{{background:#ffbd2e}}.g{{background:#27c93f}}
  .ttl{{color:#c9d1d9;font-size:13px;margin-left:10px;font-weight:600}}
  .sub{{color:#7d8590;font-size:11px;margin-left:auto;font-family:ui-monospace,Menlo,monospace}}
  pre{{margin:0;background:#0d1017;color:#d1d5db;padding:18px 20px;font:13px/1.55 ui-monospace,Menlo,Consolas,monospace;
    white-space:pre-wrap;word-break:break-word}}
  .PASS{{color:#3fb950;font-weight:700}} .FAIL{{color:#f85149;font-weight:700}}
  .hd{{color:#58a6ff}} .banner{{color:#d29922}}
</style></head><body><div class="win">
  <div class="bar"><span class="dot r"></span><span class="dot y"></span><span class="dot g"></span>
    <span class="ttl">{title}</span><span class="sub">{sub}</span></div>
  <pre>{body}</pre></div></body></html>"""

def colorize(line):
    e = html.escape(line)
    e = e.replace("[PASS]", '<span class="PASS">[PASS]</span>')
    e = e.replace("[FAIL]", '<span class="FAIL">[FAIL]</span>')
    if e.strip().startswith("==") or e.strip().startswith("##") or e.strip().startswith("######"):
        e = f'<span class="banner">{e}</span>'
    elif e.strip().startswith("---") or e.strip().startswith("==="):
        e = f'<span class="hd">{e}</span>'
    return e

manifest = []
for i, (title, src, sub) in enumerate(JOBS, 1):
    if not os.path.exists(src):
        print(f"skip (missing): {src}"); continue
    raw = open(src, errors="replace").read().strip("\n").splitlines()
    # trim noise
    raw = [l for l in raw if "NotOpenSSL" not in l and "warnings.warn" not in l
           and "Permanently added" not in l]
    body = "\n".join(colorize(l) for l in raw[:120])
    fn = f"{OUT}/shot{i:02d}.html"
    open(fn, "w").write(TPL.format(title=html.escape(title), sub=html.escape(sub), body=body))
    manifest.append((fn, f"results/screenshots/test_{i:02d}_{os.path.basename(src).split('.')[0]}.png"))
    print(f"{fn}  ->  {manifest[-1][1]}")

open(f"{OUT}/manifest.txt","w").write("\n".join(f"{h}|{p}" for h,p in manifest))
print(f"\n{len(manifest)} pages written to {OUT}")
