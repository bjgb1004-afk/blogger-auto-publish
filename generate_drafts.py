import logging

import config
import db
import generator
import keywords
import telegram_bot
import validate

logging.basicConfig(filename="app.log", level=logging.INFO, format="%(asctime)s %(message)s")


def run() -> int:
    db.init_db()
    target = config.get_daily_post_count()
    already = db.get_today_count()
    needed = max(0, target - already)
    if needed == 0:
        logging.info("generate_drafts: target %d already met (%d today), skip", target, already)
        return 0

    created = 0
    for keyword in keywords.get_keywords_to_use(needed):
        try:
            post_data = generator.generate_post(keyword)
        except Exception as e:
            logging.error("generate_drafts: gemini failed for %r: %s", keyword, e)
            continue

        draft_id = db.insert_draft(keyword, post_data["title"], post_data["content"], post_data["tags"])
        warnings = validate.check_draft(post_data["title"], post_data["content"])
        try:
            msg_id = telegram_bot.send_draft_notification(draft_id, post_data["title"], keyword, warnings)
            db.set_telegram_msg_id(draft_id, msg_id)
        except Exception as e:
            logging.error("generate_drafts: telegram notify failed for draft %d: %s", draft_id, e)
        created += 1

    logging.info("generate_drafts: created %d draft(s)", created)
    return created


if __name__ == "__main__":
    from env_loader import load_env
    load_env()
    run()
