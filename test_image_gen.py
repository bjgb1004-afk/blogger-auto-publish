import requests

import image_gen


class _FakeResponse:
    def __init__(self, content, headers=None, status_code=200):
        self.content = content
        self.headers = headers or {"content-type": "image/jpeg"}
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")


def test_generate_image_data_uri_returns_base64_data_uri(monkeypatch):
    monkeypatch.setattr(image_gen.requests, "get", lambda url, params, timeout: _FakeResponse(b"fakebytes"))

    result = image_gen.generate_image_data_uri("배당주")

    assert result == "data:image/jpeg;base64,ZmFrZWJ5dGVz"


def test_generate_image_data_uri_returns_none_on_failure(monkeypatch):
    def raise_error(url, params, timeout):
        raise requests.ConnectionError("network down")

    monkeypatch.setattr(image_gen.requests, "get", raise_error)

    assert image_gen.generate_image_data_uri("배당주") is None
