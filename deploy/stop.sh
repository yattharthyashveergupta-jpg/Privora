#!/usr/bin/env bash
# ==============================================================================
# Privora On-Premise Enterprise Shutdown Script (Linux / macOS)
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================================="
echo "  Privora On-Premise Enterprise — Stopping Services       "
echo "=========================================================="

docker compose down

echo "[OK] All Privora enterprise services stopped cleanly."
echo "     Persistent database and documents preserved in docker volumes."
