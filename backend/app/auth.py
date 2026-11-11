from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from pydantic import BaseModel, Field, field_validator


SESSION_COOKIE_NAME = "privora_session"
CSRF_COOKIE_NAME = "privora_csrf"
CSRF_HEADER_NAME = "x-csrf-token"
SESSION_DURATION_DAYS = 7


def is_cookie_secure() -> bool:
    """Return True if session cookies must enforce Secure=True (HTTPS only).
    Enabled when running behind an HTTPS reverse proxy or in production environment.
    """
    if os.getenv("COOKIE_SECURE", "").strip().lower() in ("1", "true", "yes"):
        return True
    if os.getenv("BEHIND_HTTPS_PROXY", "").strip().lower() in ("1", "true", "yes"):
        return True
    if os.getenv("PRIVORA_ENV", "").strip().lower() == "production":
        return True
    return False


def generate_csrf_token() -> str:
    """Generate a cryptographically random 256-bit token for CSRF protection."""
    return secrets.token_urlsafe(32)


def validate_csrf_token(header_token: str | None, cookie_token: str | None) -> bool:
    """Verify that client-supplied CSRF header matches the issued CSRF cookie in constant time."""
    if not header_token or not cookie_token:
        return False
    return hmac.compare_digest(header_token.strip(), cookie_token.strip())


def is_trusted_origin(origin: str | None, trusted_origins: list[str]) -> bool:
    """Verify that the incoming request's Origin header is explicitly in the trusted list."""
    if not origin:
        return True
    clean_origin = origin.rstrip("/").lower()
    trusted = {o.rstrip("/").lower() for o in trusted_origins}
    if clean_origin in trusted:
        return True
    if os.getenv("DEPLOYMENT_MODE", "local").strip().lower() != "server":
        import re
        if re.match(r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$", clean_origin):
            return True
    return False


class UserProfile(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    organization_id: str
    organization_name: str
    organization_slug: str


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    organization_name: str = Field(default="My Workspace", min_length=1, max_length=255)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v.strip()) < 8:
            raise ValueError("Password must be at least 8 characters long and cannot be only whitespace")
        return v


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)


# Precomputed dummy salt and hash for timing-attack normalization
_DUMMY_SALT = "a" * 32
_DUMMY_HASH = hashlib.pbkdf2_hmac("sha256", b"dummy_sample_password", bytes.fromhex(_DUMMY_SALT), 100_000).hex()


def dummy_verify_password(password: str) -> None:
    """Perform constant-time dummy hash calculation when user does not exist.
    Prevents response-timing attacks that probe whether an email address is registered.
    """
    try:
        salt = bytes.fromhex(_DUMMY_SALT)
        hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    except Exception:
        pass


def hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    """Hash password using PBKDF2-HMAC-SHA256 with 100,000 rounds and a cryptographic salt."""
    if salt is None:
        salt = secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return key.hex(), salt.hex()


def verify_password(password: str, password_hash: str, salt_hex: str) -> bool:
    """Verify password against stored PBKDF2 hash using constant-time comparison."""
    if not password_hash or not salt_hex:
        return False
    try:
        salt = bytes.fromhex(salt_hex)
        key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
        return hmac.compare_digest(key.hex(), password_hash)
    except Exception:
        return False


def hash_token(raw_token: str) -> str:
    """Hash session token with SHA-256 before database storage to prevent token replay from DB dumps."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_session(conn: sqlite3.Connection, user_id: str, duration_days: int = SESSION_DURATION_DAYS) -> str:
    """Create a new 256-bit cryptographically secure session token and store its SHA-256 hash."""
    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_token(raw_token)
    expires_at = (datetime.now(timezone.utc) + timedelta(days=duration_days)).isoformat()
    conn.execute(
        "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
        (token_hash, user_id, expires_at),
    )
    conn.commit()
    return raw_token


def get_user_from_session(conn: sqlite3.Connection, raw_token: str) -> dict | None:
    """Look up active user associated with a valid, unexpired session token.
    Checks SHA-256 hash with fallback to plaintext for backwards compatibility.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    token_hash = hash_token(raw_token)
    row = conn.execute(
        "SELECT u.id, u.email, u.full_name, u.role, u.organization_id, u.is_active, "
        "       o.name as organization_name, o.slug as organization_slug "
        "FROM sessions s "
        "JOIN users u ON u.id = s.user_id "
        "JOIN organizations o ON o.id = u.organization_id "
        "WHERE (s.token = ? OR s.token = ?) AND s.expires_at > ? AND u.is_active = 1",
        (token_hash, raw_token, now_iso),
    ).fetchone()
    if not row:
        return None
    return dict(row)


def delete_session(conn: sqlite3.Connection, raw_token: str) -> None:
    """Invalidate a session token upon logout."""
    token_hash = hash_token(raw_token)
    conn.execute("DELETE FROM sessions WHERE token = ? OR token = ?", (token_hash, raw_token))
    conn.commit()


def cleanup_expired_sessions(conn: sqlite3.Connection) -> int:
    """Delete all expired sessions from the database."""
    now_iso = datetime.now(timezone.utc).isoformat()
    cursor = conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (now_iso,))
    conn.commit()
    return cursor.rowcount


class RateLimiter:
    """Thread-safe and multi-worker persistent sliding-window rate limiter."""

    def __init__(self, max_attempts: int = 5, window_seconds: int = 60):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._attempts: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def is_allowed(self, key: str, conn: sqlite3.Connection | None = None) -> bool:
        now = time.time()
        window_start = now - self.window_seconds

        # 1. Multi-worker persistent storage when SQLite connection is available
        if conn is not None:
            try:
                conn.execute("DELETE FROM auth_rate_limits WHERE timestamp < ?", (window_start,))
                row = conn.execute(
                    "SELECT COUNT(*) FROM auth_rate_limits WHERE key = ? AND timestamp >= ?",
                    (key, window_start),
                ).fetchone()
                count = row[0] if row else 0
                if count >= self.max_attempts:
                    return False
                conn.execute(
                    "INSERT INTO auth_rate_limits (key, timestamp) VALUES (?, ?)",
                    (key, now),
                )
                conn.commit()
                return True
            except sqlite3.OperationalError:
                # Fallback to thread-safe memory sliding window if table not ready
                pass

        # 2. In-memory sliding-window fallback
        with self._lock:
            history = self._attempts.get(key, [])
            valid = [t for t in history if now - t < self.window_seconds]
            if len(valid) >= self.max_attempts:
                self._attempts[key] = valid
                return False
            valid.append(now)
            self._attempts[key] = valid
            return True

    def reset(self, key: str | None = None, conn: sqlite3.Connection | None = None) -> None:
        if conn is not None:
            try:
                if key:
                    conn.execute("DELETE FROM auth_rate_limits WHERE key = ?", (key,))
                else:
                    conn.execute("DELETE FROM auth_rate_limits")
                conn.commit()
            except sqlite3.OperationalError:
                pass
        with self._lock:
            if key:
                self._attempts.pop(key, None)
            else:
                self._attempts.clear()


auth_rate_limiter = RateLimiter(
    max_attempts=int(os.getenv("AUTH_RATE_LIMIT_MAX_ATTEMPTS", "5")),
    window_seconds=int(os.getenv("AUTH_RATE_LIMIT_WINDOW_SECONDS", "60")),
)
