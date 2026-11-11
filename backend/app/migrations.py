from __future__ import annotations

import sqlite3

def run_migrations(conn: sqlite3.Connection) -> None:
    """Run pending schema migrations on the SQLite database in a safe, versioned order.
    Preserves all existing documents, passages, and data.
    """
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "version INTEGER PRIMARY KEY, "
        "applied_at TEXT DEFAULT CURRENT_TIMESTAMP, "
        "description TEXT NOT NULL"
        ")"
    )

    applied = {
        row[0]
        for row in conn.execute("SELECT version FROM schema_migrations").fetchall()
    }

    # Migration 1: Base schema definition (documents and passages)
    if 1 not in applied:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS documents ("
            "id TEXT PRIMARY KEY, "
            "filename TEXT NOT NULL, "
            "content_type TEXT, "
            "size INTEGER NOT NULL, "
            "sha256 TEXT NOT NULL, "
            "status TEXT NOT NULL, "
            "pages INTEGER, "
            "error TEXT, "
            "created_at TEXT DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS passages ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "document_id TEXT NOT NULL, "
            "page INTEGER, "
            "text TEXT NOT NULL, "
            "FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE"
            ")"
        )
        conn.execute(
            "INSERT INTO schema_migrations (version, description) VALUES (1, 'Base documents and passages schema')"
        )
        conn.commit()

    # Migration 2: Identity, Organizations, Sessions, and Scoped Ownership
    if 2 not in applied:
        # 1. Create organizations / workspaces table
        conn.execute(
            "CREATE TABLE IF NOT EXISTS organizations ("
            "id TEXT PRIMARY KEY, "
            "name TEXT NOT NULL, "
            "slug TEXT UNIQUE NOT NULL, "
            "created_at TEXT DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
        conn.execute(
            "INSERT OR IGNORE INTO organizations (id, name, slug) "
            "VALUES ('org_default', 'Default Workspace', 'default')"
        )

        # 2. Create users table
        conn.execute(
            "CREATE TABLE IF NOT EXISTS users ("
            "id TEXT PRIMARY KEY, "
            "email TEXT UNIQUE NOT NULL, "
            "password_hash TEXT NOT NULL, "
            "salt TEXT NOT NULL, "
            "full_name TEXT NOT NULL, "
            "role TEXT NOT NULL DEFAULT 'member', "
            "organization_id TEXT NOT NULL, "
            "is_active INTEGER NOT NULL DEFAULT 1, "
            "created_at TEXT DEFAULT CURRENT_TIMESTAMP, "
            "FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE"
            ")"
        )
        # Default local owner user for seamless local single-user mode
        conn.execute(
            "INSERT OR IGNORE INTO users (id, email, password_hash, salt, full_name, role, organization_id) "
            "VALUES ('usr_local_owner', 'local@privora.workbench', '', '', 'Local Administrator', 'admin', 'org_default')"
        )

        # 3. Create sessions table
        conn.execute(
            "CREATE TABLE IF NOT EXISTS sessions ("
            "token TEXT PRIMARY KEY, "
            "user_id TEXT NOT NULL, "
            "created_at TEXT DEFAULT CURRENT_TIMESTAMP, "
            "expires_at TEXT NOT NULL, "
            "FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE"
            ")"
        )

        # 4. Check if documents table needs to be upgraded to scoped ownership
        doc_cols = [c[1] for c in conn.execute("PRAGMA table_info(documents)").fetchall()]
        if "owner_id" not in doc_cols:
            # Safely recreate documents table without triggering cascading deletes on child passages
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute(
                "CREATE TABLE documents_v2 ("
                "id TEXT PRIMARY KEY, "
                "filename TEXT NOT NULL, "
                "content_type TEXT, "
                "size INTEGER NOT NULL, "
                "sha256 TEXT NOT NULL, "
                "status TEXT NOT NULL, "
                "pages INTEGER, "
                "error TEXT, "
                "created_at TEXT DEFAULT CURRENT_TIMESTAMP, "
                "owner_id TEXT NOT NULL DEFAULT 'usr_local_owner', "
                "organization_id TEXT NOT NULL DEFAULT 'org_default', "
                "FOREIGN KEY(owner_id) REFERENCES users(id) ON DELETE CASCADE, "
                "FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE, "
                "UNIQUE(organization_id, owner_id, sha256)"
                ")"
            )
            # Copy all existing legacy documents and assign them to the local owner
            conn.execute(
                "INSERT INTO documents_v2 (id, filename, content_type, size, sha256, status, pages, error, created_at, owner_id, organization_id) "
                "SELECT id, filename, content_type, size, sha256, status, pages, error, created_at, 'usr_local_owner', 'org_default' "
                "FROM documents"
            )
            conn.execute("DROP TABLE documents")
            conn.execute("ALTER TABLE documents_v2 RENAME TO documents")
            conn.execute("PRAGMA foreign_keys = ON")

        # 5. Create performance and isolation indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_org_owner ON documents(organization_id, owner_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_org_owner_sha ON documents(organization_id, owner_id, sha256)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_passages_doc_id ON passages(document_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_users_org ON users(organization_id)")

        conn.execute(
            "INSERT INTO schema_migrations (version, description) "
            "VALUES (2, 'Identity models, user sessions, and workspace document isolation')"
        )
        conn.commit()

    # Migration 3: Multi-worker persistent rate limiting schema
    if 3 not in applied:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS auth_rate_limits ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "key TEXT NOT NULL, "
            "timestamp REAL NOT NULL"
            ")"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_rate_limits_key_time ON auth_rate_limits (key, timestamp)"
        )
        conn.execute(
            "INSERT INTO schema_migrations (version, description) "
            "VALUES (3, 'Multi-worker persistent rate limiting schema')"
        )
        conn.commit()

    # Migration 4: Workspaces, Enterprise RBAC, App Settings, and Audit Trail
    if 4 not in applied:
        # 1. App settings key-value store (onboarding completion, system preferences)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS app_settings ("
            "key TEXT PRIMARY KEY, "
            "value TEXT NOT NULL, "
            "updated_at TEXT DEFAULT CURRENT_TIMESTAMP"
            ")"
        )

        # 2. Workspaces table
        conn.execute(
            "CREATE TABLE IF NOT EXISTS workspaces ("
            "id TEXT PRIMARY KEY, "
            "name TEXT NOT NULL, "
            "slug TEXT NOT NULL, "
            "description TEXT, "
            "owner_id TEXT NOT NULL, "
            "organization_id TEXT NOT NULL, "
            "created_at TEXT DEFAULT CURRENT_TIMESTAMP, "
            "FOREIGN KEY(owner_id) REFERENCES users(id) ON DELETE CASCADE, "
            "FOREIGN KEY(organization_id) REFERENCES organizations(id) ON DELETE CASCADE, "
            "UNIQUE(organization_id, slug)"
            ")"
        )
        conn.execute(
            "INSERT OR IGNORE INTO workspaces (id, name, slug, description, owner_id, organization_id) "
            "VALUES ('ws_default', 'Primary Workspace', 'primary', 'Default intelligence workspace', 'usr_local_owner', 'org_default')"
        )

        # 3. Workspace members table (RBAC: owner, admin, member, viewer)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS workspace_members ("
            "id TEXT PRIMARY KEY, "
            "workspace_id TEXT NOT NULL, "
            "user_id TEXT NOT NULL, "
            "role TEXT NOT NULL DEFAULT 'member', "
            "created_at TEXT DEFAULT CURRENT_TIMESTAMP, "
            "FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE, "
            "FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE, "
            "UNIQUE(workspace_id, user_id)"
            ")"
        )
        conn.execute(
            "INSERT OR IGNORE INTO workspace_members (id, workspace_id, user_id, role) "
            "VALUES ('wm_local_owner', 'ws_default', 'usr_local_owner', 'owner')"
        )

        # 4. Add workspace_id column to documents table if missing
        doc_cols = [c[1] for c in conn.execute("PRAGMA table_info(documents)").fetchall()]
        if "workspace_id" not in doc_cols:
            conn.execute(
                "ALTER TABLE documents ADD COLUMN workspace_id TEXT NOT NULL DEFAULT 'ws_default' "
                "REFERENCES workspaces(id) ON DELETE CASCADE"
            )

        # 5. Security and compliance audit log table
        conn.execute(
            "CREATE TABLE IF NOT EXISTS audit_events ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "user_id TEXT, "
            "organization_id TEXT, "
            "workspace_id TEXT, "
            "action TEXT NOT NULL, "
            "details TEXT, "
            "ip_address TEXT, "
            "timestamp REAL NOT NULL"
            ")"
        )

        # 6. Performance and isolation indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_workspaces_org ON workspaces(organization_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_workspace_members_user ON workspace_members(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_workspace_members_ws ON workspace_members(workspace_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_ws ON documents(workspace_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_events(timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_events(action)")

        conn.execute(
            "INSERT INTO schema_migrations (version, description) "
            "VALUES (4, 'Workspaces, Enterprise RBAC, App Settings, and Audit Trail')"
        )
        conn.commit()

    # Migration 5: Passage section and coordinate anchors for structured documents & spreadsheets
    if 5 not in applied:
        passage_cols = [c[1] for c in conn.execute("PRAGMA table_info(passages)").fetchall()]
        if "section" not in passage_cols:
            conn.execute("ALTER TABLE passages ADD COLUMN section TEXT")

        conn.execute("CREATE INDEX IF NOT EXISTS idx_passages_doc_page ON passages(document_id, page)")
        conn.execute(
            "INSERT INTO schema_migrations (version, description) "
            "VALUES (5, 'Passage Section & Coordinate Anchors for Structured Docx & Excel')"
        )
        conn.commit()
