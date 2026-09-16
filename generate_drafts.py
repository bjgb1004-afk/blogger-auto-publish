import html
import json
import logging
import os
from pathlib import Path

import config
import db
import generator
import keywords
import post
import pubmed
import telegram_bot
import validate

MAX_RETRY = 5
TRACKS = ("blogspot", "tistory")

logging.basicConfig(filename=str(Path(__file__).parent / "app.log"), level=logging.INFO, format="%(asctime)s %(message)s")


def _mark_failed(draft: dict, reason: str) -> None:
    retry = db.increment_retry(draft["id"])
    logging.error("delivery failed for draft %d (retry %d): %s", draft["id"], retry, reason)
    if retry > MAX_RETRY:
        db.update_status(draft["id"], "failed")
        try:
            telegram_bot.send_alert(f"발행 반복 실패: 초안 #{draft['id']} ({draft['title']})")
        except Exception as e:
            logging.error("failure alert notify failed for draft %d: %s", draft["id"], e)


def publish(draft: dict) -> bool:
    """blogspot 트랙은 Blogger로 자동 발행, tistory 트랙은 텔레그램으로 원고만 전달."""
    tags = json.loads(draft["tags"]) if isinstance(draft["tags"], str) else draft["tags"]

    if draft["track"] == "tistory":
        try:
            telegram_bot.send_tistory_copy(
                draft["title"], draft["content"], tags,
                draft.get("summary", ""), draft.get("image_prompt_en", ""),
            )
        except Exception as e:
            _mark_failed(draft, str(e))
            return False
        db.update_status(draft["id"], "sent")
        return True

    url = post.post_to_blogger(
        blog_id=os.environ["BLOGGER_BLOG_ID"],
        title=draft["title"],
        content=draft["content"],
        tags=tags,
        search_description=draft.get("summary", ""),
    )
    if not url:
        _mark_failed(draft, "post_to_blogger returned no url")
        return False

    db.update_status(draft["id"], "published")
    try:
        telegram_bot.send_published_notice(
            draft["id"], draft["title"], url, draft["keyword"],
            warnings=validate.check_draft(draft["title"], draft["content"]),
            image_prompt_en=draft.get("image_prompt_en", ""),
        )
    except Exception as e:
        logging.error("published notice failed for draft %d: %s", draft["id"], e)
    return True


def _apply_count_commands() -> None:
    offset = int(db.get_meta("telegram_offset", "0"))
    try:
        events, next_offset = telegram_bot.get_events(offset)
    except Exception as e:
        logging.warning("telegram getUpdates failed: %s", e)
        return
    for event in events:
        if event["type"] == "count":
            config.set_daily_post_count(event["track"], event["value"])
    db.set_meta("telegram_offset", str(next_offset))


def run_track(track: str, budget: int = None) -> int:
    """한 트랙의 재시도 큐 + 오늘치 신규 생성을 처리하고 전달 성공 건수를 돌려준다."""
    delivered = 0

    # 이전 실행에서 전달 못 한 초안 먼저 처리
    for draft in db.get_unpublished(track):
        if budget is not None and delivered >= budget:
            return delivered
        if publish(draft):
            delivered += 1

    target = config.get_daily_post_count(track)
    needed = max(0, target - db.get_today_count(track))
    if budget is not None:
        needed = min(needed, budget - delivered)
    if needed <= 0:
        logging.info("generate_drafts[%s]: target %d already met, skip", track, target)
        return delivered

    for keyword in keywords.get_keywords_to_use(track, needed):
        try:
            post_data = generator.generate_post(keyword, track)
        except Exception as e:
            logging.error("generate_drafts[%s]: gemini failed for %r: %s", track, keyword, e)
            continue

        content = post_data["content"]
        study = pubmed.find_study(post_data.get("health_topic_en", "")) if track == "tistory" else None
        if study and study["title"]:
            content += (
                f'\n<p><strong>참고 연구:</strong> "{html.escape(study["title"])}" '
                f'({html.escape(study["journal"])}, {study["year"]}) — '
                f'<a href="{study["url"]}" target="_blank" rel="noopener">원문 보기</a></p>'
            )

        draft_id = db.insert_draft(
            keyword, post_data["title"], content, post_data["tags"],
            summary=post_data.get("summary", ""),
            image_prompt_en=post_data.get("image_prompt_en", ""),
            track=track,
        )
        if publish({
            "id": draft_id, "keyword": keyword, "title": post_data["title"], "content": content,
            "tags": post_data["tags"], "summary": post_data.get("summary", ""),
            "image_prompt_en": post_data.get("image_prompt_en", ""), "track": track,
        }):
            delivered += 1

    return delivered


def run() -> int:
    db.init_db()
    _apply_count_commands()

    max_per_run = int(os.environ["GENERATE_MAX_PER_RUN"]) if os.environ.get("GENERATE_MAX_PER_RUN") else None
    delivered = 0
    for track in TRACKS:
        budget = None if max_per_run is None else max_per_run - delivered
        if budget is not None and budget <= 0:
            break
        delivered += run_track(track, budget)

    logging.info("generate_drafts: delivered %d post(s)", delivered)
    return delivered


if __name__ == "__main__":
    from env_loader import load_env
    load_env()
    try:
        run()
    except Exception as e:
        logging.error("run() crashed: %s: %s", type(e).__name__, str(e).replace(os.environ.get("TELEGRAM_BOT_TOKEN", ""), "***"))
