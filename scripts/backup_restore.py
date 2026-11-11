"""Privora Backup and Disaster Recovery Utility.
Execute safe point-in-time backups and restorations for on-premise deployments.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.backup import create_backup, restore_backup, list_backups, validate_backup_archive
from app.main import get_data_dir


def main():
    parser = argparse.ArgumentParser(description="Privora Backup and Recovery Utility")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Backup command
    backup_parser = subparsers.add_parser("backup", help="Create a point-in-time backup")
    backup_parser.add_argument("--output-dir", type=str, help="Custom output directory for backup archive")

    # Restore command
    restore_parser = subparsers.add_parser("restore", help="Restore database and files from backup archive")
    restore_parser.add_argument("archive", type=str, help="Path to .zip backup archive")

    # List command
    list_parser = subparsers.add_parser("list", help="List available backups")

    # Verify command
    verify_parser = subparsers.add_parser("verify", help="Validate a backup archive without restoring")
    verify_parser.add_argument("archive", type=str, help="Path to .zip backup archive")

    args = parser.parse_args()
    data_dir = get_data_dir()

    if args.command == "backup":
        out_dir = Path(args.output_dir) if args.output_dir else None
        res = create_backup(data_dir, custom_output_dir=out_dir)
        print(f"[OK] Backup successfully created:")
        print(f"     Archive: {res['path']}")
        print(f"     Size:    {res['size_bytes'] / 1024:.1f} KB")
        print(f"     Records: {res['document_records']} documents")
        print(f"     Schema:  v{res['schema_version']}")

    elif args.command == "restore":
        archive_path = Path(args.archive).resolve()
        print(f"[*] Validating and restoring from {archive_path}...")
        res = restore_backup(archive_path, data_dir)
        print(f"[OK] Restoration complete! Status: {res['status']}")

    elif args.command == "list":
        backups = list_backups(data_dir)
        print(f"Available backups in {data_dir / 'backups'}:")
        if not backups:
            print("  (No backups found)")
        for b in backups:
            print(f"  - {b['filename']} ({b['size_bytes'] / 1024:.1f} KB, date: {b['modified_at']})")

    elif args.command == "verify":
        archive_path = Path(args.archive).resolve()
        manifest = validate_backup_archive(archive_path)
        print(f"[OK] Archive is valid and consistent:")
        for k, v in manifest.items():
            print(f"     {k}: {v}")


if __name__ == "__main__":
    main()
