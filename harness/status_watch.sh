#!/usr/bin/env bash
# Server-side witness — run ON a surviving node as the tigergraph user during a test.
# Timestamps every gadmin status transition so you can line up "service went DOWN / came back
# RUNNING" against the client-observed downtime from the probe.
# Usage:  ./status_watch.sh > results/case1_status.log
echo "# epoch | gadmin status -v (gpe/gsql/restpp) one-line"
while true; do
  echo "$(date +%s.%3N) | $(gadmin status -v gpe gsql restpp 2>/dev/null | tr '\n' '|')"
  sleep 1
done
