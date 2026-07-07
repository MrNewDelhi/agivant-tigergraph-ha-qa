#!/usr/bin/env bash
# Run on EVERY node (tg-m1, tg-m2, tg-m3) before installing TigerGraph 4.1.4.
# Installs the packages the installer expects + enables NTP (clock skew > 2s breaks schema changes).
set -euo pipefail

echo "==> Installing prerequisite packages"
sudo apt-get update -y
# NOTE: TigerGraph's installer precheck specifically requires the `ntp` package (ntpd/ntpq),
# NOT chrony or systemd-timesyncd. Installing chrony makes the clock sync work but the precheck
# still fails with "Missing one or more tools: ntp". So install `ntp` explicitly.
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
  curl tar netcat-openbsd net-tools iproute2 cron sshpass \
  openssh-server openssh-client util-linux ntp

echo "==> Enabling time sync (ntp) — TigerGraph requires clock skew < 2s across nodes"
sudo systemctl enable --now ntp || sudo systemctl enable --now ntpd || true
timedatectl status | grep -i 'synchronized' || true

echo "==> Raising open-file / process limits (TigerGraph recommends high ulimits)"
sudo bash -c 'cat >/etc/security/limits.d/99-tigergraph.conf' <<'LIM'
*   soft   nofile   1000000
*   hard   nofile   1000000
*   soft   nproc    100000
*   hard   nproc    100000
LIM

echo "==> Disk / memory sanity"
df -h /
free -g
echo "==> Prereqs done on $(hostname). Verify clock across nodes with: grun all 'date' (after install), or 'date' on each now."
