# Privora — Release Notes
### Consolidated Production Release

Privora represents the consolidated commercial production release of the Private Document Intelligence Workbench. This release delivers two enterprise deployment editions, expanded document intelligence, deterministic spreadsheet analytics, cross-document contradiction auditing, and full air-gap compliance.

---

## 1. Highlights & New Features

### 1.1 Two Production Deployment Editions
- **Edition A: Privora Desktop (Windows)**:
  - Self-contained Windows installer: `release/desktop/Privora-Setup-1.1.0.exe` (67.5 MB, Inno Setup 6).
  - Native standalone launcher (`dist/Privora.exe`) with background engine supervisor.
  - Precompiled PyInstaller backend engine (`dist/privora-engine/`) embedding the Next.js static production application.
  - Native Microsoft Edge App Mode integration for a zero-distraction desktop workstation window.
  - Installs to `%LOCALAPPDATA%\Programs\Privora` without requiring administrator privileges.
- **Edition B: Privora On-Premise (Docker & Linux)**:
  - Hardened multi-container architecture (`deploy/docker-compose.yml`) containing Privora App (4 Uvicorn workers), local Ollama inference, and Nginx reverse proxy with TLS termination.
  - Linux Systemd service unit (`deploy/privora.service`) for automated OS service management.
  - Automated startup and shutdown scripts for Linux (`deploy/start.sh`, `deploy/stop.sh`) and Windows Server (`deploy/start.ps1`, `deploy/stop.ps1`).
  - Complete packaged deployment bundle: `release/on-premise/privora-on-premise-1.1.0.zip`.

### 1.2 Deterministic Tabular Intelligence & Spreadsheet Analytics
- Native Python arithmetic calculation engine (`app/tabular_analytics.py`) that computes exact column sums, arithmetic means (averages), minimums, maximums, and record counts.
- **Traceable Coordinates**: Every numerical calculation displays exact source spreadsheet cell coordinates (e.g., `B2:B25` or `Rows 2-25`).
- **No LLM Math Hallucinations**: Numbers are computed deterministically before retrieval rather than estimated by a language model.
- Dedicated **Numerical Intelligence** tab in the document detail drawer for immediate spreadsheet inspection.

### 1.3 Full CSV Format Support
- Ingests CSV files alongside PDF, DOCX, XLSX, and TXT.
- Automated delimiter sniffing supporting comma (`,`), semicolon (`;`), tab (`\t`), and pipe (`|`).
- Automatic character encoding detection (`utf-8-sig`, `utf-8`, `latin-1`).
- Repeated column headers on chunked row windows with coordinate citations (`CSV: Rows 2-10`).

### 1.4 Cross-Document Contradiction Auditing
- Automated contradiction detection engine (`app/cross_document.py`) that extracts comparative entities across different documents (e.g., payment terms, liability caps, delivery milestones).
- Severity classification: `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`.
- **Pairwise Comparison**: Side-by-side comparative inspection between any two documents to highlight conflicting values.
- Multi-tenant isolation: Comparisons strictly enforce organization boundaries.

### 1.5 Transparent Privacy & Air-Gap Verification
- Real-time network socket inspection:
  - Windows: Automated `Get-NetTCPConnection` socket audit.
  - Linux Containers: Direct `/proc/net/tcp` socket inspection.
- Hard verification of 0 outbound WAN sockets, loopback model binding (`127.0.0.1` / internal container), and 0 cloud credentials (OpenAI, Anthropic disabled).
- Clear UI distinction between hard cryptographic verifications and informational diagnostics.

### 1.6 Multi-Tenant Workspace RBAC & Enterprise Security
- Strict workspace role hierarchy: `Owner`, `Admin`, `Member`, `Viewer`.
- Administrative document management across organization workspaces.
- Persistent database-backed sliding-window rate limiter.
- Session tokens hashed with SHA-256 before persistence.
- CSRF double-submit protection and constant-time password verification.

---

## 2. Verification & Test Metrics

| Suite | Status | Results | Notes |
| :--- | :---: | :---: | :--- |
| **Backend Pytest Suite** | **PASSED** | 97 Passed / 0 Failed / 0 Skipped | Full coverage across 12 test modules |
| **TypeScript Typecheck** | **PASSED** | 0 Errors | `npx tsc --noEmit` exited cleanly |
| **Frontend Production Build** | **PASSED** | Succeeded | Next.js 16.4.1 static export to `out/` |
| **Release Protocol Verification** | **PASSED** | 10/10 Checks Passed | `verify_all_capabilities.py` |
| **Windows Installer Build** | **PASSED** | Validated | `Privora-Setup-1.1.0.exe` (SHA-256 verified) |

---

## 3. Upgrading & Migration

- **Database Preservation**: Existing SQLite databases (`backend/data/workbench.sqlite3`) and user records are 100% preserved.
- Automatic schema migration adds required indexes and workspace associations upon startup.
- Master safety backups are preserved:
  - Database: `backend/data/workbench.sqlite3.master_bak`
  - Installer: `dist-installer/Privora-Setup-1.1.0.exe.master_bak`
