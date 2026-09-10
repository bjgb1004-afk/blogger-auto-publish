import pytest

import generate_drafts


@pytest.fixture
def stub(monkeypatch):
    """Patch every side effect of generate_drafts.run(); return captured calls."""
    seen = {"inserted": [], "notices": [], "tistory": [], "insert_args": []}

    monkeypatch.setenv("BLOGGER_BLOG_ID", "blog123")
    monkeypatch.delenv("GENERATE_MAX_PER_RUN", raising=False)
    monkeypatch.setattr(generate_drafts.db, "init_db", lambda: None)
    monkeypatch.setattr(generate_drafts, "_apply_count_commands", lambda: None)
    monkeypatch.setattr(generate_drafts.db, "get_unpublished", lambda: [])
    monkeypatch.setattr(generate_drafts.db, "get_today_count", lambda: 0)
    monkeypatch.setattr(generate_drafts.db, "update_status", lambda draft_id, status: None)
    monkeypatch.setattr(generate_drafts.validate, "check_draft", lambda title, content: [])
    monkeypatch.setattr(generate_drafts.pubmed, "find_study", lambda topic: None)
    monkeypatch.setattr(generate_drafts, "_vary_for_repost", lambda title, content: (title, content))

    def fake_insert(kw, t, c, tags, summary="", image_prompt_en=""):
        seen["inserted"].append(kw)
        seen["insert_args"].append({"title": t, "content": c, "summary": summary})
        return len(seen["inserted"])

    monkeypatch.setattr(generate_drafts.db, "insert_draft", fake_insert)
    monkeypatch.setattr(
        generate_drafts.post, "post_to_blogger",
        lambda blog_id, title, content, tags, search_description="": "http://blog/x",
    )
    monkeypatch.setattr(
        generate_drafts.telegram_bot, "send_published_notice",
        lambda draft_id, title, url, keyword, warnings=None, image_prompt_en="":
            seen["notices"].append({"url": url, "warnings": warnings, "image": image_prompt_en}),
    )
    monkeypatch.setattr(
        generate_drafts.telegram_bot, "send_tistory_copy",
        lambda title, content, tags, summary="": seen["tistory"].append(title),
    )
    return seen


def test_run_stops_when_target_met(stub, monkeypatch):
    monkeypatch.setattr(generate_drafts.config, "get_daily_post_count", lambda: 3)
    monkeypatch.setattr(generate_drafts.db, "get_today_count", lambda: 3)
    called = {"keywords": False}

    def fail_if_called(needed):
        called["keywords"] = True
        return []

    monkeypatch.setattr(generate_drafts.keywords, "get_keywords_to_use", fail_if_called)
    assert generate_drafts.run() == 0
    assert called["keywords"] is False


def test_run_publishes_needed_count_and_skips_failed_keyword(stub, monkeypatch):
    monkeypatch.setattr(generate_drafts.config, "get_daily_post_count", lambda: 2)
    monkeypatch.setattr(generate_drafts.keywords, "get_keywords_to_use", lambda needed: ["k1", "k2"])

    def fake_generate(keyword):
        if keyword == "k1":
            raise RuntimeError("gemini down")
        return {"title": "t", "content": "c", "tags": []}

    monkeypatch.setattr(generate_drafts.generator, "generate_post", fake_generate)

    assert generate_drafts.run() == 1
    assert stub["inserted"] == ["k2"]
    assert stub["tistory"] == ["t"]


def test_run_sends_validation_warnings_with_published_notice(stub, monkeypatch):
    monkeypatch.setattr(generate_drafts.config, "get_daily_post_count", lambda: 1)
    monkeypatch.setattr(generate_drafts.keywords, "get_keywords_to_use", lambda needed: ["k1"])
    monkeypatch.setattr(
        generate_drafts.generator, "generate_post",
        lambda keyword: {"title": "t", "content": "c", "tags": []},
    )
    monkeypatch.setattr(generate_drafts.validate, "check_draft", lambda title, content: ["본문 너무 짧음"])

    generate_drafts.run()
    assert stub["notices"][0]["warnings"] == ["본문 너무 짧음"]


def test_run_counts_post_even_when_telegram_notification_fails(stub, monkeypatch):
    monkeypatch.setattr(generate_drafts.config, "get_daily_post_count", lambda: 1)
    monkeypatch.setattr(generate_drafts.keywords, "get_keywords_to_use", lambda needed: ["k1"])
    monkeypatch.setattr(
        generate_drafts.generator, "generate_post",
        lambda keyword: {"title": "t", "content": "c", "tags": []},
    )

    def boom(*a, **k):
        raise RuntimeError("telegram down")

    monkeypatch.setattr(generate_drafts.telegram_bot, "send_published_notice", boom)

    assert generate_drafts.run() == 1
    assert stub["inserted"] == ["k1"]


def test_run_passes_generated_summary_to_insert_draft(stub, monkeypatch):
    monkeypatch.setattr(generate_drafts.config, "get_daily_post_count", lambda: 1)
    monkeypatch.setattr(generate_drafts.keywords, "get_keywords_to_use", lambda needed: ["k1"])
    monkeypatch.setattr(
        generate_drafts.generator, "generate_post",
        lambda keyword: {"title": "t", "content": "c", "tags": [], "summary": "생성된 요약"},
    )

    generate_drafts.run()
    assert stub["insert_args"][0]["summary"] == "생성된 요약"


def test_run_appends_pubmed_citation_for_health_posts(stub, monkeypatch):
    monkeypatch.setattr(generate_drafts.config, "get_daily_post_count", lambda: 1)
    monkeypatch.setattr(generate_drafts.keywords, "get_keywords_to_use", lambda needed: ["k1"])
    monkeypatch.setattr(
        generate_drafts.generator, "generate_post",
        lambda keyword: {
            "title": "t", "content": "<p>c</p>", "tags": [],
            "health_topic_en": "cortisol stress recovery",
        },
    )
    monkeypatch.setattr(
        generate_drafts.pubmed, "find_study",
        lambda topic: {
            "title": "Stress Recovery Study.", "journal": "J. of Examples",
            "year": "2021", "url": "https://pubmed.ncbi.nlm.nih.gov/999/",
        },
    )

    generate_drafts.run()
    content = stub["insert_args"][0]["content"]
    assert "참고 연구" in content
    assert "https://pubmed.ncbi.nlm.nih.gov/999/" in content


def test_run_publishes_backlog_before_generating_and_respects_max_per_run(stub, monkeypatch):
    monkeypatch.setenv("GENERATE_MAX_PER_RUN", "2")
    backlog = [
        {"id": i, "keyword": f"old{i}", "title": f"t{i}", "content": "<p>c</p>",
         "tags": "[]", "summary": "", "image_prompt_en": ""}
        for i in (1, 2, 3)
    ]
    monkeypatch.setattr(generate_drafts.db, "get_unpublished", lambda: backlog)
    monkeypatch.setattr(generate_drafts.config, "get_daily_post_count", lambda: 5)

    def fail_if_called(needed):
        raise AssertionError("should not generate while backlog fills the run quota")

    monkeypatch.setattr(generate_drafts.keywords, "get_keywords_to_use", fail_if_called)

    assert generate_drafts.run() == 2
    assert stub["tistory"] == ["t1", "t2"]


def test_publish_marks_failed_after_max_retry(monkeypatch):
    monkeypatch.setenv("BLOGGER_BLOG_ID", "blog123")
    monkeypatch.setattr(generate_drafts.post, "post_to_blogger", lambda **kw: None)
    monkeypatch.setattr(generate_drafts.db, "increment_retry", lambda draft_id: generate_drafts.MAX_RETRY + 1)
    statuses = []
    monkeypatch.setattr(generate_drafts.db, "update_status", lambda draft_id, status: statuses.append(status))
    monkeypatch.setattr(generate_drafts.telegram_bot, "send_alert", lambda text: None)

    draft = {"id": 1, "keyword": "k", "title": "t", "content": "c", "tags": "[]", "summary": ""}
    assert generate_drafts.publish(draft) is False
    assert statuses == ["failed"]
