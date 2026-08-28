import json
import logging
import os
from pathlib import Path

import config
import db
import post
import telegram_bot

MAX_RETRY = 5

logging.basicConfig(filename=str(Path(__file__).parent / "app.log"), level=logging.INFO, format="%(asctime)s %(message)s")


def run() -> None:
    db.init_db()
    offset = int(db.get_meta("telegram_offset", "0"))
    events, next_offset = telegram_bot.get_events(offset)

    for event in events:
        if event["type"] == "approve":
            applied = db.set_status_if_pending(event["draft_id"], "approved")
            try:
                telegram_bot.answer_callback(
                    event["callback_query_id"], "승인됨" if applied else "이미 처리된 초안임"
                )
            except Exception as e:
                logging.warning("answer_callback failed (likely expired callback query, safe to ignore): %s", e)
        elif event["type"] == "reject":
            applied = db.set_status_if_pending(event["draft_id"], "rejected")
            try:
                telegram_bot.answer_callback(
                    event["callback_query_id"], "거부됨" if applied else "이미 처리된 초안임"
                )
            except Exception as e:
                logging.warning("answer_callback failed (likely expired callback query, safe to ignore): %s", e)
        elif event["type"] == "count":
            config.set_daily_post_count(event["value"])
    db.set_meta("telegram_offset", str(next_offset))

    for draft in db.get_pending_without_telegram_msg():
        try:
            msg_id = telegram_bot.send_draft_notification(draft["id"], draft["title"], draft["keyword"], warnings=None)
            db.set_telegram_msg_id(draft["id"], msg_id)
        except Exception as e:
            logging.error("check_approvals: retry notify failed for draft %d: %s", draft["id"], e)
            continue

    for draft in db.get_approved_unpublished():
        ok = post.post_to_blogger(
            blog_id=os.environ["BLOGGER_BLOG_ID"],
            title=draft["title"],
            content=draft["content"],
            tags=json.loads(draft["tags"]),
            search_description=draft.get("summary", ""),
        )
        if ok:
            db.update_status(draft["id"], "published")
        else:
            retry = db.increment_retry(draft["id"])
            logging.error("check_approvals: publish failed for draft %d (retry %d)", draft["id"], retry)
            if retry > MAX_RETRY:
                telegram_bot.send_alert(f"발행 반복 실패: 초안 #{draft['id']} ({draft['title']})")
                db.update_status(draft["id"], "failed")


if __name__ == "__main__":
    from env_loader import load_env
    load_env()
    try:
        run()
    except Exception as e:
        logging.error("run() crashed: %s: %s", type(e).__name__, str(e).replace(os.environ.get("TELEGRAM_BOT_TOKEN", ""), "***"))
