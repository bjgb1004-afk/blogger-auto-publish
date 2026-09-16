import db
import generate_drafts


def test_both_tracks_deliver_through_their_own_path(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "integration.db")
    monkeypatch.setenv("BLOGGER_BLOG_ID", "blog123")
    monkeypatch.delenv("GENERATE_MAX_PER_RUN", raising=False)

    monkeypatch.setattr(generate_drafts, "_apply_count_commands", lambda: None)
    monkeypatch.setattr(generate_drafts.config, "get_daily_post_count", lambda track: 1)
    monkeypatch.setattr(
        generate_drafts.keywords, "get_keywords_to_use",
        lambda track, needed: ["korean bbq guide"] if track == "blogspot" else ["테스트키워드"],
    )
    monkeypatch.setattr(
        generate_drafts.generator, "generate_post",
        lambda keyword, track: {
            "title": f"제목-{track}",
            "content": "<h2>소제목</h2><p>" + "본문 내용입니다. " * 30 + "</p>",
            "tags": ["태그1"],
        },
    )
    monkeypatch.setattr(generate_drafts.pubmed, "find_study", lambda topic: None)

    sent = {}

    def fake_post(blog_id, title, content, tags, search_description=""):
        sent["posted"] = title
        return "http://blog/1"

    monkeypatch.setattr(generate_drafts.post, "post_to_blogger", fake_post)
    monkeypatch.setattr(
        generate_drafts.telegram_bot, "send_published_notice",
        lambda draft_id, title, url, keyword, warnings=None, image_prompt_en="": sent.update(url=url),
    )
    monkeypatch.setattr(
        generate_drafts.telegram_bot, "send_tistory_copy",
        lambda title, content, tags, summary="", image_prompt_en="": sent.update(tistory=title),
    )

    assert generate_drafts.run() == 2
    assert sent == {"posted": "제목-blogspot", "url": "http://blog/1", "tistory": "제목-tistory"}

    conn = db.get_connection()
    try:
        rows = {r["track"]: r["status"] for r in conn.execute("SELECT track, status FROM drafts")}
    finally:
        conn.close()
    assert rows == {"blogspot": "published", "tistory": "sent"}


def test_failed_publish_stays_pending_and_retries_next_run(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "retry.db")
    monkeypatch.setenv("BLOGGER_BLOG_ID", "blog123")
    db.init_db()
    draft_id = db.insert_draft("kimchi guide", "제목", "<p>본문</p>", ["t"], track="blogspot")

    monkeypatch.setattr(generate_drafts.post, "post_to_blogger", lambda **kw: None)
    assert generate_drafts.publish(db.get_unpublished("blogspot")[0]) is False
    assert db.get_unpublished("blogspot")[0]["id"] == draft_id
    assert db.get_unpublished("blogspot")[0]["retry_count"] == 1

    monkeypatch.setattr(generate_drafts.post, "post_to_blogger", lambda **kw: "http://blog/2")
    monkeypatch.setattr(generate_drafts.telegram_bot, "send_published_notice", lambda *a, **k: None)
    assert generate_drafts.publish(db.get_unpublished("blogspot")[0]) is True
    assert db.get_unpublished("blogspot") == []
