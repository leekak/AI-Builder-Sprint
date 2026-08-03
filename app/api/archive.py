from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.dependencies import get_ai, get_db, get_settings, require_admin, require_admin_account
from app.errors import ServiceError
from app.models import TownArchivedFragment, TownCard, TownContribution, utcnow
from app.schemas import (
    PlaceTagsResponse,
    TownCardResponse,
    TownContributionAdminResponse,
    TownPlaceStatusResponse,
)
from app.serializers import town_card_to_dict
from app.services.ai import AIService
from app.services.community import contributor_key, sanitize_contribution
from app.services.content_safety import censor_profanity, contains_profanity

router = APIRouter(tags=["town archive"])
PRIVACY_PIPELINE_MARKER = "privacy:v3"
NON_PERSON_TERMS = {
    "분위기", "장소", "장면", "기억", "원본", "활동", "사람", "사람들",
    "주민", "주민들", "이웃", "이웃들", "방문객", "행인", "누군가",
    "가게", "작은 가게", "문방구", "골목", "골목 이름", "가게명",
    "정확한 위치 정보", "위치 정보", "해당 없음", "없음",
}


def _card_contribution_ids(card: TownCard | None) -> set[str]:
    if not card:
        return set()
    return {
        item.removeprefix("archived:") for item in (card.source_contribution_ids or [])
        if isinstance(item, str) and not item.startswith("privacy:")
    }


def _active_contributor_key(item: TownContribution, settings: Settings) -> str:
    if not item.contributor_key:
        item.contributor_key = contributor_key(settings, owner_id=item.owner_id, place_tag=item.place_tag)
    return item.contributor_key


def _archived_contributor_key(item: TownArchivedFragment) -> str:
    # 구버전 익명 조각은 원래 소유자를 복원할 수 없으므로 조각별 레거시 키로 안전하게 유지한다.
    return item.contributor_key or f"legacy:{item.id}"


def _current_contributor_keys(
    contributions: list[TownContribution],
    archived_fragments: list[TownArchivedFragment],
    settings: Settings,
) -> set[str]:
    return {
        *(_active_contributor_key(item, settings) for item in contributions),
        *(_archived_contributor_key(item) for item in archived_fragments),
    }


def _group_fragments_by_contributor(
    contributions: list[TownContribution],
    archived_fragments: list[TownArchivedFragment],
    settings: Settings,
) -> list[dict[str, str]]:
    grouped: dict[str, dict[str, list[str]]] = defaultdict(lambda: {"pre": [], "post": []})
    for item in contributions:
        key = _active_contributor_key(item, settings)
        grouped[key]["pre"].append(item.pre_reveal_text)
        grouped[key]["post"].append(item.post_reveal_text)
    for item in archived_fragments:
        key = _archived_contributor_key(item)
        grouped[key]["pre"].append(item.pre_reveal_text)
        grouped[key]["post"].append(item.post_reveal_text)
    return [
        {
            "pre_reveal_text": " / ".join(dict.fromkeys(filter(None, values["pre"])))[:700],
            "post_reveal_text": " / ".join(dict.fromkeys(filter(None, values["post"])))[:700],
        }
        for values in grouped.values()
    ]


def _raw_recall_fragments(item: TownContribution) -> tuple[str, str]:
    """공유자가 작성한 회상 답변만 다시 읽는다. 원본 사진·코멘트는 공개 재료로 쓰지 않는다."""
    recall = item.card.recall
    pre_parts: list[str] = []
    if recall.initial_answer and recall.initial_answer.strip():
        pre_parts.append(recall.initial_answer.strip())
    for hint in recall.hint_answers or []:
        answer = str(hint.get("answer") or "").strip()
        if answer:
            pre_parts.append(answer)
    return "\n".join(pre_parts), (recall.newly_recalled_text or "").strip()


def _reprocess_place_contributions(
    contributions: list[TownContribution],
    settings: Settings,
    ai: AIService,
) -> int:
    """현재 개인 카드와 연결된 조각을 개선된 개인정보 보호 규칙으로 다시 만든다."""
    updated = 0
    for item in contributions:
        pre_text, post_text = _raw_recall_fragments(item)
        if not pre_text and not post_text:
            continue
        safe_pre, safe_post = sanitize_contribution(
            ai,
            settings,
            place_tag=item.place_tag,
            pre_text=pre_text,
            post_text=post_text,
        )
        combined = f"{safe_pre} {safe_post}"
        generic_markers = ("사진 촬영을 떠올린 기억", "장소의 분위기와 함께한", "함께한 장면을 더 떠올린")
        if any(marker in combined for marker in generic_markers):
            retry_pre, retry_post = sanitize_contribution(
                ai,
                settings,
                place_tag=item.place_tag,
                pre_text=pre_text,
                post_text=post_text,
            )
            if len(f"{retry_pre} {retry_post}".strip()) > len(combined.strip()):
                safe_pre, safe_post = retry_pre, retry_post
        item.pre_reveal_text = safe_pre
        item.post_reveal_text = safe_post
        updated += 1
    return updated


def _latest_place_card(db: Session, place_tag: str) -> TownCard | None:
    return db.scalar(
        select(TownCard)
        .where(TownCard.place_tag == place_tag, TownCard.deleted_at.is_(None))
        .order_by(TownCard.updated_at.desc(), TownCard.created_at.desc())
        .limit(1)
    )


def _published_contributor_keys(
    card: TownCard | None,
    contributions: list[TownContribution],
    archived_fragments: list[TownArchivedFragment],
    settings: Settings,
) -> set[str]:
    if not card:
        return set()
    if card.published_contributor_keys:
        return {str(item) for item in card.published_contributor_keys}

    # 구버전 카드에는 참여자 키가 없으므로 당시 사용한 조각 ID로 한 번만 복원한다.
    source_ids = _card_contribution_ids(card)
    keys = {
        _active_contributor_key(item, settings)
        for item in contributions
        if item.id in source_ids
    }
    keys.update(
        _archived_contributor_key(item)
        for item in archived_fragments
        if item.id in source_ids
    )
    return keys


def _place_status_dict(
    place_tag: str,
    contributions: list[TownContribution],
    archived_fragments: list[TownArchivedFragment],
    latest: TownCard | None,
    settings: Settings,
) -> dict:
    current_keys = _current_contributor_keys(contributions, archived_fragments, settings)
    published_keys = _published_contributor_keys(latest, contributions, archived_fragments, settings)
    new_keys = current_keys - published_keys
    privacy_review_required = bool(latest and PRIVACY_PIPELINE_MARKER not in (latest.source_contribution_ids or []))
    required_count = len(current_keys) if not latest else len(new_keys)
    return {
        "place_tag": place_tag,
        "distinct_contributors": len(current_keys),
        "total_fragments": len(contributions) + len(archived_fragments),
        "minimum_required": settings.town_min_contributors,
        "new_contributors": len(new_keys),
        "can_generate": required_count >= settings.town_min_contributors or privacy_review_required,
        "has_new_contributions": bool(new_keys),
        "privacy_review_required": privacy_review_required,
        "latest_card_id": latest.id if latest else None,
    }


@router.get("/place-tags", response_model=PlaceTagsResponse)
def get_place_tags(settings: Settings = Depends(get_settings)):
    return {"place_tags": settings.place_tags}


@router.get("/archive/places", response_model=list[TownCardResponse])
def list_town_cards(db: Session = Depends(get_db)):
    cards = db.scalars(
        select(TownCard)
        .where(TownCard.deleted_at.is_(None))
        .order_by(TownCard.updated_at.desc(), TownCard.created_at.desc())
    ).all()
    # 개인정보 보호 파이프라인 적용 이전의 레거시 카드는 공개 목록에서 즉시 숨긴다.
    safe_cards = []
    seen_places: set[str] = set()
    for card in cards:
        if card.place_tag in seen_places or PRIVACY_PIPELINE_MARKER not in (card.source_contribution_ids or []):
            continue
        safe_cards.append(card)
        seen_places.add(card.place_tag)
    return [town_card_to_dict(card) for card in safe_cards]


@router.get(
    "/archive/places/{place_tag}/contributions",
    response_model=list[TownContributionAdminResponse],
)
def list_place_contributions(
    place_tag: str,
    _: str = Depends(require_admin_account),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """관리자 전용: 아직 동네 카드로 합쳐지기 전, 장소별로 모인 익명 회상 조각 목록.

    town_contributions에는 원문이 아니라 공유 시점에 이미 비식별화된 문장만 저장되어 있어
    작성자를 특정할 수 있는 정보는 응답에 포함하지 않는다.
    """
    if place_tag not in settings.place_tags:
        raise HTTPException(status_code=404, detail="등록되지 않은 장소 태그입니다.")
    contributions = db.scalars(
        select(TownContribution)
        .where(TownContribution.place_tag == place_tag)
        .order_by(TownContribution.created_at.asc())
    ).all()
    return [
        {
            "id": item.id,
            "place_tag": item.place_tag,
            "pre_reveal_text": item.pre_reveal_text,
            "post_reveal_text": item.post_reveal_text,
            "created_at": item.created_at,
        }
        for item in contributions
    ]


@router.delete("/archive/places/cards/{card_id}")
def delete_town_card(
    card_id: str,
    admin_username: str = Depends(require_admin_account),
    db: Session = Depends(get_db),
):
    card = db.get(TownCard, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="삭제할 동네 추억 카드를 찾을 수 없습니다.")
    if card.deleted_at is not None:
        raise HTTPException(status_code=409, detail="이미 삭제된 동네 추억 카드입니다.")
    place_tag = card.place_tag
    card.deleted_at = utcnow()
    card.deleted_by = admin_username
    db.commit()
    return {
        "deleted": True,
        "card_id": card_id,
        "place_tag": place_tag,
        "message": f"{place_tag} 동네 추억 카드를 삭제했습니다. 관리자 화면에서 복구할 수 있습니다.",
    }


@router.get("/archive/places/cards/deleted", response_model=list[TownCardResponse])
def list_deleted_town_cards(
    _: str = Depends(require_admin_account),
    db: Session = Depends(get_db),
):
    cards = db.scalars(
        select(TownCard)
        .where(TownCard.deleted_at.is_not(None))
        .order_by(TownCard.deleted_at.desc(), TownCard.updated_at.desc())
    ).all()
    return [town_card_to_dict(card) for card in cards]


@router.post("/archive/places/cards/{card_id}/restore", response_model=TownCardResponse)
def restore_town_card(
    card_id: str,
    _: str = Depends(require_admin_account),
    db: Session = Depends(get_db),
):
    card = db.get(TownCard, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="복구할 동네 추억 카드를 찾을 수 없습니다.")
    if card.deleted_at is None:
        raise HTTPException(status_code=409, detail="삭제되지 않은 동네 추억 카드입니다.")
    active_card = db.scalar(
        select(TownCard).where(
            TownCard.place_tag == card.place_tag,
            TownCard.deleted_at.is_(None),
            TownCard.id != card.id,
        )
    )
    if active_card:
        raise HTTPException(
            status_code=409,
            detail=f"{card.place_tag}에 이미 공개 중인 카드가 있어 복구할 수 없습니다. 현재 카드를 먼저 삭제해 주세요.",
        )
    card.deleted_at = None
    card.deleted_by = None
    card.updated_at = utcnow()
    db.commit()
    db.refresh(card)
    return town_card_to_dict(card)


@router.get("/archive/places/statuses", response_model=list[TownPlaceStatusResponse])
def list_place_statuses(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    contributions_by_place: dict[str, list[TownContribution]] = defaultdict(list)
    archived_by_place: dict[str, list[TownArchivedFragment]] = defaultdict(list)
    latest_by_place: dict[str, TownCard] = {}
    for item in db.scalars(select(TownContribution)).all():
        contributions_by_place[item.place_tag].append(item)
    for item in db.scalars(select(TownArchivedFragment)).all():
        archived_by_place[item.place_tag].append(item)
    cards = db.scalars(
        select(TownCard)
        .where(TownCard.deleted_at.is_(None))
        .order_by(TownCard.updated_at.desc(), TownCard.created_at.desc())
    ).all()
    for card in cards:
        latest_by_place.setdefault(card.place_tag, card)
    statuses = [
        _place_status_dict(
            place_tag,
            contributions_by_place[place_tag],
            archived_by_place[place_tag],
            latest_by_place.get(place_tag),
            settings,
        )
        for place_tag in settings.place_tags
    ]
    db.commit()
    return statuses


@router.get("/archive/places/{place_tag}/status", response_model=TownPlaceStatusResponse)
def get_place_status(
    place_tag: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    if place_tag not in settings.place_tags:
        raise HTTPException(status_code=404, detail="등록되지 않은 장소 태그입니다.")
    contributions = list(db.scalars(select(TownContribution).where(TownContribution.place_tag == place_tag)).all())
    archived_fragments = list(db.scalars(select(TownArchivedFragment).where(TownArchivedFragment.place_tag == place_tag)).all())
    latest = _latest_place_card(db, place_tag)
    status = _place_status_dict(place_tag, contributions, archived_fragments, latest, settings)
    db.commit()
    return status


def generate_town_card_if_ready(
    db: Session,
    settings: Settings,
    ai: AIService,
    place_tag: str,
    *,
    force: bool = False,
) -> tuple[TownCard | None, dict]:
    """기여자 수가 충족되면 동네 카드를 자동으로 생성/갱신한다.

    수동 트리거(관리자 버튼)와 opt-in 공유 직후 자동 트리거 양쪽에서 공유하는 핵심 로직이다.
    아직 조건이 안 되면 (None, 현재 상태)를 반환하고 예외를 던지지 않는다.
    """
    contributions = db.scalars(
        select(TownContribution)
        .where(TownContribution.place_tag == place_tag)
        .order_by(TownContribution.created_at.asc())
    ).all()
    archived_fragments = db.scalars(
        select(TownArchivedFragment)
        .where(TownArchivedFragment.place_tag == place_tag)
        .order_by(TownArchivedFragment.created_at.asc())
    ).all()
    current_keys = _current_contributor_keys(contributions, archived_fragments, settings)
    latest = _latest_place_card(db, place_tag)
    status = _place_status_dict(place_tag, contributions, archived_fragments, latest, settings)
    if not force and not status["can_generate"]:
        return None, status
    if force and (latest is None or len(current_keys) < settings.town_min_contributors):
        return None, status

    # 같은 사용자의 여러 카드는 하나의 익명 조각으로 합쳐 모든 참여자의 가중치를 동일하게 한다.
    fragments = _group_fragments_by_contributor(contributions, archived_fragments, settings)
    combined_text = "\n".join(
        part
        for fragment in fragments
        for part in (fragment["pre_reveal_text"], fragment["post_reveal_text"])
        if part
    )
    extracted = ai.extract_context(text=combined_text)
    privacy = ai.prepare_town_fragments(place_tag=place_tag, fragments=fragments)
    blocked_terms = list(
        dict.fromkeys(
            [
                *privacy.get("blocked_terms", []),
                *[item for item in extracted.get("people", []) if item not in NON_PERSON_TERMS],
                *[
                    place
                    for place in extracted.get("places", [])
                    if place != place_tag and place in settings.place_tags
                ],
            ]
        )
    )
    blocked_terms = [term for term in blocked_terms if term not in NON_PERSON_TERMS]
    safe_fragments = [
        {"text": censor_profanity(str(item.get("text") or ""))}
        for item in privacy.get("safe_fragments", [])
        if isinstance(item, dict) and str(item.get("text") or "").strip()
    ]
    common_themes = [censor_profanity(str(item)) for item in privacy.get("common_themes", [])]
    if not safe_fragments:
        safe_fragments = [{"text": "서로 다른 만남과 일상의 장면"}]
    result = ai.create_town_card(
        place_tag=place_tag,
        fragments=safe_fragments,
        common_themes=common_themes,
        blocked_terms=blocked_terms,
    )
    safe_title = censor_profanity(str(result.get("card_title") or f"{place_tag}의 동네 추억"))[:255]
    safe_story = censor_profanity(str(result.get("story") or ""))
    safe_reflection = censor_profanity(str(result.get("reflection") or ""))
    if any(contains_profanity(value) for value in (safe_title, safe_story, safe_reflection)):
        raise ServiceError("동네 카드의 공개 문구에서 부적절한 표현을 제거하지 못했습니다.")
    public_text = " ".join(
        (safe_title, safe_story, safe_reflection)
    ).casefold()
    leaked_terms = [term for term in blocked_terms if len(term.strip()) >= 2 and term.casefold() in public_text]
    if leaked_terms:
        raise ServiceError(
            "동네 카드 개인정보 검사에서 공개할 수 없는 표현을 발견했습니다.",
            detail={"action": "카드를 저장하지 않았습니다. 비식별화를 다시 시도해주세요."},
        )
    now = utcnow()
    if latest:
        card = latest
        card.contributors = len(current_keys)
        card.card_title = safe_title
        card.story = safe_story
        card.reflection = safe_reflection
        card.published_contributor_keys = sorted(current_keys)
        card.version = (card.version or 1) + 1
        card.updated_at = now
        card.source_contribution_ids = [
            *[item.id for item in contributions],
            *[f"archived:{item.id}" for item in archived_fragments],
            PRIVACY_PIPELINE_MARKER,
        ]
    else:
        card = TownCard(
            id=str(uuid.uuid4()),
            place_tag=place_tag,
            contributors=len(current_keys),
            card_title=safe_title,
            story=safe_story,
            reflection=safe_reflection,
            published_contributor_keys=sorted(current_keys),
            version=1,
            source_contribution_ids=[
                *[item.id for item in contributions],
                *[f"archived:{item.id}" for item in archived_fragments],
                PRIVACY_PIPELINE_MARKER,
            ],
            created_at=now,
            updated_at=now,
        )
        db.add(card)
    db.commit()
    db.refresh(card)
    return card, status


@router.post(
    "/archive/places/{place_tag}/card/reprocess",
    response_model=TownCardResponse,
)
def reprocess_town_card(
    place_tag: str,
    _: None = Depends(require_admin),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    ai: AIService = Depends(get_ai),
):
    """원본 회상 답변을 다시 비식별화하고 기존 동네 카드를 새 버전으로 만든다."""
    if place_tag not in settings.place_tags:
        raise HTTPException(status_code=404, detail="등록되지 않은 장소 태그입니다.")
    contributions = list(
        db.scalars(
            select(TownContribution)
            .where(TownContribution.place_tag == place_tag)
            .order_by(TownContribution.created_at.asc())
        ).all()
    )
    distinct_count = len({_active_contributor_key(item, settings) for item in contributions})
    if distinct_count < settings.town_min_contributors:
        raise HTTPException(status_code=409, detail="재처리하려면 서로 다른 사용자 3명의 공유 조각이 필요합니다.")
    if _latest_place_card(db, place_tag) is None:
        raise HTTPException(status_code=404, detail="다시 만들 기존 동네 추억 카드가 없습니다.")
    if not _reprocess_place_contributions(contributions, settings, ai):
        raise HTTPException(status_code=409, detail="다시 비식별화할 회상 답변이 없습니다.")
    db.flush()
    card, _ = generate_town_card_if_ready(db, settings, ai, place_tag, force=True)
    if card is None:
        raise HTTPException(status_code=409, detail="동네 추억 카드를 다시 만들지 못했습니다.")
    return town_card_to_dict(card)


@router.post("/archive/places/{place_tag}/card", response_model=TownCardResponse, status_code=201)
def create_town_card(
    place_tag: str,
    _: None = Depends(require_admin),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    ai: AIService = Depends(get_ai),
):
    """관리자 수동 트리거. 조건이 안 되면 명확한 사유와 함께 409를 반환한다."""
    if place_tag not in settings.place_tags:
        raise HTTPException(status_code=404, detail="등록되지 않은 장소 태그입니다.")
    card, status = generate_town_card_if_ready(db, settings, ai, place_tag)
    if card is None:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "기존 카드 갱신에는 새로운 기여자 3명이 필요합니다." if status["latest_card_id"] else "아직 동네 추억 카드를 만들기에 기여자가 부족합니다.",
                "current": status["new_contributors"] if status["latest_card_id"] else status["distinct_contributors"],
                "required": status["minimum_required"],
            },
        )
    return town_card_to_dict(card)
