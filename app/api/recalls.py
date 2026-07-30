from __future__ import annotations

import uuid
from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.constants import (
    MEMORY_STATUS_PROCESSED,
    MEMORY_STATUS_RECALLED,
    MEMORY_STATUS_RECALL_IN_PROGRESS,
    PROCESS_COMPLETED,
    RECALL_STATUS_ANSWERED,
    RECALL_STATUS_COMPLETED,
    RECALL_STATUS_CREATED,
    RECALL_STATUS_QUESTION_READY,
    RECALL_STATUS_REVEALED,
)
from app.dependencies import get_ai, get_current_user_id, get_db, get_settings
from app.models import Memory, MemoryCard, RecallSession, utcnow
from app.repositories import get_owned_memory, get_owned_recall
from app.schemas import (
    AdditionalMemoryRequest,
    CompleteRecallRequest,
    DueRecallResponse,
    MemoryCardResponse,
    RecallAnswerRequest,
    RecallCreateRequest,
    RecallQuestionsResponse,
    RecallSessionResponse,
    RevealResponse,
)
from app.serializers import card_to_dict, recall_to_dict
from app.services.ai import AIService
from app.services.scheduling import ensure_aware, next_recall_at

router = APIRouter(prefix="/recalls", tags=["recalls"])


def _cue_categories(memory: Memory) -> list[str]:
    """원본의 정답을 노출하지 않는 범주형 단서만 만든다."""
    extracted = memory.extracted_context or {}
    categories = []
    field_labels = (
        ("people", "사람"),
        ("places", "장소"),
        ("activities", "활동"),
        ("atmosphere", "분위기"),
        ("emotions", "감정"),
    )
    for field, label in field_labels:
        if extracted.get(field):
            categories.append(label)
    return categories[:3] or ["일상의 장면"]


def _is_due(memory: Memory, settings: Settings) -> bool:
    if memory.recall_completed:
        return False
    due_at = next_recall_at(memory)
    if due_at is None:
        return False
    return ensure_aware(due_at) <= utcnow()


@router.get("/due", response_model=list[DueRecallResponse])
def get_due_recalls(
    owner_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    all_memories = db.scalars(select(Memory).where(Memory.owner_id == owner_id)).all()
    memories_by_date: dict = {}
    for item in sorted(all_memories, key=lambda memory: (memory.memory_date, memory.created_at, memory.id)):
        memories_by_date.setdefault(item.memory_date, []).append(item)
    result = []
    for memory in all_memories:
        if memory.recall_completed:
            continue
        if _is_due(memory, settings):
            due_at = next_recall_at(memory)
            same_day = memories_by_date[memory.memory_date]
            result.append(
                {
                    "memory_id": memory.id,
                    "memory_date": memory.memory_date,
                    "day_sequence": same_day.index(memory) + 1,
                    "same_day_count": len(same_day),
                    "place_tag": memory.place_tag,
                    "cue_categories": _cue_categories(memory),
                    "stage": memory.current_recall_stage,
                    "due_at": due_at,
                    "status": memory.status,
                }
            )
    result.sort(key=lambda item: ensure_aware(item["due_at"]))
    return result


@router.post("", response_model=RecallSessionResponse, status_code=201)
def create_recall_session(
    payload: RecallCreateRequest,
    owner_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    memory = get_owned_memory(db, payload.memory_id, owner_id)
    if memory.analysis_status != PROCESS_COMPLETED:
        raise HTTPException(status_code=409, detail="기억 분석을 완료한 뒤 회상을 시작할 수 있습니다.")
    if memory.recall_completed:
        raise HTTPException(status_code=409, detail="모든 회상이 완료된 기억입니다.")
    if not settings.allow_early_recall and not _is_due(memory, settings):
        raise HTTPException(status_code=409, detail="아직 회상 예정 시점이 되지 않았습니다.")

    existing = db.scalar(
        select(RecallSession).where(
            RecallSession.memory_id == memory.id,
            RecallSession.stage == memory.current_recall_stage,
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail={"message": "이미 생성된 회상 세션입니다.", "recall_id": existing.id})

    recall = RecallSession(
        id=str(uuid.uuid4()),
        memory_id=memory.id,
        owner_id=owner_id,
        stage=memory.current_recall_stage,
        status=RECALL_STATUS_CREATED,
        questions=[],
        hint_answers=[],
        hint_level=0,
        memory_not_recalled=False,
        started_at=utcnow(),
    )
    memory.status = MEMORY_STATUS_RECALL_IN_PROGRESS
    memory.updated_at = utcnow()
    db.add(recall)
    db.commit()
    db.refresh(recall)
    return recall_to_dict(recall)


@router.get("/{recall_id}", response_model=RecallSessionResponse)
def get_recall_session(
    recall_id: str,
    owner_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return recall_to_dict(get_owned_recall(db, recall_id, owner_id))


@router.post("/{recall_id}/questions", response_model=RecallQuestionsResponse)
def generate_recall_questions(
    recall_id: str,
    owner_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    ai: AIService = Depends(get_ai),
):
    recall = get_owned_recall(db, recall_id, owner_id)
    if recall.status == RECALL_STATUS_COMPLETED:
        raise HTTPException(status_code=409, detail="이미 완료된 회상 세션입니다.")
    memory = get_owned_memory(db, recall.memory_id, owner_id)
    questions = ai.generate_questions(
        extracted=memory.extracted_context or {},
        analysis=memory.analysis or {},
    )
    recall.questions = questions
    recall.status = RECALL_STATUS_QUESTION_READY
    db.commit()
    return {"recall_id": recall.id, "questions": questions}


@router.post("/{recall_id}/answers", response_model=RecallSessionResponse)
def save_recall_answer(
    recall_id: str,
    payload: RecallAnswerRequest,
    owner_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    recall = get_owned_recall(db, recall_id, owner_id)
    if recall.status in {RECALL_STATUS_REVEALED, RECALL_STATUS_COMPLETED}:
        raise HTTPException(status_code=409, detail="원본 공개 이후에는 회상 전 답변을 수정할 수 없습니다.")

    initial = payload.initial_answer.strip() if payload.initial_answer else None
    hint = payload.hint_answer.strip() if payload.hint_answer else None
    if not initial and not hint and not payload.memory_not_recalled:
        raise HTTPException(
            status_code=400,
            detail="회상 답변을 입력하거나 단계별 힌트 흐름을 완료해주세요.",
        )

    if initial:
        recall.initial_answer = initial
    if hint:
        answers = list(recall.hint_answers or [])
        answers = [answer for answer in answers if answer.get("level") != payload.hint_level]
        answers.append({"level": payload.hint_level, "answer": hint, "answered_at": utcnow().isoformat()})
        recall.hint_answers = answers
    recall.hint_level = max(recall.hint_level, payload.hint_level)
    recall.memory_not_recalled = payload.memory_not_recalled
    if payload.finalize:
        recall.answered_at = utcnow()
        recall.status = RECALL_STATUS_ANSWERED
    else:
        recall.status = RECALL_STATUS_QUESTION_READY
    db.commit()
    db.refresh(recall)
    return recall_to_dict(recall)


@router.post("/{recall_id}/reveal", response_model=RevealResponse)
def reveal_original_memory(
    recall_id: str,
    request: Request,
    owner_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    recall = get_owned_recall(db, recall_id, owner_id)
    if recall.status == RECALL_STATUS_COMPLETED:
        raise HTTPException(status_code=409, detail="이미 완료된 회상 세션입니다.")
    if not recall.initial_answer and not recall.hint_answers and not recall.memory_not_recalled:
        raise HTTPException(status_code=409, detail="회상 답변을 먼저 저장해주세요.")

    memory = get_owned_memory(db, recall.memory_id, owner_id)
    recall.revealed_at = recall.revealed_at or utcnow()
    recall.status = RECALL_STATUS_REVEALED
    db.commit()
    image_url = str(request.url_for("get_memory_image", memory_id=memory.id)) if memory.image_path else None
    return {
        "recall_id": recall.id,
        "memory_id": memory.id,
        "original_photo_url": image_url,
        "original_comment": memory.comment,
        "memory_date": memory.memory_date,
        "place_label": memory.place_label,
        "place_tag": memory.place_tag,
        "suggested_place_tag": memory.suggested_place_tag,
        "title": (memory.analysis or {}).get("title"),
        "analysis": memory.analysis or {},
    }


@router.post("/{recall_id}/additional-memory", response_model=RecallSessionResponse)
def save_additional_memory(
    recall_id: str,
    payload: AdditionalMemoryRequest,
    owner_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    recall = get_owned_recall(db, recall_id, owner_id)
    if recall.status not in {RECALL_STATUS_REVEALED}:
        raise HTTPException(status_code=409, detail="원본을 공개한 뒤 새롭게 떠오른 기억을 저장할 수 있습니다.")
    recall.newly_recalled_text = payload.text.strip()
    db.commit()
    db.refresh(recall)
    return recall_to_dict(recall)


@router.post("/{recall_id}/complete", response_model=MemoryCardResponse)
def complete_recall(
    recall_id: str,
    payload: CompleteRecallRequest,
    request: Request,
    owner_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    ai: AIService = Depends(get_ai),
):
    recall = get_owned_recall(db, recall_id, owner_id)
    if recall.status == RECALL_STATUS_COMPLETED:
        existing_card = db.scalar(select(MemoryCard).where(MemoryCard.recall_id == recall.id))
        if existing_card:
            return card_to_dict(existing_card, request)
        raise HTTPException(status_code=409, detail="완료 상태지만 추억 카드를 찾을 수 없습니다.")
    if recall.status != RECALL_STATUS_REVEALED:
        raise HTTPException(status_code=409, detail="원본을 공개한 뒤 회상을 완료할 수 있습니다.")

    if payload.additional_memory is not None:
        recall.newly_recalled_text = payload.additional_memory.strip()

    memory = get_owned_memory(db, recall.memory_id, owner_id)
    completed_recalls = db.scalars(
        select(RecallSession)
        .where(
            RecallSession.memory_id == memory.id,
            RecallSession.owner_id == owner_id,
            RecallSession.status == RECALL_STATUS_COMPLETED,
        )
        .order_by(RecallSession.stage.asc())
    ).all()
    recall_history = [*completed_recalls, recall]
    initial_history = "\n".join(
        f"{item.stage}차 회상: {item.initial_answer.strip()}"
        for item in recall_history
        if item.initial_answer and item.initial_answer.strip()
    )
    hint_history = [
        {**answer, "recall_stage": item.stage}
        for item in recall_history
        for answer in (item.hint_answers or [])
        if str(answer.get("answer", "")).strip()
    ]
    newly_recalled_history = "\n".join(
        f"{item.stage}차 회상: {item.newly_recalled_text.strip()}"
        for item in recall_history
        if item.newly_recalled_text and item.newly_recalled_text.strip()
    )
    card_data = ai.create_memory_card(
        original_comment=memory.comment,
        memory_date=memory.memory_date.isoformat(),
        analysis=memory.analysis or {},
        initial_answer=initial_history,
        hint_answers=hint_history,
        newly_recalled_text=newly_recalled_history,
    )
    card = db.scalar(
        select(MemoryCard)
        .where(MemoryCard.memory_id == memory.id, MemoryCard.owner_id == owner_id)
        .order_by(MemoryCard.created_at.asc())
    )
    if card:
        card.recall = recall
        card.card_title = str(card_data.get("card_title") or "다시 이어진 기억")[:255]
        card.story = str(card_data.get("story") or "")
        card.reflection = str(card_data.get("reflection") or "")
        card.newly_recalled_details = list(card_data.get("newly_recalled_details") or [])
        card.updated_at = utcnow()
    else:
        card = MemoryCard(
            id=str(uuid.uuid4()),
            memory_id=memory.id,
            recall=recall,
            owner_id=owner_id,
            card_title=str(card_data.get("card_title") or "다시 이어진 기억")[:255],
            story=str(card_data.get("story") or ""),
            reflection=str(card_data.get("reflection") or ""),
            newly_recalled_details=list(card_data.get("newly_recalled_details") or []),
            archived=False,
            shared_to_town=False,
            place_tag=None,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
    recall.status = RECALL_STATUS_COMPLETED
    recall.completed_at = utcnow()

    if recall.stage == 1:
        memory.current_recall_stage = 2
        memory.status = MEMORY_STATUS_PROCESSED
    else:
        memory.recall_completed = True
        memory.status = MEMORY_STATUS_RECALLED
    memory.updated_at = utcnow()

    db.add(card)
    db.commit()
    db.refresh(card)
    return card_to_dict(card, request)
