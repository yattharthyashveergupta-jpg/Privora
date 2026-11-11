#!/usr/bin/env bash
# ==============================================================================
# Privora On-Premise Enterprise Startup Script (Linux / macOS)
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================================="
echo "  Privora On-Premise Enterprise — Starting Services       "
echo "=========================================================="

if [ ! -f .env.server ]; then
    if [ -f .env.server.example ]; then
        echo "[!] .env.server not found. Initializing from .env.server.example..."
        cp .env.server.example .env.server
        echo "[*] Created .env.server. Please review secrets before public deployment."
    else
        echo "[ERROR] Missing .env.server configuration file."
        exit 1
    fi
fi

# Check Docker prerequisite
if ! command -v docker &> /dev/null; then
    echo "[-] ERROR: Docker is not installed or not in PATH."
    echo "    Please install Docker Engine (24.0+) and Docker Compose (v2+)."
    exit 1
fi

if ! docker compose version &> /dev/null; then
    echo "[-] ERROR: Docker Compose plugin not found."
    exit 1
fi

echo "[1/3] Pulling / building enterprise stack..."
docker compose build privora-app

echo "[2/3] Launching air-gapped stack (Ollama + App + Nginx)..."
docker compose up -d

echo "[3/3] Verifying container health..."
sleep 5
docker compose ps

echo "=========================================================="
echo "  Privora Enterprise is active!                           "
echo "  Web Interface: http://localhost (or configured domain)  "
echo "  Direct Backend: http://localhost:8000/api/health        "
echo "=========================================================="
