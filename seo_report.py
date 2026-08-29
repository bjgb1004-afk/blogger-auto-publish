import os
from datetime import date, timedelta

import search_console
from post import get_blogger_service

SEARCH_CONSOLE_DELAY_DAYS = 3  # Search Console 데이터는 보통 2~3일 지연됨


def get_site_url():
    service = get_blogger_service()
    blog = service.blogs().get(blogId=os.environ["BLOGGER_BLOG_ID"]).execute()
    return blog["url"]


def _print_rows(rows, key_label, key_width):
    rows = sorted(rows, key=lambda r: r.get("clicks", 0), reverse=True)
    for r in rows:
        key = r["keys"][0]
        print(
            f"{key[:key_width]:{key_width}}  클릭 {r['clicks']:>4}  노출 {r['impressions']:>6}  "
            f"CTR {r['ctr'] * 100:>5.1f}%  평균순위 {r['position']:>5.1f}"
        )


def print_report(days=28):
    site_url = get_site_url()
    end = date.today() - timedelta(days=SEARCH_CONSOLE_DELAY_DAYS)
    start = end - timedelta(days=days)

    print(f"=== {site_url} 검색 성과 ({start} ~ {end}) ===\n")

    print("[검색어별 (클릭순)]")
    query_rows = search_console.get_query_performance(
        site_url, start.isoformat(), end.isoformat(), dimensions=["query"]
    )
    _print_rows(query_rows, "검색어", 30)

    print("\n[페이지별 (클릭순)]")
    page_rows = search_console.get_query_performance(
        site_url, start.isoformat(), end.isoformat(), dimensions=["page"]
    )
    _print_rows(page_rows, "페이지", 60)


if __name__ == "__main__":
    from env_loader import load_env
    load_env()
    print_report()
