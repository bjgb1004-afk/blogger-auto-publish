import logging

from pytrends.request import TrendReq

import db
import naver_trends

EVERGREEN_KEYWORDS = {
    "주식/금융/재테크/경제": [
        "배당주 추천", "ETF 추천", "예적금 금리 비교", "청약통장 활용법",
        "신용점수 올리는 법", "개인연금 가입 방법", "퇴직연금 DC형 DB형 차이", "IRP 계좌 세액공제",
        "연말정산 절세 팁", "부업 추천", "대출 갈아타기 방법", "전세자금대출 조건",
        "주택청약 가점 계산법", "채권투자 입문", "리츠 투자 장단점", "금 투자 방법",
        "달러 투자 타이밍", "파킹통장 추천", "재테크 습관 만들기", "비상금 모으는 법",
        "신용카드 혜택 비교", "체크카드 캐시백 추천", "청년도약계좌 조건", "청년희망적금 후속 상품",
        "국민연금 조기수령 연기수령 비교", "실비보험 가입 시 주의사항", "자동차보험 저렴하게 가입하는 법",
        "종잣돈 모으는 법", "짠테크 방법", "가계부 작성법", "주식 초보 투자 가이드",
        "미국주식 투자 방법", "해외주식 세금", "배당금 재투자 전략", "인덱스펀드 액티브펀드 차이",
        "연금저축펀드 추천", "ISA 계좌 활용법", "부동산 경매 입문", "오피스텔 투자 주의사항",
        "갭투자 리스크", "전세보증금 반환보증", "월세 전세 비교", "신용대출 한도 늘리는 법",
        "마이너스통장 활용법", "카드론 대환대출", "개인회생 조건", "신용회복위원회 이용법",
        "국세환급금 조회 방법", "연말정산 부양가족 공제", "사회초년생 재테크 시작하기",
    ],
    "건강": [
        "공복 혈당 낮추는 법", "간헐적 단식 효과", "허리 디스크 스트레칭",
        "목 디스크 예방법", "불면증 개선 방법", "수면의 질 높이는 법", "편두통 완화법",
        "무릎 관절 통증 관리", "다이어트 식단 짜는 법", "근력운동 루틴 추천", "눈 건강 지키는 법",
        "장 건강 개선하는 법", "콜레스테롤 낮추는 음식", "혈압 관리 방법", "갱년기 증상 관리",
        "면역력 높이는 법", "스트레스 해소법", "거북목 교정 스트레칭", "어깨 결림 푸는 법",
        "손목터널증후군 예방법", "족저근막염 관리법", "변비 해결하는 법", "위염 관리 식습관",
        "역류성 식도염 완화법", "만성피로 원인과 관리", "탈모 예방법", "피부 노화 방지법",
        "자외선 차단 방법", "비타민D 부족 증상", "철분 부족 빈혈 관리", "유산소 운동 효과",
        "코어 근육 강화 운동", "홈트레이닝 루틴", "걷기 운동 효과", "체지방 줄이는 법",
        "근감소증 예방법", "골다공증 예방 운동", "당뇨 예방 식습관", "고혈압 예방 식단",
        "지방간 관리법", "숙면을 위한 습관", "카페인 줄이는 법", "금연 성공 방법",
        "금주 후 몸의 변화", "명상으로 스트레스 줄이기", "번아웃 극복법", "성인 ADHD 자가진단",
        "우울감 관리 방법", "계절성 우울증 대처법", "겨울철 면역력 관리",
    ],
    # ponytail: 100개 풀 + 영구 재사용금지 = 약 18~19일 runway(하루5개 기준). 소진 전에 항목 추가 필요.
}

K_CULTURE_KEYWORDS = {
    "food": [
        "how to eat Korean BBQ like a local", "what is gochujang and how do you use it",
        "difference between kimchi and sauerkraut", "how spicy is tteokbokki really",
        "what do Koreans eat for breakfast", "how to order at a Korean restaurant in Korea",
        "what is banchan and why is it free", "best Korean street food to try in Seoul",
        "how to make kimchi fried rice at home", "what is bibimbap supposed to taste like",
        "why do Koreans eat seaweed soup on birthdays", "what is Korean corn dog made of",
        "how to eat Korean fried chicken with beer", "what is jjigae and how is it different from soup",
        "is Korean food healthy for weight loss", "what is soju and how do you drink it",
        "Korean convenience store food worth trying", "what is naengmyeon and when do Koreans eat it",
        "how to use Korean chopsticks and spoon properly", "what is samgyeopsal night in Korea",
    ],
    "beauty": [
        "what is the 10 step Korean skincare routine", "is Korean sunscreen better than western sunscreen",
        "what is a cushion compact and how do you use it", "how to get glass skin naturally",
        "what is double cleansing and do you need it", "are sheet masks actually worth it",
        "Korean skincare ingredients to look for", "what is skin barrier repair Korean method",
        "how Koreans do makeup differently from the west", "what is gradient lip makeup",
        "best Korean products for sensitive skin", "is snail mucin safe for your face",
    ],
    "language": [
        "how hard is it to learn Korean for English speakers", "how to read Hangul in one day",
        "what does oppa actually mean", "Korean honorifics explained simply",
        "most useful Korean phrases for travelers", "what does aegyo mean in Korean culture",
        "difference between formal and casual Korean speech", "why Koreans ask your age first",
        "Korean words that have no English translation", "how to count in Korean two number systems",
    ],
    "travel": [
        "how many days do you need in Seoul", "how to use the subway in Seoul as a foreigner",
        "is Korea safe for solo female travelers", "best time of year to visit Korea",
        "what is a jjimjilbang and how does it work", "how to get a T money card in Korea",
        "cheapest way to travel between Seoul and Busan", "do you need to tip in Korea",
        "what to pack for Korea in winter", "how to use Korean cafes to work remotely",
    ],
    "drama_film": [
        "where to start with Korean dramas as a beginner", "why Korean dramas end after one season",
        "what is a chaebol in Korean dramas", "Korean drama cliches explained",
        "how accurate are Korean dramas about real Korean life", "best Korean movies to watch after Parasite",
        "what is the Korean wave hallyu", "why Korean dramas have so much product placement",
    ],
    "music": [
        "how does the K-pop idol training system work", "what is a K-pop comeback",
        "why do K-pop fans buy multiple albums", "what is a fanchant in K-pop",
        "how K-pop groups get their names", "what is trot music in Korea",
    ],
    "etiquette": [
        "Korean drinking etiquette rules for foreigners", "why Koreans take shoes off indoors",
        "how to give and receive things with two hands in Korea", "what is Korean age and how is it counted",
        "Korean gift giving etiquette explained", "what not to do in Korea as a tourist",
        "how bowing works in Korean culture", "why Koreans share food from one plate",
    ],
    "shopping": [
        "how to shop at Olive Young as a tourist", "what is Coupang and can foreigners use it",
        "how tax refund works for tourists in Korea", "best Korean souvenirs that are not keychains",
        "how to buy K-pop albums from overseas", "what is Myeongdong known for shopping",
    ],
}


def get_kculture_keywords() -> list:
    result = []
    for topic_list in K_CULTURE_KEYWORDS.values():
        result.extend(topic_list)
    return result


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


def get_keywords_to_use(track: str, needed_count: int) -> list:
    recent = db.get_recent_keywords(track)
    if track == "blogspot":
        # pytrends/naver_trends는 한국어 전용이라 영어 트랙에서는 풀만 쓴다
        return [kw for kw in get_kculture_keywords() if kw not in recent][:needed_count]

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
