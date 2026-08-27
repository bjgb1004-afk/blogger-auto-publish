# 셋업 가이드

## 1. 값 채우기
`.env.example`을 `.env`로 복사하고 채운다:
- `GEMINI_API_KEY`: https://aistudio.google.com/apikey 에서 무료로 발급
- `TELEGRAM_BOT_TOKEN`: 텔레그램에서 @BotFather에게 `/newbot` 실행해서 발급
- `TELEGRAM_CHAT_ID`: 만든 봇과 대화 시작 후, 브라우저로
  `https://api.telegram.org/bot<TOKEN>/getUpdates` 접속해서 `chat.id` 값 확인
- `BLOGGER_BLOG_ID`: 이미 기본값 채워져 있음(기존 post.py에서 쓰던 블로그)

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

## 5. 스케줄러 등록
```
python register_tasks.py
```
`generate_drafts.py`는 2시간마다, `check_approvals.py`는 10분마다 자동 실행되도록 등록됨.
확인: 작업 스케줄러(taskschd.msc)에서 `BlogAuto_GenerateDrafts`, `BlogAuto_CheckApprovals` 두 작업이 보이면 성공.
