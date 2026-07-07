#!/usr/bin/env bash
# Runs ON tg-m1 (a sudo-capable user). Downloads + extracts the TigerGraph 4.1.4 offline installer
# and reveals its real config format so we can generate a correct install_conf.json.
# Usage:  TG_URL="https://.../tigergraph-4.1.4-offline.tar.gz" bash node-install.sh
set -euo pipefail
: "${TG_URL:?set TG_URL to the 4.1.4 offline tarball download link from your license email}"

cd ~
echo "== [1/3] downloading tarball =="
curl -fL --retry 3 "$TG_URL" -o ~/tg.tar.gz
ls -lh ~/tg.tar.gz
file ~/tg.tar.gz || true

echo "== [2/3] extracting =="
rm -rf ~/tg-offline && mkdir -p ~/tg-offline
tar -xzf ~/tg.tar.gz -C ~/tg-offline
DIR=$(find ~/tg-offline -maxdepth 3 -type f -name 'install.sh' -printf '%h\n' 2>/dev/null | head -1)
echo "installer dir: ${DIR:-NOT FOUND}"

echo "== [3/3] installer contents + any bundled config template =="
[ -n "${DIR:-}" ] && ls -la "$DIR"
echo "--- bundled *.json / install_conf templates ---"
find ~/tg-offline -maxdepth 3 \( -iname '*.json' -o -iname '*install_conf*' \) 2>/dev/null | head
echo "--- install.sh -h (first 60 lines) ---"
[ -n "${DIR:-}" ] && sudo "$DIR/install.sh" -h 2>&1 | head -60 || true
echo
echo "DONE. Installer staged at: ${DIR:-<none>}"
echo "Next: generate install_conf.json (NodeList=10.128.0.2/3/4, ReplicationFactor=3, License=<key>) then: sudo \$DIR/install.sh -n -j install_conf.json"
