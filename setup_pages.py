import os

import post

REQUIRED_PAGES = [
    {
        "title": "개인정보처리방침",
        "content": """
        <p>이 블로그는 Google AdSense를 통해 광고를 게재할 수 있으며, 이 경우 Google 및 파트너는
        쿠키를 사용해 방문자의 관심사에 기반한 광고를 표시할 수 있습니다.</p>
        <p>방문자는 <a href="https://adssettings.google.com" target="_blank">Google 광고 설정</a>에서
        맞춤 광고를 비활성화할 수 있습니다.</p>
        <p>본 블로그는 방문자의 개인 식별 정보를 별도로 수집·저장하지 않습니다.</p>
        """,
    },
    {
        "title": "소개",
        "content": """
        <p>이 블로그는 재테크·경제와 건강 정보를 다루는 개인 운영 블로그입니다.</p>
        <p>모든 글은 일반적인 정보 제공을 목적으로 하며, 투자·의료 관련 최종 판단과 책임은
        각 글에 명시된 대로 독자 본인에게 있습니다.</p>
        """,
    },
    {
        "title": "연락처",
        "content": "<p>문의: {contact_email}</p>",
    },
]


def build_pages(contact_email: str) -> list:
    pages = []
    for page in REQUIRED_PAGES:
        content = page["content"].format(contact_email=contact_email) if "{contact_email}" in page["content"] else page["content"]
        pages.append({"title": page["title"], "content": content})
    return pages


def create_required_pages(blog_id: str, contact_email: str) -> list:
    service = post.get_blogger_service()
    existing_titles = {p["title"] for p in service.pages().list(blogId=blog_id).execute().get("items", [])}
    created = []
    for page in build_pages(contact_email):
        if page["title"] in existing_titles:
            continue
        body = {"kind": "blogger#page", "title": page["title"], "content": page["content"]}
        response = service.pages().insert(blogId=blog_id, body=body).execute()
        created.append(response["title"])
    return created


if __name__ == "__main__":
    from env_loader import load_env
    load_env()
    email = os.environ.get("BLOG_CONTACT_EMAIL", "")
    if not email:
        print("경고: BLOG_CONTACT_EMAIL이 .env에 없음 — 연락처 페이지에 이메일이 빈 채로 올라감")
    result = create_required_pages(os.environ["BLOGGER_BLOG_ID"], email)
    print(f"생성된 페이지: {result}" if result else "이미 모든 필수 페이지가 존재함, 새로 만든 것 없음")
