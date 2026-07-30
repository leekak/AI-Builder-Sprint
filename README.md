# 다시, 그날 — Memory Recall API

서비스 목적, 전체 사용자 흐름, 개인정보·삭제 정책과 발표 시나리오는 [`PROJECT_OVERVIEW.md`](PROJECT_OVERVIEW.md)에 처음 보는 사람도 이해할 수 있도록 정리했습니다.

사진을 보기 전에 기억을 먼저 떠올리고, 원본을 확인한 뒤 새롭게 떠오른 내용을 더해 하나의 추억 카드로 완성하는 FastAPI 프로젝트입니다.

이 서비스는 기억 정확도나 정답률을 평가하지 않습니다. Solar는 회상을 유도하고 회상 전후의 내용을 자연스럽게 연결하는 역할만 합니다.

## 구현 범위

- 사진 0~1장과 코멘트 등록
- 이미지가 없을 때 Swagger가 `image=""`를 보내는 경우까지 처리
- 조건부 Document Parse OCR
- Information Extract 기반 사실 필드 구조화
- Solar 기반 제목·요약·회상 단서 생성
- 7일·30일 회상 일정과 데모 압축 모드
- 원본을 숨긴 회상 세션, 개방형 질문, 답변 저장
- 원본 공개 후 추가 회상 저장
- 개인 추억 카드 생성·조회·보관
- Nano Banana 기반 텍스트 추억 이미지 자동 생성(원본 사진이 없는 카드만)
- 생성 이미지 비공개 Storage 저장, 원본 복원·재생성·삭제
- 1·2차 회상 과정을 한 카드에서 확인하는 회상 타임라인
- 작성 중 회상 답변의 브라우저 자동 임시저장
- 동네 공유 전 Solar 비식별 결과 미리보기와 사용자 최종 확인
- 프리셋 장소 태그와 opt-in 동네 공유
- 장소별 하나의 동네 카드와 새 참여자 3명 단위 수동 갱신
- 동일 사용자의 여러 공유 카드를 한 명·한 조각으로 묶는 공정한 집계
- Solar 중립화와 서버 강제 치환을 함께 적용한 공개 카드 비속어 검열
- 익명 시드 데이터
- SQLite 로컬 모드와 Supabase Postgres/Storage 모드
- 외부 키 없이 동작하는 mock AI 모드
- 따뜻한 다이어리 톤의 반응형 전체 플로우 데모 UI
- `PLACE_TAGS` 기반 장소 선택, 카드 완성 후 익명 동네 공유
- 동네별 기여 현황과 실제 `town_cards` 조회·생성
- Leaflet과 통계청 기반 실제 부산 16개 구·군 경계로 구성한 동네 추억 지도와 50개 지역 상태 마커
- 기억 장소와 익명 공유 장소를 분리해 공유 취소 후에도 원래 장소 유지
- 동일한 기여 조합의 중복 갱신 차단과 공개 카드 버전 표시
- 기억 저장 후 AI 처리 실패 시 분석 재시도 UI
- 답변 저장·원본 공개 상태를 복원하는 회상 이어하기
- 같은 날짜의 여러 기록을 순서·장소·범주형 단서로 구분하되 원본 내용은 숨기는 회상 목록
- Solar 비식별화, Information Extract 민감 후보 추출, 백엔드 누출 검사를 거치는 동네 카드 개인정보 보호 파이프라인
- API·등록·회상·개인 카드·동네 카드별 JavaScript 모듈 구조
- pytest 자동 테스트

## 프로젝트 구조

```text
memory-recall-project/
├── app/
│   ├── api/                 # memories, recalls, cards, archive, health
│   ├── services/            # Upstage/mock AI, 일정, Storage
│   ├── static/              # 발표용 반응형 데모 UI
│   │   ├── js/
│   │   │   ├── api.js       # HTTP·인증 헤더·오류 정규화
│   │   │   ├── register.js  # 기억 등록·장소 태그
│   │   │   ├── recall.js    # 회상·원본 공개·카드 완성
│   │   │   ├── cards.js     # 개인 카드·동네 공유
│   │   │   ├── town.js      # 기여 현황·동네 카드
│   │   │   ├── utils.js     # 상태·표시 공통 함수
│   │   │   └── main.js      # 초기화·탭 오케스트레이션
│   │   ├── index.html
│   │   └── styles.css
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   └── main.py
├── data/uploads/            # 로컬 이미지 저장
├── scripts/
│   ├── seed.py              # 광안리 동네 회상 조각 4건
│   └── smoke_test.py        # 실행 서버 전체 흐름 점검
├── sql/supabase_schema.sql
├── tests/
├── .env.example
├── requirements.txt
├── pyproject.toml
└── run.py
```

## 1. 빠른 실행

Python 3.11 이상을 권장합니다.

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
cp .env.example .env           # Windows: copy .env.example .env
python run.py
```

접속 주소:

- 데모 UI: `http://127.0.0.1:8000/demo/`
- Swagger: `http://127.0.0.1:8000/docs`
- 상태 확인: `http://127.0.0.1:8000/health`

기본 `.env.example`은 `AI_MODE=mock`, `STORAGE_BACKEND=local`, SQLite로 설정되어 있으므로 외부 키 없이 전체 플로우가 동작합니다.

## 2. 자동 테스트

```bash
python -m pytest
```

테스트 범위:

- 이미지 없는 multipart 등록
- Swagger 형태의 빈 이미지 문자열 처리
- 이미지 업로드 및 소유자 확인 이미지 조회
- 이미지 없이 OCR 선택 시 차단
- 등록 → 분석 → 회상 → 공개 → 추가 회상 → 카드 전체 흐름
- 사용자 간 데이터 격리
- 동네 카드 최소 3명 조건
- 동네 카드 입력에서 원본 코멘트 제외
- 현재 Information Extract JSON 요청 계약과 한글 문서 렌더링

## 3. 이미지 0~1장 처리

`POST /memories`는 `multipart/form-data`를 사용합니다. 이미지가 없으면 프런트엔드에서 `image` 필드를 아예 추가하지 않는 것이 가장 좋습니다.

```javascript
const formData = new FormData();
formData.append("comment", comment);
formData.append("memory_date", memoryDate);
formData.append("use_ocr", "false");
formData.append("place_label", "광안리 해수욕장 앞 작은 카페"); // 선택 사항, 자유 입력

if (selectedImage instanceof File) {
  formData.append("image", selectedImage);
}
```

Swagger UI가 파일 미선택 상태에서 아래처럼 빈 문자열을 보내더라도 백엔드가 `None`으로 정규화합니다.

```bash
-F 'image='
```

실제 파일이 없는데 `use_ocr=true`이면 400 오류를 반환합니다.

## 4. 핵심 API 흐름

### 화면에서의 전체 사용 흐름

```text
1. 기억 등록
   사진(선택) + 코멘트 + 날짜 + 장소 태그를 저장
   → 조건부 OCR → 사실 정보 추출 → 제목·요약·회상 단서 생성

2. 오늘의 회상
   원본을 숨긴 질문 확인 → 먼저 떠오른 답변 작성 → 답변 저장
   → 저장이 끝난 뒤에만 원본 공개 버튼 활성화
   → 작성 중인 내용은 현재 사용자·회상 세션별로 브라우저에 자동 임시저장

3. 원본 공개와 카드 완성
   원본 사진·코멘트 확인 → 새롭게 떠오른 기억 추가
   → 1차 회상은 추억 카드를 생성하고, 2차 회상은 같은 카드에 내용을 누적·갱신
   → 원하는 경우 장소를 확인하고 익명 동네 공유

4. 내 추억 카드
   완성한 카드와 1·2차 회상 타임라인을 조회
   → 원본 사진이 있으면 별도 변환 없이 그대로 표시
   → 사진이 없으면 한 번의 버튼으로 카드 내용에 어울리는 추억 이미지 생성
   → 이미지 표현 방식은 서비스가 기억의 맥락에 맞춰 자동 선택
   → 카드를 숨기거나 다시 복구할 수 있으며, 영구 삭제와 구분
   → 동네 공유 장소 변경 또는 공유 취소 가능
   → 공유 전 실제로 저장될 비식별 문장을 확인하고 동의

5. 동네 추억 카드
   실제 기여 인원과 최소 인원 충족 상태 조회
   → 조건 충족 시 여러 사람의 회상 조각으로 공동체 카드 생성
```

Step 2는 기억을 채점하는 단계가 아닙니다. 첫 화면에는 넓은 개방형 질문 하나만 표시하고, 잘 떠오르지 않으면 원본을 공개하지 않은 채 감각·분위기 중심의 약한 힌트부터 활동·장소 범주의 단서까지 순차적으로 열 수 있습니다. 힌트를 보고 떠오른 내용은 단계별로 보존되며, 마지막 힌트 뒤에도 기억나지 않는 경우에만 회상 시도를 저장하고 원본 확인으로 이동합니다. 답변을 저장하기 전에는 원본 공개 버튼이 비활성화됩니다.

추억 카드는 회상 횟수가 아니라 원본 기억을 기준으로 관리합니다. 하나의 기억을 7일 뒤와 30일 뒤에 두 번 회상해도 카드는 한 장만 유지되며, 두 번째 회상에서 새롭게 떠오른 내용은 기존 카드에 이어집니다.

회상 일정은 알림 발송 시간이 아니라 해당 기억이 `오늘의 회상` 목록에 활성화되는 시점입니다. 현재 MVP에는 푸시·이메일 알림이 포함되지 않습니다.

장소 입력은 개인 기록에 구체적인 원문을 유지합니다. 동네 공유용 표준 태그는 주요 생활권과 별칭(예: 자갈치시장 → 남포동, 전포카페거리 → 서면)을 이용해 추천하고, 사용자가 최종 확정합니다.

동네 공유 미리보기에는 10분 동안 유효한 서버 서명을 붙입니다. 사용자가 확인한 문장과 최종 저장 문장이 달라지거나 브라우저에서 내용이 변조되는 것을 막으려면 배포 환경의 `.env`에 충분히 긴 임의 문자열을 설정하세요.

```env
SHARE_PREVIEW_SECRET=replace-with-a-long-random-secret
```

### 기억 등록 및 분석

```text
POST /memories
POST /memories/{memory_id}/parse       # use_ocr=true일 때
POST /memories/{memory_id}/extract
POST /memories/{memory_id}/analyze
PATCH /memories/{memory_id}/place-tag   # AI 추천 표준 지역 확인·변경
DELETE /memories/{memory_id}           # 개인 기억과 연결 자료 삭제
```

데모나 프런트엔드에서는 아래 편의 API로 세 단계를 연속 실행할 수 있습니다.

```text
POST /memories/{memory_id}/process
```

### 회상

```text
GET  /recalls/due
POST /recalls
POST /recalls/{recall_id}/questions
POST /recalls/{recall_id}/answers
POST /recalls/{recall_id}/reveal
POST /recalls/{recall_id}/additional-memory
POST /recalls/{recall_id}/complete
```

`GET /recalls/due` 응답에는 원본 코멘트와 이미지 URL이 포함되지 않습니다.
같은 날짜에 여러 기억이 있으면 `day_sequence`, `same_day_count`로 순서를 구분하고, 확정된 `place_tag`와 `cue_categories`만 제공합니다. 범주형 단서는 사람·장소·활동·분위기·감정 수준으로 제한해 회상 전에 정답이 노출되지 않도록 합니다.

### 카드

```text
GET  /cards
GET  /cards/{card_id}
POST /cards/{card_id}/archive
POST /cards/{card_id}/share-to-town
POST /cards/{card_id}/share-preview
```

카드가 완성된 뒤에만 익명 공유 동의를 받습니다. 요청과 저장 필드의 대응은 다음과 같습니다.

```text
요청: consent + place_tag
카드: shared_to_town + place_tag
기억: share_to_town + place_tag
기여: town_contributions 행 생성/삭제
```

장소 정보는 두 필드로 분리합니다.

```text
place_label          사용자가 자유롭게 입력한 구체적인 장소. 개인 기록에 그대로 보존
suggested_place_tag  Information Extract 결과와 입력 장소에서 찾은 표준 지역 추천값
place_tag            사용자가 확인한 동네 카드 그룹용 표준 태그
```

기억 등록 후 AI가 표준 지역을 추천하지만 자동 확정하지 않습니다. 사용자가 `PATCH /memories/{memory_id}/place-tag` 또는 화면의 `지역 태그 확정`을 실행해야 `place_tag`가 저장됩니다. `place_tag` 확정도 동네 공개 동의로 간주하지 않으며 기본값은 항상 비공유입니다.

### 삭제 정책

`DELETE /memories/{memory_id}`는 다음 원칙을 적용합니다.

- 원본 사진·코멘트·OCR/분석 결과·회상 세션·개인 추억 카드·사용자 연결은 삭제합니다.
- 아직 동네 카드에 사용되지 않은 공유 조각은 함께 완전히 삭제합니다.
- 이미 발행된 동네 카드에 사용된 조각은 기존 동네 카드를 깨뜨리지 않도록 유지하되, Solar로 다시 비식별화한 뒤 `town_archived_fragments`로 옮깁니다.
- `town_archived_fragments`에는 `owner_id`, `memory_id`, `card_id`, `recall_id`가 없어 작성자에게 다시 연결할 수 없습니다.
- 공유 시점부터 `town_contributions`에는 원문이 아니라 비식별화·일반화된 문장만 저장합니다.

기존 Supabase 프로젝트에는 아래 마이그레이션을 SQL Editor에서 한 번 실행해야 합니다.

```text
sql/migrations/002_town_archived_fragments.sql
sql/migrations/003_memory_place_labels.sql
sql/migrations/004_living_town_cards.sql
sql/migrations/005_memory_card_generated_images.sql
```

### Nano Banana 추억 카드 이미지

실제 Gemini API를 사용할 때 `.env`를 다음처럼 설정합니다.

```env
CARD_IMAGE_GENERATION_ENABLED=true
CARD_IMAGE_MODE=gemini
GEMINI_API_KEY=Google_AI_Studio에서_발급한_키
NANO_BANANA_MODEL=gemini-3.1-flash-image
NANO_BANANA_TIMEOUT_SECONDS=120
```

외부 호출 없이 UI와 Storage 흐름만 시험하려면 `CARD_IMAGE_MODE=mock`을 사용합니다. `auto`는 Gemini 호출 실패 시 mock 이미지로 대체하므로 실제 연동 검증에는 사용하지 않는 것이 좋습니다.

```text
POST   /cards/{card_id}/generate-image
GET    /cards/{card_id}/generated-image
DELETE /cards/{card_id}/generated-image
```

사진이 있는 카드는 원본 사진을 그대로 사용하며 이미지 생성 버튼을 표시하지 않습니다. 따라서 원본 사진은 이미지 생성을 위해 Google API로 전송되지 않습니다. 사진이 없는 카드에서만 카드 내용을 바탕으로 이미지를 생성하며, 사용자가 화풍을 고르지 않아도 기억의 맥락에 맞는 표현 방식을 서비스가 자동 선택합니다. 생성 결과에는 화면에서 `AI로 만든 추억 이미지` 라벨을 표시합니다.

화면의 `최근 맡긴 기억` 또는 개인 추억 카드에서 삭제할 수 있으며, 되돌릴 수 없는 범위와 익명 조각 보존 여부를 확인한 뒤 실행합니다.

### 동네 아카이브

```text
GET  /place-tags
GET  /archive/places
GET  /archive/places/statuses
GET  /archive/places/{place_tag}/status
POST /archive/places/{place_tag}/card
DELETE /archive/places/cards/{card_id}   # 관리자 계정 전용
POST /admin/login
GET  /admin/me
```

동네 카드에는 아래 정보만 전달됩니다.

- 원본 공개 전 회상 답변
- 원본 공개 후 새롭게 떠오른 기억

동네 카드를 생성할 때는 원본 회상 조각을 곧바로 이야기 생성에 사용하지 않습니다.

```text
공유 동의된 회상 조각
→ 공유 시점에 Solar로 개인 식별 정보·희귀 사건을 제거해 DB 저장
→ Information Extract로 이름·다른 정밀 장소 후보 추출
→ Solar로 이름·소속·경로·희귀 사건 제거 및 공통 주제 일반화
→ 비식별화된 공통 주제로만 동네 카드 생성
→ 백엔드가 차단 표현의 최종 결과 잔존 여부 검사
→ 통과한 카드만 저장·공개
```

장소마다 공개 카드는 한 장만 유지합니다. 최초에는 서로 다른 사용자 3명이 필요하고,
발행 뒤에는 이전 발행에 포함되지 않은 새 사용자 3명이 모였을 때 같은 카드의 내용과
버전을 갱신합니다. 한 사용자가 같은 장소에 여러 개인 카드를 공유해도 기여자 수는 1명이며,
여러 조각은 하나로 합쳐져 다른 참여자와 같은 가중치로 처리됩니다.

개인 기억을 삭제해도 이미 발행된 동네 카드는 바뀌지 않습니다. 발행에 사용된 조각은
사용자·기억·개인 카드 연결을 제거한 익명 보존 조각으로 전환됩니다. 공개 전 단계와 최종
카드 저장 직전에 비속어를 중립 표현으로 치환하므로 입력의 욕설이 공개 카드에 그대로
노출되지 않습니다.

최종 결과에 차단 표현이 남으면 카드 생성은 실패 처리되며 DB에 저장되지 않습니다.
개인정보 보호 파이프라인 도입 전에 생성된 레거시 동네 카드는 공개 목록에서 숨기며, 같은 장소의 카드 생성 버튼을 다시 실행하면 최신 파이프라인으로 안전하게 재처리됩니다.

원본 사진, 원본 코멘트 전체, 사용자 식별 정보는 Solar 입력에 포함하지 않습니다.

## 5. 회상 데모 모드

```env
DEMO_MODE=true
DEMO_DAY_SECONDS=2
FIRST_RECALL_DAYS=7
SECOND_RECALL_DAYS=30
```

이 설정에서는 1일을 2초로 환산하므로 첫 회상은 등록 14초 뒤, 두 번째 회상은 60초 뒤에 도래합니다.

발표 중 즉시 테스트하려면 등록 폼에서 `first_recall_days=0`을 사용할 수 있습니다.

운영 설정:

```env
DEMO_MODE=false
FIRST_RECALL_DAYS=7
SECOND_RECALL_DAYS=30
```

## 6. Upstage 연동

`.env`를 다음처럼 설정합니다.

```env
AI_MODE=upstage
UPSTAGE_API_KEY=발급받은_API_KEY
UPSTAGE_SOLAR_MODEL=solar-pro3
```

모드 차이:

- `mock`: 외부 호출 없음
- `auto`: API 키가 있으면 Upstage를 사용하고, 설정에 따라 실패 시 mock으로 전환
- `upstage`: Upstage 오류를 숨기지 않고 502로 반환

기본 호출 위치:

- Solar: `${UPSTAGE_BASE_URL}/chat/completions`
- Document Parse: `UPSTAGE_DOCUMENT_PARSE_URL`
- Information Extract: `UPSTAGE_INFORMATION_EXTRACT_URL`

Upstage URL과 모델명은 환경변수로 분리했습니다. 기본 구현은 현재 API 계약에 맞춰 다음 형식을 사용합니다.

- Document Parse: 이미지 파일을 `multipart/form-data`의 `document`로 전달
- Information Extract: `messages[].content[].image_url`과 `response_format.json_schema`를 포함한 JSON 요청
- Solar: OpenAI 호환 Chat Completions JSON 요청

Information Extract는 문서·이미지를 입력으로 받기 때문에, 서비스가 분석해야 할 **코멘트 + 선택적 OCR 결과**를 서버에서 한글 PNG 문서로 렌더링한 뒤 data URL로 전달합니다. 따라서 원본 사진이 없는 기억도 같은 구조화 단계를 거칠 수 있습니다. 자동 탐색되는 한글 시스템 글꼴이 없는 환경에서는 다음 값을 지정하세요.

```env
UPSTAGE_TEXT_RENDER_FONT_PATH=/absolute/path/to/korean-font.ttf
```

Information Extract에는 아래 JSON Schema를 요구합니다.

```json
{
  "people": [],
  "places": [],
  "activities": [],
  "atmosphere": [],
  "emotions": []
}
```

Solar 프롬프트에는 다음 제한을 명시했습니다.

- 기억을 채점하지 않음
- 원문에 없는 사건·인물·감정을 생성하지 않음
- 동네 카드에서 반복되지 않은 감정을 공동체의 공통 감정으로 일반화하지 않음

## 7. Supabase 연결

### Database

Supabase 대시보드의 Postgres 또는 Pooler 접속 문자열을 SQLAlchemy 형식으로 넣습니다.

```env
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:6543/postgres
```

두 가지 방법 중 하나를 사용합니다.

1. `AUTO_CREATE_TABLES=true`로 FastAPI 시작 시 테이블 생성
2. Supabase SQL Editor에서 `sql/supabase_schema.sql` 실행

### Storage

```env
STORAGE_BACKEND=supabase
SUPABASE_URL=https://PROJECT.supabase.co
SUPABASE_SERVICE_ROLE_KEY=서비스_역할_키
SUPABASE_STORAGE_BUCKET=memory-images
```

`sql/supabase_schema.sql`은 private `memory-images` bucket 생성문도 포함합니다.

서비스 역할 키는 서버 전용입니다. 브라우저 코드나 공개 저장소에 넣으면 안 됩니다.

원본 사진은 public URL로 노출하지 않습니다. FastAPI가 `/memories/{memory_id}/image` 요청에서 소유자를 확인한 뒤 파일을 프록시합니다.

## 8. 인증 모드

```env
AUTH_MODE=demo
```

- `demo`: `X-User-Id`가 없으면 `DEMO_USER_ID` 사용
- `header`: 모든 개인 API에 `X-User-Id` 필수
- `supabase`: Bearer JWT의 `sub`를 사용자 ID로 사용

Supabase JWT 모드는 현재 HS256 JWT secret 방식입니다. 프로젝트가 비대칭 JWT/JWKS를 사용한다면 인증 의존성을 해당 프로젝트 설정에 맞춰 확장해야 합니다.

## 9. 동네 카드 시드

```bash
python scripts/seed.py
```

광안리로 공유 동의된 서로 다른 사용자 4명의 익명 회상 조각이 삽입됩니다.

그다음:

```text
POST /archive/places/광안리/card
```

를 호출하면 동네 추억 카드가 생성됩니다.

`ADMIN_KEY`를 설정했다면 요청에 아래 헤더가 필요합니다.

```text
X-Admin-Key: 설정한_키
```

### 관리자 계정과 동네 카드 삭제

데모 사용자 이름을 `admin`으로 바꾸는 것은 관리자 로그인이 아닙니다. 관리자 계정은 아래 환경변수로 별도 설정합니다.

```env
ADMIN_USERNAME=admin
ADMIN_PASSWORD=충분히_긴_관리자_비밀번호
ADMIN_TOKEN_SECRET=별도로_생성한_긴_무작위_문자열
ADMIN_TOKEN_HOURS=8
```

`ADMIN_TOKEN_SECRET`은 `openssl rand -hex 32`로 생성할 수 있으며 비밀번호와 다른 값을 사용해야 합니다. 서버를 재시작한 뒤 화면 상단의 `관리자 로그인`을 이용합니다. 로그인 토큰은 현재 브라우저 탭 세션에만 저장되고, 관리자에게만 동네 카드의 `동네 카드 삭제` 버튼이 표시됩니다. 삭제해도 사용자가 공유한 비식별 기억 조각은 유지되므로 나중에 관리자가 카드를 다시 생성할 수 있습니다.

기존 자동화나 발표 스크립트를 위한 `ADMIN_KEY` 헤더 방식은 동네 카드 생성 API에 한해 호환 목적으로 유지됩니다. 동네 카드 삭제는 반드시 관리자 계정 로그인 토큰을 요구합니다.

## 10. 실제 서버 스모크 테스트

서버 실행 후:

```bash
python scripts/smoke_test.py
```

등록부터 추억 카드 생성까지 HTTP 요청으로 점검합니다.

## 상태 전이

```text
registered
  → OCR 선택 시 parsed
  → extracted
  → processed
  → recall_in_progress
  → 1차 완료 후 processed
  → 2차 완료 후 recalled
```

각 AI 단계는 `pending`, `processing`, `completed`, `skipped`, `failed` 상태를 별도로 저장합니다.

## 구현상 의도적인 선택

- 동네 카드는 자동 cron이 아니라 수동 버튼으로 생성합니다.
- 기여자 수는 레코드 수가 아니라 서로 다른 `owner_id` 수로 판정합니다.
- 같은 사용자의 여러 기록만으로 최소 인원을 충족할 수 없습니다.
- 카드 공유 기본값은 비공유입니다.
- 사용자가 공유를 취소하면 동네 기여 레코드도 삭제합니다.
- 정확도 점수, 정답률, 오답 판정 필드는 존재하지 않습니다.
