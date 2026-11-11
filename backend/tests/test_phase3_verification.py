from __future__ import annotations

import io
import re
import pytest
from fastapi.testclient import TestClient
from docx import Document


def test_auth_registration_validation(client):
    # Password < 8 characters must be rejected
    res = client.post(
        "/api/auth/register",
        json={
            "email": "short_pwd@example.com",
            "password": "short",
            "full_name": "Test User",
            "organization_name": "Test Org",
        },
    )
    assert res.status_code == 422

    # Whitespace only password must be rejected
    res = client.post(
        "/api/auth/register",
        json={
            "email": "whitespace_pwd@example.com",
            "password": "        ",
            "full_name": "Test User",
            "organization_name": "Test Org",
        },
    )
    assert res.status_code == 422

    # Valid registration succeeds
    res = client.post(
        "/api/auth/register",
        json={
            "email": "valid_user@example.com",
            "password": "valid_secure_password_123",
            "full_name": "Valid User",
            "organization_name": "Valid Org",
        },
    )
    assert res.status_code == 201
    assert "access_token" in res.json()

    # Duplicate registration must return 409 Conflict
    res_dup = client.post(
        "/api/auth/register",
        json={
            "email": "valid_user@example.com",
            "password": "another_password_456",
            "full_name": "Duplicate User",
            "organization_name": "Duplicate Org",
        },
    )
    assert res_dup.status_code == 409


def test_auth_login_and_logout_cookies(client, monkeypatch):
    monkeypatch.setenv("DEPLOYMENT_MODE", "server")

    # Register user
    reg = client.post(
        "/api/auth/register",
        json={
            "email": "session_user@example.com",
            "password": "my_secure_session_password_1",
            "full_name": "Session User",
            "organization_name": "Session Org",
        },
    )
    assert reg.status_code == 201
    token = reg.json()["access_token"]
    csrf = reg.json()["csrf_token"]

    # Verify /api/auth/me works with Authorization header
    me_resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["user"]["email"] == "session_user@example.com"

    # Logout
    logout_resp = client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert logout_resp.status_code == 200
    assert logout_resp.json()["logged_out"] is True

    # After logout, token must be invalidated
    me_after = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_after.status_code == 401


def test_document_docx_table_extraction(client, isolated_env):
    # Create an in-memory docx containing a paragraph and a table
    doc = Document()
    doc.add_paragraph("Architecture Overview: Privora Workbench")
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Component"
    table.cell(0, 1).text = "Description"
    table.cell(1, 0).text = "InferenceEngine"
    table.cell(1, 1).text = "AirGappedOllamaDaemon"

    docx_bytes = io.BytesIO()
    doc.save(docx_bytes)
    docx_bytes.seek(0)

    res = client.post(
        "/api/documents",
        files={"file": ("architecture.docx", docx_bytes.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert res.status_code == 201
    doc_id = res.json()["id"]

    # Inspect passages
    passages_res = client.get(f"/api/documents/{doc_id}/passages")
    assert passages_res.status_code == 200
    all_text = " ".join(p["text"] for p in passages_res.json()["passages"])
    assert "InferenceEngine" in all_text
    assert "AirGappedOllamaDaemon" in all_text

    # Search evidence
    search_res = client.get("/api/evidence?q=InferenceEngine")
    assert search_res.status_code == 200
    assert len(search_res.json()) > 0
    assert "InferenceEngine" in search_res.json()[0]["excerpt"]


def test_document_id_path_traversal_and_glob_prevention(client):
    # Invalid characters in document_id must be rejected with 400
    bad_delete = client.delete("/api/documents/*")
    assert bad_delete.status_code == 400

    bad_passages = client.get("/api/documents/../../passages")
    assert bad_passages.status_code in (400, 404)


def test_chat_empty_ollama_response_fallback(client, monkeypatch):
    # Upload sample doc
    client.post(
        "/api/documents",
        files={"file": ("test_empty.txt", b"Grounded information regarding system stability.", "text/plain")},
    )

    class MockEmptyOllamaResponse:
        status_code = 200
        def json(self):
            return {"response": "   "}

    class MockAsyncClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def post(self, url, **kwargs):
            return MockEmptyOllamaResponse()

    monkeypatch.setattr("httpx.AsyncClient", MockAsyncClient)

    chat_res = client.post(
        "/api/chat",
        json={"message": "system stability"},
    )
    assert chat_res.status_code == 200
    body = chat_res.json()
    assert body["answer"] == "No response could be generated from the retrieved evidence."
    assert len(body["citations"]) > 0


def test_retrieval_single_char_and_symbol_query(client):
    client.post(
        "/api/documents",
        files={"file": ("symbols.txt", b"Audit evidence tracking: item #1 and item #2.", "text/plain")},
    )

    # Query with single character
    res_char = client.get("/api/evidence?q=a")
    assert res_char.status_code == 200

    # Query with symbols
    res_sym = client.get("/api/evidence?q=#1")
    assert res_sym.status_code == 200


def test_cross_workspace_data_isolation(client, monkeypatch):
    monkeypatch.setenv("DEPLOYMENT_MODE", "server")

    # User A registers
    res_a = client.post(
        "/api/auth/register",
        json={"email": "usera@example.com", "password": "password_user_a", "full_name": "User A", "organization_name": "Org A"},
    )
    token_a = res_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # User B registers
    res_b = client.post(
        "/api/auth/register",
        json={"email": "userb@example.com", "password": "password_user_b", "full_name": "User B", "organization_name": "Org B"},
    )
    token_b = res_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # User A uploads doc A
    upload_a = client.post(
        "/api/documents",
        headers=headers_a,
        files={"file": ("confidential_a.txt", b"Secret data for Workspace A.", "text/plain")},
    )
    assert upload_a.status_code == 201
    doc_a_id = upload_a.json()["id"]

    # User B lists documents -> doc A must NOT be visible
    docs_b = client.get("/api/documents", headers=headers_b)
    assert docs_b.status_code == 200
    assert len(docs_b.json()["documents"]) == 0

    # User B attempts to access passages of doc A -> 404
    passages_b = client.get(f"/api/documents/{doc_a_id}/passages", headers=headers_b)
    assert passages_b.status_code == 404

    # User B attempts to delete doc A -> 404
    del_b = client.delete(f"/api/documents/{doc_a_id}", headers=headers_b)
    assert del_b.status_code == 404

    # User B searches evidence -> doc A must NOT appear
    evidence_b = client.get("/api/evidence?q=Secret", headers=headers_b)
    assert evidence_b.status_code == 200
    assert len(evidence_b.json()) == 0
