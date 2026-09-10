import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "drafts.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS drafts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                tags TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                telegram_msg_id INTEGER,
                retry_count INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(drafts)")}
        if "summary" not in existing_cols:
            conn.execute("ALTER TABLE drafts ADD COLUMN summary TEXT NOT NULL DEFAULT ''")
        if "image_prompt_en" not in existing_cols:
            conn.execute("ALTER TABLE drafts ADD COLUMN image_prompt_en TEXT NOT NULL DEFAULT ''")
        conn.commit()
    finally:
        conn.close()


def insert_draft(keyword: str, title: str, content: str, tags: list, summary: str = "", image_prompt_en: str = "") -> int:
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO drafts (keyword, title, content, tags, summary, image_prompt_en, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)",
            (keyword, title, content, json.dumps(tags, ensure_ascii=False), summary, image_prompt_en, datetime.now().isoformat()),
        )
        conn.commit()
        draft_id = cursor.lastrowid
    finally:
        conn.close()
    return draft_id


def get_today_count() -> int:
    today = datetime.now().date().isoformat()
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM drafts WHERE substr(created_at, 1, 10) = ?", (today,)
        ).fetchone()
    finally:
        conn.close()
    return row["c"]


def get_recent_keywords(days: int = None) -> set:
    conn = get_connection()
    try:
        if days is None:
            rows = conn.execute("SELECT DISTINCT keyword FROM drafts").fetchall()
        else:
            cutoff = (datetime.now() - timedelta(days=days)).isoformat()
            rows = conn.execute(
                "SELECT DISTINCT keyword FROM drafts WHERE created_at >= ?", (cutoff,)
            ).fetchall()
    finally:
        conn.close()
    return {row["keyword"] for row in rows}


def update_status(draft_id: int, status: str) -> None:
    conn = get_connection()
    try:
        conn.execute("UPDATE drafts SET status = ? WHERE id = ?", (status, draft_id))
        conn.commit()
    finally:
        conn.close()


def increment_retry(draft_id: int) -> int:
    conn = get_connection()
    try:
        conn.execute("UPDATE drafts SET retry_count = retry_count + 1 WHERE id = ?", (draft_id,))
        conn.commit()
        row = conn.execute("SELECT retry_count AS c FROM drafts WHERE id = ?", (draft_id,)).fetchone()
    finally:
        conn.close()
    return row["c"]


def get_unpublished() -> list:
    """Drafts created but not yet posted to Blogger (retry queue)."""
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM drafts WHERE status = 'pending' ORDER BY id").fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


def get_meta(key: str, default: str = None) -> str:
    conn = get_connection()
    try:
        row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    finally:
        conn.close()
    return row["value"] if row else default


def set_meta(key: str, value: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        conn.commit()
    finally:
        conn.close()
