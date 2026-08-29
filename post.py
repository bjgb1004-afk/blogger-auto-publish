import sys

try:
    if sys.stdout.encoding != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

from googleapiclient.discovery import build

from google_auth import get_credentials

# 1. API 로그인 인증 서비스 생성 함수
def get_blogger_service():
    return build('blogger', 'v3', credentials=get_credentials())

# 2. 구글 블로그에 글을 자동 포스팅하는 함수
def post_to_blogger(blog_id, title, content, tags=[], search_description=""):
    try:
        service = get_blogger_service()

        # 발행할 포스팅 데이터 구조
        body = {
            'kind': 'blogger#post',
            'title': title,
            'content': content,  # HTML 태그 지원 (<h2>, <p>, <img> 등)
            'labels': tags
        }
        if search_description:
            body['searchDescription'] = search_description

        posts = service.posts()
        response = posts.insert(blogId=blog_id, body=body).execute()
        
        print("=" * 50)
        print("🎉 구글 블로그 자동 포스팅 성공!")
        print(f"📌 글 제목: {response['title']}")
        print(f"🔗 포스팅 URL: {response['url']}")
        print("=" * 50)
        return True

    except Exception as e:
        print(f"❌ 포스팅 중 오류 발생: {e}")
        return False

# 3. 메인 실행 영역
if __name__ == '__main__':
    # 설정하신 구글 블로그 ID (19자리)
    MY_BLOG_ID = '6119363643599838869'
    
    # 테스트 발행할 글 제목, 본문, 태그 설정
    test_title = "Python Blogger API 첫 자동 포스팅 성공!"
    
    test_content = """
    <h2>안녕하세요! 파이썬 자동 포스팅 테스트입니다.</h2>
    <p>Blogger API v3를 활용하여 생성된 포스팅입니다.</p>
    <p><strong>HTML 태그</strong>를 이용해 글자 스타일, 이미지, 링크 등을 자유롭게 적용할 수 있습니다.</p>
    """
    
    test_tags = ["파이썬", "BloggerAPI", "자동화테스트"]
    
    # 포스팅 실행
    post_to_blogger(MY_BLOG_ID, test_title, test_content, test_tags)