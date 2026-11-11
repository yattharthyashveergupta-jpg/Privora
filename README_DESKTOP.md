# Privora — Private Document Intelligence (Windows Desktop Edition)

Privora Desktop delivers on-premise private document intelligence in a native, chromeless Windows application experience without requiring VS Code, Next.js development servers, or open terminal windows.

---

## 1. Architectural Highlights

Privora Desktop implements a **Single-Process Localhost Architecture**:

```
+---------------------------------------------------------------+
|                      Microsoft Edge                           |
|             (Native App Mode / Chromeless Window)             |
|                 App-ID: PrivoraWorkbench                      |
+---------------------------------------------------------------+
                               |
              HTTP / JSON & Static HTML (Port 8000)
                               v
+---------------------------------------------------------------+
|                     Privora Engine (FastAPI)                  |
|    - Mounts Next.js static export at '/'                      |
|    - Exposes REST API at '/api/...'                           |
|    - Local BM25 ranking + hybrid semantic search              |
|    - SQLite WAL database + document storage                   |
+---------------------------------------------------------------+
                               |
               Local Loopback HTTP (Port 11434)
                               v
+---------------------------------------------------------------+
|                   Local Ollama LLM Service                    |
|             (e.g., qwen2.5:7b on 127.0.0.1:11434)             |
+---------------------------------------------------------------+
```

### Key Technical Characteristics:
- **No Node.js Runtime for End Users**: The Next.js frontend is pre-compiled via static HTML/CSS/JS export (`output: 'export'`) and served directly by FastAPI via Starlette's `StaticFiles`.
- **Zero Console Windows**: The launcher runs silently using Windows `CREATE_NO_WINDOW` and the Edge App Mode chromeless frame (`--app=http://127.0.0.1:8000/`).
- **Data Persistence Invariant**: All databases (`workbench.sqlite3`), uploaded documents, and logs are persisted strictly inside `%LOCALAPPDATA%\Privora\data` and `%LOCALAPPDATA%\Privora\logs`. They are **never** stored inside volatile temporary folders, and are preserved across software updates.
- **Dedicated Edge Profile**: Edge runs with `--user-data-dir=%LOCALAPPDATA%\Privora\edge_profile`, ensuring complete isolation from your personal browsing history, extensions, and cookies.
- **Port Conflict Resolution**: If port 8000 is occupied by another application, Privora automatically scans ports 8001–8050. If an existing Privora instance is already running on port 8000, the launcher automatically connects to it without spawning duplicate servers.

---

## 2. Launching Privora Desktop

### Option A: Compiled Standalone Desktop App (Recommended for Production)
Once built via `scripts\build_desktop.ps1`:
1. Navigate to the `dist\` folder.
2. Double-click `Privora.exe`.
3. Privora launches seamlessly in its own dedicated, branded desktop window.

### Option B: One-Click PowerShell Launcher (Recommended for Development)
Run directly from PowerShell:
```powershell
.\start-desktop.ps1
```
Or double-click `start-desktop.bat` in Windows File Explorer.

### Option C: Direct Python Execution
```powershell
python privora_launcher.py
```

---

## 3. Building the Desktop Release Bundle

To compile the entire distribution from source code into standalone Windows binaries:

```powershell
# From the project root
powershell -ExecutionPolicy Bypass -File scripts\build_desktop.ps1
```

### Build Pipeline Steps:
1. **Frontend Export**: Executes `npm run build` to compile the React/Next.js application into static HTML/CSS/JS assets inside `out/`.
2. **Backend Engine Compilation**: Executes PyInstaller on `backend/privora_engine.spec` to create `dist/privora-engine/`, bundling Python 3.14, FastAPI, Uvicorn, SQLite, PyPDF, python-docx, PyMuPDF, and the static `out/` directory.
3. **Native Launcher Compilation**: Compiles `privora_launcher.py` into a compact standalone executable `dist/Privora.exe`.
4. **Windows Installer Generation**: Invokes Inno Setup 6 (`ISCC.exe`) if installed on the build machine.

---

## 4. Inno Setup Windows Installer

The installer script is located at:
```
installer/privora_setup.iss
```

### Installer Capabilities:
- Installs Privora into `{autopf}\Privora` (or local user folder if unprivileged).
- Creates Desktop and Start Menu shortcuts.
- Registers standard Windows "Add or Remove Programs" uninstaller.
- **Safety Rule**: During uninstallation, user databases and documents inside `%LOCALAPPDATA%\Privora\data` are explicitly preserved. The user is shown an informational dialog confirming their local documents have been retained.

### Manual Inno Setup Compilation:
If Inno Setup 6 is installed on your Windows host:
```powershell
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\privora_setup.iss
```
The output setup executable will be generated at `dist-installer\Privora-Setup-1.1.0.exe`.

---

## 5. Local Ollama Integration

Privora does not bundle multi-gigabyte neural network models inside the installer. Instead, it interfaces with standard local Ollama installations:

1. Install Ollama from [ollama.com](https://ollama.com).
2. Pull your desired language model:
   ```cmd
   ollama run qwen2.5:7b
   ```
3. Privora automatically connects to `http://127.0.0.1:11434`.
4. If Ollama is offline or unavailable, Privora's graceful fallback activates: BM25 passage retrieval and document analysis remain fully accessible, and citations are presented for manual inspection.

---

## 6. Verification and Test Suite

Privora includes automated regression tests covering local authentication, document ingestion, rate limiting, and desktop packaging:

```powershell
cd backend
python -m pytest tests -q
```
**Current Test Status**: 73 passing tests (100% pass rate).
