# 검증 기록

## 자동 테스트

```bash
python -m pytest
```

```text
41 passed
```

`tests/` 아래 9개 파일로 구성되며, 검증 항목:

- **test_memories.py**: 사진 없는 기억 등록, Swagger가 `image=""`를 보내는 요청, 이미지 저장·소유자 확인 후 조회, 사진 없이 OCR을 선택한 요청 차단, `place_tag` 저장 및 허용 목록 검증
- **test_recall_flow.py**: 기억 등록 → 분석 → 회상 → 원본 공개 → 추가 회상 → 추억 카드로 이어지는 전체 흐름, 사용자별 데이터 격리
- **test_archive.py**: 동네 카드의 서로 다른 기여자 3명 조건, 카드를 다른 장소로 재공유할 때 옛 장소 조각 정리, 같은 사용자의 같은 장소 중복 공유 시 `replace_existing` 명시적 교체 확인, 3명이 모이는 순간 관리자 개입 없이 동네 카드가 자동 생성되는 흐름
- **test_community.py**: 동네 카드 Solar 입력에서 원본 코멘트 제외, 공유 비식별화 로직
- **test_card_images.py**: 사진 없는 카드의 AI 이미지 생성, 사진 있는 카드는 생성 버튼 자체가 없음
- **test_deletion.py**: 개인 기억 삭제 시 발행 전 조각은 완전 삭제, 이미 발행된 조각은 비식별 보존 테이블로 이동
- **test_admin.py / test_demo_ui.py**: 관리자 인증 흐름, 모듈형 데모 UI와 정적 자원 제공
- **test_upstage_contract.py**: Information Extract의 JSON 요청, JSON Schema, PNG data URL 계약

## 실행 검증

- `python -m compileall app scripts tests`: 통과
- ES module 7개 문법 검사: 통과
- 로컬 Uvicorn 서버 HTTP smoke test: 통과
- `scripts/seed.py` 광안리 기여자 4명 생성: 통과

## 외부 서비스 검증 범위

자동 테스트는 격리된 SQLite·mock AI·로컬 Storage 환경에서 수행합니다. 실제 계정 연결은 `.env`에서 `AI_MODE=upstage`, `STORAGE_BACKEND=supabase`, Supabase `DATABASE_URL`을 설정한 뒤 통합 테스트해야 합니다.

배포 ZIP에서는 `.env`, `venv/`, 캐시, 로컬 DB, 로컬 업로드 이미지를 제외했습니다.
