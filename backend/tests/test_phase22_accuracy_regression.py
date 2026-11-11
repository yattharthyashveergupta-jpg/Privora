import io
import pytest
from fastapi.testclient import TestClient
from docx import Document
import fitz

from app.main import app, db


@pytest.fixture
def client():
    return TestClient(app)


def test_regression_midnight_orchard_field_report(client):
    """Regression Test 1:
    Midnight_Orchard_Field_Report.docx contains:
    - Oyster mushrooms: Zone B
    - Relative humidity: 88%
    Privora must retrieve this passage and classify as fully supported.
    """
    # 1. Create realistic DOCX file
    doc = Document()
    doc.add_heading("Midnight Orchard Field Report", level=1)
    doc.add_paragraph("Agricultural Environmental Monitoring Report - Section 4.")
    doc.add_paragraph("Oyster mushrooms are cultivated in Zone B.")
    doc.add_paragraph("The relative humidity in the cultivation chambers is maintained at 88%.")
    
    # Also add a table format as commonly used in field reports
    table = doc.add_table(rows=2, cols=2)
    table.rows[0].cells[0].text = "Crop Variety"
    table.rows[0].cells[1].text = "Oyster mushrooms"
    table.rows[1].cells[0].text = "Cultivation Location & Humidity"
    table.rows[1].cells[1].text = "Zone B | Relative humidity: 88%"

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)

    # 2. Upload document
    files = {"file": ("Midnight_Orchard_Field_Report.docx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    res = client.post("/api/documents", files=files)
    assert res.status_code == 201, f"Upload failed: {res.text}"
    doc_id = res.json()["id"]

    try:
        # 3. Query chat endpoint
        chat_res = client.post(
            "/api/chat",
            json={
                "message": "Where are oyster mushrooms located and what is the relative humidity according to Midnight_Orchard_Field_Report.docx?",
                "top_k": 5,
            },
        )
        assert chat_res.status_code == 200, f"Chat failed: {chat_res.text}"
        data = chat_res.json()

        # 4. Verify accuracy and support classification
        assert data["support_level"] == "fully_supported", f"Expected fully_supported, got {data.get('support_level')}"
        assert data["insufficient_evidence"] is False
        assert len(data["citations"]) >= 1, "Expected citations"
        assert any(c["filename"] == "Midnight_Orchard_Field_Report.docx" for c in data["citations"])

        ans = data["answer"]
        assert "Zone B" in ans or "zone b" in ans.lower(), f"Expected Zone B in answer: {ans}"
        assert "88%" in ans or "88 percent" in ans.lower(), f"Expected 88% in answer: {ans}"

    finally:
        client.delete(f"/api/documents/{doc_id}")


def test_regression_transmission_media_snr_calculation(client):
    """Regression Test 2:
    Transmission_media.pdf, page 46 contains:
    - Signal power: 10 mW
    - Noise power: 1 μW
    Expected derived answer:
    - SNR = 10,000
    - SNR(dB) = 40 dB
    Privora must retrieve page 46, perform numerical calculation, and classify as fully supported.
    """
    # 1. Create multi-page PDF with 46 pages
    pdf_doc = fitz.open()
    for page_idx in range(45):
        p = pdf_doc.new_page(width=595, height=842)
        p.insert_text((50, 72), f"Transmission Media - Chapter Overview Page {page_idx + 1}")

    # Page 46: The specific test problem
    page_46 = pdf_doc.new_page(width=595, height=842)
    page_46.insert_text(
        (50, 72),
        "Transmission Media - Page 46.\n"
        "Section 3.5: Signal-to-Noise Ratio Analysis.\n"
        "Signal power: 10 mW\n"
        "Noise power: 1 μW\n"
        "Cable attenuation is 0.5 dB/km.\n"
        "Determine the transmission characteristics."
    )

    pdf_bytes = pdf_doc.tobytes()
    pdf_doc.close()

    # 2. Upload document
    files = {"file": ("Transmission_media.pdf", pdf_bytes, "application/pdf")}
    res = client.post("/api/documents", files=files)
    assert res.status_code == 201, f"Upload failed: {res.text}"
    doc_id = res.json()["id"]

    try:
        # 3. Query chat endpoint with SNR calculation request
        chat_res = client.post(
            "/api/chat",
            json={
                "message": "What is the SNR and SNR in dB for Transmission_media.pdf page 46?",
                "top_k": 5,
            },
        )
        assert chat_res.status_code == 200, f"Chat failed: {chat_res.text}"
        data = chat_res.json()

        # 4. Verify accuracy, calculation and support classification
        assert data["support_level"] == "fully_supported", f"Expected fully_supported, got {data.get('support_level')}"
        assert data["insufficient_evidence"] is False
        assert len(data["citations"]) >= 1, "Expected citations"
        assert any(c["filename"] == "Transmission_media.pdf" and c.get("page") == 46 for c in data["citations"]), "Expected citation on Page 46"

        ans = data["answer"]
        assert ("10,000" in ans or "10000" in ans), f"Expected SNR = 10,000 in answer: {ans}"
        assert ("40" in ans and "dB" in ans), f"Expected 40 dB in answer: {ans}"

    finally:
        client.delete(f"/api/documents/{doc_id}")


def test_regression_agentic_research_accuracy(client):
    """Regression Test 3:
    Verifies SafeResearchAgent executes multi-step investigation,
    gathers evidence from Midnight_Orchard_Field_Report.docx and Transmission_media.pdf,
    performs mathematical derivations, and produces fully supported briefs.
    """
    # 1. Create DOCX
    doc = Document()
    doc.add_heading("Midnight Orchard Field Report", level=1)
    doc.add_paragraph("Oyster mushrooms: Zone B")
    doc.add_paragraph("Relative humidity: 88%")
    buf = io.BytesIO()
    doc.save(buf)
    docx_bytes = buf.getvalue()

    # 2. Create PDF
    pdf_doc = fitz.open()
    for _ in range(45):
        p = pdf_doc.new_page(width=595, height=842)
        p.insert_text((50, 72), "General transmission theory.")
    p46 = pdf_doc.new_page(width=595, height=842)
    p46.insert_text((50, 72), "Transmission_media.pdf page 46.\nSignal power: 10 mW\nNoise power: 1 μW")
    pdf_bytes = pdf_doc.tobytes()
    pdf_doc.close()

    res1 = client.post("/api/documents", files={"file": ("Midnight_Orchard_Field_Report.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    res2 = client.post("/api/documents", files={"file": ("Transmission_media.pdf", pdf_bytes, "application/pdf")})
    assert res1.status_code == 201
    assert res2.status_code == 201
    d1_id = res1.json()["id"]
    d2_id = res2.json()["id"]

    try:
        # Agent Research Mission 1: Mushroom report
        agent_res1 = client.post(
            "/api/agent/research",
            json={"goal": "In Midnight_Orchard_Field_Report.docx, what zone are oyster mushrooms in and what is the relative humidity?"},
            timeout=90,
        )
        assert agent_res1.status_code == 200, f"Agent failed: {agent_res1.text}"
        rep1 = agent_res1.json()
        assert rep1["support_level"] == "fully_supported"
        assert rep1["total_evidence_passages"] >= 1
        brief1 = rep1["executive_brief"]
        assert "Zone B" in brief1 or "zone b" in brief1.lower()
        assert "88%" in brief1 or "88" in brief1

        # Agent Research Mission 2: SNR calculation
        agent_res2 = client.post(
            "/api/agent/research",
            json={"goal": "In Transmission_media.pdf page 46, calculate the SNR and SNR in dB where signal power is 10 mW and noise power is 1 μW."},
            timeout=90,
        )
        assert agent_res2.status_code == 200, f"Agent failed: {agent_res2.text}"
        rep2 = agent_res2.json()
        assert rep2["support_level"] == "fully_supported"
        assert rep2["numerical_derivations"] and len(rep2["numerical_derivations"]) >= 1
        deriv = rep2["numerical_derivations"][0]
        assert "10,000" in deriv["result"] or "10000" in deriv["result"]
        assert "40 dB" in deriv["result"] or "40" in deriv["result"]

    finally:
        client.delete(f"/api/documents/{d1_id}")
        client.delete(f"/api/documents/{d2_id}")
