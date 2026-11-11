# Contributing to Privora

Thank you for your interest in contributing to **Privora — Private Document Intelligence Workbench for Confidential Data**!

Privora is built on an absolute principle: **Zero Cloud Leakage**. Every document, passage, calculation, and AI inference must remain strictly on-premise without transmitting confidential data to external servers.

---

## 1. Code of Conduct & Core Principles

When contributing code, please ensure adherence to our core technical tenets:
1. **No External Network Calls**: Never introduce cloud AI APIs, external embeddings, remote telemetry, or third-party tracking scripts.
2. **Local Model Only**: LLM operations must interact exclusively with local Ollama (`qwen2.5:7b` / `moondream`).
3. **Evidence Grounding**: AI outputs must be grounded in indexed document passages with traceable citations. Never encourage model hallucinations.
4. **Data Isolation & Integrity**: Respect multi-tenant workspace boundaries and never bypass SQLite access controls.

---

## 2. Development Setup

### Prerequisites
- **Python**: 3.10, 3.11, 3.12, 3.13, or 3.14
- **Node.js**: 18.x or 20.x+ (with npm or pnpm)
- **Local Ollama**: [ollama.com](https://ollama.com)
  ```bash
  ollama pull qwen2.5:7b
  ollama pull moondream
  ```

### Getting Started

1. **Fork and Clone the Repository**:
   ```bash
   git clone https://github.com/your-username/privora.git
   cd privora
   ```

2. **Set Up Python Backend**:
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Linux / macOS:
   source .venv/bin/activate

   pip install -r requirements.txt
   ```

3. **Set Up Frontend**:
   ```bash
   npm install
   ```

4. **Run in Development Mode**:
   - Terminal 1 (Backend):
     ```bash
     cd backend
     python desktop_server.py
     ```
     The FastAPI API will be available at `http://127.0.0.1:8000/docs`.

   - Terminal 2 (Frontend):
     ```bash
     npm run dev
     ```
     Open `http://localhost:3000` in your browser.

---

## 3. Running Automated Tests

Before submitting a Pull Request, verify that all test suites pass cleanly:

### A. Backend Pytest Suite
```bash
# Set PYTHONPATH to the backend directory
# Windows PowerShell:
$env:PYTHONPATH = "$PWD\backend"
python -m pytest backend/tests -v

# Linux / macOS:
PYTHONPATH=backend python -m pytest backend/tests -v
```
All 121 automated tests across all 17 modules should pass.

### B. Frontend Static Typecheck & Build
```bash
npx tsc --noEmit
npm run build
```
Verify that TypeScript emits zero errors and Next.js successfully compiles the static export (`out/`).

---

## 4. Pull Request Guidelines

1. **Create a Feature Branch**:
   ```bash
   git checkout -b feature/my-enhancement
   ```
2. **Keep Changes Focused**: Avoid mixing architectural refactors with bug fixes.
3. **Preserve Documentation**: Update `README.md`, docstrings, or test suites as needed.
4. **Never Commit Sensitive Data**: Check that `git status` does not stage `.env`, SQLite databases (`*.sqlite3`), or local document uploads.
5. **Submit PR**: Open a Pull Request targeting the `main` branch with a clear description of the problem solved and test verification output.

---

## 5. Reporting Issues & Vulnerabilities

If you discover a security vulnerability or potential privacy leak:
- Please report it responsibly by contacting the maintainers or opening a private security advisory on GitHub.
- Do not post confidential corporate documents or credentials in public issues.
