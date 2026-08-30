import check_approvals


def test_run_processes_events_and_publishes(monkeypatch):
    monkeypatch.setattr(check_approvals.db, "init_db", lambda: None)
    monkeypatch.setattr(check_approvals.db, "get_meta", lambda key, default=None: "0")
    events = [
        {"type": "approve", "draft_id": 1, "callback_query_id": "cq1"},
        {"type": "count", "value": 4},
    ]
    monkeypatch.setattr(check_approvals.telegram_bot, "get_events", lambda offset: (events, 2))

    status_updates = []
    monkeypatch.setattr(
        check_approvals.db, "set_status_if_pending",
        lambda draft_id, status: status_updates.append((draft_id, status)) or True,
    )
    monkeypatch.setattr(
        check_approvals.db, "update_status",
        lambda draft_id, status: status_updates.append((draft_id, status)),
    )
    monkeypatch.setattr(check_approvals.telegram_bot, "answer_callback", lambda cq_id, text: None)
    alerts = []
    monkeypatch.setattr(check_approvals.telegram_bot, "send_alert", lambda text: alerts.append(text))
    count_calls = []
    monkeypatch.setattr(check_approvals.config, "set_daily_post_count", lambda v: count_calls.append(v))
    meta_calls = []
    monkeypatch.setattr(check_approvals.db, "set_meta", lambda k, v: meta_calls.append((k, v)))
    monkeypatch.setattr(check_approvals.db, "get_pending_without_telegram_msg", lambda: [])

    monkeypatch.setattr(
        check_approvals.db, "get_approved_unpublished",
        lambda: [{"id": 1, "title": "t", "content": "c", "tags": "[]", "keyword": "kw"}],
    )
    monkeypatch.setenv("BLOGGER_BLOG_ID", "blog123")
    monkeypatch.setattr(
        check_approvals.post, "post_to_blogger",
        lambda blog_id, title, content, tags, search_description="": True,
    )
    monkeypatch.setattr(check_approvals.telegram_bot, "send_tistory_copy", lambda title, content, tags, summary="": None)

    check_approvals.run()

    assert "approved" in [s for _, s in status_updates]
    assert "published" in [s for _, s in status_updates]
    assert count_calls == [4]
    assert meta_calls == [("telegram_offset", "2")]
    assert any("승인" in a for a in alerts)


def test_run_publishes_content_unchanged_without_auto_image(monkeypatch):
    monkeypatch.setattr(check_approvals.db, "init_db", lambda: None)
    monkeypatch.setattr(check_approvals.db, "get_meta", lambda key, default=None: "0")
    monkeypatch.setattr(check_approvals.telegram_bot, "get_events", lambda offset: ([], 0))
    monkeypatch.setattr(check_approvals.db, "set_meta", lambda k, v: None)
    monkeypatch.setattr(check_approvals.db, "get_pending_without_telegram_msg", lambda: [])
    monkeypatch.setattr(
        check_approvals.db, "get_approved_unpublished",
        lambda: [{"id": 1, "title": "t", "content": "<p>body</p>", "tags": "[]", "keyword": "kw"}],
    )
    monkeypatch.setenv("BLOGGER_BLOG_ID", "blog123")
    monkeypatch.setattr(check_approvals.db, "update_status", lambda draft_id, status: None)

    captured = {}
    monkeypatch.setattr(
        check_approvals.post, "post_to_blogger",
        lambda blog_id, title, content, tags, search_description="": captured.setdefault("content", content) or True,
    )
    monkeypatch.setattr(check_approvals.telegram_bot, "send_tistory_copy", lambda title, content, tags, summary="": None)
    monkeypatch.setattr(check_approvals.generator, "rewrite_for_repost", lambda title, intro: {"title": title, "intro": intro})

    check_approvals.run()

    assert captured["content"] == "<p>body</p>"


def test_run_retries_and_alerts_on_repeated_publish_failure(monkeypatch):
    monkeypatch.setattr(check_approvals.db, "init_db", lambda: None)
    monkeypatch.setattr(check_approvals.db, "get_meta", lambda key, default=None: "0")
    monkeypatch.setattr(check_approvals.telegram_bot, "get_events", lambda offset: ([], 0))
    monkeypatch.setattr(check_approvals.db, "set_meta", lambda k, v: None)
    monkeypatch.setattr(check_approvals.db, "get_pending_without_telegram_msg", lambda: [])
    monkeypatch.setattr(
        check_approvals.db, "get_approved_unpublished",
        lambda: [{"id": 9, "title": "t", "content": "c", "tags": "[]", "keyword": "kw"}],
    )
    monkeypatch.setenv("BLOGGER_BLOG_ID", "blog123")
    monkeypatch.setattr(
        check_approvals.post, "post_to_blogger",
        lambda blog_id, title, content, tags, search_description="": False,
    )
    monkeypatch.setattr(check_approvals.db, "increment_retry", lambda draft_id: 6)
    alerts = []
    monkeypatch.setattr(check_approvals.telegram_bot, "send_alert", lambda text: alerts.append(text))
    status_updates = []
    monkeypatch.setattr(
        check_approvals.db, "update_status",
        lambda draft_id, status: status_updates.append((draft_id, status)),
    )

    check_approvals.run()

    assert len(alerts) == 1
    assert "9" in alerts[0]
    assert (9, "failed") in status_updates


def test_run_does_not_alert_at_exactly_max_retry(monkeypatch):
    monkeypatch.setattr(check_approvals.db, "init_db", lambda: None)
    monkeypatch.setattr(check_approvals.db, "get_meta", lambda key, default=None: "0")
    monkeypatch.setattr(check_approvals.telegram_bot, "get_events", lambda offset: ([], 0))
    monkeypatch.setattr(check_approvals.db, "set_meta", lambda k, v: None)
    monkeypatch.setattr(check_approvals.db, "get_pending_without_telegram_msg", lambda: [])
    monkeypatch.setattr(
        check_approvals.db, "get_approved_unpublished",
        lambda: [{"id": 9, "title": "t", "content": "c", "tags": "[]", "keyword": "kw"}],
    )
    monkeypatch.setenv("BLOGGER_BLOG_ID", "blog123")
    monkeypatch.setattr(
        check_approvals.post, "post_to_blogger",
        lambda blog_id, title, content, tags, search_description="": False,
    )
    monkeypatch.setattr(check_approvals.db, "increment_retry", lambda draft_id: 5)
    alerts = []
    monkeypatch.setattr(check_approvals.telegram_bot, "send_alert", lambda text: alerts.append(text))
    status_updates = []
    monkeypatch.setattr(
        check_approvals.db, "update_status",
        lambda draft_id, status: status_updates.append((draft_id, status)),
    )

    check_approvals.run()

    assert len(alerts) == 0
    assert ("failed" not in [s for _, s in status_updates])


def test_run_answer_callback_failure_does_not_crash_and_still_persists_status(monkeypatch):
    monkeypatch.setattr(check_approvals.db, "init_db", lambda: None)
    monkeypatch.setattr(check_approvals.db, "get_meta", lambda key, default=None: "0")
    events = [
        {"type": "approve", "draft_id": 1, "callback_query_id": "cq1"},
        {"type": "reject", "draft_id": 2, "callback_query_id": "cq2"},
    ]
    monkeypatch.setattr(check_approvals.telegram_bot, "get_events", lambda offset: (events, 5))

    status_updates = []
    monkeypatch.setattr(
        check_approvals.db, "set_status_if_pending",
        lambda draft_id, status: status_updates.append((draft_id, status)) or True,
    )

    def raise_expired(cq_id, text):
        raise Exception("Bad Request: query is too old")

    monkeypatch.setattr(check_approvals.telegram_bot, "answer_callback", raise_expired)
    alerts = []
    monkeypatch.setattr(check_approvals.telegram_bot, "send_alert", lambda text: alerts.append(text))

    meta_calls = []
    monkeypatch.setattr(check_approvals.db, "set_meta", lambda k, v: meta_calls.append((k, v)))
    monkeypatch.setattr(check_approvals.db, "get_pending_without_telegram_msg", lambda: [])
    monkeypatch.setattr(check_approvals.db, "get_approved_unpublished", lambda: [])

    check_approvals.run()

    assert (1, "approved") in status_updates
    assert (2, "rejected") in status_updates
    assert meta_calls == [("telegram_offset", "5")]
    assert any("승인" in a for a in alerts)
    assert any("거부" in a for a in alerts)


def test_run_retries_notification_for_orphaned_pending_drafts(monkeypatch):
    monkeypatch.setattr(check_approvals.db, "init_db", lambda: None)
    monkeypatch.setattr(check_approvals.db, "get_meta", lambda key, default=None: "0")
    monkeypatch.setattr(check_approvals.telegram_bot, "get_events", lambda offset: ([], 0))
    monkeypatch.setattr(check_approvals.db, "set_meta", lambda k, v: None)
    monkeypatch.setattr(check_approvals.db, "get_approved_unpublished", lambda: [])

    orphan = {"id": 3, "title": "제목", "keyword": "키워드"}
    monkeypatch.setattr(check_approvals.db, "get_pending_without_telegram_msg", lambda: [orphan])

    notify_calls = []

    def fake_send_draft_notification(draft_id, title, keyword, warnings=None, content="", image_prompt_en=""):
        notify_calls.append((draft_id, title, keyword, warnings))
        return 777

    monkeypatch.setattr(check_approvals.telegram_bot, "send_draft_notification", fake_send_draft_notification)

    msg_id_calls = []
    monkeypatch.setattr(
        check_approvals.db, "set_telegram_msg_id",
        lambda draft_id, msg_id: msg_id_calls.append((draft_id, msg_id)),
    )

    check_approvals.run()

    assert notify_calls == [(3, "제목", "키워드", None)]
    assert msg_id_calls == [(3, 777)]


def test_run_passes_stored_summary_as_search_description(monkeypatch):
    monkeypatch.setattr(check_approvals.db, "init_db", lambda: None)
    monkeypatch.setattr(check_approvals.db, "get_meta", lambda key, default=None: "0")
    monkeypatch.setattr(check_approvals.telegram_bot, "get_events", lambda offset: ([], 0))
    monkeypatch.setattr(check_approvals.db, "set_meta", lambda k, v: None)
    monkeypatch.setattr(check_approvals.db, "get_pending_without_telegram_msg", lambda: [])
    monkeypatch.setattr(
        check_approvals.db, "get_approved_unpublished",
        lambda: [{"id": 1, "title": "t", "content": "c", "tags": "[]", "summary": "저장된 요약", "keyword": "kw"}],
    )
    monkeypatch.setenv("BLOGGER_BLOG_ID", "blog123")
    monkeypatch.setattr(check_approvals.db, "update_status", lambda draft_id, status: None)

    captured = {}
    monkeypatch.setattr(
        check_approvals.post, "post_to_blogger",
        lambda blog_id, title, content, tags, search_description="": captured.setdefault("sd", search_description) or True,
    )
    monkeypatch.setattr(check_approvals.telegram_bot, "send_tistory_copy", lambda title, content, tags, summary="": None)

    check_approvals.run()

    assert captured["sd"] == "저장된 요약"


def test_run_sends_tistory_copy_after_successful_publish(monkeypatch):
    monkeypatch.setattr(check_approvals.db, "init_db", lambda: None)
    monkeypatch.setattr(check_approvals.db, "get_meta", lambda key, default=None: "0")
    monkeypatch.setattr(check_approvals.telegram_bot, "get_events", lambda offset: ([], 0))
    monkeypatch.setattr(check_approvals.db, "set_meta", lambda k, v: None)
    monkeypatch.setattr(check_approvals.db, "get_pending_without_telegram_msg", lambda: [])
    monkeypatch.setattr(
        check_approvals.db, "get_approved_unpublished",
        lambda: [{"id": 1, "title": "제목", "content": "<p>c</p>", "tags": '["a", "b"]', "summary": "요약", "keyword": "kw"}],
    )
    monkeypatch.setenv("BLOGGER_BLOG_ID", "blog123")
    monkeypatch.setattr(check_approvals.db, "update_status", lambda draft_id, status: None)
    monkeypatch.setattr(
        check_approvals.post, "post_to_blogger",
        lambda blog_id, title, content, tags, search_description="": True,
    )
    monkeypatch.setattr(
        check_approvals.generator, "rewrite_for_repost",
        lambda title, intro: {"title": "새 제목", "intro": "<p>새 도입부</p>"},
    )

    captured = {}
    monkeypatch.setattr(
        check_approvals.telegram_bot, "send_tistory_copy",
        lambda title, content, tags, summary="": captured.update(
            title=title, content=content, tags=tags, summary=summary
        ),
    )

    check_approvals.run()

    assert captured == {"title": "새 제목", "content": "<p>새 도입부</p>", "tags": ["a", "b"], "summary": "요약"}


def test_run_skips_tistory_copy_when_publish_fails(monkeypatch):
    monkeypatch.setattr(check_approvals.db, "init_db", lambda: None)
    monkeypatch.setattr(check_approvals.db, "get_meta", lambda key, default=None: "0")
    monkeypatch.setattr(check_approvals.telegram_bot, "get_events", lambda offset: ([], 0))
    monkeypatch.setattr(check_approvals.db, "set_meta", lambda k, v: None)
    monkeypatch.setattr(check_approvals.db, "get_pending_without_telegram_msg", lambda: [])
    monkeypatch.setattr(
        check_approvals.db, "get_approved_unpublished",
        lambda: [{"id": 1, "title": "제목", "content": "c", "tags": "[]", "keyword": "kw"}],
    )
    monkeypatch.setenv("BLOGGER_BLOG_ID", "blog123")
    monkeypatch.setattr(check_approvals.post, "post_to_blogger", lambda blog_id, title, content, tags, search_description="": False)
    monkeypatch.setattr(check_approvals.db, "increment_retry", lambda draft_id: 1)

    called = []
    monkeypatch.setattr(
        check_approvals.telegram_bot, "send_tistory_copy",
        lambda title, content, tags, summary="": called.append(True),
    )

    check_approvals.run()

    assert called == []


def test_vary_for_repost_rewrites_title_and_intro(monkeypatch):
    monkeypatch.setattr(
        check_approvals.generator, "rewrite_for_repost",
        lambda title, intro: {"title": "새 제목", "intro": "<p>새 도입부</p>"},
    )

    title, content = check_approvals._vary_for_repost("원제목", "<p>원도입부</p><h2>소제목</h2>")

    assert title == "새 제목"
    assert content == "<p>새 도입부</p><h2>소제목</h2>"


def test_vary_for_repost_keeps_leading_image_tag_intact(monkeypatch):
    monkeypatch.setattr(
        check_approvals.generator, "rewrite_for_repost",
        lambda title, intro: {"title": "새 제목", "intro": "<p>새 도입부</p>"},
    )

    original = '<img src="https://example.com/x.jpg" />\n<p>원도입부</p><h2>소제목</h2>'
    title, content = check_approvals._vary_for_repost("원제목", original)

    assert content.startswith('<img src="https://example.com/x.jpg" />\n<p>새 도입부</p>')


def test_vary_for_repost_falls_back_when_rewrite_fails(monkeypatch):
    def boom(title, intro):
        raise RuntimeError("gemini down")
    monkeypatch.setattr(check_approvals.generator, "rewrite_for_repost", boom)

    title, content = check_approvals._vary_for_repost("원제목", "<p>원도입부</p>")

    assert (title, content) == ("원제목", "<p>원도입부</p>")


def test_vary_for_repost_returns_unchanged_when_no_paragraph_found():
    title, content = check_approvals._vary_for_repost("원제목", "<h2>소제목만 있음</h2>")

    assert (title, content) == ("원제목", "<h2>소제목만 있음</h2>")
