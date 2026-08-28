import json
from datetime import datetime, timedelta

import db


def test_insert_and_get_today_count(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    assert db.get_today_count() == 0
    draft_id = db.insert_draft("키워드1", "제목1", "<p>본문</p>", ["태그1"])
    assert isinstance(draft_id, int)
    assert db.get_today_count() == 1


def test_recent_keywords_excludes_old(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    db.insert_draft("최근키워드", "t", "c", [])
    conn = db.get_connection()
    old_date = (datetime.now() - timedelta(days=40)).isoformat()
    conn.execute("UPDATE drafts SET created_at = ? WHERE keyword = '최근키워드'", (old_date,))
    conn.commit()
    conn.close()
    assert "최근키워드" not in db.get_recent_keywords(days=30)


def test_update_status_and_approved_unpublished(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    draft_id = db.insert_draft("k", "t", "c", ["a", "b"])
    db.update_status(draft_id, "approved")
    approved = db.get_approved_unpublished()
    assert len(approved) == 1
    assert approved[0]["id"] == draft_id
    assert json.loads(approved[0]["tags"]) == ["a", "b"]


def test_increment_retry(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    draft_id = db.insert_draft("k", "t", "c", [])
    assert db.increment_retry(draft_id) == 1
    assert db.increment_retry(draft_id) == 2


def test_get_pending_without_telegram_msg(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    draft_id = db.insert_draft("k", "t", "c", [])
    pending = db.get_pending_without_telegram_msg()
    assert len(pending) == 1
    assert pending[0]["id"] == draft_id

    db.set_telegram_msg_id(draft_id, 123)
    assert db.get_pending_without_telegram_msg() == []


def test_meta_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    assert db.get_meta("telegram_offset", "0") == "0"
    db.set_meta("telegram_offset", "42")
    assert db.get_meta("telegram_offset") == "42"


def test_insert_draft_persists_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    draft_id = db.insert_draft("k", "t", "c", [], summary="요약문")
    conn = db.get_connection()
    row = conn.execute("SELECT summary FROM drafts WHERE id = ?", (draft_id,)).fetchone()
    conn.close()
    assert row["summary"] == "요약문"


def test_init_db_migrates_existing_table_without_summary_column(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)
    conn = db.get_connection()
    conn.execute("""
        CREATE TABLE drafts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL, title TEXT NOT NULL, content TEXT NOT NULL,
            tags TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL, telegram_msg_id INTEGER,
            retry_count INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

    db.init_db()

    cols = {row["name"] for row in db.get_connection().execute("PRAGMA table_info(drafts)")}
    assert "summary" in cols
