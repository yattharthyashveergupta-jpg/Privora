# Privora — Complete Installation & Setup Guide

This guide covers step-by-step installation instructions for both **Privora Desktop (Windows)** and **Privora Enterprise On-Premise (Linux / Docker)**.

---

## 1. System Requirements

### Hardware Requirements
| Component | Minimum | Recommended (Local LLM) |
| :--- | :--- | :--- |
| **CPU** | x86_64 4 Cores | x86_64 8 Cores (AVX2 supported) |
| **RAM** | 8 GB System RAM | 16 GB - 32 GB RAM |
| **GPU** | Integrated Graphics (CPU inference) | NVIDIA RTX (6 GB+ VRAM with CUDA) |
| **Storage** | 2 GB free SSD space | 15 GB SSD (for models & vector store) |

### Operating System Support
- **Privora Desktop**: Windows 10 (Build 19041+) or Windows 11 64-bit.
- **Privora On-Premise**: Ubuntu 22.04/24.04 LTS, Debian 12, RHEL 9, Rocky Linux 9, or Windows Server 2022 with Docker.

---

## 2. Edition A: Privora Desktop Installation (Windows)

Privora Desktop installs as a standard Windows application that does not require administrative privileges, developer command prompts, or node/python runtimes on the host machine.

### Step 1: Run the Windows Setup Wizard
1. Navigate to the `release/desktop/` directory (or your download folder).
2. Double-click `Privora-Setup-1.1.0.exe`.
3. Follow the wizard steps:
   - Select installation directory (defaults to `%LOCALAPPDATA%\Programs\Privora`).
   - Choose whether to create a Desktop Shortcut and Start Menu folder.
   - Click **Install**.
4. Installation completes in approximately 15–30 seconds.

### Step 2: Verify Local Ollama Inference Engine
Privora utilizes local Ollama to ensure your documents never leave your machine:
1. If Ollama is not yet installed:
   ```powershell
   winget install Ollama.Ollama
   ```
   *(Or download the installer from https://ollama.com)*
2. Start Ollama:
   ```powershell
   ollama serve
   ```
3. Pull the recommended local language model:
   ```powershell
   ollama pull qwen2.5:7b
   ```
   *(Alternative lightweight model for 8 GB RAM machines: `ollama pull qwen2.5:3b` or `ollama pull llama3.2:3b`)*

### Step 3: Launch Privora
- Click the **Privora** shortcut on your Desktop or Start Menu.
- Privora launches a background Python backend engine and opens directly in a clean **Microsoft Edge App Mode** workstation window.
- The First-Run Onboarding Modal will automatically verify Ollama connectivity and guide your initial workspace configuration.

### Uninstallation
- To uninstall, go to **Windows Settings > Apps > Installed Apps** and select **Privora**, or run the uninstaller in the program directory.
- **Data Safety Guarantee**: The uninstaller removes binaries and shortcuts, but preserves your confidential database and documents stored in `%LOCALAPPDATA%\Privora\data`.

---

## 3. Edition B: Privora On-Premise Installation (Linux / Docker)

Privora On-Premise runs as a hardened multi-container architecture behind Nginx.

### Prerequisites
- Docker Engine 24.0+
- Docker Compose v2.20+

### Step 1: Extract Release Archive
```bash
tar -xzf privora-on-premise-1.1.0.tar.gz -C /opt/privora
# OR
unzip privora-on-premise-1.1.0.zip -d /opt/privora

cd /opt/privora
```

### Step 2: Configure Environment Variables
Copy the template configuration file:
```bash
cp deploy/.env.server.example deploy/.env.server
```
Edit `deploy/.env.server` to specify production security keys:
```env
DEPLOYMENT_MODE=server
JWT_SECRET_KEY=generate_with_openssl_rand_hex_32
CSRF_SECRET_KEY=generate_with_openssl_rand_hex_32
OLLAMA_BASE_URL=http://ollama:11434
ALLOWED_ORIGINS=https://privora.yourcompany.corp,http://localhost
COOKIE_SECURE=true
```

### Step 3: Start Services
Execute the automated startup script:
```bash
chmod +x deploy/start.sh deploy/stop.sh
./deploy/start.sh
```
Or directly with Docker Compose:
```bash
cd deploy
docker compose up -d
```

### Step 4: Download Model into Container
```bash
docker compose exec ollama ollama pull qwen2.5:7b
```

### Step 5: Verify Deployment
Run health diagnostics:
```bash
curl -f http://localhost:8000/api/health
```
Response:
```json
{"status":"ok","documents":0,"deployment_mode":"server"}
```

Access the web interface at `https://your-server-ip` or `http://localhost`.

### Step 6 (Optional): Install as Systemd Service
To ensure Privora starts automatically on server boot:
```bash
sudo cp deploy/privora.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now privora
```

---

## 4. Air-Gapped / Isolated Installation (No Internet)

For strictly offline enclaves with no external WAN connectivity:
1. On an internet-connected staging machine:
   ```bash
   docker pull privora/workbench:latest
   docker pull ollama/ollama:latest
   docker pull nginx:1.27-alpine
   docker save -o privora_images.tar privora/workbench:latest ollama/ollama:latest nginx:1.27-alpine
   ```
2. Pull the Ollama model on staging:
   ```bash
   ollama pull qwen2.5:7b
   tar -czf ollama_models.tar.gz -C ~/.ollama .
   ```
3. Transfer `privora_images.tar`, `ollama_models.tar.gz`, and the Privora release bundle to the air-gapped machine via certified physical media.
4. Load Docker images:
   ```bash
   docker load -i privora_images.tar
   ```
5. Extract models into the persistent Docker volume:
   ```bash
   docker volume create privora_ollama_models
   tar -xzf ollama_models.tar.gz -C /var/lib/docker/volumes/privora_ollama_models/_data/
   ```
6. Launch with `./deploy/start.sh`.
