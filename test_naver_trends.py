import requests

import naver_trends


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")

    def json(self):
        return self._payload


def test_get_trend_scores_returns_latest_ratio_per_keyword(monkeypatch):
    monkeypatch.setenv("NAVER_CLIENT_ID", "id")
    monkeypatch.setenv("NAVER_CLIENT_SECRET", "secret")
    monkeypatch.setattr(
        naver_trends.requests, "post",
        lambda url, json, headers, timeout: _FakeResponse({
            "results": [
                {"title": "배당주 추천", "data": [{"ratio": 10.0}, {"ratio": 42.0}]},
                {"title": "ETF 추천", "data": [{"ratio": 5.0}]},
            ]
        }),
    )

    scores = naver_trends.get_trend_scores(["배당주 추천", "ETF 추천"])

    assert scores == {"배당주 추천": 42.0, "ETF 추천": 5.0}


def test_get_trend_scores_batches_over_five_keywords(monkeypatch):
    monkeypatch.setenv("NAVER_CLIENT_ID", "id")
    monkeypatch.setenv("NAVER_CLIENT_SECRET", "secret")
    seen_batches = []

    def fake_post(url, json, headers, timeout):
        batch = [g["groupName"] for g in json["keywordGroups"]]
        seen_batches.append(batch)
        return _FakeResponse({"results": [{"title": kw, "data": [{"ratio": 1.0}]} for kw in batch]})

    monkeypatch.setattr(naver_trends.requests, "post", fake_post)

    keywords = [f"kw{i}" for i in range(7)]
    scores = naver_trends.get_trend_scores(keywords)

    assert len(seen_batches) == 2
    assert len(seen_batches[0]) == 5
    assert len(seen_batches[1]) == 2
    assert len(scores) == 7


def test_get_trend_scores_returns_empty_on_missing_credentials(monkeypatch):
    monkeypatch.delenv("NAVER_CLIENT_ID", raising=False)
    monkeypatch.delenv("NAVER_CLIENT_SECRET", raising=False)

    assert naver_trends.get_trend_scores(["배당주 추천"]) == {}


def test_get_trend_scores_returns_empty_on_network_failure(monkeypatch):
    monkeypatch.setenv("NAVER_CLIENT_ID", "id")
    monkeypatch.setenv("NAVER_CLIENT_SECRET", "secret")

    def raise_error(url, json, headers, timeout):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(naver_trends.requests, "post", raise_error)

    assert naver_trends.get_trend_scores(["배당주 추천"]) == {}


def test_get_trend_scores_empty_list_makes_no_request(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("should not be called")

    monkeypatch.setattr(naver_trends.requests, "post", fail)

    assert naver_trends.get_trend_scores([]) == {}
