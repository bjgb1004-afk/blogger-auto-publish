import logging

from pytrends.request import TrendReq

import db

EVERGREEN_KEYWORDS = {
    "주식/금융/재테크/경제": ["배당주 추천", "ETF 추천", "예적금 금리 비교", "청약통장 활용법"],
    "건강": ["공복 혈당 낮추는 법", "간헐적 단식 효과", "허리 디스크 스트레칭"],
    "맛집": ["집들이 요리 추천", "혼밥 메뉴 추천", "다이어트 도시락 레시피"],
}


def get_trend_keywords(limit: int = 10) -> list:
    pytrends = TrendReq(hl="ko-KR", tz=540)
    df = pytrends.trending_searches(pn="south_korea")
    return df[0].tolist()[:limit]


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

    result = []
    for kw in candidates:
        if kw in recent or kw in result:
            continue
        result.append(kw)
        if len(result) >= needed_count:
            break
    return result
