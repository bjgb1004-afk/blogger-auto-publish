import keywords


def test_get_evergreen_keywords_nonempty():
    kws = keywords.get_evergreen_keywords()
    assert len(kws) > 0
    assert all(isinstance(k, str) for k in kws)


def test_get_keywords_to_use_excludes_recent(monkeypatch):
    monkeypatch.setattr(keywords, "get_trend_keywords", lambda limit=10: ["트렌드1", "트렌드2"])
    monkeypatch.setattr(keywords.db, "get_recent_keywords", lambda days=30: {"트렌드1"})
    result = keywords.get_keywords_to_use(needed_count=2)
    assert "트렌드1" not in result
    assert len(result) == 2


def test_get_keywords_to_use_falls_back_when_trends_fail(monkeypatch):
    def boom(limit=10):
        raise RuntimeError("network down")
    monkeypatch.setattr(keywords, "get_trend_keywords", boom)
    monkeypatch.setattr(keywords.db, "get_recent_keywords", lambda days=30: set())
    result = keywords.get_keywords_to_use(needed_count=1)
    assert len(result) == 1
