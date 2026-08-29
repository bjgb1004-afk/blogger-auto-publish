import logging
import os
from datetime import date, timedelta

import requests

API_URL = "https://openapi.naver.com/v1/datalab/search"
BATCH_SIZE = 5  # Naver DataLab API limit: max 5 keyword groups per request


def get_trend_scores(keyword_list: list) -> dict:
    scores = {}
    for i in range(0, len(keyword_list), BATCH_SIZE):
        scores.update(_query_batch(keyword_list[i:i + BATCH_SIZE]))
    return scores


def _query_batch(batch: list) -> dict:
    if not batch:
        return {}
    end = date.today()
    start = end - timedelta(days=7)
    body = {
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "timeUnit": "date",
        "keywordGroups": [{"groupName": kw, "keywords": [kw]} for kw in batch],
    }
    try:
        headers = {
            "X-Naver-Client-Id": os.environ["NAVER_CLIENT_ID"],
            "X-Naver-Client-Secret": os.environ["NAVER_CLIENT_SECRET"],
            "Content-Type": "application/json",
        }
        resp = requests.post(API_URL, json=body, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logging.error("naver_trends: failed for %r: %s", batch, e)
        return {}

    scores = {}
    for result in data.get("results", []):
        points = result.get("data", [])
        if points:
            scores[result["title"]] = points[-1]["ratio"]
    return scores
