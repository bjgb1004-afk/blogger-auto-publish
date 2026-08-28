import generator


def test_parse_response_plain_json():
    text = '{"title": "제목", "content": "<p>본문</p>", "tags": ["a", "b"], "summary": "요약"}'
    result = generator._parse_response(text)
    assert result == {"title": "제목", "content": "<p>본문</p>", "tags": ["a", "b"], "summary": "요약"}


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
