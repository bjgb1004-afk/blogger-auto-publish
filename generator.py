import json
import os

from google import genai

_client = None

PROMPT_TEMPLATE = """너는 블로그 작가다. 아래 키워드로 블로그 글을 하나 써라.
키워드: {keyword}

규칙:
- 숫자나 통계는 확실하지 않으면 절대 지어내지 말고, 일반적인 설명으로 대체해라.
- 본문은 <h2>, <p>, <strong> 태그를 쓴 HTML로 작성해라.
- 아래 JSON 형식으로만 답해라. 다른 텍스트 붙이지 마라.

{{"title": "글 제목", "content": "HTML 본문", "tags": ["태그1", "태그2"]}}
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
    }


def generate_post(keyword: str) -> dict:
    prompt = PROMPT_TEMPLATE.format(keyword=keyword)
    response = _get_client().models.generate_content(
        model="gemini-flash-latest",
        contents=prompt,
    )
    return _parse_response(response.text)
