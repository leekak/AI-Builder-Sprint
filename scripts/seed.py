from __future__ import annotations

import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models import Memory, MemoryCard, RecallSession, TownContribution, utcnow


SEEDS = [
    {
        "owner": "seed-user-1",
        "pre": "친구와 바다 근처를 걸었던 기억이 난다.",
        "post": "비가 갑자기 내려 우산 하나를 나눠 쓰며 민락 쪽으로 걸었다.",
        "title": "우산 하나를 나눠 쓴 광안리",
    },
    {
        "owner": "seed-user-2",
        "pre": "누군가와 약속을 기다리며 파도 소리를 들었던 것 같다.",
        "post": "첫 데이트 날 약속보다 일찍 도착해 바닷가 벤치에 앉아 있었다.",
        "title": "약속보다 일찍 도착한 바다",
    },
    {
        "owner": "seed-user-3",
        "pre": "가족과 밤에 사진을 찍었던 장면이 흐릿하게 떠오른다.",
        "post": "아버지가 삼각대를 세우고 광안대교가 켜질 때까지 기다렸다.",
        "title": "불이 켜지기를 기다리던 밤",
    },
    {
        "owner": "seed-user-4",
        "pre": "학교가 끝난 뒤 친구들과 모였던 장소였던 것 같다.",
        "post": "시험이 끝난 날 편의점 음료를 들고 모래사장에 오래 앉아 있었다.",
        "title": "시험이 끝난 날의 모래사장",
    },
]


def main() -> None:
    with TestClient(app):
        db = app.state.SessionLocal()
        try:
            created = 0
            for item in SEEDS:
                exists = db.scalar(
                    select(TownContribution).where(
                        TownContribution.owner_id == item["owner"],
                        TownContribution.place_tag == "광안리",
                    )
                )
                if exists:
                    continue

                now = utcnow()
                memory_id = str(uuid.uuid4())
                recall_id = str(uuid.uuid4())
                card_id = str(uuid.uuid4())

                memory = Memory(
                    id=memory_id,
                    owner_id=item["owner"],
                    comment="시드 데이터 원본 코멘트 — 동네 카드 입력에는 포함되지 않습니다.",
                    memory_date=now.date(),
                    image_path=None,
                    image_filename=None,
                    image_content_type=None,
                    use_ocr=False,
                    ocr_status="skipped",
                    ocr_text=None,
                    extraction_status="completed",
                    extracted_context={"people": [], "places": ["광안리"], "activities": [], "atmosphere": [], "emotions": []},
                    analysis_status="completed",
                    analysis={"title": item["title"], "summary": "", "emotions": [], "recall_cues": []},
                    first_recall_at=now,
                    second_recall_at=now,
                    current_recall_stage=2,
                    recall_completed=False,
                    place_tag="광안리",
                    share_to_town=True,
                    status="processed",
                    created_at=now,
                    updated_at=now,
                )
                recall = RecallSession(
                    id=recall_id,
                    memory_id=memory_id,
                    owner_id=item["owner"],
                    stage=1,
                    status="completed",
                    questions=[],
                    initial_answer=item["pre"],
                    hint_answers=[],
                    hint_level=0,
                    memory_not_recalled=False,
                    newly_recalled_text=item["post"],
                    started_at=now,
                    answered_at=now,
                    revealed_at=now,
                    completed_at=now,
                )
                card = MemoryCard(
                    id=card_id,
                    memory_id=memory_id,
                    recall_id=recall_id,
                    owner_id=item["owner"],
                    card_title=item["title"],
                    story=f"{item['pre']} {item['post']}",
                    reflection="각자의 기억 조각을 있는 그대로 남겼어요.",
                    newly_recalled_details=[item["post"]],
                    archived=False,
                    shared_to_town=True,
                    place_tag="광안리",
                    created_at=now,
                    updated_at=now,
                )
                contribution = TownContribution(
                    id=str(uuid.uuid4()),
                    card_id=card_id,
                    memory_id=memory_id,
                    recall_id=recall_id,
                    owner_id=item["owner"],
                    place_tag="광안리",
                    pre_reveal_text=item["pre"],
                    post_reveal_text=item["post"],
                    created_at=now,
                )
                db.add_all([memory, recall, card, contribution])
                created += 1
            db.commit()
            print(f"완료: 광안리 동네 추억 시드 {created}건 추가")
            print("POST /archive/places/광안리/card 로 공동체 카드를 생성할 수 있습니다.")
        finally:
            db.close()


if __name__ == "__main__":
    main()
