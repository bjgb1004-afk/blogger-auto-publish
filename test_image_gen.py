import requests

import image_gen


class _FakeResponse:
    def __init__(self, url, status_code=200):
        self.url = url
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")


def test_generate_image_url_returns_resolved_url(monkeypatch):
    monkeypatch.setattr(
        image_gen.requests, "get",
        lambda url, params, timeout: _FakeResponse(url + "?seed=1"),
    )

    result = image_gen.generate_image_url("배당주")

    assert result.startswith("https://image.pollinations.ai/prompt/")
    assert result.endswith("?seed=1")


def test_generate_image_url_is_deterministic_per_keyword(monkeypatch):
    seen_params = []
    monkeypatch.setattr(
        image_gen.requests, "get",
        lambda url, params, timeout: seen_params.append(params) or _FakeResponse(url),
    )

    image_gen.generate_image_url("배당주")
    image_gen.generate_image_url("배당주")

    assert seen_params[0]["seed"] == seen_params[1]["seed"]


def test_generate_image_url_returns_none_on_failure(monkeypatch):
    def raise_error(url, params, timeout):
        raise requests.ConnectionError("network down")

    monkeypatch.setattr(image_gen.requests, "get", raise_error)

    assert image_gen.generate_image_url("배당주") is None
