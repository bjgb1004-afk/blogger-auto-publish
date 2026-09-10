import telegram_bot


class _FakeResp:
    def __init__(self, json_data):
        self._json = json_data

    def raise_for_status(self):
        pass

    def json(self):
        return self._json


def test_get_events_parses_count(monkeypatch):
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
    assert events == [{"type": "count", "value": 3}]  # 승인 콜백은 더 이상 처리하지 않음


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
    assert events == []


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
