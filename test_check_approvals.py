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
        check_approvals.db, "update_status",
        lambda draft_id, status: status_updates.append((draft_id, status)),
    )
    monkeypatch.setattr(check_approvals.telegram_bot, "answer_callback", lambda cq_id, text: None)
    count_calls = []
    monkeypatch.setattr(check_approvals.config, "set_daily_post_count", lambda v: count_calls.append(v))
    meta_calls = []
    monkeypatch.setattr(check_approvals.db, "set_meta", lambda k, v: meta_calls.append((k, v)))

    monkeypatch.setattr(
        check_approvals.db, "get_approved_unpublished",
        lambda: [{"id": 1, "title": "t", "content": "c", "tags": "[]"}],
    )
    monkeypatch.setenv("BLOGGER_BLOG_ID", "blog123")
    monkeypatch.setattr(
        check_approvals.post, "post_to_blogger",
        lambda blog_id, title, content, tags: True,
    )

    check_approvals.run()

    assert "approved" in [s for _, s in status_updates]
    assert "published" in [s for _, s in status_updates]
    assert count_calls == [4]
    assert meta_calls == [("telegram_offset", "2")]


def test_run_retries_and_alerts_on_repeated_publish_failure(monkeypatch):
    monkeypatch.setattr(check_approvals.db, "init_db", lambda: None)
    monkeypatch.setattr(check_approvals.db, "get_meta", lambda key, default=None: "0")
    monkeypatch.setattr(check_approvals.telegram_bot, "get_events", lambda offset: ([], 0))
    monkeypatch.setattr(check_approvals.db, "set_meta", lambda k, v: None)
    monkeypatch.setattr(
        check_approvals.db, "get_approved_unpublished",
        lambda: [{"id": 9, "title": "t", "content": "c", "tags": "[]"}],
    )
    monkeypatch.setenv("BLOGGER_BLOG_ID", "blog123")
    monkeypatch.setattr(
        check_approvals.post, "post_to_blogger",
        lambda blog_id, title, content, tags: False,
    )
    monkeypatch.setattr(check_approvals.db, "increment_retry", lambda draft_id: 6)
    alerts = []
    monkeypatch.setattr(check_approvals.telegram_bot, "send_alert", lambda text: alerts.append(text))

    check_approvals.run()

    assert len(alerts) == 1
    assert "9" in alerts[0]


def test_run_does_not_alert_at_exactly_max_retry(monkeypatch):
    monkeypatch.setattr(check_approvals.db, "init_db", lambda: None)
    monkeypatch.setattr(check_approvals.db, "get_meta", lambda key, default=None: "0")
    monkeypatch.setattr(check_approvals.telegram_bot, "get_events", lambda offset: ([], 0))
    monkeypatch.setattr(check_approvals.db, "set_meta", lambda k, v: None)
    monkeypatch.setattr(
        check_approvals.db, "get_approved_unpublished",
        lambda: [{"id": 9, "title": "t", "content": "c", "tags": "[]"}],
    )
    monkeypatch.setenv("BLOGGER_BLOG_ID", "blog123")
    monkeypatch.setattr(
        check_approvals.post, "post_to_blogger",
        lambda blog_id, title, content, tags: False,
    )
    monkeypatch.setattr(check_approvals.db, "increment_retry", lambda draft_id: 5)
    alerts = []
    monkeypatch.setattr(check_approvals.telegram_bot, "send_alert", lambda text: alerts.append(text))

    check_approvals.run()

    assert len(alerts) == 0
