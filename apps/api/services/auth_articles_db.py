from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from ..config import DATA_DIR

CONTENT_DB_DIR = DATA_DIR / "content"
CONTENT_DB_PATH = CONTENT_DB_DIR / "content.db"
TOKEN_TTL_HOURS = int(os.getenv("AUTH_TOKEN_TTL_HOURS", "24"))
AUTH_SECRET = os.getenv("AUTH_SECRET", "change-me-in-production")


def _connect() -> sqlite3.Connection:
    CONTENT_DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(CONTENT_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_content_db() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                display_name TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user' CHECK(role IN ('user', 'moderator', 'admin')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS articles (
                id TEXT PRIMARY KEY,
                author_id TEXT NOT NULL,
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                content TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft', 'published', 'archived')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(author_id) REFERENCES users(id)
            );
            CREATE INDEX IF NOT EXISTS idx_articles_author_id ON articles(author_id);
            CREATE INDEX IF NOT EXISTS idx_articles_status ON articles(status);
            """
        )


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000).hex()


def create_user(email: str, password: str, display_name: str, role: str = "user") -> dict[str, Any]:
    now = datetime.now(UTC).isoformat()
    user_id = str(uuid4())
    salt = secrets.token_hex(16)
    password_hash = _hash_password(password, salt)
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO users(id, email, password_hash, password_salt, display_name, role, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, email.lower().strip(), password_hash, salt, display_name.strip(), role, now, now),
        )
        row = conn.execute("SELECT id, email, display_name, role FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row)


def authenticate_user(email: str, password: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email.lower().strip(),)).fetchone()
    if row is None:
        return None
    expected = _hash_password(password, row["password_salt"])
    if not secrets.compare_digest(expected, row["password_hash"]):
        return None
    return {"id": row["id"], "email": row["email"], "display_name": row["display_name"], "role": row["role"]}


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("utf-8")


def create_token(user: dict[str, Any]) -> str:
    payload = {
        "sub": user["id"],
        "email": user["email"],
        "display_name": user["display_name"],
        "role": user["role"],
        "exp": int((datetime.now(UTC) + timedelta(hours=TOKEN_TTL_HOURS)).timestamp()),
    }
    body = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(AUTH_SECRET.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).digest()
    return f"{body}.{_b64url(signature)}"


def parse_token(token: str) -> dict[str, Any] | None:
    try:
        body, sig = token.split(".", 1)
        expected_sig = hmac.new(AUTH_SECRET.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).digest()
        if not secrets.compare_digest(sig, _b64url(expected_sig)):
            return None
        padded = body + "=" * (-len(body) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8"))
        if int(payload.get("exp", 0)) < int(datetime.now(UTC).timestamp()):
            return None
        return payload
    except Exception:
        return None


def create_article(author_id: str, title: str, summary: str, content: str) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat()
    article_id = str(uuid4())
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO articles(id, author_id, title, summary, content, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'draft', ?, ?)
            """,
            (article_id, author_id, title.strip(), summary.strip(), content.strip(), now, now),
        )
    return get_article(article_id)


def get_article(article_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT a.*, u.display_name AS author_name
            FROM articles a JOIN users u ON u.id = a.author_id
            WHERE a.id = ?
            """,
            (article_id,),
        ).fetchone()
    return dict(row) if row else None


def list_articles(for_role: str, viewer_id: str) -> list[dict[str, Any]]:
    query = (
        """
        SELECT a.*, u.display_name AS author_name
        FROM articles a JOIN users u ON u.id = a.author_id
        WHERE a.status = 'published'
        ORDER BY a.updated_at DESC
        """
    )
    params: tuple[Any, ...] = ()
    if for_role in {"moderator", "admin"}:
        query = (
            """
            SELECT a.*, u.display_name AS author_name
            FROM articles a JOIN users u ON u.id = a.author_id
            ORDER BY a.updated_at DESC
            """
        )
    elif for_role == "user":
        query = (
            """
            SELECT a.*, u.display_name AS author_name
            FROM articles a JOIN users u ON u.id = a.author_id
            WHERE a.status = 'published' OR a.author_id = ?
            ORDER BY a.updated_at DESC
            """
        )
        params = (viewer_id,)

    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def update_article(article_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
    updates: list[str] = []
    values: list[Any] = []
    for key in ("title", "summary", "content", "status"):
        if key in patch and patch[key] is not None:
            updates.append(f"{key} = ?")
            values.append(str(patch[key]).strip())
    if not updates:
        return get_article(article_id)
    updates.append("updated_at = ?")
    values.append(datetime.now(UTC).isoformat())
    values.append(article_id)
    with _connect() as conn:
        conn.execute(f"UPDATE articles SET {', '.join(updates)} WHERE id = ?", values)
    return get_article(article_id)


def seed_admin_if_missing() -> None:
    admin_email = os.getenv("ADMIN_EMAIL", "admin@local-rag.dev")
    admin_password = os.getenv("ADMIN_PASSWORD", "ChangeMe123!")
    admin_name = os.getenv("ADMIN_DISPLAY_NAME", "System Admin")
    with _connect() as conn:
        exists = conn.execute("SELECT id FROM users WHERE role IN ('admin','moderator') LIMIT 1").fetchone()
    if exists is None:
        create_user(admin_email, admin_password, admin_name, role="admin")
