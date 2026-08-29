import logging

from pytrends.request import TrendReq

import db
import naver_trends

EVERGREEN_KEYWORDS = {
    "주식/금융/재테크/경제": ["배당주 추천", "ETF 추천", "예적금 금리 비교", "청약통장 활용법"],
    "건강": ["공복 혈당 낮추는 법", "간헐적 단식 효과", "허리 디스크 스트레칭"],
}


def get_trend_keywords(limit: int = 10) -> list:
    pytrends = TrendReq(hl="ko-KR", tz=540)
    results = []
    for seed in get_evergreen_keywords():
        if len(results) >= limit:
            break
        pytrends.build_payload([seed], timeframe="now 7-d", geo="KR")
        related = pytrends.related_queries().get(seed, {})
        rising = related.get("rising")
        if rising is None:
            continue
        for q in rising["query"].tolist():
            if q not in results:
                results.append(q)
            if len(results) >= limit:
                break
    return results[:limit]


def get_evergreen_keywords() -> list:
    result = []
    for topic_list in EVERGREEN_KEYWORDS.values():
        result.extend(topic_list)
    return result


def get_keywords_to_use(needed_count: int) -> list:
    recent = db.get_recent_keywords(days=30)
    candidates = []
    try:
        candidates.extend(get_trend_keywords())
    except Exception as e:
        logging.warning("get_trend_keywords failed, falling back to evergreen only: %s", e)
    candidates.extend(get_evergreen_keywords())

    unique = []
    for kw in candidates:
        if kw in recent or kw in unique:
            continue
        unique.append(kw)

    try:
        scores = naver_trends.get_trend_scores(unique)
        unique.sort(key=lambda kw: scores.get(kw, 0), reverse=True)
    except Exception as e:
        logging.warning("naver_trends failed, keeping original order: %s", e)

    return unique[:needed_count]
