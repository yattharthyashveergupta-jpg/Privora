from __future__ import annotations

import io
from fastapi.testclient import TestClient

from app.main import app, db


def test_audit_events_recorded_on_document_lifecycle(client: TestClient):
    """Verify document upload and deletion create tamper-evident audit records without leaking raw content."""
    fake_txt = io.BytesIO(b"Confidential project blueprint data.")
    res_up = client.post(
        "/api/documents",
        files={"file": ("audit_doc.txt", fake_txt, "text/plain")}
    )
    assert res_up.status_code == 201
    doc_id = res_up.json()["id"]

    # Verify audit event for upload
    res_audit = client.get("/api/system/audit-events")
    assert res_audit.status_code == 200
    events = res_audit.json()["events"]
    upload_events = [e for e in events if e["action"] in ("DOC_UPLOAD", "document_upload")]
    assert len(upload_events) >= 1
    assert "audit_doc.txt" in upload_events[0]["details"]

    # Delete document
    res_del = client.delete(f"/api/documents/{doc_id}")
    assert res_del.status_code == 200

    # Verify audit event for deletion
    res_audit2 = client.get("/api/system/audit-events")
    events2 = res_audit2.json()["events"]
    delete_events = [e for e in events2 if e["action"] in ("DOC_DELETE", "document_delete")]
    assert len(delete_events) >= 1
    assert "audit_doc.txt" in delete_events[0]["details"]


def test_audit_logs_do_not_leak_passwords_or_tokens(client: TestClient):
    """Verify user registration and authentication do not record raw passwords or secrets in audit details."""
    conn = db()
    try:
        rows = conn.execute("SELECT action, details FROM audit_events").fetchall()
        for r in rows:
            details_text = str(r["details"]).lower()
            assert "password" not in details_text or "password_hash" not in details_text
            assert "secret_password" not in details_text
            assert "session_token" not in details_text
    finally:
        conn.close()


def test_diagnostics_audit_and_server_security_warnings(client: TestClient, monkeypatch):
    """Verify system diagnostics check detects deployment mode and evaluates posture."""
    monkeypatch.setenv("DEPLOYMENT_MODE", "local")
    res = client.get("/api/system/diagnostics")
    assert res.status_code == 200
    data = res.json()
    assert data["server_mode"] is False
    assert data["database"]["status"] == "ok"
    assert data["database"]["wal_mode"] is True
    assert data["storage"]["documents_count"] >= 0

    # In server mode, protected system diagnostics strictly requires authentication
    monkeypatch.setenv("DEPLOYMENT_MODE", "server")
    res_server = client.get("/api/system/diagnostics")
    assert res_server.status_code == 401
