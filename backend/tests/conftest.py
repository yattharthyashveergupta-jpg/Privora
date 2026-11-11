import os
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    """Ensure every test runs against a clean, isolated temporary database directory.
    Guarantees the user's real database is NEVER touched.
    """
    test_data = tmp_path / "test_data"
    test_data.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("WORKBENCH_DATA_DIR", str(test_data))
    return test_data

@pytest.fixture
def client(isolated_env):
    """Provide a TestClient instance bound to the isolated environment."""
    from app.main import app
    return TestClient(app)

@pytest.fixture
def sample_txt_bytes():
    return b"Privora Intelligence Platform\n\nSecurity is paramount for on-premise document analysis.\n\nAll documents and passages are stored in local SQLite without external cloud dependencies."
