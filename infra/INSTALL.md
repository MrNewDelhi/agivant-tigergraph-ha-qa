# TigerGraph 4.1.4 HA install runbook (3-node, replication factor 2)

All commands assume Ubuntu 22.04 VMs created by `setup-gcp.sh`. Do the install **from m1** —
it pushes to m2/m3 over SSH.

## 0. Get a license (do this first, ~2 min)
Request the free **Enterprise Free** license: https://info.tigergraph.com/enterprise-free
You'll get a license key string. Keep it handy.

## 1. On EACH node: prerequisites + passwordless SSH
```bash
# Copy prereqs.sh to each node and run it
gcloud compute scp infra/prereqs.sh tg-m1:~ --zone=us-central1-a
gcloud compute scp infra/prereqs.sh tg-m2:~ --zone=us-central1-a
gcloud compute scp infra/prereqs.sh tg-m3:~ --zone=us-central1-a
# then on each: `bash ~/prereqs.sh`
```

The installer needs a single OS user (default `tigergraph`) that can SSH **passwordlessly to every
node including itself**. Easiest path: create the user + a shared key on m1 and distribute it.
```bash
# --- run on m1 ---
sudo useradd -m -s /bin/bash tigergraph && echo 'tigergraph:tigergraph' | sudo chpasswd
sudo -u tigergraph ssh-keygen -t rsa -N '' -f /home/tigergraph/.ssh/id_rsa
sudo cat /home/tigergraph/.ssh/id_rsa.pub   # copy this public key
```
Create the same `tigergraph` user on m2 and m3, and append that public key to
`/home/tigergraph/.ssh/authorized_keys` on **all three** (including m1 itself).
Verify from m1: `sudo -u tigergraph ssh tigergraph@<m2-internal-ip> hostname` (must succeed without a password).

> Tip: TigerGraph's installer can also set up SSH keys for you if you give it the password for the
> `tigergraph` user on every node — the interactive installer will offer this.

## 2. Download + extract the installer (on m1)
```bash
# Grab the 4.1.4 offline tarball from dl.tigergraph.com (link comes with your license email,
# or from the downloads page). Then:
tar -xzf tigergraph-4.1.4-offline.tar.gz
cd tigergraph-4.1.4-offline
```

## 3. Install (pick ONE)

**A) Interactive (most reliable — recommended for a one-off):**
```bash
sudo ./install.sh
# Answer the prompts:
#   - License key            -> your Enterprise Free key
#   - Install user           -> tigergraph
#   - Node list / IPs        -> the 3 INTERNAL IPs (m1,m2,m3)
#   - Replication factor     -> 2   (minimum for HA)
#   - Data/log/app dirs      -> accept defaults
```

**B) Non-interactive:** edit `infra/install_conf.reference.json` (real IPs + license), then:
```bash
sudo ./install.sh -n -j /path/to/install_conf.json
```

## 4. Verify the cluster is healthy HA
```bash
su - tigergraph          # switch to the tigergraph user; gadmin is on its PATH
gadmin status -v         # every service on every node should be RUNNING (Online)
gadmin status license    # license valid
gssh                     # shows topology: which services run on which node
grun all 'date'          # confirm clock skew < 2s across nodes
```
Screenshot `gadmin status -v` → save to `results/00_baseline_status.txt`.

## Ports you'll use
| Port | Service | Used for |
|---|---|---|
| 9000 | RESTPP | query REST endpoint (the probe hits this) |
| 14240 | GUI / Nginx / `/api/ping` | GraphStudio, liveness ping |
| 22 | SSH | admin |

## Auth note (RESTPP tokens)
TigerGraph 4.x may require a token on `/query/...`. Two options for testing:
- **Simplest for a lab:** create a secret + token and pass it to the probe (`--token`):
  ```bash
  gsql -g finGraph "CREATE SECRET s1"          # prints a secret alias/value
  curl -s -X POST 'http://localhost:9000/requesttoken' \
       -d '{"secret":"<SECRET>","lifetime":"1000000"}'   # returns a token
  ```
- Or run queries through `gsql` interpreted mode where no REST token is needed (see Case 2).
The `/api/ping` liveness endpoint on 14240 needs **no** auth.
