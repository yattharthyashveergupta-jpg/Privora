# Privora — Troubleshooting & Diagnostic Guide

This document outlines solutions for common operational, networking, and system issues encountered during Windows desktop or server deployment of Privora.

---

## 1. Port 8000 Conflict (Address Already in Use)

### Symptoms
- The desktop launcher opens to a connection error page.
- Log outputs: `[ERROR] [Errno 10048] error while attempting to bind on address ('127.0.0.1', 8000): only one usage of each socket address is normally permitted`.

### Resolution
1. **Identify the conflicting process**:
   ```powershell
   Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess
   ```
2. **Terminate the previous instance**:
   ```powershell
   Stop-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess -Force
   ```
3. **Alternative**: In server mode or custom configurations, specify a custom port in `.env`:
   ```bash
   PORT=8080
   ```

---

## 2. Local Ollama Connectivity & Model Loading Issues

### Symptom A: "Local Ollama is unavailable at http://127.0.0.1:11434"
- **Cause**: The Ollama service is not running or is blocked by local firewall policies.
- **Resolution**:
  1. Open a terminal and check if Ollama is running:
     ```powershell
     curl.exe http://127.0.0.1:11434/api/tags
     ```
  2. If not running, start Ollama:
     ```powershell
     ollama serve
     ```
  3. Verify Ollama is bound to localhost and listening on port 11434.

### Symptom B: "Model not found" or Timeout During Chat
- **Cause**: The configured model has not been downloaded or GPU VRAM is exhausted.
- **Resolution**:
  1. Verify installed models:
     ```powershell
     ollama list
     ```
  2. Pull the recommended model:
     ```powershell
     ollama pull qwen2.5:7b
     ```
  3. If your hardware has under 8GB RAM, use a smaller quantized model:
     ```powershell
     ollama pull qwen2.5:3b
     ```

---

## 3. Microsoft Edge Desktop Launcher Issues

### Symptom: Launcher script fails to open Edge App Mode
- **Cause**: Microsoft Edge is installed in a non-standard location or system group policy prohibits app mode.
- **Resolution**:
  The launcher checks the following standard paths in order:
  - `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`
  - `C:\Program Files\Microsoft\Edge\Application\msedge.exe`
  - `%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe`
  If Edge is missing or disabled, Privora falls back automatically to opening your default system browser (Chrome, Firefox, or Brave) at `http://127.0.0.1:8000`.

---

## 4. SQLite Database Locks & Concurrency Issues

### Symptoms
- Log message: `sqlite3.OperationalError: database is locked`.

### Root Cause & Prevention
Privora uses **Write-Ahead Logging (WAL)** mode (`PRAGMA journal_mode=WAL;`), which allows concurrent readers without blocking writers. Locks typically only occur if:
1. The database file is located on an unsupported network share (NFS or SMB) that doesn't support POSIX file locking.
2. A separate external process opened the file in exclusive mode.

### Resolution
1. Ensure `workbench.sqlite3` resides on a local SSD/NVMe drive, not a network drive.
2. Verify WAL mode is active:
   ```powershell
   sqlite3 "backend/data/workbench.sqlite3" "PRAGMA journal_mode;"
   ```
   Output should be: `wal`.
3. If WAL files (`workbench.sqlite3-wal`, `workbench.sqlite3-shm`) become orphaned after a hard system freeze:
   - Ensure the Privora process is completely stopped.
   - Run: `sqlite3 workbench.sqlite3 "PRAGMA wal_checkpoint(TRUNCATE);"`

---

## 5. Corrupted Backup Archive or Failed Restore

### Symptoms
- Restoring from backup reports: `Restoration failed: Manifest validation failed - checksum mismatch`.

### Resolution
Privora's backup engine enforces cryptographic verification:
1. Each backup archive contains `manifest.json` with SHA-256 hashes of all documents and the database.
2. If an archive was partially transferred or modified, Privora halts the restore operation immediately and triggers an automated rollback to keep existing data untouched.
3. Check the backup integrity manually using:
   ```powershell
   python scripts/backup_restore.py list backend/data/backups
   ```

---

## 6. Document Ingestion Failures

### Symptom A: "No readable text found in document" (Status 400)
- **Cause**: The uploaded file contains empty bytes, scanned images without OCR text, or exclusively whitespace.
- **Resolution**: Ensure PDFs have an embedded text layer (searchable text). For scanned paper documents, run OCR prior to ingestion.

### Symptom B: "File size exceeds 32 MB limit" (Status 413)
- **Cause**: Single file size exceeds the security threshold.
- **Resolution**: Split the file into smaller sections or adjust `MAX_FILE_SIZE_BYTES` in backend configuration.

---

## 7. Tabular Documents (Excel & CSV) Troubleshooting

### Symptom A: CSV Delimiter Not Detected Correctly
- **Cause**: Non-standard delimiter or mixed formatting in the first few lines.
- **Resolution**: Privora automatically sniffs delimiters (`,`, `;`, `\t`, `|`). If your CSV has unusual header lines, ensure the first non-empty line has consistent delimiters. Save files as standard UTF-8 CSV.

### Symptom B: Formulas In Excel Not Showing Values
- **Cause**: Workbook was created with an external library that did not calculate cached formula values.
- **Resolution**: Privora reads both cached formula values and raw values using `data_only=True`. Open the file in Excel or LibreOffice Calc and save once to populate cached formula results.

---

## 8. Enterprise Docker & Container Networking

### Symptom A: `privora-app` Cannot Reach Ollama Container
- **Error**: `503 Service Unavailable: Ollama is not reachable on http://ollama:11434`.
- **Resolution**:
  1. Verify the `ollama` container is running:
     ```bash
     docker compose ps
     ```
  2. Verify network connectivity on the internal bridge:
     ```bash
     docker compose exec privora-app curl -f http://ollama:11434/api/tags
     ```
  3. Check Ollama container logs:
     ```bash
     docker compose logs ollama
     ```

### Symptom B: Host Permission Denied on Linux Volume
- **Error**: `PermissionError: [Errno 13] Permission denied: '/app/data/workbench.sqlite3'`.
- **Resolution**:
  The application runs as non-root user `privora` (UID 1000). Ensure the mounted host volume directory has appropriate permissions:
  ```bash
  sudo chown -R 1000:1000 /var/lib/docker/volumes/privora_enterprise_data/_data
  ```

