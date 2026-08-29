import hashlib
import logging
import urllib.parse

import requests

POLLINATIONS_URL = "https://image.pollinations.ai/prompt/{prompt}"
PROMPT_TEMPLATE = "flat vector illustration, {keyword}, no text, clean minimal style, high quality"
TIMEOUT = 30


def generate_image_url(keyword: str):
    prompt = PROMPT_TEMPLATE.format(keyword=keyword)
    url = POLLINATIONS_URL.format(prompt=urllib.parse.quote(prompt))
    seed = int(hashlib.sha256(keyword.encode("utf-8")).hexdigest(), 16) % 1_000_000
    params = {"width": 1024, "height": 576, "nologo": "true", "seed": seed}
    try:
        resp = requests.get(url, params=params, timeout=TIMEOUT)
        resp.raise_for_status()
    except Exception as e:
        logging.error("image_gen: failed for %r: %s", keyword, e)
        return None
    return resp.url
