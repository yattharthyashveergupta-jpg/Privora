from __future__ import annotations

import io
import time
import pytest
from fastapi.testclient import TestClient
from docx import Document
import pymupdf


def test_real_pdf_multipage_extraction_and_grounding(client, isolated_env, monkeypatch):
    """Create a synthetic 2-page PDF, upload it, and verify multi-page extraction and page citations."""
    doc = pymupdf.open()
    page1 = doc.new_page()
    page1.insert_text((50, 50), "Privora Governance Policy: Data remains strictly within the on-premise perimeter.")
    page2 = doc.new_page()
    page2.insert_text((50, 50), "Retention Schedule: Audit logs must be retained for exactly seven years.")
    pdf_bytes = doc.tobytes()

    upload_res = client.post(
        "/api/documents",
        files={"file": ("governance_policy.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]
    assert upload_res.json()["pages"] == 2

    # Check passages
    passages_res = client.get(f"/api/documents/{doc_id}/passages")
    assert passages_res.status_code == 200
    passages = passages_res.json()["passages"]
    assert len(passages) >= 2

    # Page 1 passage
    p1 = next((p for p in passages if p["page"] == 1), None)
    assert p1 is not None
    assert "on-premise perimeter" in p1["text"]

    # Page 2 passage
    p2 = next((p for p in passages if p["page"] == 2), None)
    assert p2 is not None
    assert "seven years" in p2["text"]

    # Search evidence on page 2 topic
    evidence_res = client.get("/api/evidence?q=retention")
    assert evidence_res.status_code == 200
    hits = evidence_res.json()
    assert len(hits) > 0
    assert hits[0]["page"] == 2
    assert "seven years" in hits[0]["excerpt"]


def test_real_docx_tables_and_multi_paragraphs(client, isolated_env):
    """Verify that Word documents with both paragraphs and structured tables are parsed completely."""
    doc = Document()
    doc.add_paragraph("Enterprise Architecture Specifications.")
    table = doc.add_table(rows=3, cols=2)
    table.cell(0, 0).text = "Layer"
    table.cell(0, 1).text = "Technology"
    table.cell(1, 0).text = "Retrieval"
    table.cell(1, 1).text = "OkapiBM25Engine"
    table.cell(2, 0).text = "Storage"
    table.cell(2, 1).text = "SQLiteWriteAheadLog"

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)

    upload_res = client.post(
        "/api/documents",
        files={"file": ("specs.docx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    passages_res = client.get(f"/api/documents/{doc_id}/passages")
    assert passages_res.status_code == 200
    combined = " ".join(p["text"] for p in passages_res.json()["passages"])
    assert "OkapiBM25Engine" in combined
    assert "SQLiteWriteAheadLog" in combined


def test_real_txt_unicode_and_accents(client, isolated_env):
    """Verify ingestion and search of UTF-8 text with multilingual and mathematical symbols."""
    text_content = (
        "Multilingual Document Test:\n"
        "1. Deutsch: Datenschutz-Grundverordnung und Überwachung.\n"
        "2. 日本語: ドキュメント インテリジェンス ワークベンチ。\n"
        "3. Math: Entropy formula H(X) = -Σ P(x) log2 P(x).\n"
    )
    res = client.post(
        "/api/documents",
        files={"file": ("unicode_test.txt", text_content.encode("utf-8-sig"), "text/plain")},
    )
    assert res.status_code == 201

    # Search for German term
    search_de = client.get("/api/evidence?q=Datenschutz")
    assert search_de.status_code == 200
    assert len(search_de.json()) > 0
    assert "Datenschutz-Grundverordnung" in search_de.json()[0]["excerpt"]

    # Search for Math term
    search_math = client.get("/api/evidence?q=Entropy")
    assert search_math.status_code == 200
    assert len(search_math.json()) > 0
    assert "Entropy formula" in search_math.json()[0]["excerpt"]


def test_empty_and_whitespace_documents_rejection(client, isolated_env):
    """Empty files and whitespace-only files are rejected with 400."""
    files_dir = isolated_env / "documents"

    # 0 bytes file
    empty_res = client.post(
        "/api/documents",
        files={"file": ("empty.txt", b"", "text/plain")},
    )
    assert empty_res.status_code == 400

    # Whitespace file
    ws_res = client.post(
        "/api/documents",
        files={"file": ("whitespace.txt", b"   \n\n\t  \r\n  ", "text/plain")},
    )
    assert ws_res.status_code == 400

    # Ensure no files leaked onto disk
    assert len(list(files_dir.glob("*_empty.txt"))) == 0
    assert len(list(files_dir.glob("*_whitespace.txt"))) == 0


def test_duplicate_document_rejection_within_workspace(client, isolated_env):
    """Duplicate uploads of identical content within the same workspace are rejected with 409."""
    payload = b"Unique document content for duplicate rejection testing."
    res1 = client.post(
        "/api/documents",
        files={"file": ("first_upload.txt", payload, "text/plain")},
    )
    assert res1.status_code == 201

    res2 = client.post(
        "/api/documents",
        files={"file": ("second_upload.txt", payload, "text/plain")},
    )
    assert res2.status_code == 409
    assert "already indexed" in res2.json()["detail"]


def test_multi_worker_persistent_rate_limiter(client, isolated_env):
    """Verify that auth rate limiting persists to SQLite across worker calls."""
    from app.main import db, auth_rate_limiter

    # Use a custom key
    test_key = "test_worker_sync_key"
    conn1 = db()
    conn2 = db()

    try:
        # Reset any prior limits for this key
        auth_rate_limiter.reset(test_key, conn=conn1)

        # 5 allowed attempts
        for _ in range(auth_rate_limiter.max_attempts):
            assert auth_rate_limiter.is_allowed(test_key, conn=conn1) is True

        # 6th attempt from a different connection (simulating another worker process) must be rejected
        assert auth_rate_limiter.is_allowed(test_key, conn=conn2) is False

        # Reset works across connections
        auth_rate_limiter.reset(test_key, conn=conn2)
        assert auth_rate_limiter.is_allowed(test_key, conn=conn1) is True
    finally:
        conn1.close()
        conn2.close()


def test_document_id_security_injection(client):
    """Verify invalid document identifiers are rejected with 400."""
    res_glob = client.delete("/api/documents/*")
    assert res_glob.status_code == 400

    res_traversal = client.get("/api/documents/..%2F..%2Ftest/passages")
    assert res_traversal.status_code in (400, 404)


def test_unauthenticated_server_mode_all_protected_endpoints(client, monkeypatch):
    """In server mode, all protected endpoints reject unauthenticated access with 401."""
    monkeypatch.setenv("DEPLOYMENT_MODE", "server")

    protected_routes = [
        ("GET", "/api/auth/me"),
        ("POST", "/api/auth/logout"),
        ("GET", "/api/system/security-status"),
        ("GET", "/api/documents"),
        ("POST", "/api/documents"),
        ("DELETE", "/api/documents/doc123"),
        ("GET", "/api/documents/doc123/passages"),
        ("GET", "/api/evidence"),
        ("POST", "/api/chat"),
        ("GET", "/api/benchmark"),
    ]

    for method, path in protected_routes:
        if method == "GET":
            res = client.get(path)
        elif method == "POST":
            res = client.post(path, json={"message": "test"} if path == "/api/chat" else {})
        elif method == "DELETE":
            res = client.delete(path)
        assert res.status_code == 401, f"Route {method} {path} returned {res.status_code} instead of 401"


def test_database_restart_and_durability(isolated_env):
    """Verify database migrations, foreign keys, and WAL persistence across connection restarts."""
    from app.main import db

    conn1 = db()
    # Verify migration 3 was applied
    migrations = [r[0] for r in conn1.execute("SELECT version FROM schema_migrations").fetchall()]
    assert 1 in migrations
    assert 2 in migrations
    assert 3 in migrations

    # Verify WAL journal mode
    journal = conn1.execute("PRAGMA journal_mode;").fetchone()[0]
    assert journal.lower() == "wal"

    # Verify foreign keys are enabled
    fk = conn1.execute("PRAGMA foreign_keys;").fetchone()[0]
    assert fk == 1

    conn1.close()

    # Reconnect fresh
    conn2 = db()
    count = conn2.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    assert count >= 1
    conn2.close()
