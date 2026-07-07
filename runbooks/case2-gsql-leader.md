# Case 2 — GSQL primary (leader) failure  `[core]`

**Why:** The GSQL server is a **leader/follower** subsystem — a different failover path from the
leaderless data plane. Worth isolating.

**Prediction:** standby promoted on heartbeat timeout (default ≈ 2000 ms × 4 ≈ 8 s); old primary
rejoins as follower; app server (GUI) unaffected.

## Identify the leader
The 4.1 docs don't expose a one-line "who's leader" command. Use:
```bash
gadmin status -v gsql        # shows which node's GSQL is serving
gadmin config get Controller.LeaderElectionHeartBeatIntervalMS   # default 2000
gadmin config get Controller.LeaderElectionHeartBeatMaxMiss      # default 4
```
Or open the Admin Portal (`http://<IP>:14240`) — it shows the primary. If unsure, kill GSQL on m1
and confirm from a survivor.

## Setup
```bash
# T1 (laptop) — loop a GSQL statement through ALL node IPs (client tries them in order)
while true; do
  ts=$(date +%s.%3N)
  out=$(gsql -ip <M1_IP>,<M2_IP>,<M3_IP> -g finGraph "SELECT count() FROM Account" 2>&1 | tail -1)
  echo "$ts | $out"
  sleep 1
done | tee results/case2_gsql.log

# Keep GraphStudio (http://<survivor_IP>:14240) open the whole time — watch if it drops.
```

## Inject
```bash
# ssh to the LEADER node, hard-kill GSQL:
sudo kill -9 $(pgrep -f 'gsql_server\|com.tigergraph.*gsql')   # adjust match to what pgrep shows
```

## Measure
- Time from kill → the `gsql` loop returns a correct count again (standby took over).
- Did the client auto-reconnect (multi-IP), or error until you retried?
- Did the **GUI stay up** throughout? (active-active on first 3 nodes → expected yes.)
- Compare observed failover to the documented ≈8 s heartbeat window.

**Bonus (shows you know the knob):** lower the heartbeat, restart, re-measure:
```bash
gadmin config set Controller.LeaderElectionHeartBeatMaxMiss 2
gadmin config apply -y && gadmin restart -y
```

**Pass:** new leader within ~the heartbeat window; multi-IP client reconnects; GUI never drops.
