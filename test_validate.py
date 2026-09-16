import validate


def test_check_draft_flags_short_content():
    warnings = validate.check_draft("제목", "<p>짧음</p>")
    assert any("짧음" in w for w in warnings)


def test_check_draft_flags_mismatched_tags():
    content = "<h2>제목</h2><p>" + "본문 " * 60 + "</p><p>안 닫힌 태그"
    warnings = validate.check_draft("제목", content)
    assert any("태그" in w for w in warnings)


def test_check_draft_no_warnings_for_clean_long_content():
    content = "<p>도입 문단이다.</p><h2>소제목</h2><p>" + "충분히 길고 구체적인 본문 내용을 담고 있습니다. " * 150 + "</p>"
    warnings = validate.check_draft("제목", content)
    assert warnings == []


def test_warns_when_content_starts_with_heading():
    warnings = validate.check_draft("제목", "<h2>소제목</h2><p>" + "본문 " * 700 + "</p>")
    assert any("도입 문단" in w for w in warnings)


def test_no_heading_warning_when_intro_comes_first():
    warnings = validate.check_draft("제목", "<p>도입 문단이다.</p><h2>소제목</h2><p>" + "본문 " * 700 + "</p>")
    assert not any("도입 문단" in w for w in warnings)
