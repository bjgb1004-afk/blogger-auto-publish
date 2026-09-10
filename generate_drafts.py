import html
import json
import logging
import os
import re
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

logging.basicConfig(filename=str(Path(__file__).parent / "app.log"), level=logging.INFO, format="%(asctime)s %(message)s")


def _vary_for_repost(title: str, content: str) -> tuple:
    match = re.search(r"<p>.*?</p>", content, re.DOTALL)
    if not match:
        return title, content
    try:
        rewritten = generator.rewrite_for_repost(title, match.group(0))
    except Exception as e:
        logging.warning("repost rewrite failed, using original text: %s", e)
        return title, content
    return rewritten["title"], content[:match.start()] + rewritten["intro"] + content[match.end():]


def publish(draft: dict) -> bool:
    """Post draft to Blogger, then send the tistory manuscript to telegram."""
    tags = json.loads(draft["tags"]) if isinstance(draft["tags"], str) else draft["tags"]
    url = post.post_to_blogger(
        blog_id=os.environ["BLOGGER_BLOG_ID"],
        title=draft["title"],
        content=draft["content"],
        tags=tags,
        search_description=draft.get("summary", ""),
    )
    if not url:
        retry = db.increment_retry(draft["id"])
        logging.error("publish failed for draft %d (retry %d)", draft["id"], retry)
        if retry > MAX_RETRY:
            db.update_status(draft["id"], "failed")
            try:
                telegram_bot.send_alert(f"발행 반복 실패: 초안 #{draft['id']} ({draft['title']})")
            except Exception as e:
                logging.error("failure alert notify failed for draft %d: %s", draft["id"], e)
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
    try:
        tistory_title, tistory_content = _vary_for_repost(draft["title"], draft["content"])
        telegram_bot.send_tistory_copy(tistory_title, tistory_content, tags, draft.get("summary", ""))
    except Exception as e:
        logging.error("tistory copy notify failed for draft %d: %s", draft["id"], e)
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
            config.set_daily_post_count(event["value"])
    db.set_meta("telegram_offset", str(next_offset))


def run() -> int:
    db.init_db()
    _apply_count_commands()

    max_per_run = int(os.environ["GENERATE_MAX_PER_RUN"]) if os.environ.get("GENERATE_MAX_PER_RUN") else None
    published = 0

    # 이전 실행에서 발행 못 한 초안 먼저 처리
    for draft in db.get_unpublished():
        if max_per_run and published >= max_per_run:
            return published
        if publish(draft):
            published += 1

    target = config.get_daily_post_count()
    already = db.get_today_count()
    needed = max(0, target - already)
    if max_per_run:
        needed = min(needed, max_per_run - published)
    if needed <= 0:
        logging.info("generate_drafts: target %d already met (%d today), skip", target, already)
        return published

    for keyword in keywords.get_keywords_to_use(needed):
        try:
            post_data = generator.generate_post(keyword)
        except Exception as e:
            logging.error("generate_drafts: gemini failed for %r: %s", keyword, e)
            continue

        content = post_data["content"]
        study = pubmed.find_study(post_data.get("health_topic_en", ""))
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
        )
        if publish({
            "id": draft_id, "keyword": keyword, "title": post_data["title"], "content": content,
            "tags": post_data["tags"], "summary": post_data.get("summary", ""),
            "image_prompt_en": post_data.get("image_prompt_en", ""),
        }):
            published += 1

    logging.info("generate_drafts: published %d post(s)", published)
    return published


if __name__ == "__main__":
    from env_loader import load_env
    load_env()
    try:
        run()
    except Exception as e:
        logging.error("run() crashed: %s: %s", type(e).__name__, str(e).replace(os.environ.get("TELEGRAM_BOT_TOKEN", ""), "***"))
