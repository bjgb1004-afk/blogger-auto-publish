import json
import os
import time

from google import genai
from google.genai import errors as genai_errors

_client = None
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 5

PROMPT_TEMPLATE = """너는 블로그 작가다. 아래 키워드로 블로그 글을 하나 써라.
키워드: {keyword}

규칙:
- 글 안에 "블로그봇", "AI", "챗봇" 등 자기 자신(작성 주체)을 밝히거나 언급하는 표현을 절대 쓰지 마라. 사람이 직접 쓴 글처럼 작성해라.
- 제목은 키워드를 그냥 나열하지 말고, 사람이 실제로 검색창이나 챗GPT에 물어볼 법한 자연스러운 문장·질문 형태로 써라.
- 도입부 첫 문장은 이 글의 핵심 주제를 군더더기 없이 한 줄로 명확히 정의하는 문장으로 시작해라. (예: "OO란 ~하는 것을 말한다") — AI 검색엔진이 이 문장을 그대로 인용해가는 경우가 많다.
- 숫자나 통계는 확실하지 않으면 절대 지어내지 말고, 다만 두루뭉술하게 뭉개지 말고, 실행 가능한 구체적 방법이나 사례를 들어 설명해라.
- content는 반드시 <p> 태그로 시작해라. 첫 <h2>보다 앞에 도입 문단이 와야 한다. 제목을 <h2>로 다시 쓰거나 첫 소제목을 맨 앞에 두지 마라.
- 구조: 도입(한 줄 정의 + 문제 공감 1문단) → 소제목(h2) 2~3개, 각 소제목마다 구체적 방법·사례·실행 팁을 최소 1개씩 포함 → 마무리(요약 + 다음 행동 제안).
- 문장 길이를 짧은 문장과 긴 문장으로 다양하게 섞고, 같은 어미나 문장 시작 표현을 반복하지 마라.
- 본문 전체 글자 수(태그 제외)는 최소 2000자 이상으로 써라.
- 이 글이 투자/재테크/주식 관련이면 마지막 문단에 "이 글은 투자 조언이 아닌 일반 정보이며, 투자 판단과 책임은 본인에게 있습니다."를 포함해라. 건강/의료 관련이면 "본 내용은 일반 정보이며, 정확한 진단과 처방은 반드시 의료 전문가와 상담하세요."를 포함해라.
- 본문은 <h2>, <p>, <strong> 태그를 쓴 HTML로 작성해라.
- summary 필드에는 검색결과 요약(메타 설명)으로 쓸 1~2문장을 80자 내외로 작성해라.
- 이 글이 건강/의료 관련이면, 본문 핵심 주제를 PubMed 검색에 적합한 영어 키워드 3~6단어로 만들어 health_topic_en 필드에 넣어라(예: "cortisol stress recovery exercise"). 실제 논문 제목이나 저자를 지어내지 말고 검색어만 만들어라. 건강/의료 글이 아니면 health_topic_en은 빈 문자열로 둬라.
- 본문 핵심 내용을 대표하는 삽화 장면을 영어 3~6단어로 만들어 image_prompt_en 필드에 넣어라(예: "dividend stock chart on smartphone", "lower back spine anatomy diagram"). AI 이미지 생성용 프롬프트이니 반드시 영어로, 글 내용과 직접 관련된 구체적 사물·신체부위·상황 중심으로 써라. 사람 얼굴이나 특정 인물이 등장하는 장면은 절대 쓰지 마라(얼굴이 무작위로 엉뚱하게 그려짐).
- 아래 JSON 형식으로만 답해라. 다른 텍스트 붙이지 마라.

{{"title": "글 제목", "content": "HTML 본문", "tags": ["태그1", "태그2"], "summary": "검색결과용 요약", "health_topic_en": "PubMed 검색어 또는 빈 문자열", "image_prompt_en": "삽화 장면 영어 3~6단어"}}
"""

KCULTURE_PROMPT_TEMPLATE = """You are a blogger who lives in Korea and writes in English for foreign readers curious about Korean culture. Write one blog post on the keyword below.
Keyword: {keyword}

Rules:
- Never mention or hint that you are an AI, a bot, or an assistant. Write as a person sharing first-hand knowledge.
- The title must read like something a real person would type into Google or ask ChatGPT — a natural question or sentence, not a keyword dump.
- Open the first sentence with a clean one-line definition or direct answer to the keyword (e.g. "Gochujang is a fermented Korean chili paste that ..."). AI search engines quote this sentence directly.
- Never invent statistics, prices, dates, or names you are not sure about. Do not be vague either — give concrete examples, specific dishes, places, phrases, or step-by-step actions.
- The content must start with a <p> tag. The intro paragraph comes before the first <h2>. Do not repeat the title as an <h2> and do not put a section heading first.
- Structure: intro (one-line answer + one paragraph of context) -> 2-3 <h2> sections, each with at least one concrete example, step, or practical tip -> closing (short recap + what the reader should try next).
- Mix short and long sentences. Do not start consecutive sentences the same way.
- Write at least 1200 words of body text (excluding tags).
- Explain Korean words in romanization with the Hangul in parentheses on first use, e.g. gochujang (고추장).
- Write the body as HTML using only <h2>, <p>, and <strong> tags.
- Put a 1-2 sentence meta description (around 150 characters) in the summary field.
- Put an illustration scene for this post in image_prompt_en as 3-6 English words (e.g. "korean bbq grill with side dishes"). It is a prompt for AI image generation, so focus on concrete objects and scenes. Never include human faces or specific people.
- Respond with the JSON format below only. Do not add any other text.

{{"title": "post title", "content": "HTML body", "tags": ["tag1", "tag2"], "summary": "meta description", "image_prompt_en": "illustration scene in 3-6 english words"}}
"""

PROMPT_TEMPLATES = {"tistory": PROMPT_TEMPLATE, "blogspot": KCULTURE_PROMPT_TEMPLATE}


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _client


def _strip_markdown_fence(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    return cleaned.strip()


def _parse_response(text: str) -> dict:
    data = json.loads(_strip_markdown_fence(text))
    return {
        "title": data["title"],
        "content": data["content"],
        "tags": data.get("tags", []),
        "summary": data.get("summary", ""),
        "health_topic_en": data.get("health_topic_en", ""),
        "image_prompt_en": data.get("image_prompt_en", ""),
    }


def _generate_content_with_retry(prompt: str):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return _get_client().models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt,
            )
        except genai_errors.ServerError:
            if attempt == MAX_RETRIES:
                raise
            time.sleep(RETRY_BACKOFF_SECONDS * attempt)


def generate_post(keyword: str, track: str = "tistory") -> dict:
    prompt = PROMPT_TEMPLATES[track].format(keyword=keyword)
    response = _generate_content_with_retry(prompt)
    return _parse_response(response.text)
