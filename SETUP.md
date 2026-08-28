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

## 5. GitHub Actions로 무인 실행 등록
PC가 꺼져있어도 돌아가도록 Windows 작업 스케줄러 대신 GitHub Actions를 씀 (`.github/workflows/generate-drafts.yml`, `.github/workflows/check-approvals.yml`).

1. GitHub에 새 저장소 생성 (private 권장)
2. 로컬 저장소를 push: `git remote add origin <저장소 URL>` → `git push -u origin feature/blog-auto-publish`
3. 저장소 Settings → Secrets and variables → Actions → New repository secret 에서 아래 등록:
   - `GEMINI_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `BLOGGER_BLOG_ID`: `.env`에 넣은 값 그대로
   - `GOOGLE_CREDENTIALS_JSON`: `credentials.json` 파일 내용 그대로 붙여넣기
   - `GOOGLE_TOKEN_JSON`: `token.json` 파일 내용 그대로 붙여넣기 (4단계에서 브라우저 로그인으로 이미 만들어둔 파일)
4. push 직후 저장소의 Actions 탭에서 두 워크플로가 보임. 각각 "Run workflow" 버튼으로 1회 수동 실행해서 정상 동작 확인
5. 이후로는 자동: `generate-drafts`는 하루 5번(KST 09/12/15/18/21시, 1개씩), `check-approvals`는 10분마다 실행됨

`drafts.db`, `config.json`은 실행마다 저장소에 자동 커밋되어 상태가 이어짐 — 별도 DB 서비스 필요 없음.

## 6. 애드센스 신청 준비

### 신청 전 체크리스트
- [ ] 재테크·건강 글을 합쳐 최소 15~20개 이상 발행했는가 (공식 최소 기준은 없지만 이 정도는 쌓고 신청하는 게 안전함)
- [ ] `python setup_pages.py`를 1회 실행해서 개인정보처리방침/소개/연락처 페이지가 Blogger에 올라갔는가
- [ ] `.env`의 `BLOG_CONTACT_EMAIL`을 실제 연락 가능한 이메일로 채웠는가
- [ ] Blogger 테마 내비게이션에서 방금 만든 3개 페이지로 이동 가능한가 (Blogger 레이아웃 편집에서 "페이지 목록" 가젯 추가)

### 신청 절차
1. https://www.google.com/adsense 접속 → 구글 계정으로 가입
2. "사이트 추가"에서 블로그 URL 입력
3. 발급된 애드센스 코드(또는 Blogger의 "수익" 탭에서 애드센스 계정 연결)를 등록
4. 심사 대기 (수일~수 주 소요, 케이스마다 다름)

### 승인 후: 실제로 광고 띄우기
1. 애드센스에서 발급된 `ads.txt` 내용을 확인
2. Blogger 대시보드 → 설정 → "ads.txt 맞춤설정"에 붙여넣기 (Blogger가 자동으로 루트에 서빙함)
3. Blogger 대시보드 → 수익 탭에서 애드센스 계정 연결 → 자동 광고 또는 위젯 배치 선택

### 운영 원칙 (승인 이후에도 계속 적용됨)
애드센스 정책은 승인 시점에만 적용되는 게 아니라 계속 적용된다. 승인 후에도:
- 발행 개수를 급격히 늘리지 말고 몇 주에 걸쳐 서서히 늘릴 것
- 텔레그램 승인 단계에서 포맷 체크(`validate.py`)뿐 아니라 "실제로 도움이 되는 글인가"를 사람이 직접 판단할 것
- 주제를 넓히고 싶으면 `keywords.py`의 `EVERGREEN_KEYWORDS`에 니치를 하나씩 추가하며 반응을 지켜볼 것
