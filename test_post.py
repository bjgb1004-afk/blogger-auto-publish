import post


def test_post_to_blogger_returns_true_on_success(monkeypatch):
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
    assert post.post_to_blogger("blogid", "title", "<p>c</p>", ["t"]) is True


def test_post_to_blogger_returns_false_on_error(monkeypatch):
    def boom():
        raise RuntimeError("auth failed")

    monkeypatch.setattr(post, "get_blogger_service", boom)
    assert post.post_to_blogger("blogid", "title", "<p>c</p>", []) is False
