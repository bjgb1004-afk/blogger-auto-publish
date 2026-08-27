import generate_drafts


def test_run_stops_when_target_met(monkeypatch):
    monkeypatch.setattr(generate_drafts.db, "init_db", lambda: None)
    monkeypatch.setattr(generate_drafts.config, "get_daily_post_count", lambda: 3)
    monkeypatch.setattr(generate_drafts.db, "get_today_count", lambda: 3)
    called = {"keywords": False}

    def fail_if_called(needed):
        called["keywords"] = True
        return []

    monkeypatch.setattr(generate_drafts.keywords, "get_keywords_to_use", fail_if_called)
    created = generate_drafts.run()
    assert created == 0
    assert called["keywords"] is False


def test_run_creates_needed_count_and_skips_failed_keyword(monkeypatch):
    monkeypatch.setattr(generate_drafts.db, "init_db", lambda: None)
    monkeypatch.setattr(generate_drafts.config, "get_daily_post_count", lambda: 2)
    monkeypatch.setattr(generate_drafts.db, "get_today_count", lambda: 0)
    monkeypatch.setattr(generate_drafts.keywords, "get_keywords_to_use", lambda needed: ["k1", "k2"])

    def fake_generate(keyword):
        if keyword == "k1":
            raise RuntimeError("gemini down")
        return {"title": "t", "content": "c", "tags": []}

    monkeypatch.setattr(generate_drafts.generator, "generate_post", fake_generate)

    inserted = []
    monkeypatch.setattr(
        generate_drafts.db, "insert_draft",
        lambda kw, t, c, tags: inserted.append(kw) or len(inserted),
    )
    monkeypatch.setattr(
        generate_drafts.telegram_bot, "send_draft_notification",
        lambda draft_id, title, keyword, warnings=None: 111,
    )
    monkeypatch.setattr(generate_drafts.db, "set_telegram_msg_id", lambda draft_id, msg_id: None)
    monkeypatch.setattr(generate_drafts.validate, "check_draft", lambda title, content: [])

    created = generate_drafts.run()
    assert created == 1
    assert inserted == ["k2"]


def test_run_passes_validation_warnings_to_telegram(monkeypatch):
    monkeypatch.setattr(generate_drafts.db, "init_db", lambda: None)
    monkeypatch.setattr(generate_drafts.config, "get_daily_post_count", lambda: 1)
    monkeypatch.setattr(generate_drafts.db, "get_today_count", lambda: 0)
    monkeypatch.setattr(generate_drafts.keywords, "get_keywords_to_use", lambda needed: ["k1"])
    monkeypatch.setattr(
        generate_drafts.generator, "generate_post",
        lambda keyword: {"title": "t", "content": "c", "tags": []},
    )
    monkeypatch.setattr(generate_drafts.db, "insert_draft", lambda kw, t, c, tags: 1)
    monkeypatch.setattr(generate_drafts.db, "set_telegram_msg_id", lambda draft_id, msg_id: None)
    monkeypatch.setattr(generate_drafts.validate, "check_draft", lambda title, content: ["본문이 짧음"])

    captured = {}
    monkeypatch.setattr(
        generate_drafts.telegram_bot, "send_draft_notification",
        lambda draft_id, title, keyword, warnings=None: captured.setdefault("warnings", warnings) or 1,
    )

    generate_drafts.run()
    assert captured["warnings"] == ["본문이 짧음"]
