from __future__ import annotations

import json
import sqlite3
import zipfile
from pathlib import Path
import pytest

from app.backup import create_backup, validate_backup_archive, restore_backup, list_backups
from app.migrations import run_migrations


def test_backup_and_restore_cycle(tmp_path: Path):
    data_dir = tmp_path / "live_data"
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "workbench.sqlite3"
    docs_dir = data_dir / "documents"
    docs_dir.mkdir(parents=True, exist_ok=True)

    # Initialize live database with migrations and dummy data
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    run_migrations(conn)
    conn.execute(
        "INSERT INTO documents (id, filename, content_type, size, sha256, status, pages, owner_id, organization_id, workspace_id) "
        "VALUES ('doc_1', 'financials.pdf', 'application/pdf', 1024, 'abc123hash', 'indexed', 2, 'usr_local_owner', 'org_default', 'ws_default')"
    )
    conn.execute(
        "INSERT INTO passages (document_id, page, text) VALUES ('doc_1', 1, 'Q3 revenue rose by 15 percent.')"
    )
    conn.commit()
    conn.close()

    # Create dummy document file
    (docs_dir / "doc_1_financials.pdf").write_text("dummy binary content", encoding="utf-8")

    # 1. Create backup
    backup_meta = create_backup(data_dir)
    backup_file = Path(backup_meta["path"])
    assert backup_file.exists()
    assert backup_meta["schema_version"] >= 4
    assert backup_meta["document_records"] == 1

    # 2. Validate backup archive
    manifest = validate_backup_archive(backup_file)
    assert manifest["version"] == "1.1.0"
    assert manifest["document_records"] == 1

    # 3. List backups
    all_backups = list_backups(data_dir)
    assert len(all_backups) >= 1
    assert all_backups[0]["filename"] == backup_file.name

    # 4. Modify live data (simulate catastrophic loss or corruption)
    conn = sqlite3.connect(db_path)
    conn.execute("DELETE FROM passages")
    conn.execute("DELETE FROM documents")
    conn.commit()
    conn.close()
    (docs_dir / "doc_1_financials.pdf").unlink()

    # Verify live data is empty
    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 0
    conn.close()

    # 5. Restore backup
    res = restore_backup(backup_file, data_dir)
    assert res["status"] == "success"

    # Verify live data is completely restored
    conn = sqlite3.connect(db_path)
    restored_docs = conn.execute("SELECT * FROM documents WHERE id = 'doc_1'").fetchone()
    assert restored_docs is not None
    passages_count = conn.execute("SELECT COUNT(*) FROM passages WHERE document_id = 'doc_1'").fetchone()[0]
    assert passages_count == 1
    conn.close()

    # Verify physical file is restored
    assert (docs_dir / "doc_1_financials.pdf").exists()


def test_restore_rollback_on_corrupt_archive(tmp_path: Path):
    data_dir = tmp_path / "live_data"
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "workbench.sqlite3"
    
    # Live database
    conn = sqlite3.connect(db_path)
    run_migrations(conn)
    conn.execute(
        "INSERT INTO documents (id, filename, content_type, size, sha256, status, pages, owner_id, organization_id, workspace_id) "
        "VALUES ('doc_keep', 'keep.pdf', 'application/pdf', 500, 'hashkeep', 'indexed', 1, 'usr_local_owner', 'org_default', 'ws_default')"
    )
    conn.commit()
    conn.close()

    # Create a corrupted zip
    corrupt_zip = tmp_path / "corrupt_backup.zip"
    with zipfile.ZipFile(corrupt_zip, "w") as zf:
        zf.writestr("manifest.json", json.dumps({"version": "1.1.0"}))
        zf.writestr("workbench.sqlite3", b"Not a real SQLite database file")

    # Attempt restore - should raise error and leave original database intact
    with pytest.raises(Exception):
        restore_backup(corrupt_zip, data_dir)

    # Verify live database was NOT destroyed by failed restore
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT * FROM documents WHERE id = 'doc_keep'").fetchone()
    assert row is not None
    conn.close()
