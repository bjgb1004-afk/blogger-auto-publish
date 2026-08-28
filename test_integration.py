import db
import generate_drafts
import check_approvals


def test_full_pending_to_approved_to_published_lifecycle(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "integration.db")

    # -- generate_drafts.run(): fake Gemini + Telegram, real db --
    monkeypatch.setattr(generate_drafts.config, "get_daily_post_count", lambda: 1)
    monkeypatch.setattr(generate_drafts.keywords, "get_keywords_to_use", lambda needed: ["테스트키워드"])
    monkeypatch.setattr(
        generate_drafts.generator, "generate_post",
        lambda keyword: {
            "title": "테스트 제목",
            "content": "<h2>소제목</h2><p>" + "본문 내용입니다. " * 30 + "</p>",
            "tags": ["태그1"],
        },
    )
    monkeypatch.setattr(
        generate_drafts.telegram_bot, "send_draft_notification",
        lambda draft_id, title, keyword, warnings=None: 555,
    )

    created = generate_drafts.run()
    assert created == 1

    conn = db.get_connection()
    try:
        row = conn.execute("SELECT * FROM drafts WHERE status = 'pending'").fetchone()
    finally:
        conn.close()
    assert row is not None
    draft_id = row["id"]

    # -- check_approvals.run(): fake Telegram + Blogger, real db --
    approve_event = [{"type": "approve", "draft_id": draft_id, "callback_query_id": "cq1"}]
    monkeypatch.setattr(check_approvals.telegram_bot, "get_events", lambda offset: (approve_event, offset + 1))
    monkeypatch.setattr(check_approvals.telegram_bot, "answer_callback", lambda cq_id, text: None)
    monkeypatch.setattr(check_approvals.post, "post_to_blogger", lambda blog_id, title, content, tags, search_description="": True)
    monkeypatch.setenv("BLOGGER_BLOG_ID", "blog123")

    check_approvals.run()

    conn = db.get_connection()
    try:
        row = conn.execute("SELECT status FROM drafts WHERE id = ?", (draft_id,)).fetchone()
    finally:
        conn.close()
    assert row["status"] == "published"
