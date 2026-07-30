from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.config import Settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def add_recall_days(base_time: datetime, days: int, settings: Settings) -> datetime:
    if settings.demo_mode:
        return base_time + timedelta(seconds=days * settings.demo_day_seconds)
    return base_time + timedelta(days=days)


def create_schedule(
    created_at: datetime,
    settings: Settings,
    first_days: int | None = None,
    second_days: int | None = None,
) -> tuple[datetime, datetime]:
    first = settings.first_recall_days if first_days is None else first_days
    second = settings.second_recall_days if second_days is None else second_days
    if first < 0 or second < 0:
        raise ValueError("회상 일정은 0일 이상이어야 합니다.")
    if second < first:
        raise ValueError("두 번째 회상 시점은 첫 번째 회상 시점보다 빠를 수 없습니다.")
    return (
        add_recall_days(created_at, first, settings),
        add_recall_days(created_at, second, settings),
    )


def ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def next_recall_at(memory) -> datetime | None:
    if memory.recall_completed:
        return None
    return memory.first_recall_at if memory.current_recall_stage == 1 else memory.second_recall_at
