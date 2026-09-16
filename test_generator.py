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


class _PromptCapturingModels:
    def __init__(self):
        self.prompt = None

    def generate_content(self, model, contents):
        self.prompt = contents
        return _FakeResponse('{"title": "t", "content": "<p>c</p>", "tags": []}')


class _PromptCapturingClient:
    def __init__(self):
        self.models = _PromptCapturingModels()


def test_blogspot_track_uses_english_kculture_prompt(monkeypatch):
    client = _PromptCapturingClient()
    monkeypatch.setattr(generator, "_get_client", lambda: client)

    generator.generate_post("what is gochujang", track="blogspot")

    prompt = client.models.prompt
    assert "what is gochujang" in prompt
    assert "Korean culture" in prompt
    assert "진단과 처방" not in prompt  # 면책 문구 로직은 티스토리 전용
    assert "health_topic_en" not in prompt


def test_tistory_track_keeps_korean_prompt(monkeypatch):
    client = _PromptCapturingClient()
    monkeypatch.setattr(generator, "_get_client", lambda: client)

    generator.generate_post("배당주 추천", track="tistory")

    assert "health_topic_en" in client.models.prompt

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
