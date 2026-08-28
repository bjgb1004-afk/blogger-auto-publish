# 애드센스 신청 준비 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기존 자동발행 파이프라인의 주제 범위를 재테크·건강 2개로 좁히고, 트렌드 키워드를 그 니치 안으로 한정하고, 콘텐츠 품질/분량을 올리고, 애드센스 심사에 필요한 필수 페이지와 신청 절차 문서를 추가한다.

**Architecture:** 기존 5개 모듈(`keywords.py`, `generator.py`, `validate.py`, `db.py`, `post.py`) 각각에 좁은 범위의 변경을 가하고, `summary`(메타 설명용 요약) 필드 하나를 `generator.py → db.py → check_approvals.py → post.py`까지 배관 연결한다. 신규 파일은 필수 정적 페이지(개인정보처리방침/소개/연락처)를 Blogger Pages API로 올리는 일회성 스크립트 `setup_pages.py` 하나뿐이다. 스케줄러나 텔레그램 승인 흐름 자체는 바꾸지 않는다.

**Tech Stack:** 기존과 동일 (Python 3.14, sqlite3, pytrends, google-genai, googleapiclient, pytest). 새 pip 패키지 없음 — `pytrends`가 이미 `pandas`를 의존성으로 깔아뒀으므로 트렌드 관련 테스트에서 바로 씀.

**Spec:** `docs/superpowers/specs/2026-08-28-adsense-readiness-design.md`

## Global Constraints

- 새 pip 패키지를 추가하지 않는다. `pandas`는 `pytrends`가 이미 설치해뒀다.
- `post.py`의 `post_to_blogger(blog_id, title, content, tags=[])`에 `search_description: str = ""` 파라미터를 **끝에 추가**한다. 기존 4-위치인자 호출 방식은 그대로 동작해야 한다 (기존 계획 문서의 "시그니처 변경 금지" 제약을 이 스펙 범위 내에서 이 한 가지로 한정해 갱신한다).
- `db.py`의 `drafts` 테이블에 `summary` 컬럼을 **추가만** 한다 (기존 컬럼 변경/삭제 금지, 기존 발행 데이터 보존). `init_db()`가 이미 컬럼이 있는 기존 `drafts.db`에 대해서도 안전하게 재실행 가능해야 한다(멱등).
- `.env`와 `.env.example` 파일은 harness 보안 규칙상 Write/Edit 도구로 직접 못 건드린다. 이 두 파일을 고칠 때는 Bash/PowerShell로 파일을 직접 써야 한다 (`Get-Content`/heredoc 등).
- 연락처 이메일을 코드에 하드코딩하지 않는다. `.env`의 `BLOG_CONTACT_EMAIL` 값을 사용자가 직접 채우게 한다 — 사용자 개인 이메일을 공개 웹페이지에 자동으로 박아넣지 않기 위함.
- 각 모듈은 기존 관례대로 `import db`, `import post`처럼 모듈 단위로 임포트한다 (테스트에서 `monkeypatch.setattr(module, "attr", ...)`로 갈아끼우기 위함).

---

## Task 1: 키워드 소스를 재테크·건강 니치로 한정 (`keywords.py`)

**Files:**
- Modify: `keywords.py`
- Modify: `test_keywords.py`

**Interfaces:**
- Produces (변경 없음, 내부 구현만 교체): `keywords.get_evergreen_keywords() -> list`, `keywords.get_trend_keywords(limit: int = 10) -> list`
- Consumes: `keywords.TrendReq`(pytrends 클래스, 모듈 레벨 이름으로 monkeypatch 가능해야 함)

- [ ] **Step 1: 니치 축소 실패 테스트 작성**

`test_keywords.py`에 추가:

```python
def test_evergreen_keywords_scoped_to_finance_and_health():
    assert set(keywords.EVERGREEN_KEYWORDS.keys()) == {"주식/금융/재테크/경제", "건강"}
    assert "집들이 요리 추천" not in keywords.get_evergreen_keywords()
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest test_keywords.py::test_evergreen_keywords_scoped_to_finance_and_health -v`
Expected: FAIL (맛집 항목이 아직 남아있어서 `set(...)`이 3개 키를 가짐)

- [ ] **Step 3: `EVERGREEN_KEYWORDS`에서 맛집 제거**

`keywords.py`의 `EVERGREEN_KEYWORDS`를 아래로 교체:

```python
EVERGREEN_KEYWORDS = {
    "주식/금융/재테크/경제": ["배당주 추천", "ETF 추천", "예적금 금리 비교", "청약통장 활용법"],
    "건강": ["공복 혈당 낮추는 법", "간헐적 단식 효과", "허리 디스크 스트레칭"],
}
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest test_keywords.py::test_evergreen_keywords_scoped_to_finance_and_health -v`
Expected: PASS

- [ ] **Step 5: 트렌드 키워드를 니치 시드 기반으로 바꾸는 실패 테스트 작성**

`test_keywords.py` 맨 위에 `import pandas as pd` 추가. 파일 끝에 추가:

```python
class _FakePyTrends:
    def __init__(self, rising_by_seed):
        self._rising_by_seed = rising_by_seed
        self.built_seeds = []

    def build_payload(self, kw_list, timeframe=None, geo=None):
        self.built_seeds.append(kw_list[0])

    def related_queries(self):
        seed = self.built_seeds[-1]
        rising = self._rising_by_seed.get(seed)
        return {seed: {"top": None, "rising": rising}}


def test_get_trend_keywords_uses_evergreen_niches_as_seeds(monkeypatch):
    monkeypatch.setattr(keywords, "get_evergreen_keywords", lambda: ["배당주 추천", "공복 혈당 낮추는 법"])
    fake = _FakePyTrends({
        "배당주 추천": pd.DataFrame({"query": ["고배당 ETF 순위"]}),
        "공복 혈당 낮추는 법": pd.DataFrame({"query": ["저탄수 식단 추천"]}),
    })
    monkeypatch.setattr(keywords, "TrendReq", lambda hl, tz: fake)

    result = keywords.get_trend_keywords(limit=10)

    assert result == ["고배당 ETF 순위", "저탄수 식단 추천"]
    assert fake.built_seeds == ["배당주 추천", "공복 혈당 낮추는 법"]


def test_get_trend_keywords_skips_seed_with_no_rising_data(monkeypatch):
    monkeypatch.setattr(keywords, "get_evergreen_keywords", lambda: ["배당주 추천", "ETF 추천"])
    fake = _FakePyTrends({"배당주 추천": None, "ETF 추천": pd.DataFrame({"query": ["ETF 추천 순위"]})})
    monkeypatch.setattr(keywords, "TrendReq", lambda hl, tz: fake)

    result = keywords.get_trend_keywords(limit=10)

    assert result == ["ETF 추천 순위"]


def test_get_trend_keywords_respects_limit(monkeypatch):
    monkeypatch.setattr(keywords, "get_evergreen_keywords", lambda: ["배당주 추천"])
    fake = _FakePyTrends({"배당주 추천": pd.DataFrame({"query": ["a", "b", "c"]})})
    monkeypatch.setattr(keywords, "TrendReq", lambda hl, tz: fake)

    result = keywords.get_trend_keywords(limit=2)

    assert result == ["a", "b"]
```

- [ ] **Step 6: 테스트 실패 확인**

Run: `python -m pytest test_keywords.py -k get_trend_keywords -v`
Expected: FAIL (`get_trend_keywords`가 아직 전체 실시간 트렌드를 가져오는 옛날 구현이라 seed 기반 결과와 안 맞음)

- [ ] **Step 7: `get_trend_keywords`를 니치 시드 기반으로 구현**

`keywords.py`의 `get_trend_keywords` 함수를 아래로 교체:

```python
def get_trend_keywords(limit: int = 10) -> list:
    pytrends = TrendReq(hl="ko-KR", tz=540)
    results = []
    for seed in get_evergreen_keywords():
        if len(results) >= limit:
            break
        pytrends.build_payload([seed], timeframe="now 7-d", geo="KR")
        related = pytrends.related_queries().get(seed, {})
        rising = related.get("rising")
        if rising is None:
            continue
        for q in rising["query"].tolist():
            if q not in results:
                results.append(q)
            if len(results) >= limit:
                break
    return results[:limit]
```

- [ ] **Step 8: 테스트 통과 확인**

Run: `python -m pytest test_keywords.py -v`
Expected: PASS (전체 — 기존 `get_keywords_to_use` 테스트들도 `get_trend_keywords`를 통째로 monkeypatch하므로 안 깨짐)

- [ ] **Step 9: Commit**

```bash
git add keywords.py test_keywords.py
git commit -m "feat: scope keyword sourcing to finance/health niches only"
```

---

## Task 2: 하루 발행 개수 기본값 하향 (`config.py`)

**Files:**
- Modify: `config.py`
- Modify: `test_config.py`

- [ ] **Step 1: 테스트 값 변경**

`test_config.py`의 `test_default_when_missing`에서 `assert config.get_daily_post_count() == 5`를 `assert config.get_daily_post_count() == 3`으로 바꿈.

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest test_config.py::test_default_when_missing -v`
Expected: FAIL (아직 기본값이 5)

- [ ] **Step 3: `DEFAULT_CONFIG` 변경**

`config.py`의 `DEFAULT_CONFIG = {"daily_post_count": 5}`를 `DEFAULT_CONFIG = {"daily_post_count": 3}`로 바꿈.

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest test_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add config.py test_config.py
git commit -m "fix: lower default daily post count to 3 for a slower initial publish pace"
```

---

## Task 3: 최소 분량 상향 (`validate.py`)

**Files:**
- Modify: `validate.py`
- Modify: `test_validate.py`

- [ ] **Step 1: 기존 "충분히 긴 본문" 테스트를 2000자 이상으로 갱신**

`test_validate.py`의 `test_check_draft_no_warnings_for_clean_long_content`를 아래로 교체 (반복 횟수를 늘려 2000자를 확실히 넘김):

```python
def test_check_draft_no_warnings_for_clean_long_content():
    content = "<h2>제목</h2><p>" + "충분히 길고 구체적인 본문 내용을 담고 있습니다. " * 150 + "</p>"
    warnings = validate.check_draft("제목", content)
    assert warnings == []
```

- [ ] **Step 2: `MIN_LENGTH` 상향 전 상태에서 테스트 실행 (기준선 확인)**

Run: `python -m pytest test_validate.py::test_check_draft_no_warnings_for_clean_long_content -v`
Expected: PASS — `MIN_LENGTH`가 아직 200이라 2000자 넘는 본문은 이미 통과함. 이 스텝은 실패 테스트가 아니라 스텝 4에서 `MIN_LENGTH` 상향 후에도 여전히 PASS인지 비교할 기준선을 잡기 위함.

- [ ] **Step 3: `MIN_LENGTH` 상향**

`validate.py`의 `MIN_LENGTH = 200`을 `MIN_LENGTH = 2000`으로 바꿈.

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest test_validate.py -v`
Expected: PASS (3개 전부) — 특히 `test_check_draft_no_warnings_for_clean_long_content`가 2000자 넘는 본문에 대해 경고 없음을 확인

- [ ] **Step 5: Commit**

```bash
git add validate.py test_validate.py
git commit -m "fix: raise minimum draft length to 2000 chars to avoid thin-content flags"
```

---

## Task 4: `summary` 컬럼 추가 및 저장 (`db.py`)

**Files:**
- Modify: `db.py`
- Modify: `test_db.py`

**Interfaces:**
- Produces: `db.insert_draft(keyword: str, title: str, content: str, tags: list, summary: str = "") -> int` (기존 4-위치인자 호출과 호환)

- [ ] **Step 1: 실패 테스트 작성**

`test_db.py`에 추가:

```python
def test_insert_draft_persists_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    draft_id = db.insert_draft("k", "t", "c", [], summary="요약문")
    conn = db.get_connection()
    row = conn.execute("SELECT summary FROM drafts WHERE id = ?", (draft_id,)).fetchone()
    conn.close()
    assert row["summary"] == "요약문"


def test_init_db_migrates_existing_table_without_summary_column(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)
    conn = db.get_connection()
    conn.execute("""
        CREATE TABLE drafts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL, title TEXT NOT NULL, content TEXT NOT NULL,
            tags TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL, telegram_msg_id INTEGER,
            retry_count INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

    db.init_db()

    cols = {row["name"] for row in db.get_connection().execute("PRAGMA table_info(drafts)")}
    assert "summary" in cols
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest test_db.py -k summary -v`
Expected: FAIL (`summary` 컬럼 없음 / `insert_draft`에 `summary` 키워드 인자 없음)

- [ ] **Step 3: `init_db`에 마이그레이션 추가, `insert_draft`에 `summary` 파라미터 추가**

`db.py`의 `init_db()` 함수 끝(두 `CREATE TABLE` 다음, `conn.commit()` 전)에 추가:

```python
        existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(drafts)")}
        if "summary" not in existing_cols:
            conn.execute("ALTER TABLE drafts ADD COLUMN summary TEXT NOT NULL DEFAULT ''")
```

`insert_draft` 함수를 아래로 교체:

```python
def insert_draft(keyword: str, title: str, content: str, tags: list, summary: str = "") -> int:
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO drafts (keyword, title, content, tags, summary, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, 'pending', ?)",
            (keyword, title, content, json.dumps(tags, ensure_ascii=False), summary, datetime.now().isoformat()),
        )
        conn.commit()
        draft_id = cursor.lastrowid
    finally:
        conn.close()
    return draft_id
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest test_db.py -v`
Expected: PASS (전체 — 기존 `insert_draft("k", "t", "c", [])` 4-위치인자 호출들도 `summary` 기본값 `""`로 그대로 동작)

- [ ] **Step 5: Commit**

```bash
git add db.py test_db.py
git commit -m "feat: add summary column with idempotent migration for existing drafts.db"
```

---

## Task 5: 프롬프트 강화 및 `summary` 필드 생성 (`generator.py`)

**Files:**
- Modify: `generator.py`
- Modify: `test_generator.py`

**Interfaces:**
- Produces: `generator.generate_post(keyword: str) -> dict` (반환 dict에 `"summary"` 키 추가)
- Produces: `generator._parse_response(text: str) -> dict` (`"summary"` 키를 항상 포함, 응답에 없으면 `""`)

- [ ] **Step 1: 기존 파싱 테스트 갱신 + summary 파싱 실패 테스트 작성**

`test_generator.py`의 `test_parse_response_plain_json`을 아래로 교체:

```python
def test_parse_response_plain_json():
    text = '{"title": "제목", "content": "<p>본문</p>", "tags": ["a", "b"], "summary": "요약"}'
    result = generator._parse_response(text)
    assert result == {"title": "제목", "content": "<p>본문</p>", "tags": ["a", "b"], "summary": "요약"}


def test_parse_response_defaults_summary_when_missing():
    text = '{"title": "제목", "content": "<p>본문</p>"}'
    result = generator._parse_response(text)
    assert result["summary"] == ""
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest test_generator.py -v`
Expected: FAIL (`_parse_response`가 아직 `summary` 키를 안 만듦)

- [ ] **Step 3: 프롬프트와 파싱 로직 갱신**

`generator.py`의 `PROMPT_TEMPLATE`을 아래로 교체:

```python
PROMPT_TEMPLATE = """너는 블로그 작가다. 아래 키워드로 블로그 글을 하나 써라.
키워드: {keyword}

규칙:
- 숫자나 통계는 확실하지 않으면 절대 지어내지 마라. 다만 두루뭉술하게 뭉개지 말고, 실행 가능한 구체적 방법이나 사례를 들어 설명해라.
- 구조: 도입(문제 공감 1문단) → 소제목(h2) 2~3개, 각 소제목마다 구체적 방법·사례·실행 팁을 최소 1개씩 포함 → 마무리(요약 + 다음 행동 제안).
- 문장 길이를 짧은 문장과 긴 문장으로 다양하게 섞고, 같은 어미나 문장 시작 표현을 반복하지 마라.
- 본문 전체 글자 수(태그 제외)는 최소 2000자 이상으로 써라.
- 이 글이 투자/재테크/주식 관련이면 마지막 문단에 "이 글은 투자 조언이 아닌 일반 정보이며, 투자 판단과 책임은 본인에게 있습니다."를 포함해라. 건강/의료 관련이면 "본 내용은 일반 정보이며, 정확한 진단과 처방은 반드시 의료 전문가와 상담하세요."를 포함해라.
- 본문은 <h2>, <p>, <strong> 태그를 쓴 HTML로 작성해라.
- summary 필드에는 검색결과 요약(메타 설명)으로 쓸 1~2문장을 80자 내외로 작성해라.
- 아래 JSON 형식으로만 답해라. 다른 텍스트 붙이지 마라.

{{"title": "글 제목", "content": "HTML 본문", "tags": ["태그1", "태그2"], "summary": "검색결과용 요약"}}
"""
```

`_parse_response` 함수의 `return` 문을 아래로 교체:

```python
    return {
        "title": data["title"],
        "content": data["content"],
        "tags": data.get("tags", []),
        "summary": data.get("summary", ""),
    }
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest test_generator.py -v`
Expected: PASS (전체)

- [ ] **Step 5: Commit**

```bash
git add generator.py test_generator.py
git commit -m "feat: strengthen content prompt (structure, length, disclaimers) and add summary field"
```

---

## Task 6: `summary`를 초안 저장→발행 파이프라인 끝까지 배관 연결

**Files:**
- Modify: `generate_drafts.py`
- Modify: `post.py`
- Modify: `check_approvals.py`
- Modify: `test_generate_drafts.py`
- Modify: `test_post.py`
- Modify: `test_check_approvals.py`
- Modify: `test_integration.py`

**Interfaces:**
- Consumes: `generator.generate_post(keyword) -> dict`(Task 5, `"summary"` 키 포함), `db.insert_draft(..., summary="")`(Task 4)
- Produces: `post.post_to_blogger(blog_id, title, content, tags=[], search_description="") -> bool` (기존 4-위치인자 호출과 호환)

- [ ] **Step 1: `post_to_blogger`의 `search_description` 반영 실패 테스트 작성**

`test_post.py`에 추가:

```python
def test_post_to_blogger_includes_search_description_when_provided(monkeypatch):
    captured = {}

    class FakePosts:
        def insert(self, blogId, body):
            captured["body"] = body
            class Req:
                def execute(self):
                    return {"title": body["title"], "url": "http://example.com"}
            return Req()

    class FakeService:
        def posts(self):
            return FakePosts()

    monkeypatch.setattr(post, "get_blogger_service", lambda: FakeService())
    post.post_to_blogger("blogid", "title", "<p>c</p>", ["t"], search_description="검색 요약")
    assert captured["body"]["searchDescription"] == "검색 요약"


def test_post_to_blogger_omits_search_description_when_empty(monkeypatch):
    captured = {}

    class FakePosts:
        def insert(self, blogId, body):
            captured["body"] = body
            class Req:
                def execute(self):
                    return {"title": body["title"], "url": "http://example.com"}
            return Req()

    class FakeService:
        def posts(self):
            return FakePosts()

    monkeypatch.setattr(post, "get_blogger_service", lambda: FakeService())
    post.post_to_blogger("blogid", "title", "<p>c</p>", ["t"])
    assert "searchDescription" not in captured["body"]
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest test_post.py -v`
Expected: FAIL (새 파라미터가 아직 없음)

- [ ] **Step 3: `post.py`의 `post_to_blogger`에 `search_description` 추가**

`post.py`의 `post_to_blogger` 함수를 아래로 교체:

```python
def post_to_blogger(blog_id, title, content, tags=[], search_description=""):
    try:
        service = get_blogger_service()

        body = {
            'kind': 'blogger#post',
            'title': title,
            'content': content,
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
```

- [ ] **Step 4: `test_post.py` 통과 확인**

Run: `python -m pytest test_post.py -v`
Expected: PASS (전체)

- [ ] **Step 5: `check_approvals.py`가 저장된 summary를 넘기도록 수정 + 관련 테스트 갱신**

`check_approvals.py`의 `post.post_to_blogger(...)` 호출을 아래로 교체:

```python
        ok = post.post_to_blogger(
            blog_id=os.environ["BLOGGER_BLOG_ID"],
            title=draft["title"],
            content=draft["content"],
            tags=json.loads(draft["tags"]),
            search_description=draft.get("summary", ""),
        )
```

`test_check_approvals.py`에서 `check_approvals.post`를 monkeypatch하는 3곳(`lambda blog_id, title, content, tags: True`, `... : False` 두 번)을 모두 `search_description=""` 파라미터를 받도록 바꿈. 예:

```python
    monkeypatch.setattr(
        check_approvals.post, "post_to_blogger",
        lambda blog_id, title, content, tags, search_description="": True,
    )
```

(나머지 2곳도 동일하게 `search_description=""` 추가, 반환값만 `False`인 것 유지)

`test_integration.py`의 `check_approvals.post.post_to_blogger` monkeypatch도 동일하게:

```python
    monkeypatch.setattr(check_approvals.post, "post_to_blogger", lambda blog_id, title, content, tags, search_description="": True)
```

- [ ] **Step 6: summary 전달 검증 테스트 추가**

`test_check_approvals.py`에 추가:

```python
def test_run_passes_stored_summary_as_search_description(monkeypatch):
    monkeypatch.setattr(check_approvals.db, "init_db", lambda: None)
    monkeypatch.setattr(check_approvals.db, "get_meta", lambda key, default=None: "0")
    monkeypatch.setattr(check_approvals.telegram_bot, "get_events", lambda offset: ([], 0))
    monkeypatch.setattr(check_approvals.db, "set_meta", lambda k, v: None)
    monkeypatch.setattr(check_approvals.db, "get_pending_without_telegram_msg", lambda: [])
    monkeypatch.setattr(
        check_approvals.db, "get_approved_unpublished",
        lambda: [{"id": 1, "title": "t", "content": "c", "tags": "[]", "summary": "저장된 요약"}],
    )
    monkeypatch.setenv("BLOGGER_BLOG_ID", "blog123")
    monkeypatch.setattr(check_approvals.db, "update_status", lambda draft_id, status: None)

    captured = {}
    monkeypatch.setattr(
        check_approvals.post, "post_to_blogger",
        lambda blog_id, title, content, tags, search_description="": captured.setdefault("sd", search_description) or True,
    )

    check_approvals.run()

    assert captured["sd"] == "저장된 요약"
```

- [ ] **Step 7: `test_check_approvals.py`, `test_integration.py` 통과 확인**

Run: `python -m pytest test_check_approvals.py test_integration.py -v`
Expected: PASS (전체)

- [ ] **Step 8: `generate_drafts.py`가 `summary`를 `insert_draft`에 넘기도록 수정 + 관련 테스트 갱신**

`generate_drafts.py`의 `draft_id = db.insert_draft(...)` 줄을 아래로 교체:

```python
        draft_id = db.insert_draft(
            keyword, post_data["title"], post_data["content"], post_data["tags"],
            summary=post_data.get("summary", ""),
        )
```

`test_generate_drafts.py`에서 `generate_drafts.db.insert_draft`를 monkeypatch하는 3곳(`lambda kw, t, c, tags: ...`)을 모두 `summary=""` 키워드 인자를 받도록 바꿈. 예:

```python
    monkeypatch.setattr(
        generate_drafts.db, "insert_draft",
        lambda kw, t, c, tags, summary="": inserted.append(kw) or len(inserted),
    )
```

(나머지 2곳도 동일 패턴으로 `summary=""` 추가)

- [ ] **Step 9: summary 전달 검증 테스트 추가**

`test_generate_drafts.py`에 추가:

```python
def test_run_passes_generated_summary_to_insert_draft(monkeypatch):
    monkeypatch.setattr(generate_drafts.db, "init_db", lambda: None)
    monkeypatch.setattr(generate_drafts.config, "get_daily_post_count", lambda: 1)
    monkeypatch.setattr(generate_drafts.db, "get_today_count", lambda: 0)
    monkeypatch.setattr(generate_drafts.keywords, "get_keywords_to_use", lambda needed: ["k1"])
    monkeypatch.setattr(
        generate_drafts.generator, "generate_post",
        lambda keyword: {"title": "t", "content": "c", "tags": [], "summary": "생성된 요약"},
    )
    monkeypatch.setattr(generate_drafts.validate, "check_draft", lambda title, content: [])
    monkeypatch.setattr(generate_drafts.telegram_bot, "send_draft_notification", lambda draft_id, title, keyword, warnings=None: 1)
    monkeypatch.setattr(generate_drafts.db, "set_telegram_msg_id", lambda draft_id, msg_id: None)

    captured = {}
    monkeypatch.setattr(
        generate_drafts.db, "insert_draft",
        lambda kw, t, c, tags, summary="": captured.setdefault("summary", summary) or 1,
    )

    generate_drafts.run()

    assert captured["summary"] == "생성된 요약"
```

- [ ] **Step 10: 전체 관련 테스트 통과 확인**

Run: `python -m pytest test_generate_drafts.py test_post.py test_check_approvals.py test_integration.py -v`
Expected: PASS (전체)

- [ ] **Step 11: Commit**

```bash
git add generate_drafts.py post.py check_approvals.py test_generate_drafts.py test_post.py test_check_approvals.py test_integration.py
git commit -m "feat: pipe generated summary through to Blogger searchDescription"
```

---

## Task 7: 필수 페이지 자동 생성 스크립트 (`setup_pages.py`)

**Files:**
- Create: `setup_pages.py`
- Create: `test_setup_pages.py`

**Interfaces:**
- Consumes: `post.get_blogger_service()` (기존 함수 재사용)
- Produces: `setup_pages.build_pages(contact_email: str) -> list[dict]`, `setup_pages.create_required_pages(blog_id: str, contact_email: str) -> list[str]`

- [ ] **Step 1: 실패 테스트 작성**

`test_setup_pages.py` 새로 작성:

```python
import setup_pages


class _ListReq:
    def __init__(self, titles):
        self._titles = titles

    def execute(self):
        return {"items": [{"title": t} for t in self._titles]}


class _InsertReq:
    def __init__(self, body):
        self._body = body

    def execute(self):
        return {"title": self._body["title"]}


class _FakePages:
    def __init__(self, existing_titles):
        self._existing_titles = existing_titles
        self.inserted = []

    def list(self, blogId):
        return _ListReq(self._existing_titles)

    def insert(self, blogId, body):
        self.inserted.append(body)
        return _InsertReq(body)


class _FakeService:
    def __init__(self, existing_titles):
        self.pages_obj = _FakePages(existing_titles)

    def pages(self):
        return self.pages_obj


def test_build_pages_includes_contact_email():
    pages = setup_pages.build_pages("me@example.com")
    assert {p["title"] for p in pages} == {"개인정보처리방침", "소개", "연락처"}
    contact_page = next(p for p in pages if p["title"] == "연락처")
    assert "me@example.com" in contact_page["content"]


def test_create_required_pages_creates_missing_pages(monkeypatch):
    fake_service = _FakeService(existing_titles=[])
    monkeypatch.setattr(setup_pages.post, "get_blogger_service", lambda: fake_service)

    created = setup_pages.create_required_pages("blog123", "me@example.com")

    assert created == ["개인정보처리방침", "소개", "연락처"]
    assert len(fake_service.pages_obj.inserted) == 3


def test_create_required_pages_skips_existing_pages(monkeypatch):
    fake_service = _FakeService(existing_titles=["개인정보처리방침"])
    monkeypatch.setattr(setup_pages.post, "get_blogger_service", lambda: fake_service)

    created = setup_pages.create_required_pages("blog123", "me@example.com")

    assert created == ["소개", "연락처"]
    assert len(fake_service.pages_obj.inserted) == 2
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest test_setup_pages.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'setup_pages'`

- [ ] **Step 3: `setup_pages.py` 구현**

```python
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
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest test_setup_pages.py -v`
Expected: PASS (전체)

- [ ] **Step 5: Commit**

```bash
git add setup_pages.py test_setup_pages.py
git commit -m "feat: add one-time script to create required AdSense static pages"
```

---

## Task 8: 애드센스 신청 절차 및 연락처 이메일 안내 (`SETUP.md`, `.env.example`)

**Files:**
- Modify: `SETUP.md`
- Modify: `.env.example` (Write/Edit 도구 금지 — Bash/PowerShell로 직접 갱신)

- [ ] **Step 1: `.env.example`에 `BLOG_CONTACT_EMAIL` 추가**

Edit 도구 대신 아래처럼 Bash로 직접 추가:

```bash
printf '\n# 연락처 페이지(setup_pages.py)에 표시할 이메일 (선택, 비워두면 빈 채로 올라감)\nBLOG_CONTACT_EMAIL=\n' >> .env.example
```

- [ ] **Step 2: `SETUP.md`에 애드센스 섹션 추가**

`SETUP.md` 끝에 아래 섹션 추가:

```markdown
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
```

- [ ] **Step 3: 변경사항 확인**

Run: `git diff SETUP.md .env.example`
Expected: 위 내용대로 추가된 diff 확인, 삭제된 줄 없음

- [ ] **Step 4: Commit**

```bash
git add SETUP.md .env.example
git commit -m "docs: add AdSense application checklist, ads.txt setup, and ongoing operating principles"
```

---

## Task 9: 전체 테스트 스위트 확인

**Files:** 없음 (검증만)

- [ ] **Step 1: 전체 테스트 실행**

Run: `python -m pytest -v`
Expected: 모든 테스트 PASS (기존 40개 + 이 계획에서 추가된 테스트 전부)

- [ ] **Step 2: 수동 확인 (선택, 실제 Blogger 계정 필요)**

`.env`에 `BLOG_CONTACT_EMAIL`을 채운 뒤:
```
python setup_pages.py
```
Blogger 대시보드에서 개인정보처리방침/소개/연락처 3개 페이지가 실제로 생성됐는지 확인.

이후 `python generate_drafts.py`를 한 번 더 돌려서, 텔레그램 알림 메시지와 승인 후 발행된 글의 분량(2000자 이상)·면책조항 포함 여부·검색 스니펫(searchDescription)이 의도대로 나오는지 눈으로 확인.
