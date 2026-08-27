# 블로그 자동 발행 시스템 설계

## 목표
비용 0원으로 하루 5개 이상 블로그 글(트렌드+에버그린 키워드 기반)을 초안-승인-발행까지 자동화한다. 분야: 주식/금융/재테크/경제, 건강, 맛집.

## 아키텍처 (구조 A)
Windows 작업 스케줄러가 두 스크립트를 각각 다른 주기로 실행한다. 상시 실행 프로세스 없음.

```
[작업스케줄러: 2시간마다]                  [작업스케줄러: 5~10분마다]
  generate_drafts.py                      check_approvals.py
    config.json에서 daily_post_count 읽음     텔레그램 응답 폴링(getUpdates)
    오늘 이미 만든 개수 vs 목표 비교              /count 명령 오면 config.json 갱신
    모자란 만큼만 키워드 수집+생성                승인된 draft만 post_to_blogger() 호출
    → drafts.db(sqlite)에 status=pending      → 발행 성공 시 status=published
    → 텔레그램으로 알림 전송                   → 실패 시 status=approved 유지(다음 주기 재시도)
```

## 컴포넌트
- **config.json**: `{"daily_post_count": 5}`. `generate_drafts.py`가 매 실행마다 이 값과 오늘 생성분(drafts.db 기준) 비교해 모자란 만큼만 생성 — 목표 채워지면 그 실행은 스킵. 값 자체는 텔레그램으로 그때그때 변경 가능(아래 telegram.py 참고), 작업스케줄러는 안 건드림.
- **keywords.py**: 구글 트렌드 실시간 키워드(`pytrends`) + 분야별 고정 에버그린 키워드 리스트. 최근 30일 내 사용한 키워드는 `drafts.db`에서 조회해 제외(중복 방지).
- **generator.py**: Gemini 무료 API(`google-generativeai`)로 키워드 → 제목+HTML 본문 생성. 프롬프트에 "숫자/수치는 확실하지 않으면 쓰지 마라" 명시(금융/건강 분야 안전장치).
- **drafts.db** (sqlite3, 표준라이브러리): 테이블 `drafts(id, keyword, title, content, tags, status, created_at, telegram_msg_id, retry_count)`. status: pending → approved/rejected → published/failed.
- **telegram.py**: `requests`로 Bot API 직접 호출. `generate_drafts.py`가 알림 전송(제목+요약, 인라인 버튼 승인/거부), `check_approvals.py`가 `getUpdates`로 콜백/명령 읽어 처리. 명령 `/count 5` 처럼 보내면 `config.json`의 `daily_post_count` 즉시 갱신.
- **generate_drafts.py**: 스케줄러 진입점 #1. config 확인 → keywords → generator → drafts.db 저장 → telegram 알림.
- **check_approvals.py**: 스케줄러 진입점 #2. telegram 폴링 → 승인/거부 콜백이면 status 갱신, `/count` 명령이면 config.json 갱신 → approved 건 `post.py`의 `post_to_blogger()` 호출(기존 코드 재사용, 수정 없음).

## 에러 처리
- Gemini 호출 실패: 로그 남기고 해당 키워드 skip, 다음으로 진행 (전체 배치 중단 안 함).
- Blogger 발행 실패: status를 `approved`로 유지 + `retry_count` 증가. `retry_count`가 5 넘으면 텔레그램으로 실패 알림.
- 텔레그램 API 실패: 로그만 남기고 스크립트 정상 종료 (다음 스케줄에서 재시도되므로 별도 복구 로직 불필요).
- 모든 스크립트: 파일 로그(`app.log`)에 실행 시각+결과 한 줄 남김 — 나중에 뭐가 왜 실패했는지 추적용.

## 검수(발행 전 자동 체크)
승인은 사람이 하지만, 승인 전에 최소한의 기계적 체크는 자동으로: 본문 길이(너무 짧으면 reject 후보로 표시), HTML 태그 짝 안 맞으면 경고 태그 추가. 사실검증 자체는 사람 승인이 담당 — AI가 자동으로 사실 확인하는 기능은 만들지 않음(범위 밖, YAGNI).

## 테스트
각 스크립트에 `if __name__ == '__main__':` 블록으로 최소 self-check 포함:
- `keywords.py`: 키워드 리스트 하나 이상 나오는지, 중복 제외 로직이 최근 항목 걸러내는지
- `generator.py`: 임의 키워드 하나로 실제 생성 호출 1회(수동 실행 시에만, 스케줄 실행엔 포함 안 함)
- `telegram.py`: 봇 토큰/챗ID 세팅 후 테스트 메시지 전송 1회
- 통합: `generate_drafts.py` 1회 수동 실행 → drafts.db에 pending row 생기고 텔레그램 알림 오는지 확인 → 승인 버튼 클릭 → `check_approvals.py` 수동 실행 → Blogger에 실제 발행되는지 확인

## 스케줄러 등록
설계 승인 후 구현 단계에서 `schtasks` 명령으로 두 작업 등록 (`generate_drafts.py` 2시간마다 / `check_approvals.py` 5~10분마다 — 고정, 개수 조절은 config.json으로 함). 사용자 입력 필요: 초기 `daily_post_count` 값, 텔레그램 봇 토큰+챗ID(BotFather로 직접 생성).

## 범위 밖 (지금 안 만드는 것)
- 완전 자동발행(사람 승인 없이) — 나중에 패턴 잡히면 전환
- AI 자동 팩트체크
- 여러 블로그/채널 동시 지원
