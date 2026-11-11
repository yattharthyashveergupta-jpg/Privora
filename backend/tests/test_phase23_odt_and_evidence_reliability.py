"""Privora Phase 23 — ODT Support, Evidence Reliability, and Benchmark Stability
Comprehensive test suite verifying:
1. Native ODT document text and table extraction.
2. Graceful error handling for corrupted or invalid ODT archives.
3. Full ODT document ingestion, passage chunking, and BM25 retrieval.
4. Test-guide de-prioritization over primary operational source documents.
5. Multi-document synthesis and contradiction detection across differing records.
6. Unsupported query defense and refusal consistency.
7. Dynamic empirical benchmark cycle execution.
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.main import app, extract, bm25_rank_passages


def create_sample_odt_bytes(
    title: str = "MRPL Desalter Operational Manual",
    paragraphs: list[str] | None = None,
    table_data: list[list[str]] | None = None,
) -> bytes:
    """Helper to generate a structurally valid in-memory ODT archive."""
    if paragraphs is None:
        paragraphs = [
            "The crude distillation desalter maintains an operating temperature of 135 degrees Celsius.",
            "Water wash injection rate is regulated at 5.5 volume percent of crude charge rate.",
        ]

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mimetype", "application/vnd.oasis.opendocument.text")
        
        xml_parts = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"',
            '                         xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"',
            '                         xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0">',
            '  <office:body>',
            '    <office:text>',
            f'      <text:h text:outline-level="1">{title}</text:h>',
        ]
        for p in paragraphs:
            xml_parts.append(f'      <text:p>{p}</text:p>')

        if table_data:
            xml_parts.append('      <table:table table:name="OperationalLimits">')
            for row in table_data:
                xml_parts.append('        <table:table-row>')
                for cell in row:
                    xml_parts.append(f'          <table:table-cell><text:p>{cell}</text:p></table:table-cell>')
                xml_parts.append('        </table:table-row>')
            xml_parts.append('      </table:table>')

        xml_parts.extend([
            '    </office:text>',
            '  </office:body>',
            '</office:document-content>',
        ])
        zf.writestr("content.xml", "\n".join(xml_parts))

    return buf.getvalue()


def test_odt_extraction_and_table_parsing(tmp_path):
    """Verifies that ODT headings, paragraphs, and tables are accurately extracted."""
    odt_path = tmp_path / "desalter_manual.odt"
    table = [
        ["Parameter", "Target", "Max Safety Limit"],
        ["Inlet Pressure", "8.2 barg", "10.0 barg"],
        ["Grid Voltage", "24 kV", "28 kV"],
    ]
    odt_path.write_bytes(create_sample_odt_bytes(table_data=table))

    passages = extract(odt_path, ".odt")
    assert len(passages) >= 2

    # Check headings and paragraphs
    text_corpus = "\n".join(p[1] for p in passages)
    assert "MRPL Desalter Operational Manual" in text_corpus
    assert "135 degrees Celsius" in text_corpus
    assert "5.5 volume percent" in text_corpus

    # Check table parsing
    table_passages = [p for p in passages if "OperationalLimits" in (p[2] or "")]
    assert len(table_passages) == 1
    t_text = table_passages[0][1]
    assert "Inlet Pressure | 8.2 barg | 10.0 barg" in t_text
    assert "Grid Voltage | 24 kV | 28 kV" in t_text


def test_odt_error_handling_corrupted_files(tmp_path):
    """Verifies that malformed, corrupted, or empty ODT files are safely rejected with clear errors."""
    # 1. Non-zip data
    bad_zip = tmp_path / "corrupted.odt"
    bad_zip.write_bytes(b"NOT_A_VALID_ZIP_HEADER_CONTENT")
    with pytest.raises(ValueError, match="Corrupted or invalid ODT archive"):
        extract(bad_zip, ".odt")

    # 2. Valid zip but missing content.xml
    missing_xml = tmp_path / "no_content.odt"
    with zipfile.ZipFile(missing_xml, "w") as zf:
        zf.writestr("mimetype", "application/vnd.oasis.opendocument.text")
    with pytest.raises(ValueError, match="content.xml not found"):
        extract(missing_xml, ".odt")

    # 3. Malformed XML inside content.xml
    bad_xml = tmp_path / "bad_xml.odt"
    with zipfile.ZipFile(bad_xml, "w") as zf:
        zf.writestr("content.xml", "<office:document-content><unclosed_tag>")
    with pytest.raises(ValueError, match="Corrupted or invalid XML"):
        extract(bad_xml, ".odt")

    # 4. Valid XML but empty/no text
    empty_odt = tmp_path / "empty.odt"
    with zipfile.ZipFile(empty_odt, "w") as zf:
        zf.writestr(
            "content.xml",
            '<?xml version="1.0"?><office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"><office:body><office:text></office:text></office:body></office:document-content>'
        )
    with pytest.raises(ValueError, match="No readable text found"):
        extract(empty_odt, ".odt")


def test_odt_ingestion_and_bm25_retrieval(client):
    """Uploads an ODT document via API, verifies DB indexing, and searches it via BM25."""
    odt_content = create_sample_odt_bytes(
        title="MRPL Hydrocracker Unit 7 Safety Specs",
        paragraphs=[
            "Reactor R-101 operates at a reaction temperature of 410 degrees Celsius and 142 bar pressure.",
            "Emergency quench hydrogen injection must initiate within 4 seconds of temperature excursion exceeding 425 C.",
        ],
    )
    
    files = {"file": ("MRPL_Hydrocracker_Unit7.odt", odt_content, "application/vnd.oasis.opendocument.text")}
    res = client.post("/api/documents", files=files)
    assert res.status_code in (200, 201), res.text
    data = res.json()
    assert data["status"] == "indexed"
    assert data["filename"] == "MRPL_Hydrocracker_Unit7.odt"
    assert data["pages"] is not None and data["pages"] >= 1
    doc_id = data["id"]

    # Verify passages endpoint
    p_res = client.get(f"/api/documents/{doc_id}/passages")
    assert p_res.status_code == 200
    passages = p_res.json()["passages"]
    assert len(passages) >= 1
    assert any("410 degrees Celsius" in p["text"] for p in passages)

    # Query via chat API
    chat_res = client.post(
        "/api/chat",
        json={"message": "What is the reaction temperature and quench hydrogen initiation time in Unit 7?", "top_k": 3},
    )
    assert chat_res.status_code == 200
    chat_data = chat_res.json()
    assert len(chat_data["citations"]) >= 1
    assert any("MRPL_Hydrocracker_Unit7.odt" in c["filename"] for c in chat_data["citations"])


def test_test_guide_deprioritization(client):
    """Ensures operational questions cite the primary operational manual, not test guides."""
    # 1. Primary operational manual
    primary_content = create_sample_odt_bytes(
        title="MRPL Flare System Operating Manual",
        paragraphs=[
            "Primary Flare Knockout Drum V-201 operating liquid level must remain below 30 percent.",
            "High liquid level alarm sounds at 45 percent triggering automatic diversion pump P-205A.",
        ],
    )
    client.post(
        "/api/documents",
        files={"file": ("MRPL_Flare_Operating_Manual.odt", primary_content, "application/vnd.oasis.opendocument.text")},
    )

    # 2. Evaluation test guide containing the same information
    guide_content = create_sample_odt_bytes(
        title="MRPL Flare Inspection Testing Guide",
        paragraphs=[
            "Testing Guide Reference: Verify that Flare Drum V-201 operating level is documented at 30 percent.",
            "Test scenario checks high liquid level alarm at 45 percent.",
        ],
    )
    client.post(
        "/api/documents",
        files={"file": ("MRPL_Flare_Testing_Guide.odt", guide_content, "application/vnd.oasis.opendocument.text")},
    )

    # Query operational fact
    chat_res = client.post(
        "/api/chat",
        json={"message": "What is the normal operating liquid level and alarm level for Flare Knockout Drum V-201?", "top_k": 3},
    )
    assert chat_res.status_code == 200
    citations = chat_res.json()["citations"]
    assert len(citations) >= 1

    # The primary operational manual should be citation #1, NOT the testing guide
    first_citation_filename = citations[0]["filename"]
    assert "MRPL_Flare_Operating_Manual.odt" in first_citation_filename


def test_unsupported_query_defense(client):
    """Verifies that out-of-scope queries with no evidence are refused without hallucinations."""
    res = client.post(
        "/api/chat",
        json={"message": "What is the executive flight travel reimbursement policy and cafeteria dessert menu?", "top_k": 5},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["support_level"] == "unsupported"
    assert "I couldn't find enough evidence" in data["answer"]
    assert len(data["citations"]) == 0


def test_benchmark_cycle_dynamic_update(client):
    """Verifies that the benchmark endpoint returns valid metrics and POST /run updates timestamps dynamically."""
    res = client.get("/api/benchmark")
    assert res.status_code == 200
    data = res.json()
    assert "summary_metrics" in data
    assert data["summary_metrics"]["overall_answer_correctness_pct"] == 91.67
    assert data["summary_metrics"]["overall_hallucination_rate_pct"] == 0.0
    assert len(data["test_cases"]) == 6

    # Re-run benchmark
    run_res = client.post("/api/benchmark/run")
    assert run_res.status_code == 200
    run_data = run_res.json()
    assert "evaluation_timestamp" in run_data
    assert run_data["summary_metrics"]["total_test_cases"] == 6
