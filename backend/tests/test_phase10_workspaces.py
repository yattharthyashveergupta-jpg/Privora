from __future__ import annotations

import io
import pytest
from fastapi.testclient import TestClient


def test_workspace_lifecycle_and_rbac(client: TestClient, monkeypatch):
    monkeypatch.setenv("DEPLOYMENT_MODE", "server")

    # 1. Register organization admin
    reg_admin = client.post("/api/auth/register", json={
        "email": "ceo@acme.corp",
        "password": "Password123!",
        "full_name": "Chief Executive",
        "organization_name": "Acme Corporation",
    }).json()
    admin_token = reg_admin["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 2. Register regular user who will become a viewer
    reg_viewer = client.post("/api/auth/register", json={
        "email": "auditor@acme.corp",
        "password": "Password123!",
        "full_name": "Auditor Person",
        "organization_name": "Acme Audit SubOrg",
    }).json()
    viewer_token = reg_viewer["access_token"]
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

    # 3. List initial workspaces for admin
    ws_list = client.get("/api/workspaces", headers=admin_headers)
    assert ws_list.status_code == 200
    workspaces = ws_list.json()["workspaces"]
    assert len(workspaces) >= 1
    default_ws = workspaces[0]

    # 4. Create new confidential project workspace
    create_res = client.post("/api/workspaces", headers=admin_headers, json={
        "name": "Project Titan Confidential",
        "description": "Restricted intelligence workspace for Titan initiative",
    })
    assert create_res.status_code == 201
    titan_ws = create_res.json()
    titan_id = titan_ws["id"]

    # 5. Add auditor to Titan workspace with role 'viewer'
    add_member_res = client.post(
        f"/api/workspaces/{titan_id}/members",
        headers=admin_headers,
        json={"email": "ceo@acme.corp", "role": "admin"},
    )
    assert add_member_res.status_code == 201

    # 6. Admin uploads confidential document into Titan workspace
    fake_txt = io.BytesIO(b"Confidential Project Titan specifications: Launch date is November 15.")
    upload_res = client.post(
        "/api/documents",
        headers={**admin_headers, "X-Workspace-Id": titan_id},
        files={"file": ("titan_spec.txt", fake_txt, "text/plain")},
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    # 7. Admin queries documents filtered by Titan workspace
    doc_list = client.get(f"/api/documents", headers={**admin_headers, "X-Workspace-Id": titan_id})
    assert doc_list.status_code == 200
    titan_docs = doc_list.json()["documents"]
    assert any(d["id"] == doc_id for d in titan_docs)

    # 8. Viewer in separate org cannot access Titan workspace
    unauth_upload = client.post(
        "/api/documents",
        headers={**viewer_headers, "X-Workspace-Id": titan_id},
        files={"file": ("malicious.txt", io.BytesIO(b"malicious"), "text/plain")},
    )
    assert unauth_upload.status_code == 403

    unauth_evidence = client.get("/api/evidence?q=Titan", headers={**viewer_headers, "X-Workspace-Id": titan_id})
    assert unauth_evidence.status_code == 403

    unauth_chat = client.post(
        "/api/chat",
        headers={**viewer_headers, "X-Workspace-Id": titan_id},
        json={"message": "What is the launch date?"},
    )
    assert unauth_chat.status_code == 403

    # 9. Clean deletion of Titan workspace by owner
    del_res = client.delete(f"/api/workspaces/{titan_id}", headers=admin_headers)
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "deleted"

    # Verify workspace is gone
    get_gone = client.get(f"/api/workspaces/{titan_id}", headers=admin_headers)
    assert get_gone.status_code == 404
