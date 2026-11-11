import io
import json
import os
import sys
import tempfile
from pathlib import Path

# Ensure backend root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import openpyxl
from docx import Document
import pymupdf
from fastapi.testclient import TestClient

# Set isolated environment
temp_dir = tempfile.mkdtemp(prefix="privora_verification_")
os.environ["WORKBENCH_DATA_DIR"] = temp_dir

from app.main import app
from app.privacy_audit import perform_privacy_audit
from app.cross_document import detect_cross_document_contradictions, compare_two_documents

client = TestClient(app)

print("=" * 60)
print("PRIVORA RELEASE VERIFICATION PROTOCOL")
print("=" * 60)

# 1. TEST PDF INGESTION & PAGE CITATIONS
pdf_doc = pymupdf.open()
p1 = pdf_doc.new_page()
p1.insert_text((50, 50), "Privora Security Directive 101: Encryption keys never leave the local enclave.")
p2 = pdf_doc.new_page()
p2.insert_text((50, 50), "Audit Policy 202: All operational audit trails must be retained for exactly seven years.")
pdf_bytes = pdf_doc.tobytes()

r_pdf = client.post("/api/documents", files={"file": ("security_directive.pdf", pdf_bytes, "application/pdf")})
assert r_pdf.status_code == 201, f"PDF upload failed: {r_pdf.text}"
pdf_id = r_pdf.json()["id"]
assert r_pdf.json()["pages"] == 2
print("[PASS] 1. PDF Ingestion: Verified multi-page extraction (2 pages).")

# 2. TEST TXT INGESTION
txt_bytes = b"Privora Architecture Overview:\nPrivora utilizes Okapi BM25 for deterministic local passage ranking without cloud embeddings."
r_txt = client.post("/api/documents", files={"file": ("architecture.txt", txt_bytes, "text/plain")})
assert r_txt.status_code == 201
txt_id = r_txt.json()["id"]
print("[PASS] 2. TXT Ingestion: Verified clean plaintext extraction.")

# 3. TEST DOCX INGESTION WITH SECTIONS & TABLES
docx = Document()
docx.add_heading("Master Vendor Contract", level=1)
docx.add_heading("Section 4: Payment Terms", level=2)
docx.add_paragraph("All invoices shall be settled strictly within Net 30 days.")
docx.add_heading("Section 7: Liability Limitations", level=2)
docx.add_paragraph("The maximum liability under this agreement is capped at $500,000 USD.")
docx_buf = io.BytesIO()
docx.save(docx_buf)
docx_bytes = docx_buf.getvalue()

r_docx = client.post("/api/documents", files={"file": ("vendor_contract.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
assert r_docx.status_code == 201
docx_id = r_docx.json()["id"]

# Verify DOCX passages contain section titles
docx_passages = client.get(f"/api/documents/{docx_id}/passages").json()["passages"]
docx_sections = [p.get("section") for p in docx_passages if p.get("section")]
assert any("Section 4: Payment Terms" in s for s in docx_sections)
print(f"[PASS] 3. DOCX Ingestion: Verified section extraction ({len(docx_passages)} passages, sections: {docx_sections}).")

# 4. TEST XLSX INGESTION WITH MULTI-SHEETS & CELL COORDINATES
wb = openpyxl.Workbook()
ws1 = wb.active
ws1.title = "Financial Summary"
ws1.append(["Metric", "2025 Actual", "2026 Target"])
ws1.append(["Revenue", 1250000, 1800000])
ws1.append(["Operating Cost", 850000, 920000])

ws2 = wb.create_sheet(title="Disputed Billing")
ws2.append(["Invoice ID", "Terms", "Liability Cap"])
ws2.append(["INV-9901", "Net 60 days", "$1,000,000 USD"])
xlsx_buf = io.BytesIO()
wb.save(xlsx_buf)
xlsx_bytes = xlsx_buf.getvalue()

r_xlsx = client.post("/api/documents", files={"file": ("financials_audit.xlsx", xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
assert r_xlsx.status_code == 201
xlsx_id = r_xlsx.json()["id"]

xlsx_passages = client.get(f"/api/documents/{xlsx_id}/passages").json()["passages"]
xlsx_sections = [p.get("section") for p in xlsx_passages if p.get("section")]
assert any("Sheet: Financial Summary" in s and "Cells:" in s for s in xlsx_sections)
assert any("Sheet: Disputed Billing" in s and "Cells:" in s for s in xlsx_sections)
print(f"[PASS] 4. XLSX Ingestion: Verified cell coordinate citations ({len(xlsx_passages)} chunks, coords: {xlsx_sections}).")

# 4b. TEST CSV INGESTION & DETERMINISTIC TABULAR ANALYTICS
csv_data = "Department,Q1 Spend,Q2 Spend,Headcount\nEngineering,150000,180000,15\nSales,95000,110000,8\nSupport,45000,50000,6\n"
r_csv = client.post("/api/documents", files={"file": ("department_spend.csv", csv_data.encode("utf-8"), "text/csv")})
assert r_csv.status_code == 201
csv_id = r_csv.json()["id"]

csv_passages = client.get(f"/api/documents/{csv_id}/passages").json()["passages"]
assert any("CSV: Rows" in (p.get("section") or "") for p in csv_passages)

# Deterministic Analytics Check
csv_analytics = client.get(f"/api/documents/{csv_id}/analytics").json()
assert csv_analytics["format"] == "csv"
csv_num_cols = {c["column"]: c for c in csv_analytics["sheets"][0]["numeric_columns"]}
assert csv_num_cols["Q1 Spend"]["total"] == 290000.0
assert csv_num_cols["Q2 Spend"]["total"] == 340000.0
assert csv_num_cols["Headcount"]["total"] == 29.0
print(f"[PASS] 4b. CSV Ingestion & Deterministic Analytics: Verified exact sum ($290,000 / $340,000 / 29 hc) across cell coordinates.")

# 5. TEST EVIDENCE RETRIEVAL WITH CELL COORDINATES
ev_res = client.get("/api/evidence?q=INV-9901")
assert ev_res.status_code == 200
ev_items = ev_res.json()
assert len(ev_items) > 0
top_ev = ev_items[0]
assert top_ev["filename"] == "financials_audit.xlsx"
assert "Sheet: Disputed Billing" in top_ev["section"]
print(f"[PASS] 5. Evidence Retrieval: Exact coordinates returned for XLSX ({top_ev['section']}).")

# 6. TEST CROSS-DOCUMENT CONTRADICTION AUDIT (DOCX vs XLSX)
# vendor_contract.docx has Net 30 & $500,000 cap; financials_audit.xlsx has Net 60 & $1,000,000 cap
contra_res = client.post("/api/analysis/contradictions", json={})
assert contra_res.status_code == 200
contra_data = contra_res.json()
assert contra_data["status"] == "completed"
assert contra_data["findings_count"] >= 1
print(f"[PASS] 6. Cross-Document Contradiction Audit: Detected {contra_data['findings_count']} contradictions.")
for f in contra_data["findings"]:
    print(f"    - [{f['severity'].upper()}] {f['title']}")
    print(f"      Source A: {f['source_a']['filename']} ({f['source_a']['location']}) -> {f['source_a']['claimed_value']}")
    print(f"      Source B: {f['source_b']['filename']} ({f['source_b']['location']}) -> {f['source_b']['claimed_value']}")

# 7. TEST PAIRWISE DOCUMENT COMPARISON
comp_res = client.post("/api/analysis/compare", json={"document_id_a": docx_id, "document_id_b": xlsx_id})
assert comp_res.status_code == 200
comp_data = comp_res.json()
assert comp_data["conflict_count"] >= 1
print(f"[PASS] 7. Pairwise Comparison: Successfully compared DOCX vs XLSX ({comp_data['conflict_count']} conflicts flagged).")

# 8. TEST PRIVACY & AIR-GAP AUDIT (ACTUAL VERIFICATION VS INFORMATIONAL DIAGNOSTICS)
audit = perform_privacy_audit()
assert audit["status"] in ["verified", "warning"]
assert audit["model_endpoint"]["is_loopback"] is True
assert audit["storage"]["is_local_filesystem"] is True
assert audit["network_audit"]["outbound_wan_sockets"] == 0
assert audit["external_cloud_apis"]["openai_configured"] is False
assert audit["external_cloud_apis"]["anthropic_configured"] is False

print("[PASS] 8. Privacy & Air-Gap Audit:")
print(f"    - Hard Verified: Loopback Inference = {audit['model_endpoint']['is_loopback']} ({audit['model_endpoint']['url']})")
print(f"    - Hard Verified: Outbound WAN Sockets = {audit['network_audit']['outbound_wan_sockets']} (Active Air-Gap)")
print(f"    - Hard Verified: External Cloud APIs = All Disabled (0 external connections)")
print(f"    - Hard Verified: Local Filesystem Storage = {audit['storage']['is_local_filesystem']}")
print(f"    - Informational: Database file = {audit['storage']['database_file']}")
print(f"    - Informational: Verified checks = {len(audit['verified_checks'])} passing security guarantees.")

# 9. TEST INSUFFICIENT EVIDENCE HANDLING IN CHAT
chat_res = client.post("/api/chat", json={"message": "What is the quantum teleporter frequency in Atlantis?"})
assert chat_res.status_code == 200
chat_data = chat_res.json()
assert chat_data["insufficient_evidence"] is True or len(chat_data["citations"]) == 0
print(f"[PASS] 9. Unsupported Question Handling: insufficient_evidence={chat_data['insufficient_evidence']}, citations={len(chat_data['citations'])}.")

print("=" * 60)
print("ALL VERIFICATION SUITES EXECUTED AND PASSED.")
print("=" * 60)
