import setup_pages


class _ListReq:
    def __init__(self, titles):
        self._titles = titles

    def execute(self):
        return {"items": [{"title": t} for t in self._titles]}


class _InsertReq:
    def __init__(self, body):
        self._body = body

    def execute(self):
        return {"title": self._body["title"]}


class _FakePages:
    def __init__(self, existing_titles):
        self._existing_titles = existing_titles
        self.inserted = []

    def list(self, blogId):
        return _ListReq(self._existing_titles)

    def insert(self, blogId, body):
        self.inserted.append(body)
        return _InsertReq(body)


class _FakeService:
    def __init__(self, existing_titles):
        self.pages_obj = _FakePages(existing_titles)

    def pages(self):
        return self.pages_obj


def test_build_pages_includes_contact_email():
    pages = setup_pages.build_pages("me@example.com")
    assert {p["title"] for p in pages} == {"개인정보처리방침", "소개", "연락처"}
    contact_page = next(p for p in pages if p["title"] == "연락처")
    assert "me@example.com" in contact_page["content"]


def test_create_required_pages_creates_missing_pages(monkeypatch):
    fake_service = _FakeService(existing_titles=[])
    monkeypatch.setattr(setup_pages.post, "get_blogger_service", lambda: fake_service)

    created = setup_pages.create_required_pages("blog123", "me@example.com")

    assert created == ["개인정보처리방침", "소개", "연락처"]
    assert len(fake_service.pages_obj.inserted) == 3


def test_create_required_pages_skips_existing_pages(monkeypatch):
    fake_service = _FakeService(existing_titles=["개인정보처리방침"])
    monkeypatch.setattr(setup_pages.post, "get_blogger_service", lambda: fake_service)

    created = setup_pages.create_required_pages("blog123", "me@example.com")

    assert created == ["소개", "연락처"]
    assert len(fake_service.pages_obj.inserted) == 2
