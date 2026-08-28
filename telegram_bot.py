import os

import requests

API_BASE = "https://api.telegram.org/bot{token}/{method}"


def _url(method: str) -> str:
    return API_BASE.format(token=os.environ["TELEGRAM_BOT_TOKEN"], method=method)


def send_draft_notification(draft_id: int, title: str, keyword: str, warnings: list = None) -> int:
    text = f"[초안 #{draft_id}] {title}\n키워드: {keyword}"
    if warnings:
        text += "\n⚠ " + "; ".join(warnings)
    payload = {
        "chat_id": os.environ["TELEGRAM_CHAT_ID"],
        "text": text,
        "reply_markup": {
            "inline_keyboard": [[
                {"text": "승인", "callback_data": f"approve:{draft_id}"},
                {"text": "거부", "callback_data": f"reject:{draft_id}"},
            ]]
        },
    }
    resp = requests.post(_url("sendMessage"), json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()["result"]["message_id"]


def send_alert(text: str) -> None:
    payload = {"chat_id": os.environ["TELEGRAM_CHAT_ID"], "text": text}
    resp = requests.post(_url("sendMessage"), json=payload, timeout=10)
    resp.raise_for_status()


def get_events(offset: int):
    resp = requests.get(_url("getUpdates"), params={"offset": offset, "timeout": 0}, timeout=15)
    resp.raise_for_status()
    updates = resp.json()["result"]
    events = []
    next_offset = offset
    for update in updates:
        next_offset = max(next_offset, update["update_id"] + 1)
        if "callback_query" in update:
            cq = update["callback_query"]
            action, _, draft_id = cq["data"].partition(":")
            if action in ("approve", "reject"):
                events.append({"type": action, "draft_id": int(draft_id), "callback_query_id": cq["id"]})
        elif "message" in update:
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


def answer_callback(callback_query_id: str, text: str) -> None:
    resp = requests.post(
        _url("answerCallbackQuery"),
        json={"callback_query_id": callback_query_id, "text": text},
        timeout=10,
    )
    resp.raise_for_status()
