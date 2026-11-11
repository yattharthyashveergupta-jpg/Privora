from __future__ import annotations

import io
from docx import Document
import openpyxl
import pytest
from fastapi.testclient import TestClient


def create_contract_docx() -> bytes:
    doc = Document()
    doc.add_heading("Master Services Agreement", level=1)
    doc.add_heading("Section 4: Payment Terms", level=2)
    doc.add_paragraph("Customer shall pay all undisputed invoices within Net 30 days of the invoice date.")
    doc.add_heading("Section 7: Liability Cap", level=2)
    doc.add_paragraph("The maximum aggregate liability under this agreement is strictly capped at $500,000 USD.")
    doc.add_heading("Section 10: Retention", level=2)
    doc.add_paragraph("Audit logs must be retained for exactly seven years.")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def create_invoice_xlsx() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Billing Summary"
    ws.append(["Field", "Value", "Notes"])
    ws.append(["Invoice Number", "INV-2026-901", "Official"])
    ws.append(["Payment Terms", "Net 60 days", "Extended payment terms per counterparty request"])
    ws.append(["Liability Cap", "$1,000,000 USD", "Negotiated amendment"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_cross_document_contradiction_detection(client: TestClient):
    """Verify that contradictory payment terms and liability caps between Contract DOCX and Invoice XLSX are detected with dual citations."""
    contract_bytes = create_contract_docx()
    invoice_bytes = create_invoice_xlsx()

    res1 = client.post(
        "/api/documents",
        files={"file": ("contract_msa.docx", contract_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert res1.status_code == 201
    doc1_id = res1.json()["id"]

    res2 = client.post(
        "/api/documents",
        files={"file": ("invoice_spec.xlsx", invoice_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert res2.status_code == 201
    doc2_id = res2.json()["id"]

    # Run contradictions analysis across workspace documents
    audit_res = client.post("/api/analysis/contradictions", json={})
    assert audit_res.status_code == 200
    data = audit_res.json()
    assert data["status"] in ["ok", "completed"]
    assert len(data["documents_analyzed"]) >= 2
    assert data["findings_count"] >= 1

    findings = data["findings"]
    # Check that at least one contradiction was identified (e.g., payment terms or liability cap)
    conflict_topics = [f["topic"].lower() for f in findings]
    assert any("payment" in t or "liability" in t for t in conflict_topics)

    # Check dual-source citation integrity
    f = findings[0]
    assert "source_a" in f and "source_b" in f
    assert f["source_a"]["filename"] in ["contract_msa.docx", "invoice_spec.xlsx"]
    assert f["source_b"]["filename"] in ["contract_msa.docx", "invoice_spec.xlsx"]
    assert f["source_a"]["filename"] != f["source_b"]["filename"]
    assert f["source_a"]["location"] != ""
    assert f["source_b"]["location"] != ""


def test_pairwise_document_comparison(client: TestClient):
    """Verify side-by-side comparison of two documents aligns topics and flags conflicts."""
    contract_bytes = create_contract_docx()
    invoice_bytes = create_invoice_xlsx()

    res1 = client.post(
        "/api/documents",
        files={"file": ("contract_base.docx", contract_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    doc1_id = res1.json()["id"]

    res2 = client.post(
        "/api/documents",
        files={"file": ("invoice_rev.xlsx", invoice_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    doc2_id = res2.json()["id"]

    compare_res = client.post(
        "/api/analysis/compare",
        json={"document_id_a": doc1_id, "document_id_b": doc2_id},
    )
    assert compare_res.status_code == 200
    comp_data = compare_res.json()
    assert comp_data["status"] in ["ok", "completed"]
    assert comp_data["document_a"]["filename"] == "contract_base.docx"
    assert comp_data["document_b"]["filename"] == "invoice_rev.xlsx"
    assert len(comp_data["aligned_topics"]) >= 1
    assert comp_data["conflict_count"] >= 1


def test_transparent_privacy_audit_endpoint(client: TestClient):
    """Verify the /api/system/privacy-audit endpoint proves loopback binding and zero WAN sockets."""
    audit_res = client.get("/api/system/privacy-audit")
    assert audit_res.status_code == 200
    data = audit_res.json()

    assert data["status"] in ["verified", "warning"]
    assert data["model_endpoint"]["is_loopback"] is True
    assert data["storage"]["is_local_filesystem"] is True
    assert data["network_audit"]["outbound_wan_sockets"] == 0

    cloud_apis = data["external_cloud_apis"]
    assert cloud_apis["openai_configured"] is False
    assert cloud_apis["anthropic_configured"] is False
    assert cloud_apis["google_ai_configured"] is False
    assert cloud_apis["azure_ai_configured"] is False

    checks = data["verified_checks"]
    assert len(checks) >= 4
    assert all(c["passed"] is True for c in checks)
