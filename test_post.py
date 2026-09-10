import post


def test_post_to_blogger_returns_url_on_success(monkeypatch):
    class FakePosts:
        def insert(self, blogId, body):
            class Req:
                def execute(self):
                    return {"title": body["title"], "url": "http://example.com"}
            return Req()

    class FakeService:
        def posts(self):
            return FakePosts()

    monkeypatch.setattr(post, "get_blogger_service", lambda: FakeService())
    assert post.post_to_blogger("blogid", "title", "<p>c</p>", ["t"]) == "http://example.com"


def test_post_to_blogger_returns_none_on_error(monkeypatch):
    def boom():
        raise RuntimeError("auth failed")

    monkeypatch.setattr(post, "get_blogger_service", boom)
    assert post.post_to_blogger("blogid", "title", "<p>c</p>", []) is None


def test_post_to_blogger_includes_search_description_when_provided(monkeypatch):
    captured = {}

    class FakePosts:
        def insert(self, blogId, body):
            captured["body"] = body
            class Req:
                def execute(self):
                    return {"title": body["title"], "url": "http://example.com"}
            return Req()

    class FakeService:
        def posts(self):
            return FakePosts()

    monkeypatch.setattr(post, "get_blogger_service", lambda: FakeService())
    post.post_to_blogger("blogid", "title", "<p>c</p>", ["t"], search_description="검색 요약")
    assert captured["body"]["searchDescription"] == "검색 요약"


def test_post_to_blogger_omits_search_description_when_empty(monkeypatch):
    captured = {}

    class FakePosts:
        def insert(self, blogId, body):
            captured["body"] = body
            class Req:
                def execute(self):
                    return {"title": body["title"], "url": "http://example.com"}
            return Req()

    class FakeService:
        def posts(self):
            return FakePosts()

    monkeypatch.setattr(post, "get_blogger_service", lambda: FakeService())
    post.post_to_blogger("blogid", "title", "<p>c</p>", ["t"])
    assert "searchDescription" not in captured["body"]
