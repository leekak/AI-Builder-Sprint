# 검증 기록

## 자동 테스트

```text
.............                                                            [100%]
13 passed
```

검증 항목:

- 사진 없는 기억 등록
- Swagger가 `image=""`를 보내는 요청
- 이미지 저장 및 소유자 확인 후 조회
- 사진 없이 OCR을 선택한 요청 차단
- 기억 등록 → 분석 → 회상 → 원본 공개 → 추가 회상 → 추억 카드
- 사용자별 데이터 격리
- 동네 카드의 서로 다른 기여자 3명 조건
- 동네 카드 Solar 입력에서 원본 코멘트 제외
- Information Extract의 JSON 요청, JSON Schema, PNG data URL 계약
- 기억 등록 `place_tag` 저장 및 허용 목록 검증
- 모듈형 데모 UI와 정적 자원 제공

## 실행 검증

- `python -m compileall app scripts tests`: 통과
- ES module 7개 문법 검사: 통과
- 로컬 Uvicorn 서버 HTTP smoke test: 통과
- `scripts/seed.py` 광안리 기여자 4명 생성: 통과

## 외부 서비스 검증 범위

자동 테스트는 격리된 SQLite·mock AI·로컬 Storage 환경에서 수행합니다. 실제 계정 연결은 `.env`에서 `AI_MODE=upstage`, `STORAGE_BACKEND=supabase`, Supabase `DATABASE_URL`을 설정한 뒤 통합 테스트해야 합니다.

배포 ZIP에서는 `.env`, `.venv`, 캐시, 로컬 DB, 로컬 업로드 이미지를 제외했습니다.
