from __future__ import annotations

import re

from fastapi import Request

from app.models import Memory, MemoryCard, RecallSession, TownCard
from app.services.scheduling import next_recall_at


def memory_image_url(memory: Memory, request: Request) -> str | None:
    if not memory.image_path:
        return None
    return str(request.url_for("get_memory_image", memory_id=memory.id))


def memory_to_dict(memory: Memory, request: Request) -> dict:
    return {
        "id": memory.id,
        "comment": memory.comment,
        "memory_date": memory.memory_date,
        "place_label": memory.place_label,
        "original_filename": memory.image_filename,
        "image_url": memory_image_url(memory, request),
        "use_ocr": memory.use_ocr,
        "recall_schedule": {
            "first_recall_at": memory.first_recall_at,
            "second_recall_at": memory.second_recall_at,
            "current_stage": memory.current_recall_stage,
            "completed": memory.recall_completed,
            "next_recall_at": next_recall_at(memory),
        },
        "ocr_status": memory.ocr_status,
        "ocr_text": memory.ocr_text,
        "extraction_status": memory.extraction_status,
        "extracted_context": memory.extracted_context or {},
        "analysis_status": memory.analysis_status,
        "analysis": memory.analysis or {},
        "place_tag": memory.place_tag,
        "suggested_place_tag": memory.suggested_place_tag,
        "share_to_town": memory.share_to_town,
        "status": memory.status,
        "created_at": memory.created_at,
        "updated_at": memory.updated_at,
    }


def recall_to_dict(recall: RecallSession) -> dict:
    return {
        "id": recall.id,
        "memory_id": recall.memory_id,
        "stage": recall.stage,
        "status": recall.status,
        "questions": recall.questions or [],
        "initial_answer": recall.initial_answer,
        "hint_answers": recall.hint_answers or [],
        "hint_level": recall.hint_level,
        "memory_not_recalled": recall.memory_not_recalled,
        "newly_recalled_text": recall.newly_recalled_text,
        "started_at": recall.started_at,
        "answered_at": recall.answered_at,
        "revealed_at": recall.revealed_at,
        "completed_at": recall.completed_at,
    }


def card_to_dict(card: MemoryCard, request: Request, *, town_share_status: str = "not_shared") -> dict:
    memory = card.memory
    recall = card.recall
    recall_history = [
        {
            "stage": item.stage,
            "initial_answer": item.initial_answer,
            "newly_recalled_text": item.newly_recalled_text,
            "completed_at": item.completed_at,
        }
        for item in sorted(memory.recalls, key=lambda item: item.stage)
        if item.completed_at is not None
    ]
    latest_added_count = len([
        piece for piece in re.split(r"[.!?\n]+", recall.newly_recalled_text or "") if piece.strip()
    ])
    return {
        "id": card.id,
        "memory_id": card.memory_id,
        "recall_id": card.recall_id,
        "card_title": card.card_title,
        "story": card.story,
        "reflection": card.reflection,
        "newly_recalled_details": card.newly_recalled_details or [],
        "memory_date": memory.memory_date,
        "place_label": memory.place_label,
        "image_url": memory_image_url(memory, request),
        "generated_image_url": (
            str(request.url_for("get_generated_card_image", card_id=card.id))
            if card.generated_image_path else None
        ),
        "image_generation_status": card.image_generation_status or "not_requested",
        "image_generation_mode": card.image_generation_mode,
        "image_generation_style": card.image_generation_style,
        "image_generated_at": card.image_generated_at,
        "initial_recall": recall.initial_answer,
        "newly_recalled_text": recall.newly_recalled_text,
        "recall_history": recall_history,
        "archived": card.archived,
        "shared_to_town": card.shared_to_town,
        "town_share_status": town_share_status,
        "place_tag": card.place_tag,
        "latest_recall_added_count": latest_added_count,
        "created_at": card.created_at,
        "updated_at": card.updated_at,
    }


def town_card_to_dict(card: TownCard) -> dict:
    return {
        "id": card.id,
        "place": card.place_tag,
        "contributors": card.contributors,
        "card_title": card.card_title,
        "story": card.story,
        "reflection": card.reflection,
        "version": card.version,
        "deleted_at": card.deleted_at,
        "deleted_by": card.deleted_by,
        "created_at": card.created_at,
        "updated_at": card.updated_at,
    }
