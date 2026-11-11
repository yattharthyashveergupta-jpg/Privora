from __future__ import annotations

import io
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.main import app, chunk_text


def test_chunk_text_semantic_boundaries():
    """Verify smart chunking preserves paragraphs and bounds chunk sizes."""
    # Short text
    short = "This is a single short sentence."
    chunks = chunk_text(short, max_chars=500)
    assert len(chunks) == 1
    assert chunks[0] == short

    # Multi-paragraph text
    p1 = "Paragraph 1 is about cryptography and local on-premise execution."
    p2 = "Paragraph 2 discusses SQLite write-ahead logging and ACID guarantees."
    text = f"{p1}\n\n{p2}"
    chunks = chunk_text(text, max_chars=500)
    assert len(chunks) == 2
    assert chunks[0] == p1
    assert chunks[1] == p2

    # Long paragraph that exceeds max_chars
    long_p = "Sentence one. " * 30  # ~420 chars
    chunks_long = chunk_text(long_p, max_chars=200)
    assert len(chunks_long) > 1
    for c in chunks_long:
        assert len(c) <= 250


def test_unicode_and_multilingual_txt_ingestion(client: TestClient):
    """Verify UTF-8 text with multilingual scripts (German, Greek, Japanese, Arabic) and control characters."""
    multilingual_text = (
        "Privora Multilingual Intelligence:\n\n"
        "German: Überwachung und Datenschutz für Unternehmen.\n"
        "Greek: Ασφάλεια δεδομένων και προστασία της ιδιωτικότητας.\n"
        "Japanese: プライバシーとローカル文書知性プラットフォーム。\n"
        "Arabic: الخصوصية وأمان المستندات في الموقع.\n"
        "Control Chars Test: \x00\x01\x02Valid text after control characters."
    )
    res = client.post(
        "/api/documents",
        files={"file": ("multilingual.txt", multilingual_text.encode("utf-8"), "text/plain")},
    )
    assert res.status_code == 201
    doc_id = res.json()["id"]

    # Retrieve passages
    passages_res = client.get(f"/api/documents/{doc_id}/passages")
    assert passages_res.status_code == 200
    texts = [p["text"] for p in passages_res.json()["passages"]]
    combined = " ".join(texts)
    assert "Datenschutz" in combined
    assert "Ασφάλεια" in combined
    assert "プライバシー" in combined
    assert "\x00" not in combined  # Control char was stripped


def test_docx_table_and_heading_extraction(client: TestClient):
    """Verify synthetic DOCX with headings and structured tables extracts correctly."""
    from docx import Document
    doc = Document()
    doc.add_heading("Financial Q3 Report", level=1)
    doc.add_paragraph("Overall revenue grew by 18 percent year over year.")
    
    table = doc.add_table(rows=3, cols=2)
    table.rows[0].cells[0].text = "Division"
    table.rows[0].cells[1].text = "Revenue"
    table.rows[1].cells[0].text = "Enterprise"
    table.rows[1].cells[1].text = "$42M"
    table.rows[2].cells[0].text = "Consumer"
    table.rows[2].cells[1].text = "$12M"

    docx_bytes = io.BytesIO()
    doc.save(docx_bytes)
    docx_bytes.seek(0)

    res = client.post(
        "/api/documents",
        files={"file": ("financial_report.docx", docx_bytes.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert res.status_code == 201
    doc_id = res.json()["id"]

    # Verify passages contain heading and table format
    passages_res = client.get(f"/api/documents/{doc_id}/passages")
    assert passages_res.status_code == 200
    combined = " ".join([p["text"] for p in passages_res.json()["passages"]])
    assert "## Financial Q3 Report" in combined
    assert "Enterprise" in combined
    assert "$42M" in combined


def test_synthetic_grounded_evidence_retrieval(client: TestClient):
    """Verify BM25 retrieval finds exact known fact and returns proper citations."""
    doc_content = (
        "Project Aegis Technical Specification.\n\n"
        "Fact A: The encryption cipher used by Aegis is ChaCha20-Poly1305.\n\n"
        "Fact B: The default retention duration for audit records is 365 days.\n\n"
        "Fact C: Maximum allowed concurrent users per cluster node is 500."
    )
    upload_res = client.post(
        "/api/documents",
        files={"file": ("aegis_spec.txt", doc_content.encode("utf-8"), "text/plain")},
    )
    assert upload_res.status_code == 201

    # Search for Fact A
    ev_res = client.get("/api/evidence?q=ChaCha20")
    assert ev_res.status_code == 200
    evidence = ev_res.json()
    assert len(evidence) > 0
    assert "ChaCha20-Poly1305" in evidence[0]["excerpt"]
    assert evidence[0]["filename"] == "aegis_spec.txt"

    # Search for an entirely unrelated term -> grounded answering test
    chat_res = client.post(
        "/api/chat",
        json={"message": "What is the capital city of ancient Atlantis?"},
    )
    assert chat_res.status_code == 200
    ans = chat_res.json()
    assert ans["insufficient_evidence"] is True
    assert "couldn't find enough evidence" in ans["answer"]
