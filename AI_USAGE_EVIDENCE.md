# AI 활용 증빙

## 1. 제출 요약

`다시, 그날`은 AI가 사용자의 기억을 대신 만들거나 정확도를 채점하는 서비스가 아니다. 사용자가 원본 사진을 보기 전에 먼저 기억을 떠올리도록 돕고, 원본 공개 후 새롭게 떠오른 내용을 연결해 하나의 추억 카드로 완성한다.

핵심 흐름에서 Upstage API 3종을 다음과 같이 사용한다.

| 기술 | 모델·엔드포인트 | 실제 역할 | 코드 위치 |
|---|---|---|---|
| Solar LLM | `solar-pro3`, `/v1/chat/completions` | 기억 제목·요약·회상 단서, 단계별 질문, 개인 추억 카드, 익명 공유 비식별화, 동네 추억 카드 생성 | `app/services/ai.py`의 `analyze_memory()`, `generate_questions()`, `create_memory_card()`, `sanitize_town_contribution()`, `create_town_card()` |
| Document Parse | `document-parse`, `/v1/document-digitization` | 티켓·영수증·메모 등 사진 속 텍스트 추출 | `app/services/ai.py`의 `parse_document()`, `app/api/memories.py`의 `run_parse()` |
| Information Extract | `information-extract`, `/v1/information-extraction` | 코멘트와 OCR 결과에서 사람·장소·활동·분위기·감정을 JSON으로 구조화 | `app/services/ai.py`의 `extract_context()`, `app/api/memories.py`의 `run_extract()` |

보조 AI로 Gemini Nano Banana(`gemini-3.1-flash-image`)를 사용한다. 사진이 없는 개인 추억 카드에만 기록 기반 일러스트를 생성하며, Upstage API 가점 증빙과는 별도로 구분한다.

---

## 2. 전체 AI 처리 흐름

```text
사진 0~1장 + 코멘트 + 기억 날짜
    ↓
[조건부] Document Parse
사진 속 글자가 있는 경우에만 OCR
    ↓
Information Extract
people / places / activities / atmosphere / emotions 구조화
    ↓
Solar LLM
제목 / 사실 기반 요약 / 회상 단서 생성
    ↓
회상 예정일 도래
    ↓
Solar LLM
원본을 노출하지 않는 개방형 질문과 단계별 힌트 생성
    ↓
사용자 회상 → 원본 공개 → 새 기억 추가
    ↓
Solar LLM
원본과 원본 공개 후 기억만 사용해 개인 추억 카드 생성
    ↓
[사용자 명시적 동의]
Solar LLM 비식별화 → 익명 공유 미리보기
    ↓
[서로 다른 3명 이상]
Solar LLM이 공통 지역 생활 장면을 동네 추억 카드로 재구성
```

AI가 담당하지 않는 영역도 명확히 분리했다.

- 회상 예정일 계산: FastAPI 규칙 기반 로직
- 사용자·관리자 권한: 애플리케이션 인증 로직
- 최소 기여자 3명 판정: DB 및 서버 로직
- 원본 공개 순서와 상태 전환: FastAPI 상태 머신
- 비속어 2차 차단과 API 장애 fallback: 로컬 안전장치
- DB 및 이미지 저장: Supabase Database·Storage

---

## 3. API별 사용 위치와 산출물

### 3.1 Document Parse

#### 호출 조건

사용자가 사진을 첨부하고 “사진 속 글자도 기억에 활용”을 선택한 경우에만 호출한다. 일반 풍경·인물 사진은 불필요한 OCR 호출을 하지 않는다.

#### 처리 대상

- 영화·공연 티켓
- 영수증·메뉴판
- 여행 일정표
- 손편지·손글씨 메모

#### 요청 위치

```text
POST /memories/{memory_id}/parse
```

#### 출력 예시

```json
{
  "ocr_status": "completed",
  "ocr_text": "2026 부산 바다축제 / 광안리 / 19:00"
}
```

추출한 텍스트는 단독으로 공개하지 않고, 사용자 코멘트와 함께 Information Extract 입력으로 사용한다.

### 3.2 Information Extract

#### 역할

사실 기반 정보 추출과 창작 텍스트 생성을 분리한다. Information Extract는 원문에 존재하는 필드만 구조화하며 제목이나 이야기를 만들지 않는다.

#### 요청 위치

```text
POST /memories/{memory_id}/extract
```

통합 처리에서는 다음 요청으로 OCR·추출·분석을 순서대로 실행한다.

```text
POST /memories/{memory_id}/process
```

#### JSON Schema

```json
{
  "people": ["진우"],
  "places": ["광안리"],
  "activities": ["산책"],
  "atmosphere": ["비 오는 날", "바다"],
  "emotions": []
}
```

#### 활용

- 기억 맥락 구조화
- 표준 장소 태그 제안
- Solar 회상 질문의 사실 기반 입력
- 원문에 없는 정보 생성을 줄이는 근거 데이터

### 3.3 Solar LLM

Solar는 다음 여섯 단계에서 핵심적으로 사용한다.

| 단계 | 입력 | 출력 |
|---|---|---|
| 기억 분석 | 원문 + Information Extract JSON | 제목, 요약, 감정, 회상 단서 |
| 회상 질문 | 구조화 맥락 + 분석 결과 | 1~3단계 질문·힌트 |
| 개인 추억 카드 | 원본 코멘트 + 원본 공개 후 추가 기억 | 카드 제목, 이야기, 마무리 문구 |
| 익명 공유 | 개인 회상 조각 | 비식별화된 공개 조각, 제거 표현 목록 |
| 공유 미리보기 | 비식별화 완료 조각 | 사용자가 확인할 공개 요약 |
| 동네 추억 카드 | 서로 다른 참여자의 안전한 조각 | 공통 지역 이야기와 공동체적 의미 |

---

## 4. 핵심 프롬프트와 안전 지침

실제 전체 프롬프트는 `app/services/ai.py`에 있으며 아래는 핵심 지침을 요약한 것이다.

### 4.1 기억 분석

```text
기억을 채점하지 말고, 원문에 없는 사건·감정·인물을 만들지 마세요.
제목, 사실만 사용한 한 문장 요약, 명시된 감정, 정답을 직접 말하지 않는 회상 단서를 JSON으로 반환하세요.
```

### 4.2 단계별 회상 질문

```text
원본 사진과 코멘트를 보기 전에 기억을 자유롭게 떠올리도록 도우세요.
level 1은 넓은 개방형 질문,
level 2는 감각·분위기 중심의 약한 힌트,
level 3은 활동·장소 범주의 구체적인 힌트로 작성하세요.
사람 이름·가게명·음식명처럼 정답이 되는 정보는 직접 밝히지 마세요.
```

출력 예시:

```json
{
  "questions": [
    {"level": 1, "question": "그날 어떤 시간을 보냈는지 천천히 떠올려보세요."},
    {"level": 2, "question": "주변의 날씨나 소리, 분위기는 어땠나요?"},
    {"level": 3, "question": "누군가와 걷거나 식사했던 장면이 있었나요?"}
  ]
}
```

### 4.3 개인 추억 카드

```text
회상 정확도를 평가하거나 정답률을 언급하지 마세요.
원본 코멘트와 원본 공개 후 새롭게 떠오른 내용에 없는 사건을 추가하지 마세요.
원본 공개 전 답변은 추측일 수 있으므로 카드 이야기의 사실 근거로 사용하지 않습니다.
```

### 4.4 익명 동네 공유

```text
이름·별명·소속·학교·단체·모임명·정확한 시간·이동 경로를 제거하세요.
영화명·가게명·메뉴명·희귀 사건은 문화 활동·식사·산책처럼 일반화하세요.
골목·계단·평상·화분·생활 소리처럼 개인을 특정하지 않는 지역 생활 정보는 유지하세요.
비속어·욕설·혐오 표현은 삭제하거나 중립화하세요.
새로운 사실은 만들지 마세요.
```

추가 안전장치:

1. 사용자가 공유 전에 비식별화 결과를 직접 확인한다.
2. 서명된 미리보기 토큰이 있어야 최종 공유할 수 있다.
3. 원본 사진과 원본 코멘트 전체는 동네 아카이브에 전달하지 않는다.
4. 사용자 ID는 장소별 비가역 HMAC 키로 바꿔 동일 참여자 중복을 판정한다.
5. Upstage가 일시적으로 실패하면 원문 대신 제한된 범주형 문장으로 대체한다.
6. 서로 다른 사용자 3명 미만이면 동네 카드를 만들지 않는다.

---

## 5. 설정 증빙

API 키는 저장소에 포함하지 않으며 `.env`에서만 주입한다. 공개 가능한 설정 예시는 `.env.example`에 있다.

```env
AI_MODE=upstage
AI_FALLBACK_TO_MOCK=false
UPSTAGE_API_KEY=
UPSTAGE_BASE_URL=https://api.upstage.ai/v1
UPSTAGE_SOLAR_MODEL=solar-pro3
UPSTAGE_DOCUMENT_PARSE_URL=https://api.upstage.ai/v1/document-digitization
UPSTAGE_DOCUMENT_PARSE_MODEL=document-parse
UPSTAGE_INFORMATION_EXTRACT_URL=https://api.upstage.ai/v1/information-extraction
UPSTAGE_INFORMATION_EXTRACT_MODEL=information-extract
UPSTAGE_TIMEOUT_SECONDS=60
```

실제 API 호출을 증명할 때는 다음 설정을 사용한다.

```env
AI_MODE=upstage
AI_FALLBACK_TO_MOCK=false
```

이 설정은 Upstage 오류를 mock 응답으로 숨기지 않으므로 실제 연동 여부를 명확히 확인할 수 있다.

---

## 6. 테스트 및 검증 산출물

### 6.1 전체 자동 테스트

```bash
python -m pytest
```

2026년 8월 3일 최종 실행 결과:

```text
48 passed, 1 warning
```

경고 1건은 Starlette TestClient의 향후 httpx2 전환 안내이며 기능 실패가 아니다.

### 6.2 Upstage 요청 계약 테스트

```bash
python -m pytest tests/test_upstage_contract.py -v
```

검증 항목:

- Information Extract 요청 모델이 `information-extract`인지 확인
- `response_format.type`이 `json_schema`인지 확인
- 사람·장소·활동·분위기 JSON 필드 정규화 확인
- 텍스트 기억이 실제 PNG 문서 데이터 URL로 변환되는지 확인

테스트 코드: `tests/test_upstage_contract.py`

### 6.3 서비스 흐름 검증

```bash
python scripts/smoke_test.py
```

확인 범위:

- 기억 등록 및 처리
- 회상 질문 생성
- 답변 저장과 원본 공개
- 추가 기억 저장
- 개인 추억 카드 생성
- 익명 공유 및 동네 카드 생성

### 6.4 개인정보 보호 검증

관련 테스트:

```text
tests/test_community.py
tests/test_archive.py
```

검증 항목:

- 이름·영화명·구체적 메뉴가 공개 조각에서 제거되는지
- 비속어가 동네 카드에 포함되지 않는지
- Upstage 장애 시 원문 대신 안전한 fallback이 사용되는지
- 동일 사용자의 중복 기여로 3명 조건을 우회할 수 없는지
- 개인 카드를 삭제해도 이미 발행된 동네 카드가 영향을 받지 않는지

---

## 7. 심사용 실제 호출 재현 절차

1. `.env`에 실제 `UPSTAGE_API_KEY`를 입력한다.
2. `AI_MODE=upstage`, `AI_FALLBACK_TO_MOCK=false`로 설정한다.
3. 서버를 실행하고 `/health`에서 `ai_mode: upstage`를 확인한다.
4. 글자가 있는 티켓 또는 영수증 사진과 코멘트를 등록한다.
5. `POST /memories/{id}/process` 실행 후 DB에서 다음을 확인한다.
   - `ocr_status=completed`
   - `extraction_status=completed`
   - `analysis_status=completed`
   - `ocr_text`, `extracted_context`, `analysis` 값 존재
6. 회상 시작 후 Solar가 만든 3단계 질문을 확인한다.
7. 원본 공개와 추가 기억 입력 후 개인 추억 카드가 생성되는지 확인한다.
8. 익명 공유 미리보기에서 개인 정보가 일반화됐는지 확인한다.
9. 서로 다른 사용자 3명의 조각을 모아 동네 추억 카드를 생성한다.
10. Upstage Console의 사용량 화면에서 호출 증가를 캡처한다.

---


## 8. 보조 AI: 추억 카드 이미지 생성

사진이 있는 카드는 원본 사진을 그대로 사용한다. 사진이 없는 카드만 Gemini Nano Banana를 통해 일러스트를 생성한다.

안전 프롬프트 원칙:

- 기록에 없는 사람·사건·물건을 추가하지 않음
- 실존 인물의 식별 가능한 얼굴 대신 뒷모습·실루엣 사용
- 이름·상호명·학교명·전화번호·로고·문구를 이미지에 넣지 않음
- 실제 사진처럼 위장하지 않고 상징적인 분위기로 표현
- 스타일은 사용자가 고르는 대신 기록 맥락에 따라 자동 선택

코드 위치:

```text
app/services/card_image.py
app/api/cards.py의 POST /cards/{card_id}/generate-image
tests/test_card_images.py
```

이 기능은 Upstage 3종 활용과 별개의 보조 기능이며, 서비스의 핵심 회상·구조화·이야기 생성은 Upstage API가 담당한다.

---

## 9. 한 문장 정리

> Document Parse가 사진 속 기록을 읽고, Information Extract가 기억의 사실을 구조화하며, Solar LLM이 그 사실을 벗어나지 않는 질문과 이야기를 생성해 사용자가 스스로 기억을 되살리도록 돕는다.
