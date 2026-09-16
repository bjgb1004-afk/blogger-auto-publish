import pytest

import generate_drafts


@pytest.fixture
def stub(monkeypatch):
    """generate_drafts.run()의 모든 부작용을 막고, 트랙별 설정과 호출 기록을 돌려준다."""
    seen = {
        "targets": {"blogspot": 0, "tistory": 0},
        "pool": {"blogspot": [], "tistory": []},
        "inserted": [], "insert_args": [], "notices": [], "tistory_copies": [],
        "posted": [], "statuses": [],
    }

    monkeypatch.setenv("BLOGGER_BLOG_ID", "blog123")
    monkeypatch.delenv("GENERATE_MAX_PER_RUN", raising=False)
    monkeypatch.setattr(generate_drafts.db, "init_db", lambda: None)
    monkeypatch.setattr(generate_drafts, "_apply_count_commands", lambda: None)
    monkeypatch.setattr(generate_drafts.db, "get_unpublished", lambda track: [])
    monkeypatch.setattr(generate_drafts.db, "get_today_count", lambda track: 0)
    monkeypatch.setattr(generate_drafts.db, "update_status", lambda draft_id, status: seen["statuses"].append(status))
    monkeypatch.setattr(generate_drafts.validate, "check_draft", lambda title, content: [])
    monkeypatch.setattr(generate_drafts.pubmed, "find_study", lambda topic: None)
    monkeypatch.setattr(generate_drafts.config, "get_daily_post_count", lambda track: seen["targets"][track])
    monkeypatch.setattr(
        generate_drafts.keywords, "get_keywords_to_use",
        lambda track, needed: seen["pool"][track][:needed],
    )

    def fake_insert(kw, t, c, tags, summary="", image_prompt_en="", track="tistory"):
        seen["inserted"].append(kw)
        seen["insert_args"].append({"title": t, "content": c, "summary": summary, "track": track})
        return len(seen["inserted"])

    monkeypatch.setattr(generate_drafts.db, "insert_draft", fake_insert)

    def fake_post(blog_id, title, content, tags, search_description=""):
        seen["posted"].append(title)
        return "http://blog/x"

    monkeypatch.setattr(generate_drafts.post, "post_to_blogger", fake_post)
    monkeypatch.setattr(
        generate_drafts.telegram_bot, "send_published_notice",
        lambda draft_id, title, url, keyword, warnings=None, image_prompt_en="":
            seen["notices"].append({"url": url, "warnings": warnings, "image": image_prompt_en}),
    )
    monkeypatch.setattr(
        generate_drafts.telegram_bot, "send_tistory_copy",
        lambda title, content, tags, summary="", image_prompt_en="":
            seen["tistory_copies"].append(title),
    )
    return seen


def _generator(monkeypatch, **fields):
    monkeypatch.setattr(
        generate_drafts.generator, "generate_post",
        lambda keyword, track: dict({"title": f"t-{keyword}", "content": "<p>c</p>", "tags": []}, **fields),
    )


def test_run_track_stops_when_target_met(stub, monkeypatch):
    stub["targets"]["tistory"] = 3
    monkeypatch.setattr(generate_drafts.db, "get_today_count", lambda track: 3)

    def fail_if_called(track, needed):
        raise AssertionError("목표를 채웠으면 키워드를 뽑지 않아야 한다")

    monkeypatch.setattr(generate_drafts.keywords, "get_keywords_to_use", fail_if_called)
    assert generate_drafts.run_track("tistory") == 0


def test_tistory_track_sends_manuscript_and_never_posts_to_blogger(stub, monkeypatch):
    stub["targets"]["tistory"] = 2
    stub["pool"]["tistory"] = ["배당주 추천", "ETF 추천"]
    _generator(monkeypatch)

    assert generate_drafts.run_track("tistory") == 2
    assert stub["tistory_copies"] == ["t-배당주 추천", "t-ETF 추천"]
    assert stub["posted"] == []
    assert stub["statuses"] == ["sent", "sent"]
    assert {a["track"] for a in stub["insert_args"]} == {"tistory"}


def test_blogspot_track_publishes_to_blogger_without_tistory_copy(stub, monkeypatch):
    stub["targets"]["blogspot"] = 1
    stub["pool"]["blogspot"] = ["what is gochujang"]
    _generator(monkeypatch)

    assert generate_drafts.run_track("blogspot") == 1
    assert stub["posted"] == ["t-what is gochujang"]
    assert stub["tistory_copies"] == []
    assert stub["statuses"] == ["published"]


def test_run_loops_both_tracks(stub, monkeypatch):
    stub["targets"].update({"blogspot": 1, "tistory": 2})
    stub["pool"].update({"blogspot": ["kimchi guide"], "tistory": ["배당주 추천", "ETF 추천"]})
    _generator(monkeypatch)

    assert generate_drafts.run() == 3
    assert stub["posted"] == ["t-kimchi guide"]
    assert stub["tistory_copies"] == ["t-배당주 추천", "t-ETF 추천"]


def test_generate_skips_failed_keyword(stub, monkeypatch):
    stub["targets"]["tistory"] = 2
    stub["pool"]["tistory"] = ["k1", "k2"]

    def fake_generate(keyword, track):
        if keyword == "k1":
            raise RuntimeError("gemini down")
        return {"title": "t", "content": "c", "tags": []}

    monkeypatch.setattr(generate_drafts.generator, "generate_post", fake_generate)

    assert generate_drafts.run_track("tistory") == 1
    assert stub["inserted"] == ["k2"]


def test_run_sends_validation_warnings_with_published_notice(stub, monkeypatch):
    stub["targets"]["blogspot"] = 1
    stub["pool"]["blogspot"] = ["k1"]
    _generator(monkeypatch)
    monkeypatch.setattr(generate_drafts.validate, "check_draft", lambda title, content: ["본문 너무 짧음"])

    generate_drafts.run_track("blogspot")
    assert stub["notices"][0]["warnings"] == ["본문 너무 짧음"]


def test_run_counts_post_even_when_telegram_notification_fails(stub, monkeypatch):
    stub["targets"]["blogspot"] = 1
    stub["pool"]["blogspot"] = ["k1"]
    _generator(monkeypatch)

    def boom(*a, **k):
        raise RuntimeError("telegram down")

    monkeypatch.setattr(generate_drafts.telegram_bot, "send_published_notice", boom)

    assert generate_drafts.run_track("blogspot") == 1
    assert stub["statuses"] == ["published"]


def test_run_passes_generated_summary_to_insert_draft(stub, monkeypatch):
    stub["targets"]["tistory"] = 1
    stub["pool"]["tistory"] = ["k1"]
    _generator(monkeypatch, summary="생성된 요약")

    generate_drafts.run_track("tistory")
    assert stub["insert_args"][0]["summary"] == "생성된 요약"


def test_pubmed_citation_appended_for_tistory_only(stub, monkeypatch):
    stub["targets"].update({"blogspot": 1, "tistory": 1})
    stub["pool"].update({"blogspot": ["korean sauna guide"], "tistory": ["혈당 낮추는 법"]})
    _generator(monkeypatch, health_topic_en="cortisol stress recovery")
    monkeypatch.setattr(
        generate_drafts.pubmed, "find_study",
        lambda topic: {
            "title": "Stress Recovery Study.", "journal": "J. of Examples",
            "year": "2021", "url": "https://pubmed.ncbi.nlm.nih.gov/999/",
        },
    )

    generate_drafts.run()
    by_track = {a["track"]: a["content"] for a in stub["insert_args"]}
    assert "참고 연구" in by_track["tistory"]
    assert "참고 연구" not in by_track["blogspot"]


def test_run_delivers_backlog_before_generating_and_respects_max_per_run(stub, monkeypatch):
    monkeypatch.setenv("GENERATE_MAX_PER_RUN", "2")
    backlog = [
        {"id": i, "keyword": f"old{i}", "title": f"t{i}", "content": "<p>c</p>",
         "tags": "[]", "summary": "", "image_prompt_en": "", "track": "blogspot"}
        for i in (1, 2, 3)
    ]
    monkeypatch.setattr(generate_drafts.db, "get_unpublished", lambda track: backlog if track == "blogspot" else [])
    stub["targets"].update({"blogspot": 5, "tistory": 5})

    def fail_if_called(track, needed):
        raise AssertionError("백로그가 실행 쿼터를 다 쓰면 생성하면 안 된다")

    monkeypatch.setattr(generate_drafts.keywords, "get_keywords_to_use", fail_if_called)

    assert generate_drafts.run() == 2
    assert stub["posted"] == ["t1", "t2"]


def test_publish_marks_failed_after_max_retry(monkeypatch):
    monkeypatch.setenv("BLOGGER_BLOG_ID", "blog123")
    monkeypatch.setattr(generate_drafts.post, "post_to_blogger", lambda **kw: None)
    monkeypatch.setattr(generate_drafts.db, "increment_retry", lambda draft_id: generate_drafts.MAX_RETRY + 1)
    statuses = []
    monkeypatch.setattr(generate_drafts.db, "update_status", lambda draft_id, status: statuses.append(status))
    monkeypatch.setattr(generate_drafts.telegram_bot, "send_alert", lambda text: None)

    draft = {"id": 1, "keyword": "k", "title": "t", "content": "c", "tags": "[]",
             "summary": "", "track": "blogspot"}
    assert generate_drafts.publish(draft) is False
    assert statuses == ["failed"]


def test_tistory_send_failure_keeps_draft_pending_for_retry(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("telegram down")

    monkeypatch.setattr(generate_drafts.telegram_bot, "send_tistory_copy", boom)
    retries = []
    monkeypatch.setattr(generate_drafts.db, "increment_retry", lambda draft_id: retries.append(draft_id) or 1)
    monkeypatch.setattr(generate_drafts.db, "update_status", lambda draft_id, status: pytest.fail("상태를 바꾸면 안 된다"))

    draft = {"id": 1, "keyword": "k", "title": "t", "content": "c", "tags": "[]",
             "summary": "", "track": "tistory"}
    assert generate_drafts.publish(draft) is False
    assert retries == [1]
