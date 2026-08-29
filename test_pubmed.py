import requests

import pubmed


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")

    def json(self):
        return self._payload


def test_find_study_returns_none_for_empty_topic():
    assert pubmed.find_study("") is None


def test_find_study_returns_none_when_no_results(monkeypatch):
    monkeypatch.setattr(
        pubmed.requests, "get",
        lambda url, params, timeout: _FakeResponse({"esearchresult": {"idlist": []}}),
    )
    assert pubmed.find_study("some topic") is None


def test_find_study_returns_paper_details(monkeypatch):
    def fake_get(url, params, timeout):
        if url == pubmed.ESEARCH_URL:
            return _FakeResponse({"esearchresult": {"idlist": ["12345"]}})
        return _FakeResponse({"result": {"12345": {
            "title": "Some Study Title.",
            "fulljournalname": "Journal of Examples",
            "pubdate": "2021 Mar",
        }}})

    monkeypatch.setattr(pubmed.requests, "get", fake_get)

    result = pubmed.find_study("some topic")

    assert result == {
        "title": "Some Study Title.",
        "journal": "Journal of Examples",
        "year": "2021",
        "url": "https://pubmed.ncbi.nlm.nih.gov/12345/",
    }


def test_find_study_returns_none_on_network_failure(monkeypatch):
    def raise_error(url, params, timeout):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(pubmed.requests, "get", raise_error)

    assert pubmed.find_study("some topic") is None
