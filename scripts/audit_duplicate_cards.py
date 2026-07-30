"""기억당 카드가 여러 장인 레거시 데이터를 점검하고 안전한 중복만 선택적으로 정리한다."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select

from app.config import Settings
from app.database import build_engine, build_session_factory
from app.models import MemoryCard, TownContribution


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fix", action="store_true", help="동네 공유 이력이 없는 오래된 중복 카드만 삭제")
    args = parser.parse_args()
    settings = Settings()
    session_factory = build_session_factory(build_engine(settings))
    with session_factory() as db:
        duplicate_memory_ids = db.scalars(
            select(MemoryCard.memory_id)
            .group_by(MemoryCard.memory_id)
            .having(func.count(MemoryCard.id) > 1)
        ).all()
        if not duplicate_memory_ids:
            print("중복 추억 카드가 없습니다.")
            return
        removed = 0
        protected = 0
        for memory_id in duplicate_memory_ids:
            cards = db.scalars(
                select(MemoryCard)
                .where(MemoryCard.memory_id == memory_id)
                .order_by(MemoryCard.updated_at.desc())
            ).all()
            print(f"{memory_id}: {len(cards)}장 (최신 카드 {cards[0].id} 유지 권장)")
            if not args.fix:
                continue
            for card in cards[1:]:
                has_contribution = db.scalar(
                    select(func.count(TownContribution.id)).where(TownContribution.card_id == card.id)
                )
                if card.shared_to_town or has_contribution:
                    protected += 1
                    print(f"  - {card.id}: 동네 공유 이력이 있어 자동 삭제하지 않음")
                    continue
                db.delete(card)
                removed += 1
        if args.fix:
            db.commit()
            print(f"정리 완료: {removed}장 삭제, 공유 이력 {protected}장 보존")
        else:
            print("점검만 완료했습니다. 안전한 중복을 정리하려면 --fix를 추가하세요.")


if __name__ == "__main__":
    main()
