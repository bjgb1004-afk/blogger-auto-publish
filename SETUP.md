# 셋업 가이드

## 1. 값 채우기
`.env.example`을 `.env`로 복사하고 채운다:
- `GEMINI_API_KEY`: https://aistudio.google.com/apikey 에서 무료로 발급
- `TELEGRAM_BOT_TOKEN`: 텔레그램에서 @BotFather에게 `/newbot` 실행해서 발급
- `TELEGRAM_CHAT_ID`: 만든 봇과 대화 시작 후, 브라우저로
  `https://api.telegram.org/bot<TOKEN>/getUpdates` 접속해서 `chat.id` 값 확인
- `BLOGGER_BLOG_ID`: 이미 기본값 채워져 있음(기존 post.py에서 쓰던 블로그)

### Google OAuth (`credentials.json`) 준비
Blogger API로 글을 올리려면 구글 OAuth 클라이언트가 필요합니다:
1. https://console.cloud.google.com/apis/credentials 에서 프로젝트 생성(또는 기존 프로젝트 선택)
2. "라이브러리"에서 Blogger API v3 검색 후 사용 설정
3. "사용자 인증 정보 만들기" → "OAuth 클라이언트 ID" → 애플리케이션 유형 "데스크톱 앱"으로 생성
4. 다운로드한 JSON 파일을 `credentials.json`이라는 이름으로 프로젝트 폴더에 저장

## 2. 초기 발행 개수 설정 (선택)
`config.json`이 없으면 첫 실행 때 자동으로 `{"daily_post_count": 5}`로 생성됨.
바꾸고 싶으면 직접 숫자를 고치거나, 나중에 텔레그램으로 `/count 3` 처럼 보내면 됨.

## 3. 의존성 설치
```
pip install -r requirements.txt
```

## 4. 통합 테스트 (1회 수동 실행)
```
python generate_drafts.py
```
텔레그램으로 알림 오는지 확인 → 승인 버튼 클릭 →
```
python check_approvals.py
```
Blogger에 실제로 글이 올라가는지 확인.

**주의:** 이 첫 실행에서 브라우저가 열려 구글 로그인을 요청합니다 — 반드시 사람이 있는 상태에서 최소 한 번은 `check_approvals.py`(또는 `post.py`)를 직접 실행해서 `token.json`을 만들어 두어야 합니다. 이 과정을 건너뛰고 바로 스케줄러에 등록하면, 첫 스케줄 실행이 브라우저 콜백을 기다리며 무한정 멈춥니다.

## 5. 스케줄러 등록
```
python register_tasks.py
```
**주의:** Windows의 스케줄 등록은 관리자 권한(Run as Administrator)이 필요합니다. 권한 오류가 나면 PowerShell을 관리자 권한으로 다시 실행하세요.

`generate_drafts.py`는 2시간마다, `check_approvals.py`는 10분마다 자동 실행되도록 등록됨.
확인: 작업 스케줄러(taskschd.msc)에서 `BlogAuto_GenerateDrafts`, `BlogAuto_CheckApprovals` 두 작업이 보이면 성공.
