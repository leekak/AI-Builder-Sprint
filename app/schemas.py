from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    environment: str
    ai_mode: str
    storage_backend: str
    demo_mode: bool
    time: datetime


class RecallScheduleResponse(BaseModel):
    first_recall_at: datetime
    second_recall_at: datetime
    current_stage: int
    completed: bool
    next_recall_at: datetime | None


class MemoryResponse(BaseModel):
    id: str
    comment: str
    memory_date: date
    place_label: str | None
    original_filename: str | None
    image_url: str | None
    use_ocr: bool
    recall_schedule: RecallScheduleResponse
    ocr_status: str
    ocr_text: str | None
    extraction_status: str
    extracted_context: dict[str, Any]
    analysis_status: str
    analysis: dict[str, Any]
    place_tag: str | None
    suggested_place_tag: str | None
    share_to_town: bool
    status: str
    created_at: datetime
    updated_at: datetime


class MemoryProcessResponse(BaseModel):
    memory: MemoryResponse
    steps: list[dict[str, Any]]


class MemoryDeleteResponse(BaseModel):
    memory_id: str
    deleted_photo: bool
    removed_recalls: int
    removed_cards: int
    removed_pending_contributions: int
    preserved_anonymous_fragments: int
    message: str


class PlaceTagConfirmRequest(BaseModel):
    place_tag: str | None = None


class DueRecallResponse(BaseModel):
    memory_id: str
    memory_date: date
    day_sequence: int
    same_day_count: int
    place_tag: str | None
    cue_categories: list[str]
    stage: int
    due_at: datetime
    status: str
    prompt: str = "이 기억을 원본 없이 먼저 떠올려보세요."


class RecallCreateRequest(BaseModel):
    memory_id: str


class RecallSessionResponse(BaseModel):
    id: str
    memory_id: str
    stage: int
    status: str
    questions: list[dict[str, Any]]
    initial_answer: str | None
    hint_answers: list[dict[str, Any]]
    hint_level: int
    memory_not_recalled: bool
    newly_recalled_text: str | None
    started_at: datetime
    answered_at: datetime | None
    revealed_at: datetime | None
    completed_at: datetime | None


class RecallQuestionsResponse(BaseModel):
    recall_id: str
    questions: list[dict[str, Any]]


class RecallAnswerRequest(BaseModel):
    initial_answer: str | None = None
    hint_answer: str | None = None
    hint_level: int = Field(default=0, ge=0, le=10)
    memory_not_recalled: bool = False
    finalize: bool = True


class AdditionalMemoryRequest(BaseModel):
    text: str = ""


class RevealResponse(BaseModel):
    recall_id: str
    memory_id: str
    original_photo_url: str | None
    original_comment: str
    memory_date: date
    place_label: str | None
    place_tag: str | None
    suggested_place_tag: str | None
    title: str | None
    analysis: dict[str, Any]


class CompleteRecallRequest(BaseModel):
    additional_memory: str | None = None


class MemoryCardResponse(BaseModel):
    id: str
    memory_id: str
    recall_id: str
    card_title: str
    story: str
    reflection: str
    newly_recalled_details: list[str]
    memory_date: date
    place_label: str | None
    image_url: str | None
    generated_image_url: str | None
    image_generation_status: str
    image_generation_mode: str | None
    image_generation_style: str | None
    image_generated_at: datetime | None
    initial_recall: str | None
    newly_recalled_text: str | None
    recall_history: list[dict[str, Any]]
    archived: bool
    shared_to_town: bool
    town_share_status: str
    place_tag: str | None
    latest_recall_added_count: int
    created_at: datetime
    updated_at: datetime


class ArchiveCardRequest(BaseModel):
    archived: bool = True


class CardImageGenerateRequest(BaseModel):
    mode: Literal["text_illustration"] = "text_illustration"


class CardImageResponse(BaseModel):
    card_id: str
    status: str
    mode: str | None
    style: str | None
    generated_image_url: str | None
    ai_generated: bool = True


class ShareToTownRequest(BaseModel):
    consent: bool
    place_tag: str | None = None
    preview_token: str | None = None
    replace_existing: bool = False


class TownSharePreviewRequest(BaseModel):
    place_tag: str


class TownSharePreviewResponse(BaseModel):
    card_id: str
    place_tag: str
    safe_pre_text: str
    safe_post_text: str
    safe_summary_text: str
    preview_token: str
    conflicting_card_id: str | None = None
    conflicting_card_title: str | None = None


class TownShareResponse(BaseModel):
    card_id: str
    consent: bool
    place_tag: str | None
    contribution_id: str | None


class TownCardResponse(BaseModel):
    id: str
    place: str
    contributors: int
    card_title: str
    story: str
    reflection: str
    version: int
    deleted_at: datetime | None = None
    deleted_by: str | None = None
    created_at: datetime
    updated_at: datetime


class TownContributionAdminResponse(BaseModel):
    """관리자 전용: 익명 처리된 회상 조각 목록 (작성자 식별 정보는 포함하지 않는다)."""

    id: str
    place_tag: str
    pre_reveal_text: str
    post_reveal_text: str
    created_at: datetime


class TownPlaceStatusResponse(BaseModel):
    place_tag: str
    distinct_contributors: int
    total_fragments: int
    minimum_required: int
    new_contributors: int
    can_generate: bool
    has_new_contributions: bool
    privacy_review_required: bool
    latest_card_id: str | None


class PlaceTagsResponse(BaseModel):
    place_tags: list[str]


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class AdminSessionResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    expires_at: datetime
