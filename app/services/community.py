from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import TownArchivedFragment, TownCard, TownContribution
from app.config import Settings
from app.errors import ServiceError
from app.services.ai import AIService
from app.services.content_safety import censor_profanity

NON_PERSON_TERMS = {
    "분위기", "장소", "장면", "기억", "원본", "활동", "사람", "사람들",
    "주민", "주민들", "이웃", "이웃들", "방문객", "행인", "누군가",
    "가게", "작은 가게", "문방구", "골목", "골목 이름", "가게명",
    "정확한 위치 정보", "위치 정보", "해당 없음", "없음",
}

SAFE_ACTIVITY_CATEGORIES = (
    (("바다", "해변", "파도"), "바다 풍경"),
    (("걷", "산책"), "산책"),
    (("사진", "촬영"), "사진 촬영"),
    (("공연", "영화", "버스킹", "노래"), "문화 활동"),
    (("먹", "식사", "음식", "카페", "커피"), "식사와 휴식"),
    (("친구", "가족", "동료", "사람"), "사람들과 함께한 시간"),
    (("비", "눈", "날씨", "바람"), "날씨와 주변 분위기"),
)


def _fallback_contribution(place_tag: str, combined: str, *, has_post: bool) -> tuple[str, str]:
    """원문이나 고유명사를 복사하지 않는 제한된 범주형 대체 문장."""
    normalized = re.sub(r"\s+", "", combined).casefold()
    categories = [
        label for keywords, label in SAFE_ACTIVITY_CATEGORIES
        if any(keyword.casefold() in normalized for keyword in keywords)
    ]
    summary = "과 ".join(dict.fromkeys(categories[:3])) or "장소의 분위기와 함께한 시간"
    safe_pre = f"{place_tag}에서 {summary}을 떠올린 기억"
    safe_post = "원본을 확인한 뒤 장소의 분위기와 함께한 장면을 더 떠올린 기억" if has_post else ""
    return safe_pre, safe_post


def _validated_candidate(result: dict, blocked_terms: list[str]) -> tuple[str, str] | None:
    safe_pre = censor_profanity(str(result.get("safe_pre_text") or "").strip())
    safe_post = censor_profanity(str(result.get("safe_post_text") or "").strip())
    public_text = f"{safe_pre} {safe_post}".casefold()
    leaked = [term for term in blocked_terms if len(term.strip()) >= 2 and term.casefold() in public_text]
    return None if leaked or not (safe_pre or safe_post) else (safe_pre, safe_post)


def contributor_key(settings: Settings, *, owner_id: str, place_tag: str) -> str:
    """원본 사용자 ID를 공개하지 않고 장소별 동일 참여자를 판별하는 비가역 키."""
    message = f"{place_tag}\0{owner_id}".encode()
    return hmac.new(settings.share_preview_secret.encode(), message, hashlib.sha256).hexdigest()


def create_share_preview_token(
    settings: Settings,
    *,
    card_id: str,
    owner_id: str,
    place_tag: str,
    safe_pre_text: str,
    safe_post_text: str,
) -> str:
    payload = {
        "card_id": card_id,
        "owner_id": owner_id,
        "place_tag": place_tag,
        "safe_pre_text": safe_pre_text,
        "safe_post_text": safe_post_text,
        "expires_at": int(time.time()) + 600,
    }
    encoded = base64.urlsafe_b64encode(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(settings.share_preview_secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def verify_share_preview_token(
    settings: Settings,
    token: str,
    *,
    card_id: str,
    owner_id: str,
    place_tag: str,
) -> tuple[str, str]:
    try:
        encoded, signature = token.split(".", 1)
        expected = hmac.new(settings.share_preview_secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        padding = "=" * (-len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(encoded + padding))
        if payload.get("card_id") != card_id or payload.get("owner_id") != owner_id or payload.get("place_tag") != place_tag:
            raise ValueError
        if int(payload.get("expires_at", 0)) < int(time.time()):
            raise ServiceError("공유 미리보기의 유효시간이 지났습니다.", detail={"action": "내용을 다시 미리보기 해주세요."})
        return str(payload.get("safe_pre_text") or ""), str(payload.get("safe_post_text") or "")
    except ServiceError:
        raise
    except Exception as exc:
        raise ServiceError("유효하지 않은 공유 미리보기입니다.", detail={"action": "내용을 다시 미리보기 해주세요."}) from exc


def sanitize_contribution(
    ai: AIService,
    settings: Settings,
    *,
    place_tag: str,
    pre_text: str,
    post_text: str,
) -> tuple[str, str]:
    combined = "\n".join(part for part in (pre_text, post_text) if part)
    # 이 시점의 입력은 이미 구조화가 끝난 회상 답변이다. 익명 공유 때마다
    # Information Extract를 다시 호출하면 지연과 장애 지점만 늘어나므로,
    # Solar 비식별화 결과가 알려주는 차단 표현을 기준으로 검증한다.
    # Upstage가 일시적으로 응답하지 않더라도 원문을 공개하지 않고 아래의
    # 제한된 범주형 문장으로 대체해 공유 흐름을 안전하게 이어간다.
    try:
        result = ai.sanitize_town_contribution(
            place_tag=place_tag,
            pre_text=pre_text,
            post_text=post_text,
        )
    except ServiceError:
        return _fallback_contribution(place_tag, combined, has_post=bool(post_text.strip()))
    blocked_terms = list(dict.fromkeys([
        *result.get("blocked_terms", []),
    ]))
    blocked_terms = [term for term in blocked_terms if term not in NON_PERSON_TERMS]
    candidate = _validated_candidate(result, blocked_terms)
    if candidate:
        return candidate

    # 1차 결과를 다시 입력해 AI가 이미 일반화된 문장만 더 넓은 범주로 정리하도록 한다.
    try:
        retry = ai.sanitize_town_contribution(
            place_tag=place_tag,
            pre_text=str(result.get("safe_pre_text") or ""),
            post_text=str(result.get("safe_post_text") or ""),
        )
    except ServiceError:
        return _fallback_contribution(place_tag, combined, has_post=bool(post_text.strip()))
    retry_blocked_terms = list(dict.fromkeys([
        *blocked_terms,
        *retry.get("blocked_terms", []),
    ]))
    retry_blocked_terms = [term for term in retry_blocked_terms if term not in NON_PERSON_TERMS]
    candidate = _validated_candidate(retry, retry_blocked_terms)
    if candidate:
        return candidate

    # 두 번 모두 실패해도 사용자가 원문을 고쳐 쓰게 하지 않고 안전한 범주형 문장으로 대체한다.
    fallback = _fallback_contribution(place_tag, combined, has_post=bool(post_text.strip()))
    candidate = _validated_candidate(
        {"safe_pre_text": fallback[0], "safe_post_text": fallback[1]},
        retry_blocked_terms,
    )
    if not candidate:
        raise ServiceError(
            "안전한 동네 공유 문장을 만들지 못했습니다.",
            detail={"action": "원본은 공유되지 않았습니다. 잠시 후 다시 시도해주세요."},
        )
    return candidate


def contribution_was_published(db: Session, contribution_id: str) -> bool:
    cards = db.scalars(select(TownCard)).all()
    return any(
        contribution_id in {
            str(item).removeprefix("archived:")
            for item in (card.source_contribution_ids or [])
            if isinstance(item, str) and not item.startswith("privacy:")
        }
        for card in cards
    )


def detach_or_delete_contribution(
    db: Session,
    contribution: TownContribution,
    *,
    ai: AIService,
    settings: Settings,
) -> bool:
    """공개 반영된 조각은 익명 보존하고, 미반영 조각은 완전히 삭제한다."""
    published = contribution_was_published(db, contribution.id)
    if published and db.get(TownArchivedFragment, contribution.id) is None:
        safe_pre, safe_post = sanitize_contribution(
            ai,
            settings,
            place_tag=contribution.place_tag,
            pre_text=contribution.pre_reveal_text,
            post_text=contribution.post_reveal_text,
        )
        db.add(
            TownArchivedFragment(
                id=contribution.id,
                place_tag=contribution.place_tag,
                contributor_key=contribution.contributor_key or contributor_key(
                    settings,
                    owner_id=contribution.owner_id,
                    place_tag=contribution.place_tag,
                ),
                pre_reveal_text=safe_pre,
                post_reveal_text=safe_post,
                created_at=contribution.created_at,
            )
        )
    db.delete(contribution)
    return published
