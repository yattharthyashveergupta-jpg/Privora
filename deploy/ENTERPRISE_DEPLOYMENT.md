# Privora Enterprise On-Premise Deployment Guide

This guide details the steps required to deploy **Privora — Private Document Intelligence** in a secure, air-gapped or corporate intranet server environment.

---

## 1. Architecture Overview

Privora is architected as a self-contained, air-gapped system that requires no outbound external internet access:

```
[ Client Browsers / Intranet ]
               │
               ▼  (HTTPS Port 443)
┌──────────────────────────────────────────────┐
│  Nginx Reverse Proxy & TLS Termination       │
│  - Strict-Transport-Security (HSTS)          │
│  - CSP & Security Headers                    │
│  - IP Rate Limiting (5 req/min on auth)     │
└──────────────────────┬───────────────────────┘
                       │ (HTTP Port 8000 internal network)
┌──────────────────────▼───────────────────────┐
│  Privora Application Server (Docker)         │
│  - FastAPI Unified API                       │
│  - Next.js Static Export SPA (Port 8000)     │
│  - SQLite 3 (WAL Mode, Schema v4)            │
│  - RBAC Multi-Tenant Workspaces              │
│  - Tamper-Evident Audit Logging              │
└──────────────────────┬───────────────────────┘
                       │ (HTTP Port 11434 internal network)
┌──────────────────────▼───────────────────────┐
│  Ollama Inference Engine (Docker)            │
│  - Local Models (e.g. Qwen 2.5 7B, Llama 3.1)│
│  - GPU Acceleration (NVIDIA CUDA) or CPU     │
└──────────────────────────────────────────────┘
```

---

## 2. Hardware and Sizing Requirements

| Resource | Minimum (Evaluation) | Recommended (Production: 10–50 Users) | Enterprise High-Throughput |
| :--- | :--- | :--- | :--- |
| **CPU** | 8 Cores (x86_64 or ARM64) | 16 Cores | 32+ Cores |
| **RAM** | 16 GB | 32 GB | 64 GB+ |
| **GPU** | None (CPU inference) | 1x NVIDIA RTX 4090 / A4000 (16GB+ VRAM)| 1–2x NVIDIA A100 / L40S (24–80GB VRAM) |
| **Storage** | 100 GB SSD | 500 GB NVMe SSD | 1 TB+ Enterprise NVMe (RAID 1/10) |
| **OS** | Ubuntu 22.04 LTS / RHEL 9 | Ubuntu 22.04 / 24.04 LTS | Ubuntu LTS / Debian 12 / Rocky Linux 9 |

---

## 3. Prerequisites

1. **Docker Engine**: Version 24.0 or newer.
2. **Docker Compose**: Version 2.20 or newer.
3. *(Optional for GPU acceleration)* **NVIDIA Container Toolkit**:
   ```bash
   sudo apt-get install -y nvidia-container-toolkit
   sudo nvidia-ctk runtime configure --runtime=docker
   sudo systemctl restart docker
   ```

---

## 4. Deployment Steps

### Step 1: Clone Repository and Navigate to Deploy Directory
```bash
cd /opt/privora
```

### Step 2: Configure Environment Variables
Copy the production template:
```bash
cp deploy/.env.server.example deploy/.env.server
```
Edit `deploy/.env.server`:
- Generate a 64-character secret key:
  ```bash
  python3 -c "import secrets; print(secrets.token_hex(32))"
  ```
- Set `PRIVORA_SECRET_KEY` to the generated string.
- Set `CORS_ORIGINS` to your internal domain (e.g., `https://privora.corp.internal`).
- Ensure `DEPLOYMENT_MODE=server` and `COOKIE_SECURE=true`.

### Step 3: Install TLS Certificates
Mount your enterprise CA-signed certificates into `deploy/certs/`:
```bash
mkdir -p deploy/certs
cp /path/to/corporate_cert.crt deploy/certs/privora.crt
cp /path/to/corporate_key.key deploy/certs/privora.key
chmod 600 deploy/certs/privora.key
```
*(For testing environments, a self-signed certificate can be generated using OpenSSL:)*
```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout deploy/certs/privora.key \
  -out deploy/certs/privora.crt \
  -subj "/CN=privora.internal"
```

### Step 4: Build and Launch Containers
```bash
cd deploy
docker compose build
docker compose up -d
```

### Step 5: Pull AI Models into Ollama
Pull your organization's selected model into the isolated Ollama container:
```bash
# Recommended default for balanced speed and reasoning
docker compose exec ollama ollama pull qwen2.5:7b

# High-accuracy alternative
docker compose exec ollama ollama pull llama3.1:8b
```

### Step 6: Verify Deployment Status
Inspect service health:
```bash
docker compose ps
curl -k https://127.0.0.1/api/health
```
Expected output:
```json
{"status":"ok","version":"1.0.0","mode":"server"}
```

---

## 5. Air-Gapped Offline Model Distribution

If your deployment server has zero internet access:

1. **On an internet-connected staging machine**, pull and save the model:
   ```bash
   ollama pull qwen2.5:7b
   # Tar the Ollama models directory
   tar -czf qwen2.5_models.tar.gz -C ~/.ollama/models .
   ```
2. **Transfer the archive** via approved secure media to the production server.
3. **Extract into the Docker volume**:
   ```bash
   docker run --rm -v privora_ollama_models:/target -v $(pwd):/source alpine \
     tar -xzf /source/qwen2.5_models.tar.gz -C /target
   ```
4. Restart the Ollama service:
   ```bash
   docker compose restart ollama
   ```

---

## 6. Automated Disaster Recovery & Backups

Privora includes an online SQLite snapshot engine that operates while the database is actively writing in WAL mode.

### Setting Up Daily Automated Backups via Cron
Add a root cron job (`crontab -e`):
```cron
# Run daily backup at 02:00 AM UTC
0 2 * * * docker compose -f /opt/privora/deploy/docker-compose.yml exec -T privora-app python -m scripts.backup_restore backup /app/data/backups >> /var/log/privora_backup.log 2>&1
```

### Restoring from Backup
```bash
docker compose -f /opt/privora/deploy/docker-compose.yml exec -T privora-app \
  python -m scripts.backup_restore restore /app/data/backups/privora_backup_YYYYMMDD_HHMMSS.zip
```
The restoration engine:
1. Validates the SHA-256 integrity manifest.
2. Checks foreign keys and SQLite schema version.
3. Performs an atomic swap with automated rollback on failure.

---

## 7. Security Hardening Checklist

- [x] **No Outbound Network Calls**: Local document extraction and LLM inference run entirely on-premise.
- [x] **Strict Transport Security**: Nginx enforces HSTS (`max-age=63072000`).
- [x] **HTTP-Only, Secure, SameSite Cookies**: Auth session cookies cannot be read by JavaScript.
- [x] **PBKDF2 Password Hashing**: Passwords stored with cryptographic salt and 600,000 iterations.
- [x] **Tamper-Evident Audit Trail**: Every document upload, deletion, workspace modification, and auth event is recorded in `audit_events`.
- [x] **Prompt Injection Delimitation**: Extracted evidence passages are fenced in `### BEGIN UNTRUSTED EVIDENCE PASSAGES ###` blocks.
- [x] **Non-Root Execution**: Privora backend container runs as dedicated user `privora` (UID 1000).
