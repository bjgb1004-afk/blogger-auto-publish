import pytest
from google.genai import errors as genai_errors

import generator


def _server_error():
    return genai_errors.ServerError(503, {"error": {"message": "overloaded"}})


def test_parse_response_plain_json():
    text = '{"title": "제목", "content": "<p>본문</p>", "tags": ["a", "b"], "summary": "요약"}'
    result = generator._parse_response(text)
    assert result == {
        "title": "제목", "content": "<p>본문</p>", "tags": ["a", "b"],
        "summary": "요약", "health_topic_en": "", "image_prompt_en": "",
    }


def test_parse_response_passes_through_health_topic_en():
    text = '{"title": "제목", "content": "<p>c</p>", "health_topic_en": "cortisol stress"}'
    result = generator._parse_response(text)
    assert result["health_topic_en"] == "cortisol stress"


def test_parse_response_defaults_summary_when_missing():
    text = '{"title": "제목", "content": "<p>본문</p>"}'
    result = generator._parse_response(text)
    assert result["summary"] == ""


def test_parse_response_strips_markdown_fence():
    text = '```json\n{"title": "제목", "content": "<p>c</p>", "tags": []}\n```'
    result = generator._parse_response(text)
    assert result["title"] == "제목"


class _FakeResponse:
    def __init__(self, text):
        self.text = text


class _FakeModels:
    def __init__(self, text):
        self._text = text

    def generate_content(self, model, contents):
        return _FakeResponse(self._text)


class _FakeClient:
    def __init__(self, text):
        self.models = _FakeModels(text)


def test_generate_post_uses_client(monkeypatch):
    fake_text = '{"title": "제목", "content": "<p>c</p>", "tags": ["x"]}'
    monkeypatch.setattr(generator, "_get_client", lambda: _FakeClient(fake_text))
    result = generator.generate_post("키워드")
    assert result["title"] == "제목"
    assert result["tags"] == ["x"]


def test_rewrite_for_repost_returns_new_title_and_intro(monkeypatch):
    fake_text = '{"title": "새 제목", "intro": "<p>새 도입부</p>"}'
    monkeypatch.setattr(generator, "_get_client", lambda: _FakeClient(fake_text))
    result = generator.rewrite_for_repost("원래 제목", "<p>원래 도입부</p>")
    assert result == {"title": "새 제목", "intro": "<p>새 도입부</p>"}


def test_rewrite_for_repost_strips_markdown_fence(monkeypatch):
    fake_text = '```json\n{"title": "새 제목", "intro": "<p>새 도입부</p>"}\n```'
    monkeypatch.setattr(generator, "_get_client", lambda: _FakeClient(fake_text))
    result = generator.rewrite_for_repost("원래 제목", "<p>원래 도입부</p>")
    assert result["title"] == "새 제목"


class _FlakyModels:
    def __init__(self, fail_times, text):
        self._fail_times = fail_times
        self._text = text
        self.calls = 0

    def generate_content(self, model, contents):
        self.calls += 1
        if self.calls <= self._fail_times:
            raise _server_error()
        return _FakeResponse(self._text)


class _FlakyClient:
    def __init__(self, fail_times, text):
        self.models = _FlakyModels(fail_times, text)


def test_generate_post_retries_on_server_error_then_succeeds(monkeypatch):
    monkeypatch.setattr(generator, "RETRY_BACKOFF_SECONDS", 0)
    fake_text = '{"title": "제목", "content": "<p>c</p>", "tags": ["x"]}'
    client = _FlakyClient(fail_times=2, text=fake_text)
    monkeypatch.setattr(generator, "_get_client", lambda: client)
    result = generator.generate_post("키워드")
    assert result["title"] == "제목"
    assert client.models.calls == 3


def test_generate_post_raises_after_exhausting_retries(monkeypatch):
    monkeypatch.setattr(generator, "RETRY_BACKOFF_SECONDS", 0)
    client = _FlakyClient(fail_times=99, text="{}")
    monkeypatch.setattr(generator, "_get_client", lambda: client)
    with pytest.raises(genai_errors.ServerError):
        generator.generate_post("키워드")
    assert client.models.calls == generator.MAX_RETRIES
