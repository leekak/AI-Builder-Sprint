# 검증 기록

## 자동 테스트

```bash
python -m pytest
```

```text
48 passed, 1 warning
```

2026년 8월 3일 Python 3.12 환경에서 실행한 최종 결과입니다. 경고 1건은 Starlette TestClient의 향후 httpx2 전환 안내이며 기능 실패가 아닙니다.

`tests/` 아래 10개 파일로 구성되며, 검증 항목:

- **test_memories.py**: 사진 없는 기억 등록, Swagger가 `image=""`를 보내는 요청, 이미지 저장·소유자 확인 후 조회, 사진 없이 OCR을 선택한 요청 차단, `place_tag` 저장 및 허용 목록 검증
- **test_recall_flow.py**: 기억 등록 → 분석 → 회상 → 원본 공개 → 추가 회상 → 추억 카드로 이어지는 전체 흐름, 사용자별 데이터 격리
- **test_archive.py**: 동네 카드의 서로 다른 기여자 3명 조건, 카드를 다른 장소로 재공유할 때 옛 장소 조각 정리, 같은 사용자의 같은 장소 중복 공유 시 `replace_existing` 명시적 교체 확인, 3명이 모이는 순간 관리자 개입 없이 동네 카드가 자동 생성되는 흐름
- **test_community.py**: 동네 카드 Solar 입력에서 원본 코멘트 제외, 공유 비식별화 로직
- **test_card_images.py**: 사진 없는 카드의 AI 이미지 생성, 사진 있는 카드는 생성 버튼 자체가 없음
- **test_deletion.py**: 개인 기억 삭제 시 발행 전 조각은 완전 삭제, 이미 발행된 조각은 비식별 보존 테이블로 이동
- **test_admin.py / test_demo_ui.py**: 관리자 인증 흐름, 모듈형 데모 UI와 정적 자원 제공
- **test_database.py**: SQLite·PostgreSQL 연결 설정과 Pooler 호환성 검증
- **test_upstage_contract.py**: Information Extract의 JSON 요청, JSON Schema, PNG data URL 계약

## 실행 검증

- `python -m compileall app scripts tests`: 통과
- 전체 프런트엔드 모듈 로딩 및 정적 자원 제공 검증: 통과
- 로컬 Uvicorn 서버 HTTP smoke test: 통과
- `scripts/seed.py` 광안리 기여자 4명 생성: 통과

## 외부 서비스 검증 범위

자동 테스트는 재현성을 위해 격리된 SQLite·mock AI·로컬 Storage 환경에서 수행합니다.

2026년 8월 3일 Railway 평가 배포에서는 `AI_MODE=upstage`, `AI_FALLBACK_TO_MOCK=false`, Supabase PostgreSQL·비공개 Storage, Gemini 이미지 생성을 실제로 연결해 다음 항목을 통합 검증했습니다.

- 비로그인 개인 API `401` 차단과 공개 동네 아카이브 조회
- 사진·코멘트 기억 등록과 Supabase 이미지 저장·조회
- Document Parse OCR, Information Extract 구조화, Solar 기억 분석·회상 질문·추억 카드 생성
- 1·2차 회상 이력 통합과 기억 하나당 카드 하나 유지
- 익명 공유 미리보기·비식별화·opt-in 공유·공유 취소
- 사진 없는 카드의 Gemini 이미지 생성·조회·삭제
- 관리자 로그인·JWT 권한 검증과 삭제 카드 목록 조회
- 테스트 중 생성한 개인 기억·회상·카드 최종 정리

공개 동네 카드에 영향을 주는 관리자 삭제·복구와 서로 다른 사용자 3명의 자동 생성 정책은 운영 데이터 훼손을 피하기 위해 실제 배포에서 강제로 실행하지 않고 `test_admin.py`, `test_archive.py`, `test_community.py`, `test_deletion.py`로 검증했습니다.

배포 ZIP에서는 `.env`, `venv/`, 캐시, 로컬 DB, 로컬 업로드 이미지를 제외했습니다.
