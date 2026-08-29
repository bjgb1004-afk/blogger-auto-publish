import base64
import logging
import urllib.parse

import requests

POLLINATIONS_URL = "https://image.pollinations.ai/prompt/{prompt}"
PROMPT_TEMPLATE = "flat vector illustration, {keyword}, no text, clean minimal style, high quality"
TIMEOUT = 30


def generate_image_data_uri(keyword: str):
    prompt = PROMPT_TEMPLATE.format(keyword=keyword)
    url = POLLINATIONS_URL.format(prompt=urllib.parse.quote(prompt))
    try:
        resp = requests.get(url, params={"width": 1024, "height": 576, "nologo": "true"}, timeout=TIMEOUT)
        resp.raise_for_status()
    except Exception as e:
        logging.error("image_gen: failed for %r: %s", keyword, e)
        return None
    mime = resp.headers.get("content-type", "image/jpeg")
    b64 = base64.b64encode(resp.content).decode("ascii")
    return f"data:{mime};base64,{b64}"
