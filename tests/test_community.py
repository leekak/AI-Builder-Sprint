from __future__ import annotations

from app.config import Settings
from app.errors import ServiceError
from app.services.community import sanitize_contribution


class RetryThenSafeAI:
    def __init__(self):
        self.calls = 0

    def extract_context(self, *, text: str):
        return {"people": ["진우"], "places": ["광안리"]}

    def sanitize_town_contribution(self, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return {
                "safe_pre_text": "진우와 광안리에서 산책한 기억",
                "safe_post_text": "",
                "blocked_terms": ["진우"],
            }
        return {
            "safe_pre_text": "광안리에서 사람들과 산책한 기억",
            "safe_post_text": "",
            "blocked_terms": [],
        }


class AlwaysInvalidAI:
    def extract_context(self, *, text: str):
        return {"people": ["진우"], "places": ["광안리"]}

    def sanitize_town_contribution(self, **kwargs):
        return {
            "safe_pre_text": "진우",
            "safe_post_text": "",
            "blocked_terms": ["진우"],
        }


def test_privacy_filter_retries_with_more_general_text():
    ai = RetryThenSafeAI()
    safe_pre, safe_post = sanitize_contribution(
        ai,
        Settings(_env_file=None),
        place_tag="광안리",
        pre_text="진우와 광안리에서 산책했다",
        post_text="",
    )
    assert ai.calls == 2
    assert safe_pre == "광안리에서 사람들과 산책한 기억"
    assert safe_post == ""


def test_privacy_filter_uses_safe_category_fallback_after_two_failures():
    safe_pre, safe_post = sanitize_contribution(
        AlwaysInvalidAI(),
        Settings(_env_file=None),
        place_tag="광안리",
        pre_text="진우와 바다를 산책하며 씨발이라고 말했다",
        post_text="사진을 보고 카페에서 커피를 마신 일이 떠올랐다",
    )
    assert "진우" not in safe_pre
    assert "씨발" not in safe_pre
    assert "바다 풍경" in safe_pre
    assert "산책" in safe_pre
    assert safe_post


class CommunityDetailAI:
    def extract_context(self, *, text: str):
        return {"people": ["주민들"], "places": ["감천문화마을", "골목"]}

    def sanitize_town_contribution(self, **kwargs):
        return {
            "safe_pre_text": "골목의 생활 소리와 주민들의 평범한 하루가 기억난다",
            "safe_post_text": "",
            "blocked_terms": [],
        }


def test_privacy_filter_preserves_non_identifying_community_details():
    safe_pre, _ = sanitize_contribution(
        CommunityDetailAI(),
        Settings(_env_file=None),
        place_tag="감천문화마을",
        pre_text="늦은 오후 골목에서 주민들의 생활 소리를 들었다",
        post_text="",
    )
    assert "골목" in safe_pre
    assert "생활 소리" in safe_pre
    assert "주민들" in safe_pre


class UnavailableAI:
    def sanitize_town_contribution(self, **kwargs):
        raise ServiceError("temporary Upstage failure")


def test_privacy_filter_uses_non_identifying_fallback_when_upstage_is_unavailable():
    safe_pre, safe_post = sanitize_contribution(
        UnavailableAI(),
        Settings(_env_file=None),
        place_tag="광안리",
        pre_text="진우와 해변을 걷고 카페에서 커피를 마셨다",
        post_text="사진을 보고 비가 오던 날씨가 떠올랐다",
    )
    assert "진우" not in safe_pre
    assert "바다 풍경" in safe_pre
    assert "산책" in safe_pre
    assert safe_post
