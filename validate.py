import re
from collections import Counter

MIN_LENGTH = 2000
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
