import json
import logging
import os

import config
import db
import post
import telegram_bot

MAX_RETRY = 5

logging.basicConfig(filename="app.log", level=logging.INFO, format="%(asctime)s %(message)s")


def run() -> None:
    db.init_db()
    offset = int(db.get_meta("telegram_offset", "0"))
    events, next_offset = telegram_bot.get_events(offset)

    for event in events:
        if event["type"] == "approve":
            db.update_status(event["draft_id"], "approved")
            telegram_bot.answer_callback(event["callback_query_id"], "승인됨")
        elif event["type"] == "reject":
            db.update_status(event["draft_id"], "rejected")
            telegram_bot.answer_callback(event["callback_query_id"], "거부됨")
        elif event["type"] == "count":
            config.set_daily_post_count(event["value"])
    db.set_meta("telegram_offset", str(next_offset))

    for draft in db.get_approved_unpublished():
        ok = post.post_to_blogger(
            blog_id=os.environ["BLOGGER_BLOG_ID"],
            title=draft["title"],
            content=draft["content"],
            tags=json.loads(draft["tags"]),
        )
        if ok:
            db.update_status(draft["id"], "published")
        else:
            retry = db.increment_retry(draft["id"])
            logging.error("check_approvals: publish failed for draft %d (retry %d)", draft["id"], retry)
            if retry > MAX_RETRY:
                telegram_bot.send_alert(f"발행 반복 실패: 초안 #{draft['id']} ({draft['title']})")


if __name__ == "__main__":
    from env_loader import load_env
    load_env()
    run()
