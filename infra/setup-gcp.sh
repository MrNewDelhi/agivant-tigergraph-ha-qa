#!/usr/bin/env bash
# Provision a 3-node TigerGraph HA cluster on GCP (paid account, quota confirmed).
# Topology: 3-node (replication factor 2). Nodes: e2-standard-4 (4 vCPU / 16 GB), Ubuntu 22.04, 50 GB SSD.
# Total = 12 vCPU  -> well inside the 32 global / 24 E2-regional quota. ~$38 for 3 days.
#
# Prereqs on your laptop: gcloud CLI installed + authenticated (`gcloud auth login`),
# and a free-trial project created. Set TG_PROJECT below (or export it).
set -euo pipefail

PROJECT="${TG_PROJECT:?set TG_PROJECT=your-project-id}"
REGION="${TG_REGION:-us-central1}"
ZONE="${TG_ZONE:-us-central1-a}"
MACHINE="${TG_MACHINE:-e2-standard-4}"     # 4 vCPU / 16 GB (paid account). Meets TigerGraph 4-core/8GB min with headroom.
DISK_GB="${TG_DISK_GB:-50}"
NODES=(tg-m1 tg-m2 tg-m3)

# The IP you'll drive the cluster from (your laptop) — locks external ports to just you.
MYIP="$(curl -s https://ifconfig.me || echo 0.0.0.0)"

echo "==> Project=$PROJECT Zone=$ZONE Machine=$MACHINE Disk=${DISK_GB}GB  yourIP=$MYIP"
gcloud config set project "$PROJECT"

# --- Create the 3 VMs -------------------------------------------------------
# The default VPC already ships `default-allow-internal` (all node<->node TCP/UDP on 10.x),
# so NO extra firewall is needed for the cluster to talk internally. SSD via --boot-disk-type=pd-ssd.
for n in "${NODES[@]}"; do
  gcloud compute instances create "$n" \
    --zone="$ZONE" \
    --machine-type="$MACHINE" \
    --image-family=ubuntu-2204-lts --image-project=ubuntu-os-cloud \
    --boot-disk-size="${DISK_GB}GB" --boot-disk-type=pd-ssd \
    --tags=tigergraph \
    --metadata=enable-oslogin=FALSE
done

# --- Firewall: expose RESTPP (9000) + GUI/GSQL (14240) to YOUR ip only ------
gcloud compute firewall-rules create tg-allow-ext \
  --network=default --direction=INGRESS --action=ALLOW \
  --rules=tcp:9000,tcp:14240 \
  --target-tags=tigergraph \
  --source-ranges="${MYIP}/32" || echo "(firewall rule may already exist)"

echo
echo "==> VMs created. Internal + external IPs:"
gcloud compute instances list --filter="name~'tg-m'" \
  --format="table(name,networkInterfaces[0].networkIP,networkInterfaces[0].accessConfigs[0].natIP,status)"

cat <<EOF

Next:
  1. SSH to m1:   gcloud compute ssh tg-m1 --zone=$ZONE
  2. Note the INTERNAL IPs above -> put them in infra/install_conf.reference.json
  3. Run infra/prereqs.sh on ALL three nodes (see infra/INSTALL.md)
  4. Install TigerGraph from m1 (it pushes to the others over SSH)

To STOP billing the compute (keeps disks, cheap) when not testing:
  gcloud compute instances stop ${NODES[*]} --zone=$ZONE
To DELETE everything when done:
  gcloud compute instances delete ${NODES[*]} --zone=$ZONE -q
  gcloud compute firewall-rules delete tg-allow-ext -q
EOF
