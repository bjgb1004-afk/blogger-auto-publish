import json
import os

from google import genai

_client = None

PROMPT_TEMPLATE = """너는 블로그 작가다. 아래 키워드로 블로그 글을 하나 써라.
키워드: {keyword}

규칙:
- 숫자나 통계는 확실하지 않으면 절대 지어내지 말고, 다만 두루뭉술하게 뭉개지 말고, 실행 가능한 구체적 방법이나 사례를 들어 설명해라.
- 구조: 도입(문제 공감 1문단) → 소제목(h2) 2~3개, 각 소제목마다 구체적 방법·사례·실행 팁을 최소 1개씩 포함 → 마무리(요약 + 다음 행동 제안).
- 문장 길이를 짧은 문장과 긴 문장으로 다양하게 섞고, 같은 어미나 문장 시작 표현을 반복하지 마라.
- 본문 전체 글자 수(태그 제외)는 최소 2000자 이상으로 써라.
- 이 글이 투자/재테크/주식 관련이면 마지막 문단에 "이 글은 투자 조언이 아닌 일반 정보이며, 투자 판단과 책임은 본인에게 있습니다."를 포함해라. 건강/의료 관련이면 "본 내용은 일반 정보이며, 정확한 진단과 처방은 반드시 의료 전문가와 상담하세요."를 포함해라.
- 본문은 <h2>, <p>, <strong> 태그를 쓴 HTML로 작성해라.
- summary 필드에는 검색결과 요약(메타 설명)으로 쓸 1~2문장을 80자 내외로 작성해라.
- 이 글이 건강/의료 관련이면, 본문 핵심 주제를 PubMed 검색에 적합한 영어 키워드 3~6단어로 만들어 health_topic_en 필드에 넣어라(예: "cortisol stress recovery exercise"). 실제 논문 제목이나 저자를 지어내지 말고 검색어만 만들어라. 건강/의료 글이 아니면 health_topic_en은 빈 문자열로 둬라.
- 아래 JSON 형식으로만 답해라. 다른 텍스트 붙이지 마라.

{{"title": "글 제목", "content": "HTML 본문", "tags": ["태그1", "태그2"], "summary": "검색결과용 요약", "health_topic_en": "PubMed 검색어 또는 빈 문자열"}}
"""


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _client


def _parse_response(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    data = json.loads(cleaned.strip())
    return {
        "title": data["title"],
        "content": data["content"],
        "tags": data.get("tags", []),
        "summary": data.get("summary", ""),
        "health_topic_en": data.get("health_topic_en", ""),
    }


def generate_post(keyword: str) -> dict:
    prompt = PROMPT_TEMPLATE.format(keyword=keyword)
    response = _get_client().models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
    )
    return _parse_response(response.text)
