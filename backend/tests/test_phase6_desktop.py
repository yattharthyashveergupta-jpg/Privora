from __future__ import annotations

import os
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.main import app, get_data_dir, get_static_dir


def test_get_data_dir_with_explicit_env(tmp_path, monkeypatch):
    """Verify WORKBENCH_DATA_DIR overrides desktop and default data dirs."""
    custom_dir = tmp_path / "custom_data"
    monkeypatch.setenv("WORKBENCH_DATA_DIR", str(custom_dir))
    monkeypatch.delenv("PRIVORA_DESKTOP", raising=False)
    
    resolved = get_data_dir()
    assert resolved == custom_dir
    assert resolved.exists()


def test_get_data_dir_desktop_mode(tmp_path, monkeypatch):
    """Verify PRIVORA_DESKTOP=1 targets LocalAppData\\Privora\\data."""
    fake_localappdata = tmp_path / "fake_localappdata"
    monkeypatch.delenv("WORKBENCH_DATA_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(fake_localappdata))
    monkeypatch.setenv("PRIVORA_DESKTOP", "1")
    
    resolved = get_data_dir()
    expected = fake_localappdata / "Privora" / "data"
    assert resolved == expected
    assert resolved.exists()


def test_get_static_dir_explicit_env(tmp_path, monkeypatch):
    """Verify STATIC_DIR points to static export when index.html is present."""
    fake_out = tmp_path / "fake_out"
    fake_out.mkdir()
    (fake_out / "index.html").write_text("<html>Privora</html>", encoding="utf-8")
    
    monkeypatch.setenv("STATIC_DIR", str(fake_out))
    assert get_static_dir() == fake_out


def test_get_static_dir_missing(tmp_path, monkeypatch):
    """Verify STATIC_DIR returns None or fallback if index.html is missing."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    monkeypatch.setenv("STATIC_DIR", str(empty_dir))
    
    # Empty dir does not have index.html
    # Should fall back or return None (or repo root out if exists)
    resolved = get_static_dir()
    # It should not return the empty dir
    assert resolved != empty_dir


def test_api_routes_precede_static_routes(client: TestClient):
    """Verify /api/health and /api/auth/csrf are served by FastAPI and not masked by static files."""
    health_resp = client.get("/api/health")
    assert health_resp.status_code == 200
    assert health_resp.json().get("status") == "ok"
    
    csrf_resp = client.get("/api/auth/csrf")
    assert csrf_resp.status_code == 200
    assert "csrf_token" in csrf_resp.json()


def test_launcher_helpers():
    """Verify launcher helper functions operate correctly."""
    # Add project root to sys.path to test privora_launcher functions
    root_dir = Path(__file__).resolve().parents[2]
    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))
        
    import privora_launcher
    
    # Test port checking on an unbound high port
    assert not privora_launcher.is_port_in_use(59999)
    
    # Test browser detection
    edge_path = privora_launcher.detect_edge_browser()
    # On Windows 11 host, Edge should be detected or None on Linux CI
    if os.name == "nt":
        assert edge_path is not None
        assert Path(edge_path).exists()


def test_find_suitable_port_prefers_8000_when_free(monkeypatch):
    """Regression test: verify find_suitable_port returns (8000, False) when port 8000 is unoccupied."""
    root_dir = Path(__file__).resolve().parents[2]
    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))

    import privora_launcher

    # Mock is_port_in_use to return False (port free)
    monkeypatch.setattr(privora_launcher, "is_port_in_use", lambda p, host="127.0.0.1": False)

    port, already_running = privora_launcher.find_suitable_port(8000)
    assert port == 8000, f"Expected port 8000 when free, got {port}"
    assert already_running is False


def test_find_suitable_port_advances_when_8000_occupied(monkeypatch):
    """Regression test: verify find_suitable_port increments port when 8000 is occupied by non-Privora."""
    root_dir = Path(__file__).resolve().parents[2]
    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))

    import privora_launcher

    # Mock 8000 as in use (non-Privora), 8001 as free
    def mock_in_use(p, host="127.0.0.1"):
        return p == 8000

    monkeypatch.setattr(privora_launcher, "is_port_in_use", mock_in_use)
    monkeypatch.setattr(privora_launcher, "check_privora_health", lambda p, host="127.0.0.1": False)

    port, already_running = privora_launcher.find_suitable_port(8000)
    assert port == 8001
    assert already_running is False

