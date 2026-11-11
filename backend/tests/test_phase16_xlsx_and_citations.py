from __future__ import annotations

import io
import openpyxl
from docx import Document
import pymupdf
import pytest
from fastapi.testclient import TestClient


def create_synthetic_xlsx() -> bytes:
    """Create a multi-sheet spreadsheet with header rows and data rows."""
    wb = openpyxl.Workbook()
    # Sheet 1: Financials
    ws1 = wb.active
    ws1.title = "Financials"
    ws1.append(["Department", "Q1 Budget", "Q2 Budget", "Status"])
    ws1.append(["Engineering", 150000, 180000, "Approved"])
    ws1.append(["Compliance", 45000, 50000, "Approved"])
    ws1.append(["Security Ops", 95000, 110000, "Pending Review"])

    # Sheet 2: SLA Commitments
    ws2 = wb.create_sheet(title="SLA Specs")
    ws2.append(["Service Tier", "Uptime Target", "Support Response Hours"])
    ws2.append(["Enterprise Air-Gap", "99.99%", 1])
    ws2.append(["Standard Enclave", "99.9%", 4])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def create_synthetic_docx_with_sections() -> bytes:
    """Create a DOCX with explicit sections, headings, and paragraph content."""
    doc = Document()
    doc.add_heading("Master Service Agreement", level=1)
    doc.add_paragraph("This Master Service Agreement governs the terms of local deployment.")

    doc.add_heading("Section 3: Payment Terms and Billing", level=2)
    doc.add_paragraph("All invoices shall be paid within Net 30 days of receipt by the customer.")

    doc.add_heading("Section 8: Liability Limitation", level=2)
    doc.add_paragraph("The maximum aggregate liability under this agreement is strictly capped at $500,000 USD.")

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_xlsx_upload_and_cell_coordinate_citations(client: TestClient):
    """Verify XLSX ingestion extracts sheets, batches rows with headers, and generates cell coordinate sections."""
    xlsx_bytes = create_synthetic_xlsx()

    upload_res = client.post(
        "/api/documents",
        files={"file": ("department_budget.xlsx", xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert upload_res.status_code == 201
    data = upload_res.json()
    doc_id = data["id"]
    assert data["filename"] == "department_budget.xlsx"
    assert data["status"] == "indexed"

    # Query passages for this XLSX document
    passages_res = client.get(f"/api/documents/{doc_id}/passages")
    assert passages_res.status_code == 200
    p_data = passages_res.json()
    passages = p_data["passages"]
    assert len(passages) >= 2

    # Verify sheet names and cell coordinates in section field
    sections = [p["section"] for p in passages if p.get("section")]
    assert any("Sheet: Financials" in s for s in sections)
    assert any("Cells:" in s for s in sections)
    assert any("Sheet: SLA Specs" in s for s in sections)

    # Verify text preservation: headers repeated with row data
    all_text = " ".join(p["text"] for p in passages)
    assert "Engineering" in all_text
    assert "150000" in all_text or "150,000" in all_text
    assert "Enterprise Air-Gap" in all_text


def test_docx_section_heading_extraction(client: TestClient):
    """Verify DOCX parser captures heading names in the section field."""
    docx_bytes = create_synthetic_docx_with_sections()

    upload_res = client.post(
        "/api/documents",
        files={"file": ("vendor_agreement.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    passages_res = client.get(f"/api/documents/{doc_id}/passages")
    assert passages_res.status_code == 200
    passages = passages_res.json()["passages"]
    assert len(passages) >= 2

    sections = [p["section"] for p in passages if p.get("section")]
    assert any("Section 3: Payment Terms and Billing" in s for s in sections)
    assert any("Section 8: Liability Limitation" in s for s in sections)


def test_evidence_endpoint_returns_section_coordinates(client: TestClient):
    """Verify /api/evidence endpoint returns section coordinate metadata for citations."""
    xlsx_bytes = create_synthetic_xlsx()
    client.post(
        "/api/documents",
        files={"file": ("sla_metrics.xlsx", xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )

    ev_res = client.get("/api/evidence?query=Enterprise Air-Gap")
    assert ev_res.status_code == 200
    results = ev_res.json()
    assert len(results) >= 1

    top_hit = results[0]
    assert top_hit["filename"] == "sla_metrics.xlsx"
    assert top_hit.get("section") is not None
    assert "Sheet: SLA Specs" in top_hit["section"]
