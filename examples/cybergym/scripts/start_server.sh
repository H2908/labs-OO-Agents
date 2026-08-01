#!/usr/bin/env bash
#
# Start the CyberGym submission server in the foreground. Run this in its own
# terminal and leave it running while you run tasks and validate PoCs.
#
# This is Docker-image server mode: the server pulls vulnerable/fixed images on
# demand. Do NOT add --binary_dir unless you separately downloaded CyberGym's
# binary-only server-data archive.
#
set -euo pipefail
source "$(dirname "$0")/config.sh"
activate_venv

if [ -z "${CYBERGYM_API_KEY:-}" ]; then
  echo "CYBERGYM_API_KEY is not set. Run scripts/setup.sh first (it generates one in .env)." >&2
  exit 1
fi
# The server reads CYBERGYM_API_KEY from the environment (CyberGym ServerConfig).
export CYBERGYM_API_KEY

PORT="${PORT:-8666}"
SERVER_DIR="$AGENT_REPO/runs/server"
mkdir -p "$SERVER_DIR"

echo "==> Starting CyberGym server on 0.0.0.0:$PORT (Ctrl-C to stop)"
cd "$CYBERGYM_REPO"
exec python3 -m cybergym.server \
  --host 0.0.0.0 \
  --port "$PORT" \
  --mask_map_path "$CYBERGYM_MASK_MAP" \
  --log_dir "$SERVER_DIR" \
  --db_path "$SERVER_DIR/poc.db"
