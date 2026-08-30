import html
import logging
import os
from pathlib import Path

import config
import db
import generator
import keywords
import pubmed
import telegram_bot
import validate

logging.basicConfig(filename=str(Path(__file__).parent / "app.log"), level=logging.INFO, format="%(asctime)s %(message)s")


def run() -> int:
    db.init_db()
    target = config.get_daily_post_count()
    already = db.get_today_count()
    needed = max(0, target - already)
    max_per_run = os.environ.get("GENERATE_MAX_PER_RUN")
    if max_per_run:
        needed = min(needed, int(max_per_run))
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
        warnings = validate.check_draft(post_data["title"], content)
        try:
            msg_id = telegram_bot.send_draft_notification(
                draft_id, post_data["title"], keyword, warnings, content=content,
                image_prompt_en=post_data.get("image_prompt_en", ""),
            )
            db.set_telegram_msg_id(draft_id, msg_id)
        except Exception as e:
            logging.error("generate_drafts: telegram notify failed for draft %d: %s", draft_id, e)
        created += 1

    logging.info("generate_drafts: created %d draft(s)", created)
    return created


if __name__ == "__main__":
    from env_loader import load_env
    load_env()
    try:
        run()
    except Exception as e:
        logging.error("run() crashed: %s: %s", type(e).__name__, str(e).replace(os.environ.get("TELEGRAM_BOT_TOKEN", ""), "***"))
