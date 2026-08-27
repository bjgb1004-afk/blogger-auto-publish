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
        conn.commit()
    finally:
        conn.close()


def insert_draft(keyword: str, title: str, content: str, tags: list) -> int:
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO drafts (keyword, title, content, tags, status, created_at) "
            "VALUES (?, ?, ?, ?, 'pending', ?)",
            (keyword, title, content, json.dumps(tags, ensure_ascii=False), datetime.now().isoformat()),
        )
        conn.commit()
        draft_id = cursor.lastrowid
    finally:
        conn.close()
    return draft_id


def set_telegram_msg_id(draft_id: int, msg_id: int) -> None:
    conn = get_connection()
    try:
        conn.execute("UPDATE drafts SET telegram_msg_id = ? WHERE id = ?", (msg_id, draft_id))
        conn.commit()
    finally:
        conn.close()


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


def get_recent_keywords(days: int = 30) -> set:
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    conn = get_connection()
    try:
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


def get_approved_unpublished() -> list:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM drafts WHERE status = 'approved'").fetchall()
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
