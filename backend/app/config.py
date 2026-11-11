"""Privora — Configuration & Storage Path Resolvers"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def get_data_dir() -> Path:
    if "WORKBENCH_DATA_DIR" in os.environ:
        p = Path(os.environ["WORKBENCH_DATA_DIR"])
    elif getattr(sys, "frozen", False) or os.getenv("PRIVORA_DESKTOP", "").lower() in ("1", "true"):
        local_app_data = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        p = Path(local_app_data) / "Privora" / "data"
    else:
        p = ROOT / "data"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_files_dir() -> Path:
    d = get_data_dir() / "documents"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_db_path() -> Path:
    return get_data_dir() / "workbench.sqlite3"


def get_ollama_base_url() -> str:
    return os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")


def get_deployment_mode() -> str:
    return os.getenv("DEPLOYMENT_MODE", "local").strip().lower()


def is_server_mode() -> bool:
    return get_deployment_mode() == "server"
