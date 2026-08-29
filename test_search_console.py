import search_console


class _FakeQuery:
    def __init__(self, response):
        self._response = response

    def execute(self):
        return self._response


class _FakeSearchAnalytics:
    def __init__(self, response):
        self._response = response
        self.captured_site = None
        self.captured_body = None

    def query(self, siteUrl, body):
        self.captured_site = siteUrl
        self.captured_body = body
        return _FakeQuery(self._response)


class _FakeService:
    def __init__(self, response):
        self.searchanalytics_obj = _FakeSearchAnalytics(response)

    def searchanalytics(self):
        return self.searchanalytics_obj


def test_get_query_performance_returns_rows(monkeypatch):
    fake = _FakeService({"rows": [
        {"keys": ["배당주 추천"], "clicks": 3, "impressions": 40, "ctr": 0.075, "position": 12.5}
    ]})
    monkeypatch.setattr(search_console, "get_service", lambda: fake)

    rows = search_console.get_query_performance("https://example.com/", "2026-08-01", "2026-08-28")

    assert rows == [{"keys": ["배당주 추천"], "clicks": 3, "impressions": 40, "ctr": 0.075, "position": 12.5}]
    assert fake.searchanalytics_obj.captured_site == "https://example.com/"
    assert fake.searchanalytics_obj.captured_body["dimensions"] == ["query"]


def test_get_query_performance_returns_empty_list_when_no_rows(monkeypatch):
    fake = _FakeService({})
    monkeypatch.setattr(search_console, "get_service", lambda: fake)

    rows = search_console.get_query_performance("https://example.com/", "2026-08-01", "2026-08-28")

    assert rows == []


def test_get_query_performance_uses_custom_dimensions(monkeypatch):
    fake = _FakeService({"rows": []})
    monkeypatch.setattr(search_console, "get_service", lambda: fake)

    search_console.get_query_performance("https://example.com/", "2026-08-01", "2026-08-28", dimensions=["page"])

    assert fake.searchanalytics_obj.captured_body["dimensions"] == ["page"]
