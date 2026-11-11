from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_onboarding_and_diagnostics_lifecycle(client: TestClient):
    # 1. Initial onboarding status should be completed=False
    init_res = client.get("/api/system/onboarding")
    assert init_res.status_code == 200
    data = init_res.json()
    assert "completed" in data
    assert "ollama" in data
    assert "recommended_models" in data
    assert len(data["recommended_models"]) >= 3
    assert data["offline_evidence_mode_available"] is True

    # 2. Complete onboarding
    complete_res = client.post(
        "/api/system/onboarding",
        json={
            "completed": True,
            "selected_model": "qwen2.5:7b",
            "workspace_name": "My Intelligence Lab",
        },
    )
    assert complete_res.status_code == 200
    assert complete_res.json()["onboarding_completed"] is True

    # 3. Check onboarding is now completed
    after_res = client.get("/api/system/onboarding")
    assert after_res.status_code == 200
    assert after_res.json()["completed"] is True

    # 4. Check system models endpoint
    models_res = client.get("/api/system/models")
    assert models_res.status_code == 200
    models_data = models_res.json()
    assert "recommended" in models_data
    assert "active_model" in models_data

    # 5. Check system diagnostics
    diag_res = client.get("/api/system/diagnostics")
    assert diag_res.status_code == 200
    diag = diag_res.json()
    assert diag["version"] == "1.1.0"
    assert diag["status"] == "healthy"
    assert "database" in diag
    assert "storage" in diag
    assert "ollama" in diag
    assert diag["database"]["document_count"] >= 0
    assert diag["storage"]["disk_free_gb"] > 0

    # 6. Check audit events endpoint
    audit_res = client.get("/api/system/audit-events")
    assert audit_res.status_code == 200
    events = audit_res.json()["audit_events"]
    assert len(events) >= 1
    # Verify ONBOARDING_COMPLETED event is recorded
    actions = [e["action"] for e in events]
    assert "ONBOARDING_COMPLETED" in actions


def test_models_metadata_contract_and_offline_safety(client: TestClient, monkeypatch):
    """Regression test: verify model options are returned as rich objects with required fields,
    handle Ollama unavailability cleanly, and support string model identifier persistence."""
    # 1. Models endpoint contract
    res = client.get("/api/system/models")
    assert res.status_code == 200
    data = res.json()
    assert "connected" in data
    assert "installed" in data
    assert "available" in data
    assert "recommended" in data
    assert "active_model" in data
    assert isinstance(data["recommended"], list)
    assert len(data["recommended"]) >= 4

    # Each recommended model must be an object with valid metadata fields
    for model in data["recommended"]:
        assert isinstance(model, dict)
        assert "name" in model and isinstance(model["name"], str)
        assert "tag" in model and isinstance(model["tag"], str)
        assert "label" in model and isinstance(model["label"], str)
        assert "download_size" in model and isinstance(model["download_size"], str)
        assert "ram_required" in model and isinstance(model["ram_required"], str)
        assert "is_default" in model and isinstance(model["is_default"], bool)
        assert "installed" in model and isinstance(model["installed"], bool)

    # 2. Onboarding endpoint contract
    onb_res = client.get("/api/system/onboarding")
    assert onb_res.status_code == 200
    onb_data = onb_res.json()
    assert "recommended_models" in onb_data
    assert isinstance(onb_data["recommended_models"], list)
    for model in onb_data["recommended_models"]:
        assert isinstance(model, dict)
        assert "name" in model and isinstance(model["name"], str)
        assert "tag" in model and isinstance(model["tag"], str)
        assert "label" in model and isinstance(model["label"], str)

    # 3. Model selection persistence using string tag
    post_res = client.post(
        "/api/system/onboarding",
        json={
            "completed": True,
            "selected_model": "qwen2.5:3b",
            "workspace_name": "Test Lab",
        },
    )
    assert post_res.status_code == 200
    assert post_res.json()["onboarding_completed"] is True

    # 4. Offline Ollama simulation: point to non-existent port
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:54321")
    offline_res = client.get("/api/system/models")
    assert offline_res.status_code == 200
    offline_data = offline_res.json()
    assert offline_data["connected"] is False
    assert offline_data["installed"] == []
    assert len(offline_data["recommended"]) >= 4
