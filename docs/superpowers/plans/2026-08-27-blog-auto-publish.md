# 블로그 자동 발행 시스템 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 트렌드+에버그린 키워드로 Gemini가 초안을 만들고, 텔레그램 승인을 거쳐 기존 Blogger 발행 코드(`post.py`)로 자동 발행하는 파이프라인을 만든다.

**Architecture:** 상시 실행 프로세스 없이, Windows 작업 스케줄러가 `generate_drafts.py`(2시간마다)와 `check_approvals.py`(10분마다) 두 스크립트를 각각 실행한다. 상태는 `drafts.db`(sqlite3)에 저장, 발행 개수 목표는 `config.json`에 저장하고 텔레그램 `/count` 명령으로 즉시 바꿀 수 있다.

**Tech Stack:** Python 3.14, sqlite3(표준라이브러리), `requests`(이미 설치됨), 신규 설치 `pytrends`·`google-genai`(Gemini 공식 통합 SDK — 구버전 `google-generativeai`는 2025년 지원 종료됐으므로 사용 안 함), pytest(이미 설치됨).

**Spec:** `docs/superpowers/specs/2026-08-27-blog-auto-publish-design.md`

## Global Constraints

- 새 pip 패키지는 `pytrends`, `google-genai` 두 개만 추가한다. 그 외는 표준라이브러리(`sqlite3`, `json`, `logging`)나 이미 설치된 패키지(`requests`, `pytest`)로 해결한다.
- `post.py`의 `post_to_blogger(blog_id, title, content, tags=[])` 시그니처는 바꾸지 않는다 — 반환값만 추가한다(성공 True / 실패 False).
- 스케줄러 트리거 주기는 고정(`generate_drafts.py` 2시간마다, `check_approvals.py` 10분마다)이다. 하루 발행 개수 조절은 `config.json`의 `daily_post_count` 값으로만 한다 — 스케줄러 자체는 건드리지 않는다.
- 발행 전 사람 승인 필수 — 텔레그램 승인 없이는 어떤 draft도 `post_to_blogger`를 호출하지 않는다.
- "오늘"과 스케줄 시각은 시스템 로컬 시간(Asia/Seoul) 기준이다.
- 각 모듈은 `import db`, `import config` 처럼 모듈 단위로 임포트한다(함수 개별 임포트 금지) — 테스트에서 `monkeypatch.setattr(module, "attr", ...)`로 갈아끼우기 위함.
- 파일은 전부 프로젝트 루트(`blogger_auto/`)에 평평하게 둔다. 패키지화(`__init__.py`) 안 함 — 단일 목적 스크립트 모음이라 과함.
- 테스트 파일은 해당 모듈과 같은 디렉터리에 `test_<module>.py`로 둔다(별도 `tests/` 폴더나 `conftest.py` 없이 pytest가 바로 import하게).

---

## Task 1: 프로젝트 스캐폴딩 (git, 의존성, config, env 로더)

**Files:**
- Create: `.gitignore`
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `config.py`
- Create: `test_config.py`
- Create: `env_loader.py`
- Create: `test_env_loader.py`

**Interfaces:**
- Produces: `config.get_daily_post_count() -> int`, `config.set_daily_post_count(count: int) -> None`, `config.CONFIG_PATH` (모듈 상수, 테스트에서 monkeypatch 대상)
- Produces: `env_loader.load_env() -> None`, `env_loader.ENV_PATH` (모듈 상수)

- [ ] **Step 1: git 저장소 초기화 및 .gitignore**

```bash
git init
```

```
# .gitignore
.env
token.json
credentials.json
*.db
__pycache__/
*.pyc
app.log
```

- [ ] **Step 2: requirements.txt와 .env.example 작성**

```
# requirements.txt
requests
pytrends
google-genai
```

```
# .env.example
GEMINI_API_KEY=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
BLOGGER_BLOG_ID=6119363643599838869
```

- [ ] **Step 3: 신규 패키지 설치**

Run: `pip install pytrends google-genai`
Expected: 설치 성공, 에러 없음

- [ ] **Step 4: config.py 실패 테스트 작성**

```python
# test_config.py
import json
import config


def test_default_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.json")
    assert config.get_daily_post_count() == 5
    assert (tmp_path / "config.json").exists()


def test_set_and_get_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.json")
    config.set_daily_post_count(8)
    assert config.get_daily_post_count() == 8
    data = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert data["daily_post_count"] == 8
```

- [ ] **Step 5: 테스트 실패 확인**

Run: `python -m pytest test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'config'`

- [ ] **Step 6: config.py 구현**

```python
# config.py
import json
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.json"
DEFAULT_CONFIG = {"daily_post_count": 5}


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        save_config(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config_data: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config_data, f, ensure_ascii=False, indent=2)


def get_daily_post_count() -> int:
    return load_config().get("daily_post_count", DEFAULT_CONFIG["daily_post_count"])


def set_daily_post_count(count: int) -> None:
    data = load_config()
    data["daily_post_count"] = count
    save_config(data)
```

- [ ] **Step 7: 테스트 통과 확인**

Run: `python -m pytest test_config.py -v`
Expected: PASS (2 passed)

- [ ] **Step 8: env_loader.py 실패 테스트 작성**

```python
# test_env_loader.py
import os
import env_loader


def test_load_env_sets_missing_vars(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("FOO_TEST_KEY=bar\n# comment\n\nBAZ=qux\n", encoding="utf-8")
    monkeypatch.setattr(env_loader, "ENV_PATH", env_file)
    monkeypatch.delenv("FOO_TEST_KEY", raising=False)
    monkeypatch.delenv("BAZ", raising=False)
    env_loader.load_env()
    assert os.environ["FOO_TEST_KEY"] == "bar"
    assert os.environ["BAZ"] == "qux"


def test_load_env_does_not_override_existing(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("FOO_TEST_KEY=fromfile\n", encoding="utf-8")
    monkeypatch.setattr(env_loader, "ENV_PATH", env_file)
    monkeypatch.setenv("FOO_TEST_KEY", "already_set")
    env_loader.load_env()
    assert os.environ["FOO_TEST_KEY"] == "already_set"
```

- [ ] **Step 9: 테스트 실패 확인**

Run: `python -m pytest test_env_loader.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'env_loader'`

- [ ] **Step 10: env_loader.py 구현**

```python
# env_loader.py
import os
from pathlib import Path

ENV_PATH = Path(__file__).parent / ".env"


def load_env() -> None:
    if not ENV_PATH.exists():
        return
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())
```

- [ ] **Step 11: 테스트 통과 확인**

Run: `python -m pytest test_env_loader.py -v`
Expected: PASS (2 passed)

- [ ] **Step 12: Commit**

```bash
git add .gitignore requirements.txt .env.example config.py test_config.py env_loader.py test_env_loader.py
git commit -m "feat: add config and env loading scaffolding"
```

---

## Task 2: drafts.db (sqlite3) 데이터 계층

**Files:**
- Create: `db.py`
- Create: `test_db.py`

**Interfaces:**
- Consumes: 없음 (표준라이브러리만)
- Produces: `db.DB_PATH`, `db.get_connection()`, `db.init_db() -> None`, `db.insert_draft(keyword: str, title: str, content: str, tags: list) -> int`, `db.set_telegram_msg_id(draft_id: int, msg_id: int) -> None`, `db.get_today_count() -> int`, `db.get_recent_keywords(days: int = 30) -> set`, `db.update_status(draft_id: int, status: str) -> None`, `db.increment_retry(draft_id: int) -> int`, `db.get_approved_unpublished() -> list[dict]`, `db.get_meta(key: str, default: str = None) -> str`, `db.set_meta(key: str, value: str) -> None`

- [ ] **Step 1: 실패 테스트 작성**

```python
# test_db.py
import json
from datetime import datetime, timedelta

import db


def test_insert_and_get_today_count(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    assert db.get_today_count() == 0
    draft_id = db.insert_draft("키워드1", "제목1", "<p>본문</p>", ["태그1"])
    assert isinstance(draft_id, int)
    assert db.get_today_count() == 1


def test_recent_keywords_excludes_old(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    db.insert_draft("최근키워드", "t", "c", [])
    conn = db.get_connection()
    old_date = (datetime.now() - timedelta(days=40)).isoformat()
    conn.execute("UPDATE drafts SET created_at = ? WHERE keyword = '최근키워드'", (old_date,))
    conn.commit()
    conn.close()
    assert "최근키워드" not in db.get_recent_keywords(days=30)


def test_update_status_and_approved_unpublished(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    draft_id = db.insert_draft("k", "t", "c", ["a", "b"])
    db.update_status(draft_id, "approved")
    approved = db.get_approved_unpublished()
    assert len(approved) == 1
    assert approved[0]["id"] == draft_id
    assert json.loads(approved[0]["tags"]) == ["a", "b"]


def test_increment_retry(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    draft_id = db.insert_draft("k", "t", "c", [])
    assert db.increment_retry(draft_id) == 1
    assert db.increment_retry(draft_id) == 2


def test_meta_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    assert db.get_meta("telegram_offset", "0") == "0"
    db.set_meta("telegram_offset", "42")
    assert db.get_meta("telegram_offset") == "42"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest test_db.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'db'`

- [ ] **Step 3: db.py 구현**

```python
# db.py
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "drafts.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS drafts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            tags TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            telegram_msg_id INTEGER,
            retry_count INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.commit()
    conn.close()


def insert_draft(keyword: str, title: str, content: str, tags: list) -> int:
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO drafts (keyword, title, content, tags, status, created_at) "
        "VALUES (?, ?, ?, ?, 'pending', ?)",
        (keyword, title, content, json.dumps(tags, ensure_ascii=False), datetime.now().isoformat()),
    )
    conn.commit()
    draft_id = cursor.lastrowid
    conn.close()
    return draft_id


def set_telegram_msg_id(draft_id: int, msg_id: int) -> None:
    conn = get_connection()
    conn.execute("UPDATE drafts SET telegram_msg_id = ? WHERE id = ?", (msg_id, draft_id))
    conn.commit()
    conn.close()


def get_today_count() -> int:
    today = datetime.now().date().isoformat()
    conn = get_connection()
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM drafts WHERE substr(created_at, 1, 10) = ?", (today,)
    ).fetchone()
    conn.close()
    return row["c"]


def get_recent_keywords(days: int = 30) -> set:
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    conn = get_connection()
    rows = conn.execute(
        "SELECT DISTINCT keyword FROM drafts WHERE created_at >= ?", (cutoff,)
    ).fetchall()
    conn.close()
    return {row["keyword"] for row in rows}


def update_status(draft_id: int, status: str) -> None:
    conn = get_connection()
    conn.execute("UPDATE drafts SET status = ? WHERE id = ?", (status, draft_id))
    conn.commit()
    conn.close()


def increment_retry(draft_id: int) -> int:
    conn = get_connection()
    conn.execute("UPDATE drafts SET retry_count = retry_count + 1 WHERE id = ?", (draft_id,))
    conn.commit()
    row = conn.execute("SELECT retry_count AS c FROM drafts WHERE id = ?", (draft_id,)).fetchone()
    conn.close()
    return row["c"]


def get_approved_unpublished() -> list:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM drafts WHERE status = 'approved'").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_meta(key: str, default: str = None) -> str:
    conn = get_connection()
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def set_meta(key: str, value: str) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT INTO meta (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()
    conn.close()
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest test_db.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add db.py test_db.py
git commit -m "feat: add sqlite data layer for drafts"
```

---

## Task 3: keywords.py (트렌드 + 에버그린 키워드, 중복 제외)

**Files:**
- Create: `keywords.py`
- Create: `test_keywords.py`

**Interfaces:**
- Consumes: `db.get_recent_keywords(days: int) -> set` (Task 2)
- Produces: `keywords.get_trend_keywords(limit: int = 10) -> list[str]`, `keywords.get_evergreen_keywords() -> list[str]`, `keywords.get_keywords_to_use(needed_count: int) -> list[str]`

- [ ] **Step 1: 실패 테스트 작성**

```python
# test_keywords.py
import keywords


def test_get_evergreen_keywords_nonempty():
    kws = keywords.get_evergreen_keywords()
    assert len(kws) > 0
    assert all(isinstance(k, str) for k in kws)


def test_get_keywords_to_use_excludes_recent(monkeypatch):
    monkeypatch.setattr(keywords, "get_trend_keywords", lambda limit=10: ["트렌드1", "트렌드2"])
    monkeypatch.setattr(keywords.db, "get_recent_keywords", lambda days=30: {"트렌드1"})
    result = keywords.get_keywords_to_use(needed_count=2)
    assert "트렌드1" not in result
    assert len(result) == 2


def test_get_keywords_to_use_falls_back_when_trends_fail(monkeypatch):
    def boom(limit=10):
        raise RuntimeError("network down")
    monkeypatch.setattr(keywords, "get_trend_keywords", boom)
    monkeypatch.setattr(keywords.db, "get_recent_keywords", lambda days=30: set())
    result = keywords.get_keywords_to_use(needed_count=1)
    assert len(result) == 1
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest test_keywords.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'keywords'`

- [ ] **Step 3: keywords.py 구현**

```python
# keywords.py
from pytrends.request import TrendReq

import db

EVERGREEN_KEYWORDS = {
    "주식/금융/재테크/경제": ["배당주 추천", "ETF 추천", "예적금 금리 비교", "청약통장 활용법"],
    "건강": ["공복 혈당 낮추는 법", "간헐적 단식 효과", "허리 디스크 스트레칭"],
    "맛집": ["집들이 요리 추천", "혼밥 메뉴 추천", "다이어트 도시락 레시피"],
}


def get_trend_keywords(limit: int = 10) -> list:
    pytrends = TrendReq(hl="ko-KR", tz=540)
    df = pytrends.trending_searches(pn="south_korea")
    return df[0].tolist()[:limit]


def get_evergreen_keywords() -> list:
    result = []
    for topic_list in EVERGREEN_KEYWORDS.values():
        result.extend(topic_list)
    return result


def get_keywords_to_use(needed_count: int) -> list:
    recent = db.get_recent_keywords(days=30)
    candidates = []
    try:
        candidates.extend(get_trend_keywords())
    except Exception:
        pass
    candidates.extend(get_evergreen_keywords())

    result = []
    for kw in candidates:
        if kw in recent or kw in result:
            continue
        result.append(kw)
        if len(result) >= needed_count:
            break
    return result
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest test_keywords.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add keywords.py test_keywords.py
git commit -m "feat: add trend and evergreen keyword sourcing"
```

---

## Task 4: generator.py (Gemini로 제목/본문 생성)

**Files:**
- Create: `generator.py`
- Create: `test_generator.py`

**Interfaces:**
- Consumes: 환경변수 `GEMINI_API_KEY` (`.env` → `env_loader.load_env()`가 채움)
- Produces: `generator.generate_post(keyword: str) -> dict` (`{"title": str, "content": str, "tags": list[str]}`), `generator._parse_response(text: str) -> dict`, `generator._get_client()` (테스트에서 monkeypatch 대상)

- [ ] **Step 1: 실패 테스트 작성**

```python
# test_generator.py
import generator


def test_parse_response_plain_json():
    text = '{"title": "제목", "content": "<p>본문</p>", "tags": ["a", "b"]}'
    result = generator._parse_response(text)
    assert result == {"title": "제목", "content": "<p>본문</p>", "tags": ["a", "b"]}


def test_parse_response_strips_markdown_fence():
    text = '```json\n{"title": "제목", "content": "<p>c</p>", "tags": []}\n```'
    result = generator._parse_response(text)
    assert result["title"] == "제목"


class _FakeResponse:
    def __init__(self, text):
        self.text = text


class _FakeModels:
    def __init__(self, text):
        self._text = text

    def generate_content(self, model, contents):
        return _FakeResponse(self._text)


class _FakeClient:
    def __init__(self, text):
        self.models = _FakeModels(text)


def test_generate_post_uses_client(monkeypatch):
    fake_text = '{"title": "제목", "content": "<p>c</p>", "tags": ["x"]}'
    monkeypatch.setattr(generator, "_get_client", lambda: _FakeClient(fake_text))
    result = generator.generate_post("키워드")
    assert result["title"] == "제목"
    assert result["tags"] == ["x"]
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest test_generator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'generator'`

- [ ] **Step 3: generator.py 구현**

```python
# generator.py
import json
import os

from google import genai

_client = None

PROMPT_TEMPLATE = """너는 블로그 작가다. 아래 키워드로 블로그 글을 하나 써라.
키워드: {keyword}

규칙:
- 숫자나 통계는 확실하지 않으면 절대 지어내지 말고, 일반적인 설명으로 대체해라.
- 본문은 <h2>, <p>, <strong> 태그를 쓴 HTML로 작성해라.
- 아래 JSON 형식으로만 답해라. 다른 텍스트 붙이지 마라.

{{"title": "글 제목", "content": "HTML 본문", "tags": ["태그1", "태그2"]}}
"""


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _client


def _parse_response(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    data = json.loads(cleaned.strip())
    return {
        "title": data["title"],
        "content": data["content"],
        "tags": data.get("tags", []),
    }


def generate_post(keyword: str) -> dict:
    prompt = PROMPT_TEMPLATE.format(keyword=keyword)
    response = _get_client().models.generate_content(
        model="gemini-flash-latest",
        contents=prompt,
    )
    return _parse_response(response.text)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest test_generator.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add generator.py test_generator.py
git commit -m "feat: add Gemini-based post generator"
```

---

## Task 5: telegram_bot.py (알림, 승인/거부, /count 명령)

**Files:**
- Create: `telegram_bot.py`
- Create: `test_telegram_bot.py`

**Interfaces:**
- Consumes: 환경변수 `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- Produces: `telegram_bot.send_draft_notification(draft_id: int, title: str, keyword: str, warnings: list = None) -> int`, `telegram_bot.send_alert(text: str) -> None`, `telegram_bot.get_events(offset: int) -> tuple[list[dict], int]`, `telegram_bot.answer_callback(callback_query_id: str, text: str) -> None`. `get_events`가 반환하는 event dict 형태: `{"type": "approve"|"reject", "draft_id": int, "callback_query_id": str}` 또는 `{"type": "count", "value": int}`

- [ ] **Step 1: 실패 테스트 작성**

```python
# test_telegram_bot.py
import telegram_bot


class _FakeResp:
    def __init__(self, json_data):
        self._json = json_data

    def raise_for_status(self):
        pass

    def json(self):
        return self._json


def test_send_draft_notification(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    captured = {}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        return _FakeResp({"result": {"message_id": 99}})

    monkeypatch.setattr(telegram_bot.requests, "post", fake_post)
    msg_id = telegram_bot.send_draft_notification(5, "제목", "키워드")
    assert msg_id == 99
    assert "tok" in captured["url"]
    assert captured["json"]["chat_id"] == "123"
    assert "approve:5" in str(captured["json"]["reply_markup"])
    assert "⚠" not in captured["json"]["text"]


def test_send_draft_notification_includes_warnings(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    captured = {}

    def fake_post(url, json, timeout):
        captured["json"] = json
        return _FakeResp({"result": {"message_id": 100}})

    monkeypatch.setattr(telegram_bot.requests, "post", fake_post)
    telegram_bot.send_draft_notification(6, "제목", "키워드", warnings=["본문이 짧음"])
    assert "본문이 짧음" in captured["json"]["text"]


def test_get_events_parses_approve_and_count(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    updates = [
        {"update_id": 1, "callback_query": {"id": "cq1", "data": "approve:7"}},
        {"update_id": 2, "message": {"text": "/count 3"}},
    ]
    monkeypatch.setattr(
        telegram_bot.requests, "get",
        lambda url, params, timeout: _FakeResp({"result": updates}),
    )
    events, next_offset = telegram_bot.get_events(offset=0)
    assert next_offset == 3
    assert events[0] == {"type": "approve", "draft_id": 7, "callback_query_id": "cq1"}
    assert events[1] == {"type": "count", "value": 3}
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest test_telegram_bot.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'telegram_bot'`

- [ ] **Step 3: telegram_bot.py 구현**

```python
# telegram_bot.py
import os

import requests

API_BASE = "https://api.telegram.org/bot{token}/{method}"


def _url(method: str) -> str:
    return API_BASE.format(token=os.environ["TELEGRAM_BOT_TOKEN"], method=method)


def send_draft_notification(draft_id: int, title: str, keyword: str, warnings: list = None) -> int:
    text = f"[초안 #{draft_id}] {title}\n키워드: {keyword}"
    if warnings:
        text += "\n⚠ " + "; ".join(warnings)
    payload = {
        "chat_id": os.environ["TELEGRAM_CHAT_ID"],
        "text": text,
        "reply_markup": {
            "inline_keyboard": [[
                {"text": "승인", "callback_data": f"approve:{draft_id}"},
                {"text": "거부", "callback_data": f"reject:{draft_id}"},
            ]]
        },
    }
    resp = requests.post(_url("sendMessage"), json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()["result"]["message_id"]


def send_alert(text: str) -> None:
    payload = {"chat_id": os.environ["TELEGRAM_CHAT_ID"], "text": text}
    requests.post(_url("sendMessage"), json=payload, timeout=10)


def get_events(offset: int):
    resp = requests.get(_url("getUpdates"), params={"offset": offset, "timeout": 0}, timeout=15)
    resp.raise_for_status()
    updates = resp.json()["result"]
    events = []
    next_offset = offset
    for update in updates:
        next_offset = max(next_offset, update["update_id"] + 1)
        if "callback_query" in update:
            cq = update["callback_query"]
            action, _, draft_id = cq["data"].partition(":")
            if action in ("approve", "reject"):
                events.append({"type": action, "draft_id": int(draft_id), "callback_query_id": cq["id"]})
        elif "message" in update:
            text = update["message"].get("text", "")
            if text.startswith("/count"):
                parts = text.split()
                if len(parts) == 2 and parts[1].isdigit():
                    events.append({"type": "count", "value": int(parts[1])})
    return events, next_offset


def answer_callback(callback_query_id: str, text: str) -> None:
    requests.post(
        _url("answerCallbackQuery"),
        json={"callback_query_id": callback_query_id, "text": text},
        timeout=10,
    )
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest test_telegram_bot.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add telegram_bot.py test_telegram_bot.py
git commit -m "feat: add telegram approval and notification client"
```

---

## Task 6: post.py에 발행 성공/실패 반환값 추가

기존 `post_to_blogger`는 예외를 내부에서 삼키고 출력만 하고 끝나서, 호출자가 발행 성공 여부를 알 방법이 없다. `check_approvals.py`(Task 8)가 재시도 여부를 판단하려면 반환값이 필요하다 — 시그니처와 기존 동작(로그 출력)은 그대로 두고 `return` 두 줄만 추가한다.

**Files:**
- Modify: `post.py`
- Create: `test_post.py`

**Interfaces:**
- Produces: `post.post_to_blogger(blog_id, title, content, tags=[]) -> bool` (성공 True, 실패 False — 기존 호출부는 반환값을 안 쓰므로 영향 없음)

- [ ] **Step 1: 실패 테스트 작성**

```python
# test_post.py
import post


def test_post_to_blogger_returns_true_on_success(monkeypatch):
    class FakePosts:
        def insert(self, blogId, body):
            class Req:
                def execute(self):
                    return {"title": body["title"], "url": "http://example.com"}
            return Req()

    class FakeService:
        def posts(self):
            return FakePosts()

    monkeypatch.setattr(post, "get_blogger_service", lambda: FakeService())
    assert post.post_to_blogger("blogid", "title", "<p>c</p>", ["t"]) is True


def test_post_to_blogger_returns_false_on_error(monkeypatch):
    def boom():
        raise RuntimeError("auth failed")

    monkeypatch.setattr(post, "get_blogger_service", boom)
    assert post.post_to_blogger("blogid", "title", "<p>c</p>", []) is False
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest test_post.py -v`
Expected: FAIL — both tests fail because `post_to_blogger` returns `None`, not `True`/`False`

- [ ] **Step 3: post.py 수정**

`post.py`의 `post_to_blogger` 함수에서 성공 경로 마지막 줄 뒤에 `return True`, `except` 블록 마지막 줄 뒤에 `return False`만 추가한다:

```python
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

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest test_post.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add post.py test_post.py
git commit -m "fix: return success flag from post_to_blogger for caller retry logic"
```

---

## Task 7: validate.py + generate_drafts.py (스케줄 진입점 #1)

설계 문서의 "발행 전 자동 체크"(본문 길이, HTML 태그 짝) — 사람 승인 전에 기계가 최소 경고만 붙여준다. 자동 반려는 안 하고, 텔레그램 알림에 경고를 얹어 사람이 보고 판단하게 한다.

**Files:**
- Create: `validate.py`
- Create: `test_validate.py`
- Create: `generate_drafts.py`
- Create: `test_generate_drafts.py`

**Interfaces:**
- Produces (validate.py): `validate.check_draft(title: str, content: str) -> list[str]` (경고 문자열 목록, 없으면 빈 리스트)
- Consumes (generate_drafts.py): `config.get_daily_post_count()`, `db.init_db()`, `db.get_today_count()`, `db.insert_draft()`, `db.set_telegram_msg_id()`, `keywords.get_keywords_to_use(needed: int)`, `generator.generate_post(keyword: str)`, `validate.check_draft(title, content)`, `telegram_bot.send_draft_notification(draft_id, title, keyword, warnings)`
- Produces (generate_drafts.py): `generate_drafts.run() -> int` (생성한 draft 개수)

- [ ] **Step 1: validate.py 실패 테스트 작성**

```python
# test_validate.py
import validate


def test_check_draft_flags_short_content():
    warnings = validate.check_draft("제목", "<p>짧음</p>")
    assert any("짧음" in w for w in warnings)


def test_check_draft_flags_mismatched_tags():
    content = "<h2>제목</h2><p>" + "본문 " * 60 + "</p><p>안 닫힌 태그"
    warnings = validate.check_draft("제목", content)
    assert any("태그" in w for w in warnings)


def test_check_draft_no_warnings_for_clean_long_content():
    content = "<h2>제목</h2><p>" + "충분히 긴 본문 내용입니다. " * 20 + "</p>"
    warnings = validate.check_draft("제목", content)
    assert warnings == []
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest test_validate.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'validate'`

- [ ] **Step 3: validate.py 구현**

```python
# validate.py
import re
from collections import Counter

MIN_LENGTH = 200
CHECKED_TAGS = ("h2", "p", "strong")


def check_draft(title: str, content: str) -> list:
    warnings = []

    text_only = re.sub(r"<[^>]+>", "", content)
    if len(text_only) < MIN_LENGTH:
        warnings.append(f"본문이 {len(text_only)}자로 짧음(최소 권장 {MIN_LENGTH}자)")

    open_tags = re.findall(r"<(" + "|".join(CHECKED_TAGS) + r")>", content)
    close_tags = re.findall(r"</(" + "|".join(CHECKED_TAGS) + r")>", content)
    if Counter(open_tags) != Counter(close_tags):
        warnings.append("HTML 태그 짝이 안 맞음(h2/p/strong 확인 필요)")

    return warnings
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest test_validate.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add validate.py test_validate.py
git commit -m "feat: add pre-publish draft validation warnings"
```

- [ ] **Step 6: generate_drafts.py 실패 테스트 작성**

```python
# test_generate_drafts.py
import generate_drafts


def test_run_stops_when_target_met(monkeypatch):
    monkeypatch.setattr(generate_drafts.db, "init_db", lambda: None)
    monkeypatch.setattr(generate_drafts.config, "get_daily_post_count", lambda: 3)
    monkeypatch.setattr(generate_drafts.db, "get_today_count", lambda: 3)
    called = {"keywords": False}

    def fail_if_called(needed):
        called["keywords"] = True
        return []

    monkeypatch.setattr(generate_drafts.keywords, "get_keywords_to_use", fail_if_called)
    created = generate_drafts.run()
    assert created == 0
    assert called["keywords"] is False


def test_run_creates_needed_count_and_skips_failed_keyword(monkeypatch):
    monkeypatch.setattr(generate_drafts.db, "init_db", lambda: None)
    monkeypatch.setattr(generate_drafts.config, "get_daily_post_count", lambda: 2)
    monkeypatch.setattr(generate_drafts.db, "get_today_count", lambda: 0)
    monkeypatch.setattr(generate_drafts.keywords, "get_keywords_to_use", lambda needed: ["k1", "k2"])

    def fake_generate(keyword):
        if keyword == "k1":
            raise RuntimeError("gemini down")
        return {"title": "t", "content": "c", "tags": []}

    monkeypatch.setattr(generate_drafts.generator, "generate_post", fake_generate)

    inserted = []
    monkeypatch.setattr(
        generate_drafts.db, "insert_draft",
        lambda kw, t, c, tags: inserted.append(kw) or len(inserted),
    )
    monkeypatch.setattr(
        generate_drafts.telegram_bot, "send_draft_notification",
        lambda draft_id, title, keyword, warnings=None: 111,
    )
    monkeypatch.setattr(generate_drafts.db, "set_telegram_msg_id", lambda draft_id, msg_id: None)
    monkeypatch.setattr(generate_drafts.validate, "check_draft", lambda title, content: [])

    created = generate_drafts.run()
    assert created == 1
    assert inserted == ["k2"]


def test_run_passes_validation_warnings_to_telegram(monkeypatch):
    monkeypatch.setattr(generate_drafts.db, "init_db", lambda: None)
    monkeypatch.setattr(generate_drafts.config, "get_daily_post_count", lambda: 1)
    monkeypatch.setattr(generate_drafts.db, "get_today_count", lambda: 0)
    monkeypatch.setattr(generate_drafts.keywords, "get_keywords_to_use", lambda needed: ["k1"])
    monkeypatch.setattr(
        generate_drafts.generator, "generate_post",
        lambda keyword: {"title": "t", "content": "c", "tags": []},
    )
    monkeypatch.setattr(generate_drafts.db, "insert_draft", lambda kw, t, c, tags: 1)
    monkeypatch.setattr(generate_drafts.db, "set_telegram_msg_id", lambda draft_id, msg_id: None)
    monkeypatch.setattr(generate_drafts.validate, "check_draft", lambda title, content: ["본문이 짧음"])

    captured = {}
    monkeypatch.setattr(
        generate_drafts.telegram_bot, "send_draft_notification",
        lambda draft_id, title, keyword, warnings=None: captured.setdefault("warnings", warnings) or 1,
    )

    generate_drafts.run()
    assert captured["warnings"] == ["본문이 짧음"]
```

- [ ] **Step 7: 테스트 실패 확인**

Run: `python -m pytest test_generate_drafts.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'generate_drafts'`

- [ ] **Step 8: generate_drafts.py 구현**

```python
# generate_drafts.py
import logging

import config
import db
import generator
import keywords
import telegram_bot
import validate

logging.basicConfig(filename="app.log", level=logging.INFO, format="%(asctime)s %(message)s")


def run() -> int:
    db.init_db()
    target = config.get_daily_post_count()
    already = db.get_today_count()
    needed = max(0, target - already)
    if needed == 0:
        logging.info("generate_drafts: target %d already met (%d today), skip", target, already)
        return 0

    created = 0
    for keyword in keywords.get_keywords_to_use(needed):
        try:
            post_data = generator.generate_post(keyword)
        except Exception as e:
            logging.error("generate_drafts: gemini failed for %r: %s", keyword, e)
            continue

        draft_id = db.insert_draft(keyword, post_data["title"], post_data["content"], post_data["tags"])
        warnings = validate.check_draft(post_data["title"], post_data["content"])
        try:
            msg_id = telegram_bot.send_draft_notification(draft_id, post_data["title"], keyword, warnings)
            db.set_telegram_msg_id(draft_id, msg_id)
        except Exception as e:
            logging.error("generate_drafts: telegram notify failed for draft %d: %s", draft_id, e)
        created += 1

    logging.info("generate_drafts: created %d draft(s)", created)
    return created


if __name__ == "__main__":
    from env_loader import load_env
    load_env()
    run()
```

- [ ] **Step 9: 테스트 통과 확인**

Run: `python -m pytest test_generate_drafts.py -v`
Expected: PASS (3 passed)

- [ ] **Step 10: Commit**

```bash
git add generate_drafts.py test_generate_drafts.py
git commit -m "feat: add generate_drafts scheduler entrypoint"
```

---

## Task 8: check_approvals.py (스케줄 진입점 #2)

**Files:**
- Create: `check_approvals.py`
- Create: `test_check_approvals.py`

**Interfaces:**
- Consumes: `db.get_meta/set_meta`, `db.update_status`, `db.get_approved_unpublished`, `db.increment_retry`, `telegram_bot.get_events/answer_callback/send_alert`, `config.set_daily_post_count`, `post.post_to_blogger(blog_id, title, content, tags) -> bool` (Task 6)
- Produces: `check_approvals.run() -> None`, `check_approvals.MAX_RETRY`

- [ ] **Step 1: 실패 테스트 작성**

```python
# test_check_approvals.py
import check_approvals


def test_run_processes_events_and_publishes(monkeypatch):
    monkeypatch.setattr(check_approvals.db, "init_db", lambda: None)
    monkeypatch.setattr(check_approvals.db, "get_meta", lambda key, default=None: "0")
    events = [
        {"type": "approve", "draft_id": 1, "callback_query_id": "cq1"},
        {"type": "count", "value": 4},
    ]
    monkeypatch.setattr(check_approvals.telegram_bot, "get_events", lambda offset: (events, 2))

    status_updates = []
    monkeypatch.setattr(
        check_approvals.db, "update_status",
        lambda draft_id, status: status_updates.append((draft_id, status)),
    )
    monkeypatch.setattr(check_approvals.telegram_bot, "answer_callback", lambda cq_id, text: None)
    count_calls = []
    monkeypatch.setattr(check_approvals.config, "set_daily_post_count", lambda v: count_calls.append(v))
    meta_calls = []
    monkeypatch.setattr(check_approvals.db, "set_meta", lambda k, v: meta_calls.append((k, v)))

    monkeypatch.setattr(
        check_approvals.db, "get_approved_unpublished",
        lambda: [{"id": 1, "title": "t", "content": "c", "tags": "[]"}],
    )
    monkeypatch.setenv("BLOGGER_BLOG_ID", "blog123")
    monkeypatch.setattr(
        check_approvals.post, "post_to_blogger",
        lambda blog_id, title, content, tags: True,
    )

    check_approvals.run()

    assert "approved" in [s for _, s in status_updates]
    assert "published" in [s for _, s in status_updates]
    assert count_calls == [4]
    assert meta_calls == [("telegram_offset", "2")]


def test_run_retries_and_alerts_on_repeated_publish_failure(monkeypatch):
    monkeypatch.setattr(check_approvals.db, "init_db", lambda: None)
    monkeypatch.setattr(check_approvals.db, "get_meta", lambda key, default=None: "0")
    monkeypatch.setattr(check_approvals.telegram_bot, "get_events", lambda offset: ([], 0))
    monkeypatch.setattr(check_approvals.db, "set_meta", lambda k, v: None)
    monkeypatch.setattr(
        check_approvals.db, "get_approved_unpublished",
        lambda: [{"id": 9, "title": "t", "content": "c", "tags": "[]"}],
    )
    monkeypatch.setenv("BLOGGER_BLOG_ID", "blog123")
    monkeypatch.setattr(
        check_approvals.post, "post_to_blogger",
        lambda blog_id, title, content, tags: False,
    )
    monkeypatch.setattr(check_approvals.db, "increment_retry", lambda draft_id: 6)
    alerts = []
    monkeypatch.setattr(check_approvals.telegram_bot, "send_alert", lambda text: alerts.append(text))

    check_approvals.run()

    assert len(alerts) == 1
    assert "9" in alerts[0]
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest test_check_approvals.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'check_approvals'`

- [ ] **Step 3: check_approvals.py 구현**

```python
# check_approvals.py
import json
import logging
import os

import config
import db
import post
import telegram_bot

MAX_RETRY = 5

logging.basicConfig(filename="app.log", level=logging.INFO, format="%(asctime)s %(message)s")


def run() -> None:
    db.init_db()
    offset = int(db.get_meta("telegram_offset", "0"))
    events, next_offset = telegram_bot.get_events(offset)

    for event in events:
        if event["type"] == "approve":
            db.update_status(event["draft_id"], "approved")
            telegram_bot.answer_callback(event["callback_query_id"], "승인됨")
        elif event["type"] == "reject":
            db.update_status(event["draft_id"], "rejected")
            telegram_bot.answer_callback(event["callback_query_id"], "거부됨")
        elif event["type"] == "count":
            config.set_daily_post_count(event["value"])
    db.set_meta("telegram_offset", str(next_offset))

    for draft in db.get_approved_unpublished():
        ok = post.post_to_blogger(
            blog_id=os.environ["BLOGGER_BLOG_ID"],
            title=draft["title"],
            content=draft["content"],
            tags=json.loads(draft["tags"]),
        )
        if ok:
            db.update_status(draft["id"], "published")
        else:
            retry = db.increment_retry(draft["id"])
            logging.error("check_approvals: publish failed for draft %d (retry %d)", draft["id"], retry)
            if retry > MAX_RETRY:
                telegram_bot.send_alert(f"발행 반복 실패: 초안 #{draft['id']} ({draft['title']})")


if __name__ == "__main__":
    from env_loader import load_env
    load_env()
    run()
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest test_check_approvals.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add check_approvals.py test_check_approvals.py
git commit -m "feat: add check_approvals scheduler entrypoint"
```

---

## Task 9: 작업 스케줄러 등록 + 셋업 가이드

**Files:**
- Create: `register_tasks.py`
- Create: `test_register_tasks.py`
- Create: `SETUP.md`

**Interfaces:**
- Consumes: `generate_drafts.py`, `check_approvals.py` 파일 경로 (Task 7, 8)
- Produces: `register_tasks.build_schtasks_commands(python_exe: str) -> list[list[str]]`, `register_tasks.register(dry_run: bool) -> None`

- [ ] **Step 1: 실패 테스트 작성**

```python
# test_register_tasks.py
import register_tasks


def test_build_schtasks_commands():
    cmds = register_tasks.build_schtasks_commands(python_exe="C:\\py\\python.exe")
    assert len(cmds) == 2
    gen_cmd, chk_cmd = cmds
    assert "generate_drafts.py" in " ".join(gen_cmd)
    assert "hourly" in gen_cmd
    assert "2" in gen_cmd
    assert "check_approvals.py" in " ".join(chk_cmd)
    assert "minute" in chk_cmd
    assert "10" in chk_cmd
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest test_register_tasks.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'register_tasks'`

- [ ] **Step 3: register_tasks.py 구현**

```python
# register_tasks.py
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).parent


def build_schtasks_commands(python_exe: str = sys.executable) -> list:
    generate_script = str(PROJECT_DIR / "generate_drafts.py")
    check_script = str(PROJECT_DIR / "check_approvals.py")
    return [
        [
            "schtasks", "/create", "/tn", "BlogAuto_GenerateDrafts",
            "/tr", f'"{python_exe}" "{generate_script}"',
            "/sc", "hourly", "/mo", "2", "/f",
        ],
        [
            "schtasks", "/create", "/tn", "BlogAuto_CheckApprovals",
            "/tr", f'"{python_exe}" "{check_script}"',
            "/sc", "minute", "/mo", "10", "/f",
        ],
    ]


def register(dry_run: bool = False) -> None:
    for cmd in build_schtasks_commands():
        if dry_run:
            print(" ".join(cmd))
        else:
            subprocess.run(cmd, check=True)


if __name__ == "__main__":
    register(dry_run="--dry-run" in sys.argv)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest test_register_tasks.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: SETUP.md 작성**

```markdown
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
```

- [ ] **Step 6: Commit**

```bash
git add register_tasks.py test_register_tasks.py SETUP.md
git commit -m "feat: add scheduler registration and setup guide"
```

---

## Task 10: 전체 테스트 스위트 확인

**Files:** 없음 (검증만)

- [ ] **Step 1: 전체 테스트 실행**

Run: `python -m pytest -v`
Expected: 모든 테스트 PASS (총 20개 안팎)

- [ ] **Step 2: 수동 통합 확인 (SETUP.md 4번 항목 그대로 실행)**

`.env` 값을 채운 뒤 `generate_drafts.py` → 텔레그램 알림 → 승인 → `check_approvals.py` → Blogger 실제 발행까지 한 번 손으로 돌려서 확인. (reborn-claudekit 스킬의 "손으로 열 번 먼저" 원칙 — 최소 1회는 실제로 확인하고 스케줄러에 맡긴다.)
