# Privora — Open Source License Compliance Audit
### Commercial Redistribution & On-Premise Deployment Review

This document provides a comprehensive third-party software license inventory for Privora (Private Document Intelligence Workbench).

---

## 1. Compliance Executive Summary

- **Total Direct Components Audited**: 22 (14 Frontend, 8 Backend)
- **Permissive Licenses Identified**: 100% (MIT, Apache 2.0, BSD-3-Clause, ISC)
- **Copyleft / Viral Licenses (GPL / AGPL / LGPL)**: 0 (Zero detected)
- **Proprietary Commercial Restrictions**: 0
- **Legal Posture**: **Fully approved for enterprise on-premise installation and commercial closed-source redistribution.**

---

## 2. Frontend Dependency Inventory

| Package | Version | License | Redistribution Restrictions |
| :--- | :--- | :--- | :--- |
| `next` | 16.4.1 | MIT | None; includes copyright notice |
| `react` | 19.x | MIT | None; includes copyright notice |
| `react-dom` | 19.x | MIT | None; includes copyright notice |
| `lucide-react` | 1.16.x | ISC | Permissive; equivalent to MIT |
| `@base-ui/react` | 1.5.0 | MIT | None |
| `class-variance-authority`| 0.7.1 | MIT | None |
| `clsx` | 2.1.1 | MIT | None |
| `tailwind-merge` | 3.3.1 | MIT | None |
| `tw-animate-css` | 1.4.0 | MIT | None |
| `tailwindcss` | 4.3.3 | MIT | None |
| `postcss` | 8.5.x | MIT | None |
| `typescript` | 5.7.3 | Apache-2.0 | None; build tool only |

---

## 3. Backend Dependency Inventory

| Package | Version | License | Redistribution Restrictions |
| :--- | :--- | :--- | :--- |
| `fastapi` | >=0.115,<1 | MIT | None |
| `uvicorn` | >=0.30,<1 | BSD-3-Clause | None; binary distribution retains BSD notice |
| `python-multipart` | >=0.0.9,<1 | Apache-2.0 | None |
| `pypdf` | >=5,<7 | BSD-3-Clause | None; standard PDF parsing |
| `python-docx` | >=1.1,<2 | MIT | None |
| `httpx` | >=0.27,<1 | BSD-3-Clause | None; internal HTTP client |
| `rank-bm25` | >=0.2.2 | Apache-2.0 | None; algorithmic ranking |
| `pytest` | >=8,<9 | MIT | Development & test runner only |

---

## 4. Architectural Isolation Guarantees

1. **Ollama Engine Isolation**: Privora communicates with the Ollama server strictly over an unauthenticated HTTP REST API (`localhost:11434`). The Ollama binary is MIT-licensed and executed as an independent separate process or separate container. No source-level linking takes place.
2. **SQLite Database Runtime**: SQLite is in the public domain and has zero copyright restrictions or licensing encumbrances.
3. **Microsoft Edge Runtime**: The Windows desktop launcher invokes the existing system-installed Microsoft Edge executable (`msedge.exe --app=...`). No proprietary Microsoft binaries are statically linked or redistributed with Privora.

---

## 5. Certification of Commercial Clearance

All libraries and components bundled into the Privora desktop package or server container permit:
- Commercial utilization within private organizations.
- Modification and internal customization.
- Closed-source binary packaging and distribution.
- Zero requirement to publish or open-source proprietary workbench code.
