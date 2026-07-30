from __future__ import annotations

import re


# 공개 동네 카드에 적합하지 않은 대표적인 한국어·영어 비속어와 축약 표현.
_PROFANITY_PATTERNS = [
    r"씨+발+", r"시+발+", r"ㅅ\s*ㅂ", r"병+신+", r"ㅂ\s*ㅅ",
    r"개\s*새끼", r"새끼", r"좆+", r"존+나+", r"지랄", r"미친\s*(?:놈|년)",
    r"꺼져", r"닥쳐", r"fuck(?:ing)?", r"shit", r"bitch",
]
_PROFANITY_RE = re.compile("|".join(f"(?:{pattern})" for pattern in _PROFANITY_PATTERNS), re.IGNORECASE)


def censor_profanity(text: str) -> str:
    """비속어를 공개 가능한 중립 표현으로 치환하고 연속 치환을 정리한다."""
    censored = _PROFANITY_RE.sub("부적절한 표현", text or "")
    censored = re.sub(r"(?:부적절한 표현[\s,]*){2,}", "부적절한 표현 ", censored)
    return censored.strip()


def contains_profanity(text: str) -> bool:
    return bool(_PROFANITY_RE.search(text or ""))
