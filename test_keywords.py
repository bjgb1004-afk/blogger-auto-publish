import keywords
import pandas as pd


def test_evergreen_keywords_scoped_to_finance_and_health():
    assert set(keywords.EVERGREEN_KEYWORDS.keys()) == {"주식/금융/재테크/경제", "건강"}
    assert "집들이 요리 추천" not in keywords.get_evergreen_keywords()


def test_get_evergreen_keywords_nonempty():
    kws = keywords.get_evergreen_keywords()
    assert len(kws) > 0
    assert all(isinstance(k, str) for k in kws)


def test_get_keywords_to_use_excludes_recent(monkeypatch):
    monkeypatch.setattr(keywords, "get_trend_keywords", lambda limit=10: ["트렌드1", "트렌드2"])
    monkeypatch.setattr(keywords.db, "get_recent_keywords", lambda days=30: {"트렌드1"})
    monkeypatch.setattr(keywords.naver_trends, "get_trend_scores", lambda kws: {})
    result = keywords.get_keywords_to_use(needed_count=2)
    assert "트렌드1" not in result
    assert len(result) == 2


def test_get_keywords_to_use_falls_back_when_trends_fail(monkeypatch):
    def boom(limit=10):
        raise RuntimeError("network down")
    monkeypatch.setattr(keywords, "get_trend_keywords", boom)
    monkeypatch.setattr(keywords.db, "get_recent_keywords", lambda days=30: set())
    monkeypatch.setattr(keywords.naver_trends, "get_trend_scores", lambda kws: {})
    result = keywords.get_keywords_to_use(needed_count=1)
    assert len(result) == 1


def test_get_keywords_to_use_prioritizes_higher_naver_trend_score(monkeypatch):
    monkeypatch.setattr(keywords, "get_trend_keywords", lambda limit=10: [])
    monkeypatch.setattr(keywords, "get_evergreen_keywords", lambda: ["배당주 추천", "ETF 추천", "예적금 금리 비교"])
    monkeypatch.setattr(keywords.db, "get_recent_keywords", lambda days=30: set())
    monkeypatch.setattr(
        keywords.naver_trends, "get_trend_scores",
        lambda kws: {"배당주 추천": 10.0, "ETF 추천": 80.0, "예적금 금리 비교": 30.0},
    )

    result = keywords.get_keywords_to_use(needed_count=3)

    assert result == ["ETF 추천", "예적금 금리 비교", "배당주 추천"]


def test_get_keywords_to_use_keeps_order_when_naver_lookup_fails(monkeypatch):
    monkeypatch.setattr(keywords, "get_trend_keywords", lambda limit=10: [])
    monkeypatch.setattr(keywords, "get_evergreen_keywords", lambda: ["배당주 추천", "ETF 추천"])
    monkeypatch.setattr(keywords.db, "get_recent_keywords", lambda days=30: set())

    def boom(kws):
        raise RuntimeError("naver api down")
    monkeypatch.setattr(keywords.naver_trends, "get_trend_scores", boom)

    result = keywords.get_keywords_to_use(needed_count=2)

    assert result == ["배당주 추천", "ETF 추천"]


class _FakePyTrends:
    def __init__(self, rising_by_seed):
        self._rising_by_seed = rising_by_seed
        self.built_seeds = []

    def build_payload(self, kw_list, timeframe=None, geo=None):
        self.built_seeds.append(kw_list[0])

    def related_queries(self):
        seed = self.built_seeds[-1]
        rising = self._rising_by_seed.get(seed)
        return {seed: {"top": None, "rising": rising}}


def test_get_trend_keywords_uses_evergreen_niches_as_seeds(monkeypatch):
    monkeypatch.setattr(keywords, "get_evergreen_keywords", lambda: ["배당주 추천", "공복 혈당 낮추는 법"])
    fake = _FakePyTrends({
        "배당주 추천": pd.DataFrame({"query": ["고배당 ETF 순위"]}),
        "공복 혈당 낮추는 법": pd.DataFrame({"query": ["저탄수 식단 추천"]}),
    })
    monkeypatch.setattr(keywords, "TrendReq", lambda hl, tz: fake)

    result = keywords.get_trend_keywords(limit=10)

    assert result == ["고배당 ETF 순위", "저탄수 식단 추천"]
    assert fake.built_seeds == ["배당주 추천", "공복 혈당 낮추는 법"]


def test_get_trend_keywords_skips_seed_with_no_rising_data(monkeypatch):
    monkeypatch.setattr(keywords, "get_evergreen_keywords", lambda: ["배당주 추천", "ETF 추천"])
    fake = _FakePyTrends({"배당주 추천": None, "ETF 추천": pd.DataFrame({"query": ["ETF 추천 순위"]})})
    monkeypatch.setattr(keywords, "TrendReq", lambda hl, tz: fake)

    result = keywords.get_trend_keywords(limit=10)

    assert result == ["ETF 추천 순위"]


def test_get_trend_keywords_respects_limit(monkeypatch):
    monkeypatch.setattr(keywords, "get_evergreen_keywords", lambda: ["배당주 추천"])
    fake = _FakePyTrends({"배당주 추천": pd.DataFrame({"query": ["a", "b", "c"]})})
    monkeypatch.setattr(keywords, "TrendReq", lambda hl, tz: fake)

    result = keywords.get_trend_keywords(limit=2)

    assert result == ["a", "b"]
