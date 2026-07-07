#!/usr/bin/env bash
# Runs ON m1. Builds install_conf.json for the 3-node HA cluster (replication factor 2), injecting the license.
# Usage:  bash build_install_conf.sh <license_file> <output_path>
set -euo pipefail
LIC="$(tr -d '\n\r' < "$1")"
OUT="$2"
cat > "$OUT" <<EOF
{
  "BasicConfig": {
    "TigerGraph": {
      "Username": "tigergraph",
      "Password": "tigergraph",
      "SSHPort": 22,
      "PrivateKeyFile": "/home/tigergraph/.ssh/id_rsa",
      "PublicKeyFile": "/home/tigergraph/.ssh/id_rsa.pub"
    },
    "RootDir": {
      "AppRoot": "/home/tigergraph/tigergraph/app",
      "DataRoot": "/home/tigergraph/tigergraph/data",
      "LogRoot": "/home/tigergraph/tigergraph/log",
      "TempRoot": "/home/tigergraph/tigergraph/tmp"
    },
    "License": "${LIC}",
    "RegionAware": false,
    "NodeList": [
      "m1: 10.128.0.2",
      "m2: 10.128.0.3",
      "m3: 10.128.0.4"
    ]
  },
  "AdvancedConfig": {
    "ClusterConfig": {
      "LoginConfig": {
        "SudoUser": "tigergraph",
        "Method": "K",
        "P": "tigergraph",
        "K": "/home/tigergraph/.ssh/id_rsa"
      },
      "ReplicationFactor": 2
    }
  }
}
EOF
python3 -c "import json,sys; json.load(open('$OUT')); print('install_conf.json is valid JSON')" || { echo "INVALID JSON"; exit 1; }
echo "ReplicationFactor=2 (HA), NodeList=m1/m2/m3 (10.128.0.2-4)"