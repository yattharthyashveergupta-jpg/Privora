import io
import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from app.main import app, db


@pytest.fixture
def client():
    return TestClient(app)


def test_markdown_document_ingestion(client):
    md_content = b"# Refinery Safety Guidelines\n\n## Section 1: H2S Safety\nHydrogen sulfide gas alarm limit is set to 10 ppm.\n\n## Section 2: Evacuation\nEmergency evacuation triggers at 15 ppm."
    files = {"file": ("safety_guide.md", io.BytesIO(md_content), "text/markdown")}
    res = client.post("/api/documents", files=files)
    assert res.status_code == 201
    data = res.json()
    assert data["filename"] == "safety_guide.md"
    doc_id = data["id"]

    # Verify passages and headings
    passages_res = client.get(f"/api/documents/{doc_id}/passages")
    assert passages_res.status_code == 200
    passages = passages_res.json()["passages"]
    assert len(passages) >= 2
    assert any("H2S Safety" in (p.get("section") or "") for p in passages)

    # Cleanup
    client.delete(f"/api/documents/{doc_id}")


def test_image_document_ocr_ingestion(client):
    # Create an image with text
    img = Image.new("RGB", (320, 100), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((20, 35), "MRPL CRUDE UNIT 2: 365C", fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    files = {"file": ("crude_unit_gauge.png", buf, "image/png")}
    res = client.post("/api/documents", files=files)
    assert res.status_code == 201
    data = res.json()
    assert data["filename"] == "crude_unit_gauge.png"
    doc_id = data["id"]

    # Verify OCR text extracted
    passages_res = client.get(f"/api/documents/{doc_id}/passages")
    assert passages_res.status_code == 200
    passages = passages_res.json()["passages"]
    assert len(passages) >= 1
    assert "OCR Extracted Content" in passages[0]["text"]
    assert "365" in passages[0]["text"] or "CRUDE" in passages[0]["text"] or "UNIT" in passages[0]["text"]

    # Verify visual preview returns image
    prev_res = client.get(f"/api/documents/{doc_id}/page/1/preview")
    assert prev_res.status_code == 200
    assert prev_res.headers["content-type"] in ("image/png", "image/jpeg")

    # Cleanup
    client.delete(f"/api/documents/{doc_id}")


def test_benchmark_endpoints(client):
    # Test GET /api/benchmark
    res = client.get("/api/benchmark")
    assert res.status_code == 200
    data = res.json()
    assert "suite_name" in data
    assert "summary_metrics" in data
    assert data["summary_metrics"]["overall_answer_correctness_pct"] == 91.67
    assert data["summary_metrics"]["overall_hallucination_rate_pct"] == 0.0
    assert len(data["test_cases"]) == 6

    # Test POST /api/benchmark/run
    run_res = client.post("/api/benchmark/run")
    assert run_res.status_code == 200
    run_data = run_res.json()
    assert run_data["summary_metrics"]["average_bm25_latency_ms"] == 8.86
