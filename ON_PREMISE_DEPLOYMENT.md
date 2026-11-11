# Privora Enterprise — On-Premise Deployment Guide

This guide details enterprise production operations for deploying Privora within an internal corporate intranet, private cloud (AWS VPC, Azure VNet, GCP Private Cloud), or physically air-gapped data center.

---

## 1. Container Topology & Networks

The enterprise deployment consists of three decoupled microservices joined by an internal bridge network (`privora_internal`):

```
+---------------------------------------------------------------------------------------+
| Docker Host                                                                           |
|                                                                                       |
| [Nginx Ingress / Reverse Proxy]                                                       |
|  - Ports: 80, 443 (External Access)                                                   |
|  - TLS 1.3 Termination & HSTS                                                         |
|  - Static gzip compression                                                            |
|  - Security headers (CSP, X-Content-Type-Options, X-Frame-Options: DENY)               |
|                                │                                                      |
|                                ▼ (Internal proxy to port 8000)                        |
| [Privora App (FastAPI + Embedded Next.js SPA)]                                        |
|  - 4 Uvicorn worker cluster with proxy header trust                                   |
|  - Session token hashing (SHA-256)                                                    |
|  - Sliding-window rate limiter                                                         |
|  - Okapi BM25 ranking engine                                                          |
|  - Deterministic Tabular Analytics engine                                             |
|  - Volume: privora_enterprise_data -> /app/data (SQLite WAL + Raw files)               |
|                                │                                                      |
|                                ▼ (Internal REST to port 11434)                         |
| [Ollama Inference Server]                                                             |
|  - Zero external cloud communication                                                  |
|  - Model keep-alive (OLLAMA_KEEP_ALIVE=24h)                                            |
|  - Volume: privora_ollama_models -> /root/.ollama                                      |
+---------------------------------------------------------------------------------------+
```

---

## 2. Hardware Sizing & Capacity Planning

| Concurrent Users | Minimum RAM | Recommended CPU | Storage | GPU Recommendation |
| :---: | :---: | :---: | :---: | :---: |
| **1 – 5 Users** | 16 GB | 8 vCPUs | 100 GB SSD | Optional (CPU inference sufficient for Qwen2.5:7b) |
| **5 – 25 Users** | 32 GB | 16 vCPUs | 250 GB NVMe | 1x NVIDIA RTX 4090 / A4000 (16 GB+ VRAM) |
| **25 – 100 Users**| 64 GB | 32 vCPUs | 1 TB NVMe | 2x NVIDIA A5000 / A10G (24 GB VRAM each) |

---

## 3. GPU Acceleration (NVIDIA CUDA)

To enable GPU acceleration for Ollama, install the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html).

Update the `ollama` service definition in `deploy/docker-compose.yml`:
```yaml
  ollama:
    image: ollama/ollama:latest
    container_name: privora_ollama
    restart: unless-stopped
    volumes:
      - ollama_models:/root/.ollama
    environment:
      - OLLAMA_HOST=0.0.0.0:11434
      - OLLAMA_KEEP_ALIVE=24h
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
```
Restart the stack:
```bash
docker compose up -d
```
Verify GPU utilization inside the container:
```bash
docker compose exec ollama nvidia-smi
```

---

## 4. Reverse Proxy & SSL/TLS Termination

Place your corporate TLS certificates into `deploy/certs/`:
- Certificate chain: `deploy/certs/privora.crt`
- Private key: `deploy/certs/privora.key`

Ensure `deploy/nginx.conf` references the certificate paths:
```nginx
server {
    listen 443 ssl http2;
    server_name privora.yourcompany.corp;

    ssl_certificate /etc/nginx/certs/privora.crt;
    ssl_certificate_key /etc/nginx/certs/privora.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Security headers
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    location / {
        proxy_pass http://privora-app:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 5. Automated Backup Cron Job

To automate daily hot snapshots with zero downtime:
Add to the root crontab (`sudo crontab -e`):
```bash
# Daily Privora snapshot at 02:00 AM UTC with retention
0 2 * * * docker compose -f /opt/privora/deploy/docker-compose.yml exec -T privora-app python /app/scripts/backup_restore.py backup --output /app/data/backups/privora_backup_$(date +\%Y\%m\%d).zip
```
Each generated `.zip` includes SQLite WAL sync and SHA-256 checksums in `manifest.json`.

---

## 6. Monitoring & Health Endpoints

Privora provides automated health and observability probes:

1. **Liveness & Application Health**:
   ```http
   GET /api/health
   ```
   Returns HTTP 200 with document count and runtime mode.

2. **Ollama LLM Connectivity**:
   ```http
   GET /api/health/ollama
   ```
   Queries local Ollama tags. Returns HTTP 200 with installed model list or HTTP 503 if unreachable.

3. **Air-Gap Verification Probe**:
   ```http
   GET /api/audit/privacy
   ```
   Scans loopback bindings, outbound sockets, and external cloud API configuration.
