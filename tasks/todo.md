# blogspot 주제 전환 + 파이프라인 분리

작성 2026-09-16 / 브랜치 `feature/blog-auto-publish`

## 배경

blogspot 글 41개가 **전량 미색인**이다. 원인은 기술 오류가 아니라 구글의 크롤 거부(`Discovered - currently not indexed` 19건)로, 신규 저권위 도메인에 하루 5개씩 쏟아붓는 패턴 + YMYL(재테크·건강) 주제 조합이 겹친 결과다. YMYL은 구글이 E-E-A-T를 가장 혹독하게 적용하는 영역이라 익명 자동생성 블로그가 가장 못 뚫는다.

그래서 blogspot을 **영어 K-culture**로 돌린다. 애드센스가 달린 티스토리는 한국어 재테크·건강을 유지해 수익을 담당한다.

문제는 현재 티스토리 원고가 blogspot 글에서 **파생**된다는 것(`generate_drafts.py:63` `_vary_for_repost`). 주제도 언어도 갈라지면 파생이 불가능하므로 파이프라인을 둘로 쪼갠다.

## 목표 구조

| 트랙 | 출력 | 언어 | 주제 | 발행 방식 | 하루 |
|---|---|---|---|---|---|
| `blogspot` | Blogger API | 영어 | K-culture | 자동 발행 | 2 |
| `tistory` | 텔레그램 원고 | 한국어 | 재테크 + 건강 | 수동 복붙 | 3 |

두 트랙은 키워드 풀·프롬프트·발행 경로가 완전히 독립이다. 파생 관계 없음.

## 확정된 결정

- 기존 blogspot 41개는 **전부 삭제**. 색인이 0이라 검색 손실이 없고, 저품질 대량 글이 남으면 새 영어 글 평가까지 끌어내린다.
- 티스토리 주제는 재테크 + 건강 그대로. `keywords.py`의 기존 100개 풀과 `pubmed.py` 연동을 통째로 물려받는다.
- 발행량 blogspot 2 / 티스토리 3.

## 작업 항목

- [x] `config.json` 발행량 5 → 2 (임시 조치, 아래 트랙별 설정으로 대체)
- [x] **db.py** — `drafts`에 `track` 컬럼 추가 (기본값 `'tistory'`, 기존 20건은 전부 한국어 재테크라 이 값이 맞다). 기존 `summary`/`image_prompt_en`과 동일한 `ALTER` 패턴 사용. `get_today_count()`, `get_recent_keywords()`, `get_unpublished()`를 트랙별로 필터.
- [x] **config.py** — `daily_post_count`를 `{"blogspot": 2, "tistory": 3}` 형태로 교체. `get_daily_post_count(track)` / `set_daily_post_count(track, n)`. 정수→dict 마이그레이션 코드는 넣지 않는다(config.json은 리포에 커밋되니 한 번 바꾸면 끝, YAGNI).
- [x] **keywords.py** — 기존 `EVERGREEN_KEYWORDS`는 티스토리 전용으로 그대로 유지. 영어 `K_CULTURE_KEYWORDS` 풀 신규 작성(음식·뷰티·언어·여행·드라마/영화·음악·예절/문화·쇼핑 카테고리, 롱테일 질문형). `get_keywords_to_use(track, needed_count)`로 분기 — 티스토리는 기존 pytrends + naver_trends 정렬 로직, blogspot은 영어 풀만 사용(pytrends/naver는 한국어 전용이라 영어 트랙에서 스킵).
- [x] **generator.py** — 기존 `PROMPT_TEMPLATE`은 티스토리용으로 유지. 영어 `KCULTURE_PROMPT_TEMPLATE` 신규(투자/의료 면책 문구 로직 없음, `health_topic_en` 없음, `image_prompt_en`은 유지). `generate_post(keyword, track)`.
- [x] **generate_drafts.py** — `_vary_for_repost()` 삭제(파생 구조 폐기). `publish()`를 트랙 분기: `blogspot`은 기존 `post_to_blogger` + 발행 알림, `tistory`는 `send_tistory_copy`로 원고만 보내고 상태를 `sent`로. `run()`을 트랙 루프로 재구성. `pubmed` 첨부는 티스토리 트랙에서만.
- [x] **telegram_bot.py** — `/count N` → `/count <track> N`으로 확장.
- [x] **테스트 갱신** — `test_db.py`, `test_config.py`, `test_keywords.py`, `test_generator.py`, `test_generate_drafts.py`, `test_integration.py`.
- [x] **기존 pending 5건 처리** — 한국어 재테크 초안이므로 `track='tistory'`로 넘겨 텔레그램 원고로 소진. 폐기하지 않는다.
- [x] **blogspot 41개 삭제** — `posts().delete()` 스크립트. **되돌릴 수 없으므로 코드 작업을 전부 끝내고 마지막에, 실행 직전 한 번 더 확인받는다.**
- [x] **커밋 + push** — GitHub Actions가 실제 실행 주체라 push 전까지는 아무것도 반영되지 않는다.

## 검증

- 코드 변경 후 `pytest` 전체 통과
- `GENERATE_MAX_PER_RUN`을 1로 두고 로컬 1회 실행 → 두 트랙이 각자 경로로 나가는지 확인
- **주의(CLAUDE.md #4)**: 로컬 수동 실행 성공은 "코드 버그 없음"만 증명한다. GitHub Actions cron이 무인으로 도는 것까지 확인해야 완료다. 다음 트리거 이후 `app.log`와 워크플로 실행 이력을 직접 확인할 것.

## 이번 작업으로 해결되지 않는 것

- **색인은 즉시 안 뚫린다.** 크롤 거부는 신호를 바꾼 뒤 구글이 재평가할 때까지 수 주가 걸린다.
- Search Console 성과 숫자는 속성 등록이 2026-09-16이라 소급되지 않는다. 3일 지연까지 감안해 2026-09-19~20부터 `python seo_report.py`에 숫자가 나온다.
- `Redirect error` 14건(`?m=1`)은 Blogger 플랫폼 동작이라 손댈 수단이 없다. 원인도 아니라고 결론냈다.
- 커스텀 도메인 연결(`gzclab.com` 등 보유 중)은 권위 신호 측면에서 남은 선택지지만 이번 범위 밖이다.

## 리뷰

2026-09-16 완료.

- 두 트랙이 키워드 풀·프롬프트·발행 경로까지 완전히 독립. 파생 구조(`_vary_for_repost`,
  `rewrite_for_repost`)는 삭제했다. Gemini 호출도 글당 1회로 줄었다(기존엔 재작성까지 2회).
- 기존 blogspot 글은 41개가 아니라 **42개**였고 전량 삭제했다. 삭제 후 목록 조회 0개 확인.
- 영어 트랙 로컬 1회 실행 성공:
  `how to eat Korean BBQ like a local` → https://korean-culture4you.blogspot.com/2026/09/how-do-locals-actually-eat-korean-bbq.html
  (본문 9,231자, 영어 슬러그, summary/image_prompt_en 정상)
- **로컬 `drafts.db`가 원격보다 22건 뒤처져 있었다.** 로컬은 20건(5건 pending)인데 원격은
  Actions가 계속 돌려 42건 전량 published 상태였고, 방금 삭제한 blogspot 42개와 정확히 일치한다.
  즉 "pending 5건"은 로컬만의 착시였고 실제로는 이미 발행·전달이 끝난 글이다. 로컬 DB를 밀면
  22건의 발행 이력이 사라져 같은 키워드로 중복 생성될 뻔했다. 원격 DB를 정본으로 채택하고
  `track` 마이그레이션(42건 전부 tistory) + 영어 글 1건을 blogspot 레코드로 옮겨 넣었다.
  → 진단·작업 전 `git pull` 필수. 이번에도 이걸 건너뛰어 리베이스 충돌로 뒤늦게 발견했다.
- `pytest` 82개 전부 통과.

### 미확인 (CLAUDE.md #4)
로컬 수동 실행만 성공했다. **GitHub Actions cron 무인 실행은 아직 검증 안 됨.**
다음 트리거(KST 09/12/15/18/21시 07분) 이후 워크플로 실행 이력과 `app.log`를 직접 확인해야
완료다. 특히 확인할 것: 한 실행에 `GENERATE_MAX_PER_RUN=2`라 blogspot 2건이 먼저 나가고
다음 실행부터 tistory가 도는 순서가 실제로 맞는지.
