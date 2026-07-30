from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile as StarletteUploadFile

from app.config import PLACE_TAG_ALIASES, Settings
from app.constants import (
    MEMORY_STATUS_PROCESSED,
    MEMORY_STATUS_REGISTERED,
    PROCESS_COMPLETED,
    PROCESS_FAILED,
    PROCESS_PENDING,
    PROCESS_PROCESSING,
    PROCESS_SKIPPED,
)
from app.dependencies import get_ai, get_current_user_id, get_db, get_settings, get_storage
from app.models import Memory, TownContribution, utcnow
from app.repositories import get_owned_memory
from app.schemas import MemoryDeleteResponse, MemoryProcessResponse, MemoryResponse, PlaceTagConfirmRequest
from app.serializers import memory_to_dict
from app.services.ai import AIService
from app.services.community import detach_or_delete_contribution
from app.services.scheduling import create_schedule
from app.services.storage import StorageBackend

router = APIRouter(prefix="/memories", tags=["memories"])


def normalize_optional_image(value: UploadFile | str | None) -> StarletteUploadFile | None:
    if value is None:
        return None
    if isinstance(value, str):
        if value.strip() == "":
            return None
        raise HTTPException(status_code=400, detail="image에는 파일만 전달할 수 있습니다.")
    if isinstance(value, StarletteUploadFile):
        if not value.filename:
            return None
        return value
    raise HTTPException(status_code=400, detail="지원하지 않는 이미지 입력 형식입니다.")


def validate_and_read_image(image: StarletteUploadFile, settings: Settings) -> tuple[bytes, str, str]:
    content_type = image.content_type or "application/octet-stream"
    if content_type not in settings.allowed_image_type_set:
        raise HTTPException(status_code=400, detail="JPG, PNG, WEBP 이미지만 업로드할 수 있습니다.")
    data = image.file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(status_code=413, detail=f"이미지는 {settings.max_upload_mb}MB 이하만 업로드할 수 있습니다.")
    if not data:
        raise HTTPException(status_code=400, detail="빈 이미지 파일은 업로드할 수 없습니다.")
    return data, image.filename or "image", content_type


def _source_text(memory: Memory) -> str:
    parts = [memory.comment.strip()]
    if memory.place_label:
        parts.append(f"[사용자가 입력한 장소]\n{memory.place_label.strip()}")
    if memory.ocr_text:
        parts.append(f"[사진 속 텍스트]\n{memory.ocr_text.strip()}")
    return "\n\n".join(part for part in parts if part)


def run_parse(memory: Memory, db: Session, storage: StorageBackend, ai: AIService) -> dict[str, Any]:
    if not memory.use_ocr:
        memory.ocr_status = PROCESS_SKIPPED
        memory.ocr_text = None
        memory.ocr_error = None
        db.commit()
        return {"step": "document_parse", "status": PROCESS_SKIPPED, "reason": "use_ocr=false"}
    if not memory.image_path:
        raise HTTPException(status_code=400, detail="OCR을 실행할 이미지가 없습니다.")

    memory.ocr_status = PROCESS_PROCESSING
    memory.ocr_error = None
    db.commit()
    try:
        data, content_type = storage.read(memory.image_path)
        text = ai.parse_document(
            data=data,
            filename=memory.image_filename or "image",
            content_type=memory.image_content_type or content_type,
        )
        memory.ocr_text = text
        memory.ocr_status = PROCESS_COMPLETED
        memory.updated_at = utcnow()
        db.commit()
        return {"step": "document_parse", "status": PROCESS_COMPLETED, "text_length": len(text)}
    except Exception as exc:
        memory.ocr_status = PROCESS_FAILED
        memory.ocr_error = str(exc)
        db.commit()
        raise


def _suggest_place_tag(memory: Memory, extracted: dict[str, Any], settings: Settings) -> str | None:
    sources = [memory.place_label or "", memory.comment, *extracted.get("places", [])]
    normalized = " ".join(str(item).replace(" ", "").casefold() for item in sources if item)
    matches: list[tuple[int, str]] = []
    for tag in settings.place_tags:
        terms = [tag, *PLACE_TAG_ALIASES.get(tag, [])]
        matched_lengths = [len(term) for term in terms if term.replace(" ", "").casefold() in normalized]
        if matched_lengths:
            matches.append((max(matched_lengths), tag))
    return max(matches)[1] if matches else None


def run_extract(memory: Memory, db: Session, ai: AIService, settings: Settings) -> dict[str, Any]:
    if memory.use_ocr and memory.ocr_status not in {PROCESS_COMPLETED, PROCESS_SKIPPED}:
        raise HTTPException(status_code=409, detail="OCR 처리 후 Information Extract를 실행해주세요.")
    memory.extraction_status = PROCESS_PROCESSING
    memory.extraction_error = None
    db.commit()
    try:
        extracted = ai.extract_context(text=_source_text(memory))
        memory.extracted_context = extracted
        memory.suggested_place_tag = memory.place_tag or _suggest_place_tag(memory, extracted, settings)
        memory.extraction_status = PROCESS_COMPLETED
        memory.updated_at = utcnow()
        db.commit()
        return {"step": "information_extract", "status": PROCESS_COMPLETED, "fields": extracted}
    except Exception as exc:
        memory.extraction_status = PROCESS_FAILED
        memory.extraction_error = str(exc)
        db.commit()
        raise


def run_analyze(memory: Memory, db: Session, ai: AIService) -> dict[str, Any]:
    if memory.extraction_status != PROCESS_COMPLETED:
        raise HTTPException(status_code=409, detail="Information Extract 처리 후 Solar 분석을 실행해주세요.")
    memory.analysis_status = PROCESS_PROCESSING
    memory.analysis_error = None
    db.commit()
    try:
        analysis = ai.analyze_memory(
            original_text=_source_text(memory),
            extracted=memory.extracted_context or {},
        )
        memory.analysis = analysis
        memory.analysis_status = PROCESS_COMPLETED
        memory.status = MEMORY_STATUS_PROCESSED
        memory.updated_at = utcnow()
        db.commit()
        return {"step": "solar_analyze", "status": PROCESS_COMPLETED, "analysis": analysis}
    except Exception as exc:
        memory.analysis_status = PROCESS_FAILED
        memory.analysis_error = str(exc)
        db.commit()
        raise


@router.post("", response_model=MemoryResponse, status_code=201)
def create_memory(
    request: Request,
    comment: Annotated[str, Form(min_length=1, max_length=2000)],
    memory_date: Annotated[date, Form()],
    use_ocr: Annotated[bool, Form()] = False,
    place_tag: Annotated[str | None, Form()] = None,
    place_label: Annotated[str | None, Form(max_length=255)] = None,
    first_recall_days: Annotated[int | None, Form(ge=0, le=30)] = None,
    second_recall_days: Annotated[int | None, Form(ge=0, le=365)] = None,
    image: Annotated[
        UploadFile | str | None,
        File(description="선택 사항. 파일을 고르지 않으면 빈 값을 None으로 처리합니다."),
    ] = None,
    owner_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
    settings: Settings = Depends(get_settings),
):
    cleaned_comment = comment.strip()
    if not cleaned_comment:
        raise HTTPException(status_code=400, detail="코멘트를 입력해주세요.")

    normalized_place_tag = (place_tag or "").strip() or None
    normalized_place_label = (place_label or "").strip() or None
    if normalized_place_tag and normalized_place_tag not in settings.place_tags:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "허용되지 않은 장소 태그입니다.",
                "allowed": settings.place_tags,
            },
        )

    normalized_image = normalize_optional_image(image)
    stored = None
    if normalized_image is not None:
        data, filename, content_type = validate_and_read_image(normalized_image, settings)
        stored = storage.save(owner_id=owner_id, filename=filename, content_type=content_type, data=data)
    if use_ocr and stored is None:
        raise HTTPException(status_code=400, detail="OCR을 사용하려면 사진을 등록해야 합니다.")

    created_at = utcnow()
    try:
        first_at, second_at = create_schedule(
            created_at,
            settings,
            first_days=first_recall_days,
            second_days=second_recall_days,
        )
    except ValueError as exc:
        if stored:
            storage.delete(stored.path)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    memory = Memory(
        id=str(uuid.uuid4()),
        owner_id=owner_id,
        comment=cleaned_comment,
        memory_date=memory_date,
        place_label=normalized_place_label,
        image_path=stored.path if stored else None,
        image_filename=stored.filename if stored else None,
        image_content_type=stored.content_type if stored else None,
        use_ocr=use_ocr,
        ocr_status=PROCESS_PENDING if use_ocr else PROCESS_SKIPPED,
        ocr_text=None,
        extraction_status=PROCESS_PENDING,
        extracted_context={"people": [], "places": [], "activities": [], "atmosphere": [], "emotions": []},
        analysis_status=PROCESS_PENDING,
        analysis={"title": None, "summary": None, "emotions": [], "recall_cues": []},
        first_recall_at=first_at,
        second_recall_at=second_at,
        current_recall_stage=1,
        recall_completed=False,
        place_tag=normalized_place_tag,
        suggested_place_tag=normalized_place_tag,
        share_to_town=False,
        status=MEMORY_STATUS_REGISTERED,
        created_at=created_at,
        updated_at=created_at,
    )
    try:
        db.add(memory)
        db.commit()
        db.refresh(memory)
    except Exception:
        db.rollback()
        if stored:
            storage.delete(stored.path)
        raise
    return memory_to_dict(memory, request)


@router.get("", response_model=list[MemoryResponse])
def list_memories(
    request: Request,
    owner_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    memories = db.scalars(
        select(Memory).where(Memory.owner_id == owner_id).order_by(Memory.created_at.desc())
    ).all()
    return [memory_to_dict(memory, request) for memory in memories]


@router.get("/{memory_id}", response_model=MemoryResponse)
def get_memory(
    memory_id: str,
    request: Request,
    owner_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    memory = get_owned_memory(db, memory_id, owner_id)
    return memory_to_dict(memory, request)


@router.patch("/{memory_id}/place-tag", response_model=MemoryResponse)
def confirm_memory_place_tag(
    memory_id: str,
    payload: PlaceTagConfirmRequest,
    request: Request,
    owner_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    memory = get_owned_memory(db, memory_id, owner_id)
    place_tag = (payload.place_tag or "").strip() or None
    if place_tag and place_tag not in settings.place_tags:
        raise HTTPException(status_code=400, detail={"message": "허용되지 않은 장소 태그입니다.", "allowed": settings.place_tags})
    memory.place_tag = place_tag
    memory.updated_at = utcnow()
    db.commit()
    db.refresh(memory)
    return memory_to_dict(memory, request)


@router.delete("/{memory_id}", response_model=MemoryDeleteResponse)
def delete_memory(
    memory_id: str,
    owner_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
    settings: Settings = Depends(get_settings),
    ai: AIService = Depends(get_ai),
):
    """개인 자료는 삭제하되, 이미 발행된 동네 카드의 비식별 조각만 연결 없이 보존한다."""
    memory = get_owned_memory(db, memory_id, owner_id)
    removed_recalls = len(memory.recalls)
    removed_cards = len(memory.cards)
    contributions = db.scalars(
        select(TownContribution).where(TownContribution.memory_id == memory.id)
    ).all()
    pending = 0
    preserved = 0
    for contribution in contributions:
        if detach_or_delete_contribution(db, contribution, ai=ai, settings=settings):
            preserved += 1
        else:
            pending += 1

    image_path = memory.image_path
    generated_image_paths = [card.generated_image_path for card in memory.cards if card.generated_image_path]
    if image_path:
        # 원본 사진이 남는 것보다 삭제 실패를 사용자에게 알리는 편이 개인정보 보호에 안전하다.
        storage.delete(image_path)
    for generated_path in generated_image_paths:
        storage.delete(generated_path)
    db.delete(memory)
    db.commit()
    return {
        "memory_id": memory_id,
        "deleted_photo": bool(image_path),
        "removed_recalls": removed_recalls,
        "removed_cards": removed_cards,
        "removed_pending_contributions": pending,
        "preserved_anonymous_fragments": preserved,
        "message": (
            "개인 기억과 연결 정보를 삭제했습니다. 이미 동네 카드에 반영된 비식별 조각은 익명 상태로 유지됩니다."
            if preserved else "개인 기억과 관련 자료를 모두 삭제했습니다."
        ),
    }


@router.get("/{memory_id}/image", name="get_memory_image")
def get_memory_image(
    memory_id: str,
    owner_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
):
    memory = get_owned_memory(db, memory_id, owner_id)
    if not memory.image_path:
        raise HTTPException(status_code=404, detail="이 기억에는 이미지가 없습니다.")
    data, content_type = storage.read(memory.image_path)
    return Response(content=data, media_type=memory.image_content_type or content_type)


@router.post("/{memory_id}/parse", response_model=MemoryResponse)
def parse_memory_image(
    memory_id: str,
    request: Request,
    owner_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
    ai: AIService = Depends(get_ai),
):
    memory = get_owned_memory(db, memory_id, owner_id)
    run_parse(memory, db, storage, ai)
    db.refresh(memory)
    return memory_to_dict(memory, request)


@router.post("/{memory_id}/extract", response_model=MemoryResponse)
def extract_memory_context(
    memory_id: str,
    request: Request,
    owner_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    ai: AIService = Depends(get_ai),
    settings: Settings = Depends(get_settings),
):
    memory = get_owned_memory(db, memory_id, owner_id)
    run_extract(memory, db, ai, settings)
    db.refresh(memory)
    return memory_to_dict(memory, request)


@router.post("/{memory_id}/analyze", response_model=MemoryResponse)
def analyze_memory(
    memory_id: str,
    request: Request,
    owner_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    ai: AIService = Depends(get_ai),
):
    memory = get_owned_memory(db, memory_id, owner_id)
    run_analyze(memory, db, ai)
    db.refresh(memory)
    return memory_to_dict(memory, request)


@router.post("/{memory_id}/process", response_model=MemoryProcessResponse)
def process_memory_pipeline(
    memory_id: str,
    request: Request,
    owner_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
    ai: AIService = Depends(get_ai),
    settings: Settings = Depends(get_settings),
):
    memory = get_owned_memory(db, memory_id, owner_id)
    steps: list[dict[str, Any]] = []
    if memory.use_ocr:
        steps.append(run_parse(memory, db, storage, ai))
    else:
        memory.ocr_status = PROCESS_SKIPPED
        steps.append({"step": "document_parse", "status": PROCESS_SKIPPED})
    steps.append(run_extract(memory, db, ai, settings))
    steps.append(run_analyze(memory, db, ai))
    db.refresh(memory)
    return {"memory": memory_to_dict(memory, request), "steps": steps}
