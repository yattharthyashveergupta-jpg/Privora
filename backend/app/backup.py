from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path


def get_backup_dir(base_data_dir: Path) -> Path:
    bdir = base_data_dir / "backups"
    bdir.mkdir(parents=True, exist_ok=True)
    return bdir


def compute_file_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def create_backup(data_dir: Path, custom_output_dir: Path | None = None) -> dict:
    """Creates a consistent, point-in-time point backup of the SQLite database and all documents.
    Uses SQLite's online backup API for consistency under WAL mode.
    """
    db_path = data_dir / "workbench.sqlite3"
    files_dir = data_dir / "documents"
    output_dir = custom_output_dir or get_backup_dir(data_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_filename = f"privora_backup_{timestamp_str}.zip"
    backup_path = output_dir / backup_filename

    # Never overwrite an existing backup silently
    if backup_path.exists():
        timestamp_str = f"{timestamp_str}_{int(time.time() * 1000) % 1000}"
        backup_filename = f"privora_backup_{timestamp_str}.zip"
        backup_path = output_dir / backup_filename

    with tempfile.TemporaryDirectory() as tmp_str:
        tmp_dir = Path(tmp_str)
        snapshot_db = tmp_dir / "workbench.sqlite3"

        # 1. Atomic SQLite Online Backup
        if db_path.exists():
            source_conn = sqlite3.connect(db_path, timeout=15.0)
            dest_conn = sqlite3.connect(snapshot_db)
            try:
                source_conn.backup(dest_conn)
            finally:
                dest_conn.close()
                source_conn.close()
        else:
            # Create empty initialized db
            conn = sqlite3.connect(snapshot_db)
            conn.close()

        # Check max migration version
        chk_conn = sqlite3.connect(snapshot_db)
        try:
            cur = chk_conn.execute("SELECT MAX(version) FROM schema_migrations")
            row = cur.fetchone()
            schema_version = row[0] if row and row[0] is not None else 0
            doc_count = chk_conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        except Exception:
            schema_version = 0
            doc_count = 0
        finally:
            chk_conn.close()

        db_sha256 = compute_file_sha256(snapshot_db)

        # 2. Build manifest
        manifest = {
            "app": "Privora — Private Document Intelligence",
            "version": "1.1.0",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "schema_version": schema_version,
            "document_records": doc_count,
            "db_sha256": db_sha256,
        }
        manifest_path = tmp_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        # 3. Create zip archive
        with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(snapshot_db, arcname="workbench.sqlite3")
            zf.write(manifest_path, arcname="manifest.json")

            if files_dir.exists():
                for fpath in files_dir.iterdir():
                    if fpath.is_file():
                        zf.write(fpath, arcname=f"documents/{fpath.name}")

    backup_size = backup_path.stat().st_size
    return {
        "filename": backup_filename,
        "path": str(backup_path),
        "size_bytes": backup_size,
        "schema_version": schema_version,
        "document_records": doc_count,
        "created_at": manifest["created_at"],
    }


def validate_backup_archive(backup_zip_path: Path) -> dict:
    """Inspects and validates backup integrity without modifying live data."""
    if not backup_zip_path.exists():
        raise FileNotFoundError(f"Backup file not found: {backup_zip_path}")

    if not zipfile.is_zipfile(backup_zip_path):
        raise ValueError("Selected file is not a valid ZIP archive")

    with zipfile.ZipFile(backup_zip_path, "r") as zf:
        namelist = zf.namelist()
        if "workbench.sqlite3" not in namelist:
            raise ValueError("Corrupt backup: missing 'workbench.sqlite3'")
        if "manifest.json" not in namelist:
            raise ValueError("Corrupt backup: missing 'manifest.json'")

        manifest_data = json.loads(zf.read("manifest.json").decode("utf-8"))

        # Verify SQLite integrity from memory / temp extraction
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp_db = Path(tmp_str) / "workbench.sqlite3"
            with open(tmp_db, "wb") as f:
                f.write(zf.read("workbench.sqlite3"))

            chk_conn = sqlite3.connect(tmp_db)
            try:
                res = chk_conn.execute("PRAGMA integrity_check").fetchone()[0]
                if res != "ok":
                    raise ValueError(f"SQLite PRAGMA integrity_check failed: {res}")
            finally:
                chk_conn.close()

    return manifest_data


def restore_backup(backup_zip_path: Path, data_dir: Path) -> dict:
    """Restores database and document files with automated rollback protection."""
    manifest = validate_backup_archive(backup_zip_path)

    db_path = data_dir / "workbench.sqlite3"
    files_dir = data_dir / "documents"
    files_dir.mkdir(parents=True, exist_ok=True)

    rollback_dir = data_dir / ".rollback_temp"
    if rollback_dir.exists():
        shutil.rmtree(rollback_dir)
    rollback_dir.mkdir(parents=True, exist_ok=True)

    # 1. Create safety rollback snapshot of current live state
    try:
        if db_path.exists():
            shutil.copy2(db_path, rollback_dir / "workbench.sqlite3")
        rollback_docs = rollback_dir / "documents"
        if files_dir.exists():
            shutil.copytree(files_dir, rollback_docs)
    except Exception as exc:
        shutil.rmtree(rollback_dir, ignore_errors=True)
        raise RuntimeError(f"Could not create safety rollback snapshot before restore: {exc}")

    # 2. Extract backup contents
    try:
        with zipfile.ZipFile(backup_zip_path, "r") as zf:
            # Extract database
            zf.extract("workbench.sqlite3", path=data_dir)

            # Extract documents
            for member in zf.namelist():
                if member.startswith("documents/") and len(member) > len("documents/"):
                    zf.extract(member, path=data_dir)

        # 3. Post-restore integrity verification
        conn = sqlite3.connect(db_path, timeout=15.0)
        try:
            conn.execute("PRAGMA foreign_keys = ON;")
            check = conn.execute("PRAGMA integrity_check").fetchone()[0]
            if check != "ok":
                raise ValueError(f"Integrity check failed on restored database: {check}")
        finally:
            conn.close()

        # Success: cleanup rollback
        shutil.rmtree(rollback_dir, ignore_errors=True)
        return {
            "status": "success",
            "restored_at": datetime.now(timezone.utc).isoformat(),
            "manifest": manifest,
        }
    except Exception as exc:
        # Automatic Rollback
        if (rollback_dir / "workbench.sqlite3").exists():
            shutil.copy2(rollback_dir / "workbench.sqlite3", db_path)
        if (rollback_dir / "documents").exists():
            if files_dir.exists():
                shutil.rmtree(files_dir, ignore_errors=True)
            shutil.copytree(rollback_dir / "documents", files_dir)
        shutil.rmtree(rollback_dir, ignore_errors=True)
        raise RuntimeError(f"Restore failed and automated rollback was performed: {exc}")


def list_backups(data_dir: Path) -> list[dict]:
    bdir = get_backup_dir(data_dir)
    backups = []
    for f in sorted(bdir.glob("privora_backup_*.zip"), reverse=True):
        try:
            stat = f.stat()
            summary = {
                "filename": f.name,
                "path": str(f),
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            }
            try:
                manifest = validate_backup_archive(f)
                summary["manifest"] = manifest
            except Exception:
                summary["manifest"] = None
            backups.append(summary)
        except Exception:
            continue
    return backups
