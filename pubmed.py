import logging

import requests

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
TIMEOUT = 15


def find_study(topic_en: str):
    if not topic_en:
        return None
    try:
        search = requests.get(ESEARCH_URL, params={
            "db": "pubmed", "term": topic_en, "retmax": 1,
            "sort": "relevance", "retmode": "json",
        }, timeout=TIMEOUT)
        search.raise_for_status()
        ids = search.json()["esearchresult"]["idlist"]
        if not ids:
            return None
        pmid = ids[0]

        summary = requests.get(ESUMMARY_URL, params={
            "db": "pubmed", "id": pmid, "retmode": "json",
        }, timeout=TIMEOUT)
        summary.raise_for_status()
        doc = summary.json()["result"][pmid]
    except Exception as e:
        logging.error("pubmed: failed for %r: %s", topic_en, e)
        return None

    return {
        "title": doc.get("title", ""),
        "journal": doc.get("fulljournalname", ""),
        "year": (doc.get("pubdate") or "")[:4],
        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
    }
