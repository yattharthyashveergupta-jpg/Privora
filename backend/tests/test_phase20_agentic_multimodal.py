from __future__ import annotations

import io
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import pytest
from fastapi.testclient import TestClient


def create_pdf_with_table_and_drawing() -> bytes:
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 50), "MRPL Refinery Hydrogen Plant Operations Manual", fontsize=14)

    # Insert a structured grid / table
    table_rect = fitz.Rect(50, 100, 500, 200)
    # Draw simple lines so fitz detects layout/drawings
    shape = page.new_shape()
    shape.draw_rect(table_rect)
    shape.finish()
    shape.commit()

    page.insert_text((60, 120), "Stream Name       | Design Flow (Nm3/h) | Pressure bar(g)", fontsize=10)
    page.insert_text((60, 140), "Feed Naphtha      | 15,000              | 25.0", fontsize=10)
    page.insert_text((60, 160), "Product Hydrogen  | 45,000              | 22.5", fontsize=10)

    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def test_multimodal_pdf_table_and_diagram_extraction(client: TestClient):
    """Verifies that PDF extraction detects text, structured table layout, and visual page structures."""
    pdf_bytes = create_pdf_with_table_and_drawing()

    res = client.post(
        "/api/documents",
        files={"file": ("MRPL_H2_Plant.pdf", pdf_bytes, "application/pdf")},
    )
    assert res.status_code == 201
    doc_id = res.json()["id"]

    # Verify passages were extracted
    passages_res = client.get(f"/api/documents/{doc_id}/passages")
    assert passages_res.status_code == 200
    passages = passages_res.json()["passages"]
    assert len(passages) >= 1

    all_text = " ".join(p["text"] for p in passages)
    assert "Hydrogen Plant" in all_text
    assert "Feed Naphtha" in all_text or "Design Flow" in all_text


def test_multimodal_page_preview_endpoint(client: TestClient):
    """Verifies that the multimodal visual preview endpoint renders high-resolution PNG page previews."""
    pdf_bytes = create_pdf_with_table_and_drawing()

    res = client.post(
        "/api/documents",
        files={"file": ("MRPL_Preview_Test.pdf", pdf_bytes, "application/pdf")},
    )
    assert res.status_code == 201
    doc_id = res.json()["id"]

    preview_res = client.get(f"/api/documents/{doc_id}/page/1/preview")
    assert preview_res.status_code == 200
    assert preview_res.headers["content-type"] == "image/png"
    # Verify PNG magic header: \x89PNG\r\n\x1a\n
    assert preview_res.content[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(preview_res.content) > 1000  # Valid non-empty rendered image


def test_agentic_research_workflow(client: TestClient):
    """Verifies the multi-step agentic research workflow: decomposition, iterative tool search, synthesis."""
    # Ingest test document
    doc_text = (
        b"MRPL Plant Safety Guidelines\n\n"
        b"Refinery H2S alarm threshold is strictly set at 10 ppm.\n\n"
        b"Pump P-101B vibration status is HIGH_VIBRATION_ALARM at 7.8 mm/s."
    )
    client.post(
        "/api/documents",
        files={"file": ("MRPL_Guidelines.txt", doc_text, "text/plain")},
    )

    mock_plan_resp = MagicMock(status_code=200)
    mock_plan_resp.json.return_value = {
        "response": '["H2S alarm threshold", "Pump vibration status"]'
    }

    mock_synth_resp = MagicMock(status_code=200)
    mock_synth_resp.json.return_value = {
        "response": (
            "Executive Intelligence Brief:\n\n"
            "1. Process Safety: The H2S alarm threshold is set at 10 ppm [1].\n"
            "2. Equipment Health: Pump P-101B is under HIGH_VIBRATION_ALARM at 7.8 mm/s [2].\n\n"
            "Recommendations: Inspect Pump P-101B immediately and verify personal H2S detectors."
        )
    }

    # Simulate sequential calls: first planning, then synthesis
    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [mock_plan_resp, mock_synth_resp]

        res = client.post(
            "/api/agent/research",
            json={"goal": "Audit process safety and pump vibration status at MRPL"},
        )
        assert res.status_code == 200
        data = res.json()

        assert data["status"] == "completed"
        assert len(data["plan_queries"]) >= 2
        assert len(data["steps_executed"]) >= 2
        assert len(data["citations"]) >= 1
        assert "Executive Intelligence Brief" in data["executive_brief"]
        assert "[1]" in data["executive_brief"]
        assert data["safety_profile"]["air_gapped"] is True
        assert data["safety_profile"]["destructive_operations_blocked"] is True
