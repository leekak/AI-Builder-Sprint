from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.config import Settings
from app.dependencies import get_ai, get_card_image_service, get_current_user_id, get_db, get_settings, get_storage
from app.errors import ServiceError
from app.models import MemoryCard, TownContribution, utcnow
from app.repositories import get_owned_card
from app.schemas import (
    ArchiveCardRequest,
    CardImageGenerateRequest,
    CardImageResponse,
    MemoryCardResponse,
    ShareToTownRequest,
    TownSharePreviewRequest,
    TownSharePreviewResponse,
    TownShareResponse,
)
from app.serializers import card_to_dict
from app.api.archive import generate_town_card_if_ready
from app.services.ai import AIService
from app.services.card_image import CardImageService
from app.services.content_safety import censor_profanity
from app.services.storage import StorageBackend
from app.services.community import (
    create_share_preview_token,
    contribution_was_published,
    contributor_key,
    detach_or_delete_contribution,
    sanitize_contribution,
    verify_share_preview_token,
)

router = APIRouter(prefix="/cards", tags=["cards"])
logger = logging.getLogger(__name__)


def _card_image_response(card: MemoryCard, request: Request) -> dict:
    return {
        "card_id": card.id,
        "status": card.image_generation_status or "not_requested",
        "mode": card.image_generation_mode,
        "style": card.image_generation_style,
        "generated_image_url": (
            str(request.url_for("get_generated_card_image", card_id=card.id))
            if card.generated_image_path else None
        ),
        "ai_generated": True,
    }


def _share_text(card: MemoryCard) -> tuple[str, str]:
    recall = card.recall
    pre_parts = []
    if recall.initial_answer:
        pre_parts.append(recall.initial_answer.strip())
    for item in recall.hint_answers or []:
        answer = str(item.get("answer", "")).strip()
        if answer:
            pre_parts.append(answer)
    return "\n".join(pre_parts).strip(), (recall.newly_recalled_text or "").strip()


def _town_share_status(db: Session, card: MemoryCard) -> str:
    if not card.shared_to_town:
        return "not_shared"
    contribution = db.scalar(select(TownContribution).where(TownContribution.card_id == card.id))
    if contribution and contribution_was_published(db, contribution.id):
        return "published"
    return "pending"


def _image_source_text(memory) -> str:
    """AI 이미지 생성 프롬프트에 쓸 '사실 기반' 텍스트만 모은다.

    원본 공개 전 답변(initial_answer)과 힌트 답변(hint_answers)은 사용자가 원본을
    보기 전에 떠올린 추측이라 실제와 다를 수 있다. 잘못된 내용이 그대로 이미지로
    그려지지 않도록, 이미지 생성에는 다음 세 가지만 사용한다: 기억 원본 코멘트,
    1차 회상에서 원본을 본 뒤 추가한 내용, 2차 회상에서 원본을 본 뒤 추가한 내용.
    card.story는 화면에 보여주는 회상 여정용 텍스트라 추측 내용이 섞여 있어
    이미지 프롬프트에는 쓰지 않는다.
    """
    parts = [memory.comment.strip()]
    for recall in sorted(memory.recalls, key=lambda item: item.stage):
        if recall.newly_recalled_text and recall.newly_recalled_text.strip():
            parts.append(recall.newly_recalled_text.strip())
    return " ".join(parts)


@router.get("", response_model=list[MemoryCardResponse])
def list_cards(
    request: Request,
    archived: bool | None = None,
    sort: str = "latest",
    owner_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    stmt = (
        select(MemoryCard)
        .options(joinedload(MemoryCard.memory), joinedload(MemoryCard.recall))
        .where(MemoryCard.owner_id == owner_id)
    )
    if archived is not None:
        stmt = stmt.where(MemoryCard.archived.is_(archived))
    if sort not in {"latest", "memory_date"}:
        raise HTTPException(status_code=400, detail="sort는 latest 또는 memory_date여야 합니다.")
    stmt = stmt.order_by(MemoryCard.created_at.desc())
    cards = db.scalars(stmt).unique().all()
    # 과거 버전에서 회상 차수마다 생성된 중복 카드는 원본 기억별 최신 한 장만 노출한다.
    seen_memory_ids: set[str] = set()
    unique_cards = []
    for card in cards:
        if card.memory_id in seen_memory_ids:
            continue
        seen_memory_ids.add(card.memory_id)
        unique_cards.append(card)
    cards = unique_cards
    if sort == "memory_date":
        cards.sort(key=lambda card: card.memory.memory_date, reverse=True)
    return [card_to_dict(card, request, town_share_status=_town_share_status(db, card)) for card in cards]


@router.post("/{card_id}/generate-image", response_model=CardImageResponse)
def generate_card_image(
    card_id: str,
    payload: CardImageGenerateRequest,
    request: Request,
    owner_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
    image_service: CardImageService = Depends(get_card_image_service),
):
    card = get_owned_card(db, card_id, owner_id)
    memory = card.memory
    if memory.image_path:
        raise HTTPException(status_code=409, detail="원본 사진이 있는 카드는 원본 사진을 그대로 사용합니다.")

    image_source_text = _image_source_text(memory)
    style = image_service.choose_style(image_source_text)

    prompt = image_service.build_prompt(
        mode=payload.mode,
        style=style,
        memory_date=memory.memory_date.isoformat(),
        place=memory.place_label or memory.place_tag,
        story=image_source_text,
        details=card.newly_recalled_details or [],
    )
    card.image_generation_status = "pending"
    card.image_generation_mode = payload.mode
    card.image_generation_style = style
    card.image_generation_prompt = prompt
    card.updated_at = utcnow()
    db.commit()

    try:
        generated = image_service.generate(
            prompt=prompt,
            source_image=None,
            source_content_type=None,
        )
        stored = storage.save(
            owner_id=f"{owner_id}/generated",
            filename=f"card-{card.id}.png",
            content_type="image/png",
            data=generated,
        )
        old_path = card.generated_image_path
        card.generated_image_path = stored.path
        card.generated_image_filename = stored.filename
        card.generated_image_content_type = stored.content_type
        card.image_generation_status = "completed"
        card.image_generated_at = utcnow()
        card.updated_at = utcnow()
        db.commit()
        if old_path and old_path != stored.path:
            try:
                storage.delete(old_path)
            except ServiceError:
                # 새 이미지는 이미 안전하게 저장됐으므로 예전 파일 정리 실패가 카드 생성을 되돌리지는 않는다.
                pass
        return _card_image_response(card, request)
    except Exception:
        card.image_generation_status = "failed"
        card.updated_at = utcnow()
        db.commit()
        raise


@router.get("/{card_id}/generated-image", name="get_generated_card_image")
def get_generated_card_image(
    card_id: str,
    owner_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
):
    card = get_owned_card(db, card_id, owner_id)
    if not card.generated_image_path:
        raise HTTPException(status_code=404, detail="생성된 추억 이미지가 없습니다.")
    data, detected_type = storage.read(card.generated_image_path)
    return Response(content=data, media_type=card.generated_image_content_type or detected_type)


@router.delete("/{card_id}/generated-image", response_model=CardImageResponse)
def delete_generated_card_image(
    card_id: str,
    request: Request,
    owner_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
):
    card = get_owned_card(db, card_id, owner_id)
    if card.generated_image_path:
        storage.delete(card.generated_image_path)
    card.generated_image_path = None
    card.generated_image_filename = None
    card.generated_image_content_type = None
    card.image_generation_status = "not_requested"
    card.image_generation_mode = None
    card.image_generation_style = None
    card.image_generation_prompt = None
    card.image_generated_at = None
    card.updated_at = utcnow()
    db.commit()
    return _card_image_response(card, request)


@router.get("/{card_id}", response_model=MemoryCardResponse)
def get_card(
    card_id: str,
    request: Request,
    owner_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    card = get_owned_card(db, card_id, owner_id)
    return card_to_dict(card, request, town_share_status=_town_share_status(db, card))


@router.post("/{card_id}/archive", response_model=MemoryCardResponse)
def archive_card(
    card_id: str,
    payload: ArchiveCardRequest,
    request: Request,
    owner_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    card = get_owned_card(db, card_id, owner_id)
    card.archived = payload.archived
    card.updated_at = utcnow()
    db.commit()
    db.refresh(card)
    return card_to_dict(card, request, town_share_status=_town_share_status(db, card))


@router.post("/{card_id}/share-to-town", response_model=TownShareResponse)
def share_card_to_town(
    card_id: str,
    payload: ShareToTownRequest,
    owner_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    ai: AIService = Depends(get_ai),
):
    card = get_owned_card(db, card_id, owner_id)
    memory = card.memory
    recall = card.recall

    if not payload.consent:
        existing = db.scalar(select(TownContribution).where(TownContribution.card_id == card.id))
        if existing:
            detach_or_delete_contribution(db, existing, ai=ai, settings=settings)
        card.shared_to_town = False
        card.place_tag = None
        memory.share_to_town = False
        db.commit()
        return {"card_id": card.id, "consent": False, "place_tag": None, "contribution_id": None}

    place_tag = (payload.place_tag or "").strip()
    if not place_tag:
        raise HTTPException(status_code=400, detail="공유할 장소 태그를 선택해주세요.")
    if place_tag not in settings.place_tags:
        raise HTTPException(status_code=400, detail={"message": "허용되지 않은 장소 태그입니다.", "allowed": settings.place_tags})
    if card.shared_to_town and card.place_tag and card.place_tag != place_tag:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "이미 다른 동네에 공유된 기억은 장소를 바로 옮길 수 없습니다.",
                "action": "먼저 공유를 취소한 뒤 새 장소로 다시 공유해주세요.",
                "current_place_tag": card.place_tag,
            },
        )

    pre_text, post_text = _share_text(card)
    if not pre_text and not post_text:
        raise HTTPException(status_code=400, detail="공유할 회상 조각이 없습니다.")
    if payload.preview_token:
        try:
            safe_pre_text, safe_post_text = verify_share_preview_token(
                settings,
                payload.preview_token,
                card_id=card.id,
                owner_id=owner_id,
                place_tag=place_tag,
            )
        except ServiceError as exc:
            raise HTTPException(status_code=400, detail={"message": exc.message, **(exc.detail or {})}) from exc
    else:
        safe_pre_text, safe_post_text = sanitize_contribution(
            ai,
            settings,
            place_tag=place_tag,
            pre_text=pre_text,
            post_text=post_text,
        )

    # 위에서 이미 "장소 이동" 시도를 막았으므로, 여기 남아있는 기여가 있다면 같은 장소일 수밖에 없다.
    existing = db.scalar(select(TownContribution).where(TownContribution.card_id == card.id))

    # 같은 사용자가 다른 기억(카드)으로 이미 이 장소에 공유해 둔 경우, 명시적으로 교체 확인을 받는다.
    conflicting = db.scalar(
        select(TownContribution).where(
            TownContribution.owner_id == owner_id,
            TownContribution.place_tag == place_tag,
            TownContribution.card_id != card.id,
        )
    )
    if conflicting:
        conflicting_card = db.get(MemoryCard, conflicting.card_id)
        if not payload.replace_existing:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "이미 이 장소에 다른 기억이 등록되어 있습니다.",
                    "conflicting_card_id": conflicting.card_id,
                    "conflicting_card_title": conflicting_card.card_title if conflicting_card else None,
                },
            )
        # 이미 발행된 동네 카드에 쓰인 조각이라면 익명 보존 후 교체, 아니면 그냥 삭제 후 교체한다.
        detach_or_delete_contribution(db, conflicting, ai=ai, settings=settings)
        if conflicting_card:
            conflicting_card.shared_to_town = False
            conflicting_card.place_tag = None
        db.flush()

    participant_key = contributor_key(settings, owner_id=owner_id, place_tag=place_tag)
    if existing:
        contribution = existing
        contribution.place_tag = place_tag
        contribution.contributor_key = participant_key
        contribution.pre_reveal_text = safe_pre_text
        contribution.post_reveal_text = safe_post_text
    else:
        contribution = TownContribution(
            id=str(uuid.uuid4()),
            card_id=card.id,
            memory_id=memory.id,
            recall_id=recall.id,
            owner_id=owner_id,
            contributor_key=participant_key,
            place_tag=place_tag,
            pre_reveal_text=safe_pre_text,
            post_reveal_text=safe_post_text,
            created_at=utcnow(),
        )
        db.add(contribution)

    card.shared_to_town = True
    card.place_tag = place_tag
    card.updated_at = utcnow()
    memory.share_to_town = True
    memory.updated_at = utcnow()
    db.commit()
    db.refresh(contribution)

    # 서로 다른 기여자 3명이 모이면 관리자 개입 없이 자동으로 동네 카드를 생성/갱신한다.
    # 생성 파이프라인 실패가 공유 자체를 막지 않도록 실패는 조용히 넘어간다 (관리자가 나중에 수동 재시도 가능).
    try:
        generate_town_card_if_ready(db, settings, ai, place_tag)
    except Exception:
        logger.exception("동네 카드 자동 생성 실패 (place_tag=%s)", place_tag)

    return {
        "card_id": card.id,
        "consent": True,
        "place_tag": place_tag,
        "contribution_id": contribution.id,
    }


@router.post("/{card_id}/share-preview", response_model=TownSharePreviewResponse)
def preview_card_for_town(
    card_id: str,
    payload: TownSharePreviewRequest,
    owner_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    ai: AIService = Depends(get_ai),
):
    card = get_owned_card(db, card_id, owner_id)
    place_tag = payload.place_tag.strip()
    if place_tag not in settings.place_tags:
        raise HTTPException(status_code=400, detail={"message": "허용되지 않은 장소 태그입니다.", "allowed": settings.place_tags})
    if card.shared_to_town and card.place_tag and card.place_tag != place_tag:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "이미 다른 동네에 공유된 기억은 장소를 바로 옮길 수 없습니다.",
                "action": "먼저 공유를 취소한 뒤 새 장소로 다시 공유해주세요.",
                "current_place_tag": card.place_tag,
            },
        )
    pre_text, post_text = _share_text(card)
    if not pre_text and not post_text:
        raise HTTPException(status_code=400, detail="공유할 회상 조각이 없습니다.")
    safe_pre_text, safe_post_text = sanitize_contribution(
        ai,
        settings,
        place_tag=place_tag,
        pre_text=pre_text,
        post_text=post_text,
    )
    safe_summary_text = censor_profanity(
        ai.summarize_share_preview(
            place_tag=place_tag,
            safe_pre_text=safe_pre_text,
            safe_post_text=safe_post_text,
        )
    )
    conflicting = db.scalar(
        select(TownContribution).where(
            TownContribution.owner_id == owner_id,
            TownContribution.place_tag == place_tag,
            TownContribution.card_id != card.id,
        )
    )
    conflicting_card = (
        db.get(MemoryCard, conflicting.card_id) if conflicting is not None else None
    )
    return {
        "card_id": card.id,
        "place_tag": place_tag,
        "safe_pre_text": safe_pre_text,
        "safe_post_text": safe_post_text,
        "safe_summary_text": safe_summary_text,
        "preview_token": create_share_preview_token(
            settings,
            card_id=card.id,
            owner_id=owner_id,
            place_tag=place_tag,
            safe_pre_text=safe_pre_text,
            safe_post_text=safe_post_text,
        ),
        "conflicting_card_id": conflicting_card.id if conflicting_card else None,
        "conflicting_card_title": conflicting_card.card_title if conflicting_card else None,
    }
