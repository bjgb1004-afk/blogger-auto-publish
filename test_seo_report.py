import seo_report


def test_get_site_url_reads_blog_url_via_blogger_api(monkeypatch):
    class FakeBlogs:
        def get(self, blogId):
            class Req:
                def execute(self):
                    return {"url": "https://example.blogspot.com/"}
            assert blogId == "blog123"
            return Req()

    class FakeService:
        def blogs(self):
            return FakeBlogs()

    monkeypatch.setenv("BLOGGER_BLOG_ID", "blog123")
    monkeypatch.setattr(seo_report, "get_blogger_service", lambda: FakeService())

    assert seo_report.get_site_url() == "https://example.blogspot.com/"
