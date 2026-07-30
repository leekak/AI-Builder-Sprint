from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Memory(Base):
    __tablename__ = "memories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(128), index=True)

    comment: Mapped[str] = mapped_column(Text)
    memory_date: Mapped[date] = mapped_column(Date)
    place_label: Mapped[str | None] = mapped_column(String(255), nullable=True)

    image_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    image_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    image_content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    use_ocr: Mapped[bool] = mapped_column(Boolean, default=False)

    ocr_status: Mapped[str] = mapped_column(String(32), default="pending")
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    extraction_status: Mapped[str] = mapped_column(String(32), default="pending")
    extracted_context: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    extraction_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    analysis_status: Mapped[str] = mapped_column(String(32), default="pending")
    analysis: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    analysis_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    first_recall_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    second_recall_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    current_recall_stage: Mapped[int] = mapped_column(Integer, default=1)
    recall_completed: Mapped[bool] = mapped_column(Boolean, default=False)

    place_tag: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    suggested_place_tag: Mapped[str | None] = mapped_column(String(100), nullable=True)
    share_to_town: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(32), default="registered", index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    recalls: Mapped[list["RecallSession"]] = relationship(back_populates="memory", cascade="all, delete-orphan")
    cards: Mapped[list["MemoryCard"]] = relationship(back_populates="memory", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_memories_owner_due_stage", "owner_id", "current_recall_stage", "recall_completed"),
    )


class RecallSession(Base):
    __tablename__ = "recall_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    memory_id: Mapped[str] = mapped_column(ForeignKey("memories.id", ondelete="CASCADE"), index=True)
    owner_id: Mapped[str] = mapped_column(String(128), index=True)
    stage: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="created", index=True)

    questions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    initial_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    hint_answers: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    hint_level: Mapped[int] = mapped_column(Integer, default=0)
    memory_not_recalled: Mapped[bool] = mapped_column(Boolean, default=False)
    newly_recalled_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revealed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    memory: Mapped[Memory] = relationship(back_populates="recalls")
    card: Mapped["MemoryCard | None"] = relationship(back_populates="recall", uselist=False)

    __table_args__ = (
        UniqueConstraint("memory_id", "stage", name="uq_recall_memory_stage"),
    )


class MemoryCard(Base):
    __tablename__ = "memory_cards"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    memory_id: Mapped[str] = mapped_column(ForeignKey("memories.id", ondelete="CASCADE"), index=True)
    recall_id: Mapped[str] = mapped_column(ForeignKey("recall_sessions.id", ondelete="CASCADE"), unique=True)
    owner_id: Mapped[str] = mapped_column(String(128), index=True)

    card_title: Mapped[str] = mapped_column(String(255))
    story: Mapped[str] = mapped_column(Text)
    reflection: Mapped[str] = mapped_column(Text)
    newly_recalled_details: Mapped[list[str]] = mapped_column(JSON, default=list)

    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    shared_to_town: Mapped[bool] = mapped_column(Boolean, default=False)
    place_tag: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    generated_image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    generated_image_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    generated_image_content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    image_generation_status: Mapped[str] = mapped_column(String(30), default="not_requested")
    image_generation_mode: Mapped[str | None] = mapped_column(String(40), nullable=True)
    image_generation_style: Mapped[str | None] = mapped_column(String(60), nullable=True)
    image_generation_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    memory: Mapped[Memory] = relationship(back_populates="cards")
    recall: Mapped[RecallSession] = relationship(back_populates="card")
    contribution: Mapped["TownContribution | None"] = relationship(
        back_populates="card", cascade="all, delete-orphan", uselist=False
    )


class TownContribution(Base):
    __tablename__ = "town_contributions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    card_id: Mapped[str] = mapped_column(ForeignKey("memory_cards.id", ondelete="CASCADE"), unique=True)
    memory_id: Mapped[str] = mapped_column(ForeignKey("memories.id", ondelete="CASCADE"), index=True)
    recall_id: Mapped[str] = mapped_column(ForeignKey("recall_sessions.id", ondelete="CASCADE"), index=True)
    owner_id: Mapped[str] = mapped_column(String(128), index=True)
    contributor_key: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    place_tag: Mapped[str] = mapped_column(String(100), index=True)

    pre_reveal_text: Mapped[str] = mapped_column(Text)
    post_reveal_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    card: Mapped[MemoryCard] = relationship(back_populates="contribution")


class TownArchivedFragment(Base):
    """공동체 카드에 반영된 뒤 사용자 연결을 제거해 보존하는 비식별 조각."""

    __tablename__ = "town_archived_fragments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    place_tag: Mapped[str] = mapped_column(String(100), index=True)
    contributor_key: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    pre_reveal_text: Mapped[str] = mapped_column(Text)
    post_reveal_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TownCard(Base):
    __tablename__ = "town_cards"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    place_tag: Mapped[str] = mapped_column(String(100), index=True)
    contributors: Mapped[int] = mapped_column(Integer)
    card_title: Mapped[str] = mapped_column(String(255))
    story: Mapped[str] = mapped_column(Text)
    reflection: Mapped[str] = mapped_column(Text)
    source_contribution_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    published_contributor_keys: Mapped[list[str]] = mapped_column(JSON, default=list)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
