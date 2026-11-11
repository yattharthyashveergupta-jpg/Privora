# Privora Enterprise — Administrator & Operations Guide

Privora is an air-gapped, zero-cloud Document Intelligence Workbench designed for enterprise compliance, legal defense, financial research, and sensitive operations. This guide covers installation, deployment topology, security policies, multi-user workspace RBAC, disaster recovery, and operational monitoring.

---

## 1. System Architecture & Topology

Privora is deployed in two production topologies:

```
[Workstation Topology - Windows Desktop]
+-------------------------------------------------------------------+
| Host Machine (Air-Gapped / Enclave)                               |
|                                                                   |
|  [Microsoft Edge App Mode]                                        |
|         │                                                         |
|         │ HTTP (127.0.0.1:8000)                                   |
|         ▼                                                         |
|  [Privora Engine (Compiled PyInstaller / FastAPI / Uvicorn)]      |
|         │                                                         |
|         ├─► [Static Next.js SPA] (Embedded in Engine)             |
|         ├─► [SQLite WAL Database] (%LOCALAPPDATA%\Privora\data)   |
|         ├─► [Okapi BM25 Lexical Ranking Engine]                   |
|         ├─► [Deterministic Tabular Analytics Engine]             |
|         └─► [Local Ollama Inference Engine] (127.0.0.1:11434)     |
+-------------------------------------------------------------------+
```

```
[Enterprise Server Topology - On-Premise Docker Compose]
+-------------------------------------------------------------------+
| Linux Host / On-Premise VM (DMZ or Internal Intranet)              |
|                                                                   |
|  Clients (Web Browsers across Corporate LAN / VPN)                |
|         │                                                         |
|         │ HTTPS (Port 443 / 80)                                   |
|         ▼                                                         |
|  [Hardened Nginx Reverse Proxy]                                   |
|         │                                                         |
|         │ Internal Docker Bridge Network                          |
|         ▼                                                         |
|  [Privora App Container] (FastAPI 4-worker cluster)               |
|         │                                                         |
|         ├─► [Persistent Volume: /app/data] (SQLite WAL + Docs)    |
|         ├─► [Cross-Tenant RBAC & Workspace Isolation]             |
|         └─► [Internal HTTP: http://ollama:11434]                  |
|                   │                                               |
|                   ▼                                               |
|             [Ollama LLM Container] (Qwen 2.5:7b / Llama 3.1)      |
+-------------------------------------------------------------------+
```

---

## 2. Security Architecture & Privacy Guarantees

### 2.1 Zero Cloud Data Leakage (Strict Air-Gap)
- Privora has zero outbound network calls to OpenAI, Anthropic, Google, or any telemetry endpoints.
- Socket monitoring continuously inspects active system sockets:
  - Windows: Querying `Get-NetTCPConnection` for non-loopback connections.
  - Linux Container: Inspecting `/proc/net/tcp` to ensure 0 established WAN sockets.
- The built-in **Transparent Privacy Audit** endpoint (`GET /api/audit/privacy`) provides cryptographically verifiable evidence of local loopback operation and zero cloud credentials.

### 2.2 Enterprise Authentication & Hardening
In Server Mode (`DEPLOYMENT_MODE=server`):
- **Session Tokens**: Cryptographically hashed using SHA-256 before storage in SQLite. Raw session tokens are never stored.
- **Cookie Security**: `HttpOnly`, `SameSite=Lax` (or `Strict`), and configurable `Secure` flags for TLS connections.
- **CSRF Protection**: Double-submit cookie pattern with CSRF token verification on all state-mutating requests (`POST`, `PUT`, `DELETE`).
- **Timing Attack Mitigation**: Constant-time comparison for passwords and dummy password hash calculations on invalid usernames.
- **Multi-Worker Rate Limiting**: Persistent database-backed sliding-window rate limiter preventing brute-force attacks across clustered workers.

---

## 3. Workspace Isolation & RBAC

Privora provides multi-tenant organizational isolation with granular workspace permissions.

### Role Hierarchy
| Role | Upload & Query | Delete Documents | Create Workspaces | Manage Members | Delete Workspaces |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Owner** | Yes | Yes (Any in Org) | Yes | Yes (All Roles) | Yes |
| **Admin** | Yes | Yes (Any in Org) | Yes | Yes (Admins/Members) | Yes |
| **Member** | Yes | Yes (Own Docs Only) | Yes (In Scope) | No | No |
| **Viewer** | Read / Query Only | No | No | No | No |

### Multi-Tenant Isolation Guarantees
- Cross-tenant queries are blocked at the database layer using strict `organization_id` predicates.
- Cross-document contradiction detection (`POST /api/analysis/contradictions`) and pairwise comparisons (`POST /api/analysis/compare`) strictly enforce organization boundaries.

---

## 4. Document Processing & Ingestion Engine

Privora supports 5 document types with zero loss of coordinates:

1. **PDF (`.pdf`)**: PyMuPDF extraction preserving page numbers for exact page citations (`[1] Page 4`).
2. **Word (`.docx`)**: python-docx parser preserving heading hierarchy (H1, H2, H3) and markdown table formatting.
3. **Excel (`.xlsx`)**: openpyxl parser extracting multi-sheet workbooks, preserving headers across row chunks, and generating cell coordinates (`Sheet: Financials | Cells: B2:D14`).
4. **CSV (`.csv`)**: Automated delimiter sniffing (`,`, `;`, `\t`, `|`) with coordinate tracking (`CSV: Rows 2-10`).
5. **Plaintext (`.txt`, `.md`)**: Unicode normalization (NFC) with paragraph-preserving semantic chunking.

---

## 5. Deterministic Tabular Analytics

Unlike generic RAG platforms that ask an LLM to calculate numbers (leading to hallucinations), Privora features a native **Python Deterministic Calculation Engine**:
- Computes exact totals, averages (means), min, max, and record counts.
- Automatically generates deterministic summary passages for spreadsheets.
- Accessible via `GET /api/documents/{id}/analytics` and displayed under the **Numerical Intelligence** tab in the document drawer.

---

## 6. Backup, Restore & Disaster Recovery

Privora includes an online hot-backup engine that snapshots the SQLite database and document store without server downtime.

### Performing a Hot Backup
```bash
# In Linux container / On-premise VM
python scripts/backup_restore.py backup --output /var/backups/privora_backup.zip

# In Windows Server
python scripts\backup_restore.py backup --output C:\Backups\privora_backup.zip
```

### Verifying Backup Manifest & Integrity
Each backup archive includes an SHA-256 `manifest.json` certifying every document chunk and table checksum.
```bash
python scripts/backup_restore.py verify --archive /var/backups/privora_backup.zip
```

### Restoring from Backup with Safe Rollback
If a restore operation is interrupted or corrupt, Privora automatically rolls back to the pre-restore state.
```bash
python scripts/backup_restore.py restore --archive /var/backups/privora_backup.zip
```

---

## 7. Audit Logging & Compliance Monitoring

Privora logs all administrative actions into an append-only audit table:
- `DOC_UPLOAD`: Document ID, filename, workspace ID, user ID, IP address.
- `DOC_DELETE`: Deleted document coordinates, user ID, timestamp.
- `WORKSPACE_CREATE` / `WORKSPACE_MEMBER_ADD`: Access privilege modifications.
- Sensitive credentials, passwords, and raw session tokens are automatically redacted.

Query audit events via API:
```http
GET /api/audit/logs?limit=100
Authorization: Bearer <ADMIN_TOKEN>
```
