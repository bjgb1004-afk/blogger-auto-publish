import telegram_bot


class _FakeResp:
    def __init__(self, json_data):
        self._json = json_data

    def raise_for_status(self):
        pass

    def json(self):
        return self._json


def test_send_draft_notification(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    captured = {}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        return _FakeResp({"result": {"message_id": 99}})

    monkeypatch.setattr(telegram_bot.requests, "post", fake_post)
    msg_id = telegram_bot.send_draft_notification(5, "제목", "키워드")
    assert msg_id == 99
    assert "tok" in captured["url"]
    assert captured["json"]["chat_id"] == "123"
    assert "approve:5" in str(captured["json"]["reply_markup"])


def test_send_draft_notification_includes_image_command(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    captured = {}

    def fake_post(url, json, timeout):
        captured["json"] = json
        return _FakeResp({"result": {"message_id": 1}})

    monkeypatch.setattr(telegram_bot.requests, "post", fake_post)
    telegram_bot.send_draft_notification(5, "제목", "키워드", image_prompt_en="lower back spine anatomy diagram")
    text = captured["json"]["text"]
    assert "lower back spine anatomy diagram" in text
    assert "얼굴" in text


def test_send_draft_notification_includes_content_preview_without_html(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    captured = {}

    def fake_post(url, json, timeout):
        captured["json"] = json
        return _FakeResp({"result": {"message_id": 1}})

    monkeypatch.setattr(telegram_bot.requests, "post", fake_post)
    telegram_bot.send_draft_notification(
        5, "제목", "키워드", content="<h2>소제목</h2><p>본문 내용입니다.</p>"
    )
    text = captured["json"]["text"]
    assert "<h2>" not in text
    assert "소제목" in text and "본문 내용입니다." in text


def test_send_draft_notification_truncates_long_content_preview(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    captured = {}

    def fake_post(url, json, timeout):
        captured["json"] = json
        return _FakeResp({"result": {"message_id": 1}})

    monkeypatch.setattr(telegram_bot.requests, "post", fake_post)
    long_content = "<p>" + "가" * 2000 + "</p>"
    telegram_bot.send_draft_notification(5, "제목", "키워드", content=long_content)
    text = captured["json"]["text"]
    assert text.endswith("…")
    assert len(text) < len(long_content)
    assert "⚠" not in captured["json"]["text"]


def test_send_draft_notification_includes_warnings(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    captured = {}

    def fake_post(url, json, timeout):
        captured["json"] = json
        return _FakeResp({"result": {"message_id": 100}})

    monkeypatch.setattr(telegram_bot.requests, "post", fake_post)
    telegram_bot.send_draft_notification(6, "제목", "키워드", warnings=["본문이 짧음"])
    assert "본문이 짧음" in captured["json"]["text"]


def test_get_events_parses_approve_and_count(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    updates = [
        {"update_id": 1, "callback_query": {"id": "cq1", "data": "approve:7"}},
        {"update_id": 2, "message": {"text": "/count 3", "chat": {"id": 123}}},
    ]
    monkeypatch.setattr(
        telegram_bot.requests, "get",
        lambda url, params, timeout: _FakeResp({"result": updates}),
    )
    events, next_offset = telegram_bot.get_events(offset=0)
    assert next_offset == 3
    assert events[0] == {"type": "approve", "draft_id": 7, "callback_query_id": "cq1"}
    assert events[1] == {"type": "count", "value": 3}


def test_send_alert_posts_message(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    captured = {}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        return _FakeResp({})

    monkeypatch.setattr(telegram_bot.requests, "post", fake_post)
    telegram_bot.send_alert("경고 메시지")
    assert captured["json"]["text"] == "경고 메시지"
    assert captured["json"]["chat_id"] == "123"


def test_send_tistory_copy_sends_header_then_content(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    sent = []

    def fake_post(url, json, timeout):
        sent.append(json["text"])
        return _FakeResp({})

    monkeypatch.setattr(telegram_bot.requests, "post", fake_post)
    telegram_bot.send_tistory_copy("제목", "<h2>소제목</h2><p>본문 <strong>강조</strong></p>", ["a", "b"], summary="요약")

    assert "제목" in sent[0]
    assert "a, b" in sent[0]
    assert "요약" in sent[0]
    assert "HTML" not in sent[0]
    assert "<" not in sent[1]
    assert "▶ 소제목" in sent[1]
    assert "본문 강조" in sent[1]


def test_to_plain_text_converts_links_and_images():
    html_content = '<img src="http://x/i.png" alt="a" /><p>본문 <a href="http://x/y" target="_blank">참고</a></p>'
    plain = telegram_bot._to_plain_text(html_content)
    assert "[이미지: http://x/i.png]" in plain
    assert "참고 (http://x/y)" in plain
    assert "<" not in plain


def test_send_tistory_copy_chunks_long_content(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    sent = []

    def fake_post(url, json, timeout):
        sent.append(json["text"])
        return _FakeResp({})

    monkeypatch.setattr(telegram_bot.requests, "post", fake_post)
    long_content = "가" * 8000
    telegram_bot.send_tistory_copy("제목", long_content, [])

    body_chunks = sent[1:]
    assert len(body_chunks) == 3
    assert "".join(body_chunks) == long_content


def test_answer_callback_posts_response(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    captured = {}

    def fake_post(url, json, timeout):
        captured["json"] = json
        return _FakeResp({})

    monkeypatch.setattr(telegram_bot.requests, "post", fake_post)
    telegram_bot.answer_callback("cq123", "승인됨")
    assert captured["json"]["callback_query_id"] == "cq123"
    assert captured["json"]["text"] == "승인됨"


def test_get_events_advances_offset_past_non_event_updates(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    updates = [
        {"update_id": 5, "message": {"text": "hello", "chat": {"id": 123}}},
        {"update_id": 6, "message": {"text": "/count abc", "chat": {"id": 123}}},
        {"update_id": 7, "callback_query": {"id": "cqX", "data": "approve:1"}},
    ]
    monkeypatch.setattr(
        telegram_bot.requests, "get",
        lambda url, params, timeout: _FakeResp({"result": updates}),
    )
    events, next_offset = telegram_bot.get_events(offset=0)
    assert next_offset == 8
    assert len(events) == 1
    assert events[0] == {"type": "approve", "draft_id": 1, "callback_query_id": "cqX"}


def test_get_events_ignores_count_from_wrong_chat(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    updates = [
        {"update_id": 1, "message": {"text": "/count 5", "chat": {"id": 999}}},
    ]
    monkeypatch.setattr(
        telegram_bot.requests, "get",
        lambda url, params, timeout: _FakeResp({"result": updates}),
    )
    events, next_offset = telegram_bot.get_events(offset=0)
    assert events == []
    assert next_offset == 2


def test_get_events_clamps_count_value(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    updates = [
        {"update_id": 1, "message": {"text": "/count 500", "chat": {"id": 123}}},
    ]
    monkeypatch.setattr(
        telegram_bot.requests, "get",
        lambda url, params, timeout: _FakeResp({"result": updates}),
    )
    events, next_offset = telegram_bot.get_events(offset=0)
    assert events == []
    assert next_offset == 2
