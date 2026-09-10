import db
import generate_drafts


def test_generate_publishes_immediately_and_sends_tistory_copy(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "integration.db")
    monkeypatch.setenv("BLOGGER_BLOG_ID", "blog123")

    monkeypatch.setattr(generate_drafts, "_apply_count_commands", lambda: None)
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
    monkeypatch.setattr(generate_drafts.pubmed, "find_study", lambda topic: None)
    monkeypatch.setattr(generate_drafts, "_vary_for_repost", lambda title, content: (title, content))

    sent = {}
    monkeypatch.setattr(
        generate_drafts.post, "post_to_blogger",
        lambda blog_id, title, content, tags, search_description="": "http://blog/1",
    )
    monkeypatch.setattr(
        generate_drafts.telegram_bot, "send_published_notice",
        lambda draft_id, title, url, keyword, warnings=None, image_prompt_en="": sent.update(url=url),
    )
    monkeypatch.setattr(
        generate_drafts.telegram_bot, "send_tistory_copy",
        lambda title, content, tags, summary="": sent.update(tistory=title),
    )

    assert generate_drafts.run() == 1
    assert sent == {"url": "http://blog/1", "tistory": "테스트 제목"}

    conn = db.get_connection()
    try:
        row = conn.execute("SELECT status FROM drafts").fetchone()
    finally:
        conn.close()
    assert row["status"] == "published"


def test_failed_publish_stays_pending_and_retries_next_run(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "retry.db")
    monkeypatch.setenv("BLOGGER_BLOG_ID", "blog123")
    db.init_db()
    draft_id = db.insert_draft("키워드", "제목", "<p>본문</p>", ["t"])

    monkeypatch.setattr(generate_drafts.post, "post_to_blogger", lambda **kw: None)
    assert generate_drafts.publish(db.get_unpublished()[0]) is False
    assert db.get_unpublished()[0]["id"] == draft_id
    assert db.get_unpublished()[0]["retry_count"] == 1

    monkeypatch.setattr(generate_drafts.post, "post_to_blogger", lambda **kw: "http://blog/2")
    monkeypatch.setattr(generate_drafts.telegram_bot, "send_published_notice", lambda *a, **k: None)
    monkeypatch.setattr(generate_drafts.telegram_bot, "send_tistory_copy", lambda *a, **k: None)
    monkeypatch.setattr(generate_drafts, "_vary_for_repost", lambda title, content: (title, content))
    assert generate_drafts.publish(db.get_unpublished()[0]) is True
    assert db.get_unpublished() == []
