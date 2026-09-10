import os
import re

import requests

API_BASE = "https://api.telegram.org/bot{token}/{method}"
TISTORY_CHUNK_SIZE = 3500


def _url(method: str) -> str:
    return API_BASE.format(token=os.environ["TELEGRAM_BOT_TOKEN"], method=method)


def _image_command(image_prompt_en: str) -> str:
    return (
        f'"{image_prompt_en}" 주제로 블로그 삽화 이미지 만들어줘. '
        "플랫 벡터 일러스트 스타일, 미니멀하고 깔끔한 색감, 16:9 비율, "
        "텍스트 없이, 사람 얼굴이나 인물 없이 사물·상황 중심으로."
    )


def send_published_notice(
    draft_id: int, title: str, url: str, keyword: str, warnings: list = None, image_prompt_en: str = ""
) -> None:
    text = f"✅ [발행 #{draft_id}] {title}\n키워드: {keyword}\n{url}"
    if warnings:
        text += "\n⚠ " + "; ".join(warnings)
    if image_prompt_en:
        text += "\n\n🎨 이미지 생성 명령어(나노바나나 등에 붙여넣기):\n" + _image_command(image_prompt_en)
    _send_text(text)


def _send_text(text: str) -> None:
    payload = {"chat_id": os.environ["TELEGRAM_CHAT_ID"], "text": text}
    resp = requests.post(_url("sendMessage"), json=payload, timeout=10)
    resp.raise_for_status()


def _to_plain_text(content: str) -> str:
    text = re.sub(r'<a\s+[^>]*href="([^"]+)"[^>]*>(.*?)</a>', r'\2 (\1)', content, flags=re.DOTALL)
    text = re.sub(r'<img\s+[^>]*src="([^"]+)"[^>]*/?>', r'[이미지: \1]', text)
    text = re.sub(r'<h2[^>]*>(.*?)</h2>', r'\n▶ \1\n', text, flags=re.DOTALL)
    text = re.sub(r'</?(strong|b)>', '', text)
    text = re.sub(r'<p[^>]*>(.*?)</p>', r'\1\n', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', '', text)
    return re.sub(r'\n{3,}', '\n\n', text).strip()


def send_tistory_copy(title: str, content: str, tags: list, summary: str = "") -> None:
    header = f"📋 티스토리용 원고 - {title}\n\n태그: {', '.join(tags)}"
    if summary:
        header += f"\n메타설명: {summary}"
    header += "\n\n아래 텍스트를 티스토리 에디터에 순서대로 붙여넣으세요. (▶ 표시는 소제목, 이미지는 표시된 URL로 직접 추가)"
    _send_text(header)

    plain = _to_plain_text(content)
    for i in range(0, len(plain), TISTORY_CHUNK_SIZE):
        _send_text(plain[i:i + TISTORY_CHUNK_SIZE])


def send_alert(text: str) -> None:
    _send_text(text)


def get_events(offset: int):
    """Poll telegram for /count commands only. Approval flow removed."""
    resp = requests.get(_url("getUpdates"), params={"offset": offset, "timeout": 0}, timeout=15)
    resp.raise_for_status()
    updates = resp.json()["result"]
    events = []
    next_offset = offset
    for update in updates:
        next_offset = max(next_offset, update["update_id"] + 1)
        if "message" not in update:
            continue
        chat_id = str(update["message"].get("chat", {}).get("id", ""))
        if chat_id != os.environ["TELEGRAM_CHAT_ID"]:
            continue
        text = update["message"].get("text", "")
        if text.startswith("/count"):
            parts = text.split()
            if len(parts) == 2 and parts[1].isdigit():
                value = int(parts[1])
                if 1 <= value <= 20:
                    events.append({"type": "count", "value": value})
    return events, next_offset
