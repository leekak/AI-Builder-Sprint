from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Memory, MemoryCard, RecallSession


def get_owned_memory(db: Session, memory_id: str, owner_id: str) -> Memory:
    memory = db.scalar(select(Memory).where(Memory.id == memory_id, Memory.owner_id == owner_id))
    if not memory:
        raise HTTPException(status_code=404, detail="해당 기억을 찾을 수 없습니다.")
    return memory


def get_owned_recall(db: Session, recall_id: str, owner_id: str) -> RecallSession:
    recall = db.scalar(select(RecallSession).where(RecallSession.id == recall_id, RecallSession.owner_id == owner_id))
    if not recall:
        raise HTTPException(status_code=404, detail="해당 회상 세션을 찾을 수 없습니다.")
    return recall


def get_owned_card(db: Session, card_id: str, owner_id: str) -> MemoryCard:
    card = db.scalar(select(MemoryCard).where(MemoryCard.id == card_id, MemoryCard.owner_id == owner_id))
    if not card:
        raise HTTPException(status_code=404, detail="해당 추억 카드를 찾을 수 없습니다.")
    return card
